# PR Delivery Workflow

Branch protection: direct push to `master` blocked. All changes via PR + required checks.

## Flow

1. Select or create a Trellis task while on `master`, then confirm its `prd.md` matches the intended scope
2. Sync: `git switch master && git pull --ff-only`
3. If the task was created elsewhere, reset its PR target with `python3 ./.trellis/scripts/task.py set-base-branch <task-dir> master`
4. Branch: `git switch -c pr/<scope>-<topic>-<yyyymmdd>` and record it with `python3 ./.trellis/scripts/task.py set-branch <task-dir> <branch>`
5. Set PR scope up front: `python3 ./.trellis/scripts/task.py set-scope <task-dir> <scope>`
6. Implement minimal scoped change and run targeted checks
7. Create or update the draft PR through Trellis: `python3 ./.trellis/scripts/task.py create-pr [task-dir]`
   - this stages repo changes, excludes Trellis workspace artifacts, creates the commit, pushes the branch, and opens or reuses a draft PR
8. CI: `gh pr checks <pr_number>` — use staged polling instead of tight loops
   - first poll after about **2 minutes**
   - if several jobs are still pending, retry about every **2 minutes**
   - once only the long integration E2E job is pending, retry about every **3 minutes**
   - only tighten to about **1 minute** polling if you specifically need the exact final completion / merge moment
   - current rule of thumb: backend / lint-build / mock E2E / docker usually finish in about **1.5–2 minutes**, while the required integration E2E job is usually about **3 minutes** when green but can stretch much longer under retries
   - if checks fail, fix on the same branch, rerun targeted verification, then rerun `python3 ./.trellis/scripts/task.py create-pr [task-dir]`
9. When checks pass, mark ready and merge: `gh pr ready <pr_number>` then `gh pr merge <pr_number> --merge --delete-branch`
10. Cleanup local state:
   ```bash
   git branch -D <branch>
   git switch master && git pull --ff-only
   ```
   If local `master` cannot fast-forward because it diverged, preserve the local-only commits on a backup branch and reset `master` to `origin/master` instead of repeatedly retrying `pull --ff-only`.

## Guardrails

- Keep PR scope small and single-purpose
- Don't include runtime artifacts (e.g., `*.jsonl` debug logs)
- Prefer targeted tests covering changed behavior
- Before `task.py create-pr`, make sure task scope/name will generate a public-readable commit/PR title with no sensitive internal wording
- If release/public pipeline files change, re-check `.github/public-mirror-exclude.txt` and `tests/test_release_pipeline_contract.py`

## Public Release Repo

### Decision: Public release stays decoupled from private PR merges
The public GitHub repo is **not** a live mirror of private `master`.

- private PR merges decide what enters internal `master`
- public releases happen later, via `v*` tags or manual dispatch from private `master`
- `v*` tags now drive the public release pipeline: publish sanitized history and version tags to the public repo
- one public release may batch several already-merged private PRs

### Decision: Preserve public commit history instead of orphan snapshots
Public publishing now replays the unpublished, sanitized `master` commits that still produce public diffs.

That means:

- the public repo keeps readable commit-by-commit history
- commits touching only excluded/private files are skipped
- release tags still mark stable public version points
- tag-driven public releases also create/update the matching public GitHub Release and mark it as Latest
- if a private PR was squash-merged, the public repo can only preserve the squashed diff

See `.github/workflows/release-tag.yml`, `.github/workflows/deploy-hosted.yml`, `.github/workflows/mirror-public.yml`, `docs/public-release-repo.md`, and `docs/release-checklist.md`.

### Don't: leak private operator context into public releases
Public release snapshots must not expose personal privacy, internal dev tooling, or operator-only release details. Treat assistant instructions, private specs, unpublished docs, personal identifiers, cloud resource names, machine/user names, private deployment runbooks, and similar "helps us operate the private repo" material as private-by-default; exclude or sanitize them before tagging. When unsure, prefer keeping the file out of the public snapshot and record the allow/deny rule in `.github/public-mirror-exclude.txt`. See `.github/public-mirror-exclude.txt`, `.github/workflows/mirror-public.yml`, and `tests/test_release_pipeline_contract.py`.

### Decision: GHCR image publishing stays private-repo-only
Keep `.github/workflows/docker-publish.yml` out of the public snapshot even though selfhost artifacts stay public, because the official GHCR image is published from the private repo’s verified pipeline and should not be re-triggered or shadowed by the public mirror. Rejected: letting the public repo carry a second image-publish workflow, because that creates duplicate-publication ambiguity and weakens the “private repo is the release control plane” boundary. See `.github/public-mirror-exclude.txt`, `.github/workflows/docker-publish.yml`, `docs/public-release-repo.md`, and `tests/test_release_pipeline_contract.py`.

## Definition of Done

PR merged · CI passed · branch deleted (remote + local) · local master synced · working tree state reported
