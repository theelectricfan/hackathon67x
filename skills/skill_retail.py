"""
Bucket 8 — Retail Query.

Detects when a BuyLead is fundamentally a B2C/retail enquiry rather
than a B2B requirement.  Different from B7 (Quantity Mismatch), which
looks at order-size mismatch — B8 asks "is this entire BL the wrong
*kind* of enquiry for this marketplace?"

Hard signals:
  - eto_enq_typ in (1=Retail, 3=Auto-Retail)
  - probable_req_type == "Personal Use"
  - GST unverified + tiny quantity

Soft signals (LLM):
  - offer_name implies personal-use product (e.g. "for my kitchen")
  - specs filled point to consumer-grade SKU
"""
from llm.client import llm
from langfuse_client import observe
from config.settings import settings


_RETAIL_FLAG_LABEL = {1: "RETAIL", 2: "B2B", 3: "AUTO-RETAIL"}


@observe(name="skill_retail")
def run_skill_retail(ctx: dict) -> dict:
    offer_name    = ctx["offer_name"]
    mcat_name     = ctx.get("mapped_mcat_name", "")
    specs_filled  = ctx.get("specs_filled", {})
    aov           = ctx.get("probable_order_value")
    req_type      = ctx.get("probable_req_type")
    retail_flag   = ctx.get("retail_flag")
    gst_verified  = bool(ctx.get("buyer", {}).get("eto_ofr_buyer_is_gst_verf"))
    mob_verified  = bool(ctx.get("buyer", {}).get("eto_ofr_buyer_is_mob_verf"))
    is_first_time = ctx.get("is_first_time_buyer", False)
    was_purchased      = ctx.get("was_purchased", False)
    has_business_buyer = ctx.get("has_business_buyer", False)
    purchasers         = ctx.get("purchasing_sellers") or []

    # ── Rule-based signals ───────────────────────────────────────────────────
    enq_typ_label = _RETAIL_FLAG_LABEL.get(retail_flag, "UNKNOWN") if retail_flag is not None else "MISSING"
    rule_retail_flag = retail_flag in (1, 3)
    rule_req_type_retail = str(req_type or "").strip().lower() == "personal use"
    rule_unverified_personal = (not gst_verified) and is_first_time

    # Fast path: missing all signals AND offer name short → just run LLM
    # (we always run LLM since retail-vs-B2B is nuanced)

    result = llm.chat_json(
        system=(
            "You are a marketplace integrity analyst for IndiaMART (India's largest B2B platform). "
            "Decide whether a BuyLead is RETAIL/B2C (1 piece / personal use / consumer scale) or "
            "B2B (bulk / wholesale / business scale). Default assumption is B2B — only flag retail "
            "with HARD evidence. AOV in lakhs/crores, quantity in Tons/Truckload/Quintal/Drum, "
            "GST-verified buyer, or 'Business Use' req-type all indicate B2B and should suppress "
            "retail confidence dramatically."
        ),
        user=f"""BuyLead: "{offer_name}" (Category: {mcat_name})

── HARD DB SIGNALS ──
- Enquiry-type code (eto_enq_typ): {retail_flag} → {enq_typ_label}
- Probable requirement type:       {req_type or "not specified"}
- Probable Order Value (AOV):      {aov or "not specified"}

── BUYER SIGNALS ──
- GST verified:     {gst_verified}    ← genuine B2B businesses are GST-registered
- Mobile verified:  {mob_verified}
- First-time buyer: {is_first_time}

── PURCHASE OUTCOME (hardest evidence) ──
- BL was purchased:               {was_purchased}    ← TRUE = a real seller paid for this lead
- Purchased by a paid B2B seller: {has_business_buyer}    ← TRUE = professional B2B seller, NOT retail
- Purchasing-seller custtypes:    {[s.get('custtype_name') for s in purchasers] or 'n/a'}

── BUYER-FILLED SPECS ──
{specs_filled if specs_filled else "(no specs filled)"}

Rule-based pre-checks:
- Enquiry type code explicitly retail: {rule_retail_flag}
- Req-type = "Personal Use":           {rule_req_type_retail}
- Unverified first-timer:              {rule_unverified_personal}

Calibration guidance — anchor your confidence to evidence, not vibes:
- Purchased by a B2B custtype seller (CATALOG/TSCATALOG/etc.)                                          →  retail confidence  0-10  (proves B2B)
- BL purchased but no business-tier buyer info                                                          →  retail confidence  5-25
- ALL three hard pre-checks FALSE and AOV ≥ Rs. 1 Lakh and/or quantity in Ton/Truckload/Quintal/Drum  →  retail confidence  0-15
- One soft signal (e.g. first-time + small AOV, no GST) but nothing decisive                           →  retail confidence 30-45
- "Personal Use" req-type OR enq_typ in (1,3) explicit                                                  →  retail confidence 70-90
- Multiple hard signals + tiny quantity + no GST                                                       →  retail confidence 90-100

Return JSON only:
{{
  "is_retail_query": true or false,
  "confidence": 0-100,
  "reasoning": "explicit reasoning naming the SPECIFIC signals — quantity, AOV, GST, req-type — that drove the score",
  "fix": "one actionable sentence — e.g. filter from B2B pool, route to consumer marketplace, etc."
}}""",
        model=settings.GEMINI_FLASH_LITE_MODEL,
    )

    confidence = int(result.get("confidence", 0))
    # Hard-floor confidence if the retail_flag is explicit (1 = Retail)
    if rule_retail_flag and confidence < 70:
        confidence = max(confidence, 70)

    return {
        "bucket": "RETAIL_QUERY",
        # Rule-based signals
        "retail_flag":           retail_flag,
        "enq_typ_label":         enq_typ_label,
        "rule_retail_flag":      rule_retail_flag,
        "rule_req_type_retail":  rule_req_type_retail,
        "rule_unverified_personal": rule_unverified_personal,
        # LLM verdict
        "is_retail_query": bool(result.get("is_retail_query", False)),
        "confidence":      confidence,
        "reasoning":       result.get("reasoning", ""),
        "fix":             result.get("fix", "Confirm if this BL should be routed to a consumer marketplace instead."),
    }
