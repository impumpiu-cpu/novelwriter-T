from __future__ import annotations

import logging
import threading
import uuid
from typing import Callable, Protocol, TypeVar

ClaimT = TypeVar("ClaimT")
BuildOutputT = TypeVar("BuildOutputT")


class JobRunnerAdapter(Protocol[ClaimT, BuildOutputT]):
    def build(self, *, claim: ClaimT) -> BuildOutputT: ...

    def finalize_success(
        self,
        *,
        claim: ClaimT,
        build_output: BuildOutputT,
    ) -> bool: ...

    def finalize_failure(
        self,
        *,
        claim: ClaimT,
        error: str,
    ) -> bool: ...

    def sanitize_error(self, exc: Exception) -> str: ...

    def format_failure(self, claim: ClaimT) -> str: ...


def _resolve_heartbeat_interval_seconds(*, adapter: object, claim: ClaimT) -> float:
    interval_resolver = getattr(adapter, "heartbeat_interval_seconds", None)
    if not callable(interval_resolver):
        return 0.0
    interval_seconds = float(interval_resolver(claim=claim))
    return max(interval_seconds, 0.0)


def _start_claim_heartbeat(
    *,
    adapter: object,
    claim: ClaimT,
    logger: logging.Logger,
) -> tuple[threading.Event, threading.Thread] | None:
    heartbeat = getattr(adapter, "heartbeat", None)
    if not callable(heartbeat):
        return None

    interval_seconds = _resolve_heartbeat_interval_seconds(adapter=adapter, claim=claim)
    if interval_seconds <= 0:
        return None

    stop_event = threading.Event()

    def _run() -> None:
        while not stop_event.wait(interval_seconds):
            try:
                keep_lease = bool(heartbeat(claim=claim))
            except Exception:
                logger.warning("Background job heartbeat refresh failed", exc_info=True)
                continue
            if keep_lease:
                continue
            logger.warning("Background job heartbeat lost lease ownership")
            return

    thread = threading.Thread(
        target=_run,
        name="job-heartbeat",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


def run_job_until_idle(
    *,
    claim_next: Callable[[str], ClaimT | None],
    adapter: JobRunnerAdapter[ClaimT, BuildOutputT],
    logger: logging.Logger,
) -> bool:
    worker_id = uuid.uuid4().hex
    handled_work = False

    while True:
        claim = claim_next(worker_id)
        if claim is None:
            return handled_work
        handled_work = True

        heartbeat_state = _start_claim_heartbeat(adapter=adapter, claim=claim, logger=logger)
        try:
            build_output = adapter.build(claim=claim)
        except Exception as exc:
            if heartbeat_state is not None:
                stop_event, thread = heartbeat_state
                stop_event.set()
                thread.join(timeout=1.0)
            logger.exception("%s", adapter.format_failure(claim))
            if adapter.finalize_failure(
                claim=claim,
                error=adapter.sanitize_error(exc),
            ):
                continue
            return handled_work

        if heartbeat_state is not None:
            stop_event, thread = heartbeat_state
            stop_event.set()
            thread.join(timeout=1.0)
        if adapter.finalize_success(
            claim=claim,
            build_output=build_output,
        ):
            continue
        return handled_work
