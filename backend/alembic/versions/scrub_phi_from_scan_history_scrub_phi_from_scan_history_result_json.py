"""scrub phi from scan history result_json

Revision ID: scrub_phi_from_scan_history
Revises: 518f2aab47ed
Create Date: 2026-05-09

"""

from __future__ import annotations

import json
from typing import Union

from alembic import op
from sqlalchemy import text

revision: str = "scrub_phi_from_scan_history"
down_revision: Union[str, None] = "518f2aab47ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        text("SELECT id, result_json FROM scan_history WHERE result_json IS NOT NULL")
    )
    rows = result.fetchall()

    updated = 0
    for row_id, result_json_raw in rows:
        if isinstance(result_json_raw, str):
            try:
                data = json.loads(result_json_raw)
            except (ValueError, TypeError):
                continue
        elif isinstance(result_json_raw, dict):
            data = result_json_raw
        else:
            continue

        if isinstance(data, dict) and "personalized_insights" in data:
            data.pop("personalized_insights")
            bind.execute(
                text("UPDATE scan_history SET result_json = :json WHERE id = :id"),
                {"json": json.dumps(data), "id": row_id},
            )
            updated += 1

    print(f"\n[migration] Scrubbed personalized_insights from {updated} scan_history rows")


def downgrade() -> None:
    pass  # PHI removal is intentional and irreversible
