# I32: DISCH II, discharge profiles in the §8.4 form, Pareto search, bounded dominance and classification

Rendered from `docs/BUILD_PLAN.md` §4 I32. Milestone M3; its outcomes are on the test milestone T32 and, for the
classification, on M3.

Whitepaper sources:
- §2.4 (the delay guard: κ ≡ enq[P] + D < t, ρ ≡ n > 0; the pay and wait strategies) and §11.5 (O33 reconciled);
- §5.7 (DISCH revised: Write*_X, Def 6.20's discharge profile, the persistent variant, the class table);
- Def 6.20 and Prop 6.21 (profile computation by bi-criteria label-correcting search on a finite abstraction; each
  Pareto point witnessed by a strategy the kernel checks as a program; blocking by a Thm 6.10 invariant);
- §8.4 (the DISCH row: per profile point, ∃ strategy σ. ∀ schedule ≤ H. holds(σ));
- §10.7 (the algorithm: abstraction, (cost, delay) labels, the search, one law per point).

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first. Then read:
- `docs/M1_REPORT.md` §1 and §2.1 (M1's delay laws and the third strategy L_disch_delay_prove);
- `laws/M1/L_disch_delay_*.json` and `spec/M1/facts/morph_rollup.json` (its `disch` cost model and `principals`);
- `docs/iterations/I31.md` and the contract of `tests_m3/test_disch.py` (I31's basis, classes and law families).

**The docstring of `tests_m3/test_disch_profile.py` is the contract.** It fixes the command
`python -m holon profile --milestone T32`, the profile document, the laws and their subforms, the Bend files, the
records (`disch_class`, `disch_profile`) and the M3 classification document.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in
`spec/M3/amendments.jsonl`):
- `spec/M3/lib/disch_profile.json`: the obligation (the delay guard on M1's machine at s*), the candidates (M1's
  search hints), the cost model, the search bound, the schedule (H, principals, the E-closure alphabet), the
  dominance bound, the persistent variant, the time abstraction and the class table;
- `tests_m3/_i32.py` and `tests_m3/fixtures/disch_profile/i32.mjs`: the instrument, written without holon's profile
  code.

Why T32: the delay guard reads the L1 message queue. Only M1's machine models the queue; on M3 the queue is an
external component until I36 extracts it, and Q19 forbids hand-written facts on M3. So the plan's predictions are
made on T32, M1's machine under the I32 rule, and the delay guard's M3 profile follows I36.

Deliverables:
- `holon/analysis/abstraction.py`: the finite abstraction (the move alphabets from the hints, the E-closure, the time
  abstraction and its soundness check);
- `holon/js/profile.mjs`: the bi-criteria label-correcting search, the exhaustive bounded enumeration, the persistent
  search, the strategy-table synthesis against every schedule (the game), and the abstraction check;
- `holon/rules/disch_profile.py`: the obligation, the laws (points, dominance, persistent points, abstraction), the
  class, the M3 classification;
- `holon/gen/profile.py`: the Bend profile module and each law's LAWS.bend and PROOF.bend (decided by evaluation);
- `python -m holon profile --milestone T32`: the run, the records, the summary, and `gen/M3/disch/classification.json`.

Constraints:
- No file of a generator closure changes (holon-ir/0.1-0.3, the typed, DISCH, UNDO and FACT runners): rule I32 is
  not registered in `holon/rules/__init__.py` nor in the M3 rule catalog, and nothing in a closure imports it.
- No M0-M3 law, record or Bend file changes, except the new `gen/M3/disch/classification.json`.
- Every T32 law is decided by Bend; a law Bend does not accept is UNKNOWN with what was tried, never edited.
- Determinism: two runs write the same bytes (records equal up to seconds).

Exit: `tests_m3/test_disch_profile.py` green; profile laws regenerate byte-identically.
