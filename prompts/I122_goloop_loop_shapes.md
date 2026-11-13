# I122 (M6, generality): goloop's loop shapes

Branch `claude/i122-goloop-loop-shapes`, based on the lead `claude/holon-v2-bend2-c6z3cd` (40da439d). It builds in
parallel. Its measured runs come after I120's landing, on the base the coordinator names: the last landing before this
key's, merged into this branch by a merge commit, with its sha recorded in the report (Q92 (4), Q98 (2)). When the lead
moves, merge it with a merge commit. Never rebase. Branch only (Q88): the lead lands this key. Read AGENTS.md,
docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality", docs/iterations/I117.md, holon/gen/goloop.py's
docstring and tests_m3/test_go_loop.py's rules Y6-Y7 first.

## The gap (I117's measurement; HUMAN_ANSWERS Q93 (3))

goloop's loop class (I67) takes one counted loop of step 1 from a constant to a constant, over a byte array, reading one
affine cell per iteration. Four of one corpus entry's seven Go ops have a loop outside it; the Go frontend records `paths_reason
"loop"` for them and emits no loop body, so their laws are unbound and UNKNOWN. In I116's counted run, 13 corpus Go ops
are in that state. Their recorded loop shapes (aggregates only, counted before the prereg from the committed Go-op documents and
`go.loops`, never from an entry's code): 5 have one for-range loop over a slice whose length is read from the carrier;
4 have loops in sequence or nested; 3 have one unbounded loop; 1 has a range with a nested range. Every recorded step
is 1 or none.

The wall has two halves: what the Go frontend's `loop_bodies` emits, and what goloop can model.

## Build (Q93 (3), Q90 (1)-(2), Q98 (2))

1. **Two loop classes, each defined from the Go specification** (spec/M6/predictions/I122.json's `definitions`):
   - **S1 (range):** one for-range loop over a slice the carrier holds (the op's parameter or a field path from it), of
     an integer element type of at most 32 bits. The range expression is evaluated once, so the trip count is the
     slice's length, read from the carrier. The carrier value is the element sequence, of any length. A signed element
     is encoded in offset binary, which keeps the signed order.
   - **S2 (stride):** one counted loop with a constant step other than 0 and 1, of either sign, over a fixed-length
     byte array. The trip sequence is computed concretely in the induction variable's Go type, with wraparound.
   - Both are tried only after the I67 class refuses an op, so an op in that class is modelled as before.
2. **The frontend's opt-in `loops "shapes"`** (config holon-go-frontend/0.3, only with `ops "typed"`; protocol
   `go.loops "shapes"`; never passed to the Go machine frontend). Under it, loop bodies are emitted for every function
   with a body and for counted loops of any constant non-zero step. A loop of step other than 1 gets no `init <= iv`
   assumption. Each entry carries the typed terms and the induction variable's type. Without it every output is as
   before.
3. **Arithmetic:** both classes run under `ops "typed"`'s opaque-arithmetic reading. S1 has no arithmetic. S2's trip
   sequence and index are evaluated concretely in Go's semantics. No kept or pruned branch depends on unbounded
   integers (I119's defect). The narrow-arithmetic loop mode is unchanged (Q93 (1)).
4. **Everything else stays `Unsupported`:** sequential, nested and unbounded loops, a second cell, a wide or non-integer
   element, calls before reads, conditions over call results (Q93 (3): these wait for an inter-procedural model). The
   reasons are counted before any decision (Q72), in `results/M6/I122/loop_shapes.json`.
5. **No proof route** (gap G6, not closed here): every law the classes decide is a refutation, handled under Q56.

## Planted fixtures and checks (tests_m6/test_i122_goloop_loop_shapes.py, CI job `tests-m6-i122`)

The fixture `tests_m6/fixtures/i122` is a Go package written from the specification's rules:
- **S1:** Frame.Scan, Frame.Tail and Signed.
- **S2:** Back, WrapScan (a uint8 index that wraps) and Down.
- **Just outside:** Frame.Wide (64-bit elements) and Pair (two cells per iteration).

The checks:
- **Q90's differential test:** the compiled model equals real Go on the pinned go 1.24.7, on every edge input (at least
  2000), and each S2 header's trip sequence equals Go's.
- **The planted false laws:** WrapScan's totality is true only without wraparound. It and three others must be
  REFUTED, never PROVED, and every witness is replayed as real Go.
- **The planted true laws** must never be REFUTED.
- **The ops just outside** stay unbound.
- **The control:** Morph's committed Go-op models regenerate byte-identical.

## Rules

Prereg first. Then:
- Q56, Q72 and Q89 apply: decided counts never split.
- The sealed pair's no-read rule, with the read-receipt.
- Morph's M0-M3 move only by re-stamp.
- Run the target-agnostic test locally.
- Run every earlier `tests-m6-*` job locally after each lead merge.
- The lead's Q98 additions: the count above is the stated reason for the classes (aggregates only, with no entry name,
  path or identifier in a class's definition or code). The corpus predictions are smoke on contaminated data:
  generality is claimed only from I114's sealed pair.
