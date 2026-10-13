# I60: A1 mutation adequacy on real code, replacement catalog

Rendered from `docs/BUILD_PLAN.md` §3 row I60 and §4 I22, whose kill criterion, threshold and exit I60 inherits (whitepaper §9.5 auditor A1, §9.6, §12.1 L1 "Sensitivity", §13 "mutation adequacy", §15.2 M2 exit (b)). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs, formats, CLIs and rules are in the docstring of `tests_m2/test_mutation_adequacy_i60.py`.

## Why a replacement

I22's catalog was rejected before any mutant ran. The delegated independent sign-off found three problems (`docs/iterations/I22.md`, `docs/iterations/I22_catalog_review.json`):
- its scope was tied to the outcome;
- its K2 was not localized;
- its error clause was too broad.

I22's own contract (the `tests_m2/test_mutation_adequacy.py` docstring, preregistered at `f8fa447`; restated by BUILD_PLAN §3 row I60) says: "If the human rejects the catalog, nothing runs and a replacement is preregistered under a new key." I60 is that key.

I22's predictions stay in `spec/M2/predictions.json` and are never scored. Its run tests are removed from `tests_m2/test_mutation_adequacy.py`, one `spec/M2/amendments.jsonl` line per test key (kind `retired_by_rejection`); none is skipped. Its `TestInstrument` stays, as the record of the rejected instrument.

## The instrument

`spec/M2/lib/mutation_catalog_i60.json` is frozen: the test pins its sha256. Its `computation` field shows how every value was computed from the pinned checkout (`3e44e795`) and the pinned HOLON artifacts (at `04e2293`, I20 merged). It holds:
- **The threshold:** 0.80 of stratum A's non-equivalent mutants (human answer Q6).
- **The seed:** 20261060. The catalog is exhaustive, so no sampling uses it.
- **The strata:**
  - **Stratum A** is scored. It covers three groups:
    - the coverage-certified scope: every function and modifier the I19 walker reaches from the actions of the adopted rollup document (92 of them), plus the two codec functions no action reaches;
    - the header codec libraries;
    - the Go codec file the M2 diagram adopts (`common/batch/batch_header.go`).
  - **Stratum B** is measured with no threshold: the 11 other Go files holding an I18 codec.
  - The site rule never depends on laws.
- **12 operators:**
  - I22's 8;
  - `cmp_boundary_mirror` (`<=` and `<` flipped);
  - three decoder operators: Solidity getter `mload` offset ±1, `shr` width ±8, and Go getter slice ±1.
- **242 mutants:** A001-A192 and B001-B050. One stratum-B site does not compile and is listed as stillborn.
- **The rules:**
  - the predicted sets: one mechanical rule over the M0 roles (`dec_go` implies `ok_go`), the M1x cones naming actions, and the M2 DERIVATION entry points;
  - the structural classes;
  - the kill criterion;
  - the replay semantics;
  - the projection;
  - equivalence, duplicates and the tce mutants;
  - the channels, survivor classes and reporting;
  - the adjudication procedure.

**Preregistered limitations** (instrument `replaces.findings`, "Limitations that stay"): the M1x laws are decided on I20's window view, so 51 stratum-A mutants are abstraction-carried by construction; no M2 law can move (SORT-site laws decide on the hand model, SORT-width laws have no Reach predicate); `L_dom_hdr`, `L_par_hdr_v2` and `L_par_hdr_ssvh` are REFUTED at baseline and only mask; the Solidity getters feed no projected op; stratum B has no decision path; no in-scope file holds a bit mask, so whitepaper §9.5's "wrong masks" has no operator; mutants are first-order. The structural ceiling is stated before anything runs: 103 of 192 stratum-A mutants are reachable.

`spec/M2/lib/mutation_diff_sheet_i60.md` shows every mutant as a unified diff. It holds no prediction, no structural class and no outcome. The equivalence panel judges from this sheet.

## When it runs

1. **This prereg merges.**
2. **The catalog review.** The lead delegates a two-lens review to two fresh agents:
   - a fairness lens;
   - a soundness lens.

   Each agent reads the instrument in full and recomputes the sites. The review is committed at `docs/iterations/I60_catalog_review.json`, recording the delegation. If either lens finds a blocking problem, nothing runs and a replacement is preregistered under a new key.
3. **The equivalence panel.** A blind panel judges equivalence from the diff sheet:
   - two judges per file group;
   - a refuter, who must confirm every equivalent verdict;
   - every tce mutant is equivalent.

   The adjudication is committed alone at `spec/M2/equivalent_mutants_i60.json`. It records the delegation and is never written to `spec/M2/equivalent_mutants.json`. The panel's full record, if kept, goes to `docs/iterations/I60_equivalence_panel.json` in a later commit.
4. **The build** starts after I21's exit (zero open high-severity findings): the tree of the records' `pipeline_commit` holds `audit/rounds/M2/round2.json` and no open high finding in `audit/M2_findings.jsonl`. Before the review and the adjudication exist, `mutate run` runs no mutant; only `--baseline-only` and fixtures outside the catalog may run.

## Deliverables (summary; the contract has the details)

- **`holon/mutate/`:**
  - `operators.py`: `catalog()` re-finds exactly the instrument's 242 mutants; `apply()` checks the original text.
  - `project.py`: the projected holon-facts/0.1 header document. It uses additive extensions only, and `facts/morph_header.json` compiles to the same bytes.
  - `replay.py`: runs each role on a tree's own code, by claim, at exact field values, with the declared meanings (`call`, `claim`), and replays trace witnesses on the tree's own Rollup (`trace_claim`: a Panic at the law's site falsifies, a reverted step is a no-op).
  - `run.py`: the per-mutant pipeline and the rates.
  - The CLI: `python -m holon mutate list|sheet|project|replay --i16|run|rate`.
  - holon/mutate names nothing of the target.
- **The replay harness sources:** under `replay/M2/mutation_i60/`.
- **The pipeline, per mutant and for the null mutant (the baseline):**
  1. a scratch copy with the mutant applied;
  2. re-extraction with I17, I19 (with A19) and I18, unchanged;
  3. the M0, M1x and M2 law sets decided on a scratch tree. A law whose own decided input is unchanged is carried;
  4. model hits, replayed on the mutant and on the original code;
  5. the K2 (c) search;
  6. the detection channels (`i20_step`, `i16_edge`), which never decide a kill;
  7. the kill decision. Errors are scoped to laws.
- **Outputs:**
  - `results/M2/mutation_i60/baseline.json`, `<id>.json` for each mutant, and `summary.json`;
  - `gen/M2/mutation_i60/header.projected.json`;
  - the `mutation_adequacy` entry of `results/M2/metrics.json`, with I22-R6's name and shape (I23 reads it);
  - `docs/iterations/I60.md`, with the prediction table.

## Kill criterion (BUILD_PLAN I22, verbatim, read mechanically by the instrument)

A mutant is killed iff the obstruction predicted for its operator appears, localized to the mutated edge: a law moves to REFUTED, with a witness that replays on the mutant code, or a PROVED law loses its proof. A replay disagreement alone is recorded as "extraction defect detected", not as a kill.

- **K1** needs all of:
  - the law is PROVED or UNKNOWN at baseline, or new (absent at baseline, with its basis inside a mutated function);
  - the law is REFUTED on the mutant, with a Bend-checked counter-law;
  - the recorded witness replays on the mutant code and not on the original.
- **K2** needs all of:
  - the law is PROVED at baseline and UNKNOWN on the mutant;
  - (a) the law's own decided input changed;
  - (b) the generator that proved it at baseline completed on the mutant and Bend rejected the proof. A timeout, `Unsupported` or `None` is a law-level error, retried once;
  - (c) one of the first 16 candidates falsifies the claim on the mutant code and not on the original.

  With (a) and (b) but not (c), the law is `proof_lost_unwitnessed`, never a kill. A law PROVED at baseline whose mutant proof attempt did not complete with a rejection is `error`, never UNKNOWN.
- **Recorded, never counted as kills:**
  - a masked obstruction (a predicted, baseline-REFUTED law whose hit replays on the mutant only);
  - a replay disagreement;
  - a baseline finding (the hit replays on both the mutant and the original);
  - an unpredicted obstruction (K1 or K2 on a law outside the predicted set).

## Predictions (key I60)

| id | claim |
|---|---|
| P1 | The baseline decides M0 (5 PROVED, 3 REFUTED), M1x (7/7/1) and M2 (6 PROVED, 4 UNKNOWN, 2 REFUTED) exactly as committed. |
| P2 | 95 of 192 stratum-A mutants are killed, with 0 errors, 0 unpredicted obstructions, 0 replay disagreements and 0 baseline findings. rate_non_equivalent < 0.80: M2 exit (b) is not met. |
| P3 | Killed per operator (A): mstore 21/22, shl 8/12, delete 0/7, swap 0/12, cmp 2/23, mirror 0/15, mload 0/22, shr 0/9, putuint64 14/14, copy 26/28, drop_len 0/4, go_slice 24/24. |
| P4 | mstore_offset: K1 where every byte is written, K2 alone where one byte is left unwritten. A018 survives as proof_lost_unwitnessed. |
| P5 | The 8 codec-store shl_width mutants are killed by K1. The 4 in `_commitBatch` survive with the projection unchanged. |
| P6 | cmp_boundary: exactly A058 (K1) and A059 (K2) are killed, each by L_par_hdr_v1 and L_rt_go_v1. |
| P7 | No mirrored flip is killed. A081 loses L_rt_go_v2's proof, unwitnessed. |
| P8 | No Solidity getter mutant is killed or changes the projection. The 6 tce mutants change no document. |
| P9 | m1_view never changes, so every M1x law is carried. No drop_delete or swap_cursor mutant is killed. |
| P10 | All 14 putuint64_offset mutants are killed (A136 by K2 alone). |
| P11 | 26 of 28 copy_offset mutants are killed by K1. A148 and A162 survive. |
| P12 | All 24 go_slice_offset mutants are killed by K1, through the round-trip laws whose version reads the getter. |
| P13 | No drop_len_check (A) mutant is killed. A165-A167 are masked on L_dom_hdr and filed rule_gap (law_unmoved). A168 is filed extraction_gap (model). |
| P14 | Exactly 40 stratum-A mutants show a masked obstruction: 36 on L_par_hdr_ssvh, and 4 on L_dom_hdr (A076, A165-A167). |
| P15 | 79 stratum-A mutants are killed by K1; 16 are killed by K2 alone. |
| P16 | No stratum-B mutant is killed. Each is filed rule_gap (no_law) or extraction_gap (frontend). 42 change their document. |
| P17 | Families (A): PAR-codec 91 predicted, 71 killed; PAR-round-trip 77 predicted, 55 killed; PAR-domain 6 predicted, 0 killed; M1x:DISCH, FACT, NAT, SORT, SYM, UNDO 100 predicted each, 0 killed; M2:SORT/site 99 and M2:SORT/width 73 predicted, 0 killed; no other family. |
| P18 | The i20_step corpus detects the 7 swapped cursors A045 and A047-A052. |
| P19 | Every stratum-A mutant but the 6 tce ones changes an extracted document. |
| P20 | No M2 law moves to REFUTED or loses its proof. |

**Regressions.**
- R1: gates M0, M1 and M2 pass, with no stray changes outside the outcome paths and the pinned checkout untouched.
- R2: the instrument and the operators are intact.
- R3: the scope, sites, predicted sets and structural classes are recomputed by test.
- R4: the projection equals the frozen header facts.
- R5: the replay harness reproduces I16's real outputs, sees planted edits, follows the declared meanings, and replays I15's trace witnesses.
- R6: the review and the adjudication are signed off, complete and committed in order, and the run started after I21's exit.
- R7: records, kills, proof losses, new-law localization, families, rates and the summary's lists are recomputed, and a sample reruns identically.
- R8: exit (b) is checked by test.
- R9: the `mutation_adequacy` metric is reported.
- R10: I22 is retired honestly.

## Rules

- **AGENTS.md is binding.** Never edit `facts/`, `spec/M1/facts/`, `laws/M0/` or `laws/M1/`. Never write to the pinned checkout, to sol_deps or to `spec/M2/disagreements.json`. Never read `spec/heldout/`.
- **No tool changes.** The extractors, the M0 pipeline (except the projection's additive generator extensions), holon differential, holon derive, holon fragments and the I16/I20 harnesses run unchanged. A defect found in them is a Surprise. Fixing it means rerunning every mutant from scratch, and the first run's records are reported.
- **No moving goalposts.**
  - The catalog never changes after the sign-off.
  - The threshold never moves.
  - Predictions are never tuned.
  - A miss is a Surprise reported with its evidence.
- **Survivors are filed mechanically,** never explained away. Each record keeps the instrument's structural class beside the class it received.
- **No skips.**
