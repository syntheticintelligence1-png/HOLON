"""I29's instrument: rules N1-N4 of tests_m3/test_nat.py written out a second time, independently of holon/ (it imports
nothing from holon/ and reads only the committed JSON documents), over I28's versioned document and the per-version
transitions documents it lists.

  basis(vd, docs)        N1-N3: the NAT basis (composition squares, naturality squares) and N4's native gaps
  touched(vd, docs, t)   the touched words of an in-flight type at the edge's new version (members or "*")
  readers(doc, family, touched)   the actions of a document that read the touched words (Z1-style read positions)
  law_ids / gap_ids      the ids the basis gives
  min_length(vd, a)      the length of the shortest trace from vr0 whose last state is at version a (the entry edge and
                         one migration per path edge up to a)
  ERROR_INITIALIZED      the revert data of OpenZeppelin 4.9.3's initializer guard (Error(string))

Nothing here names a version, an action or a family of the target: every one comes from the documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests._util import ROOT

VERSIONS_SIDECAR = "spec/M3/lib/versions.json"
NAT_SIDECAR = "spec/M3/lib/nat.json"
CONTRACT_PREFIX = "L_nat_"
SUBFORMS = ("composition", "naturality")
THREAD_KEYS = ("carried", "next", "at_break", "exit")      # a loop record's threading entries (I72 rule Z1)
STATE_WRAP = {"carried": 2, "exit": 2, "store": 1}          # the argument of a state term that holds the state before


def load(rel: str, root: Path = ROOT):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def error_string(reason: str) -> str:
    """The ABI encoding of Error(string) with the reason, as hex with 0x."""
    b = reason.encode()
    pad = (32 - len(b) % 32) % 32
    return ("0x08c379a0" + (32).to_bytes(32, "big").hex() + len(b).to_bytes(32, "big").hex() + (b + bytes(pad)).hex())


ERROR_INITIALIZED = error_string("Initializable: contract is already initialized")


# ---------------------------------------------------------------------------------------------- the documents
def versioned(root: Path = ROOT) -> tuple[str, dict, dict]:
    """(the versioned document's path, the document, {version: its transitions document})."""
    side = load(VERSIONS_SIDECAR, root)
    rel = side["outputs"]["versions"]
    vd = load(rel, root)
    docs = {v: load(x["path"], root) for v, x in vd["documents"].items()}
    return rel, vd, docs


def vkey(v: str):
    return (int(v[1:]) if v[1:].isdigit() else 10 ** 9, v)


def actions(doc: dict) -> dict:
    return {a["name"]: a for a in doc.get("actions") or []}


def selector(doc: dict, name: str):
    a = actions(doc).get(name)
    return None if a is None else (a.get("selector") or None)


def family(doc: dict, name: str) -> dict | None:
    return next((f for f in (doc.get("storage") or []) + (doc.get("inherited_storage") or []) if f.get("name") == name),
                None)


def label(entry: str) -> str:
    return entry.split(".", 1)[1]


# ---------------------------------------------------------------------------------------------- reads (Z1-style)
def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def state_family(t):
    """The family of a state term (["storage", F], or a carried/exit/store wrapper of one), else None."""
    while is_op(t):
        if t[0] == "storage" and len(t) == 2 and isinstance(t[1], str):
            return t[1]
        i = STATE_WRAP.get(t[0])
        if i is None or len(t) <= i:
            return None
        t = t[i]
    return None


def reads_in(t, out: list) -> None:
    """Every read in a term: (family, member or None, whole) for each maximal member/map chain over a state term; a bare
    state term (no chain) is a whole read."""
    if isinstance(t, dict):
        for v in t.values():
            reads_in(v, out)
        return
    if not isinstance(t, list):
        return
    if is_op(t, "member") and len(t) == 3 and is_op(t[1], "map") and len(t[1]) == 3:
        f = state_family(t[1][1])
        if f is not None:
            out.append((f, t[2], False))
            reads_in(t[1][2], out)
            return
    if is_op(t, "map") and len(t) == 3:
        f = state_family(t[1])
        if f is not None:
            out.append((f, None, True))
            reads_in(t[2], out)
            return
    f = state_family(t)
    if f is not None:
        out.append((f, None, True))
        for i, x in enumerate(t[1:], 1):     # the state underneath a wrapper is threading, its other arguments are read
            if i != STATE_WRAP.get(t[0]):
                reads_in(x, out)
        return
    for x in t:
        reads_in(x, out)


def action_reads(a: dict) -> list:
    """The reads of an action outside threading positions: the action record without post (it restates the writes),
    each loop record's threading entries named by a state term dropped (their entry and value thread the family)."""
    out: list = []
    for k, v in a.items():
        if k == "post":
            continue
        if k == "loops":
            for lp in v or []:
                for lk, lv in lp.items():
                    if lk in THREAD_KEYS:
                        for e in lv or []:
                            if not (isinstance(e, dict) and state_family(e.get("name")) is not None):
                                reads_in(e, out)
                    else:
                        reads_in(lv, out)
            continue
        reads_in(v, out)
    return out


def touched(vd: dict, docs: dict, t: dict):
    """The words of an in-flight type the change touches at the new version: for a reinterpreted entry "*" (every word);
    for a retyped mapping of structs, the members of the new layout whose (slot, offset) holds no member of the old
    layout with the same name and type (sorted); "*" for any other retyped entry."""
    a, b = t["edge"].split("->")
    if t["kind"] != "retyped":
        return "*"
    fb = family(docs[b], label(t["entry"]))
    fa = family(docs[a], label(t["reads"][0]))
    if not fb or not fa or not fb.get("fields") or not fa.get("fields"):
        return "*"
    old = {(m["slot"], m["offset"]): (m["name"], m.get("type")) for m in fa["fields"]}
    return sorted(m["name"] for m in fb["fields"] if old.get((m["slot"], m["offset"])) != (m["name"], m.get("type")))


def readers(doc: dict, fam: str, words) -> list:
    """The actions of a document (every action) that read the touched words of family fam: any read of fam when words
    is "*"; else a member read of a touched member, or a whole read of fam or of one of its entries."""
    out = []
    for name, a in sorted(actions(doc).items()):
        hit = False
        for f, m, whole in action_reads(a):
            if f != fam:
                continue
            if words == "*" or whole or m in words:
                hit = True
                break
        if hit:
            out.append(name)
    return out


# ---------------------------------------------------------------------------------------------- the basis
def introduced(vd: dict) -> list:
    """[(edge (a, b), function name, reinitializer version)] of the entry edge and the path's MIG edges, path order."""
    out = []
    edges = ([("placeholder", vd["entry"]["to"], vd["entry"].get("introduced") or [])] if vd.get("entry") else []) + \
        [(e["from"], e["to"], e.get("introduced") or []) for e in vd["edges"]]
    for a, b, intro in edges:
        for x in intro:
            out.append(((a, b), x["name"], int(x["version"])))
    return out


def basis(vd: dict, docs: dict, contract: str | None = None) -> dict:
    """{"composition": [..], "naturality": [..], "native_gaps": [..]}, each sorted by id (N1-N4)."""
    if contract is None:
        contract = vd["contract"]["name"] if isinstance(vd.get("contract"), dict) else vd["contract"]
    comp, nat, gaps = [], [], []
    intro = introduced(vd)
    for (ei, fi, vi) in intro:
        for (ej, fj, vj) in intro:
            a, b = ej
            if vi >= vj or a == "placeholder":
                continue
            sa, sb = selector(docs[a], fi), selector(docs[b], fi)
            if sa is None or sa != sb:
                continue
            comp.append({"law_id": f"{CONTRACT_PREFIX}comp_{contract}_{fi}_{fj}", "subform": "composition",
                         "edge": f"{a}->{b}", "op": fi, "early": {"edge": f"{ei[0]}->{ei[1]}", "function": fi,
                                                                  "version": vi},
                         "late": {"edge": f"{a}->{b}", "function": fj, "version": vj}})
    for t in vd.get("in_flight_types") or []:
        a, b = t["edge"].split("->")
        words = touched(vd, docs, t)
        for op in readers(docs[b], label(t["entry"]), words):
            sa, sb = selector(docs[a], op), selector(docs[b], op)
            lid = None
            if sa is not None and sa == sb:
                lid = f"{CONTRACT_PREFIX}sq_{contract}_{a}_{b}_{label(t['entry'])}_{op}"
                nat.append({"law_id": lid, "subform": "naturality", "edge": f"{a}->{b}", "op": op, "entry": t["entry"],
                            "kind": t["kind"], "touched": words})
            gaps.append({"id": f"gap:M3:native:{a}->{b}:{t['entry']}:{op}", "kind": "native", "edge": f"{a}->{b}",
                         "entry": t["entry"], "in_flight_kind": t["kind"], "touched": words, "reader": op,
                         "square": lid})
    return {"composition": sorted(comp, key=lambda x: x["law_id"]), "naturality": sorted(nat, key=lambda x: x["law_id"]),
            "native_gaps": sorted(gaps, key=lambda x: x["id"])}


def law_ids(bs: dict) -> list:
    return sorted(x["law_id"] for k in SUBFORMS for x in bs[k])


def gap_ids(bs: dict) -> list:
    return [g["id"] for g in bs["native_gaps"]]


def min_length(vd: dict, a: str) -> int:
    """The shortest trace from vr0 to a state at path version a: the entry edge, then one migration per path edge."""
    return 1 + vd["path"].index(a)


def square_id(model: str, edge: str, op: str) -> str:
    a, b = edge.split("->")
    return f"{model}:square:{a}:{b}:{op}"


def hash_binders(docs: list) -> list:
    """One Fn<Bytes,Word> binder per hash function the documents apply (keccak256 first), keccak256 when none."""
    used = set()
    for d in docs:
        s = json.dumps(d)
        for h in ("keccak256", "sha256"):
            if f'["{h}",' in s:
                used.add(h)
    return [h for h in ("keccak256", "sha256") if h in used] or ["keccak256"]


def expected_statement(model: str, element: dict, docs: dict) -> dict:
    """N5's statement of a basis element's law."""
    a, b = element["edge"].split("->")
    binders = [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"},
               {"q": "forall", "name": "u", "type": "Act"}, {"q": "forall", "name": "e", "type": "Env"}]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hash_binders([docs[a], docs[b]])]
    return {"binders": binders, "assume": [],
            "claim": {"eq": [{"square": square_id(model, element["edge"], element["op"]),
                              "on": [{"var": "a"}, {"var": "u"}, {"var": "s"}, {"var": "e"}]}, {"bool": True}]},
            "scope": {"kind": "unbounded"}}


def basis_doc(root: Path = ROOT) -> dict:
    """The instrument's basis over the committed versioned document (what spec/M3/lib/nat_basis.json records)."""
    rel, vd, docs = versioned(root)
    bs = basis(vd, docs)
    return {"versioned": {"path": rel, "sha256": sha256_file(Path(root) / rel)}, "path": vd["path"],
            "in_flight_types": vd.get("in_flight_types") or [], "introduced": [
                {"edge": f"{e[0]}->{e[1]}", "function": f, "version": v} for e, f, v in introduced(vd)],
            **bs, "law_ids": law_ids(bs), "gap_ids": gap_ids(bs)}
