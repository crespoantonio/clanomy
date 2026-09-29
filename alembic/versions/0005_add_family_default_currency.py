"""Add default_currency to Family model

Revision ID: 0005_add_family_default_currency
Revises: 0004_enable_rls_security
Create Date: 2026-08-31 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005_add_family_default_currency'
down_revision: Union[str, None] = '0004_enable_rls_security'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('family', sa.Column('default_currency', sa.String(length=3), server_default='USD', nullable=False))


def downgrade() -> None:
    op.drop_column('family', 'default_currency')
