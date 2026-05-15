"""
FastAPI — POST /rca/single accepts 4 required + 2 optional CSVs, runs RCA, returns JSON.
"""
import sys
import os
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from core.bl_context_builder import build_bl_context
from core.orchestrator import run_rca

app = FastAPI(title="BL RCA Agent API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve UI
ui_dir = Path(__file__).parent.parent / "ui"
if ui_dir.exists():
    app.mount("/ui", StaticFiles(directory=str(ui_dir)), name="ui")


@app.get("/")
def root():
    index = ui_dir / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "BL RCA Agent API v2.1", "docs": "/docs", "ui": "/ui/index.html"}


@app.post("/rca/single")
async def rca_single(
    bl_csv:              UploadFile = File(...,  description="bl_data.csv"),
    buyer_csv:           UploadFile = File(...,  description="buyer_data.csv"),
    seller_csv:          UploadFile = File(...,  description="seller_data.csv"),
    specs_csv:           UploadFile = File(...,  description="buyer_specs_data.csv"),
    sold_bl_csv:         Optional[UploadFile] = File(None, description="0_1_2_specs_mcat_bl_sold_Data.csv (optional)"),
    seller_detailed_csv: Optional[UploadFile] = File(None, description="Seller_Detailed_Data.csv (optional)"),
):
    """
    Run RCA on a single BL.
    Required: bl_csv, buyer_csv, seller_csv, specs_csv.
    Optional: sold_bl_csv (DS5 benchmark), seller_detailed_csv (DS6 enrichment).
    """
    tmp_files = []
    try:
        paths = {}

        # Required files
        for name, upload in [
            ("bl", bl_csv), ("buyer", buyer_csv),
            ("seller", seller_csv), ("specs", specs_csv),
        ]:
            content = await upload.read()
            tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb")
            tmp.write(content)
            tmp.close()
            paths[name] = tmp.name
            tmp_files.append(tmp.name)

        # Optional files
        for name, upload in [("sold_bl", sold_bl_csv), ("seller_detailed", seller_detailed_csv)]:
            if upload and upload.filename:
                content = await upload.read()
                tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb")
                tmp.write(content)
                tmp.close()
                paths[name] = tmp.name
                tmp_files.append(tmp.name)
            else:
                paths[name] = None

        ctx = build_bl_context(
            bl_csv=paths["bl"],
            buyer_csv=paths["buyer"],
            seller_csv=paths["seller"],
            specs_csv=paths["specs"],
            sold_bl_csv=paths.get("sold_bl"),
            seller_detailed_csv=paths.get("seller_detailed"),
        )
        result = run_rca(ctx)

        # Serialise for JSON response — strip heavy internal fields
        safe = {k: v for k, v in result.items() if k != "all_skill_results"}
        safe["skill_results"] = {
            k: {sk: sv for sk, sv in v.items() if sk != "parallel_raw"}
            for k, v in result.get("all_skill_results", {}).items()
        }
        # Flag which optional data sources were provided
        safe["data_sources"] = {
            "sold_bl_benchmark": paths.get("sold_bl") is not None,
            "seller_detailed": paths.get("seller_detailed") is not None,
        }
        return JSONResponse(content=safe)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        for f in tmp_files:
            try:
                os.unlink(f)
            except Exception:
                pass


@app.get("/rca/demo")
def rca_demo():
    """Run RCA on built-in dummy data — no upload required."""
    data_dir = Path(__file__).parent.parent / "data" / "dummy testing data"
    try:
        ctx = build_bl_context(
            bl_csv=str(data_dir / "bl_data.csv"),
            buyer_csv=str(data_dir / "buyer_data.csv"),
            seller_csv=str(data_dir / "seller_data.csv"),
            specs_csv=str(data_dir / "buyer_specs_data.csv"),
            sold_bl_csv=str(data_dir / "0_1_2_specs_mcat_bl_sold_Data.csv"),
            seller_detailed_csv=str(data_dir / "Seller_Detailed_Data.csv"),
        )
        result = run_rca(ctx)
        safe = {k: v for k, v in result.items() if k != "all_skill_results"}
        safe["skill_results"] = {
            k: {sk: sv for sk, sv in v.items() if sk != "parallel_raw"}
            for k, v in result.get("all_skill_results", {}).items()
        }
        safe["data_sources"] = {"sold_bl_benchmark": True, "seller_detailed": True}
        return JSONResponse(content=safe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/demo")
def report_demo():
    """Full structured report — BL form, buyer profile, seller cards + RCA."""
    data_dir = Path(__file__).parent.parent / "data" / "dummy testing data"
    try:
        ctx = build_bl_context(
            bl_csv=str(data_dir / "bl_data.csv"),
            buyer_csv=str(data_dir / "buyer_data.csv"),
            seller_csv=str(data_dir / "seller_data.csv"),
            specs_csv=str(data_dir / "buyer_specs_data.csv"),
            sold_bl_csv=str(data_dir / "0_1_2_specs_mcat_bl_sold_Data.csv"),
            seller_detailed_csv=str(data_dir / "Seller_Detailed_Data.csv"),
        )
        result = run_rca(ctx)

        # ── 1. Spec form (what buyer filled, shown against catalog options) ──────
        specs_form = []
        for spec_name, info in sorted(
            ctx["mcat_spec_catalog"].items(), key=lambda x: x[1]["priority"]
        ):
            buyer_val = ctx["specs_filled"].get(spec_name)
            is_filled = buyer_val is not None
            options = info["options"]
            is_free_text = len(options) == 0
            is_other = is_filled and not is_free_text and buyer_val not in options
            specs_form.append({
                "name": spec_name,
                "priority": info["priority"],
                "options": options,
                "buyer_value": buyer_val,
                "is_filled": is_filled,
                "is_free_text": is_free_text,
                "is_other": is_other,
            })

        # ── 2. Buyer profile ──────────────────────────────────────────────────────
        b = ctx["buyer"]
        sell_mcats_raw = str(b.get("eto_ofr_buyer_sell_mcats") or "")
        prime_mcats_raw = str(b.get("eto_ofr_buyer_prime_mcats") or "")
        buyer_profile = {
            "company":         b.get("eto_ofr_companyname") or b.get("eto_ofr_s_organization") or "—",
            "contact":         b.get("eto_ofr_s_sendername") or "—",
            "designation":     b.get("eto_ofr_s_designation") or "—",
            "city":            b.get("eto_ofr_s_city") or "—",
            "state":           b.get("eto_ofr_s_state") or "—",
            "gst_verified":    bool(b.get("eto_ofr_buyer_is_gst_verf")),
            "mobile_verified": bool(b.get("eto_ofr_buyer_is_mob_verf")),
            "email_verified":  bool(b.get("eto_ofr_email_verified")),
            "first_time_buyer": ctx["is_first_time_buyer"],
            "total_leads":     int(float(b.get("eto_ofr_buyer_leads_cnt") or 0)),
            "past_search":     b.get("eto_ofr_buyer_past_search_mcat") or "—",
            "prime_mcats":     [x.strip() for x in prime_mcats_raw.split(",") if x.strip()],
            "sell_mcats":      [x.strip() for x in sell_mcats_raw.split(",") if x.strip()],
            "sells_competing": ctx["sells_competing"],
            "city_mismatch":   ctx["city_mismatch"],
            "intent_score":    result["all_skill_results"]["intent"].get("intent_score"),
            "is_genuine":      result["all_skill_results"]["intent"].get("is_genuine"),
            "intent_reasoning": result["all_skill_results"]["intent"].get("reasoning", ""),
        }

        # ── 3. Seller cards ───────────────────────────────────────────────────────
        buyer_city = str(b.get("eto_ofr_s_city") or "").lower()
        seller_cards = []
        for s in sorted(ctx["seller_detailed_pool"], key=lambda x: x.get("selected_seller_rank") or 99):
            credits = s.get("available_credits")
            has_credits = (
                credits is not None
                and str(credits).strip() not in ("", "nan", "None", "0", "0.0")
            )
            try:
                credit_val = float(credits) if credits is not None else 0
                has_credits = credit_val > 0
            except Exception:
                has_credits = False

            pref_cities = str(s.get("a_rank_preferred_cities") or "").lower()
            consume_cities = str(s.get("b_rank_consuming_cities") or "").lower()
            city_match = bool(buyer_city and (buyer_city in pref_cities or buyer_city in consume_cities))

            bl_yr = int(s.get("total_bl_purchased_1yr") or 0)
            dist = s.get("eto_lead_supplier_dist")
            member_since = s.get("glusr_usr_membersince") or "—"

            seller_cards.append({
                "rank":           int(s.get("selected_seller_rank") or 0),
                "company":        s.get("glusr_usr_companyname") or "—",
                "membership":     s.get("custtype_name") or "—",
                "alert_rank":     s.get("eto_trd_alert_rank") or "—",
                "alert_subrank":  s.get("eto_trd_alert_subrank") or "—",
                "credits":        credits,
                "has_credits":    has_credits,
                "last_login":     s.get("glusr_usr_lastlogin") or "—",
                "bl_purchased_1yr": bl_yr,
                "distance_km":    dist,
                "quality_score":  s.get("_quality_score"),
                "selection_type": s.get("selection_rejection_type") or "—",
                "search_keyword": s.get("eto_lead_search_keyword") or "—",
                "mapp_info":      s.get("eto_lead_supp_mapp_result_info") or "—",
                "preferred_cities": [x.strip() for x in str(s.get("a_rank_preferred_cities") or "").split(",") if x.strip()][:6],
                "member_since":   member_since,
                "city_match":     city_match,
                "flags": {
                    "no_credits":     not has_credits,
                    "no_bl_history":  bl_yr == 0,
                    "distant":        bool(dist and float(dist) > 100),
                    "city_match":     city_match,
                },
            })

        # ── 4. Pool-level signals ─────────────────────────────────────────────────
        pool_signals = {
            "total_sellers":        len(ctx["seller_detailed_pool"]),
            "avg_quality":          ctx["seller_pool_avg_quality"],
            "sellers_with_credits": sum(1 for s in seller_cards if s["has_credits"]),
            "thin_sold_bl_count":   ctx["thin_sold_bl_count"],
            "thin_sold_bl_channels": ctx["thin_sold_bl_channels"],
            "all_no_credits":       ctx["seller_all_credits_blank"],
        }

        return JSONResponse(content={
            "report": {
                "bl": {
                    "offer_id":           ctx["offer_id"],
                    "offer_name":         ctx["offer_name"],
                    "mcat_name":          ctx["mapped_mcat_name"],
                    "approval_date":      ctx.get("approval_date", ""),
                    "probable_order_value": ctx["probable_order_value"],
                    "probable_req_type":  ctx["probable_req_type"],
                    "specs_form":         specs_form,
                    "specs_fill_count":   ctx["specs_fill_count"],
                    "total_spec_count":   len(ctx["mcat_spec_catalog"]),
                },
                "buyer":        buyer_profile,
                "sellers":      seller_cards,
                "pool_signals": pool_signals,
            },
            "rca": {k: v for k, v in result.items() if k != "all_skill_results"},
            "skill_results": {
                k: {sk: sv for sk, sv in v.items() if sk != "parallel_raw"}
                for k, v in result.get("all_skill_results", {}).items()
            },
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
