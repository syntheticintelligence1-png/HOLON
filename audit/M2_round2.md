# Audit round 2, M2: A2 and A4 on the extraction (I21)

**Label.** Same family: the auditor is a fresh session of the same model family as the builders (Q9 is unanswered), so this round is labelled `same` and does not count toward convergence. Its findings still block (Q9).

**Target.** The project branch at `8d9f02da4648d2150b4994261ced05aa6da72c8e` ("Gates M0, M1 and M2 pass on the merged I20 tree"), which holds I20's outputs. The pinned target code is `/root/work/morph` at `3e44e795586af3e11285b603ab642c67823add51`, never written. Real mainnet inputs come from I59's snapshot (`~/.holon/historical`, every object checked against its sha256 in `results/M2/historical/index.json`).

**Instruments.** Two new modules, plus harness sources under `audit/rounds/M2/round2/harness/`:
- `python -m holon audit hostile` (`holon/audit/hostile.py`): auditor A2, hostile input at every interface carrier through public entry points. Output: `audit/rounds/M2/round2/a2.json`.
- `python -m holon audit vacuity` (`holon/audit/vacuity.py`): auditor A4, premise satisfiability, representative inhabitants, and hypotheses tested against real oracles. Output: `audit/rounds/M2/round2/a4.json`.

Both rebuild their record from a fresh `git archive` of the target commit, so nothing in the working tree can leak into the audit. Both are deterministic: `--check` rebuilds byte for byte. Both are target-agnostic: names come from the frozen sidecar `spec/M2/lib/audit_round2.json`, the extracted documents, the compiled artifacts and the harnesses; `tests_m2/test_target_agnostic_exhaustive.py` passes over them. `tests/reference/` is never read.

Machine-readable files:
- `audit/rounds/M2/round2.json`: the round;
- `audit/rounds/M2/round2/a2.json` and `a4.json`: the evidence;
- `audit/M2_findings.jsonl`: F-M2-38 to F-M2-42, and the update of F-M2-36.

## What was tried, attack by attack

**A1, sol_loader (model_vs_code).** The 2561-input header corpus was run against each of the 9 non-dominated `Rollup._loadBatchHeader` call sites, each reached through its public function:
- the sites are `:230 importGenesisBatch`, `:259 commitBatch`, `:277 commitState`, `:402` and `:414 commitBatchWithProof`, `:433 revertBatch`, `:600 proveState`, `:627 finalizeBatch` and `:716 proveCommittedBatchState`;
- each call starts from a state where every check before the call site passes. The Solidity harness builds four states: bare deployment, after genesis, after the delay and with a stored blob hash. Each item runs from a snapshot of its state.

That is 23049 calls. Each was compared with:
- the path of the extracted `load_sol` that its bytes select;
- the frozen `ok_sol`, evaluated on the compiled M0 model.

Results:
- 0 mismatches. All 6 paths are exercised. The observed reverts are exactly the 4 extracted reasons.
- All 27 malformed ABI encodings (3 kinds at each site) revert with empty data.
- `:309` is recorded as dominated by `:259`, `:277` and `:402`.
- No finding.

**A2, sol_encoder (model_vs_code).** The 1024 encoder inputs (versions 0..255, each with 4 root patterns) went through `commitBatch`, `commitState` and `commitBatchWithProof`, plus 9 malformed encodings.
- **Extracted `enc_sol`:** it predicts every outcome. 0 mismatches, all 5 paths exercised.
- **Frozen `enc_sol`:** it agrees on versions 3..255, where the UNDEF sentinel stands for "the code reverts". It disagrees on the 27 inputs with version 0..2 and a zero state root: there the frozen encoder builds a header, and the code reverts with "previous state root is zero" (`:294`) or "new state root is zero" (`:295`).
- **Diagram labels:** only one CODEC edge carries a partiality label that the code contradicts. `CODEC.enc_sol` is labelled total, but the code rejects inputs of its carrier. `dec_go` (partial) and `enc_go_v0`/`enc_go_v1` (total) agree with the code.

This reproduces F-M2-36 with numbers. **Finding F-M2-38** (medium): the frozen domain misses the zero-root rejections, and the edge is mislabelled. The fix needs the human's answer to I11 Q1 and a re-freeze.

**A3, go_header (model_vs_code).** The header corpus went through the 31 exported `BatchHeaderBytes` methods, called by name: 16 in `morph-l2/common/batch` and 15 in `morph-l2/node/types`. That is 79391 calls. `validate` was reached through an in-package harness. Each call was compared with:
- its extracted path: whether the error is nil and, on a nil error, the decoder's reads;
- the frozen `ok_go` and `dec_go`.

Results:
- 0 mismatches and 0 panics.
- 222 of the 223 extracted paths are exercised. The remaining one is infeasible: `(BatchHeaderBytes).BlobCommitHash` path 8 requires `b[0] < 2 ∧ b[0] ≠ 0 ∧ b[0] ≠ 1`. The Go frontend's interval reasoner never gives a byte-typed term its 0..255 range, so it cannot refute that path.
- **Finding F-M2-39** (low). The preregistered R3 count (223 paths exercised) is a MISS for this reason.

**A4, go_encoders (model_vs_code).** Inputs: `(BatchHeaderV0).Bytes` and `(BatchHeaderV1).Bytes` on 34 structs, built by varying one field at a time from the zero struct.

Results:
- Against the extracted encoder paths and layouts, and the frozen `enc_go_v0` and `enc_go_v1`: 0 mismatches.
- All 4 paths are exercised.
- No finding.

**A5, rollup_act (model_vs_code).** I20's refinement harness ran 1240 hostile calls across the 33 actions that the extracted model compiles.
- **Inputs.** One ABI leaf was varied at a time over the sidecar's values (uint, bytes32, bool, and the 51-input act-header corpus for header arguments). The caller was varied (one that satisfies the principal predicate, one that fails it, and address 0), and msg.value was 0 or 1.
- **Where calls start.** Calls fork both at a corpus state where the base call succeeds and after genesis. The 8 modelled actions have succeeding corpus bases.
- **Comparison.** Status, revert data, storage and events: 0 disagreements.
- **One panic.** Panic 0x11 in `revertBatch` (`Rollup.sol:439`, `idx + count` overflow) is a check the document records, and the model gives the same revert.
- **Gap.** For 13 non-modelled actions, no candidate base call succeeds: initializers, `claimReward`, `proveCommittedBatchState`, `removeChallenger`, `transferOwnership` and the owner updates. Their hostile calls vary a reverting base. That is weaker coverage, recorded under "Not done" in `docs/iterations/I21.md`.
- No finding.

**A6, batchdata_act (model_vs_code).** Inputs:
- from `NewBatchData`, every sequence of up to 3 `Append` calls: 254080 sequences;
- after each sequence, each of the 10 exported methods;
- each method on a nil receiver.

Results:
- The batch-data model agrees on all 75895 sequences inside its 512-byte bound.
- The open site `common/batch/batch_data.go:75:36:slice` is decided as reachable. Witness: `NewBatchData`, then `Append("0x", "0x", [])`, then `DataHash`, which panics with "slice bounds out of range [:58] with capacity 0".
- The 7 nil-receiver panics are explained by the documents' `go-nil-deref-not-modelled` assumption.
- No panic occurs at a safe site.
- No finding.

**A11, go_consumer (model_vs_code).** The node's derivation was attacked through its two exported entry points, `(*Derivation).UnPackData` and `(*BatchInfo).ParseBatch`. The harness loads the four ABIs as `NewDerivationClient` does. There are two input sets.

*Hostile inputs.* The header corpus, placed inside a well-formed commitBatch calldata under each of the 4 selectors, with one zero blob each: 10244 inputs.

*Real inputs.* The calldata and blobs of all 62172 mainnet commits in I59's snapshot:
- `UnPackData` returns a nil error for every one, by selector: 0x41f756da 1695, 0x428868b5 40247, 0x4a8d544f 12656, 0xd63b3549 7574.
- Every unpacked parent hashes to the parent keccak that I59 recorded.
- `ParseBatch` rejects 2954 commits at its first header step (BatchIndex, `batch_info.go:92:55`): batches 2..7575, whose parents are 281-byte version-0 headers. 2953 of them come under 0xd63b3549, and batch 7575 under 0x4a8d544f. The batch-index digest is `cad2b461…0030`.
- The pinned `Rollup._loadBatchHeader` accepts all 2954 of those parents, through `commitBatch`.
- `ParseBatch` rejects 8 more commits after its header steps: batches 1, 23, 25-28, 271 and 310, each carrying the all-zero blob ("morph da zstd decode: invalid frame").
- No commit fails at the TotalL1MessagePopped step.

Against the extracted BatchIndex/TotalL1MessagePopped paths and the frozen `ok_go`: 0 mismatches. No HOLON finding. These results are target findings, reported below.

**A7, vacuity.** Scope: the 27 records under `results/M2` and `results/M2/extracted_m1`, of which 10 are PROVED and premised.

How each inhabitant was checked:
- It was replayed on the compiled model that its record names, after checking the model's sha256 against the record.
- The premises were evaluated: for a SORT-site law, by Reach (the replayed run) and the model's own `hit_<x>`; for the others, by `explore.mjs`.
- For a site law, the subtraction's operands were evaluated at the inhabitant. The values come from probe definitions that the model's own generator emits from the facts and appends to the compiled model.

Results:
- **Satisfiability.** All 10 laws are satisfiable.
- **Degenerate inhabitants.** Under the degenerate rule, 5 of the 6 PROVED SORT-site laws have degenerate inhabitants. Both `def_bvh_at` laws and `def_w` sit at the initial state. `rollup_441` and `rollup_485_495` have subtrahend `lfi = 0`. `rollup_644_660` is not degenerate.
- **Representatives.** A breadth-first search over runs of at most 6 actions finds a non-degenerate representative for each of the 5. The run lengths are 1, 1, 3, 4 and 4, all with a nonzero subtrahend. None is a vacuity finding.
- **REFUTED laws.** Their counter-witnesses replay with their premises holding.
- No finding.

**A8, bindings_ledger.** All 12 hypotheses were handled through the round's binding (`audit/rounds/M2/round2/harness/hypotheses.json`). Seven were tested against implementations outside `holon/`: the pinned contracts, the Go module graph, or the EVM.
- **CF-agg: pass.** EVM KECCAK256 on the 273-list sample.
- **CF-hdr: pass.** 768 in-domain headers. The codec libraries in Solidity and `BatchHeaderBytes.Hash` in Go agree, and the hashes are pairwise distinct.
- **Hyp-Z0-kzg: pass.** kzg4844 of the pinned Go module graph equals Rollup's `ZERO_VERSIONED_HASH` and Go's `EmptyVersionedHash`.
- **Hyp-messenger: pass.** 90 sendMessage calls on the real messenger and queue. Each of the 36 successes enqueues exactly one message at the previous next index, and each reverted call enqueues none.
- **HypT: pass.** All 180 transactions the codec encodes round-trip.
- **Hyp-ISubmitter: fail.** See F-M2-40.
- **HypZ: fail.** See F-M2-41.

HypC, HypF, HypP, HypSeal and HypV-proof1 are untestable. Each record names the missing piece: no prover or circuits, no L1 endpoints, no L2 chain, no running sequencer, no valid proof.

Findings:
- **F-M2-40** (medium). Against `Submitter.sol`:
  - `updateChallengeDeposit` changes `challengeDeposit()`;
  - `setMinimumStake`, `withdraw` and `removeSubmitter` leave a staked, unslashed submitter inactive.
  The M1 stand-in models none of these.
- **F-M2-41** (medium). HypZ is false at the empty payload. The codec encodes it as nothing, and decoding nothing, or zeros, fails. The 8 zero-blob commits above are mainnet instances.
- **F-M2-42** (low). While testing CF-agg, the auditor found that the model applies `agg` to the whole blob list, while the Rollup stops at the first zero blob hash. The divergence lies only on inputs the chain cannot produce.

**A9, mutation_adequacy.** One planted partiality mutant per surface (scratch copies, never written to the repository):
- sol_loader: the loader's 249-byte constant moved to 250;
- sol_encoder: the version bound 2 moved to 3;
- go_header and go_consumer: BatchIndex's length constant 249 moved to 250;
- go_encoders: the cache-length condition 0 moved to 1;
- batchdata_act: the decided open site marked safe;
- rollup_act: a require that hostile inputs met, negated. This replaces the first planted mutant, which bumped a constant that no hostile input crossed and was not detected. The undetected attempt is reported in `docs/iterations/I21.md`, not hidden.

Every mutant is detected (`a2.json` mutants). All three A4 canaries are detected:
- a contradicting premise added to `L_disch_stale`;
- `L_undo_BD`'s inhabitant moved to the initial state;
- Hyp-Z0-kzg's stated value altered.

**A10, determinism.** `python -m holon audit hostile --check` and `python -m holon audit vacuity --check` each rebuild their record from a fresh archive of the target commit, and each matches the committed file byte for byte.

## Target findings (not HOLON defects; the upstream report is the human's decision)

**T1 (bin `finding`, law `L_dom_hdr`).** 2954 real mainnet commits, for batches 2..7575, carry a 281-byte version-0 parent header.
- **Contract side.** The chain accepted them, and the pinned `Rollup._loadBatchHeader` still accepts them, because `BatchHeaderCodecV0.loadAndValidate` requires only `length >= 249`.
- **Node side.** The pinned node rejects them at its first header step, because Go's `validate` requires exactly 249 bytes.
- **Frozen predicates.** `ok_sol` and `ok_go` agree with the two real sides on every one of these headers, so this realizes `L_dom_hdr` on mainnet data.

The question was whether this path is reachable on mainnet, and what the node does when it is. I read the node at the pinned commit (`audit/rounds/M2/round2/harness/consumer_reachability.json`):
- **What the node does.** It runs `derivationBlock` (`node/derivation/derivation.go:236`), whose two modes both fail on this parent:
  - In local mode (the default, `config.go:43`), `fetchBatchInfoOutline` calls BatchIndex on the parent (`verify_local.go:67`).
  - In layer1 mode, `fetchRollupDataByTxHash` calls `ParseBatch` (`batch_info.go:92`).

  In either mode the error returns from `derivationBlock` (`:315-316` or `:461-462`) before the L1 cursor is written (`:521`). So every later poll fails on the same log, and derivation stops for good at the first such commit.
- **Default configuration: not reached.** With no stored cursor and no `--derivation.startHeight`, the start is pinned on the first run to the latest confirmed L1 block (`:165-176`). The `--mainnet` preset sets only the rollup address (`config.go:142-143`). So a default node never processes these historical commits.
- **When it is reached.** An operator who sets `--derivation.startHeight` (`flags.go:172-176`) at or below the L1 block of any of batches 2..7575 reaches it. A node deriving the chain from L1 since the rollup's deployment would do this. Such a node stops at the first of these commits in local mode.
- **Layer1 mode.** A layer1-mode node whose range includes batch 1 stops even earlier, at T2.

I did not run a node (no L1 endpoint here). The schedule is the public commits that are on chain, followed by the node's own entry points on their real calldata and blobs.

**T2 (bin `finding`, no law).** 8 real mainnet commits (batches 1, 23, 25, 26, 27, 28, 271 and 310) pass `ParseBatch`'s header steps. `zstd.DecompressBatchBytes` then fails on the all-zero blob (`batch_info.go:122-124`). Layer1 mode stops there; local mode does not decode blobs. These are F-M2-41's instances.

**T3 (bin `known_limitation`, law `L_dom_hdr`).** 6 hostile headers pass every Solidity call site and fail the Go decoders. No public entry point commits such a header with the pinned code. T1 is the mainnet form of the same difference.

## Findings filed (audit/M2_findings.jsonl)

| id | severity | category | title | fix |
|---|---|---|---|---|
| F-M2-38 | medium | model_vs_code | Frozen enc_sol is defined on zero roots the code rejects; CODEC.enc_sol mislabelled total | human (I11 Q1, re-freeze), I24 |
| F-M2-39 | low | model_vs_code | Go frontend keeps an infeasible path (BlobCommitHash path 8) | Go frontend reasoner, I38 |
| F-M2-40 | medium | bindings_ledger | Hyp-ISubmitter fails against Submitter.sol | oracle stand-in and ledger, I36 |
| F-M2-41 | medium | bindings_ledger | HypZ false at the empty payload; 8 mainnet commits are its instances | hypothesis statement, I38 |
| F-M2-42 | low | model_vs_code | agg over the whole blob list vs the Rollup's prefix before the first zero hash | facts, I36 |

F-M2-36 is resolved by this round: it is reproduced, and its status is now `duplicate`, continued as F-M2-38. No finding is high, and `python -m holon audit status --findings audit/M2_findings.jsonl` reports nothing blocking.

## Limits of this round

- The rollup corpus varies one parameter at a time around a single base call per action. Interactions between two hostile parameters are not covered, and neither are the 13 actions without a succeeding base.
- The consumer surface compares only `ParseBatch`'s header step. Its later steps are recorded (`error:other`) but not compared with a model; there is none yet (I38, I39).
- The reachability argument for T1 and T2 rests on reading the node's code, not on running a node against L1.
- A4 evaluates hypotheses on finite samples. A pass is a test, not a proof. A fail carries a concrete counterexample.
