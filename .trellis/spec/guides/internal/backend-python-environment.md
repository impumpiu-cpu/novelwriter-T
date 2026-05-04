# Backend Python Environment

Use this doc for the environment contract behind backend commands.
Keep concrete setup steps in scripts and `docs/python-environment.md`; keep the non-obvious rules here.

## Core Contract

### Decision: backend Python runs through `uv` + repo-local `.venv` + locked project metadata
The project default is a repo-scoped environment bootstrapped from `pyproject.toml` + `uv.lock`, typically entered through `scripts/setup_python_env.sh` and `scripts/uv_run.sh`. Rejected: relying on whichever `python`, `pip`, `pytest`, or ad-hoc `requirements*.txt` happens to be on the machine, because that creates agent/CI/Docker/deploy drift and cross-project pollution. See `pyproject.toml`, `uv.lock`, `scripts/setup_python_env.sh`, `scripts/uv_run.sh`, and `docs/python-environment.md`.

### Decision: `.uv-version` is the single uv tool-version source
Chose `.uv-version` as the only hand-edited uv version pin, then generate/sync derived literals into `pyproject.toml` and `install.sh`, because CI, Docker build, hosted deploy, and the curl installer must agree on the exact uv toolchain. CI must read the synced `pyproject.toml` `tool.uv.required-version` field instead of the raw `.uv-version` file, because `astral-sh/setup-uv` expects `version-file` inputs to be TOML documents. Rejected: independently editing uv versions in each surface, because those drifts are easy to miss and break release/install parity. See `.uv-version`, `scripts/sync_uv_version.py`, `pyproject.toml`, `install.sh`, `Dockerfile`, `.github/workflows/ci.yml`, and `tests/test_release_pipeline_contract.py`.

### Don't: install or run backend tooling against the system interpreter
Do not use bare `python` / `pip` / `pytest`, legacy `requirements*.txt`, or `uv pip install --system` for backend work in this repo. Keep installs and execution scoped to the locked project environment. See `scripts/backend_checks.sh`.

### Gotcha: cache permissions can break `uv` in sandboxes
If a sandbox cannot write to the default cache directory, point `UV_CACHE_DIR` and `XDG_CACHE_HOME` at a writable path for that command instead of bypassing the project environment. See `docs/python-environment.md`.

### Gotcha: selfhost bind-mounted `/data` must stay writable from the container
The public selfhost flow bind-mounts a host directory into `/data`, so a non-root runtime user can fail first-run SQLite/bootstrap writes when the host path is created by an arbitrary UID/GID. Keep the runtime contract compatible with writable bind mounts (currently by leaving the selfhost runtime container on the default root user) unless the compose/CLI flow grows explicit UID/GID coordination. See `Dockerfile`, `deploy/selfhost/docker-compose.yml`, `app/cli.py`, and `scripts/selfhost_smoke.sh`.

### Gotcha: \"works locally\" often means \"ran outside `.venv`\"
Intermittent import or dependency mismatches usually come from executing outside the repo environment. Re-run through `scripts/uv_run.sh` first before debugging anything deeper.

## Related Files

- `pyproject.toml`
- `uv.lock`
- `scripts/setup_python_env.sh`
- `scripts/uv_run.sh`
- `scripts/backend_checks.sh`
- `docs/python-environment.md`
