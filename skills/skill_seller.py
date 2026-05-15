"""
Bucket 5 — Seller Side Failure.

Pre-computes pool-level and per-seller metrics from DS6.
Single Gateway Flash Lite call for reasoning — both seller-wise and combined.
Note: no direct "seller consumed BL" signal available in current data.
Proxy signals used: credits, alert rank, last login, BL purchase history, distance, city match.
"""
from llm.client import llm
from config.settings import settings
from langfuse_client import observe


def _ratio(count: int, total: int) -> dict:
    """Return numerator/denominator/percentage dict."""
    pct = round(count / total * 100, 1) if total else 0.0
    return {"count": count, "total": total, "pct": pct, "label": f"{count}/{total} ({pct}%)"}


def _days_since(date_str: str) -> int | None:
    """Approximate days since a date string."""
    if not date_str or str(date_str).strip() in ("", "nan", "None", "—"):
        return None
    from datetime import datetime, date
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(str(date_str).strip()[:19], fmt)
            return (date.today() - d.date()).days
        except Exception:
            continue
    return None


def _safe_float(val):
    try:
        return float(val)
    except Exception:
        return None


def _build_per_seller(sellers: list, buyer_city: str) -> list[dict]:
    """Build structured per-seller signal dict from DS6 rows."""
    buyer_city_lower = str(buyer_city or "").lower().strip()
    result = []

    for s in sorted(sellers, key=lambda x: x.get("selected_seller_rank") or 99):
        # Credits
        credits_raw = s.get("available_credits")
        credits_val = _safe_float(credits_raw)
        has_credits = bool(credits_val and credits_val > 0)

        # Last login
        last_login_str = str(s.get("glusr_usr_lastlogin") or "")
        days_inactive = _days_since(last_login_str)

        # Distance
        dist = _safe_float(s.get("eto_lead_supplier_dist"))

        # City match
        pref_cities   = str(s.get("a_rank_preferred_cities") or "").lower()
        consume_cities = str(s.get("b_rank_consuming_cities") or "").lower()
        city_match = bool(
            buyer_city_lower and
            (buyer_city_lower in pref_cities or buyer_city_lower in consume_cities)
        )

        # BL purchase history
        bl_yr = int(_safe_float(s.get("total_bl_purchased_1yr") or 0) or 0)

        # Alert rank
        alert_rank    = str(s.get("eto_trd_alert_rank") or "").strip().upper() or "—"
        alert_subrank = str(s.get("eto_trd_alert_subrank") or "").strip().upper() or "—"

        # Hard blockers (rule-based — no LLM needed)
        blockers = []
        if not has_credits:
            blockers.append("no credits — cannot respond")
        if days_inactive is not None and days_inactive > 60:
            blockers.append(f"inactive {days_inactive}d")
        if bl_yr == 0:
            blockers.append("no BL purchase history this year")
        if dist is not None and dist > 500:
            blockers.append(f"far ({dist:.0f} km)")
        if not city_match and buyer_city_lower:
            blockers.append("buyer city not in preferred cities")

        result.append({
            "rank":          int(s.get("selected_seller_rank") or 0),
            "company":       s.get("glusr_usr_companyname") or "—",
            "membership":    s.get("custtype_name") or "—",
            "alert_rank":    alert_rank,
            "alert_subrank": alert_subrank,
            "quality_score": s.get("_quality_score"),
            "credits":       credits_raw,
            "has_credits":   has_credits,
            "last_login":    last_login_str or "—",
            "days_inactive": days_inactive,
            "bl_purchased_1yr": bl_yr,
            "distance_km":   dist,
            "city_match":    city_match,
            "blockers":      blockers,
        })
    return result


@observe(name="skill_seller")
def run_skill_seller(ctx: dict) -> dict:
    sellers     = ctx.get("seller_detailed_pool", [])
    seller_pool = ctx.get("seller_pool", [])
    buyer_city  = str(ctx.get("buyer", {}).get("eto_ofr_s_city") or "").strip()
    offer_name  = ctx["offer_name"]
    mcat_name   = ctx.get("mapped_mcat_name", "")

    # Fall back to basic pool size if DS6 not available
    pool_size = len(sellers) if sellers else len(seller_pool)

    if pool_size == 0:
        return {
            "bucket":     "SELLER_SIDE_FAILURE",
            "pool_size":  0,
            "confidence": 90,
            "primary_failure_mode": "No sellers in pool — supply gap for this category",
            "fix": "Expand seller pool for this category and geography",
        }

    # ── Per-seller structured signals ─────────────────────────────────────────
    per_seller = _build_per_seller(sellers, buyer_city)

    # ── Pool-level aggregates (rule-based) ────────────────────────────────────
    total = len(per_seller)

    with_credits    = sum(1 for s in per_seller if s["has_credits"])
    no_credits      = total - with_credits

    city_match_cnt  = sum(1 for s in per_seller if s["city_match"])

    with_bl_history = sum(1 for s in per_seller if s["bl_purchased_1yr"] > 0)

    active_30d      = sum(
        1 for s in per_seller
        if s["days_inactive"] is not None and s["days_inactive"] <= 30
    )

    alert_breakdown = {"A": 0, "B": 0, "C": 0, "unknown": 0}
    for s in per_seller:
        key = s["alert_rank"] if s["alert_rank"] in ("A", "B", "C") else "unknown"
        alert_breakdown[key] += 1

    distances = [s["distance_km"] for s in per_seller if s["distance_km"] is not None]
    avg_dist  = round(sum(distances) / len(distances), 1) if distances else None
    min_dist  = round(min(distances), 1) if distances else None
    max_dist  = round(max(distances), 1) if distances else None

    quality_scores = [s["quality_score"] for s in per_seller if s["quality_score"] is not None]
    avg_quality    = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None

    pool_metrics = {
        "pool_size":        total,
        "with_credits":     _ratio(with_credits, total),
        "no_credits":       _ratio(no_credits, total),
        "city_match":       _ratio(city_match_cnt, total),
        "with_bl_history":  _ratio(with_bl_history, total),
        "active_last_30d":  _ratio(active_30d, total),
        "alert_breakdown":  alert_breakdown,
        "distance_km":      {"avg": avg_dist, "min": min_dist, "max": max_dist},
        "avg_quality_score": avg_quality,
        "all_credits_blank": no_credits == total,
    }

    # ── Build seller summary text for LLM ────────────────────────────────────
    seller_lines = []
    for s in per_seller:
        blockers_str = "; ".join(s["blockers"]) if s["blockers"] else "no hard blockers"
        dist_str     = f"{s['distance_km']:.0f} km" if s["distance_km"] is not None else "dist unknown"
        inactive_str = f"inactive {s['days_inactive']}d" if s["days_inactive"] is not None else "login unknown"
        seller_lines.append(
            f"  Seller #{s['rank']} — {s['company']} | "
            f"Alert: {s['alert_rank']}{s['alert_subrank']} | "
            f"Credits: {'YES' if s['has_credits'] else 'NO'} | "
            f"BL/yr: {s['bl_purchased_1yr']} | "
            f"{dist_str} | {inactive_str} | "
            f"City match: {'YES' if s['city_match'] else 'NO'} | "
            f"Quality: {s['quality_score']}/100 | "
            f"Blockers: [{blockers_str}]"
        )
    seller_text = "\n".join(seller_lines)

    # ── Gateway Flash Lite: per-seller + combined reasoning ───────────────────
    result = llm.chat_json(
        system=(
            "You are a seller engagement analyst for IndiaMART B2B marketplace. "
            "You diagnose exactly why sellers in a pool did not respond to a BuyLead. "
            "Be specific — name sellers by rank and explain each blocker clearly."
        ),
        user=f"""BuyLead: "{offer_name}" (Category: {mcat_name})
Buyer city: {buyer_city or "unknown"}

POOL SUMMARY:
- Total sellers: {total}
- Has credits (can respond): {pool_metrics['with_credits']['label']}
- Buyer city match: {pool_metrics['city_match']['label']}
- BL purchase history this year: {pool_metrics['with_bl_history']['label']}
- Active last 30 days: {pool_metrics['active_last_30d']['label']}
- Alert rank breakdown: A={alert_breakdown['A']}, B={alert_breakdown['B']}, C={alert_breakdown['C']}, unknown={alert_breakdown['unknown']}
- Distance: avg={avg_dist} km, min={min_dist} km, max={max_dist} km
- Avg quality score: {avg_quality}/100

PER-SELLER SIGNALS:
{seller_text}

Note: No direct "seller responded" data available. Diagnose using proxy signals above.
Credits=NO is a hard blocker — seller physically cannot respond without credits.

Analyse:
1. Per-seller: for each seller, why did they likely not respond?
2. Combined: what is the primary failure mode of this pool overall?

Return JSON only:
{{
  "confidence": 0-100,
  "primary_failure_mode": "one clear sentence describing the dominant pool-level problem",
  "per_seller_reasoning": [
    {{"rank": 1, "company": "...", "likely_responded": false, "reason": "specific reason"}}
  ],
  "combined_reasoning": "overall pool diagnosis — what pattern explains non-response",
  "fix": "one actionable sentence for ops team"
}}""",
        model=settings.GEMINI_FLASH_LITE_MODEL,
    )

    return {
        "bucket": "SELLER_SIDE_FAILURE",
        # Pool-level metrics (rule-based, all with n/total/pct)
        "pool_metrics": pool_metrics,
        # Per-seller structured data
        "per_seller": per_seller,
        # LLM verdict
        "confidence":           int(result.get("confidence", 50)),
        "primary_failure_mode": result.get("primary_failure_mode", ""),
        "per_seller_reasoning": result.get("per_seller_reasoning", []),
        "combined_reasoning":   result.get("combined_reasoning", ""),
        "fix":                  result.get("fix", "Review seller pool quality for this category"),
    }
