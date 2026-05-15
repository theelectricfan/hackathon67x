"""
Builds a single flat BL context dict from up to 6 CSV files.

bl_data is PIVOTED (many rows per BL, one per spec).
We group by offer_id, then join buyer, seller, and spec catalog.
DS5 (sold_bl_csv) and DS6 (seller_detailed_csv) are optional enrichment sources.
"""
import re
import pandas as pd
from urllib.parse import urlparse, parse_qs


# ── Helpers ──────────────────────────────────────────────────────────────────

def _extract_mcat_from_url(url: str):
    """Pull mcatid or mcat_id from the page_referrer URL query string."""
    if not url or not isinstance(url, str):
        return None
    try:
        qs = parse_qs(urlparse(url).query)
        for key in ("mcatid", "mcat_id", "mcat"):
            if key in qs:
                return int(qs[key][0])
    except Exception:
        pass
    m = re.search(r"mcatid?=(\d+)", url)
    return int(m.group(1)) if m else None


def _str_overlap(a: str, b: str) -> bool:
    """Check if any word in string a appears in string b (case-insensitive)."""
    if not a or not b:
        return False
    a_words = {w.strip().lower() for w in str(a).split(",") if w.strip()}
    b_lower = str(b).lower()
    return any(w in b_lower for w in a_words)


def _safe_int(val):
    try:
        return int(float(val))
    except Exception:
        return None


def _safe_float(val):
    try:
        return float(val)
    except Exception:
        return None


def _clean_dict(d: dict) -> dict:
    """Replace NaN values with None in a dict."""
    return {k: (None if pd.isna(v) else v) for k, v in d.items()}


# ── DS6 helpers ──────────────────────────────────────────────────────────────

_ALERT_RANK_SCORE = {"A": 90, "B": 60, "C": 30}
_ALERT_SUBRANK_BONUS = {"AA": 5, "AB": 3, "BA": 2, "BB": 1, "CA": 0, "CB": -5}


def _seller_quality_score_from_ds6(row: dict) -> int:
    """
    Rule-based seller quality score (0-100) from DS6 signals.
    Higher = better seller engagement quality.
    """
    score = 50  # baseline

    # Alert rank (primary quality signal)
    alert_rank = str(row.get("eto_trd_alert_rank") or "").strip().upper()
    score += _ALERT_RANK_SCORE.get(alert_rank, 0) - 50

    # Subrank adjustment
    alert_subrank = str(row.get("eto_trd_alert_subrank") or "").strip().upper()
    score += _ALERT_SUBRANK_BONUS.get(alert_subrank, 0)

    # Credits: blank or zero = can't respond
    credits = row.get("available_credits")
    if credits is None or str(credits).strip() in ("", "nan", "None"):
        score -= 20
    else:
        try:
            c = float(credits)
            if c <= 0:
                score -= 20
            elif c >= 100:
                score += 5
        except Exception:
            pass

    # BL purchase history: more purchased = more engaged
    bl_purchased = _safe_int(row.get("total_bl_purchased_1yr")) or 0
    if bl_purchased == 0:
        score -= 10
    elif bl_purchased >= 10:
        score += 10
    elif bl_purchased >= 5:
        score += 5

    # Distance: closer = more relevant
    dist = _safe_float(row.get("eto_lead_supplier_dist"))
    if dist is not None:
        if dist == 0:
            score += 10
        elif dist > 500:
            score -= 10

    # Selection vs rejection
    sel_type = str(row.get("selection_rejection_type") or "").strip().upper()
    if sel_type == "A":
        score += 5  # selected / accepted

    return max(0, min(100, score))


# ── Main builder ─────────────────────────────────────────────────────────────

def build_bl_context(
    bl_csv: str,
    buyer_csv: str,
    seller_csv: str,
    specs_csv: str,
    sold_bl_csv: str = None,
    seller_detailed_csv: str = None,
) -> dict:
    """
    Returns a single flat dict representing one BL's full context.
    Assumes each CSV contains data for exactly one BL (or the first offer_id found).
    DS5 (sold_bl_csv) and DS6 (seller_detailed_csv) are optional enrichment files.
    """

    # ── 1. Read & pivot bl_data ───────────────────────────────────────────────
    bl_df = pd.read_csv(bl_csv)
    bl_df.columns = bl_df.columns.str.strip()

    offer_id = bl_df["offer_id"].dropna().iloc[0]
    bl_rows = bl_df[bl_df["offer_id"] == offer_id]

    bl_base = bl_rows.iloc[0]
    mapped_mcat_id = _safe_int(bl_base.get("mapped_mcat_id"))

    # Pivot specs: spec_id == -1 are system metadata rows
    specs_filled = {}
    probable_order_value = None
    probable_req_type = None

    for _, row in bl_rows.iterrows():
        spec_id = _safe_int(row.get("spec_id"))
        spec_name = str(row.get("spec_name", "")).strip()
        spec_option = str(row.get("spec_option", "")).strip()

        if spec_id == -1:
            if "Probable Order Value" in spec_name:
                probable_order_value = spec_option or None
            elif "Probable Requirement Type" in spec_name:
                probable_req_type = spec_option or None
        elif spec_name and spec_option and spec_option.lower() not in ("nan", "none", ""):
            specs_filled[spec_name] = spec_option

    # ── 2. Extract URL MCAT ───────────────────────────────────────────────────
    page_referrer = str(bl_base.get("page_referrer", ""))
    url_mcat_id = _extract_mcat_from_url(page_referrer)

    # ── 3. Read buyer_data ────────────────────────────────────────────────────
    buyer_df = pd.read_csv(buyer_csv)
    buyer_df.columns = buyer_df.columns.str.strip()
    buyer_row = buyer_df[buyer_df["eto_ofr_display_id"] == offer_id]
    buyer = buyer_row.iloc[0].to_dict() if not buyer_row.empty else {}
    buyer = _clean_dict(buyer)

    # ── 4. Read seller_data (basic pool) ─────────────────────────────────────
    seller_df = pd.read_csv(seller_csv)
    seller_df.columns = seller_df.columns.str.strip()
    seller_pool = []
    for _, row in seller_df.iterrows():
        d = row.to_dict()
        seller_pool.append(_clean_dict(d))

    # ── 5. Build MCAT spec catalog ────────────────────────────────────────────
    specs_df = pd.read_csv(specs_csv)
    specs_df.columns = specs_df.columns.str.strip()
    mcat_rows = specs_df[specs_df["mcat_id"] == mapped_mcat_id]

    mcat_spec_catalog = {}
    priority_specs = []

    for spec_id, grp in mcat_rows.groupby("spec_id"):
        first = grp.iloc[0]
        spec_name = str(first.get("spec_name", ""))
        priority = _safe_int(first.get("spec_priority")) or 99
        options = [
            str(r.get("option_value", ""))
            for _, r in grp.iterrows()
            if pd.notna(r.get("option_value"))
        ]
        mcat_spec_catalog[spec_name] = {
            "spec_id": int(spec_id),
            "priority": priority,
            "options": options,
            "is_quantity_related": bool(first.get("is_quantity_related_spec", 0)),
        }
        if priority <= 2:
            priority_specs.append(spec_name)

    # ── 6. DS5: Sold thin-content BL benchmark (optional) ────────────────────
    # DS5 contains BLs that had 0, 1, or 2 specs filled but WERE sold.
    # thin_sold_bl_count = how many such BLs exist for this MCAT.
    # High count → thin BLs regularly sell here → content less critical.
    # Zero count → even sparse BLs don't convert → content quality matters a lot.
    thin_sold_bl_count = None
    thin_sold_bl_channels = {}

    if sold_bl_csv:
        try:
            sold_df = pd.read_csv(sold_bl_csv)
            sold_df.columns = sold_df.columns.str.strip()
            # Filter to same MCAT
            mcat_thin_sold = sold_df[sold_df["fk_glcat_mcat_id"] == mapped_mcat_id]
            thin_sold_bl_count = len(mcat_thin_sold)
            # Channel distribution of thin sold BLs in this MCAT
            if "fk_gl_module_id" in mcat_thin_sold.columns and not mcat_thin_sold.empty:
                ch_counts = mcat_thin_sold["fk_gl_module_id"].value_counts().to_dict()
                total = sum(ch_counts.values()) or 1
                thin_sold_bl_channels = {
                    ch: round(cnt / total * 100, 1)
                    for ch, cnt in ch_counts.items()
                }
        except Exception:
            pass

    # ── 7. DS6: Seller detailed data (optional) ───────────────────────────────
    seller_detailed_pool = []
    seller_pool_has_credits = False
    seller_pool_avg_alert_score = None
    seller_pool_avg_quality = None
    seller_pool_avg_bl_purchased = None

    if seller_detailed_csv:
        try:
            sd_df = pd.read_csv(seller_detailed_csv)
            sd_df.columns = sd_df.columns.str.strip()
            # Filter to this BL's offer_id
            offer_id_float = float(offer_id) if str(offer_id).replace(".", "").isdigit() else offer_id
            sd_rows = sd_df[
                (sd_df["offer_id"] == offer_id_float) |
                (sd_df["offer_id"].astype(str) == str(offer_id))
            ]

            for _, row in sd_rows.iterrows():
                d = _clean_dict(row.to_dict())
                d["_quality_score"] = _seller_quality_score_from_ds6(d)
                seller_detailed_pool.append(d)

            if seller_detailed_pool:
                # Credits: at least one seller has credits
                seller_pool_has_credits = any(
                    _safe_float(s.get("available_credits") or 0) and
                    _safe_float(s.get("available_credits") or 0) > 0
                    for s in seller_detailed_pool
                )

                # Alert rank → numeric score
                alert_scores = []
                for s in seller_detailed_pool:
                    rank = str(s.get("eto_trd_alert_rank") or "").strip().upper()
                    if rank in _ALERT_RANK_SCORE:
                        alert_scores.append(_ALERT_RANK_SCORE[rank])
                if alert_scores:
                    seller_pool_avg_alert_score = round(sum(alert_scores) / len(alert_scores), 1)

                # Average quality score
                quality_scores = [s["_quality_score"] for s in seller_detailed_pool]
                seller_pool_avg_quality = round(sum(quality_scores) / len(quality_scores), 1)

                # Average BL purchased
                bl_vals = [
                    _safe_int(s.get("total_bl_purchased_1yr")) or 0
                    for s in seller_detailed_pool
                ]
                seller_pool_avg_bl_purchased = round(sum(bl_vals) / len(bl_vals), 1)

        except Exception:
            pass

    # ── 8. Computed signals ───────────────────────────────────────────────────
    leads_cnt = buyer.get("eto_ofr_buyer_leads_cnt")
    is_first_time_buyer = (leads_cnt is not None and int(float(leads_cnt)) <= 1)

    glb_city = buyer.get("eto_ofr_sender_glb_city_id")
    ip_city = buyer.get("eto_ofr_sender_ip_city_id")
    city_mismatch = (
        glb_city is not None and ip_city is not None and str(glb_city) != str(ip_city)
    )

    sell_mcats = str(buyer.get("eto_ofr_buyer_sell_mcats") or "")
    prime_mcats = str(buyer.get("eto_ofr_buyer_prime_mcats") or "")
    sells_competing = _str_overlap(sell_mcats, prime_mcats) or _str_overlap(
        sell_mcats, str(bl_base.get("mapped_mcat_name", ""))
    )

    seller_all_fcp_zero = all(
        str(s.get("fcp_flag", "0")) in ("0", "0.0") for s in seller_pool
    )
    seller_all_credits_blank = all(
        not s.get("glusr_eto_cust_credits_av") for s in seller_pool
    )

    specs_fill_count = len(specs_filled)
    aov_blank = not probable_order_value

    # ── 9. Assemble context ───────────────────────────────────────────────────
    ctx = {
        # BL identity
        "offer_id": str(offer_id),
        "offer_name": str(bl_base.get("offer_name", "")),
        "glusr_id": str(bl_base.get("glusr_id", "")),
        "mod_id": str(bl_base.get("mod_id", "")),
        "page_referrer": page_referrer,
        "mapped_mcat_id": mapped_mcat_id,
        "mapped_mcat_name": str(bl_base.get("mapped_mcat_name", "")),
        "url_mcat_id": url_mcat_id,
        "approval_status": str(bl_base.get("approval_status", "")),
        "approval_date": str(bl_base.get("approval_date", "")),
        # Specs
        "specs_filled": specs_filled,
        "specs_fill_count": specs_fill_count,
        "probable_order_value": probable_order_value,
        "probable_req_type": probable_req_type,
        "aov_blank": aov_blank,
        # MCAT catalog
        "mcat_spec_catalog": mcat_spec_catalog,
        "priority_specs": priority_specs,
        # Buyer
        "buyer": buyer,
        # Seller pool (basic)
        "seller_pool": seller_pool,
        # DS5: Thin-content sold BL benchmark
        "thin_sold_bl_count": thin_sold_bl_count,
        "thin_sold_bl_channels": thin_sold_bl_channels,
        # DS6: Seller detailed pool
        "seller_detailed_pool": seller_detailed_pool,
        "seller_pool_has_credits": seller_pool_has_credits,
        "seller_pool_avg_alert_score": seller_pool_avg_alert_score,
        "seller_pool_avg_quality": seller_pool_avg_quality,
        "seller_pool_avg_bl_purchased": seller_pool_avg_bl_purchased,
        # Computed signals
        "is_first_time_buyer": is_first_time_buyer,
        "city_mismatch": city_mismatch,
        "sells_competing": sells_competing,
        "seller_all_fcp_zero": seller_all_fcp_zero,
        "seller_all_credits_blank": seller_all_credits_blank,
    }

    return ctx
