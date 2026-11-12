# I110 (M6, generality): the scale wall and the composed driver

Branch `claude/i110-scale-composed-driver`, based on I109's branch `claude/i109-pipeline-totality-3` (224f9b81; it
holds Q62's empty codec layer). When the lead lands I107 (#181) and I109 (#179), merge the lead
`claude/holon-v2-bend2-c6z3cd` with a merge commit. Never rebase. Branch only: this key lands after I109 (Q73).
Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality", docs/iterations/I107.md (on
the I107 landing branch) and docs/iterations/I109.md first.

## The gap (I107, the generality run)

- Extraction worked on the fresh sealed targets: 87 of 95 contract documents (EigenLayer 48/53, Aave V3 39/42).
- The sort pass timed out at 1,800 s on both, over the whole milestone at once, so 0 laws.
- No single driver composes the M6 tools end to end. `holon eval holon` records inferred roles but does not install
  them. The route that installs them (I104's smoke, route C) refused at derive without `link.json`. I109 built Q62
  (a missing link sidecar means an empty codec layer).

## Build, generically, justified by semantics, never by a corpus entry

(a) The scale wall: a per-document sort budget, preregistered with its tier.
- First measure where the time goes, per document and per phase, on the corpus's largest entries and on Morph.
- A semantics-preserving speedup is in scope only if every sort output stays byte-identical (Morph's documents and
  I108's and I109's corpus documents). Prove it.
- The budget catches what remains. A document over budget is a recorded miss, its terms opaque downstream. It is
  never dropped silently and never appears in a PROVED.
- The tier is a recorded protocol parameter, fixed in the prereg. No tier is raised after a run sees its result
  (Q69).

(b) One composed route-A driver, landed through `holon eval holon` itself as an explicit opt-in (no fourth route). It
composes I103's extraction; I104's roles, installed only where no hand sidecar exists; I105's Go machines with
`nil_maps` as I109 defaults it; derive with Q62's empty codec layer; then run, replay and decide as route A does.
Every derived record carries `roles_source`.

(c) `holon eval go-machines` records `machines.nil_maps` in its output (I107's Question 3).

After committing any new transitions document, re-walk I103's sort coverage (`python -m holon.sorts.coverage`).

## Invariants

AGENTS.md's hard rules; prereg first (this prompt, `spec/M6/predictions/I110.json` and its aggregate entry, contract
tests `tests_m6/test_i110_scale_composed.py`; `python -m holon audit prereg --milestone M6` prints PREREG OK, pushed
before any build commit or measured run). Morph's M0-M3 outputs stay byte-identical (re-stamp only). holon/ names no
target. Soundness over coverage: a fallback may only make a law weaker or UNKNOWN. Never read `spec/heldout/` or
`scroll-tech/`. Runs on EigenLayer and Aave V3 (spec/heldout2/target.json, as I107 pinned them) are labelled
`contaminated: post-I107`, are measurements only, and follow Q56 and Q72. Evidence for a change comes only from the
corpus, Morph and planted fixtures. Disk: run large runners with `--jobs 2` or one at a time.

## Report and PR

docs/iterations/I110.md with each prediction's outcome, the soundness argument, surprises and what is left. A draft PR
against `claude/holon-v2-bend2-c6z3cd` whose body's first line is `I110 ready: <one-line outcome>`, then Done (with
the frozen suite's summary line), Surprises, Questions for the human, Not done.
