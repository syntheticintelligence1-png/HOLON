"""I71's instrument, fixed at the prereg (do not edit: a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl). Rules C1-C3 of tests_m3/test_undo_cancel.py (UNDO's cancellations: the cancel restore U3',
the criterion U4', their residues and static class) and rule C6's law of a cancellation, written out a second time,
independently of holon/. It builds on I27's instrument (tests_m3/test_undo.py: U1's keys, writes and conjuncts, U2's
pins, U5's identity writes and residues, D1-D3), itself independent of holon/ and fixed at I27's prereg. Standard
library only; deterministic.

U3' (cancel restore). ā cancel-restores a's write w (writes[i]) of the register (F, k_a) when
  - w is whole, fresh (its value reads no ["storage", F]), final, has cond 1, and its value is an integer literal v;
  - a pins (F, k_a) (U2, the same key term) to a literal c != v at a guard reach before w;
  - ā has a write w' (writes[j]) of F, whole, final in ā and in no loop, whose value is the integer literal c, at a key
    matching k_a (both scalar, or both keyed with matching keys: U1), and every top-level conjunct of w''s cond is
      ["param", p] or ["!", ["param", p]] (a parameter of ā or its negation), or
      a reading of the register (F at w''s own key: R = ["storage", F], or ["map", ["storage", F], k_b]) holding v:
      R itself, ["!=", R, 0] or ["!=", 0, R] when F's value type is bool and v = 1; ["!", R], ["==", R, 0] or
      ["==", 0, R] when v = 0; ["==", R, v] or ["==", v, R] otherwise.
  Record: {"family", "a_write": "writes[i]", "undo_write": "writes[j]", "how": "cancel", "pin": "guards[g]",
  "cond": w''s cond}; a candidate's restores are distinct and sorted by canonical JSON.
U4' (criterion cond). Some restore's cond has a conjunct of the second kind (it reads the register). A candidate
  (a, ā) (distinct actions, neither a view nor pure, at least one U3' restore) is a cancellation when U4' holds, with
  criteria ["cond"], and is rejected with reason "no_criterion" otherwise.
U5 for a cancellation: the families of a's final writes that ā does not cancel-restore and that are not identity writes,
  sorted. Static class of each residue family F: I27's D1-D3 with no cursor and no zero family (deadness(doc, F, [], []):
  dead iff no live reader); the cancellation is dead iff every residue is dead (a cancellation with no residue is dead).
  No residue basis comes from a cancellation (U6 bases come from pairs only).
L3 (rule C6). One law per cancellation: law id "L_undo_cancel_<contract>_<a>_<undo>", undo id
  "<model>:cancel:<a>:<undo>", basis {"kind": "undo_cancel", "model", "contract", "a", "undo", "criteria", "restores",
  "residues"}, static {"class", "residues": {family: class}}; its ref undo:<id> is the sha256 of canonical
  {"template": "holon.rules.undo/cancel", "template_version": 1, "subform": "cancel", "basis"}.

Planted variants (rule C1's edge cases): planted(doc, kind) returns a copy of the extracted Rollup document with one
change to setPause's restoring write of inChallenge (or to challengeState's pin), each with the cancellations rules
C1-C3 give it (PLANTED below).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from tests_m3 import test_undo as U27

NOT_STATE = U27.NOT_STATE
TEMPLATE_VERSION = 1


def _windex(at: str) -> int:
    return int(at[len("writes["):-1])


def doc_of(d: dict):
    """I27's Doc over a document held in memory (the same fields as U27.Doc reads from a file)."""
    doc = U27.Doc.__new__(U27.Doc)
    doc.path = None
    doc.d = d
    doc.fams = {f["name"]: f for f in d["storage"] + d.get("inherited_storage", [])}
    doc.actions = d["actions"]
    doc.by = {a["name"]: a for a in doc.actions}
    return doc


def load(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _param_conj(c) -> bool:
    if U27.is_op(c, "param") and len(c) == 2:
        return True
    return U27.is_op(c, "!") and len(c) == 2 and U27.is_op(c[1], "param") and len(c[1]) == 2


def _register(fam: str, key):
    return ["storage", fam] if key is None else ["map", ["storage", fam], key]


def holds(doc, fam: str, key, v: int, c) -> bool:
    """c reads the register (fam at key) holding v (U3')."""
    ck = U27.ck
    R = ck(_register(fam, key))
    if doc.value_type(fam) == "bool" and v == 1:
        if ck(c) == R:
            return True
        return U27.is_op(c, "!=") and len(c) == 3 and ((ck(c[1]) == R and c[2] == 0) or (ck(c[2]) == R and c[1] == 0))
    if v == 0:
        if U27.is_op(c, "!") and len(c) == 2 and ck(c[1]) == R:
            return True
        return U27.is_op(c, "==") and len(c) == 3 and ((ck(c[1]) == R and c[2] == 0) or (ck(c[2]) == R and c[1] == 0))
    return U27.is_op(c, "==") and len(c) == 3 and ((ck(c[1]) == R and c[2] == v) or (ck(c[2]) == R and c[1] == v))


def cancel_restores(doc, a: dict, ab: dict) -> list:
    """U3': every cancel restore by ab of a write of a, distinct, sorted by canonical JSON."""
    out = []
    ps = U27.pins(doc, a)
    for i, wa in enumerate(a["writes"]):
        if wa["cond"] != 1 or not U27.final(a, i):
            continue
        ka, whole_a = U27.wkey(wa)
        F = wa["family"]
        v = wa["value"]
        if not whole_a or U27.reads(v, F) or not U27.is_int(v):
            continue
        for p in ps:
            if p["family"] != F or U27.ck(p["key"]) != U27.ck(ka) or p["seq"] >= wa["seq"] or p["literal"] == v:
                continue
            c = p["literal"]
            for j, wb in enumerate(ab["writes"]):
                kb, whole_b = U27.wkey(wb)
                if wb["family"] != F or not whole_b or wb.get("loop") is not None or not U27.final(ab, j):
                    continue
                if not U27.is_int(wb["value"]) or wb["value"] != c or (ka is None) != (kb is None):
                    continue
                if ka is not None and not U27.keys_match(ka, kb):
                    continue
                if not all(_param_conj(x) or holds(doc, F, kb, v, x) for x in U27.conjuncts(wb["cond"])):
                    continue
                out.append({"family": F, "a_write": f"writes[{i}]", "undo_write": f"writes[{j}]", "how": "cancel",
                            "pin": p["at"], "cond": wb["cond"]})
    uniq = {U27.ck(r): r for r in out}
    return [uniq[k] for k in sorted(uniq)]


def cancel_criteria(doc, a: dict, ab: dict, rs: list) -> list:
    """U4': ["cond"] when some restore's cond has a conjunct reading the register it restores, else []."""
    for r in rs:
        wa = a["writes"][_windex(r["a_write"])]
        wb = ab["writes"][_windex(r["undo_write"])]
        kb, _ = U27.wkey(wb)
        if any(holds(doc, r["family"], kb, wa["value"], x) for x in U27.conjuncts(wb["cond"])):
            return ["cond"]
    return []


def cancellations(d: dict) -> dict:
    """{"cancellations": [{"a", "undo", "criteria", "restores", "residues", "class", "residue_classes"}],
    "rejected": [{"a", "undo", "restores", "reason"}]} of one document, each sorted by (a, undo)."""
    doc = doc_of(d)
    state = [a for a in doc.actions if a["mutability"] not in NOT_STATE]
    found, rejected = [], []
    for a in state:
        for ab in state:
            if a is ab:
                continue
            rs = cancel_restores(doc, a, ab)
            if not rs:
                continue
            cr = cancel_criteria(doc, a, ab, rs)
            if not cr:
                rejected.append({"a": a["name"], "undo": ab["name"], "restores": rs, "reason": "no_criterion"})
                continue
            res = U27.residues_of(a, rs)
            cls = {F: ("live" if U27.deadness(doc, F, [], [])[0] else "dead") for F in res}
            found.append({"a": a["name"], "undo": ab["name"], "criteria": cr, "restores": rs, "residues": res,
                          "class": "dead" if all(c == "dead" for c in cls.values()) else "live",
                          "residue_classes": cls})
    key = lambda x: (x["a"], x["undo"])  # noqa: E731
    return {"cancellations": sorted(found, key=key), "rejected": sorted(rejected, key=key)}


def model_of(rel: str) -> str:
    name = Path(rel).name
    return name[:-len(".json")] if name.endswith(".json") else Path(rel).stem


def cancel_laws(d: dict, model: str) -> dict:
    """L3: law id -> {"subform": "cancel", "undo_id", "basis", "static"} of one document's cancellations."""
    contract = d["contract"]
    out = {}
    for x in cancellations(d)["cancellations"]:
        basis = {"kind": "undo_cancel", "model": model, "contract": contract, "a": x["a"], "undo": x["undo"],
                 "criteria": x["criteria"], "restores": x["restores"], "residues": x["residues"]}
        out[f"L_undo_cancel_{contract}_{x['a']}_{x['undo']}"] = {
            "subform": "cancel", "undo_id": f"{model}:cancel:{x['a']}:{x['undo']}", "basis": basis,
            "static": {"class": x["class"], "residues": dict(sorted(x["residue_classes"].items()))}}
    return dict(sorted(out.items()))


def undo_ref(basis: dict) -> str:
    """The ref undo:<id> of a cancel law: the sha256 of the canonical template, version, subform and basis."""
    return hashlib.sha256(U27.canonical({"template": "holon.rules.undo/cancel", "template_version": TEMPLATE_VERSION,
                                         "subform": "cancel", "basis": basis})).hexdigest()


# ------------------------------------------------------------------------------------------------ planted variants
def _action(d: dict, name: str) -> dict:
    return next(a for a in d["actions"] if a["name"] == name)


def _restoring_write(d: dict) -> dict:
    """setPause's write of inChallenge with the literal 0 (the restore of the extracted document's cancellation)."""
    return next(w for w in _action(d, "setPause")["writes"] if w["family"] == "inChallenge" and w["value"] == 0)


IN_CH = ["storage", "inChallenge"]
STATUS = ["param", "_status"]
# kind -> (the change, the (a, undo) cancellations and rejected candidates rules C1-C3 give)
PLANTED = {
    "as_extracted": ("none", [("challengeState", "setPause")], []),
    "no_register_conjunct": ("the restoring write's cond is [param _status] alone", [], [("challengeState", "setPause")]),
    "foreign_conjunct": ("the cond gains the conjunct [! [storage _paused]] (neither a parameter nor the register)", [],
                         []),
    "negated_register": ("the cond's register conjunct is [! [storage inChallenge]] (the register holding 0, not v = 1)",
                         [], []),
    "ne_form": ("the cond's register conjunct is [!= [storage inChallenge] 0] (the register holding 1)",
                [("challengeState", "setPause")], []),
    "negated_param": ("the cond's parameter conjunct is [! [param _status]]", [("challengeState", "setPause")], []),
    "wrong_literal": ("the restoring write stores 1, not the pinned 0", [], []),
    "in_loop": ("the restoring write sits in a loop (a loop field naming a loop record's seq)", [], []),
    "no_pin": ("challengeState loses the guard reach [! [storage inChallenge]] that pins the register", [], []),
}


def planted(d: dict, kind: str) -> dict:
    """A copy of the extracted Rollup document with the change PLANTED[kind] names."""
    out = copy.deepcopy(d)
    w = _restoring_write(out)
    if kind == "as_extracted":
        pass
    elif kind == "no_register_conjunct":
        w["cond"] = STATUS
    elif kind == "foreign_conjunct":
        w["cond"] = ["&&", STATUS, IN_CH, ["!", ["storage", "_paused"]]]
    elif kind == "negated_register":
        w["cond"] = ["&&", STATUS, ["!", IN_CH]]
    elif kind == "ne_form":
        w["cond"] = ["&&", STATUS, ["!=", IN_CH, 0]]
    elif kind == "negated_param":
        w["cond"] = ["&&", ["!", STATUS], IN_CH]
    elif kind == "wrong_literal":
        w["value"] = 1
    elif kind == "in_loop":
        # a loop record of setPause (head and cond 1, so the write is no first-iteration write of it: I27's U3 still
        # sees a conditional write) holding the restoring write
        sp = _action(out, "setPause")
        seqs = [r.get("seq") or 0 for sec in ("guards", "checks", "panics", "calls", "writes", "events", "mstores", "loops")
                for r in (sp.get(sec) or []) if isinstance(r, dict)]
        n = 1 + max(seqs + [0])
        sp.setdefault("loops", []).append({"seq": n, "head": 1, "cond": 1, "bound": 1, "count": 1})
        w["loop"] = n
    elif kind == "no_pin":
        a = _action(out, "challengeState")
        for g in a["guards"]:
            g["reaches"] = [r for r in g["reaches"] if U27.ck(r.get("expr")) != U27.ck(["!", IN_CH])]
        a["guards"] = [g for g in a["guards"] if g["reaches"]]
    else:
        raise ValueError(f"no planted variant {kind!r}")
    return out
