"""Rule-gap records and the L7 admission rule (whitepaper L7: "every finding outside the rules files a rule-gap record;
a new rule needs at least two instances and a basis argument"; BUILD_PLAN I45 adds human approval; the contract is the
docstring of tests_m3/test_audit_loop.py, "Rule gaps and the L7 admission rule").

    python -m holon audit gaps [--root R] [--json]

audit/rule_gaps.jsonl holds one JSON object per line, valid against spec/schemas/rule_gap.schema.json:
  {"kind": "gap", "id": "RG-<M>-<nn>", "milestone", "finding", "title", "outside", "candidate"}
  {"kind": "candidate", "name", "instances": [gap ids], "basis": {"argument", "obligation"},
   "approval": {"by", "signature"} | null}
A candidate is admitted iff
  (a) its instances are at least the policy's min_instances gap lines naming it, every listed id is such a line, each
      names a finding of its milestone's findings file (audit/<M>_findings.jsonl; M0 and M1: audit/findings.jsonl),
      and together they name at least two distinct findings;
  (b) its basis has a non-empty argument and a non-empty obligation;
  (c) human approval: approval.signature verifies over the candidate line without its approval field
      (holon.statement_diff.signed_payload's canonical JSON) against a key the human froze
      (holon.statement_diff.verify_signature). Agents never freeze a key (AGENTS.md rule 1), so no agent can approve.
The policy is spec/M3/lib/audit_loop.json of the root (else this repository's). Exit 0 iff the file is valid, whatever
the verdicts; a missing file is invalid. Nothing here names a law or a target.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .rounds import DEFAULT_POLICY, findings_rel

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "spec" / "schemas" / "rule_gap.schema.json"
GAPS = Path("audit") / "rule_gaps.jsonl"
_GAP_ID = re.compile(r"^RG-(M[0-9]+)-[0-9]{2,}$")


def _policy(root: Path) -> dict:
    for p in (Path(root) / DEFAULT_POLICY, ROOT / DEFAULT_POLICY):
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"no audit policy at {DEFAULT_POLICY.as_posix()}")


def _findings(root: Path, milestone: str, policy: dict, cache: dict) -> set:
    if milestone not in cache:
        p = Path(root) / findings_rel(milestone, policy)
        ids = set()
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    f = json.loads(line) if line.strip() else None
                except ValueError:
                    continue
                if isinstance(f, dict) and isinstance(f.get("id"), str):
                    ids.add(f["id"])
        cache[milestone] = ids
    return cache[milestone]


def approval_verifies(cand: dict, root: Path) -> tuple[bool, str]:
    """(c): the human's signature over the candidate line without its approval field, against a frozen key."""
    from ..statement_diff import verify_signature
    ap = cand.get("approval")
    if not isinstance(ap, dict) or not isinstance(ap.get("signature"), str) or not ap["signature"].strip():
        return False, "no human approval (a signature by a key the human froze)"
    entry = {k: v for k, v in cand.items() if k != "approval"}
    entry["signature"] = ap["signature"]
    return verify_signature(entry, Path(root))


def check(root: Path) -> dict:
    from ..schema import errors
    root = Path(root)
    policy = _policy(root)
    need = int((policy.get("rule_gaps") or {}).get("min_instances", 2))
    p = root / GAPS
    problems: list[str] = []
    lines: list[dict] = []
    if not p.is_file():
        return {"valid": False, "problems": [f"{GAPS.as_posix()} does not exist"], "gaps": 0, "candidates": {}}
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    for n, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            x = json.loads(raw)
        except ValueError as e:
            problems.append(f"line {n}: not JSON ({e})")
            continue
        errs = errors(x, schema)
        if errs:
            problems.append(f"line {n}: " + "; ".join(errs))
            continue
        lines.append(x)
    gaps: dict = {}
    cands: dict = {}
    for x in lines:
        if x["kind"] == "gap":
            m = _GAP_ID.match(x["id"])
            if x["id"] in gaps:
                problems.append(f"{x['id']}: listed twice")
            elif not m or m.group(1) != x["milestone"]:
                problems.append(f"{x['id']}: the id does not name its milestone {x['milestone']}")
            gaps[x["id"]] = x
        else:
            if x["name"] in cands:
                problems.append(f"candidate {x['name']}: listed twice")
            cands[x["name"]] = x
    cache: dict = {}
    verdicts = {}
    for name, c in sorted(cands.items()):
        fails, why = [], []
        inst = list(dict.fromkeys(c.get("instances") or []))
        good = []
        for i in inst:
            g = gaps.get(i)
            if g is None:
                why.append(f"{i} is no gap line")
            elif g.get("candidate") != name:
                why.append(f"{i} names another candidate ({g.get('candidate')})")
            elif g["finding"] not in _findings(root, g["milestone"], policy, cache):
                why.append(f"{i}'s finding {g['finding']} is not in {findings_rel(g['milestone'], policy)}")
            else:
                good.append(g)
        distinct = {(g["milestone"], g["finding"]) for g in good}
        if len(good) != len(inst) or len(good) < need or len(distinct) < 2:
            fails.append("a")
            why.append(f"(a) {len(good)} valid instance(s) on {len(distinct)} distinct finding(s); L7 needs at least "
                       f"{need} instances on at least two findings")
        b = c.get("basis") or {}
        if not (str(b.get("argument") or "").strip() and str(b.get("obligation") or "").strip()):
            fails.append("b")
            why.append("(b) no basis argument and obligation")
        ok, vwhy = approval_verifies(c, root)
        if not ok:
            fails.append("c")
            why.append(f"(c) {vwhy}")
        verdicts[name] = {"admitted": not fails, "fails": fails,
                          "why": "admitted: two or more instances, a basis argument and the human's approval"
                                 if not fails else "refused: " + "; ".join(why)}
    return {"valid": not problems, "problems": problems, "gaps": len(gaps), "candidates": verdicts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit gaps", description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rep = check(Path(a.root).resolve())
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        for p in rep["problems"]:
            print(f"  {p}")
        for name, v in rep["candidates"].items():
            print(f"  {name}: {v['why']}")
        adm = sorted(n for n, v in rep["candidates"].items() if v["admitted"])
        print(f"{rep['gaps']} rule-gap record(s), {len(rep['candidates'])} candidate(s), admitted: "
              f"{', '.join(adm) if adm else 'none'}" + ("" if rep["valid"] else "; INVALID"))
    return 0 if rep["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
