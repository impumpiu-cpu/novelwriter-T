# Backend Spec Index

Use backend specs for non-discoverable decisions, tripwires, and routing.
Do not copy API field lists, ORM column definitions, or repo-tree facts that can be read directly from code.

## Always-On Constraints

- pre-launch mode is active (`../guides/pre-launch-mode.md`)
- architecture consistency over backward compatibility
- config in `app/config.py` is the source of truth for runtime behavior
- fail fast on ambiguous or dangerous states
- dependency direction stays `api/` -> `core/` -> `models/database`; `api/` -> `schemas`; `core/` -> `schemas/models/config`

## Foundations

| Spec | Use when |
|---|---|
| [World Model Architecture](./world-model-architecture.md) | product principles and architecture boundaries |
| [World Model Schema](./world-model-schema.md) | ownership, visibility, overwrite, and deferred world-model rules |
| [Quality Guidelines](./quality-guidelines.md) | config, hosted/selfhost boundaries, invariant gates, regression expectations |

## Runtime Contracts

| Spec | Use when |
|---|---|
| [Context Assembly](./context-assembly.md) | relevance, visibility injection, budget fuse, narrative constraints |
| [Copilot Runtime](./copilot-runtime.md) | evidence packs, suggestion compilation, resumable runs, multilingual copilot rules |
| [Continuation Design](./continuation-design.md) | `/continue`, streaming behavior, persistence, prompt-shape decisions |
| [Continuation Post-Check](./continuation-postcheck.md) | lore-drift warnings after generation |
| [Bootstrap Design](./bootstrap-design.md) | bootstrap mode selection, reextract safety, optimization guardrails |
| [Bootstrap Invariant Gates](./bootstrap-invariant-gates.md) | temporary invariant IDs and gate suites during fast iteration |
| [Database Guidelines](./database-guidelines.md) | chapter numbering, transaction boundaries, runtime DB trade-offs |
| [Error Handling](./error-handling.md) | fail-fast error translation and safe degradation rules |
| [Logging Guidelines](./logging-guidelines.md) | request logging, secret/content redaction, logging failure modes |

## Private Internal References

| Spec | Use when |
|---|---|
| [GCP Hosted Ops](../guides/internal/gcp-hosted-ops.md) | hosted-only runtime assumptions and operational tripwires |
| [Backend Python Environment](../guides/internal/backend-python-environment.md) | `uv` / `.venv` command conventions for backend work |

## Historical Reference

| Spec | Use when |
|---|---|
| [Bootstrap Experiment Archive](../guides/internal/bootstrap-experiment-archive.md) | closed bootstrap optimization experiments and why they were shelved |

## Quick Routing

- world-model ownership / worldpack overwrite / visibility -> `world-model-schema.md`
- copilot runtime / evidence packs / suggestion compilation / future exploration seam -> `copilot-runtime.md`
- writer prompt injection / ambiguity handling / budget fuse -> `context-assembly.md`
- continuation flow / result persistence / streaming UX -> `continuation-design.md`
- post-generation warnings -> `continuation-postcheck.md`
- bootstrap trigger mode / destructive reextract / single-instance release gate -> `bootstrap-design.md`
- bootstrap workflow drift tests -> `bootstrap-invariant-gates.md`
- hosted auth / quota / BYOK / owner isolation -> `quality-guidelines.md`
- chapter numbering / chapter linearity / selfhost DB bootstrap -> `database-guidelines.md`
- API fail-fast rules -> `error-handling.md`
- request logging + redaction -> `logging-guidelines.md`
- backend command / environment hygiene -> `../guides/internal/backend-python-environment.md`

## Architectural Guardrails

### Keep

- SQLAlchemy + FastAPI
- `app/core/ai_client.py` routing
- JWT auth
- token metering / quota reservations
- `pyahocorasick`
- window index

### Do Not Recreate

| Removed component | Replaced by |
|---|---|
| `StoryState` / `NarrativeEvent` / event sourcing | world model entities + relationships |
| `CharacterArc` / `Epoch` / `Moment` | flexible entity types |
| `MemoryManager` / `memory_manager.py` | world model |
| `CouplingResolver` | explicit user decisions |
| 8-node pipeline (Analyst -> ... -> Extractor) | Context Assembly -> Writer -> Update Detector |
| `anthropic` SDK + provider | `openai` SDK against OpenAI-compatible endpoints |
| `instructor` library | native JSON mode + `model_validate_json()` |
| ChromaDB / BM25 / RAPTOR | window index + world model |
