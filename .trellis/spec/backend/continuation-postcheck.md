# Continuation Post-Check

Use this doc for the post-generation warning contract.
Keep drift-check internals in `app/core/continuation_postcheck.py`; keep prose-check internals in `app/core/prose_check.py`; keep the product boundary here.

## Core Contract

### Decision: post-check is advisory only
Lore-drift and prose-quality detection surface warnings, but they must not block or reject a generation. See `app/core/continuation_postcheck.py`, `app/core/prose_check.py`, `app/api/novels.py`, and tests.

### Decision: post-check stays deterministic and stateless
Both drift-check and prose-check use deterministic text rules instead of another LLM call so they stay cheap, predictable, and easy to reason about. Rejected: a second model pass on every continuation before the main workflow is proven.

### Decision: warnings live in the debug payload under split keys
- `debug.drift_warnings` — term-level lore drift warnings; drives inline highlighting in the results stage.
- `debug.prose_warnings` — paragraph-level prose quality warnings; rendered in a dedicated collapsible panel.

This split replaces the former `debug.postcheck_warnings` key. See `app/schemas.py` (`ContinueDebugSummary`).

### Decision: prose-check v0 rule surface
Four deterministic rules: `repeated_ngram`, `long_paragraph`, `abnormal_sentence_length`, `summary_tone`. All regex/counting-based with CJK and whitespace-language variants. See `app/core/prose_check.py` and `tests/test_prose_check.py`.

### Decision: post-check warnings use descriptor + fallback message
Each warning carries a stable `message_key` and `message_params` alongside the rendered `message`. This keeps the payload immediately readable while allowing future locale switching without changing the warning shape. See `app/schemas.py` and `web/src/types/api.ts`.

### Gotcha: if post-check ever becomes failure-prone, split it out first
Right now both checkers are simple enough to run inline. If they grow to need fragile parsing or external calls, they should be isolated behind a degradable boundary instead of turning continuation generation into a warning-system SPOF. See `error-handling.md`.

## Related Specs

- Continuation flow: [Continuation Design](./continuation-design.md)
- Context assembly: [Context Assembly](./context-assembly.md)
