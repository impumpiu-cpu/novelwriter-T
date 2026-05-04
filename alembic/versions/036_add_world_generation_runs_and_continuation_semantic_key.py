"""Add durable semantic admission rows for generation endpoints.

Deletion notes:
- Removes the hidden contract where duplicate continuation/world-generation
  clicks could queue behind in-process locks and execute later as separate runs.
- Promotes durable active-run admission to the canonical backend boundary for
  duplicate-click fast-fail semantics.

Rollback:
- `alembic downgrade 035`
- `git revert <commit>`
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "continuation_runs" in tables:
        continuation_columns = {column["name"] for column in inspector.get_columns("continuation_runs")}
        if "semantic_key" not in continuation_columns:
            with op.batch_alter_table("continuation_runs") as batch_op:
                batch_op.add_column(sa.Column("semantic_key", sa.String(length=64), nullable=True))
        continuation_indexes = {index["name"] for index in inspector.get_indexes("continuation_runs")}
        if "uq_continuation_runs_active_semantic" not in continuation_indexes:
            op.create_index(
                "uq_continuation_runs_active_semantic",
                "continuation_runs",
                ["user_id", "novel_id", "semantic_key"],
                unique=True,
                sqlite_where=sa.text("semantic_key IS NOT NULL AND status = 'running'"),
                postgresql_where=sa.text("semantic_key IS NOT NULL AND status = 'running'"),
            )

    if "world_generation_runs" in tables:
        return

    op.create_table(
        "world_generation_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("claim_token", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_world_generation_runs_novel_status",
        "world_generation_runs",
        ["novel_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_world_generation_runs_active_user_novel",
        "world_generation_runs",
        ["user_id", "novel_id"],
        unique=True,
        sqlite_where=sa.text("status = 'running'"),
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "world_generation_runs" in tables:
        world_indexes = {index["name"] for index in inspector.get_indexes("world_generation_runs")}
        if "uq_world_generation_runs_active_user_novel" in world_indexes:
            op.drop_index(
                "uq_world_generation_runs_active_user_novel",
                table_name="world_generation_runs",
            )
        if "ix_world_generation_runs_novel_status" in world_indexes:
            op.drop_index("ix_world_generation_runs_novel_status", table_name="world_generation_runs")
        op.drop_table("world_generation_runs")

    if "continuation_runs" in tables:
        continuation_indexes = {index["name"] for index in inspector.get_indexes("continuation_runs")}
        if "uq_continuation_runs_active_semantic" in continuation_indexes:
            op.drop_index("uq_continuation_runs_active_semantic", table_name="continuation_runs")
        continuation_columns = {column["name"] for column in inspector.get_columns("continuation_runs")}
        if "semantic_key" in continuation_columns:
            with op.batch_alter_table("continuation_runs") as batch_op:
                batch_op.drop_column("semantic_key")
