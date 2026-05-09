"""add enrichment fields to products

Revision ID: 518f2aab47ed
Revises: aabbc492fe8d
Create Date: 2026-05-09

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "518f2aab47ed"
down_revision: str | None = "aabbc492fe8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.add_column(sa.Column("ingredients_json", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("ingredients_source", sa.String(length=20), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ingredients_confidence", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "needs_barcode_link",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    op.create_index(
        "idx_products_needs_barcode_link",
        "products",
        ["needs_barcode_link"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_products_needs_barcode_link", table_name="products")
    with op.batch_alter_table("products", schema=None) as batch_op:
        batch_op.drop_column("needs_barcode_link")
        batch_op.drop_column("ingredients_confidence")
        batch_op.drop_column("ingredients_source")
        batch_op.drop_column("ingredients_json")
