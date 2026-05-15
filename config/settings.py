from dotenv import load_dotenv
import os

load_dotenv()


class Settings:

    # LLM Gateway
    LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL")
    LLM_GATEWAY_KEY = os.getenv("LLM_GATEWAY_KEY")

    # Parallel AI
    PARALLEL_API_KEY = os.getenv("PARALLEL_API_KEY")
    DEFAULT_PARALLEL_PROCESSOR = os.getenv("DEFAULT_PARALLEL_PROCESSOR", "base-fast")

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", 4096))

    # Langfuse
    LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
    LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")

    # Models
    GEMINI_FLASH = os.getenv("GEMINI_FLASH", "google/gemini-flash-1.5")
    GEMINI_PRO_MODEL = os.getenv("GEMINI_PRO_MODEL", "google/gemini-pro")
    GEMINI_FLASH_LITE_MODEL = os.getenv("GEMINI_FLASH_LITE_MODEL", "google/gemini-flash-1.5-8b")
    DEFAULT_EXTRACTION_MODEL = os.getenv("DEFAULT_EXTRACTION_MODEL", os.getenv("GEMINI_FLASH", "google/gemini-flash-1.5"))

    # App
    LOG_LLM_CALLS = os.getenv("LOG_LLM_CALLS", "true").lower() == "true"
    LLM_RETRY_ATTEMPTS = int(os.getenv("LLM_RETRY_ATTEMPTS", 3))
    LLM_RETRY_DELAY = int(os.getenv("LLM_RETRY_DELAY", 2))
    RCA_CONFIDENCE_THRESHOLD = int(os.getenv("RCA_CONFIDENCE_THRESHOLD", 60))


settings = Settings()
