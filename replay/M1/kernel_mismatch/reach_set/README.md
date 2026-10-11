# BendTT kernel mismatch on large deduplicated record lists

Second kernel-mismatch case (next to ../LAWS.bend + morph_batchdata.bend, the
OWN batchdata case). This one is a reach-set: a large list of *distinct*
25-field records normalised in one term.
Bend 2.0.36, bun runner, upstream commit 2343aec, Lean 4.34.0 via elan,
kernel cached at ~/.bend/bendtt.

`model/rollup_sm.bend` is a generated 25-field record state machine
(`State`, `Outcome = Ok|Revert|Bound`, `succs`, `expand_all`, deduplicated
`reach_k`).

Reproducer:

    cd failing  && bend --verdict PROOF.bend
    -> plain `bend PROOF.bend` prints ALL PROOFS CHECK, but --verdict prints:
       "Sorry - this is a mismatch between the TypeScript implementation,
        and the formalized BendTT kernel. ..."

    cd passing  && bend --verdict PROOF.bend
    -> ALL PROOFS CHECK (both plain and kernel)

Bisect results (same model):

- `llen(M.reach_k(0n))`, `reach_k(1n)`, `reach_k(2n)` pass --verdict.
- `llen(M.reach_k(3n))` fails --verdict. reach_k(3) has 1308 unique states.
- `llen(mklist(1500, init_state()))` passes: a longer list of a single
  shared record is fine.
- `llen(List.append(mkn(224), mkn(1084)))` over `List<&2, Nat>` passes.
- `llen(M.expand_all(M.reach_k(2n)))` passes (~5.9k expanded states).
- `llen(M.add_fresh(M.expand_all(M.reach_k(2n)), M.reach_k(2n)))` passes
  (the layer-3 dedup alone).
- `llen(List.append(s2, f3))` where s2 = reach_k(2) (224 states) and
  f3 = layer-3 fresh (1084 states) FAILS.
- `myapp(f3, [init_state()])` (1085 records) passes; `myapp(f3, f3)`
  (2168 records) fails. Hand-rolled append behaves like List.append.
- Checking each state during a fused no-dedup fold (passing/) passes:
  the same states are evaluated, but no single ~1.3k-record list is
  ever materialized as a proof term.

Minimal trigger hypothesis: normalizing a single list term containing
roughly 1.3k+ distinct large records (25 fields) diverges between the
TypeScript checker and the BendTT kernel. State dedup in `add_fresh` /
`contains_state` / `state_eq` is not itself the trigger (a single
layer-3 dedup passes); the failing term is the materialized result.
