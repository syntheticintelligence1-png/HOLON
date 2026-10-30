# I89 (= I39c): the Go consumer compiled to Bend, and I88's derivation laws decided on it

Rendered from `docs/BUILD_PLAN.md` §4 I39 and its rows I85, I88 and I89. Sources: whitepaper §5.1 consumer and cycle, §5.5, §8.5 (HypC and split status) and §11.3 (O7, O8, O24); Appendix A (F11); I85's report and prompt; I88's prompt, contract and sidecar; the coordinator's brief of 2026-10-30. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, and run `bend guide` once.

The exact rules are in the docstring of `tests_m3/test_derivation_bend.py`:
- B1-B6, the model (the cut, the decoder, values, control, natives, cones);
- H1-H3, HypB's instance;
- F1-F3, the refinement;
- S1-S6, the laws (stage 2);
- the commands, exit codes and commit rules.

The key's thresholds pin that docstring, the instrument `tests_m3/_i89.py` and the sidecar `spec/M3/lib/derivation_bend.json` by sha256. The base is `f02ae3c3`: the lead `f30e0dd5` plus BUILD_PLAN's row I89.

## Why this key

HOLON's moat is that a proof checker, not a generator, decides what is true. I85 extracted the Go derivation consumer `BatchInfo.ParseBatch` as SSA and refined a Python interpreter of it against the real Go (169 cases, 0 disagreements). I88 froze I39's five product laws, all UNKNOWN because no Bend model of the consumer exists. I89 generates that model and lets the checker decide.

## What I89 builds

### Stage 1 (now, on the lead)

1. **A generator from Go SSA to Bend** (`holon/derivation/bendgen.py`), reading only I85's consumer section and this key's sidecar.
   - Values: Go integers of every width as two U32 limbs with Go's wraparound (the checker's Nat is unary past small values, so 64-bit arithmetic in Nat never finishes); slices over a heap of cells; structs and arrays as records; pointers as (cell, path); interfaces as (type, value).
   - Outcomes: ORet, OPanic (Go's text as a template and its arguments), OFuel. Errors carry their text's template (a format string of the document) and arguments, or an oracle's text.
   - Control: one trampoline def per function over a fuelled transition. Bend refuses a match on a computed value, a destructuring let included, so every branch goes through a helper def's parameter.
   - Natives: one library def per sidecar kind. Anything else is Unsupported, and nothing is written.
2. **The cut and the hypotheses.** The blob layer (the retrieval loop, its early return and the decompress call) is cut at the region the SSA gives (rule B1). It enters as the parameter `pl` of the stated hypothesis HypB, with four answers (PlOk, PlDErr, PlRet, PlPanic). The decoder enters as HypT's parameter `dt`. Neither is ever an axiom: no def answers them.
3. **HypB's instance** (H1-H2). The real blob layer runs on the 169 cases through a generated Go test, offline. Its answers are checked against I85's recorded decompressor answers, and HypB itself is checked on the 132 canonical cases.
4. **The refinement** (F1-F3). The compiled model, fed HypB's and HypT's instance answers, is compared with the real `ParseBatch` on the 169 cases: status, error text, panic text, and the cone view.

### Stage 2 (after I88 merges; the coordinator says when)

- **The engine.** `holon derivation bend-decide` runs I88's decider (`holon.derivation.decide.run`) with I89's Bend engine as its consumer model (`laws.verdict` calls `model.decide(law, evidence)`). I88's candidates are the starting point. The engine:
  - renders each frozen statement in Bend over the consumer model, the Rollup's typed model and I24's header component, with every premise, hypotheses included;
  - finds the witness on the compiled models;
  - checks the counter-law or the generated proof in Bend and BendTT;
  - replays the witness's consumer side on the real Go.
- **Records.** I88's records and `splits.json` are re-decided in place (I88's D3).

## Predictions

| id | claim (short) |
|---|---|
| P1 | the cut and compiled functions are the instrument's (a construction check, not counted) |
| P2 | the model is generated, reproduces, states no law, has no escape hatch, and Bend checks it; nothing unsupported |
| P3 | HypB's instance: 0 disagreements with I85's recorded answers; HypB holds on all 132 canonical cases |
| P4 | the refinement: 169 agree, 0 disagree, 0 unsupported, 0 out of fuel, 0 unanswered |
| P5 | O7 REFUTED in both kernels (observation [3, 2], relayed from I88, not counted) |
| P6 | F11's L1 count REFUTED in both kernels ([1, 0], not counted) |
| P7 | O8 under HypC_binds_trailing PROVED in both kernels (hypothesis application) |
| P8 | O8 under HypC_ignores_trailing REFUTED in both kernels ([1, 0], not counted) |
| P9 | O24 REFUTED in both kernels ([[1], [2]], not counted) |
| P10 | the HypC split true |

Regressions:
- **R1:** nothing rule-derived moves.
- **R2:** the commit rules.
- **R3:** the audits pass, and CI fails only on the base's items.
- **R4:** the new code is generic and outside every closure.

## Where I expect the plan to miss (disclosed)

**PROVED for O8 under binds is by hypothesis.** The law's last premise is `HypC_binds_trailing`, whose statement concludes `trailing == 0` from premises the law itself states. The proof is the premise applied. It checks the statement's form, not the consumer's code. The split is real, but it is a split between two hypotheses about the circuit; it is not a property of `ParseBatch`.

**The commit side is the least certain part of stage 2.** It is:
- the Rollup's typed model's Reach, with its keccak table;
- the committed header, compiled from the document's header-family write by the typed model's own compiler;
- the checker's time on the witness.

If any of these fails, the law stays UNKNOWN with the reason, and its prediction misses.

## What was known before this prereg (disclosed)

See the key's `thresholds.disclosed`. In short:
- **Read:** I85's code, records and SSA; I88's prompt, contract, sidecar, instrument and decide interface.
- **Relayed by the coordinator:** I88's evaluator results, before this prereg. So the stage 2 observations are not counted; the verdicts are.
- **Probed:** Bend, on the facts the design rests on.
- **Not run:** no I89 generator, model, Go run or law.

## Questions for the human (stated at the prereg)

- **Q-I89-a (Reach's keccak table).** I88's statements bind no keccak256. The Rollup's typed model's Reach ranges over a keccak table, so the Bend rendering quantifies that table with the state: universally in a proof, existentially in a counter-law, holding the real keccak of every key the steps look up. FACT and DISCH render the document's keccak256 the same way. Is this the intended rendering of I88's `Reach`?
- **Q-I89-b (I88's tests after the re-decision).** I88's P2 (every law UNKNOWN) and P5 (split false) assert I88's own scope. They fail by design once I89 re-decides the records in place, as I88's D3 provides. Should the lead amend them, or leave them as recorded history?
- **Q-I89-c (oracle instances in counter-laws).** A counter-law's HypB and HypT instances are generic functions whose hypotheses Bend proves for all arguments, for example a marker codec. They match the real library at the witness, which the replay checks. Is that the intended reading of "uninterpreted functions under a named hypothesis"?

## Commands

```
python -m holon derivation bend [--check]
python -m holon derivation bend-refine [--check]
python -m holon derivation bend-decide [--check]
```

## Rules

- `AGENTS.md` throughout.
- **Never edit:** a frozen file, an earlier key, I85's or I88's sidecar, a closure file, or a law statement.
- **A disagreement is a generator bug,** fixed in the generator, never in a case.
- **A missed prediction is a result.**
- **The target repository is read through the local checkout at the pin,** never fetched. Never read `scroll-tech/*` or `spec/heldout/`.
