"""
Bucket 3 — Spec Contradiction.

Checks three types of contradictions:
  1. Spec vs spec — filled values conflict with each other
  2. Offer name vs specs — title implies a value that contradicts a filled spec
  3. Out-of-catalog — buyer filled a value not in the valid options list

Parallel AI does deep contradiction analysis with full catalog context.
Gateway summariser produces final confidence + fix.
"""
from llm.client import llm
from langfuse_client import observe


_PARALLEL_OUTPUT_SCHEMA = {
    "type": "json",
    "json_schema": {
        "type": "object",
        "properties": {
            "has_contradiction": {"type": "boolean"},
            "contradicting_pairs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "spec_a":  {"type": "string"},
                        "spec_b":  {"type": "string"},
                        "reason":  {"type": "string"},
                    },
                    "required": ["spec_a", "spec_b", "reason"],
                },
            },
            "reasoning":  {"type": "string"},
            "confidence": {"type": "integer"},
            "fix":        {"type": "string"},
        },
        "required": ["has_contradiction", "contradicting_pairs", "reasoning", "confidence", "fix"],
    },
}


def _build_spec_context(specs_filled: dict, mcat_spec_catalog: dict) -> list[dict]:
    """
    For each filled spec, build a structured comparison row:
      spec name | buyer value | valid catalog options | is value in catalog
    """
    rows = []
    for spec_name, buyer_value in specs_filled.items():
        catalog_info = mcat_spec_catalog.get(spec_name, {})
        options = catalog_info.get("options", [])
        is_free_text = len(options) == 0
        in_catalog = is_free_text or (str(buyer_value) in options)
        rows.append({
            "spec":          spec_name,
            "buyer_value":   buyer_value,
            "valid_options": options if not is_free_text else ["(free text — any value valid)"],
            "in_catalog":    in_catalog,
            "is_free_text":  is_free_text,
        })
    return rows


@observe(name="skill_spec")
def run_skill_spec(ctx: dict) -> dict:
    specs_filled      = ctx["specs_filled"]
    offer_name        = ctx["offer_name"]
    mcat_name         = ctx.get("mapped_mcat_name", "")
    mcat_spec_catalog = ctx.get("mcat_spec_catalog", {})

    # ── Rule-based: out-of-catalog count ─────────────────────────────────────
    spec_context = _build_spec_context(specs_filled, mcat_spec_catalog)
    out_of_catalog_specs = [
        r["spec"] for r in spec_context
        if not r["in_catalog"] and not r["is_free_text"]
    ]
    out_of_catalog_count = len(out_of_catalog_specs)

    # ── Parallel AI: full contradiction analysis ──────────────────────────────
    spec_context_text = "\n".join(
        f"  - {r['spec']}: buyer filled \"{r['buyer_value']}\" | "
        f"valid options: {r['valid_options']} | "
        f"in catalog: {'YES' if r['in_catalog'] else 'NO — out of catalog'}"
        for r in spec_context
    ) or "  (no specs filled)"

    parallel_result = llm.parallel(
        prompt=f"""BuyLead posted on IndiaMART (Indian B2B marketplace):
Offer Title: "{offer_name}"
Category: {mcat_name}

Specs filled by buyer (with valid catalog options):
{spec_context_text}

Out-of-catalog specs already detected (rule-based): {out_of_catalog_count} spec(s) — {out_of_catalog_specs}

Check for THREE types of contradictions:

1. SPEC vs SPEC — do any two filled spec values contradict each other?
   (e.g. Material=Natural Rubber but Grade=Synthetic Grade — these conflict)

2. OFFER TITLE vs SPECS — does the offer title imply a spec value that contradicts a filled spec?
   (e.g. title says "Natural Rubber Sheet" but Form spec is filled as "Bale" — title says Sheet, spec says Bale)

3. OUT-OF-CATALOG — specs marked "in catalog: NO" above; are those values outright errors or just custom values?

For every contradiction found, name the two conflicting items exactly (spec_a vs spec_b, or "offer_title" vs spec name) and explain why they conflict.
Use Indian B2B market knowledge.
Also provide a fix: one actionable sentence telling the buyer what to correct.""",
        task_spec={
            "input_schema":  {"type": "text"},
            "output_schema": _PARALLEL_OUTPUT_SCHEMA,
        },
    )

    return {
        "bucket": "SPEC_CONTRADICTION",
        # Rule-based signals
        "out_of_catalog_count": out_of_catalog_count,
        "out_of_catalog_specs": out_of_catalog_specs,
        # Parallel AI result
        "has_contradiction":  parallel_result.get("has_contradiction", False),
        "confidence":         int(parallel_result.get("confidence", 0)),
        "reasoning":          parallel_result.get("reasoning", ""),
        "fix":                parallel_result.get("fix", "Review spec combinations for consistency"),
        "parallel_raw":       parallel_result,
    }
