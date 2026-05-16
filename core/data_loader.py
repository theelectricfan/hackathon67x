"""
Parallel Redash data loader.

Runs every query needed to diagnose a single BuyLead in two parallel
stages:

  Stage 1 (3 queries, depend only on offer_id)
    - bl_data        (ds=16)   offer + filled specs + retail flag
    - buyer_data     (ds=16)   buyer profile
    - seller_mapping (ds=16)   matched supplier pool

  Stage 2 (3 queries, depend on stage-1 outputs)
    - buyer_specs        (ds=8)   MCAT spec catalog        (needs mcat_id)
    - sold_bl_benchmark  (ds=8)   90-day spec-fill benchmark (needs mcat_id)
    - seller_details     (ds=8)   enriched supplier data    (uses offer_id)

Returns the raw rows for each query — the context builder turns them
into the flat ctx dict the skills consume.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from config.settings import settings
from core.redash_client import redash

logger = logging.getLogger(__name__)

_SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def _sql(name: str) -> str:
    return (_SQL_DIR / name).read_text()


def _int(val, field: str) -> int:
    try:
        return int(val)
    except (TypeError, ValueError) as e:
        raise ValueError(f"{field} must be an integer, got {val!r}") from e


def _run(sql_template: str, ds_id: int, **fmt) -> list[dict[str, Any]]:
    sql = sql_template.format(**fmt)
    return redash.run_sql(sql, data_source_id=ds_id)


def load_for_offer(offer_id) -> dict[str, Any]:
    """
    Fetch all 6 data slices for a BL from Redash in parallel.
    Returns a dict of {slice_name: rows} plus timing info.
    """
    if redash is None:
        raise RuntimeError("Redash client not initialised — check REDASH_API_KEY")

    oid = _int(offer_id, "offer_id")
    timings: dict[str, float] = {}

    # ── Stage 1 — 3 queries, only need offer_id ──────────────────────────────
    t0 = time.time()
    bl_sql      = _sql("bl_data.sql")
    buyer_sql   = _sql("buyer_data.sql")
    mapping_sql = _sql("seller_mapping.sql")

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(_run, bl_sql,      settings.REDASH_DS_BL,     offer_id=oid): "bl_data",
            pool.submit(_run, buyer_sql,   settings.REDASH_DS_BUYER,  offer_id=oid): "buyer_data",
            pool.submit(_run, mapping_sql, settings.REDASH_DS_SELLER, offer_id=oid): "seller_mapping",
        }
        stage1: dict[str, list[dict]] = {}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                stage1[name] = fut.result()
            except Exception as e:
                logger.warning("stage-1 query %s failed: %s", name, e)
                stage1[name] = []
    timings["stage1_secs"] = round(time.time() - t0, 2)

    if not stage1["bl_data"]:
        raise ValueError(f"No BL found for offer_id={oid}")

    # Pull mcat_id from stage 1
    mcat_id_raw = stage1["bl_data"][0].get("mapped_mcat_id")
    mcat_id = _int(mcat_id_raw, "mapped_mcat_id") if mcat_id_raw else None

    # ── Stage 2 — needs mcat_id (catalog + benchmark) + offer_id (sellers) ──
    t1 = time.time()
    catalog_sql  = _sql("buyer_specs.sql")
    benchmark_sql = _sql("sold_bl_benchmark.sql")
    details_sql  = _sql("seller_details.sql")

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures: dict = {}
        if mcat_id is not None:
            futures[pool.submit(_run, catalog_sql,  settings.REDASH_DS_MCATSPEC, mcat_id=mcat_id)] = "mcat_catalog"
            futures[pool.submit(_run, benchmark_sql, settings.REDASH_DS_MCATSPEC, mcat_id=mcat_id)] = "sold_benchmark"
        # seller_details lives on warehouse ds (im_dwh_rpt) — same ds id as catalog
        futures[pool.submit(_run, details_sql, settings.REDASH_DS_MCATSPEC, offer_id=oid)] = "seller_details"

        stage2: dict[str, list[dict]] = {}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                stage2[name] = fut.result()
            except Exception as e:
                logger.warning("stage-2 query %s failed: %s", name, e)
                stage2[name] = []
    timings["stage2_secs"] = round(time.time() - t1, 2)
    timings["total_secs"] = round(time.time() - t0, 2)

    return {
        "bl_data":         stage1["bl_data"],
        "buyer_data":      stage1["buyer_data"],
        "seller_mapping":  stage1["seller_mapping"],
        "mcat_catalog":    stage2.get("mcat_catalog", []),
        "sold_benchmark":  stage2.get("sold_benchmark", []),
        "seller_details":  stage2.get("seller_details", []),
        "timings":         timings,
    }
