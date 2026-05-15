"""Bucket 2 — Thin Content. Parallel AI when fill_count < 2, else low confidence."""
from llm.client import llm
from langfuse_client import observe


_PARALLEL_OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "is_uniquely_identifiable": {"type": "boolean"},
            "reasoning": {"type": "string"},
            "missing_specs": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "integer"},
        },
        "required": ["is_uniquely_identifiable", "reasoning", "missing_specs", "confidence"],
    },
}


@observe(name="skill_content")
def run_skill_content(ctx: dict) -> dict:
    specs_filled = ctx["specs_filled"]
    fill_count = ctx["specs_fill_count"]
    aov_blank = ctx["aov_blank"]
    offer_name = ctx["offer_name"]
    priority_specs = ctx.get("priority_specs", [])

    if fill_count < 2:
        parallel_result = llm.parallel(
            prompt=f"""Product BuyLead posted on IndiaMART (Indian B2B marketplace): "{offer_name}"
Buyer filled only these specs: {specs_filled}
Priority specs for this category: {priority_specs}
AOV (order value) provided: {"No" if aov_blank else "Yes"}

Search Indian B2B market context.
Can an Indian seller uniquely identify this product and send an accurate quote with just these specs?
Answer with what is missing and why it matters.""",
            task_spec={
                "input_schema": {"type": "text"},
                "output_schema": _PARALLEL_OUTPUT_SCHEMA,
            },
        )

        summary = llm.chat_json(
            system="You are a BuyLead content quality analyst for IndiaMART.",
            user=f"""Market research result for BuyLead "{offer_name}":
{parallel_result}

Based on this research, rate how thin/incomplete this BuyLead content is.
Return JSON only:
{{
  "confidence": 0-100,
  "fix": "one actionable sentence telling buyer exactly what to add"
}}""",
        )

        return {
            "bucket": "THIN_CONTENT",
            "fill_count": fill_count,
            "aov_blank": aov_blank,
            "confidence": int(summary.get("confidence", 70)),
            "fix": summary.get("fix", f"Add more specs for {offer_name}. Priority: {', '.join(priority_specs[:3])}"),
            "parallel_raw": parallel_result,
        }

    return {
        "bucket": "THIN_CONTENT",
        "fill_count": fill_count,
        "aov_blank": aov_blank,
        "confidence": 20,
        "fix": "Spec count sufficient. Consider adding order value for better seller matching.",
    }
