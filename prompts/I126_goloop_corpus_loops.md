# I126 (M6 follow-on): goops coverage of the corpus's loop shapes

Rulings: HUMAN_ANSWERS Q112 (5), Q93 (3), Q90 (1)-(2), Q104, Q117 (the lead's 19:02Z and 19:08Z rulings, recorded at
I121's landing as Q117 (3) and (5)). The key is `spec/M6/predictions/I126.json`; its thresholds are the definitions.

## Why

F-M6-05 at corpus scale: 234 of I124's 268 derived laws are PAR laws over Go ops that goops writes as
`# <op>: unsupported (<reason>)`, so they cannot bind. 78 of them are refused for a loop reason (the lead, 19:08Z):
47 with 0 loop bodies, 17 with a body with no paths, 10 with 2 bodies, 4 with 3. I122's S1 and S2 matched no corpus op.

## The wall, in two halves

- **(a) The frontend's emission.** A loop with no induction phi (a range over a string, map, channel or function, or a
  for with no condition) gets no body. A body whose iteration meets another loop's header has no paths (OtherLoop),
  whether that loop is nested in it or follows it in sequence.
- **(b) goloop's classes.** I67, S1 and S2 each take one loop.

## The change (behind protocol `go.loop_forms "seq"`, frontend config `loop_forms "seq"`, with `loops "shapes"`)

1. The frontend records every loop's form and why it has no body or no paths (`loop_forms`), ends an iteration's path
   that meets a later, disjoint loop's header with `"next"`, and passes an earlier, side-effect-free counted loop met on
   a later loop's prefix (its values opaque).
2. `holon.gen.goshapes` adds class SEQ: counted loops over one byte array, in program order, each trip computed in its
   induction variable's Go type with wraparound, an empty loop dropped once its trip is shown finite. The model is
   I122's S2 model over the concatenated trip.
3. Everything else stays Unsupported, its reason counted before any decision (Q72). I122's S1 and S2 are unchanged;
   Morph's M0-M3 move by re-stamp only.

## Evidence

The Go specification ("Statements", "For statements", "Integer overflow", "Index expressions"), the corpus's counts
(aggregates only) and the planted package `tests_m6/fixtures/i126`, never an entry's code. Q90's differential test
against the pinned go 1.24.7. Corpus measurements are smoke on contaminated data; decided counts are never split (Q89).
