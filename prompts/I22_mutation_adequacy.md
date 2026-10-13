# I22: A1 mutation adequacy on real code

Rendered from `docs/BUILD_PLAN.md` §4 I22 (whitepaper §9.5 auditor A1, §12.1 L1 "Sensitivity", §13 "mutation adequacy", §15.2 M2 exit (b); closes V14). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs, formats, CLIs and rules are in the docstring of `tests_m2/test_mutation_adequacy.py`.

The instrument is `spec/M2/lib/mutation_preregistration.json`. It is frozen: the test pins its sha256. It holds:
- the threshold (0.80, human answer Q6);
- the seed (20261022);
- the target and the in-scope list;
- the 8 operators, with their rewrite rules and predicted obstructions;
- the kill criterion, the equivalence definition and the detection channels;
- the projection roles and the law sets, with their decided inputs;
- the 110 mutants M001-M110.

Its `computation` field shows how every value was computed from the pinned checkout and committed artifacts. BUILD_PLAN names `spec/M2/preregistration.json`; a prereg commit may only add files under `spec/M2/lib/`, hence the path.

## Goal

Plant realistic misimplementations in the real Solidity and Go of the pinned Morph checkout (`3e44e795`). Re-extract each mutant with the M2 frontends, decide the laws on what was extracted, and measure the kill rate against the threshold the human fixed in advance. The threshold never moves.

## When it runs

1. **The prereg merges.** The human then receives `spec/M2/lib/mutation_diff_sheet.md`, which shows every mutant as a unified diff and holds no prediction and no outcome. The human:
   - signs off the catalog;
   - adjudicates each mutant equivalent or not;
   - commits `spec/M2/equivalent_mutants.json` alone, with `"catalog_signed_off": true`.
2. **The build starts** after:
   - I20 is merged (holon differential and its window view, the SORT-width rule, holon fragments, the re-derived site laws);
   - I21's exit holds (zero open high-severity findings).
3. **Before the adjudication exists**, the pipeline may run only on the baseline (`mutate run --baseline-only`) and on fixtures outside the catalog. `mutate run` refuses to run any mutant without a complete, signed-off adjudication.

## Deliverables (summary; the contract has the details)

- **`holon/mutate/`:**
  - `operators.py`: `catalog()` re-finds exactly the instrument's 110 mutants on the pinned checkout, and `apply()` makes a mutant.
  - `project.py`: the holon-facts/0.1 header document the laws/M0 statements are decided on, composed from the extracted documents only.
  - `run.py`: the per-mutant pipeline and the rates.
  - `python -m holon mutate list|sheet|project|run|rate`.
  - holon/mutate names nothing of the target.
- **The pipeline, per mutant and for the null mutant (the baseline):**
  1. a scratch copy of the pinned checkout with the mutant applied;
  2. re-extraction with I17, I19 (with A19) and I18, unchanged;
  3. three law sets decided on a scratch copy of the tree:
     - **M0:** the projected header document, `holon run --milestone M0 --no-registry`;
     - **M1x:** the 15 rollup laws through I20's `holon differential`;
     - **M2:** `holon derive` then `holon run --milestone M2 --no-registry`;
  4. witness replay on the mutant and on the original code;
  5. the detection channels: I20's step refinement and corpus (`i20_step`: the baseline and every Solidity mutant, at least 2432 steps), and I16's per-edge refinement (`i16_edge`: the baseline, every Go mutant and every Solidity mutant with header edges). Their harnesses run unchanged, every record lists exactly its runs, and the channels never decide a kill.
- **Carrying.** A set whose normalized decided input equals the baseline's carries the baseline's statuses. `run --check` reruns a sample with `--no-carry` and must agree.
- **Outputs:**
  - `results/M2/mutation/baseline.json` and `results/M2/mutation/M001.json` .. `M110.json`;
  - `results/M2/mutation_adequacy.json`, with both rates (all mutants, non-equivalent mutants), survivors filed as `extraction_gap` (with `gap_stage` frontend or model) or `rule_gap`, extraction defects, corpus detections and unpredicted obstructions;
  - `gen/M2/mutation/header.projected.json`;
  - the `mutation_adequacy` entry of `results/M2/metrics.json` (whitepaper §13 metric, §12.1 "Sensitivity"), read from the summary; it leaves `not_applicable`.
- **Recomputed, not trusted:** every `changed` flag is a comparison of hashes with the baseline record (canonical JSON of the normalized document); the baseline reproduces the committed statuses of all three sets and the committed documents.
- **`docs/iterations/I22.md`**, with a prediction table.

## Kill criterion (BUILD_PLAN I22, verbatim)

A mutant is killed iff the obstruction predicted for its operator appears, localized to the mutated edge: a law moves to REFUTED, with a witness that replays on the mutant code, or a PROVED law loses its proof. A replay disagreement alone is recorded as "extraction defect detected", not as a kill.

Mechanically:
- **K1:** baseline PROVED or UNKNOWN, mutant REFUTED, and the recorded witness replays on the mutant and not on the original. Every move to REFUTED needs this replay, whatever the baseline status.
- **K2:** baseline PROVED, mutant UNKNOWN, and the decided input of the law's set changed (the proof is lost).
- **Killed:** some law of the operator's predicted set satisfies K1 or K2.
- **Replay disagreement:** a law that moves to REFUTED without a witness that replays on the mutant and not on the original. It is listed in `replay_disagreements`, sets `extraction_defect_detected`, and is never a kill (whitepaper §9.6: a witness that fails on the real code is a model defect).
- A witness replays when running it shows the claim false. A call of the claim that panics, or returns an error where the claim needs its value, makes the claim false; the replay harness recovers the panic and records it.

## Predictions (key I22)

| id | claim |
|---|---|
| P1 | The baseline decides the 8 laws/M0 statements exactly as results/M0 does: 5 PROVED, 3 REFUTED. |
| P2 | All 22 mstore_offset mutants are killed (K1 or K2): M001-M020 by L_par_hdr_v0, M021-M022 by L_par_hdr_v1. |
| P3 | The 8 codec shl_width mutants are killed (M023-M028 by L_par_hdr_v0, M029-M030 by L_par_hdr_v1). The 4 in `_commitBatch` (M031-M034) survive. |
| P4 | Of the 16 cmp_boundary mutants, exactly M052 and M053 (Rollup.sol:333, :353) are killed, by L_par_hdr_v1. |
| P5 | No drop_delete mutant is killed. The plan expected the UNDO laws to kill M035. |
| P6 | No swap_cursor mutant is killed. The corpus detects M041 and M043-M048. |
| P7 | The M1x decided input (I20's window view) never changes, so the 15 rollup laws keep their baseline statuses. |
| P8 | The 30 Rollup-only mutants leave the projected header document unchanged. |
| P9 | All 14 putuint64_offset mutants are killed (M065-M070 by L_par_hdr_v0, M071-M078 by L_par_hdr_v1). |
| P10 | 26 of the 28 copy_offset mutants are killed. M090 and M104 (the ssvh copy shifted to 186) survive. |
| P11 | No drop_len_check mutant is killed. The plan expected the domain law to kill them. |
| P12 | 72 of 110 are killed, with 0 errors and 0 unpredicted obstructions. rate_non_equivalent < 0.80: M2 exit (b) is not met. |
| P13 | extraction_defect_detected (replay disagreements and channels) is false for the 30 Rollup-only mutants and for 41 Go mutants. It is null for M078 and M107-M110, whose code panics on I16's corpus. |
| P14 | Every mutant changes at least one extracted document, so no survivor is a frontend-stage extraction gap. |

**Regressions.**
- Gates M0, M1 and M2 pass.
- I22 changes no law, statement, facts document, extracted document or result outside its outcome paths.
- Construction: the projection equals the frozen header facts where I17 and I18 compared them; the instrument, the sheet and the operators are intact; run refuses every incomplete adjudication and accepts a complete one; the adjudication is ordered and complete; the baseline reproduces the committed documents and statuses; records, changed flags, channel runs, replay disagreements, kill decisions, classes and rates are recomputed; the pinned checkout is untouched; a sample reruns identically.
- Metrics: results/M2/metrics.json reports mutation adequacy (§13).
- Exit: rate_non_equivalent >= 0.80, recomputed by test.

## Rules

- **AGENTS.md is binding.** Never edit `facts/`, `spec/M1/facts/`, `laws/M0/` or `laws/M1/`. Never write to the pinned checkout or to `spec/M2/disagreements.json`.
- **No tool changes.** The extractors, the M0 pipeline, holon differential, holon derive, holon fragments and the I16/I20 harnesses run unchanged. A defect found in them is a Surprise. Fixing it means rerunning all 110 mutants from scratch, and the first run's records are reported.
- **No moving goalposts.** The catalog never changes after the human's sign-off, and the threshold never moves. A miss is a Surprise reported with its evidence.
- **Survivors are filed, never explained away.** Each one is an extraction gap or a rule gap (whitepaper §9.5), with its why.
- **No skips.**
