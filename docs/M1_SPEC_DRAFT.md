# M1 spec (draft, not frozen)

Scope (README "After M0"): the rollup state-machine slice. Rules UNDO, DISCH and NAT on commit / revert / challenge / prove / finalize / pause in `Rollup.sol` at Morph `3e44e79`, plus the composed producers that M0 flagged. It reuses the M0 factory: frozen facts, generated Bend model, frozen laws with statement hashes, kernel-checked proof or counter-law (`--verdict`), gate with canaries, and replay on real code.

The whitepaper (§15.2, F2/F4/F7/N1) is not in the starter kit, so the law list below is derived from the code. Mapping to F-numbers is left to Omar.

## 1. Freeze discipline

`tools/freeze.py` treats any new file under `facts/`, `predictions/`, `schemas/` or `tests/` as drift, and `freeze.py write` is human-only. M1's frozen inputs are therefore staged under `proposals/M1/` (facts, laws, registry, predictions, IR 0.2 schema, acceptance tests). The predictions are committed before the first pipeline run (preregistration). Omar moves the staged files into place and runs `freeze.py write`. Until then the pipeline reads from `proposals/M1/`, and the gate checks the staged registry.

## 2. Model (generated from `proposals/M1/facts/rollup_sm.json`)

The model is a bounded abstract state machine: batch indices 0..N (N=3 by default, with genesis 0 finalized), a discrete clock, hashes as small tokens, and roots as small Nats with 0 meaning "zero".

State: `lastCommitted`, `lastFinalized`, per-index `{committed, stateRoot, blobHash, origin, finalizeTs, chal{challenger, finished, success, start, deposit}, finalizedRoot}`, `inChallenge`, `batchChallenged`, `revertReqIndex`, `paused`, queue `{len, pending, enqueueTime[]}`, `now`.

Actions are each guard-for-guard from the cited lines, and a failed guard = revert = state unchanged plus a revert tag:
`commitBatch(numL1)`, `commitState(numL1)`, `commitBatchWithProof(numL1, proofOk)`, `revertBatch(i, count)`, `challengeState(i)`, `proveState(i, proofOk)`, `finalizeBatch(i)`, `setPause(b)`, `enqueue`, `tick(d)`.
The checked arithmetic in `proveRemainingTime` (Rollup.sol:362) is modelled as a revert on underflow.

Each action is one generated Bend function `State -> Outcome`, where Outcome = `Ok{State} | Revert{Tag}`. The facts carry every guard as data (field, op, operand, source line), so the generator emits it mechanically. No Python reimplements the model, and the trusted reference oracle (Python, under `proposals/M1/tests/reference`) is used only by tests.

## 3. Proof shape

Laws quantify over traces of length ≤ K from the initial state, at bound N. PROVED means a Bend proof by reflection over the bounded domain: `{check_all(K) == true}` by `{==}`, with the bound recorded in the result record (`"bound": {"N":3,"K":…}`). It is not a claim for unbounded N. REFUTED means a counter-law `exs t: Trace` with the concrete trace, kernel-checked. UNKNOWN covers checker failure, timeout, or a bound beyond P0's scale limits.

## 4. Laws and preregistered predictions

| Law | Rule | Claim | Predicted | Why (code) |
|---|---|---|---|---|
| L_undo_commit_revert | UNDO | commit then revertBatch(new,1) returns the storage state | REFUTED, intent_question | revertBatch 430-468 leaves batchBlobVersionedHashes[i], batchDataStore[i] and committedStateRoots[i] |
| L_undo_enabled | UNDO | after commit∘revert, commitBatch (fresh blob) is enabled iff it was before | REFUTED, intent_question | commitBatch 261 requires no stored blob hash. Only commitState / commitBatchWithProof can recommit |
| L_undo_pause | UNDO | setPause(true)∘setPause(false) leaves finalizeTs and challengeability unchanged | REFUTED | setPause 573-587 deletes the challenge but keeps the +proofWindow extensions (challengeState 489-493), so the same batch can be re-challenged and extended again |
| L_disch_nonowner | DISCH | every started challenge can be discharged (the batch finalized or the challenge closed with the pipeline live) by non-owner actions | REFUTED, intent_question | _challengerWin sets revertReqIndex, and nonReqRevert blocks every non-owner path. Only revertBatch (owner) clears it |
| L_disch_timeout | DISCH | after the proof window expires, a party other than the submitter can close the challenge | REFUTED, finding candidate | proveState is onlyActiveSubmitter. Commits revert on proveRemainingTime underflow (362), so the chain stalls until the submitter proves its own loss |
| L_nat_delay_frontier | NAT | if every enqueued message is included in a committed batch, the delay guard does not force numL1Messages > 0 | REFUTED, intent_question (delay, not freeze: permissionless finalize discharges it) | getFirstUnfinalizedMessageEnqueueTime reads pendingQueueIndex, which only finalize advances |
| L_inv_prefix | FACT | lastFinalized ≤ lastCommitted; committed[i]≠0 ⇔ i ≤ lastCommitted; finalizedRoot chain is contiguous | PROVED@bound | |
| L_inv_one_challenge | FACT | inChallenge ⇔ batchInChallenge(batchChallenged), and no other index is in challenge | PROVED@bound | |
| L_par_hdr_v2_composed | PAR | Solidity v2 header == Go V1.Bytes() with byte0 patched to 2 (shared aggregated blob hash, ssvh=0) | PROVED | Rollup.sol 343-370 vs batch_cache.go 1720-1731. Both aggregate keccak(concat blob hashes) (892-918 / 1789) |
| L_par_ssvh_live | PAR | under the live sealBatch guard (no replay index), Go header == Solidity header at v1/v2 | PROVED | batch_cache.go 1447-1449 |

Gas (challengeState O(B) loop, revertBatch per-count cost) is measured in replay, not stated as a law.

## 5. Replay

- Foundry: deploy the real Rollup behind ERC1967Proxy with a mock verifier and the real L1MessageQueue, drive each REFUTED trace as a transaction sequence (`vm.warp`, blobhash via `vm.blobhashes`), and assert each step's revert/ok tag and the final storage against the model's.
- This closes the M0 `not_applicable` sides: a full `commitBatch` v2 replay showing byte0=2 and ssvh=0 on the committed header.
- Go: composed producer via `createBatchHeaderWithSequencerSetHash` at v2.

## 6. Gate additions

G1/G2/G3/G5/G11 extend to M1 paths. G4 canaries add mutation kinds for state machines: drop a guard, flip a guard comparison, skip an effect. Each must flip at least one law's status or be rejected. G12: every PROVED result record carries its bound.
