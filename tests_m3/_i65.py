"""I65 instrument (= I33b: the O12 intent contract on M2's window view), fixed at the I65 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_o12.py, rules O1-O9. This module writes O5 and O7 out a second time,
independently of holon/, so that the tests can decide what holon must mark and what G10 must say on a milestone whose
records live in two directories. It takes I64's instrument (tests_m3/_i64.py, fixed at the I64 prereg) for everything
I65 leaves as it was: contract validity (K1, K9), the registry hash (K2), the derived law (K3) and a contract's state
(K5). It reads contract files, law files, result records and facts documents as JSON; nothing here imports holon/.

  record_dirs(milestone, root)       O5: the milestone's record directories, [(key, path)]: "" for results/<M>, and
                                     "extracted_m1" for results/<M>/extracted_m1 when it is a directory
  locate(milestone, lid, root)       O5: the keys of the directories that hold a record of the law
  ambiguous(milestone, root)         O5: the scope laws of the milestone's intended contracts that two directories hold
  licensed(milestone, lid, c, root)  O5: the record path (relative to results/<M>) the contract may mark, or None
  expected_marks(milestone, root)    O5: {record path: {"contract", "l_weak"}} for the records the contracts must mark
  contracts_doc(milestone, root)     O5: results/<M>/contracts.json as the last step must write it
  marks(milestone, root)             O7: the marks the records of both directories carry
  g10(milestone, root)               O7: (passed, [reasons]) as G10 must decide it

A record path is the record's file stem relative to results/<M>: "L_x" for results/<M>/L_x.json and
"extracted_m1/L_x" for results/<M>/extracted_m1/L_x.json. Like I64's, this module leaves the statement_hash check of a
proved contract to holon.
"""
from __future__ import annotations

from pathlib import Path

import tests_m3._i64 as I64

ROOT = Path(__file__).resolve().parents[1]
VIEW = "extracted_m1"
MARK = "intended_bounded"
load, sha256_bytes = I64.load, I64.sha256_bytes
problems, content_sha256, derived_law, states = I64.problems, I64.content_sha256, I64.derived_law, I64.states
contract_docs, milestone_of, scope_of = I64.contract_docs, I64.milestone_of, I64.scope_of
NOT_APPLICABLE, NA_WHY = I64.NOT_APPLICABLE, I64.NA_WHY


# ---------------------------------------------------------------------------------------------------- O5
def record_dirs(milestone: str, root: Path = ROOT) -> list:
    """[(key, directory)]: results/<M> ("") and, when it is a directory, results/<M>/extracted_m1 ("extracted_m1")."""
    base = Path(root) / "results" / milestone
    out = [("", base)]
    if (base / VIEW).is_dir():
        out.append((VIEW, base / VIEW))
    return out


def rel(key: str, lid: str) -> str:
    return f"{key}/{lid}" if key else lid


def locate(milestone: str, lid: str, root: Path = ROOT) -> list:
    """The keys of the record directories holding results/<...>/<lid>.json, in record_dirs order."""
    return [k for k, d in record_dirs(milestone, root) if (d / f"{lid}.json").is_file()]


def ambiguous(milestone: str, root: Path = ROOT) -> list:
    """The sorted scope laws of the milestone's intended contracts (valid or not) that both directories hold."""
    lids = set()
    for _, c in contract_docs(root):
        if milestone_of(c) == milestone:
            lids |= set(scope_of(c))
    return sorted(lid for lid in lids if len(locate(milestone, lid, root)) > 1)


def _record(path: Path):
    try:
        r = load(path) if path.is_file() else None
    except ValueError:
        return None
    return r if isinstance(r, dict) else None


def licensed(milestone: str, lid: str, c: dict, root: Path = ROOT) -> str | None:
    """The record path of lid that contract c may mark: the law's one record (none, or an ambiguous law, licenses
    nothing), when it is REFUTED and its facts_sha256 is the sha256 of c's facts file now."""
    keys = locate(milestone, lid, root)
    if len(keys) != 1:
        return None
    d = dict(record_dirs(milestone, root))[keys[0]]
    r = _record(d / f"{lid}.json")
    try:
        now = sha256_bytes((Path(root) / c["facts"]).read_bytes())
    except (OSError, KeyError, TypeError):
        return None
    if r is None or r.get("status") != "REFUTED" or r.get("facts_sha256") != now:
        return None
    return rel(keys[0], lid)


def _proved(milestone: str, root: Path) -> list:
    """[(state row, contract)] of the proved intended contracts of the milestone, by id."""
    docs = {c.get("id"): c for _, c in contract_docs(root) if isinstance(c, dict)}
    return [(s, docs[s["id"]]) for s in states(milestone, root)
            if s["kind"] == "intended" and s["state"] == "proved" and s["id"] in docs]


def expected_marks(milestone: str, root: Path = ROOT) -> dict:
    """{record path: {"contract", "l_weak"}}: every record a proved contract licenses, naming the least id among the
    proved contracts that license it."""
    root = Path(root)
    out = {}
    for s, c in _proved(milestone, root):   # by id: the first to claim a record has the least id
        for lid in s["scope"]:
            r = licensed(milestone, lid, c, root)
            if r is not None and r not in out:
                out[r] = {"contract": s["id"], "l_weak": f"L_contract_{s['id']}"}
    return dict(sorted(out.items()))


def contracts_doc(milestone: str, root: Path = ROOT):
    """results/<M>/contracts.json as the last step must write it (None when the milestone has no contract): I64's
    document, where marked lists, under every proved intended contract, the law ids of its scope whose record it
    licenses (O5), and [] under every other contract."""
    root = Path(root)
    rows = states(milestone, root)
    if not rows:
        return None
    docs = {c.get("id"): c for _, c in contract_docs(root) if isinstance(c, dict)}
    for s in rows:
        s["marked"] = (sorted(lid for lid in s["scope"] if licensed(milestone, lid, docs[s["id"]], root) is not None)
                       if s["kind"] == "intended" and s["state"] == "proved" else [])
    return {"contracts_version": I64.STATUS_VERSION, "milestone": milestone, "contracts": rows}


# ---------------------------------------------------------------------------------------------------- O7
def marks(milestone: str, root: Path = ROOT) -> dict:
    """{record path: {"filter_bin", "contract", "l_weak"}} for every record of both directories whose filter_bin is
    intended_bounded or that has the field intended (so a half-made mark shows)."""
    out = {}
    for key, d in record_dirs(milestone, root):
        for p in sorted(d.glob("L*.json")):
            r = _record(p)
            if r is not None and (r.get("filter_bin") == MARK or "intended" in r):
                i = r.get("intended") if isinstance(r.get("intended"), dict) else {}
                out[rel(key, p.stem)] = {"filter_bin": r.get("filter_bin"), "contract": i.get("contract"),
                                         "l_weak": i.get("l_weak")}
    return out


def g10(milestone: str, root: Path = ROOT) -> tuple:
    """(passed, reasons) for G10 on the milestone ((None, [reason]) on M0 and M1): I64's checks of the registry, the
    contract files and their states (tests_m3/_i64.g10, whose own mark comparison over results/<M> alone is replaced
    here), every record of both directories a JSON object, no ambiguous scope law, and the marks of both directories
    exactly the licensed ones."""
    root = Path(root)
    if milestone in NOT_APPLICABLE:
        return None, [NA_WHY.format(m=milestone)]
    _, base = I64.g10(milestone, root)
    reasons = [r for r in base if not _is_mark_reason(r)]
    for key, d in record_dirs(milestone, root):
        if not key:
            continue   # I64.g10 read results/<M> itself
        for p in sorted(d.glob("L*.json")):
            if _record(p) is None:
                reasons.append(f"{rel(key, p.stem)}: the record is not a JSON object")
    for lid in ambiguous(milestone, root):
        reasons.append(f"{lid}: a scope law with a record in more than one of results/{milestone} and "
                       f"results/{milestone}/{VIEW}")
    want = {k: {"filter_bin": MARK, **v} for k, v in expected_marks(milestone, root).items()}
    have = marks(milestone, root)
    for r in sorted(set(have) | set(want)):
        if have.get(r) != want.get(r):
            reasons.append(f"{r}: the record's mark {have.get(r)} is not the contracts' {want.get(r)}")
    return not reasons, reasons


def _is_mark_reason(r: str) -> bool:
    """I64.g10's own mark comparison (over results/<M> alone), which g10 replaces by the one over both directories."""
    return ": the record's mark " in r and " is not the contracts' " in r
