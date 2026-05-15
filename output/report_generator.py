BUCKET_EMOJI = {
    "MCAT_MISMATCH":       ("🔵", "MCAT Mismatch"),
    "THIN_CONTENT":        ("🟠", "Thin Content"),
    "SPEC_CONTRADICTION":  ("🟣", "Spec Contradiction"),
    "LOW_BUYER_INTENT":    ("🟡", "Low Buyer Intent"),
    "SELLER_SIDE_FAILURE": ("🔴", "Seller Side Failure"),
    "UNKNOWN":             ("⚪", "Unknown"),
}


def _bar(confidence: int, width: int = 20) -> str:
    filled = int(width * confidence / 100)
    return f"[{'█' * filled}{'░' * (width - filled)}] {confidence}%"


def generate_bl_card(rca: dict) -> str:
    p = rca.get("primary_bucket", "UNKNOWN")
    p_emoji, p_label = BUCKET_EMOJI.get(p, BUCKET_EMOJI["UNKNOWN"])
    s = rca.get("secondary_bucket")
    s_emoji, s_label = BUCKET_EMOJI.get(s or "UNKNOWN", BUCKET_EMOJI["UNKNOWN"])

    lines = [
        "━" * 58,
        f"  BL ID   : {rca.get('offer_id', 'N/A')}",
        f"  Title   : {str(rca.get('offer_name',''))[:55]}",
        f"  MCAT    : {rca.get('mapped_mcat', 'N/A')}",
        f"  Run ID  : {rca.get('run_id', 'N/A')}",
        "━" * 58,
        f"  {p_emoji} PRIMARY   : {p_label}",
        f"     {_bar(rca.get('primary_confidence', 0))}",
        f"     Fix : {rca.get('primary_fix', '—')}",
    ]
    if s:
        lines += [
            "",
            f"  {s_emoji} SECONDARY : {s_label}",
            f"     {_bar(rca.get('secondary_confidence', 0))}",
            f"     Fix : {rca.get('secondary_fix', '—')}",
        ]
    lines += [
        "",
        "  BUCKET SCORES",
        "  " + "─" * 40,
    ]
    for bucket, score in sorted(
        rca.get("bucket_scores", {}).items(), key=lambda x: x[1], reverse=True
    ):
        emoji = BUCKET_EMOJI.get(bucket, BUCKET_EMOJI["UNKNOWN"])[0]
        lines.append(f"  {emoji} {bucket:<25} {_bar(score, 12)}")
    lines.append("━" * 58)
    return "\n".join(lines)
