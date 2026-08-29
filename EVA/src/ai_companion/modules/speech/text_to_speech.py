import io
import logging

import edge_tts

logger = logging.getLogger(__name__)

# Microsoft Neural voice — free, no API key required
EDGE_TTS_VOICE = "en-US-AriaNeural"


class TextToSpeech:
    """A class to handle text-to-speech conversion using Microsoft Edge TTS (free)."""

    async def synthesize(self, text: str) -> bytes:
        """Convert text to speech using Microsoft Edge TTS.

        Args:
            text: Text to convert to speech

        Returns:
            bytes: MP3 audio data

        Raises:
            ValueError: If the input text is empty
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")

        try:
            communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
            audio_buffer = io.BytesIO()

            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])

            audio_bytes = audio_buffer.getvalue()
            if not audio_bytes:
                raise RuntimeError("Generated audio is empty")

            logger.info(f"TTS synthesized {len(audio_bytes)} bytes via Edge TTS")
            return audio_bytes

        except Exception as e:
            logger.error(f"Text-to-speech conversion failed: {str(e)}")
            raise RuntimeError(f"TTS synthesis failed: {str(e)}") from e
