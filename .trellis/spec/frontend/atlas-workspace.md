# Atlas Workspace

Use this spec for non-discoverable Atlas decisions: why Atlas exists, what belongs there instead of `Studio`, and the information-architecture rules that keep it usable as a deep-work surface.
Keep exact visual recipes, token values, and component structure in code.

## Role

`Atlas` is the strategic world-governance surface. It exists so `Studio` can stay focused on daily chapter work, results review, and single-object inspection instead of becoming a mega-screen.

See `web/src/pages/NovelAtlasPage.tsx`, `web/src/components/atlas/`, and `web/src/components/novel-shell/`.

For the current implementation-oriented layout and mode design, see `atlas-design-spec.md`.

## Core Decisions

### Decision: Atlas is for deep governance, not overflow UI
Atlas owns world-model work that is denser, riskier, or structurally broader than the lightweight inspection allowed in `Studio`. Rejected: treating Atlas as a dumping ground for controls that do not fit elsewhere. See `web/src/pages/NovelAtlasPage.tsx` and `.trellis/spec/frontend/product-ux-contracts.md`.

### Decision: Atlas keeps a three-zone workspace
Atlas uses a stable three-zone layout — navigator, center stage, and copilot workbench — because world governance needs persistent scan, inspect, and inquiry surfaces at the same time. Rejected: modal or stacked flows that hide one of those activities. See `web/src/pages/NovelAtlasPage.tsx`, `web/src/components/novel-shell/NovelShellLayout.tsx`, and `web/src/components/novel-copilot/NovelCopilotDrawer.tsx`.

### Decision: navigator panels are scan-first only
Atlas navigators exist to search, filter, sort, and select. Long descriptions, evidence reading, and dense editing belong in the center stage. Rejected: overloading left rails with detail content. See `web/src/components/atlas/entities/EntityNavigator.tsx`, `web/src/components/atlas/review/DraftReviewNavigator.tsx`, and `web/src/components/atlas/relationships/RelationshipSidebarPanel.tsx`.

### Decision: Review is an ephemeral governance mode
The Review tab appears only when the user enters draft review and should disappear when they move back to a primary world mode. Rejected: permanently reserving top-level tab space for an intermittent batch-governance workflow. See `web/src/pages/NovelAtlasPage.tsx` and `web/src/components/atlas/review/`.

### Decision: graph and batch governance stay Atlas-only
Relationship graph exploration, batch confirm/reject flows, topology-changing edits, and structural system editing stay in Atlas so `Studio` can remain artifact-first and single-object oriented. Rejected: allowing those flows to creep back into the daily workspace. See `web/src/pages/NovelAtlasPage.tsx`, `web/src/components/world-model/relationships/RelationshipsTab.tsx`, and `web/src/components/world-model/shared/DraftReviewTab.tsx`.

### Decision: Atlas must preserve Studio continuity
Entering Atlas should preserve enough origin and workbench context that the user feels they are still inside one novel workspace. Rejected: raw detours that strand the user in a separate product-feeling page. See `web/src/components/novel-shell/NovelShellRouteState.ts`, `web/src/pages/NovelAtlasPage.tsx`, and `.trellis/spec/frontend/runtime-contracts.md`.

## Interaction Boundary

Atlas should be the default home for:

- relationship graph work
- batch draft review and queue governance
- relationship endpoint changes
- entity deep maintenance with broader cleanup intent
- system constraints / hierarchy / timeline / list structure editing
- future merge / split / dedupe governance

Atlas should not absorb work that is better finished inline with writing or results review:

- single-object inspection that users should finish quickly and then return from
- lightweight confirmation of one suggestion or one draft item
- low-risk metadata edits that are tightly coupled to the current chapter or results context

## Design Guardrails

### Don’t: let Atlas become “where clutter goes”
If a proposed feature only lands in Atlas because the current page is messy, the problem is likely unresolved information architecture rather than correct Atlas scope. Instead: prove the feature is genuinely deep-governance, graph-oriented, batch-oriented, or structurally broad. See `web/src/pages/NovelAtlasPage.tsx`.

### Don’t: turn the center stage into a second sidebar
Atlas center-stage panels should remain the primary reading/editing surface. Splitting too much detail into secondary panes makes governance slower and less legible. See `web/src/pages/NovelAtlasPage.tsx` and `web/src/components/world-model/entities/EntityDetail.tsx`.

> **Gotcha**: Atlas density is intentional, but density is not the same as clutter. If a queue needs more than one-line scanning plus status context, move the extra detail into the center stage instead of growing the navigator.

## Related Specs

- page ownership and Studio/Atlas flow -> `product-ux-contracts.md`
- Atlas shell and graph tripwires -> `component-guidelines.md`
- route-state and cross-surface continuity -> `runtime-contracts.md`
