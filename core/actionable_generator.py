"""
Actionable synthesis — runs ONE Gateway LLM call after all bucket
skills complete, with every signal we have, and produces:
  - a one-sentence root-cause headline
  - a paragraph explaining why the BL didn't sell
  - an ordered list of concrete fixes (with impact level)
  - a confidence score + any caveats

This is the agent's final "what do we tell the human" answer.  It is
NOT a bucket — it consumes the bucket verdicts as input.
"""
import logging

from config.settings import settings
from langfuse_client import observe
from llm.client import llm

logger = logging.getLogger(__name__)


_BUCKET_LABEL = {
    "MCAT_MISMATCH":      "B1 MCAT Mismatch",
    "THIN_CONTENT":       "B2 Thin Content",
    "SPEC_CONTRADICTION": "B3 Spec Contradiction",
    "LOW_BUYER_INTENT":   "B4 Low Buyer Intent",
    "SPEC_VALUE_QUALITY": "B5 Spec Value Quality",
    "QUANTITY_MISMATCH":  "B6 Quantity Mismatch",
    "RETAIL_QUERY":       "B7 Retail Query",
}


def _short(s: str, n: int = 280) -> str:
    if not s:
        return ""
    s = str(s).strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _bucket_summary(rca: dict, skill_results: dict) -> str:
    lines = []
    scored = sorted(
        (rca.get("bucket_scores") or {}).items(),
        key=lambda x: -x[1],
    )
    for bucket, score in scored:
        label = _BUCKET_LABEL.get(bucket, bucket)
        # Map bucket → skill key
        sk_map = {
            "MCAT_MISMATCH": "mcat", "THIN_CONTENT": "content",
            "SPEC_CONTRADICTION": "spec", "LOW_BUYER_INTENT": "intent",
            "SPEC_VALUE_QUALITY": "spec_quality",
            "QUANTITY_MISMATCH": "quantity", "RETAIL_QUERY": "retail",
        }
        sr = skill_results.get(sk_map.get(bucket, ""), {}) or {}
        reasoning = _short(sr.get("reasoning") or sr.get("combined_reasoning")
                           or sr.get("primary_failure_mode") or "")
        fix = _short(sr.get("fix"), 200)
        active = "●" if score > 40 else " "
        lines.append(f"  {active} {label:<28} {score:>3}%  | reason: {reasoning}\n      proposed fix: {fix}")
    return "\n".join(lines)


def _buyer_summary(ctx: dict) -> str:
    b = ctx.get("buyer") or {}
    def yn(v): return "yes" if v else "no"
    return (
        f"company={b.get('eto_ofr_companyname') or b.get('eto_ofr_s_organization') or '—'}, "
        f"city={b.get('eto_ofr_s_city') or '—'}, "
        f"verified GST={yn(b.get('eto_ofr_buyer_is_gst_verf'))} "
        f"mobile={yn(b.get('eto_ofr_buyer_is_mob_verf'))} "
        f"email={yn(b.get('eto_ofr_email_verified'))}, "
        f"total_leads_buyer_has_posted={b.get('eto_ofr_buyer_leads_cnt') or 0}  ← this is the buyer's LIFETIME lead-post count, NOT a purchase outcome, "
        f"first_time_buyer={yn(ctx.get('is_first_time_buyer'))}, "
        f"buyer_in_prime_mcat={yn(ctx.get('buyer_in_prime_mcat'))}, "
        f"sells_competing={yn(ctx.get('sells_competing'))}"
    )


def _purchase_summary(ctx: dict) -> str:
    if not ctx.get("was_purchased"):
        return "purchased_status=Not Purchased / Unknown — true unsold case"
    purchasers = ctx.get("purchasing_sellers") or []
    if not purchasers:
        return f"purchased_status=Purchased (count={ctx.get('purchase_count')}) but buyer details not in warehouse (archived)"
    parts = [f"{s.get('company','?')} ({s.get('custtype_name','?')}, bought {str(s.get('purchased_at') or '')[:10]})"
             for s in purchasers]
    return f"PURCHASED by: {' | '.join(parts)}  (has_business_buyer={ctx.get('has_business_buyer')})"


def _content_summary(ctx: dict) -> str:
    specs_filled = ctx.get("specs_filled") or {}
    catalog = ctx.get("mcat_spec_catalog") or {}
    bm = ctx.get("sold_benchmark") or {}
    parts = [
        f"specs_filled={len(specs_filled)}/{len(catalog)} ({list(specs_filled.keys())[:6]})",
        f"aov={ctx.get('probable_order_value') or 'n/a'}",
        f"req_type={ctx.get('probable_req_type') or 'n/a'}",
    ]
    if bm.get("total_sold_bls"):
        parts.append(
            f"benchmark: {bm['total_sold_bls']} BLs sold in last 90d, "
            f"{bm.get('pct_sold_with_le_1_spec','—')}% sold with ≤1 spec"
        )
    return ", ".join(parts)


_SCHEMA_REMINDER = """{
  "root_cause_headline": "one declarative sentence — exactly why this BL did not sell",
  "root_cause_detail": "2-3 paragraphs citing specific signals (bucket scores, purchaser custtype, prime-mcat match, etc.). Tie each claim to evidence.",
  "action_items": [
    {"priority": 1, "label": "Short imperative", "detail": "Specific implementation step", "impact": "Low|Medium|High"},
    {"priority": 2, "label": "...",              "detail": "...",                          "impact": "..."}
  ],
  "confidence": 0-100,
  "caveats": "what we couldn't determine OR data limitations (e.g. archived BL, no purchasing-seller info)"
}"""


@observe(name="actionable_generator")
def generate_actionable(ctx: dict, rca: dict) -> dict:
    """Produce the final synthesised verdict + action items."""
    skill_results = rca.get("all_skill_results") or {}
    bucket_lines = _bucket_summary(rca, skill_results)

    # Build a compact but evidence-rich brief
    brief = f"""You are the senior root-cause analyst for IndiaMART. Synthesise ONE final
answer from every signal below. Be decisive, evidence-grounded, and concrete.

=================== BUYLEAD ===================
Offer ID:    {ctx.get('offer_id')}
Title:       {ctx.get('offer_name')}
Category:    {ctx.get('mapped_mcat_name')} (id {ctx.get('mapped_mcat_id')})
Approved:    {ctx.get('approval_date','')[:10]}
Enq type:    {ctx.get('retail_flag')!r}  (1=Retail, 2=B2B, 3=Auto-Retail, None=unknown)
Content:     {_content_summary(ctx)}

=================== BUYER ===================
{_buyer_summary(ctx)}

=================== PURCHASE OUTCOME (hardest evidence) ===================
{_purchase_summary(ctx)}

=================== BUCKET VERDICTS ({rca.get('overlap_count',0)} active) ===================
{bucket_lines}

Active buckets above the 40% threshold are the candidate root causes.
Overlap summary: {rca.get('overlap_summary','')}

=================== YOUR TASK ===================
Synthesise the single best answer to: "Why did this BuyLead not sell, and how should we fix it?"

Critical rules:
1. DO NOT analyse or speculate about which sellers the BL was originally recommended to —
   we have NO data on the original-recommendation seller pool.  Don't say things like
   "routed to a pool with no local presence" or "no suppliers in the target city".  Those
   claims are unsupported by the data above.  Only reason about: buyer profile, BL content,
   spec quality, MCAT mapping, retail-vs-B2B, and purchase outcome.

2. DO NOT invent statistics we do not have.  Specifically:
   - We know how many BuyLeads the buyer has POSTED (`total_leads_buyer_has_posted`)
   - We DO NOT know how many of those leads were purchased / converted / sold.
   Therefore phrases like "21 leads with zero purchases", "history of unsold leads",
   "low conversion history", "previous leads went unanswered" are FORBIDDEN.  Only state
   the lead-count itself if you mention it at all.

3. If the BL was purchased by a B2B seller, the "why didn't it sell" framing is wrong — call that
   out explicitly and pivot the action items to spec normalization / process improvements
   / training-data tagging.  Do NOT pivot to seller-routing improvements — we can't analyse routing.

4. If multiple buckets are active, identify the PRIMARY driver and call out secondary contributors.

5. Each action item must be implementable (concrete who/what), not vague advice.

6. Order action items by impact, highest first.

7. WRITE FOR A BUSINESS READER, NOT AN ENGINEER.
   - Avoid jargon like "B3/B5", "algorithm tuning", "model recalibration", "spec normalization
     in DBA layer", "training-data tagging".
   - Avoid mentioning internal bucket codes (B1-B7) — refer to issues by their plain names
     ("the category mapping check", "the buyer-intent check", etc.).
   - Use everyday language a category-team lead would say in a Monday meeting.
   - Cite signals naturally — "the buyer is a GST-verified business buying 100 tons of rubber"
     beats "buyer.verification.score=3 and ofr_aov in lakh-tier band".

Return JSON only, exactly this shape:
{_SCHEMA_REMINDER}
"""

    return llm.chat_json(
        system=(
            "You are the lead RCA analyst for IndiaMART, India's largest B2B marketplace. "
            "You read every bucket verdict and every raw signal, then produce ONE coherent "
            "answer — root cause + ordered fixes. Be concise, specific, and grounded in the "
            "evidence provided."
        ),
        user=brief,
        model=settings.DEFAULT_EXTRACTION_MODEL,
        max_tokens=2500,
    )
