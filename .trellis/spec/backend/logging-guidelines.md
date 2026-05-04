# Logging Guidelines

Use this doc for logging red-lines and failure-mode decisions.
Keep logger setup code in `app/main.py`; keep the non-obvious safety rules here.

## Core Rules

### Decision: request logs must carry correlation data but not content
Request logging should include request id, method, path, status, and duration so failures can be traced across layers without logging novel text or prompt bodies. See `app/main.py`.

### Decision: startup config logging stays allowlist-only
Startup logs may confirm the active runtime mode and selected safe config, but must never dump secrets or full settings objects. See `app/main.py` and `app/config.py`.

### Don't: log secrets, prompts, or novel content

API keys/secrets · JWT secrets/tokens · full LLM prompts/responses · system prompt templates · novel content · PII · passwords. When in doubt, exclude.

### Gotcha: graceful degradation still needs traceback context
If an optional path degrades gracefully, log it at `WARNING` with `exc_info=True`. Rejected: silent fallback or warning logs stripped of exception context, because they erase the only diagnosis trail. See `error-handling.md`.

### Don't: log an error and then quietly return `None`
If a failure matters enough to log at error level, it must either raise or be translated into an explicit fallback contract. Logging plus silent `None` return creates invisible corruption. See `error-handling.md`.

### Pattern: log LLM metadata, not LLM content
It is safe to log model selection, timing, token counts, and retry/fallback behavior. It is not safe to log prompt bodies or generated prose. See `app/core/ai_client.py`.
