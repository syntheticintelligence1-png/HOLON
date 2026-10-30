# I80 (= I37a): Bundle II's extraction and acquisition, no laws

Rendered from `docs/BUILD_PLAN.md` §4 I37 and its row I80 (whitepaper §10.1 Solidity and linking, §8.5 HypC, §8.7 refinement, App. D cost, §5.7 self-controlled enabledness, §11.1 scope), and from the human answers Q12 (real code over stand-ins), Q18 (code-derived history cross-checked on chain) and Q19 (extracted facts are the input of every M3 law) in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

The exact rules (E1-E6, M1-M4, L1-L8, C1-C6, A1-A3), commands, formats, exit codes, shared files, commit rules and the definition of I80's own commits are in the docstring of `tests_m3/test_bundle2_extraction.py`. The key's thresholds pin that docstring, the instrument `tests_m3/_i80.py`, I63's instrument, the sidecar `spec/M3/lib/bundle2.json`, the basis `spec/M3/lib/bundle2_basis.json` and eleven inputs by sha256. The base is `2ef07b6d`, the lead.

## Why a separate key

BUILD_PLAN I37 (Bundle II: router, public input, HypC, calibrated cost) predicts O3 REFUTED, O23 REFUTED with F(PI, parent lbn) = 64 bits, calibrated costs within 5% of forge gas at backlogs 1..64, and O35. Its laws depend on I36 (Bundle I) and I32. What they read does not:
- the verifier router extracted, modelled and linked with the Rollup, so that a proof check runs the router's transitions instead of a free answer;
- the zkEVM verifier's extraction, so the circuit's debt is named before I37 states it as HypC;
- the public-input term and the loop records, which are I37's PI = K(...) and its cost expressions;
- notes on what the deployed router and verifiers are.

So this goes first, under its own key, as I69 (= I36a) does for Bundle I. I80 is numbered I80 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys). I37 keeps its number, its plan text and its predictions.

## Dependencies

- **Done, read here:** I19 (the Solidity frontend), I20 (the adopted Rollup document, its harness, deployment parameters and base corpus), I30 (model3, evaluate3), I63 (the committed receipts, the pinned tags, the compiler configurations and the code identity).
- **Parallel:** I69 (= I36a, Bundle I). It writes `gen/M3/bundle/`, `spec/M3/lib/bundle*.json` and `holon/bundle/`, and extends the frontend, the evaluator and model3. I80 uses only its own paths (`gen/M3/bundle2/`, `spec/M3/lib/bundle2*.json`, `holon/bundle2/`, `replay/M3/bundle2/`, `results/M3/bundle2/`) and edits no closure file. Both add a dispatch line to `holon/__main__.py`; whoever merges second reconciles.
- **After I80:** I37 proper (the laws), which also needs I36 and I32.

## What I80 does

1. **Members.** Found as I69 found Bundle I's, from the code at the pinned head and committed records:
   - The Rollup's COMMIT edge `IRollupVerifier(verifier).verifyAggregateProof` (Rollup.sol:779-784, in commitBatchWithProof, proveCommittedBatchState and proveState) is implemented at the head by one contract, `MultipleVersionRollupVerifier` (the router).
   - The router calls `IZkEvmVerifier(_verifier).verifyBatch`, implemented at the head by one non-test contract, `ZkEvmVerifierV1` (with `SP1Verifier` and the generated `PlonkVerifier`).
   - `RollupVerifier.sol` is a library no non-test contract imports at the head, so it is not a member.
   - I63's committed receipt of the Rollup proxy's initialization logs `UpdateVerifier(0, 0x87c1…dcf6)` at block 20998835: the router the Rollup was deployed with.

   The members are the Rollup (the adopted document, as it is) and the router; the zkEVM verifier is extracted only. It is the circuit oracle: whitepaper §8.5 states circuits as hypothesis predicates (HypC_v), so I80 names its debt and I37 states its hypothesis.
2. **Extraction (E1-E6).** `holon bundle2 extract` writes one generated sidecar and one transitions document per extracted member, by I19's frontend, unchanged. Each member's extraction is bounded by the sidecar's 1800 s budget, and an error or timeout is debt. The declaration `gen/M3/bundle2/bundle2.json` lists the members, the documents, their coverage entries, the static link rows (L2), the public-input view (E4) and the cost sites (E5).
3. **Models (M1-M4).** `holon bundle2 model` compiles the router's document with model3's untyped machine. holon/bundle2 adds what the router needs and model3 lacks: storage dynamic arrays (index, length, push, pop). It adds them by an additive extension that lives outside every generator closure and changes nothing model3 emits for a document without such arrays. The model is checked by the pinned Bend and refined on the real router through evaluate3 (M3).
4. **The linked machine (L1-L8).** It is evaluator-level, in `holon/bundle2/`, over `holon.extracted_eval`'s programs of the members' documents (with the same extension):
   - a call whose receiver is a member runs that member as a nested frame (dispatch by selector, getters included);
   - re-entry into a writing action is unsupported, never guessed;
   - a call to a non-member is answered from the harness's record;
   - a call to an account without code reverts as the compiler's checks make it.
5. **Harness and corpus (C1-C6).** `replay/M3/bundle2/` deploys I20's Rollup deployment with the real router as its verifier (versions 0-2 mapped to a stand-in Z1 that accepts proof byte 1, as I20's verifier stand-in did; Z2 accepts byte 2). The corpus has three sources:
   - I20's 300 m1 traces;
   - five planted traces: router updates, lookups and ownership, proofs through the Rollup after verifier updates, a challenge and its proof, and a router whose rollup word points to itself or an EOA;
   - 60 random traces of 10 router or proof steps.

   Every call step is compared in status, revert key, return data, every member's storage, logs and frames. `holon bundle2 deploy` and `holon bundle2 refine` are the only commands that run forge.
6. **Acquisition notes (A1-A3).** `holon bundle2 acquire` writes `gen/M3/bundle2/acquisition.json`:
   - the anchor (the router named by the Rollup's initialization receipt);
   - the blobs of every member's units at I63's 25 pinned tags and the head (the router's unit is one blob from v0.4.1 on; the SP1 and Plonk sources change at v0.4.2, v0.4.3, v0.5.0 and v0.5.6);
   - the head builds' code identities under I63's three configurations;
   - what remains to read on chain.

   Nothing is fetched.

The outcome paths are `gen/M3/bundle2/`, `results/M3/bundle2/`, `replay/M3/bundle2/` and `docs/iterations/I80.md`.

## Deviations from the plan's text, and why

- **No laws.** The plan's four predictions stay with I37.
- **The zkEVM verifier is extracted only.** It is the circuit, which the whitepaper treats as an oracle under HypC. Modelling 1100 lines of Plonk Yul would model the oracle, not the protocol. The harness answers the router's verifyBatch with stand-ins, as I20 answered the Rollup's verifier.
- **No calibration.** The cost sites (E5) are the extraction half of "calibrated cost". Measuring forge gas and fitting c0 + Σ c_l · iters_l is I37's prediction ("within 5%"). Measuring here would make it observable before I37's prereg.
- **No network read, no coverage entry.** Acquisition is notes from committed records and git objects. G8's coverage report gains the router after I69's E5 lands; a later key generalizes it.
- **The model3 extension lives under holon/bundle2/.** Editing model3 or the evaluator would move every generator closure and force a re-make of M1, M2 and T32 (I69 does that for its own extensions). Keeping I80's additions outside the closures leaves every record current. A later key can fold them into model3 when I69's push and pop land.

## What was known before this prereg (disclosed)

**Nothing was read from the network.** In `/root/work/morph` (a partial clone) every git command ran with `protocol.allow=never`.

**Sources read** (git objects present locally) at the head `3e44e79`:
- `MultipleVersionRollupVerifier.sol`;
- `ZkEvmVerifierV1.sol`, `SP1VerifierPlonk.sol`, `PlonkVerifier.sol` (its outline, its Yul builtin counts and its staticcall sites);
- the interfaces;
- in `Rollup.sol`: `_verifyProof`, the three proof actions, the commit, challenge and finalize logic;
- the queue's `getFirstUnfinalizedMessageEnqueueTime`;
- OpenZeppelin's `Ownable` 4.9 in the pinned dependency tree.

P1's and P2's structures and debt come from these readings. They were not computed by running anything.

**Committed records read:**
- the adopted Rollup document's call records of `IRollupVerifier.verifyAggregateProof`: their receivers, giving P3's three Rollup rows by rule L2 (a construction fact), and their argument terms, giving E4's view (a construction check);
- I63's receipts, giving the anchor.

**Runs (no network):**
- the instrument's basis (`python -m tests_m3._i80 --write`, about 4 s): the anchor, the tag tree listings and the head builds of the router and the zkEVM verifier under I63's three configurations (hardhat and foundry builds are equal for both);
- a toy forge test of the state-diff `reverted` flag, which is set for a frame whose enclosing frame reverted (so L8's "persisted");
- the generator closures, computed with holon's own functions: 149 files, none under `holon/bundle2/`, `holon/__main__.py` or `holon/coverage.py`.

**Never run on a Bundle II member:** the frontend, model3, the evaluator, forge or Bend.

## Risks for the build

1. **The frontend on the zkEVM verifier.** The Plonk verifier's Yul has nested functions, loops and about 200 mstores, so the walk may exceed its term budget or the time budget. Either misses P2, and is never smoothed.
2. **The frontend on the router.** A construct left unsupported (a memory struct copied from a storage array element inside a loop with break, a push of a memory struct) is debt, and misses P1.
3. **model3's dynamic arrays.** The extension computes keccak256(slot) through the model's keccak table and packs a 28-byte struct per slot. An action it cannot compile is model debt, and misses P6.
4. **The linked machine's exactness.** Nested frames, bubbled revert data, the code-size check, getters and the frames' "persisted" flag. A difference misses P4.
5. **Corpus reach.** The planted traces must pass the Rollup's guards (commit timing, the delay rule, the challenge window, the active submitter) and the router's (owner, finalization, start index). A row no trace reaches misses P5, and the corpus is never edited after the prereg.
6. **Coordination with I69.** Both edit `holon/__main__.py`. I69's frontend and model3 extensions may change what I80's documents or models would be if regenerated after its merge. Whoever merges second regenerates and reports any difference.

## The build branch and commit sequence

1. `holon/bundle2/` extraction (`extract`) with its declaration, views and cost sites.
2. The model extension and `model`.
3. The linked machine, the harness in `replay/M3/bundle2/`, then `corpus`, `deploy`, `refine`.
4. `acquire`.
5. The outputs, then the report `docs/iterations/I80.md`, with every miss and every debt item stated plainly.

No record is re-made: I80 moves no generator closure. CI runs the gates, which must not move.

## Predictions (key I80 in `spec/M3/predictions.json`)

- **P1, the router is extracted as read.** One debt entry: the `IRollup.lastFinalizedBatchIndex` call at :149. No unaccounted statement. The structure:
  - eight actions;
  - families `rollup`, `legacyVerifiers`, `latestVerifier`, and one inherited entry;
  - one loop and one cost term (the search at :108-114) in getVerifier and in verifyAggregateProof;
  - the COMMIT edge `IZkEvmVerifier.verifyBatch`.
- **P2, the zkEVM verifier is extracted with named debt.** The extraction ends within budget. It has eight actions and no unaccounted statement. Its external_call debt is exactly the three self calls (ZkEvmVerifierV1.sol:23, :27, SP1VerifierPlonk.sol:81), and it holds at least one unsupported entry in PlonkVerifier.sol. This is the least certain prediction.
- **P3, the static links.** Four rows: the Rollup's three proof checks into `router.verifyAggregateProof`, and `router.updateVerifier` into the Rollup's `lastFinalizedBatchIndex` getter.
- **P4, the linked machine refines the bundle.** 0 disagreements and 0 unsupported steps on all 365 traces.
- **P5, corpus reach.** Every link row and every router action is executed in a persisted frame.
- **P6, the router's model.** No model debt, ALL PROOFS CHECK, and 0 disagreements and 0 unsupported steps on every top-level router step.

**Regressions:**
- **R1.** The adopted Rollup's extraction, coverage and M3 model texts do not move (green at the prereg; its init.json is written by `holon run` since F40, so it is not compared).
- **R2.** The commit rules: no closure file, no frontend, nothing outside I80's paths.
- **R3.** Both prereg audits pass, and CI's gates do not move.
- **R4.** `holon/bundle2/` is generic and outside every closure.

## Earlier tests amended at this prereg

None.

## Questions for the human

- **Q-I80-a (HypC's member).** I80 treats ZkEvmVerifierV1 (and its SP1/Plonk bases) as the circuit oracle: extracted, debt named, never modelled or linked. Should I37 state HypC_v over the router's call (`verifyBatch(proof, PI)` succeeds iff the circuit accepts) as the hypothesis, as this assumes? Or do you want a stand-in-free model of the SP1 wrapper (selector, exit code and vkRoot checks) linked, with only `PlonkVerifier.Verify` as the oracle?
- **Q-I80-b (acquisition).** The on-chain reads that would match the deployed router and verifiers are listed in `acquisition.json`, not made. Should I37 or a later key fetch them (the router's code at the anchor, its UpdateVerifier logs, every verifier's code and `programVkey`)? Or is "the router at the head; the verifier an oracle" an acceptable stated assumption for I37?
- **Q-I80-c (folding the extension).** The storage-dynamic-array extension of model3 and the evaluator lives under `holon/bundle2/`, to leave every closure and record untouched. When I69's model3 extensions land, should a small key fold the two together (one implementation), re-making the records then?

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, the adopted Rollup document or its sidecar, `spec/`, `laws/`, `holon/rules/`, `holon/frontends/`, a closure file, or any earlier key's output.
- The instrument, the sidecar and the basis are fixed at the prereg. A wrong instrument is a Question plus an amendment line in `spec/M3/amendments.jsonl`, never a silent edit.
- A missed prediction is a result. Report it; never adjust a rule, an input, the corpus or a budget to make it hold.
- The target repository is read through git objects with lazy fetching disabled, and is never written.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
