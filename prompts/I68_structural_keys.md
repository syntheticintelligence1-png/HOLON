# I68: structural storage keys in the M3 model (the Q21 fix)

The plan is row I68 of `docs/BUILD_PLAN.md`, section 3. The human's answer is Q21 in `docs/HUMAN_ANSWERS.md` (I30's Question 1). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (S1-S13) are in the docstring of `tests_m3/test_structural_keys.py`. The design this key follows is the Q21 design note: read-only, written by the other session's design pass, with scratch Bend probes.

## Why

- **The table aliases mapping slots.** Today the M3 model computes a mapping slot as `h_get(kh, key ++ slot)`, a lookup in the law's `keccak256` table parameter, and every typed law quantifies that table. Under an adversarial table, such as the empty one, mapping slots alias each other and slot 0.
- **What that costs:**
  - true laws become false (I30's Question 1: the toy's kept-register law has a counter-law at `kh = []`);
  - frames over mapping state have no proof route (I31's gap table: 14 blocking laws UNKNOWN for exactly this reason);
  - every frame needs `w_eq(written slot, B's slot) == False`, which no premise may supply (AGENTS rule 2).
- **Q21's answer.** Key mapping storage structurally, as (base slot, key path). Map keys to real slots with the real keccak256 only against real traces (R5) and in replay. Check every raw slot against every structural image, a collision being a finding. Name the idealisation `A-keccak-structural`. Change no statement.

## What I68 does (rules S1-S12)

- **The store (S1).** `SK{b, o, p}` keys with `SP_m{k, o}` steps, `sk_eq`, and `sload`/`sstore` over `KV` entries. The W-keyed helpers stay for the environment's balance table, and `h_get` for code-level hashes, so F32's eight pinned helpers keep their text. Model version `holon-model-m3/0.3`.
- **Canonical keys (S2).** One SK per real slot, with the offset word always present and key words cleaned as solc hashes them. No storage key goes through `h_get`.
- **Raw slots (S3)** are `SK{r, 0, []}`; on the Rollup that is only initialize4's EIP-1967 admin read.
- **Modes (S4, option A1).** model3 gets a raw mode, which I28's versioned generator passes, so I28's outputs and records are untouched.
- **The deployment (S5).** s0 is converted from the capture's raw slots and recorded preimages: 9 literal, 7 structural, 2 raw. Its real image is the capture exactly.
- **The evaluator (S6)** maps keys to real slots only in R5, the replays, the deployment conversion and the search heuristics.
- **The keys check (S7).** `gen/M3/sorts/keys.json` covers the deployment, the R5 corpus, and every witness and inhabitant. A collision is a finding.
- **The ledger (S8).** `A-keccak-structural` enters through `spec/M3/ledger.json`. `spec/M2/ledger.json` is untouched (I62-D3 pins it).
- **Proof routes (S9-S10):**
  - the SK frame library (the probe's text);
  - frames by evaluation across families and members;
  - key splits on the program's own key words;
  - the convoy (each passed check's equation carried down the chain);
  - loop frames;
  - bit-field lemmas (scope F);
  - `tag_exact`, a Reach induction for SORT tag laws.
- **The lifecycle (S11).** A remodel kind in `holon.statement_diff`, under strict mechanical criteria (a)-(e), licensed by Q21. `holon bind` writes 51 remodel lines, and G2 accepts them. This is the human's to confirm (H1).
- **The recipe (S12).** Typed model, keys, R5, the 51 typed records, the remodel lines, the filter and metrics, plus generator stamps for every M1, M2, T32 and PAR record. The run happens after I28's build is on the lead, so the 51 records are re-made once.

## What was known before this prereg (disclosed)

- The design note's outcomes are readings of the code and the committed records. Its Bend probes ran in scratch:
  - the SK store;
  - the frame library and five frame facts;
  - a Reach induction of a kept-register invariant on a two-action machine.
  Each checked in bend2 and BendTT, and planted errors failed. No generator, refuter, gate or forge ran on the subject.
- In this session before the prereg: the instrument classified the committed capture (9, 7, 2, clean); the 51 typed records' statuses were read; the store, compiler and evaluator code was read. No build code exists.
- **All seven predictions are counted.** None was observed: each needs the structural model built and the 51 records re-made, which has not happened.

## Predictions (key I68 in `spec/M3/predictions.json`)

- **P1.** R5 on the structural model: I20's corpus (460 traces, 3013 steps, 8894 storage comparisons) with 0 disagreements, I20's statuses and panics. The risk is a canonical-form hole: two accesses to one real slot with different keys, or a key cleaned differently from solc.
- **P2.** The keys check is clean, over the deployment, R5, witnesses and inhabitants.
- **P3.** The toy's kept-register law is PROVED by `tag_exact` with an inhabitant; the other toy laws and the guard mutation are as designed. I30-R6's toy clause turns green.
- **P4.** DISCH goes from 13/7/15 to 27/7/1. 14 laws flip to PROVED, all with both kernels: I31's 13 UNKNOWN blocking laws but blk_363_anyone, plus rev_363 and TI2. blk_363_anyone stays UNKNOWN, naming a monotone transport. blk_363_onlyActiveSubmitter stays REFUTED.
- **P5.** Every flipped law but TI4 has a checked reachable inhabitant; TI4's is unknown.
- **P6.** G4's disch_writer canaries exist and are all rejected: I31's exit criterion, met for the first time.
- **P7.** Every proof and counter-law of the 51 records checks in both kernels within budget.

**Regressions.**
- **R1.** No statement, registry, derivation, LAWS.bend or catalog changes.
- **R2.** Every other typed status is unchanged, and every REFUTED witness replays.
- **R3.** M0-M2, T32 and PAR records change in stamps only; gen/M0-M2 and gen/M3/model are byte-identical.
- **R4.** F32's helpers and the M2 ledger are unchanged.
- **R5.** `A-keccak-structural` appears on the 51 typed records only.
- **R6.** Construction checks on the instrument and the capture.
- **R7.** The 51 remodel lines are accepted.

## Risks

- **G2 (H1).** Without the remodel channel, G2 stays red on the 51 laws, labelled pending under Q32's rule. Nothing is weakened.
- **tag_exact is the first Reach induction on the M3 word model.** It needs loop frames, the convoy and key splits through the toy's 15 actions. If a piece slips, the law stays UNKNOWN and P3 is a miss.
- **BendTT fuel** on long mirrored chains (commitBatchWithProof, finalizeBatch) and on re-made counter-laws (Q22). Mitigations are per-statement lemmas and cheaper SK accesses. A fuel stop is budget exhaustion, never acceptance.
- **Search drift.** The search's candidate pool loses slot preimages, and a lost witness turns a REFUTED or ext law UNKNOWN. The search re-offers key words. A lost witness is a miss (R2).
- **Canonical-form holes** on constructs the Rollup lacks (I36's arrays, small packed elements, bytes keys) stay GenErrors.
- **Run time:** about 15-25 machine-hours, sharded on CI runners (Q24).

## Questions for the human (also in the key)

- **H1.** The remodel channel (S11), or another one.
- **H2.** I28's versioned machine stays raw until NAT needs frames.
- **L3.** A full-budget search for an `_initialized >= 4` inhabitant (TI4).
- **L5.** I43's re-baseline after the keys in flight land.
