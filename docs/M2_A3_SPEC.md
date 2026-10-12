# M2 A3: scenario laws for the boundaries A2 never probed

A1 (19/45 = 0.4222) and A2 (14/30 = 0.4667) are final and both miss 0.80. A3 neither
replaces nor re-scores them.

## Why A3 exists

A2's misses (`replay/M2/A2/report.json`) cluster on code A2's laws never exercised:
- no `commitState` probe at all (A017, A022, A023, A027);
- no version above 2 (A003);
- no `challengeState` bump of batch `lfi+1` (A018);
- no finalize of an index below LFI or of an already-finalized batch (A028, A029);
- no revert of an uncommitted index or with `count > 1` (A008, A010, A011, A026).

These laws were written after seeing A2's misses. So they are never scored against A2's
mutants, only against a fresh held-out set drawn after they are frozen.

## A3 laws (`spec/M2/A3/build_laws.py`, committed before any A3 run)

- **Shape and checking:** the same shape and helpers as A2: closed, single-equation laws,
  with a setup law per distinct setup trace.
- **Revert reasons** are named by message (no numeric codes).
- **Predictions:** all 16 scenario laws and 10 setup laws are predicted `PROVED`. The
  predictions were written from Rollup.sol @3e44e79 without running the model.
  A law whose result differs from its prediction is reported, never edited.
- **Known limits, stated in advance.**
  - The facts abstract `finalizeBatch`'s deletes at `idx-1` as `drop win 1`. A delete at a
    different index becomes `unmodelled_write` debt, so mutants of those lines (the A004,
    A009 and A025 kind) are not expected to be detectable by any law.
  - The revert loop is modelled as one bulk effect.

## Held-out mutant set A3 (frozen after the A3 laws, before any A3 scoring)

- **Sites:** the A2 function set and sampler mechanics (`spec/M2/A2/sample_mutants.py`).
  Excluded:
  - lines used by an A1 mutant;
  - lines used by any of the 30 A2 mutants that were scored.

  At the A3 commit this leaves 75 candidates.
- **Seed:** `int(sha256("\n".join(sorted A3 statement hashes)), 16) mod 2**32`.
  Candidates are shuffled with `random.Random(seed)`, and the first 30 that compile are kept.
- **Detection, labels and invalidity:** as in A2, using M0, M1, A2 and A3 laws.
- **Threshold:** 0.80 on the 30 A3 mutants, reported separately as A3.
- **Pipeline fixes:** fixes to extraction crashes found on A2 mutants (A001,
  `unbound variable next`) may land before the A3 draw. They apply equally to the baseline.

## Pre-freeze record (before any A3 scoring)

- **Baselines:** on the hand facts and the extracted facts, all 26 A3 laws come out `PROVED`, matching every prediction.
- **A001 fix:** the extraction crash fix (`791eba6`) leaves the unmutated extraction byte-identical: baseline facts sha256 `edd337829f4aebf62e4d253c862b7b6c82f1e42f0e8205cb464604c6b01e92a0`. The A2 report is not re-scored.
- **Held-out set:** `spec/M2/A3/mutants.json`, with pool 75 and seed 1397366245.
- **Freezing:** A3 files are frozen by commit and the hashes below, as A2's are. They are not added to `tools/freeze.py` roots, which only Omar re-freezes.
  - mutant-set sha256: `619d1db5ab75f21cc5b205f0446310e290f65effece99431c3bfd6da10b08c5a`
  - `laws/A3/REGISTRY.json` sha256: `393ef84748d3aa131537110f32cda626ccebd8d7e37fff0518e71a761a2c642e`
- **Smoke run:** only a 2-mutant run (`--limit 2`, report not committed, never final) was made before the full campaign.
