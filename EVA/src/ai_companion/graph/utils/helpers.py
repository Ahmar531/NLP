import re

from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

from ai_companion.modules.image.image_to_text import ImageToText
from ai_companion.modules.image.text_to_image import TextToImage
from ai_companion.modules.speech import TextToSpeech
from ai_companion.settings import settings


def get_chat_model(temperature: float = 0.7):
    primary = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=settings.TEXT_MODEL_NAME,
        temperature=temperature,
        max_tokens=350,
        max_retries=2,
    )
    # Automatic fallback model if primary hits 429 rate limit
    fallback_model = "openai/gpt-oss-20b" if settings.TEXT_MODEL_NAME == "qwen/qwen3.8-27b" else "qwen/qwen3.8-27b"
    secondary = ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=fallback_model,
        temperature=temperature,
        max_tokens=350,
        max_retries=2,
    )
    return primary.with_fallbacks([secondary])


def get_text_to_speech_module():
    return TextToSpeech()


def get_text_to_image_module():
    return TextToImage()


def get_image_to_text_module():
    return ImageToText()


def remove_asterisk_content(text: str) -> str:
    """Remove content between asterisks from the text."""
    return re.sub(r"\*.*?\*", "", text).strip()


class AsteriskRemovalParser(StrOutputParser):
    def parse(self, text):
        return remove_asterisk_content(super().parse(text))
