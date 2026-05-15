---
name: rca
description: Use this skill when working on the IndiaMART BL RCA Agent — diagnosing why a BuyLead failed to sell, improving any of the 7 failure bucket skills (B1–B7), debugging confidence scores, updating bucket logic, fixing the seller pool analysis, working on the UI, or running the demo. Returns a structured RCA report with confidence scores, overlap detection, and per-bucket fixes. Also renders the full visual dashboard as an HTML artifact directly in the chat.
---

When invoked, do the following:

1. Read `CLAUDE.md` in the project root for full project context before making any changes.
2. Identify what the user wants — improve a bucket, debug a score, add a feature, or run the demo.
3. Read the relevant skill file(s) from `skills/` before editing.
4. Make changes if needed.
5. **Run the demo and render the dashboard as an HTML artifact** (see Dashboard Output below).

## Inputs
- Optional: bucket name (B1–B7) or offer_id to focus on
- If no argument given, load full project context and await instruction

## Outputs
- Code changes to skill files, orchestrator, context builder, or UI
- The full RCA dashboard rendered as an HTML artifact in the chat

## Project Location
`C:\Users\Imart\Desktop\67xHackathon\hackathon67x`

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Full project guide — read first |
| `data/SCHEMA.md` | All 6 CSV schemas |
| `core/orchestrator.py` | Runs all 7 skills, overlap detection |
| `core/bl_context_builder.py` | Reads 6 CSVs → flat context dict |
| `api/main.py` | FastAPI — /report/demo, /rca/single, /health |
| `skills/skill_mcat.py` | B1 MCAT Mismatch |
| `skills/skill_content.py` | B2 Thin Content |
| `skills/skill_spec.py` | B3 Spec Contradiction |
| `skills/skill_intent.py` | B4 Low Buyer Intent |
| `skills/skill_seller.py` | B5 Seller Side Failure |
| `skills/skill_spec_quality.py` | B6 Spec Value Quality |
| `skills/skill_quantity.py` | B7 Quantity Mismatch |
| `ui/index.html` | Single-page dark UI (server-hosted) |
| `ui/artifact_template.html` | Standalone template — Claude injects data here for artifact output |
| `llm/client.py` | Singleton `llm` — chat_json(), parallel() |
| `config/settings.py` | All env vars and model names |

## 7 Failure Buckets

| ID | Bucket | LLM | Fast Path |
|----|--------|-----|-----------|
| B1 | MCAT_MISMATCH | Gateway Flash | — |
| B2 | THIN_CONTENT | Parallel AI + Gateway | — |
| B3 | SPEC_CONTRADICTION | Parallel AI only | — |
| B4 | LOW_BUYER_INTENT | Gateway Flash Lite | — |
| B5 | SELLER_SIDE_FAILURE | Gateway Flash Lite | pool_size=0 → conf=90 |
| B6 | SPEC_VALUE_QUALITY | Parallel AI only | out_of_catalog=0 → conf=0 |
| B7 | QUANTITY_MISMATCH | Parallel AI only | no qty+no AOV → conf=0 |

Active threshold: **40%** — buckets above 40 flagged as active issues.

## Critical Design Rules
- B1: confidence = raw if is_mismatch=True, else 100-raw (inversion when category is correct)
- B3/B6/B7: Parallel AI returns `fix` directly — no Gateway summariser (cost saving)
- B4/B5: use `model=settings.GEMINI_FLASH_LITE_MODEL` for cost saving
- All count metrics output as `{count, total, pct, label}` format
- city_mismatch in ctx = buyer GLB vs IP city, NOT buyer vs seller city
- selection_rejection_type=A = selected for distribution, NOT responded

## Demo Data
Dummy test data in `data/dummy testing data/` — offer_id: 144220567946 (Natural Rubber Scrap)
Expected result: 4 active issues — B5(100%), B2(85%), B4(80%), B1(~2% after fix)

## Dashboard Output — HTML Artifact

After running the demo (or after any code change), render the full dashboard as a self-contained HTML artifact in the chat. Follow these exact steps:

### Step 1 — Get the RCA JSON
Start the API server if not running, then fetch the report:
```bash
# Start server in background (skip if already running)
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
sleep 3

# Fetch the full report JSON
curl -s http://localhost:8000/report/demo
```

If the server is already running, just run the curl command.

### Step 2 — Read the artifact template
Read the file `ui/artifact_template.html` in full.

### Step 3 — Inject data and output artifact
In the template, find this exact line:
```
window.RCA_DATA = null; /* __INJECT_RCA_DATA__ */
```
Replace it with:
```
window.RCA_DATA = <PASTE_FULL_JSON_HERE>;
```
Where `<PASTE_FULL_JSON_HERE>` is the complete JSON object returned by `/report/demo`.

Then output the entire modified HTML as an artifact:

```
<antArtifact identifier="rca-dashboard" type="text/html" title="BL RCA Dashboard — {offer_name}">
[full modified HTML here]
</antArtifact>
```

### What the dashboard shows
- **Section 1** — BuyLead form with all specs (filled/empty, priority stars, option pills)
- **Section 2** — Buyer profile (verification, intent score, competing seller flags)
- **Section 3** — Seller pool (credits, quality, distance, per-seller blockers, B5 diagnosis)
- **Section 4** — RCA Diagnosis (radar chart, Venn overlap diagram, bucket cards with fixes, all 7 score bars)

## References
See `references/` folder for detailed bucket logic and data schema.
