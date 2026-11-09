"""HUMAN_ANSWERS Q9b's reading of the audit loop, for tests_m3/test_audit_q9b.py and the amended R2 of
tests_m3/test_audit_loop.py (spec/M3/amendments/I87.jsonl). Written without holon's audit code.

I87's instrument (tests_m3/_i87.py, byte-identical to its prereg) read on rounds in which every same-family round
whose auditor.ruling is exactly the admitting ruling of the milestone's spec/<M>/lib/audit_rulings.json
(same_family_admitted.ruling) reads as a round of the counted family. Nothing else about the round changes, so every
other CV1 condition (not a dry run, A1-A4 each ran, a fresh session) and RD1-RD3, CV2-CV4 are I87's own.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from tests_m3 import _i87 as I

ROOT = Path(__file__).resolve().parents[1]
RULING = "HUMAN_ANSWERS Q9b"


def rulings(root: Path = ROOT, m: str = "M3") -> dict:
    p = Path(root) / "spec" / m / "lib" / "audit_rulings.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def admitted(rnd: dict, rul: dict) -> bool:
    want = ((rul or {}).get("same_family_admitted") or {}).get("ruling")
    a = rnd.get("auditor") or {}
    return bool(want) and a.get("family") == "same" and a.get("ruling") == want


def converge(rounds: list, findings: list, pol: dict, rul: dict) -> dict:
    fam = pol["convergence"]["counted_family"]
    mapped = []
    for r in rounds:
        if admitted(r, rul):
            r = copy.deepcopy(r)
            r["auditor"]["family"] = fam
        mapped.append(r)
    return I.converge(mapped, findings, pol)


def q9b_round(n: int, m: str, session: str, counts: bool = True, *, ruling: str | None = RULING, **kw) -> dict:
    """A synthetic same-family round that cites `ruling` (none when ruling is None)."""
    r = I.make_round(n, m, session, "same", counts, **kw)
    if ruling is not None:
        r["auditor"]["ruling"] = ruling
    return r


def fixtures(m: str = "M9") -> list[tuple[str, list, list]]:
    """(name, rounds, findings): the Q9b scenarios. Expected verdicts come from converge() above."""
    q = lambda n, s, **kw: q9b_round(n, m, s, **kw)                       # noqa: E731
    d = lambda n, s, **kw: I.make_round(n, m, s, "different", True, **kw)  # noqa: E731
    F = lambda i: f"F-{m}-{i:02d}"                                         # noqa: E731
    return [
        ("three clean Q9b rounds converge", [q(1, "s1"), q(2, "s2"), q(3, "s3")], []),
        ("Q9b and different-family rounds count together", [d(1, "s1"), q(2, "s2"), d(3, "s3")], []),
        ("a same-family round without the ruling claiming to count is invalid",
         [q(1, "s1"), q(2, "s2", ruling=None), q(3, "s3")], []),
        ("a same-family round citing another ruling claiming to count is invalid",
         [q(1, "s1"), q(2, "s2", ruling="HUMAN_ANSWERS Q9"), q(3, "s3")], []),
        ("a same-family round without the ruling does not count",
         [q(1, "s1"), q(2, "s2", ruling=None, counts=False), q(3, "s3")], []),
        ("a Q9b round with an earlier round's session claiming to count is invalid",
         [q(1, "s1"), q(2, "s2"), q(3, "s1")], []),
        ("a Q9b dry run claiming to count is invalid", [q(1, "s1", dry=True), q(2, "s2"), q(3, "s3")], []),
        ("a Q9b round without A3 claiming to count is invalid",
         [q(1, "s1"), q(2, "s2", types=("A1", "A2", "A4")), q(3, "s3")], []),
        ("a high finding of a Q9b round resets the streak",
         [q(1, "s1"), q(2, "s2", findings={"vacuity": [F(1)]}), q(3, "s3"), q(4, "s4")],
         [I.finding(F(1), "high", "fixed")]),
        ("an open high finding blocks Q9b convergence", [q(1, "s1"), q(2, "s2"), q(3, "s3")],
         [I.finding(F(1), "high", "open")]),
    ]
