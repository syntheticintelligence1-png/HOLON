# Session P6: adversarial audit (fresh session, ideally a different model family)

You have never seen this codebase. Your job is to break it, not to improve it.

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, and then the code in `holon/`.

The frozen digest is `f854d69b0b58b581eb205a657d6925cc1e1460141ef9626df89ea87de1594fd0`.

## Attack the claims

For each item, either produce a concrete demonstration (commands and output), or explain why it is not possible.

1. **Statement fidelity.**
   - Read every generated `gen/M0/*/LAWS.bend` next to its `laws/M0/*.json`. Does each Bend law say exactly what the IR says: same functions, same premises, same binder?
   - Use `bend PROOF.bend -o x.bendtt` to read the kernel-level statement.
2. **Gate evasion.** Find a change to `holon/` or `gen/` that makes a false claim come out PROVED while `python -m holon gate` still passes. Candidates:
   - an emitter that weakens only some laws;
   - a model that differs from the facts only outside the refuter's candidates;
   - a canary generator that only makes easy canaries.
3. **Model vs. reality.**
   - Pick 3 random facts ops and verify them against the real Morph source at 3e44e79.
   - Look for code paths the facts leave out: other encoders, other validators, the `EncodedBytes` cache.
4. **Vacuity.** Is any premise unsatisfiable? Is any law trivially true for a reason unrelated to the code?
5. **Determinism and environment.** Run the pipeline twice and diff the outputs. Look for anything that reads the environment, time, or unpinned tools.
6. **Mutation adequacy beyond the frozen four.**
   - Invent 3 new realistic bugs in a scratch copy of the facts (an off-by-one, a missing write, a wrong length rule).
   - Run `python -m holon run --facts <copy> --no-registry --out <tmp> --gen-dir <tmp>`.
   - Does each bug change some outcome? A bug that changes nothing is a coverage gap: report which law family is missing.

## Output

Write `audit/M0_round1.md`. For each finding give:
- severity (high: a false result can pass; medium: weakens evidence; low: hygiene);
- reproduction;
- suggested fix.

Do not fix anything yourself. Fixes go to a separate session, and that session's PR must add a test for each one.
