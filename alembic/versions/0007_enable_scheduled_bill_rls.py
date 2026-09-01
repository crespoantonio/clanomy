"""Enable RLS for scheduled_bill table

Revision ID: 0007_enable_scheduled_bill_rls
Revises: 0006_add_scheduled_bill
Create Date: 2026-09-01 15:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0007_enable_scheduled_bill_rls'
down_revision: Union[str, None] = '0006_add_scheduled_bill'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE scheduled_bill ENABLE ROW LEVEL SECURITY;")
        op.execute("REVOKE ALL ON TABLE scheduled_bill FROM anon, authenticated;")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE scheduled_bill DISABLE ROW LEVEL SECURITY;")
        op.execute("GRANT ALL ON TABLE scheduled_bill TO anon, authenticated;")
