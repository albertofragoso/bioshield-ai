"""merge_heads_before_waitlist

Revision ID: b99d9a6cbc0e
Revises: 7e1140260890, b7493142c951
Create Date: 2026-05-23 09:02:06.465085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b99d9a6cbc0e'
down_revision: Union[str, None] = ('7e1140260890', 'b7493142c951')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
