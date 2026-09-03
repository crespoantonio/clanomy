"""Add daily_tx_count to Family model

Revision ID: 0010_add_family_daily_tx_count
Revises: 0009_add_lemonsqueezy_fields
Create Date: 2026-09-03 10:37:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0010_add_family_daily_tx_count'
down_revision: Union[str, None] = '0009_add_lemonsqueezy_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'family',
        sa.Column('daily_tx_count', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('family', 'daily_tx_count')
