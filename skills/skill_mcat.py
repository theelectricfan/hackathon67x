"""Bucket 1 — MCAT Mismatch. Gateway LLM only."""
from llm.client import llm
from langfuse_client import observe


@observe(name="skill_mcat")
def run_skill_mcat(ctx: dict) -> dict:
    result = llm.chat_json(
        system=(
            "You are an MCAT category mapping expert at IndiaMART, "
            "India's largest B2B marketplace. Think step by step."
        ),
        user=f"""BuyLead Title: "{ctx['offer_name']}"
Mapped MCAT: "{ctx['mapped_mcat_name']}" (ID: {ctx['mapped_mcat_id']})
MCAT from search URL: {ctx.get('url_mcat_id')} (None means not in URL)

Is this MCAT correct for this BuyLead title?
Reason step by step considering Indian B2B context.

Return JSON only:
{{
  "is_correct": true or false,
  "confidence": 0-100,
  "reasoning": "step by step explanation",
  "suggested_mcat": "better MCAT name if wrong, else same",
  "fix": "one actionable sentence"
}}""",
    )

    is_correct = result.get("is_correct", True)
    raw_confidence = int(result.get("confidence", 50))
    # Convert to mismatch confidence: if correct → low mismatch confidence
    mismatch_confidence = (100 - raw_confidence) if is_correct else raw_confidence

    return {
        "bucket": "MCAT_MISMATCH",
        "is_mismatch": not is_correct,
        "confidence": mismatch_confidence,
        "reasoning": result.get("reasoning", ""),
        "suggested_mcat": result.get("suggested_mcat", ctx["mapped_mcat_name"]),
        "fix": result.get("fix", "Verify MCAT mapping manually"),
    }
