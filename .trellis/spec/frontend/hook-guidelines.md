# Hook Guidelines

Use this doc for server-state, mutation, retry, and provider-boundary contracts that are not obvious from type signatures alone.
Keep query-key factories, hook names, and low-level TanStack wiring in code.

## Mutation Contracts

### Decision: mutation strategy follows interaction frequency
High-frequency inline edits and visibility toggles stay optimistic; create flows that need server-assigned ids stay pessimistic; destructive/batch actions stay explicit-confirm + pessimistic. Rejected: one global rule for every mutation, because the product relies on different latency trade-offs for editing vs creation. See `web/src/hooks/world/useEntities.ts`, `web/src/hooks/world/useRelationships.ts`, `web/src/hooks/world/useSystems.ts`, and `web/src/hooks/novel/`.

### Decision: background-job triggers patch cache immediately
If a mutation response already contains the new bootstrap job state, write it into the query cache before waiting for the next polling cycle. Otherwise the UI looks idle right after a successful trigger. See `web/src/hooks/world/useBootstrap.ts`.

## Error Contracts

### Decision: frontend errors branch on `(status, code)`
`ApiError.message` is intentionally generic. UI copy and control flow must branch on `status` + stable `code`, and `requestId` is only for debugging/support correlation. See `web/src/services/apiClient.ts`, `web/src/services/copilotApi.ts`, `web/src/__tests__/api.test.ts`, and `web/src/__tests__/llmErrorMessages.test.ts`.

### Decision: copilot quota exhaustion must not collapse into generic 429 busy copy
Copilot run-create UX must distinguish user quota exhaustion (for example `generation_quota_exhausted`) from concurrency throttles such as `too_many_active_runs`. Rejected: one shared “当前请求较多” message for every 429, because it hides the actual recovery path when the user simply ran out of quota. See `web/src/hooks/novel-copilot/useNovelCopilotRuns.ts` and `web/src/__tests__/NovelCopilotDrawer.test.tsx`.

### Don't: swallow broad classes of HTTP errors
Only the documented optional-resource code path may collapse into `null`/idle UI state (for example `bootstrap_job_not_found`). Swallowing all 404s or all 5xxs hides real regressions such as missing novels or broken permissions. See `web/src/hooks/world/useBootstrap.ts` and `web/src/__tests__/useBootstrap.test.ts`.

### Decision: some 503s are domain-terminal, not retryable
Structured availability errors such as manual AI disable, hard-stop quota, or disabled budget metering must bypass automatic retries even if the transport status is 503. Rejected: retrying every 503, because it delays user feedback for known terminal states. See `web/src/services/apiClient.ts` and `web/src/__tests__/api.test.ts`.

## Boundary Contracts

### Decision: BYOK headers attach only to LLM endpoints
User-supplied LLM headers may go to continuation, world-generation, bootstrap, copilot, and test endpoints, but never to generic CRUD/auth requests. This limits accidental secret exposure through unrelated proxies or logs. See `web/src/services/apiClient.ts`, `web/src/services/api.ts`, `web/src/services/copilotApi.ts`, and `web/src/__tests__/api.test.ts`.

### Decision: standalone workbench embeddings should reuse the shared provider stack
Copilot session/run hooks assume `NovelCopilotProvider`, and workbench actions that toast failures assume a `ToastProvider`. Standalone embeddings should go through the shared `WorldBuildPanel` wrapper rather than mounting drawer pieces ad hoc. See `web/src/components/novel-shell/NovelShell.tsx`, `web/src/components/novel-copilot/NovelCopilotProvider.tsx`, and `web/src/components/world-model/shared/WorldBuildPanel.tsx`.

### Decision: copilot controller hooks live above drawer views
Run hydration, polling, apply, and dismiss behavior belong in `NovelCopilotProvider` + controller hooks, while `NovelCopilotDrawer` renders already-owned state only. Rejected: view-local controller lifecycles that reset on unmount or route switches. See `web/src/components/novel-copilot/NovelCopilotProvider.tsx`, `web/src/hooks/novel-copilot/useNovelCopilotRuns.ts`, and `web/src/components/novel-copilot/NovelCopilotDrawer.tsx`.

## Related Specs

- UI/product tripwires: `component-guidelines.md`
- State ownership and trust boundaries: `runtime-contracts.md`
- Product/page flow: `product-ux-contracts.md`
