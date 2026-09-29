"""Remove Lemon Squeezy subscription fields from Family model

Revision ID: 0011_remove_lemonsqueezy_fields
Revises: 0010_add_family_daily_tx_count
Create Date: 2026-09-04 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0011_remove_lemonsqueezy_fields'
down_revision: Union[str, None] = '0010_add_family_daily_tx_count'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('family') as batch_op:
        batch_op.drop_index('ix_family_lemonsqueezy_subscription_id')
        batch_op.drop_index('ix_family_lemonsqueezy_customer_id')
        batch_op.drop_column('lemonsqueezy_subscription_id')
        batch_op.drop_column('lemonsqueezy_customer_id')


def downgrade() -> None:
    with op.batch_alter_table('family') as batch_op:
        batch_op.add_column(sa.Column('lemonsqueezy_customer_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('lemonsqueezy_subscription_id', sa.String(), nullable=True))
        batch_op.create_index('ix_family_lemonsqueezy_customer_id', ['lemonsqueezy_customer_id'], unique=False)
        batch_op.create_index('ix_family_lemonsqueezy_subscription_id', ['lemonsqueezy_subscription_id'], unique=False)
