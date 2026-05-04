# Component Guidelines

Use this doc for frontend UI contracts that are easy to break during refactors.
Keep visual recipes, token values, and component prop surfaces in code.

## Shell and Layering Contracts

### Decision: animated background is a shell contract, not page-local decoration
`PageShell` owns the ambient background. Route-level wrappers must stay transparent; adding opaque background layers on intermediate layout/page wrappers hides the blobs and makes glass surfaces read like solid cards. See `web/src/components/layout/PageShell.tsx`, `web/src/components/layout/AnimatedBackground.tsx`, and `web/src/index.css`.

### Decision: workspace routes optimize for interaction latency over heavy glass effects
Marketing/auth routes may keep the animated ambient background and stronger glass styling, but authenticated authoring routes (`Library`, `Studio`, `Atlas`, `Settings`) should default to static backgrounds and avoid large-area `backdrop-filter` blur. Reserve stronger blur for small floating layers such as toasts, sheets, and dialogs. Rejected: reusing the landing-page glass recipe across the authoring workspace, because large animated/blurred surfaces visibly degrade hover and text-input responsiveness. See `web/src/contexts/PerformanceModeContext.tsx`, `web/src/components/layout/AnimatedBackground.tsx`, `web/src/components/ui/glass-surface.tsx`, and `web/src/index.css`.

### Decision: `Atlas` owns its own full-height shell
`/world/:novelId` is allowed to opt out of the default navbar/scroll contract so its sidebars, graph canvas, and sheets can manage nested scrolling without the whole page moving. When changing route shells, preserve the `App.tsx` special-casing instead of wrapping `NovelAtlasPage` in another generic page container. See `web/src/App.tsx` and `web/src/pages/NovelAtlasPage.tsx`.

## World-Building Entry Contracts

### Decision: bootstrap speaks extraction, not index maintenance
The primary bootstrap CTA stays `从章节提取` on first run and after initialization. `index_refresh` is maintenance-only and must not become the visible primary action again. See `web/src/components/world-model/shared/BootstrapPanel.tsx` and `web/src/__tests__/BootstrapPanel.invariants.test.tsx`.

### Decision: bootstrap and copilot surfaces must read the explicit index lifecycle contract
Status copy about retrieval readiness must come from the novel's window-index lifecycle (`fresh`, `stale`, `missing`, `failed` plus active rebuild job), not from bootstrap job history alone. Bootstrap UI may show extraction progress/history, but copilot readiness text should explain when the app is temporarily falling back to recent chapters instead of implying the user must manually rerun bootstrap first. See `web/src/components/world-model/shared/BootstrapPanel.tsx`, `web/src/components/novel-copilot/NovelCopilotCard.tsx`, `web/src/hooks/novel/useNovelWindowIndex.ts`, and `web/src/__tests__/WorldBuildPanel.test.tsx`.

### Decision: world-build entry is shared module infrastructure
`WorldBuildPanel` is available from the world-model module regardless of the current tab. Do not relegate generation/bootstrap entry to a single tab; the shared sidebar entry is part of the information architecture. When mounted outside `NovelShell`, it must self-host the minimal `ToastProvider` + `NovelCopilotProvider` stack and local drawer so the same entry still works in standalone embeddings. See `web/src/components/world-model/shared/WorldBuildPanel.tsx`, `web/src/__tests__/WorldBuildPanel.test.tsx`, and `web/e2e/mock/world-onboarding-and-generation.spec.ts`.

### Decision: empty-world onboarding intentionally displaces the Studio workspace
When a novel has no entities/systems and no running bootstrap job, the `/novel/:novelId` Studio route shows the onboarding gate instead of the normal chapter workflow. Treat this as the intended first-run path, not a small dismissible banner. See `web/src/pages/NovelStudioPage.tsx` and `web/e2e/integration/upload-workflow.spec.ts`.

## Graph Tripwires

### Gotcha: relationship graph must remount on center-entity change
The React Flow instance is keyed by the selected entity so `fitView` re-runs and stale invisible nodes do not persist across selection changes. Reusing the same instance without remounting breaks the graph reset contract. See `web/src/components/world-model/relationships/RelationshipsTab.tsx` and `web/src/components/world-model/relationships/StarGraph.tsx`.

### Don't: remove the hidden handles from the star-graph custom node
The relationship graph uses explicit handles on every side of the custom node. Deleting them looks like harmless cleanup but causes edges to stop rendering. See `web/src/components/world-model/relationships/StarGraph.tsx`.

## Copilot Surface Tripwires

### Decision: copilot suggestion cards stay route-agnostic
Shared workbench cards may preview, apply, or dismiss suggestions, but target navigation belongs to surface-specific handlers (`Atlas` vs `Studio`). Rejected: embedding fallback URL mutation inside the generic card, because the same structured target resolves differently across Atlas tabs, Studio stages, and Atlas fallback navigation. See `web/src/components/novel-copilot/NovelCopilotSuggestionCard.tsx`, `web/src/components/novel-copilot/useCopilotTargetNavigation.ts`, `web/src/pages/NovelAtlasPage.tsx`, and `web/src/pages/NovelStudioPage.tsx`.

## Related Specs

- Product/page ownership: `product-ux-contracts.md`
- Server-state and error contracts: `hook-guidelines.md`
- State ownership and persistence scope: `runtime-contracts.md`
