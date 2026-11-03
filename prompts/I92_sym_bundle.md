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

I92 builds those three, then derives and decides SYM's tau and sentinel laws over the queue and the messenger. O21 is
stated as the getter's sentinel invariant over the versioned queue.

**O21.** `getFirstUnfinalizedMessageEnqueueTime` reads `messageEnqueueTime[pendingQueueIndex] == 0` as "no pending
message".
- The mapping arrived in v0.4.10 (#849). A message enqueued under v0.4.9 reads enqueue time 0 after the upgrade.
- So the Rollup's "l1msg delay" check skips it.
- The getter assumes that every pending message has a nonzero enqueue time. Every head enqueue keeps that, and the
  upgrade breaks it. That is the invariant law, predicted REFUTED over the versioned queue.
- Why not tau: I34's tau leaves a key the store does not hold at 0 (holon.gen.symsec's documented limit). The
  migrated zero is such a key, so both runs take the same branch and the tau form cannot see O21.

## Order of work

1. **model3 (K8).** Add three constructs to EXT1, I70's extension in `holon/sorts/model3.py`:
   - EXT1's length takes a storage path, not only a carried view;
   - Yul byte, `["wbyte", x, n]`: byte n of x, 0 the most significant, 0 past the word;
   - a top-level conditional memory write, compiled as a helper of the action's input and the memory, as `mloop`
     is. Inline, the RLP encoding's 18 conditional writes duplicate the memory term past 90 MB.

   Then:
   - The bundle compiles its members with EXT1.
   - The queue's debt goes to none: all four actions, computeTransactionHash included.
   - Every other model stays byte-identical: the other three bundle members (check them against the sidecar's
     `bundle_models_sha256`), and I70's cutover models (`holon cutover ... --check`).
   - No committed law imports the queue's bundle model.
   - This touches the generator closure, so the landing re-stamps M1, M2 and T32.
2. **The legacy queue (K1).**
   - Extract the queue at `legacy.commit` (v0.4.9) with I69's frontend and sidecar, from a scratch worktree of the
     target checkout, into `gen/M3/symb/legacy/queue.json`.
   - Compile its model into `gen/M3/symb/legacy/`.
   - Write `gen/M3/symb/eta_enq.json` (K3) from the two documents' storage lists, never by hand.
3. **Sorts (K2).**
   - Extend holon's sort inference to the member documents: Time and Idx, with the fixed point K2 states.
   - Write `gen/M3/symb/sorts.json`. holon/ names no member, register or contract (R4): the rules come from the terms.
4. **The link and the versioned queue (K3).**
   - Use I94's linked layer and versioned reach (PR #100, its P5).
   - The messenger → queue link (nextCrossDomainMessageIndex, appendCrossDomainMessage) is for the lastIndex sentinel.
   - The versioned queue, v0.4.9 → upgrade (eta_enq) → head, is for the invariant.
   - A piece I94 does not provide, write under `gen/M3/symb/`.
5. **Laws (K5).**
   - SYM's producers over the members and the link, under the next free catalog version (J4's shape: every earlier
     producer the same object).
   - `holon derive` must write exactly the basis's law ids.
   - Statements use I34's terms and comparison. One exception: a view's return word whose return term K2 sorts Time
     is translated in the first run's observation, as J3 compares the outcome and the logs' Time words.
   - The sentinel invariant (K4) is stated over the versioned queue, with the premise that every reach step's
     block_timestamp is at least 1. Disclose that premise in the record.
6. **Decide (K6) on runners.**
   - Use `holon land plan`, then `apply`.
   - Never commit a record made with the container's unpinned checker.
   - A REFUTED tau record names its site and site_kind.
   - The invariant's record names the view (its site) and carries sym.prefix, with the upgrade step.
7. **Replays (K7).**
   - The forge harness deploys the v0.4.9 queue behind its proxy and enqueues through the messenger.
   - It upgrades to the head implementation, then reads the getter while a message is pending.
   - Write `replay/M3/symb/<law>.json` for every REFUTED law.
8. **Head-only contrast (P6).**
   - Run the invariant's search with the queue at the head only. Write `results/M3/symb/head_only.json` (law →
     status, and bound).
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
  - tau over the Rollup-queue link (the migrated zero is no tau break);
  - revertReqIndex (Q-S4);
  - the members' other versions.
- **Overlap with I94.** I94 also edits model3 (a deleted struct's dynamic bytes members). Merge with it; don't
  conflict. Keep every model byte-identical except the ones each key names.

## The PR description ends with

- **Done:** what changed and which tests pass. Include the summary line of
  `python -m unittest discover -s tests -t . -v` from CI's frozen-suite job.
- **Surprises.**
- **Questions for the human.**
- **Not done.**
