"""Backfill bootstrap initialized column as the only runtime truth.

Deletion notes:
- Removes runtime legacy inference from `bootstrap_jobs.result/status/mode` when
  deciding whether a novel has been bootstrap-initialized.
- Promotes `bootstrap_jobs.initialized` to the sole contract consumed by API,
  queue admission, and frontend gating logic.

Rollback:
- `alembic downgrade 036`
- `git revert <commit>`
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "bootstrap_jobs" not in tables:
        return
    connection = bind.connect() if isinstance(bind, sa.Engine) else bind
    bootstrap_jobs = sa.table(
        "bootstrap_jobs",
        sa.column("id", sa.Integer()),
        sa.column("mode", sa.String(length=20)),
        sa.column("status", sa.String(length=20)),
        sa.column("initialized", sa.Boolean()),
        sa.column("result", sa.JSON()),
    )

    try:
        completed_rows = connection.execute(
            sa.select(
                bootstrap_jobs.c.id,
                bootstrap_jobs.c.mode,
                bootstrap_jobs.c.status,
                bootstrap_jobs.c.result,
            )
            .where(bootstrap_jobs.c.initialized == sa.false())
        ).all()
    finally:
        if connection is not bind:
            connection.close()

    ids_to_initialize = [
        row.id
        for row in completed_rows
        if row.status == "completed" and (
            row.mode in {"initial", "reextract"}
            or not bool((row.result or {}).get("index_refresh_only", False))
        )
    ]
    if not ids_to_initialize:
        return

    op.execute(
        bootstrap_jobs.update()
        .where(bootstrap_jobs.c.id.in_(ids_to_initialize))
        .values(initialized=True)
    )


def downgrade() -> None:
    # Data backfill only. Downgrade leaves current values in place.
    return None
