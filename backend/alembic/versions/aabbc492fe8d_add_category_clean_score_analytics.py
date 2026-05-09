"""add_category_clean_score_analytics

Revision ID: aabbc492fe8d
Revises: a3f7c2d1e845
Create Date: 2026-05-08 21:13:22.647549

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "aabbc492fe8d"
down_revision: Union[str, None] = "a3f7c2d1e845"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(100), nullable=True))
        batch_op.add_column(
            sa.Column(
                "clean_score",
                sa.SmallInteger(),
                nullable=False,
                server_default="0",
            )
        )

    op.create_index("idx_products_category", "products", ["category"])
    op.create_index("idx_products_clean_score", "products", ["clean_score"])

    op.create_table(
        "analytics_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("idx_analytics_user", "analytics_events", ["user_id"])
    op.create_index("idx_analytics_event", "analytics_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("idx_analytics_event", table_name="analytics_events")
    op.drop_index("idx_analytics_user", table_name="analytics_events")
    op.drop_table("analytics_events")
    op.drop_index("idx_products_clean_score", table_name="products")
    op.drop_index("idx_products_category", table_name="products")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("clean_score")
        batch_op.drop_column("category")
