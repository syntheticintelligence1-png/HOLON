# M3 comparison: factory vs. manual analysis vs. blind reruns

Morph pinned at `3e44e795586af3e11285b603ab642c67823add51`. This is the M3 exit artifact required by `docs/M3_SPEC.md`.
For each of the Appendix A findings F1–F14 and each §11.8 law it gives:
- the factory status;
- the status from both blind reruns;
- the replay evidence.

Status words follow `AGENTS.md`:
- `PROVED` / `REFUTED` mean a kernel-checked proof or counter-law;
- `UNKNOWN` means no verdict;
- "replayed" means the model witness was re-executed through public entry points of the pinned code and bound through G6;
- "model-only" means no replay;
- "native" means a native test that reproduces the behaviour but is not bound to a law.

## Sources

| run | input | laws | outcome |
|---|---|---|---|
| Factory (this branch) | full repo | M0 8, M1 17, M3_sorts 6, M3_msg 14, M3_router 10, M3_nat 17 | see tables |
| Blind B1 ([session](https://app.devin.ai/sessions/779ac65a4f23457496f034db910aacac)) | bundle `5ae11584…` only; output tarball sha256 `4c3460ee…` | 32 | 9 PROVED / 13 REFUTED / 10 UNKNOWN; 22/32 predictions correct; 9 findings (7 replayed, 2 model-only) |
| Blind B2 ([session](https://app.devin.ai/sessions/66f2a8f02819491590fc6d3427e259fa)) | same bundle; output tarball sha256 `4ab04ae0…` | 41 (+4 unbuildable, never run) | 21 PROVED / 20 REFUTED / 0 UNKNOWN; 7 prediction mismatches; 20 REFUTED (10 replayed and reproduced, 5 replay failed = model defects, 5 model-only) |

Both blind runs preregistered their laws before each run. B2 used four batches; it posted the commit sha and tarball sha of each batch before running it.

**Blindness deviations, both runs:**
- A HOLON checkout existed on the VM. Neither run opened it.
- The harness auto-injected the repo's generic `AGENTS.md` rules into both sessions. They contain no laws or results.
- The bundle keeps 7 known-leak files (`BLIND_MANIFEST.json`). B2 flagged three leak names as possible pointers: `L_sort_remaining`, `L_sym_omega` and `L_disch_delay_wait`. B1 flagged none. A finding re-found next to a leak name counts as weak evidence only.

## Appendix A findings F1–F14

| F | manual finding (abridged) | factory | B1 | B2 |
|---|---|---|---|---|
| F1 | challenge gas grows with backlog | **not covered**: gas is not in the model (debt) | — | — |
| F2 | revert keeps the blob hash; recommits must reuse it | M1 `L_undo_BVH` REFUTED, finding, replayed | REFUTED, replayed (B1-F1, B1-F2) | REFUTED, replayed (`F_disch_bvh_pin`, `F_undo_commit_revert_residue`) |
| F3 | Go blob retrieval indexes out of bounds for elements ≥ 3968 | E3 extraction derives the out-of-range condition; **native** panic replay in `replay/M3/f3_report.json` (reachability chain L1 fetch → `ParseBatch` → `common/batch/blob.go:49`, no `recover`). No law; not G6-bound | — | — |
| F4 | challenge arithmetic underflow disables commits | M1 `L_sort_remaining` REFUTED, finding, replayed; M3_sorts `L_sort3_remaining` REFUTED, replayed | — | REFUTED, replayed (`F_sort_commit_panic_reachable`; also `F_sym_tau_proofwindow_midchallenge`: owner shrinks proofWindow mid-challenge). Leak flag: `L_sort_remaining` |
| F5 | a challenge reopens a proof-backed batch's window | M1 `L_sym_omega` REFUTED, intent_question, replayed | — | REFUTED, **replay failed**: model defect, because proof-backed finality is missing from the extracted challenge guard (`F_sym_omega_proof_backed_challenge`). Leak flag: `L_sym_omega` |
| F6 | recommit changes version while reusing the blob hash | M1 `L_tag_BVH` REFUTED, finding, replayed | REFUTED, replayed (B1-F3) | REFUTED, replayed, but only for the model's ghost tag (`F_par_tags_reachable`) |
| F7 | delay guard reads the finalization cursor (profile) | M1 `L_disch_delay_{nofree,pay,prove,wait}` all PROVED (profile) | — | `L_disch_delay_guard_cost` PROVED. Leak flag: `L_disch_delay_wait` |
| F8 | third parties exhaust the replay budget; the fee waiver is keyed on the original sender | M3 `L_msgr_sender_can_replay` REFUTED, finding, replayed agree; `L_msgr_payer_bears_fee` REFUTED, finding, replayed agree | — | `L_disch_replay_budget` PROVED against its prediction of REFUTED; its law did not capture third-party exhaustion. Waiver not found |
| F9 | estimators assume no expansion; one omits contexts; slice aliasing | M1 `L_own_txspayload` REFUTED, finding (conditional), replayed. E3: the two estimators differ **by design** per batch version (`batch_cache.go:1280-1284`), not a defect. Compression expansion is not modelled (debt) | — | aliasing REFUTED, replayed, latent (`F_own_view_intact_reachable_b3`) |
| F10 | slashing is vacuous for pre-cutover batches | M3 `L_natr_defend` REFUTED (w=2) and `L_natr_slash_at_stake` REFUTED (w=2), both finding, replayed agree. Both rest on the **spec-bound** effect `initialize4: active := nact`. The native control `L_natr_slash_at_stake_native` is UNKNOWN (prediction miss). Bond/reward side native only (`replay/M3/nat_report.json`) | model-only (B1-F9: cutover swaps the registry under in-flight batches) | model-only, adjacent (`F_nat_legacy_csr`) |
| F11 | derivation accepts trailing payload; contiguity/last block unchecked; L1 counts dropped; parent lbn not in public input | **not covered**: E3 extracts `ParseBatch` but no M3 law targets these (debt) | — | — |
| F12 | codec domains, missing v2 encoder, legacy hash, … | M0 `L_dom_hdr` REFUTED, finding, replayed; `L_par_hdr_ssvh` REFUTED, intent_question, replayed; `L_par_hdr_v2` REFUTED, replayed; M1 `L_nat_eta2` REFUTED, intent_question, replayed. Cache, uint16 accumulators and documentation drift are not covered | REFUTED, replayed: ssvh hard-coded 0 (B1-F6) and 250-byte v0 domain (B1-F7); eta2 migration model-only (B1-F8) | — |
| F13 | attached value is unaccounted | **not covered** (debt) | — | — |
| F14 | batches committable at a version/index the router cannot resolve | partial: `L_rt_unregistered_zero` PROVED (model routes to 0). `L_rt_before_start` REFUTED is a **model artefact**: the not-found sentinel `b_nf(0)=1` stands in for a revert, triage none. No Rollup-linked law yet (AUDIT_R2 F3) | — | — |

**Factory coverage of F1–F14:**
- reproduced on real code and law-bound: F2, F4, F6, F8, F9 (aliasing part), F10, F12 (part);
- native only: F3;
- profile PROVED: F7;
- intent question: F5;
- partial or open: F14;
- not covered: F1, F11, F13.

**Re-found blind:**
- F2 and F12 (parts) by B1, with no leak flag;
- F2, F4 and F9 by B2 (F4 with a leak flag);
- F6 by B1;
- F10 by both, model-only.

Neither blind run found F1, F3, F5 (B2's attempt failed replay), F8, F11, F13 or F14.

## §11.8 preregistered laws

| law | prediction | factory | match | B1 / B2 counterpart |
|---|---|---|---|---|
| L_par_hdr_v0 | PROVED | PROVED | yes | — |
| L_par_hdr_v1 | PROVED | PROVED | yes | — |
| L_par_hdr_v2 | REFUTED | REFUTED, replayed | yes | — |
| L_dom_v0 | REFUTED | REFUTED (as `L_dom_hdr`), replayed | yes | B1-F7 REFUTED, replayed |
| L_undo_CSR, L_undo_BD | PROVED | PROVED, PROVED | yes | — |
| L_undo_BVH | REFUTED | REFUTED, replayed | yes | B1-F1; B2 `F_undo_commit_revert_residue` |
| L_undo_cancel | REFUTED | REFUTED, replayed | yes | — |
| L_sort_remaining | REFUTED | REFUTED, replayed | yes | B2 `F_sort_commit_panic_reachable` (leak flag) |
| L_tag_BVH | REFUTED | REFUTED, replayed | yes | B1-F3 |
| L_disch_delay | profile | 4 profile laws PROVED | yes | B2 `L_disch_delay_guard_cost` PROVED |
| L_disch_stale | blocked for permissionless committers | `L_disch_stale`, `L_disch_stale_commit` PROVED | yes | B1-F5 REFUTED, replayed (only an active submitter can discharge); B2 `L_disch_stale_*` PROVED |
| L_fact_Z | REFUTED | REFUTED, replayed | yes | B1-F4; B2 `F_fact_blob_kernel` |
| L_sym_ω | REFUTED | REFUTED (intent_question), replayed | yes | B2 replay failed (model defect) |
| L_own_txspayload | REFUTED, conditional | REFUTED, replayed | yes | B2 `F_own_view_intact_reachable_b3` |

## Blind findings outside Appendix A

| finding | run | replay | assessment |
|---|---|---|---|
| `initialize3` has no caller restriction | B2 | replayed on a fresh proxy | **not live on mainnet**. Storage slot 0 of the Rollup proxy `0x7598…CeF60` reads `4` at latest. My inference: under the OpenZeppelin 4.x layout that is `_initialized`, so version 3 is already consumed. The issue applies only to deployments that don't upgrade and initialize atomically. |
| role separation: a swapped submitter fails earlier | B2 | replayed | informational |
| `setPause` residue on later commits | B2 | replayed | informational, intended |
| challenge then prove is not an undo | B2 | replayed | informational |

## Factory defects the blind runs exposed (open)

- The trace-search policy covers only the Rollup and Go batch-data machines. Quantified laws on the Submitter, router or messenger cannot be refuted and come out UNKNOWN.
- The Go extractor emits identifiers with an apostrophe, and a `txsPayload` input shadows a state field, so the lifted Go facts don't compile in Bend. Both blind runs hit this.
- The blind replay lineariser lacked `last_ok`.
- `proj` erases the named registers. Its documentation misled B2 into three trivially false laws.
- G9 needs `spec/M2/schemas/result_v2.json`, which the bundle omits.
- G4 has fewer than 10 canaries for new milestones.
- B2 found two extraction defects: Submitter `removeSubmitter` lacks `onlyOwner`, and `withdraw` takes the Rollup index as a free input.

## Audit round 2 (`docs/audit/round2.md`) remediation state

| audit | state |
|---|---|
| F1: PROVED scenario laws bypass G6 | fixed. M3 milestones are added to the record gates. G6 binds PROVED laws only when their prediction entry marks them as findings. O13/O14/O29/O34 are restated as REFUTED laws and replayed with a mechanical model-vs-chain verdict |
| F2: NAT effects spec-written, vacuous slash law | provenance fixed (`spec` label, 56 `spec_bound` items). One-shot `reinitializer(4)` recorded as debt. The new laws disclose the spec-bound premise. The non-vacuous control is UNKNOWN |
| F3: router body forced; not-found certified as PROVED | not-found is now a sentinel (`sentinel_value` debt, collides with address 1). `L_rt_before_start` went PROVED → REFUTED (artefact, ERRATA). `getVerifier` AST extraction and the Rollup-linked F14 law are open |
| F4: `_nextQueueIndex` emitted into the wrong input | fixed with per-action `emit_overrides`, plus an unused-input differ test (26 items) |
| F5: preregistration drift | `spec/M3/predictions.json`, sha in the spec Amendments, GPRED gate, and facts rebinds in `laws/*/ERRATA.json` |
| F6: duplicate messenger law | superseded by `L_msgr_sender_can_replay`. The old law is kept unchanged |
| F7: npm-dependent test failures | the tests now provision or skip cleanly; `setup_env.sh --replay` runs `npm ci` |
| F8: M2 replay scope | disclosed: the 45,240/45,240 result covers plain `commitBatch` only |

## Coverage debt and gate state

- **All M3 gates pass**, M3_nat, M3_msg, M3_router and M3_sorts, with 0 uncovered actions or registers. M0 and M1 pass too.
- **How the earlier G8 holes were closed:**
  - **Extraction fixes, so no hole is hidden** (`07d4905`, `8369b08`):
    - the OZ owner guard now reads the `own` register instead of the constant `OWNER`;
    - MVRV `rollup` is now a state register written by `initialize`;
    - the register list now leaves out three registers that no extracted source path reads: MVRV `t`, and messenger `bf`/`fq`. The fee stays abstracted as the input `amt`, disclosed by `defs.est_fee.body`.

    All law statuses stayed the same after these fixes; the facts rebinds are recorded in ERRATA.
  - **28 coverage laws** `L_cov_*` (`spec/M3/laws_src/r3_cov_laws.py`), preregistered in `1023e72` before any run. All are predicted PROVED from the pinned Solidity source. One generator encoding erratum was fixed before any NAT law ran (`37a2970`).
- **Results:** 27 PROVED as predicted.
  - **The miss:** `L_cov_rt_vap_unregistered_fails` came out REFUTED. The model routes an unregistered version to the `b_nf` sentinel, whereas `MVRV:117-118` reverts `ErrorVerifierNotFound`. This is the same sentinel artefact as `L_rt_before_start`. Its triage is `none` and it is published as a GPRED miss.
- **Limit:** most `L_cov_*` laws are guard and success scenarios, one step past a fixed setup. They show that each action is reachable and that its guard reasons match the source. They are not full functional specifications of the action's effects. G8 counts an action as covered when a law touches it.
- M0, M1 and M3_sorts pass.

## M2 record (unchanged)

M2 met the replay target: 45,240 of 45,240 checks agree across 1,131 commits.

It missed mutation adequacy in all three frozen rounds, against a threshold of 0.80:

| round | score |
|---|---|
| A1 | 19/45 = 0.42 |
| A2 | 14/30 = 0.47 |
| A3 | 16/30 = 0.53 |

## Prediction accuracy

| run | correct | detail |
|---|---|---|
| Factory, §11.8 | 14/14 rows | |
| Factory, M3 laws | 39/41 | `L_natr_slash_at_stake_native` predicted PROVED, came out UNKNOWN; `L_rt_before_start` predicted PROVED, now REFUTED after the AUDIT_R2 F3 facts rebind (ERRATA) |
| B1 | 22/32 | |
| B2 | 34/41 | |
