"""Add is_admin to user table

Revision ID: 0003_add_user_is_admin
Revises: 0002_subscription_schema
Create Date: 2026-08-31 14:02:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0003_add_user_is_admin'
down_revision: Union[str, None] = '0002_subscription_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('user', 'is_admin')
