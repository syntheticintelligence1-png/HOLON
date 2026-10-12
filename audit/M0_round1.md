# Audit round 1, M0 (partial)

Same-family auditor (Q9 unanswered); does not count toward convergence. The round was stopped early at the human's request before every category finished, so categories marked *incomplete* are not evidence of absence. Findings below were reproduced on scratch copies of the repo; the scratch artefacts lived in the session scratchpad.

Audited HOLON commit: `01aa22f29de08f32abcd082c5d8cc523d67d2938`. Morph target: `3e44e795586af3e11285b603ab642c67823add51` (read-only).

## What was tried, per category

- **statement_fidelity** (no_finding): Started comparing gen/M0/*/LAWS.bend with laws/M0/*.json; the audit was stopped before a result was recorded (incomplete).
- **gate_evasion** (finding): Attack A (proof/laws co-location) and attack C (counter-law at another witness) on copies; full gate passed for both. Findings: F-M1-04, F-M1-06.
- **model_vs_code** (no_finding): Sampled facts ops were not finished before the stop (incomplete).
- **vacuity** (no_finding): Covered by G11V; the vacuity probe (vac/probe.py) did not report before the stop (incomplete).
- **determinism** (no_finding): Two full runs in separate copies: 40 files each, identical after stripping 'seconds', identical to the committed outputs.
- **mutation_adequacy** (finding): Three new mutations: NM0_1 v0 length off-by-one, NM0_2 Go v1 drops ssvh, NM0_3 Go v1 len >= 257. NM0_2 moves L_par_hdr_ssvh; NM0_1 and NM0_3 move nothing. Findings: F-M0-01, F-M0-02.
- **bindings_ledger** (no_finding): Not reached before the stop (incomplete).

## Findings

### F-M0-01 (medium, mutation_adequacy): A v0 length off-by-one in the Solidity commit-path encoder changes no M0 outcome

- Reproduction: Mutation NM0_1 (sol_v0_len_off_by_one) in a scratch copy of facts/morph_header.json: enc_sol(h v0) stays 249 bytes long, but ok_sol(enc_sol(h)) becomes False. Running `holon run --facts <copy> --no-registry` moves no law's status (scratchpad/audit_i5 (session scratch, not committed), mut/log.txt).
- Suggested fix: Add a round-trip law over the Solidity side: ok_sol(enc_sol(h)) for every version.
- Status: open; fix iteration: I24.

### F-M0-02 (medium, mutation_adequacy): A Go v1 validator that accepts len >= 257 changes no M0 outcome

- Reproduction: Mutation NM0_3 (go_v1_len_ge): ok_go(258-byte v1 header) becomes True instead of False. No law moves (mut/log.txt).
- Suggested fix: Add a PAR-domain law for version 1 (the analogue of L_dom_hdr), or a family over all versions.
- Status: open; fix iteration: I24.

### F-M1-04 (medium, gate_evasion): A counter-law proved at a witness other than the recorded (replayed) one passes the gate

- Reproduction: Attack C: in a copy, the counter-law PROOF.bend proves the refutation at a witness different from record.witness (the one the replay binds by hash); the full gate passed (scratchpad/audit_i5 (session scratch, not committed), attackC_M0_gate.json). The law stays refuted (the kernel-checked witness is genuine), but the replayed witness is not tied to the kernel-checked one. Detailed reproduction was in the stopped audit session.
- Suggested fix: G1/G5: regenerate the counter-law PROOF.bend from record.witness and require it byte-identical (or parse the witness constants out of the checked file).
- Status: open; fix iteration: I10.

### F-M1-06 (low, gate_evasion): No check ties a record's artifacts.proof to its artifacts.laws (co-location)

- Reproduction: Attack A (both milestones): the gate passed after the co-location edit (scratchpad/audit_i5 (session scratch, not committed), attackA_M0_gate.json, attackA_M1_gate.json). holon/ is not frozen (Q1), so regeneration-based checks trust the generators.
- Suggested fix: G11: require artifacts.proof and artifacts.laws to be siblings under gen/<m>/<law>/ and PROOF.bend to import exactly that LAWS.bend.
- Status: open; fix iteration: I10.

## Not covered

Statement fidelity, bindings/ledger evasion and most model-vs-code sampling did not finish. They are carried to the next audit round (I21), which must cover them before any convergence claim.
