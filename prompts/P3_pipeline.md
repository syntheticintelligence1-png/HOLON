# Session P3: emitter, proof generator, refuter, counter-laws, pipeline (about 1 day)

Read `AGENTS.md`, `docs/M0_SPEC.md` (§2, §5–§6), `docs/BEND_PRIMER.md` (§3, §5.2–5.4) and `docs/BEND_NOTES.md`.

The frozen digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`.

## Tasks

1. **`holon/emit.py`: IR law → `LAWS.bend` + `PROOF.bend`.**
   - Premises (`field == const`) are applied through a generated `pin` def in `LAWS.bend`.
   - The law is named `law_id.lower()`.
   - Model defs are referenced as `M.<fn>` through `import ../model/morph_header.bend as M`.
   - The claim type comes from the facts function's `to` type.
2. **Proof generator "refl_after_open".** It opens every `Header` binder with `match h: case M.Hdr{...}:`, then writes `{==}`. This is the only proof class M0 needs; it is fine that it fails on `Bytes` laws.
3. **`holon/refute.py`.**
   - A deterministic, bounded witness search, evaluated on the compiled model through `model_eval`. It must never use the oracle.
   - Header candidates: all zeros, all `0xff`, one field set to `0x01..` at a time, plus seeded random. Apply the pins to every candidate.
   - Bytes candidates: versions {0, 1, 2, 3, 255} × lengths {0, 1, 2, 248, 249, 250, 256, 257, 258}, zero-filled and random.
4. **Counter-law emitter.** `exs` form with the witness as a literal, proof by motive rewrite (BEND_PRIMER §5.4).
5. **`holon/run.py` and `python -m holon run`.**
   - Behaves exactly as M0_SPEC §6 describes, including `--facts`, `--out`, `--gen-dir` and `--no-registry`.
   - Writes result records and `summary.json`.
   - Triage overrides go in `config/triage.json`, with a `why`. Decide the triage of each REFUTED law yourself, from the evidence, and justify it.
6. **Run it for real.**
   - `python -m holon run --milestone M0`.
   - Commit `gen/M0/` and `results/M0/`.
   - Compare against `predictions/M0.json`.
   - If anything differs from the prediction, do not "fix" it towards the prediction. Find out whether the model, the emitter, or the prediction is wrong, and report your finding.

## Definition of done

- `python -m unittest tests.test_30_m0_results tests.test_31_mutations -v` passes.
  - Test 31 plants four bugs in the facts. Your pipeline must move the outcomes as predicted. Any hard-coding fails here.
- All earlier tests still pass.
- In the PR, paste the summary table, and the witness and difference for each REFUTED law.
