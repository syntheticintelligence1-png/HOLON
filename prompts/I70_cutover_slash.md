# I70 (= I36c): the cutover × slash laws, O13 and O20's economic half, over the real legacy staking code

Rendered from `docs/BUILD_PLAN.md` §4 I36 and its rows I69 and I70, from whitepaper §5.3 NAT, §7.5 SORT, §11.3 (O13, O20) and Appendix A F10, and from the human answer Q12 in `docs/HUMAN_ANSWERS.md` (fetch the real legacy code; a stand-in is the last resort). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, and run `bend guide` once.

The exact rules are in the docstring of `tests_m3/test_cutover_slash.py`: A1-A3 (acquisition), M1-M2 (the legacy registry's model), L1-L4 (the link and its refinement), S1-S6 (the laws), RP1-RP2 (replay), the own commits and the commit rules. The key's thresholds pin that docstring, the instrument `tests_m3/_i70.py`, the sidecar `spec/M3/lib/cutover_slash.json`, the basis `spec/M3/lib/cutover_slash_basis.json` and thirteen inputs by sha256. The base is `f30e0dd5`, the lead after I87's build.

## What I70 is

BUILD_PLAN I36 predicts two cutover results, which the split of 2026-10-23 gave to I70 (= I36c):
- **O13 REFUTED** (NAT, cutover × slash; Appendix A's F10: "Slashing is vacuous for pre-cutover batches").
- **O20's economic half:** a slash on a pre-cutover batch transfers zero, so the conservation or π law is REFUTED. O20's π split law itself is the lead's I34.

The mechanism, read from the sources:
- At V10, `commitBatch` stores `IL1Staking.getStakerBitmap(msg.sender)` = `1 << stakerIndexes[sender]` as the batch's fourth word, `signedSequencersBitmap`. A won challenge calls `IL1Staking.slash(bitmap)`, which removes the staker and returns its share of `stakingValue`.
- At V11 the same word is read as `submitter`, its low 160 bits. A won challenge calls `ISubmitter.slash(address(uint160(bitmap)))`.
- For a batch committed before the cutover and challenged after it, that address is `0x…02` for the first staker, never registered at the new registry. Its stake is 0, so the slash returns 0. For a staker index of 160 or more, the low bits are zero, so the address is `address(0)`: the implicit address(0) role of O20.
- The legacy staker keeps its bond in L1Staking, and can still withdraw it.

## Why two new sub-forms (approved by the coordinator, 2026-10-30)

- **I29's naturality square cannot state O13.** It answers the registry's call from one environment (`VEnv.e_calls`) shared by both sides. So the slash's reward is the same number on both sides, whatever the registries' code says.
- **I86's SORT conservation cannot state O20's economic half.** It is the inflow half ("every inflow is accounted for"). A vacuous slash conserves: nothing flows in, and nothing is credited.
- The two cutover laws need the registries' own code to answer the slash: the legacy registry at the old version, the new one at the new version. I70 links them, and states:
  - **NAT `slash`** (O13): the answer of the new version's slash site at the migrated state equals the answer of the old version's slash site at the state. This is naturality, §5.3 (b), observed at the slash site.
  - **SORT `slash`** (O20's economic half): if the old site's slash would move value, the new site's slash moves value too.
- **The site predicate is structural** (S2). It is computed from the versioned machine's MIG-edge data and the documents alone:
  - the call's receiver is a word of a reinterpreted in-flight entry;
  - an argument reads a member of a retyped in-flight entry;
  - the result is credited to a mapping cell.

  No target name, law id or action is special-cased in holon/.
- **The catalog version** is the next free holon-rules version when I70's predecessor in the chain lands, holding every earlier catalog's producers as the same objects. Expected: 1.12, after I86's 1.11. If the lead's I34 lands first, I70 takes the version after I34's. The build fixes the number at the re-derive and discloses it.

## The two stages

1. **Now: no dependency on the unmerged branches.**
   - **The acquisition (A1-A3).** Read the explorer's verified source of the registry implementation and compile-match it.
   - **The legacy registry's model3 model (M1-M2).**
   - **The linked cutover machine (L1-L4).** I69's machine with a versioned Rollup member: V10's document until the cutover step, V11's after it. L1Staking is linked at V10 and the Submitter at V11. It is refined against the real code through a harness built on I69's and I28's: the V10 and V11 implementations behind one proxy, and the v0.6.1 L1Staking behind its own.
2. **After I29, I83 and I86 land** (the coordinator says when):
   - merge the lead;
   - generate the analysis and the laws under the new catalog;
   - re-derive M3 (every earlier law moves only in `rule_catalog_version`) and rebind;
   - decide the two laws in Bend and BendTT over the linked layer;
   - replay every witness on the real code;
   - re-make the records the closures move: M1, M2 and T32 locally, M3 on CI runners (LANE_RULES).

## The acquisition plan (Q12)

| item | value |
|---|---|
| registry proxy | `0x0dc417f8af88388737c5053ff73f345f080543f7`, the old registry of I63's cutover receipt |
| registry implementation | `0xdb0734109051daab5c32e45e9a5ad0548b2df714`, set at block 20999722 (tx `0xda523669…`), live through the cutover block 26031669 (I69's timeline; no later Upgraded log in the window) |
| V10 era | blocks [25236554, 26031669): V10's implementation `0xac3c379d…` to the cutover's `0x213ce22b…` (I28's versioned document) |
| explorer | Etherscan, chain 1, through the session's connector (`getsourcecode`), once, after this prereg is pushed. The response is committed verbatim under `results/M3/cutover/explorer/`. Never `scroll-tech/*` or `spec/heldout/`. |
| compile-match criterion | The verified sources, compiled by the pinned solc with the explorer's recorded settings, give L1Staking a runtime code whose identity under I63's rule (immutable ranges zeroed, CBOR metadata stripped) equals the on-chain code's. Also, the verified `L1Staking.sol` equals v0.6.1's blob `165fec18` byte for byte. |
| labels | `verified` (P1's prediction); `tag_matched` (I69's match stands and the explorer's source is absent or not matched); `bytecode` (a labelled bytecode-level model); `standin` (a labelled stand-in, the last resort) |

The V10-era members the link runs are known from committed records, not predicted:
- The messenger's implementation `0x0cc37d52…` (set at block 21614282) and the queue's `0xf3b77243…` (set at block 24575015) are I69's head-build matches. Both were set before V10's deployment block 25236554 and were unchanged through the cutover.
- So for I70's window, Q66's question has its answer in I69's timeline.

The registry's whitelisting at the queue during the V10 era, which decides whether a legacy slash could send its fee-free message, is an acquisition read reported in the report. It is not predicted. The harness whitelists the registry, which is the sidecar's environment premise.

## Predictions (key I70)

| id | prediction |
|---|---|
| P1 | The explorer holds a verified source of the registry implementation, equal to v0.6.1's unit and compile-matched: label `verified` |
| P2 | model3 compiles L1Staking with no debt in the corpus's actions, and refines with 0 disagreements |
| P3 | The linked cutover machine refines the real code on T1-T4: 0 disagreements, 0 unsupported, frames on the four link rows |
| P4 | The generator emits exactly the basis: one site pair (proveState, V10→V11) and two laws |
| P5 | O13: `L_nat_slash_Rollup_V10_V11_proveState` REFUTED. The V11 answer is (ok, 0) and the V10 answer is (ok, R > 0). Bend and BendTT accept the counter-law, and both runs replay. |
| P6 | O20's economic half: `L_sort_slash_Rollup_V10_V11_proveState` REFUTED, replayed |

Regressions R1-R4: earlier outputs do not move; the own-commit rules; the prereg audits and CI; target-agnostic code.

## Deviations from the plan's text, and why

- **The real code, not a stand-in.** The plan's "O13 REFUTED (stand-in)" predates Q12's answer and I69's recovery of the registry. I70 links the extracted v0.6.1 document of the matched implementation. A stand-in is used only if the acquisition fails, and then it is labelled.
- **O13 is observed at the slash site.**
  - The cutover's initializer refuses a state with a challenge in progress or a pending revert. Its guards are `!inChallenge` and `revertReqIndex == 0`.
  - So a square whose op is the whole challenge cannot have both orders defined. Its refutation would be by definedness, not by the slash.
  - The site-level square compares what each version's registry pays for the same in-flight batch.
  - The replay then runs the whole scenario on the real code, on both sides: challenge, the proof window, proveState.
- **The law's state space is the product of the members' reachable sets, under the wiring premise.**
  - That space over-approximates the linked machine. A law over it is a stronger claim, never a weaker one.
  - The witness is a state of the linked machine. Its counter-law checks the link equations by computation: every answer the trace's Rollup steps take from a registry equals that registry model's answer.
  - The witness is replayed on the real code.

## What was known before this prereg (disclosed)

**Read:**
- I69's report, prompt, sidecar, declaration, timeline and its L1Staking document's action list;
- I28's prompt, versioned document and its deployments;
- the V10 (`55272a51`) and V11 (`5edbc693`) `Rollup.sol`, the head's `Submitter.sol` and v0.6.1's `L1Staking.sol`, through git objects with lazy fetching disabled;
- I29's prompt, contract docstring and claims module (gen/M3/nat/models/morph_rollup_nat.bend) on its pushed branch;
- I83's prompt, and its key's predictions on its pushed branch;
- I86's prompt and contract docstring on its pushed branch.

No record, verdict or witness of I29, I83 or I86 was read.

**Ran:**
- `tests_m3/_i70.py --write`: the basis over the committed versioned document. It gives one site pair, proveState V10→V11, and the two law ids. That is a construction fact, and P4 predicts that holon's generator emits the same.
- sha256 of the pinned inputs, and of v0.6.1's `L1Staking.sol` blob.

**Not run:**
- model3 on L1Staking;
- the linked machine;
- forge;
- Bend on any I70 law;
- the explorer (no network read at all).

## Risks for the build

1. **model3 on L1Staking.** A struct with a `bytes` member in storage, a mapping keyed by `bytes` and `abi.encodeCall` with a struct argument may each need a generic extension. Any extension must leave every earlier model byte-identical. It also moves the generator closures, so M1, M2 and T32 are re-made locally and M3 on runners.
2. **The legacy slash's message.** `slash` sends a zero-value message through the messenger, which requires the queue's fee waiver. The harness whitelists the registry. The mainnet status is read and reported.
3. **Kernel time.**
   - The counter-law imports the versioned layer (about 5 MB of Bend) and both registry models.
   - Its Rollup trace is I83's in-flight prefix up to the V10 commit.
   - A time or fuel stop is never acceptance: the law is then UNKNOWN with the bound.
4. **The catalog chain.** I70's version follows I86's. Whoever merges second re-derives.
5. **The search's environment premise.** The registries' own calls answer ok. A refutation that needs a failing environment answer is not one I70 reports.

## Commands

```
python -m holon cutover acquire|model|corpus|refine|analyze|replay [--check]
python -m holon derive --milestone M3
python -m holon run --milestone M3 --laws L_nat_slash_Rollup_V10_V11_proveState,L_sort_slash_Rollup_V10_V11_proveState
```

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, an earlier key, or another key's sidecar or instrument.
- The instrument, the sidecar and the basis are fixed at the prereg. A wrong instrument is a Question plus an amendment line, never a silent edit.
- A missed prediction is a result. Never adjust a witness source, a bound or the environment premise after a run.
- The target repository is read through git objects with lazy fetching disabled. Never fetch or read `scroll-tech/*` or `spec/heldout/`.
