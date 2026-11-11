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
      (holon.statement_diff.verify_signature). Agents never freeze a key (AGENTS.md rule 1), so no agent can sign.
      Without a signature, (c) holds under HUMAN_ANSWERS Q42 (the human, 2026-11-11: a plain-language approval
      counts, no signature needed) iff the root's spec/M3/lib/rule_approvals.json names exactly that ruling, whose
      row of the root's docs/HUMAN_ANSWERS.md is marked as the human's own, and has an entry naming the candidate
      whose payload_sha256 is the sha256 of that same payload and whose words name the candidate and are quoted by
      the human's own row the entry cites ("answer", by default the ruling's) (plain_approval). An edit to the line
      voids the approval. A signature, when the line carries one, must verify.
The policy is spec/M3/lib/audit_loop.json of the root (else this repository's). Exit 0 iff the file is valid, whatever
the verdicts; a missing file is invalid. Nothing here names a law or a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from .rounds import DEFAULT_POLICY, findings_rel

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "spec" / "schemas" / "rule_gap.schema.json"
GAPS = Path("audit") / "rule_gaps.jsonl"
APPROVALS = Path("spec") / "M3" / "lib" / "rule_approvals.json"
ANSWERS = Path("docs") / "HUMAN_ANSWERS.md"
PLAIN_RULING = "HUMAN_ANSWERS Q42"
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


def _ruling_row(root: Path, ruling: str) -> str | None:
    """The row of the root's docs/HUMAN_ANSWERS.md that a ruling "HUMAN_ANSWERS Q<n>" names, when the row is marked
    as the human's own ("(the human, " in its first cell); else None."""
    m = re.fullmatch(r"HUMAN_ANSWERS (Q[0-9]+[a-z]?)", ruling or "")
    p = Path(root) / ANSWERS
    if not m or not p.is_file():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"| **{m.group(1)}** "):
            first = line.split(" | ", 1)[0]
            return line if "(the human, " in first else None
    return None


def plain_approval(cand: dict, root: Path) -> tuple[bool, str]:
    """(c) under HUMAN_ANSWERS Q42: the human's plain-language approval of exactly this line, recorded in the root's
    spec/M3/lib/rule_approvals.json by the sha256 of the line without its approval field."""
    from ..statement_diff import signed_payload
    p = Path(root) / APPROVALS
    if not p.is_file():
        return False, f"no {APPROVALS.as_posix()}"
    try:
        side = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        return False, f"{APPROVALS.as_posix()} is not JSON ({e})"
    ruling = side.get("ruling") if isinstance(side, dict) else None
    entries = [a for a in (side.get("approvals") or []) if isinstance(a, dict) and a.get("candidate") == cand.get("name")] \
        if isinstance(side, dict) and isinstance(side.get("approvals"), list) else []
    if not entries:
        return False, f"{APPROVALS.as_posix()} records no approval of {cand.get('name')}"
    payload = hashlib.sha256(signed_payload({k: v for k, v in cand.items() if k != "approval"})).hexdigest()
    hit = [a for a in entries if a.get("payload_sha256") == payload]
    if not hit:
        return False, (f"the recorded approval of {cand.get('name')} covers another line (payload sha256 "
                       f"{str(entries[0].get('payload_sha256'))[:12]}..., the line's is {payload[:12]}...): an edit "
                       "voids the approval")
    if ruling != PLAIN_RULING or _ruling_row(root, ruling) is None:
        return False, (f"the sidecar's ruling is {ruling!r}, not {PLAIN_RULING} as a row of {ANSWERS.as_posix()} "
                       "marked as the human's own")
    answer = hit[0].get("answer") or ruling
    row = _ruling_row(root, answer)
    if row is None:
        return False, f"the approval's answer {answer!r} is no row of {ANSWERS.as_posix()} marked as the human's own"
    words = hit[0].get("words")
    if not isinstance(words, str) or not words.strip() or words not in row or str(cand.get("name")) not in words:
        return False, f"the {answer} row does not quote approval words that name {cand.get('name')}"
    return True, (f"a plain-language approval of this line under {ruling}" + (f" ({answer})" if answer != ruling else "")
                  + ", with no signature")


def approval_verifies(cand: dict, root: Path) -> tuple[bool, str]:
    """(c): the human's signature over the candidate line without its approval field, against a frozen key; or,
    without a signature, the human's plain-language approval of that line (plain_approval, HUMAN_ANSWERS Q42)."""
    from ..statement_diff import verify_signature
    ap = cand.get("approval")
    if isinstance(ap, dict) and isinstance(ap.get("signature"), str) and ap["signature"].strip():
        entry = {k: v for k, v in cand.items() if k != "approval"}
        entry["signature"] = ap["signature"]
        return verify_signature(entry, Path(root))
    ok, why = plain_approval(cand, root)
    if ok:
        return True, why
    return False, ("no human approval (a signature by a key the human froze, or a plain-language approval of this "
                   f"line under HUMAN_ANSWERS Q42: {why})")


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
                          "why": f"admitted: two or more instances, a basis argument and the human's approval: {vwhy}"
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
