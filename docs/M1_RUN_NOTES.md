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
| L_inv_prefix | 5 | PROVED | PROVED@bound | yes | checked |
| L_inv_one_challenge | 5 | PROVED | PROVED@bound | yes | checked |
| L_par_hdr_v2_composed | — | PROVED | PROVED | yes | checked |

All 9 laws now match predictions: 6 REFUTED + 3 PROVED.

## --verdict mismatch bisected and fixed (Task A)

Original `{all_states_<lid>(M.reach_k(K n)) == True{}}` laws passed plain
`bend` but `--verdict` reported "mismatch between the TypeScript
implementation, and the formalized BendTT kernel". Bisect under /tmp/vmt:

- `reach_k` laws for K<=2 verdict-OK; K=3 (1308 unique states) fails.
- A `llen` law over a 1500-element list of the *same* 25-field record passes;
  a 1085-record append passes; ~1300+ *distinct* 25-field records in one list
  term fails. Trigger = normalized size of the materialized deduplicated
  `reach_k` list term, not the dedup/equality functions themselves.
- Fix (generator-only, `holon/sm_emit.py`): for K<=3 emit a fused per-layer
  fold `check_reach_<lid>(k, frontier)` that checks each expanded frontier
  layer including the base — the exact same universal claim (every state
  reachable in <=K Ok steps satisfies check), without materializing the
  deduplicated list. K>3 keeps `all_states(reach_k)` (the undeduplicated
  per-layer expansion would be ~1172 states/layer x 5, too large for the
  plain checker). Keyed on K, not law ID.
- Both invariant laws now PROVED (verdict=checked). Minimal reproducer:
  `bend/notes/verdict_mismatch/` (failing + passing PROOF.bend, model copy,
  README with commands, outputs and the bisect table).

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
| L_inv_prefix | 2.03 | — | — | ~0.3 (fused fold; was 7.83 kernel-rejected) |
| L_inv_one_challenge | 2.11 | — | — | ~0.3 (fused fold; was 7.64 kernel-rejected) |
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
- **Kernel verdict**: the two invariant laws originally failed `--verdict`
  (TS-vs-BendTT mismatch on the materialized ~1.3k-element `reach_k` list);
  fixed by the fused per-layer fold (see above). Reproducer under
  `bend/notes/verdict_mismatch/` for an upstream report.
- **Bend codegen hazards hit**: callee-before-caller ordering required;
  recursive helpers must match the fuel parameter first; `Ok{+s}` needed to
  reuse states; mutual recursion rejected (rewritten with `Bool.pick`).
- **Node stack**: the compiled `reach_k` equality/dedup helpers exceed the
  default Node stack at layer ≥4; `eval_sm_jobs` now invokes node with
  `--stack-size=65500`.
- **Early pipeline bug found by the oracle tests**: loop bodies originally
  ran the first index twice; caught by `rollup_ref` cross-check before any
  law relied on it.

## Replay on real code (Task B)

All 6 REFUTED witnesses replayed on the real contracts (Morph @3e44e79,
read-only; harness `replay/M1/solidity/Harness.t.sol`, real Rollup +
ERC1967Proxy, real L1MessageQueueWithGasPriceOracle + proxy, real Submitter +
proxy, accept-all verifier; config F=2, P=2, D=3, genesis at t=1):
`forge test --match-path test/M1Harness.t.sol -vv` — 6/6 PASS. Report:
`replay/M1/report.json`, `replay/M1/README.md`.

- undo_commit_revert: after commit + revertBatch(1,1),
  `batchBlobVersionedHashes(1) != 0`, `batchDataStore(1)` and
  `committedStateRoots(1)` retain residue (model's claim failure confirmed).
- undo_enabled: commitBatch then reverts "commitBatch requires no stored
  blob hash"; commitState succeeds and recommits batch 1.
- undo_pause: challenge(1) extends batch 2 fin_ts 3->5; pause/unpause leaves
  it at 5; re-challenging batch 1 succeeds and extends it again to 7
  (extra observation past the model witness).
- disch_nonowner: after timeout proveState, revertReqIndex=1 and the
  submitter is slashed; every non-owner path (commitBatch on a re-staked
  submitter, commitState, commitBatchWithProof, challengeState, proveState,
  finalizeBatch) reverts "pending revert request"; owner revertBatch clears.
- disch_timeout: past the window, commitBatch and commitBatchWithProof
  revert Panic(0x11), challengeState reverts "already in challenge";
  setPause(true) clears with no slash (submitter stays active).
- nat_delay_frontier: enqueue -> commitBatch(1 msg) -> warp 5 ->
  commitBatch(0) reverts "l1msg delay"; permissionless finalizeBatch pops
  the message and lifts the guard.
- M0 closure: real commitBatch at version 2 through the deployed Rollup;
  byte0==2, ssvh==0, committed bytes == model `enc_go_v2_producer` output
  evaluated via holon/model_eval (byte-for-byte). Go side drives the real
  `createBatchHeaderWithSequencerSetHash` on a hand-built BatchCache in
  `~/ext/morph_scratch` (test copied to `replay/M1/go/`) — same 257 bytes
  match. No divergences between model and real code.

## Triage after replay (config/triage.json, set by the lead after reading replay/M1)

| Law | Triage | Why |
|---|---|---|
| L_undo_commit_revert | intent_question | revert leaves blob hash / batch data / state root; commitState is the designed recommit path |
| L_undo_enabled | intent_question | same residue; commitBatch blocked, commitState works |
| L_undo_pause | finding | pause cancels the challenge but keeps the +proofWindow extension; re-challenge stacks it again (real Rollup: 5 -> 7) |
| L_disch_nonowner | intent_question | revertReqIndex blocks all non-owner transitions until owner revertBatch |
| L_disch_timeout | finding | after the proof window, only the submitter (self-slash) or the owner can close the challenge; commits revert with Panic(0x11) meanwhile |
| L_nat_delay_frontier | intent_question | guard reads the finalized frontier; permissionless finalizeBatch lifts it |

Caveat: the reach-reflection proofs use a fused per-layer fold for K<=3 (kernel limit, see bend/notes/verdict_mismatch/). Above K=3 the generator falls back to the reach_k form, which currently fails --verdict.
