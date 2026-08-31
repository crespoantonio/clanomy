"""Enable RLS and lock down public schema for Supabase security compliance

Revision ID: 0004_enable_rls_security
Revises: 0003_add_user_is_admin
Create Date: 2026-08-31 14:04:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0004_enable_rls_security'
down_revision: Union[str, None] = '0003_add_user_is_admin'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        tables = ['alembic_version', 'family', 'familyinvite', '"transaction"', '"user"']
        for table in tables:
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
            
        # Revoke public PostgREST API access from anon and authenticated roles
        op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;")
        op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;")
        op.execute("REVOKE ALL ON ALL ROUTINES IN SCHEMA public FROM anon, authenticated;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        tables = ['alembic_version', 'family', 'familyinvite', '"transaction"', '"user"']
        for table in tables:
            op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.execute("GRANT ALL ON ALL TABLES IN SCHEMA public TO anon, authenticated;")
        op.execute("GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO anon, authenticated;")
        op.execute("GRANT ALL ON ALL ROUTINES IN SCHEMA public TO anon, authenticated;")
