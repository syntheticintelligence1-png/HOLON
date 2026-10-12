# Checkpoint after merging I7–I11

On `341ffee`, after I7 through I11 were merged onto one tree, all three suites were run in full, one after the other:

| suite | summary line |
|---|---|
| `python -m unittest discover -s tests -t .` (frozen) | `Ran 38 tests in 571.145s` / `OK (skipped=1)` (the replay test) |
| `python -m unittest discover -s tests_m1 -t .` | `Ran 13 tests in 896.526s` / `OK (skipped=1)` (the M1 mutation test passes again; see I6.md) |
| `python -m unittest discover -s tests_m2 -t .` | `Ran 262 tests in 840.891s` / `FAILED (failures=2, skipped=2)` |

The two `tests_m2` failures are I4's preregistered misses. They are reported in `docs/iterations/I4.md`, and they stay red by rule:
- `test_replay_completion::TestConsumerSides::test_fact_z_consumer` (I4-P4): Go `node/derivation` rejects both equal-commitment batches, so the consumer observes no divergence.
- `test_filter::TestBins::test_predicted_bins_new_replays` (I4-P5): `L_fact_Z` is `pending`, not `finding`.

Gates on the same tree:
- M0 passes: G7 lists Lean 8/8 with I2, and both Lean canaries are rejected.
- M1 passes, with 21 canaries rejected.

`python -m holon audit prereg --milestone M2` passes for I1 through I11.
