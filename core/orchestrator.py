"""
RCA Orchestrator — runs all 8 skills, ranks by confidence, reports full overlap.

Execution model
---------------
1. B1 (MCAT mismatch) runs first — its outcome gates B2.
2. Remaining 7 skills (B2-B8) run in parallel via ThreadPoolExecutor;
   each is dominated by LLM I/O so threads parallelise cleanly.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from langfuse_client import observe, flush
from output.report_generator import generate_bl_card
from output.result_writer import ResultWriter
from skills.skill_content import run_skill_content
from skills.skill_intent import run_skill_intent
from skills.skill_mcat import run_skill_mcat
from skills.skill_quantity import run_skill_quantity
from skills.skill_retail import run_skill_retail
from skills.skill_seller import run_skill_seller
from skills.skill_spec import run_skill_spec
from skills.skill_spec_quality import run_skill_spec_quality

logger = logging.getLogger(__name__)


BUCKET_ORDER = [
    "MCAT_MISMATCH",
    "THIN_CONTENT",
    "SPEC_CONTRADICTION",
    "LOW_BUYER_INTENT",
    "SELLER_SIDE_FAILURE",
    "SPEC_VALUE_QUALITY",
    "QUANTITY_MISMATCH",
    "RETAIL_QUERY",
]

BUCKET_LABELS = {
    "MCAT_MISMATCH":       "MCAT Mismatch",
    "THIN_CONTENT":        "Thin Content",
    "SPEC_CONTRADICTION":  "Spec Contradiction",
    "LOW_BUYER_INTENT":    "Low Buyer Intent",
    "SELLER_SIDE_FAILURE": "Seller Side Failure",
    "SPEC_VALUE_QUALITY":  "Spec Value Quality",
    "QUANTITY_MISMATCH":   "Quantity Mismatch",
    "RETAIL_QUERY":        "Retail Query",
}

ACTIVE_THRESHOLD = 40

SKILL_KEY_MAP = {
    "MCAT_MISMATCH":       "mcat",
    "THIN_CONTENT":        "content",
    "SPEC_CONTRADICTION":  "spec",
    "LOW_BUYER_INTENT":    "intent",
    "SELLER_SIDE_FAILURE": "seller",
    "SPEC_VALUE_QUALITY":  "spec_quality",
    "QUANTITY_MISMATCH":   "quantity",
    "RETAIL_QUERY":        "retail",
}

# Skills runnable in parallel after B1 has completed
_PARALLEL_SKILLS = [
    ("content",      run_skill_content),
    ("spec",         run_skill_spec),
    ("intent",       run_skill_intent),
    ("seller",       run_skill_seller),
    ("spec_quality", run_skill_spec_quality),
    ("quantity",     run_skill_quantity),
    ("retail",       run_skill_retail),
]


@observe(name="rca_orchestrator")
def run_rca(ctx: dict) -> dict:
    t_start = time.time()
    writer = ResultWriter(ctx["offer_id"])
    writer.save("00_bl_context", _safe_ctx(ctx))

    results: dict = {}

    # ── Stage 1: B1 (MCAT mismatch) — gates B2 ──────────────────────────────
    results["mcat"] = run_skill_mcat(ctx)
    writer.save("01_skill_mcat", results["mcat"])

    # Pass B1 verdict to downstream skills via ctx
    ctx = dict(ctx)  # shallow-copy so we don't mutate caller's dict
    ctx["_b1_mcat_correct"] = not results["mcat"].get("is_mismatch", False)

    # ── Stage 2: B2-B8 in parallel ───────────────────────────────────────────
    with ThreadPoolExecutor(max_workers=len(_PARALLEL_SKILLS)) as pool:
        futures = {pool.submit(fn, ctx): name for name, fn in _PARALLEL_SKILLS}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                logger.exception("skill %s crashed", name)
                results[name] = {
                    "bucket":     name.upper(),
                    "confidence": 0,
                    "fix":        f"Skill error: {e}",
                    "error":      str(e),
                }

    # Persist each skill result with stable numbering for the UI
    writer.save("02_skill_content",      results["content"])
    writer.save("03_skill_spec",         results["spec"])
    writer.save("04_skill_intent",       results["intent"])
    writer.save("05_skill_seller",       results["seller"])
    writer.save("06_skill_spec_quality", results["spec_quality"])
    writer.save("07_skill_quantity",     results["quantity"])
    writer.save("08_skill_retail",       results["retail"])

    # ── Score all buckets ────────────────────────────────────────────────────
    bucket_scores = {
        "MCAT_MISMATCH":       results["mcat"]["confidence"],
        "THIN_CONTENT":        results["content"]["confidence"],
        "SPEC_CONTRADICTION":  results["spec"]["confidence"],
        "LOW_BUYER_INTENT":    results["intent"]["confidence"],
        "SELLER_SIDE_FAILURE": results["seller"]["confidence"],
        "SPEC_VALUE_QUALITY":  results["spec_quality"]["confidence"],
        "QUANTITY_MISMATCH":   results["quantity"]["confidence"],
        "RETAIL_QUERY":        results["retail"]["confidence"],
    }

    ranked = sorted(bucket_scores.items(), key=lambda x: x[1], reverse=True)
    primary_bucket, primary_confidence = ranked[0]
    primary_fix = results[SKILL_KEY_MAP[primary_bucket]].get("fix", "")

    secondary_bucket = ranked[1][0] if ranked[1][1] > ACTIVE_THRESHOLD else None
    secondary_confidence = ranked[1][1] if secondary_bucket else 0
    secondary_fix = (
        results[SKILL_KEY_MAP[secondary_bucket]].get("fix", "") if secondary_bucket else None
    )

    active_buckets = [
        {
            "bucket":     b,
            "label":      BUCKET_LABELS[b],
            "confidence": score,
            "fix":        results[SKILL_KEY_MAP[b]].get("fix", ""),
        }
        for b, score in ranked if score > ACTIVE_THRESHOLD
    ]
    overlap_count = len(active_buckets)

    if overlap_count == 0:
        overlap_summary = "No significant issues detected"
    elif overlap_count == 1:
        overlap_summary = f"1 issue detected: {active_buckets[0]['label']}"
    else:
        labels = ", ".join(ab["label"] for ab in active_buckets)
        overlap_summary = f"{overlap_count} overlapping issues detected: {labels}"

    all_bucket_fixes = {
        b: results[SKILL_KEY_MAP[b]].get("fix", "") for b in BUCKET_ORDER
    }

    final = {
        "offer_id":    ctx["offer_id"],
        "offer_name":  ctx["offer_name"],
        "mapped_mcat": ctx["mapped_mcat_name"],
        "primary_bucket":     primary_bucket,
        "primary_confidence": primary_confidence,
        "primary_fix":        primary_fix,
        "secondary_bucket":     secondary_bucket,
        "secondary_confidence": secondary_confidence,
        "secondary_fix":        secondary_fix,
        "overlap_count":   overlap_count,
        "overlap_summary": overlap_summary,
        "active_buckets":  active_buckets,
        "all_bucket_fixes": all_bucket_fixes,
        "bucket_scores":   bucket_scores,
        "all_skill_results": results,
        "output_dir": str(writer.dir),
        "run_id":     writer.run_id,
        "elapsed_secs": round(time.time() - t_start, 2),
    }

    writer.save("09_final_rca", {k: v for k, v in final.items() if k != "all_skill_results"})
    writer.save_text("10_bl_card", generate_bl_card(final))
    writer.save("11_manifest", writer.manifest())

    flush()
    return final


def _safe_ctx(ctx: dict) -> dict:
    """Strip non-serialisable objects for JSON saving."""
    return {
        k: v for k, v in ctx.items()
        if k not in ("mcat_spec_catalog",) and not callable(v)
    }
