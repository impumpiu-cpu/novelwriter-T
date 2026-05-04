# Frontend Test Layers

The frontend test tree is organized by contract depth, not by implementation type alone.

Use the lowest layer that can prove the behavior:

- `contracts/`: product invariants and fail-fast tripwires that must not drift.
- `runtime/`: storage, polling, query-cache, and pure client runtime contracts.
- `orchestration/`: hooks/selectors that resolve UI behavior from multiple runtime inputs.
- `components/`: component behavior with mocked boundaries.
- `pages/`: route-level integration inside the React shell.
- `web/e2e/mock/`: browser flows with mocked backend contracts.
- `web/e2e/integration/`: browser flows against the real backend stack and worker loop.

For high-risk Studio world-entry changes, keep coverage stacked in this order:

1. invariant in `contracts/`
2. runtime state contract in `runtime/`
3. multi-source decision logic in `orchestration/`
4. visible behavior in `components/` or `pages/`
5. browser replay in `web/e2e/`

Common commands:

- `npm run test:contracts`
- `npm run test:runtime`
- `npm run test:orchestration`
- `npm run test:components`
- `npm run test:pages`
- `npm run test:studio-regression`
- `npm run test:e2e:studio:mock`
- `npm run test:e2e:studio:integration`
