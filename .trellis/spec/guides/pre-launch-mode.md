# Pre-Launch Development Mode

> Status: ACTIVE (since 2026-02-09)
> Deactivate only by explicit CEO instruction.

## Priority Order

1. architecture consistency > backward compatibility
2. small rollbackable changes > big-bang rewrites
3. spec/test/code stay in sync

## Required for Every Change

1. deletion notes (what removed and why)
2. rollback path (`git revert <hash>`)
3. regression coverage for the **current intended behavior**
4. residual risk + next minimal follow-up

## Regression Coverage vs Backward Compatibility

In pre-launch these are separate:

- backward compatibility may be intentionally broken
- regression tests are still mandatory to lock the **new** product contract

Example: if first-run bootstrap action changes from index-maintenance to extraction,
legacy behavior can be removed, but tests must enforce the new first-run flow.

## Memory Sync (End of Task)

Update only what changed:

- architecture/API docs
- Trellis session record
- `MEMORY.md` for important new constraints/patterns

## Related Specs

- Quality rules: `../backend/quality-guidelines.md`
- Invariant gate method: `./invariant-gate-thinking-guide.md`
- Error handling: `../backend/error-handling.md`
- PR flow: `./pr-delivery-workflow.md`
