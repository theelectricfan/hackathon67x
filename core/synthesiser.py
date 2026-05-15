BUCKET_PRIORITY = {
    "MCAT_MISMATCH": 1,
    "THIN_CONTENT": 2,
    "SPEC_CONTRADICTION": 3,
    "LOW_BUYER_INTENT": 4,
    "SELLER_SIDE_FAILURE": 5,
}


def synthesise(bl_id: str, skill_results: dict) -> dict:
    ranked = sorted(
        [(name, res) for name, res in skill_results.items() if res.get("confidence", 0) > 20],
        key=lambda x: (-x[1].get("confidence", 0), BUCKET_PRIORITY.get(x[1].get("bucket", ""), 99)),
    )

    primary = ranked[0][1] if len(ranked) > 0 else {}
    secondary = ranked[1][1] if len(ranked) > 1 else {}

    return {
        "bl_id": bl_id,
        "primary_bucket": primary.get("bucket", "UNKNOWN"),
        "primary_confidence": primary.get("confidence", 0),
        "primary_fix": primary.get("fix", "No fix identified"),
        "secondary_bucket": secondary.get("bucket"),
        "secondary_confidence": secondary.get("confidence", 0),
        "secondary_fix": secondary.get("fix"),
        "all_skill_results": skill_results,
    }
