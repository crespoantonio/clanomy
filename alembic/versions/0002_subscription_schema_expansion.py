"""Subscription schema expansion for trials and quota tracking

Revision ID: 0002_subscription_schema_expansion
Revises: 0001_initial_baseline
Create Date: 2026-08-26 13:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '0002_subscription_schema_expansion'
down_revision: Union[str, None] = '0001_initial_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Family table new columns
    op.add_column('family', sa.Column('last_reset_month', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.add_column('family', sa.Column('max_members', sa.Integer(), server_default='5', nullable=False))
    op.add_column('family', sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('family', sa.Column('notified_day_50', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('family', sa.Column('notified_day_60', sa.Boolean(), server_default='false', nullable=False))

    # User table new columns
    op.add_column('user', sa.Column('has_used_trial', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('user', 'has_used_trial')
    op.drop_column('family', 'notified_day_60')
    op.drop_column('family', 'notified_day_50')
    op.drop_column('family', 'trial_ends_at')
    op.drop_column('family', 'max_members')
    op.drop_column('family', 'last_reset_month')
