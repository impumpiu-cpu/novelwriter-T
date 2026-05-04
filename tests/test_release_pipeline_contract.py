from pathlib import Path
import re
import subprocess
import sys
import tomllib
import json

from packaging.version import Version


ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def test_release_tag_workflow_publishes_public_history_without_hosted_deploy():
    workflow = _read(".github/workflows/release-tag.yml")

    assert "uses: ./.github/workflows/mirror-public.yml" in workflow
    assert "uses: ./.github/workflows/deploy-hosted.yml" not in workflow
    assert re.search(r"publish-public:\n(?:.*\n)*?\s+contents:\s+read", workflow)
    assert "source_event_name: push" in workflow
    assert "source_ref_type: tag" in workflow
    assert "source_ref_name: ${{ github.ref_name }}" in workflow
    assert "source_sha: ${{ github.sha }}" in workflow


def test_mirror_public_workflow_is_reusable_and_still_manual_dispatchable():
    workflow = _read(".github/workflows/mirror-public.yml")

    assert "workflow_call:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "source_sha:" in workflow
    assert "source_ref_name:" in workflow
    assert "Manual public release must be dispatched from master" in workflow
    assert "must point to a commit already merged into master" in workflow
    assert "Build public GitHub Release notes" in workflow
    assert "Create or update public GitHub Release" in workflow
    assert "gh release create" in workflow
    assert "gh release edit" in workflow
    assert "--latest" in workflow
    assert "public-release-applied-commits.md" in workflow
    assert "公开仓差异对比" in workflow


def test_internal_release_pipeline_files_stay_out_of_public_snapshot():
    excluded = _read(".github/public-mirror-exclude.txt")

    assert ".github/workflows/deploy-hosted.yml" in excluded
    assert ".github/workflows/deploy-hosted-beta.yml" in excluded
    assert ".github/workflows/release-tag.yml" in excluded
    assert ".github/workflows/mirror-public.yml" in excluded
    assert ".github/workflows/docker-publish.yml" in excluded
    assert ".codex" in excluded
    assert "competition.md" in excluded
    assert "scripts/deploy_hosted.sh" in excluded
    assert "scripts/loadtest/" in excluded


def test_hosted_deploy_script_keeps_healthcheck_and_metadata_contract():
    script = _read("scripts/deploy_hosted.sh")
    uv_version = _read(".uv-version").strip()

    assert "http://localhost:8000/api/health" in script
    assert "http://localhost:8000/api/health/access" in script
    assert "NOVWR_HEALTHCHECK_RETRIES" in script
    assert "last-access-health.json" in script
    assert "last-success.env" in script
    assert "current-sha.txt" in script
    assert "systemctl restart novwr" in script
    assert "systemctl restart \"$HOSTED_WORKER_UNIT_NAME\"" in script
    assert "systemctl enable --now \"$HOSTED_WORKER_UNIT_NAME\"" in script
    assert "systemctl daemon-reload" in script
    assert 'UV_VERSION_FILE="${NOVWR_UV_VERSION_FILE:-$ROOT_DIR/.uv-version}"' in script
    assert f'https://astral.sh/uv/{uv_version}/install.sh' not in script
    assert 'https://astral.sh/uv/${uv_version}/install.sh' in script
    assert "scripts/setup_python_env.sh" in script
    assert "--group hosted-proxy" in script
    assert "scripts/build_state_proto_rust.sh" in script
    assert "--no-dev" in script
    assert "upgrade_runtime_database_schema" in script
    assert "app.selfhost_db_bootstrap" in script
    assert 'Target ref does not contain alembic.ini.' in script
    assert "astral.sh/uv/install.sh" not in script
    assert "requirements.txt" not in script
    assert "resolve_uv_version" in script
    assert "build_state_proto_extension" in script
    assert "verify_state_proto_extension" in script
    assert "https://sh.rustup.rs" in script
    assert 'DEPLOY_REQUIRE_ORIGIN_MASTER="${NOVWR_DEPLOY_REQUIRE_ORIGIN_MASTER:-true}"' in script
    assert 'DEPLOY_GIT_FETCH_SCOPE="${NOVWR_DEPLOY_GIT_FETCH_SCOPE:-master}"' in script
    assert 'DEPLOY_TRACK="${NOVWR_DEPLOY_TRACK:-production}"' in script
    assert 'DEPLOY_BOOTSTRAPPED="${NOVWR_DEPLOY_BOOTSTRAPPED:-false}"' in script
    assert 'DEPLOY_APP_USER="${NOVWR_DEPLOY_APP_USER:-$(id -un)}"' in script
    assert 'HOSTED_WORKER_TEMPLATE="${NOVWR_HOSTED_WORKER_TEMPLATE:-$ROOT_DIR/deploy/hosted/novwr-worker.service}"' in script
    assert 'HOSTED_WORKER_UNIT_NAME="${NOVWR_HOSTED_WORKER_UNIT_NAME:-novwr-worker.service}"' in script
    assert 'HOSTED_NGINX_TEMPLATE="${NOVWR_HOSTED_NGINX_TEMPLATE:-$ROOT_DIR/deploy/hosted/novwr.nginx.site}"' in script
    assert 'HOSTED_NGINX_SITE_NAME="${NOVWR_HOSTED_NGINX_SITE_NAME:-novwr}"' in script
    assert 'HOSTED_SERVER_NAMES="${NOVWR_HOSTED_SERVER_NAMES:?NOVWR_HOSTED_SERVER_NAMES is required}"' in script
    assert "_novwr_state_proto" in script
    assert "NOVWR_DEPLOY_TRACK=" in script
    assert "install_hosted_nginx_site" in script
    assert "render_hosted_nginx_site" in script
    assert "sudo nginx -t" in script
    assert "sudo systemctl reload nginx" in script
    assert 'sudo rm -f "$HOSTED_NGINX_ENABLED_DIR/default"' in script
    assert 'export NOVWR_DEPLOY_BOOTSTRAPPED=true' in script
    assert 'export NOVWR_PREVIOUS_SHA="$previous_sha"' in script
    assert 'exec bash "$ROOT_DIR/scripts/deploy_hosted.sh"' in script


def test_hosted_nginx_site_template_blocks_sensitive_path_probes():
    site = _read("deploy/hosted/novwr.nginx.site")

    assert "server_name __NOVWR_SERVER_NAMES__;" in site
    assert "ssl_certificate __NOVWR_SSL_CERTIFICATE__;" in site
    assert "ssl_certificate_key __NOVWR_SSL_CERTIFICATE_KEY__;" in site
    assert "map $uri $novwr_probe_class {" in site
    assert 'log_format novwr_probe ' in site
    assert 'probe=1 probe_class=$novwr_probe_class host="$host" rt=$request_time' in site
    assert "access_log /var/log/nginx/novwr.access.log combined if=$novwr_log_main;" in site
    assert "access_log /var/log/nginx/novwr-probes.access.log novwr_probe if=$novwr_probe_request;" in site
    assert r"location ~ /\.(?!well-known(?:/|$))" in site
    assert r"location ~* ^/(?:Dockerfile(?:\.[^/]+)?|docker-compose(?:\.[^/]+)?\.ya?ml|compose(?:\.[^/]+)?\.ya?ml)$" in site
    assert r"location ~* ^/(?:wp-admin|wp-content|wp-includes|cgi-bin|vendor/phpunit)(?:/|$)" in site
    assert r"location ~* ^/(?:wp-login\.php|xmlrpc\.php|phpinfo\.php|phpunit(?:\.xml(?:\.dist)?)?|server-status|web\.config|settings\.php|config(?:\.php|\.json))$" in site
    assert "return 404;" in site


def test_hosted_worker_unit_template_uses_runtime_placeholders():
    unit = _read("deploy/hosted/novwr-worker.service")

    assert "User=__NOVWR_APP_USER__" in unit
    assert "WorkingDirectory=__NOVWR_ROOT_DIR__" in unit
    assert "EnvironmentFile=-__NOVWR_ROOT_DIR__/.env" in unit
    assert "ExecStart=__NOVWR_ROOT_DIR__/.venv/bin/python -m app.workers.hosted_jobs" in unit
    assert "/home/omega/novwr" not in unit


def test_state_proto_ensure_script_keeps_runtime_preflight_and_auto_build_contract():
    ensure_script = _read("scripts/ensure_state_proto_extension.sh")
    uv_run = _read("scripts/uv_run.sh")

    assert "_novwr_state_proto" in ensure_script
    assert "build_state_proto_rust.sh" in ensure_script
    assert "--check-only" in ensure_script
    assert "cargo" in ensure_script
    assert "rustc" in ensure_script
    assert "NOVWR_SKIP_STATE_PROTO_ENSURE" in uv_run
    assert "should_ensure_state_proto" in uv_run
    assert 'python|pytest|uvicorn' in uv_run
    assert '"$ROOT_DIR/scripts/ensure_state_proto_extension.sh" --quiet' in uv_run


def test_python_environment_bootstrap_is_uv_lock_driven():
    setup_script = _read("scripts/setup_python_env.sh")
    pyproject = _read("pyproject.toml")
    pyproject_data = tomllib.loads(pyproject)
    uv_version = _read(".uv-version").strip()

    assert "uv venv" in setup_script
    assert "uv sync" in setup_script
    assert "--group <name>" in setup_script
    assert "--skip-state-proto" in setup_script
    assert 'SYNC_GROUPS+=("$2")' in setup_script
    assert 'ENSURE_STATE_PROTO=true' in setup_script
    assert '"$ROOT_DIR/scripts/ensure_state_proto_extension.sh"' in setup_script
    assert "--frozen" in setup_script
    assert "--no-install-project" in setup_script
    assert "[project]" in pyproject
    assert "[dependency-groups]" in pyproject
    assert 'requires-python = ">=3.13,<3.14"' in pyproject
    assert pyproject_data["project"]["scripts"]["novwr"] == "app.cli:main"
    assert pyproject_data["dependency-groups"]["hosted-proxy"] == [
        "aiohttp>=3.13.5",
        "cryptography>=46.0.6",
        "litellm[proxy,google]==1.82.0",
    ]
    assert pyproject_data["tool"]["uv"]["package"] is True
    assert pyproject_data["tool"]["uv"]["required-version"] == f"=={uv_version}"
    assert pyproject_data["tool"]["setuptools"]["package-data"]["app.core.indexing"] == [
        "data/*.txt",
        "data/*.tsv",
    ]


def test_uv_lock_keeps_audited_security_floors_for_proxy_and_dev_tooling():
    lock = _read("uv.lock")

    def _locked_version(name: str) -> Version:
        pattern = rf'\[\[package\]\]\nname = "{re.escape(name)}"\nversion = "([^"]+)"'
        match = re.search(pattern, lock)
        assert match, f"missing {name} in uv.lock"
        return Version(match.group(1))

    assert _locked_version("aiohttp") >= Version("3.13.5")
    assert _locked_version("cryptography") >= Version("46.0.6")
    assert _locked_version("pygments") >= Version("2.20.0")


def test_uv_version_generated_targets_are_in_sync():
    completed = subprocess.run(
        [sys.executable, "scripts/sync_uv_version.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


def test_dockerfile_allows_frontend_build_mode_overrides():
    dockerfile = _read("Dockerfile")

    assert "# syntax=docker/dockerfile:1.7" in dockerfile
    assert "ARG VITE_DEPLOY_MODE=selfhost" in dockerfile
    assert 'VITE_DEPLOY_MODE="$VITE_DEPLOY_MODE"' in dockerfile
    assert "COPY .uv-version ./" in dockerfile
    assert 'env UV_UNMANAGED_INSTALL="/uv-bin" sh' in dockerfile
    assert "COPY scripts/setup_python_env.sh scripts/ensure_state_proto_extension.sh scripts/build_state_proto_rust.sh ./scripts/" in dockerfile
    assert "COPY app/core/indexing/data/ app/core/indexing/data/" in dockerfile
    assert "scripts/setup_python_env.sh --no-dev --skip-state-proto" in dockerfile
    assert "--mount=type=cache,target=/root/.cache/uv" in dockerfile
    assert "COPY data/demo/ data/demo/" in dockerfile
    assert "COPY data/worldpacks/ data/worldpacks/" in dockerfile
    assert "python:3.13-slim" in dockerfile
    assert "scripts/setup_python_env.sh --no-dev" in dockerfile
    assert "COPY --from=backend-build /app/.venv /app/.venv" in dockerfile
    assert "COPY --from=uv /uv /uvx /bin/" not in dockerfile
    assert "USER app" not in dockerfile


def test_docker_build_context_keeps_demo_seed_assets():
    dockerignore = _read(".dockerignore")

    assert "!data/demo/" in dockerignore
    assert "!data/demo/**" in dockerignore
    assert "!data/worldpacks/" in dockerignore
    assert "!data/worldpacks/**" in dockerignore


def test_hosted_compose_builds_frontend_in_hosted_mode():
    compose = _read("deploy/hosted/docker-compose.yml")

    assert "VITE_DEPLOY_MODE: hosted" in compose


def test_selfhost_compose_template_uses_official_image():
    compose = _read("deploy/selfhost/docker-compose.yml")

    assert "ghcr.io/hurricane0698/novelwriter:latest" in compose
    assert "${NOVWR_BIND_HOST:-127.0.0.1}:${NOVWR_PORT:-8000}:8000" in compose
    assert "${NOVWR_DATA_DIR:-./data}:/data" in compose


def test_ci_workflow_uses_uv_for_backend_jobs():
    workflow = _read(".github/workflows/ci.yml")

    assert "astral-sh/setup-uv@v7" in workflow
    assert "version-file: pyproject.toml" in workflow
    assert "./scripts/setup_python_env.sh --skip-state-proto" in workflow
    assert "./scripts/uv_run.sh pytest tests/" in workflow
    assert "pip install -r requirements.txt" not in workflow
    assert "uses: ./.github/workflows/ci-selfhost-smoke.yml" in workflow


def test_frontend_dependency_installation_stays_lockfile_driven_and_audited():
    package = json.loads(_read("web/package.json"))
    readme = _read("README.md")

    assert "npm ci" in readme
    assert "npm install" not in readme
    assert package["overrides"] == {
        "ajv": "6.14.0",
        "flatted": "3.4.2",
        "undici": "7.24.7",
        "rollup": "4.60.1",
        "picomatch@2.3.1": "2.3.2",
        "picomatch@4.0.3": "4.0.4",
        "minimatch@3.1.2": "3.1.5",
        "minimatch@9.0.5": "9.0.9",
        "brace-expansion@1.1.12": "1.1.13",
        "brace-expansion@2.0.2": "2.0.3",
    }


def test_loadtest_bootstrap_uses_locked_hosted_proxy_group():
    script = _read("scripts/loadtest/bootstrap_target_vm.sh")

    assert 'scripts/setup_python_env.sh" --no-dev --group hosted-proxy --skip-state-proto' in script
    assert "bootstrap_locked_hosted_proxy_env" in script
    assert "--group hosted-proxy" in script
    assert "--frozen" in script
    assert "uv pip install --python" not in script
    assert "litellm[proxy,google]" not in script
    assert "requires a lockfile-defined hosted-proxy dependency group" in script


def test_selfhost_smoke_workflow_gates_pr_installer_and_compose_paths():
    workflow = _read(".github/workflows/ci-selfhost-smoke.yml")

    assert "workflow_call:" in workflow
    assert "Selfhost install smoke" in workflow
    assert "astral-sh/setup-uv@v7" in workflow
    assert "version-file: pyproject.toml" in workflow
    assert "./scripts/selfhost_smoke.sh" in workflow


def test_selfhost_smoke_script_covers_wheel_installer_and_compose_flows():
    script = _read("scripts/selfhost_smoke.sh")

    assert 'docker build -t "$SMOKE_IMAGE_TAG" .' in script
    assert 'uv build --wheel --out-dir dist' in script
    assert 'uv tool run --isolated --from "$WHEEL_PATH" novwr --help' in script
    assert 'uv tool run --isolated --from "$WHEEL_PATH" novwr uninstall --help' in script
    assert 'curl -fsSL "file://${ROOT_DIR}/install.sh" | bash' in script
    assert 'export NOVWR_UV_VERSION="$(tr -d ' in script
    assert '"$NOVWR_BIN" doctor --dir "$INSTALL_DIR"' in script
    assert "unset NOVWR_HOME NOVWR_IMAGE NOVWR_BIND_HOST NOVWR_PORT NOVWR_PACKAGE_SPEC NOVWR_UV_VERSION" in script
    assert 'cp deploy/selfhost/docker-compose.yml "$COMPOSE_DIR/docker-compose.yml"' in script
    assert 'docker compose --project-directory "$COMPOSE_DIR" --project-name "$COMPOSE_PROJECT_NAME" up -d' in script
    assert 'dump_compose_debug()' in script
    assert 'docker compose "${compose_args[@]}" logs --no-color || true' in script


def test_playwright_integration_backend_server_uses_uv_wrapper():
    config = _read("web/playwright.config.ts")
    script = _read("scripts/run_playwright_integration_backend.sh")

    assert "./scripts/run_playwright_integration_backend.sh" in config
    assert '"$ROOT_DIR/scripts/uv_run.sh" python -m app.workers.hosted_jobs &' in script
    assert 'exec "$ROOT_DIR/scripts/uv_run.sh" uvicorn app.main:app --port 8000' in script


def test_install_script_bootstraps_novwr_cli_and_runs_init_then_run():
    script = _read("install.sh")

    assert 'NOVWR_UV_VERSION="${NOVWR_UV_VERSION:-}"' in script
    assert "DEFAULT_NOVWR_UV_VERSION" in script
    assert 'curl -LsSf "https://astral.sh/uv/${uv_version}/install.sh" -o "$installer"' in script
    assert "raw.githubusercontent.com" in script
    assert ".uv-version" in script
    assert "NOVWR_PACKAGE_SPEC" in script
    assert "archive/refs/heads/master.tar.gz" in script
    assert 'if [[ "$package_spec" == git+* ]]; then' in script
    assert "ensure_command git" in script
    assert 'uv tool install --force "$package_spec"' in script
    assert 'init_args=(init --dir "$NOVWR_HOME")' in script
    assert 'novwr run --dir "$NOVWR_HOME"' in script
    assert 'novwr doctor --dir "$NOVWR_HOME"' in script
    assert 'novwr uninstall --dir "$NOVWR_HOME"' in script


def test_docker_publish_workflow_gates_latest_on_master_ci_success():
    workflow = _read(".github/workflows/docker-publish.yml")

    assert "workflow_run:" in workflow
    assert re.search(r"workflows:\n\s+- CI", workflow)
    assert re.search(r"types:\n\s+- completed", workflow)
    assert re.search(r"branches:\n\s+- master", workflow)
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert "github.event.workflow_run.head_sha" in workflow
    assert "docker/login-action@v3" in workflow
    assert "docker/metadata-action@v5" in workflow
    assert "docker/build-push-action@v6" in workflow
    assert "ghcr.io/${{ github.repository_owner }}/novelwriter" in workflow
    assert "org.opencontainers.image.source=https://github.com/Hurricane0698/novelwriter" in workflow
    assert "org.opencontainers.image.url=https://github.com/Hurricane0698/novelwriter" in workflow
    assert "annotations: ${{ steps.meta.outputs.annotations }}" in workflow
    assert "DOCKER_METADATA_ANNOTATIONS_LEVELS: manifest,index" in workflow
    assert "type=raw,value=latest" in workflow
    assert "type=ref,event=tag" in workflow
    assert "Guard tag source" in workflow
    assert "refs/heads/master:refs/remotes/origin/master" in workflow
    assert "must point to a commit already merged into origin/master" in workflow
    assert "type=raw,value=latest,enable={{is_default_branch}}" not in workflow


def test_hosted_deploy_workflow_bootstraps_script_from_origin_master_for_rollbacks():
    workflow = _read(".github/workflows/deploy-hosted.yml")

    assert 'remote_script_ref="origin/master"' in workflow
    assert "git show %q:scripts/deploy_hosted.sh" in workflow
    assert "bash .deploy/deploy_hosted.sh" in workflow
    assert (
        "git fetch origin refs/heads/master:refs/remotes/origin/master --tags --force"
        in workflow
    )
    assert "require_origin_master:" in workflow
    assert "deploy_git_fetch_scope:" in workflow
    assert "deploy_track:" in workflow
    assert 'NOVWR_DEPLOY_REQUIRE_ORIGIN_MASTER=%q' in workflow
    assert 'NOVWR_DEPLOY_GIT_FETCH_SCOPE=%q' in workflow
    assert 'NOVWR_DEPLOY_TRACK=%q' in workflow
    assert "git checkout --detach %q && NOVWR_PREVIOUS_SHA" not in workflow


def test_hosted_beta_deploy_workflow_reuses_production_deploy_with_beta_overrides():
    workflow = _read(".github/workflows/deploy-hosted-beta.yml")

    assert "uses: ./.github/workflows/deploy-hosted.yml" in workflow
    assert "workflow_dispatch:" in workflow
    assert "require_origin_master: false" in workflow
    assert "deploy_git_fetch_scope: all" in workflow
    assert "deploy_track: beta" in workflow
