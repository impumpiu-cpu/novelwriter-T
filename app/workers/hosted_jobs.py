from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.core.ingest import (
    enqueue_next_deferred_window_index_build,
    run_next_novel_ingest_job,
)
from app.core.indexing.lifecycle import run_next_window_index_rebuild_job
from app.core.world.bootstrap_application import run_next_bootstrap_job
from app.database import SessionLocal, init_db
from app.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def run_worker_loop(*, once: bool = False) -> int:
    settings = get_settings()
    configure_logging(is_production=settings.is_production)
    init_db()
    logger.info("hosted_jobs: worker started")

    idle_cycles = 0
    while True:
        did_work = False
        did_work = run_next_novel_ingest_job(session_factory=SessionLocal, settings=settings) or did_work
        if not did_work:
            did_work = enqueue_next_deferred_window_index_build(
                session_factory=SessionLocal,
                settings=settings,
            ) or did_work
        did_work = run_next_window_index_rebuild_job(session_factory=SessionLocal, settings=settings) or did_work
        did_work = run_next_bootstrap_job(session_factory=SessionLocal, settings=settings) or did_work

        if once:
            return 0

        if did_work:
            idle_cycles = 0
            continue

        idle_cycles += 1
        if idle_cycles == 1 or idle_cycles % 30 == 0:
            logger.debug("hosted_jobs: idle")
        time.sleep(max(float(settings.hosted_job_worker_poll_seconds or 0.0), 0.25))


def main() -> int:
    return run_worker_loop(once=False)


if __name__ == "__main__":
    raise SystemExit(main())
