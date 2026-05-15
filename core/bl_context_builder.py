"""
Builds a single flat BL context dict from the 4 CSV files.

bl_data is PIVOTED (many rows per BL, one per spec).
We group by offer_id, then join buyer, seller, and spec catalog.
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
    # Fallback: regex scan
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


# ── Main builder ─────────────────────────────────────────────────────────────

def build_bl_context(
    bl_csv: str,
    buyer_csv: str,
    seller_csv: str,
    specs_csv: str,
) -> dict:
    """
    Returns a single flat dict representing one BL's full context.
    Assumes each CSV contains data for exactly one BL (or the first offer_id found).
    """

    # ── 1. Read & pivot bl_data ───────────────────────────────────────────────
    bl_df = pd.read_csv(bl_csv)
    bl_df.columns = bl_df.columns.str.strip()

    offer_id = bl_df["offer_id"].dropna().iloc[0]
    bl_rows = bl_df[bl_df["offer_id"] == offer_id]

    # BL-level fields (same across all spec rows)
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
    # Clean NaN
    buyer = {k: (None if pd.isna(v) else v) for k, v in buyer.items()}

    # ── 4. Read seller_data ───────────────────────────────────────────────────
    seller_df = pd.read_csv(seller_csv)
    seller_df.columns = seller_df.columns.str.strip()
    seller_pool = []
    for _, row in seller_df.iterrows():
        d = row.to_dict()
        seller_pool.append({k: (None if pd.isna(v) else v) for k, v in d.items()})

    # ── 5. Build MCAT spec catalog from buyer_specs_data ─────────────────────
    specs_df = pd.read_csv(specs_csv)
    specs_df.columns = specs_df.columns.str.strip()
    mcat_rows = specs_df[specs_df["mcat_id"] == mapped_mcat_id]

    mcat_spec_catalog = {}
    priority_specs = []  # priority 1 or 2

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

    # ── 6. Computed signals ───────────────────────────────────────────────────
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

    # ── 7. Assemble context ───────────────────────────────────────────────────
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
        # Seller pool
        "seller_pool": seller_pool,
        # Computed signals
        "is_first_time_buyer": is_first_time_buyer,
        "city_mismatch": city_mismatch,
        "sells_competing": sells_competing,
        "seller_all_fcp_zero": seller_all_fcp_zero,
        "seller_all_credits_blank": seller_all_credits_blank,
    }

    return ctx
