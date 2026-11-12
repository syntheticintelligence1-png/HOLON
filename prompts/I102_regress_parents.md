# I102: holon audit regress compares each commit with its own parents

The lead's brief for I102 (2026-11-12), on the lead's `82134fff` (#165, I101). The M3 exit (docs/M3_EXIT.md) left
F-M3-07 open (round 2, medium after the lead's triage, statement_fidelity), with F-M3-30 (round 7) as its duplicate.
`holon audit regress` compares each version of a law file with the previous one in a path-limited, topologically
ordered log. On branchy history that one is often another branch's commit, so the tool:
- reports changes no commit made (680 uncovered on round 2's range, 408 on fe1f88f2..ef39bed5);
- leaves out changes commits did make (224 on fe1f88f2..ef39bed5).
The lead's triage says the fix compares each commit with each of its parents (`git rev-parse C^@`), that a merge
introduces a change only where its hash differs from every parent's, and that it must fix both directions.

## Rules for this key

- Read both findings' reproductions in `audit/M3_findings.jsonl`, and round 7's checkers
  `audit/rounds/M3/round7/a3/hidden_check.py` and `parent_check.py`. `audit/` files may be read, never edited. The
  lead's triage lines change only in their status, fix_iteration and test fields.
- Scope: `holon/audit/regress.py` hash_changes, its module docstring, and its CLI's text output where a change names
  its parent. No other report key changes. No generator closure changes, so no record and no law moves.
- A3 is an audit tool, not a gate check. Its output is what a human reads, so a phantom change and a hidden change
  are both defects, in both directions.
- Generated, target-agnostic (no target names in holon/), deterministic (sorted iteration, no clock).
- The report, docs/iterations/I102.md, states each prediction's outcome. A miss is a result.
