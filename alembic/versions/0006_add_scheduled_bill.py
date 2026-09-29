"""Add ScheduledBill model

Revision ID: 0006_add_scheduled_bill
Revises: 0005_add_family_default_currency
Create Date: 2026-09-01 10:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '0006_add_scheduled_bill'
down_revision: Union[str, None] = '0005_add_family_default_currency'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_bill',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('concept', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(length=15), server_default='pending', nullable=False),
        sa.Column('paid_transaction_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['family.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['paid_transaction_id'], ['transaction.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_bill_family_id'), 'scheduled_bill', ['family_id'], unique=False)
    op.create_index(op.f('ix_scheduled_bill_user_id'), 'scheduled_bill', ['user_id'], unique=False)
    op.create_index(op.f('ix_scheduled_bill_category'), 'scheduled_bill', ['category'], unique=False)
    op.create_index(op.f('ix_scheduled_bill_due_date'), 'scheduled_bill', ['due_date'], unique=False)
    op.create_index(op.f('ix_scheduled_bill_status'), 'scheduled_bill', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_scheduled_bill_status'), table_name='scheduled_bill')
    op.drop_index(op.f('ix_scheduled_bill_due_date'), table_name='scheduled_bill')
    op.drop_index(op.f('ix_scheduled_bill_category'), table_name='scheduled_bill')
    op.drop_index(op.f('ix_scheduled_bill_user_id'), table_name='scheduled_bill')
    op.drop_index(op.f('ix_scheduled_bill_family_id'), table_name='scheduled_bill')
    op.drop_table('scheduled_bill')
