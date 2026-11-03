# I92 (= I34b): rule SYM over Bundle I — O21 and the messenger's sentinels

You are building I92 on M3. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then this key's
contract, `tests_m3/test_sym_bundle.py` (rules K1-K12), its instrument `tests_m3/_i92.py`, its sidecar
`spec/M3/lib/sym_bundle.json` and basis `spec/M3/lib/sym_bundle_basis.json`, and the key itself,
`spec/M3/predictions/I92.json`. The predictions are fixed. A prediction that misses is reported as missed, with what
happened. Never weaken a claim, special-case a law id, or hand-write a generated file.

## What I92 is

I34 stated SYM over the typed Rollup alone. Its J1 scope left out O21 and the messenger's sentinels, because no M3
machine had three things:
- the queue's enqueue actions in model3;
- a migrated legacy-queue state;
- nominal sorts over the bundle members.

I92 builds those three, then derives and decides SYM's tau and sentinel laws over the queue and the messenger, and
tau over the Rollup-queue link.

**O21.** `getFirstUnfinalizedMessageEnqueueTime` reads `messageEnqueueTime[pendingQueueIndex] == 0` as "no pending
message".
- The mapping arrived in v0.4.10 (#849). A message enqueued under v0.4.9 reads enqueue time 0 after the upgrade.
- So the Rollup's "l1msg delay" check skips it.
- On the Rollup alone, I34's tau laws for commitBatch, commitState and commitBatchWithProof are UNKNOWN. Over the
  versioned link, I92 predicts them REFUTED at queue :262.

## Order of work

1. **model3 (K8).**
   - Add the length of a storage dynamic array, and its push, to `holon/sorts/model3.py`.
   - The change is additive: every model model3 compiled before stays byte-identical, except the queue's bundle model,
     which gains appendCrossDomainMessage, appendEnforcedTransaction and getCrossDomainMessage.
   - Regenerate the bundle models with holon's own command, and check every other member's sha256 against the
     sidecar's `bundle_models_sha256`.
   - This touches the generator closure, so the landing re-stamps M1, M2 and T32.
2. **The legacy queue (K1).**
   - Extract the queue at `legacy.commit` (v0.4.9) with I69's frontend and sidecar, from a scratch worktree of the
     target checkout, into `gen/M3/symb/legacy/queue.json`.
   - Compile its model into `gen/M3/symb/legacy/`.
   - Write `gen/M3/symb/eta_enq.json` (K3) from the two documents' storage lists, never by hand.
3. **Sorts (K2).**
   - Extend holon's sort inference to the member documents: Time and Idx, with the fixed point K2 states.
   - Write `gen/M3/symb/sorts.json`. holon/ names no member, register or contract (R4): the rules come from the terms.
4. **The link (K3).**
   - If I94 has landed a Bend linked layer and versioned reach that are generic in the callee member and its version
     chain, use them.
   - Otherwise write, under `gen/M3/symb/`, two links in which the callee runs its extracted transitions:
     - Rollup → queue (the getter);
     - messenger → queue (nextCrossDomainMessageIndex, appendCrossDomainMessage).
   - Add a queue member whose version chain is v0.4.9 → upgrade (eta_enq) → head.
5. **Laws (K5).**
   - SYM's producers over the members and the link, under the next free catalog version (J4's shape: every earlier
     producer the same object).
   - `holon derive` must write exactly the basis's law ids.
   - Statements use I34's terms. The link laws add the premise that every reach step's block_timestamp is at least 1;
     disclose it in the record.
6. **Decide (K6) on runners.**
   - Use `holon land plan`, then `apply`.
   - Never commit a record made with the container's unpinned checker.
   - A REFUTED tau record names its site and site_kind. A link law's record carries sym.prefix, with the upgrade step.
7. **Replays (K7).**
   - The forge harness deploys the v0.4.9 queue behind its proxy and enqueues through the messenger.
   - It upgrades to the head implementation, then runs the Rollup's action from s and from tau_d s.
   - Write `replay/M3/symb/<law>.json` for every REFUTED law.
8. **Head-only contrast (P6).**
   - Run the same search with the queue at the head only. Write `results/M3/symb/head_only.json` (law → site or null,
     and bound).
9. **Report.**
   - Write `docs/iterations/I92.md`. Commit it first on I92's own line, before any landing merge: R2 reads the
     first-parent range up to it.
   - Run the contract and `holon audit prereg` for M3 and M2.

## Limits and fallbacks

- **Time box: about two working days of build.**
  - A Reach induction that cannot close, such as the lastIndex invariant across the two members, stays UNKNOWN naming
    the invariant.
  - A link the layer cannot express stays UNKNOWN naming the missing piece.
- **Not this key's (K12):**
  - pi and omega over the members;
  - iota's laws;
  - revertReqIndex (Q-S4);
  - computeTransactionHash's wbyte;
  - the members' other versions.
- **Overlap with I94.** I94 also edits model3 (a deleted struct's dynamic bytes members). Merge with it; don't
  conflict. Keep every model byte-identical except the ones each key names.

## The PR description ends with

- **Done:** what changed and which tests pass. Include the summary line of
  `python -m unittest discover -s tests -t . -v` from CI's frozen-suite job.
- **Surprises.**
- **Questions for the human.**
- **Not done.**
