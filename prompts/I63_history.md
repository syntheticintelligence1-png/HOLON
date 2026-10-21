# I63 (= I28a): deployment history from the code, cross-checked on chain

Rendered from `docs/BUILD_PLAN.md` §4 I28, its history deliverable (whitepaper §10.1 deployment history, Def 4.3 S_k/A_k and the MIG edges), and from human answer Q18 (`docs/HUMAN_ANSWERS.md`): code-derived history is the model, and the on-chain timeline is an independent check. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (H1-H8), commands, formats and exit codes are in the docstring of `tests_m3/test_history.py`.

## Why a separate key

BUILD_PLAN I28 has two halves:
- **History:** versions, reinitializers, storage-layout diffs and MIG edges, plus the on-chain timeline.
- **Laws:** versioned machines `step_k`/`run_k`, PAR-init, O9, D4, F12.5 and G11V's in-flight inhabitants.

The laws half adds a rule producer, so it bumps the rule catalog. The roadmap split of 2026-10-21 runs catalog-bumping iterations one at a time, and I26 (catalog holon-rules/1.5) is in flight in the other lane.

So the history half, which needs no catalog, goes first, under its own key. This follows the precedent of I59 (= I23a), the on-chain fetch pulled forward from I23 and numbered I59 only because prereg keys are plain numbers. I28 keeps its number, its plan text and its predictions (O9, D4, F12.5) for the laws half, which reads I63's outputs.

## What I63 does

1. **Refs (H1).** Every tag of the target repository whose tree holds `Rollup.sol` (25 tags, `v0.2.0-beta`..`v0.6.3`; `v0.1.0-beta` has no Rollup), ordered by commit time, plus the pinned head `3e44e79`.
2. **Builds (H2).** Each ref is materialized from git objects and compiled with the pinned solc 0.8.24 under three configurations:
   - `deployed`: optimizer runs 200, I23's Surprise 1;
   - `foundry`: 999999;
   - `hardhat`: 10000.

   A build's code identity is its runtime code with the immutable ranges zeroed and the CBOR metadata stripped.
3. **Initializers (H3)** and **layout (H4)**, from the `deployed` build's AST and storageLayout. Each layout entry is keyed by the contract that declares it, not by solc's compiled-contract name, so three `__gap`s stay three.
4. **Layout diff (H5)** between consecutive versions: persisted, moved, retyped, added, removed, resized gaps and overlaps, and whether the step is compatible.
5. **Versions and MIG edges (H6).** A version is a maximal run of refs with equal code identity. An edge records the reinitializers it introduces, its layout diff and the in-flight entries the new code reads from the old state.
6. **On-chain snapshot (H7).** For each of the 12 Upgraded logs in I59's index, holon reads the receipt (the Upgraded, Initialized and AdminChanged logs the proxy emitted), the implementation's runtime code and the block's time. It writes them once, and checks them offline afterwards.
7. **Timeline (H8).** Each upgrade's matches against the basis, its version, and whether the reinitializers its version introduces ran in its own transaction. Also recorded: downgrades, coverage debt (unmatched upgrades, never smoothed over: Q18) and never-deployed versions.

I63 states no law, changes no catalog and reads no law, record or fact document. Its outcome paths are `gen/M3/history/` and `results/M3/history/`.

## Deviations from the plan's text, and why

- **All tags, not `v0.4.6`..`v0.6.3`.** The plan's range was what the checkout was believed to hold. The checkout has 26 tags. The proxy's 12 upgrades start in October 2024, a year before `v0.4.6`'s commit (November 2025), so the plan's range could not explain most of the timeline.
- **The on-chain timeline is fetched, not assumed.** Q18 was answered "both, cross-checked" after the plan was written. The I59 index gives the Upgraded transactions, and the keyless gateway I59 and I23 used gives the receipts and code.
- **MIG edges join versions, not tags.** 26 refs collapse to 11 code versions under the `deployed` configuration. An edge between two tags with equal code would be empty.

## What was known before this prereg (disclosed)

- **The basis**, computed by the instrument at the prereg, as BUILD_PLAN §0.1 requires: every ref compiled under every configuration, 11 versions, 10 edges, and two of them incompatible under H5:
  - **V2->V3:** `maxNumTxInChunk` is renamed `__maxNumTxInChunk` at slot 154, same type. H5 identifies entries by name, so a rename is a removal plus an overlapping addition.
  - **V10->V11, the cutover:** slot 151's `l1StakingContract` becomes `submitterContract` (both addresses). `batchDataStore`'s `BatchData` struct changes its fourth member from `signedSequencersBitmap` (uint256) to `submitter` (address). For every batch committed before the upgrade, `submitter` reads the low 160 bits of the old bitmap.

  No prediction is made about the basis. These are construction facts, and the laws half (I28: in-flight sets, G11V) and NAT (I29) inherit them.
- **The last upgrade's receipt** (block 26031669) was decoded while checking that the gateway serves receipts: an Upgraded log naming I23's implementation `0x213ce22b…` and an Initialized log. I23 had already recorded that implementation and its code (I63-R1).
- **The 12 upgrade blocks' timestamps** were fetched for a "newest tag before the block" date-rule prediction. That prediction was dropped before this commit: the launch upgrades (19-20 October 2024) precede `v0.4.0`'s tag commit (21 October) by a day or two, and the lead does not believe the rule.
- **A smoke build of the head:** runtime code of 19192 bytes, the deployed implementation's length.
- **Morph's deploy and upgrade scripts at the head commit:**
  - `contracts/deploy/013-DeployProxys.ts` creates proxies over `EmptyContract`, with the deployer as admin;
  - `020-ContractInit.ts` calls `initialize2` and `initialize3` as separate transactions on a fresh deployment;
  - `tasks/mainnet_upgrade.ts` prints `initialize2` calldata;
  - `tasks/proxy_upgrade.ts` runs `upgradeAndCall(initialize4)`.
- **Not read before this commit:** any other implementation's code, any other receipt, and any match of a deployed code against a build.

## Predictions (key I63 in `spec/M3/predictions.json`)

- **P1.** The first upgrade is the proxy's creation over the placeholder: no match, no Initialized log, and an AdminChanged log from zero.
- **P2.** The other 11 each match exactly one version, under `deployed` only.
- **P3.** Mainnet starts on the `v0.4.0` line, and the v0.2 versions are never deployed.
- **P4.** No downgrade.
- **P5.** Every reinitializer ran inside its own upgrade's transaction. `initialize2` and `initialize3` are guarded by nothing but `reinitializer(k)`, so a gap between upgrade and initialization would have left them callable by anyone.

**Regressions:**
- **R1:** the last upgrade is I23's implementation and code, matched to the head's version.
- **R2:** no law, record, catalog or earlier-milestone output changes, and the gates pass.
- **R3:** construction checks.

## Deliverables

- **`holon/frontends/solidity/history.py`**, generic: every target-specific name comes from the sidecar `spec/M3/lib/history.json`. It implements H1-H8, independently of `tests_m3/_i63.py`; the tests compare the two.
- **The CLI.** `python -m holon history extract|fetch|timeline [--check]`, with the exit codes of the contract. Only `fetch` touches the network, and it writes once. `--check` never writes.
- **Outputs:**
  - `gen/M3/history/morph_rollup.json`;
  - `results/M3/history/onchain.json` and `results/M3/history/code/<implementation>.hex`;
  - `results/M3/history/timeline.json`.

  All canonical JSON, byte-identical across runs.
- **`docs/iterations/I63.md`:** the report, with the timeline, every miss and every coverage-debt item stated plainly.

## Rules

- AGENTS.md throughout. Never edit a frozen file, `spec/M2`, `laws/`, `results/M0-M2`, `gen/M0-M2`, `replay/` or `holon/rules/`.
- The instrument, the sidecar and the basis are fixed at this commit. A wrong instrument is a Question plus an amendment line in `spec/M3/amendments.jsonl`, never a silent edit.
- A missed prediction is a result: report it, never adjust the rule or the inputs to make it hold.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
