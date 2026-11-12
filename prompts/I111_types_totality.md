# I111 (M6, generality): types totality

Branch `claude/i111-types-totality`, based on I110's branch `claude/i110-scale-composed-driver` (1801dca1; it holds
the composed driver and the sort budget). When the lead lands I110 (branch `claude/ci-i110-landing`), merge the lead
`claude/holon-v2-bend2-c6z3cd` with a merge commit. Never rebase. Branch only: this key lands after I110 (Q77).
Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality" and docs/iterations/I110.md
first.

## The gap (I110, the composed driver)

I110 removed the scale wall: the per-document sort budget lets the sort pass finish on both spent targets, and
`holon eval holon --compose` runs the M6 tools end to end. But 0 laws are derived anywhere, because `holon types`
refuses a whole milestone over one ill-sorted term (11 corpus entries and both targets). This is the failure the sort
pass had before I103 made it total.

## Build (HUMAN_ANSWERS Q77), generically, justified by semantics, never by a corpus entry

A per-document `holon types` fallback:
- A document with an ill-sorted term becomes a recorded miss naming the document, the term and why it is ill-sorted.
- Its part of the typed model is opaque: its state is unconstrained, so no law that reads it can be PROVED through
  it. Its laws are UNKNOWN.
- The other documents are typed as before, byte-identical where no opaque document touches them.
- The prereg defines "opaque" exactly, before any build commit: what an opaque document contributes to the model (its
  state, its actions, and what other documents may assume about it), with planted fixtures that show an ill-sorted
  document never makes a law PROVED where it would otherwise be refuted: a law over an opaque document alone; a
  cross-document law reading one typed and one opaque document; a law that holds only if the opaque document's state
  is constrained, which must come out UNKNOWN.
- The soundness argument goes into the report: why opacity can only remove constraints, never add them.

## Part (2), the torsor-role blow-up (Q78; the coordinator's amendment to the brief, read before the prereg)

The lead's corrected rulings Q77 and Q78 make the torsor-role search part (2) of this key (the brief had sent it to a
later key):
- a planted fixture that reproduces the exponential backtracking, built from the search's semantics, never from a
  spent target's document (I110's report names where the blow-up happens; that is all that is taken from it);
- bound or rewrite the search under Q74 (1)-(3) and (5): evaluation strategy only, never which roles are admissible;
  a committed byte-identity test, old versus new, wherever the old search finishes (the coverage set, Morph's
  documents, the fixtures), plus a unit-count test if it is metered, both in this key's CI job; the old search run
  with no time limit where feasible on the documents it never finished, identity claimed only where shown;
- a cutoff, if any, is a preregistered tier under Q75 and Q76, in units invariant between old and new code or
  calibrated on the final code before any measured run.

Order of work: part (1) with its fixtures and soundness argument first, then part (2). Whatever does not fit by about
18:00Z goes under Not done.

Not in this key: `holon eval go-machines` keeps its T-milestone (Q79), and `--compose` stays the one composing
route.

If a budget is touched, Q74 and Q75 bind (evaluation strategy only, a committed byte-identity test, a tier fixed
before any measured run in comparable units, Morph moves by re-stamp only).

## Measures

Through `holon eval holon --compose` with I110's protocol as the base: per entry, documents typed versus opaque;
entries reaching each stage; laws derived and decided, as aggregates; Morph byte-identical (re-stamp only). Smoke
measures on contaminated data. Runs on EigenLayer and Aave V3 (spec/heldout2/target.json) are labelled
`contaminated: post-I107` and follow Q56 and Q72: aggregates only, one bundle commitment per target, any REFUTED kept
in the session's vault and reported to the coordinator as a potential vulnerability unless shown to be a model defect.

## Invariants

AGENTS.md's hard rules; prereg first (this prompt, spec/M6/predictions/I111.json and its aggregate entry, the contract
tests_m6/test_i111_types_totality.py; PREREG OK before any build commit or measured run); Morph's M0-M3 outputs
byte-identical (re-stamp only); holon/ names no target; soundness over coverage; never read spec/heldout/ or
scroll-tech/; rulings read before the prereg and before each measured run (Q76).

## Report

docs/iterations/I111.md and a draft PR against the lead whose body starts `I111 ready: <one-line outcome>`, with Done
(the frozen suite's summary line), Surprises, Questions for the human and Not done.
