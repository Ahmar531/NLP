import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()

import httpx

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field

from ai_companion.graph import graph_builder
from ai_companion.interfaces.whatsapp.safety import (
    SERVER_START_TIME,
    idempotency_store,
    normalize_phone_number,
    validate_incoming_event,
    validate_outgoing_send,
)
from ai_companion.modules.image import ImageToText
from ai_companion.modules.response_behavior import (
    calculate_initial_delay,
    calculate_inter_chunk_delay,
)
from ai_companion.modules.speech import SpeechToText, TextToSpeech
from ai_companion.settings import settings

# Per-user async locks to prevent race conditions across requests for the same user
_user_locks: Dict[str, asyncio.Lock] = {}


def _get_user_lock(user_id: str) -> asyncio.Lock:
    """Return an asyncio.Lock dedicated to this user, creating it if needed."""
    if user_id not in _user_locks:
        _user_locks[user_id] = asyncio.Lock()
    return _user_locks[user_id]


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(
    "ai_companion.api"
)


# ============================================================
# DIRECTORIES
# ============================================================

os.makedirs(
    "generated_images",
    exist_ok=True,
)

db_dir = os.path.dirname(
    settings.SHORT_TERM_MEMORY_DB_PATH
)

if db_dir:
    os.makedirs(
        db_dir,
        exist_ok=True,
    )


# ============================================================
# MODULES
# ============================================================

speech_to_text = SpeechToText()

text_to_speech = TextToSpeech()

image_to_text = ImageToText()


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="AI Companion",
    description=(
        "FastAPI backend for LangGraph AI Agent "
        "with Text, Audio, Vision and WhatsApp "
        "capabilities"
    ),
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STATIC IMAGES
# ============================================================

app.mount(
    "/images",
    StaticFiles(
        directory="generated_images"
    ),
    name="images",
)


# ============================================================
# EVOLUTION API CONFIGURATION
# ============================================================

EVOLUTION_API_URL = (
    os.getenv("EVOLUTION_API_URL")
    or settings.EVOLUTION_API_URL
    or "http://localhost:8080"
).rstrip("/")


EVOLUTION_API_KEY = (
    os.getenv("EVOLUTION_API_KEY")
    or settings.EVOLUTION_API_KEY
    or "D4C48552A640-4169-AB43-A4BACEF8347F"
)


EVOLUTION_INSTANCE = (
    os.getenv("EVOLUTION_INSTANCE")
    or settings.EVOLUTION_INSTANCE
    or "AVA"
)


logger.info(
    "Evolution API configured | url=%s | instance=%s",
    EVOLUTION_API_URL,
    EVOLUTION_INSTANCE,
)


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================


class ChatRequest(BaseModel):

    message: str = Field(
        ...,
        description="The user's text message",
    )

    session_id: Optional[str] = Field(
        "default_session",
        description=(
            "Session / thread ID for "
            "short-term conversation memory"
        ),
    )

    user_id: Optional[str] = Field(
        None,
        description=(
            "Persistent user ID for "
            "long-term memory"
        ),
    )


class ChatResponse(BaseModel):

    response: str

    workflow: str

    session_id: str

    image_url: Optional[str] = None

    audio_base64: Optional[str] = None

    transcription: Optional[str] = None

    image_analysis: Optional[str] = None


class MessageItem(BaseModel):

    role: str

    content: str


class HistoryResponse(BaseModel):

    session_id: str

    messages: List[MessageItem]


# ============================================================
# GRAPH EXECUTION
# ============================================================


async def run_agent_graph(
    session_id: str,
    user_content: str,
    user_id: Optional[str] = None,
    is_voice_note: bool = False,
    contact_name: str = "",
) -> Dict[str, Any]:

    """
    Execute LangGraph.

    session_id:
        Short-term conversation identity.

    user_id:
        Long-term user identity.

    session_id can change when a user starts
    a new conversation.

    user_id should remain stable for the same
    user so long-term memory can be retrieved.
    """

    try:

        # ----------------------------------------------------
        # STABLE USER ID
        # ----------------------------------------------------

        effective_user_id = (
            user_id
            or "default_user"
        )

        logger.info(
            "Running agent | session_id=%s | user_id=%s",
            session_id,
            effective_user_id,
        )

        # ----------------------------------------------------
        # SQLITE SHORT-TERM MEMORY
        # ----------------------------------------------------

        async with (
            AsyncSqliteSaver.from_conn_string(
                settings.SHORT_TERM_MEMORY_DB_PATH
            )
            as short_term_memory
        ):

            graph = graph_builder.compile(
                checkpointer=short_term_memory
            )

            # ------------------------------------------------
            # RUN LANGGRAPH
            # ------------------------------------------------

            await graph.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=user_content
                        )
                    ],

                    "user_id": (
                        effective_user_id
                    ),

                    # Pass WhatsApp-specific flags so nodes can use them
                    "is_voice_note": is_voice_note,
                    "contact_name": contact_name,
                },

                {
                    "configurable": {

                        "thread_id": (
                            session_id
                        ),

                        "user_id": (
                            effective_user_id
                        ),
                    }
                },
            )

            # ------------------------------------------------
            # GET LATEST STATE
            # ------------------------------------------------

            output_state = (
                await graph.aget_state(
                    config={
                        "configurable": {
                            "thread_id": (
                                session_id
                            ),
                            "user_id": (
                                effective_user_id
                            ),
                        }
                    }
                )
            )

        # ====================================================
        # RESPONSE
        # ====================================================

        workflow = (
            output_state.values.get(
                "workflow",
                "conversation",
            )
        )

        messages = (
            output_state.values.get(
                "messages",
                [],
            )
        )

        if messages:

            response_text = str(
                messages[-1].content
            )

        else:

            response_text = (
                "No response generated."
            )

        image_url = None

        audio_base64 = None

        # ====================================================
        # IMAGE WORKFLOW
        # ====================================================

        if workflow == "image":

            img_path = (
                output_state.values.get(
                    "image_path"
                )
            )

            if (
                img_path
                and os.path.exists(img_path)
            ):

                filename = (
                    os.path.basename(
                        img_path
                    )
                )

                image_url = (
                    f"/images/{filename}"
                )

        # ====================================================
        # AUDIO WORKFLOW
        # ====================================================

        elif workflow == "audio":

            raw_audio = (
                output_state.values.get(
                    "audio_buffer"
                )
            )

            if (
                raw_audio
                and len(raw_audio) > 0
            ):

                audio_base64 = (
                    base64.b64encode(
                        raw_audio
                    ).decode("utf-8")
                )

            else:

                try:

                    synth_audio = (
                        await text_to_speech.synthesize(
                            response_text
                        )
                    )

                    if synth_audio:

                        audio_base64 = (
                            base64.b64encode(
                                synth_audio
                            ).decode("utf-8")
                        )

                except Exception as tts_err:

                    logger.warning(
                        "Fallback TTS synthesis failed: %s",
                        tts_err,
                    )

        # ====================================================
        # RESPONSE BEHAVIOR
        # ====================================================

        resp_behavior = (
            output_state.values.get(
                "response_behavior"
            )
            or {}
        )

        return {

            "response": response_text,

            "workflow": workflow,

            "session_id": session_id,

            "image_url": image_url,

            # Return the local file path so the WhatsApp webhook
            # can open and send the image without going through
            # the /images static URL.
            "image_path": (
                output_state.values.get(
                    "image_path"
                )
                or ""
            ),

            # Return raw audio bytes for WhatsApp voice note sending.
            "audio_bytes": (
                output_state.values.get(
                    "audio_buffer"
                )
                or b""
            ),

            "audio_base64": audio_base64,

            "response_behavior": (
                resp_behavior
            ),

            "response_chunks": (
                resp_behavior.get(
                    "chunks"
                )
                or [response_text]
            ),

            "should_respond": (
                resp_behavior.get(
                    "should_reply",
                    True,
                )
            ),

            "initial_delay": (
                resp_behavior.get(
                    "initial_delay",
                    0.0,
                )
            ),

            "chunk_delay": (
                resp_behavior.get(
                    "chunk_delay",
                    0.0,
                )
            ),
        }

    except Exception as e:

        logger.error(
            "Error executing agent graph: %s",
            e,
            exc_info=True,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Agent graph execution error: "
                f"{str(e)}"
            ),
        )


# ============================================================
# EVOLUTION API
# SEND WHATSAPP MESSAGE
# ============================================================


async def send_whatsapp_message(
    number: str,
    text: str,
    incoming_message_id: str = "",
    sender_number: str = "",
    event_type: str = "MESSAGES_UPSERT",
) -> Dict[str, Any]:
    """
    Send a text message through Evolution API after strict safety validation.
    """
    # ── Strict outgoing gatekeeper validation ──────────────────────────────
    effective_sender = sender_number or number
    is_valid, reason = validate_outgoing_send(
        incoming_message_id=incoming_message_id,
        sender_number=effective_sender,
        outgoing_recipient=number,
        event_type=event_type,
    )
    if not is_valid:
        logger.error("[SAFETY] Outgoing WhatsApp message BLOCKED: %s", reason)
        return {"error": reason, "blocked": True}

    if not EVOLUTION_API_KEY:
        raise RuntimeError(
            "EVOLUTION_API_KEY is not configured."
        )

    url = (
        f"{EVOLUTION_API_URL}"
        f"/message/sendText/"
        f"{EVOLUTION_INSTANCE}"
    )

    payload = {
        "number": number,
        "text": text,
    }

    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY,
    }

    logger.info(
        "Sending WhatsApp message | number=%s | incoming_id=%s",
        number,
        incoming_message_id,
    )

    async with httpx.AsyncClient(
        timeout=30.0
    ) as client:
        response = await client.post(
            url,
            json=payload,
            headers=headers,
        )

        logger.info(
            "Evolution response | status=%s | body=%s",
            response.status_code,
            response.text[:1000],
        )

        response.raise_for_status()
        return response.json()


# ============================================================
# EVOLUTION API - FETCH MEDIA & SEND MEDIA / AUDIO
# ============================================================


async def fetch_evolution_media(message_data: dict) -> bytes:
    """
    Extract media bytes from Evolution API message payload or fetch via API.
    """
    if not EVOLUTION_API_KEY:
        raise RuntimeError("EVOLUTION_API_KEY is not configured.")

    # 1. Direct base64 in data
    b64_str = (
        message_data.get("base64")
        or message_data.get("media", {}).get("base64")
        or message_data.get("message", {}).get("imageMessage", {}).get("base64")
        or message_data.get("message", {}).get("audioMessage", {}).get("base64")
        or message_data.get("message", {}).get("pttMessage", {}).get("base64")
    )
    if b64_str and isinstance(b64_str, str) and len(b64_str) > 50:
        if "base64," in b64_str:
            b64_str = b64_str.split("base64,")[1]
        return base64.b64decode(b64_str)

    # 2. Fetch from Evolution API
    url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{EVOLUTION_INSTANCE}"
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY,
    }
    payload = {
        "message": message_data,
        "convertToMp4": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code in [200, 201]:
                data = res.json()
                b64_out = data.get("base64") or ""
                if b64_out:
                    if "base64," in b64_out:
                        b64_out = b64_out.split("base64,")[1]
                    return base64.b64decode(b64_out)
    except Exception as fetch_err:
        logger.warning("Error fetching media from Evolution API: %s", fetch_err)

    logger.warning("Could not extract media base64 from Evolution API message")
    return b""


async def send_whatsapp_image(
    number: str,
    image_bytes: bytes,
    caption: str = "",
    incoming_message_id: str = "",
    sender_number: str = "",
    event_type: str = "MESSAGES_UPSERT",
) -> Dict[str, Any]:
    """
    Send an image message through Evolution API after strict safety validation.
    """
    # ── Strict outgoing gatekeeper validation ──────────────────────────────
    effective_sender = sender_number or number
    is_valid, reason = validate_outgoing_send(
        incoming_message_id=incoming_message_id,
        sender_number=effective_sender,
        outgoing_recipient=number,
        event_type=event_type,
    )
    if not is_valid:
        logger.error("[SAFETY] Outgoing WhatsApp image BLOCKED: %s", reason)
        return {"error": reason, "blocked": True}

    if not EVOLUTION_API_KEY:
        raise RuntimeError("EVOLUTION_API_KEY is not configured.")

    url = f"{EVOLUTION_API_URL}/message/sendMedia/{EVOLUTION_INSTANCE}"
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "number": number,
        "mediatype": "image",
        "mimetype": "image/png",
        "caption": caption,
        "media": img_b64,
        "fileName": "photo.png",
    }
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY,
    }
    logger.info("Sending WhatsApp Image | number=%s | incoming_id=%s | caption=%s", number, incoming_message_id, caption[:50])
    async with httpx.AsyncClient(timeout=45.0) as client:
        res = await client.post(url, json=payload, headers=headers)
        logger.info("Evolution sendMedia | status=%s", res.status_code)
        res.raise_for_status()
        return res.json()


async def send_whatsapp_audio(
    number: str,
    audio_bytes: bytes,
    incoming_message_id: str = "",
    sender_number: str = "",
    event_type: str = "MESSAGES_UPSERT",
) -> Dict[str, Any]:
    """
    Send a voice note / audio message through Evolution API after strict safety validation.
    """
    # ── Strict outgoing gatekeeper validation ──────────────────────────────
    effective_sender = sender_number or number
    is_valid, reason = validate_outgoing_send(
        incoming_message_id=incoming_message_id,
        sender_number=effective_sender,
        outgoing_recipient=number,
        event_type=event_type,
    )
    if not is_valid:
        logger.error("[SAFETY] Outgoing WhatsApp audio BLOCKED: %s", reason)
        return {"error": reason, "blocked": True}

    if not EVOLUTION_API_KEY:
        raise RuntimeError("EVOLUTION_API_KEY is not configured.")

    url = f"{EVOLUTION_API_URL}/message/sendWhatsAppAudio/{EVOLUTION_INSTANCE}"
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    payload = {
        "number": number,
        "audio": audio_b64,
        "encoding": True,
    }
    headers = {
        "Content-Type": "application/json",
        "apikey": EVOLUTION_API_KEY,
    }
    logger.info("Sending WhatsApp Audio | number=%s | incoming_id=%s | size=%s bytes", number, incoming_message_id, len(audio_bytes))
    async with httpx.AsyncClient(timeout=45.0) as client:
        res = await client.post(url, json=payload, headers=headers)
        logger.info("Evolution sendWhatsAppAudio | status=%s", res.status_code)
        res.raise_for_status()
        return res.json()


# ============================================================
# WHATSAPP WEBHOOK
# ============================================================


@app.get(
    "/webhook/whatsapp",
    summary="Evolution API webhook verification probe",
)
async def whatsapp_webhook_verify():
    """
    Evolution API sends a GET to verify the webhook URL
    is reachable before forwarding POST message events.
    Must return 200 OK.
    """
    return {"status": "ok", "webhook": "whatsapp"}


@app.post(
    "/webhook/whatsapp",
    summary="Receive WhatsApp messages from Evolution API",
)
async def whatsapp_webhook(
    request: Request,
):
    """
    Evolution API
          ↓
    WhatsApp Webhook
          ↓
    LangGraph
          ↓
    Groq / Memory / Tools
          ↓
    Evolution API
          ↓
    WhatsApp
    """

    try:
        # ----------------------------------------------------
        # READ WEBHOOK BODY
        # ----------------------------------------------------
        data = await request.json()

        logger.info(
            "WhatsApp webhook received: %s",
            json.dumps(
                data,
                ensure_ascii=False,
            )[:5000],
        )

        # ----------------------------------------------------
        # EVENT
        # ----------------------------------------------------
        event = str(
            data.get(
                "event",
                "",
            )
        ).upper()

        normalized_event = event.replace(
            ".",
            "_",
        )

        logger.info(
            "WhatsApp event: %s | Normalized: %s",
            event,
            normalized_event,
        )

        # ----------------------------------------------------
        # MESSAGE DATA (can be dict, list, or nested in messages)
        # ----------------------------------------------------
        message_data = data.get(
            "data",
            {},
        )

        if isinstance(message_data, list) and len(message_data) > 0:
            message_data = message_data[0]

        if not isinstance(message_data, dict):
            return {
                "success": True,
                "ignored": True,
                "reason": "Invalid message data",
            }

        # Check for nested messages array in data
        if "messages" in message_data and isinstance(message_data["messages"], list) and len(message_data["messages"]) > 0:
            message_data = message_data["messages"][0]

        # ----------------------------------------------------
        # KEY + MESSAGE
        # ----------------------------------------------------
        key = message_data.get(
            "key",
            {},
        )
        message = message_data.get(
            "message",
            {},
        )

        if not isinstance(key, dict):
            key = {}
        if not isinstance(message, dict):
            message = {}

        message_id = key.get("id") or message_data.get("id") or ""
        from_me = bool(key.get("fromMe", False))
        remote_jid = key.get("remoteJid", "")
        remote_jid_alt = key.get("remoteJidAlt", "")
        message_timestamp = message_data.get("messageTimestamp")

        # ----------------------------------------------------
        # STRICT SAFETY VALIDATION (STALENESS, NON-MESSAGES, DEDUP)
        # ----------------------------------------------------
        is_valid, reason = validate_incoming_event(
            event_type=normalized_event,
            message_id=message_id,
            sender_number=remote_jid,
            message_timestamp=message_timestamp,
            from_me=from_me,
        )

        if not is_valid:
            logger.info(
                "[SAFETY] Webhook skipped (%s) | message_id=%s | jid=%s",
                reason, message_id, remote_jid,
            )
            return {
                "success": True,
                "ignored": True,
                "reason": reason,
            }

        # Mark processed atomically in idempotency store
        if not idempotency_store.mark_processed(message_id):
            logger.info(
                "[DEDUP] Duplicate message_id already processed: %s",
                message_id,
            )
            return {
                "success": True,
                "ignored": True,
                "reason": "Duplicate message already processed",
            }

        # ----------------------------------------------------
        # USER ISOLATION & SESSION IDENTITY
        # ----------------------------------------------------
        clean_user_phone = normalize_phone_number(remote_jid, remote_jid_alt)
        whatsapp_user_id = f"whatsapp_{clean_user_phone}"
        whatsapp_session_id = f"whatsapp_{clean_user_phone}"
        send_to_number = remote_jid

        # Extract WhatsApp contact name if present in Evolution payload
        push_name = (
            message_data.get("pushName")
            or data.get("senderName")
            or message_data.get("verifiedBizName")
            or ""
        )
        contact_name = str(push_name).strip()

        # ── Per-User Async Lock Guard ───────────────────────
        user_lock = _get_user_lock(whatsapp_session_id)
        async with user_lock:
            # ----------------------------------------------------
            # EXTRACT TEXT / AUDIO / IMAGE CONTENT
            # ----------------------------------------------------
            text = ""
            msg_type = (
                message_data.get("messageType", "")
                or message_data.get("type", "")
            ).lower()

            has_audio = (
                message.get("audioMessage")
                or message.get("pttMessage")
                or msg_type in ("audiomessage", "audio", "ptt", "pttmessage")
            )

            has_image = (
                message.get("imageMessage")
                or msg_type in ("imagemessage", "image")
            )

            # Voice note / Audio message
            if has_audio:
                logger.info("Received WhatsApp audio/voice note from %s, transcribing...", send_to_number)
                try:
                    media_bytes = await fetch_evolution_media(message_data)
                    if media_bytes:
                        transcription = await speech_to_text.transcribe(media_bytes)
                        text = transcription.strip()
                        logger.info("Transcribed voice note: %s", text)
                    else:
                        logger.warning("Could not fetch audio bytes from Evolution API for voice note")
                        text = "(I received your voice note but couldn't process the audio)"
                except Exception as audio_err:
                    logger.error("Failed to transcribe WhatsApp audio: %s", audio_err, exc_info=True)
                    text = "(I received your voice note but couldn't process the audio)"

            # Image message
            elif has_image:
                img_msg = message.get("imageMessage") or {}
                caption = str(img_msg.get("caption", "") if isinstance(img_msg, dict) else "").strip()
                logger.info("Received WhatsApp image from %s (caption: %r)", send_to_number, caption)
                description = ""
                try:
                    media_bytes = await fetch_evolution_media(message_data)
                    if media_bytes:
                        description = await image_to_text.analyze_image(
                            media_bytes,
                            prompt="Describe what you see in this image in detail so we can talk about it.",
                        )
                except Exception as img_err:
                    logger.error("Failed to analyze WhatsApp image: %s", img_err, exc_info=True)

                if description:
                    text = (f"{caption}\n" if caption else "") + f"[Image Analysis: {description}]"
                else:
                    text = caption or "(friend sent an image)"

            # Normal text message
            elif message.get("conversation"):
                text = str(message.get("conversation", ""))

            # Extended text message
            elif message.get("extendedTextMessage"):
                extended = message.get("extendedTextMessage", {})
                if isinstance(extended, dict):
                    text = str(extended.get("text", ""))

            # Video caption
            elif message.get("videoMessage"):
                text = str(message.get("videoMessage", {}).get("caption", ""))

            # Document caption
            elif message.get("documentWithCaptionMessage"):
                doc = message.get("documentWithCaptionMessage", {}).get("message", {}).get("documentMessage", {})
                text = str(doc.get("caption", ""))

            # ----------------------------------------------------
            # EMPTY MESSAGE
            # ----------------------------------------------------
            if not text.strip():
                logger.info(
                    "WhatsApp message contains no text or media."
                )
                return {
                    "success": True,
                    "ignored": True,
                    "reason": "No text message",
                }

            text = text.strip()

            logger.info(
                "WhatsApp message | user=%s | target=%s | text=%s | contact_name=%s",
                clean_user_phone,
                send_to_number,
                text,
                contact_name,
            )

            # ====================================================
            # RUN LANGGRAPH
            # ====================================================
            result = await run_agent_graph(
                session_id=whatsapp_session_id,
                user_content=text,
                user_id=whatsapp_user_id,
                is_voice_note=bool(has_audio),
                contact_name=contact_name,
            )

            # ====================================================
            # GET RESPONSE
            # ====================================================
            response_text = str(
                result.get(
                    "response",
                    "",
                )
            ).strip()

            should_reply = result.get(
                "should_respond",
                True,
            )

            workflow = result.get(
                "workflow",
                "conversation",
            )

            logger.info(
                "AVA response | user=%s | workflow=%s | "
                "should_reply=%s | response=%s",
                clean_user_phone,
                workflow,
                should_reply,
                response_text,
            )

            # ====================================================
            # AVA DECIDED NOT TO REPLY
            # ====================================================
            if not should_reply:
                logger.info(
                    "AVA decided not to reply."
                )
                return {
                    "success": True,
                    "replied": False,
                    "reason": "Agent decided not to reply",
                }

            # ====================================================
            # EMPTY RESPONSE
            # ====================================================
            if not response_text and workflow != "image":
                logger.warning(
                    "AVA generated empty response."
                )
                return {
                    "success": True,
                    "replied": False,
                    "reason": "Empty response",
                }

            # ====================================================
            # SEND RESPONSE THROUGH EVOLUTION API WITH STRICT AUDIT
            # ====================================================
            evolution_response = None

            # ── Image workflow: send generated image as WhatsApp media ──────────
            img_path = result.get("image_path", "")
            if workflow == "image" and img_path and os.path.exists(img_path):
                logger.info("Sending generated image to WhatsApp: %s", img_path)
                with open(img_path, "rb") as f:
                    img_data = f.read()
                short_caption = response_text[:200] if response_text else "dekho 😊"
                evolution_response = await send_whatsapp_image(
                    number=send_to_number,
                    image_bytes=img_data,
                    caption=short_caption,
                    incoming_message_id=message_id,
                    sender_number=send_to_number,
                    event_type=normalized_event,
                )
            elif workflow == "image":
                logger.warning("Image workflow but no valid image_path (%r), sending text fallback", img_path)
                evolution_response = await send_whatsapp_message(
                    number=send_to_number,
                    text=response_text or "Sorry abhi image generate nahi ho saki, baad mein try karo 😅",
                    incoming_message_id=message_id,
                    sender_number=send_to_number,
                    event_type=normalized_event,
                )

            # ── Audio workflow: synthesize TTS and send as WhatsApp voice note ───
            elif workflow == "audio":
                logger.info("Sending voice note response to WhatsApp")
                raw_audio = result.get("audio_bytes") or b""
                if not raw_audio:
                    try:
                        raw_audio = await text_to_speech.synthesize(response_text)
                    except Exception as tts_e:
                        logger.warning("TTS fallback synthesis failed: %s", tts_e)
                        raw_audio = b""

                if raw_audio:
                    evolution_response = await send_whatsapp_audio(
                        number=send_to_number,
                        audio_bytes=raw_audio,
                        incoming_message_id=message_id,
                        sender_number=send_to_number,
                        event_type=normalized_event,
                    )
                else:
                    evolution_response = await send_whatsapp_message(
                        number=send_to_number,
                        text=response_text,
                        incoming_message_id=message_id,
                        sender_number=send_to_number,
                        event_type=normalized_event,
                    )

            # ── Conversation workflow: send as plain WhatsApp text chunks ────────
            else:
                chunks = result.get("response_chunks") or [response_text]
                chunk_delay = result.get("chunk_delay", 0.6) or 0.6
                for idx, chunk in enumerate(chunks):
                    chunk_str = str(chunk).strip()
                    if chunk_str:
                        evolution_response = await send_whatsapp_message(
                            number=send_to_number,
                            text=chunk_str,
                            incoming_message_id=message_id,
                            sender_number=send_to_number,
                            event_type=normalized_event,
                        )
                        if idx < len(chunks) - 1 and chunk_delay > 0:
                            await asyncio.sleep(chunk_delay)

            # ====================================================
            # DONE
            # ====================================================
            return {
                "success": True,
                "replied": True,
                "user_id": clean_user_phone,
                "workflow": workflow,
                "response": response_text,
                "evolution_response": evolution_response,
            }

    except Exception as e:

        logger.error(
            "WhatsApp webhook error: %s",
            e,
            exc_info=True,
        )

        return {
            "success": False,
            "error": str(e),
        }

# ============================================================
# HEALTH
# ============================================================


@app.get(
    "/health",
    summary="Health Status",
)
async def health():

    return {
        "status": "healthy"
    }


# ============================================================
# CHAT - SSE STREAMING
# ============================================================


async def _create_chat_stream(
    request: ChatRequest,
):

    """
    Generate Server-Sent Events stream
    for the web frontend.
    """

    async def _event_generator():

        try:

            result = await run_agent_graph(

                session_id=(
                    request.session_id
                    or "default_session"
                ),

                user_content=(
                    request.message
                ),

                user_id=(
                    request.user_id
                ),
            )

            resp_behavior = (
                result.get(
                    "response_behavior"
                )
                or {}
            )

            chunks = (
                resp_behavior.get(
                    "chunks"
                )
                or result.get(
                    "response_chunks"
                )
                or [
                    result["response"]
                ]
            )

            should_reply = (
                resp_behavior.get(
                    "should_reply",
                    result.get(
                        "should_respond",
                        True,
                    ),
                )
            )

            initial_delay = (
                resp_behavior.get(
                    "initial_delay",
                    0.0,
                )
            )

            chunk_delay = (
                resp_behavior.get(
                    "chunk_delay",
                    0.0,
                )
            )

            workflow = result.get(
                "workflow",
                "conversation",
            )

            image_url = result.get(
                "image_url"
            )

            audio_b64 = result.get(
                "audio_base64"
            )

            # ------------------------------------------------
            # SILENT RESPONSE
            # ------------------------------------------------

            if not should_reply:

                yield (
                    "data: "
                    + json.dumps({
                        "done": True,
                        "should_reply": False,
                    })
                    + "\n\n"
                )

                return

            # ------------------------------------------------
            # INITIAL DELAY
            # ------------------------------------------------

            if initial_delay > 0:

                await asyncio.sleep(
                    initial_delay
                )

            # ------------------------------------------------
            # STREAM CHUNKS
            # ------------------------------------------------

            total = len(chunks)

            for idx, chunk in enumerate(
                chunks
            ):

                payload = {

                    "chunk": chunk,

                    "index": idx,

                    "total": total,

                    "workflow": workflow,

                    "image_url": image_url,

                    "audio_base64": audio_b64,

                    "should_reply": True,
                }

                yield (
                    "data: "
                    + json.dumps(
                        payload
                    )
                    + "\n\n"
                )

                if (
                    idx < total - 1
                    and chunk_delay > 0
                ):

                    await asyncio.sleep(
                        chunk_delay
                    )

            # ------------------------------------------------
            # DONE
            # ------------------------------------------------

            yield (
                "data: "
                + json.dumps({
                    "done": True,
                    "should_reply": True,
                    "total": total,
                })
                + "\n\n"
            )

        except Exception as e:

            logger.error(
                "Error in /chat stream generator: %s",
                e,
                exc_info=True,
            )

            error_payload = {

                "error": str(e),

                "done": True,
            }

            yield (
                "data: "
                + json.dumps(
                    error_payload
                )
                + "\n\n"
            )

    return StreamingResponse(

        _event_generator(),

        media_type=(
            "text/event-stream"
        ),

        headers={

            "Cache-Control":
                "no-cache",

            "X-Accel-Buffering":
                "no",
        },
    )


@app.post(
    "/chat",
    summary=(
        "Send a text message and "
        "receive chunked SSE response"
    ),
)
async def chat_endpoint(
    request: ChatRequest,
):

    if not request.message.strip():

        raise HTTPException(
            status_code=400,
            detail=(
                "Message cannot be empty."
            ),
        )

    return await _create_chat_stream(
        request
    )


@app.post(
    "/chat/stream",
    summary=(
        "Send a text message and "
        "receive chunked SSE response "
        "(stream alias)"
    ),
)
async def chat_stream_endpoint(
    request: ChatRequest,
):

    if not request.message.strip():

        raise HTTPException(
            status_code=400,
            detail=(
                "Message cannot be empty."
            ),
        )

    return await _create_chat_stream(
        request
    )


# ============================================================
# AUDIO
# ============================================================


@app.post(
    "/audio",
    response_model=ChatResponse,
    summary=(
        "Upload audio file for voice chat"
    ),
)
async def audio_endpoint(

    file: UploadFile = File(
        ...,
        description=(
            "Audio recording file "
            "(mp3, wav, ogg, m4a, webm)"
        ),
    ),

    session_id: str = Form(
        "default_session",
        description="Session ID",
    ),

    user_id: Optional[str] = Form(
        None,
        description=(
            "Persistent User ID"
        ),
    ),
):

    try:

        # ----------------------------------------------------
        # READ AUDIO
        # ----------------------------------------------------

        audio_bytes = await file.read()

        if not audio_bytes:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Uploaded audio file "
                    "is empty."
                ),
            )

        # ----------------------------------------------------
        # SPEECH TO TEXT
        # ----------------------------------------------------

        transcription = (
            await speech_to_text.transcribe(
                audio_bytes
            )
        )

        if (
            not transcription
            or not transcription.strip()
        ):

            transcription = (
                "(Inaudible audio)"
            )

        logger.info(
            "Transcribed audio: %s",
            transcription,
        )

        # ----------------------------------------------------
        # RUN AGENT
        # ----------------------------------------------------

        result = await run_agent_graph(

            session_id=session_id,

            user_content=transcription,

            user_id=user_id,
        )

        result["transcription"] = (
            transcription
        )

        # ----------------------------------------------------
        # FALLBACK TTS
        # ----------------------------------------------------

        if (
            not result.get(
                "audio_base64"
            )
            and result.get(
                "response"
            )
        ):

            try:

                synth_audio = (
                    await text_to_speech.synthesize(
                        result["response"]
                    )
                )

                if synth_audio:

                    result[
                        "audio_base64"
                    ] = (
                        base64.b64encode(
                            synth_audio
                        ).decode(
                            "utf-8"
                        )
                    )

            except Exception as tts_err:

                logger.warning(
                    "Voice reply synthesis failed: %s",
                    tts_err,
                )

        return ChatResponse(
            **result
        )

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            "Audio processing error: %s",
            e,
            exc_info=True,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Audio processing failed: "
                f"{str(e)}"
            ),
        )


# ============================================================
# IMAGE
# ============================================================


@app.post(
    "/image",
    response_model=ChatResponse,
    summary=(
        "Upload an image for "
        "multimodal analysis"
    ),
)
async def image_endpoint(

    file: UploadFile = File(
        ...,
        description=(
            "Image file "
            "(jpg, png, webp)"
        ),
    ),

    caption: Optional[str] = Form(
        None,
        description=(
            "Optional caption or question "
            "about the image"
        ),
    ),

    session_id: str = Form(
        "default_session",
        description="Session ID",
    ),

    user_id: Optional[str] = Form(
        None,
        description=(
            "Persistent User ID"
        ),
    ),
):

    try:

        # ----------------------------------------------------
        # READ IMAGE
        # ----------------------------------------------------

        image_bytes = await file.read()

        if not image_bytes:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Uploaded image file "
                    "is empty."
                ),
            )

        # ----------------------------------------------------
        # IMAGE ANALYSIS
        # ----------------------------------------------------

        if caption:

            analysis_prompt = (
                "Please describe what you see "
                "in this image in the context "
                "of our conversation. "
                f"User question/caption: "
                f"{caption}"
            )

        else:

            analysis_prompt = (
                "Please describe what you see "
                "in this image in detail."
            )

        description = (
            await image_to_text.analyze_image(
                image_bytes,
                analysis_prompt,
            )
        )

        logger.info(
            "Image analysis result: %s",
            description,
        )

        # ----------------------------------------------------
        # CREATE MESSAGE
        # ----------------------------------------------------

        if (
            caption
            and caption.strip()
        ):

            user_content = (
                f"{caption.strip()}\n\n"
                f"[Attached Image Analysis: "
                f"{description}]"
            )

        else:

            user_content = (
                f"[Attached Image Analysis: "
                f"{description}]"
            )

        # ----------------------------------------------------
        # RUN GRAPH
        # ----------------------------------------------------

        result = await run_agent_graph(

            session_id=session_id,

            user_content=user_content,

            user_id=user_id,
        )

        result[
            "image_analysis"
        ] = description

        return ChatResponse(
            **result
        )

    except HTTPException:

        raise

    except Exception as e:

        logger.error(
            "Image processing error: %s",
            e,
            exc_info=True,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Image processing failed: "
                f"{str(e)}"
            ),
        )


# ============================================================
# HISTORY
# ============================================================


@app.get(
    "/history/{session_id}",
    response_model=HistoryResponse,
    summary=(
        "Get conversation history"
    ),
)
async def get_history(
    session_id: str,
):

    try:

        async with (
            AsyncSqliteSaver.from_conn_string(
                settings.SHORT_TERM_MEMORY_DB_PATH
            )
            as short_term_memory
        ):

            graph = graph_builder.compile(
                checkpointer=short_term_memory
            )

            state = (
                await graph.aget_state(
                    config={
                        "configurable": {
                            "thread_id": (
                                session_id
                            )
                        }
                    }
                )
            )

        raw_messages = (

            state.values.get(
                "messages",
                [],
            )

            if state
            and state.values

            else []
        )

        formatted: List[
            MessageItem
        ] = []

        for msg in raw_messages:

            if isinstance(
                msg,
                HumanMessage,
            ):

                role = "user"

            elif isinstance(
                msg,
                AIMessage,
            ):

                role = "assistant"

            else:

                role = "system"

            formatted.append(

                MessageItem(

                    role=role,

                    content=str(
                        msg.content
                    ),
                )
            )

        return HistoryResponse(

            session_id=session_id,

            messages=formatted,
        )

    except Exception as e:

        logger.error(
            "Failed to fetch history "
            "for session %s: %s",
            session_id,
            e,
        )

        return HistoryResponse(

            session_id=session_id,

            messages=[],
        )


# ============================================================
# FRONTEND
# ============================================================


frontend_dist_path = os.path.join(

    os.getcwd(),

    "frontend",

    "dist",
)


if os.path.exists(
    frontend_dist_path
):

    logger.info(
        "Mounting built React frontend from %s",
        frontend_dist_path,
    )

    app.mount(

        "/",

        StaticFiles(

            directory=frontend_dist_path,

            html=True,
        ),

        name="frontend",
    )

else:

    @app.get(
        "/",
        summary="Root Health Check",
    )
    async def root():

        return {

            "status": "online",

            "service": (
                "AI Companion "
                "FastAPI Backend"
            ),

            "version": "1.0.0",

            "endpoints": {

                "health":
                    "GET /health",

                "chat":
                    "POST /chat",

                "chat_stream":
                    "POST /chat/stream",

                "audio":
                    "POST /audio",

                "image":
                    "POST /image",

                "history":
                    "GET /history/{session_id}",

                "whatsapp":
                    "POST /webhook/whatsapp",

                "docs":
                    "/docs",
            },
        }