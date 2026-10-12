# Checkpoint after merging I12, I13 and I16

The I12, I13 and I16 implementations were built in separate worktrees against the preregistration `32dd35c`. Each was independently audited and cherry-picked onto `claude/holon-v2-bend2-c6z3cd`, and the audit findings were fixed after the merge:
- I13 audit: clean.
- I12 audit: three minor findings, all fixed.
- I16 audit: one regression (G1 compared a gate-derived metrics section) and one minor finding, both fixed.

Full suites on the merged tree (`9807a06` plus the gate reports), run one after the other:

| suite | summary line |
|---|---|
| `python -m unittest discover -s tests -t .` (frozen) | `Ran 38 tests in 819.462s` / `OK (skipped=1)` |
| `python -m unittest discover -s tests_m1 -t .` | `Ran 13 tests in 952.231s` / `OK (skipped=1)` |
| `python -m unittest discover -s tests_m2 -t .` | `Ran 376 tests in 2061.001s` / `FAILED (failures=4, skipped=2)` |

The four `tests_m2` failures:
- **I4-P4** (`test_replay_completion::TestConsumerSides::test_fact_z_consumer`) and **I4-P5** (`test_filter::TestBins::test_predicted_bins_new_replays`): preregistered misses, reported in `docs/iterations/I4.md`, red by rule.
- **I16-P1** (`test_native::TestNativeAgreement::test_native_agrees_with_mjs_on_every_refuter_candidate`): a preregistered miss. Bend 2.0.36's C backend rejects the M0 model's 257-field header (arity limit 247), so the `.mjs` model stays the engine (BUILD_PLAN I16 fallback). Recorded in `results/M2/native.json` and `docs/iterations/I16.md`; red by rule.
- `test_i3_review::TestG1IgnoresRunLogs::test_gate_logs_do_not_affect_g1`: the regression the I16 audit found, fixed in the commit after the suites started. After the fix, that test and `tests_m2.test_metrics` pass: `Ran 11 tests ... OK`.

Gates after the fixes:
- M0 passes: G1 finds `metrics.json` identical, G7 gives Lean I2 for 8 laws, and 16 canaries are rejected.
- M1 passes, with 21 canaries rejected.

`python -m holon audit prereg --milestone M2` passes for I1 through I13 and I16.

Not built: I14 (evidence calculus) and I15 (sorts II and the first generated laws). I14 depends on I13's frozen assignment, which is now committed in `gen/M2/sorts/`.
