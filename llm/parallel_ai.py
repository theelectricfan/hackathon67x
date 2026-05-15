import logging
from config.settings import settings
from llm.utils import with_retry

logger = logging.getLogger(__name__)

_parallel_client = None


def get_parallel_client():
    """Initialize Parallel AI client once. Reused across all calls."""
    global _parallel_client
    if _parallel_client is None:
        try:
            from parallel import Parallel
            _parallel_client = Parallel(api_key=settings.PARALLEL_API_KEY)
            logger.info("Parallel AI client initialized")
        except ImportError:
            logger.error("Parallel package not installed. Run: pip install parallel-ai")
            raise
    return _parallel_client


def call_parallel(
    prompt: str,
    task_spec: dict,
    processor: str = None,
) -> dict:
    """
    Call Parallel AI for task-based discovery.

    Used for complex MCAT discovery tasks, semantic search, and long-running AI tasks.
    Returns parsed dict from task result.
    """

    def _call():
        client = get_parallel_client()
        _processor = processor or settings.DEFAULT_PARALLEL_PROCESSOR

        if settings.LOG_LLM_CALLS:
            logger.info(
                f"Parallel call | processor={_processor} | prompt_len={len(prompt)}"
            )

        task_run = client.task_run.create(
            input=prompt,
            processor=_processor,
            task_spec=task_spec,
        )
        logger.info(f"Parallel task created | run_id={task_run.run_id}")

        run_result = client.task_run.result(task_run.run_id, api_timeout=3600)

        output = run_result.output
        if hasattr(output, "content"):
            return output.content
        return output

    return with_retry(_call)
