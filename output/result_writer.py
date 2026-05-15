"""
Timestamped output storage.
Creates one directory per RCA run: output/results/YYYY-MM-DD_HH-MM-SS_<offer_id>/
Saves each layer as a separate JSON file.
"""
import json
import os
from datetime import datetime
from pathlib import Path


class ResultWriter:
    BASE_DIR = Path(__file__).parent / "results"

    def __init__(self, offer_id: str):
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.run_id = f"{ts}_{offer_id}"
        self.dir = self.BASE_DIR / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, stage: str, data: dict) -> str:
        path = self.dir / f"{stage}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
        return str(path)

    def save_text(self, stage: str, text: str) -> str:
        path = self.dir / f"{stage}.txt"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return str(path)

    def manifest(self) -> dict:
        files = sorted(self.dir.iterdir())
        return {
            "run_id": self.run_id,
            "output_dir": str(self.dir),
            "files": [f.name for f in files],
        }
