# I62: A1 mutation adequacy on real code, the rerun of I61's catalog with I61's defects fixed

Rendered from `docs/BUILD_PLAN.md` §4 I22, whose kill criterion, threshold and exit I62 inherits, as I61 did (whitepaper §9.5 auditor A1, §9.6, §12.1 L1 "Sensitivity", §13 "mutation adequacy", §15.2 M2 exit (b)). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs, formats, CLIs and rules are in the docstring of `tests_m2/test_mutation_adequacy_i62.py`.

## Why a rerun

I61 ran its 242 mutants once (`docs/iterations/I61.md`, `results/M2/mutation_i61/`, pipeline commit a233867). Its run showed five defects of the pipeline and one of the gate's rules. Each is named in the instrument's `replaces.defects`, with what it did in I61's run and its fix:

| | defect | in I61's run |
|---|---|---|
| D1 | The replay read dec_go's none value as a call not yet run. | 6 law entries became replay disagreements (A001 ×3, A058, C3 ×2). No kill or rate changed. |
| D2 | A deployment that reverts failed every trace of I20's step harness and I15's trace harness. | 5 error outcomes: A076, A098, A100, A101, A104 break Rollup's genesis import. |
| D3 | A SORT-width law over the header document could not be recorded: no ledger bundle, and no coverage entry. | 2 error outcomes (A116, A120); A027 and A031 were killed anyway. |
| D4 | One failing law failed its whole set's run. | The width laws of those four mutants. |
| D5 | Channel runs were never retried. | None seen. |
| D6 | Messages held timings and scratch paths. | 9 records not byte-reproducible (AGENTS.md rule 7). |
| D7 | A control's replay disagreement passed the gate. | C3, the D1 defect, visible before any catalog mutant ran. |
| D8 | The gate's first attempt came after a component-level rehearsal of its checks. | Disclosed in the I61 report. |

I61's own rule: "A defect found in them is a Surprise; a fix needs a rerun of every mutant from scratch, and the first run's records are reported." Its gate stops at the first passing attempt, so the rerun needs a new key. I62 is that key, as the human chose.

## What I62 keeps and what it changes

- **Kept, byte for byte.** I61's 242 mutants, its diff sheet (`spec/M2/lib/mutation_diff_sheet_i61.md`) and every value computed from the pinned checkout: the scope, sites, edges, actions, predicted sets, structural classes, tce mutants and the four planted controls. Also kept: I61's panel verdicts. Equivalence is a property of the mutant and the original program, and neither has changed.
- **Changed.** Only what D1-D8 touch:
  - **D1:** a role whose value is none is a value, unequal to every some(...).
  - **D2:** the i20_step channel and the trace replay run copies of the two harnesses' Solidity (`replay/M2/mutation_i62/`) that probe each trace's deployment. I20's and I15's own files and outputs are unchanged.
  - **D3:** the header document's ledger bundle carries its four declared assumptions, and a layout document has no coverage entry.
  - **D4, D5:** errors are isolated law by law, and channels are retried once.
  - **D6:** every message is scrubbed before it is cut to length.
  - **D7, D8:** a control with a replay disagreement fails the gate, and no check of the gate runs before its first attempt.
- **Records.** I61's records stay as its run wrote them, and are reported as the first run. I61's tests keep reading them through `HOLON_MUTATE_KEY=I61`, by two amendment lines.
- **The forecast.** I61's measured outcomes with the fixes' expected effects. The rerun tests whether the fixes do what they claim, and nothing else.

## When it runs (instrument `preconditions`)

1. **This prereg merges.**
2. **The build:**
   - the fixes of `holon/mutate`;
   - the harness copies;
   - the header document's ledger bundle and holon.records' coverage rule;
   - the M1 and M2 records regenerated for the changed generator closure (generator_sha256 only);
   - the projection at `gen/M2/mutation_i62/header.projected.json`.
3. **The delta review.** One fresh agent, both lenses, reads the I62 instrument against I61's, I61's signed-off review, and the fixes' diff. It is committed at `docs/iterations/I62_catalog_review.json`. If it does not sign off, nothing runs and a replacement is preregistered under a new key.
4. **The carried adjudication**, committed alone at `spec/M2/equivalent_mutants_i62.json`.
5. **The harness gate.** `results/M2/mutation_i62/gate.json` must pass at the run's pipeline commit, with no earlier run of its checks on the build.
6. **The baseline** reproduces the pinned statuses, the committed documents and the committed projection.
7. **I21's exit** holds at the records' pipeline commit.

The reviewer never reads the files the instrument's `adjudication.forbidden` names. The lead keeps forecasts and outcomes beyond the instrument out of every text the reviewer sees.

## Deliverables (summary; the contract has the details)

- **`holon/mutate/`**, serving the key `HOLON_MUTATE_KEY` (I62 by default, I61 for I61's tests).
- **`replay/M2/mutation_i62/`:** `HolonStepBase.sol` and `HolonTraceReplay.t.sol`.
- **`spec/M2/ledger.json`:** the header document's bundle. **`holon/records.py`:** the coverage rule.
- **Outputs:**
  - `results/M2/mutation_i62/`: `gate.json`, `controls/C1.json`-`C4.json`, `baseline.json`, `<id>.json` for each mutant, and `summary.json`;
  - `gen/M2/mutation_i62/`: `header.projected.json`, `baseline_inputs.json` and `i20_corpus.json`;
  - the `mutation_adequacy` entry of `results/M2/metrics.json`, now from I62's summary;
  - `docs/iterations/I62.md`, comparing every record with I61's.

## Predictions (key I62)

| id | claim |
|---|---|
| P1 | The baseline decides every law as committed; its documents, projection, own inputs and i20_step corpus are I61's baseline's. |
| P2 | Stratum A: 96 of 192 killed (79 with K1), 12 equivalent, 0 errors, rate_non_equivalent 96/180 < 0.80 (exit (b) not met). Stratum B: 0 of 50. |
| P3 | Every record equals I61's but for the fixes' effects on A001, A058 (D1), A076, A098, A100, A101, A104 (D2), A027, A031, A116, A120 (D3, D4). |
| P4 | A001's three round-trip laws and A058's L_rt_go_v1 are K1; no replay disagreement anywhere; 18 extraction defects (I61's less A001). |
| P5 | The five genesis-breaking mutants complete i20_step with all 3013 corpus steps differing, are corpus_detected, and survive as rule_gap (law_unmoved). |
| P6 | The width laws of A027, A031, A116, A120 are UNKNOWN by a run. A116 and A120 survive as rule_gap (law_unmoved). No record holds an error. |
| P7 | The gate passes at its first attempt. C3 is now killed by K1 through L_par_hdr_v1, L_rt_go_v1 and L_rt_go_v2. No control has a replay disagreement or a replay error. |
| P8 | The rates are I61's, with 0 errors, PAR-round-trip kills 56 (I61: 54), and the 7 former errors filed rule_gap/law_unmoved. |
| P9 | No message holds a duration, a machine path or a traceback frame. |

**Regressions.**
- R1: gates M0-M2 pass; nothing outside the outcome paths changes but the records' generator_sha256 and the metric.
- R2-R5: I61's construction checks hold for the I62 instrument, operators, scope, projection and replay harness.
- R6: the review and the carried adjudication came in order.
- R7: records and rates are recomputed by test.
- R8: exit (b) is checked by test.
- R9: the metric reads I62's summary.
- R10: I61's first run stays as written.
- R11: the gate passed, before any catalog record, and reproduces.
- R12: the fixes are what the instrument says.
- R13: a sample reruns byte for byte, two former error mutants included.

## Rules

- **AGENTS.md is binding.** Never edit `facts/`, `spec/M1/facts/`, `laws/M0/` or `laws/M1/`. Never write to the pinned checkout, to sol_deps or to `spec/M2/disagreements.json`. Never read `spec/heldout/`.
- **No tool changes beyond the named fixes.** The extractors, the M0 pipeline, holon differential, holon derive, holon fragments and the I16/I20/I15 harnesses run unchanged. D2 runs copies, and D3 changes no committed output. A new defect is a Surprise.
- **No moving goalposts.**
  - The catalog never changes.
  - The threshold never moves.
  - Predictions are never tuned.
  - A miss is a Surprise reported with its evidence.
- **I61's records are never edited.** The report compares every I62 record with I61's, and files every change no defect explains as a Surprise.
- **No skips.**
