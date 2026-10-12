# I16: native C model, per-edge corpus, refinement records, metrics

Rendered from `docs/BUILD_PLAN.md` §4, I16. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. Milestone M2, the corpus half of M2 exit (a). Goal: per-edge replay at volume, with every disagreement classified by a mechanical criterion (whitepaper §8.7 sources 1–3, Def 4.7 ρ(e), §8.6, §13).

The acceptance tests are `tests_m2/test_native.py`, `tests_m2/test_refinement.py` and `tests_m2/test_metrics.py`. Their docstrings are the contract: file formats, CLI and API. `tests_m2/_i16.py` and `tests_m2/fixtures/refinement/` are instruments fixed at the prereg. Do not edit them; if one is wrong, it is a Question and an amendment.

## What to build

- **Probe first: `bend/notes/c_probe/`.**
  - `probe.bend`: a small program with a `main` and no escape hatch. Do not use `!`: clang 18 cannot build it.
  - `RESULT.json`: the exit codes of `bend probe.bend -o probe.c` and `bend probe.bend -o probe`, plus the binary's exit code and stdout.
  - The test re-runs all three.
- **`holon/gen/cdriver.py`.** `generate(facts_path) -> {file name: text}` gives the M0 model a `main` that evaluates IR jobs.
  - It is deterministic.
  - The `.bend` files it writes hold no escape hatch. In particular there is no foreign `import "./x.c"`. Base already has `IO.args` and `File.*`.
  - Native build products go under `holon.bend.build_dir()`, never under `gen/M0`. `gen/M0` and `gen/M1` stay byte-identical (G1, the I6 `GEN_PIN`).
- **`holon/model_native.py`.**
  - `NativeModel.build(facts_path)` and `NativeModel.run_jobs(jobs)` follow the same contract and value encoding as `holon.model_eval.CompiledModel.run_jobs`.
  - `NativeModel.binary` is the ELF executable it runs and `NativeModel.c_source` the C source bend emitted for it, both under `holon.bend.build_dir()`. `run_jobs` executes only that binary: the agreement test runs it with `PATH` empty. The C source's sha256 is `native.json`'s `c_source_sha256`.
  - `NativeBuildError` carries the captured compiler output, with the build directory replaced by `<build>`.
  - Write `results/M2/native.json` with one of two statuses:
    - `native`, with agreement counts over every candidate `holon.refute.candidates` yields for every M0 law;
    - `fallback`, with the captured error.
- **`holon/corpus.py`.** It holds `SEED`, `GRAMMAR_SAMPLES = 2000` and `corpus(edge)`, which builds three kinds of item:
  - seeded grammar samples of the edge's input sort;
  - the sort-boundary values of whitepaper §8.7 (0, 1, max, max − 1 and every sentinel constant);
  - every REFUTED M0 witness of the sort.

  The edges are the four CODEC edges of the I11 M0 diagram (`enc_sol`, `enc_go_v0`, `enc_go_v1`, `dec_go`) and the decoder domains (`ok_go`, `ok_sol`). Encoder corpora stay inside the edge's domain; for `enc_sol` that means version ≤ 2.
- **Harnesses.** Their dependencies stay outside the repo: no `node_modules`, `lib/`, `vendor/` or `go.sum` under `replay/M2/`.
  - `replay/M2/go/holon_codec_test.go`, in `package batch`, is copied into a scratch copy of morph `common/batch`, as `holon/replay.py::replay_go` does. It calls `BatchHeaderV0/V1{..}.Bytes()`, `validate()` and the getters (`BlobCommitHash` for the blob field).
  - `replay/M2/solidity/HolonCodec.t.sol` runs in a scratch Foundry project, as `replay_solidity` does, with deps from `config replay.sol_deps`.
    - `enc_sol` runs through the `BatchHeaderCodecV0` store functions and `BatchHeaderCodecV1.storeLastBlockNumber`, in the order of the header build block of `_commitBatchWithBatchData`.
    - `ok_sol` runs through `_loadBatchHeader`, via a harness that inherits `Rollup`.
  - Reuse `holon.replay.toolchain()` and `check_checkout()`. A record carries the pins and the full morph commit.
  - The real outputs are re-measured by two instruments fixed at the prereg: `tests_m2/fixtures/refinement/holon_prereg_instrument.go.txt` (the four Go edges) and `tests_m2/fixtures/refinement/HolonPreregInstrument.t.sol.txt` (`enc_sol`, `ok_sol`). Your harnesses are independent of them; do not copy them.
- **`holon/refinement.py` and `python -m holon refine --milestone M0 [--edges ..] [--out DIR] [--morph PATH] [--work DIR] [--fix COMMIT ..]`.**
  - It writes `results/M2/refinement/<edge>.json`, comparing each model edge **with its own implementation**:
    - `enc_sol` with the Solidity store;
    - `enc_go_v0` and `enc_go_v1` with Go's `Bytes()`;
    - `dec_go` with Go's decode;
    - `ok_go` with `validate()`;
    - `ok_sol` with `_loadBatchHeader`.
  - The model side runs on the native model, or on `.mjs` after a recorded fallback.
  - Records hold counts by source, an inputs digest, model and real output digests, domain counts, the `--fix` commits (`fixes`) and the pins. Records are byte-identical across runs and do not depend on `--edges`, `--out`, `--work` or `--morph`: the record's `command` is the real side's harness invocation, with no absolute path.
  - It writes `results/M2/cross_edge.json`: PAR differences between edges, over corpus(a) then corpus(b) restricted to both domains, grouped by (pair, first M0 law whose claim compares the pair and whose premises the input satisfies). They are never counted as refinement disagreements.
  - It appends new disagreements to `spec/M2/disagreements.json` as `unexplained`, with no links, under ids that are a deterministic function of (edge, input). The file is committed even when its list is empty.
- **Mechanical classes.** `classify(entry, root)` decides from the links only; the label is never read. `check_disagreements(root)` lists the problems.
  - `extraction_defect`: a 40-hex `fix_commit`, plus a `rerun` record under `results/M2/refinement/` for the same edge, with 0 disagreements, whose `fixes` lists that commit.
  - `real_defect`: `law: "<M>/<law_id>"`. The record must be REFUTED with replay passed, have the edge in its cone, have a witness hash equal to the report's, and every report side must have `obstruction_observed`.
  - `oracle_mismatch`: `hypothesis: id`, whose record in `results/M2/hypotheses.json` has status `failed`.
  - Anything else is `unexplained`: `links` must hold exactly the keys of one kind (`{fix_commit, rerun}`, `{law}` or `{hypothesis}`).
  - `tests_m2/_i16.py::expected_class` writes these rules out; `classify` must agree with it on every entry.
  - New gate check **GREF** in `CHECK_ORDER`, for every milestone. It passes iff `check_disagreements(root) == []`, and it reads no git. Checking that a fix commit exists is left to `holon audit`.
- **Records gain `refinement_refs`; `pending:I16` is removed** from `holon/records.py` and from `spec/schemas/result_record_v2.schema.json`.
  - M0 records: the per-edge records of the refined edges in the cone.
  - M1 records: `replay/M1/report.json#/refinement/per_action/<a>` for each corpus action `a` with `step_<a>` in the cone.
  - Two amendments follow, logged in `spec/M2/amendments.jsonl` (precedent: the I3, I4 and I9 lines) and reported under Surprises:
    - `tests_m2/test_records_v2.py::TestRecordsV2.test_pending_fields_name_their_iteration` asserts `refinement_refs == "pending:I16"`; remove that assertion only.
    - The I6 records pin (`tests_m2/test_target_agnostic.py::norm_record`, `RECORDS_PIN`) sees `refinement_refs` change. Narrow `norm_record` to drop `refinement_refs`, as I9 did for `lean4`, and keep the pin.
- **`holon/metrics.py` and `python -m holon metrics --milestone M [--root DIR]`.**
  - It writes a deterministic `results/<M>/metrics.json` for M0 and M1. It covers the laws, `unknown_rate`, `witness_replay_rate`, `canary_acceptance` and `refinement {compared, disagreements, unexplained}` with the rate. Every other §13 metric (including `unknown_calibration`) is either a key or under `not_applicable`, with a reason.
  - Timings go to `results/<M>/metrics_timing.json`, including `from_scratch_gate_s` (the gate records its wall time). Add that file to `G1_EXCLUDED`.
  - G1 regenerates and compares `metrics.json`.

## Rules

- **Witnesses and model outputs come from the compiled model** (native or `.mjs`). Never import `tests/reference/` from `holon/`.
- **Every edge is faithful.** There is no flag that excludes an edge from the counts.
- **The fixed inputs never move:** the corpus size (2,000), the boundary rule and the classes.
  - A disagreement is a result. It is recorded, classified by its links and reported, never relabelled.
  - O1 and O2 belong to `cross_edge.json`, not to the refinement counts.
- **If C compilation fails, use the fallback.** Keep `.mjs`, write `native.json` with status `fallback` and the captured compiler error, produce every per-edge record on `.mjs`, and report a Surprise. `test_native_agrees_with_mjs_on_every_refuter_candidate` then stays red: report it.
- **Determinism:** fixed seeds, sorted iteration, no timestamps outside `metrics_timing.json`.
- **No tools in the repo.** No tool installs, `node_modules`, `bunfig.toml` or `.env` in the repo. Tools go under `~/.holon/tools`.
- **Before committing,** run every suite, `holon gate` for M0 and M1, `tools/freeze.py check` and `holon audit prereg`.
