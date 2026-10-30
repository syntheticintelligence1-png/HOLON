# I69 (= I36a): Bundle I's extraction and acquisition, no laws

Rendered from `docs/BUILD_PLAN.md` §4 I36 and its row I69 (whitepaper §10.1 Solidity, deployment history and linking, §8.7 refinement, §9.3 G8, §11.1 scope), and from the human answers Q12 (fetch the real legacy code; a stand-in is the last resort), Q18 (code-derived history cross-checked on chain) and Q19 (extracted facts are the input of every M3 law) in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (E1-E7, M1-M6, L1-L8, C1-C6, A1-A7), commands, formats, exit codes, shared files, commit rules and the definition of I69's own commits are in the docstring of `tests_m3/test_bundle_extraction.py`. The key's thresholds pin that docstring, the instrument `tests_m3/_i69.py`, I63's instrument, the sidecar `spec/M3/lib/bundle.json`, the basis `spec/M3/lib/bundle_basis.json`, the corpus's m1 part and twelve inputs by sha256. The base is `2ef07b6d`, the lead after I67's build, I72's prereg and the I25 commit-test fix (the prereg was drafted on `fde1f819` and rebased onto `e215fbf5`, `f5534775` and `2ef07b6d`; §"What was known" lists what was re-checked). The independent prereg review (`docs/iterations/I69_prereg_review.json`: no sign-off; major M1-M5, minor m1-m9) is folded into this prereg; `docs/iterations/I69_prereg_fold.json` says what changed for each finding.

## Why a separate key

BUILD_PLAN I36 (Bundle I: messenger, queue, Merkle, accounting, cutover) predicts eight results: O29, O30, O34, D7, D8, D9, O13 and O20's economic half. They span five rules (SORT, DISCH, PAR-lossy, NAT and a D9 that no rule produces). Four need a new or extended producer, so each is a catalog bump. Two blockers are independent of each other:
- **I28's versioned machine:** O13 and O20's economic half are about the cutover (V10 -> V11) and the legacy registry.
- **Q21's structural storage keys:** O34's blocking law, D8 and D9 are ∀ laws over mapping state, which I31 could not frame under the ∀-quantified keccak table.

Every one of them first needs what does not exist yet: the messenger, the queue, the whitelist and the Submitter extracted, a machine in which a call from one of them to another runs the callee's transitions instead of a free answer, and the legacy registry's real code (Q12). That work needs no rule, no catalog bump and neither blocker. So it goes first, under its own key, as I59 (= I23a) and I63 (= I28a) did. The split agreed on 2026-10-23:

| part | key | content |
|---|---|---|
| fix | I68 | Q21's structural storage keys in model3 (after I28's build) |
| **I36a** | **I69** | extraction, models, the linked machine and acquisition; no law |
| I36b | I36 | the laws over the current deployment: O29, O30, O34, D7, D8, D9, Q28's BMC rerun, and D4 if Q63 moves it there |
| I36c | I70 | O13 and O20's economic half over I28's versioned machine and I29's NAT, with L1Staking linked to the V10 Rollup |

I69 is numbered I69 only because prereg keys must be plain numbers. I36 keeps its number, its plan text and its predictions.

## Dependencies

- **Done, read here:** I19 (the Solidity frontend), I20 (the extracted Rollup, its harness, parameters and corpus), I23 (the call record naming the queue), I59 (the window and receipt hashes), I63 (the history mechanism, the cutover receipt, the on-chain snapshot and its instrument), I66 (its prereg re-scoped I32-R2 to I32's own commits, merged at `a0bfc521`; its build is the re-make precedent).
- **On the base:** I32's build (its five T32 records, whose generator closure holds I69's files), I67's build (Go frontend 0.2 and `goops`: two more files in every closure but holon-ir/0.1), I28's prereg (the laws half of versioned machines) and I72's prereg.
- **Either order:** I28's build (PR #50), which shares rule E3's tag-tree mechanism (its V5). If it merges first, I69 merges the lead and keeps one mechanism.
- **Beside it, no shared output:** I72's build (`gen/M2/evidence.json`, never written here), I29 and I80 (Bundle II's extraction).
- **After I69:** I68 (Q21's structural keys), I36 (= I36b, which also adopts the member documents into M3) and I70 (= I36c).

## What I69 does

1. **Extraction (E1-E7).** `holon bundle extract` writes one generated extraction sidecar and one transitions document per member, by I19's frontend:
   - at the pinned head `3e44e79`: the messenger (`L1CrossDomainMessenger`), the queue (`L1MessageQueueWithGasPriceOracle`), the whitelist (`Whitelist`) and the Submitter (`Submitter`);
   - at `v0.6.1` (`4a1607db`), the last tag that holds it: the legacy registry (`L1Staking`), compiled from that commit's tree, materialized from git objects with lazy fetching disabled (E3; the same mechanism as I28's V5, built once).

   The Rollup is a member as it is: the adopted document `spec/M2/facts/morph_rollup.extracted.json` is read, never rewritten. The frontend gains overload names (E2: `sendMessage_b2267a7b` and `sendMessage_5f7b1577`, also for called functions) and whatever constructs the five documents need. No earlier document moves (E6). The declaration `gen/M3/bundle/bundle.json` lists the members, the documents, their coverage entries and the static link rows (L2). `holon coverage --milestone M3` gains the four head members' entries (E5), so G8 on M3 covers them; the legacy registry's entry stays in the declaration, because CI's partial clone of the target holds the head's objects only.
2. **Models (M1-M6).** The evaluator of record (`holon.extracted_eval`) and model3 get additive extensions for the members' constructs:
   - push and pop on storage dynamic arrays, index reads and writes and lengths;
   - static arrays of sub-word elements;
   - `abi.encodeWithSignature` and `abi.encodeCall`;
   - ABI-encoded return data;
   - in model3, also non-constant shifts and the packed width of a loop-carried or calldata-array operand of `abi.encodePacked` (Verify.sol's fold).

   PRELUDE, `_COMMON` and `MODEL3_VERSION` do not change, and the adopted Rollup's typed and untyped models regenerate byte for byte. `holon bundle model` compiles each head member's document as `holon model --untyped` compiles one, and each model is refined on the real member (M4).
3. **The linked machine (L1-L8)** lives in `holon/bundle/`, outside every generator closure. It runs over the evaluator's programs of the members' documents:
   - its state is every member's raw storage and ETH balance;
   - a call to a member dispatches by selector (getters and receive included) and runs as a nested frame;
   - re-entry is allowed only into an action that writes no storage, else the step is unsupported, never guessed;
   - the depth limit is 8;
   - a call to a non-member is answered from the harness's record, as I20's env.calls.

   The Bend composition of the linked machine is I36b's, when a law needs it.
4. **Harness and corpus (C1-C6).** `replay/M3/bundle/` deploys the real bundle:
   - the Rollup, messenger, queue and Submitter behind OpenZeppelin 4.9.3 proxies;
   - the real Whitelist;
   - I20's verifier stand-in and I20's parameters and actors.

   The corpus (`gen/M3/bundle/corpus.json`) has three sources, each checked by the instrument: I20's 300 M1 traces (`holon.mreplay.random_corpus`, its sha256 pinned at the prereg), with sendMessage rows sent to the real messenger; the sidecar's 7 planted traces verbatim (rows, calls and relay steps whose withdrawal roots are poked into the Rollup's storage); and 120 random traces of 12 steps, generated by a rule written out in C3 (`random.Random(20261023)`, a fixed draw order, pools from the sidecar and earlier arguments only), which the instrument regenerates. Every step is compared in status, revert key, return data, every member's storage at every touched slot, logs, balances, outgoing calls and the frames. The harness's frames are committed per step (`results/M3/bundle/steps.json`), and the instrument recounts the record's reach counts from them. `holon bundle refine` is the one command that runs forge.
5. **Acquisition (A1-A7; Q12, Q18).**
   - `holon bundle history` builds L1Staking at the 24 pinned tags that hold it, under I63's three configurations, in I63's history format.
   - `holon bundle fetch`, once and holon's only network step, reads from I59's window start to the fetch block:
     - the Upgraded, AdminChanged and Initialized logs of the registry proxy `0x0dc417f8…43f7` and the Submitter proxy `0xf2d50000…bef6` (both named by I63's cutover receipt);
     - the same logs of the queue proxy `0x3931ade8…c1ef` (named by I23's record) and of the messenger proxy (the queue's `MESSENGER` word);
     - each proxy's EIP-1967 implementation slot at the fetch block, which anchors the log scan's end;
     - every upgrade's receipt in I59's canonical form, and every implementation's code;
     - the whitelist the queue names (its `whitelistChecker` word), and its code.
   - `holon bundle timeline` matches every implementation by I63's metadata-stripped identity against the registry's versions and the members' head builds.
   - Then the instrument, not holon, reads it all again from a second host (`python -m tests_m3._i69 --second-read`, A7) and commits `results/M3/bundle/second_read.json`; a test compares it with the snapshot.

The predictions are decided on the committed outputs and on the instrument's recomputations, never on holon's derived fields: the timeline is rebuilt from the snapshot's raw logs, the committed receipts and code; the corpus is checked against its rule; the reach counts are recounted from the harness's frames. I69 states no law, changes no catalog and adopts no document into M3's derivation: `spec/M3/lib/derive_extracted.json` stays I24's, so M3's evidence set, its laws and their records do not move. The outcome paths are `gen/M3/bundle/`, `results/M3/bundle/`, `replay/M3/bundle/` and `docs/iterations/I69.md`.

## Deviations from the plan's text, and why

- **No laws.** The plan's eight predictions stay with I36 and I70 (above).
- **The legacy registry is extracted, not stood in.** Q12 asks for the real code. `L1Staking.sol` is in the local checkout at every tag from `v0.2.0-beta` to `v0.6.1`. It was deleted only at `v0.6.3`, so the gap map's "absent from the pinned checkout" is true of the head alone. Its proxy is named by I63's committed cutover receipt (the `SubmitterContractUpdated` log's old registry). The deployed implementation is matched against the tag builds by metadata-stripped bytecode, which is Q12's condition for extracting the source with the I17/I19 frontends.
- **The explorer's verified source is not fetched by the build.** No explorer key is configured. The bytecode match against the tag builds is offline-checkable and decides what Q12 asks the source for. The build review may read an explorer's verified source and compare it with `v0.6.1`'s unit, reporting a difference under Surprises.
- **L1Staking is extracted but not modelled or linked here.** Its link is to the V10 Rollup, which is I28's versioned machine, so I70 links it. Its document records the debt and loops that model must face.
- **The Merkle check and the accounting are extracted, not proved.** `Verify.sol`'s fold is a cost term of the messenger's document and a part of its model, refined on the real code. D7 and D8 are I36b's.
- **The linked machine is evaluator-level.** A Bend linked composition would be a kernel term over five models (about 15k lines for the Rollup alone, Q22 and Q34); I36b builds it when a law needs it. I69's machine decides refinement, which is what I69 predicts.
- **The member documents are not adopted here.** The plan's I36 lists `spec/M3/facts/morph_messenger.extracted.json` as a deliverable. I69 writes the documents under `gen/M3/bundle/documents/`; I36 (= I36b) adopts the head members' documents into M3's derivation, at `spec/M3/facts/morph_<member>.extracted.json`, when its laws need them.

## What was known before this prereg (disclosed)

**Nothing was read from the network** for this prereg or for the design note before it. In `/root/work/morph`, a partial clone (`blob:none`), every git command ran with `protocol.allow=never`, `gc.auto=0`, `maintenance.auto=false` and `GIT_TERMINAL_PROMPT=0`, so a missing object fails instead of being fetched (the I63 incident). The pack directory's listing hash, `c3cdea1b5d4e95d29912def84c87843c`, was the same before and after.

**Sources read** (git objects present locally):
- at the head `3e44e79`:
  - `L1CrossDomainMessenger.sol`, `CrossDomainMessenger.sol`, `Verify.sol`, `L1MessageQueueWithGasPriceOracle.sol`, `Whitelist.sol`, `OwnableBase.sol` and `Submitter.sol`;
  - the interfaces they call (`IL1MessageQueue`, `IWhitelist`, `IRollup`, `IRollupSubmitterView`, `ICrossDomainMessenger`);
  - the adopted Rollup document;
- at `v0.6.1`: `L1Staking.sol` (`165fec18`), `IL1Staking.sol`, `Staking.sol`, `Types.sol`, `Predeploys.sol`, `IL2Staking.sol` and both `ICrossDomainMessenger.sol` blobs (`9ec8f339`, `8d0ee03f`);
- V10's `Rollup.sol` (`14aae181`), read for the design note.

P3's debt lists, P4's structures and P6's link rows for the four new head members come from these readings. They were not computed by running anything.

**Tree listings** (`git ls-tree`, no blob read) over the 25 pinned tags and the head:
- `L1Staking.sol` and five of its six repository imports are one blob each from `v0.4.0` to `v0.6.1`.
- `ICrossDomainMessenger.sol` is `9ec8f339` at `v0.4.0`..`v0.4.2` and `8d0ee03f` from `v0.4.3` on. The two texts differ in the pragma line alone. The design note said `v0.5.0`; that was wrong.
- The head's `L1CrossDomainMessenger.sol` is the blob of every tag from `v0.4.2` on.
- The head's `L1MessageQueueWithGasPriceOracle.sol` is the blob from `v0.4.10` on.
- `Submitter.sol` first appears at `v0.6.3`.
- `Whitelist.sol`, `Verify.sol`, `CrossDomainMessenger.sol` and `OwnableBase.sol` are one blob at every tag.

**Committed records read:**
- I63's `results/M3/history/onchain.json` and `timeline.json`. Every pre-cutover Rollup implementation matched under `hardhat`, and the cutover's (V11) under `deployed` alone. The proxy was created at block 20996846 over the placeholder `0x98df3206…` by `0x2818a3af…`.
- I63's cutover receipt, whose `SubmitterContractUpdated` log names the old registry `0x0dc417f8…43f7`, the Submitter proxy `0xf2d50000…bef6` and the index 60477.
- I23's `results/M2/historical/trans.json`. Its most frequent address, `0x3931ade8…c1ef`, occurs 1772 times, equal to its IL1MessageQueue call count.

**Runs (no network):**
- The basis: `python -m tests_m3._i69 --write` built L1Staking at the 24 tags and the four members at the head, under I63's three configurations (about 73 s). These are construction facts, not predictions. They give:
  - three registry versions: V1 `v0.2.0-beta`, V2 `v0.2.1`, V3 the 22 tags `v0.4.0`..`v0.6.1`, the last under every configuration;
  - V3's immutables `MESSENGER` and `OTHER_STAKING`;
  - the members' code identities: the Whitelist's `hardhat` and `foundry` builds are equal, and its `deployed` build differs.
- The instrument's rule E2 over solc's AST, on the Rollup only: it gives the adopted document's 33 action names. It was not run on a new member.
- Rule L2 on the adopted document: its 12 Rollup rows.
- The relay literals of the seed step `S2_relay` 1.
- `holon model --milestone M3`, typed and untyped, into a scratch directory: byte-identical to the committed models.
- `holon extract solidity --sidecar spec/M2/lib/extract_rollup.json --check` and `holon coverage --milestone M3 --check`: both up to date.

**Not run:** the frontend on any new contract (so no new document, coverage count or extraction error was seen), model3 on a new document, forge, Bend, any gate, any network read.

**Re-checked after rebasing onto `e215fbf5`** (I32's build: 36 files, among them `holon/profile.py`, `holon/gen/profile.py`, `holon/rules/disch_profile.py`, `holon/analysis/abstraction.py`, `holon/js/profile.mjs`, `holon/__main__.py`, T32's laws, records and generated files, `gen/M3/disch/classification.json` and two I32 amendment lines):
- none of the twelve pinned inputs, the sidecar, `config/holon.json` or `gen/M3/coverage.json` moved, and the basis recomputes byte for byte;
- the closures, recomputed: holon-ir/0.1 6, 0.2 122, 0.3 123, GEN3 122 (with GEN_FACT 132, GEN_UNDO 125, GEN_DISCH 127), and I32's GEN_PROFILE 124, equal to `holon.profile.generator_files`. Every closure but holon-ir/0.1 holds `holon/extracted_eval.py`, `holon/machine.py`, `holon/sorts/model3.py`, `holon/sorts/evaluate3.py`, `holon/frontends/__init__.py` and `holon/frontends/solidity/{__init__,compile,transitions}.py`. None holds `holon/__main__.py`, `holon/coverage.py`, `holon/gate.py` or `holon/frontends/solidity/history.py`, so `holon/bundle/` can be dispatched from there and stay outside every closure (R4);
- the five T32 records are current at the base (`generator_sha256` `f043522b…`, `holon.profile.generator_sha256` with the hints `spec/M1/policy_hints.mjs`), and their only timing keys are named `seconds`;
- I32-R2 in its unamended form still passes with this prereg on top.

**Re-checked after rebasing onto `2ef07b6d`** (I66's build, F40, I65's build, I28's prereg, I67's prereg and build, I72's prereg, the I25 fix; 27 commits):
- none of the twelve pinned inputs, the sidecar's inputs, `config/holon.json`, `gen/M3/coverage.json`, `tests_m3/_m3.py`, `tests_m3/_i63.py`, `tests_m2/_keccak.py` or `tests/_util.py` moved; the basis recomputes with the same builds (only its `sidecar_sha256` moved, with the sidecar);
- the closures, recomputed: holon-ir/0.1 6, 0.2 127, 0.3 128, GEN3 126 (with GEN_FACT 136, GEN_UNDO 129, GEN_DISCH 131), GEN_PROFILE 127, equal to `holon.profile.generator_files`. I67's build added `holon/diagram/goops.py` and `holon/gen/goloop.py` to every closure but holon-ir/0.1. The candidate files and the files in no closure are as before;
- records: M1 16 (current, `27f717ba`), M2 13 (current, `d1fd1e37`; I65 added one), M3 135 (already trailing: five digests), T32 5 (current, `bd51e9b7`);
- the lead's CI run 40116936084 on `2ef07b6d` passed all 11 jobs, gate-M3-partial included (F40 made G11V pass on Q36's law).
- R1 was red here as first written: since F40 (`5b369d4c`), `holon.sorts.run3` writes the typed model's init with the deployment's code table (`init.code`, `holon.sorts.envcode3`), and `holon model --milestone M3` writes it without. R1 now compares that init with the committed one less `code`; the `.bend` models are still compared byte for byte.

**Folded from the prereg review** (each finding's change is in `docs/iterations/I69_prereg_fold.json`):
- own commits follow LANE_RULES' one-PR rule, shown on toy repositories (M1, M2);
- the timeline is rebuilt from raw logs, committed receipts and code, with the proxy addresses, the whitelist slot and the EIP-1967 slot checked (M3);
- the corpus is pinned and checked: m1 by sha256, seed verbatim, random by an exact rule the instrument regenerates; per-step frames are committed and recounted (M4, m4);
- member refinement compares return data and every touched slot (M5);
- solc's construction facts left P4, P6 and P7 for R5 and are pinned for all five documents, L1Staking's storage among them (m1);
- R4 scans every holon line I69 adds, and the hosts (m2); I69's amendment lines are allowed (m3);
- the second read is committed and tested (m5); environment reads and dispatch order are specified (m6); later keys own the re-make of I69's outputs after they change the frontend or model3 (m7); the plan's rows are updated (m8); R1 regenerates I20's M2 model (m9); lookups use `--full-history` (n2).

The fold ran, without the network and on no new member output: the instrument's `interfaces` (solc's ABI, AST and layout for the five members at their commits; about 1 s), `holon.mreplay.random_corpus` for the m1 part (twice, 103 s each, byte-identical: 300 traces, 2432 rows, sha256 `0b82e5f5…`), the instrument's random part (sha256 `5e4ea3d5…`), the timeline on a fabricated snapshot with matching stubbed (plumbing and seven refusals), and the one-PR toy repositories. The only network calls were `eth_blockNumber` on the three hosts, to check they answer.

**Code readings for the findings lane** (Question Q67; none is a prediction):
- **The legacy deposit drifts.** `register` takes `stakingValue` at the time (`L1Staking.sol:165`), while `claimWithdrawal` and `slash` count the current one (`:325`, `:224`, `:227`).
- **The legacy slash needs the fee waiver.** `slash` sends `_msgRemoveStakers` through the messenger with no value (`:486-491`), and the messenger requires `msg.value >= fee`. So a challenger can win under V10 only when L1Staking is whitelisted or `l2BaseFee` is 0.
- **Some bitmaps make the legacy slash revert.** `getStakersFromBitmap(b)` reverts with Panic 0x11 when no bit 1..255 of `b` is set: the `uint8` loop counter overflows after 255 (`:426`). So `slash(0)` and `slash(1)` revert.
- **The BLS check is a stub.** `verifySignature` returns true (`:333-341`).
- **A relay can carry ETH into the Rollup.** A relayed message can send value into `Rollup.receive`, which accounts for nothing.

## Risks for the build

1. **Frontend constructs.**
   - The messenger has the overloads, a mapping of structs (`replayStates`) and `abi.encodeWithSignature`.
   - The queue has a storage dynamic array and an inline-assembly RLP encoder: Yul functions, a Yul loop at `:154-157`, `mstore8`, shifted `mstore`s and `calldatacopy`.
   - The Submitter has a low-level transfer.
   - L1Staking has `address[255]`, a struct with a `bytes` member, `uint8` loops, `1 << i` and `abi.encodeCall`.
   - The queue's `appendEnforcedTransaction` reads `_sender.code.length` and the Submitter's `initialize` reads `rollupContract_.code.length`: the frontend's `["code", a]` term, answered from the deployment record (C5's environment reads).

   A construct the build leaves unsupported is debt, which misses P3, and is never smoothed over.
2. **model3 gaps.**
   - It refuses non-constant shifts today (`Verify.sol` `(index >> height) & 1`, the queue's `shl(mul(8, sub(32, len)), v)`).
   - It has no `wbyte`, calldata load or offset ops, push, pop, `encodeWithSignature` or `encodeCall`.
   - Packed widths of carried names are untyped (`model3.py:1061`).

   Model debt misses P5. Each extension must leave the adopted Rollup's models byte-identical (R1), or every M3 law needs a rebind.
3. **The linked machine.** Nested frames, revert data through high-level calls, callok decoding and value moves must follow the EVM exactly, or P6 misses. The re-entry rule is conservative by design: an unsupported step is a disagreement, and also a miss. Random steps reach a nested call on a member already on the stack with a selector of no action (for example after `queue.updateWhitelistChecker(@messenger)`): L3's dispatcher revert decides it before L5.
   - The harness's frames come from forge's state-diff recording (`vm.startStateDiffRecording`), declared in the harness for the pinned forge; a frame's ok is "kept" (C2), which forge marks for a reverted ancestor too.
4. **Corpus reach (P7).** The planted traces must pass real guards:
   - fees and the whitelist for `replayMessage`;
   - the poked withdrawal root for `proveAndRelayMessage`;
   - the gateway caller w8 for `appendEnforcedTransaction`;
   - the Rollup as caller for `popCrossDomainMessage`;
   - a successful challenge for the Submitter's `slash` and its transfer into `Rollup.receive`.

   A row no trace reaches is a miss, never a corpus edit after the prereg.
5. **The re-make.**
   - I69 edits files of the holon-ir/0.2 and 0.3 closures (and of GEN3, GEN_FACT, GEN_UNDO, GEN_DISCH and I32's GEN_PROFILE). So every M1 and M2 record is re-made, with I40's filter stage in the same commit.
   - The five T32 records (I32's, on the base) are re-made by `holon profile --milestone T32`: I32's GEN_PROFILE closure (127 files at the base `2ef07b6d`) holds every closure file I69 is expected to edit.
   - No M3 record is re-made, so they trail the closures until the next M3 re-make, as after I66.
   - `holon/lean.py` and `holon/gen/lean_*.py` import none of the modules I69 extends, so the lean4 entries rebuild as they are.
6. **CI.**
   - G8 on M3 now compiles four more contracts.
   - G3 scans the member models for escape hatches (I30's N6).
   - `tests-m3-catalog` must stay green.
   - The legacy registry's tree is not in CI's partial clone, which is why E5 keeps it out of the report.
7. **The network.** The keyless gateway serves logs, receipts and code at the latest block, but no old state. Ranges are chunked as I59 did. A second provider re-reads every receipt and code at review (A7); a disagreement makes the predictions that read it UNKNOWN.
8. **Coordination.**
   - **I28's build (PR #50).** It extracts tag trees by the same mechanism (whichever key merges second merges the other and keeps one). Its V6 compiles V3..V10 with model3, and I69's additive extensions can only remove model debt there. After it lands, G11V on M3 fails on the lead ("in-flight: 0 of 8 edges inhabited", its P5 miss): a base item for R3.
   - **The lead.** I69 merges the lead by merge commits, the lead's lines first in append-only logs, and regenerates what a merge makes stale.
   - **I68.** It may change model3's storage representation. The member models follow it, and every storage claim here is in real slots (M6).
   - **Later keys (m7).** A key that changes the frontend, the evaluator, model3, evaluate3 or `holon/bundle/` so that a bundle `--check` differs re-makes `gen/M3/bundle/` and `results/M3/bundle/` under its own commit rules; until then I69's R5 `--check` tests are expected red, and that key says so.

## The branch and commit sequence (one PR)

0. The BUILD_PLAN row, the prereg commit C_K (key, prompt, contract, instrument, sidecar, basis), then one commit adding the prereg review and the fold notes (`docs/iterations/I69_prereg_review.json`, `docs/iterations/I69_prereg_fold.json`). Pushed, and the draft PR opened, before any implementation.
1. Frontend and extraction: E2, E3 and `holon bundle extract`, giving the sidecars, documents and declaration. Then E5 in `holon/coverage.py` and the four entries in `gen/M3/coverage.json`.
2. Evaluator and model3 extensions (M1, M2), and `holon bundle model`.
3. The linked machine in `holon/bundle/`, the harness in `replay/M3/bundle/`, then `holon bundle corpus` and `holon bundle refine`.
4. Acquisition: `holon bundle history`, `fetch` (once) and `timeline`; then the instrument's second read.
5. The re-make. `holon run --milestone M1` and `--milestone M2`, then `holon refute --milestone M3 --only filter`, in one commit. Then `holon profile --milestone T32`.
6. CI on the PR, then the report, `docs/iterations/I69.md`, with every miss and every debt item stated plainly: the branch's last own commit, written once.

Own commits are the non-merge commits of `git log --first-parent <C_K>..<the report>`. The branch takes the lead only by merge commits and reaches the lead as the second parent of a merge commit.

## Predictions (key I69 in `spec/M3/predictions.json`)

P1 and P2 are decided on the instrument's timeline, rebuilt from the snapshot's raw material (A6). When the anchor test (A7: the instrument's second read against the snapshot) fails, both are UNKNOWN.

- **P1, the legacy registry is recovered.** The registry proxy has exactly two Upgraded logs in the window.
  - The first is its creation over I63's placeholder `0x98df3206…` by the Rollup proxy's deployer `0x2818a3af…`: the receipt's contractAddress is the proxy, with one AdminChanged from zero to the sender, no Initialized and no match.
  - The second, before block 26031669, sets an implementation that matches V3 (`v0.4.0`..`v0.6.1`) under `hardhat` alone. Its transaction logs Initialized(1). Its immutables read `OTHER_STAKING` = `0x5300…0015` (the L2 staking predeploy) and `MESSENGER` = the queue's `MESSENGER` word.

  *Derivation:*
  - Morph's scripts create every proxy over the placeholder from one deployer; I63 saw this for the Rollup proxy.
  - L1Staking's code is one identity across all 22 tags of the mainnet era, so no upgrade was needed after launch.
  - The launch-era pipeline is `hardhat`: every pre-cutover Rollup implementation matched under it.
  - The legacy registry used the same messenger proxy as the queue.
  - *Disclosed:* `OTHER_STAKING`'s value follows from the constructor (`Predeploys.L2_STAKING`, `L1Staking.sol:93`), read before the prereg. The word is still read on chain, because the code identity masks immutables.
- **P2, the live bundle is the modelled code.** In the window:
  - the queue proxy's last implementation matches the queue's head build under `hardhat` alone, with `ROLLUP_CONTRACT` = the Rollup proxy;
  - the messenger proxy's last implementation matches its head build under `hardhat` alone;
  - the Submitter proxy's last implementation matches its head build under `deployed` alone;
  - the whitelist the queue names matches under `hardhat` and `foundry` (equal builds), not under `deployed`.

  *Derivation:* the head sources of the queue (from `v0.4.10`), the messenger (from `v0.4.2`) and the Whitelist (every tag) are hardhat-era blobs. `Submitter.sol` appears with the cutover, whose Rollup implementation matched under `deployed` alone.
- **P3, five documents and their coverage.** No member debt, no unaccounted statement, and exactly these debt entries (`thresholds.debt`), which `holon coverage --milestone M3` lists for the four head documents beside the unchanged Rollup entry:

  | member | entries | what they are |
  |---|---|---|
  | messenger | 18 | the queue calls at :198, :208, :209, :286, :290, :298 and :320; `withdrawalRoots` at :147; the five low-level transfers at :161, :203, :240, :293 and :313, each an external_call and a value_transfer |
  | queue | 1 | `isSenderAllowed` at :115 |
  | whitelist | 1 | the loop that writes `isWhitelisted`, :25-28 |
  | submitter | 4 | :134, :172, and the transfer at :178 |
  | l1staking | 10 | six storage-writing loops, the transfer at :467, and the two `ICrossDomainMessenger.sendMessage_b2267a7b` calls |

  *Derivation:* reading the sources under I19's coverage rules, which make every external call, value transfer and storage-writing loop debt at its site and nothing else unsupported.
- **P4, the documents are as read.** Per document: the loop records per action and the loop spans of the cost terms (`thresholds.structure`'s `loops` and `cost`). The action names (E2's two `sendMessage` names; 16, 17, 4, 15 and 27 actions), the own families, the inherited counts and the constants are solc's construction facts, checked under R5 (the review's m1).

  *Derivation:* reading the sources (most-derived first; I19's rules). For example, the queue's Yul loop is inlined at each use, giving 5 or 6 records with one span, and `slash` holds its own loop plus `getStakersFromBitmap`'s two.
- **P5, member models.** The four head members' models compile with no model debt. On every top-level corpus step on its member, each model agrees with the real code (status, revert key, return data, the member's storage at every touched slot, logs), with no unsupported step.
- **P6, the linked machine.**
  - The declaration's static links are 28 rows: Rollup 12, messenger 11, Submitter 4, queue 1; 22 actions, 5 getters and 1 receive. The 16 non-Rollup rows are predicted by reading; the Rollup's 12 are rule L2 on the committed document (construction).
  - On all 427 traces, the linked machine agrees with the real bundle in every observable and in its frames, with no disagreement and no unsupported step, in the record and in every compared step of `steps.json`.

  *Derivation:* the Rollup's rows come from rule L2 on the committed document, the others from reading. Agreement holds because the member call graph has no writing re-entry. Messenger -> queue -> whitelist and Rollup -> queue and Submitter call down only. The Submitter calls the Rollup's getters and its empty receive.
- **P7, corpus reach.** Decided on the instrument's recount of the harness's frames. Every link row is executed with a kept frame at least once. Each of the 49 non-initializer actions of the four head members (a count of rule E2) ends ok in some kept frame.

**Regressions:**
- **R1** (green at the prereg). The adopted Rollup document re-extracts byte for byte, and `holon coverage --milestone M2 --check` passes. The typed and untyped M3 models of the adopted document and I20's M2 model (`gen/M2/extracted/`) regenerate byte for byte. The twelve pinned inputs keep their sha256, and the Rollup's M3 coverage entry is unchanged.
- **R2.** The commit rules over the one-PR own commits: no change to a frozen root, `laws/`, `spec/` (but I69's appended amendment lines), `holon/rules/`, replay or gen files outside I69's own (but `gen/M3/coverage.json`, which only gains entries), or results outside `results/M3/bundle/` but M1, M2 and T32 records, re-made in `generator_sha256` and seconds alone.
- **R3.** Every CI job that passed at the base (run 40116936084: all 11) passes on the PR, and a job fails only on an item it fails on at the lead the branch last merged (after I28's build: G11V's in-flight sets), with G8 covering the four head documents. The full M3 gate is not claimed: its G1 fails on the M3 records' staleness.
- **R4** (construction). `holon/bundle/` and every line I69 adds under `holon/` are generic: no target, member function, address or host, no test import; no generator closure imports `holon/bundle/`.

**Construction checks, not scored (R5):**
- the instruments and the sidecar's committed facts;
- the 22-tag unit;
- rule E2 on the Rollup;
- solc's structure of every document (action names, own families, inherited entries, constants), pinned and carried by the documents;
- the generated sidecars and E2 over solc's AST for every member;
- `--check` reproduction of `extract`, `model`, `corpus`, `history`, `fetch` and `timeline`;
- the links by rule L2;
- the corpus by rule C3 (m1 pinned, seed verbatim, random regenerated);
- the history equal to the basis;
- the anchor: the instrument's second read agrees with the snapshot (else P1 and P2 are UNKNOWN).

## Earlier tests amended at this prereg

None.
- I69 adopts no document, so I24's and I25's pins of M3's documents, models, evidence set and records hold.
- It adds no rule, law or catalog.
- Its outputs live under new paths, and every shared file changes only as the contract says.
- I32-R2 was re-scoped by I66's prereg (merged at `a0bfc521`) to I32's own commits found by ancestry path, so I69 adds no amendment of it.

An earlier test that fails on I69's outcomes is a miss, reported.

## Deliverables

- `holon/bundle/` (the linked machine, the corpus, the refinement, acquisition) and the frontend, evaluator, model3 and coverage extensions. All are generic: every contract, function, address, slot and host comes from the sidecars, the documents or the compiler.
- `python -m holon bundle extract|model|corpus|refine|history|fetch|timeline [--check]`, with the contract's exit codes. Only `fetch` touches the network, once. `--check` never writes.
- The outputs under the outcome paths, the shared files changed only as the contract says, the build review and `docs/iterations/I69.md`.

## Questions for the human

- **Q65 (anchors and the verified source).** These reads have no anchor in the repository:
  - the legacy registry's two receipts and its implementation's code;
  - the live members' receipts and code.

  After the fetch, the instrument re-reads them from a second provider (A7), commits that read, and a test compares it with the snapshot; the EIP-1967 implementation slot anchors the log scan's end. Q12 also mentions the explorer's verified source, but no explorer key is configured, and the build matches the tag source by metadata-stripped bytecode instead. Is the committed second read an acceptable anchor, and is the bytecode match an acceptable substitute for the verified source? Or should the build use an explorer key or archive endpoint that you provide?
- **Q66 (history of the other members).** The messenger, queue, whitelist and Submitter are modelled at the pinned head only. P2 checks that each proxy's last implementation in the window is that build, and the timeline lists every earlier implementation unmatched, as coverage debt. Should a later key, at the latest I70 for the cutover-era bundle, match those earlier implementations to tag builds (an I63-style history per member)? Or is "modelled at the head; the live code matches" an acceptable stated assumption?
- **Q67 (findings).** Should the five code readings above go to the findings lane's review, as Q60 asks for I63's findings? Should I36b and I70 predict the ones in their scope, as disclosed readings?
  - the legacy deposit drift;
  - the legacy slash's dependence on the fee waiver;
  - the slash revert on bitmaps 0 and 1;
  - the BLS stub;
  - the relay into `Rollup.receive`.

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, the adopted Rollup document or its sidecar, `spec/`, `laws/`, `holon/rules/`, or any earlier key's output.
- The instrument, the sidecar and the basis are fixed at the prereg. A wrong instrument is a Question plus an amendment line in `spec/M3/amendments.jsonl`, never a silent edit.
- A missed prediction is a result. Report it; never adjust a rule, an input, the corpus or a budget to make it hold.
- The target repository is read through git objects with lazy fetching disabled, and is never written. A missing object refuses; it is never fetched.
- Never fetch, clone or read `scroll-tech/*` (the messenger and queue are Scroll-derived; Q7 seals Scroll's ScrollChain) or `spec/heldout/`.
