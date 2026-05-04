# Context Assembly

Use this doc for the non-obvious prompt-injection contract.
Keep low-level selection code in `app/core/context_assembly.py`; keep visibility, relevance, and narrative-rule decisions here.

## Prompt Assembly Contract

### Decision: context assembly is read-only
Context assembly may inspect world-model rows and chapter text, but it must not mutate DB state or opportunistically "fix" world data while assembling prompts. See `app/core/context_assembly.py` and `app/api/novels.py`.

### Decision: visibility is the writer-facing control plane

Writer-facing contract:

- `active`: included by default
- `reference`: included when directly relevant
- `hidden`: excluded

Consistency checks may inspect hidden rows and `truth`, but the writer prompt must not.

### Decision: relevance is deterministic and ambiguity-safe

Only confirmed entities participate in relevance detection. Matching uses Aho-Corasick over canonical names plus aliases, normalizes scan text and keywords through the novel-language policy, disables ambiguous keywords entirely, and keeps longest matches over contained spans. Languages with whitespace also require word-boundary checks so short aliases do not fire inside longer words. Rejected: heuristic tie-breaking that guesses which entity the user meant, because silent false positives are worse than missed context. See `app/core/context_assembly.py` and `tests/test_context_assembly.py`.

### Decision: active systems always inject; hidden facts never inject
Relevant entities contribute visible attributes and relationships; confirmed active systems inject regardless of chapter relevance. Writer prompts must never see hidden rows or `truth` fields. Per-element hidden nodes inside `WorldSystem.data` stay filtered as well. See `app/core/context_assembly.py` and `tests/test_context_assembly.py`.

### World Context Budget (Hard Fuse)

Writer context is capped to an estimated budget (default: **100000**). This is a safety fuse, not a precision tokenizer.

- estimator: deterministic character-count heuristic (`_estimate_writer_context_tokens`)
- truncation order (fixed, testable):
  1. drop `visibility=reference` relationships
  2. drop `visibility=reference` attributes
  3. drop tail entities (and relationships connected to them) until within budget

Implementation: `apply_writer_context_budget(...)` with `DEFAULT_WORLD_CONTEXT_TOKEN_BUDGET`.

### Design Decision: Narrative Constraints Separated from World Context

**Context**: When WorldSystem `constraints` were rendered inline inside `【World Context】` (next to system descriptions and JSON-ish `data`), the LLM tended to treat them as reference information rather than hard rules, causing low compliance (especially for pacing constraints like "max 1 time-skip per chapter").

**Decision**: Extract all `constraints` from writer-injected (active) systems into a dedicated `【Narrative Constraints — MUST FOLLOW】` prompt section, structurally separated from `【World Context】`.

**Why**:
- LLMs respond better to imperative, dedicated sections than to rules buried inside context dumps.
- Constraints are orthogonal to world info: they govern *how to write*, not *what exists in the world*.
- The continuation prompt explicitly treats narrative constraints as higher-priority writing rules when they conflict with generic guidance.

See `app/api/novels.py`, `app/core/generator.py`, `app/utils/prompts.py`, and `tests/test_narrative_constraints.py`.

### Pattern: always-on narrative rules live in active systems
If a rule must appear in every writer prompt, model it as a confirmed `WorldSystem` with `visibility=active` and a compact `constraints` list. Rejected: scattering prompt rules across unrelated entity attributes or frontend-only fields. See `app/core/world_application.py` and `tests/test_narrative_constraints.py`.

### Gotcha: foreshadowing uses `surface` vs `truth`, not a special visibility mode

Unresolved mysteries stay in `truth` while `surface` carries the writer-visible hinting script. Do not invent a dedicated foreshadowing visibility enum. See `world-model-schema.md` and `tests/test_world_models.py`.

## Related Specs

- Schema and table contracts: [World Model Schema](./world-model-schema.md)
- Architecture principles: [World Model Architecture](./world-model-architecture.md)
