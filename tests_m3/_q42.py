"""HUMAN_ANSWERS Q42's reading of the L7 admission rule, for tests_m3/test_audit_q42.py and the amended R7 of
tests_m3/test_audit_loop.py (spec/M3/amendments/I87.jsonl). Written without holon's audit code.

I87's instrument (tests_m3/_i87.py, byte-identical to its prereg) gives each candidate's (a), (b) and (c). Under Q42
(the human, 2026-11-11: a plain-language approval counts, no signature needed) a candidate whose line carries no
signature also meets (c) iff three things hold:
  - the root's spec/M3/lib/rule_approvals.json names the ruling HUMAN_ANSWERS Q42, and that row of the root's
    docs/HUMAN_ANSWERS.md is the human's own: its first cell holds "(the human, ";
  - the sidecar has an entry naming the candidate whose payload_sha256 is the sha256 of I87's payload of the line
    (the line without its approval field, as canonical JSON);
  - the entry's words name the candidate, and the human's own row the entry cites quotes them. The entry cites its
    row in "answer" ("HUMAN_ANSWERS Q<n>"), or else the ruling's row.
A line that carries a signature is I87's: the signature must verify. Nothing else about the rule changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests_m3 import _i87 as I

ROOT = Path(__file__).resolve().parents[1]
RULING = "HUMAN_ANSWERS Q42"
SIDECAR = "spec/M3/lib/rule_approvals.json"
ANSWERS = "docs/HUMAN_ANSWERS.md"


def approvals(root: Path = ROOT) -> dict:
    p = Path(root) / SIDECAR
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def human_row(root: Path, ruling: str) -> str | None:
    """The row a ruling "HUMAN_ANSWERS Q<n>" names, when its first cell marks it as the human's own."""
    if not isinstance(ruling, str) or not ruling.startswith("HUMAN_ANSWERS Q"):
        return None
    q = ruling[len("HUMAN_ANSWERS "):]
    p = Path(root) / ANSWERS
    if not p.is_file():
        return None
    for line in p.read_text(encoding="utf-8").split("\n"):
        if line.startswith("| **" + q + "** "):
            return line if "(the human, " in line.split(" | ")[0] else None
    return None


def payload_sha256(cand: dict) -> str:
    return hashlib.sha256(I.payload(cand)).hexdigest()


def plainly_approved(cand: dict, root: Path) -> bool:
    side = approvals(root)
    if side.get("ruling") != RULING or human_row(root, RULING) is None:
        return False
    for a in side.get("approvals") or []:
        if not (isinstance(a, dict) and a.get("candidate") == cand.get("name")
                and a.get("payload_sha256") == payload_sha256(cand)):
            continue
        row = human_row(root, a.get("answer") or RULING)
        w = a.get("words")
        return bool(row is not None and isinstance(w, str) and w.strip() and w in row and cand["name"] in w)
    return False


def signed(cand: dict) -> bool:
    ap = cand.get("approval")
    return isinstance(ap, dict) and isinstance(ap.get("signature"), str) and bool(ap["signature"].strip())


def admission(lines: list, findings_by_m: dict, frozen_key: bytes | None, root: Path) -> dict:
    """{candidate name: {"admitted", "fails"}}: I87's verdicts, with (c) met by a plain approval of the root."""
    out = I.admission(lines, findings_by_m, frozen_key)
    for c in (x for x in lines if x.get("kind") == "candidate"):
        v = out[c["name"]]
        if "c" in v["fails"] and not signed(c) and plainly_approved(c, root):
            fails = [f for f in v["fails"] if f != "c"]
            out[c["name"]] = {"admitted": not fails, "fails": fails}
    return out


def findings_by_milestone(root: Path, lines: list, pol: dict) -> dict:
    """{milestone: finding ids} for the milestones the gap lines name, from the policy's findings files."""
    files = (pol.get("convergence") or {}).get("findings_file") or {}
    out = {}
    for m in sorted({x.get("milestone") for x in lines if x.get("kind") == "gap"}):
        rel = files.get(m) or str(files.get("default", "audit/<M>_findings.jsonl")).replace("<M>", m)
        p = Path(root) / rel
        ids = set()
        if p.is_file():
            for raw in p.read_text(encoding="utf-8").splitlines():
                if raw.strip():
                    f = json.loads(raw)
                    if isinstance(f, dict) and isinstance(f.get("id"), str):
                        ids.add(f["id"])
        out[m] = ids
    return out


def frozen_key(root: Path) -> bytes | None:
    """keys/human.asc's bytes when FROZEN.sha256 lists it with its sha256 (as I87's make_frozen_root writes)."""
    k, m = Path(root) / "keys" / "human.asc", Path(root) / "FROZEN.sha256"
    if not (k.is_file() and m.is_file()):
        return None
    data = k.read_bytes()
    return data if f"{hashlib.sha256(data).hexdigest()}  keys/human.asc" in m.read_text().splitlines() else None
