# World Model Architecture

> ADR-005 (2026-02-10). Replaces event sourcing (ADR-001).

## Product Positioning

SCNGS is a **creative workshop for novel continuation**. The user explores ideas within a persistent world model — not a chat conversation. Our job is to make ideas cheap — cheap to generate, cheap to discard, cheap to refine — while keeping output quality high enough that the user starts from a strong draft, not garbage.

Two things must be true simultaneously: **output quality must be worth reading**, and **iteration speed must be worth experimenting**. Quality without speed means users won't explore. Speed without quality means users won't stay.

Long-term, the product may expand beyond novel continuation toward broader creative exploration ("AI for fun"). The current architecture is optimized for the novel-writing vertical, but design decisions should not permanently foreclose other creative use cases.

## Meta-Principle: The Map Is Not the Territory

The design principles below are **the map** — our current best model of how to build this product. They are not the territory (the actual space of what users need and what technology enables). When a principle conflicts with observed reality — user behavior, competitive evidence, or new technical capabilities — **re-examine the principle first**, not the evidence.

Concretely: no principle in this document is exempt from audit. If real-world data suggests a principle is wrong, the correct response is to run an experiment, not to defend the principle. Principles that survive repeated contact with reality earn trust; principles that have never been tested are hypotheses, not truths.

### Principles Currently Under Audit

The following principles have identified tension points (2026-03-10 competitive analysis). They remain active defaults until experiments produce evidence to revise them:

| # | Principle | Tension | Experiment Needed |
|---|-----------|---------|-------------------|
| 2 | Context > Pipeline | May be wrong for **exploration** (discovering novel plot directions) vs **continuation** (maintaining consistency). Multi-agent emergent behavior produces outcomes no single prompt can. | Lightweight multi-agent "exploration mode" prototype; compare user-perceived value of emergent vs single-call outputs. |
| 3 | User Is Only Author | May limit creative surprise. Authors writing 1000+ chapters may want to be **surprised** by their own world, not just served consistent drafts. | Test an opt-in "world simulation" feature where characters act autonomously; measure whether authors find the output creatively stimulating. |
| 4 | Ideas Are Disposable | Optimizes for throughput (many fast iterations). But creative breakthroughs sometimes come from **depth** (one slow, rich exploration). Speed and depth serve different creative phases. | Offer a "deep exploration" mode with longer/richer generation; track whether users who use it produce higher-rated continuations. |
| 6 | Search, Don't Precompute | Keyword matching misses implicit references (e.g., "那年悬崖边的约定" references character B and location C without naming them). In ultra-long novels, missed callbacks compound into lore drift. | Measure callback coverage: sample 100 cross-chapter references from real novels, check what % the window index catches vs a relationship-aware retrieval approach. |

## Design Principles

### 1. Model the World, Not the History

A novelist carries a mental model of their world: who the characters are, how the rules work, what relationships exist. They don't replay every past event to write the next chapter.

The system should mirror this. Maintain a **world model** (entities, relationships, rules, facts) — not a per-chapter event log. The world model's size is proportional to the world's complexity, not the novel's length. A 100-chapter novel and a 2000-chapter novel have roughly the same-sized world model.

*Implication*: When evaluating any new feature, ask "does this enrich the world model?" not "does this track more history?"

### 2. Quality Comes from Context, Not from Pipeline Stages

A single LLM call with rich, relevant context produces better output than five LLM calls passing summaries to each other. Each handoff between pipeline stages loses nuance and introduces drift. The old 8-node pipeline didn't improve quality — it diluted it across multiple lossy transformations.

The world model exists to give the writer LLM the **right context at the right time**: who these characters are, how they relate, what rules govern this world, what has already happened. The better the context, the better the first draft. The better the first draft, the less the user has to fix.

*Implication*: When output quality is poor, the fix is almost always better context assembly — not more pipeline stages. Add richer entity descriptions, better relationship data, more targeted retrieval. Don't add another LLM "reviewer" or "planner" node.

### 3. The User Is the Only Author

AI generates drafts. The user decides truth. Every AI output — extracted entities, generated chapters, suggested updates — is a proposal that the user accepts, modifies, or discards.

*Implication*: Never auto-commit AI output into the world model. Never let AI output silently influence future generation without user approval. The `draft`/`confirmed` distinction exists solely as a user approval gate.

### 4. Ideas Are Disposable, the World Is Not

The world model is the persistent asset. Chapters are explorations — the user should feel free to generate, discard, and regenerate without anxiety. Saving a chapter is a deliberate act; generating one is throwaway.

*Implication*: Generation must be fast enough that discarding output feels painless. If generating a chapter takes 10 minutes, users won't experiment. If it takes 1 minute, they'll try 5 variations. Fewer LLM calls per generation = faster = more experimentation = better final output.

### 5. Let the Novel Define Its Own Structure

Novels mix genres. A 玄幻 novel has power hierarchies; a 悬疑 novel has information asymmetry; most novels have both plus more. Don't impose genre categories — extract whatever systems actually exist in the text.

*Implication*: The world model schema must be flexible enough to represent the supported system shapes (hierarchy, timeline, list) without hardcoding genres. Relationship-network graphs are a derived view over `WorldRelationship`, not a separate persistent system type. Adding a new novel never requires new frontend code.

### 6. Search, Don't Precompute

When the writer needs to know "what happened between 云澈 and 楚月仙 in the tournament arc", the answer is: search the chapters, read the relevant passages, summarize. This is what LLMs are best at. Pre-extracting and maintaining every possible fact is what databases are worst at (for unstructured narrative data).

*Implication*: Invest in good retrieval rather than exhaustive extraction. The world model captures the **structure** (who, what, how things relate). The **details** live in the chapter text and are retrieved when needed. Concrete implementation: window index (ADR-006, see [Bootstrap Design](./bootstrap-design.md)).

### 7. Simplicity Captures Essence

Like physical theories, the design should be as simple as possible — not because we're lazy, but because simplicity means we've found the right abstraction. If two concepts can be unified without losing expressiveness, they must be unified. Redundant states, overlapping enums, and special cases are symptoms of not yet understanding the problem.

*Implication*: Prefer orthogonal axes over combinatorial enums. Visibility (injection priority) and foreshadowing (surface vs truth) are independent concerns — don't merge them into a single multi-level enum. A field's presence (`truth IS NOT NULL`) is a better signal than a dedicated status value.

### 8. Surface Is a Script, Not a Fact

The `surface` field on entity attributes is not "what is objectively true" — it is "everything the writer is allowed to see and use". This includes phenomena, atmospheric hints, unexplained observations, and sensory details. The mental model: the author is a director giving the writer a script. The script can say "the sword sometimes trembles with cold energy, origin unknown" without revealing that it's an ancient divine weapon.

This reframing changes nothing in the schema but changes everything in how users think about the field. It shifts the user's role from "maintaining a factual database" to "curating the writer's creative material".

## What This Replaces

See the full Removed Components table in [backend/index.md](./index.md).

## Mainline Flow (Pre-Launch)

Primary product flow (replaces "bootstrap as the entry point"):

1. **Worldpack (offline)** produces `worldpack.v1` JSON.
2. **Import** moves that pack into the WorldModel under pack-scoped overwrite rules, with promotion-on-edit protecting any user-touched rows from future re-import replacement.
3. **Generate continuation** uses DB-read-only relevance + visibility injection, applies the world-context budget fuse, and returns both draft variants and a debug injection summary so the user can verify context quality.

Frontend validation loop:

- `/world/:novelId` provides Worldpack import + WorldModel editing.
- `/workspace` in bound mode calls `/continue` and renders the injection debug summary so users can verify relevance and noise controls.

Bootstrap is still supported for extraction workflows, but is not the default entry path for proving the "world-model improves continuation" loop.

### Decision: centralize world write invariants
Chose a shared write-policy seam for relationship canonical signatures, origin promotion, and system data validation because API CRUD, bootstrap, world generation, and worldpack import all mutate the same rows and drift fast when they each reimplement the rules. Rejected: flow-local copies hidden inside each entry path. See `app/core/world_write.py`, `app/core/world_application.py`, `app/core/world_crud.py`, `app/core/worldpack_import.py`, `app/core/world_gen.py`, `app/core/bootstrap.py`, and `tests/test_world_write.py`.
