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

    # Redash (replaces CSV ingestion)
    REDASH_URL = os.getenv("REDASH_URL", "https://redash.intermesh.net")
    REDASH_API_KEY = os.getenv("REDASH_API_KEY")
    REDASH_POLL_INTERVAL = float(os.getenv("REDASH_POLL_INTERVAL", 1.5))
    REDASH_QUERY_TIMEOUT = int(os.getenv("REDASH_QUERY_TIMEOUT", 180))
    # Data-source IDs on this Redash instance (override per env)
    REDASH_DS_BL       = int(os.getenv("REDASH_DS_BL", 16))     # pg-imblr-prod-live → eto_ofr, eto_unsold_leads
    REDASH_DS_BUYER    = int(os.getenv("REDASH_DS_BUYER", 16))
    REDASH_DS_SELLER   = int(os.getenv("REDASH_DS_SELLER", 16))
    REDASH_DS_MCATSPEC = int(os.getenv("REDASH_DS_MCATSPEC", 8))  # im_dwh_rpt → fact_im_*

    # DWH (direct Redshift connection — bypasses Redash for heavier queries)
    DWH_HOST     = os.getenv("DWH_HOST")
    DWH_PORT     = int(os.getenv("DWH_PORT", 5439))
    DWH_DB       = os.getenv("DWH_DB")
    DWH_USER     = os.getenv("DWH_USER")
    DWH_PASSWORD = os.getenv("DWH_PASSWORD")
    DWH_SSLMODE  = os.getenv("DWH_SSLMODE", "require")
    DWH_CONNECT_TIMEOUT = int(os.getenv("DWH_CONNECT_TIMEOUT", 15))


settings = Settings()
