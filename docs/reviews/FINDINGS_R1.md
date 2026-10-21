# Findings review, round 1: what HOLON's REFUTED results found in Morph

Read-only review by the lead (2026-10-21), on the lead head bd67d4e, against Morph at the pinned commit 3e44e795. Inputs:
every record whose `filter_bin` is `finding` (I40's triage: the counterexample reproduces on the real code), plus the
4-step Panic path to `Rollup.sol:491` that I40's review found. Each was judged against the Morph source and against the
whitepaper's prior manual findings (Appendix A, F1-F14) and outcome table (§11, O1-O32). Nothing here changes a law, a
record, a bin or a prediction.

## Bottom line

**No new security vulnerability.** The 25 `finding` records are 10 distinct behaviors of the real code, and all 10
reproduce on Morph:

| | distinct behaviors | records |
|---|---|---|
| A known prior finding or outcome, re-derived mechanically (the back-test working): rows 1-7 | 7 | 17 |
| Intended behavior (who may lift a guard): row 10 | 1 | 4 |
| An artifact of the law (a premise the code enforces elsewhere): row 8 | 1 | 3 |
| Benign (reverts either way): row 9 | 1 | 1 |
| Total | 10 | 25 |

The `Rollup.sol:491` path is real but needs the owner to misconfigure `proofWindow`. It is informational and not in
Appendix A.

What this says about HOLON: the factory re-derived, from extracted code and with replayable witnesses, 7 of the
whitepaper's manually found items (F2, F4, F5, F6, O2 of F12, O12/N2, O31). It found nothing the manual review
missed. The remaining Appendix A items (F1, F3, F7-F11, F13, F14) wait on rules not yet built: NAT (I29), SYM (I34),
the bundle (I36, I37) and the Go side (I38, I39).

## Each behavior

| # | Behavior on the real code | Records | Verdict | Evidence |
|---|---|---|---|---|
| 1 | `Rollup.sol:363`: `proofWindow + challenges[c].startTime - block.timestamp` underflows (Panic 0x11) for every commit once a challenge is stale | M1 `L_sort_remaining`, M2 `extracted_m1/L_sort_remaining`, M2 `L_sort_site_rollup_363_1fc7f88a`, M3 `L_sort_realize_rollup_363_4a64383b` | **Known: F4 (O27)** | replays: commitBatch, commitBatchWithProof and commitState revert `panic:0x11` at :363 |
| 2 | F4's block lasts until outside action: the active submitter's `proveState` after the window settles the challenge as a timeout (challenger wins, the batch's submitter is slashed, `inChallenge` clears), or the owner's `revertBatch` | M3 `L_disch_blk_rollup_363_e11d8bb2_onlyActiveSubmitter`, `L_disch_noext_rollup_363_e11d8bb2_onlyActiveSubmitter`, `L_disch_noext_rollup_363_e11d8bb2_onlyOwner` | **Known: O31** ("until outside action", whitepaper line 468) | emitted Foundry tests: challenge at t+10 with a 10 s window, `proveState` at t+21 succeeds and clears `inChallenge` (slot 166) |
| 3 | `revertBatch` leaves `batchBlobVersionedHashes[i]`, so a recommit at the same index behaves differently than before the commit | M1 `L_undo_BVH`, M2 `extracted_m1/L_undo_BVH`, M3 `L_undo_pair_Rollup_commitBatch_revertBatch`, `L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes` | **Known: F2 (O11)** | replays diverge at the recommit; emitted with/without tests |
| 4 | A recommit can change the version while the stored blob hash keeps its old meaning | M1 `L_tag_BVH` | **Known: F6 (O26)** | the Go consumer reads the same hash as a v1 blob hash and as a v2 commit hash |
| 5 | A proof-backed commit and a challenge do not commute: either order succeeds, the continuations differ | M1 `L_sym_omega`, M2 `extracted_m1/L_sym_omega` | **Known: F5 (O19)** | real outcomes differ (code 33 against ok) |
| 6 | Pausing cancels an open challenge but leaves the +W extensions it added | M1 `L_undo_cancel`, M2 `extracted_m1/L_undo_cancel` | **Known: O12 (N2)** | real outcomes differ |
| 7 | No Go encoder produces the headers Solidity commits at version 2 | M0 `L_par_hdr_v2` | **Known: O2, part of F12** | Go and Solidity replays |
| 8 | Go's header encoders carry any `sequencerSetVerifyHash`; Solidity's commit stores zero there (`Rollup.sol:351`) | M0 `L_par_hdr_ssvh`, M3 `L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0`, `L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1` | **Artifact: a missing premise** | the bytes differ only at offsets 185-216 (the hash). Go's batch sealing rejects a non-zero hash on live batches ("live batch cannot contain a sequencer-set hash", `common/batch/batch_cache.go:1447`) and allows one only when replaying a legacy batch at or before the cutover, which the old contract committed with it. The M0 law's own note expected this premise to surface |
| 9 | `finalizeBatch` of batch 0 underflows at `Rollup.sol:636` (`_batchIndex - 1`) | M2 `L_sort_site_rollup_636_e68daf06` | **Benign** | only the genesis batch reaches it, and batch 0 is finalized at import, so the call would revert at "batch already verified" anyway: a Panic instead of a message |
| 10 | The owner or the active submitter can lift a blocking guard: the pause (`PausableUpgradeable:77`), a pending revert request (`Rollup.sol:132`), `initialize4`'s "challenge in progress" (`Rollup.sol:213`) | M3 `L_disch_noext_pausableupgradeable_77_ed0ce816_onlyOwner`, `L_disch_noext_rollup_132_d953872f_onlyOwner`, `L_disch_noext_rollup_213_f2e7faf8_onlyActiveSubmitter`, `L_disch_noext_rollup_213_f2e7faf8_onlyOwner` | **Intended** | DISCH external-discharge classification (I31): the designed admin and submitter powers |

**`Rollup.sol:491` (I40 review, not a record).** `challengeState` adds `proofWindow` to every open batch's
`finalizeTimestamp`. `updateProofWindow` (`Rollup.sol:500`) bounds the window only below (`> 0`), so an owner who sets it
near 2^256 makes every later challenge revert with Panic 0x11: challenges are disabled. It needs the trusted owner, who
can upgrade the contract anyway. **Informational: a missing upper bound on an owner setting.** It is not in Appendix A.

## What the review means for HOLON

1. **The `finding` bin is overloaded.** It means "the counterexample reproduces on the real code", which mixes known
   prior findings, intended behavior and law artifacts (rows 8-10). Proposed follow-up: a generated sub-label on
   `finding` records (`known:<F or O id>`, `intended`, `law_artifact`, `benign`, `new`), computed from the outcome
   ledger and recorded review decisions, never by hand. This changes no law and no bin.
2. **M2 and M3 laws carry no `maps_to`.** Only M0 and M1 laws link to the whitepaper's outcome IDs, so
   docs/CASESTUDY.md undercounts what M2 and M3 re-derived (rows 1-3 here). Linking them belongs to the ledger
   generator (`spec/ledger/maps_to.json`).
3. **Row 8's law stays as it is.** Adding the premise `sequencerSetVerifyHash = 0` would weaken a frozen statement, which
   needs a signed weakening (Q3, Q40: impossible by design). The honest record is the label above, not a new premise.
4. **Recall so far:** 7 of the whitepaper's manually found items re-derived. M3's remaining rules are where the rest
   should appear; this review is the baseline to compare them against.

Nothing in this review is reported outside the repository. Row 10 and the `:491` note are design observations, not
vulnerabilities; whether to mention the missing bound to Morph is the human's call.
