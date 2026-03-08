"""merge_b1c2_and_d2e3

Revision ID: 4d0e491c6f8f
Revises: b1c2d3e4f5a6, d2e3f4a5b6c7
Create Date: 2026-03-08 16:25:40.861521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d0e491c6f8f'
down_revision: Union[str, Sequence[str], None] = ('b1c2d3e4f5a6', 'd2e3f4a5b6c7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
