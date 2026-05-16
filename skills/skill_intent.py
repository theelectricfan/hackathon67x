"""
Bucket 4 — Low Buyer Intent.

Pre-computes structured buyer signals, then single Gateway Flash Lite call
to rate intent confidence directly.
"""
from llm.client import llm
from config.settings import settings
from langfuse_client import observe


_CHANNEL_LABELS = {
    "FENQ":    "Form Enquiry (web form)",
    "LEAP":    "LEAP (assisted posting)",
    "IMOB":    "IndiaMART Mobile App",
    "EXPORTM": "Export Marketplace",
}


def _lead_history_label(leads_cnt) -> str:
    try:
        n = int(float(leads_cnt))
        if n <= 1:
            return f"first-time ({n} lead ever)"
        if n <= 10:
            return f"occasional ({n} leads total)"
        return f"frequent ({n} leads total)"
    except Exception:
        return "unknown"


@observe(name="skill_intent")
def run_skill_intent(ctx: dict) -> dict:
    buyer      = ctx.get("buyer", {})
    offer_name = ctx["offer_name"]
    mcat_name  = ctx.get("mapped_mcat_name", "")

    # ── Pre-compute structured signals ───────────────────────────────────────
    leads_cnt          = buyer.get("eto_ofr_buyer_leads_cnt")
    lead_history       = _lead_history_label(leads_cnt)
    is_first_time      = ctx["is_first_time_buyer"]

    gst_verified       = bool(buyer.get("eto_ofr_buyer_is_gst_verf"))
    mobile_verified    = bool(buyer.get("eto_ofr_buyer_is_mob_verf"))
    email_verified     = bool(buyer.get("eto_ofr_email_verified"))
    verification_score = sum([gst_verified, mobile_verified, email_verified])

    sells_competing      = ctx["sells_competing"]
    buyer_in_prime_mcat  = ctx.get("buyer_in_prime_mcat", False)
    buyer_in_past_search = ctx.get("buyer_in_past_search", False)
    sell_mcats           = str(buyer.get("eto_ofr_buyer_sell_mcats") or "").strip()
    prime_mcats          = str(buyer.get("eto_ofr_buyer_prime_mcats") or "").strip()

    channel_raw        = str(ctx.get("mod_id", "")).strip().upper()
    channel_label      = _CHANNEL_LABELS.get(channel_raw, channel_raw or "Unknown")

    company            = buyer.get("eto_ofr_companyname") or buyer.get("eto_ofr_s_organization") or "—"
    designation        = buyer.get("eto_ofr_s_designation") or "—"
    state              = buyer.get("eto_ofr_s_state") or "—"
    past_search        = buyer.get("eto_ofr_buyer_past_search_mcat") or "—"

    # ── Gateway Flash Lite: intent analysis ──────────────────────────────────
    result = llm.chat_json(
        system=(
            "You are a buyer intent analyst for IndiaMART, India's largest B2B marketplace. "
            "Your job is to assess whether a buyer posting a BuyLead is a genuine purchaser "
            "or a low-intent / suspicious lead. Be precise and critical."
        ),
        user=f"""A buyer posted a BuyLead on IndiaMART.

BUYLEAD: "{offer_name}" (Category: {mcat_name})

── VERIFICATION SIGNALS ({verification_score}/3 verified) ──
- GST verified:    {gst_verified}
- Mobile verified: {mobile_verified}
- Email verified:  {email_verified}

── BEHAVIORAL SIGNALS ──
- Lead history:       {lead_history}
- First-time buyer:   {is_first_time}
- Past search MCAT:   {past_search}
- Channel:            {channel_label}

── CATEGORY FIT (strong intent signals — heavily weight these) ──
- Buying category in buyer's PRIME MCats: {buyer_in_prime_mcat}    ← TRUE = strong genuine signal (the buyer's stated line of business)
- Buying category in buyer's PAST SEARCH: {buyer_in_past_search}   ← TRUE = prior research = real demand

Calibration: anchor `confidence` (= how sure this is LOW intent) as follows:
- 3/3 verified + buyer_in_prime_mcat + not sells_competing               →  confidence  5-20  (clearly genuine)
- 2-3/3 verified + buyer_in_prime_mcat, but first-time + no past search   →  confidence 20-40  (probably genuine)
- Unverified or competing-seller, mixed signals                           →  confidence 50-70
- Multiple red flags (no verification, sells competing, no profile, fake) →  confidence 80-100

── COMPETITIVE SIGNALS ──
- Buyer also sells competing category: {sells_competing}
- What buyer sells (MCats):            {sell_mcats or "nothing listed"}
- Buyer's primary interest MCats:      {prime_mcats or "none listed"}
- What they're buying now:             {mcat_name}

── BUYER PROFILE ──
- Company:     {company}
- Designation: {designation}
- State:       {state}

Assess the genuineness of this buyer's purchase intent.
Consider: Is this a real purchaser, a competitor gathering price intelligence,
a fake/accidental lead, or a market researcher?

Return JSON only:
{{
  "intent_score": 0-100,
  "confidence": 0-100,
  "is_genuine": true or false,
  "reasoning": "explain each signal group — verification, behavior, competitive — and what they indicate",
  "fix": "one actionable sentence for the ops team or the buyer"
}}""",
        model=settings.GEMINI_FLASH_LITE_MODEL,
    )

    return {
        "bucket": "LOW_BUYER_INTENT",
        # Pre-computed signals (shown in UI)
        "verification_score":  verification_score,
        "gst_verified":        gst_verified,
        "mobile_verified":     mobile_verified,
        "email_verified":      email_verified,
        "is_first_time_buyer": is_first_time,
        "lead_history":        lead_history,
        "sells_competing":     sells_competing,
        "buyer_in_prime_mcat": buyer_in_prime_mcat,
        "buyer_in_past_search": buyer_in_past_search,
        "sell_mcats":          sell_mcats,
        "channel":             channel_label,
        # LLM result
        "intent_score": int(result.get("intent_score", 50)),
        "confidence":   int(result.get("confidence", 50)),
        "is_genuine":   result.get("is_genuine", True),
        "reasoning":    result.get("reasoning", ""),
        "fix":          result.get("fix", "Verify buyer identity before routing to sellers"),
    }
