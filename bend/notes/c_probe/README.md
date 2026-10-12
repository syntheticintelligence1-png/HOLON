# C probe (I16)

`RESULT.json` records what `tests_m2/test_native.py` re-runs on `probe.bend`:
the exit code of `bend probe.bend -o probe.c`, of `bend probe.bend -o probe`, and the binary's exit
code and stdout. `probe.bend` is a small codec in the shape of the generated M0 model (a byte record, a
`put` chain over a zeroed buffer, a version dispatch); it has a `main`, no `!` and no escape hatch.
It emits C, builds with clang 18 and runs: `0 1 2 255` then `57005`.

`arity_limit` records why the M0 model itself does not build natively with the pinned Bend 2.0.36:

- `bend <driver of the M0 model> -o driver.c` fails with `Error: an arity over 247`
  (results/M2/native.json, status `fallback`).
- The C backend (`bend2/comp.ts`, `WIDE = 247`) refuses a compiled segment with more than 247
  parameters. A non-tail call made while more than 246 variables are live needs such a segment for its
  continuation. The generated Go encoders `enc_go_v0` and `enc_go_v1` open the 257-cell header record
  and call `put` once per field while the cells of the later fields are still live (248 cells for
  `enc_go_v0`, 256 for `enc_go_v1`). `enc_sol` keeps fewer live: it never reads `sequencerSetVerifyHash`.
- `wide.bend` reproduces it in isolation: a 248-field record, one `put` call while 247 fields are live,
  fails with the same error. `wide_control.bend`, the same program with 247 fields (246 live), emits C.

The driver logic is not the cause: run by `bend driver.bend JOBS OUT` (Bend's own JavaScript lane, not
native), the same generated driver agrees with the `.mjs` model on every refuter candidate
(results/M2/native.json `driver_on_bend_lane`).
