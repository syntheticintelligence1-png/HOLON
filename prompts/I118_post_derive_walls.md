# I118 (M6, generality): the post-derive walls

Branch `claude/i118-post-derive-walls`, based on I116's branch `claude/i116-per-document-fallbacks` (303ae8a0), whose
fallbacks it needs. The lead lands I116 (branch `claude/ci-i116-landing`). Merge the lead `claude/holon-v2-bend2-c6z3cd`
with a merge commit whenever it moves; never rebase. Branch only (Q88): the lead lands this key. Read AGENTS.md,
docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality" and docs/iterations/I116.md first.

## The gap (I116, the per-document fallbacks)

I116's fallbacks took down Aave V3's DISCH refusal and EigenLayer's evidence and derive refusals. Aave V3 now derives
8 laws and decides none; EigenLayer derives none. On Aave V3 the walls stand after derive:
- the composed coverage stage refuses over one extraction sidecar;
- `holon bind` exits 1, binding none of the 8 laws;
- the typed runner exits 1 and writes no record.

Q88 (1)'s gate for I114 is not met. This key is the gate's critical path.

## Build (HUMAN_ANSWERS Q92, the lead's approval), generically, justified by semantics, never by a corpus entry

1. **Coverage, bind and the typed runner (Q92 (1)).**
   - (a) The composed coverage stage skips the documents with no typed model (not extracted, or made opaque by types:
     I111's O2-O7), each recorded as skipped.
   - (b) A bind or runner failure confined to one document's laws is a per-document fallback in Q77's shape: that
     document's laws are UNKNOWN with the error, and the rest run. A failure not confined to one document stays a
     refusal.
   - The definitions are preregistered (spec/M6/predictions/I118.json thresholds coverage_skip, run_fallback,
     bind_fallback), with planted fixtures in I111's three shapes (alone, cross-document, constrained-state, which
     must be UNKNOWN) plus a control, built from the stages' semantics, never from a spent target's documents (Q73,
     Q84). A fallback can only make a law UNKNOWN, never PROVED.
2. **EigenLayer's empty derive (Q92 (2)).** Record per rule family why no law is derived on each spent target, as
   pre-decision aggregates (Q72). A family that covers nothing a target declares is a reported coverage limit. This is
   a measurement; nothing is fitted to EigenLayer.
3. **The evidence schema (Q92 (3)).** spec/schemas/evidence.schema.json gains an optional `fallback`, absent unless a
   milestone opts in. Every committed M0-M3 evidence.json still validates and stays byte-identical. The frozen
   schemas/ at the repository root is never touched.
4. **Order (Q92 (4)).** Build now; measure on top of the landing before this key (I117's if landed by then, otherwise
   I116's), and tell the coordinator which base before the counted run.

## Rules

Every invariant of the M6 briefs holds: AGENTS.md's hard rules; prereg first (PREREG OK before any build commit or
measured run); Morph's M0-M3 outputs byte-identical but for re-stamps; holon/ names no target; soundness over coverage;
never read spec/heldout/, scroll-tech/, I113's candidates or spec/heldout3/ (but commitment.json); counted runs are
sacred (Q80, Q76, Q69); decided counts never split (Q89); runs on the spent targets are labelled contaminated:
post-I107 and commit aggregates and one bundle commitment per target only (Q56, Q72); every REFUTED that is not a
model defect is withheld and reported to the coordinator in one line.

## Report

docs/iterations/I118.md with each prediction's outcome, the soundness argument, surprises, and what is left; a draft PR
against the lead whose first line is `I118 ready: <one-line outcome>`.
