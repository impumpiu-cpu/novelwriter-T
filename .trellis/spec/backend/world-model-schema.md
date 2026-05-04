# World Model Schema

Use this doc for persistent world-model contracts that are not obvious from `app/models.py`.
Keep column lists and Pydantic field definitions in code; keep ownership, overwrite, and modeling decisions here.

## Why This Schema Exists (Long-Term Principles)

1. **World structure first**: persist entities/relations/systems; dynamic chapter-state stays in text retrieval.
2. **No orphan facts**: information must belong to an entity attribute, relationship, or system.
3. **Draft-first governance**: AI-proposed structure is editable and confirmable by users.
4. **Flexible domain modeling**: avoid hard genre enums; let novels define their own types.
5. **Visibility as control plane**: prompt assembly is controlled by `active/reference/hidden` rather than ad-hoc prompt rules.

### Surface vs Truth

- `surface` is the writer-facing value shown in context assembly.
- `truth` is the optional deeper truth for consistency checks and foreshadowing. Orthogonal to visibility — a `hidden` attribute can still have a non-NULL `truth`.

### `label_canonical` Semantics (Relationships)

Canonicalization: NFKC normalize, trim, collapse whitespace, lowercase. If the label contains CJK and ends with `关系`/`關係` (and is longer than the suffix), strip the suffix. Display still uses `label`.

### Decision: Drop duplicates during world generation
Chose to drop duplicate relationships by `(source_id, target_id, label_canonical)` and duplicate systems by `name`, emitting warnings, because LLM output often repeats entries and draft spam degrades review UX. Rejected: hard-fail on duplicates or rely on DB uniqueness (too brittle under retries/concurrency). See `app/core/world_gen.py` and `tests/test_world_generation.py`.

### Decision: Chunk long free-text settings during world generation
Long setting collections are extracted chunk-by-chunk and then merged deterministically by entity name / relationship signature / system name before persistence. If chunks disagree on a system `display_type`, backend emits a warning and downgrades that merged system to `list` so hierarchy/timeline-only fields are not silently discarded. This improves coverage for multi-thousand-word setting packs without changing the ownership contract (`origin=worldgen`, draft-only writes). Rejected: single-shot extraction for all lengths (coverage collapses on long inputs) and final freeform summarization passes (higher hallucination risk). See `app/core/world_gen.py` and `tests/test_world_generation.py`.

### Decision: world systems use `list` / `hierarchy` / `timeline`; relationship graphs stay derived UI
Persistent `WorldSystem` rows use `list`, `hierarchy`, or `timeline`. Relationship-network visualization belongs to `WorldRelationship` and its derived UI, not a separate `graph` system type, to avoid dual truth sources and duplicated writer-context facts. World generation follows the same contract and may draft only those three system shapes. For hierarchy drafts, the server generates node ids during persistence so the LLM never invents editor-facing ids. Transitional safety rule: legacy `graph` rows may still be returned by read APIs and shown read-only in the UI, but create/update contracts must continue rejecting new graph writes. See `app/core/world_gen.py`, `app/core/text/zh.py`, `app/schemas.py`, and `tests/test_world_generation.py`.

### Decision: warning payloads carry i18n descriptors, not only rendered strings
World-generation and worldpack-import warnings must return stable `code` plus `message_key` and `message_params`, while retaining a rendered `message` as a compatibility fallback. UI should prefer localized rendering from the descriptor when available and fall back to `message` otherwise. Rejected: warning payloads with only a final `message`, because locale switching would require backend-specific string parsing or another breaking API change. See `app/schemas.py`, `app/core/world_gen.py`, `app/core/worldpack_import.py`, and `web/src/types/api.ts`.

### System `display_type` / `data` Consistency

`display_type` selects the schema for the `data` JSON blob. Backend must prevent persisting mismatched pairs:
- On create: validate `data` against `display_type` (invalid → 422).
- On update: if either changes, validate the resulting pair before commit.
- `data={}` is allowed for any `display_type` (empty system). Server does not inject default keys (roundtrip stability).

Notes:
- For `display_type=list`, items may include an optional stable `id` (commonly emitted by worldpack imports). If present, it is validated and preserved.

## Ownership and Safety Boundary

- `origin=bootstrap` → AI-extracted drafts
- `origin=worldgen` → AI-generated drafts from world settings generation
- `origin=worldpack` → imported from worldpack
- `origin=manual` → user-created or user-edited
- **Promotion-on-edit**: user edits on bootstrap/worldgen/worldpack rows promote `origin` to `manual`
- Confirmed rows are protected from bootstrap overwrite

Safe overwrite semantics:
- Bootstrap reextract: may replace only `origin=bootstrap` drafts (per `draft_policy`)
- World generation: may replace only `origin=worldgen` drafts
- Worldpack import: may replace only `origin=worldpack` rows for the same `worldpack_pack_id`

### Decision: malformed worldpack entities keep rows only for link resolution
If an incoming worldpack entity cannot supply a usable `name` but an existing row for the same worldpack identity already exists, keep that row available for relationship resolution but do not reconcile or delete its worldpack-owned attributes in that pass. Rejected: treating the malformed payload as a normal sync target, because partial imports would silently erase existing worldpack facts. See `app/core/worldpack_import.py`, `app/core/worldpack_import_planner.py`, and `tests/test_worldpack_import.py`.

### Worldpack Visibility Is Strict

- Allowed values: `active | reference | hidden`
- Normalization: `.strip().lower()`
- Missing/null → defaults to `reference`
- Invalid values → 422 with exact field path via `detail[].loc`
- **Never silently coerce** invalid visibility to a default (a typo intended as `hidden` becoming `reference` is a silent promotion — hard to debug after import)

### Worldpack Payload Must Be Strict JSON

No smart quotes, no JSON5. Preflight: `python3 -m json.tool worldpack.json >/dev/null`. Use ASCII double quotes for JSON delimiters; use `「」` for literal quotes in human text.

### Pattern: Writer Constraints as Active Systems

Rules that must always appear in the writer prompt (pacing, taboos, naming/honorifics) → model as `WorldSystem` with `visibility=active`. Context assembly injects all confirmed active systems regardless of chapter relevance. Keep them compact (prefer `display_type=list`).

## API Isolation Rule

All `/api/novels/{novel_id}/world/...` operations must enforce same-novel ownership for touched resources.

### List Filter Contract

Enumerated query params (`origin`, `status`, `visibility`, `display_type`) are strict — invalid values return 422, not empty lists. List responses use deterministic default ordering (`ORDER BY id ASC`).

## Deferred Contract: Update Detection Never Writes Directly

Future post-chapter update detection may use keyword or LLM proposal generators, but proposals remain suggestions keyed by entity names and must still flow through the normal CRUD confirmation path. Rejected: detector-owned direct writes, because that would bypass the user approval boundary. See `world-model-architecture.md`, `app/core/world_application.py`, and `app/api/world.py`.

## Roadmap

**Planned**: improved relation representation (direction + role-aware display semantics); better "current effective relation" handling.

**Deferred**: relationship timeline/history ledger; fully automatic chapter-to-world writes without user confirmation.

## Related Specs

- Context assembly: `./context-assembly.md`
- Architecture: `./world-model-architecture.md`
- Bootstrap: `./bootstrap-design.md`
- Bootstrap invariants: `./bootstrap-invariant-gates.md`
- DB patterns: `./database-guidelines.md`
