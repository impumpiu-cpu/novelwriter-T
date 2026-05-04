from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_

from .time import normalize_utc_naive, utcnow_naive


def is_stale_running_job(
    *,
    status: str | None,
    running_status: str,
    lease_expires_at,
    updated_at,
    created_at,
    stale_timeout_seconds: int,
    now: datetime | None = None,
) -> bool:
    if status != running_status:
        return False

    current_time = normalize_utc_naive(now) or utcnow_naive()
    normalized_lease_expiry = normalize_utc_naive(lease_expires_at)
    if normalized_lease_expiry is not None:
        return normalized_lease_expiry <= current_time

    if stale_timeout_seconds <= 0:
        return False

    normalized_updated_at = normalize_utc_naive(updated_at) or normalize_utc_naive(created_at)
    if normalized_updated_at is None:
        return False
    return normalized_updated_at <= (current_time - timedelta(seconds=stale_timeout_seconds))


def stale_running_job_filter(
    model: Any,
    *,
    now: datetime,
    stale_timeout_seconds: int,
):
    lease_expires_at = model.lease_expires_at
    updated_at = model.updated_at
    if stale_timeout_seconds > 0:
        stale_cutoff = now - timedelta(seconds=stale_timeout_seconds)
        return or_(
            and_(
                lease_expires_at.is_not(None),
                lease_expires_at <= now,
            ),
            and_(
                lease_expires_at.is_(None),
                updated_at <= stale_cutoff,
            ),
        )
    return and_(
        lease_expires_at.is_not(None),
        lease_expires_at <= now,
    )
