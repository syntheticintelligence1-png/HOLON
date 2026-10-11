# Session P0: Bend 2 calibration (about 1–2 hours)

You are joining the HOLON repo. Read `AGENTS.md`, then `docs/BEND_PRIMER.md`, then `docs/M0_SPEC.md` §1.

The frozen manifest digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`. `python tools/freeze.py digest` must print exactly this value, before your work and after it.

## Why this session exists

Bend 2 was released in September 2026, after your training data. Your priors about "Bend" are probably about Bend 1, which is a different language. This session turns the language into verified knowledge before anyone writes generators. It is not a reading assignment: every claim you make must be backed by a file the checker ran.

## Tasks

1. **Install Bend 2.**
   - Preferred: `tools/install_bend.sh`, which pins commit `2343aec…`, version 2.0.36.
   - Alternative: the official installer (`curl -fsSL https://bend-lang.com/install.sh | sh`).
   - Create `config/holon.json` from `config/holon.example.json`, with `bend.cmd` pointing at your `bend`.
   - If the version you end up with is not 2.0.36: run every probe; if all pass, set `pinned_version` to it and say so in the PR.
2. **Learn the language.** Read the full output of `bend guide`, then skim `bend base`. Save both to `docs/bend_guide.txt` and `docs/bend_base.txt`, so later sessions read the same text.
3. **Run the tests:**
   ```
   python -m unittest tests.test_00_freeze tests.test_01_reference tests.test_02_bend_probes -v
   ```
   All must pass. If a probe fails, do not edit it (it is frozen). Report the exact output and what it implies.
4. **Verify the second kernel.**
   - Install elan with toolchain `leanprover/lean4:v4.34.0`.
   - Run `bend <probe> --verdict` on p01, p07, p09, p11 and p12.
   - Record pass or fail and the wall time of each.
   - Run `--verdict` on p05 too: it must fail.
5. **Find the scale limit.**
   - Write `scratch/scale_*.bend`, which is not committed: a record with N `U32` fields; two encoders, one using overlapping `put` writes and one direct; equality proved by `match` then `{==}`, as in probe p07.
   - Use N = 300, 1 000, 3 000, 10 000. Measure check time.
   - Record where it degrades. M1 needs this to size state-machine models.
6. **Record what you learned.**
   - Write `docs/BEND_NOTES.md` (not frozen). Include: the verdict results, the scale table, installer vs. checkout differences, and anything in the guide that the primer gets wrong or leaves out.
   - Every snippet in BEND_NOTES must be a file that you ran. Commit such files under `bend/notes/`, never under `bend/probes/`.

## Definition of done

- Tests 00, 01 and 02 pass.
- `config/holon.json` is committed, with the pin.
- `docs/BEND_NOTES.md` answers the three open questions in BEND_PRIMER §6.
- The PR description follows the AGENTS.md template.

Do not start on `holon/`.
