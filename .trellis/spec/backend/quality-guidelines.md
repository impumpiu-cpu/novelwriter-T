# Quality Guidelines

Use this doc for backend decisions that are easy to regress during fast iteration.
Keep code-level details in code/tests; keep the why and the tripwires here.

## Config as Source of Truth

- Runtime tunables live in `app/config.py` via `get_settings()`.
- Mutable thresholds belong on the config wiring chain, not inside method bodies.
- Standalone helpers may keep local `DEFAULT_*` constants only when they improve testability or isolated reuse.

### Decision: production gates use `Settings.environment`
Chose a single normalized `Settings.environment` / `settings.is_production` contract because scattered `os.getenv("ENVIRONMENT")` string checks drift and create inconsistent security behavior. See `app/config.py`, `app/main.py`, `tests/test_logging_environment.py`, and `tests/test_startup_security.py`.

### Decision: `.env` vs OS env precedence is mode-dependent
Local and selfhost prefer repo-local `.env` so project settings override shell leftovers; hosted and production prefer OS env so deployment secrets cannot be shadowed by a stale file. See `app/config.py`, `tests/test_config_env_precedence.py`, `tests/test_settings_dotenv_precedence.py`, and `deploy/hosted/docker-compose.yml`.

## Hosted and Gateway Contracts

### Decision: OpenAI-compatible gateways stay request-shape compatible
Backend requests keep the standard OpenAI payload shape (`model`, `messages`, streaming flags, etc.). Treat routing mismatches as provider provisioning problems, not as a reason to invent project-specific request headers or body fields. See `app/core/ai_client.py`.

### Gotcha: OpenAI-compatible does not mean optional-params-compatible
Some gateways reject newer optional fields such as `stream_options`. Feature-gate or retry without the optional arg instead of forking the core request contract. See `app/core/ai_client.py`.

### Don't: persist BYOK secrets server-side
User-supplied BYOK config (`api_key`, `base_url`, `model`) must travel per request via `X-LLM-*` headers and must never be stored in DB rows, server-side settings, or logs. Server-owned hosted credentials are separate and remain env-only. See `web/src/services/apiClient.ts`, `web/src/services/api.ts`, `web/src/services/copilotApi.ts`, `app/api/novels.py`, and `tests/test_hosted_byok_contract.py`.

### Decision: hosted BYOK bypasses spend hard-stop checks, not operator disable
Hosted spend-budget fuses exist to cap server-owned model cost. When a request is clearly BYOK, spend-meter disabled/unavailable states and hard-stop thresholds must not block it. The explicit operator kill switch (`ai_manual_disable`) still blocks all AI traffic, including BYOK. See `app/core/safety_fuses.py`, `app/core/ai_client.py`, and `tests/test_safety_fuses.py`.

### Don't: accept partial BYOK header overrides
If any of `X-LLM-Base-Url`, `X-LLM-Api-Key`, or `X-LLM-Model` is supplied, all three must be present. Silent fallback from a partial override to hosted/selfhost env config is forbidden because it hides which credentials and model were actually used. Return a structured `400` instead. See `app/api/novels.py`, `app/api/llm.py`, and `tests/test_world_generation.py`.

### Decision: `Novel.owner_id` isolation is hosted-only
Selfhost is intentionally single-user, so local DBs remain readable even if the default user id changes. Hosted mode must enforce strict `owner_id` filtering and return `404` on cross-user access to avoid existence leaks. See `app/api/novels.py`, `app/api/world.py`, `app/core/world_crud.py`, `tests/test_hosted_byok_contract.py`, and `tests/test_hosted_novel_scoped_access.py`.

### Don't: record hosted token usage without `user_id`
Hosted usage rollups filter on `TokenUsage.user_id`; missing `user_id` silently disappears from reporting. Every hosted LLM path, including bootstrap or background work, must carry a real user id or an explicit system-user policy. See `app/api/usage.py`, `app/core/ai_client.py`, `app/core/world_generation_application.py`, `app/core/world_bootstrap_application.py`, and `app/core/bootstrap.py`.

### Don't: assume container-local files persist in hosted deployments
If hosted code writes files to disk, they must live under the mounted data directory contract. Anything else is disposable container state. See `app/api/novels.py` and `deploy/hosted/docker-compose.yml`.

### Decision: hosted auth is provider-admitted, not a full account system
Hosted mode is a validation-tier access model, not a full account system. Invite code is manual admission, GitHub OAuth can be open-provider admission when configured, and quota is still the real scarce resource. Product-facing identity lives on `User.nickname`, while internal usernames stay implementation detail and every hosted provider must converge onto the same downstream session/quota contract. See `app/api/auth.py`, `app/config.py`, `tests/test_invite_quota.py`, and `tests/test_github_oauth_login.py`.

### Decision: hosted auth providers attach to `User` through auth identities
`User` stays the product principal for quota, ownership, and downstream JWT/session contracts; external auth sources (including invite) map onto that user through `auth_identities` keyed by provider + provider-stable subject. Rejected: storing provider-specific auth state on `users` or resolving relogin by ad-hoc user-table lookups. See `app/core/auth.py`, `app/api/auth.py`, `alembic/versions/032_add_auth_identities.py`, and `tests/test_invite_quota.py`.

### Decision: OAuth-created hosted users must reserve an invite fallback identity
GitHub-created hosted users also reserve the invite identity keyed by `User.nickname`, so reverting to invite-only login still resolves the same `User` and preserves quota/novels. Rejected: GitHub-only users that become stranded after rollback, and rejected: silently minting a second user when that nickname/login handle is already claimed; fail the OAuth signup instead. See `app/core/auth.py`, `app/api/auth.py`, and `tests/test_github_oauth_login.py`.

### Decision: invite login must repair missing legacy invite identities before provisioning
If hosted invite login cannot find `auth_identities(invite, nickname)`, it must first recover the earliest existing `users.nickname == nickname` row and backfill that identity instead of creating a fresh user/quota bucket. Rejected: trusting `auth_identities` so completely that partial migrations/restores silently duplicate hosted accounts. See `app/core/auth.py`, `alembic/versions/032_add_auth_identities.py`, and `tests/test_invite_quota.py`.

### Decision: generation quota is hosted-only and uses reserve-then-refund
Quota lifecycle is `reserve()` -> `charge(delivered)` -> `finalize()` through `QuotaScope`, shared by streaming and non-stream endpoints. Users only pay for delivered variants; abandoned reservations must reconcile on restart. See `app/core/auth.py`, `app/api/novels.py`, `tests/test_quota_scope.py`, `tests/test_quota_atomicity.py`, and `tests/test_continue_quota.py`.

### Decision: quota exhaustion returns structured 429 codes
Quota failures must return stable structured `detail.code` values such as `generation_quota_exhausted` instead of raw strings so frontend surfaces can distinguish exhausted user quota from concurrency throttles or generic busy states. See `app/core/auth.py`, `app/api/copilot.py`, and `tests/test_copilot.py`.

### Don't: deduct metered resources per-unit inside generators
Per-unit deduction inside the generation loop charges users for server work they may never receive after disconnects or failures. Upfront reservation plus end-of-request reconciliation is the only allowed contract. See `app/core/auth.py` and `app/api/novels.py`.

## Isolation and Concurrency

### Decision: selfhost default-user bootstrap must tolerate uniqueness races
Selfhost auth may resolve the implicit `default` user from multiple concurrent requests (for example browser startup fanout during integration tests). Creating that user must treat the unique-username race as expected: rollback, reload the row, and continue instead of surfacing a 500. See `app/core/auth.py` and `tests/test_auth_default_user.py`.

### Decision: bootstrap admission must be deterministic
`POST /world/bootstrap` must serialize admission per novel, return `409` for active non-stale jobs, and translate uniqueness races into rollback + `409` instead of leaking raw DB errors. See `app/core/world_bootstrap_application.py`, `app/core/bootstrap.py`, `tests/test_bootstrap_contract.py`, and `tests/test_bootstrap_invariants.py`.

### Decision: novel isolation must be enforced through every touched resource
Novel scoping is not satisfied by checking only the top-level route param. Sub-resources and relationship endpoints must verify that every touched row belongs to the same novel. See `app/api/world.py`, `app/core/world_crud.py`, `tests/test_api_world.py`, and `tests/test_hosted_novel_scoped_access.py`.

### Decision: fast-moving product contracts get invariant gates
When behavior is changing quickly, define invariant IDs in spec, add focused backend/frontend gate suites, wire them in CI, and delete placeholder markers once the feature stabilizes. See `bootstrap-invariant-gates.md` and `tests/bootstrap/test_invariants.py`.

## Test Coverage Conventions

- New or changed behavior in `app/core/` and `app/api/` needs regression coverage.
- In pre-launch mode, tests lock the current intended behavior, not legacy behavior.
- Test files should mirror the source module when practical.
- Spec, tests, and code change together when the product contract changes.

### Don't: override the wrong FastAPI dependency in tests
Override the exact dependency referenced by the route. Overriding `get_current_user` does nothing for a route wired to `get_current_user_or_default`, and creates false-green tests. See `tests/test_continue_endpoint.py`.

## Review Checklist

- [ ] No mutable tunables were hardcoded in method bodies
- [ ] New config values follow `config -> wiring -> usage`
- [ ] Novel scoping is enforced on every touched resource
- [ ] Bootstrap conflicts stay deterministic (`202` vs `409`)
- [ ] Invariant-gate-worthy behavior is documented and tested
- [ ] Relevant regression tests were updated with the contract

## Related Specs

- pre-launch delivery rules: `../guides/pre-launch-mode.md`
- API error translation: `./error-handling.md`
- hosted runtime tripwires: `../guides/internal/gcp-hosted-ops.md`
