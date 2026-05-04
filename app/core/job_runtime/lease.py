from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .time import resolve_lease_expiry


def apply_row_updates(record: Any, updates: Mapping[Any, Any]) -> None:
    for field, value in updates.items():
        setattr(record, getattr(field, "key", field), value)


def claim_lease_values(
    model: Any,
    *,
    now: datetime,
    worker_id: str,
    lease_seconds: int,
    extra_updates: Mapping[Any, Any] | None = None,
) -> dict[Any, Any]:
    updates: dict[Any, Any] = {
        model.lease_owner: worker_id,
        model.lease_expires_at: resolve_lease_expiry(now, lease_seconds),
    }
    started_at = getattr(model, "started_at", None)
    if started_at is not None:
        updates[started_at] = now
    updated_at = getattr(model, "updated_at", None)
    if updated_at is not None:
        updates[updated_at] = now
    if extra_updates:
        updates.update(dict(extra_updates))
    return updates


def refresh_lease_values(
    model: Any,
    *,
    now: datetime,
    lease_seconds: int,
    extra_updates: Mapping[Any, Any] | None = None,
) -> dict[Any, Any]:
    updates: dict[Any, Any] = {
        model.lease_expires_at: resolve_lease_expiry(now, lease_seconds),
    }
    updated_at = getattr(model, "updated_at", None)
    if updated_at is not None:
        updates[updated_at] = now
    if extra_updates:
        updates.update(dict(extra_updates))
    return updates


def release_lease_values(
    model: Any,
    *,
    now: datetime | None = None,
    extra_updates: Mapping[Any, Any] | None = None,
) -> dict[Any, Any]:
    updates: dict[Any, Any] = {
        model.lease_owner: None,
        model.lease_expires_at: None,
    }
    if now is not None:
        updated_at = getattr(model, "updated_at", None)
        if updated_at is not None:
            updates[updated_at] = now
    if extra_updates:
        updates.update(dict(extra_updates))
    return updates
