"""Add Paddle subscription fields and processed_webhook table

Revision ID: 0013_paddle_subscriptions
Revises: 0012_add_user_terms_accepted
Create Date: 2026-09-09 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0013_paddle_subscriptions'
down_revision: Union[str, None] = '0012_add_user_terms_accepted'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add Paddle columns to family table
    with op.batch_alter_table('family') as batch_op:
        batch_op.add_column(sa.Column('paddle_customer_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('paddle_subscription_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('paddle_price_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('scheduled_change_action', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('scheduled_change_effective_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index('ix_family_paddle_customer_id', ['paddle_customer_id'], unique=False)
        batch_op.create_index('ix_family_paddle_subscription_id', ['paddle_subscription_id'], unique=False)

    # 2. Create processed_webhook table for idempotency
    op.create_table(
        'processed_webhook',
        sa.Column('event_id', sa.String(length=100), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index('ix_processed_webhook_event_type', 'processed_webhook', ['event_type'], unique=False)
    op.create_index('ix_processed_webhook_received_at', 'processed_webhook', ['received_at'], unique=False)

    # 3. Enable RLS on PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE processed_webhook ENABLE ROW LEVEL SECURITY;")
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON TABLE processed_webhook FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON TABLE processed_webhook FROM authenticated;
                END IF;
            END
            $$;
        """)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    GRANT ALL ON TABLE processed_webhook TO anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    GRANT ALL ON TABLE processed_webhook TO authenticated;
                END IF;
            END
            $$;
        """)
        op.execute("ALTER TABLE processed_webhook DISABLE ROW LEVEL SECURITY;")

    op.drop_index('ix_processed_webhook_received_at', table_name='processed_webhook')
    op.drop_index('ix_processed_webhook_event_type', table_name='processed_webhook')
    op.drop_table('processed_webhook')

    with op.batch_alter_table('family') as batch_op:
        batch_op.drop_index('ix_family_paddle_subscription_id')
        batch_op.drop_index('ix_family_paddle_customer_id')
        batch_op.drop_column('scheduled_change_effective_at')
        batch_op.drop_column('scheduled_change_action')
        batch_op.drop_column('paddle_price_id')
        batch_op.drop_column('paddle_subscription_id')
        batch_op.drop_column('paddle_customer_id')
