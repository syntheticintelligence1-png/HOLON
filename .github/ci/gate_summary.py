"""CI only: print a gate report's per-check verdicts (GENV first) and add them to the job summary.
   python .github/ci/gate_summary.py <report.json>"""
import json
import os
import sys
from pathlib import Path

p = Path(sys.argv[1])
try:
    rep = json.loads(p.read_text())
except (OSError, ValueError) as e:
    sys.exit(f"{p}: unreadable ({e})")
checks = rep.get("checks") or {}
lines = [f"{p}: milestone {rep.get('milestone')} passed={rep.get('passed')}"]
for name in sorted(checks, key=lambda c: (c != "GENV", c)):
    c = checks[name]
    lines.append(f"  {name} {'PASS' if c.get('passed') else 'FAIL'}: {c.get('detail', '')}")
for name, why in sorted((rep.get("not_applicable") or {}).items()):
    lines.append(f"  {name} n/a: {why}")
print("\n".join(lines))
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary, "a") as f:
        f.write("```\n" + "\n".join(lines) + "\n```\n")
