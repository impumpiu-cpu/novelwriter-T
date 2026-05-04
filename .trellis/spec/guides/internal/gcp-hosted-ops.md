# GCP Hosted Ops

Use this doc for hosted-only decisions that are not obvious from selfhost development.
Because this file is private-only, it may also keep the pinned GCP config and operator commands that are not discoverable from repo code.

### Decision: GCP hosted ops is a private operator path, not the developer-facing release surface
Treat this doc and the GCP deploy path as private-repo operational context for the hosted validation tier (and later writer-beta style validation), not as part of the public/selfhost developer contract. Rejected: documenting GCP hosted as if it were the default developer-facing deployment story, because public release, selfhost install, and official image flows are intentionally separate. See `scripts/deploy_hosted.sh`, `.github/workflows/deploy-hosted.yml`, `docs/public-release-repo.md`, and `README.md`.

## Current GCP Footprint

| Item | Value |
|---|---|
| Cloud | GCP (`project-4ecbd827-64a1-4156-93a`) |
| VM | Compute Engine `novwr-host`, `e2-small`, `us-central1-c`, Ubuntu 22.04 Minimal |
| LLM | Vertex AI Gemini 3 Flash via LiteLLM |
| App ports | LiteLLM `:4000`, FastAPI `:8000` |
| Database | SQLite on VM disk (`data/novels.db`) |
| Process manager | systemd (`litellm.service`, `novwr.service`) |

## GitHub Deploy Federation

These resources back the private repo hosted deploy path:

| Item | Value |
|---|---|
| Workload Identity Pool | `projects/880279581268/locations/global/workloadIdentityPools/github-actions` |
| Workload Identity Provider | `projects/880279581268/locations/global/workloadIdentityPools/github-actions/providers/novelwrite-private` |
| Deploy service account | `novwr-github-deploy@project-4ecbd827-64a1-4156-93a.iam.gserviceaccount.com` |
| Trusted GitHub repo attribute | `attribute.repository=Hurricane0698/novelWrite` |
| Deploy role | `projects/project-4ecbd827-64a1-4156-93a/roles/novwrGithubHostedDeploy` |

### Decision: GitHub deploy uses a dedicated SA + OIDC, not VM credentials or static SSH keys

The release pipeline should federate from GitHub Actions into the dedicated deploy service account above. Do not fall back to long-lived JSON keys or repo-stored SSH private keys unless the OIDC path is broken and you are in break-glass mode.

### Decision: deploy SA stays scoped to temporary SSH metadata + instance inspection

`novwr-github-deploy` only holds the custom `novwrGithubHostedDeploy` role plus `roles/iam.workloadIdentityUser` trust for the private repo. Keep broader roles such as `roles/owner`, `roles/editor`, or `roles/compute.admin` off this service account unless a new deploy requirement proves they are necessary.

These values are operationally significant: if they drift, hosted runbooks and safety assumptions must be updated with them.

## Hosted Contract

### Decision: hosted is a validation tier, not a general multi-tenant platform
Hosted mode exists to validate the product loop with invite-gated users and quota control. Selfhost remains the durable "bring your own key, no quota" path. See `app/config.py`, `app/api/auth.py`, and `app/core/auth.py`.

### Decision: hosted LLM traffic goes through platform-owned LiteLLM + ADC
Hosted credentials stay server-owned and env-loaded; clients never receive provider credentials. The backend still speaks OpenAI-compatible traffic, but the platform owns the cloud auth boundary. See `app/config.py`, `app/core/ai_client.py`, and `deploy/hosted/docker-compose.yml`.

### Gotcha: Gemini 3 Flash requires the global Vertex endpoint
The hosted proxy must target the global endpoint. Regional defaults look plausible but fail in production. Keep this as an explicit deployment check whenever hosted LLM routing changes. See `deploy/hosted/docker-compose.yml` and `docs/hosted-safety-fuses.md`.

### Pinned runtime config on the VM

- Compute Engine default service account with Vertex AI User role
- service account: `880279581268-compute@developer.gserviceaccount.com`
- LiteLLM unit must include `Environment=VERTEXAI_LOCATION=global`
- production `.env` keeps:
  - `DEPLOY_MODE=hosted`
  - `ENVIRONMENT=production`
  - `HOSTED_LLM_BASE_URL=http://localhost:4000/v1`
  - `HOSTED_LLM_API_KEY=anything` (ignored by LiteLLM; ADC does the real auth)
  - `HOSTED_LLM_MODEL=vertex_ai/gemini-3-flash-preview`
  - `JWT_SECRET_KEY=<secret>`
  - `INVITE_CODE=<secret>`
  - `DB_AUTO_CREATE=true`
  - `ENABLE_EVENT_TRACKING=true`
  - `CORS_ALLOWED_ORIGINS=["*"]`

Secrets are VM-only and must not be copied into the repo or local notes.

### Firewall rules currently assumed by ops

| Rule | Protocol | Port | Source |
|---|---|---|---|
| default-allow-http | TCP | 80 | 0.0.0.0/0 |
| default-allow-https | TCP | 443 | 0.0.0.0/0 |
| allow-8000 | TCP | 8000 | 0.0.0.0/0 |

### Don't: copy hosted secrets or auth tokens into local notes or scripts
Invite codes, JWT secrets, and hosted provider credentials stay on the host. When debugging or exporting analytics, pull sanitized output back to local and leave secrets in the runtime environment. See `app/config.py` and `docs/hosted-safety-fuses.md`.

### Decision: demo assets are a release gate
The hosted first-run experience depends on demo seeding. Missing demo text or worldpack assets silently degrades onboarding even when the rest of the app looks healthy. Treat demo asset presence as part of deployment verification. See `app/core/seed_demo.py` and `app/api/auth.py`.

### Gotcha: bulk admin work must be throttled or taken off traffic
The hosted tier is intentionally small. Backfills, repair scripts, or mass seeding can starve the live service unless they are throttled or run with the app stopped. See `docs/hosted-safety-fuses.md`.

### Decision: current hosted architecture is single-process and single-node
Quota recovery, bootstrap admission, and other mutable hosted workflows assume one active app process. Any multi-worker or multi-node move must upgrade those ownership contracts first. See `app/core/auth.py`, `app/core/bootstrap.py`, and `../../backend/database-guidelines.md`.

## Service Commands

```bash
# Check status
sudo systemctl status litellm novwr

# Restart after backend/config change
sudo systemctl restart novwr

# Restart the LLM proxy
sudo systemctl restart litellm

# Reload edited unit files
sudo systemctl daemon-reload

# View recent logs
journalctl -u novwr -n 100 --no-pager
journalctl -u litellm -n 100 --no-pager
```

Systemd unit locations:

- `/etc/systemd/system/litellm.service`
- `/etc/systemd/system/novwr.service`

## GitHub Actions Release Path

Hosted deploy and public release sync are now separate GitHub Actions paths.

1. Merge the validated change into `master`
2. If you need to move the hosted environment, run `Deploy hosted production` with the target tag or commit SHA
3. If you need to publish to the public repo, cut a release tag from the merged commit, for example `git tag v0.1.1 && git push origin v0.1.1`
4. GitHub Actions `Release tag` now runs only `Publish public release repo`
5. Verify the workflow logs, hosted healthcheck, and/or public tag appropriate to the path you used

### GitHub configuration required by the private hosted deploy workflow

Repository variables:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT`
- `GCP_VM_NAME`
- `GCP_VM_ZONE`
- `GCP_VM_REPO_DIR`
- `GCP_VM_APP_USER` (optional; set when the SSH login user is not the repo/app owner)

Public-release repo sync has its own separate config in `mirror-public.yml`; do not treat those variables/secrets as part of the hosted deploy contract.

### Decision: rollback reuses the same deploy workflow

Use the manual `Deploy hosted production` workflow with an older tag or commit SHA. Do not move an existing release tag backward.

## Break-Glass Manual Deploy

Use this only when GitHub Actions is unavailable or when you must inspect the VM interactively first.

```bash
# 1) SSH to the VM
gcloud compute ssh novwr-host --zone=us-central1-c

# 2) Deploy a specific merged commit or tag
cd ~/novwr
NOVWR_DEPLOY_REF=v0.1.1 NOVWR_DEPLOY_LABEL=v0.1.1 bash scripts/deploy_hosted.sh

# 3) Verify services
sudo systemctl status novwr litellm
curl -s http://localhost:8000/api/health

# 4) Verify demo assets still exist
ls data/demo/西游记_前27回.txt data/worldpacks/journey-to-the-west.json
git status data/demo/
```

## GCP Remote Ops

```bash
# Interactive shell
gcloud compute ssh novwr-host --zone=us-central1-c

# Single remote command
gcloud compute ssh novwr-host --zone=us-central1-c -- '<command>'
```

### Gotcha: SSH user is not the app user
`gcloud compute ssh` logs in as the local OS username. The app files and DB may require `sudo` or `sudo -u yangyinuo298` depending on what you are touching.

### Gotcha: admin APIs live under the auth router
Admin endpoints are `/api/auth/admin/funnel` and `/api/auth/admin/feedback`, not `/api/admin/...`.

### Rules for running commands on the VM

1. No heredoc in SSH terminals; build scripts line-by-line if needed.
2. Avoid long one-liners; write a `.py` file and then execute it.
3. Use the project venv for Python: `PYTHONPATH=. .venv/bin/python script.py`.
4. Throttle batch operations or stop the service first.
5. Use `sudo` for app files, git operations, and direct DB access when required.

## Operational Commands

```bash
# Backfill demo novels for users missing one
cd ~/novwr && PYTHONPATH=. .venv/bin/python /tmp/sf.py

# Verify demo coverage
sqlite3 ~/novwr/data/novels.db "SELECT COUNT(*) FROM novels WHERE title = '西游记';"

# Check for unexpected admin accounts
sqlite3 ~/novwr/data/novels.db "SELECT id, nickname, role FROM users WHERE role != 'user';"
```

## Known Gaps To Respect

- no automated DB backup contract yet; treat hosted SQLite as fragile until backup exists
- no monitoring or alerting contract yet; operational changes need manual verification
- open CORS is tolerated only for the current validation phase and should not become an unstated default

## Related Specs

- hosted auth / quota / owner isolation: `../../backend/quality-guidelines.md`
- DB/runtime trade-offs: `../../backend/database-guidelines.md`
- local-vs-hosted Python command rules: `./backend-python-environment.md`
