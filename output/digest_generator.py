from collections import Counter


def generate_weekly_digest(all_rca_results: list) -> str:
    total = len(all_rca_results)
    if total == 0:
        return "No BLs processed."

    bucket_counts = Counter(r.get("primary_bucket", "UNKNOWN") for r in all_rca_results)
    fix_counts = Counter(r.get("primary_fix", "") for r in all_rca_results if r.get("primary_fix"))

    lines = [
        "=" * 55,
        "  BL RCA WEEKLY DIGEST",
        f"  Total BLs Analysed : {total}",
        "=" * 55,
        "",
        "  BUCKET DISTRIBUTION",
        "  " + "-" * 35,
    ]

    for bucket, count in bucket_counts.most_common():
        pct = count / total * 100
        bar = "█" * int(pct / 5)
        lines.append(f"  {bucket:<25} {count:>3} ({pct:4.1f}%)  {bar}")

    lines += [
        "",
        "  TOP 3 FIX RECOMMENDATIONS",
        "  " + "-" * 35,
    ]
    for i, (fix, count) in enumerate(fix_counts.most_common(3), 1):
        lines.append(f"  {i}. [{count} BLs] {fix[:70]}")

    estimated_recovery = int(total * 0.15)
    lines += [
        "",
        "  ESTIMATED IMPACT",
        "  " + "-" * 35,
        f"  Applying top fixes could recover ~{estimated_recovery} BLs ({estimated_recovery/total*100:.0f}%)",
        "=" * 55,
    ]

    return "\n".join(lines)
