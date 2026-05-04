# SPDX-FileCopyrightText: 2026 Isaac.X.Ω.Yuan
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.models import BootstrapJob


def is_bootstrap_initialized(job: BootstrapJob | None) -> bool:
    if job is None:
        return False
    return bool(job.initialized)


__all__ = ["is_bootstrap_initialized"]
