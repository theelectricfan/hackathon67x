"""
Redash connection smoke test.

Runs `select * from glusr_usr limit 3` against pg-imblr-prod-live
(data source id 16 on https://redash.intermesh.net) and prints the
rows.  Doubles as a pytest test.

Run as a script:
    python tests/test_redash_connection.py

Or via pytest:
    pytest tests/test_redash_connection.py -v -s
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.redash_client import redash


DATA_SOURCE_ID = 16  # pg-imblr-prod-live
SQL = "select * from glusr_usr limit 3"


def fetch_rows():
    assert redash is not None, "Redash client not initialised — check REDASH_API_KEY in .env"
    return redash.run_sql(SQL, data_source_id=DATA_SOURCE_ID)


def test_redash_connection():
    """Pytest entrypoint — fails loudly if Redash is unreachable."""
    rows = fetch_rows()
    assert isinstance(rows, list)
    assert len(rows) <= 3
    if rows:
        assert isinstance(rows[0], dict)


if __name__ == "__main__":
    print(f"→ POST /api/query_results  (ds={DATA_SOURCE_ID}, sql={SQL!r})")
    rows = fetch_rows()
    print(f"← {len(rows)} row(s) returned\n")
    for i, row in enumerate(rows, 1):
        print(f"── row {i} ──")
        for k, v in row.items():
            val = str(v)
            if len(val) > 80:
                val = val[:77] + "..."
            print(f"  {k:<35} {val}")
        print()
