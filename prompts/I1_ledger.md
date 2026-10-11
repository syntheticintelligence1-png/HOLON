# I1: prereg tool, honest ledger, v2 records, G1 over records, G6/G9

Rendered from `docs/BUILD_PLAN.md` §4, I1. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

## Why

M0 and M1 left integrity debts (BUILD_PLAN §1.1):
- **D-e(1).** Every M1 record carries a hard-coded `CF(keccak256, headers)` premise, including the Go OWN law, which has no hash at all.
- **D-e(3).** The model assumptions of the facts (A-width, A-cache, the oracle stand-ins, the window/shadow representation, ...) appear in no record.
- **D-a, mechanical half.** No tool checks that predictions were committed before their outcomes.
- G1 does not cover records. G6 and G9 do not exist.

## What to build

1. **Prereg commit first.** It contains only:
   - the `I1` key of `spec/M2/predictions.json`;
   - `spec/ledger/assumptions.json`;
   - `spec/schemas/predictions.schema.json`;
   - the red acceptance tests in `tests_m2/`;
   - this prompt.

   Push it before implementing.
2. **`holon/records.py`.**
   - Compute a law's cone: the generated model definitions its frozen statement reaches, starting from the `M.<name>` references of the emitted statement and closing over definition references.
   - Join the cone with the ledger to get `model_assumptions`.
   - Build the v2 fields: `model_sha256`, `generator_sha256`, `cone`, `model_assumptions`, `scope_v2`, `kernels`, `independence_class`, and pending values for `refinement_refs`, `coverage`, `non_vacuity`, `witness_provenance` and `filter_bin`.
   - An unknown facts bundle is an error.
3. **`holon/ir.py`.** `premises()` renders holon-ir/0.2 terms. M0 output stays byte-identical.
4. **`holon/mpipeline.py`.** Delete the CF append. Premises come from `ir.premises`.
5. **Schemas.** `spec/schemas/result_record_v2.schema.json` and `spec/schemas/law_ir_0_2.schema.json`. The 0.2 schema is written from the emitter grammar.
6. **Gate.**
   - **G1** also compares every `results/<m>/L_*.json`, after stripping `seconds` and normalising artifact paths. Regeneration uses a fresh build directory (`HOLON_BUILD_DIR`).
   - **G6**: every REFUTED record has a passed replay; its witness sha256 matches the report; the report's morph commit is the facts' target commit; a `not_applicable` side must be labelled `model-only pending replay`.
   - **G9**: every record validates against the frozen v1 schema and against v2.
   - `--checks` runs a subset, for tamper tests.
7. **Replay labels.** Label the two never-replayed M0 Solidity sides `model-only pending replay`. I4 replays them.
8. **`holon/audit/prereg.py`** and `python -m holon audit prereg --milestone M2 [--root R]`. It checks, from git history:
   - the order of prereg and outcome commits;
   - that each key is immutable after its prereg commit;
   - that every test function present at the prereg commit is unchanged, unless an entry in `spec/M2/amendments.jsonl` covers it.

## Rules

- Never edit frozen files or `spec/M1/facts/`.
- Never edit `predictions.json` keys after the prereg commit.
- A missed prediction is a Surprise, not a fix.
