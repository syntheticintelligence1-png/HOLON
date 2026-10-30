# I87 (= I45a): the audit-loop machinery, exercised on today's M3

Written from `docs/BUILD_PLAN.md` row I87, a sub-key of I45 (§4 "I45. Audit loop, coordinator, rule gaps, rule
admission, SYM route (ii)"), and the lane lead's assignment. Milestone M3. I45 keeps its number for the A1-A4 rounds
over the full M3, its predictions (k = 3; the A2 round re-finds the O4 class; the A4 round flags no degenerate
inhabitant), the I34 and I25 adjudications and the convergence exit.

Whitepaper sources:
- §9.1 (the coordinator: the human's one window into the system; auditors from a different model family, fresh
  context per round);
- §9.2(6) and §9.5 (the audit loop: A1 mutation, A2 hostile input, A3 regression, A4 vacuity and over-strength;
  convergence after k consecutive rounds with no high-priority finding);
- §12.3 (L21: A4 audits that inhabitants are representative rather than degenerate) and §9.7 (hypotheses tested
  against the real oracles);
- L7 (every finding outside the rules files a rule-gap record; a new rule needs at least two instances and a basis
  argument; BUILD_PLAN I45 adds human approval) and L19 (shared blind spots: another family, fresh context);
- §5.4 (ii) (SYM route (ii) adjudications: I45's, not this key's).

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` first. Then read:
- `docs/HUMAN_ANSWERS.md` Q9: same-family rounds are labelled `same` and never count toward convergence;
- `docs/iterations/I5.md` and `docs/iterations/I21.md`, `audit/rounds/`, `audit/M2_round2.md`,
  `spec/schemas/audit_round.schema.json` (I5's minimal round format, which this key extends);
- `holon/audit/` (prereg.py, status.py, regress.py, and I21's hostile.py and vacuity.py for M2, which must keep
  working unchanged);
- `holon/gate.py` and `holon/inhabit.py` (G11V; reused, never duplicated), `holon/versions/inhabit.py` (G11V's
  in-flight clause), `holon/codecrun.py` and `holon/gen/linked.py` (the codec inhabitants), `holon/oracle_check.py`
  (A4's hypothesis tests), `holon/statement_diff.py` (signatures verified only against keys the human froze).

**The docstring of `tests_m3/test_audit_loop.py` is the contract.** It fixes the round format, the convergence rule
(CV1-CV4, RD1-RD3), the hostile-review packet, A4's classes (V1-V7) and degenerate rules (D1-D3), the representative
rule, the oracle report (O1-O3), the rule-gap records and the L7 admission rule, and the coordinator's commands.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in
`spec/M3/amendments.jsonl`):
- `spec/M3/lib/audit_loop.json`: the policy (k, auditor types, counted family, high-priority severities, degenerate
  rules, representative fill, admission rule); it names no law, action or target;
- `tests_m3/_i87.py`: the instrument, written without holon's audit code: its own reading of the classes and
  degenerate rules, its own convergence and admission rules over synthetic fixtures, and the oracle tables checked
  with `tests_m2/_keccak.py`.

Deliverables:
- `holon/audit/rounds.py`, `holon/audit/converge.py`, `holon/audit/oracles.py`, `holon/audit/gaps.py`; an M3 path in
  `holon/audit/hostile.py` (the hostile-review packet) and `holon/audit/vacuity.py` (A4), leaving I21's M2 path
  byte-for-byte unchanged in behaviour; `holon/coordinator.py`;
- `python -m holon audit round|converge|oracles|gaps ...`, `holon audit hostile|vacuity --milestone M3 ...`,
  `python -m holon coordinator status|prompt|audit-prompt ...`;
- `spec/schemas/audit_round.schema.json` extended with optional fields only, `spec/schemas/audit_status.schema.json`,
  `spec/schemas/rule_gap.schema.json`;
- `audit/prompts/` (the auditor prompts, A1-A4 and the round preamble);
- the dry run on today's M3: `audit/rounds/M3/round1.json` (same family, dry run, not counted), its packet and
  `a4.json`, `audit/M3_findings.jsonl`, `results/M3/audit_status.json` (converged = false), `audit/rule_gaps.jsonl`,
  `docs/STATUS.md`.

Constraints:
- Never fake convergence. No round run here is from another family; every round I87 writes is labelled `same` and
  `dry_run`, and `results/M3/audit_status.json` says converged = false until real rounds exist.
- No human approval exists, and agents never freeze a key: the L7 admission check must refuse every candidate.
- Reuse the gate's G11V records, its in-flight clause and the inhabitant generators; never re-implement a gate check.
- No generator closure moves: no law, record, generated or replay file changes except `results/M3/audit_status.json`.
- No law id, action, register or target in `holon/`. Determinism: every output regenerates byte for byte.

Exit: `tests_m3/test_audit_loop.py` (construction tests green; a missed prediction is reported, not fixed);
`python -m holon audit prereg --milestone M3` prints PREREG OK.
