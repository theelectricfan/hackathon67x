"""
CENTRALISED LLM CLIENT
=======================
Single import for ALL LLM calls in the project.

Usage in any skill:
    from llm.client import llm

    # Gateway call (reasoning/extraction)
    result = llm.chat(system="...", user="...")

    # Gateway call returning parsed JSON
    result = llm.chat_json(system="...", user="Return JSON with keys: bucket, confidence")

    # Parallel AI call (task/discovery)
    result = llm.parallel(prompt="...", task_spec={"type": "search", ...})

    # Orchestrator tool calling (Anthropic)
    response = llm.chat_with_tools(messages=messages, tools=tools, system="...")

Rules:
- Skills use llm.chat() or llm.chat_json()
- Orchestrator uses llm.chat_with_tools()
- Complex discovery uses llm.parallel()
- Never import gateway/parallel_ai directly
- Never import anthropic directly
- Never hardcode model names or keys
"""

import logging
import anthropic
from config.settings import settings
from llm.gateway import call_llm
from llm.parallel_ai import call_parallel
from llm.utils import extract_json

logger = logging.getLogger(__name__)

_anthropic_client = None


def get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


class LLMClient:
    """Unified interface for all LLM providers. One import. One object. All providers."""

    # ── 1. GATEWAY CHAT ─────────────────────────────────────────────────────────
    def chat(
        self,
        system: str,
        user: str,
        model: str = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """
        Standard gateway call. Returns raw string.
        Use when you process the response yourself.
        """
        return call_llm(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ── 2. GATEWAY CHAT → JSON ───────────────────────────────────────────────────
    def chat_json(
        self,
        system: str,
        user: str,
        model: str = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> dict:
        """
        Gateway call that returns parsed JSON dict.
        Use in all skills for structured output.
        Automatically handles markdown code blocks.
        """
        raw = call_llm(
            system=system,
            user=user,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return extract_json(raw)

    # ── 3. PARALLEL AI ───────────────────────────────────────────────────────────
    def parallel(
        self,
        prompt: str,
        task_spec: dict,
        processor: str = None,
    ) -> dict:
        """
        Parallel AI task call. Returns parsed dict from task result.
        Use for complex discovery/search tasks.
        """
        return call_parallel(prompt=prompt, task_spec=task_spec, processor=processor)

    # ── 4. ANTHROPIC TOOL CALLING ────────────────────────────────────────────────
    def chat_with_tools(
        self,
        messages: list,
        tools: list,
        system: str = None,
    ) -> anthropic.types.Message:
        """
        Anthropic tool calling for agent loop.
        ONLY used by orchestrator.
        Returns raw Anthropic Message object.
        """
        client = get_anthropic_client()

        kwargs = {
            "model": settings.ANTHROPIC_MODEL,
            "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
            "tools": tools,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        if settings.LOG_LLM_CALLS:
            logger.info(
                f"Tool call | tools={[t['name'] for t in tools]} | messages={len(messages)}"
            )

        return client.messages.create(**kwargs)

    # ── 5. EXTRACT JSON UTILITY ──────────────────────────────────────────────────
    def parse_json(self, text: str) -> dict:
        """Parse JSON from any raw LLM response. Available to all skills if needed."""
        return extract_json(text)


# ── SINGLETON ────────────────────────────────────────────────────────────────────
# This is the only thing skills need to import
llm = LLMClient()
