# Bootstrap Design

Use this doc for bootstrap contracts that are easy to break while iterating.
See `app/core/world_bootstrap_application.py`, `app/core/bootstrap.py`, `app/api/world.py`, and `tests/test_bootstrap*.py` for the implementation.

## Principles

- bootstrap builds a usable world skeleton and retrieval index; it does not try to persist full narrative history
- bootstrap stays draft-first; user confirmation remains the authority boundary
- maintenance work should stay hidden from the primary UI path
- deterministic steps should carry most of the cost so LLM refinement stays minimal

## Current Runtime Contract

### Decision: omitted `mode` resolves from initialization state
If the caller omits `mode`, an uninitialized novel defaults to `initial`; an initialized novel defaults to `index_refresh`. This keeps first-run extraction obvious while making post-init refresh the safe maintenance default. See `app/core/world_bootstrap_application.py`, `app/core/bootstrap.py`, and `tests/test_bootstrap_contract.py`.

### Decision: `initial`, `index_refresh`, and `reextract` are separate product contracts
`initial` performs first extraction, `index_refresh` rebuilds only the window index, and `reextract` rebuilds bootstrap drafts. Do not collapse them into a single "smart" mode; the UI and overwrite semantics depend on the distinction. See `app/core/bootstrap.py` and `tests/test_bootstrap_contract.py`.

### Decision: destructive reextract only touches `origin=bootstrap,status=draft`
`replace_bootstrap_drafts` requires explicit `force=true` and may only delete draft rows still owned by bootstrap. Confirmed rows and user-promoted rows stay out of bounds. See `app/core/world_bootstrap_application.py`, `app/core/bootstrap.py`, `tests/bootstrap/test_invariants.py`, and `world-model-schema.md`.

### Gotcha: legacy pre-origin draft rows block destructive replace
Rows created before origin tracking can look like manual data even when they were bootstrap output. Fail fast with actionable remediation instead of guessing. See `app/core/world_bootstrap_application.py` and `tests/bootstrap/test_invariants.py`.

### Decision: bootstrap output stays narrow
Bootstrap writes draft entities, draft relationships, and `novel.window_index`; it does not auto-write attributes, systems, or confirmed world-model rows. See `app/core/bootstrap.py` and `tests/test_bootstrap.py`.

### Decision: bootstrap text processing routes through the shared language policy
Bootstrap tokenization, stopword loading, and candidate normalization should resolve from the novel language first and only fall back to text detection when language is absent. Current lightweight policy: Chinese uses `jieba` when available; Japanese/Korean use deterministic CJK n-grams; stopword loading still reuses the existing `zh/en` files until better per-language corpora are warranted. Rejected: hardcoded `zh/en` branching in each bootstrap helper and premature dependency expansion. See `app/language_policy.py`, `app/core/bootstrap.py`, and `tests/test_bootstrap.py`.

### Decision: `index_refresh` is maintenance, not the default post-init CTA
After initialization, the primary user action remains `reextract`, not maintenance-only refresh. Keep index rebuild available, but do not let it displace the visible extraction workflow. See `bootstrap-invariant-gates.md` and `web/src/__tests__/BootstrapPanel.invariants.test.tsx`.

### Decision: bootstrap job state does not define retrieval readiness by itself
Bootstrap may still build or refresh the window index, but retrieval readiness now belongs to the window-index lifecycle contract rather than to bootstrap completion history. Product/API surfaces must read the normalized index state from the novel (`fresh`, `stale`, `missing`, `failed`) and treat bootstrap job state as progress/history only. Rejected: inferring copilot readiness from `bootstrap.result.index_refresh_only` or from whether a bootstrap job exists, because chapter edits and derived-asset rebuilds now advance the retrieval contract independently of bootstrap extraction. See `app/core/indexing/lifecycle.py`, `app/api/novels.py`, `app/core/world/bootstrap_application.py`, and `tests/test_upload_novel.py`.

## Optimization Guardrails

### Decision: bootstrap evaluation covers deterministic steps only
Benchmarking focuses on deterministic candidate extraction, index build, and co-occurrence behavior. LLM refinement stays out of the optimization loop so metric deltas remain attributable. See `benchmarks/bootstrap_v1/` and `../guides/internal/bootstrap-experiment-archive.md`.

### Decision: eval ordering must match runtime ordering
Evaluation code must call the deterministic steps in the same order as production. Otherwise pair/entity deltas become attribution noise rather than useful signal. See `app/core/bootstrap.py` and `../guides/internal/bootstrap-experiment-archive.md`.

### Decision: optimization runs change one variable at a time
Each optimization run isolates one change against a frozen baseline and must pass no-regression gates before it is accepted. Rejected: multi-knob sweeps during this phase, because they hide which change caused the delta. See `../guides/internal/bootstrap-experiment-archive.md`.

### Don't: keep mismatched run artifacts
Delete local benchmark artifacts produced with mixed parameters, wrong parity, or other invalid conditions. A contaminated baseline is worse than no baseline. See `../guides/internal/bootstrap-experiment-archive.md`.

### Release Gate: current admission control is single-instance only
Bootstrap trigger coordination assumes one active server process. Horizontal scaling needs DB-backed claim or lease semantics before bootstrap can remain safe. See `app/core/world_bootstrap_application.py` and `app/core/bootstrap.py`.

## Explicit Non-Goals

- no temporal relationship history ledger in bootstrap output
- no automatic conversion of chapter text into confirmed world-model writes
