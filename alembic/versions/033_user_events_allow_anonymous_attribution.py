"""Allow anonymous pre-signup analytics events.

Revision ID: 033
Revises: 032
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '033'
down_revision: Union[str, None] = '032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('user_events') as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    bind = op.get_bind()
    orphan_count = bind.execute(sa.text('SELECT COUNT(*) FROM user_events WHERE user_id IS NULL')).scalar_one()
    if orphan_count:
        raise RuntimeError('Cannot downgrade user_events.user_id to NOT NULL while anonymous events exist')

    with op.batch_alter_table('user_events') as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
