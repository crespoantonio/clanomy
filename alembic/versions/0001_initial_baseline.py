"""Initial baseline schema

Revision ID: 0001_initial_baseline
Revises: 
Create Date: 2026-08-26 10:38:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = '0001_initial_baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Family table
    op.create_table(
        'family',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notion_api_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notion_database_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notion_database_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notion_connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('plan_type', sqlmodel.sql.sqltypes.AutoString(), server_default='free', nullable=False),
        sa.Column('subscription_status', sqlmodel.sql.sqltypes.AutoString(), server_default='active', nullable=False),
        sa.Column('monthly_tx_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('telegram_payment_charge_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_family_notion_database_id'), 'family', ['notion_database_id'], unique=False)

    # 2. User table
    op.create_table(
        'user',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['family_id'], ['family.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_family_id'), 'user', ['family_id'], unique=False)
    op.create_index(op.f('ix_user_telegram_id'), 'user', ['telegram_id'], unique=True)

    # 3. Transaction table
    op.create_table(
        'transaction',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('concept', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('type', sqlmodel.sql.sqltypes.AutoString(length=7), server_default='expense', nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('notion_page_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notion_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['family_id'], ['family.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transaction_category'), 'transaction', ['category'], unique=False)
    op.create_index(op.f('ix_transaction_family_id'), 'transaction', ['family_id'], unique=False)
    op.create_index(op.f('ix_transaction_notion_page_id'), 'transaction', ['notion_page_id'], unique=False)
    op.create_index(op.f('ix_transaction_timestamp'), 'transaction', ['timestamp'], unique=False)
    op.create_index(op.f('ix_transaction_type'), 'transaction', ['type'], unique=False)
    op.create_index(op.f('ix_transaction_user_id'), 'transaction', ['user_id'], unique=False)

    # 4. FamilyInvite table
    op.create_table(
        'familyinvite',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('family_id', sa.Uuid(), nullable=False),
        sa.Column('created_by_user_id', sa.Uuid(), nullable=False),
        sa.Column('token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['user.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['family_id'], ['family.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_familyinvite_expires_at'), 'familyinvite', ['expires_at'], unique=False)
    op.create_index(op.f('ix_familyinvite_family_id'), 'familyinvite', ['family_id'], unique=False)
    op.create_index(op.f('ix_familyinvite_created_by_user_id'), 'familyinvite', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_familyinvite_token'), 'familyinvite', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_familyinvite_token'), table_name='familyinvite')
    op.drop_index(op.f('ix_familyinvite_created_by_user_id'), table_name='familyinvite')
    op.drop_index(op.f('ix_familyinvite_family_id'), table_name='familyinvite')
    op.drop_index(op.f('ix_familyinvite_expires_at'), table_name='familyinvite')
    op.drop_table('familyinvite')

    op.drop_index(op.f('ix_transaction_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_type'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_timestamp'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_notion_page_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_family_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_category'), table_name='transaction')
    op.drop_table('transaction')

    op.drop_index(op.f('ix_user_telegram_id'), table_name='user')
    op.drop_index(op.f('ix_user_family_id'), table_name='user')
    op.drop_table('user')

    op.drop_index(op.f('ix_family_notion_database_id'), table_name='family')
    op.drop_table('family')
