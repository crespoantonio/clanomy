"""Add timezone support to Family and User models
 
Revision ID: 0008_add_timezone_support
Revises: 0007_enable_scheduled_bill_rls
Create Date: 2026-09-02 01:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0008_add_timezone_support'
down_revision: Union[str, None] = '0007_enable_scheduled_bill_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('family', sa.Column('timezone', sa.String(length=50), server_default='America/Argentina/Buenos_Aires', nullable=False))
    op.add_column('user', sa.Column('timezone', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'timezone')
    op.drop_column('family', 'timezone')
