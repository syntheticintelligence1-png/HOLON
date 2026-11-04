"""`python -m holon audit status [--json] [--root DIR]`: the state of the adversarial audit findings.

Reads audit/findings.jsonl (one finding per line, written by audit rounds; BUILD_PLAN I5) and reports
totals and open findings per severity. Open high-severity findings are `blocking`: the command exits 1
while any exist, so an iteration cannot start on top of one (I5 exit: zero open high before I6).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
SEVERITIES = ("high", "medium", "low")
STATUSES = ("open", "fixed", "wontfix", "duplicate")


def load(root: Path, path: str = "audit/findings.jsonl") -> tuple[list[dict], list[str]]:
    p = root / path
    if not p.exists():
        return [], [f"{p.relative_to(root)} does not exist"]
    out, bad = [], []
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            f = json.loads(line)
        except json.JSONDecodeError as e:
            bad.append(f"line {n}: not JSON ({e})")
            continue
        if not isinstance(f, dict) or f.get("severity") not in SEVERITIES or f.get("status") not in STATUSES:
            bad.append(f"line {n}: needs a severity in {SEVERITIES} and a status in {STATUSES}")
            continue
        out.append(f)
    return out, bad


def summary(findings: list[dict]) -> dict:
    return {
        "total": len(findings),
        "by_status": {s: sum(1 for f in findings if f["status"] == s) for s in STATUSES},
        "open": {s: sum(1 for f in findings if f["severity"] == s and f["status"] == "open") for s in SEVERITIES},
        "blocking": sorted(f.get("id", "?") for f in findings if f["severity"] == "high" and f["status"] == "open"),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon audit status", description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    ap.add_argument("--findings", default="audit/findings.jsonl",
                    help="findings file relative to the root (the M2 round writes audit/M2_findings.jsonl)")
    a = ap.parse_args(argv)
    findings, bad = load(Path(a.root).resolve(), a.findings)
    s = summary(findings)
    if bad:
        s["errors"] = bad
    if a.json:
        print(json.dumps(s, indent=2, sort_keys=True))
    else:
        print(f"{s['total']} findings; open: " + ", ".join(f"{k} {v}" for k, v in s["open"].items())
              + f"; blocking (open high): {', '.join(s['blocking']) or 'none'}")
        for e in bad:
            print(f"error: {e}")
    return 1 if s["blocking"] or bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
