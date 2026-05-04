# Code Reuse Thinking Guide

> Prevent drift: reuse existing code paths before creating new ones.

## Quick Checklist (Before You Write)

- Search for an existing implementation in the relevant layer.
- Prefer extending a shared component/hook/service over creating a parallel version.
- Put shared code where it belongs (so the next person finds it quickly).
- If you touched many files, re-run a search to ensure no callers were missed.

## Fast Search (Avoid `node_modules/`)

Prefer `rg` if available; fallback to `grep`.

```bash
# Frontend
rg -n "ThingName|useThing" web/src || grep -RIn -- "ThingName\|useThing" web/src

# Backend
rg -n "thing_name|ThingName" app || grep -RIn -- "thing_name\|ThingName" app
```

## Where to Reuse (Most Common)

- visual recipe → `web/src/components/ui/` (tokens + variants)
- feature behavior → `web/src/components/<feature>/`
- data fetching/mutations → `web/src/hooks/*/` (TanStack Query)
- pure helpers/formatting → `web/src/lib/`
- HTTP boundary → `web/src/services/api.ts`

## Duplication Red Flags (High Drift Risk)

- Copy/paste of a Tailwind “glass recipe” bundle instead of using a shared primitive
- Re-defining query keys instead of using the key factory
- A second API wrapper for the same endpoint
- Repeating error mapping logic instead of branching on `(status, code)` in one place

## When to Abstract vs Keep Local

- **Abstract** when the same idea appears 2+ times *and* drift would hurt (tokens, query keys, validation, contracts).
- **Definitely abstract** at 3+ copies.
- **Keep local** for a true one-off; don’t invent an abstraction that’s harder than the duplication.

## After a Sweep / Refactor

- Re-run search for old names/strings to catch stragglers.
- Delete dead modules (pre-launch mode favors removal over deprecation).
- Update the spec/tests that describe the contract if behavior changed.

## Related Specs

- Frontend guide index: `../frontend/index.md`
- UI recipes and tokens: `../frontend/component-guidelines.md`
- Server-state conventions: `../frontend/hook-guidelines.md`
- State ownership and trust boundaries: `../frontend/runtime-contracts.md`
