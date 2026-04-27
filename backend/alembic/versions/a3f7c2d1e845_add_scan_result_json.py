"""add_scan_result_json

Revision ID: a3f7c2d1e845
Revises: 91b0a38b0422
Create Date: 2026-04-26 00:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa

from alembic import op

revision: str = "a3f7c2d1e845"
down_revision: Union[str, None] = "91b0a38b0422"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scan_history", schema=None) as batch_op:
        batch_op.add_column(sa.Column("result_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scan_history", schema=None) as batch_op:
        batch_op.drop_column("result_json")
