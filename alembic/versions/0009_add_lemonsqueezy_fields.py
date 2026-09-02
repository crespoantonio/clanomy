"""Add Lemon Squeezy subscription fields to Family model

Revision ID: 0009_add_lemonsqueezy_fields
Revises: 0008_add_timezone_support
Create Date: 2026-09-02 08:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0009_add_lemonsqueezy_fields'
down_revision: Union[str, None] = '0008_add_timezone_support'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('family', sa.Column('lemonsqueezy_customer_id', sa.String(), nullable=True))
    op.add_column('family', sa.Column('lemonsqueezy_subscription_id', sa.String(), nullable=True))
    op.add_column('family', sa.Column('customer_portal_url', sa.String(), nullable=True))
    op.create_index(op.f('ix_family_lemonsqueezy_customer_id'), 'family', ['lemonsqueezy_customer_id'], unique=False)
    op.create_index(op.f('ix_family_lemonsqueezy_subscription_id'), 'family', ['lemonsqueezy_subscription_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_family_lemonsqueezy_subscription_id'), table_name='family')
    op.drop_index(op.f('ix_family_lemonsqueezy_customer_id'), table_name='family')
    op.drop_column('family', 'customer_portal_url')
    op.drop_column('family', 'lemonsqueezy_subscription_id')
    op.drop_column('family', 'lemonsqueezy_customer_id')
