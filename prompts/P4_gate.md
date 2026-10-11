# Session P4: the gate, canaries and tamper resistance (about half a day)

Read `AGENTS.md`, `docs/M0_SPEC.md` §7 and `docs/BEND_PRIMER.md` §3.

The frozen digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`.

## Tasks

1. **`holon/gate.py` and `python -m holon gate --milestone M0 [--root] [--report]`.**
   - Checks GENV, G2, G1, G3, G5, G11 and G4, in the order and with the meanings in M0_SPEC §7.
   - GENV runs first. If `bunfig.toml` or `.env` exists, do not invoke Bend at all: write the report and fail.
   - Always write the report, also on failure, and make it schema-valid.
2. **Canaries.**
   - Generate them from every PROVED law, with kinds `pin_const`, `swap_fn` and `negated`.
   - Keep a mutant only if the model produces a concrete counterexample.
   - Emit each one with the same emitter and proof generator as the real laws.
   - Every canary must be rejected. Store `law`, `negated`, `counterexample` and `rejected` for each.
3. **Prove to yourself that the canaries work, without committing anything.** In a scratch branch, make the emitter write `{L == L}` instead of `{L == R}`. G4 must fail while G1, G5 and G11 still pass. Describe the result in the PR.
4. Run the gate on the committed tree and commit `results/M0/gate_report.json`.

## Definition of done

- `python -m unittest tests.test_40_gate -v` passes. The tamper tests delete proofs, add holes, add `@unsafe`, make a law file vacuous, edit a statement, and add a `bunfig.toml`.
- Then the full suite passes:
  ```
  python -m unittest discover -s tests -t . -v
  ```
  (test 50 skips).
