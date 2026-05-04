# Continuation Design

Use this doc for the non-obvious `/continue` product contract.
Keep request and response field shapes in `app/schemas.py`; keep the persistence, prompt, and UX decisions here.

## Core Contract

### Decision: continuation persists proposals, not chapters
`/continue` stores generated variants as `Continuation` rows so the user can compare, rate, and adopt them later. It must not auto-write a chapter row or mutate the world model. See `app/api/novels.py`, `app/core/generator.py`, and `tests/test_continue_endpoint.py`.

### Decision: next chapter number uses gap-filling, not `total_chapters + 1`
Continuation generation must follow the same chapter-number contract as CRUD: use the smallest missing positive number so deleted gaps stay reusable. See `app/core/chapter_numbering.py`, `app/core/generator.py`, and `tests/test_chapter_crud.py`.

### Decision: one generation call per variant, with bounded target-length shaping
When `target_chars` is provided, backend estimates a bounded `max_tokens`, nudges the model toward a slightly higher hidden drafting target, then trims near a sentence boundary. Rejected: multi-pass append/repair loops, because they add cost and semantic drift. See `app/core/generator.py`.

### Decision: response includes a debug injection summary
The API returns injected systems, entities, relationships, relevant entity ids, and disabled ambiguous keywords so users can verify context quality without reading logs. See `app/api/novels.py`, `app/core/generator.py`, `web/src/components/studio/stages/ContinuationResultsStage.tsx`, and `web/src/pages/GenerationResults.tsx`.

### Decision: lorebook matching follows the novel-language policy
Lorebook keyword injection normalizes case-insensitive matching through the same language-policy seam used by bootstrap/context work, and whitespace languages require word boundaries so short nicknames do not fire inside longer words. Rejected: ad-hoc `.lower()` matching that behaves differently from the rest of the runtime. See `app/core/lore_manager.py`, `app/language_policy.py`, and `tests/test_lore_manager.py`.

## Streaming Contract

### Decision: streaming and non-stream share the same persistence contract
Streaming improves time-to-first-token, but completed variants still persist as `Continuation` rows just like non-stream generation. Rejected: keeping streaming-only variants ephemeral, because results pages/stages must survive refreshes and navigation. See `app/api/novels.py`, `app/core/generator.py`, `web/src/components/studio/stages/ContinuationResultsStage.tsx`, and `web/src/pages/GenerationResults.tsx`.

### Decision: stream `variant=0`, emit later variants when complete
The first variant streams incrementally; additional variants may complete off-stream and are emitted when ready. The client must treat navigation state as transient and use persisted continuation ids for reload safety. See `app/api/novels.py`, `web/src/components/studio/stages/ContinuationResultsStage.tsx`, and `web/src/pages/GenerationResults.tsx`.

### Design Decision: Recent Chapters Last (Style Anchoring)

**Context**: Style drift occurs because the model's autoregressive output is influenced by the most recently seen tokens. When meta-instructions (length guidance, user instruction) come after the novel text, they shift the model's register toward modern vernacular Chinese before generation starts.

**Decision**: Place `<recent_chapters>` at the very end of the user prompt, immediately before the generation trigger. All instructions, constraints, and user directives come before the novel text.

**Why**: Autoregressive models naturally continue the register of the most recently processed text. By making the novel prose the last thing the model "reads", the first generated tokens inherit the original style. The generation trigger (`请续写第N章：`) is kept to 7 characters to minimize the instruction gap.

**Trade-off**: Length guidance is now only in the system prompt, not repeated in the user message tail. This is acceptable because the system prompt is always present and length discipline has proven reliable there.

## Key Design Decisions

### Don't: output chapter headings inside continuation body
Chapter numbering is backend-owned and title editing is user-owned. Prompting and sanitization should keep continuation content body-only to avoid duplicated labels and broken downstream formatting. See `app/utils/prompts.py`, `app/core/generator.py`, and `web/src/lib/chaptersPlainText.ts`.

### Don't: Persist Chain-of-Thought / Thinking Blocks

Some reasoning-capable models and gateways may emit analysis text (often inside `<think>...</think>` blocks). We never display or persist these in NovWr: the prompt forbids meta commentary and the backend strips common thinking blocks before saving/outputting.

See `app/utils/prompts.py` and `app/core/generator.py` (`_sanitize_continuation_content`).

### Single Call + Token Estimate

Continuation uses one generation call per version. When `target_chars` is provided, backend converts the requested character target into `max_tokens` using a configurable Chinese-writing heuristic (chars→tokens ratio plus a small safety buffer). Prompting uses a slightly higher hidden drafting target so the stream is less likely to end early, and backend then trims at a nearby sentence boundary around the user-visible target. This keeps cost bounded while avoiding semantic-repeat issues caused by repair/append passes.

### User as Author

Generated content is always a draft proposal. Continuations are persisted but never auto-committed to chapters or world model. User reviews, rates, and decides what to keep. (Principle #3.)

### Debug Injection Summary

Response includes `debug` listing injected systems/entities/relationships, relevant entity IDs, and disabled ambiguous keywords — so users can verify world context reached the LLM without reading logs.

## Related Specs

- Context assembly: [Context Assembly](./context-assembly.md)
- World model: [World Model Architecture](./world-model-architecture.md)
- Schema: [World Model Schema](./world-model-schema.md)
- Hosted quota semantics: [Quality Guidelines](./quality-guidelines.md)
