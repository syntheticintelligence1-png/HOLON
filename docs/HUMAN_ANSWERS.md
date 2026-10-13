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

## Answers delegated to the lead (2026-10-13)

The human delegated the open questions to the lead agent ("answer the questions urself accordingly … we dont cut corners"). They also set standing guidance:

- **HOLON's end goal is complex software in general.** Rollups are the starting target, not the goal.
- **Measure for the strongest signal of a breakthrough.**
- **Cut no corners.**

These answers are the lead's, made under that delegation, not the human's own. The lead builds the system these answers govern, so each answer takes the stricter option. Where an answer defines a measure of HOLON's own work (Q11), the concrete definition is preregistered and adversarially reviewed before the work it measures.

| Q | Answer (lead, delegated) | Effect |
|---|---|---|
| **Q11** L6 and L9 definitions | **Target-agnostic and measured against ground truth, never against HOLON's own outputs alone.** I54 preregisters the exact definitions and thresholds, and an adversarial reviewer checks them, before any of I55–I57 runs.<br><br>**L6 ("can" versus "will").** Each REFUTED finding gets a bounded game over the extracted principal classes, with ordinal payoffs from the extracted value flows (transfers, rewards, slashing, fees). The game classifies the finding as *rational* (some permitted actor has a strategy with non-negative payoff that triggers it), *irrational*, or UNKNOWN. Reported:<br>- the decided fraction;<br>- accuracy against corpus ground truth (I48), wherever exploitation, or its absence, is documented;<br>- a negative control: findings known to be unexploitable must not come out *rational*.<br><br>**L9 (environment).** Environment axioms are replaced by time-indexed modules: L1 fork choice and reorg depth, the DA availability window, and the data fetchers. Reported:<br>- environment-premise coverage: the share of laws whose environment premises are modelled rather than assumed;<br>- module accuracy against recorded history on held-out time slices, for example blob retrievability against I59's snapshot;<br>- sensitivity: the number of law statuses that change when an axiom becomes a module, each change replayed. | Unblocks I54 (M5). |
| **Q18** deployment history | **Both, cross-checked.**<br><br>**Code-derived history is the model.** It comes from reinitializers and storage-layout diffs across git tags, built as a generic extractor for any upgradeable-proxy codebase.<br><br>**The on-chain timeline is an independent check.** It uses the proxy `Upgraded` and admin events, and the implementation bytecode at each upgrade, matched to tags by metadata-stripped bytecode hash.<br>- An unmatched implementation, or a mismatched order, is recorded as a finding or as coverage debt, never smoothed over.<br>- In-flight states at each cutover come from real chain history where it is reachable. Logs and transactions need no token; historical *state* needs an archive key in `ETH_RPC_URL`, which is optional. | Unblocks I28. The upgrade timeline stops being an assumption. |
| **Q4** schemas | **Yes.** `result_record_v2` and `law_ir_0_3` are adopted into the frozen `schemas/` at I33's adoption step, after I41 has added `prover`, so the frozen version is complete. That includes the `filter_bin` values with `intended_bounded`, `kernels[]`, `scope{kind,H}`, `refinement_refs`, `coverage` and the INTENT rule. v1 `triage` stays untouched. The agent prepares the files and the exact steps. Running `tools/freeze.py write` stays the human's (AGENTS.md rule 1). | I33 proceeds. The v2 formats are self-certified until the human freezes them. |
| **Q12** legacy registry | **Fetch the real code. A stand-in is a last resort.** The pre-cutover staking and registry contract is found from on-chain history.<br>- Its bytecode is fetched, along with its verified source from the explorer where one exists.<br>- When the source compiles to the deployed bytecode (metadata stripped), it is extracted with the I17/I19 frontends.<br>- Otherwise it gets a bytecode-level model, labelled.<br><br>A stand-in is used only if the code cannot be recovered, and it is labelled. The acquisition component is generic: historical code for any target. | Unblocks I36. O13 and O14 rest on real code. |
| **Q8** G7 promotion | **Every PROVED law.** A hand-picked subset would be a selection bias.<br>- A law that Lean cannot check within budget stays single-kernel (I1), with the reason recorded: timeout, recursion depth, or an unsupported form.<br>- Cross-kernel coverage is reported as a metric.<br>- A cross-kernel disagreement is a blocking finding.<br><br>Large byte layouts may use generated per-cell lemmas. The 131,072-byte blob laws are the known risk. | Unblocks I43. |
| **Q19** M3 hand-written facts | **Extracted facts are the input of every M3 law.**<br><br>**When a hand-written fact is allowed.** Only for a component no extractor reaches, and only under a per-item waiver. The waiver names:<br>- the component;<br>- why the extractor cannot reach it;<br>- the extraction-debt entry that will retire it.<br><br>Waivers are listed in coverage (`hand_written: true`). A result that rests on a waiver is labelled and does not count toward an exit criterion that requires extraction.<br><br>**A waiver never applies where an extracted document exists.** For the rollup, I19 with A19 extracts the document and I20 adopts it. So M3 laws over the rollup run on the adopted extracted documents, and an M3 prereg drafted over the hand-written `spec/M1/facts` is redrafted after I20 merges. | I30's draft, which runs on the hand facts, is held and redrafted after I20. Builds under I24, I28 and later bind to the extracted documents. |

**How the end goal applies later.**

- **I47 (target-agnostic factory).** Its tests require that nothing in `holon/` names a target, as I6 and I22 already require.
- **I48 (corpus).** The corpus is chosen to test generality beyond rollups wherever the frontends reach.
- **New frontends.** A new language frontend is a candidate iteration once M3's rules are stable.

## Q1: the steps for the human

1. In `tools/freeze.py`, extend `FROZEN_ROOTS` with:
   - `laws/M1/`, `spec/M1/predictions.json`, `spec/M1/mutations.json`, `tests_m1/` and `whitepaper.md`, as §6 Q1 asks;
   - `laws/M2/`, `spec/M2/predictions.json`, `spec/schemas/`, `holon/audit/prereg.py`, `holon/statement_diff.py` and `docs/HUMAN_ANSWERS.md`.
2. Run `python tools/freeze.py write` and commit `FROZEN.sha256` together with the change to `tools/freeze.py`.

## I23a: historical data acquisition (added for Q5; prereg key I59)

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

## Network check after the human opened access (2026-10-12)

- **Reachable now:**
  - the L1 execution RPC (`ethereum-rpc.publicnode.com`, latest block about 26.18M);
  - the beacon API (Lighthouse);
  - the blob archive (`api.blobscan.com`);
  - Etherscan;
  - the Morph L2 RPC.
- **Historical state needs a token.** Public RPC archive *state* requests return "Archive requests require a personal token". Transactions, receipts and logs at any height work without one. A keyed archive endpoint in `ETH_RPC_URL` would add historical state; it is optional.
- **No credentials set yet:** `ETHERSCAN_API_KEY`, `ETH_RPC_URL` and BigQuery are absent. I23a works without them; each one adds a source.
