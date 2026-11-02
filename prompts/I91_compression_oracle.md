# I91 (= I38c): the compression oracle, HypZ and HypZ_len

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, then BUILD_PLAN rows I91, I93, I90 and I67, then this key:
`iterations.I91` in `spec/M3/predictions.json`. The contract is the docstring of `tests_m3/test_compress.py` (rules
Z1-Z9). Its instruments are `tests_m3/_i91.py` and `tests_m3/fixtures/compression/holon_i91_instrument.go.txt`; do not
edit them (a wrong instrument is a Question and an amendment line).

## The obligation

Whitepaper §8.5: a model of the batch codec takes the compressor Enc and the decompressor Dec as uninterpreted
parameters, under two hypotheses. HypZ: forall x non-empty, k <= K. Dec(Enc x ++ 0^k) = x. The derivation node
concatenates the blob bodies of a batch and decompresses them once, so a compressed payload arrives followed by the zero
bytes of its last blob. HypZ_len: |Enc x| is at most zstd's compress bound of |x|. Both are distinct from D2's
Hyp-Z0-kzg.

I91 states both with the bound K the pinned code implies (the blob capacity minus one: the submitter splits the
compressed payload over the fewest blobs) and tests them, without a proof, on the real codec through the real blob
pipeline (sidecar `spec/M3/lib/compression.json`). It writes one results document,
`results/M3/compression_oracle.json`, and changes no law, record, rule catalog, frontend, Go document or model.

## Build, in order

1. Code (no target vocabulary in the new module: every name comes from the sidecar):
   - `holon/oracles/compression.py`: the sidecar (Z1), the generated Go probe and its run on a scratch workspace (Z2),
     the capacity (Z3), the two hypothesis entries (Z4, Z5), the expansion (Z6), the empty payload (Z7), the document
     and the CLI (Z8).
   - `holon/__main__.py`: `holon oracle compression` beside `zero-blob` and `check`.
2. The outcome: `python -m holon oracle compression --milestone M3`, committed alone; then `--check`.
3. `holon report --milestone M3` (BUILD_PLAN's rows I91 and I93 moved O5, O6 and D3 to I93), its own commit.
4. The report `docs/iterations/I91.md`, ending with Done / Surprises / Questions for the human / Not done.

## Do not

- Run the codec on the sample before the prereg commit, or edit the instruments after it.
- Call "checked" a proof: it is a test on the sample.
- Touch laws, records, generated models, replay reports, the Go document or the rule catalog (rule Z9).
