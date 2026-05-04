# Frontend Spec Index

Use frontend specs for non-discoverable frontend decisions, UX contracts, tripwires, and routing pointers.
Do not copy component props, CSS token values, folder trees, or test commands that can be read directly from code.

## Always-On Constraints

- pre-launch mode is active (`../guides/pre-launch-mode.md`)
- frontend docs stay in English even when the product UI is Chinese
- prefer pointing to canonical code/tests over restating implementation

## Specs

| Spec | Use when |
|---|---|
| [Atlas Design Spec](./atlas-design-spec.md) | implementing Atlas layout, workspace modes, and detailed deep-governance interaction design |
| [Atlas Workspace](./atlas-workspace.md) | deep world-governance IA, Studio-vs-Atlas boundary, and Atlas-specific UX guardrails |
| [Component Guidelines](./component-guidelines.md) | UI-shell contracts, world-building entry points, graph/layout tripwires |
| [Hook Guidelines](./hook-guidelines.md) | server-state, mutation, retry, and provider-boundary contracts |
| [Runtime Contracts](./runtime-contracts.md) | state ownership, URL/storage scope, session boundaries, trust boundaries |
| [Testing Guidelines](./testing-guidelines.md) | behavior-first regression scope and CI merge-gate expectations |
| [Product UX Contracts](./product-ux-contracts.md) | page ownership, navigation flow, and product-facing frontend behavior |

## Quick Routing

- page shell / onboarding / world-model UI tripwires -> `component-guidelines.md`
- Atlas current layout / tab / continuity design -> `atlas-design-spec.md`
- Atlas deep-work IA / Studio-vs-Atlas boundary -> `atlas-workspace.md`
- optimistic vs pessimistic mutation / structured error handling -> `hook-guidelines.md`
- URL vs local state / BYOK session scope / reload safety -> `runtime-contracts.md`
- E2E merge gate / onboarding and replay gotchas -> `testing-guidelines.md`
- page roles / latest-only continuation / world-model behavior -> `product-ux-contracts.md`

## Local Dev (WSL + Windows Browser)

> **Gotcha**: Keep `VITE_API_URL` unset and rely on the Vite `/api` dev proxy (see `web/vite.config.ts`). Do not point the frontend at `http://localhost:8000` when the browser runs on Windows: `localhost` resolves on Windows, not WSL, and selfhost mode usually does not enable direct cross-origin calls.
