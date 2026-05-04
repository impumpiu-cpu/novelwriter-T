# Product UX Contracts

Use this doc for product-facing frontend decisions: page ownership, navigation flow, and behavioral contracts.
Keep visual styling recipes in code and UI tripwires in `component-guidelines.md`.

## Product Positioning

NovWr is an AI continuation tool for ultra-long web novels. The frontend must keep the product centered on cheap iteration: generate, compare, discard, refine, and only promote world-model changes after explicit user review.

## Page Ownership

| Page | Role | Core responsibility |
|---|---|---|
| Landing `/` | acquisition | explain the product and route users into auth |
| Login `/login` | auth entry | establish the session |
| Library `/library` | work overview | create/import/open/delete novels |
| Studio `/novel/:novelId` | daily novel workspace | read/edit chapters, host the latest-only continuation setup via `?stage=write`, export, and enter world-building |
| Atlas `/world/:novelId` | strategic editing | review and edit entities, relationships, systems |
| Results `/novel/:novelId/chapter/:chapterNum/results` | compatibility entry | redirect into the `Studio` results stage instead of owning a separate workspace |
| Settings `/settings` | operator/user preferences | account, appearance, and session-local BYOK configuration |

## Navigation Flow Contracts

### Decision: `Studio` is the default hub, including results review
The normal flow is Library -> Studio -> Studio write/results/light inspection -> Atlas when needed -> Studio. Results review is an in-shell `Studio` stage, and results-derived entity/relationship/system inspection should change only the center stage so left/right rails remain stable. See `web/src/pages/NovelStudioPage.tsx` and `web/src/components/studio/stages/ContinuationResultsStage.tsx`.

### Decision: Atlas exposes one return-to-Studio action, not competing exits
Atlas should present a single `返回工作台` action in the toolbar so the user sees Atlas as one deep-work mode inside the same novel workspace rather than a separate page with multiple escape hatches. When Atlas was opened from a specific Studio state, that action returns to the encoded Studio origin; otherwise it falls back to the novel's default Studio route. See `web/src/pages/NovelAtlasPage.tsx` and `web/src/components/novel-shell/NovelShellRouteState.ts`.

### Decision: continuation is latest-chapter only
The frontend does not offer arbitrary `from_chapter` continuation. The canonical continuation and results entries live on `Studio` via `/novel/:novelId?stage=write|results`; the legacy results route is compatibility-only. The write stage always configures the next continuation from the latest chapter, and revisiting results must never auto-start a new generation. See `web/src/pages/NovelStudioPage.tsx`, `web/src/components/studio/stages/ContinuationResultsStage.tsx`, `web/src/components/novel-shell/NovelShellRouteState.ts`, and `app/schemas.py`.

### Decision: empty-world novels funnel through world-building before normal writing flow
For a fresh novel with no world-model data, `Studio` first offers world generation/bootstrap onboarding. This keeps world-building discoverable without making it a mandatory pre-generation wizard once the novel already has data. See `web/src/pages/NovelStudioPage.tsx` and `web/src/components/detail/EmptyWorldOnboarding.tsx`.

## Behavioral Contracts

### Decision: AI output stays advisory until the user confirms it
Continuation candidates are drafts for chapter adoption, and extracted world-model rows stay draft until the user confirms them. The frontend must keep that review boundary legible instead of auto-promoting AI output. See `web/src/components/studio/stages/ContinuationResultsStage.tsx`, `web/src/pages/GenerationResults.tsx`, and `web/src/components/world-model/shared/DraftReviewTab.tsx`.

### Decision: interrupted copilot runs retry explicitly from the interrupted card
When a copilot run is interrupted, the latest run card may offer a dedicated resume action that retries that exact run and continues its saved workspace. The composer below still means “ask a new question” and must not silently resume stale execution state. Rejected: hiding resume behind the generic composer or automatically treating every post-interruption prompt as a retry. See `web/src/components/novel-copilot/NovelCopilotDrawer.tsx`, `web/src/hooks/novel-copilot/useNovelCopilotRuns.ts`, `app/core/copilot.py`, and `tests/test_copilot.py`.

### Decision: the world model tracks world truth, not plot history
The frontend should guide users toward entities, relationships, systems, and reviewable lore constraints, not event-timeline bookkeeping for story beats. See `web/src/pages/NovelAtlasPage.tsx` and `web/src/components/world-model/`.

### Decision: postcheck warnings are review aids, not hard blockers
Lore-drift warnings may highlight terms, open world-model inspection, or be locally whitelisted, but they do not block draft adoption by themselves. See `web/src/components/studio/stages/ContinuationResultsStage.tsx` and `web/src/lib/postcheckWhitelistStorage.ts`.

### Decision: adopting a continuation must update the chapter rail immediately
When the user adopts a continuation, the app should return to `Studio` with the new chapter already visible in the left chapter rail instead of requiring a reload. See `web/src/components/studio/stages/ContinuationResultsStage.tsx` and `web/src/hooks/novel/useCreateChapter.ts`.

### Decision: Studio chapter navigation uses canonical internal chapter numbering
The `Studio` chapter rail, chapter search, plain-text export, and continuation entry all present chapters using the stable internal `chapter_number` plus editable title. Imported `source_chapter_label` / `source_chapter_number` may remain in storage as source metadata, but they do not drive visible numbering in the current MVP. Rejected: mixing source-book numbering into Studio labels or next-chapter references, because it makes chapter counts and “latest chapter” copy disagree in confusing ways. See `web/src/pages/NovelStudioPage.tsx`, `web/src/lib/chaptersPlainText.ts`, `app/core/continuation_text.py`, and `web/src/__tests__/NovelStudioPage.test.tsx`.

> **Gotcha**: chapter-title normalization in `Studio` should strip only numbered heading prefixes from editable `title`; standalone special titles like `序章` / `Prologue` remain user-visible titles for display, search, and export. See `web/src/lib/chaptersPlainText.ts` and `web/src/__tests__/chaptersPlainText.test.ts`.

## Explicit Non-Goals

- no arbitrary earlier-chapter continuation flow
- no required world-model step before every generation
- no automatic promotion of AI-generated world-model drafts into confirmed data
