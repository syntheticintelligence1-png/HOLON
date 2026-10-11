# M1 run notes — rollup state-machine slice

Branch `devin/m1-sm`. Pipeline: `python3 -m holon run --milestone M1`, gate:
`python3 -m holon gate --milestone M1` (exit 0). Facts:
`proposals/M1/facts/rollup_sm.json` (config N=3, F=2, D=3, P=2, Q=2, T=12;
11 actions; K per law statement).

## Status vs predictions

| Law | Bound K | Status | Predicted | Match | kernel verdict |
|---|---|---|---|---|---|
| L_undo_commit_revert | 1 | REFUTED | REFUTED | yes | checked |
| L_undo_enabled | 1 | REFUTED | REFUTED | yes | checked |
| L_undo_pause | 1 | REFUTED | REFUTED | yes | checked |
| L_disch_nonowner | 4 | REFUTED | REFUTED | yes | checked |
| L_disch_timeout | 4 | REFUTED | REFUTED | yes | checked |
| L_nat_delay_frontier | 5 | REFUTED | REFUTED | yes | checked |
| L_inv_prefix | 5 | UNKNOWN | PROVED@bound | no | failed |
| L_inv_one_challenge | 5 | UNKNOWN | PROVED@bound | no | failed |
| L_par_hdr_v2_composed | — | PROVED | PROVED | yes | checked |

Both invariant laws: the plain checker prints `ALL PROOFS CHECK` on the
generated `{all_states(reach(K), check) == true}` law proved by `{==}`, but
`bend --verdict` reports a mismatch between the TypeScript implementation and
the formalized BendTT kernel, so per policy the status is UNKNOWN (checker is
authoritative). The proofs themselves are the exact bounded-reach laws; this
is a tool/kernel limitation, not a model disagreement.

## Witness traces (plain words)

- **L_undo_commit_revert** (depth 0, forall `act=commitBatch, n=0, r=1`): at
  init, `revertBatch` does not undo the effects claimed by the law — after a
  commit+revert the residue `blob/origin/fin_ts/state_root/hdr_*/submitter[1]`
  stays set. Witness is the empty trace at init with that forall assignment.
- **L_undo_enabled** (depth 0, `n=0, r=1`): after revert, `commitBatch` still
  reverts on "requires no stored blob hash" — enabled() is false.
- **L_undo_pause** (trace: `commitBatch(0,1)` × 2, forall `i=1`): pause
  deletes the challenge but leaves the +proofWindow extensions on other
  batches, so the claimed undo does not restore the pre-challenge state.
- **L_disch_nonowner** (`commitBatch(0,1)` → `challengeState(1)` → `tick(2)`
  → `proveState(1)`): after the challenger wins at index 1, a non-revertBatch
  transition is claimed enabled but is not — `revertReqIndex` blocks it.
- **L_disch_timeout** (`commitBatch(0,1)` → `challengeState(1)` → `tick(1)` →
  `tick(2)`): the claimed discharge-by-timeout transition is not enabled.
- **L_nat_delay_frontier** (`enqueue()` → `commitBatch(1,1)` → `tick(2)` →
  `tick(2)`): queue has 1 pending message, `q_pending=0`, `lastCommitted=1`,
  `now=5` — frontier delay claim fails.

## Timings (plain proof attempt / witness search / counter-law / verdict, s)

| Law | plain proof | witness BFS | counter-law | verdict |
|---|---|---|---|---|
| L_undo_commit_revert | 0.14 | 0.40 | 0.18 | 0.31 |
| L_undo_enabled | 0.17 | 0.40 | 0.18 | 0.29 |
| L_undo_pause | 0.18 | 0.54 | 0.18 | 0.31 |
| L_disch_nonowner | 5.58 | 1.79 | 0.25 | 0.73 |
| L_disch_timeout | 5.54 | 1.34 | 0.27 | 2.33 |
| L_nat_delay_frontier | 44.53 | 1.09 | 0.17 | 0.32 |
| L_inv_prefix | 2.03 | — | — | 7.83 (kernel rejected) |
| L_inv_one_challenge | 2.11 | — | — | 7.64 (kernel rejected) |
| L_par_hdr_v2_composed | 0.21 | — | — | 0.37 |

## Reach-set sizes (compiled `reach_k`, unique states per layer)

`model_checked.reach` (informational only): cumulative `[1, 7, 39, 224, 1308,
7554]` for K=0..5 — per-layer `[1, 6, 32, 185, 1084, 6246]`.

## Canaries (G4, M1)

14 canaries across 5 kinds — 12 SM facts mutations (4 drop-req, 4 flip
comparison lt↔le/eq↔ne, 4 drop-set) applied to copies of `rollup_sm.json`
in a temp dir, plus M0-style law-statement canaries for the PAR law.
Detected: 14/14; survivors: none. A surviving SM mutation would have been
reported, not hidden — none survived.

## Surprises / decisions to confirm

- **`for ... while` semantics**: generated loop advances the iterator and
  skips the body when the `while` guard is false (the facts' `while` is
  `committed[j] != 0`; once it fails the body would only touch already-zero
  slots, so modeled end state is unchanged either way — but the intended
  reading is "break"). Please confirm the break-vs-skip reading.
- **Kernel verdict**: the two invariant laws prove under the plain checker
  but `--verdict` rejects with the TS-vs-BendTT mismatch; kept UNKNOWN.
- **Bend codegen hazards hit**: callee-before-caller ordering required;
  recursive helpers must match the fuel parameter first; `Ok{+s}` needed to
  reuse states; mutual recursion rejected (rewritten with `Bool.pick`).
- **Node stack**: the compiled `reach_k` equality/dedup helpers exceed the
  default Node stack at layer ≥4; `eval_sm_jobs` now invokes node with
  `--stack-size=65500`.
- **Early pipeline bug found by the oracle tests**: loop bodies originally
  ran the first index twice; caught by `rollup_ref` cross-check before any
  law relied on it.
