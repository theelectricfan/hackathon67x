"""
Build the flat BL-context dict the orchestrator + skills consume,
sourced live from Redash via core.data_loader.

Public API: build_bl_context_from_redash(offer_id) -> dict
"""
import logging
import re
from urllib.parse import parse_qs, urlparse

from core.data_loader import load_for_offer

logger = logging.getLogger(__name__)

# Spec names that are SYSTEM metadata (not actual product specs).
_SYSTEM_SPEC_NAMES = {
    "probable order value",
    "probable requirement type",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _extract_mcat_from_url(url):
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


def _str_overlap(a, b) -> bool:
    if not a or not b:
        return False
    a_words = {w.strip().lower() for w in str(a).split(",") if w.strip()}
    return any(w in str(b).lower() for w in a_words)


def _in_csv(needle, csv_str) -> bool:
    if not csv_str or not needle:
        return False
    needle = str(needle).strip().lower()
    return any(needle == t.strip().lower() for t in str(csv_str).split(","))


def _safe_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


_ALERT_SCORE = {
    "AA": 100, "AB": 90, "AC": 80,
    "A":  85,
    "BA": 75, "BB": 65, "BC": 55,
    "B":  60,
    "CA": 45, "CB": 35, "CC": 25,
    "C":  35,
    "D":  20, "":   30,
}


def _seller_quality_score(s: dict) -> int:
    """Composite 0–100 quality score from alert rank + credits + activity + history."""
    score = 0
    rank = (str(s.get("eto_trd_alert_subrank") or s.get("eto_trd_alert_rank") or "")
            .strip().upper())
    score += _ALERT_SCORE.get(rank, 30) * 0.4   # 40% weight

    credits = _safe_float(s.get("available_credits"))
    score += (30 if credits and credits > 0 else 0)  # 30% weight

    bl_yr = _safe_int(s.get("total_bl_purchased_1yr")) or 0
    score += min(bl_yr / 50 * 20, 20)               # 20% weight (cap at 50 BLs)

    dist = _safe_float(s.get("eto_lead_supplier_dist"))
    if dist is not None:
        score += max(0, 10 * (1 - min(dist, 1000) / 1000))  # 10% weight, decays with distance
    return int(round(min(score, 100)))


# ── main ─────────────────────────────────────────────────────────────────────

def build_bl_context_from_redash(offer_id) -> dict:
    """Fetch everything for one BL and assemble the orchestrator-ready ctx dict."""
    data = load_for_offer(offer_id)
    bl_rows         = data["bl_data"]
    buyer_rows      = data["buyer_data"]
    mapping_rows    = data["seller_mapping"]
    catalog_rows    = data["mcat_catalog"]
    benchmark_rows  = data["sold_benchmark"]
    seller_details  = data["seller_details"]

    # ── 1. BL identity + filled specs (pivot bl_rows) ────────────────────────
    base = bl_rows[0]
    offer_id_str = str(_safe_int(base.get("offer_id")) or offer_id)
    mapped_mcat_id = _safe_int(base.get("mapped_mcat_id"))
    page_referrer = base.get("page_referrer") or ""

    specs_filled: dict[str, str] = {}
    probable_order_value = None
    probable_req_type = None

    for row in bl_rows:
        sname = (row.get("spec_name") or "").strip()
        svalue = (row.get("spec_option") or "").strip()
        if not sname or not svalue or svalue.lower() in ("nan", "none"):
            continue
        norm = sname.lower()
        if norm == "probable order value":
            probable_order_value = svalue
        elif norm == "probable requirement type":
            probable_req_type = svalue
        elif norm not in _SYSTEM_SPEC_NAMES:
            specs_filled[sname] = svalue

    # ── 2. Buyer ──────────────────────────────────────────────────────────────
    buyer = buyer_rows[0] if buyer_rows else {}

    # ── 3. MCAT spec catalog (group catalog_rows by spec_name) ───────────────
    mcat_spec_catalog: dict = {}
    for row in catalog_rows:
        sname = row.get("spec_name")
        if not sname:
            continue
        entry = mcat_spec_catalog.setdefault(sname, {
            "spec_id": _safe_int(row.get("spec_id")),
            "priority": _safe_int(row.get("spec_priority")) or 99,
            "options": [],
            "is_quantity_related": bool(row.get("is_quantity_related_spec")),
            "is_free_text": False,
        })
        opt = row.get("option_value")
        if opt and opt not in entry["options"]:
            entry["options"].append(opt)
        if row.get("option_schema_status") == "NO_OPTION_DEFINED_OR_FREE_TEXT_SPEC":
            entry["is_free_text"] = True
    priority_specs = [n for n, v in mcat_spec_catalog.items() if v["priority"] <= 2]

    # ── 4. 90-day sold-BL benchmark ──────────────────────────────────────────
    bm = benchmark_rows[0] if benchmark_rows else {}
    total_sold     = _safe_int(bm.get("total_sold_bls")) or 0
    sold_0         = _safe_int(bm.get("sold_bls_0_specs")) or 0
    sold_1         = _safe_int(bm.get("sold_bls_1_spec")) or 0
    sold_2         = _safe_int(bm.get("sold_bls_2_specs")) or 0
    sold_3plus     = _safe_int(bm.get("sold_bls_3plus_specs")) or 0
    sold_le_1 = sold_0 + sold_1
    sold_benchmark = {
        "total_sold_bls":     total_sold,
        "sold_bls_0_specs":   sold_0,
        "sold_bls_1_spec":    sold_1,
        "sold_bls_2_specs":   sold_2,
        "sold_bls_3plus":     sold_3plus,
        "pct_sold_with_le_1_spec": round(sold_le_1 / total_sold * 100, 1) if total_sold else None,
        "pct_sold_with_3plus":     round(sold_3plus / total_sold * 100, 1) if total_sold else None,
    }

    # ── 5. Seller pool: merge mapping + detailed warehouse data by supplier_id ──
    # Keep the RAW field names (eto_trd_alert_rank, a_rank_preferred_cities, etc.)
    # so the existing skill_seller code works unmodified.
    detail_by_supplier = {
        _safe_int(r.get("supplier_gl_id")): r
        for r in seller_details if r.get("supplier_gl_id") is not None
    }
    seller_detailed_pool = []
    for m in mapping_rows:
        sid = _safe_int(m.get("seller_id"))
        d = detail_by_supplier.get(sid) or {}
        merged = {
            "supplier_gl_id":           sid,
            "selected_seller_rank":     _safe_int(m.get("selected_seller_rank")),
            "selection_rejection_type": m.get("selection_rejection_type"),
            "eto_lead_search_keyword":  m.get("search_kw"),
            "product_accuracy_score":   m.get("product_accuracy_score"),
            "eto_lead_prime_mcat":      _safe_int(m.get("prime_mcat_id")),
            "glusr_usr_companyname":    d.get("glusr_usr_companyname"),
            "custtype_name":            d.get("custtype_name"),
            "available_credits":        d.get("available_credits"),
            "glusr_usr_membersince":    d.get("glusr_usr_membersince"),
            "glusr_usr_lastlogin":      d.get("glusr_usr_lastlogin"),
            "eto_trd_alert_rank":       d.get("eto_trd_alert_rank"),
            "eto_trd_alert_subrank":    d.get("eto_trd_alert_subrank"),
            "glusr_usr_deduced_loc_pref1": _safe_int(d.get("glusr_usr_deduced_loc_pref1")),
            "a_rank_preferred_cities":  d.get("a_rank_preferred_cities"),
            "b_rank_consuming_cities":  d.get("b_rank_consuming_cities"),
            "eto_lead_supplier_dist":   d.get("eto_lead_supplier_dist"),
            "eto_lead_total_supp_count": _safe_int(d.get("eto_lead_total_supp_count")),
            "total_bl_purchased_1yr":   _safe_int(d.get("total_bl_purchased_1yr")) or 0,
            "eto_lead_supp_mapp_result_info": d.get("eto_lead_supp_mapp_result_info"),
        }
        # Rule-based quality score 0-100 (used by skill_seller)
        merged["_quality_score"] = _seller_quality_score(merged)
        seller_detailed_pool.append(merged)

    # ── 6. Computed signals ──────────────────────────────────────────────────
    leads_cnt = _safe_int(buyer.get("eto_ofr_buyer_leads_cnt"))
    is_first_time_buyer = bool(leads_cnt is not None and leads_cnt <= 1)

    glb_city = buyer.get("eto_ofr_sender_glb_city_id")
    ip_city  = buyer.get("eto_ofr_sender_ip_city_id")
    city_mismatch = bool(glb_city is not None and ip_city is not None
                         and str(glb_city) != str(ip_city))

    sell_mcats  = buyer.get("eto_ofr_buyer_sell_mcats") or ""
    prime_mcats = buyer.get("eto_ofr_buyer_prime_mcats") or ""
    mapped_mcat_name = str(base.get("mapped_mcat_name") or "")

    sells_competing      = _str_overlap(sell_mcats, prime_mcats) or _str_overlap(sell_mcats, mapped_mcat_name)
    buyer_in_prime_mcat  = _in_csv(mapped_mcat_name, prime_mcats)
    buyer_in_past_search = _str_overlap(mapped_mcat_name, buyer.get("eto_ofr_buyer_past_search_mcat") or "")

    buyer_city = str(buyer.get("eto_ofr_s_city") or "").lower()
    sellers_with_credits = sum(
        1 for s in seller_detailed_pool
        if s["available_credits"] and str(s["available_credits"]).strip() not in ("", "0", "0.0", "None", "nan")
    )
    sellers_city_match = sum(
        1 for s in seller_detailed_pool
        if buyer_city and (
            buyer_city in str(s.get("a_rank_preferred_cities") or "").lower()
            or buyer_city in str(s.get("b_rank_consuming_cities") or "").lower()
        )
    )
    sellers_with_history = sum(1 for s in seller_detailed_pool if s["total_bl_purchased_1yr"] > 0)

    seller_all_credits_blank = (len(seller_detailed_pool) > 0
                                and sellers_with_credits == 0)

    # Retail flag from eto_enq_typ — 1=Retail, 2=B2B, 3=Auto-Retail
    retail_flag_raw = _safe_int(base.get("retail_flag"))

    # ── 7. Assemble ──────────────────────────────────────────────────────────
    ctx = {
        # BL identity
        "offer_id":          offer_id_str,
        "offer_name":        str(base.get("offer_name") or ""),
        "mapped_mcat_id":    mapped_mcat_id,
        "mapped_mcat_name":  mapped_mcat_name,
        "page_referrer":     page_referrer,
        "url_mcat_id":       _extract_mcat_from_url(page_referrer),
        "approval_status":   str(base.get("approval_status") or ""),
        "approval_date":     str(base.get("approval_date") or ""),
        "mod_id":            str(base.get("mod_id") or ""),
        "retail_flag":       retail_flag_raw,

        # Specs
        "specs_filled":         specs_filled,
        "specs_fill_count":     len(specs_filled),
        "probable_order_value": probable_order_value,
        "probable_req_type":    probable_req_type,
        "aov_blank":            not probable_order_value,

        # MCAT catalog
        "mcat_spec_catalog": mcat_spec_catalog,
        "priority_specs":    priority_specs,

        # 90-day sold benchmark
        "sold_benchmark":           sold_benchmark,
        "thin_sold_bl_count":       sold_benchmark["sold_bls_0_specs"] + sold_benchmark["sold_bls_1_spec"],
        "thin_sold_bl_channels":    {},  # not available in current query — placeholder for UI

        # Buyer
        "buyer":                buyer,
        "is_first_time_buyer":  is_first_time_buyer,
        "city_mismatch":        city_mismatch,
        "sells_competing":      sells_competing,
        "buyer_in_prime_mcat":  buyer_in_prime_mcat,
        "buyer_in_past_search": buyer_in_past_search,

        # Seller pool (single unified list)
        "seller_pool":              seller_detailed_pool,
        "seller_detailed_pool":     seller_detailed_pool,
        "seller_pool_has_credits":  sellers_with_credits > 0,
        "seller_all_credits_blank": seller_all_credits_blank,
        "seller_all_fcp_zero":      True,  # fcp not in current query — UI compat
        "sellers_with_credits":     sellers_with_credits,
        "sellers_city_match":       sellers_city_match,
        "sellers_with_history":     sellers_with_history,

        # Loader timing — handy for UI
        "_timings": data["timings"],
    }
    return ctx
