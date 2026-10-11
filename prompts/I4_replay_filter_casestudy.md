# I4: replay completion, provisional finding filter, case-study coverage

Rendered from `docs/BUILD_PLAN.md` §4, I4 (debts D-b and D-f; strict G6). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

## Why

- **D-b.** The Solidity side of the M0 `L_par_hdr_v2` and `L_par_hdr_ssvh` witnesses was never replayed. `replay/M0/report.json` says `not_applicable`, "model-only pending replay".
- **D-f.** `L_tag_BVH`'s M1 replay shows only that the real Rollup accepts the trace: "invisible on chain by design". The ghost-tag obstruction itself (a v1 versioned hash where a v2 consumer expects an aggregate) was never observed. `L_fact_Z`'s consumer side (derivation) was never replayed.
- **No filter.** A replayed witness is a reproducible hypothesis, not yet a finding. Nothing records how a replay ran (public schedule, internal harness, emulated storage, library call) or which bin it lands in (whitepaper §9.6, §10.9).
- **Coverage by hand.** The O/D/F coverage of §11 is a hand count in `docs/BUILD_PLAN.md` §1.

## What to build

1. **Prereg commit first.** It contains:
   - the `I4` key of `spec/M2/predictions.json`;
   - the red tests `tests_m2/test_replay_completion.py`, `test_filter.py` and `test_casestudy.py`, with helpers `tests_m2/_i4.py` (the bin rule) and `tests_m2/_keccak.py` (an independent Keccak-256);
   - the sidecar `spec/ledger/maps_to.json`;
   - the I1 test amendment (`witness_provenance` and `filter_bin` are no longer pending), logged in `spec/M2/amendments.jsonl`;
   - this prompt.
2. **M0 commit-path replays** (`holon replay --milestone M0`).
   - Linearise each witness's pinned version into a one-step trace from `s0`, run through the M1 Foundry harness `replay/M1/solidity/HolonTraceReplay.t.sol`, which deploys the real Rollup at the pinned commit:
     - `L_par_hdr_v2`: `commitBatch` at version 2, with one blob;
     - `L_par_hdr_ssvh`: `commitBatch` at version 1.
   - The harness logs the committed header bytes and `committedBatches(i)`. The side records `trace`, `header`, `batch_index` and `committed_hash`. It asserts byte 0 (v2), the ssvh cells 185..216 (ssvh), and `keccak256(header) == committedBatches(i)`.
   - M0 report entries keep holding sides only, because the frozen `tests/test_50_replay.py` reads every value as a side.
3. **`L_tag_BVH`.**
   - The Solidity side logs the version-2 header that `commitState` committed (`header`, `committed_hash`) and the stored versioned hash (`stored_vh`). It observes `header[57:89] == stored_vh`.
   - A Go consumer side (`go_consumer`, a test in `common/batch`) reads that header (`input_header`). It records `BlobCommitHash()` (`blob_commit_hash`) and `aggregateBlobHashes([stored_vh])` (`aggregate`). It observes that the two differ.
4. **`L_fact_Z`.**
   - The Solidity side records both commits' `committed_hash` (`{"c1", "c2"}`) and the `parent_header`.
   - A Go consumer side (`go_consumer`, a test in `node/derivation`) runs `BatchInfo.ParseBatch` on the two batches. They have the same parent header (`input_parent_header`) and sidecars of 0 and 1 blobs (`sidecar_blobs`); the blob is all zero. It records both `outcomes` and observes that they differ.
5. **Every side** carries `status`, `command`, `observed`, `obstruction_observed` (a bool set by the harness from the real code's output; false unless the side passed) and `provenance`.
   - M1 entries keep their law-level verdict (`status`, `obstruction_reproduced`, `observed`, `traces`) and gain `sides`.
   - Two-sided trace replays store each trace's `split`.
   - The law-level verdict is the conjunction of the sides.
6. **`holon/filter.py` (provisional).**
   - `bin_of(sides)` must agree with `tests_m2/_i4.py::expected_bin` on every input:
     - `model_defect` if some side failed;
     - `finding` if every side passed and observed the obstruction, at least one side is `public_schedule`, and no side is `internal_harness` or `emulated_storage`;
     - `pending` otherwise.
   - Records get `witness_provenance` (side → provenance) and `filter_bin` for REFUTED laws, and null for the others. `known_limitation` is not assigned before I40.
   - Bins are about reproducibility. v1 `triage` (intent) is untouched.
7. **Toolchain pins.** `config/holon.json: replay.{forge, forge_sha256, solc, solc_sha256, morph, sol_deps, sol_deps_sha256}`. Both reports record `toolchain` with the three hashes.
8. **Strict G6.** On top of I1's checks, G6 requires:
   - every claimed side present, with the I4 fields well-typed and `provenance` in the enum;
   - record `witness_provenance` and `filter_bin` equal to the filter recomputed from the report;
   - the report's toolchain hashes equal to the config pins.

   G6 must not read git or run tools: the frozen gate test runs it on a copy without `.git`.
9. **`tools/casestudy.py`** writes `results/casestudy_coverage.json` and `docs/CASESTUDY.md`. The coverage rule is in `tests_m2/test_casestudy.py`'s docstring. Counts are derived data, not predictions.

## Deviation from the plan, stated before results

The plan's prediction line puts `L_tag_BVH` and `L_fact_Z` in `pending`. This prereg predicts `finding` for both, if their consumer sides observe the obstruction. A library-level consumer side fed by bytes from a public-schedule chain replay does not block a finding. A law whose only side is a library call (`L_own_txspayload`) stays `pending`. The plan's rule text ("provenance is `public_schedule` from a deployed reachable state") is ambiguous for laws with several sides. The rule in `tests_m2/_i4.py` resolves that ambiguity, and it is fixed here before any of these replays has run.

## Honest limits

- **The harness is written after this prereg.** It is the measurement device. The tests recompute what they can from the bytes it logs: keccak256 over the header against `committedBatches`, byte 0, the ssvh cells, the blob field, and the aggregate. They cannot detect a harness that logs fabricated chain reads.
- **The provenance table is a construction check.** It describes how each side runs, and the replay code is written after this prereg. So I4-P6 and the bins of the already-replayed laws (I4-P7) do not count toward prediction accuracy.
- **M0 Go sides are not yet fed chain bytes.** They run on the witness header, as before.

## Rules

- Never edit frozen files or `spec/M1/facts/`.
- Statements and statuses do not change.
- A consumer side that cannot run stays `model-only pending replay`, its bin stays `pending`, and the prediction is reported as missed. It is never relabelled.
- A replay that fails is a model defect and is reported loudly.
