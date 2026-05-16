"""
CLI entrypoint — fetches BLs from Redash by offer_id and runs RCA.

  python main.py --offer-id 142052799067
  python main.py --offer-id 142052799067,142055263895,142055215246
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.bl_context_builder_redash import build_bl_context_from_redash
from core.orchestrator import run_rca
from output.digest_generator import generate_weekly_digest
from output.report_generator import generate_bl_card


def process_offer_ids(offer_ids: list[int], output_dir: str = "output/results") -> list[dict]:
    os.makedirs(output_dir, exist_ok=True)
    print(f"Fetching {len(offer_ids)} BL(s) from Redash...")

    all_results, cards = [], []
    for i, oid in enumerate(offer_ids, 1):
        print(f"[{i}/{len(offer_ids)}] offer_id={oid}")
        try:
            ctx = build_bl_context_from_redash(oid)
            result = run_rca(ctx)
            all_results.append(result)
            cards.append(generate_bl_card(result))
            print(f"  → {result.get('primary_bucket')} ({result.get('primary_confidence')}%)")
        except Exception as e:
            print(f"  ERROR: {e}")
            all_results.append({"offer_id": str(oid), "error": str(e)})

    cards_path = os.path.join(output_dir, "bl_cards.txt")
    Path(cards_path).write_text("\n\n".join(cards), encoding="utf-8")
    print(f"\nBL cards saved to {cards_path}")

    digest = generate_weekly_digest(all_results)
    digest_path = os.path.join(output_dir, "weekly_digest.txt")
    Path(digest_path).write_text(digest, encoding="utf-8")
    print(f"Weekly digest saved to {digest_path}")
    print("\n" + digest)

    json_path = os.path.join(output_dir, "rca_results.json")
    Path(json_path).write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")
    print(f"Raw JSON saved to {json_path}")
    return all_results


def _parse_offer_ids(arg: str) -> list[int]:
    return [int(x.strip()) for x in arg.split(",") if x.strip()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BL RCA pipeline (Redash-backed)")
    parser.add_argument("--offer-id", required=True,
                        help="Offer id or comma-separated list of offer ids")
    parser.add_argument("--output", default="output/results", help="Output directory")
    args = parser.parse_args()

    process_offer_ids(_parse_offer_ids(args.offer_id), args.output)
