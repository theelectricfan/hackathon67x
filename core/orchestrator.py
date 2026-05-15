"""
RCA Orchestrator — runs all 7 skills, ranks by confidence, reports full overlap.
"""
from langfuse_client import observe, flush
from output.result_writer import ResultWriter
from skills.skill_mcat import run_skill_mcat
from skills.skill_content import run_skill_content
from skills.skill_spec import run_skill_spec
from skills.skill_intent import run_skill_intent
from skills.skill_seller import run_skill_seller
from skills.skill_spec_quality import run_skill_spec_quality
from skills.skill_quantity import run_skill_quantity
from output.report_generator import generate_bl_card


BUCKET_ORDER = [
    "MCAT_MISMATCH",
    "THIN_CONTENT",
    "SPEC_CONTRADICTION",
    "LOW_BUYER_INTENT",
    "SELLER_SIDE_FAILURE",
    "SPEC_VALUE_QUALITY",
    "QUANTITY_MISMATCH",
]

BUCKET_LABELS = {
    "MCAT_MISMATCH":       "MCAT Mismatch",
    "THIN_CONTENT":        "Thin Content",
    "SPEC_CONTRADICTION":  "Spec Contradiction",
    "LOW_BUYER_INTENT":    "Low Buyer Intent",
    "SELLER_SIDE_FAILURE": "Seller Side Failure",
    "SPEC_VALUE_QUALITY":  "Spec Value Quality",
    "QUANTITY_MISMATCH":   "Quantity Mismatch",
}

# Buckets scoring above this threshold are considered active issues
ACTIVE_THRESHOLD = 40

SKILL_KEY_MAP = {
    "MCAT_MISMATCH":       "mcat",
    "THIN_CONTENT":        "content",
    "SPEC_CONTRADICTION":  "spec",
    "LOW_BUYER_INTENT":    "intent",
    "SELLER_SIDE_FAILURE": "seller",
    "SPEC_VALUE_QUALITY":  "spec_quality",
    "QUANTITY_MISMATCH":   "quantity",
}


@observe(name="rca_orchestrator")
def run_rca(ctx: dict) -> dict:
    writer = ResultWriter(ctx["offer_id"])
    writer.save("00_bl_context", _safe_ctx(ctx))

    # ── Run all 7 skills ──────────────────────────────────────────────────────
    results = {}

    results["mcat"] = run_skill_mcat(ctx)
    writer.save("01_skill_mcat", results["mcat"])

    results["content"] = run_skill_content(ctx)
    writer.save("02_skill_content", results["content"])

    results["spec"] = run_skill_spec(ctx)
    writer.save("03_skill_spec", results["spec"])

    results["intent"] = run_skill_intent(ctx)
    writer.save("04_skill_intent", results["intent"])

    results["seller"] = run_skill_seller(ctx)
    writer.save("05_skill_seller", results["seller"])

    results["spec_quality"] = run_skill_spec_quality(ctx)
    writer.save("06_skill_spec_quality", results["spec_quality"])

    results["quantity"] = run_skill_quantity(ctx)
    writer.save("07_skill_quantity", results["quantity"])

    # ── Score all buckets ─────────────────────────────────────────────────────
    bucket_scores = {
        "MCAT_MISMATCH":       results["mcat"]["confidence"],
        "THIN_CONTENT":        results["content"]["confidence"],
        "SPEC_CONTRADICTION":  results["spec"]["confidence"],
        "LOW_BUYER_INTENT":    results["intent"]["confidence"],
        "SELLER_SIDE_FAILURE": results["seller"]["confidence"],
        "SPEC_VALUE_QUALITY":  results["spec_quality"]["confidence"],
        "QUANTITY_MISMATCH":   results["quantity"]["confidence"],
    }

    ranked = sorted(bucket_scores.items(), key=lambda x: x[1], reverse=True)

    # Primary = highest scoring bucket
    primary_bucket, primary_confidence = ranked[0]
    primary_fix = results[SKILL_KEY_MAP[primary_bucket]].get("fix", "")

    # Secondary = second highest IF above threshold
    secondary_bucket = ranked[1][0] if ranked[1][1] > ACTIVE_THRESHOLD else None
    secondary_confidence = ranked[1][1] if secondary_bucket else 0
    secondary_fix = (
        results[SKILL_KEY_MAP[secondary_bucket]].get("fix", "") if secondary_bucket else None
    )

    # ── Overlap: ALL buckets above threshold ──────────────────────────────────
    active_buckets = [
        {
            "bucket":     b,
            "label":      BUCKET_LABELS[b],
            "confidence": score,
            "fix":        results[SKILL_KEY_MAP[b]].get("fix", ""),
        }
        for b, score in ranked
        if score > ACTIVE_THRESHOLD
    ]
    overlap_count = len(active_buckets)

    if overlap_count == 0:
        overlap_summary = "No significant issues detected"
    elif overlap_count == 1:
        overlap_summary = f"1 issue detected: {active_buckets[0]['label']}"
    else:
        labels = ", ".join(ab["label"] for ab in active_buckets)
        overlap_summary = f"{overlap_count} overlapping issues detected: {labels}"

    # ── All bucket fixes ──────────────────────────────────────────────────────
    all_bucket_fixes = {
        b: results[SKILL_KEY_MAP[b]].get("fix", "")
        for b in BUCKET_ORDER
    }

    final = {
        "offer_id":    ctx["offer_id"],
        "offer_name":  ctx["offer_name"],
        "mapped_mcat": ctx["mapped_mcat_name"],
        # Primary (always present)
        "primary_bucket":     primary_bucket,
        "primary_confidence": primary_confidence,
        "primary_fix":        primary_fix,
        # Secondary (only if above threshold)
        "secondary_bucket":     secondary_bucket,
        "secondary_confidence": secondary_confidence,
        "secondary_fix":        secondary_fix,
        # Full overlap data
        "overlap_count":   overlap_count,
        "overlap_summary": overlap_summary,
        "active_buckets":  active_buckets,
        "all_bucket_fixes": all_bucket_fixes,
        # Raw scores for all buckets
        "bucket_scores": bucket_scores,
        # All skill details
        "all_skill_results": results,
        "output_dir": str(writer.dir),
        "run_id":     writer.run_id,
    }

    writer.save("08_final_rca", {k: v for k, v in final.items() if k != "all_skill_results"})
    writer.save_text("09_bl_card", generate_bl_card(final))
    writer.save("10_manifest", writer.manifest())

    flush()
    return final


def _safe_ctx(ctx: dict) -> dict:
    """Strip non-serialisable objects for JSON saving."""
    return {
        k: v for k, v in ctx.items()
        if k not in ("mcat_spec_catalog",) and not callable(v)
    }
