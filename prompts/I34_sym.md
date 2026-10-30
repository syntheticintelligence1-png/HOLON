# I34: rule SYM on M3

The prereg is the key `iterations.I34` in `spec/M3/predictions.json`. The contract is the docstring of
`tests_m3/test_sym.py`, rules J1-J12. The instrument is `tests_m3/_i34.py`. The lead's design note covers the
generators, the law forms and the split into I34b.

## Before building

- Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, the contract, and whitepaper §5.4, §8.3, §8.4 and
  Appendix E.
- The build starts once I68 (structural store) and I33 (Word lemmas, typed terms) are on the lead. Merge the lead in
  first; the lead's lines go first.

## What to build

1. **`holon sym --milestone M3`** (J1, J5, J7, J8): `results/M3/sym/` (families, splits per family, races) and
   `audit/sym_adjudications/`. Inputs: the facts, the sort solution and the typed model's text. Nothing names the
   target.
2. **`holon/rules/sym.py`**: the producers tau, pi, omega, sentinel, and the catalog entry (J4: the next free version,
   the same producer objects plus SYM).
3. **The generated sym section** (J2, J3):
   - the generators τ_d and π_{a,b} over I68's store, with τ_d EVM-faithful (an absent key reads d);
   - the sym_ok terms;
   - the IR term `sym` in the schema, with Q4 kept byte-equal;
   - render_term and refs.
4. **The decision** (J6):
   - equivariance proofs by commutation lemmas over SK frames and I33's Word lemmas;
   - sentinel proofs by Reach induction where an invariant is needed;
   - refutation from reachable prefixes;
   - two-world replays on the real Rollup;
   - both-order replays for omega;
   - race_disabling classification.
5. **The filter value `split_pending`** (additive in result_record_v2), and the routes (J8).
6. **Outcomes.** Derive with the bump, recatalog, bind, and re-make every M3 record on runners (the sharded
   workflow: DISCH in 7 jobs, typed SORT one job per law). Then rank, report and metrics.

## Rules

- **Never weaken a law to make it pass.**
  - A law with no proof stays UNKNOWN, naming the lemma it lacks.
  - A REFUTED law is a result.
- **O21 and the messenger's sentinels belong to I34b.** Do not state them here.
- **Run your own adversarial self-check.** Do not spawn review agents.
- **Push only to `claude/ci-i34*`.**
- **The report** is `docs/iterations/I34.md`, ending with Done / Surprises / Questions for the human / Not done.
