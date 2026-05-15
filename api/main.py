"""
FastAPI — POST /rca/single accepts 4 uploaded CSVs, runs RCA, returns JSON.
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from core.bl_context_builder import build_bl_context
from core.orchestrator import run_rca

app = FastAPI(title="BL RCA Agent API", version="2.0.0")

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
    return {"message": "BL RCA Agent API v2", "docs": "/docs", "ui": "/ui/index.html"}


@app.post("/rca/single")
async def rca_single(
    bl_csv:     UploadFile = File(..., description="bl_data.csv"),
    buyer_csv:  UploadFile = File(..., description="buyer_data.csv"),
    seller_csv: UploadFile = File(..., description="seller_data.csv"),
    specs_csv:  UploadFile = File(..., description="buyer_specs_data.csv"),
):
    """Run RCA on a single BL. Upload 4 CSV files."""
    tmp_files = []
    try:
        # Save uploads to temp files
        paths = {}
        for name, upload in [
            ("bl", bl_csv), ("buyer", buyer_csv),
            ("seller", seller_csv), ("specs", specs_csv),
        ]:
            content = await upload.read()
            tmp = tempfile.NamedTemporaryFile(
                suffix=".csv", delete=False, mode="wb"
            )
            tmp.write(content)
            tmp.close()
            paths[name] = tmp.name
            tmp_files.append(tmp.name)

        ctx = build_bl_context(
            bl_csv=paths["bl"],
            buyer_csv=paths["buyer"],
            seller_csv=paths["seller"],
            specs_csv=paths["specs"],
        )
        result = run_rca(ctx)

        # Serialise for JSON response
        safe = {k: v for k, v in result.items() if k != "all_skill_results"}
        safe["skill_results"] = {
            k: {sk: sv for sk, sv in v.items() if sk != "parallel_raw"}
            for k, v in result.get("all_skill_results", {}).items()
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


@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
