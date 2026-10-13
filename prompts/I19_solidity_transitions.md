# I19: Solidity frontend II: storage, transitions, cost terms, principals, linking, G8

Rendered from `docs/BUILD_PLAN.md` §4 I19 (whitepaper §10.1 Solidity and linking, §7.7 step 5, §9.3 G8, L1 coverage). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact CLI, document formats and rules are in the docstrings of `tests_m2/test_extract_transitions.py` and `tests_m2/test_coverage.py`. I19 extends I17's frontend; its walker rules W1–W10 are in the docstring of `tests_m2/test_extract_solidity_layout.py`.

## Goal

Extract the rollup contract's state machine from the compiler's view: storage families with widths and slots, every external and public function's ordered guards with reasons, effects, loop bounds as cost terms, modifiers as principal predicates, and hash and commit edges. Link Solidity to Go. Account for every statement (coverage, G8). This replaces the hand-written M1 rollup facts with extracted ones; I20 compiles them.

## Deliverables

- **`holon/frontends/solidity/{storage, transitions}.py`.** They are driven by a sidecar with `"transitions"` (`spec/M2/lib/extract_rollup.json`).
  - Storage comes from solc's `storageLayout` output, never from counting.
  - Guards, effects, cost terms, principals and edges come from I17's AST walk, with modifiers, internal calls and library calls inlined.
- **`spec/M2/facts/morph_rollup.extracted.json`.** It is canonical, byte-identical across runs, and covered by G1, which re-extracts every extraction sidecar.
- **`spec/schemas/facts_0_3.schema.json`** gains the transitions branch.
- **`holon/coverage.py`, `python -m holon coverage`, and `gen/M2/coverage.json`.** The gate check **G8** applies to M2+; M0 and M1 list it under `not_applicable`.
- **`holon/frontends/link.py`, `python -m holon link`, and `gen/M2/link.json`,** with the roles from `spec/M2/lib/link.json`.
- **Records v2 gain `coverage`.** The `pending:I19` value is removed, logged as a pending-field amendment. The I6 `norm_record` pin is narrowed the same way as for I14 and I16.
- **`docs/iterations/I19.md`,** with a prediction table, pass or miss for each id.

## Predictions (key I19)

These were made by reading `Rollup.sol` and `IRollup.sol` at `3e44e79` and the M1 facts. Nothing was extracted before the prereg.

| id | claim |
|---|---|
| P1 | The extracted storage families are exactly Rollup's 24 own declarations, in order. Names, kinds, value types, widths and struct fields are as listed in the test. They sit at slots 151–174 (the range BUILD_PLAN states). |
| P2 | Every M1 `require` of the 8 modelled actions whose span lies in the extraction's closure matches an extracted guard of the same action by span, in the same relative order. The only unmatched M1 guards are the 2 `oracle:` verifier rules and the 4 inside `L1MessageQueueWithGasPriceOracle.sol`, which code on the far side of external calls holds. |
| P3 | The guards that the M1 facts annotate as committedBatches abstractions (`:311` in the three commits, `:436` in revertBatch) are extracted as reads of the `committedBatches` family. |
| P4 | The principal predicates are: `onlyOwner` (revertBatch, setPause); `onlyActiveSubmitter` = `ISubmitter.isActive(caller)` (the three commits' submitters and proveState); `onlyChallenger` = `isChallenger[caller]` (challengeState). finalizeBatch and commitBatchWithProof have none. |
| P5 | Cost terms. Each of the three commits has exactly one, the L1-message-hash loop at `:936`, which iterates `numL1Messages` times. finalizeBatch has exactly one, the loop at `:744`. |
| P6 | Edges. commitBatch has a `blobhash` COMMIT edge and a HASH edge at the header hash (`BatchHeaderCodecV0.sol:242`). commitState has a `blobhash` COMMIT edge. proveState and commitBatchWithProof have an `IRollupVerifier.verifyAggregateProof` COMMIT edge. |
| P7 | Coverage: no statement is unaccounted for. |
| P8 | Debt: the storage-writing loops at `:444` (revertBatch) and `:489` (challengeState), the submitter call at `:120`, and the value transfer at `:816`. |

**Regressions and construction checks.**
- **R1.** The header length per version and the zero versioned hash agree across Solidity and Go. The values are already recorded in the I17 and I18 documents.
- **R2.** Gates M0, M1 and M2 pass. G8 passes on M2.
- **R3.** The extraction and the coverage report are byte-identical across runs and match the committed files.
- **R4.** The planted toy extracts exactly as constructed.
- **R5.** M0, M1 and M2 statements and statuses are unchanged.

## Rules

- **AGENTS.md is binding.** Never edit `facts/` or `spec/M1/facts/`. A difference from the M1 facts is reported, never fixed.
- **Target vocabulary** appears only in the sidecars. `holon/frontends/solidity/*.py` names no Morph identifier, which the exhaustive grep checks.
- **No tuning.** A predicted outcome that does not come out is a Surprise. No skips.
