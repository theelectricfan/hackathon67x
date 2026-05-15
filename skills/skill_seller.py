"""Bucket 5 — Seller Side Failure. Gateway LLM on seller pool data."""
from llm.client import llm
from langfuse_client import observe


@observe(name="skill_seller")
def run_skill_seller(ctx: dict) -> dict:
    seller_pool = ctx.get("seller_pool", [])
    buyer_city = ctx.get("buyer", {}).get("eto_ofr_s_city", "Unknown")

    if not seller_pool:
        return {
            "bucket": "SELLER_SIDE_FAILURE",
            "pool_size": 0,
            "confidence": 85,
            "likely_responded": False,
            "primary_reason": "No sellers in pool — supply gap",
            "seller_quality_score": 0,
            "fix": "Expand seller pool for this category and geography",
        }

    seller_summary = ""
    for i, s in enumerate(seller_pool, 1):
        last_login = s.get("glusr_usr_lastlogin") or "never"
        credits = s.get("glusr_eto_cust_credits_av") or "blank/exhausted"
        seller_summary += f"""
Seller {i} — {s.get('glusr_usr_companyname', 'Unknown')}:
  Membership: {s.get('custtype_name')} | Paid: {s.get('custtype_is_paid')}
  FCP Flag: {s.get('fcp_flag')} | Credits: {credits}
  Member Since: {s.get('glusr_usr_membersince')} | Last Login: {last_login}
  City ID: {s.get('fk_gl_city_id')}"""

    result = llm.chat_json(
        system=(
            "You are a seller engagement analyst for IndiaMART B2B marketplace. "
            "You diagnose why sellers in a pool did not respond to a BuyLead."
        ),
        user=f"""A BuyLead for "{ctx['offer_name']}" was sent to {len(seller_pool)} sellers.
The buyer is from: {buyer_city}
All sellers have FCP=0: {ctx.get('seller_all_fcp_zero')}
All sellers have blank credits: {ctx.get('seller_all_credits_blank')}

Seller Pool:
{seller_summary}

Based on this seller pool data, explain why these sellers likely did NOT respond.
Consider: FCP flag (0=no proactive calling), blank credits=cannot respond,
unpaid membership=limited access, last login=activity, city match.

Return JSON only:
{{
  "likely_responded": true or false,
  "confidence": 0-100,
  "primary_reason": "main reason sellers did not respond",
  "seller_quality_score": 0-100,
  "fix": "one actionable sentence"
}}""",
    )

    return {
        "bucket": "SELLER_SIDE_FAILURE",
        "pool_size": len(seller_pool),
        "likely_responded": result.get("likely_responded", False),
        "confidence": int(result.get("confidence", 50)),
        "primary_reason": result.get("primary_reason", ""),
        "seller_quality_score": int(result.get("seller_quality_score", 50)),
        "fix": result.get("fix", "Review seller pool quality for this category"),
    }
