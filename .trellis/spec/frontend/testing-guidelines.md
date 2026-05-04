# Testing Guidelines

Use this doc for project-specific frontend regression expectations.
Keep helper names, file naming, command lines, and fixture shapes in code.

## Core Principle

### Decision: test behavior and contracts, not styling
Assert on user-visible behavior, API contracts, navigation, and state recovery. Rejected: DOM-structure, CSS-class, or token snapshots, because pre-launch UI iteration is fast and visual recipes already live in code. See `web/src/__tests__/` and `web/e2e/`.

## Merge-Gate Contract

### Decision: frontend CI must cover the core authoring loop
Keep merge-gated coverage across auth, library, import/onboarding, world-model review/edit, continue, and adopt. Add a focused regression whenever a bug changes one of these transitions. See `web/e2e/mock/app.spec.ts`, `web/e2e/mock/world-onboarding-and-generation.spec.ts`, `web/e2e/integration/upload-workflow.spec.ts`, `web/e2e/integration/world-model.spec.ts`, and `web/e2e/integration/worldpack-import.spec.ts`.

### Decision: real-LLM E2E is optional but maintained
The real-LLM world-generation path is a supported contract, but local/CI runs may skip it when the backend key is absent or `E2E_SKIP_LLM=1`. Rejected: making paid LLM availability a hard gate for every run. See `web/e2e/integration/world-generation-llm.spec.ts`.

## Gotchas Worth Locking Down

> **Gotcha**: New empty-world novels intentionally hide the normal chapter UI until onboarding is dismissed or world data exists. Tests that expect the chapter sidebar/editor must dismiss onboarding first. See `web/e2e/integration/upload-workflow.spec.ts` and `web/src/components/detail/EmptyWorldOnboarding.tsx`.

> **Gotcha**: Bootstrap CTA wording/behavior is a product invariant. Keep regression coverage that prevents `index_refresh` from reappearing as the first-run primary action. See `web/src/__tests__/BootstrapPanel.invariants.test.tsx`.

> **Gotcha**: Results reload/history behavior must never restream generations. When changing results-stage routing, add regression coverage around persisted continuation ids, Studio URL replay, and compatibility-entry safety. See `web/src/components/studio/stages/ContinuationResultsStage.tsx`, `web/src/pages/NovelStudioPage.tsx`, and `web/src/pages/GenerationResults.tsx`.

### Decision: assert on structured errors, not free-text diagnostics
Failure-path tests should match `status`, `code`, or mapped frontend copy rather than backend diagnostic text. See `web/src/__tests__/api.test.ts` and `web/src/__tests__/llmErrorMessages.test.ts`.

## Related Specs

- Product/page flow: `product-ux-contracts.md`
- State ownership and persistence: `runtime-contracts.md`
- Server-state error handling: `hook-guidelines.md`
