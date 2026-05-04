# Error Handling

> Fail-fast error strategy and cross-layer API error shape contract.

## Strategy

**Fail-fast**: errors propagate explicitly. Silent swallowing is forbidden. Domain layer raises domain exceptions (no FastAPI dependency); API boundary translates to `HTTPException`; pipeline nodes let exceptions propagate for orchestration to catch.

## API Error Response Contract

Domain/business errors return structured `detail`:

```json
{"detail": {"code": "entity_name_conflict", "message": "Entity with this name already exists"}}
```

- `code` (required for domain errors): stable machine-readable identifier for frontend mapping.
- `message` (optional): diagnostic text, safe (no stack traces). Frontend must not display verbatim.
- Additional keys allowed (`component`, `field`, `meta`) but not required.
- Validation 422s may use FastAPI's default shape (list of error objects). If frontend needs stable mapping for a validation case, wrap as domain error with `detail={"code": "..."}`.

## Rules

### `if` + raise, not `assert`

`assert` is stripped by `python -O`. Use explicit checks in domain layer, map to HTTP 400/422 at API boundary.

### DB Constraint Conflicts -> 409

DB uniqueness violations must not surface as 500s. Always `rollback()` then translate to HTTP 409. Do not rely only on pre-check queries (race conditions).

### Background Task Error Sanitization

Background tasks storing errors in DB must:
1. Log full exception server-side (`logger.exception(...)`)
2. Store a user-friendly message in DB (e.g. `"AI 输出解析失败，请重试"`)
3. Never store `str(exc)` — leaks Pydantic class names, JSON fragments, stack traces.

### Graceful Degradation (Exception to Fail-Fast)

Allowed only when ALL four criteria are met:
1. Feature is optional
2. Fallback is safe (no corruption)
3. Logged at WARNING with `exc_info=True`
4. Never silent `pass`

### Don't: drop HTTP response headers during exception translation
Backpressure and auth semantics may live in headers such as `Retry-After` or `WWW-Authenticate`. If an application-layer wrapper converts `HTTPException` into domain/detail errors, it must carry headers through to the API boundary instead of rebuilding a header-less response. See `app/core/world_use_case_errors.py`, `app/api/world.py`, and `tests/test_world_generation_quota.py`.

## Common Mistakes

### `KeyError` -> 500 from Validation Mappings

Dict lookups like `mapping[key]` with unknown values -> `KeyError` -> 500. Use `.get(...)` and raise a domain error translated to 422.

### Silent Swallowing

```python
# FORBIDDEN
try:
    lore_manager = LoreManager(...)
except Exception:
    pass  # invisible failure
```

Always: log + raise, or let propagate.

## Related Specs

- Frontend error mapping: `../frontend/hook-guidelines.md`
- Frontend trust boundary: `../frontend/runtime-contracts.md`
