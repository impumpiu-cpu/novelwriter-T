# Database Guidelines

Use this doc for persistence rules that are easy to regress.
See `app/models.py`, Alembic revisions, and tests for schema details.

## Data Contracts

### Decision: canonical names stay in the novel's own language
Store canonical entity names in the novel's language and treat translated or alternate spellings as aliases. Rejected: overwriting canon with translated text, because it breaks retrieval and matching across bootstrap, context assembly, and worldpack import. See `app/models.py`, `app/core/context_assembly.py`, and `tests/test_world_models.py`.

### Decision: chapter ingest resolves headings from declared novel language first
TXT upload parsing should use the stored/declared novel language as the first chapter-heading policy, then fall back to other supported heading families so mislabeled or mixed-source files still parse when possible. Rejected: one global zh/en regex bucket or hard failure when the declared language and heading style disagree. See `app/core/parser.py`, `app/api/novels.py`, and `tests/test_parser.py`.

### Decision: upload auto-detects novel language when the client omits it
Upload clients should not be forced to choose a language before ingest. When `language` is absent or blank, the backend detects the novel language from decoded source text, persists that detected language on `Novel.language`, and then uses it as the primary chapter-heading policy for parsing. Explicit client language still wins when provided. Rejected: treating omitted `language` as an implicit `zh`, because that silently biases prompt locale, parsing, and post-check behavior for non-Chinese novels. See `app/api/novels.py`, `app/language_policy.py`, and `tests/test_upload_novel.py`.

### Decision: internal chapter numbering stays gap-filling and is the MVP display contract
`Chapter.chapter_number` is the stable internal chapter identity used by CRUD routes, Studio display/search/export, continuation flow, and gap-filling numbering. Imported source-book headings still live in `source_chapter_label` / `source_chapter_number`, but in the current MVP they are preserved as source metadata rather than driving Studio numbering or next-chapter references. Rejected: overloading `chapter_number` to mean both internal sequencing and raw source-book numbering, and rejected: mixing source numbering back into visible Studio numbering because it creates confusing count/latest mismatches. `Novel.total_chapters` remains a count, not a next-number oracle. See `app/core/chapter_numbering.py`, `app/core/parser.py`, `app/api/novels.py`, `app/core/continuation_text.py`, `web/src/lib/chaptersPlainText.ts`, and `tests/test_chapter_crud.py`.

### Don't: infer historical source metadata from `Chapter.title`
`Chapter.title` is user-editable and old rows do not carry trustworthy import provenance, so migrations must not regex-rewrite historical titles into `source_chapter_label` / `source_chapter_number`. Instead: add the source-metadata columns for future imports and preserve legacy titles unless a trusted import repair path can prove the source label. See `alembic/versions/031_add_chapter_source_metadata.py` and `tests/test_migration_031_chapter_source_metadata_preserves_titles.py`.

### Decision: chapters stay linear
Generated variants are disposable, but committed chapters remain a single ordered sequence per novel. Rejected: built-in branching, because the persistent asset is the world model and branching would add high-ceremony chapter management before the core workflow is proven. See `app/models.py`, `app/core/chapter_numbering.py`, and `tests/test_chapter_crud.py`.

## Mutation Boundaries

### Decision: worldpack import is atomic; bootstrap writes are step-scoped
Worldpack import stays all-or-nothing inside one transaction. Bootstrap may commit per pipeline step so long jobs can fail fast and report progress without mixing partial ownership semantics. See `app/core/worldpack_import.py`, `app/core/bootstrap.py`, `tests/test_worldpack_import.py`, and `tests/test_bootstrap_contract.py`.

### Decision: copilot run reclamation treats `queued` and `running` as lease-bound active states
Copilot runs may exist in `queued` before the worker claims them and in `running` while the worker is alive. Both states are active only while their lease is valid. Rejected: counting stale `queued`/`running` rows against admission forever or requiring manual cleanup after restart. Persist lease metadata on the run row, reclaim expired active rows into `interrupted`, and clear ownership on terminal states. Keep the "one active run per session" invariant backed by a DB-level partial unique index rather than only Python pre-checks, and when tightening that invariant in migrations, interrupt extra active rows before creating the index so legacy duplicate data cannot block deploys. See `app/models.py`, `app/core/copilot.py`, `app/core/copilot_run_store.py`, and `tests/test_copilot.py`.

### Decision: copilot session reuse is signature-unique at the DB boundary
Copilot session reuse is keyed by `(novel_id, user_id, signature)` and that key must be unique in storage, not just in application pre-checks. The signature comes from normalized identity context, not every field in `context_json`, so surface/stage/display metadata may update on reuse without minting a new durable session. Atlas continuity is tab-based, so legacy plural atlas stage aliases should be canonicalized into `tab` before storage. Each `CopilotRun` must snapshot that canonical context onto its own row so queued work cannot be retargeted by later session reuse. Rejected: `SELECT`-then-`INSERT` without a unique constraint, and rejected: treating all UI continuity hints as part of the DB identity key. On uniqueness conflicts, rollback, reload the existing session, and return it as reuse rather than surfacing a raw DB failure. If a migration introduces that uniqueness after legacy duplicate rows already exist, merge runs onto one keeper session and delete the extras before creating the unique index. See `app/models.py`, `app/core/copilot.py`, `web/src/types/copilot.ts`, and `tests/test_copilot.py`.

### Decision: fresh selfhost databases bootstrap from current metadata
A brand-new selfhost DB must be created from current metadata and stamped to head instead of replaying early migrations that assumed legacy tables. See `app/selfhost_db_bootstrap.py`, `Dockerfile`, and `tests/test_selfhost_db_bootstrap.py`.

### Gotcha: `GET /chapters/meta` needs its own response model
Metadata rows do not carry chapter content. Reusing the full chapter response model creates FastAPI validation failures that look like runtime bugs. See `app/api/novels.py`, `web/src/services/api.ts`, and `tests/test_chapter_crud.py`.

### Don't: store chapter headings inside `Chapter.content`
Continuation output must stay body-only. The backend owns chapter numbering and the UI owns editable titles; stuffing headings into content creates duplicated labels and broken plain-text formatting. See `app/utils/prompts.py`, `web/src/lib/chaptersPlainText.ts`, and `web/src/__tests__/chaptersPlainText.test.ts`.

## Runtime Trade-Offs

### Decision: SQLite stays the default until real pressure appears
SQLite + WAL remains the launch database. Move to PostgreSQL only when the hosted tier has enough RAM for the daemon or when real write contention shows up as measurable `database is locked` failures. See `app/database.py` and `app/config.py`.

### Decision: uvicorn stays at two workers on the current hosted tier
The hosted tier is intentionally resource-constrained; extra workers multiply memory pressure faster than they improve throughput. Revisit only after the hosted footprint changes. See `deploy/hosted/docker-compose.yml` and `docs/hosted-safety-fuses.md`.

### Decision: async SQLAlchemy is deferred
Current sync DB access wrapped with threadpool boundaries is sufficient for the present workload. Rejected: async ORM migration before there is evidence that DB blocking, not LLM latency, is the bottleneck. See `app/api/novels.py`, `app/api/world.py`, and `app/core/generator.py`.

### Decision: SQLite uses `NullPool`
SQLite connection setup is cheap in-process; queue pooling adds contention without helping throughput on the current architecture. See `app/database.py` and `tests/test_selfhost_db_bootstrap.py`.

### Decision: LLM concurrency is capped with an in-process semaphore
Single-process hosting can use `asyncio.Semaphore` to fail fast under LLM pressure. Rejected: introducing a message queue before multi-worker or multi-node coordination exists. See `app/core/llm_semaphore.py`.

## Related Specs

- world-model ownership and overwrite: `./world-model-schema.md`
- bootstrap behavior: `./bootstrap-design.md`
- hosted runtime assumptions: `../guides/internal/gcp-hosted-ops.md`
- error translation for DB conflicts: `./error-handling.md`
