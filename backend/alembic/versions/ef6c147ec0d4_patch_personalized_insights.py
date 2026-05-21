"""patch_personalized_insights

Revision ID: ef6c147ec0d4
Revises: 40b89212052d
Create Date: 2026-05-19 21:36:16.964451

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef6c147ec0d4'
down_revision: Union[str, None] = '40b89212052d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("""
            UPDATE scan_history
            SET result_json = (result_json::jsonb || '{"personalized_insights":[]}'::jsonb)
            WHERE result_json IS NOT NULL
              AND (result_json::jsonb -> 'personalized_insights') IS NULL
        """)
    else:
        op.execute("""
            UPDATE scan_history
            SET result_json = JSON_SET(result_json, '$.personalized_insights', JSON_ARRAY())
            WHERE JSON_EXTRACT(result_json, '$.personalized_insights') IS NULL
              AND result_json IS NOT NULL
        """)


def downgrade() -> None:
    pass  # Non-destructive — no schema change to revert
