"""
Bucket 2 — Thin Content.

Computes fill metrics, feeds everything to Parallel AI to classify
if the BL represents a uniquely identifiable product/SKU or is too thin.
Gateway summariser produces final confidence + fix.
"""
from llm.client import llm
from langfuse_client import observe


_PARALLEL_OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "is_thin":    {"type": "boolean"},
            "confidence": {"type": "integer"},
            "reasoning":  {"type": "string"},
        },
        "required": ["is_thin", "confidence", "reasoning"],
    },
}


@observe(name="skill_content")
def run_skill_content(ctx: dict) -> dict:
    specs_filled       = ctx["specs_filled"]
    fill_count         = ctx["specs_fill_count"]
    mcat_spec_catalog  = ctx.get("mcat_spec_catalog", {})
    priority_specs     = ctx.get("priority_specs", [])
    offer_name         = ctx["offer_name"]
    mcat_name          = ctx.get("mapped_mcat_name", "")
    thin_sold_count    = ctx.get("thin_sold_bl_count")

    # ── Compute fill metrics ──────────────────────────────────────────────────
    total_specs = len(mcat_spec_catalog)
    fill_ratio  = round(fill_count / total_specs, 2) if total_specs else 0.0
    fill_pct    = round(fill_ratio * 100, 1)

    total_priority   = len(priority_specs)
    priority_filled  = sum(1 for s in priority_specs if s in specs_filled)
    priority_ratio   = round(priority_filled / total_priority, 2) if total_priority else 1.0
    priority_pct     = round(priority_ratio * 100, 1)

    # Priority-1 and priority-2 spec fill status
    p1_specs = [s for s, info in mcat_spec_catalog.items() if info.get("priority") == 1]
    p2_specs = [s for s, info in mcat_spec_catalog.items() if info.get("priority") == 2]
    is_priority1_filled = any(s in specs_filled for s in p1_specs)
    is_priority2_filled = any(s in specs_filled for s in p2_specs)

    # ── Parallel AI: classify thin or not ────────────────────────────────────
    parallel_result = llm.parallel(
        prompt=f"""BuyLead posted on IndiaMART (Indian B2B marketplace):
Product: "{offer_name}" (Category: {mcat_name})

Specs filled by buyer: {specs_filled if specs_filled else "NONE — completely empty"}

Fill metrics:
- Specs filled: {fill_count} out of {total_specs} total ({fill_pct}%)
- Priority specs filled: {priority_filled} out of {total_priority} ({priority_pct}%)
- Priority-1 spec filled: {is_priority1_filled}
- Priority-2 spec filled: {is_priority2_filled}
- Thin-content BLs sold historically in this MCAT: {thin_sold_count if thin_sold_count is not None else "No benchmark data"}

Can an Indian B2B seller uniquely identify this product/SKU from the above specs and send an accurate quote?
Is this BuyLead too thin in content to be actionable?""",
        task_spec={
            "input_schema":  {"type": "text"},
            "output_schema": _PARALLEL_OUTPUT_SCHEMA,
        },
    )

    # ── Gateway summariser: final confidence + fix ────────────────────────────
    summary = llm.chat_json(
        system="You are a BuyLead content quality analyst for IndiaMART, India's largest B2B platform.",
        user=f"""Analysis result for BuyLead "{offer_name}" (Category: {mcat_name}):
{parallel_result}

Fill metrics:
- {fill_count}/{total_specs} specs filled ({fill_pct}%)
- {priority_filled}/{total_priority} priority specs filled ({priority_pct}%)
- Priority-1 filled: {is_priority1_filled} | Priority-2 filled: {is_priority2_filled}
- Thin-content BLs sold in this MCAT: {thin_sold_count if thin_sold_count is not None else "No data"}

Rate how much thin content is contributing to this BuyLead not being sold.
Return JSON only:
{{
  "confidence": 0-100,
  "fix": "one actionable sentence telling the buyer exactly what to add"
}}""",
    )

    # ── Spec review signal: thin fill + low DS5 benchmark ────────────────────
    spec_review_needed = False
    spec_review_reason = ""
    if fill_count <= 1:
        if thin_sold_count is None:
            spec_review_needed = True
            spec_review_reason = f"Only {fill_count} spec(s) filled — no benchmark data to assess impact."
        elif thin_sold_count <= 3:
            spec_review_needed = True
            spec_review_reason = (
                f"Only {fill_count} spec(s) filled and only {thin_sold_count} thin BL(s) "
                f"have sold in this category — buyer specs critically need review."
            )

    return {
        "bucket": "THIN_CONTENT",
        # Fill metrics
        "fill_count":    fill_count,
        "total_specs":   total_specs,
        "fill_ratio":    fill_ratio,
        "fill_pct":      fill_pct,
        # Priority metrics
        "priority_filled":      priority_filled,
        "total_priority":       total_priority,
        "priority_ratio":       priority_ratio,
        "priority_pct":         priority_pct,
        "is_priority1_filled":  is_priority1_filled,
        "is_priority2_filled":  is_priority2_filled,
        # DS5 benchmark
        "thin_sold_bl_count":   thin_sold_count,
        # Review signal
        "spec_review_needed":   spec_review_needed,
        "spec_review_reason":   spec_review_reason,
        # LLM result
        "confidence": int(summary.get("confidence", 50)),
        "fix":        summary.get("fix", "Add more product specifications to help sellers identify your requirement."),
        "parallel_raw": parallel_result,
    }
