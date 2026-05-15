import json
import time
import logging
from config.settings import settings

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """
    Robustly parse JSON from any LLM response.
    Handles markdown code blocks, extra text, and trailing commas.
    """
    if not text:
        return {}

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        cleaned = text.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                try:
                    return json.loads(part)
                except Exception:
                    continue

        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(cleaned[start:end])

    except Exception as e:
        logger.error(f"JSON parse failed: {e}\nRaw: {text[:200]}")

    return {"error": "parse_failed", "raw": text}


def with_retry(func, *args, **kwargs):
    """Retry wrapper for any LLM call."""
    attempts = settings.LLM_RETRY_ATTEMPTS
    delay = settings.LLM_RETRY_DELAY

    for attempt in range(attempts):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == attempts - 1:
                logger.error(f"All {attempts} attempts failed: {e}")
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
