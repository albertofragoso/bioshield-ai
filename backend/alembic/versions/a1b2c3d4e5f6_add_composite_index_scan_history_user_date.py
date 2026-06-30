"""add composite index scan_history user_date

Revision ID: a1b2c3d4e5f6
Revises: 383e457f2a26
Create Date: 2026-06-26 00:00:00.000000

Speeds up paginated history queries: SELECT ... WHERE user_id=X ORDER BY scanned_at DESC
"""

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "383e457f2a26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_scan_history_user_date",
        "scan_history",
        ["user_id", "scanned_at"],
        postgresql_ops={"scanned_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_scan_history_user_date", table_name="scan_history")
