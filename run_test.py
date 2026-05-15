"""
Quick test runner — processes the dummy data and prints full RCA result.

Usage:
  python run_test.py
"""
import sys
import json
import io
from pathlib import Path

# Force UTF-8 stdout on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

DATA_DIR = Path("data/dummy testing data")

BL_CSV     = str(DATA_DIR / "bl_data.csv")
BUYER_CSV  = str(DATA_DIR / "buyer_data.csv")
SELLER_CSV = str(DATA_DIR / "seller_data.csv")
SPECS_CSV  = str(DATA_DIR / "buyer_specs_data.csv")


def main():
    from core.bl_context_builder import build_bl_context
    from core.orchestrator import run_rca

    print("\n" + "=" * 58)
    print("  BL RCA Agent — Test Run")
    print("=" * 58)

    # ── Step 1: Build context ──────────────────────────────────────
    print("\n[1/3] Building BL context from CSVs...")
    ctx = build_bl_context(BL_CSV, BUYER_CSV, SELLER_CSV, SPECS_CSV)

    print(f"  [OK] Offer ID    : {ctx['offer_id']}")
    print(f"  [OK] Title       : {ctx['offer_name']}")
    print(f"  [OK] MCAT        : {ctx['mapped_mcat_name']} ({ctx['mapped_mcat_id']})")
    print(f"  [OK] Specs filled: {ctx['specs_fill_count']} -> {ctx['specs_filled']}")
    print(f"  [OK] AOV blank   : {ctx['aov_blank']}")
    print(f"  [OK] Seller pool : {len(ctx['seller_pool'])} sellers")
    print(f"  [OK] First-timer : {ctx['is_first_time_buyer']}")
    print(f"  [OK] City mismatch: {ctx['city_mismatch']}")
    print(f"  [OK] Sells competing: {ctx['sells_competing']}")

    # ── Step 2: Run RCA ────────────────────────────────────────────
    print("\n[2/3] Running RCA agent (all 5 skills)...")
    result = run_rca(ctx)

    # ── Step 3: Print results ──────────────────────────────────────
    print("\n[3/3] Results\n")
    print("  BUCKET SCORES")
    print("  " + "─" * 40)
    for bucket, score in sorted(
        result["bucket_scores"].items(), key=lambda x: x[1], reverse=True
    ):
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"  {bucket:<28} [{bar}] {score}%")

    print(f"\n  [PRIMARY]   : {result['primary_bucket']} ({result['primary_confidence']}%)")
    print(f"     Fix      : {result['primary_fix']}")
    if result.get("secondary_bucket"):
        print(f"\n  [SECONDARY] : {result['secondary_bucket']} ({result['secondary_confidence']}%)")
        print(f"     Fix      : {result['secondary_fix']}")

    print(f"\n  Output saved to: {result['output_dir']}")
    print("\n" + "=" * 58)

    # Full JSON dump
    safe = {k: v for k, v in result.items() if k != "all_skill_results"}
    print("\n--- Full Result JSON ---")
    print(json.dumps(safe, indent=2, default=str))


if __name__ == "__main__":
    main()
