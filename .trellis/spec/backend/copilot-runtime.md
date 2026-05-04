# Copilot Runtime

Use this doc for the non-obvious backend contract behind world copilot runs.
Keep API shapes, ORM models, and concrete tool implementations in code; keep the runtime principles and guardrails here.

## Runtime Shape

### Decision: copilot is a scoped research protocol, not a schema wizard
Chose a stable `target -> evidence -> claim -> optional delta` runtime because copilot must support inquiry-only turns, world-model cleanup, and future exploration without hardcoding what kinds of facts a novel is allowed to contain. Rejected: fixed facet/field wizards or mutation-first chat flows that assume every run exists to edit canon. See `app/core/copilot_scope.py`, `app/core/copilot_suggestions.py`, `app/core/copilot_apply.py`, and `app/api/copilot.py`.

### Decision: runtime responsibilities stay split by seam
Chose a seam-based runtime split — orchestration in `copilot.py`, prompt policy in `copilot_prompting.py`, scope loading in `copilot_scope.py`, deterministic tool execution in `copilot_research_tools.py`, loop orchestration in `copilot_tool_loop.py`, workspace state in `copilot_workspace.py`, durable progress persistence in `copilot_run_store.py`, trace shaping in `copilot_tracing.py`, and card compilation in `copilot_suggestions.py`. Rejected: re-expanding one copilot god module, because lease logic, prompt policy, deterministic tool behavior, and result persistence evolve at different speeds and drift when forced through one file. See `app/core/copilot.py` and the adjacent `app/core/copilot_*.py` modules.

### Decision: runtime isolation converges to 3 profiles, with scenario as a lightweight variant
Chose `focused_research`, `draft_governance`, and `broad_exploration` as the backend isolation profiles because entity-vs-relationship work should share the same bounded local-graph loader, while draft cleanup and whole-book exploration need materially different preload and evidence policies. Rejected: a 4-way hard split where entity and relationship become separate runtime architectures, because that duplicates logic without improving isolation. Use scenario/focus only for prompt phrasing and workflow hints; use profile for snapshot loading, preload thickness, and evidence defaults. See `app/core/copilot_scope.py`, `app/core/copilot_prompting.py`, and `tests/test_copilot.py`.

### Decision: long-novel retrieval uses evidence packs plus progressive disclosure
Chose backend-built evidence packs with explicit expansion because ultra-long novels break when many raw passages are stuffed into a single prompt, while backend-written authoritative summaries erase nuance and conflict. Rejected: raw passage dumping as the default copilot context and backend semantic pre-resolution of evidence. See `app/core/copilot_research_tools.py`, `app/core/copilot_workspace.py`, `app/core/copilot_scope.py`, and `tests/test_copilot.py`.

### Decision: copilot reads the explicit window-index lifecycle instead of inferring from blob presence
Chose to branch retrieval behavior on the normalized index lifecycle (`fresh`, `stale`, `missing`, `failed`) because the index is now a first-class derived asset with its own freshness/job seam. `fresh` may use the serialized window index; `stale`, `missing`, and `failed` must degrade predictably to recent-chapter fallback without pretending the index is ready. Rejected: treating `novel.window_index` as a nullable implementation detail and silently collapsing every non-fresh state into the same behavior, because that hides recovery paths and breaks the product contract established by the indexing lifecycle work. See `app/core/indexing/lifecycle.py`, `app/core/copilot/scope.py`, `app/core/copilot/research_tools.py`, and `tests/copilot/test_runtime.py`.

### Decision: research tool surface stays read-only and narrow
Tool-loop work is limited to `load_scope_snapshot`, `find`, `open`, and `read`. Rejected: mutation tools inside the loop, because `apply` must remain the only approval boundary and tool results must stay resumable/verifiable. See `app/core/copilot_research_tools.py`, `app/core/copilot_tool_loop.py`, and `tests/test_copilot.py`.

### Decision: actionable cards must be backend-compiled
Chose backend compilation of model-drafted claims/deltas because probabilistic raw parameters will sometimes point at the wrong target, exceed the allowed write surface, or drift stale before apply. Rejected: exposing model-emitted mutation params directly as clickable actions or trusting display text as the mutation target. See `app/core/copilot_suggestions.py`, `app/core/copilot_apply.py`, `app/core/world_crud.py`, and `app/api/copilot.py`.

### Decision: relationship suggestions synthesize missing endpoint entity cards
When a `create_relationship` suggestion references a named endpoint that is not yet in the world model, the compiler must synthesize dependent `create_entity` suggestions before exposing the relationship as actionable. Rejected: leaving entity-scope relationship cards as advisory-only just because the model forgot to emit the paired entity card, because users read those cards as directly approvable research outcomes. Resolve endpoints against existing names/aliases first, then synthesize only the truly missing ones. See `app/core/copilot_suggestions.py`, `app/core/copilot_apply.py`, and `tests/test_copilot.py`.

### Decision: copilot runs preserve resumable workspaces
Chose resumable run workspaces because multi-step retrieval, long-novel evidence gathering, and intermittent transport failures are normal rather than exceptional. Rejected: treating every interrupted run as disposable and forcing the user to restart the inquiry from scratch. See `app/core/copilot_workspace.py`, `app/core/copilot_tool_loop.py`, `app/core/copilot_run_store.py`, and `tests/test_copilot.py`.

### Decision: follow-up runs reuse durable research memory, not stale execution state
Interrupted runs resume the full saved workspace only when the caller explicitly requests a retry of that interrupted run. Fresh follow-up runs — including new prompts asked after an interruption — instead reuse prior conversation plus evidence-pack memory while resetting round counts, pending tool calls, and exhausted run budget. Rejected: both stateless follow-ups and carrying stale execution state across unrelated turns. See `app/core/copilot.py`, `app/core/copilot_workspace.py`, and `tests/test_copilot.py`.

### Decision: active copilot runs are lease-based and reclaimable
Chose a renewable lease on `queued`/`running` runs because the current hosted shape still launches work in-process, so process loss or dropped transport must not leave orphaned active rows permanently blocking admission. Rejected: trusting `queued` forever or letting a stale worker write back after another actor has already reclaimed the run. Use lease expiry for reclaim, renew on heartbeat/persist points, and treat lease loss as a terminal interruption rather than a recoverable silent fallback. See `app/core/copilot.py`, `app/core/copilot_run_store.py`, `app/models.py`, and `tests/test_copilot.py`.

### Decision: tool-loop degradation stays visible and contract-preserving
If the active model/gateway does not support tools or the tool loop fails for a recoverable reason, copilot may degrade to one-shot analysis, but the run must still persist through the same completed/error contract and the trace must explicitly disclose the degradation. Rejected: surfacing raw recoverable tool failures to end users or silently changing execution mode without trace evidence, because both break trust in suggestion provenance. See `app/core/copilot.py`, `app/core/copilot_tool_loop.py`, `app/core/copilot_tracing.py`, and `tests/test_copilot.py`.

### Decision: hosted copilot quota is run-scoped, not session-scoped
Chose `CopilotRun` as the hosted billing unit because sessions are reusable context shells while each run launches fresh LLM work and can complete, fail, or stale independently. Reserve one quota unit when the run is created, charge only when results are durably persisted as `completed`, and refund on `error` / `interrupted` / stale reclaim. Rejected: gating without reservation, which allows unlimited runs after the first quota check, and charging once per session, which turns long-lived drawers into unlimited free follow-up turns. See `app/api/copilot.py`, `app/core/auth.py`, `app/core/copilot.py`, `app/core/copilot_run_store.py`, and `tests/test_copilot.py`.

### Decision: stored copilot prompt stays user-visible, quick-action focus stays internal
Chose to persist the raw user prompt on `CopilotRun.prompt` and store quick-action intent separately, then synthesize the enriched execution prompt only inside the runtime. Rejected: saving the internal `[研究重点: ...]` scaffold into the public `prompt` field, because the drawer request bubble, hydration, and poll responses should always reflect what the user actually asked. See `app/api/copilot.py`, `app/core/copilot_prompting.py`, `app/core/copilot.py`, `app/models.py`, and `tests/test_copilot.py`.

### Don't: rename quick-action ids in only one layer
Quick-action ids are a cross-layer contract between frontend workbench affordances and backend prompt policy. Update the frontend action registry and backend focus registry together, or the UI will still render the action while the runtime silently falls back to a generic prompt. See `web/src/components/novel-copilot/novelCopilotWorkbench.tsx`, `app/core/copilot_prompting.py`, and `tests/test_copilot.py`.

### Decision: light conversational turns skip heavy preload and suggestion compilation
`smalltalk` and `capability_query` turns should answer from workbench context only; only task turns auto-preload world context and compile suggestions. Rejected: dumping full world summaries or suggestion cards into greetings/capability answers. See `app/core/copilot_prompting.py`, `app/core/copilot_tool_loop.py`, and `tests/test_copilot.py`.

## Language and Identity

### Decision: language is a runtime axis, not a UI afterthought
Chose distinct novel-language, interaction-locale, and prompt-locale concerns because future Japanese/Korean/English support must not require redesigning the copilot protocol. Rejected: translation-first canonicalization or a single implicit locale leaking through prompts, retrieval, and apply. See `app/language_policy.py`, `app/core/copilot_prompting.py`, `app/core/copilot_scope.py`, and `./database-guidelines.md`.

### Decision: copilot runtime copy stays registry-backed
Chose one registry seam for backend copilot runtime copy because inline locale branches across scope loading, research tools, suggestion compilation, apply errors, workspace evidence, and tracing drift quickly and make new languages expensive. Rejected: keeping `choose_locale_text(...)`-style compatibility helpers after the migration. Add new runtime strings through `app/core/copilot/messages.py`, and keep prompt copy in the prompt-layer registries instead of reintroducing module-local ad hoc branching. See `app/core/copilot/messages.py`, `app/core/copilot/{scope,research_tools,suggestions,apply,workspace,prompting}.py`, and `tests/copilot/test_i18n.py`.

### Decision: session identity strips UI continuity hints
Durable session reuse depends only on normalized research identity (`mode`, `scope`, stable target/tab context, locale). `surface`, `stage`, and other route-continuity hints still belong in stored context for prompt phrasing and UI recovery, but they must not split the session signature. Atlas continuity is tab-based, so plural atlas stage aliases are tolerated only as legacy input and must be canonicalized into `tab` instead of persisting as durable stage labels. Rejected: letting Studio/Atlas wording changes mint new backend sessions for the same research workspace. See `app/core/copilot.py`, `app/schemas.py`, `app/models.py`, and `tests/test_copilot.py`.

### Decision: runs snapshot UI context at enqueue time
Copilot runs must persist the canonicalized session UI context that existed when the run was created, then execute against that snapshot even if the reusable session is later reopened from another surface/tab. Rejected: reading mutable `copilot_sessions.context_json` at execution time, because a quick Studio/Atlas switch can silently retarget an already-queued run. Keep session reuse cheap, but make run execution context immutable per run. See `app/models.py`, `app/core/copilot.py`, `alembic/versions/028_add_copilot_run_context_snapshot.py`, and `tests/test_copilot.py`.

### Decision: language policy stays dependency-light in the first seam
Chose a small shared language-policy layer for tokenization, matching normalization, sentence-boundary trimming, and relationship-label canonicalization before adding new segmenter stacks. Current rule: Chinese uses `jieba` when available; Japanese/Korean share a deterministic CJK n-gram fallback until dedicated analyzers are justified by real quality pressure. Rejected: adding per-language NLP dependencies before the copilot/runtime contract is stable. See `app/language_policy.py`, `app/core/bootstrap.py`, `app/core/context_assembly.py`, and `app/core/generator.py`.

### Don't: replace canonical world names with translated display text
Canonical names and labels stay in the novel's own language; translated, transliterated, or romanized forms are retrieval/display aids only. Instead: resolve mutations against stable target refs and keep source-language evidence authoritative. See `./database-guidelines.md`, `app/core/context_assembly.py`, and `app/world_relationships.py`.

## Future Extension

### Decision: future plot exploration should reuse the same runtime seam
Chose to keep copilot compatible with later inspiration/exploration features because both modeling and exploration are scoped research tasks over the same novel corpus. The seam should stay the same — target selection, evidence gathering, claim formation, workspace persistence — while the output policy changes: exploration may yield speculative/advisory branches, but canonical writes still require later grounding and backend compilation. Rejected: a separate freeform exploration chat stack that bypasses evidence, workspaces, and apply guardrails. See `app/core/copilot_scope.py`, `app/core/copilot_workspace.py`, `app/core/copilot_suggestions.py`, and `./world-model-architecture.md`.
