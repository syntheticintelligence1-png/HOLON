"""Rule NAT over a contract's versioned machine (BUILD_PLAN I29; whitepaper §5.3 (a)-(c), Thm 6.7 (c), §8.4's NAT row;
the contract is the docstring of tests_m3/test_nat.py, rules N1-N6 and N10).

  N1 initializers  the "introduced" entries of the versioned document's entry edge and MIG edges (edge, function,
                   reinitializer version), in path order
  N2 composition   per ordered pair (f_i, v_i) < (f_j, v_j) with f_j introduced at a MIG edge a -> b and f_i an action of
                   a's and b's documents with one selector: the square of f_i across a -> b (f_i before the migration,
                   as a call at a, against after it, as a call at b)
  N3 naturality    per in-flight type of the versioned document (kind retyped or reinterpreted, I28 rule V3) and each
                   action of the new version's document that reads its touched words and has a same-selector action at
                   the old version: the square of that action across the edge
  N4 native gaps   per in-flight type and reader: native equivalence has no statement over the machine; a generated gap
                   record
  N5 laws          one holon-ir/0.3 law per N2/N3 element, its claim the square term
                   {"square": "<model>:square:<a>:<b>:<op>", "on": [a, u, s, e]} equal to true

produce(ctx) is the catalog's producer for each sub-form (PRODUCERS): it reads the milestone's versions sidecar
(spec/<M>/lib/versions.json; a milestone without one derives nothing), the versioned document and every per-version
document it lists (each checked by its sha256: holon.rules.par_init.Versioned), all through ctx.inputs. square_ref(id,
law, root) is the statement ref square:<id>: the sha256 of the basis element and of the documents of its edge's two
versions, recomputed from the law's versioned document.

Nothing here names a target: every edge, function, family and action comes from the documents, the model's name from
the sidecar.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RULE = "NAT"
SUBFORMS = ("composition", "naturality")
TEMPLATE = "holon.rules.nat/{}"
TEMPLATE_VERSION = 1
LAW_PREFIX = "L_nat_"
PLACEHOLDER = "placeholder"
THREAD_KEYS = ("carried", "next", "at_break", "exit")   # a loop record's threading entries (I72 rule Z1)
STATE_ARG = {"carried": 2, "exit": 2, "store": 1}       # the argument of a state term that holds the state it wraps
HASHES = ("keccak256", "sha256")


class NatError(ValueError):
    """A versioned document that cannot be read as the sidecar names it (derive exit 1)."""


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


# ------------------------------------------------------------------------------------------------ reads
def base_family(t):
    """The family a state term stands for: ["storage", F], or a carried, exit or store term over one; else None."""
    while is_op(t):
        if t[0] == "storage" and len(t) == 2 and isinstance(t[1], str):
            return t[1]
        k = STATE_ARG.get(t[0])
        if k is None or len(t) <= k:
            return None
        t = t[k]
    return None


def _reads(t, acc: list) -> None:
    if isinstance(t, dict):
        for v in t.values():
            _reads(v, acc)
        return
    if not isinstance(t, list):
        return
    if is_op(t, "member") and len(t) == 3 and is_op(t[1], "map") and len(t[1]) == 3:
        f = base_family(t[1][1])
        if f is not None:                      # a member of a mapping's entry: (family, member)
            acc.append((f, t[2]))
            _reads(t[1][2], acc)
            return
    if is_op(t, "map") and len(t) == 3:
        f = base_family(t[1])
        if f is not None:                      # a mapping's entry read whole
            acc.append((f, None))
            _reads(t[2], acc)
            return
    f = base_family(t)
    if f is not None:                          # a bare state term: a whole read; its other operands are read too
        acc.append((f, None))
        k = STATE_ARG.get(t[0])
        for i, x in enumerate(t[1:], 1):
            if i != k:
                _reads(x, acc)
        return
    for x in t:
        _reads(x, acc)


def reads_of(action: dict) -> list:
    """[(family, member or None)] of an action's reads outside threading positions (rule N3): not the action's post (it
    restates the writes), nor a loop record's carried, next, at_break and exit entries named by a state term."""
    acc: list = []
    for k, v in action.items():
        if k == "post":
            continue
        if k == "loops":
            for lp in v or []:
                for lk, lv in lp.items():
                    if lk not in THREAD_KEYS:
                        _reads(lv, acc)
                        continue
                    for e in lv or []:
                        if not (isinstance(e, dict) and base_family(e.get("name")) is not None):
                            _reads(e, acc)
            continue
        _reads(v, acc)
    return acc


# ------------------------------------------------------------------------------------------------ the documents
def family(doc: dict, name: str) -> dict | None:
    for f in (doc.get("storage") or []) + (doc.get("inherited_storage") or []):
        if isinstance(f, dict) and f.get("name") == name:
            return f
    return None


def selectors(doc: dict) -> dict:
    return {a["name"]: (a.get("selector") or None) for a in doc.get("actions") or []}


def same_entry(da: dict, db: dict, name: str) -> bool:
    sa, sb = selectors(da), selectors(db)
    return name in sa and name in sb and sa[name] is not None and sa[name] == sb[name]


def touched(t: dict, da: dict, db: dict):
    """The touched words of an in-flight type at its new version: "*" for a reinterpreted entry; for a retyped one the
    members of the new layout whose (slot, offset) held no member of the same name and type in the old layout, sorted
    ("*" when either layout has no members)."""
    if t.get("kind") != "retyped":
        return "*"
    new = family(db, t["entry"].split(".", 1)[1])
    old = family(da, (t.get("reads") or [t["entry"]])[0].split(".", 1)[1])
    if not new or not old or not new.get("fields") or not old.get("fields"):
        return "*"
    had = {(m["slot"], m["offset"]): (m["name"], m.get("type")) for m in old["fields"]}
    return sorted(m["name"] for m in new["fields"] if had.get((m["slot"], m["offset"])) != (m["name"], m.get("type")))


def readers(doc: dict, fam: str, words) -> list:
    """The actions of a document that read the touched words of a family (rule N3), sorted."""
    out = []
    for a in doc.get("actions") or []:
        for f, mem in reads_of(a):
            if f == fam and (words == "*" or mem is None or mem in words):
                out.append(a["name"])
                break
    return sorted(out)


def introduced(vd: dict) -> list:
    """N1: [(source, target, function, version)] of the entry edge and the MIG edges, in path order."""
    out = []
    edges = []
    if vd.get("entry"):
        edges.append((PLACEHOLDER, vd["entry"]["to"], vd["entry"].get("introduced") or []))
    edges += [(e["from"], e["to"], e.get("introduced") or []) for e in vd.get("edges") or []]
    for a, b, intro in edges:
        for x in intro:
            out.append((a, b, x["name"], int(x["version"])))
    return out


def contract_name(vd: dict) -> str:
    c = vd.get("contract")
    return c.get("name") if isinstance(c, dict) else str(c)


def square_id(model: str, edge: str, op: str) -> str:
    a, b = edge.split("->")
    return f"{model}:square:{a}:{b}:{op}"


def analysis(vd: dict, docs: dict, model: str) -> dict:
    """N2-N4 over a versioned document and its per-version documents: {"composition", "naturality", "native_gaps"},
    each list sorted by id (the gaps without the sidecar's obligation, question and status)."""
    c = contract_name(vd)
    comp, nat, gaps = [], [], []
    intro = introduced(vd)
    for (ai, bi, fi, vi) in intro:
        for (a, b, fj, vj) in intro:
            if vi >= vj or a == PLACEHOLDER or a not in docs or b not in docs:
                continue
            if not same_entry(docs[a], docs[b], fi):
                continue
            comp.append({"law_id": f"{LAW_PREFIX}comp_{c}_{fi}_{fj}", "subform": "composition", "edge": f"{a}->{b}",
                         "op": fi, "early": {"edge": f"{ai}->{bi}", "function": fi, "version": vi},
                         "late": {"edge": f"{a}->{b}", "function": fj, "version": vj}})
    for t in vd.get("in_flight_types") or []:
        a, b = t["edge"].split("->")
        if a not in docs or b not in docs:
            continue
        words = touched(t, docs[a], docs[b])
        lab = t["entry"].split(".", 1)[1]
        for op in readers(docs[b], lab, words):
            lid = None
            if same_entry(docs[a], docs[b], op):
                lid = f"{LAW_PREFIX}sq_{c}_{a}_{b}_{lab}_{op}"
                nat.append({"law_id": lid, "subform": "naturality", "edge": f"{a}->{b}", "op": op,
                            "entry": t["entry"], "kind": t["kind"], "touched": words})
            gaps.append({"id": f"gap:M3:native:{a}->{b}:{t['entry']}:{op}", "kind": "native", "edge": f"{a}->{b}",
                         "entry": t["entry"], "in_flight_kind": t["kind"], "touched": words, "reader": op,
                         "square": lid})
    return {"composition": sorted(comp, key=lambda x: x["law_id"]),
            "naturality": sorted(nat, key=lambda x: x["law_id"]), "native_gaps": sorted(gaps, key=lambda x: x["id"])}


def elements(an: dict) -> list:
    return sorted(an["composition"] + an["naturality"], key=lambda x: x["law_id"])


def hash_binders(docs: list) -> list:
    used = set()
    for d in docs:
        s = canon(d)
        for h in HASHES:
            if f'["{h}",' in s:
                used.add(h)
    return [h for h in HASHES if h in used] or ["keccak256"]


# ------------------------------------------------------------------------------------------------ reading the documents
def versioned(milestone: str, root: Path, read=None):
    """holon.rules.par_init.Versioned: the versions sidecar, the versioned document and its per-version documents."""
    from .par_init import Versioned
    return Versioned(milestone, root, read=read)


def spec_of(element: dict, shas: dict) -> dict:
    a, b = element["edge"].split("->")
    return {"template": TEMPLATE.format(element["subform"]), "template_version": TEMPLATE_VERSION, "basis": element,
            "documents": {a: shas.get(a), b: shas.get(b)}}


def square_ref(sid: str, law: dict, root=None) -> str:
    """The ref square:<ID>: the sha256 (hex) of the canonical {template, template_version, basis, documents} of the basis
    element whose square id is ID, recomputed from the law's versioned document and the documents of its edge."""
    root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    try:
        vd = versioned(str(law.get("milestone")), root)
        els = [el for el in elements(analysis(vd.doc, vd.docs, vd.model))
               if square_id(vd.model, el["edge"], el["op"]) == sid]
        # the law's own element (the laws of several in-flight types share a square), else the first
        el = next((x for x in els if x["law_id"] == law.get("law_id")), els[0] if els else None)
        if el is not None:
            return hashlib.sha256(canon(spec_of(el, vd.shas)).encode("utf-8")).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as e:
        return hashlib.sha256(canon({"absent": sid, "error": type(e).__name__}).encode("utf-8")).hexdigest()
    return hashlib.sha256(canon({"absent": sid}).encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ the producers
def law_of(el: dict, milestone: str, cv: str, rel: str, sha: str, model: str, hashes: list) -> dict:
    a, b = el["edge"].split("->")
    binders = [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"},
               {"q": "forall", "name": "u", "type": "Act"}, {"q": "forall", "name": "e", "type": "Env"}]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    sid = square_id(model, el["edge"], el["op"])
    if el["subform"] == "composition":
        what = (f"composition coherence (whitepaper §5.3 (c)): {el['op']}, introduced at {el['early']['edge']} "
                f"(version {el['early']['version']}), applied before the migration {a} -> {b} that introduces "
                f"{el['late']['function']} (version {el['late']['version']}) or after it")
    else:
        what = (f"naturality (whitepaper §5.3 (b)): {el['op']}, a reader at {b} of the in-flight type {el['entry']} "
                f"({el['kind']}, touched {el['touched'] if el['touched'] == '*' else ', '.join(el['touched'])}), "
                f"before the migration {a} -> {b} (at {a}) or after it (at {b})")
    notes = (f"{what}: from the reachable state s, the migration u then the call a at {b}, and the call a at {a} then u, "
             f"end in the same version and storage, the call succeeding on both sides or on neither and u likewise; "
             f"square {sid}")
    return {"ir_version": "holon-ir/0.3", "law_id": el["law_id"], "milestone": milestone, "rule": RULE,
            "subform": el["subform"], "rule_catalog_version": cv, "facts": rel, "facts_sha256": sha, "notes": notes,
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"square": sid, "on": [{"var": "a"}, {"var": "u"}, {"var": "s"},
                                                                  {"var": "e"}]}, {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def _produce(ctx, subform: str) -> list:
    from .par_init import sidecar_path, InitChainError
    root = Path(ctx.root)
    if not sidecar_path(ctx.milestone, root).is_file():
        return []
    try:
        vd = versioned(ctx.milestone, root, read=lambda p: ctx.inputs.read(Path(p)))
    except (OSError, KeyError, InitChainError) as e:
        raise NatError(f"the versioned document of {ctx.milestone} cannot be read: {type(e).__name__}: {e}") from e
    an = analysis(vd.doc, vd.docs, vd.model)
    out = []
    for el in an[subform]:
        a, b = el["edge"].split("->")
        law = law_of(el, ctx.milestone, ctx.rule_catalog_version, vd.rel, vd.sha, vd.model,
                     hash_binders([vd.docs[a], vd.docs[b]]))
        out.append((law, {"law_id": el["law_id"], "rule": RULE, "subform": subform, "facts": vd.rel, "basis": el}))
    return out


def produce_composition(ctx) -> list:
    return _produce(ctx, "composition")


def produce_naturality(ctx) -> list:
    return _produce(ctx, "naturality")


class _Producer:
    """A catalog producer object (a module-like object with produce(ctx)) for one sub-form."""

    def __init__(self, subform: str):
        self.subform = subform

    def produce(self, ctx) -> list:
        return _produce(ctx, self.subform)

    def __repr__(self) -> str:
        return f"<holon.rules.nat producer {self.subform}>"


PRODUCERS = {s: _Producer(s) for s in SUBFORMS}
