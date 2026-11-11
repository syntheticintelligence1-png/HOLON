"""Round 8 (M3), A7 (gate evasion) against the convergence gate: a round that claims to count with hollow evidence.

    python audit/rounds/M3/round8/a7_hollow_round.py <target commit> <scratch dir>

Builds, in <scratch dir>, a minimal root holding the target commit's audit/ and spec/ trees (git archive; nothing of
this checkout's working tree), then adds a fabricated round 8 there that claims to count under HUMAN_ANSWERS Q9b:
  - a1.json: one mutant, verdict "refused" (nothing was applied, extracted or run);
  - a2.json: one case, verdict "unsupported" (nothing was run on either side);
  - a4.json and packet.json: only the four header fields the evidence rule reads (version field, milestone, round,
    target_commit), no law, no input, no canary;
  - round8.json: A1-A7 marked run, each citing those files, no finding.
Then it runs `holon audit round --milestone M3 --root <scratch>` and `holon audit converge --milestone M3 --root
<scratch> --out <scratch>/audit_status.json`, and prints round 8's row. Nothing is written outside <scratch dir>.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

C, S = sys.argv[1], Path(sys.argv[2]).resolve()
ROOT = Path(__file__).resolve().parents[4]
S.mkdir(parents=True, exist_ok=True)
tar = S / "t.tar"
subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "-o", str(tar), C, "audit", "spec/M3/lib",
                "spec/schemas"], check=True)
subprocess.run(["tar", "-xf", str(tar), "-C", str(S)], check=True)
tar.unlink()
d = S / "audit" / "rounds" / "M3" / "round8"
assert not (S / "audit/rounds/M3/round8.json").exists(), "round 8 already exists at the target"
d.mkdir(parents=True)
head = {"milestone": "M3", "round": 8, "target_commit": C}
rel = "audit/rounds/M3/round8"
a1 = {"a1_version": "holon-audit-a1/0.1", **head, "checkout": {"repo": "x", "commit": "0" * 40},
      "spec": {"path": f"{rel}/s.json", "sha256": "0" * 64, "body": {}}, "budget": {"law_timeout_s": 1, "max_law_runs": 0},
      "law_runs": 0, "scope": {"documents": [], "reachable": [], "out_of_reach": []},
      "baseline": {"documents": {}, "runs": {}},
      "mutations": [{"id": "m1", "file": "x.sol", "spec_sha256": "0" * 64, "diff": None, "documents": {},
                     "derivation": None, "runs": {}, "not_run": {}, "verdict": "refused", "why": "nothing applied",
                     "obstructions": []}],
      "summary": {"detected": [], "missed": [], "incomplete": [], "refused": ["m1"]},
      "attack": {"id": "A1", "category": "mutation_adequacy", "auditor_type": "A1", "run": True, "tried": "-",
                 "result": "no_finding", "findings": [], "evidence": [f"{rel}/a1.json"]}}
a2 = {"a2_version": "holon-audit-a2/0.1", **head, "spec": {"path": f"{rel}/s.json", "sha256": "0" * 64, "body": {}},
      "cases": [{"id": "c1", "entry": {"kind": "go", "document": "none"}, "verdict": "unsupported", "why": "nothing"}],
      "summary": {"agree": [], "disagree": [], "unsupported": ["c1"]},
      "attack": {"id": "A2", "category": "model_vs_code", "auditor_type": "A2", "run": True, "tried": "-",
                 "result": "no_finding", "findings": [], "evidence": [f"{rel}/a2.json"]}}
a4 = {"a4_version": "holon-audit-a4/0.1", **head}
pk = {"packet_version": "holon-audit-packet/0.1", **head}
for name, obj in (("a1.json", a1), ("a2.json", a2), ("a4.json", a4), ("packet.json", pk)):
    (d / name).write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")
ev = {"A1": [f"{rel}/a1.json"], "A2": [f"{rel}/a2.json"], "A4": [f"{rel}/a4.json"]}
cats = [("A1", "mutation_adequacy", "A1"), ("A2", "model_vs_code", "A2"), ("A3", "statement_fidelity", "A3"),
        ("A4", "vacuity", "A4"), ("A5", "bindings_ledger", "A4"), ("A6", "determinism", None),
        ("A7", "gate_evasion", None)]
attacks = []
for i, c, t in cats:
    a = {"id": i, "category": c, "run": True, "tried": "-", "result": "no_finding", "findings": [],
         "evidence": ev.get(i, [])}
    if t:
        a["auditor_type"] = t
    attacks.append(a)
rnd = {"round": 8, "milestone": "M3", "target_commit": C, "round_version": "holon-audit-round/0.2", "dry_run": False,
       "packet": {"path": f"{rel}/packet.json", "sha256": hashlib.sha256((d / "packet.json").read_bytes()).hexdigest()},
       "auditor": {"session": "a7-hollow-probe/never-a-real-session", "family": "same", "ruling": "HUMAN_ANSWERS Q9b",
                   "counts_toward_convergence": True},
       "attacks": attacks, "findings": [], "notes": "a fabricated round with hollow evidence (A7 probe)"}
(S / "audit/rounds/M3/round8.json").write_text(json.dumps(rnd, indent=1) + "\n")
for args in (["audit", "round", "--milestone", "M3", "--root", str(S)],
             ["audit", "converge", "--milestone", "M3", "--root", str(S), "--out", str(S / "audit_status.json")]):
    p = subprocess.run([sys.executable, "-m", "holon", *args], cwd=str(ROOT), capture_output=True, text=True)
    print(f"$ python -m holon {' '.join(args).replace(str(S), '<scratch>')}: exit {p.returncode}")
    print("\n".join(l for l in (p.stdout + p.stderr).splitlines() if "round8" in l or "ROUNDS" in l or "round(s)" in l))
st = json.loads((S / "audit_status.json").read_text())
row = [x for x in st.get("rounds") or [] if x.get("round") == 8]
print("round 8 in audit_status.json:", json.dumps(row))
print("converged:", st.get("converged"))
