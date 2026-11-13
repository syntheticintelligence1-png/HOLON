# I116 (M6, generality): per-document fallbacks

Branch `claude/i116-per-document-fallbacks`, based on I112's branch `claude/i112-run-wall` (a5db40d6). The lead lands
I112, then I115 (the binding wall, built in parallel). Merge the lead `claude/holon-v2-bend2-c6z3cd` with a merge commit
whenever it moves. The first measured run waits until I115's landing is merged here; record that merge's sha. Never
rebase. Branch only (Q88): the lead lands this key. Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4
"M6: generality" and docs/iterations/I112.md first.

## The gap (I112, the run wall)

I112 took down the run wall's first layer. On the spent targets no law is derived:
- EigenLayer passes types, and then evidence and derive refuse the milestone over one transitions document's E2
  construct;
- Aave V3 is refused at DISCH, where D2 refuses one document ("one predicate for two classes").

Each of these is a refusal of one document that stops every document.

## Build (HUMAN_ANSWERS Q83 and Q88 (3), the lead's), generically, justified by semantics, never by a corpus entry

Per-document fallbacks, in Q77's shape:
1. **DISCH.** A DISCH refusal for one document makes that document's DISCH laws UNKNOWN. It is a recorded miss naming
   the document and the refusal, and every other document's DISCH still runs.
2. **Evidence and derive.** An evidence or derive refusal for one document makes that document's laws in that stage
   UNKNOWN, recorded the same way, and every other document still runs.
3. **Milestone-wide input errors** stay refusals of the milestone. Only a per-document refusal falls back.

The prereg (spec/M6/predictions/I116.json) defines each fallback exactly before any build commit: what a fallen-back
document contributes to later stages, and what other documents may assume about it. Each fallback gets planted
fixtures from the stages' semantics (never from a spent target's document) in I111's three shapes:
- the fallen-back document alone;
- cross-document;
- constrained, which must be UNKNOWN, never PROVED.

Each set has a control that decides at least one law.

Not in this key: the binding wall (I115, landing first).

## Measures

Through `holon eval holon --compose` with I112's protocol plus document_fallback, and I115's binding keys once it
lands (spec/M6/lib/i116_run.json). The measures:
- documents falling back per stage and class;
- entries reaching each stage;
- laws derived and decided, as aggregates (Q56, Q89);
- whether Q88 (1)'s gate is met;
- Morph byte-identical (re-stamp only).

These are smoke measures on contaminated data. Runs on EigenLayer and Aave V3 are labelled `contaminated: post-I107` and
follow Q56 and Q72. The counted run is the first measured run that finishes (Q80, Q76, Q69).

## Invariants

- AGENTS.md's hard rules.
- Prereg first: this prompt, the key and its aggregate entry, and the contract tests_m6/test_i116_per_document_fallbacks.py.
  PREREG OK comes before any build commit or measured run.
- Morph's M0-M3 outputs stay byte-identical (re-stamp only).
- holon/ names no target.
- Soundness over coverage: a fallback only removes constraints.
- Never read spec/heldout/ or scroll-tech/, and follow the sealed pair's no-read rule (Q86 (3)).
- Read the rulings before the prereg and before each measured run (Q76).

## Report

Write docs/iterations/I116.md, and open a draft PR against the lead whose body starts `I116 ready: <one-line outcome>`.
The body has the sections Done (with the frozen suite's summary line), Surprises, Questions for the human and Not done.
