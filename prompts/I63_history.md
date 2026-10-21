# I63 (= I28a): deployment history from the code, cross-checked on chain

Rendered from `docs/BUILD_PLAN.md` §4 I28, its history deliverable (whitepaper §10.1 deployment history, Def 4.3 S_k/A_k and the MIG edges), and from human answer Q18 (`docs/HUMAN_ANSWERS.md`): code-derived history is the model, and the on-chain timeline is an independent check. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (H1-H8), commands, formats and exit codes are in the docstring of `tests_m3/test_history.py`. The key's thresholds pin that docstring, the sidecar and the basis by sha256.

## Why a separate key

BUILD_PLAN I28 has two halves:
- **History:** versions, reinitializers, storage-layout diffs and MIG edges, plus the on-chain timeline.
- **Laws:** versioned machines `step_k`/`run_k`, PAR-init, O9, D4, F12.5 and G11V's in-flight inhabitants.

The laws half adds a rule producer, so it bumps the rule catalog. The roadmap split of 2026-10-21 runs catalog-bumping iterations one at a time, and I26 (catalog holon-rules/1.5) is in flight in the other lane.

So the history half, which needs no catalog, goes first, under its own key. This follows the precedent of I59 (= I23a), the on-chain fetch pulled forward from I23 and numbered I59 only because prereg keys are plain numbers. I28 keeps its number, its plan text and its predictions (O9, D4, F12.5) for the laws half, which reads I63's outputs.

## What I63 does

1. **Refs (H1).** The 25 tags of the target repository whose tree holds `Rollup.sol` (`v0.2.0-beta`..`v0.6.3`; `v0.1.0-beta` has no Rollup), pinned to their commits in the sidecar, plus the pinned head `3e44e79`. A tag that is missing or has moved refuses.
2. **Builds (H2).** Each ref is materialized from git objects and compiled with the pinned solc 0.8.24 and the pinned dependency tree under three configurations:
   - `deployed`: optimizer runs 200, I23's Surprise 1;
   - `foundry`: 999999;
   - `hardhat`: 10000.

   A build's code identity is its runtime code with the immutable ranges zeroed and the CBOR metadata stripped.
3. **Initializers (H3)** and **layout (H4)**, from the `deployed` build's AST and storageLayout. Each layout entry is keyed by the contract that declares it, not by solc's compiled-contract name, so three `__gap`s stay three.
4. **Layout diff (H5)** between consecutive versions: persisted, moved, retyped, added, removed, resized gaps and overlaps, and whether the step is compatible.
5. **Versions and MIG edges (H6).** A version is a maximal run of refs with equal code identity. An edge records:
   - the reinitializers it introduces;
   - its layout diff;
   - its in-flight set: every non-gap entry of the new layout whose bytes meet old non-gap state, labelled unchanged, retyped or reinterpreted, with the old entries it reads.
6. **On-chain snapshot (H7).** For each of the 12 Upgraded logs in I59's index, holon reads the receipt, the implementation's runtime code and the block's time. The receipt is stored in I59's canonical form, so that its sha256 must equal the receipt hash I59 committed weeks ago. The upgrade's facts are decoded from that receipt: the implementation, Initialized and AdminChanged logs, the sender and the contractAddress. The snapshot is written once and checked offline afterwards.
7. **Timeline (H8).** Each upgrade's matches against the basis, its version, and whether the reinitializers its version introduces ran in its own transaction. The baseline counts Initialized logs of every earlier upgrade transaction, matched or not. Also recorded: downgrades, coverage debt (unmatched or ambiguous upgrades, never smoothed over: Q18) and never-deployed versions.

The predictions are decided on the instrument's own recomputation of H8 from the verified receipts and the code files, never on holon's timeline. I63 states no law, changes no catalog and reads no law, record or fact document. Its outcome paths are `gen/M3/history/`, `results/M3/history/` and `docs/iterations/I63.md`.

## What is anchored, and what is not

- **Receipts:** every upgrade transaction's receipt is anchored by I59's committed receipt hash (`results/M2/historical/index.json`).
- **The last implementation's code:** anchored by I23's record (`results/M2/historical/trans.json`, R1).
- **The other 11 implementations' code** (the placeholder and the ten in between) has no anchor in the repository.
  - The gateway refuses state proofs that far back (see the probes below), so the code cannot be tied to I59's block hash.
  - The build's review therefore reads every implementation's code again from a second provider and records the sha256s.
- **Block times:** informational. No prediction uses them.

## Deviations from the plan's text, and why

- **All tags, not `v0.4.6`..`v0.6.3`.** The plan's range was what the checkout was believed to hold. The checkout has 26 tags. The proxy's 12 upgrades start in October 2024, a year before `v0.4.6`'s commit (November 2025), so the plan's range could not explain most of the timeline. The 25 tags are pinned so that a later `git fetch --tags` cannot change H1.
- **The on-chain timeline is fetched, not assumed.** Q18 was answered "both, cross-checked" after the plan was written.
- **MIG edges join versions, not tags.** 26 refs collapse to 11 code versions under the `deployed` configuration. If mainnet skips versions, the transition that ran is the composition of consecutive edges, which I28 computes.
- **Dependencies.** Every ref compiles against the pinned OpenZeppelin 4.9.3 tree (`replay.sol_deps`), while the tags' `yarn.lock` resolves 4.9.5. I23's match of the head build shows no effect on Rollup's imports. A difference it caused elsewhere would show as coverage debt, not as a wrong match.

## What was known before this prereg (disclosed)

**The basis**, computed by the instrument at the prereg, as BUILD_PLAN §0.1 requires: every ref compiled under every configuration, 11 versions and 10 edges. Two edges are incompatible under H5:
- **V2->V3:** `maxNumTxInChunk` is renamed `__maxNumTxInChunk` at slot 154, same type.
- **V10->V11, the cutover:**
  - slot 151's `l1StakingContract` becomes `submitterContract` (both addresses);
  - `batchDataStore`'s `BatchData` struct changes its fourth member from `signedSequencersBitmap` (uint256) to `submitter` (address), so for every batch committed before the upgrade, `submitter` reads the low 160 bits of the old bitmap.

The in-flight sets list both as read by the new code. No prediction is made about the basis. These are construction facts, which the laws half (I28) and NAT (I29) inherit.

**Network calls before the first prereg commit (da90ec05, 15:21:50 UTC),** all to the sidecar's gateway:
- **14:51 UTC:** `eth_blockNumber`, and `eth_getTransactionReceipt` for the last upgrade (tx `0xdeb5268c…`, block 26031669). Printed per log: the emitting address, the first 16 hex digits of topic 0, and topic 1. Seen:
  - the proxy's Upgraded, with topic 1 = I23's implementation `0x213ce22b…`;
  - a proxy log with topic 0 `0xaf9f8e4eb71b2fdd…` and topic 1 `0x0dc417f8af88388737c5053ff73f345f080543f7`;
  - the proxy's Initialized, with no topic 1; its data, which holds the version, was not printed;
  - a log of `0x542675e9…` (topic 0 `0xc2617efa69bab667…`) and a log of `0xf101f7f5…` (topic 0 `0x442e715f626346e8…`).

  There was no AdminChanged. Because this receipt was partly seen, P5 leaves the last upgrade out.
- **About 15:01 UTC:** `eth_getBlockByNumber` for the 12 upgrade blocks, for their timestamps only. They were fetched for a "newest tag before the block" date-rule prediction, which was dropped before the first prereg commit because the lead did not believe it. The timestamps:

  | block | time (UTC) |
  |---|---|
  | 20996846 | 2024-10-19 03:11 |
  | 20998835 | 2024-10-19 09:51 |
  | 21007191 | 2024-10-20 13:48 |
  | 21283676 | 2024-11-28 03:51 |
  | 21614093 | 2025-01-13 07:31 |
  | 22465639 | 2025-05-12 07:11 |
  | 23874746 | 2025-11-25 08:51 |
  | 24575030 | 2026-03-03 06:06 |
  | 24745644 | 2026-03-27 01:34 |
  | 24769565 | 2026-03-30 09:36 |
  | 25236554 | 2026-06-03 11:26 |
  | 26031669 | 2026-09-22 07:54 |

**Between the first prereg commit and this one** (the independent review of da90ec05 asked for a full account):
- **A draft of the build ran in the prereg worktree** between 15:21 and 15:29 UTC: `holon/frontends/solidity/history.py` and its `history` dispatch. The lead ran three things:
  - `python -c "import holon.frontends.solidity.history"`;
  - `python -m holon history --help`;
  - `python -m holon history extract`, which reads git and solc only. Its refs, versions and edges equalled the basis's.

  No `fetch` or `timeline` was run, and no receipt, code or log of an upgrade was read. The draft was moved out of the worktree at 15:29 UTC while the review ran. The build resumes after this prereg is pushed.
- **Two capability probes of the gateway**, about no upgrade:
  - `eth_getBlockByNumber(26179508)`, whose header rebuilds to I59's `to_block_hash`;
  - `eth_getProof` of the WETH contract at that block, which was refused: "distance to target block exceeds maximum proof window".

**Scripts and sources read,** all at the head commit `3e44e79`, with `git grep` and `git show`. None was read at an older tag.
- `git grep EmptyContract` over `contracts/`. Matching lines were read in:
  - `contracts/deploy/011-EmptyContract.ts`, `013-DeployProxys.ts`, `019-AdminTransfer.ts` and `index.ts`;
  - `contracts/src/types.ts`.

  The file list also named `contracts/contracts/misc/EmptyContract.sol`, `contracts/contracts/test/base/CommonTest.t.sol` and `contracts/tasks/deploy.ts`.
- `013-DeployProxys.ts`, lines 1-60, filtered by `git show | grep`.
- `git grep` for `upgradeAndCall`, `initialize2`, `initialize3` and `initialize4` over `contracts/deploy`, `contracts/tasks` and `contracts/scripts`. Matching lines were read in:
  - `contracts/deploy/020-ContractInit.ts`;
  - `contracts/tasks/README.md`, `mainnet_upgrade.ts`, `proxy_upgrade.ts` and `token_deploy.ts`.
- `Rollup.sol`'s initializer signatures at `v0.4.1`, `v0.4.10` and the head.
- `016-RollupInit.ts`, which the review notes calls `upgradeToAndCall(initialize)`, was not read.

**The independent review of da90ec05** is `docs/iterations/I63_prereg_review.json`. That commit is kept on the branch `claude/brave-wright-2c5d0o-i63-prereg-v1`. Its verdict was no sign-off: 1 blocking, 6 major, 9 minor and 5 advisory findings. How each was folded into this commit:

| finding | resolution |
|---|---|
| F1 (blocking) | Receipts are stored canonically and checked against I59's hashes. The instrument decodes them, and P1 and P5 are decided on its decoding. Code anchoring is disclosed above. |
| F2 | Every prediction is decided on the instrument's H8. |
| F3, F4 | P5 now needs evidence (a matched upgrade and logged versions 1, 2 and 3), and leaves out the partly seen last upgrade. The "initialize4 ran inside the cutover's" clause is gone. |
| F5 | The baseline counts every earlier upgrade transaction's Initialized logs. |
| F6 | `in_flight` now holds what the new version reads, including retyped and reinterpreted entries. |
| F7 | Disclosed above. |
| F8 | The report is an outcome path. |
| F9 | The thresholds pin the sidecar, the basis and the contract docstring by sha256. A test checks them and every threshold number. R2 forbids touching `spec/M3/lib/history*`. |
| F10 | Tags are pinned. |
| F11 | P4 needs two matched upgrades. |
| F12 | P2 covers upgrades 2-11 and no longer claims `bytecodeHash`. |
| F13 | The choices are written into H6 and H8. `never_deployed` means "in no match". |
| F14 | The index's content hash is recomputed. |
| F15 | The generic check is case-insensitive, and `holon/` may not import `tests_m3` or name the instrument. |
| F16 | P1 checks the creation receipt and the sender as the new admin. The EmptyContract identity stays an expectation, untested. |
| F17, F20 | Noted in H6. |
| F18 | A non-literal reinitializer is an extraction error. |
| F19 | The dependency tree is checked against its pin and disclosed. |
| F21 | Disclosed above. |

## Predictions (key I63 in `spec/M3/predictions.json`)

- **P1.** The first upgrade is the proxy's creation:
  - the receipt's contractAddress is the proxy;
  - no version matches;
  - no Initialized log;
  - one AdminChanged log, from zero to the sender.
- **P2.** Upgrades 2-11 each match exactly one version, under `deployed` only.
- **P3.** Mainnet starts on the `v0.4.0` line, and the v0.2 versions appear in no match.
- **P4.** At least two upgrades match, with no downgrade.
- **P5.** Before the last upgrade:
  - every matched upgrade is consistent;
  - upgrade transactions log the Initialized versions 1, 2 and 3.

  `initialize2` and `initialize3` are guarded by nothing but `reinitializer(k)`, so a gap between upgrade and initialization would have left them callable by anyone.

**Regressions:**
- **R1:** the last upgrade is I23's implementation and code, matched to the head's version.
- **R2:** no law, record, catalog, I63 instrument or earlier-milestone output changes, and the gates pass.
- **R3:** construction checks.

## Deliverables

- **`holon/frontends/solidity/history.py`**, generic: every target-specific name comes from the sidecar `spec/M3/lib/history.json`. It implements H1-H8, independently of `tests_m3/_i63.py`; the tests compare the two.
- **The CLI.** `python -m holon history extract|fetch|timeline [--check]`, with the exit codes of the contract. Only `fetch` touches the network, and it writes once. `--check` never writes.
- **Outputs:**
  - `gen/M3/history/morph_rollup.json`;
  - `results/M3/history/onchain.json`, `results/M3/history/receipts/<tx>.json` and `results/M3/history/code/<implementation>.hex`;
  - `results/M3/history/timeline.json`.

  All byte-identical across runs.
- **The build's review:** one fresh agent. It also re-reads every implementation's code from a second provider.
- **`docs/iterations/I63.md`:** the report, with the timeline, every miss and every coverage-debt item stated plainly.

## Rules

- AGENTS.md throughout. Never edit a frozen file, `spec/M2`, `laws/`, `results/M0-M2`, `gen/M0-M2`, `replay/` or `holon/rules/`.
- The instrument, the sidecar and the basis are fixed at this commit. A wrong instrument is a Question plus an amendment line in `spec/M3/amendments.jsonl`, never a silent edit.
- A missed prediction is a result: report it, never adjust the rule or the inputs to make it hold.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
