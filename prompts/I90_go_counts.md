# I90 (= I38b): O28 through the count channels of a Go component

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, then BUILD_PLAN rows I90, I91 and I67, then this key:
`iterations.I90` in `spec/M3/predictions.json`. The contract is the docstring of `tests_m3/test_go_counts.py`
(rules C1-C10). Its instruments are `tests_m3/_i90.py` and `tests_m3/fixtures/go_counts/holon_i90_instrument.go.txt`;
do not edit them (a wrong instrument is a Question and an amendment line).

## The obligation

O28 (whitepaper §11.3, SORT-width): Σ n_l1 is realized in uint16. `morph-l2/common/batch.BatchData.Append` counts the
L1 messages of a batch twice: it appends each hash's 32 bytes to `l1TxHashes` (one per element of its parameter) and
adds `uint16(len(l1TxHashes))` to the uint16 field `l1TxNum`. At 65,536 L1 messages the second count is 0.

I90 states it without a catalog change, as I67 did for O4: a Go count component (rule C1) whose two channels are two
CODEC edges citing one function, so rule PAR's existing branch producer (P3) derives the law and the cycle producer (P8)
records a duplicate. The law is decided on a model whose carrier is the parameter's length, a `Nat` (parametric counts,
rule C4), at 65,536 in both kernels (C5), and replayed on the real `Append` (C7).

## Build, in order

1. Code (holon/; no target vocabulary in the new modules):
   - `holon/diagram/gocount.py`: the sidecar, the count documents (C1), the diagram (C2), the anchors.
   - Hooks beside I67's Go-op hooks: `holon codecs` (writes and checks gen/M3/goops/), `holon diagram`, `holon evidence`
     (a model with anchors, no atom), `holon derive` (stale-input checks, the component's diagram into PAR as it is),
     `holon.ir` (binder type), `holon.records` (the generated ledger bundle), `holon.gen.refs` (statement refs),
     `holon.bindings` (binding and emission), `holon.codecrun` (the kind gocount), `holon.rank` (K6),
     `holon.refute_m3.i4_sides` (the gocount report), the evidence schema's facts_version.
   - `holon/gen/gocount.py`: the model (C4), the emitter, the candidates and the counter-law (C5), the bundle.
   - `holon/goreplay.py`: the count replay (C7), writing `replay/M3/gocount/report.json`; the Go-op report unchanged.
2. Outcomes by rule C9's recipe and grouping. Each REFUTED witness is replayed on the real code.
3. Report `docs/iterations/I90.md`, ending with Done / Surprises / Questions for the human / Not done.

## Never

- Never weaken the law, re-parametrize the witness to a smaller N, or special-case the law id in a generator.
- Never touch I67's sidecar, frontend config, Go-op document or report.
- Never run `tools/freeze.py write`; never edit a frozen file.
