"""Add terms_accepted and terms_accepted_at to User model

Revision ID: 0012_add_user_terms_accepted
Revises: 0011_remove_lemonsqueezy_fields
Create Date: 2026-09-07 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0012_add_user_terms_accepted'
down_revision: Union[str, None] = '0011_remove_lemonsqueezy_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(sa.Column('terms_accepted', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('terms_accepted_at')
        batch_op.drop_column('terms_accepted')
