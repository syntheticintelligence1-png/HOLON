# I84 (= I37b): Bundle II's laws (O3, O23, the calibrated cost, O35) over I80's extraction

Rendered from `docs/BUILD_PLAN.md` §4 I37 and its row I84 (whitepaper §5.1 PAR-domain, §5.5 FACT, §5.7 DISCH and self-controlled enabledness, §3.8 En_G, §8.5 HypC, App. D cost; Appendix A F1, F11, F14), and from I80's report (`docs/iterations/I80.md`, merged at 873cb0d9). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

The exact rules are in the docstring of `tests_m3/test_bundle2_laws.py`:
- FR1-FR3, the frontend's loop rule;
- C1-C2, the catalog;
- N1, the law ids;
- LD1-LD5, PAR link_domain;
- FC1-FC3, FP1-FP4 and FM1-FM3, FACT public_input;
- K1-K5, calibration;
- D1-D6, DISCH self_controlled;
- RC1-RC2, records and replay;
- the commands, exit codes and commit rules.

The key's thresholds pin that docstring, the instrument `tests_m3/_i84.py`, the sidecar `spec/M3/lib/bundle2_laws.json` and the basis `spec/M3/lib/bundle2_laws_basis.json` by sha256. The base is `92c98e40`, the lead after I80, I81 and I72's build.

## Why a separate key

I37 keeps its number; I80 = I37a was its extraction half. I84 = I37b states I37's laws over that extraction, calibrates the cost, and closes the one gap I80 left in the router's model. It is numbered I84 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys).

## What I84 does

1. **The frontend's loop rule (FR1).** I80 found that a break-only local (the router's `found`, :108-114) has no entry value in its loop record. So the router's getVerifier and verifyAggregateProof are model debt, and the linked machine refuses two steps (Q-I80-e).
   - **The fix.** A generic extension of `holon/frontends/solidity`: such a local is recorded as carried, with its value before the loop.
   - **What moves.** The adopted Rollup document has no such name, so it does not move (R1). The router's document gains the carried name, its model compiles every action (P1), and I80's corpus is re-run (P2).
   - **Cost.** This is a closure change, so the M1, M2 and T32 records are re-made locally and the M3 records on CI runners.
2. **The catalog (C1).** holon-rules/1.10 is the next free version after I71's 1.7, I29's 1.8 and I35's 1.9. It adds three sub-forms over I80's declaration, and every earlier producer is kept as the same object.
3. **PAR link_domain (O3; LD1-LD5).** For each static link row into the router, the law is: whenever the Rollup admits a proof call (the router as an oracle), the router resolves the call's (version, index) to a non-zero verifier.
   - **The deployment** is I80's, except for the router, which is constructed as the target's own deploy script constructs it: `contracts/deploy/016-RollupInit.ts:38-40`, one version `[1]`.
   - **Why that matters.** Versions 0 and 2, which the Rollup's commit admits (`version <= 2`), then resolve to `address(0)` without entering the search loop.
   - **Under I80's harness configuration** (versions 0, 1 and 2 at start 0), the router's domain is total and stays so: updateVerifier only pushes legacy entries. So no witness exists there. This was read before the prereg, and it is why the deploy script's configuration is the laws' deployment.
4. **FACT public_input (O23; FC, FP, FM).**
   - **The commitment** is the public input PI: E4's keccak256 over header bytes 25..217 and the chain id.
   - **The consumers** are the extracted Go derivation's reads of the parent header (`ParseBatch` and `fetchBatchInfoOutline` call BatchIndex, TotalL1MessagePopped, Version and LastBlockNumber). That header is the commit transaction's `parentBatchHeader` (`batch_info.go:91`, `verify_local.go:66`; the Go document records the call edge but not its receiver, so the sidecar states it with the lines).
   - **Laws.** One law per field, for `commitBatchWithProof`, the one PI-checking action that takes the parent header as input.
   - **The measure** comes from how the commit actions store the field: LastBlockNumber is a free input member (64 bits); Version is checked jointly (a bound [1, log2 3]); BatchIndex and TotalL1MessagePopped are computed (bounds [1, 64]).
5. **Calibration (K1-K5).**
   - **The site.** The one state-indexed cost site is `challengeState`'s loop (Rollup.sol:489-493, count `lastCommittedBatchIndex - lastFinalizedBatchIndex`). It is `loop_storage_write` debt in the extraction, not a cost term, so its count is taken from the loop record, as I80's report says.
   - **The harness.** `tools/calibrate_gas.py` runs a forge harness: commit k batches, then challenge. It measures the call frame's gas and adds the transaction's intrinsic gas.
   - **The fit.** c0 + c1 * k is fitted on backlogs {3, 6, 12, 24, 48} only, and evaluated at {1, 2, 4, 8, 16, 32, 64}. Fitting the evaluated points would make "within 5%" nearly free for a linear loop; extrapolating to 64 from at most 48 is the test.
6. **DISCH self_controlled (O35; D1-D6).** The law is: in every reachable state where `challengeState` succeeds, its calibrated cost is at most G.
   - **G** is 30,000,000: `spec/M3/lib/refute.json`'s `gas_limit`, I40's, read and not chosen.
   - **k*** is the least backlog at which the calibrated cost exceeds G.
   - **A counter-law over Reach** carries the whole strategy's trace and keccak table. So the kernel path is bounded at 64 steps, BUILD_PLAN I37's own bound. Beyond it, the law is UNKNOWN, and the strategy is replayed on the real code by bisection (k*_real).
   - **D6 shows the REFUTED path exists**, with a planted ceiling that makes k* = 2.

## Predictions, and what of BUILD_PLAN is adopted

| BUILD_PLAN I37 | I84 |
|---|---|
| O3 REFUTED | **P8**: the three link_domain laws REFUTED under the deploy script's router configuration; witnesses replay |
| O23 REFUTED, F(PI, parent lbn) = 64 bits | **P6**: REFUTED, 64 bits (a value), the witness replays. **P7**: the three sibling parent reads REFUTED, with their measures |
| calibrated within 5% at k in {1..64} | **P3**: as stated, with disjoint fit and evaluation sets |
| O35: a submitter strategy with k <= 64 leaves En_G | **P4**: registered as written. **P5**: the agent's own prediction |

**The agent expects P4 to miss.** This is disclosed before any measurement. Under the EIP-2929/2200 schedule, each backlog iteration costs a cold SLOAD (2100) plus a dirty SSTORE (2900) plus loop overhead, about 5,150 to 5,600 gas, and the fixed part is about 0.1 to 0.25 M. At G = 30 M that puts k* in the thousands, not at 64 or below. So **P5** predicts k*_model and k*_real in [5000, 6000], the law UNKNOWN (beyond the 64-step kernel budget), and the replay passing. P4 is kept because the plan's predictions are preregistered claims, and dropping one after reading the code would be hindsight.

The frontend fix's outcomes are predictions too:
- **P1**: the router's document gains only the carried `found`; the model has no debt; ALL PROOFS CHECK.
- **P2**: I80's corpus re-run gives the linked machine 0 disagreements and 0 unsupported steps. The router model has 0 unsupported steps and only I80's known S5 status disagreement (Q-I80-d).

Regressions:
- **R1**: the adopted Rollup's document, coverage and M3 model texts do not move.
- **R2**: the own-commit rules, and the M1, M2 and T32 records are re-made.
- **R3**: both prereg audits pass.
- **R4**: the new code names no target.

**Not predicted: I81's ranking cells.** I81's frozen sidecar (`spec/M3/lib/ranking.json`) gives the FACT measure for sub-form `kernel` only, and copies `pending_measures` verbatim. Filling "F(PI, parent lbn)" or the DISCH and gas cells there needs a change to that frozen policy. I84 records F(PI, parent lbn) in its own records and asks (Q-I84-c).

## Risks for the build

1. **The frontend rule** may move another document or test fixture with a break-only local. Any such move is reported, and needs an amendment only where an assertion is wrong.
2. **model3 and I80's extension** may fail on getVerifier after the fix, or may not compile return values. Then O3's domain predicate is not modelled, the three laws are UNKNOWN, and P1 and P8 miss.
3. **The FACT search's two runs** need a time move before `commitBatchWithProof`'s delay rule and equal parent post roots. A field with no witness within the bound is UNKNOWN, and P6 or P7 misses.
4. **Calibration** may disagree with the gas schedule's estimate. Then P5's band misses, and that is reported.
5. **Catalog ordering.** 1.9 (I35) may land after 1.10. Whoever merges second chains the versions and regenerates.
6. **The M3 re-make runs on CI.** I28's base items (G11V's in-flight clause) stay as they are.

## Questions for the human (stated at the prereg)

- **Q-I84-a (the laws' deployment).** O3's laws use the router as the target's head deploy script constructs it (`[1]`). The deployed router's real configuration is an on-chain read I80 listed and did not make (Q-I80-b). Is the deploy script's configuration the right stand-in, or should a later key fetch the router's `UpdateVerifier` logs and state the laws over the deployed configuration?
- **Q-I84-b (G).** G is I40's `gas_limit` (30 M, mainnet's block gas limit when the Rollup was deployed). Since then, Fusaka's EIP-7825 caps a transaction at 2^24 gas, and mainnet's block limit has been raised. Should En_G use the per-transaction cap (it would roughly halve k*)?
- **Q-I84-c (I81's cells).** Should `spec/M3/lib/ranking.json` list FACT's `public_input` among the measured sub-forms, and mark the pending pair filled by `L_fact_pi_Rollup_commitBatchWithProof_LastBlockNumber`? Should its DISCH and gas cells name I44 instead of I37?

## What was known before this prereg (disclosed)

**Read:**
- the router's, the Rollup's (commit, proof, challenge, finalize and revert paths) and the queue's sources at the head;
- the deploy script `016-RollupInit.ts`;
- the Go derivation's `ParseBatch` and `fetchBatchInfoOutline`;
- the Go header codec;
- I80's outputs (the declaration, the router's document and model, the refinement records, the report);
- the adopted Rollup document's loop and header-store records;
- the Go documents' decoders and call edges;
- I81's measures and ranking sidecar.

**Ran:**
- the instrument's basis (`python -m tests_m3._i84 --write`, a few seconds: the deploy script's lines, the receiver sites, the consumers, the field classes, the views, the cost sites and the law ids);
- `bend guide`.

**Never run before this prereg:** forge, Bend, model3, the evaluator or the frontend, on anything I84 measures or decides. No gas was measured. The k* band is the gas schedule's arithmetic above.

## Commands

```
python -m holon bundle2 extract|model|corpus|refine            (I80's, re-run under FR1)
python tools/calibrate_gas.py [--check]
python -m holon bundle2 laws [--check]
python -m holon derive --milestone M3
python -m holon run --milestone M3 --laws <the eight ids>
python -m holon bundle2 replay-laws [--check]
```

## Rules

- `AGENTS.md` throughout. Never edit a frozen file, an earlier key, I80's or I81's sidecars, or `spec/M3/lib/refute.json`.
- **The instrument, the sidecar and the basis are fixed at the prereg.** A wrong instrument is a Question plus an amendment line, never a silent edit.
- **A missed prediction is a result.** Never adjust G, the fit set, a bound, the deployment or the search after a run.
- **The target repository is read through git objects** with lazy fetching disabled. Never fetch or read `scroll-tech/*` or `spec/heldout/`.
