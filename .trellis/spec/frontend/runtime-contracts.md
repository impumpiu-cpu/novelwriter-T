# Runtime Contracts

Use this doc for client-side state ownership, persistence scope, and trust-boundary rules.
Keep implementation details in code.

## State Ownership

### Decision: keep one owner per state class
Server data lives in TanStack Query, shareable navigation state lives in the URL, cross-cutting stable dependencies live in Context, and transient UI lives in local state. Rejected: mirroring the same resource across query cache, Context, and `useState`, because it creates drift and invalidation bugs. See `web/src/hooks/world/`, `web/src/pages/NovelAtlasPage.tsx`, and `web/src/contexts/AuthContext.tsx`.

### Decision: `NovelShell` owns the shared copilot workspace per novel
Route parsing, drawer width, toast scope, and the durable copilot session/run controller live at the shell level so Studio and Atlas behave like one workspace. Rejected: page-local copilot providers or drawer-owned run controllers, because they lose session/run continuity on surface switches and duplicate shell chrome state. See `web/src/components/novel-shell/NovelShell.tsx`, `web/src/components/novel-shell/NovelShellProvider.tsx`, `web/src/components/novel-copilot/NovelCopilotProvider.tsx`, `web/src/hooks/novel-copilot/useNovelCopilotRuns.ts`, and `web/src/__tests__/NovelShell.test.tsx`.

### Don't: keep shadow copies of server resources
Do not fetch/query a resource and then treat a copied `useState` version as the new source of truth. Keep only the minimal edit buffer or selection state that cannot live in the cache. See `web/src/pages/NovelStudioPage.tsx` for the chapter-edit buffer pattern.

### Decision: context-switch resets use remounts or deterministic fallback
When UI state should reset on a changed entity/chapter/context, prefer keyed remounts or deterministic fallback selection over repair effects that chase stale state after the fact. See `web/src/components/world-model/relationships/RelationshipsTab.tsx` and `web/src/pages/NovelAtlasPage.tsx`.

## Routing and Persistence

### Decision: generation results must be replay-safe inside the `Studio` host route
The results stage may consume `streamParams` only on the first mount. Once continuation ids exist, persist them to the `Studio` URL and clear history state so reloads, back/forward, and results-derived light-inspection detours never trigger a second generation. See `web/src/components/studio/stages/ContinuationResultsStage.tsx`, `web/src/pages/NovelStudioPage.tsx`, and `web/src/pages/GenerationResults.tsx`.

### Decision: `Atlas` returns to `Studio` via structured origin state, not raw paths
`Atlas` keeps durable tab/review/entity/system state in its own URL, but the return target back into `Studio` is encoded as structured origin params (`originStage`, chapter/entity/system/review state, results provenance, artifact panel state). Rejected: piping a raw `returnTo` URL through query state, because it is opaque and easy to stale-break during route convergence. See `web/src/components/novel-shell/NovelShellRouteState.ts`, `web/src/pages/NovelStudioPage.tsx`, and `web/src/pages/NovelAtlasPage.tsx`.

### Decision: `Atlas` entity selection is URL-scoped, with validity fallback
Keep the selected entity in the `Atlas` URL so deep links, copilot locate actions, and `Studio` -> `Atlas` hops land on the same entity context across refresh and back/forward navigation. If the entity disappears, fall back to the first remaining entity instead of keeping a dangling selection. See `web/src/pages/NovelAtlasPage.tsx` and `web/src/components/novel-shell/NovelShellRouteState.ts`.

### Decision: onboarding and review-local storage is novel-scoped, not global
Local dismiss/whitelist keys are scoped per novel. For onboarding, the key must include stable novel identity (`novelId` + `created_at`) rather than raw id alone, because SQLite id reuse can otherwise carry dismissal state into a different book. See `web/src/lib/worldOnboardingStorage.ts`, `web/src/lib/postcheckWhitelistStorage.ts`, and `web/src/__tests__/worldOnboardingStorage.test.ts`.

### Decision: UI locale is one global client preference, persisted locally and mirrored to `document.lang`
The frontend keeps a single UI-locale owner in Context, persists it in local storage, and mirrors the active locale onto `document.documentElement.lang` before and after React boot so supported surfaces switch coherently and downstream consumers can reuse the same signal. Rejected: page-local locale toggles or ad hoc per-feature storage keys, because they silently fork the user-visible language state and make copilot/session defaults drift from the rest of the app. Copilot's default interaction locale should follow this UI-locale seam unless a caller explicitly overrides it for a narrower contract. See `web/src/contexts/UiLocaleContext.tsx`, `web/src/lib/uiLocale.ts`, `web/src/lib/uiMessages.ts`, `web/index.html`, `web/src/components/novel-shell/NovelShellProvider.tsx`, and `web/src/types/copilot.ts`.

> **Gotcha**: keep route-specific locale catalogs out of the root locale provider's static imports. If the global locale seam eagerly imports Atlas/legal/world-model message packs, those strings move into the entry chunk and silently break route-level code splitting; register route packs from the lazy route/module instead. See `web/src/lib/uiMessages.ts`, `web/src/lib/uiMessagePacks/`, `web/src/App.tsx`, and `web/src/__tests__/PublicLocaleSurfaces.test.tsx`.

## Session and Trust Boundaries

### Decision: copilot session reuse keys off normalized research context, not raw route labels
Copilot session identity should follow stable research context (`novel`, `mode`, `scope`, normalized target/context, interaction locale). Page-level route labels such as `stage`, surface-local tab wording, or singular/plural aliases are navigation metadata and must be normalized before they influence reuse. Studio continuity uses `stage`; Atlas continuity uses `tab`, and plural atlas stage aliases are legacy input only. Rejected: letting raw route-state strings define session identity, because Studio/Atlas route refactors silently fork the user's research workspace without changing what they are researching. Shared launcher helpers should build that normalized context instead of each page hand-composing it. See `web/src/types/copilot.ts`, `web/src/components/novel-copilot/novelCopilotLauncher.ts`, `web/src/components/novel-shell/NovelShellRouteState.ts`, `web/src/pages/NovelStudioPage.tsx`, `web/src/pages/NovelAtlasPage.tsx`, `app/core/copilot.py`, and `tests/test_copilot.py`.

### Decision: copilot launches come from shared launcher helpers
Pages may decide when to open copilot, but `prefill` + display-title construction belongs in shared launcher helpers so session identity, quick-action semantics, and surface metadata stay aligned across Studio, Atlas, and standalone world-build embeddings. Rejected: hand-composing `mode/scope/tab/surface/stage` strings at each callsite, because those drift into accidental session forks and inconsistent drawer titles. See `web/src/components/novel-copilot/novelCopilotLauncher.ts`, `web/src/pages/NovelStudioPage.tsx`, `web/src/pages/NovelAtlasPage.tsx`, `web/src/components/world-model/entities/EntityDetail.tsx`, `web/src/components/atlas/relationships/RelationshipSidebarPanel.tsx`, and `web/src/components/atlas/review/DraftReviewNavigator.tsx`.

### Decision: backend copilot session resolution is single-flight per local session
Opening the drawer may prefetch the backend session, but every later run/apply/dismiss path must reuse the same in-flight resolver until the open-session request key changes. Rejected: separate warmup and submit paths that each call `openSession`, because they create duplicate session-open traffic and race over which `backendSessionId` is authoritative. Backend session reuse may update the session's UI continuity hints, so run creation must rely on the backend's run-time context snapshot rather than assuming the session row is immutable. See `web/src/hooks/novel-copilot/useNovelCopilotSessions.ts`, `web/src/hooks/novel-copilot/useNovelCopilotRuns.ts`, `web/src/__tests__/NovelCopilotDrawer.test.tsx`, `app/core/copilot.py`, and `tests/test_copilot.py`.

### Decision: copilot target routing belongs to the active surface, not to cards
Suggestion cards emit structured targets only. Atlas and Studio translate those targets into their own URL/stage semantics through shared navigation helpers so highlight, review-kind, and fallback-to-Atlas behavior stay in one place. Rejected: card-local route mutation, because it drifts from page-level entity/system/review contracts as the shell evolves. See `web/src/components/novel-copilot/useCopilotTargetNavigation.ts`, `web/src/components/novel-copilot/NovelCopilotSuggestionCard.tsx`, `web/src/pages/NovelAtlasPage.tsx`, and `web/src/pages/NovelStudioPage.tsx`.

### Decision: Atlas review target highlight is URL-driven and must light up both navigator and content
When copilot target navigation lands on Atlas review items, the shared `highlight` URL param is the source of truth for both the review navigator selection and the review content-card highlight. Rejected: driving only the content pane from URL while the navigator keeps a separate local highlight state, because the selected target becomes hard to spot in light mode and after direct URL navigation. See `web/src/pages/NovelAtlasPage.tsx` and `web/src/__tests__/NovelAtlasPage.test.tsx`.

### Decision: BYOK config is session-local tab memory
The frontend may let the user enter BYOK settings, but that config lives only in the current tab's in-memory store. Refreshing the page clears it, and hosted mode must warn that requests are proxied through the current instance. See `web/src/lib/llmConfigStore.ts` and `web/src/components/settings/LlmConfigCard.tsx`.

### Decision: logout clears local state even if the network call fails
Local cleanup wins over logout transport success. On logout, clear query cache, in-memory BYOK config, and user state to avoid half-logged-out sessions. See `web/src/contexts/AuthContext.tsx` and `web/src/__tests__/useAuth.test.ts`.

### Decision: `apiClient.ts` owns transport/errors; feature modules own response narrowing
Generic fetch policy, retries, structured error extraction, and request-header policy belong in `services/apiClient.ts`, while feature-specific response narrowing belongs in `services/copilotApi.ts` or other service modules. Components/hooks consume typed results and must treat `localStorage`, URL params, and arbitrary error bodies as untrusted until narrowed. See `web/src/services/apiClient.ts`, `web/src/services/copilotApi.ts`, `web/src/services/api.ts`, `web/src/lib/worldOnboardingStorage.ts`, and `web/src/lib/postcheckWhitelistStorage.ts`.

### Decision: API warnings use descriptor-first rendering with message fallback
Typed warning payloads may include both a rendered `message` and an i18n descriptor (`message_key`, `message_params`). Frontend components should treat the descriptor as the durable contract for future locale switching and use `message` only as a fallback when no local translation exists. See `web/src/types/api.ts`, `web/src/components/world-model/shared/WorldpackPanel.tsx`, and `web/src/pages/GenerationResults.tsx`.

## Related Specs

- Server-state and retry policy: `hook-guidelines.md`
- UI tripwires: `component-guidelines.md`
- Product/page behavior: `product-ux-contracts.md`
