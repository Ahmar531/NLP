from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    GROQ_API_KEY: str
    ELEVENLABS_API_KEY: str = ""
    ELEVENLABS_VOICE_ID: str = "kdmDKE6EkgrWrrykO9Qt"
    TOGETHER_API_KEY: str = ""

    QDRANT_API_KEY: str | None = None
    QDRANT_URL: str | None = None
    QDRANT_PORT: str = "6333"
    QDRANT_HOST: str | None = None
    LONG_TERM_MEMORY_PATH: str = "./data/qdrant_db"

    TEXT_MODEL_NAME: str = "qwen/qwen3.8-27b"
    SMALL_TEXT_MODEL_NAME: str = "openai/gpt-oss-20b"
    STT_MODEL_NAME: str = "whisper-large-v3-turbo"
    TTS_MODEL_NAME: str = "eleven_flash_v2_5"
    TTI_MODEL_NAME: str = "black-forest-labs/FLUX.1-schnell-Free"
    ITT_MODEL_NAME: str = "llama-3.2-90b-vision-preview"

    MEMORY_TOP_K: int = 3
    ROUTER_MESSAGES_TO_ANALYZE: int = 3
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 20
    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5

    SHORT_TERM_MEMORY_DB_PATH: str = "./data/memory.db"

    EVOLUTION_API_URL: str = "http://localhost:8080"
    EVOLUTION_API_KEY: str = "D4C48552A640-4169-AB43-A4BACEF8347F"
    EVOLUTION_INSTANCE: str = "AVA"


settings = Settings()
