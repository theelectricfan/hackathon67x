"""
Bucket 6 — Spec Value Quality.

Checks if out-of-catalog spec values are real/valid in Indian B2B market.
Only activates when buyer filled values not present in catalog options.
Uses Parallel AI to verify each out-of-catalog value.
confidence = 0 if all specs are within catalog options.
"""
from llm.client import llm
from langfuse_client import observe


_PARALLEL_OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "spec_verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "spec":              {"type": "string"},
                        "buyer_value":       {"type": "string"},
                        "is_valid_in_market": {"type": "boolean"},
                        "reasoning":         {"type": "string"},
                    },
                    "required": ["spec", "buyer_value", "is_valid_in_market", "reasoning"],
                },
            },
            "confidence": {"type": "integer"},
            "fix":        {"type": "string"},
        },
        "required": ["spec_verdicts", "confidence", "fix"],
    },
}


@observe(name="skill_spec_quality")
def run_skill_spec_quality(ctx: dict) -> dict:
    specs_filled      = ctx["specs_filled"]
    mcat_spec_catalog = ctx.get("mcat_spec_catalog", {})
    offer_name        = ctx["offer_name"]
    mcat_name         = ctx.get("mapped_mcat_name", "")

    # ── Rule-based: find out-of-catalog specs ────────────────────────────────
    out_of_catalog = []
    for spec_name, buyer_value in specs_filled.items():
        catalog_info = mcat_spec_catalog.get(spec_name, {})
        options      = catalog_info.get("options", [])
        is_free_text = len(options) == 0
        if not is_free_text and str(buyer_value) not in options:
            out_of_catalog.append({
                "spec":          spec_name,
                "buyer_value":   buyer_value,
                "valid_options": options,
            })

    out_of_catalog_count = len(out_of_catalog)
    total_filled         = len(specs_filled)

    # ── Fast path: all specs within catalog → no issue ───────────────────────
    if out_of_catalog_count == 0:
        return {
            "bucket":              "SPEC_VALUE_QUALITY",
            "out_of_catalog_count": 0,
            "total_filled":        total_filled,
            "out_of_catalog_pct":  0.0,
            "out_of_catalog_specs": [],
            "confidence":          0,
            "fix":                 "All spec values are within catalog options.",
        }

    out_of_catalog_pct = round(out_of_catalog_count / total_filled * 100, 1) if total_filled else 0.0

    # ── Parallel AI: verify each out-of-catalog value ────────────────────────
    spec_lines = "\n".join(
        f"  - Spec: \"{s['spec']}\"\n"
        f"    Buyer filled: \"{s['buyer_value']}\"\n"
        f"    Valid catalog options: {s['valid_options']}"
        for s in out_of_catalog
    )

    parallel_result = llm.parallel(
        prompt=f"""BuyLead on IndiaMART (Indian B2B marketplace):
Product: "{offer_name}" (Category: {mcat_name})

The following specs were filled with values NOT present in the standard catalog options.
Verify each value against real Indian B2B market knowledge:
Is this a recognised, valid product variant/specification in the Indian market?
Or is it a typo, junk value, or non-existent variant?

Specs to verify:
{spec_lines}

For each spec, determine:
- is_valid_in_market: true if this value is a real/recognized variant in India B2B market
- reasoning: explain why it is or isn't valid with specific market context""",
        task_spec={
            "input_schema":  {"type": "text"},
            "output_schema": _PARALLEL_OUTPUT_SCHEMA,
        },
    )

    # Enrich out_of_catalog list with Parallel AI verdicts
    verdict_map = {
        v["spec"]: v
        for v in parallel_result.get("spec_verdicts", [])
    }
    enriched = []
    for s in out_of_catalog:
        verdict = verdict_map.get(s["spec"], {})
        enriched.append({
            "spec":               s["spec"],
            "buyer_value":        s["buyer_value"],
            "valid_options":      s["valid_options"],
            "is_valid_in_market": verdict.get("is_valid_in_market", None),
            "reasoning":          verdict.get("reasoning", ""),
        })

    invalid_count = sum(1 for s in enriched if s["is_valid_in_market"] is False)

    return {
        "bucket": "SPEC_VALUE_QUALITY",
        # Counts
        "out_of_catalog_count": out_of_catalog_count,
        "total_filled":         total_filled,
        "out_of_catalog_pct":   out_of_catalog_pct,
        "invalid_in_market":    invalid_count,
        # Per-spec detail
        "out_of_catalog_specs": enriched,
        # LLM result
        "confidence": int(parallel_result.get("confidence", 0)),
        "fix":        parallel_result.get("fix", "Correct the spec values to match standard catalog options."),
        "parallel_raw": parallel_result,
    }
