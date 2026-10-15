# I61: A1 mutation adequacy on real code, second replacement catalog

Rendered from `docs/BUILD_PLAN.md` §3 row I61 and §4 I22, whose kill criterion, threshold and exit I61 inherits (whitepaper §9.5 auditor A1, §9.6, §12.1 L1 "Sensitivity", §13 "mutation adequacy", §15.2 M2 exit (b)). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs, formats, CLIs and rules are in the docstring of `tests_m2/test_mutation_adequacy_i61.py`.

## Why a second replacement

I60's catalog was not signed off before any mutant ran (`docs/iterations/I60.md`, `docs/iterations/I60_catalog_review.json`):
- **Blocking (soundness).** The enc_sol replay harness, which every K1 witness and every K2 (c) falsification of a PROVED M0 law passes through, was specified so that its inputs did not overlap the refuter's candidates. It copied the state-root requires and typed `l1MessagePopped` as the code's uint16. Under either literal reading the kill rate is about 0, so the outcome would rest on a build choice made after the prereg.
- **The fairness lens signed off,** with advisories.

I60's own contract: "If either lens finds a blocking problem, nothing runs and a replacement is preregistered under a new key." I61 is that key.

I60's predictions stay in `spec/M2/predictions.json` and are never scored. Its run tests are removed from `tests_m2/test_mutation_adequacy_i60.py`, one `spec/M2/amendments.jsonl` line per test key (kind `retired_by_rejection`); none is skipped. Its `TestInstrument`, `TestScope` and `TestI22Retirement` stay, as the record of the instrument.

## What I61 keeps and what it changes

- **Kept, byte for byte.** I60's 242 mutants (A001-A192, B001-B050; `mutants_sha256` equal) and every value computed from the pinned checkout: the scope, the sites, edges, actions, predicted sets, structural classes and tce mutants. The fairness lens signed them off, and no mutant has run. They were re-verified at the new pin, where the extracted documents, laws, diagrams and bindings are byte-identical to I60's.
- **Changed.** What the review found. The instrument's `replaces.findings` answers every finding, blocking and advisory, as fixed or stated:
  - **The replay harness** (`replay.m0`) is I16's store-level binding, which agreed with the real code on 2107 of 2107 inputs:
    - generated per tree from the tree's own `Rollup.sol`, with the statement locations and field map of the null mutant's document;
    - each stored Header field bound from the witness at the Header field's width;
    - only the version's require copied;
    - a top-level role call with no value is no execution.
  - **A harness gate** (`harness_gate`) runs before any catalog mutant, and nothing runs if it fails. On the original code it must:
    - reproduce I16's outputs for all six edges;
    - agree with the baseline model wherever the model is defined;
    - falsify no PROVED M0 law;
    - replay every REFUTED M0 law's witness.

    Four planted controls outside the catalog must be killed as preregistered:
    - C1 and C2, in the codec library and the Go encoder, by K1;
    - C3, inside the entry function's copied build block, by K1;
    - C4, at the copied version require, by K2 through a partiality witness.

    C3 and C4 close the gap that library-only controls leave: a harness that copied the null tree's entry text would still pass C1 and C2.
  - **The kill criterion**:
    - a law REFUTED with a checked counter-law is decided whatever happened to its proof attempt;
    - K2 (b) reads the first line of the checker's output, over a generated model that checks alone: the pinned Bend prints `SOME PROOFS FAIL` for a parse or type error of a generated file too;
    - K2 (c) also accepts a partiality witness, so a domain that shrank (A081) is witnessed at code level;
    - each K2 records its model tie.
  - **Survivor classes**: `extraction_gap` with stage `replay` (a replay disagreement), and `baseline_finding`.
  - **Duplicates** widened to every operator within one statement (14 candidate groups).
  - **Contradictions** reported as function-level and as reachable.
  - **Reporting** adds per-site, non-error, by-language, B-codec, plan-literal, new-law and K2 model-tie rates.
  - **Adjudication** names its forbidden files one by one. The list includes I60's review file, which records I60's headline forecast in two disclosures. Reviewers get I60's findings from `replaces.findings`, or from a redacted copy. The instrument's own statements that border on outcomes are stated as known exposure.
  - **Limitations** stated:
    - the premise-limited reachable mutants A148, A162 and A165-A168, which put the ceiling at 97;
    - the threshold's consequence, at least 71 equivalent verdicts for exit (b);
    - the unmutated sites;
    - the masked-obstruction blind spot behind L_par_hdr_v2;
    - M0's whole-document own input;
    - the bvh_at matching gap;
    - the store-level reading.
- **The forecast** is I60's, which was made before any run and is consistent with the working reading of its harness, the one I61 preregisters. It was re-derived under I61's rules, and only A081 changes: it is now killed by K2 through a partiality witness. New predictions cover the gate, the language and site splits, the K2 model tie and the plan-literal count.

## When it runs (instrument `preconditions`)

1. **This prereg merges.**
2. **The catalog review.** The lead delegates a two-lens review to two fresh agents: a fairness lens, and a soundness lens that also covers the harness and its gate.
   - Each reads the instrument in full and recomputes the sites.
   - The review is committed at `docs/iterations/I61_catalog_review.json`.
   - If either lens finds a blocking problem, nothing runs and a replacement is preregistered under a new key.
3. **The equivalence panel.** A blind panel judges equivalence from `spec/M2/lib/mutation_diff_sheet_i61.md`:
   - two judges per file group;
   - a refuter, who must confirm every equivalent verdict;
   - every tce mutant is equivalent.

   The adjudication is committed alone at `spec/M2/equivalent_mutants_i61.json`.
4. **The harness gate.** `results/M2/mutation_i61/gate.json` must pass at the run's pipeline commit. It needs neither the review nor the adjudication, and is first committed before any catalog mutant's record.
   - Its attempts are all kept, each at its own commit, and a fix of `holon/mutate` after a failed attempt is reported.
   - A failure caused by a tool the rules keep unchanged stops the run, and the human decides.
5. **The baseline** reproduces the pinned statuses, the committed documents and the committed projection. Otherwise it is a reported defect, not a measurement.
6. **I21's exit** holds at the records' pipeline commit. It holds today: I21 is merged and has no open high-severity finding.

Agents of the delegated steps never read the forbidden files (instrument `adjudication.forbidden`). The lead keeps forecasts and verdicts out of task lists and any other text a delegated agent can see.

## Deliverables (summary; the contract has the details)

- **`holon/mutate/`:**
  - `operators.py`: `catalog()` re-finds exactly the 242 mutants; `apply()` checks the original text.
  - `project.py`: the projected holon-facts/0.1 header document, with additive extensions only.
  - `replay.py`: the per-tree harness of `replay.m0`. Roles run by claim at exact field values, and trace witnesses replay on the tree's own Rollup.
  - `run.py`: the per-mutant pipeline, the controls, the gate and the rates.
  - The CLI: `python -m holon mutate list|sheet|project|replay --i16|gate|run|rate`.
  - holon/mutate names nothing of the target.
- **The harness sources:** under `replay/M2/mutation_i61/`.
- **Outputs:**
  - `results/M2/mutation_i61/`: `gate.json`, `controls/C1.json` and `C2.json`, `baseline.json`, `<id>.json` for each mutant, and `summary.json`;
  - `gen/M2/mutation_i61/header.projected.json`;
  - the `mutation_adequacy` entry of `results/M2/metrics.json` (I23 reads it);
  - `docs/iterations/I61.md`, with the prediction table.

## Kill criterion (BUILD_PLAN I22, verbatim, read mechanically by the instrument)

A mutant is killed iff the obstruction predicted for its operator appears, localized to the mutated edge: a law moves to REFUTED, with a witness that replays on the mutant code, or a PROVED law loses its proof. A replay disagreement alone is recorded as "extraction defect detected", not as a kill.

- **K1:**
  - the law is PROVED or UNKNOWN at baseline, or new with its basis inside the mutated function;
  - it is REFUTED on the mutant, with a Bend-checked counter-law;
  - the recorded witness replays on the mutant code and not on the original.
- **K2:**
  - the law is PROVED at baseline and UNKNOWN on the mutant;
  - (a) its own decided input changed;
  - (b) the baseline generator completed on the mutant, the checker's first output line reads SOME PROOFS FAIL, and the mutant's generated model checks alone;
  - (c) one of the first 16 candidates falsifies the claim on the mutant code and not on the original, or is a partiality witness.
  - With (a) and (b) but not (c), the law is `proof_lost_unwitnessed`, never a kill.
- **Recorded, never counted:**
  - masked obstructions;
  - replay disagreements;
  - baseline findings;
  - unpredicted and recomputed-only obstructions.

## Predictions (key I61)

| id | claim |
|---|---|
| P1 | The baseline decides M0 (5 PROVED, 3 REFUTED), M1x (7/7/1) and M2 (6 PROVED, 4 UNKNOWN, 2 REFUTED) exactly as committed. |
| P2 | 96 of 192 stratum-A mutants are killed, with 0 errors, 0 unpredicted obstructions, 0 replay disagreements and 0 baseline findings. rate_non_equivalent < 0.80: M2 exit (b) is not met. |
| P3 | Killed per operator (A): mstore 21/22, shl 8/12, delete 0/7, swap 0/12, cmp 2/23, mirror 1/15, mload 0/22, shr 0/9, putuint64 14/14, copy 26/28, drop_len 0/4, go_slice 24/24. |
| P4 | mstore_offset: K1 where every byte is written, K2 alone where one byte is left unwritten. A018 survives as proof_lost_unwitnessed. |
| P5 | The 8 codec-store shl_width mutants are killed by K1. The 4 in `_commitBatch` survive with the projection unchanged. |
| P6 | cmp_boundary: exactly A058 (K1) and A059 (K2) are killed, each by L_par_hdr_v1 and L_rt_go_v1. |
| P7 | Of the mirrored flips, exactly A081 is killed: K2 on L_rt_go_v2, through a partiality witness. |
| P8 | No Solidity getter mutant is killed or changes the projection. The 6 tce mutants change no document. |
| P9 | m1_view never changes, so every M1x law is carried. No drop_delete or swap_cursor mutant is killed. |
| P10 | All 14 putuint64_offset mutants are killed (A136 by K2 alone). |
| P11 | 26 of 28 copy_offset mutants are killed by K1. A148 and A162 survive. |
| P12 | All 24 go_slice_offset mutants are killed by K1, through the round-trip laws whose version reads the getter. |
| P13 | No drop_len_check (A) mutant is killed. A165-A167 are masked on L_dom_hdr and filed rule_gap (law_unmoved). A168 is filed extraction_gap (model). |
| P14 | Exactly 40 stratum-A mutants show a masked obstruction: 36 on L_par_hdr_ssvh, and 4 on L_dom_hdr (A076, A165-A167). |
| P15 | 79 stratum-A mutants are killed by K1; 17 are killed by K2 alone. |
| P16 | No stratum-B mutant is killed, including the 42 in codec functions. Each is filed rule_gap (no_law) or extraction_gap (frontend). 42 change their document. |
| P17 | Families (A): PAR-codec 91 predicted, 71 killed; PAR-round-trip 77 predicted, 56 killed; PAR-domain 6 predicted, 0 killed; M1x:DISCH, FACT, NAT, SORT, SYM, UNDO 100 predicted each, 0 killed; M2:SORT/site 99 and M2:SORT/width 73 predicted, 0 killed; no other family. |
| P18 | The i20_step corpus detects the 7 swapped cursors A045 and A047-A052. |
| P19 | Every stratum-A mutant but the 6 tce ones changes an extracted document. |
| P20 | No M2 law moves to REFUTED or loses its proof. |
| P21 | The harness gate passes at its first attempt. C1 and C2 are killed by K1 through L_par_hdr_v0, C3 by K1 through L_par_hdr_v1, and C4 by K2 with partiality witnesses through L_rt_go_v1 and L_rt_go_v2. |
| P22 | By language (A): Solidity 32/122, Go 64/70; B: Go 0/50. Per site, 51 of 127 stratum-A sites are killed. |
| P23 | Every killed mutant with a K2 law has a model-tied one; no baseline_finding or extraction_gap (replay) survivor; no recomputed-only obstruction. |
| P24 | The plan-literal count of stratum A is 97 of 192 (the 96 kills and A018). |

**Regressions.**
- R1: gates M0, M1 and M2 pass, with no stray changes outside the outcome paths and the pinned checkout untouched.
- R2: the instrument, the operators and the controls are intact, and the run refuses without its preconditions.
- R3: the scope, sites, predicted sets, structural classes, duplicate groups and premise-limited ids are recomputed by test.
- R4: the projection equals the frozen header facts.
- R5: the replay harness reproduces I16's outputs, binds at the Header widths, sees planted edits and follows the declared meanings.
- R6: the review and the adjudication are signed off, complete and committed in order, and the run started after I21's exit.
- R7: records, kills, proof losses, partiality witnesses, survivors, every rate and the summary's lists are recomputed, and a sample reruns identically.
- R8: exit (b) is checked by test.
- R9: the `mutation_adequacy` metric is reported.
- R10: I60 is retired honestly.
- R11: the harness gate passed, before any catalog record, and reproduces.

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
