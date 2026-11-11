"""A7 probe (round 6): CV1 counts a round on its own `run` flags. In a scratch copy of the target tree (never this
repository), write three M3 rounds (6, 7, 8) whose A1-A7 attacks say `run: true` but cite no evidence, ran no command
(`tried` says so), and have no packet, no round directory and no driver record; then run `holon audit round` and
`holon audit converge` on that copy. Usage: python cv1_probe.py <scratch tree of the target commit>"""
import json, sys
tree = sys.argv[1]
C = "ed893be8abb2fa2c57804cf32e0cd45de7184fbb"
cats = [("A1", "mutation_adequacy", "A1"), ("A2", "model_vs_code", "A2"), ("A3", "statement_fidelity", "A3"),
        ("A4", "vacuity", "A4"), ("A5", "bindings_ledger", "A4"), ("A6", "determinism", None),
        ("A7", "gate_evasion", None)]
for n in (6, 7, 8):
    atk = []
    for i, c, t in cats:
        a = {"id": i, "category": c, "tried": "nothing (scratch probe of CV1: no command was run)",
             "result": "no_finding", "findings": [], "run": True, "evidence": []}
        if t:
            a["auditor_type"] = t
        atk.append(a)
    r = {"round": n, "milestone": "M3", "target_commit": C, "round_version": "holon-audit-round/0.2", "dry_run": False,
         "auditor": {"session": f"scratch-probe-{n}", "family": "same", "ruling": "HUMAN_ANSWERS Q9b",
                     "counts_toward_convergence": True},
         "attacks": atk, "findings": [], "notes": "scratch probe, never committed"}
    json.dump(r, open(f"{tree}/audit/rounds/M3/round{n}.json", "w"), indent=1)
print("wrote rounds 6-8 into", tree)
