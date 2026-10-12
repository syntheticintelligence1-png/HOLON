# Human answers

Answers to `docs/BUILD_PLAN.md` §6, "Questions for the human". The human gave them in the build session on 2026-10-12 ("I agree with your recommendations ... for Q5, an unconditional yes for everything unbounded"). Each answer replaces the default in §0.3 from now on.

| Q | Answer | Effect |
|---|---|---|
| **Q5** historical data | **Unconditional yes, unbounded.** Every source: an L1 execution RPC with archive state, a beacon API, a blob archive for blobs past the pruning window, the block explorer API, BigQuery's public Ethereum dataset, and the Morph L2 RPC. Window: the full history of the Morph rollup contracts since deployment. Calldata-only inputs are accepted where blobs are no longer retrievable, labelled as such. The human calls on-chain replay **make or break**: every other result is secondary to it. | M2 exit (a) is no longer recorded as UNKNOWN by default. Historical data acquisition becomes a priority track (`I23a`, below) that starts as soon as the network is open, ahead of I20. The environment's network policy currently refuses every one of these hosts (`CONNECT tunnel failed, response 403`, checked 2026-10-12), so the track waits on the environment change, not on any decision. |
| **Q6** mutation threshold | **0.80** of non-equivalent mutants in scope. The agent drafts the operator catalog in I22's prereg for the human to sign off; equivalent mutants are adjudicated from the diffs before any run. | Unblocks I22's prereg. |
| **Q7** held-out target | **Scroll's ScrollChain at a pinned commit**, sealed now: `spec/heldout/target.json` (`scroll-tech/scroll-contracts` v4.0.0, `42de954b…`, `src/L1/rollup/ScrollChain.sol`). A public, clonable repo is acceptable. | Unblocks I49. No agent reads it before I49's prereg. |
| **Q9** auditor family | The default stands. Same-family rounds are labelled `same` and do not count toward convergence. | I21, I45 and I46 proceed under the label. |
| **Q14b** meta-theorems | **Yes.** Thm 6.4, 6.6 and 6.7 may be proved once, by hand, in Lean, and kernel-checked. | I42 is no longer "paper proof only". |
| **Q14c** agent proofs | **Yes**, through an intake. Bend checks every agent proof, and the intake never trusts one. | Unblocks I41. |
| **Q16** installs | **Yes.** `tools/setup_env.sh` may install pinned slither-analyzer, z3-solver, hevm, echidna, medusa and halmos into `~/.holon/tools` (never into the repo). | I17 onwards; I52's baselines. |
| **Q20** corpus size | **N = 20** defects across at least 3 systems. | Unblocks I48. |
| **Q1** freezing | **Yes**, to be done by the human. AGENTS.md rule 1 reserves `tools/freeze.py write` for the human, and `tools/freeze.py` is itself frozen, so no agent can extend `FROZEN_ROOTS` either. The steps are below. | Until it is done, every protection resting on an agent-writable file stays self-certified. |

## Q1: the steps for the human

1. In `tools/freeze.py`, extend `FROZEN_ROOTS` with:
   - `laws/M1/`, `spec/M1/predictions.json`, `spec/M1/mutations.json`, `tests_m1/` and `whitepaper.md`, as §6 Q1 asks;
   - `laws/M2/`, `spec/M2/predictions.json`, `spec/schemas/`, `holon/audit/prereg.py`, `holon/statement_diff.py` and `docs/HUMAN_ANSWERS.md`.
2. Run `python tools/freeze.py write` and commit `FROZEN.sha256` together with the change to `tools/freeze.py`.

## I23a: historical data acquisition (added for Q5)

- **Goal.** Fetch the complete on-chain history the replay needs, as soon as the environment allows the hosts.
- **What it fetches:**
  - every transaction to the Morph L1 rollup and message-queue contracts since deployment, with calldata, receipts and logs;
  - the blob sidecars of every commit, from the beacon API inside the pruning window and from the blob archive outside it;
  - the L2 blocks the batches commit to, from the Morph L2 RPC.
- **How it is stored.** A content-addressed snapshot outside the repo (`~/.holon/historical/`), with an index committed under `results/M2/historical/`. Each item carries the source and the block range it came from.
- **What it feeds:**
  - I16's per-edge corpus, with real headers and real batches for the codec and derivation edges, before I20;
  - I23's replay of the extracted model on real commits.
- **Hosts the human must allow** (environment settings, Network access):
  - an L1 execution RPC: for example `ethereum-rpc.publicnode.com`, or a keyed `eth-mainnet.g.alchemy.com` or `mainnet.infura.io`, for archive state;
  - a beacon API: for example `ethereum-beacon-api.publicnode.com`;
  - a blob archive: `api.blobscan.com`;
  - the explorer API: `api.etherscan.io`;
  - the Morph L2 RPC: `rpc.morphl2.io`.

  BigQuery is already reachable but needs credentials.
- **Credentials**, set as environment variables in the environment's secrets and never pasted into the chat:
  - `ETH_RPC_URL`, for a keyed archive endpoint;
  - `ETHERSCAN_API_KEY`;
  - optionally a GCP service-account key for BigQuery (`GOOGLE_APPLICATION_CREDENTIALS_JSON`).

  A new session picks up environment changes.
