"""
Bucket 7 — Quantity Mismatch.

Checks if the buyer's quantity and AOV are B2B-appropriate or retail-level.
Three signals:
  1. probable_req_type = "Personal Use" → retail buyer in B2B MCAT (rule-based)
  2. Quantity vs B2B norms for this product (Parallel AI)
  3. AOV vs quantity consistency — implied unit price check (Parallel AI)

confidence = 0 if no quantity specs and AOV blank (insufficient data to judge).
"""
from llm.client import llm
from langfuse_client import observe


_PARALLEL_OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "is_retail_quantity":    {"type": "boolean"},
            "aov_quantity_mismatch": {"type": "boolean"},
            "req_type_mismatch":     {"type": "boolean"},
            "confidence":            {"type": "integer"},
            "reasoning":             {"type": "string"},
            "fix":                   {"type": "string"},
        },
        "required": [
            "is_retail_quantity", "aov_quantity_mismatch",
            "req_type_mismatch", "confidence", "reasoning", "fix"
        ],
    },
}


@observe(name="skill_quantity")
def run_skill_quantity(ctx: dict) -> dict:
    specs_filled      = ctx["specs_filled"]
    mcat_spec_catalog = ctx.get("mcat_spec_catalog", {})
    offer_name        = ctx["offer_name"]
    mcat_name         = ctx.get("mapped_mcat_name", "")
    aov               = ctx.get("probable_order_value")
    req_type          = ctx.get("probable_req_type")
    gst_verified      = bool(ctx.get("buyer", {}).get("eto_ofr_buyer_is_gst_verf"))

    # ── Extract quantity-related specs ────────────────────────────────────────
    quantity_specs = {
        spec: value
        for spec, value in specs_filled.items()
        if mcat_spec_catalog.get(spec, {}).get("is_quantity_related")
    }

    aov_blank        = not aov
    req_type_retail  = str(req_type or "").strip().lower() == "personal use"
    has_quantity     = len(quantity_specs) > 0

    # ── Insufficient data: no quantity specs and no AOV ───────────────────────
    if not has_quantity and aov_blank and not req_type_retail:
        return {
            "bucket":           "QUANTITY_MISMATCH",
            "quantity_specs":   {},
            "aov":              aov,
            "req_type":         req_type,
            "req_type_retail":  False,
            "aov_blank":        True,
            "gst_verified":     gst_verified,
            "confidence":       0,
            "fix":              "No quantity or order value data available to assess.",
        }

    # ── Rule-based: req type retail is a hard signal ──────────────────────────
    # We still run Parallel AI for full analysis, but flag this upfront
    quantity_text = (
        "\n".join(f"  - {k}: {v}" for k, v in quantity_specs.items())
        if quantity_specs else "  (no quantity specs filled)"
    )

    # ── Parallel AI: quantity + AOV B2B check ────────────────────────────────
    parallel_result = llm.parallel(
        prompt=f"""BuyLead on IndiaMART (Indian B2B marketplace — wholesale/bulk buying platform):
Product: "{offer_name}" (Category: {mcat_name})

Buyer's order details:
- Quantity specs filled:
{quantity_text}
- Approximate Order Value (AOV): {aov if aov else "Not provided"}
- Requirement type declared: {req_type if req_type else "Not specified"}
- GST verified (registered business): {gst_verified}

Analyse for THREE issues:

1. RETAIL QUANTITY — Is the quantity retail-level for this product in India?
   (e.g. buying 1 piece / 100g / small pack in a wholesale B2B marketplace = retail mismatch)
   What is the typical minimum B2B order quantity for this product in Indian market?

2. AOV vs QUANTITY MISMATCH — If both quantity and AOV are provided, does the implied unit price make sense?
   (e.g. 500 pieces at Rs. 1000-5000 total = Rs. 2-10/piece — is that realistic for this product?)

3. REQ TYPE vs MARKETPLACE — "Personal Use" in a B2B wholesale marketplace is a mismatch.
   Is this buyer's stated purpose appropriate for this B2B category?

Be specific — use actual Indian B2B market price ranges and MOQ norms for this product.""",
        task_spec={
            "input_schema":  {"type": "text"},
            "output_schema": _PARALLEL_OUTPUT_SCHEMA,
        },
    )

    return {
        "bucket": "QUANTITY_MISMATCH",
        # Rule-based signals
        "quantity_specs":  quantity_specs,
        "aov":             aov,
        "req_type":        req_type,
        "req_type_retail": req_type_retail,
        "aov_blank":       aov_blank,
        "gst_verified":    gst_verified,
        # Parallel AI result
        "is_retail_quantity":    parallel_result.get("is_retail_quantity", False),
        "aov_quantity_mismatch": parallel_result.get("aov_quantity_mismatch", False),
        "req_type_mismatch":     parallel_result.get("req_type_mismatch", req_type_retail),
        "confidence":            int(parallel_result.get("confidence", 0)),
        "reasoning":             parallel_result.get("reasoning", ""),
        "fix":                   parallel_result.get("fix", "Confirm order quantity and value are B2B-appropriate."),
        "parallel_raw":          parallel_result,
    }
