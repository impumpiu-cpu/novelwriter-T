# Bootstrap Invariant Gates

Purpose: prevent bootstrap workflow drift during fast pre-launch iteration.

## Invariants

- `BI-01` Initial extraction must remain available after index-only refresh runs.
- `BI-02` User edits on bootstrap drafts transfer ownership to `origin=manual` and must not be auto-replaced.
- `BI-03` First-run primary CTA triggers extraction (`initial`), not maintenance-only index refresh.
- `BI-04` Reextract replacement must fail fast on ambiguous legacy manual drafts with actionable remediation.

## Gate Suites

- backend: `tests/bootstrap/test_invariants.py`
- frontend: `web/src/__tests__/BootstrapPanel.invariants.test.tsx`

## Touch Trigger

Review/update invariants when touching:

- `app/api/world.py`
- `app/core/world_bootstrap_application.py`
- `app/core/bootstrap.py`
- `alembic/versions/012_add_bootstrap_modes_and_origin_tracking.py`
- `web/src/components/world-model/shared/BootstrapPanel.tsx`

## CI Requirement

Invariant suites must stay explicitly wired in CI alongside broader test jobs.
