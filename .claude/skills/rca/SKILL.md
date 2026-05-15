---
name: rca
description: BL RCA Agent for IndiaMART — diagnose why a BuyLead failed to sell across 7 failure buckets. Use when working on the RCA agent codebase, debugging bucket logic, improving skills, or analysing a BuyLead.
allowed-tools: Read Bash Glob Grep Edit Write
---

# BL RCA Agent — Project Skill

You are working on the **IndiaMART BL RCA Agent** — a system that diagnoses why a BuyLead (buyer enquiry) failed to sell on IndiaMART's B2B marketplace.

## Project Location
`C:\Users\Imart\Desktop\67xHackathon\hackathon67x`

## What the System Does
- Ingests up to 6 CSV data sources for a BuyLead
- Builds a flat context dict with all signals
- Runs **7 specialised skill agents** — each scores one failure bucket (0–100 confidence)
- Detects overlap — multiple active issues simultaneously
- Serves a web UI at `http://localhost:8000`

## 7 Failure Buckets

| ID | Bucket | File | LLM |
|----|--------|------|-----|
| B1 | `MCAT_MISMATCH` | `skills/skill_mcat.py` | Gateway Flash |
| B2 | `THIN_CONTENT` | `skills/skill_content.py` | Parallel AI + Gateway |
| B3 | `SPEC_CONTRADICTION` | `skills/skill_spec.py` | Parallel AI only |
| B4 | `LOW_BUYER_INTENT` | `skills/skill_intent.py` | Gateway Flash Lite |
| B5 | `SELLER_SIDE_FAILURE` | `skills/skill_seller.py` | Gateway Flash Lite |
| B6 | `SPEC_VALUE_QUALITY` | `skills/skill_spec_quality.py` | Parallel AI only |
| B7 | `QUANTITY_MISMATCH` | `skills/skill_quantity.py` | Parallel AI only |

**Active threshold: 40%** — buckets above 40 are flagged as active issues.

## Key Files

```
api/main.py                  ← FastAPI (port 8000) — /report/demo, /rca/single, /health
core/bl_context_builder.py   ← Reads 6 CSVs → flat context dict
core/orchestrator.py         ← Runs all 7 skills, overlap detection, saves output
skills/skill_mcat.py         ← B1
skills/skill_content.py      ← B2
skills/skill_spec.py         ← B3
skills/skill_intent.py       ← B4
skills/skill_seller.py       ← B5
skills/skill_spec_quality.py ← B6
skills/skill_quantity.py     ← B7
llm/client.py                ← Singleton `llm` — chat_json(), parallel()
config/settings.py           ← All env vars and model names
ui/index.html                ← Single-page dark UI
data/dummy testing data/     ← Test CSVs (offer_id: 144220567946, Natural Rubber Scrap)
CLAUDE.md                    ← Full project guide — read this for complete context
data/SCHEMA.md               ← All 6 CSV schemas with field meanings
```

## Data Sources

| # | File | Key Info |
|---|------|----------|
| DS1 | `bl_data.csv` | PIVOTED — group by offer_id. spec_id=-1 = metadata (AOV, req_type) |
| DS2 | `buyer_data.csv` | GST/mobile/email verified, leads_cnt, sell_mcats, prime_mcats |
| DS3 | `seller_data.csv` | Basic seller pool, fcp_flag |
| DS4 | `buyer_specs_data.csv` | MCAT catalog — options, priority (1=required), is_quantity_related |
| DS5 | `0_1_2_specs_mcat_bl_sold_Data.csv` | Thin BL benchmark — BLs with 0/1/2 specs that sold |
| DS6 | `Seller_Detailed_Data.csv` | Rich seller data — alert rank, credits, last login, distance |

## Important Design Rules

1. **B1 confidence inversion** — if `is_mismatch=False`, bucket confidence = `100 - raw_confidence`
2. **B6/B7 fast path** — confidence=0 and no LLM if no out-of-catalog specs / no quantity data
3. **city_mismatch** in ctx = buyer GLB city vs IP city (suspicious login), NOT buyer vs seller city
4. **selection_rejection_type=A** = seller selected for distribution, NOT that they responded
5. **All count metrics** output as `{count, total, pct, label}` format for direct UI display
6. **No Gateway summariser in B3/B6/B7** — Parallel AI returns fix directly (cost saving)
7. **Flash Lite** used for B4/B5 Gateway calls — `model=settings.GEMINI_FLASH_LITE_MODEL`

## Running the Project

```bash
# Start server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Test demo endpoint
curl http://localhost:8000/health
curl http://localhost:8000/report/demo
```

## Current Demo Data Result (offer_id: 144220567946)
- 4 overlapping issues: B5 Seller Side Failure (100%), B1 MCAT Mismatch (~2% after fix), B2 Thin Content (85%), B4 Low Buyer Intent (80%)
- B3 Spec Contradiction: ~5% (no contradiction found)
- B6 Spec Value Quality: 0% (all values in catalog)
- B7 Quantity Mismatch: ~5% (no retail quantity issue)

## If the user passes an argument ($ARGUMENTS)
Treat it as either:
- An offer_id to analyse
- A bucket name (B1–B7) to focus on
- A task description to execute

Read `CLAUDE.md` for full context before making any changes.
