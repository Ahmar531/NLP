from typing import Any, Dict

from langgraph.graph import MessagesState


class AICompanionState(MessagesState):
    """State class for the AI Companion workflow.

    Extends MessagesState to track conversation history and maintains the last message received.

    Attributes:
        last_message (AnyMessage): The most recent message in the conversation, can be any valid
            LangChain message type (HumanMessage, AIMessage, etc.)
        workflow (str): The current workflow the AI Companion is in. Can be "conversation", "image", or "audio".
        audio_buffer (bytes): The audio buffer to be used for speech-to-text conversion.
        current_activity (str): The current activity of Ava based on the schedule.
        memory_context (str): The context of the memories to be injected into the character card.
        response_behavior (dict): Human-like delivery plan set by response_behavior_node.
            Keys: should_reply (bool), initial_delay (float), chunks (list[str]), chunk_delay (float).
        is_voice_note (bool): True when the incoming WhatsApp message was a voice note.
            Forces the reply to be sent as a voice note regardless of content.
        contact_name (str): The saved WhatsApp contact name for this user (from contacts[].profile.name).
            Stored in long-term memory so EVA can address the user naturally.
    """

    summary: str
    workflow: str
    audio_buffer: bytes
    image_path: str
    current_activity: str
    apply_activity: bool
    memory_context: str
    user_id: str
    # True when incoming message was a WhatsApp voice note → reply must be audio
    is_voice_note: bool
    # Saved WhatsApp contact name for this user
    contact_name: str
    # Pakistan Standard Time dynamic context (Asia/Karachi, UTC+05:00)
    datetime_context: str
    # Real-time weather context fetched via WeatherService
    weather_context: str
    # Human-like response behaviour plan (set by response_behavior_node)
    response_behavior: Dict[str, Any]
