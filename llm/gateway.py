import httpx
import logging
from config.settings import settings
from llm.utils import with_retry

logger = logging.getLogger(__name__)


def call_llm(
    system: str,
    user: str,
    model: str = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
) -> str:
    """
    Call the Intermesh LLM Gateway.

    Used for all skill reasoning calls, extraction, and classification.
    Returns raw string response from LLM.
    """

    def _call():
        payload = {
            "model": model or settings.DEFAULT_EXTRACTION_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if settings.LOG_LLM_CALLS:
            logger.info(
                f"Gateway call | model={payload['model']} | user_len={len(user)}"
            )

        resp = httpx.post(
            settings.LLM_GATEWAY_URL,
            headers={
                "Authorization": f"Bearer {settings.LLM_GATEWAY_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    return with_retry(_call)
