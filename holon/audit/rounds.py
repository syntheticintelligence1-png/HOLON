"""Audit rounds (whitepaper §9.5; BUILD_PLAN I45 and row I87; the contract is the docstring of
tests_m3/test_audit_loop.py, "Rounds").

    python -m holon audit round --milestone M [--root R] [--json]

A round of milestone M is audit/rounds/<M>/round<n>.json, valid against spec/schemas/audit_round.schema.json: I5's
format, which I87 extends with optional fields only (round_version, dry_run, packet, and per attack auditor_type and
run), so every earlier round stays valid. A round's auditor types are the auditor_type of its attacks that ran.

  RD1  auditor.family is "same" or "different" (relative to the builders' family); a same-family round and a dry run
       have counts_toward_convergence false (HUMAN_ANSWERS Q9)
  RD2  counts_toward_convergence is true only for a round that qualifies (CV1, holon.audit.converge)
  RD3  the rounds of M are numbered 1..n without a gap; each round's findings are exactly the union of its attacks'
  RD4  every line of the milestone's findings file is a JSON object with a string id that no earlier line has, a
       severity in high, medium, low and a status in open, fixed, wontfix, duplicate (I5's line rule,
       holon.audit.status); CV2 and CV4 read severities and statuses, so a round whose author spells them otherwise
       (an auditor of another family, say "critical" or "Open") is refused here instead of counting as clean
  RD5  every driver record in a round's directory (a1.json of `holon audit mutation`, a2.json of `holon audit
       hostile-input`) is valid against spec/schemas/audit_a1|a2.schema.json, names the round's milestone, number and
       target commit, lists each of its mutants or cases once in its summary, and is cited by an attack of the
       round's file that ran, of the record's auditor type and category; an attack citing one that is missing fails

Schemas are read from this repository; rounds and the policy from the root. The policy is spec/<M>/lib/audit_loop.json
of the root, or I87's spec/M3/lib/audit_loop.json (the root's, else this repository's) for a milestone without one.
Exit 0 iff every round of M is valid; a milestone with no round is valid. Nothing here names a law or a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from .status import SEVERITIES, STATUSES

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "spec" / "schemas" / "audit_round.schema.json"
ROUND_VERSION = "holon-audit-round/0.2"
DEFAULT_POLICY = Path("spec") / "M3" / "lib" / "audit_loop.json"
_ROUND_FILE = re.compile(r"^round([1-9][0-9]*)\.json$")


class RoundError(RuntimeError):
    pass


def load_rulings(root: Path, milestone: str) -> dict:
    """The milestone's audit rulings, spec/<M>/lib/audit_rulings.json of the root, or {} without one. Its
    same_family_admitted.ruling names the human's ruling (HUMAN_ANSWERS Q9b) under which a same-family round may count."""
    p = Path(root) / "spec" / milestone / "lib" / "audit_rulings.json"
    if not p.is_file():
        return {}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise RoundError(f"{rel_or_abs(p, Path(root))}: {e}") from None
    return doc if isinstance(doc, dict) else {}


def admitted_same_family(r: dict, rulings: dict | None) -> str | None:
    """The ruling that admits a same-family round toward convergence, or None: the round's auditor.family is "same"
    and either its auditor.ruling is exactly the milestone's same_family_admitted.ruling (HUMAN_ANSWERS Q9b), or the
    round's number is in same_family_admitted.rounds_before_field (rounds the ruling covers that were written before
    auditor.ruling existed; their files stay as their auditors wrote them). The round keeps its family; every other
    CV1 condition still applies."""
    adm = (rulings or {}).get("same_family_admitted") or {}
    want, a = adm.get("ruling"), r.get("auditor") or {}
    if not (isinstance(want, str) and want and a.get("family") == "same"):
        return None
    listed = adm.get("rounds_before_field") or []
    return want if a.get("ruling") == want or (isinstance(r.get("round"), int) and r["round"] in listed) else None


def policy_path(root: Path, milestone: str) -> Path:
    """The milestone's policy file: spec/<M>/lib/audit_loop.json of the root, else I87's (root's, else ours)."""
    root = Path(root)
    for p in (root / "spec" / milestone / "lib" / "audit_loop.json", root / DEFAULT_POLICY, ROOT / DEFAULT_POLICY):
        if p.is_file():
            return p
    raise RoundError(f"no audit policy: neither spec/{milestone}/lib/audit_loop.json nor {DEFAULT_POLICY.as_posix()}")


def load_policy(root: Path, milestone: str) -> tuple[dict, Path]:
    p = policy_path(root, milestone)
    return json.loads(p.read_text(encoding="utf-8")), p


def rel_or_abs(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        try:
            return Path(p).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            return str(p)


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def findings_rel(milestone: str, policy: dict) -> str:
    """audit/<M>_findings.jsonl, or the policy's own name for the milestone (M0 and M1: audit/findings.jsonl)."""
    ff = (policy.get("convergence") or {}).get("findings_file") or {}
    return ff.get(milestone) or str(ff.get("default") or "audit/<M>_findings.jsonl").replace("<M>", milestone)


def load_findings(root: Path, milestone: str, policy: dict) -> tuple[list[dict], list[str]]:
    """(findings, problems): one JSON object per line of the milestone's findings file (none when it is missing). A
    line that breaks RD4 is a problem and is left out of the findings."""
    p = Path(root) / findings_rel(milestone, policy)
    if not p.is_file():
        return [], []
    out, bad, ids = [], [], set()
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{findings_rel(milestone, policy)} line {n}"
        try:
            f = json.loads(line)
        except ValueError as e:
            bad.append(f"{where}: not JSON ({e})")
            continue
        if not isinstance(f, dict) or not isinstance(f.get("id"), str):
            bad.append(f"{where}: not a finding with an id")
            continue
        if f["id"] in ids:
            bad.append(f"{where}: {f['id']} is an earlier line's id")
            continue
        ids.add(f["id"])
        if f.get("severity") not in SEVERITIES or f.get("status") not in STATUSES:
            bad.append(f"{where}: {f['id']} has severity {f.get('severity')!r} and status {f.get('status')!r}; it "
                       f"needs a severity in {', '.join(SEVERITIES)} and a status in {', '.join(STATUSES)}")
            continue
        out.append(f)
    return out, bad


def load_rounds(root: Path, milestone: str) -> list[tuple[int, Path, dict]]:
    """[(n, path, round)] of audit/rounds/<M>/round<n>.json, by n. A file that is not a JSON object raises."""
    d = Path(root) / "audit" / "rounds" / milestone
    out = []
    if d.is_dir():
        for p in sorted(d.iterdir()):
            m = _ROUND_FILE.match(p.name)
            if m and p.is_file():
                try:
                    r = json.loads(p.read_text(encoding="utf-8"))
                except ValueError as e:
                    raise RoundError(f"{p.name}: not JSON ({e})") from None
                if not isinstance(r, dict):
                    raise RoundError(f"{p.name}: not a JSON object")
                out.append((int(m.group(1)), p, r))
    return sorted(out, key=lambda x: x[0])


def round_types(r: dict) -> set:
    """The auditor types of the attacks that ran (an attack with run false was listed, not run)."""
    return {a["auditor_type"] for a in r.get("attacks") or []
            if isinstance(a, dict) and a.get("auditor_type") and a.get("run", True) is not False}


def qualifies(r: dict, earlier_sessions: set, policy: dict, rulings: dict | None = None) -> tuple[bool, str]:
    """CV1 without the round's own claim: (qualifies, why not). A same-family round that cites the milestone's
    admitting ruling (admitted_same_family; HUMAN_ANSWERS Q9b) passes the family condition, and only that one."""
    cv = policy["convergence"]
    a = r.get("auditor") or {}
    if a.get("family") != cv["counted_family"] and not admitted_same_family(r, rulings):
        return False, f"family {a.get('family')!r}: only a {cv['counted_family']!r}-family round counts (Q9)"
    if r.get("dry_run") is True:
        return False, "a dry run"
    missing = sorted(set(cv["auditor_types"]) - round_types(r))
    if missing:
        return False, f"auditor types {', '.join(missing)} did not run"
    if a.get("session") in earlier_sessions:
        return False, "its auditor session is an earlier round's (no fresh context, L19)"
    return True, ""


def schema_errors(r: dict) -> list[str]:
    from ..schema import errors
    return errors(r, json.loads(SCHEMA.read_text(encoding="utf-8")))


# the driver records RD5 checks: a1.json and a2.json holding a1_version and a2_version
DRIVERS = {"a1.json": ("audit_a1.schema.json", "mutations", ("detected", "missed", "incomplete", "refused")),
           "a2.json": ("audit_a2.schema.json", "cases", ("agree", "disagree", "unsupported"))}


def driver_problems(root: Path, milestone: str, n: int, r: dict) -> list[str]:
    """RD5 over the driver records of round n's directory, and the records its attacks cite."""
    from ..schema import errors
    d = Path(root) / "audit" / "rounds" / milestone / f"round{n}"
    rel = f"audit/rounds/{milestone}/round{n}"
    attacks = [a for a in r.get("attacks") or [] if isinstance(a, dict)]
    out = []
    for fname, (schema, items, verdicts) in DRIVERS.items():
        path = f"{rel}/{fname}"
        citing = [a for a in attacks if path in (a.get("evidence") or [])]
        if not (d / fname).is_file():
            out += [f"attack {a.get('id')} cites {path}, which does not exist" for a in citing]
            continue
        try:
            rec = json.loads((d / fname).read_text(encoding="utf-8"))
        except ValueError as e:
            out.append(f"{fname}: not JSON ({e})")
            continue
        if not isinstance(rec, dict) or f"{fname[:2]}_version" not in rec:
            continue    # another instrument's record under that name (I21's M2 a2.json): not a driver record
        errs = errors(rec, json.loads((ROOT / "spec" / "schemas" / schema).read_text(encoding="utf-8")))
        if errs:
            out += [f"{fname}: schema: {e}" for e in errs[:10]]
            continue
        for k, want in (("milestone", milestone), ("round", n), ("target_commit", r.get("target_commit"))):
            if rec.get(k) != want:
                out.append(f"{fname}: its {k} is {rec.get(k)!r}, the round's {want!r}")
        ids = [x.get("id") for x in rec.get(items) or []]
        listed = sorted(i for v in verdicts for i in rec["summary"].get(v) or [])
        if len(set(ids)) != len(ids) or listed != sorted(ids):
            out.append(f"{fname}: its summary does not list each of its {items} once")
        for x in rec.get(items) or []:
            if x.get("id") not in (rec["summary"].get(x.get("verdict")) or []):
                out.append(f"{fname}: {items} {x.get('id')} is {x.get('verdict')!r} but the summary says otherwise")
        want = rec["attack"]
        ok = [a for a in citing if a.get("run", True) is not False and a.get("auditor_type") == want["auditor_type"]
              and a.get("category") == want["category"]]
        if not ok:
            out.append(f"{fname}: no attack that ran with auditor_type {want['auditor_type']} and category "
                       f"{want['category']} cites it in its evidence")
    return out


def check(root: Path, milestone: str) -> dict:
    """{"milestone", "rounds": n, "problems": [..], "policy": rel}: RD1-RD4 and the schema over every round of M."""
    root = Path(root)
    policy, pp = load_policy(root, milestone)
    problems: list[str] = [f"RD4: {b}" for b in load_findings(root, milestone, policy)[1]]
    try:
        rulings = load_rulings(root, milestone)
    except RoundError as e:
        rulings, problems = {}, problems + [str(e)]
    try:
        rounds = load_rounds(root, milestone)
    except RoundError as e:
        return {"milestone": milestone, "rounds": 0, "problems": problems + [str(e)], "policy": rel_or_abs(pp, root)}
    if [n for n, _p, _r in rounds] != list(range(1, len(rounds) + 1)):
        problems.append(f"RD3: rounds numbered {[n for n, _p, _r in rounds]}, not 1..{len(rounds)}")
    seen: set = set()
    for n, p, r in rounds:
        name = f"round{n}"
        problems += [f"{name}: schema: {e}" for e in schema_errors(r)]
        if r.get("round") != n:
            problems.append(f"{name}: its round field is {r.get('round')!r}")
        if r.get("milestone") != milestone:
            problems.append(f"{name}: its milestone field is {r.get('milestone')!r}")
        a = r.get("auditor") or {}
        claims = a.get("counts_toward_convergence") is True
        if a.get("family") not in ("same", "different"):
            problems.append(f"RD1: {name}: auditor.family {a.get('family')!r} is neither 'same' nor 'different'")
        if claims and (r.get("dry_run") is True or (a.get("family") == "same"
                                                    and not admitted_same_family(r, rulings))):
            problems.append(f"RD1: {name}: a {'dry run' if r.get('dry_run') is True else 'same-family round'} "
                            "never counts toward convergence (Q9), unless a same-family round cites the milestone's "
                            "admitting ruling in auditor.ruling (Q9b)")
        ok, why = qualifies(r, seen, policy, rulings)
        if claims and not ok:
            problems.append(f"RD2: {name} claims to count toward convergence but does not qualify: {why}")
        problems += [f"RD5: {name}: {x}" for x in driver_problems(root, milestone, n, r)]
        union = sorted({f for at in r.get("attacks") or [] if isinstance(at, dict) for f in at.get("findings") or []})
        if union != sorted(set(r.get("findings") or [])):
            problems.append(f"RD3: {name}: its findings are not the union of its attacks' findings")
        seen.add(a.get("session"))
    return {"milestone": milestone, "rounds": len(rounds), "problems": problems, "policy": rel_or_abs(pp, root)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit round", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        rep = check(Path(a.root).resolve(), a.milestone)
    except RoundError as e:
        print(f"round: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
    else:
        for p in rep["problems"]:
            print(f"  {p}")
        print(f"{a.milestone}: {rep['rounds']} round(s), " + ("ROUNDS OK" if not rep["problems"] else
                                                               f"{len(rep['problems'])} problem(s)"))
    return 0 if not rep["problems"] else 1


if __name__ == "__main__":
    sys.exit(main())
