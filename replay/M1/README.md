# M1 replay — rollup state-machine witnesses on the real contracts

Replays every REFUTED M1 witness trace against the real Morph contracts at
commit `3e44e795586af3e11285b603ab642c67823add51` (checkout `~/ext/morph`,
read-only), plus the M0 codec closure: a full `commitBatch` at version 2.

## Setup

- Solidity side: Foundry scratch tree `~/ext/replay_sol` (solc 0.8.24, forge
  1.8.5, evm_version cancun, ffi=true). Real contracts deployed:
  - `Rollup` behind `ERC1967Proxy` (`initialize` + `initialize3`,
    `addChallenger`, `importGenesisBatch`)
  - `L1MessageQueueWithGasPriceOracle` behind `ERC1967Proxy` (real contract;
    constructor sets MESSENGER/ROLLUP_CONTRACT/ENFORCED_TX_GATEWAY immutables
    and disables initializers, so `initialize` runs through the proxy)
  - `Submitter` behind `ERC1967Proxy`; one registered submitter staked 1 ETH,
    one challenger via `addChallenger`
  - `AcceptAllVerifier` (returns true) and `AllowAllWhitelist`
  - Config matching `proposals/M1/facts/rollup_sm.json`: genesis imported at
    timestamp 1, `finalizationPeriodSeconds=2`, `proofWindow=2`,
    `rollupDelayPeriod=3`, `challengeDeposit=1 wei`.
- Harness source: `replay/M1/solidity/Harness.t.sol`, copied to
  `~/ext/replay_sol/test/M1Harness.t.sol`. Real batch headers are built with
  the V0/V1 codec layout (`mkV0Header`/`mkV1Header` in the harness) so the
  contract's keccak header-hash checks run for real (abstraction A1).
  `vm.blobhashes` supplies blobs; `vm.warp` uses literal timestamps.
- Go side: `replay/M1/go/holon_m1_replay_test.go`, copied to
  `~/ext/morph_scratch/common/batch/` (worktree at the same commit), driving
  the real `BatchCache.createBatchHeaderWithSequencerSetHash`
  (`batch_cache.go:1684-1731`, the `h[0] = BatchHeaderVersion2` patch).

## Commands

```
export PATH=$HOME/.foundry/bin:$PATH
cd ~/ext/replay_sol
forge test --match-path test/M1Harness.t.sol -vv
```

Observed:

```
Ran 6 tests for test/M1Harness.t.sol:HolonM1Replay
[PASS] test_disch_nonowner() (gas: 1304291)
  OBSERVED disch_nonowner: all non-owner paths reverted; owner revertBatch cleared
[PASS] test_disch_timeout() (gas: 1025225)
  OBSERVED disch_timeout: Panic(0x11) on both commit paths; setPause cleared
[PASS] test_nat_delay_frontier() (gas: 1031350)
  OBSERVED nat_delay_frontier: l1msg delay then lifted by finalize
[PASS] test_undo_commit_revert_and_enabled() (gas: 739352)
  OBSERVED undo_enabled: commitBatch reverted, commitState recommitted batch 1
[PASS] test_undo_pause() (gas: 1197726)
  OBSERVED undo_pause: fin_ts residue 5, re-challenge -> 7
[PASS] test_v2_composed_header() (gas: 388203)
  OBSERVED v2 closure: byte0=2, ssvh=0, committed hash matches constructed header
Suite result: ok. 6 passed; 0 failed; 0 skipped
```

```
cd ~/ext/morph_scratch
go test ./common/batch/ -run TestCreateBatchHeaderV2Producer -v
```

Observed:

```
=== RUN   TestCreateBatchHeaderV2Producer
--- PASS: TestCreateBatchHeaderV2Producer (0.00s)
ok  	morph-l2/common/batch
```

Model bytes for the M0 closure were produced by evaluating
`enc_go_v2_producer` on the compiled Bend model
(`holon/model_eval.eval_batch`, facts `proposals/M1/facts/morph_header_m1.json`)
with the same field values; byte-for-byte equal on both chains of evidence.

## Divergences

None between model and real code. Two model abstractions matter for reading
the trace (documented in facts): enqueue maps to
`appendCrossDomainMessage` from the MESSENGER immutable (pranked), and
`commitState` is the no-blob recommit path (`blobhash(0) == 0` — the test
environment has no blob by default). `undo_pause` also contains one
extra-observation step past the model witness: after pause/unpause the batch
can be challenged again and extended a second time.

Fold into result records: `python3 -m holon replay --milestone M1`.
Statuses are in `report.json`.
