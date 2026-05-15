# BL RCA Agent — IndiaMART Hackathon Submission

## Problem
Thousands of BuyLeads on IndiaMART go unsold every day. The root causes are not systematically identified, leaving sellers frustrated and buyers underserved.

## Solution
An AI-powered Root Cause Analysis (RCA) agent that diagnoses **why** a BuyLead failed to convert, classifies it into one of 5 failure buckets, and produces actionable fixes.

## 5 Failure Buckets

| # | Bucket | Trigger | Approach |
|---|--------|---------|----------|
| B1 | **MCAT Mismatch** | Wrong category mapping | LLM |
| B2 | **Thin Content** | Missing fields, low ISQ fill | Rules + LLM fallback |
| B3 | **Spec Contradiction** | Title/desc/category inconsistency | LLM |
| B4 | **Low Buyer Intent** | Auto-gen, guest login, late night | Rules only |
| B5 | **Seller Side Failure** | NI overload, slow response, supply gap | Rules + LLM fallback |

## Architecture

```
CSV Input → BL Context Builder → Orchestrator (Claude tool_use loop)
                                        ↓
                    ┌───────────────────┼───────────────────┐
               skill_mcat        skill_content         skill_spec
               skill_intent      skill_seller
                    └───────────────────┼───────────────────┘
                                   Synthesiser
                                        ↓
                              Per-BL Card + Weekly Digest
```

## Stack
- **Model**: `claude-haiku-4-5-20251001` (cost-efficient for high volume)
- **Orchestration**: Anthropic native `tool_use` agent loop
- **API**: FastAPI
- **Data**: Pandas
- **UI**: Vanilla HTML/JS

## Cost Optimisation
- B4 (Intent): 100% rule-based — zero LLM calls
- B2 (Content): LLM only invoked when rule pre-confidence is 40–80%
- B5 (Seller): LLM skipped when rules give clear signal
- Uses Haiku (not Sonnet) for skill calls — 10× cheaper

## Running

```bash
# Install
pip install -r requirements.txt

# Set API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# Run on sample data
python main.py data/sample_unsold_bls.csv

# Run API server
python -m uvicorn api.main:app --reload --port 8000

# Run tests (no API key needed)
pytest tests/test_skill_intent.py tests/test_skill_content.py -v
```

## Team
IndiaMART Hackathon 2026
