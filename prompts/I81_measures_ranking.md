# I81 (= I44a): Def 6.13's measures and §10.10's ranking, over the M3 laws that exist today

Rendered from `docs/BUILD_PLAN.md` row I81 (a sub-key of I44, §4 "I44. Measures (all of Def 6.13), ranking").
Milestone M3; its outcome is `results/M3/ranking.json`.

Whitepaper sources:
- Def 6.13 (the five measures: PAR holonomy defect size, NAT naturality defect mass, FACT adversarial freedom
  F(m, c), UNDO residue liveness distance, DISCH discharge profile) through Thm 6.15; Thm 6.8 (F(m, c) is 0 iff the
  factorization holds), Thm 6.9 (undo residue is observable iff live), Def 6.20 (discharge profile);
- §10.10 (rank lexicographically by sink class, then persistence, then reach class, then adversary cost; discharge
  profiles feed persistence: a mixed profile ranks below a non-dischargeable one);
- §11.3 (the Impact column: sink / reach / persistence).

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` first. Then read:
- `docs/iterations/I26.md` and `holon/measures_fact.py` (I26's F(m, c), reused, never duplicated);
- `docs/iterations/I32.md` and `holon/profile.py` (I32's DISCH classes on M3, `classification()`);
- `docs/iterations/I27.md` and `replay/M3/undo/report.json` (the model's observations of each UNDO witness);
- `docs/iterations/I28.md` (the PAR-init law and the versioned machines).

**The docstring of `tests_m3/test_ranking.py` is the contract.** It fixes the command
`python -m holon rank --milestone M3 [--check]`, the document, every measure (M-PAR, M-UNDO, M-FACT, M-DISCH, M-NAT,
M-NA) and every ranking rule (channels K1-K8, persistence PE1-PE3, reach RE1-RE3, cost CO1).

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in
`spec/M3/amendments.jsonl`):
- `spec/M3/lib/ranking.json`: the policy (each rule's measure, the pending keys, the sink class of each channel, the
  order of each dimension); it names no law, action or target;
- `tests_m3/_i81.py`: the instrument, written without holon's measure or ranking code; the predicted values and the
  analogue map of §11.3's Impact column (a human reading, which lives in the tests, never in `holon/`).

Deliverables:
- `holon/measures.py`: one interface over the five measures; each law gets a value, a certified bound,
  "not applicable" (a rule Def 6.13 gives no measure) or "pending <key>" (NAT until I29; the DISCH profile until
  I37's calibrated cost);
- `holon/rank.py`: the channels, persistence, reach and cost of every REFUTED law, and the lexicographic ranking;
- `python -m holon rank --milestone M3 [--check]`, `results/M3/ranking.json`, `spec/schemas/ranking.schema.json`;
- the regeneration check: `tests_m3/test_ranking.py::TestCommand` (cheap: no checker, no solver, no node).

Constraints:
- Everything is computed from records, witnesses, replay reports and model documents. Never hand-write a measure;
  never special-case a law id in `holon/`.
- No generator closure moves: no law, record, generated or replay file changes except `results/M3/ranking.json`.
- Computed sink classes are compared with §11.3's Impact column; each difference is explained in the report, never
  "fixed" by changing the policy after the comparison.
- Determinism: two runs write the same bytes.

Coordination: I28 (PR #50) is merged into the base. I29 (the NAT rule, PR #51) follows; NAT stays "pending I29" unless
I29 merges before the build ends, when its measure is computed. Whoever merges second regenerates the ranking.

Exit: `tests_m3/test_ranking.py` (its construction tests green; a missed prediction is reported, not fixed); the
ranking regenerates byte-identically; every measure has a value, a bound, "not applicable" or a pending key.
