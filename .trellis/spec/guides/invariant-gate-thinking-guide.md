# Invariant Gate Thinking Guide

Use this when rapid iterations risk drifting from intended product behavior.

## When to Apply

- default CTA/flow changed
- automation may overwrite user-managed data
- technical maintenance is hidden behind user actions
- team keeps relying on "remember this next round"

## Core Rule

In pre-launch mode, breaking old behavior is allowed; leaving new behavior unguarded is not.

Protect the **new contract**, not legacy expectations.

## Fast Process (5 min)

1. define 2-4 invariant IDs (`X-01`, `X-02`)
2. write one-line pass condition for each
3. add focused backend/frontend gate tests
4. wire tests into CI
5. if implementation not done yet, mark temporary skeleton tests and remove them once done

## Minimal Template

```text
X-01 Default path does A (not B)
X-02 User-edited data is not auto-overwritten
X-03 Ambiguous dangerous state fails fast with actionable error
```

## Anti-Patterns

- skipping tests because "pre-launch can break things"
- only broad integration tests, no explicit invariants
- leaving skeleton markers forever
