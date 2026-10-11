# M1 report: the Morph rollup state-machine slice, mechanized

**Scope** (whitepaper §15.2, M1): the Rollup batch lifecycle as a state machine.
- Registers: CB, CSR, BVH, BD, CH, LCI, LFI, P, T, L, enq, inChallenge, s, W, D.
- Actions: commitBatch, commitState, commitBatchWithProof, revertBatch, challengeState, proveState, finalizeBatch, setPause, and the L1 message queue.
- Rules: UNDO, SORT, DISCH, FACT, SYM-ω, NAT.

**Exit criterion:** every M1 row of §11.8 matches or is explained, and every REFUTED witness replays as a Foundry test on the pinned contract.

**Status: met.**
- **Predictions:** all 14 preregistered M1 laws (§11.8, including the OWN row) matched their predicted outcome on the mechanized run. Two further laws were added post hoc and are marked as such.
- **Kernels:** every certificate and counter-law is accepted by Bend and re-checked by BendTT `--verdict`.
- **Replay:** every REFUTED witness replays on the real code at morph `3e44e79`: the `Rollup` and `L1MessageQueueWithGasPriceOracle` witnesses step for step through Foundry, and the OWN witness on the real Go `BatchData` (Go 1.24.7).
- **Refinement evidence:** a seeded random corpus of 300 traces (2,432 steps, all 10 actions) agrees with the real contracts on every step.

```
python -m holon run    --milestone M1      # ~40 s: 8 PROVED, 8 REFUTED, all dual-kernel
python -m holon gate   --milestone M1      # ~60 s: GENV G1 G2 G3 G4(21 canaries) G5 G7 G11
python -m holon replay --milestone M1 --morph <checkout> --solc <solc-0.8.24>   # ~2 min, needs forge
python -m unittest discover -s tests_m1 -t .        # HOLON_REPLAY=1 to include the replay check
```

## 1. Results

| Law | Rule | Predicted (§11.8) | Outcome | Evidence |
|---|---|---|---|---|
| L_undo_CSR | UNDO | PROVED | **PROVED**, unbounded | `noninterference`: committedStateRoots residues above LCI are unobservable after **every** trace, from **any** two states that differ only there |
| L_undo_BD | UNDO | PROVED | **PROVED**, unbounded | same, for batchDataStore residues |
| L_undo_BVH | UNDO | REFUTED | **REFUTED**, replayed | commit(1, blob 17); revert(1); a recommit of the *same* data via commitBatch reverts with "commitBatch requires no stored blob hash", but succeeds from the pre-commit state (O11/F2) |
| L_undo_cancel | UNDO | REFUTED | **REFUTED**, replayed | two batches; challenge(1); pause. After unpausing and waiting 40 s, batch 2 can still be challenged (its +W extension survived). Without the cancelled challenge it is outside the window (O12/N2) |
| L_sort_remaining | SORT | REFUTED | **REFUTED**, replayed | commit; challenge(1); wait W+1; commit → **Panic(0x11)** at Rollup.sol:363, `realize(W + start - t)` (O27/F4) |
| L_tag_BVH | SORT | REFUTED | **REFUTED**, replayed | commit v1 (blob 17); revert; commitState **v2** reuses the v1 versioned hash as the v2 "aggregate" field. The real contract accepts it (O26/F6). The search found the v1→v2 direction; the prediction named v2→v1. Same obstruction |
| L_disch_delay_nofree | DISCH | profile ∌ (0,0) | **PROVED** | at the representative state s*, a commit with **any** batch size n reverts (`nat_split`) |
| L_disch_delay_pay | DISCH | (c_msg, 0) | **PROVED** | strategy [sendMessage, commit n=1]: cost 1 message, delay 0 |
| L_disch_delay_wait | DISCH | (0, Δ_fin) | **PROVED** | strategy [wait 19, finalizeBatch(1), commit n=0]: cost 0, delay Δ_fin = 19 |
| L_disch_stale | DISCH | blocked (invariant) | **PROVED**, unbounded | `deadline`: kappa = inChallenge ∧ W + start < t is preserved by commitBatchWithProof, finalizeBatch, sendMessage and time, from **any** state (Thm 6.10) |
| L_disch_stale_commit | DISCH | blocked | **PROVED**, unbounded | `chain_revert`: while kappa holds, commitBatchWithProof reverts for every input (kappa falsifies the require at :363) |
| L_fact_Z | FACT | REFUTED | **REFUTED**, replayed | two commits from genesis, identical except blobs = [] vs [ZERO_VERSIONED_HASH], produce the **same** committedBatches hash on the real contract (O22) |
| L_sym_omega | SYM-ω | REFUTED | **REFUTED**, replayed | [commitBatchWithProof(2), challenge(1)] vs the reverse order. After proving batch 1, batch 2 can be challenged in one order (f₂ reopened to t+W) and not in the other (O19/F5) |
| L_own_txspayload | OWN | REFUTED, conditional | **REFUTED**, replayed on Go | Go `BatchData` (heap model, Go 1.24 growth oracle): append(8 B ctx), append(60 B ctx), `TxsPayloadV2`, append(8 B ctx). The held view's bytes 68.. are overwritten. Real Go: cap 80, first diff 68, exactly as modelled. The realistic case (three 60-byte contexts, 1-byte payloads) corrupts too: cap 256, first diff 180 (O36) |
| L_disch_delay_prove | DISCH | *post hoc* | **PROVED** | third profile point (c_proof, 0), found by the strategy search (§2) |
| L_nat_eta2 | NAT | *post hoc* (O15/N1) | **REFUTED**, replayed | legacy state with LFI < LCI; initialize2 writes CSR only at LCI; revert(1); recommit → "incorrect previous state root". Natively it succeeds. Replayed by emulating the pre-v2 storage (CSR slots zeroed) and calling the real `initialize2` |

*Predictions:* `spec/M1/predictions.json`, transcribed from §11.8. *Records:* `results/M1/`. *Bend files:* `gen/M1/`. *Replay:* `replay/M1/report.json`.

## 2. Surprises

1. **A third discharge strategy (L_disch_delay_prove).**
   - **What happened.** The mechanized strategy search found that at s*, `commitBatchWithProof` discharges the delay guard immediately. The rollup itself is also delayed there (`originTimestamp[LCI] + D < t`), and that skips the `n > 0` requirement.
   - **The fix.** With proof cost priced (c_proof = 1000 · c_msg), it is a dominated point: the preregistered Pareto frontier {(c_msg, 0), (0, Δ_fin)} stands.
   - **Why it matters.** The cost model is an *assumption* the profile depends on, and it is now explicit in the facts (`disch.cost_doc`).
2. **Even resubmitting the same data fails (L_undo_BVH).** After a revert, the shortest divergent continuation is a commitBatch of *the same blob*: it still reverts. The only way forward is commitState with the stale hash, which is exactly what makes O26 (L_tag_BVH) reachable.
3. **The cancellation residue is visible to challengers, not only to finalization (L_undo_cancel).** The shortest witness observes the stale +W through `challengeState`: a cancelled challenge keeps other batches challengeable longer.
4. **N1 reproduces with the minimal configuration.** LFI = 0, LCI = 1, revert into (0, 1]. The genesis index's committedStateRoots is zero in a legacy state, so even the first recommit fails.
5. **Ghost-tag direction.** Either version swap breaks exactness. The witness the search reaches first is v1→v2.
6. **A bend2 / BendTT disagreement (kernel finding).**
   - **What happened.** The first OWN counter-law, with 60-byte contexts and a 32 KiB size-class table in the state, was accepted by bend2 in 0.3 s, but `--verdict` reported "a mismatch between the TypeScript implementation and the formalized BendTT kernel".
   - **Bisected.** Every component and smaller instances of the same claim pass both kernels.
   - **Workaround.** Trimming the oracle table to ≤ 512 B and letting the search prefer 8-byte contexts gives a witness both kernels accept. The real-code replay still runs the realistic 60-byte case.
   - **Kept for upstream.** The failing case is preserved in `replay/M1/kernel_mismatch/` to report upstream (whitepaper §8.8: kernel bugs found along the way are reported).
   - **Status.** The certificate's dual-kernel status is honest: the committed result is `verdict: checked`.

## 3. How the certificates work (no tactics, no axioms)

**Model.** The rollup is a *guarded-command machine* in `spec/M1/facts/morph_rollup.json`, hand-written from the real repo with a source line per guard. The Go side of OWN is a second machine, `spec/M1/facts/morph_batchdata.json`, with the same DSL: a heap of backing arrays, slices as (backing, offset, len, cap), and Go 1.24's growth policy as an oracle. Both compile through the same generator. `holon/gen/machine.py` compiles every action to:

- `decide_a(reads.., inputs..) -> Dec_a`: the requires, in source order, reading **only** the state fields they mention;
- `exec_a(d, fields.., inputs..)`: field-wise effects selected by the decision.

**Window and shadow.**
- Committed batches LFI..LCI live in a window.
- Residues that revertBatch leaves at indices above LCI live in **shadow lists**: `s_csr`, `s_bd`, `s_bvh` and the ghost `s_tag`.
- `challenges` and `finalizedStateRoots` are arrays indexed by absolute batch index.

**Proof classes** (`holon/gen/mproofs.py`):

| Class | Laws | Idea |
|---|---|---|
| `noninterference` | L_undo_CSR, L_undo_BD | Per action, generalise over the decision `d`; then `exec` reduces branch by branch, and the erased shadow never reaches an observed field. Rewrite with the hypothesis `proj(s1) == proj(s2)` and induct on the trace. A live register makes the per-action lemma ill-typed: erasing `s_bvh` is rejected because `decide_commitBatch` reads it (canary `erase_live`). |
| `deadline` | L_disch_stale | kappa's fields are left alone (frame), only advanced (t += dt, lemma `core_and_lt_add`), or only cleared (challenges[i] := empty, list lemma `dl_nth_set_le` plus monotonicity). All lemmas are proved by induction in the proof file. |
| `chain_revert` | L_disch_stale_commit | Mirror the decide chain of commitBatchWithProof down to the require that kappa falsifies. Generalise each earlier guard; rewrite the last one to False. |
| `nat_split` / `evaluate` | DISCH profile points | Case split, or check a strategy by computation. |
| `counter` | all REFUTED laws | The concrete witness, premises by computation, the two sides separated through the model's equality function. |

**Kernels.** All 15 checked files also pass BendTT `--verdict` (0.5–1.2 s each).

## 4. Refinement evidence (whitepaper §8.7, §12.1)

`holon replay --milestone M1` runs one generic Foundry harness, `replay/M1/solidity/HolonTraceReplay.t.sol`.

**Deployment, per trace:**
- the **real** Rollup and L1MessageQueueWithGasPriceOracle, behind TransparentUpgradeableProxy, with `initialize`, `updateRollupDelayPeriod`, `addChallenger` and `importGenesisBatch`;
- oracle stand-ins only for ISubmitter (active set; slash deactivates) and IRollupVerifier (accepts proof byte 0x01).

**Execution.** The harness executes model traces step by step: it re-encodes headers itself, uses `vm.blobhashes`, and warps time. It logs the real outcome of every step, plus `committedBatches[LCI]`.

**Corpora:**
- **Witnesses.** Each REFUTED law is linearised into the traces its claim compares. All steps agree, and the obstruction reproduces on the real code (table in §1).
- **Random corpus.** 300 seeded random traces, 2,432 steps. They mix successful and failing actions, perturbed indices and principals, and every revert path the policy reaches. Per action, model and real outcomes agree on all steps: commitBatch 874, wait 628, commitState 224, commitBatchWithProof 130, setPause 123, finalizeBatch 114, sendMessage 108, proveState 96, revertBatch 68, challengeState 67. There were **0 disagreements**.

Earlier runs did fail. Both causes were harness defects, and both were fixed in the harness, not the model:
1. The block gas limit was exceeded, so the harness now replays in chunks of 25 traces.
2. Non-challengers without ETH could not attach the challenge deposit, so every principal is now funded.

## 5. Premises and assumptions (visible, never axioms)

**Correction (I1, 2026-10-11).** These are model assumptions, not premises of the frozen statements. Until I1, a hard-coded `CF(keccak256, headers)` string was appended to the premises of every M1 record, including `L_own_txspayload`, which involves no hash. Since I1:
- each record's `premises` are exactly the assume clauses of its statement;
- its `model_assumptions` are the entries of `spec/ledger/assumptions.json` that its cone reaches.

The list below is the original text, corrected where it was wrong.

- **CF(keccak256, headers).** Presenting a header is modelled by its index, and committedBatches by `k ≤ LCI`. Replay re-checks it: `keccak(header)` must equal `committedBatches(k)` after every commit, or the harness logs a mismatch. None were logged.
- **Hyp-Z0-kzg (D2).** This item was originally called HypZ, but §8.5 reserves that name for the compression hypothesis. The claim is that ZERO_VERSIONED_HASH equals the versioned hash of the zero blob, `0x01 ‖ sha256(0xc0 ‖ 0⁴⁷)[1:]`.
  - The constant is at Rollup.sol:25, not :24.
  - The original text said the value was "oracle-checked". No code in the repo performed that check. The value was recomputed by hand on 2026-10-11 and matches.
  - A checked test arrives with I3 (`docs/BUILD_PLAN.md`).
- **Oracles.** ISubmitter and the verifier are oracles (stand-ins above). keccak over blob hashes (version 2) is an injective stand-in `agg`. Replay uses real keccak, and outcomes agreed.
- **Index specialization.** Reads of per-batch registers above LCI go through the shadow only for `batchBlobVersionedHashes`. Every other read follows a guard that established `idx ≤ LCI`. This is documented per guard in the facts and exercised by the random corpus.
- **Representative state for DISCH-delay.** The profile is computed at s*, a reachable representative of the guard class: one message, included, delay window passed, finalization pending. The profile is per state (Def 6.20), not global.

## 6. Gate, canaries and mutation adequacy

**Gate M1.** All checks pass:
- G1: regeneration of the 31 generated `.bend` files and the summary is byte-identical.
- G2: statement hashes.
- G3: no escape hatches.
- G4: **21 canaries**, all rejected with an expected/observed mismatch:
  - `erase_live` ×12: non-interference over `s_bvh`, `s_tag`, `t`, `paused`, `inch`, `qlen`;
  - `pin_const` ×6: profile constants changed;
  - `negated` ×3 (one per proved forall law it applies to).
- G5: re-check from scratch.
- G7: dual kernel.
- G11: one law per LAWS.bend.

**Mutations.** `spec/M1/mutations.json` plants four bugs in the facts:
1. revertBatch clears BVH (the F2 fix).
2. Saturating arithmetic at the commitBatchWithProof realize site.
3. challengeState stops extending other batches.
4. commitBatch reads a CSR residue.

The outcomes move as predicted. Examples: (4) turns L_undo_CSR from PROVED to REFUTED, and (2) refutes L_disch_stale_commit. `tests_m1/test_m1_mutations.py` checks this.

## 7. Not in M1, and next

- **Reachability invariants (D4) and NAT laws other than η₂.** These need induction over `Reach`. Today's PROVED laws avoid that by holding from *every* state. That is stronger than needed, and enough.
- **M2.** Automated extraction (solc/Yul → facts DSL; go/ssa → facts), historical-input replay, and a preregistered mutation-adequacy threshold. The facts DSL is the target format extraction must produce.
