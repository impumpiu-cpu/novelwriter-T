"""Add continuation_runs for stream/fallback idempotency.

Deletion notes:
- Continuation generation no longer treats the stream request and its sync
  fallback as independent billable runs. The durable request row is the
  canonical ownership boundary for one generation attempt.
- Removes the old implicit contract where a transport retry could create a
  second continuation set and a second quota reservation.

Rollback:
- `alembic downgrade 033`
- `git revert <commit>`

Revision ID: 034
Revises: 033
Create Date: 2026-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "continuation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("client_request_id", sa.String(length=64), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("claim_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("continuation_ids", sa.JSON(), nullable=True),
        sa.Column("debug_summary", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "novel_id", "client_request_id", name="uq_continuation_runs_user_novel_request"),
    )
    op.create_index("ix_continuation_runs_novel_status", "continuation_runs", ["novel_id", "status"])

    with op.batch_alter_table("continuation_runs") as batch_op:
        batch_op.alter_column(
            "delivered_count",
            existing_type=sa.Integer(),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    op.drop_index("ix_continuation_runs_novel_status", table_name="continuation_runs")
    op.drop_table("continuation_runs")
