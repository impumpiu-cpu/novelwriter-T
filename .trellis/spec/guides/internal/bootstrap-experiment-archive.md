# Bootstrap Experiment Archive

> Closed experiments kept for reference. These were tested, evaluated, and removed during the bootstrap optimization phase.

## NFKC Alias Canonicalization (2026-02-20, removed)

A deterministic alias canonicalization pass (NFKC + trim + lower) was tested between
`build_window_index` and `compute_cooccurrence`, then removed after isolated
A/B verification.

Result: key collisions were effectively zero on the important-candidate set.
The pass was a no-op and was removed.

## Substring Containment Canonicalization (2026-02-21, removed)

A deterministic pass that merged important candidate A into B when A was a
substring of B and ≥60% of A's windows also contained B. Implemented, tested,
and evaluated with `eval_runner.py` single-variable isolation.

Diagnostic found real substrate: yxs had 163 high-overlap substring pairs, 18 in
top-200 co-occurrence. santi had 37 / 11. gmzz had 4 / 12.

Eval result (3-book):
- Entity_F1: small positive delta (precision improved, recall unchanged)
- Pair_F1: zero delta (freed top-K slots filled by other FPs)
- BookScore mean delta: +0.000621 (below soft gate 0.002)
- Hard gates: all passed

Conclusion: the algorithm works correctly but hits a hard ceiling. Removing
substring noise from top-K does not improve Pair_F1 because the replacement
pairs are also FPs. The bottleneck is overall candidate precision, not
substring artifacts specifically. Shelved until candidate quality improves
enough that freed slots would be filled by TPs.
