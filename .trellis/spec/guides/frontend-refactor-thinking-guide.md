# Frontend Refactor Thinking Guide

Use this when refactoring UI/pages to improve **reuse + testability + token/Tailwind consistency**.

## Core Idea

Refactor by **shared contracts** (visual recipes + behaviors), not by file size.

The goal is to prevent **style/behavior drift** across pages while keeping feature code readable.

## Fast Checklist (10 min)

1. Identify drift-prone repetition:
   - long Tailwind/token class bundles repeated across files
   - inline `style={{ ... }}` for theme-able visuals
   - duplicated text rendering logic (`split('\n')` vs `split('\n\n')`)
2. Centralize the *recipe* into `components/ui/` primitives with small APIs:
   - glass surfaces → `GlassSurface` (tier variants)
   - plain text rendering → `PlainTextContent` (split + spacing)
   - app buttons → `NwButton` (token-driven variants)
3. Keep **recipe vs layout** separate:
   - primitive owns tokens/blur/shadow/border defaults
   - caller owns padding/rounding/overflow/width via `className`
4. Prefer Tailwind + CSS tokens:
   - never hardcode colors/opacity values (use `--nw-glass-*`, `--color-*`, shadcn vars)
   - avoid JS-driven hover/active style mutations; use `hover:` / `focus-visible:`
5. Extract behavior only when it is reusable and test-critical:
   - React timers / side-effects → `hooks/`
   - pure formatting/serialization/download → `lib/`

## Layering Rules (Where Code Goes)

- `pages/`: route params, navigation, and composition only.
- `components/<feature>/`: feature-specific UI + orchestration.
- `components/ui/`: generic primitives with stable semantics and token recipes.
- `hooks/`: reusable behaviors with React state/timers/side-effects.
- `lib/`: pure functions (no React), easy to unit test.

## Examples

**Do (centralize glass recipe):**

```tsx
<GlassSurface variant="floating" className="rounded-xl p-2">
  ...
</GlassSurface>
```

**Don't (copy/paste the recipe):**

```tsx
<div className="rounded-xl border border-[var(--nw-glass-border)] bg-[hsl(var(--background)/0.75)] backdrop-blur-2xl shadow-[0_18px_50px_rgba(0,0,0,0.55)]">
  ...
</div>
```

**Do (normalize plain-text rendering):**

```tsx
<PlainTextContent content={text} className="flex-1 overflow-y-auto nw-scrollbar-thin" />
```

## Anti-Patterns

- splitting files just to reduce LOC (no reuse/test gain)
- introducing primitives with huge prop surfaces (hard to keep consistent)
- exposing token knobs as props (e.g. arbitrary blur/opacity) instead of tiered variants
- inconsistent newline handling across pages (paragraph rhythm drifts)

## Related Specs

- Frontend visual/tokens: `../frontend/component-guidelines.md`
- Frontend guide index: `../frontend/index.md`
- Runtime state/trust boundaries: `../frontend/runtime-contracts.md`
- Server-state and error contracts: `../frontend/hook-guidelines.md`
- Reuse-first checklist: `./code-reuse-thinking-guide.md`
