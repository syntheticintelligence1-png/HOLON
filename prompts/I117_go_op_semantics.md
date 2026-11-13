# I117 (M6, generality): Go op semantics for the binding

Branch `claude/i117-go-op-semantics`, based on I115's branch `claude/i115-binding-wall` (9571c02f; it holds the bind
stage). It builds in parallel; its measured runs come only after I116's landing has merged into the lead (I115 lands
first, then I116), and it lands after I116, so each measurement isolates one change. When the lead moves, merge it with
a merge commit; before the first measured run, merge the lead that holds I116's landing and record its sha. Never
rebase. Branch only (Q88): the lead lands this key. Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4
"M6: generality" and docs/iterations/I115.md first.

## The gap (I115, the binding wall; HUMAN_ANSWERS Q90, the lead's approval)

I115 added `holon bind` to the composed route. The run step completes on every law-deriving corpus entry, but all 93
corpus PAR laws are recorded UNKNOWN by binding: a PAR law over Go code can be bound only when every op in its statement
has a defined meaning in goloop, and goloop defines only its loop class. The corpus has 107 laws derived, 1 decided
(PROVED and REFUTED together, Q56).

## Build: goloop semantics for the non-loop ops the Go frontend emits

1. **Each op is defined from the Go specification, never from corpus code (Q90 (1)):** fixed-width wraparound;
   division and remainder; shifts; conversions between signed and unsigned and between widths; comparisons; the
   panicking cases. An op HOLON can't state exactly stays undefined: its laws stay unbound and UNKNOWN, never guessed.
2. **Each definition is checked against the pinned Go toolchain on planted programs (Q90 (2)):** a differential test
   over edge cases (overflow, negative operands, shifts at and past the width, MinInt / -1), each case run as real Go
   under the pinned toolchain and compared with HOLON's definition; and a planted law that is false under Go's real
   semantics, which must not be PROVED. Both are committed tests in the key's CI job `tests-m6-i117` (X6).
3. **The prereg carries the definitions and fixtures** before any measured run (Q90 (3)). The report carries the
   soundness argument: why each definition matches the specification, and why an undefined op can never make a law
   PROVED.

**Addition (HUMAN_ANSWERS Q91, the lead's, relayed by the coordinator before the prereg):**
1. The Go-op model's scope: straight-line ops and guards over the carrier's fields, each defined from the Go
   specification and checked against the pinned toolchain.
2. The go 1.24.7 `bin_sha256` pin stands (Q87): a counted run whose bin/go differs refuses, and the refusal is
   recorded; the check is never relaxed.
3. I115's mpipeline path runs its binding check after the decision. Move that check before the emitter on the
   mpipeline path, so that no decision is ever emitted for an unbound law on any path, with a planted control (an
   unbound law on the mpipeline path is refused before any decision is emitted), in the prereg and the CI job.

Not in this key: anything outside Go op semantics. Report whatever else blocks as the next wall.

## Predictions

Fixed by the prereg (`spec/M6/predictions/I117.json`) before any measured run, through `holon eval holon --compose`
with the protocol of I116's landing as the base: PAR laws bound, run and decided; ops defined versus left undefined;
laws derived and decided as aggregates (Q89's wording); whether Q88 (1)'s gate is met; Morph byte-identical
(re-stamp only). These are smoke measures on contaminated data; I114 scores generality on the sealed pair.

## Invariants (every M6 key; the brief in full is the coordinator's message to this session)

- AGENTS.md's hard rules, all of them. Prereg first (BUILD_PLAN §0.1); `python -m holon audit prereg --milestone M6`
  prints PREREG OK, committed and pushed before any build commit or measured run.
- Morph's M0-M3 outputs move only by re-stamp; every new inference applies only under an explicit opt-in.
- holon/ names no target. Soundness over coverage: a fallback may only make a law weaker or UNKNOWN; every REFUTED
  still needs its replay.
- Never read `spec/heldout/` or `scroll-tech/`; the sealed pair's no-read rule (Q86 (3)) until I114's reveal: no
  system outside the evidence, none of I113's candidates, nothing under `spec/heldout3/` but `commitment.json`.
- Decided counts never split (Q89). Runs on the spent targets (EigenLayer, Aave V3, as I107 pinned them) are labelled
  `contaminated: post-I107` and follow Q56 and Q72; any REFUTED there, or on corpus code other than a known fixed
  defect, is kept in the vault, replayed and classified, and reported to the coordinator as one line.
- Counted runs are sacred (Q80, Q76, Q69): the first measured run that finishes is counted; no started run's output is
  ever deleted; the preflight must pass first.
- Merge commits only; work in progress pushed with `[skip ci]`; the final push runs CI.

## Report and PR

docs/iterations/I117.md, with each prediction's outcome, the soundness argument, surprises and what is left. A draft
PR against `claude/holon-v2-bend2-c6z3cd` whose body's first line is `I117 ready: <one-line outcome>`, then Done (with
the frozen suite's summary line), Surprises, Questions for the human, Not done.
