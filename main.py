import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.bl_context_builder import load_bls_from_csv
from core.orchestrator import run_rca
from output.report_generator import generate_bl_card
from output.digest_generator import generate_weekly_digest


def process_csv(filepath: str, output_dir: str = "output/results"):
    os.makedirs(output_dir, exist_ok=True)
    bls = load_bls_from_csv(filepath)
    print(f"Loaded {len(bls)} BLs from {filepath}")

    all_results = []
    cards = []

    for i, bl_ctx in enumerate(bls, 1):
        bl_id = bl_ctx.get("eto_ofr_display_id", f"BL-{i}")
        print(f"[{i}/{len(bls)}] Running RCA for {bl_id}...")
        try:
            result = run_rca(bl_ctx)
            all_results.append(result)
            card = generate_bl_card(result, bl_ctx)
            cards.append(card)
            print(f"  → {result.get('primary_bucket')} ({result.get('primary_confidence')}%)")
        except Exception as e:
            print(f"  ERROR: {e}")
            all_results.append({"bl_id": str(bl_id), "error": str(e)})

    cards_path = os.path.join(output_dir, "bl_cards.txt")
    with open(cards_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(cards))
    print(f"\nBL cards saved to {cards_path}")

    digest = generate_weekly_digest(all_results)
    digest_path = os.path.join(output_dir, "weekly_digest.txt")
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(digest)
    print(f"Weekly digest saved to {digest_path}")
    print("\n" + digest)

    json_path = os.path.join(output_dir, "rca_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"Raw JSON saved to {json_path}")

    return all_results


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/sample_unsold_bls.csv"
    process_csv(csv_path)
