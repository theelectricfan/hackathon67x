"""Bucket 1 — MCAT Mismatch. Single LLM call: title + category only."""
from llm.client import llm
from langfuse_client import observe


@observe(name="skill_mcat")
def run_skill_mcat(ctx: dict) -> dict:
    result = llm.chat_json(
        system=(
            "You are an MCAT category mapping expert at IndiaMART, "
            "India's largest B2B marketplace."
        ),
        user=f"""BuyLead Title: "{ctx['offer_name']}"
Mapped Category: "{ctx['mapped_mcat_name']}"

Is this category a mismatch for this product?
Think about what the buyer is actually looking for based on the title.

Return JSON only:
{{
  "is_mismatch": true or false,
  "confidence": 0-100,
  "reasoning": "one clear explanation",
  "suggested_mcat": "correct category name if mismatched, else leave empty",
  "fix": "one actionable sentence for the buyer or ops team"
}}""",
    )

    is_mismatch = bool(result.get("is_mismatch", False))
    raw_confidence = int(result.get("confidence", 50))
    # confidence = how sure LLM is about its is_mismatch verdict
    # bucket confidence = mismatch likelihood → invert when category is correct
    confidence = raw_confidence if is_mismatch else (100 - raw_confidence)

    return {
        "bucket": "MCAT_MISMATCH",
        "is_mismatch": is_mismatch,
        "confidence": confidence,
        "reasoning": result.get("reasoning", ""),
        "suggested_mcat": result.get("suggested_mcat", ""),
        "fix": result.get("fix", "Verify category mapping manually"),
    }
