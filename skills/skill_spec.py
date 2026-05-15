"""Bucket 3 — Spec Contradiction. Parallel AI always, then Gateway summariser."""
from llm.client import llm
from langfuse_client import observe


_PARALLEL_OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "has_contradiction": {"type": "boolean"},
            "contradicting_specs": {"type": "array", "items": {"type": "string"}},
            "reasoning": {"type": "string"},
            "confidence": {"type": "integer"},
        },
        "required": ["has_contradiction", "contradicting_specs", "reasoning", "confidence"],
    },
}


@observe(name="skill_spec")
def run_skill_spec(ctx: dict) -> dict:
    specs_filled = ctx["specs_filled"]
    offer_name = ctx["offer_name"]

    parallel_result = llm.parallel(
        prompt=f"""Product: "{offer_name}" (listed on IndiaMART, Indian B2B marketplace)
Buyer filled these specifications: {specs_filled}

Search Indian B2B market for this product type.
Do any of these specs contradict each other or are logically inconsistent?
Example: if Material=Natural Rubber, can Source Product=Tyre be a valid spec combination?
Use real Indian market knowledge to verify each combination.""",
        task_spec={
            "input_schema": {"type": "text"},
            "output_schema": _PARALLEL_OUTPUT_SCHEMA,
        },
    )

    summary = llm.chat_json(
        system="You are a product spec analyst for IndiaMART B2B marketplace.",
        user=f"""Market research result for spec contradiction check on "{offer_name}":
{parallel_result}

Summarise the finding clearly.
Return JSON only:
{{
  "has_contradiction": true or false,
  "confidence": 0-100,
  "detail": "explain the contradiction in one sentence",
  "fix": "one actionable sentence for the buyer"
}}""",
    )

    return {
        "bucket": "SPEC_CONTRADICTION",
        "has_contradiction": summary.get("has_contradiction", False),
        "confidence": int(summary.get("confidence", 0)),
        "detail": summary.get("detail", ""),
        "fix": summary.get("fix", "Review spec combinations for consistency"),
        "parallel_raw": parallel_result,
    }
