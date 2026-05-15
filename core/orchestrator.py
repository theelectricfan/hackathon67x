"""
RCA Orchestrator — runs all 5 skills, ranks by confidence, saves outputs.
"""
from langfuse_client import observe, flush
from output.result_writer import ResultWriter
from skills.skill_mcat import run_skill_mcat
from skills.skill_content import run_skill_content
from skills.skill_spec import run_skill_spec
from skills.skill_intent import run_skill_intent
from skills.skill_seller import run_skill_seller
from output.report_generator import generate_bl_card


BUCKET_ORDER = [
    "MCAT_MISMATCH",
    "THIN_CONTENT",
    "SPEC_CONTRADICTION",
    "LOW_BUYER_INTENT",
    "SELLER_SIDE_FAILURE",
]


@observe(name="rca_orchestrator")
def run_rca(ctx: dict) -> dict:
    writer = ResultWriter(ctx["offer_id"])
    writer.save("00_bl_context", _safe_ctx(ctx))

    # ── Run all 5 skills ──────────────────────────────────────────────────────
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

    # ── Rank buckets by confidence ────────────────────────────────────────────
    bucket_scores = {
        "MCAT_MISMATCH":       results["mcat"]["confidence"],
        "THIN_CONTENT":        results["content"]["confidence"],
        "SPEC_CONTRADICTION":  results["spec"]["confidence"],
        "LOW_BUYER_INTENT":    results["intent"]["confidence"],
        "SELLER_SIDE_FAILURE": results["seller"]["confidence"],
    }

    ranked = sorted(bucket_scores.items(), key=lambda x: x[1], reverse=True)
    primary_bucket, primary_confidence = ranked[0]
    secondary = ranked[1] if ranked[1][1] > 40 else (None, 0)

    # Pull fix text for primary and secondary
    skill_key_map = {
        "MCAT_MISMATCH": "mcat",
        "THIN_CONTENT": "content",
        "SPEC_CONTRADICTION": "spec",
        "LOW_BUYER_INTENT": "intent",
        "SELLER_SIDE_FAILURE": "seller",
    }
    primary_fix = results[skill_key_map[primary_bucket]].get("fix", "")
    secondary_fix = (
        results[skill_key_map[secondary[0]]].get("fix", "") if secondary[0] else None
    )

    final = {
        "offer_id": ctx["offer_id"],
        "offer_name": ctx["offer_name"],
        "mapped_mcat": ctx["mapped_mcat_name"],
        "primary_bucket": primary_bucket,
        "primary_confidence": primary_confidence,
        "primary_fix": primary_fix,
        "secondary_bucket": secondary[0],
        "secondary_confidence": secondary[1],
        "secondary_fix": secondary_fix,
        "bucket_scores": bucket_scores,
        "all_skill_results": results,
        "output_dir": str(writer.dir),
        "run_id": writer.run_id,
    }

    writer.save("06_final_rca", {k: v for k, v in final.items() if k != "all_skill_results"})
    writer.save_text("07_bl_card", generate_bl_card(final))
    writer.save("08_manifest", writer.manifest())

    flush()
    return final


def _safe_ctx(ctx: dict) -> dict:
    """Strip non-serialisable objects for JSON saving."""
    return {
        k: v for k, v in ctx.items()
        if k not in ("mcat_spec_catalog",) and not callable(v)
    }
