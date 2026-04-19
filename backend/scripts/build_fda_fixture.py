"""Build data/seed/fda_eafus_fixture.xlsx from the curated additives.json.

Run once (or whenever additives.json["fda_eafus"] is updated):
    cd backend && python -m scripts.build_fda_fixture
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from openpyxl import Workbook

SEED_JSON = Path(__file__).parents[1] / "data" / "seed" / "additives.json"
OUTPUT = Path(__file__).parents[1] / "data" / "seed" / "fda_eafus_fixture.xlsx"


def main() -> int:
    data = json.loads(SEED_JSON.read_text())
    fda_records = data.get("fda_eafus", [])

    wb = Workbook()
    ws = wb.active
    ws.title = "EAFUS"
    ws.append(["Substance", "CAS Reg No. (or other ID)", "Status"])
    for rec in fda_records:
        ws.append([
            rec.get("canonical_name", ""),
            rec.get("cas_number") or "",
            rec.get("status", "APPROVED"),
        ])

    wb.save(OUTPUT)
    print(f"✓ Written {len(fda_records)} records to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
