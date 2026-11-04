"""I95's instrument (= I46b; the contract is the docstring of tests_m3/test_blind_rerun_i95.py; the protocol is
spec/M3/lib/blind_rerun_i95.json). It imports nothing from holon/ or tools/. It reuses I82's instrument
(tests_m3/_i82.py: statement keys, tree classes and git reads) and I46's (tests_m3/_i46.py: the transcript projection,
the preregistered reads scorer and the flips). The amended reads scorer is tests_m3/_i46_reads.py. All of them are
fixed at I95's prereg (C_K) and pinned by sha256 in the key's thresholds.

    binding_rows(blind_tree, lead_root, commit, stems) -> [{"document", "blind", "lead", "equal"}]
        the binding row: for each typed document stem, the sha256 of the blind tree's gen/M3/binding/<stem>.json and
        of the lead's committed one at commit (None where a side has no record)
    per_rule(lead_tree, blind_tree, cmp, m) -> {rule: {"lead", "matched", "agree"}}
        the lead's recorded classes per rule; matched = the classes the blind tree also records; agree = matched
        and not among cmp's disagreements of m. A class's rule is the rule of its first law (sorted ids)
    carried(i46_lead, i46_tree, i46_cmp, lead_tree, blind_tree, cmp, m) -> {"i46_disagreements", "now_agree",
        "i46_agreements", "kept"}
        which of I46's disagreeing classes agree in I95's comparison, and which of I46's agreeing classes still agree
        (by statement key; a class that is not matched in I95 neither agrees nor is kept)
    exit_clauses(root, p, cmp, reads_ok_pre, reads_ok_amended, report_ok) -> {"E1".."E5", "E5_pre", "E5_amended",
        "m3_exit", "i95_clause"}
        E2 needs blind_agreement >= 0.90 over at least 40 matched M3 classes. E5 is the preregistered scorer's
        verdict, and E5_amended the amended scorer's
    pack_commit(root, ref) -> the oldest commit of ref's first-parent chain whose tree holds holon/binding.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from tests_m3 import _i46 as I46
from tests_m3 import _i82 as I82

ROOT = Path(__file__).resolve().parents[1]
KEY = "I95"
SIDECAR = "spec/M3/lib/blind_rerun_i95.json"
OUT = "audit/blind/I95"
MARKER = "holon/binding.py"
BINDING_DIR = "gen/M3/binding"
THRESHOLD = 0.90
MIN_MATCHED = 40


def sidecar(root=ROOT) -> dict:
    return json.loads((Path(root) / SIDECAR).read_text(encoding="utf-8"))


def _sha(b: bytes | None) -> str | None:
    return None if b is None else hashlib.sha256(b).hexdigest()


def _git(root, *args) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True)


# ====================================================================== the binding row
def binding_rows(blind_tree, lead_root, commit: str, stems: list[str]) -> list[dict]:
    rows = []
    for s in sorted(stems):
        rel = f"{BINDING_DIR}/{s}.json"
        bp = Path(blind_tree) / rel
        b = bp.read_bytes() if bp.is_file() else None
        r = _git(lead_root, "show", f"{commit}:{rel}")
        lead = r.stdout if r.returncode == 0 else None
        rows.append({"document": s, "blind": _sha(b), "lead": _sha(lead),
                     "equal": b is not None and lead is not None and b == lead})
    return rows


# ====================================================================== the comparison, per rule
def _rule_of(tree, m: str, laws: list[str]) -> str:
    return I46._law(tree, m, sorted(laws)[0])["rule"]


def _disagreeing(cmp: dict, m: str) -> set[str]:
    return {d["key"] for d in (cmp["milestones"].get(m) or {}).get("disagreements", [])}


def _recorded(tree, m: str) -> dict:
    classes, _ = I82.tree_classes(tree, m)
    return {k: c for k, c in classes.items() if c.get("status") is not None}


def per_rule(lead_tree, blind_tree, cmp: dict, m: str = "M3") -> dict:
    lead, blind, dis = _recorded(lead_tree, m), _recorded(blind_tree, m), _disagreeing(cmp, m)
    out: dict = {}
    for k, c in sorted(lead.items()):
        r = out.setdefault(_rule_of(lead_tree, m, c["laws"]), {"lead": 0, "matched": 0, "agree": 0})
        r["lead"] += 1
        if k in blind:
            r["matched"] += 1
            r["agree"] += k not in dis
    return out


def carried(i46_lead, i46_tree, i46_cmp: dict, lead_tree, blind_tree, cmp: dict, m: str = "M3") -> dict:
    l46, b46, d46 = _recorded(i46_lead, m), _recorded(i46_tree, m), _disagreeing(i46_cmp, m)
    m46 = set(l46) & set(b46)
    now, blind, dis = set(_recorded(lead_tree, m)), set(_recorded(blind_tree, m)), _disagreeing(cmp, m)
    matched = now & blind
    agree46, dis46 = m46 - d46, m46 & d46
    return {"i46_disagreements": len(dis46), "now_agree": len((dis46 & matched) - dis),
            "i46_agreements": len(agree46), "kept": len((agree46 & matched) - dis)}


def flips(cmp: dict) -> list[dict]:
    return I46.flips(cmp)


# ====================================================================== the exit
def exit_clauses(root, p: str, cmp: dict, reads_ok_pre: bool, reads_ok_amended: bool, report_ok: bool) -> dict:
    m3 = cmp["milestones"].get("M3") or {"matched": 0, "agree": 0}
    status = json.loads(I82.show(root, p, "results/M3/audit_status.json"))
    back = json.loads(I82.show(root, p, "results/M3/backtest.json"))
    e = {"E1": bool(report_ok),
         "E2": m3["matched"] >= MIN_MATCHED and m3["agree"] >= THRESHOLD * m3["matched"],
         "E3": status.get("converged") is True,
         "E4": not back.get("exit_blockers"),
         "E5": bool(reads_ok_pre), "E5_pre": bool(reads_ok_pre), "E5_amended": bool(reads_ok_amended)}
    e["m3_exit"] = all(e[k] for k in ("E1", "E2", "E3", "E4", "E5"))
    e["i95_clause"] = e["E2"]
    return e


# ====================================================================== the pack commit
def pack_commit(root=ROOT, ref: str = "origin/claude/holon-v2-bend2-c6z3cd") -> str | None:
    r = _git(root, "rev-list", "--first-parent", "--reverse", ref)
    for c in r.stdout.decode().split():
        if _git(root, "cat-file", "-e", f"{c}:{MARKER}").returncode == 0:
            return c
    return None
