# Iteration I48 — Evaluation corpus and unsolved controls

**Milestone:** M4 (Evaluation protocol and paper tables)  
**Branch:** `claude/i48-corpus-controls`  
**Preregistration file:** `spec/M4/predictions.json` (iteration `I48`)  
**Preregistered sidecar:** `spec/M4/lib/corpus_controls.json`  
**Preregistered test file:** `tests_m4/test_corpus_controls.py`

## Goal

Build the preregistered 20-defect historical evaluation corpus (`CORPUS-01`..`CORPUS-20`, 5 each from Morph, Arbitrum Nitro, OP Stack, and Taiko) and the 12-obligation unsolved control suite (`CTRL-01`..`CTRL-12`: 6 `FALSE_BEYOND_BOUND` obligations `L_ctrl_01`..`L_ctrl_06` and 6 `TRUE_UNPROVED` obligations `L_ctrl_07`..`L_ctrl_12`), together with the target-agnostic evaluation harness `holon/eval/` and the deterministic report `results/eval/I48_corpus_controls.json` for `whitepaper.md` §12 (Limitations and Remedies) and §13 (Evaluation Protocol).

## Context

- `docs/BUILD_PLAN.md` §M4 / Iteration `I48` and `docs/build_plan/gap_map.json` (`GAP-EVAL-CORPUS-AND-CONTROLS`) require:
  1. **20 historical defect-fixing commits** across 4 L2 rollup repositories (`morph`, `arbitrum-nitro`, `optimism`, `taiko`, 5 per system) spanning both Solidity and Go and covering all 8 rule families (`PAR`, `SORT`, `NAT`, `OWN`, `DISCH`, `FACT`, `UNDO`, `SYM`), with self-contained pre-fix, fix, and patch excerpts whose git blob SHA-1 and diff SHA-256 digests match upstream history.
  2. **12 control obligations** over a self-contained `holon-facts/0.2` state machine (`eval_ctrl_machine`):
     - **6 `FALSE_BEYOND_BOUND` (`CTRL-01`..`CTRL-06`)**: genuinely false obligations whose minimal counterexample witness requires prefix depth $\ge 3$ or `Nat` input $\ge 6$, strictly exceeding the evaluation budget (`{"prefixDepth": 2, "maxPrefixes": 100, "natMax": 5}`). Unassisted HOLON must report `UNKNOWN` with the explicit bound string; supplying the ground-truth witness must emit a counter-law accepted by Bend 2.
     - **6 `TRUE_UNPROVED` (`CTRL-07`..`CTRL-12`)**: genuinely true obligations whose Bend 2 proof requires inductive lemmas (`Nat.sub` diagonal, two-variable `Nat.add`/`Nat.sub` cancellation, `Nat.add` commutativity, `Nat.add` right-commutativity) or `Bool` state-field case analysis outside HOLON's unassisted tactic library (`mproofs.GENERATORS`). Unassisted HOLON must report `UNKNOWN` with the explicit bound string; supplying the preregistered ground-truth Bend proof must be accepted by Bend 2 with zero escape hatches.

## Preregistered contract

`spec/M4/predictions.json` (iteration `I48`) defines predictions `I48-P1`..`I48-P8` and regressions `I48-R1`..`I48-R3`:

1. **`I48-P1` (`TestPreregAndSidecar::test_sidecar_integrity`)**: `spec/M4/lib/corpus_controls.json` validates 20 corpus entries (`CORPUS-01`..`CORPUS-20`, 5 per system, all 8 rules) and 12 control obligations (`CTRL-01`..`CTRL-12`) over `eval_ctrl_machine`.
2. **`I48-P2` (`TestDefectCorpus::test_corpus_commits_and_coverage`)**: `spec/eval/corpus_manifest.json` (`schema: "holon-corpus-manifest/0.1"`) materializes all 20 preregistered defect commits and matches `spec/M4/lib/corpus_controls.json`.
3. **`I48-P3` (`TestDefectCorpus::test_corpus_excerpts_and_patches`)**: `spec/eval/excerpts/<corpus_id>/` stores `pre_fix.<ext>`, `fix.<ext>`, and `patch.diff` matching the exact git blob SHA-1s (`pre_fix_blob_sha`, `fix_blob_sha`), `patch_sha256`, and `excerpt_identifiers`.
4. **`I48-P4` (`TestUnsolvedControls::test_false_beyond_bound_controls`)**: `spec/eval/controls/` materializes `eval_ctrl_machine.facts.json`, `controls_manifest.json`, and `laws/L_ctrl_01.json`..`L_ctrl_06.json` (`FALSE_BEYOND_BOUND`) with witnesses strictly exceeding `{"prefixDepth": 2, "maxPrefixes": 100, "natMax": 5}`.
5. **`I48-P5` (`TestUnsolvedControls::test_true_unproved_controls`)**: `spec/eval/controls/laws/L_ctrl_07.json`..`L_ctrl_12.json` (`TRUE_UNPROVED`) validate against `holon-ir/0.3` and carry escape-hatch-free Bend ground-truth proofs.
6. **`I48-P6` (`TestControlExecution::test_unassisted_holon_reports_unknown_with_bounds`)**: Running unassisted HOLON on all 12 controls returns `unassisted_status == "UNKNOWN"` with `bound == "prefixes: BFS depth 2 over policy actions (<= 100 states); suffixes: divergence BFS depth 4; Nat binders 0..5 plus premise-solved values"`, zero false-positive proofs, and zero false-negative refutations.
7. **`I48-P7` (`TestControlExecution::test_ground_truth_verifications_accepted_by_bend`)**: All 6 `FALSE_BEYOND_BOUND` ground-truth witnesses produce Bend-accepted counter-laws (`Laws.cl_l_ctrl_01`..`Laws.cl_l_ctrl_06`) and all 6 `TRUE_UNPROVED` ground-truth proofs (`Laws.l_ctrl_07`..`Laws.l_ctrl_12`) under `gen/M4/controls/ground_truth/L_ctrl_01..12/{LAWS,PROOF}.bend` pass `bend.check`, `bend.check_verdict`, and `mpipeline.accepted`.
8. **`I48-P8` (`TestEvaluationReport::test_report_reproducibility_and_limitations_table`)**: `results/eval/I48_corpus_controls.json` (`schema: "holon-eval-report/0.1"`) matches a fresh `holon.eval.build_evaluation_report(...)` run byte-for-byte.
9. **`I48-P9` (`TestIsomorphicRenaming::test_isomorphic_renaming_and_tamper_rejection`)**: `holon.eval.rename` and `python3 -m holon.eval.rename` perform deterministic, seed-parameterized, bijective isomorphic renaming and unrenaming across Solidity/Go excerpts, dynamic runtime snippets, HOLON `facts` JSON, and `law` IR JSON, scrubbing domain identifiers and comments while preserving language keywords and raising `ValueError` on tampered non-bijective mappings.

## Deliverables

1. `holon/eval/__init__.py` and `holon/eval/rename.py` (plus submodules as needed):
   - `load_corpus_manifest(path=...) -> dict`
   - `verify_corpus(manifest_path=..., sidecar_path=..., root=...) -> dict`
   - `verify_git_provenance(manifest_path=..., cache_dir=..., root=...) -> dict`
   - `load_controls_manifest(controls_dir=...) -> dict`
   - `run_controls_evaluation(controls_dir=..., sidecar_path=...) -> dict`
   - `compute_calibration(records) -> dict`
   - `build_evaluation_report(manifest_path=..., controls_dir=..., sidecar_path=..., root=...) -> dict`
   - `holon.eval.rename`: `rename`, `unrename`, `rename_facts`, `unrename_facts`, `rename_law`, `unrename_law`, `validate_mapping`, and CLI `python3 -m holon.eval.rename`
   - Must contain zero forbidden Morph-specific identifiers (`tests_m2/test_target_agnostic_exhaustive.py`).
2. `spec/eval/corpus_manifest.json` and `spec/eval/excerpts/CORPUS-01/`..`CORPUS-20/`.
3. `spec/eval/controls/controls_manifest.json`, `spec/eval/controls/eval_ctrl_machine.facts.json`, and `spec/eval/controls/laws/L_ctrl_01.json`..`L_ctrl_12.json`.
4. `gen/M4/controls/model/eval_ctrl_machine.bend`, `gen/M4/controls/ground_truth/L_ctrl_01..12/{LAWS,PROOF}.bend`, `results/M4/controls/L_ctrl_01..12.json`, and `results/eval/I48_corpus_controls.json`.

## Disclosures by the drafter and reviewer (before the prereg commit)

- **Upstream git provenance check**: All 20 corpus entries (`CORPUS-01`..`CORPUS-20`) in `spec/M4/lib/corpus_controls.json` were verified against bare clones of `morph-l2/morph`, `OffchainLabs/nitro-contracts`, `ethereum-optimism/optimism`, and `taikoxyz/taiko-mono` in `/tmp/holon-corpus-cache` (`git cat-file -t <fix_commit>`, `git rev-parse <fix_commit>^1`, `git rev-parse <pre_fix_commit>:<file_path>`, `git rev-parse <fix_commit>:<file_path>`, `git diff <pre_fix_commit> <fix_commit> -- <file_path>`, and presence of `excerpt_identifiers` in both blobs).
- **Control machine and obligation check**: Before the preregistration commit, the 12 control obligations (`L_ctrl_01`..`L_ctrl_12`) over `eval_ctrl_machine` were checked in an ephemeral `/tmp` directory against `holon.mpipeline.CompiledMachine`, `holon.gen.mproofs.GENERATORS`, `holon.mpipeline.param_search`, `holon.mpipeline.reach_search`, `explore.mjs` (under budget `{"prefixDepth": 2, "maxPrefixes": 100, "natMax": 5}`), `holon.bend.check`, and `holon.bend.check_verdict`. During review, `CTRL-06` (`L_ctrl_06`) was tightened from `obsv_alert` (which fires at `stage == 2`, reachable at prefix depth 2 within budget `prefixDepth=2`) to `obsv_breach` (which fires at `stage == 3`, requiring prefix depth 3 strictly beyond `prefixDepth=2`), and `tests_m4/_i48.py::witness_exceeds_budget` was tightened so claim-internal `step` terms cannot substitute for prefix depth.

## Verification

1. `python3 tools/freeze.py check`
2. `python3 -m unittest discover -s tests_m4 -t . -v`
3. `python3 -m holon.audit.prereg --milestone M4 --iteration I48`
4. `python3 -m unittest discover -s tests -t . -v`
5. `python3 -m unittest discover -s tests_m2 -t . -v`
6. `python3 -m unittest discover -s tests_m3 -t . -v`

## Hard rules for I48

- Do not touch any file in `FROZEN.sha256`.
- Do not touch `spec/heldout/target.json` (`unsealed` must remain `false`).
- Do not modify `spec/M4/predictions.json`, `spec/M4/lib/corpus_controls.json`, `prompts/I48_corpus_controls.md`, or `tests_m4/*` in the deliverable commit `D_K`.
- Do not introduce any Morph-specific identifiers into `holon/`.
