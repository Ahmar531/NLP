import logging
import os
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage
from langchain_core.runnables import RunnableConfig

from ai_companion.graph.state import AICompanionState
from ai_companion.graph.utils.chains import (
    get_character_response_chain,
    get_router_chain,
)
from ai_companion.graph.utils.helpers import (
    get_chat_model,
    get_text_to_image_module,
    get_text_to_speech_module,
)
from ai_companion.modules.memory.long_term.memory_manager import get_memory_manager
from ai_companion.modules.response_behavior import build_response_behavior
from ai_companion.modules.schedules.context_generation import (
    ScheduleContextGenerator,
    get_pakistan_datetime_context,
)
from ai_companion.modules.weather import (
    extract_location,
    is_weather_query,
    weather_service,
)
from ai_companion.settings import settings

logger = logging.getLogger(__name__)


def _get_user_id(
    state: AICompanionState,
    config: RunnableConfig | None = None,
) -> str:
    """
    Get the persistent user ID.

    IMPORTANT:
    - user_id identifies the person.
    - thread_id identifies a conversation.
    - Never use thread_id as user_id.
    """

    configurable = {}

    if isinstance(config, dict):
        configurable = config.get("configurable", {}) or {}

    user_id = (
        state.get("user_id")
        or configurable.get("user_id")
        or "default_user"
    )

    return str(user_id)


async def router_node(state: AICompanionState):
    """Determine response type based on user message content.

    IMPORTANT: If the incoming message was a WhatsApp voice note (is_voice_note=True),
    always route to audio workflow — regardless of transcribed text content.
    This ensures voice-in → voice-out parity.
    """

    # ── Voice note input → always reply with voice ────────────────────────────
    if state.get("is_voice_note"):
        logger.info("router_node: incoming voice note — forcing audio workflow")
        return {"workflow": "audio"}

    last_message = (
        state["messages"][-1].content.lower()
        if state.get("messages")
        else ""
    )

    image_keywords = [
        "image", "picture", "photo", "selfie", "pic", "pics",
        "show me", "tasveer", "tasweer", "draw", "generate image",
        "photo bhejo", "pic bhejo", "selfie bhejo", "image bhejo",
        "send photo", "send pic", "send selfie", "send image",
        "photo send", "pic send", "selfie send", "image send",
        "photo dikhao", "pic dikhao", "selfie dikhao",
    ]

    audio_keywords = [
        "voice", "audio", "speak", "voice note", "voice msg",
        "voice message", "awaaz", "awaz", "bol ke", "bol k", "bol kar",
        "sunao", "record voice", "voice bhejo", "audio bhejo",
        "send voice", "send audio", "talk to me", "voice me",
        "voice pe", "voice mai", "voice per", "voice send",
        "apni awaz", "apni awaaz", "awaz me", "awaaz me",
        "audio msg", "audio message", "audio send",
    ]

    if any(word in last_message for word in image_keywords):
        return {"workflow": "image"}

    elif any(word in last_message for word in audio_keywords):
        return {"workflow": "audio"}

    else:
        return {"workflow": "conversation"}


async def context_injection_node(state: AICompanionState):
    """Inject current schedule/activity, Pakistan datetime, and real-time weather context."""

    schedule_context = ScheduleContextGenerator.get_current_activity()
    datetime_context = get_pakistan_datetime_context()

    if schedule_context != state.get("current_activity", ""):
        apply_activity = True
    else:
        apply_activity = False

    # Extract user's latest message to check for weather intent
    messages = state.get("messages", [])
    user_text = ""
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human" or isinstance(msg, HumanMessage):
            user_text = str(getattr(msg, "content", ""))
            break

    weather_context = ""
    if user_text and is_weather_query(user_text):
        try:
            mem_context = state.get("memory_context", "")
            location = extract_location(user_text, memory_context=mem_context)
            logger.info("Detected weather query in message: '%s' -> target location: '%s'", user_text[:60], location)
            weather_data = await weather_service.get_weather(location)
            weather_context = weather_service.format_weather_context(weather_data)
        except Exception as w_err:
            logger.warning("Failed to fetch weather context: %s", w_err, exc_info=True)
            weather_context = "Could not retrieve live weather update at this moment."
    else:
        weather_context = "No weather query in this conversation turn."

    return {
        "apply_activity": apply_activity,
        "current_activity": schedule_context,
        "datetime_context": datetime_context,
        "weather_context": weather_context,
    }


async def conversation_node(
    state: AICompanionState,
    config: RunnableConfig,
):
    """Generate normal conversational response."""

    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    datetime_context = state.get("datetime_context") or get_pakistan_datetime_context()
    weather_context = state.get("weather_context", "No weather query in this conversation turn.")

    chain = get_character_response_chain(
        state.get("summary", "")
    )

    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
            "datetime_context": datetime_context,
            "weather_context": weather_context,
        },
        config,
    )

    return {
        "messages": AIMessage(content=response),
        "audio_buffer": b"",
        "image_path": "",
    }


async def response_behavior_node(
    state: AICompanionState,
) -> dict:
    """
    Post-process the AI response for human-like delivery.

    Reads the last AI message produced by conversation_node and:
    1. Decides whether EVA should reply or stay silent.
    2. Calculates a natural initial typing delay.
    3. Splits the text into 1-4 natural sentence-based chunks.
    4. Calculates a human-like delay between chunks.

    Stores everything in state["response_behavior"] for the SSE endpoint.
    Only wired after conversation_node — image/audio nodes bypass it.
    """

    messages = state.get("messages", [])

    # ── Find the last human message (for the should_reply decision) ──────────
    user_text = ""
    from langchain_core.messages import HumanMessage as _HM
    for msg in reversed(messages):
        if isinstance(msg, _HM) or getattr(msg, "type", "") == "human":
            user_text = str(getattr(msg, "content", ""))
            break

    # ── Get the AI response text ─────────────────────────────────────────────
    ai_text = ""
    if messages:
        last = messages[-1]
        if not isinstance(last, _HM) and getattr(last, "type", "") != "human":
            ai_text = str(getattr(last, "content", ""))
        else:
            # If the last message is human, response hasn't been appended yet
            ai_text = state.get("summary", "")

    # ── Build behaviour plan ─────────────────────────────────────────────────
    behavior = build_response_behavior(
        user_message=user_text,
        ai_response=ai_text,
    )

    return {"response_behavior": dict(behavior)}


async def image_node(
    state: AICompanionState,
    config: RunnableConfig,
):
    """Generate an image and respond conversationally."""

    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    datetime_context = state.get("datetime_context") or get_pakistan_datetime_context()
    weather_context = state.get("weather_context", "No weather query in this conversation turn.")

    chain = get_character_response_chain(
        state.get("summary", "")
    )

    text_to_image_module = get_text_to_image_module()

    scenario = await text_to_image_module.create_scenario(
        state["messages"][-5:]
    )

    os.makedirs("generated_images", exist_ok=True)

    img_path = (
        f"generated_images/image_{str(uuid4())}.png"
    )

    await text_to_image_module.generate_image(
        scenario.image_prompt,
        img_path,
    )

    scenario_message = HumanMessage(
        content=(
            "<image attached by Ava generated from prompt: "
            f"{scenario.image_prompt}>"
        )
    )

    updated_messages = state["messages"] + [scenario_message]

    response = await chain.ainvoke(
        {
            "messages": updated_messages,
            "current_activity": current_activity,
            "memory_context": memory_context,
            "datetime_context": datetime_context,
            "weather_context": weather_context,
        },
        config,
    )

    return {
        "messages": AIMessage(content=response),
        "image_path": img_path,
        "audio_buffer": b"",
    }


async def audio_node(
    state: AICompanionState,
    config: RunnableConfig,
):
    """Generate conversational response and synthesize audio."""

    current_activity = ScheduleContextGenerator.get_current_activity()
    memory_context = state.get("memory_context", "")
    datetime_context = state.get("datetime_context") or get_pakistan_datetime_context()
    weather_context = state.get("weather_context", "No weather query in this conversation turn.")

    chain = get_character_response_chain(
        state.get("summary", "")
    )

    text_to_speech_module = get_text_to_speech_module()

    response = await chain.ainvoke(
        {
            "messages": state["messages"],
            "current_activity": current_activity,
            "memory_context": memory_context,
            "datetime_context": datetime_context,
            "weather_context": weather_context,
        },
        config,
    )

    output_audio = await text_to_speech_module.synthesize(
        response
    )

    return {
        "messages": AIMessage(content=response),
        "audio_buffer": output_audio,
        "image_path": "",
    }


async def summarize_conversation_node(
    state: AICompanionState,
):
    """Summarize the conversation when message history becomes large."""

    model = get_chat_model()
    summary = state.get("summary", "")

    if summary:
        summary_message = (
            "This is summary of the conversation to date "
            "between Ava and the user:\n"
            f"{summary}\n\n"
            "Extend the summary by taking into account "
            "the new messages above:"
        )
    else:
        summary_message = (
            "Create a summary of the conversation above "
            "between Ava and the user. "
            "The summary must be a short description of "
            "the conversation so far, but that captures "
            "all the relevant information shared between "
            "Ava and the user:"
        )

    messages = state["messages"] + [
        HumanMessage(content=summary_message)
    ]

    response = await model.ainvoke(messages)

    delete_messages = [
        RemoveMessage(id=m.id)
        for m in state["messages"][
            :-settings.TOTAL_MESSAGES_AFTER_SUMMARY
        ]
    ]

    return {
        "summary": response.content,
        "messages": delete_messages,
    }


async def memory_extraction_node(
    state: AICompanionState,
    config: RunnableConfig | None = None,
):
    """
    Extract important information from the latest user message
    and permanently store it for the user.

    Also persists the WhatsApp contact name (contact_name from state) as a
    long-term memory fact on the first message — so EVA can address the user
    naturally in future conversations.

    IMPORTANT:
    user_id is persistent across conversations.
    thread_id is NOT used as user_id.
    """

    messages = state.get("messages", [])

    if not messages:
        return {}

    user_id = _get_user_id(state, config)

    try:
        memory_manager = get_memory_manager()

        # ── Store WhatsApp contact name as a long-term memory fact ──────────
        contact_name = (state.get("contact_name") or "").strip()
        if contact_name:
            from langchain_core.messages import HumanMessage as _HM2
            name_fact = f"User's saved WhatsApp contact name is: {contact_name}"
            name_message = _HM2(content=name_fact)
            try:
                await memory_manager.extract_and_store_memories(
                    name_message,
                    user_id=user_id,
                )
                logger.info(
                    "Stored contact name '%s' as memory for user '%s'",
                    contact_name,
                    user_id,
                )
            except Exception as name_err:
                logger.warning(
                    "Failed to store contact name for user '%s': %s",
                    user_id,
                    name_err,
                )

        # ── Extract memories from the user's message ────────────────────────
        await memory_manager.extract_and_store_memories(
            messages[-1],
            user_id=user_id,
        )

        logger.info(
            "Memory extraction completed for user '%s'",
            user_id,
        )

    except Exception as e:
        logger.error(
            "Error in memory_extraction_node for user '%s': %s",
            user_id,
            e,
            exc_info=True,
        )

    return {}


def memory_injection_node(
    state: AICompanionState,
    config: RunnableConfig | None = None,
):
    """
    Retrieve long-term memories for the current user and inject
    them into the conversation context.

    If a WhatsApp contact name is present in state and not yet in memory,
    it is prepended to the context so EVA can address the user by name
    immediately — before the async memory extraction has had a chance to
    persist it.

    IMPORTANT:
    user_id identifies the user.
    thread_id identifies only the current conversation.
    """

    messages = state.get("messages", [])

    if not messages:
        return {
            "memory_context": "No previous memories recorded yet."
        }

    user_id = _get_user_id(state, config)

    try:
        memory_manager = get_memory_manager()

        recent_context = " ".join(
            str(message.content)
            for message in messages[-3:]
        )

        memories = memory_manager.get_relevant_memories(
            recent_context,
            user_id=user_id,
        )

        memory_context = (
            memory_manager.format_memories_for_prompt(
                memories
            )
        )

        # ── Prepend contact name if known and not already in memory ─────────
        contact_name = (state.get("contact_name") or "").strip()
        if contact_name:
            name_fact = f"User's saved WhatsApp contact name is: {contact_name}"
            if name_fact not in memory_context:
                if memory_context == "No previous memories recorded yet.":
                    memory_context = f"- {name_fact}"
                else:
                    memory_context = f"- {name_fact}\n{memory_context}"

        logger.info(
            "Retrieved %d memories for user '%s'",
            len(memories),
            user_id,
        )

        return {
            "memory_context": memory_context
        }

    except Exception as e:
        logger.error(
            "Error in memory_injection_node for user '%s': %s",
            user_id,
            e,
            exc_info=True,
        )

        return {
            "memory_context": "No previous memories recorded yet."
        }