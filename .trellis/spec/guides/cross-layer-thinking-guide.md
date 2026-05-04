# Cross-Layer Thinking Guide

## Core Idea

Most bugs happen at layer boundaries, not within layers. Before implementing cross-layer features, map the data flow and define contracts at each boundary.

## Pre-Implementation Checklist

For each boundary (API↔Service, Service↔DB, Backend↔Frontend):
- What is the exact input/output format?
- Who validates? (Validate at entry point + defensive checks at trust boundaries)
- What errors can occur?

## Common Mistakes

1. **Implicit format assumptions** — always explicit conversion at boundaries
2. **Duplicate validation** — validate primarily at entry, not every layer
3. **Leaky abstractions** — each layer only knows its neighbors

## Project-Specific: Config Wiring Flow

```
config.py (Settings field, Pydantic default)
  → node module (reads via get_settings())
    → domain class (__init__ stores on self, methods use it)
```

| Boundary | Contract |
|----------|----------|
| config → node | `settings.<field>` returns Pydantic-validated type |
| node → domain class | Constructor kwarg matches `DEFAULT_*` type |
| domain class internal | `self.<field>` in methods; `DEFAULT_*` when no arg |

**Keyword list desync**: when two related lists exist (regex source vs membership check), define merge semantics — `None` = default, `[]` = disable, non-empty = merge. Otherwise keywords in one but not the other become dead code.

**Adding a new config parameter**: (1) field in `Settings` with default, (2) node reads via `get_settings()`, (3) domain `__init__` accepts with `Optional` + `DEFAULT_*`, (4) `None` vs `[]` semantics documented, (5) tests in `test_config_unification.py`.

## Post-Implementation

- [ ] Tested edge cases (null, empty, invalid) at each boundary
- [ ] Error handling verified at each boundary
- [ ] Data survives round-trip

## Related Specs

- Backend error shape contract: `../backend/error-handling.md`
- Frontend ApiError mapping: `../frontend/hook-guidelines.md`
- Frontend trust boundaries: `../frontend/runtime-contracts.md`
