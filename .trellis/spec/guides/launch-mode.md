# Launch Mode

> Status: ACTIVE (since 2026-03-06)
> Deactivate only by explicit CEO instruction.

## Core Principle

Users are on the product. Stability > velocity. Every change must not break the live experience.

## Priority Order

1. live-site stability > new features
2. data integrity > code elegance
3. user-facing bugs > internal cleanup
4. backward compatibility > architecture purity

## Change Rules

### Breaking Changes

Breaking changes are **not allowed** without a migration plan. If a schema, API, or config change would break existing user data or sessions:

1. add the new path alongside the old
2. migrate existing data
3. remove the old path only after confirming zero usage

### Required for Every Change

1. **regression test** for the changed behavior
2. **rollback path** — every commit must be revertable without data loss
3. **no raw SQL on production DB** — use migration scripts or API endpoints
4. **test on local hosted-mode** before pushing to production server

### Deployment Checklist

For normal hosted releases:

1. merge the validated change into `master`
2. deploy hosted separately with `Deploy hosted production` if the hosted environment actually needs to move
3. cut a `v*` tag from the merged commit only when you want to publish to the public repo
4. verify the workflow/logs appropriate to the path you used

Break-glass only:

1. SSH into production VM
2. run `NOVWR_DEPLOY_REF=<tag-or-sha> bash scripts/deploy_hosted.sh`
3. verify healthcheck and logs before declaring recovery complete

### Hotfix Protocol

For critical live-site bugs:

1. fix on a branch, test locally
2. PR + merge (skip CI wait only if site is down)
3. deploy hosted with the dedicated deploy workflow if the site needs recovery; cut a patch tag separately when you also want a public release
4. post-mortem: what broke, why, how to prevent

## Monitoring

- Check `systemctl status novwr litellm` for process health
- Check `journalctl -u novwr -n 50` for recent backend logs
- Event tracking is enabled — check `events` table for user activity funnel
- Token usage tracked in `token_usage` table for cost monitoring

## What NOT to Do

- Do not run `DELETE` or `UPDATE` directly on production SQLite
- Do not restart services during peak hours without checking active connections
- Do not push untested frontend builds — broken UI = instant user churn
- Do not change `.env` on production without documenting what changed and why

## Related Specs

- Pre-launch mode (archived): `./pre-launch-mode.md`
- PR flow: `./pr-delivery-workflow.md`
- Error handling: `../backend/error-handling.md`
