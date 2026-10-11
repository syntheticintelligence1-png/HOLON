# Bend 2 calibration notes (M0, P0)

Environment: Ubuntu, bun (~/.bun/bin), node v22.23.3, Lean 4.34.0 via elan.
Bend 2.0.36, checkout of commit 2343aec043b7967f2a6f653e7f2e3bcbe55c8c9a
(equal to upstream HEAD on 2026-10-11), wrapper /home/ubuntu/.holon/bin/bend
installed by tools/install_bend.sh. The release-installer binary was not
tested; every result below comes from the checkout wrapper.

## Probes

`python -m unittest tests.test_00_freeze tests.test_01_reference tests.test_02_bend_probes -v`
ran 10 tests and all passed.

`bend <probe> --verdict` (the TS checker, then elaboration and a re-check in
the BendTT kernel in Lean, bend2/bendtt.lean):

| probe | result |
|---|---|
| p01_law_refl | ALL PROOFS CHECK |
| p07_codec_equal | ALL PROOFS CHECK |
| p09_counterlaw_forall | ALL PROOFS CHECK |
| p11_counterlaw_exists | ALL PROOFS CHECK |
| p12_fn_premise | ALL PROOFS CHECK |
| p05_unsafe | SOME PROOFS FAIL: "2 defs rely on unsafe or foreign code: loop" |
| p02_false_refl | SOME PROOFS FAIL: expected `Nat.add(x, 1n)` |

On the first `--verdict` run, Bend builds the kernel and caches it in
`~/.bend/bendtt`. `$BENDTT` can point to a prebuilt kernel. `--verdict`
accepts only Lean v4.34.0 (safe.ts `LEAN_VERSION`).

## Differences from the primer

- The plain checker prints `ALL PROOFS CHECK`, then the line
  `Use --verdict for mathematical validity.` Bend therefore treats only the
  `--verdict` path as authoritative. HOLON runs `--verdict` as well when
  `config.bend.verdict` is true and records the result in
  `kernel.verdict`.
- The plain checker also prints `ALL PROOFS CHECK` for a file with zero
  laws, so the gate must check the expected law names itself.

## Scale

`bend/notes/gen_scale.py N` generates a Data record with N U32 fields, an
encoder that writes through `put` into dirty memory, a direct-list encoder,
and an equality law proved by opening the record and applying `{==}`.
`bend/notes/scale_300.bend` is the N=300 instance.

| N | plain check | --verdict |
|---|---|---|
| 300 | ALL PROOFS CHECK, 0.14 s | ALL PROOFS CHECK |
| 1000 | ALL PROOFS CHECK, 0.36 s | ALL PROOFS CHECK, 3.7 s |
| 2500 | ALL PROOFS CHECK, 1.3 s | ALL PROOFS CHECK, 49 s |
| 3000 | stack overflow ("the machine stack overflowed"), 1.1 s | not run |
| 10000 | stack overflow, 7.8 s | not run |

- `ulimit -s unlimited` did not fix the overflow at N=3000.
- `--verdict` cost grows superlinearly: 1000 → 2500 fields multiplies it by
  about 13.
- The 257-byte Morph header is well inside both limits. A model with 3000+
  flat fields would have to be split into nested records or chunked lists.
