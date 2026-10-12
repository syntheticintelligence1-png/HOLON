# I5: first audit round on M0/M1

Rendered from `docs/BUILD_PLAN.md` §4, I5 (debt D-g). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

## Why

No adversarial audit has ever run on M0 or M1. `prompts/P6_audit.md` was never executed, and there is no `audit/` directory (D-g). M2 builds on these results, so they get attacked first.

## What to build

1. **Prereg commit first.** The `I5` key, the red test `tests_m2/test_audit.py`, the auditor prompt `prompts/P6b_audit_M1.md`, and this prompt.
2. **The round.** One fresh auditor session runs `prompts/P6b_audit_M1.md` and writes only `audit/`. Q9 is unanswered, so the auditor is the same model family, and the round is labelled `same` and does not count toward convergence.
3. **`spec/schemas/audit_round.schema.json`.** A minimal version; I45 extends it.
4. **`python -m holon audit status [--json]`** reads `audit/findings.jsonl` and reports totals and open findings per severity. It lists open high findings as `blocking` and exits 1 while any exist.
5. **Triage and fixes.** Every high finding is fixed before I6, each fix with a test (P6), and its line in `findings.jsonl` is set to `fixed` with that test. Medium and low findings get a `fix_iteration`. A finding judged wrong is set to `wontfix` with the reason in the round file. It is never deleted.

## Rules

- The auditor does not fix anything.
- Fix sessions never weaken a claim or edit frozen files.
- A finding that contradicts a prediction is a Surprise, not something to argue away.
