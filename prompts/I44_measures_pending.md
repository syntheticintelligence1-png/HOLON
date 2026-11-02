# I44 (= I44b): Def 6.13's measures that I81 left pending, and the ranking over them

Rendered from `docs/BUILD_PLAN.md` row I44 (I81 = I44a built the computable half). Milestone M3; its outcome is
`results/M3/ranking.json`.

Whitepaper sources:
- Def 6.13 (naturality defect mass for NAT; F(m, c) for FACT; discharge profile for DISCH), Def 6.20, Thm 6.8;
- §5.3 (NAT: native equivalence, naturality, composition coherence), and §6's NAT row (Obs(op'(eta s)) against
  Obs(op'(nat s)));
- §10.10 (the ranking; discharge profiles feed persistence).

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` first. Then read:
- `docs/iterations/I81.md` (its "Not done" list is this key's scope) and `holon/measures.py`, `holon/rank.py`;
- `docs/iterations/I29.md`, `holon/rules/nat_run.py` and `holon/rules/nat_replay.py` (the NAT squares, their
  witnesses and the model's two runs per witness in `replay/M3/nat/report.json`);
- for stage 2: I84's report (I37b: the calibrated cost, the public_input laws and their measures) and I89's report
  (I39c: the Go consumer compiled to Bend, I88's laws decided).

**The docstring of `tests_m3/test_measures_i44.py` is the contract.** It replaces I81's M-NAT and adds the stage-2
clauses; I81's contract stands otherwise.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line):
- `spec/M3/lib/ranking.json`, as amended at this prereg: NAT's measure is computed (unit, replay sub-directory,
  observation), and its pending_measures entry is removed;
- `tests_m3/_i44.py`: the instrument, written without holon's measure code; the predicted values.

Process:
1. Stage 1, on the lead: M-NAT in `holon/measures.py`, generic (no target identifier in `holon/`:
   `tests_m2.test_target_agnostic_exhaustive`); constants come from the sidecar or the records. Regenerate
   `results/M3/ranking.json` with `python -m holon rank --milestone M3`.
2. Stage 2, after I84 and I89 land (merge the lead, never rebase): FACT's public_input measure from I84's records,
   DISCH with I37's cost where it prices a discharge (otherwise pending, with the reason), F(Z, derivation) where a
   FACT pair over the Go derivation exists (otherwise pending, with the reason), and whatever persistence the decided
   blocking laws allow. If a measure needs a law or a new sub-form, stop and ask the lead.
3. No laws, no catalog bump; the measures stay outside every generator closure.
4. Report: `docs/iterations/I44.md`, with the CI results and the four sections. Before it, run the frozen suite,
   `python -m unittest tests_m2.test_target_agnostic_exhaustive`, `holon audit prereg --milestone M3` and the freeze
   check.
