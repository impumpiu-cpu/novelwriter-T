# Thinking Guides

Use only the guide needed for the current task to keep context small.

## Guide Map

| Guide | Use when |
|---|---|
| [Pre-Launch Mode](./pre-launch-mode.md) | every task (current global mode) |
| [Invariant Gate Thinking](./invariant-gate-thinking-guide.md) | changing default flow, overwrite boundaries, hidden orchestration |
| [Cross-Layer](./cross-layer-thinking-guide.md) | feature spans multiple layers/contracts |
| [Code Reuse](./code-reuse-thinking-guide.md) | about to create a new module/function/component; refactors touching many files |
| [Frontend Refactor](./frontend-refactor-thinking-guide.md) | refactoring UI/pages for reuse + token/Tailwind consistency |
| [PR Delivery](./pr-delivery-workflow.md) | branch/PR/CI/merge operations |

## Internal Guides

Private-only references that should stay out of public-facing docs/spec loading by default.

| Guide | Use when |
|---|---|
| [Internal Guide Index](./internal/index.md) | locating private ops/dev references |
| [GCP Hosted Ops](./internal/gcp-hosted-ops.md) | hosted runtime assumptions and operator tripwires |
| [Backend Python Environment](./internal/backend-python-environment.md) | backend Python execution environment rules |
| [Bootstrap Experiment Archive](./internal/bootstrap-experiment-archive.md) | historical bootstrap optimization outcomes |

## Trigger Shortcuts

- cross-layer change -> open Cross-Layer guide
- about to copy/paste or create a "new but similar" module -> open Code Reuse guide
- product-contract drift risk -> open Invariant Gate guide
- delivery/merge work -> open PR Delivery guide

## Pre-Modification Rule

Before changing any literal value, search global usage first:

`rg -n "value_to_change" .` (or `grep -RIn -- "value_to_change" .`)
