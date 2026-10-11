# HOLON M0 run notes (P1–P4)

## Status

Branch `devin/m0-pipeline`. Full pipeline and gate implemented in `holon/`
(stdlib-only Python 3.10). `python3 -m holon run --milestone M0` then
`python3 -m holon gate --milestone M0` both exit 0. Freeze digest unchanged:
`f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`.

Test suite: `python3 -m unittest discover -s tests -t . -v`
`FAILED (failures=1)` on the first full run — the canary `L_rt_go_v2:pin_const`
picked a witness on `enc_sol`'s domain boundary (pinned version 3), where the
model returns `Nil{}` but the oracle raises `DomainError`. Fixed in
`refute.py` (`_in_domain`: skip candidates whose pinned version exceeds a
called encoder's `domain.version_le`). All tests then pass; test_50 skips.

## Summary table

| Law | Status | kernel.verdict | checker s | witness |
|---|---|---|---|---|
| L_dom_hdr | REFUTED (finding) | checked | ~0.15 | `0x00` + 249 zero bytes (len 250) |
| L_par_hdr_ssvh | REFUTED (intent_question) | checked | ~0.20 | all-0xff header, version pinned 1 |
| L_par_hdr_v0 | PROVED | checked | ~0.14 | — |
| L_par_hdr_v1 | PROVED | checked | ~0.15 | — |
| L_par_hdr_v2 | REFUTED (finding) | checked | ~0.19 | all-zero header, version pinned 2 |
| L_rt_go_v0 | PROVED | checked | ~0.15 | — |
| L_rt_go_v1 | PROVED | checked | ~0.15 | — |
| L_rt_go_v2 | PROVED | checked | ~0.15 | — |

All statuses match `predictions/M0.json`. `--verdict` (BendTT kernel) passed on
every PROVED/REFUTED `PROOF.bend` (~0.1–0.4 s each; recorded per attempt in the
result records). The whole pipeline runs in ~6 s, the gate in ~15 s.

## REFUTED laws — witnesses and differences

- **L_dom_hdr** `ok_sol(b) == ok_go(b)` — witness `b` = 250 bytes, byte 0 = 0,
  rest zero. difference: lhs `true`, rhs `false`. Solidity accepts any v0
  header of length ≥ 249; Go requires exactly 249.
- **L_par_hdr_v2** `enc_sol(h) == enc_go_v1(h)` [version=2, ssvh=0] — witness =
  all-zero header pinned version 2. difference: `0x02…` vs `0x01…`; first
  difference at index 0 (lhs byte 2, rhs byte 1). Go has no v2 encoder;
  `BatchHeaderV1.Bytes` hard-codes byte 0 = 1. Codec-level obstruction: the real
  v2 producer (`batch_cache.go:1720-1731`) builds a `BatchHeaderV1`, calls
  `Bytes()`, then patches `h[0] = 2` — so `enc_go_v1` alone cannot emit v2, but
  the system composes a patch. Triage stays `finding` per the prediction; the
  call-site patch is P5 replay detail.
- **L_par_hdr_ssvh** `enc_sol(h) == enc_go_v1(h)` [version=1] — witness =
  all-0xff header pinned version 1. First difference inside bytes 185..217
  (`sequencerSetVerifyHash`): Solidity writes `bytes32(0)`, Go copies the
  struct field. Triage `intent_question` (config/triage.json): whether a Go
  producer ever sets a nonzero value is outside M0; `batch_cache.go:1447-1462`
  (sealBatch) rejects a nonzero ssvh for live batches and allows it only for
  legacy replay at index ≤ legacyCutoverBatchIndex.

## Cheating-emitter experiment (P4 step 3, scratch copy, not committed)

Patched `emit.emit_laws` to write `{L == L}` instead of `{L == R}`, re-ran the
pipeline (all 8 laws now "PROVED", verdict still checked) and the gate:

- GENV PASS, G2 PASS, G1 PASS (regeneration identical), G3 PASS,
- G5 PASS (`{L == L}` re-checks fine), G11 PASS (law names present),
- **G4 FAIL** — 21 canaries generated, only 7/21 rejected (exit 1).

The canaries catch a silently-weakening emitter, exactly as designed.

## Surprises / Bend behaviour differing from priors

- A `def` may only call defs declared **above** it; forward references are
  rejected with "an unfilled law is a dead claim". The generator emits helper
  defs before their callers.
- `Maybe<Fields>` needs `Maybe<&2, List<&2, List<&2, U32>>>` — the inner
  element type must be spelled fully.
- Compiled `.mjs` `Bool` values come back as plain JS `true`/`false`, not
  `{$:"True"}` objects; the eval runner handles both.
- `bend F.bend` prints `ALL PROOFS CHECK` plus "Use --verdict for mathematical
  validity." — `--verdict` was enabled (`config/holon.json` `bend.verdict:
  true`) and passes everywhere; recorded as `kernel.verdict` per spec.
- A vacuous LAWS.bend still prints `ALL PROOFS CHECK` — handled by checking
  law names (G11) rather than trusting exit 0.

## P5: replay on the real Morph code

`replay/M0/report.json` (morph @ 3e44e795586af3e11285b603ab642c67823add51) is
folded into the result records by `python3 -m holon replay --milestone M0`,
and `holon run` applies it automatically when the report exists so regenerated
output stays identical.

| Law | go | solidity | replay.status |
|---|---|---|---|
| L_par_hdr_v2 | passed | not_applicable (needs full commitBatch deployment, M1) | passed |
| L_dom_hdr | passed | passed | passed |
| L_par_hdr_ssvh | passed | not_applicable (Rollup.sol:351 writes bytes32(0) by inspection; live exec needs commitBatch, M1) | passed |

`HOLON_REPLAY=1 python3 -m unittest tests.test_50_replay -v` passes.

Facts-audit differences (`replay/M0/facts_audit.md`):

- **D1** — the real Go v2 producer `BatchCache.createBatchHeaderWithSequencerSetHash`
  (batch_cache.go:1720-1731) encodes a `BatchHeaderV1` then patches `h[0] = 2`;
  the codec-level obstruction is real but the call site resolves it (M1).
- **D2** — `sealBatch` (batch_cache.go:1447-1462) rejects nonzero ssvh for live
  batches; nonzero only for legacy replay at index ≤ legacyCutoverBatchIndex.
  Confirms L_par_hdr_ssvh is an intent question, not a live defect.
- **D3** — node/types/batch_header.go is a DEPRECATED duplicate of common/batch's
  `BatchHeaderBytes` (no BlobCommitHash, no encoders); a second `dec_go`
  instance is uncovered by the M0 facts.
- **D4** — dirty memory is harmless at this commit: writes cover [0,249) for v0
  and [0,257) for v1/v2; storeLastBlockNumber writes past the hashed range.

## Questions for the human / suspected frozen-file issues

None. Model, emitter and predictions all agree; nothing was steered toward a
prediction.
