import asyncio
import logging
import os
import time
from io import BytesIO
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, Request, Response
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ai_companion.graph import graph_builder
from ai_companion.interfaces.whatsapp.safety import (
    idempotency_store,
    normalize_phone_number,
    validate_incoming_event,
    validate_outgoing_send,
)
from ai_companion.modules.image import ImageToText
from ai_companion.modules.speech import SpeechToText, TextToSpeech
from ai_companion.settings import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Global module instances (one each — thread-safe for async use)
# ─────────────────────────────────────────────────────────────────────────────

speech_to_text = SpeechToText()
text_to_speech = TextToSpeech()
image_to_text = ImageToText()


# ─────────────────────────────────────────────────────────────────────────────
# Per-user async locks: prevent concurrent processing of messages from the
# same user (or any race across users sharing the SQLite checkpoint DB).
# ─────────────────────────────────────────────────────────────────────────────

_user_locks: Dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    """Return the asyncio.Lock dedicated to this user, creating it if needed."""
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


# ─────────────────────────────────────────────────────────────────────────────
# Router — only 2 routes: GET /webhook and POST /webhook
# ─────────────────────────────────────────────────────────────────────────────

whatsapp_router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: read env vars at call time (not import time)
# ─────────────────────────────────────────────────────────────────────────────

def get_whatsapp_token() -> str:
    return (os.getenv("WHATSAPP_TOKEN") or "").strip()


def get_whatsapp_phone_number_id() -> str:
    return (os.getenv("WHATSAPP_PHONE_NUMBER_ID") or "").strip()


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 1 — GET /webhook
# Meta calls this once to verify your webhook URL
# ─────────────────────────────────────────────────────────────────────────────

@whatsapp_router.get("/webhook", summary="Webhook verification by Meta")
async def verify_webhook(request: Request) -> Response:
    """
    Meta sends a GET request with hub.verify_token and hub.challenge.
    We must echo back hub.challenge if the token matches.
    """
    params = request.query_params
    verify_token = (os.getenv("WHATSAPP_VERIFY_TOKEN") or "").strip()

    if params.get("hub.verify_token") == verify_token:
        logger.info("Webhook verified successfully.")
        return Response(content=params.get("hub.challenge"), status_code=200)

    logger.warning("Webhook verification failed — token mismatch.")
    return Response(content="Verification token mismatch", status_code=403)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE 2 — POST /webhook
# Meta sends every incoming WhatsApp message here
# ─────────────────────────────────────────────────────────────────────────────

@whatsapp_router.post("/webhook", summary="Receive incoming WhatsApp messages")
async def receive_message(request: Request) -> Response:
    """
    Handles all incoming WhatsApp messages (text, audio/voice, image).

    Safety guarantees:
    - Deduplication: duplicate webhook deliveries (same message_id) are ignored.
    - Per-user lock: only one message per user is processed at a time.
    - Recipient safety: response is always sent to the exact `from_number`
      extracted from the current webhook payload — never a cached or global value.
    - Contact name: the WhatsApp saved contact name is extracted and passed
      into the graph so EVA can store and use it naturally.
    - Voice note flag: voice/audio messages always receive a voice note reply.
    """
    try:
        data = await request.json()

        # Navigate to the change value safely
        try:
            change_value = data["entry"][0]["changes"][0]["value"]
        except (KeyError, IndexError):
            logger.warning("Malformed webhook payload — missing entry/changes/value")
            return Response(content="OK", status_code=200)

        # ── Incoming message ──────────────────────────────────────────────────
        if "messages" in change_value:
            message = change_value["messages"][0]
            message_id: str = message.get("id", "")
            from_number: str = message.get("from", "")
            msg_timestamp = message.get("timestamp")

            # ── Safety & Idempotency Guard ─────────────────────────────────
            is_valid, reason = validate_incoming_event(
                event_type="MESSAGES",
                message_id=message_id,
                sender_number=from_number,
                message_timestamp=msg_timestamp,
                from_me=False,
            )
            if not is_valid:
                logger.info(
                    "[SAFETY] Webhook event rejected (%s) | message_id=%s | from=%s",
                    reason, message_id, from_number,
                )
                return Response(content="OK", status_code=200)

            # Mark processed atomically
            if not idempotency_store.mark_processed(message_id):
                logger.info(
                    "[DEDUP] Duplicate message_id already processed: %s",
                    message_id,
                )
                return Response(content="OK", status_code=200)

            # ── Stable isolated user & session ID ─────────────────────────
            clean_from = normalize_phone_number(from_number)
            session_id: str = f"whatsapp_{clean_from}"

            # ── Extract saved contact name (may be absent) ─────────────────
            contact_name: str = ""
            try:
                contacts = change_value.get("contacts", [])
                if contacts:
                    contact_name = (
                        contacts[0]
                        .get("profile", {})
                        .get("name", "")
                        or ""
                    ).strip()
                    if contact_name:
                        logger.info(
                            "Contact name for %s: '%s'", from_number, contact_name
                        )
            except Exception as name_err:
                logger.warning("Failed to extract contact name: %s", name_err)

            # ── Process message under per-user lock ────────────────────────
            user_lock = _get_user_lock(session_id)
            async with user_lock:
                return await _process_message(
                    message=message,
                    from_number=from_number,
                    session_id=session_id,
                    contact_name=contact_name,
                    incoming_message_id=message_id,
                )

        # ── Status update (delivery receipts, read receipts, etc.) ──────────
        elif "statuses" in change_value:
            return Response(content="OK", status_code=200)

        else:
            logger.debug("Unknown webhook event type — ignoring.")
            return Response(content="OK", status_code=200)

    except Exception as e:
        logger.error("Error in receive_message: %s", e, exc_info=True)
        return Response(content="Internal server error", status_code=500)


# ─────────────────────────────────────────────────────────────────────────────
# Internal: process a single validated message
# ─────────────────────────────────────────────────────────────────────────────

async def _process_message(
    message: Dict,
    from_number: str,
    session_id: str,
    contact_name: str,
    incoming_message_id: str = "",
) -> Response:
    """
    Build the AI graph input, run the graph, and send the response.

    `from_number` is a local variable — it can NEVER be confused with another
    user's number because it was extracted from the same webhook payload above.
    """
    msg_type: str = message.get("type", "")
    is_voice_note: bool = False
    content: str = ""

    # ── Build message content ─────────────────────────────────────────────
    try:
        if msg_type in ["audio", "voice"]:
            # WhatsApp voice notes → transcribe and flag for voice reply
            content = await process_audio_message(message)
            is_voice_note = True
            logger.info(
                "Voice note from %s transcribed: %r", from_number, content[:80]
            )

        elif msg_type == "image":
            content = message.get("image", {}).get("caption", "")
            image_bytes = await download_media(message["image"]["id"])
            try:
                description = await image_to_text.analyze_image(
                    image_bytes,
                    "Please describe what you see in this image in the context of our conversation.",
                )
                content += f"\n[Image Analysis: {description}]"
            except Exception as img_err:
                logger.warning("Failed to analyze image: %s", img_err)

        else:
            # Plain text message
            content = message.get("text", {}).get("body", "") or ""

    except Exception as content_err:
        logger.error(
            "Failed to process incoming media from %s: %s", from_number, content_err,
            exc_info=True,
        )
        # Send fallback text so the user isn't left waiting
        await send_text(
            from_number,
            "Sorry, I couldn't process that message. Can you try again?",
            incoming_message_id=incoming_message_id,
            sender_number=from_number,
        )
        return Response(content="Media processing error", status_code=200)

    if not content.strip():
        logger.info("Empty content from %s — skipping", from_number)
        return Response(content="OK", status_code=200)

    # ── Ensure memory DB directory exists ─────────────────────────────────
    db_dir = os.path.dirname(settings.SHORT_TERM_MEMORY_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # ── Run AI agent graph ─────────────────────────────────────────────────
    try:
        async with AsyncSqliteSaver.from_conn_string(
            settings.SHORT_TERM_MEMORY_DB_PATH
        ) as short_term_memory:
            graph = graph_builder.compile(checkpointer=short_term_memory)

            graph_input = {
                "messages": [HumanMessage(content=content)],
                "user_id": session_id,
                "is_voice_note": is_voice_note,
                "contact_name": contact_name,
            }
            graph_config = {
                "configurable": {
                    "thread_id": session_id,
                    "user_id": session_id,
                }
            }

            await graph.ainvoke(graph_input, graph_config)
            output_state = await graph.aget_state(config=graph_config)

    except Exception as graph_err:
        logger.error(
            "Graph execution failed for user %s: %s", from_number, graph_err,
            exc_info=True,
        )
        await send_text(
            from_number,
            "Something went wrong on my end. Give me a sec!",
            incoming_message_id=incoming_message_id,
            sender_number=from_number,
        )
        return Response(content="Graph error", status_code=200)

    # ── Extract graph outputs ──────────────────────────────────────────────
    workflow: str = output_state.values.get("workflow", "conversation")
    response_message: str = output_state.values["messages"][-1].content

    # ── Send reply ─────────────────────────────────────────────────────────
    success = False

    if workflow == "audio":
        audio_buffer: Optional[bytes] = output_state.values.get("audio_buffer")
        if audio_buffer and len(audio_buffer) > 0:
            success = await send_response(
                from_number,
                response_message,
                "audio",
                audio_buffer,
                incoming_message_id=incoming_message_id,
                sender_number=from_number,
            )
        else:
            logger.warning(
                "Audio workflow but no audio_buffer for %s — falling back to text",
                from_number,
            )
            success = await send_response(
                from_number,
                response_message,
                "text",
                incoming_message_id=incoming_message_id,
                sender_number=from_number,
            )

    elif workflow == "image":
        image_path: str = output_state.values.get("image_path", "")
        if image_path and os.path.isfile(image_path):
            try:
                with open(image_path, "rb") as f:
                    image_data = f.read()
                success = await send_response(
                    from_number,
                    response_message,
                    "image",
                    image_data,
                    incoming_message_id=incoming_message_id,
                    sender_number=from_number,
                )
            except Exception as read_err:
                logger.error(
                    "Failed to read generated image at '%s': %s", image_path, read_err
                )
                success = await send_response(
                    from_number,
                    response_message,
                    "text",
                    incoming_message_id=incoming_message_id,
                    sender_number=from_number,
                )
        else:
            logger.warning(
                "Image workflow but no valid image_path ('%s') for %s — falling back to text",
                image_path, from_number,
            )
            success = await send_response(
                from_number,
                response_message,
                "text",
                incoming_message_id=incoming_message_id,
                sender_number=from_number,
            )

    else:
        success = await send_response(
            from_number,
            response_message,
            "text",
            incoming_message_id=incoming_message_id,
            sender_number=from_number,
        )

    if not success:
        logger.error("Failed to send reply to %s", from_number)
        return Response(content="Failed to send message", status_code=500)

    return Response(content="Message processed", status_code=200)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers (not routes)
# ─────────────────────────────────────────────────────────────────────────────

async def download_media(media_id: str) -> bytes:
    """Download a media file from WhatsApp servers."""
    token = get_whatsapp_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(
            f"https://graph.facebook.com/v21.0/{media_id}",
            headers=headers,
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("url")

        media_resp = await client.get(download_url, headers=headers)
        media_resp.raise_for_status()
        return media_resp.content


async def process_audio_message(message: Dict) -> str:
    """Download audio from WhatsApp and transcribe to text."""
    token = get_whatsapp_token()

    # WhatsApp can send type="audio" or type="voice"; the payload key matches the type
    audio_obj = message.get("audio") or message.get("voice") or {}
    audio_id = audio_obj.get("id")
    if not audio_id:
        raise ValueError("Audio message missing ID")

    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(
            f"https://graph.facebook.com/v21.0/{audio_id}",
            headers=headers,
        )
        meta_resp.raise_for_status()
        download_url = meta_resp.json().get("url")

        audio_resp = await client.get(download_url, headers=headers)
        audio_resp.raise_for_status()

    audio_data = BytesIO(audio_resp.content)
    audio_data.seek(0)
    transcription = await speech_to_text.transcribe(audio_data.read())
    return transcription


async def send_text(
    to_number: str,
    text: str,
    incoming_message_id: str = "",
    sender_number: str = "",
) -> bool:
    """Convenience wrapper to send a plain text message with outgoing validation."""
    return await send_response(
        to_number,
        text,
        "text",
        incoming_message_id=incoming_message_id,
        sender_number=sender_number or to_number,
    )


async def send_response(
    from_number: str,
    response_text: str,
    message_type: str = "text",
    media_content: Optional[bytes] = None,
    incoming_message_id: str = "",
    sender_number: str = "",
    event_type: str = "META_MESSAGE",
) -> bool:
    """
    Send a reply to the user via WhatsApp Cloud API.

    Enforces strict outgoing validation: response is only sent if
    incoming_message_id, sender_number, and recipient match.
    """
    # ── Strict outgoing gatekeeper validation ──────────────────────────────
    effective_sender = sender_number or from_number
    is_valid, reason = validate_outgoing_send(
        incoming_message_id=incoming_message_id,
        sender_number=effective_sender,
        outgoing_recipient=from_number,
        event_type=event_type,
    )
    if not is_valid:
        logger.error(
            "[SAFETY] Blocked WhatsApp send to %s: %s (incoming_id=%s, sender=%s)",
            from_number, reason, incoming_message_id, effective_sender,
        )
        return False
    token = get_whatsapp_token()
    phone_id = get_whatsapp_phone_number_id()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    json_data: Dict = {}

    if message_type in ["audio", "image"]:
        try:
            if not media_content or len(media_content) == 0:
                raise ValueError("media_content is empty — cannot upload")

            mime_type = "audio/mpeg" if message_type == "audio" else "image/png"
            media_id = await upload_media(BytesIO(media_content), mime_type)

            json_data = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": message_type,
                message_type: {"id": media_id},
            }

            if message_type == "image" and response_text:
                json_data["image"]["caption"] = response_text

        except Exception as upload_err:
            logger.error(
                "Media upload failed for %s (%s) — falling back to text: %s",
                from_number, message_type, upload_err,
            )
            message_type = "text"

    if message_type == "text":
        json_data = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {"body": response_text},
        }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/messages",
            headers=headers,
            json=json_data,
        )

    if response.status_code != 200:
        logger.error(
            "WhatsApp send failed to %s [%d]: %s",
            from_number, response.status_code, response.text,
        )
    else:
        logger.info(
            "Reply sent to %s as %s", from_number, message_type
        )

    return response.status_code == 200


async def upload_media(media_content: BytesIO, mime_type: str) -> str:
    """Upload audio or image to WhatsApp media servers and return the media ID."""
    token = get_whatsapp_token()
    phone_id = get_whatsapp_phone_number_id()
    headers = {"Authorization": f"Bearer {token}"}
    filename = "response.mp3" if "audio" in mime_type else "response.png"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://graph.facebook.com/v21.0/{phone_id}/media",
            headers=headers,
            files={"file": (filename, media_content, mime_type)},
            data={"messaging_product": "whatsapp", "type": mime_type},
        )
        result = response.json()

    if "id" not in result:
        raise Exception(f"Failed to upload media: {result}")

    logger.info("Uploaded media — id=%s mime=%s", result["id"], mime_type)
    return result["id"]
