# I29: rule NAT over I28's versioned machine

The plan is BUILD_PLAN §4's I29 (NAT rule; milestone M3; after I28). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (N1-N10) are in the docstring of `tests_m3/test_nat.py`. I28's contract (the versioned machine, its in-flight types, its trace format and harness) is the docstring of `tests_m3/test_versions.py`.

## What NAT means here

Whitepaper §5.3: for each migration, each in-flight object type and each new-version operation that reads it,
- (a) native equivalence, op'(η(s)) ≈ op'(s^nat);
- (b) naturality, η ∘ op = op' ∘ η where op exists in the old version;
- (c) composition coherence: all reachable migration sequences coincide.

Thm 6.7 (c) says entry points × in-flight types, plus reachable migration sequences, suffice.

I28 built the machine this needs: the deployed path V3 .. V11 behind the transparent proxy, one storage, migration steps by upgradeTo or upgradeToAndCall, and VReach from the proxy's creation. Its in-flight types (rule V3) are the in-flight entries of kind retyped or reinterpreted. On the path there are two, both at the cutover V10->V11:
- `batchDataStore`: the struct's fourth word was `signedSequencersBitmap` and is now `submitter`;
- `submitterContract`: it occupies `l1StakingContract`'s slot.

## The rule, as built

- **(b) Naturality squares (N3).** For each in-flight type, the readers at the new version of its touched words, restricted to those with a same-selector action at the old version: proveState for both types, challengeState for submitterContract. Three laws.
- **(c) Composition (N2).** Each ordered pair of the path's introduced initializers (initialize at the entry edge, initialize2, initialize3, initialize4) whose early one exists at the late one's edge with one selector. The law is the square of the early initializer across the late one's edge. Six laws; O18 (η₄ before η₃ leaves D = 0) is `L_nat_comp_Rollup_initialize3_initialize4`.
- **One claim for both sub-forms (N5).** From a reachable state s, compare "migrate, then op at b" with "op at a, then migrate". They must reach the same version and the same storage, with the same success of the op and of the migration (definedness included).
- **(a) Native equivalence (N4) is a generated gap record per (in-flight type, reader).** The machine has no native state for an in-flight object:
  - the writers of the touched words at V11 are commitBatch and commitState, whose selectors changed;
  - the native submitter registry is external.

  So nothing can be stated. Six gaps.

## Decision

- **Search.** Breadth first from vr0 over the upgrade path's kinds of steps and the deployment record's calls (N7), with upgradeTo allowed on every edge (A-proxy). A witness is a state and a square whose claim is false on the versioned machine.
- **Proof.** Its counter-law is checked by Bend over the layer.
- **Replay.** Its two orders are replayed on the real code through I28's harness (N9).
- **No prover.** No generator proves a square: that needs induction over VReach. A square with no witness is UNKNOWN, with what was tried.

## Predictions, and what of BUILD_PLAN is not adopted

- **P1.** The six composition laws are REFUTED by the shortest migrations-only witnesses. Running the late reinitializer first locks out the early one for good.
- **P2.** The three cutover squares are UNKNOWN. I28's model compiles no commit before V11 (model debt), so no in-flight batch is reachable, and the squares hold on the model's reachable states. BUILD_PLAN's "O14 REFUTED" is therefore not adopted, and O13/O14 stand as naturality laws plus native gaps.
- **P3.** Every REFUTED witness replays.
- **Not generated:**
  - O16 (η_enq is the queue's; no extracted history);
  - O17 (an added variable is no in-flight type);
  - "unchanged entry points PROVED" (NAT squares only readers of in-flight types, and has no prover).
- **R1.** The O15 analogue (M1's `L_nat_eta2`) stays REFUTED.

## Questions for the human (stated at the prereg)

- **I29-Q1.** How should s^nat be defined for an in-flight object whose writers' ABI changed across the migration, or whose native value is an external contract's? (Native equivalence, §5.3 (a); the six gaps.)

## Commands

```
python -m holon nat analyze|replay [--check]
python -m holon derive --milestone M3
python -m holon run --milestone M3 --laws <NAT ids>
```
