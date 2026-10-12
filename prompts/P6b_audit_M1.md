# Session P6b: adversarial audit of M0 and M1 (fresh session)

You have never seen this codebase. Your job is to break it, not to improve it. Do not fix anything.

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, `docs/BUILD_PLAN.md` §0–§1, `docs/M1_REPORT.md`, `docs/iterations/I1.md`..`I4.md`, then the code in `holon/`. The Morph target is the read-only checkout `/root/work/morph` at `3e44e795586af3e11285b603ab642c67823add51`. Work only on scratch copies: `tests._util.copy_repo()` for HOLON, never the repo itself.

## Attack the claims

For each category, produce a concrete demonstration (commands and output) or explain why it is not possible. Cover M0 (header codec, 8 laws) and M1 (rollup machine and Go BatchData, 16 laws).

1. **statement_fidelity.** Each generated `gen/<M>/*/LAWS.bend` says exactly what its IR says: same functions, premises and binders. Read the kernel form with `bend PROOF.bend -o x.bendtt`.
2. **gate_evasion.** Find a change to `holon/`, `gen/`, `results/` or `replay/` that makes a false claim PROVED, a refutation unreplayed, or a bin `finding`, while `python -m holon gate --milestone <M>` still passes.
3. **model_vs_code.**
   - Check 3 random M0 facts ops against Morph's code, and 3 random M1 transition rules against `Rollup.sol` / Go.
   - Look for code paths the facts leave out.
4. **vacuity.** Is any premise unsatisfiable, or any law true for a reason unrelated to the code? G11V's inhabitants are the starting point. Attack them.
5. **determinism.** Run the pipelines twice in copies and diff the outputs. Look for anything that reads the environment, time or an unpinned tool.
6. **mutation_adequacy.** Invent 3 new realistic bugs in scratch copies of the facts, beyond MUT1–MUT4: an off-by-one, a missing write, a wrong guard. Does each change some outcome? A bug that changes nothing is a coverage gap: name the missing law family.
7. **bindings_ledger.** Evade G2 through `spec/bindings/` or the ledger (`spec/ledger/assumptions.json`). Is any assumption a record depends on missing from its `model_assumptions`?

## Output (only these files)

- `audit/M0_round1.md` and `audit/M1_round1.md`: what you tried per category and what happened, with reproductions.
- `audit/rounds/M0/round1.json` and `audit/rounds/M1/round1.json`:
  ```json
  {"round": 1, "milestone": "M1", "target_commit": "<40-hex HOLON HEAD you audited>",
   "auditor": {"session": "<label>", "family": "same", "counts_toward_convergence": false},
   "attacks": [{"id": "A1", "category": "statement_fidelity", "tried": "...", "result": "finding|no_finding",
                "findings": ["F-M1-01"]}],
   "findings": ["F-M1-01"]}
  ```
  Every one of the 7 categories appears at least once per milestone. The family is `same` unless the human says otherwise (Q9).
- `audit/findings.jsonl`, one line per finding:
  ```json
  {"id": "F-M1-01", "round": "M1/round1", "severity": "high|medium|low",
   "category": "<one of the 7>", "title": "...", "reproduction": "...", "suggested_fix": "...",
   "status": "open", "fix_iteration": "I5", "test": null}
  ```
  Severity: `high` means a false result can pass the gate; `medium` weakens evidence; `low` is hygiene.

Report only what you reproduced. A finding without a reproduction is not a finding.
