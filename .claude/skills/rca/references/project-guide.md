# BL RCA Agent — Project Guide

## Problem Statement

**IndiaMART BuyLeads (BLs)** are buyer enquiries posted on the platform. A BuyLead is "unsold" when none of the matched sellers respond or convert the enquiry into a deal. This project is a **Root Cause Analysis (RCA) Agent** that automatically diagnoses *why* a specific BuyLead failed to sell, assigns confidence scores to each failure reason, detects when multiple failures overlap, and recommends fixes.

Built for the **67x Hackathon** at IndiaMART.

---

## What the System Does

1. **Ingests** up to 6 CSV data sources for a BuyLead
2. **Builds a context dict** with all signals (specs filled, buyer profile, seller pool, benchmarks)
3. **Runs 7 specialised skill agents** — each scores one failure bucket (0–100 confidence)
4. **Detects overlap** — a BL can have multiple active issues simultaneously
5. **Returns a structured report** — BL form view, buyer profile, seller cards, RCA diagnosis
6. **Serves a web UI** at `http://localhost:8000` — demo endpoint built-in, no file uploads needed

---

## 7 Failure Buckets

| ID | Bucket | What It Checks | LLM Used |
|----|--------|---------------|----------|
| B1 | `MCAT_MISMATCH` | Is the BuyLead mapped to the correct product category? | Gateway (Gemini Flash) |
| B2 | `THIN_CONTENT` | Did the buyer fill enough specs? Priority coverage? Fill ratio? | Parallel AI + Gateway |
| B3 | `SPEC_CONTRADICTION` | Do specs contradict each other, the offer title, or catalog options? | Parallel AI only |
| B4 | `LOW_BUYER_INTENT` | Is the buyer genuine? Competitor, first-time, unverified? | Gateway (Gemini Flash Lite) |
| B5 | `SELLER_SIDE_FAILURE` | Can sellers in the pool actually respond? Credits, activity, distance? | Gateway (Gemini Flash Lite) |
| B6 | `SPEC_VALUE_QUALITY` | Are out-of-catalog spec values real/valid in Indian B2B market? | Parallel AI only |
| B7 | `QUANTITY_MISMATCH` | Is the quantity B2B-appropriate? Does AOV match quantity? | Parallel AI only |

**Active threshold: 40%** — any bucket scoring above 40 is flagged as an active issue.

---

## Data Sources (6 CSVs)

> Full schema with every field, sample values, confirmed vs assumed meanings: **`data/SCHEMA.md`**

| # | File | Purpose | Used In |
|---|------|---------|---------|
| DS1 | `bl_data.csv` | Pivoted BuyLead data — many rows per BL (one per spec). `spec_id=-1` rows are system metadata (AOV, req_type) | All buckets |
| DS2 | `buyer_data.csv` | Buyer profile — GST/mobile/email verification, total leads, city, designation, sell_mcats, prime_mcats | B4 |
| DS3 | `seller_data.csv` | Basic seller pool — matched sellers, fcp_flag, basic credits | B5 (fallback) |
| DS4 | `buyer_specs_data.csv` | MCAT spec catalog — valid options per spec, priority (1=required, 2=important), `is_quantity_related_spec` flag | B1, B2, B3, B6, B7 |
| DS5 | `0_1_2_specs_mcat_bl_sold_Data.csv` | **Thin-content sold BL benchmark** — BLs with 0, 1, or 2 specs filled that WERE sold. `thin_sold_bl_count` = how many such BLs exist for this MCAT. High count → thin content less critical. | B2 |
| DS6 | `Seller_Detailed_Data.csv` | Rich seller data — alert rank (A/B/C+AA/AB etc.), available_credits, last login, BL purchased/year, distance, preferred_cities, consuming_cities | B5 |

**DS1 is PIVOTED** — always GROUP BY offer_id. `spec_id = -1` rows = system metadata, not actual specs.
**DS5 and DS6 are optional** — system works with DS1–DS4, accuracy improves with DS5+DS6.

---

## Architecture

```
ui/index.html               ← Single-page dark UI — calls /report/demo, no file uploads
        │
api/main.py                 ← FastAPI, port 8000
  GET  /                    ← Serves index.html
  GET  /report/demo         ← Full structured report (BL form + buyer + sellers + RCA)
  GET  /rca/demo            ← Raw RCA result only
  POST /rca/single          ← Upload 4–6 CSVs, run full RCA
  GET  /health              ← {"status":"ok"}
        │
core/bl_context_builder.py  ← Reads all 6 CSVs → builds flat context dict
core/orchestrator.py        ← Runs all 7 skills, computes overlap, saves outputs
        │
skills/skill_mcat.py         ← B1: Gateway LLM (offer_name + mcat_name only)
skills/skill_content.py      ← B2: Compute fill metrics → Parallel AI → Gateway
skills/skill_spec.py         ← B3: Rule-based out-of-catalog + Parallel AI only
skills/skill_intent.py       ← B4: Pre-compute signals → Gateway Flash Lite
skills/skill_seller.py       ← B5: Rule-based per-seller blockers + Gateway Flash Lite
skills/skill_spec_quality.py ← B6: Out-of-catalog value verification via Parallel AI
skills/skill_quantity.py     ← B7: Extract quantity specs + AOV → Parallel AI
        │
llm/client.py               ← Singleton `llm` — chat(), chat_json(), parallel()
llm/gateway.py              ← httpx POST to Intermesh LLM Gateway
llm/parallel_ai.py          ← Parallel AI task polling
        │
output/result_writer.py     ← Saves timestamped JSON per run → output/results/
output/report_generator.py  ← Generates BL card text
langfuse_client.py          ← Langfuse v4 observability (no-op fallback if not configured)
```

---

## Bucket Logic — Detailed

### B1 — MCAT_MISMATCH (`skills/skill_mcat.py`)
- **Input:** `offer_name` + `mapped_mcat_name` only — nothing else
- **LLM:** Gateway Gemini Flash — "Is this category a mismatch for this product?"
- **Returns:** `is_mismatch`, `raw_confidence`, `confidence` (= raw if mismatch, 100-raw if correct), `reasoning`, `suggested_mcat`, `fix`
- **Key:** confidence is INVERTED when `is_mismatch=False` — LLM confidence in correct mapping → low mismatch bucket score

### B2 — THIN_CONTENT (`skills/skill_content.py`)
- **Step 1 — Rule-based metrics:**
  - `fill_count / total_specs` → `fill_ratio`, `fill_pct`
  - `priority_filled / total_priority` → `priority_ratio`, `priority_pct`
  - `is_priority1_filled`, `is_priority2_filled` (booleans)
  - `thin_sold_bl_count` from DS5 (shown as raw count)
  - `spec_review_needed` flag: True when `fill_count <= 1` AND `thin_sold_bl_count <= 3`
- **Step 2 — Parallel AI:** all metrics + specs_filled → `is_thin`, `confidence`, `reasoning`
- **Step 3 — Gateway:** final `confidence` + `fix`

### B3 — SPEC_CONTRADICTION (`skills/skill_spec.py`)
- **Step 1 — Rule-based:** `_build_spec_context()` checks each filled spec against catalog options → `out_of_catalog_count`, `out_of_catalog_specs` list
- **Step 2 — Parallel AI only (no Gateway):** sends structured spec table (buyer value vs valid options) + out-of-catalog signal
- **Checks 3 contradiction types:** spec vs spec, offer title vs spec, out-of-catalog validity
- **Returns:** `contradicting_pairs` (array of `{spec_a, spec_b, reason}`), `reasoning`, `confidence`, `fix`

### B4 — LOW_BUYER_INTENT (`skills/skill_intent.py`)
- **Step 1 — Pre-compute:** `verification_score` (0-3), `lead_history` label, `channel_label` from mod_id
- **Step 2 — Gateway Flash Lite:** structured prompt in 4 sections (Verification / Behavioral / Competitive / Profile)
- **city_mismatch NOT included** — buyer vs seller city comparison belongs in B5
- **Returns:** `verification_score`, `lead_history`, `sells_competing`, `intent_score`, `confidence` (direct, no inversion), `is_genuine`, `reasoning`, `fix`

### B5 — SELLER_SIDE_FAILURE (`skills/skill_seller.py`)
- **Step 1 — `_build_per_seller()`:** for each DS6 seller: `has_credits`, `days_inactive`, `distance_km`, `city_match`, `bl_yr`, `alert_rank`, rule-based `blockers[]`
- **Step 2 — Pool aggregates:** all as `{count, total, pct, label}` format: `with_credits`, `city_match`, `with_bl_history`, `active_last_30d`, `alert_breakdown`, `distance_km {avg/min/max}`
- **Step 3 — Gateway Flash Lite:** pool summary + per-seller one-liner → returns `per_seller_reasoning[]` + `combined_reasoning` + `primary_failure_mode`
- **Note:** No direct "seller consumed BL" signal — `selection_rejection_type=A` means selected for distribution, NOT responded

### B6 — SPEC_VALUE_QUALITY (`skills/skill_spec_quality.py`)
- **Fast path:** `out_of_catalog_count == 0` → confidence=0, skip LLM
- **Parallel AI only:** for each out-of-catalog spec, verifies if value is real/recognised in Indian B2B market
- **Returns:** `out_of_catalog_count/total_filled (pct%)`, per-spec `{is_valid_in_market, reasoning}`, `invalid_in_market` count

### B7 — QUANTITY_MISMATCH (`skills/skill_quantity.py`)
- **Extracts:** quantity specs from catalog using `is_quantity_related` flag, `probable_order_value` (AOV), `probable_req_type`
- **Fast path:** no quantity + no AOV + not retail req_type → confidence=0
- **Rule-based:** `req_type_retail = True` when `probable_req_type == "Personal Use"` (hard signal)
- **Parallel AI only:** checks retail vs B2B norms, AOV vs quantity unit price, req_type appropriateness
- **Returns:** `quantity_specs`, `req_type_retail`, `is_retail_quantity`, `aov_quantity_mismatch`, `reasoning`, `fix`

---

## Context Dict — Key Fields

Built by `build_bl_context()`, passed to every skill:

```python
ctx = {
    # BL identity
    "offer_id", "offer_name", "mapped_mcat_id", "mapped_mcat_name",
    "url_mcat_id",           # extracted from page_referrer URL (?mcatid=...)
    "mod_id",                # channel: FENQ, LEAP, IMOB, EXPORTM
    "approval_date", "approval_status",

    # Buyer specs (from DS1)
    "specs_filled",          # dict {spec_name: buyer_value}
    "specs_fill_count",      # int
    "probable_order_value",  # "Rs. 22-50 Lakh" (spec_id=-1 metadata)
    "probable_req_type",     # "Business Use" / "Personal Use" / "Resale"
    "aov_blank",             # bool

    # MCAT catalog (from DS4)
    "mcat_spec_catalog",     # {spec_name: {priority, options, is_quantity_related}}
    "priority_specs",        # list of spec names with priority <= 2

    # Buyer profile (from DS2)
    "buyer",                 # raw dict from buyer_data.csv

    # Basic seller pool (from DS3)
    "seller_pool",           # list of basic seller dicts

    # DS5 benchmark
    "thin_sold_bl_count",    # int — how many 0/1/2-spec BLs sold in this MCAT
    "thin_sold_bl_channels", # {"FENQ": 60.0, "LEAP": 40.0} — channel % distribution

    # DS6 enriched sellers
    "seller_detailed_pool",          # list of enriched seller dicts with _quality_score
    "seller_pool_has_credits",       # bool
    "seller_pool_avg_alert_score",   # float 0-100
    "seller_pool_avg_quality",       # float 0-100 (rule-based composite)
    "seller_pool_avg_bl_purchased",  # float

    # Computed signals
    "is_first_time_buyer",       # bool — leads_cnt <= 1
    "city_mismatch",             # bool — buyer GLB city != IP city (buyer signal only)
    "sells_competing",           # bool — buyer sells what they're buying
    "seller_all_fcp_zero",       # bool — no seller has FCP enabled
    "seller_all_credits_blank",  # bool — ALL basic pool sellers have no credits
}
```

---

## Orchestrator Output Shape

```python
{
    "offer_id", "offer_name", "mapped_mcat",
    "primary_bucket", "primary_confidence", "primary_fix",
    "secondary_bucket", "secondary_confidence", "secondary_fix",  # None if < 40
    "overlap_count",      # int — number of active buckets (confidence > 40)
    "overlap_summary",    # "4 overlapping issues detected: ..."
    "active_buckets",     # [{"bucket", "label", "confidence", "fix"}, ...]
    "all_bucket_fixes",   # {bucket_name: fix_text} for all 7
    "bucket_scores",      # {bucket_name: confidence} for all 7
    "all_skill_results",  # full raw skill outputs keyed by skill name
    "output_dir",         # str path to timestamped output folder
    "run_id",             # "2026-05-16_00-01-23_144220567946.0"
}
```

---

## LLM Infrastructure

All LLM access via `llm/client.py` singleton `llm`. Never import gateway/parallel_ai directly.

### Gateway (Intermesh — internal)
- `llm.chat(system, user, model, temperature)` → str
- `llm.chat_json(system, user, model)` → dict (auto-parses JSON)
- Default model: `settings.DEFAULT_EXTRACTION_MODEL` = `GEMINI_FLASH`
- Flash Lite for cost saving: `model=settings.GEMINI_FLASH_LITE_MODEL`
- **Used in:** B1 (Flash), B4 (Flash Lite), B5 (Flash Lite), B2 summariser (Flash)

### Parallel AI (external)
- `llm.parallel(prompt, task_spec, processor)` → dict
- Long-running search/research tasks with polling
- **Used in:** B2 content check, B3 contradiction check, B6 value verification, B7 quantity check

### Cost design
- B3, B6, B7: Parallel AI only (no Gateway summariser)
- B4, B5: Flash Lite (cheaper than Flash)
- B6, B7: fast path returns confidence=0 with no LLM if no signal detected

---

## Environment Variables (.env)

```
LLM_GATEWAY_URL=<intermesh gateway endpoint>
LLM_GATEWAY_KEY=<key>
PARALLEL_API_KEY=<key>
ANTHROPIC_API_KEY=<key>
LANGFUSE_PUBLIC_KEY=<key>
LANGFUSE_SECRET_KEY=<key>
LANGFUSE_HOST=https://cloud.langfuse.com
GEMINI_FLASH=google/gemini-flash-1.5
GEMINI_PRO_MODEL=google/gemini-pro
GEMINI_FLASH_LITE_MODEL=google/gemini-flash-1.5-8b
DEFAULT_EXTRACTION_MODEL=google/gemini-flash-1.5
```

---

## Running the Project

```bash
# Install dependencies
pip install -r requirements.txt

# Start API server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Open UI
# → http://localhost:8000
# → Click "Load Demo BL" — runs built-in dummy data, no upload needed

# Run CLI test
python run_test.py

# Verify setup
python verify_setup.py
```

---

## Output Files (per run)

Saved to `output/results/<run_id>/`:
```
00_bl_context.json       ← full context dict
01_skill_mcat.json       ← B1 result
02_skill_content.json    ← B2 result
03_skill_spec.json       ← B3 result
04_skill_intent.json     ← B4 result
05_skill_seller.json     ← B5 result
06_skill_spec_quality.json ← B6 result
07_skill_quantity.json   ← B7 result
08_final_rca.json        ← orchestrator output (all scores + overlap)
09_bl_card.txt           ← human-readable BL card
10_manifest.json         ← run metadata
```

---

## Current State (as of May 2026)

**Built and working:**
- All 7 skill agents (B1–B7)
- Context builder with all 6 data sources
- Full overlap detection (ACTIVE_THRESHOLD = 40)
- FastAPI with `/report/demo`, `/rca/demo`, `/rca/single` endpoints
- Web UI: BL form → Buyer profile → Seller pool → RCA Diagnosis (radar chart + Venn diagram)
- Langfuse v4 observability (no-op fallback)
- Timestamped output files (00–10)

**Dummy test data** in `data/dummy testing data/`:
- BL: *Natural Rubber Scrap* (offer_id: 144220567946)
- 7 matched sellers — all with no credits (root cause of B5=100%)
- 5 specs filled — no contradiction (B3 low)
- Buyer: Eco Tyrex, Kolkata, GST+Mobile+Email verified, first-time buyer
- **Latest RCA result: 4 overlapping issues — B5 Seller Side Failure (100%), B1 MCAT Mismatch (98% — KNOWN: url_mcat vs mapped_mcat are parent/child, not a true mismatch), B2 Thin Content (85%), B4 Low Buyer Intent (80%)**

**Known behaviour:**
- B1 returns high confidence on dummy data because url_mcat_id differs from mapped_mcat_id — these are parent/child taxonomy IDs, NOT a real mismatch. B1 only receives offer_name + mcat_name now, so LLM decides purely on product/category fit.
- `selection_rejection_type=A` in DS6 = seller was selected for BL distribution, NOT that they responded. No consumption signal in current data.
- city_mismatch in ctx = buyer GLB city vs IP city (suspicious login location), NOT buyer vs seller city.

---

## Key Design Decisions

1. **7 buckets always scored** — overlap is the goal, not just primary bucket
2. **Orchestrator = direct calls** — no Anthropic tool_use loop. Faster, cheaper, easier to debug
3. **DS6 seller quality is rule-based** — alert rank + credits + BL history + distance → 0-100 score, no LLM
4. **B1 confidence inversion** — if `is_mismatch=False`, bucket confidence = `100 - raw_confidence`
5. **B6/B7 fast path** — if no out-of-catalog specs / no quantity data → confidence=0, zero LLM cost
6. **n/total/pct format** — all count metrics in B2/B5 output as `{count, total, pct, label}` for direct UI display
7. **No city_mismatch in B4** — buyer vs seller city comparison needs seller data, belongs in B5
8. **No missing_critical_specs in B3** — spec quality analysis belongs in B6, not contradiction check
9. **Flash Lite for B4/B5** — B4 and B5 Gateway calls use `GEMINI_FLASH_LITE_MODEL` to reduce cost
10. **Parallel AI no-Gateway for B3/B6/B7** — these buckets use Parallel AI directly, fix included in schema
11. **bl_data is PIVOTED** — always group by offer_id. `spec_id=-1` rows are metadata, not specs
12. **Langfuse observe decorator** is a no-op if keys not set — never crashes without observability
