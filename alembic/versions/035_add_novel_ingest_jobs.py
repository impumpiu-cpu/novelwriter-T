"""Add dedicated novel ingest job table.

Deletion notes:
- Removes the request-owned upload parse/persist lifecycle as the canonical path.
- Introduces a dedicated ingest job row per novel so accepted uploads can be
  processed by worker-owned runtime lanes instead of the web request.

Rollback:
- `alembic downgrade 034`
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "novel_ingest_jobs" in tables:
        return

    op.create_table(
        "novel_ingest_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(length=20), nullable=False, server_default="accepted"),
        sa.Column("size_tier", sa.String(length=20), nullable=True),
        sa.Column("source_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_chars", sa.Integer(), nullable=True),
        sa.Column("chapter_count", sa.Integer(), nullable=True),
        sa.Column("requested_language", sa.String(length=50), nullable=True),
        sa.Column("resolved_language", sa.String(length=50), nullable=True),
        sa.Column("auto_index_plan", sa.String(length=20), nullable=True),
        sa.Column("bootstrap_plan", sa.String(length=30), nullable=True),
        sa.Column("readiness_mode", sa.String(length=30), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("lease_owner", sa.String(length=64), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", name="uq_novel_ingest_jobs_novel_id"),
    )
    op.create_index(
        "ix_novel_ingest_jobs_status_lease",
        "novel_ingest_jobs",
        ["status", "lease_expires_at"],
        unique=False,
    )

    dialect = bind.dialect.name if bind is not None else ""
    if dialect == "sqlite":
        with op.batch_alter_table("novel_ingest_jobs") as batch_op:
            batch_op.alter_column("status", server_default=None)
            batch_op.alter_column("stage", server_default=None)
            batch_op.alter_column("source_bytes", server_default=None)
    else:
        op.alter_column("novel_ingest_jobs", "status", server_default=None)
        op.alter_column("novel_ingest_jobs", "stage", server_default=None)
        op.alter_column("novel_ingest_jobs", "source_bytes", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "novel_ingest_jobs" not in tables:
        return

    indexes = {index["name"] for index in inspector.get_indexes("novel_ingest_jobs")}
    if "ix_novel_ingest_jobs_status_lease" in indexes:
        op.drop_index("ix_novel_ingest_jobs_status_lease", table_name="novel_ingest_jobs")
    op.drop_table("novel_ingest_jobs")
