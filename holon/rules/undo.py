"""Rule UNDO over the extracted documents: undo pairs, residues, residue bases and their laws (BUILD_PLAN I27; whitepaper
§5.2, §10.6, Thm 6.9, §8.4 and §10.4 UNDO rows, App. E, App. F; the contract is the docstring of tests_m3/test_undo.py,
rules U1-U6, L1, L2 and "The analysis").

  python -m holon undo --milestone M [--root DIR] [--undo-sidecar PATH] [--facts PATH ..] [--out DIR]
                       [--classify] [--backtest]

writes <out, default gen/<M>/undo>/<model>.json for every transitions document the UNDO sidecar's typed-sorts sidecar
names (default spec/<M>/lib/undo.json), or for each --facts document (planted documents). --classify then writes
results/<M>/undo/classification.json (the static class of every UNDO law against its record's kernel class) and
--backtest results/<M>/undo/backtest.json (the M1 UNDO laws against their analogues, by the sidecar's frozen map).
Exit 0 written; 2 refused, nothing written (a sidecar or document missing or malformed); 1 an unreadable input.

Registers and terms (U1). A register is a storage family at a key (a scalar family is one register; a mapping
family's register at k is its whole value there). ["storage", F] reads F's value before the transaction (A-env).
Conjuncts split ["&&", ..] recursively. A write is whole when its path has at most one element; unconditional when its
cond is 1, or when it sits in a loop whose cond is 1 and its cond is the loop's head (the body's first iteration);
final when no later write of its action writes the same family whole at the syntactically same key. Keys of two
different actions match unless both are integer literals that differ, after normalization (["iter", s] reads 0,
["carried", s, x] reads x, x + 0 reads x).

  U2 pins       a guard reach's top-level conjunct ["==", R, c] / ["==", c, R] (c an integer), ["!", R] (c = 0) or,
                for a bool family, R, ["!=", R, 0], ["!=", 0, R] (c = 1), R the read of a register
  U3 restores   literal: a whole, fresh write of a pinned register (pinned before it, to a literal it does not write),
                that ā writes back to the literal unconditionally, at a matching key ("zero" when the literal is 0);
                cursor: a uint scalar advanced by n (from itself, or from a term a guard equates with it), that ā
                moves back by n unconditionally
  U4 pairs      (a, ā), distinct, neither a view nor pure, ā restoring a write of a, with at least one criterion: guard
                (a guard reach of ā before a restoring write reads the restored family at a matching key), cursor (a
                cursor restore), event (an unconditional event of each, different names, the same parameter types and
                indexed flags); a restore with no criterion is rejected ("no_criterion"); (a, a) is never a pair
  U5 residues   the families of a's final writes that ā does not restore and that are not identity writes
  U6 bases      one per (ā, F): the cursors ā restores in the pairs that leave F, the mapping families ā clears whole
                with 0 unconditionally (other than F), and those pairs' actions

Laws (L1, L2): one pair law per undo pair, L_undo_pair_<contract>_<a>_<undo>; one residue law per residue basis,
L_undo_res_<contract>_<undo>_<family>; the claim {"undo": <undo id>, "on": [binders]} == true, hashed through the ref
"undo:<id>" (undo_ref). Their static class is D1-D3's (holon.analysis.deadness).

Nothing here names a target: every action, family, term and law id comes from the document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from ..analysis import deadness as D
from ..analysis.deadness import canon, conjuncts, is_int, is_op, reaches

RULE = "UNDO"
SUBFORMS = ("pair", "residue")
UNDO_VERSION = "holon-undo/0.1"
TEMPLATE_VERSION = 1
NOT_STATE = ("view", "pure")
ROOT = Path(__file__).resolve().parents[2]
LAW_PREFIX = "L_" + RULE.lower() + "_"


class UndoError(ValueError):
    """A basis that cannot be derived (two bases with one law id): derive exit 3."""


class Refused(ValueError):
    """A sidecar or document missing or malformed: exit 2, nothing written."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------------ the document
class Doc:
    """A holon-facts/0.3 transitions document: its storage families and actions."""

    def __init__(self, d: dict):
        self.d = d
        self.fams = {f["name"]: f for f in (d.get("storage") or []) + (d.get("inherited_storage") or [])}
        self.actions = list(d.get("actions") or [])
        self.by = {a["name"]: a for a in self.actions}
        self.contract = d.get("contract")

    def value_type(self, f: str) -> str:
        return str(self.fams.get(f, {}).get("value", ""))

    def is_mapping(self, f: str) -> bool:
        return self.fams.get(f, {}).get("kind") == "mapping"

    def uint_scalar(self, f: str) -> bool:
        x = self.fams.get(f, {})
        return x.get("kind") == "scalar" and str(x.get("value", "")).startswith("uint")


def wkey(w: dict) -> tuple:
    """(key or None, whole) of a write: path [] a scalar (whole), [["map", k]] a whole register, longer a member."""
    path = w.get("path") or []
    if not path:
        return None, True
    if is_op(path[0], "map"):
        return path[0][1], len(path) == 1
    return None, False


def norm_key(t):
    """U1: ["iter", s] -> 0, ["carried", s, x] -> x, then x + 0 -> x."""
    if is_op(t, "iter"):
        return 0
    if is_op(t, "carried") and len(t) == 3:
        return norm_key(t[2])
    if isinstance(t, list):
        t = [norm_key(x) for x in t]
        if is_op(t, "+") and len(t) == 3:
            if t[2] == 0:
                return t[1]
            if t[1] == 0:
                return t[2]
    return t


def keys_match(k1, k2) -> bool:
    k1, k2 = norm_key(k1), norm_key(k2)
    if is_int(k1) and is_int(k2):
        return k1 == k2
    return True


def unconditional(action: dict, rec: dict) -> bool:
    if rec.get("cond") == 1:
        return True
    lp = D.loop_of(action, rec)
    return lp is not None and lp.get("cond") == 1 and canon(rec.get("cond")) == canon(lp.get("head"))


def final(action: dict, i: int) -> bool:
    w = action["writes"][i]
    k, _ = wkey(w)
    for w2 in action["writes"]:
        if w2 is w or w2["family"] != w["family"] or w2["seq"] <= w["seq"]:
            continue
        k2, whole2 = wkey(w2)
        if whole2 and canon(k2) == canon(k):
            return False
    return True


def identity_write(w: dict) -> bool:
    k, whole = wkey(w)
    if not whole:
        return False
    own = D.storage(w["family"]) if k is None else ["map", D.storage(w["family"]), k]
    return canon(w.get("value")) == canon(own)


def _windex(at: str) -> int:
    m = re.fullmatch(r"writes\[(\d+)\]", at)
    if not m:
        raise ValueError(f"not a write reference: {at!r}")
    return int(m.group(1))


# ------------------------------------------------------------------------------------------------ U2-U6
def pins(doc: Doc, a: dict) -> list:
    """U2: the registers a's guard reaches pin to a literal."""
    out = []
    for gi, _ri, r in reaches(a):
        for c in conjuncts(r.get("expr")):
            cand = []
            if is_op(c, "==") and len(c) == 3:
                if is_int(c[2]):
                    cand.append((c[1], c[2]))
                if is_int(c[1]):
                    cand.append((c[2], c[1]))
            elif is_op(c, "!") and len(c) == 2:
                cand.append((c[1], 0))
            elif is_op(c, "!=") and len(c) == 3 and (c[2] == 0 or c[1] == 0) and not (c[1] == 0 and c[2] == 0):
                cand.append((c[1] if c[2] == 0 else c[2], "bool"))
            else:
                cand.append((c, "bool"))
            for reg, lit in cand:
                if is_op(reg, "map") and len(reg) == 3 and is_op(reg[1], "storage") and len(reg[1]) == 2:
                    fam, key = reg[1][1], reg[2]
                elif is_op(reg, "storage") and len(reg) == 2:
                    fam, key = reg[1], None
                else:
                    continue
                if fam not in doc.fams:
                    continue
                if lit == "bool":
                    if doc.value_type(fam) != "bool":
                        continue
                    lit = 1
                out.append({"family": fam, "key": key, "literal": lit, "seq": r.get("seq"), "at": f"guards[{gi}]"})
    return out


def restores(doc: Doc, a: dict, ab: dict) -> list:
    """U3: every restore by ab of a write of a, sorted by canonical JSON."""
    out = []
    ps = pins(doc, a)
    for i, wa in enumerate(a.get("writes") or []):
        if wa.get("cond") != 1 or not final(a, i):
            continue
        ka, whole_a = wkey(wa)
        fam = wa["family"]
        if whole_a and not D.reads_family(wa.get("value"), fam):            # literal
            for p in ps:
                if p["family"] != fam or canon(p["key"]) != canon(ka) or p["seq"] >= wa["seq"] \
                        or wa.get("value") == p["literal"]:
                    continue
                for j, wb in enumerate(ab.get("writes") or []):
                    kb, whole_b = wkey(wb)
                    if wb["family"] != fam or not whole_b or not unconditional(ab, wb):
                        continue
                    if not is_int(wb.get("value")) or wb["value"] != p["literal"] or (ka is None) != (kb is None):
                        continue
                    if ka is not None and not keys_match(ka, kb):
                        continue
                    out.append({"family": fam, "a_write": f"writes[{i}]", "undo_write": f"writes[{j}]",
                                "how": "zero" if p["literal"] == 0 else "literal", "pin": p["at"]})
        v = wa.get("value")
        if ka is None and doc.uint_scalar(fam) and is_op(v, "+") and len(v) == 3:   # cursor
            t, n = (v[1], v[2]) if is_int(v[2]) else (v[2], v[1])
            if not (is_int(n) and n >= 1):
                continue
            adv = canon(t) == canon(D.storage(fam))
            for _, _, r in reaches(a):
                if r.get("seq") is None or r["seq"] >= wa["seq"]:
                    continue
                for c in conjuncts(r.get("expr")):
                    if is_op(c, "==") and len(c) == 3 and sorted([canon(c[1]), canon(c[2])]) == sorted(
                            [canon(t), canon(D.storage(fam))]):
                        adv = True
            if not adv:
                continue
            for j, wb in enumerate(ab.get("writes") or []):
                vb = wb.get("value")
                if wb["family"] != fam or wb.get("path") or not unconditional(ab, wb):
                    continue
                if is_op(vb, "-") and len(vb) == 3 and is_int(vb[2]) and vb[2] == n:
                    out.append({"family": fam, "a_write": f"writes[{i}]", "undo_write": f"writes[{j}]",
                                "how": "cursor", "pin": None})
    return sorted(out, key=canon)


def sig_types(sig: str) -> str:
    m = re.match(r"^[^(]*\((.*)\)$", sig or "")
    return m.group(1) if m else (sig or "")


def criteria(a: dict, ab: dict, rs: list) -> list:
    """U4's criteria for a restoring pair."""
    out = set()
    if any(r["how"] == "cursor" for r in rs):
        out.add("cursor")
    for r in rs:
        wa = a["writes"][_windex(r["a_write"])]
        wb = ab["writes"][_windex(r["undo_write"])]
        ka, _ = wkey(wa)
        for _, _, g in reaches(ab):
            if g.get("seq") is None or g["seq"] >= wb["seq"]:
                continue
            occ = D.occurrences(g.get("expr"), r["family"])
            if any(ka is None or k is None or keys_match(ka, k) for k, _ in occ):
                out.add("guard")
    for e in a.get("events") or []:
        if e.get("cond") != 1:
            continue
        for eb in ab.get("events") or []:
            if not unconditional(ab, eb):
                continue
            if e.get("event") != eb.get("event") and sig_types(e.get("signature")) == sig_types(eb.get("signature")) \
                    and e.get("indexed") == eb.get("indexed"):
                out.add("event")
    return sorted(out)


def residues_of(a: dict, rs: list) -> list:
    """U5: the families of a's final writes that the pair does not restore and that are not identity writes."""
    restored = {r["a_write"] for r in rs}
    fams = set()
    for i, w in enumerate(a.get("writes") or []):
        if not final(a, i) or f"writes[{i}]" in restored or identity_write(w):
            continue
        fams.add(w["family"])
    return sorted(fams)


def zero_families(doc: Doc, ab: dict, exclude: str) -> list:
    """U6: the mapping families other than `exclude` that ab writes whole with the literal 0, unconditionally."""
    out = set()
    for w in ab.get("writes") or []:
        k, whole = wkey(w)
        if k is None or not whole or w["family"] == exclude or not doc.is_mapping(w["family"]):
            continue
        if is_int(w.get("value")) and w["value"] == 0 and unconditional(ab, w):
            out.add(w["family"])
    return sorted(out)


def analyse(d: dict, model: str) -> dict:
    """The pairs, rejected pairs and residue bases (with their static classes) of one transitions document."""
    doc = Doc(d)
    pairs, rejected = [], []
    state = [a for a in doc.actions if a.get("mutability") not in NOT_STATE]
    for a in state:
        for ab in state:
            if a is ab:
                continue
            rs = restores(doc, a, ab)
            if not rs:
                continue
            cr = criteria(a, ab, rs)
            if cr:
                pairs.append({"a": a["name"], "undo": ab["name"], "criteria": cr, "restores": rs,
                              "residues": residues_of(a, rs)})
            else:
                rejected.append({"a": a["name"], "undo": ab["name"], "restores": rs, "reason": "no_criterion"})
    bases: dict = {}
    for p in pairs:
        for fam in p["residues"]:
            b = bases.setdefault((p["undo"], fam), {"pairs": set(), "cursors": set()})
            b["pairs"].add(p["a"])
            b["cursors"] |= {r["family"] for r in p["restores"] if r["how"] == "cursor"}
    residues = []
    for (ab, fam), b in sorted(bases.items()):
        cursors, zero = sorted(b["cursors"]), zero_families(doc, doc.by[ab], fam)
        st = D.classify(d, fam, cursors, zero)
        residues.append({"undo": ab, "family": fam, "pairs": sorted(b["pairs"]), "cursors": cursors, "zero": zero,
                         "class": st["class"], "live_readers": st["live_readers"], "excluded": st["excluded"]})
    cls = {(r["undo"], r["family"]): r["class"] for r in residues}
    for p in pairs:
        p["class"] = "dead" if all(cls[(p["undo"], f)] == "dead" for f in p["residues"]) else "live"
    key = lambda x: (x["a"], x["undo"])  # noqa: E731
    return {"model": model, "contract": d.get("contract"), "pairs": sorted(pairs, key=key),
            "rejected": sorted(rejected, key=key), "residues": residues}


# ------------------------------------------------------------------------------------------------ L1, L2
def pair_law_id(contract: str, a: str, undo: str) -> str:
    return f"{LAW_PREFIX}pair_{contract}_{a}_{undo}"


def residue_law_id(contract: str, undo: str, family: str) -> str:
    return f"{LAW_PREFIX}res_{contract}_{undo}_{family}"


def undo_id(model: str, subform: str, basis: dict) -> str:
    if subform == "pair":
        return f"{model}:pair:{basis['a']}:{basis['undo']}"
    return f"{model}:residue:{basis['undo']}:{basis['family']}"


def ghost_x(law_id: str) -> str:
    """The suffix of a law's generated definitions undo_<x> and uhit_<x>: the law id without its rule prefix (L1, L2)."""
    return law_id[len(LAW_PREFIX):]


def elements(an: dict) -> list:
    """Every basis element of an analysis: {"law_id", "subform", "undo_id", "basis", "static"}."""
    m, c = an["model"], an["contract"]
    out = []
    cls = {r["family"]: r["class"] for r in an["residues"]}
    by_res = {(r["undo"], r["family"]): r for r in an["residues"]}
    for p in an["pairs"]:
        basis = {"kind": "undo_pair", "model": m, "contract": c, "a": p["a"], "undo": p["undo"],
                 "criteria": p["criteria"], "restores": p["restores"], "residues": p["residues"]}
        out.append({"law_id": pair_law_id(c, p["a"], p["undo"]), "subform": "pair",
                    "undo_id": undo_id(m, "pair", basis), "basis": basis,
                    "static": {"class": p["class"],
                               "residues": {f: by_res[(p["undo"], f)]["class"] for f in p["residues"]}}})
    for r in an["residues"]:
        basis = {"kind": "undo_residue", "model": m, "contract": c, "undo": r["undo"], "family": r["family"],
                 "cursors": r["cursors"], "zero": r["zero"], "pairs": r["pairs"]}
        out.append({"law_id": residue_law_id(c, r["undo"], r["family"]), "subform": "residue",
                    "undo_id": undo_id(m, "residue", basis), "basis": basis,
                    "static": {"class": r["class"], "live_readers": r["live_readers"], "excluded": r["excluded"]}})
    del cls
    ids = [e["law_id"] for e in out]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise UndoError(f"two basis elements map to one law id: {dup}")
    uids = [e["undo_id"] for e in out]
    dup = sorted({i for i in uids if uids.count(i) > 1})
    if dup:
        raise UndoError(f"two bases with one undo id: {dup}")
    return sorted(out, key=lambda e: e["law_id"])


def undo_spec(subform: str, basis: dict) -> dict:
    return {"template": f"holon.rules.undo/{subform}", "template_version": TEMPLATE_VERSION, "subform": subform,
            "basis": basis}


def undo_hash(subform: str, basis: dict) -> str:
    """The ref "undo:<ID>": the sha256 of the canonical template, version, subform and basis."""
    return sha256_bytes(canon(undo_spec(subform, basis)).encode("utf-8"))


def model_of(doc_rel: str) -> str:
    """The model name of a document: its file name without ".json"."""
    name = Path(doc_rel).name
    return name[:-len(".json")] if name.endswith(".json") else Path(doc_rel).stem


def undo_ref(uid: str, law: dict, root=None) -> str:
    """The ref "undo:<ID>" recomputed from the law's document (G2 needs no derive output): the basis element whose
    undo id is uid, hashed as undo_hash; a document that no longer gives it hashes as absent."""
    root = Path(root or ROOT)
    rel = str(law.get("facts"))
    try:
        d = json.loads((root / rel).read_text(encoding="utf-8"))
        els = elements(analyse(d, model_of(rel)))
    except (OSError, ValueError, KeyError, TypeError) as e:
        return sha256_bytes(canon({"absent": uid, "error": type(e).__name__}).encode("utf-8"))
    for e in els:
        if e["undo_id"] == uid:
            return undo_hash(e["subform"], e["basis"])
    return sha256_bytes(canon({"absent": uid}).encode("utf-8"))


def law_ir(e: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str, hashes: list) -> dict:
    """The holon-ir/0.3 law of a basis element (L1, L2)."""
    if e["subform"] == "pair":
        head = [("s", "Reach"), ("x", "Act"), ("y", "Act"), ("t", "Trace")]
        b = e["basis"]
        notes = (f"after a call x of {b['a']} and a call y of {b['undo']}, both succeeding and restoring every "
                 "register the pair restores, every trace t observes the same outputs as from the state before x "
                 "(App. F's undo law; Thm 6.9)")
    else:
        b = e["basis"]
        head = [("s", "Reach"), ("k", "Word"), ("v", f"Val[{b['family']}]"), ("t", "Trace")]
        notes = (f"with the context of the residue {b['family']} after {b['undo']} at key k (every cursor below k, "
                 "every cleared marker zero at k), setting the register to any value v changes no observation of any "
                 "trace t (Thm 6.9(i): index-relative noninterference)")
    binders = [{"q": "forall", "name": n, "type": t} for n, t in head]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    return {"ir_version": "holon-ir/0.3", "law_id": e["law_id"], "milestone": milestone, "rule": RULE,
            "subform": e["subform"], "rule_catalog_version": catalog_version, "facts": doc_rel,
            "facts_sha256": doc_sha, "notes": f"{notes}; undo {e['undo_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"undo": e["undo_id"], "on": [{"var": x["name"]} for x in binders]},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(e: dict, doc_rel: str) -> dict:
    return {"law_id": e["law_id"], "rule": RULE, "subform": e["subform"], "facts": doc_rel, "basis": e["basis"],
            "static": e["static"]}


# ------------------------------------------------------------------------------------------------ the sidecar
class Sidecar:
    """The UNDO sidecar (holon-undo/0.1): the typed-sorts sidecar whose documents it reads, the observation, the
    premise, the search budget and the back-test map."""

    def __init__(self, path: Path, rel: str, doc: dict, root: Path):
        self.path, self.rel, self.doc, self.root = path, rel, doc, root

    @property
    def sort_types(self) -> str:
        return self.doc["sort_types"]

    @property
    def search(self) -> dict:
        return dict(self.doc.get("search") or {})

    @property
    def backtest(self) -> dict | None:
        return self.doc.get("backtest")


def _rel(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return f"<outside>/{Path(p).name}"


def resolve(path: str, root: Path) -> Path:
    """A path argument: relative to the root when it exists there, else to the working directory."""
    p = Path(path)
    if p.is_absolute():
        return p
    return root / p if (root / p).exists() else Path.cwd() / p


def default_sidecar(milestone: str, root: Path) -> Path:
    return Path(root) / "spec" / milestone / "lib" / "undo.json"


def load_sidecar(milestone: str, root: Path, path: str | None = None) -> Sidecar:
    root = Path(root).resolve()
    p = resolve(path, root) if path else default_sidecar(milestone, root)
    if not p.is_file():
        raise Refused(f"the UNDO sidecar {_rel(p, root)} does not exist")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise Refused(f"{_rel(p, root)}: not JSON: {e}") from None
    if not isinstance(doc, dict) or doc.get("undo_version") != UNDO_VERSION:
        raise Refused(f"{_rel(p, root)}: undo_version {doc.get('undo_version') if isinstance(doc, dict) else None!r} "
                      f"(want {UNDO_VERSION})")
    for k in ("sort_types", "observation", "premise", "search"):
        if k not in doc:
            raise Refused(f"{_rel(p, root)}: no {k!r}")
    return Sidecar(p, _rel(p, root), doc, root)


def has_sidecar(milestone: str, root: Path, path: str | None = None) -> bool:
    return bool(path) or default_sidecar(milestone, root).is_file()


# ------------------------------------------------------------------------------------------------ producers
def _ctx_elements(ctx) -> list:
    """(document, its elements) for every typed document of the derivation that the milestone's UNDO sidecar reads;
    none without an UNDO sidecar (a test milestone takes one with --undo-sidecar)."""
    from .sort import hash_functions
    root = Path(ctx.root)
    spath = getattr(ctx, "undo_sidecar", None)
    if not has_sidecar(ctx.milestone, root, spath):
        return []
    if getattr(ctx, "_undo_elements", None) is not None:
        return ctx._undo_elements
    try:
        sc = load_sidecar(ctx.milestone, root, spath)
    except Refused as e:
        raise UndoError(str(e)) from e
    tsc = getattr(ctx, "sidecar", None)
    if tsc is not None and Path(sc.root / sc.sort_types).resolve() != Path(tsc.path).resolve():
        raise UndoError(f"the UNDO sidecar {sc.rel} reads {sc.sort_types}, not the typed-sorts sidecar {tsc.rel}")
    inputs = getattr(ctx, "inputs", None)
    if inputs is not None:
        inputs.read(sc.path)
    out = []
    for d in getattr(ctx, "typed_documents", []) or []:
        an = analyse(d.facts, model_of(d.rel))
        out.append((d, elements(an), hash_functions(d.facts)))
    ctx._undo_elements = out
    return out


class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.undo.{subform}"

    def produce(self, ctx) -> list:
        out = []
        for d, els, hashes in _ctx_elements(ctx):
            for e in els:
                if e["subform"] != self.subform:
                    continue
                law = law_ir(e, ctx.milestone, d.rel, d.sha256, ctx.rule_catalog_version, hashes)
                out.append((law, entry_of(e, d.rel)))
        return out


PAIR = _Producer("pair")
RESIDUE = _Producer("residue")
PRODUCERS = {"pair": PAIR, "residue": RESIDUE}


# ------------------------------------------------------------------------------------------------ the analysis document
def documents_of(sc: Sidecar, root: Path) -> list:
    """The transitions documents the UNDO sidecar's typed-sorts sidecar names (repo-relative)."""
    p = resolve(sc.sort_types, root)
    if not p.is_file():
        raise Refused(f"the typed-sorts sidecar {sc.sort_types} the UNDO sidecar names does not exist")
    try:
        ts = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise Refused(f"{sc.sort_types}: not JSON: {e}") from None
    docs = ts.get("documents") if isinstance(ts, dict) else None
    if not isinstance(docs, list) or not docs:
        raise Refused(f"{sc.sort_types}: no documents")
    return [str(x) for x in docs]


def _transitions(d) -> bool:
    return isinstance(d, dict) and d.get("facts_version") == "holon-facts/0.3" and \
        (d.get("extraction") or {}).get("kind") == "transitions"


def analysis_document(milestone: str, root: Path, doc_rel: str, inputs: list) -> dict:
    p = root / doc_rel
    raw = p.read_bytes()
    d = json.loads(raw.decode("utf-8"))
    if not _transitions(d):
        raise Refused(f"{doc_rel}: not a holon-facts/0.3 transitions document")
    an = analyse(d, model_of(doc_rel))
    ins = {x["path"]: x["sha256"] for x in inputs}
    ins[doc_rel] = sha256_bytes(raw)
    return {"document": "undo", "undo_version": UNDO_VERSION, "milestone": milestone, "model": an["model"],
            "contract": an["contract"], "facts": doc_rel, "facts_sha256": sha256_bytes(raw),
            "inputs": [{"path": k, "sha256": v} for k, v in sorted(ins.items())],
            "pairs": an["pairs"], "rejected": an["rejected"], "residues": an["residues"]}


# ------------------------------------------------------------------------------------------------ classification
def kernel_class(rec: dict | None) -> str:
    st = (rec or {}).get("status")
    return {"PROVED": "dead", "REFUTED": "live"}.get(st, "unknown")


def classification(milestone: str, root: Path, results: Path | None = None) -> dict:
    """results/<M>/undo/classification.json: every UNDO law of laws/<M>/DERIVATION.json, its static class against
    its record's kernel class (PROVED dead, REFUTED live, anything else unknown); a disagreement blocks the law's
    window and shadow generation."""
    root = Path(root)
    results = Path(results) if results else root / "results" / milestone
    dv = json.loads((root / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    laws, dis = {}, []
    for e in dv.get("laws") or []:
        if e.get("rule") != RULE:
            continue
        lid = e["law_id"]
        rp = results / f"{lid}.json"
        rec = json.loads(rp.read_text(encoding="utf-8")) if rp.is_file() else None
        static, kernel = (e.get("static") or {}).get("class"), kernel_class(rec)
        agree = static == kernel
        laws[lid] = {"subform": e.get("subform"), "static": static, "kernel": kernel, "agree": agree,
                     "blocks": [] if agree else ["shadow", "window"]}
        if not agree:
            dis.append(lid)
    return {"document": "undo_classification", "milestone": milestone, "laws": dict(sorted(laws.items())),
            "disagreements": sorted(dis)}


def warnings(milestone: str, root: Path, results: Path | None = None) -> list:
    """The gate's GUNDO warnings: one per disagreement of the regenerated classification, sorted by law."""
    try:
        c = classification(milestone, root, results)
    except (OSError, ValueError):
        return []
    return [{"check": "GUNDO", "law": lid} for lid in c["disagreements"]]


# ------------------------------------------------------------------------------------------------ the back-test
def backtest(milestone: str, root: Path, sc: Sidecar) -> dict:
    """results/M3/undo/backtest.json: each M1 UNDO law of the sidecar's frozen map against the law L1 or L2 would
    give its analogue (names mapped); analogue null when laws/<M> holds no such law (a back-test miss, an open rule
    gap). Reads the M1 laws and records the map names, and only them, for the M1 side."""
    root = Path(root)
    bt = sc.backtest or {}
    names = bt.get("names") or {}
    against = bt.get("against", "M1")
    rows, gaps = [], []
    dv = json.loads((root / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    entries = {e["law_id"]: e for e in dv.get("laws") or [] if e.get("rule") == RULE}
    for m1, spec in sorted((bt.get("laws") or {}).items()):
        m1_rec = json.loads((root / "results" / against / f"{m1}.json").read_text(encoding="utf-8"))
        json.loads((root / "laws" / against / f"{m1}.json").read_text(encoding="utf-8"))   # the M1 statement exists
        contracts = sorted({e["basis"]["contract"] for e in entries.values()})
        aid = None
        for c in contracts:
            if spec.get("subform") == "residue":
                cand = residue_law_id(c, names.get(spec["undo"], spec["undo"]), names.get(spec["family"], spec["family"]))
            else:
                cand = pair_law_id(c, names.get(spec["a"], spec["a"]), names.get(spec["undo"], spec["undo"]))
            if cand in entries:
                aid = cand
                break
        if aid is None:
            sub = spec.get("subform")
            if sub == "residue":
                why = (f"no residue basis ({names.get(spec['undo'], spec['undo'])}, "
                       f"{names.get(spec['family'], spec['family'])}) on the extracted document")
            else:
                why = (f"({names.get(spec['a'], spec['a'])}, {names.get(spec['undo'], spec['undo'])}) is not an undo "
                       "pair of the extracted document (no restore with a criterion: U3, U4): a back-test miss, an "
                       "open rule gap")
            rows.append({"m1_law": m1, "m1_status": m1_rec.get("status"), "analogue": None, "analogue_status": None,
                         "same_status": False, "reason": why})
            gaps.append(m1)
            continue
        rp = root / "results" / milestone / f"{aid}.json"
        st = json.loads(rp.read_text(encoding="utf-8")).get("status") if rp.is_file() else None
        same = st == m1_rec.get("status")
        e = entries[aid]
        why = (f"{aid} decides the {e['subform']} basis of the extracted document "
               f"(static class {(e.get('static') or {}).get('class')}); "
               + ("the same status as M1" if same else f"{st} where M1 recorded {m1_rec.get('status')}"))
        rows.append({"m1_law": m1, "m1_status": m1_rec.get("status"), "analogue": aid, "analogue_status": st,
                     "same_status": same, "reason": why})
    return {"document": "undo_backtest", "against": against, "rows": rows, "gaps": sorted(gaps)}


# ------------------------------------------------------------------------------------------------ the CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon undo")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--undo-sidecar", help="the UNDO sidecar (default spec/<M>/lib/undo.json)")
    ap.add_argument("--facts", action="append", help="a planted transitions document to analyse instead")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/undo)")
    ap.add_argument("--classify", action="store_true", help="write results/<M>/undo/classification.json")
    ap.add_argument("--backtest", action="store_true", help="write results/<M>/undo/backtest.json")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        written = {}
        if a.facts:
            sc_inputs = []
            if a.undo_sidecar or default_sidecar(a.milestone, root).is_file():
                sc = load_sidecar(a.milestone, root, a.undo_sidecar)
                sc_inputs = [{"path": sc.rel, "sha256": sha256_bytes(sc.path.read_bytes())}]
            for f in a.facts:
                p = resolve(f, root)
                if not p.is_file():
                    raise Refused(f"--facts {f}: no such document")
                rel = _rel(p, root)
                if rel.startswith("<outside>"):
                    raise Refused(f"--facts {f}: not inside the root {root}")
                written[model_of(rel)] = analysis_document(a.milestone, root, rel, sc_inputs)
            sc = None
        else:
            sc = load_sidecar(a.milestone, root, a.undo_sidecar)
            ts = resolve(sc.sort_types, root)
            base = [{"path": sc.rel, "sha256": sha256_bytes(sc.path.read_bytes())},
                    {"path": _rel(ts, root), "sha256": sha256_bytes(ts.read_bytes()) if ts.is_file() else None}]
            for rel in documents_of(sc, root):
                if not (root / rel).is_file():
                    raise Refused(f"{rel}: the document the sidecar names does not exist")
                written[model_of(rel)] = analysis_document(a.milestone, root, rel, base)
    except Refused as e:
        print(f"holon undo: refused: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"holon undo: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out = Path(a.out).resolve() if a.out else root / "gen" / a.milestone / "undo"
    out.mkdir(parents=True, exist_ok=True)
    for model, doc in sorted(written.items()):
        (out / f"{model}.json").write_text(dumps(doc), encoding="utf-8")
        print(f"holon undo: {model}: {len(doc['pairs'])} pairs, {len(doc['rejected'])} rejected, "
              f"{len(doc['residues'])} residue bases -> {_rel(out / f'{model}.json', root)}")
    try:
        if a.classify:
            c = classification(a.milestone, root)
            p = root / "results" / a.milestone / "undo" / "classification.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(dumps(c), encoding="utf-8")
            print(f"holon undo: classification: {len(c['laws'])} laws, {len(c['disagreements'])} disagreements")
        if a.backtest:
            sc = sc or load_sidecar(a.milestone, root, a.undo_sidecar)
            b = backtest(a.milestone, root, sc)
            p = root / "results" / a.milestone / "undo" / "backtest.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(dumps(b), encoding="utf-8")
            print(f"holon undo: back-test: {len(b['rows'])} rows, gaps {b['gaps']}")
    except Refused as e:
        print(f"holon undo: refused: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as e:
        print(f"holon undo: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0
