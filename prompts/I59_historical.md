# I59 (the I23a track): historical on-chain acquisition and the first per-edge replay on real inputs

Added by the human's answer to Q5 (`docs/HUMAN_ANSWERS.md`): on-chain replay is make or break, unconditionally and over the whole history. Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, then this prompt. The exact CLI, file formats and API are in the docstring of `tests_m2/test_historical.py`. The frozen instrument is `spec/M2/lib/historical.json`.

## Goal

Fetch the complete on-chain history of the Morph rollup on Ethereum mainnet, from the sidecar's `from_block` to its finalized `to_block`. Run the first replays of real inputs through the models before I20 exists, so that real data starts falsifying them now. Whitepaper §8.7: refinement evidence comes from native replay on real inputs.

## What to build

- **`holon/historical/`** (a package):
  - **fetch.** Paginated `eth_getLogs` over the proxy and the sidecar's topics, at most `get_logs_max_blocks` per call. Then the transactions and receipts of those logs, then the commit transactions' blobs: from the beacon API (`/eth/v1/beacon/blob_sidecars/<slot>`) within its retention window, otherwise from the blob archive.
    - Uses `ETH_RPC_URL` or `ETHERSCAN_API_KEY` when set; falls back to the public endpoints.
    - Retries with backoff. Resumable through the content-addressed snapshot outside the repo.
  - **replay.** ABI-decodes each commit from the pinned `IRollup.sol` / `Rollup.sol`. Runs the parent-header checks against the frozen M0 header model: `ok_sol`, `ok_go` and the `enc_sol(dec(·))` round trip, through the existing native or `.mjs` model (`holon/model_native.py`, `holon/model_eval.py`). Runs the real Go decoders: a Go harness outside the repo that imports the pinned checkout's `common/batch`, as in the M1 Go replay. Also does linkage against the emitted batch hashes, blob versioned hashes and KZG commitment hashes, and revert/recommit bookkeeping.
  - **header_checks.** The per-header checks, without the chain.
  - **disagreements.** Classified by I16's mechanical rules (`holon.refinement`), into `results/M2/historical/disagreements.json`.
- **CLI:** `python -m holon historical fetch|replay`.
- **Committed outputs:** `results/M2/historical/{index.json, replay.json, disagreements.json}` only. Raw bytes never enter the repo.
- **`docs/iterations/I23a.md`** with a prediction table, pass or miss for each id.

## Predictions (key I59)

Each is scored separately, and each is about chain data that nobody had fetched when the prereg was made.

| id | claim |
|---|---|
| P1 | Every decoded successful commit's parent header hashes (keccak256) to the batchHash the latest CommitBatch event emitted for that index. There are 0 exceptions, reverts and recommits included. |
| P2 | Every real parent header has length 249 or 257 and is accepted by both `ok_sol` and `ok_go`. Its `enc_sol(dec(·))` round trip differs at most in the sequencerSetVerifyHash cells 185..216. |
| P3 | Headers with a nonzero sequencerSetVerifyHash form a prefix of the batch sequence. Every one has a lower batch index than every header whose field is zero, and at least one header has it zero. The pinned commit path writes `bytes32(0)`; older implementations may have written a real value. |
| P4 | Only header versions 0 and 1 occur on mainnet in the window. Version 2, which the pinned code allows, never appears. |
| P5 | For every batch whose latest commit was a `commitBatch` carrying blobs, the header's blobVersionedHash, as seen in the next commit's parent, equals that transaction's first blob versioned hash. There are 0 exceptions. |
| P6 | At least 99% of the commit blobs in the window can be retrieved, from the beacon API or the blob archive. Every retrieved blob's KZG commitment hashes to its versioned hash. |
| P7 | The real Go decoders (`common/batch`) agree with the frozen `dec_go`/`ok_go` on every real parent header. |
| P8 | The window holds the whole history. The earliest committed batch index is 1, the indices cover 1..max without gaps, and every reverted batch is recommitted within the window. |
| P9 | Every successful commit transaction after the proxy's last Upgraded event in the window decodes under the pinned ABI. |

**Regressions.** Gates M0, M1 and M2 pass. Statements, statuses and gen files of M0, M1 and M2 are unchanged.

**Construction checks.** The index for a fixed sub-window is byte-identical across runs. No secret appears in any output. The snapshot is outside the repo. The toy-header checks pass.

## Disclosure

While writing this prereg, the lead read the following:
- the finalized block number (the window end);
- one `eth_getLogs` probe over the most recent ~2000 blocks, to learn the range limit. It returned one CommitBatch log, batch index 62151.
- proxy-admin probes, which the RPC refused.

No prediction concerns batch counts or that batch. No transaction, header or blob was read.

## Rules

- **AGENTS.md is binding.** Never edit `facts/`. A model-vs-chain difference is a finding, recorded and classified, never fixed by editing the model or the facts.
- **No tuning.** A predicted outcome that does not come out is a Surprise, reported with the items that show it.
- **No skips.** A missing network or endpoint is a failure with a clear message.
- **Determinism.** Fetch order and the index are canonical. Retries and timing never enter the outputs.
