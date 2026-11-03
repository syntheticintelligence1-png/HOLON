"""Convergence of the audit loop (whitepaper §9.5: "converged after k consecutive rounds with no high-priority
finding"; BUILD_PLAN I45's exit; HUMAN_ANSWERS Q9; the contract is the docstring of tests_m3/test_audit_loop.py,
"Convergence").

    python -m holon audit converge --milestone M [--root R] [--out PATH] [--check]

writes results/<M>/audit_status.json (holon-audit-status/0.1; JSON with sorted keys, indent 1 and a final newline; no
timestamps). It exits 0 whenever it wrote the document, problems included; --check writes nothing and exits 0 iff the
regeneration is byte-identical to the file.

With the policy's k, auditor types, counted family and high-priority severities (holon.audit.rounds.load_policy) and
the milestone's findings file (audit/<M>_findings.jsonl; M0 and M1: audit/findings.jsonl):
  CV1  a round is counted iff counts_toward_convergence is true and it qualifies (holon.audit.rounds.qualifies: the
       counted family, not a dry run, every auditor type ran, a session no earlier round of M had)
  CV2  a round is clean iff every finding it lists is in the findings file with a severity that is not high-priority
  CV3  walking the rounds in order, a round that is not clean resets the streak to 0, whatever its family; a counted
       clean round adds 1; any other round leaves it unchanged
  CV4  converged iff the rounds are valid (RD1-RD3, holon.audit.rounds.check), the streak is at least k, and no
       high-priority finding of M is open
A same-family round never counts, so with no round from another family the loop cannot converge. Nothing here names a
law or a target.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .rounds import (ROOT, RoundError, check, file_sha256, findings_rel, load_findings, load_policy, load_rounds,
                     qualifies, rel_or_abs)

STATUS_VERSION = "holon-audit-status/0.1"


def dumps(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def compute(root: Path, milestone: str) -> dict:
    root = Path(root)
    policy, pp = load_policy(root, milestone)
    cv = policy["convergence"]
    k, high = int(cv["k"]), set(cv["high_priority_severities"])
    problems = list(check(root, milestone)["problems"])
    try:
        rounds = load_rounds(root, milestone)
    except RoundError as e:
        rounds, problems = [], problems + [str(e)]
    findings, fbad = load_findings(root, milestone, policy)
    problems += fbad
    sev = {f["id"]: f.get("severity") for f in findings}
    seen: set = set()
    streak = counted = 0
    per = []
    for n, _p, r in rounds:
        a = r.get("auditor") or {}
        claims = a.get("counts_toward_convergence") is True
        ok, why_not = qualifies(r, seen, policy)
        is_counted = claims and ok
        listed = list(r.get("findings") or [])
        unknown = sorted(f for f in listed if f not in sev)
        highs = sorted(f for f in listed if f in sev and sev[f] in high)
        clean = not unknown and not highs
        seen.add(a.get("session"))
        if not clean:
            streak = 0
        elif is_counted:
            streak += 1
        counted += int(is_counted)
        if is_counted:
            why = "counted"
        elif not ok:
            why = f"not counted: {why_not}"
        else:
            why = "not counted: its counts_toward_convergence is false"
        if highs:
            why += f"; not clean: high-priority finding(s) {', '.join(highs)}"
        if unknown:
            why += f"; not clean: finding(s) {', '.join(unknown)} not in {findings_rel(milestone, policy)}"
        if not clean:
            why += "; the streak resets"
        per.append({"round": n, "family": a.get("family"), "dry_run": r.get("dry_run") is True,
                    "counted": is_counted, "clean": clean, "why": why})
    open_high = sorted(f["id"] for f in findings if f.get("severity") in high and f.get("status") == "open")
    converged = not problems and streak >= k and not open_high
    if converged:
        why = f"converged: {streak} consecutive counted clean rounds (k = {k}) and no open high-priority finding"
    else:
        parts = []
        if problems:
            parts.append(f"the rounds are invalid ({len(problems)} problem(s))")
        if streak < k:
            parts.append(f"the streak is {streak} counted clean round(s), k is {k}")
        if not counted:
            parts.append("no round counts: none is a qualifying round from another model family (Q9: same-family "
                         "and dry-run rounds are labelled and never counted)" if rounds else "no round exists")
        if open_high:
            parts.append(f"open high-priority finding(s): {', '.join(open_high)}")
        why = "not converged: " + "; ".join(parts)
    return {"status_version": STATUS_VERSION, "milestone": milestone, "k": k, "converged": converged,
            "streak": streak, "counted": counted, "rounds": per, "open_high": open_high, "problems": problems,
            "findings_file": findings_rel(milestone, policy),
            "policy": {"path": rel_or_abs(pp, root), "sha256": file_sha256(pp)}, "why": why}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit converge", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", help="default: <root>/results/<M>/audit_status.json")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 0 iff the file regenerates byte for byte")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    out = Path(a.out) if a.out else root / "results" / a.milestone / "audit_status.json"
    try:
        text = dumps(compute(root, a.milestone))
    except RoundError as e:
        print(f"converge: {e}", file=sys.stderr)
        return 2
    if a.check:
        if not out.is_file():
            print(f"converge: {out} does not exist", file=sys.stderr)
            return 1
        if out.read_text(encoding="utf-8") != text:
            print(f"converge: {out} differs from the regeneration", file=sys.stderr)
            return 1
        print(f"{a.milestone}: audit status regenerates byte for byte")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"{a.milestone}: {json.loads(text)['why']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
