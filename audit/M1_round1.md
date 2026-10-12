# Audit round 1, M1 (partial)

Same-family auditor (Q9 unanswered); does not count toward convergence. The round was stopped early at the human's request before every category finished, so categories marked *incomplete* are not evidence of absence. Findings below were reproduced on scratch copies of the repo; the scratch artefacts lived in the session scratchpad.

Audited HOLON commit: `01aa22f29de08f32abcd082c5d8cc523d67d2938`. Morph target: `3e44e795586af3e11285b603ab642c67823add51` (read-only).

## What was tried, per category

- **statement_fidelity** (no_finding): Not finished before the stop (incomplete).
- **gate_evasion** (finding): Attack B (forged consumer outcome, rerun), attack A (co-location) and attack C; full gates passed. Findings: F-M1-03, F-M1-04, F-M1-06.
- **model_vs_code** (no_finding): Initial principals and parameters checked against the facts (active [2,3], challengers [4], W/F/D 10/40/20); further rules not finished (incomplete).
- **vacuity** (no_finding): Covered by G11V; the vacuity probe did not report before the stop (incomplete). Attack D (a forged reachability label on an inhabitant that still checks) is filed under gate_evasion (F-M1-05).
- **determinism** (no_finding): Two full runs: 64 files each, identical after stripping 'seconds', identical to the committed outputs.
- **mutation_adequacy** (finding): Three new mutations: NM1_1 revert keeps rri, NM1_2 challenge without the in-challenge guard, NM1_3 finalize window off by one. NM1_3 moves L_disch_delay_wait to UNKNOWN; NM1_1 and NM1_2 move nothing. Findings: F-M1-01, F-M1-02.
- **bindings_ledger** (no_finding): A G2 probe was started when the audit was stopped (incomplete).

## Findings

### F-M1-01 (medium, mutation_adequacy): revertBatch keeping the revert request index changes no M1 outcome

- Reproduction: Mutation NM1_1 (revert_keeps_rri): trace commitBatch, challengeState, wait, proveState, revertBatch, commitState. The last step goes from ok to 'rev 2 (pending revert request)' on the model, yet no law moves (mut/live_out.txt, mut/log.txt).
- Suggested fix: An UNDO law for revertBatch's request-index residue, or an invariant over rri.
- Status: open; fix iteration: I27.

### F-M1-02 (medium, mutation_adequacy): challengeState without its in-challenge guard changes no M1 outcome

- Reproduction: Mutation NM1_2 (challenge_no_inch_guard): a second challengeState now succeeds instead of reverting with 'already in challenge'. No law moves (mut/live_out.txt, mut/log.txt).
- Suggested fix: A SYM or DISCH law about concurrent challenges (at most one open).
- Status: open; fix iteration: I31.

### F-M1-03 (medium, gate_evasion): A consistently forged replay outcome passes the full gate (G6 cannot rerun the real code)

- Reproduction: Attack B: forge L_fact_Z's go_consumer outcome in replay/M1/report.json consistently (outcomes, classes, flags), then `holon run --milestone M1` and the full gate in a copy: GATE PASSED (scratchpad/audit_i5 (session scratch, not committed), attackB_M1_gate.json). This is the known limit stated in docs/iterations/I4.md: G6 checks consistency, not re-execution.
- Suggested fix: Re-execute `holon replay` on a trusted runner (CI) and compare the report byte for byte; until then, label replay reports as agent-writable evidence.
- Status: open; fix iteration: I47.

### F-M1-04 (medium, gate_evasion): A counter-law proved at a witness other than the recorded (replayed) one passes the gate

- Reproduction: Attack C: in a copy, the counter-law PROOF.bend proves the refutation at a witness different from record.witness (the one the replay binds by hash); the full gate passed (scratchpad/audit_i5 (session scratch, not committed), attackC_M0_gate.json). The law stays refuted (the kernel-checked witness is genuine), but the replayed witness is not tied to the kernel-checked one. Detailed reproduction was in the stopped audit session.
- Suggested fix: G1/G5: regenerate the counter-law PROOF.bend from record.witness and require it byte-identical (or parse the witness constants out of the checked file).
- Status: open; fix iteration: I10.

### F-M1-05 (medium, gate_evasion): An unreachable constructed inhabitant recorded as reachable passes the gate

- Reproduction: Attack D: in a copy, a non-vacuity witness built as a constructed state (not run(p, s0)) is recorded with reachable: true; the full gate passed (scratchpad/audit_i5 (session scratch, not committed), attackD_M1_gate.json). Non-vacuity itself still holds (the inhabitant checks); what is overstated is reachability.
- Suggested fix: G11V: recompute `reachable` from the witness shape (every state binder is {run: ...} from s0) instead of trusting the field.
- Status: open; fix iteration: I8.

### F-M1-06 (low, gate_evasion): No check ties a record's artifacts.proof to its artifacts.laws (co-location)

- Reproduction: Attack A (both milestones): the gate passed after the co-location edit (scratchpad/audit_i5 (session scratch, not committed), attackA_M0_gate.json, attackA_M1_gate.json). holon/ is not frozen (Q1), so regeneration-based checks trust the generators.
- Suggested fix: G11: require artifacts.proof and artifacts.laws to be siblings under gen/<m>/<law>/ and PROOF.bend to import exactly that LAWS.bend.
- Status: open; fix iteration: I10.

## Not covered

Statement fidelity, bindings/ledger evasion and most model-vs-code sampling did not finish. They are carried to the next audit round (I21), which must cover them before any convergence claim.
