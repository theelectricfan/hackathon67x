"""
Langfuse observability wrapper.
Exports `observe` decorator used by all skills and orchestrator.
Falls back to a no-op decorator if Langfuse is not configured.
"""
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

_langfuse_enabled = False

try:
    if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
        from langfuse import Langfuse

        # v4: observe is at top level; v2/v3: langfuse.decorators
        try:
            from langfuse import observe as _lf_observe  # type: ignore
        except ImportError:
            from langfuse.decorators import observe as _lf_observe  # type: ignore

        langfuse = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            host=settings.LANGFUSE_HOST or "https://cloud.langfuse.com",
        )
        observe = _lf_observe
        _langfuse_enabled = True
        logger.info("Langfuse observability enabled")
    else:
        raise ValueError("Langfuse keys not set")

except Exception as e:
    logger.warning(f"Langfuse not available ({e}). Using no-op observe decorator.")

    def observe(name=None, **kwargs):
        """No-op fallback when Langfuse is not configured."""
        def decorator(fn):
            return fn
        return decorator

    langfuse = None


def flush():
    """Flush pending Langfuse events. Call after each RCA run."""
    if _langfuse_enabled and langfuse:
        try:
            langfuse.flush()
        except Exception:
            pass


__all__ = ["observe", "langfuse", "flush"]
