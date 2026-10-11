# M3 (U3): refined semantic sorts — `holon/sorts/`, SORT laws for O20 / O21 / O27 / O28

Morph commit `3e44e795586af3e11285b603ab642c67823add51`. Everything below is generated:
`python -m holon sorts` (inference, sorted facts, 7.8 Bend types, registry) then
`python -m holon run|replay|gate --milestone M3_sorts`. Running `sorts` twice leaves the tree byte-identical (tests_m3).

## What was built

| piece | where | whitepaper |
|---|---|---|
| sort grammar `Mach(w) | Time | Dur | Dur- | Idx[k] | Cnt[k] | Cnt[k]- | Prin[r] | Amt[u] | Dig[d] | Ver | Bool | Null | A+B | <rec> | List<S>` | `holon/sorts/grammar.py` | 7.1 |
| affine rules (`Time - Time = Dur-`, `Time + Dur = Time`, `Time + Time` ill-sorted, `Idx - Idx = Cnt-`, principals/amounts never arithmetic), width of sums, realize / width / sentinel obligations | `holon/sorts/rules.py` | 7.2, 7.5, 7.6, 7.8 |
| inference over the frozen facts: seeds (`spec/M3/sorts/seeds.json`) -> fixpoint over state, record fields, actions (guards, effects), definitions, migrations; writer provenance per register/field; untagged-union reads, `== 0` tests on unions and Time registers, signed realizations, width overflow | `holon/sorts/infer.py` | 7.3, 7.4, 7.7 |
| frozen assignments (functoriality 6: the assignment is frozen before Bend typing) | `spec/M3/sorts/assignment/*.json` | 6, 7.7 |
| sorted facts: the M1 rollup facts + the cited extensions (`addChallenger` Rollup.sol:527-531, `legacy_enq` pre-upgrade storage, principal/sentinel observers) — M1 facts untouched | `holon/sorts/factsgen.py` -> `spec/M3/sorts/facts/morph_rollup.sorted.json`; O28 facts `spec/M3/sorts/facts/morph_batchdata_l1num.json` | 8.3 |
| sorts as Bend nominal types with coercion obligations: `realize_SDur(x, nonneg)`, `as_U_.._Prin(u, tag)`, `narrow_16(v, bound)`, affine ops typed by sort; `--verdict` checked; 4 canaries that Bend must reject | `holon/sorts/bendgen.py` -> `spec/M3/sorts/gen/sorts.bend` | 7.8, 8.8 |
| SORT law class (rule `SORT`, subforms `realize`, `principal`, `sentinel`, `width`), emitted through the existing M1 emitter / counter-law / `--verdict` pipeline | `spec/M3/sorts/laws/`, `results/M3_sorts/` | 5, 8.4 |
| gate G4 canaries for refuted laws (`negated`: certificate at the empty trace; `witness_prefix`: one step short of the witness) + `sort_*` canaries | `holon/mcanary.py`, `holon/gate.py` | 8.8 |

Inference over `spec/M1/facts/morph_rollup.json`: 49 obligations, 0 conflicts (15 sentinel tests, 11 signed realizations of which
6 are discharged by a guard, 10 ghost-tag tests, 6 tag writers, 4 width, 2 union reads, 1 mismatch). Registers (excerpt):
`t : Time`, `W F D : Dur`, `enq : List<Time>` (with `Null` writer from pre-upgrade storage), `qpend : Cnt[msg]+Idx[msg]`,
`chs.c : Null+Prin[challenger]`, `win.bds : Null+Prin[submitter]`, `win.bvh : Dig[agg]+Dig[bvh]+Null` (O26 = M1 `L_tag_BVH`, not duplicated).

## Results

| law | obstruction | status | replay | note |
|---|---|---|---|---|
| L_sort3_remaining | O27 | REFUTED | Foundry **passed**: last step `rev panic:0x11` | the statement is *identical* to M1 `L_sort_remaining` (tests_m3 asserts it): the SORT rule *derives* it — `W + cstart - t : Dur-` realized as `uint256` at Rollup.sol:363 with no sign premise |
| L_sort3_width_l1num | O28 | REFUTED (k = 65535) | Go **passed**: `l1TxNum=0` after 65536 L1 hashes (`spec/M3/sorts/replay/go/`) | `Σ len(l1TxHashes)` needs 17+ bits, `l1TxNum` is `uint16` (batch_data.go:41,105-107); the header total is 64-bit, so the narrowing is intermediate |
| L_sort3_prin_submitter | O20 | REFUTED | Foundry **passed** (trace accepted; the Null principal is invisible on chain) | `commitBatchWithProof` stores `submitter = address(0)` (Rollup.sol:411); a later timeout `_challengerWin(idx, batchDataStore[idx].submitter)` (Rollup.sol:616) would slash address(0). Whether such a batch can still be challenged is not decided by this law |
| L_sort3_prin_challenger | O20 | REFUTED | **model-only pending replay** | `addChallenger(address(0))` is accepted (Rollup.sol:527-531, no nonzero check), then `isChallenger[address(0)]` lets the Null principal start a challenge; the Foundry harness cannot call from address(0) |
| L_sort3_enq_sentinel | O21 | REFUTED (empty trace from `legacy_enq(s0, [7])`) | **model-only pending replay** | with a pre-upgrade message (`messageEnqueueTime == 0`), `enq_first` reads the sentinel `!= 0` as "not pending" (L1MessageQueueWithGasPriceOracle.sol:261-268); needs a fork with pre-upgrade storage |
| L_sort3_enq_fresh | O21 | UNKNOWN (bounded search, no proof) | — | from the post-upgrade `s0` every writer of `enq` is `t >= 10`, so no witness exists; the generator has no proof strategy for this observer invariant yet |

Gate: GENV, G1-G5, G7 (BendTT `--verdict` on the 5 counter-law certificates and on `sorts.bend`), G11 pass; G4: 10 canaries of
6 kinds, all rejected for semantic reasons (`results/M3_sorts/gate_report.json`). Refinement corpus of the replay: 60 traces, 510 steps, 0 disagreements.

## Known limits
- The SORT laws are compiled *by hand from the frozen obligations* (each law's `notes` names its obligation); the obligation -> law
  step is not yet automatic. The assignment, facts, types, proofs and canaries are generated.
- Pending replays: address(0) caller (prin_challenger) needs a `vm.prank(address(0))` harness step; enq sentinel needs pre-upgrade storage.
- `docs/M2_SPEC.md` named in the brief does not exist in the tree.
