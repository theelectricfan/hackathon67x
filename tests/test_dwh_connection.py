"""
DWH (Redshift) connection smoke test.

Runs a join across im_dwh_rpt.gl_gsm_master + im_dwh_rpt.dim_glusr_usr
against the bi-dwh-redshift-development cluster and prints the first
rows.  Doubles as a pytest test.

Run as a script:
    python tests/test_dwh_connection.py

Or via pytest:
    pytest tests/test_dwh_connection.py -v -s
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.dwh_client import dwh


SQL = """
SELECT
    gl.glusr_usr_id,
    gsm.gl_gsm_number
FROM im_dwh_rpt.gl_gsm_master gsm
JOIN im_dwh_rpt.dim_glusr_usr gl
    ON gsm.gl_gsm_number = gl.glusr_usr_im_gsm
WHERE gsm.gl_gsm_vendor_type NOT IN ('AR4X', 'KN4X')
  AND gl.custtype_is_paid = '0'
  AND gl.glusr_usr_custtype_id IN (17, 36, 6, 30, 29, 9, 20)
ORDER BY gl.glusr_usr_custtype_weight
LIMIT 25
"""


def fetch_rows():
    assert dwh is not None, "DWH client not initialised — check DWH_* in .env"
    return dwh.run_sql(SQL)


def test_dwh_connection():
    """Pytest entrypoint — fails loudly if Redshift is unreachable."""
    rows = fetch_rows()
    assert isinstance(rows, list)
    if rows:
        assert "glusr_usr_id" in rows[0]
        assert "gl_gsm_number" in rows[0]


if __name__ == "__main__":
    print("→ Redshift query (im_dwh_rpt.gl_gsm_master ⋈ dim_glusr_usr)")
    rows = fetch_rows()
    print(f"← {len(rows)} row(s) returned\n")
    for i, row in enumerate(rows, 1):
        print(f"  {i:>3}.  glusr_usr_id={row['glusr_usr_id']!s:<15}  "
              f"gl_gsm_number={row['gl_gsm_number']!s}")
