"""Bucket 4 — Low Buyer Intent. Gateway LLM only (all buyer signals)."""
from llm.client import llm
from langfuse_client import observe


@observe(name="skill_intent")
def run_skill_intent(ctx: dict) -> dict:
    buyer = ctx.get("buyer", {})

    signals = f"""- First time buyer: {ctx['is_first_time_buyer']}
- Total leads ever posted: {buyer.get('eto_ofr_buyer_leads_cnt', 'unknown')}
- Buyer also sells: {buyer.get('eto_ofr_buyer_sell_mcats', 'none')}
- Buyer primary interest MCats: {buyer.get('eto_ofr_buyer_prime_mcats', 'none')}
- Buyer selling competing category: {ctx['sells_competing']}
- Past search MCAT: {buyer.get('eto_ofr_buyer_past_search_mcat', 'none')}
- GST verified: {buyer.get('eto_ofr_buyer_is_gst_verf', 'unknown')}
- Mobile verified: {buyer.get('eto_ofr_buyer_is_mob_verf', 'unknown')}
- Email verified: {buyer.get('eto_ofr_email_verified', 'unknown')}
- Account city == IP city (consistent): {not ctx['city_mismatch']}
- Company name: {buyer.get('eto_ofr_companyname', 'unknown')}
- Designation: {buyer.get('eto_ofr_s_designation', 'unknown')}
- State: {buyer.get('eto_ofr_s_state', 'unknown')}"""

    result = llm.chat_json(
        system=(
            "You are a buyer intent analyst for IndiaMART, India's largest B2B marketplace. "
            "You assess whether a buyer posting a BuyLead is a genuine purchaser."
        ),
        user=f"""A buyer posted a BuyLead on IndiaMART for: "{ctx['offer_name']}"

Buyer profile signals:
{signals}

Based on these signals, rate the GENUINENESS of this buyer's purchase intent.
Consider: Is this buyer a real purchaser, or possibly a competitor gathering market intelligence,
a fake lead, or an accidental post?

Return JSON only:
{{
  "intent_score": 0-100,
  "confidence": 0-100,
  "is_genuine": true or false,
  "reasoning": "explain the key signals clearly",
  "fix": "one action sentence"
}}""",
    )

    intent_score = int(result.get("intent_score", 50))
    # confidence of LOW_BUYER_INTENT bucket = inverse of intent score
    bucket_confidence = max(0, 100 - intent_score)

    return {
        "bucket": "LOW_BUYER_INTENT",
        "intent_score": intent_score,
        "confidence": bucket_confidence,
        "is_genuine": result.get("is_genuine", True),
        "reasoning": result.get("reasoning", ""),
        "fix": result.get("fix", "Verify buyer identity before routing to sellers"),
    }
