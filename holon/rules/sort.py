"""SORT over the extracted documents: the producers of the subforms realize, as_member and reinterpret (BUILD_PLAN I30;
whitepaper §7.8, Thm 6.18, Prop 6.19, §5.6; the contract is the docstring of tests_m3/test_sort_types.py, rules M1-M4,
Z1 and C1-C3 and the law id and law IR sections).

Registered for M3 and later and for test milestones T<n> with n >= 30 (holon.rules.catalog_version). Each producer reads
the milestone's typed-sorts sidecar documents (holon.sorts.typed_sidecar), the frozen assignment (gen/<M>/sorts,
written by `holon sorts` only: Thm 6.18's freezing) and nothing else; it never writes the assignment.

  realize      (Z1) one law per site with obligation "sign" (holon.sorts.extracted, E4); hits: a checked site's
               realization check in each entry point (holon.machine's check id), else each occurrence
  as_member    (M1-M4) one law per member read: a read R of a union family f whose value reaches a write of f, at a
               write site with a member function, as its whole value or as a copy branch; hit: that copy write
  reinterpret  (C1-C3) one law per (register, guard span) of the coherence obstructions (E5) whose kappa uses the
               register as a mapping key or array index; hit: the action's effects

Law ids: L_sort_<tag|realize|reinterpret>_<slug(file stem)>_<lo>[_<hi>]_<x8> (x8: the site id's last 8 hex digits for
realize; sha256(canonical(R))[:8] for as_member; sha256(canonical([register, from, to]))[:8] for reinterpret). The
coercion id is "<model>:<subform>:<span>:<x8>". Two basis elements with one id are a derive error.

Nothing here names a target: every name, span and term comes from the documents and the assignment.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..sorts import extracted as X
from ..sorts import grammar as G

RULE = "SORT"
SUBFORMS = ("as_member", "realize", "reinterpret")
PREFIX = {"as_member": "L_sort_tag_", "realize": "L_sort_realize_", "reinterpret": "L_sort_reinterpret_"}
TEMPLATE = "holon.rules.sort/coerce_ok"
TEMPLATE_VERSION = 1
BOTTOM = ["bottom"]
_SPAN = re.compile(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$")


class SortRuleError(ValueError):
    """A basis element that cannot be derived (named): derive exit 3."""


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def x8(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()[:8]


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def law_id(subform: str, span: str, h8: str) -> str:
    m = _SPAN.match(span or "")
    if not m:
        raise SortRuleError(f"span {span!r} is not a source span")
    where = slug(Path(m["path"]).stem) + f"_{m['lo']}" + (f"_{m['hi']}" if m["hi"] else "")
    return f"{PREFIX[subform]}{where}_{h8}"


def coercion_id(model: str, subform: str, span: str, h8: str) -> str:
    return f"{model}:{subform}:{span}:{h8}"


def ghost_x(lid: str) -> str:
    """The suffix of a law's ghost definitions coerce_<x> and chit_<x>: the law id without "L_sort_"."""
    return lid[len("L_sort_"):]


# ------------------------------------------------------------------------------------------------ terms
def reads_family(t, f: str) -> bool:
    """Does a term read family f (["storage", f], under any access path)?"""
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and t[1] == f:
            return True
        return any(reads_family(x, f) for x in t)
    return False


def read_terms(t, f: str) -> list:
    """The read terms of f in t: ["map", ["storage", f], key] (any depth of map/index) or ["storage", f]."""
    out = []

    def walk(x):
        if not isinstance(x, list) or not x:
            return
        if x[0] in ("map", "index") and len(x) == 3 and _base_family(x) == f:
            out.append(x)
            walk(x[2])
            return
        if len(x) == 2 and x[0] == "storage" and x[1] == f:
            out.append(x)
            return
        for y in x:
            walk(y)
    walk(t)
    return out


def _base_family(t):
    while isinstance(t, list) and t and t[0] in ("map", "index") and len(t) == 3:
        t = t[1]
    if isinstance(t, list) and len(t) == 2 and t[0] == "storage":
        return t[1]
    return None


def fresh_value(v, f: str):
    """M1: the value with every branch of a ? that reads f removed (keeping the other branch, without its condition);
    None for a copy (all of its branches read f)."""
    if isinstance(v, list) and v and v[0] == "?" and len(v) == 4:
        c, x, y = v[1], v[2], v[3]
        rx, ry = reads_family(x, f), reads_family(y, f)
        if rx and ry:
            return None
        if rx:
            return fresh_value(y, f)
        if ry:
            return fresh_value(x, f)
        fx, fy = fresh_value(x, f), fresh_value(y, f)
        if fx is None or fy is None:
            return fx if fy is None else fy
        return ["?", c, fx, fy]
    if reads_family(v, f):
        return None
    return v


def copy_branches(v, f: str) -> list:
    """The branches of a write's value that M1 removes as reading f (the value itself when it reads f)."""
    if isinstance(v, list) and v and v[0] == "?" and len(v) == 4:
        x, y = v[2], v[3]
        rx, ry = reads_family(x, f), reads_family(y, f)
        out = []
        out += [x] if rx and not (isinstance(x, list) and x and x[0] == "?") else (copy_branches(x, f) if rx else [])
        out += [y] if ry and not (isinstance(y, list) and y and y[0] == "?") else (copy_branches(y, f) if ry else [])
        return out
    return [v] if reads_family(v, f) else []


class Tagger:
    """tg(e) of rule G2, over one document and its frozen assignment."""

    def __init__(self, model: str, seeds: dict, assignment: dict, unions: set):
        self.w = X.Walker(model, {"actions": []}, seeds)
        self.assignment = assignment
        self.unions = unions            # the union families of the model (their read terms are companion reads)

    def member_of_seed(self, t) -> str | None:
        ms = [s for _i, s in self.w.term_seed(t) + self.w.digest_seed(t)]
        ms = sorted(set(ms))
        if len(ms) == 1 and G.parse(ms[0]).head != "Union":
            return ms[0]
        return None

    def var_sort(self, t, action: str) -> str | None:
        v = self.w.family_var(t)
        if v is None:
            v = self.w.param_var(t, action)
        if v is None and isinstance(t, list) and t and t[0] == "env":
            v = f"env:{t[1]}"
        if v is None:
            return None
        return self.assignment.get(v)

    def tg(self, t, action: str):
        if isinstance(t, list) and t:
            f = _base_family(t)
            if f is not None and f in self.unions:
                key = t[2] if t[0] in ("map", "index") else None
                return [X.TAG_HEAD, f, key]
            if t[0] == "?" and len(t) == 4:
                a, b = self.tg(t[2], action), self.tg(t[3], action)
                if a == b and _is_member(a):
                    return a
                if a == BOTTOM and _is_member(b):
                    return b
                if b == BOTTOM and _is_member(a):
                    return a
                return ["?", t[1], a, b]
        m = self.member_of_seed(t)
        if m is not None:
            return ["sort", m]
        s = self.var_sort(t, action) if isinstance(t, list) else None
        if s is not None:
            try:
                ss = G.parse(s)
            except G.SortError:
                ss = None
            if ss is not None and ss.head not in ("Union", "Unrefined") and ss.head in G.UNION_FAMILIES:
                return ["sort", s]
        return BOTTOM


def _is_member(t) -> bool:
    return isinstance(t, list) and len(t) == 2 and t[0] == "sort"


def mentions_only_params(t) -> bool:
    """A member function mentions only ["param", ..] terms (with their ["member", ..] paths) and literals."""
    if isinstance(t, (int, bool)) or t is None:
        return True
    if not isinstance(t, list) or not t:
        return False
    h = t[0]
    if h == "sort" or t == BOTTOM:
        return True
    if h == "param":
        return True
    if h == "member":
        return mentions_only_params(t[1]) and isinstance(t[2], str)
    if h in (X.TAG_HEAD, "storage", "env", "caller", "this", "call", "blobhash", "keccak256", "sha256", "iter", "count",
             "carried", "exit", "unknown", "sload"):
        return False
    return all(mentions_only_params(x) for x in t[1:] if not isinstance(x, str))


# ------------------------------------------------------------------------------------------------ the basis
class DocBasis:
    """Every I30 basis element of one document (all three subforms), computed once."""

    def __init__(self, doc_rel: str, doc: dict, model: str, assignment_doc: dict, seeds: dict | None,
                 obstructions: list | None = None):
        from ..machine import document_programs
        self.rel, self.doc, self.model = doc_rel, doc, model
        m = (assignment_doc.get("models") or {}).get(model) or {}
        self.sorts = m.get("assignment") or {}
        self.provenance = m.get("provenance") or {}
        self.sites = [s for s in assignment_doc.get("sites") or [] if s.get("model") == model]
        self.unions = {k for k, v in self.sorts.items() if G.parse(v).head == "Union" and "." not in k
                       or (G.parse(v).head == "Union" and k.partition(".")[0] in X.family_table(doc))}
        self.seeds = seeds or {}
        self.tagger = Tagger(model, self.seeds, self.sorts, self.unions)
        self.programs = document_programs(doc)
        self.actions = {a["name"]: a for a in doc.get("actions") or []}
        self.obstructions = obstructions if obstructions is not None else X.obstructions(model, doc, assignment_doc)

    # ---------------------------------------------------------- realize (Z1)
    def check_id_of(self, action: str, rec: dict) -> str | None:
        for c in self.programs[action].checks():
            if c.section == "panics" and c.reach is rec:
                return c.id
            if c.section == "panics" and c.seq == rec.get("seq"):
                return c.id
        return None

    def realize(self) -> list[dict]:
        out = []
        real = X.realization_checks(self.doc)
        for s in self.sites:
            if s.get("obligation") != "sign":
                continue
            span = s["span"]
            h8 = s["id"].rsplit(":", 1)[1]
            node = s["expr"]
            hits = []
            if s.get("checked"):
                for a in s["entry_points"]:
                    p = real.get((a, X.ckey(node)))
                    if p is None or p.get("src") != span:
                        continue
                    cid = self.check_id_of(a, p)
                    if cid is None:
                        raise SortRuleError(f"site {s['id']}: {a}'s realization check has no check id")
                    hits.append({"action": a, "at": cid, "kind": "realization_check"})
            else:
                for o in s["occurrences"]:
                    hits.append({"action": o["action"], "at": o["where"], "kind": "occurrence"})
            hits = sorted(hits, key=lambda h: (h["action"], h["at"]))
            to = G.render(G.unsigned(G.parse(s["sort"])))
            out.append({"subform": "realize", "law_id": law_id("realize", span, h8),
                        "coercion_id": coercion_id(self.model, "realize", span, h8),
                        "basis": {"kind": "site", "site_id": s["id"], "model": self.model, "span": span,
                                  "expr": node},
                        "coercion": {"from": s["sort"], "to": to},
                        "entry_points": sorted({h["action"] for h in hits}), "hits": hits,
                        "site": s})
        return out

    # ---------------------------------------------------------- as_member (M1-M4)
    def union_writes(self, f: str) -> list[tuple[str, int, dict]]:
        """(action, i, write record) of every write of union family f (writes[i] of the action)."""
        out = []
        for a in sorted(self.actions):
            for i, w in enumerate(self.actions[a].get("writes") or []):
                if w.get("family") == f:
                    out.append((a, i, w))
        return out

    def member_function(self, f: str, src) -> object | None:
        """M1: the site's member function (tg of its fresh values), None when undefined."""
        tags = []
        for a, _i, w in self.union_writes(f):
            if w.get("src") != src:
                continue
            fv = fresh_value(w.get("value"), f)
            if fv is None:
                continue
            tags.append(self.tagger.tg(fv, a))
        if not tags:
            return None
        if len({canonical(t) for t in tags}) != 1:
            return None
        t = tags[0]
        if not mentions_only_params(t):
            return None
        return t

    def first_span(self, action: str, term) -> str | None:
        """M3: the src of the action's first record in walk order whose terms hold the term (a guard by its reach)."""
        for r in X.action_records(self.actions[action]):
            for _k, t in X.record_terms(r):
                if X.contains(t, term):
                    return r.src
        return None

    def as_member(self) -> list[dict]:
        out = []
        for f in sorted(self.unions):
            sort = self.sorts[f]
            members = sorted(G.render(m) for m in G.parse(sort).members)
            fns = {}
            for a, i, w in self.union_writes(f):
                src = w.get("src")
                if src not in fns:
                    fns[src] = self.member_function(f, src)
            for a, i, w in self.union_writes(f):
                fn = fns.get(w.get("src"))
                if fn is None:
                    continue
                val = w.get("value")
                cands = [val] if read_terms(val, f) and val in read_terms(val, f) else []
                cands += [b for b in copy_branches(val, f) if b in read_terms(b, f) and b not in cands]
                for R in cands:
                    if not (isinstance(R, list) and R and (R[0] in ("map", "index") or R[0] == "storage")):
                        continue
                    for p in _params_of(fn):
                        if p not in {x["name"] for x in self.actions[a].get("params") or []}:
                            raise SortRuleError(f"member read {X.ckey(R)} in {a}: the member function at {w.get('src')} "
                                                f"names parameter {p}, which {a} does not have")
                    span = self.first_span(a, R)
                    if span is None:
                        raise SortRuleError(f"member read {X.ckey(R)} in {a}: no record holds it")
                    h8 = x8(R)
                    out.append({"subform": "as_member", "law_id": law_id("as_member", span, h8),
                                "coercion_id": coercion_id(self.model, "as_member", span, h8),
                                "basis": {"kind": "member_read", "model": self.model, "action": a,
                                          "at": f"writes[{i}]", "site": w.get("src"), "span": span, "read": R,
                                          "registers": [f]},
                                "coercion": {"from": sort, "to": None, "members": members, "member_fn": fn},
                                "entry_points": [a], "hits": [{"action": a, "at": f"writes[{i}]",
                                                               "kind": "copy_write"}],
                                "write": w, "family": f})
        return out

    # ---------------------------------------------------------- reinterpret (C1-C3)
    def reinterpret(self) -> list[dict]:
        groups: dict = {}
        for o in self.obstructions:
            a = o["action"]
            uses = dict(X.storage_reads(o[X.KAPPA]))
            cursor = None
            for w in self.actions[a].get("writes") or []:
                v = w.get("value")
                if isinstance(v, list) and len(v) == 3 and v[0] == "+":
                    for p, b in ((v[1], v[2]), (v[2], v[1])):
                        if isinstance(p, list) and len(p) == 2 and p[0] == "param" and p[1] in o["constrains"]:
                            cursor = b
                            break
                if cursor is not None:
                    break
            if cursor is None:
                continue
            cvar = X.Walker(self.model, {"actions": []}, self.seeds).family_var(cursor)
            to = self.sorts.get(cvar) if cvar else None
            if to is None:
                continue
            for r in o["registers"]:
                if "key" not in uses.get(r["var"], []):
                    continue
                k = (r["var"], o["guard_span"])
                g = groups.setdefault(k, {"register": r["var"], "from": r["sort"], "to": to, "span": o["guard_span"],
                                          "cursor": {}, "obstructions": []})
                g["cursor"][a] = cursor
                g["obstructions"].append(o["id"])
        out = []
        for (reg, span), g in sorted(groups.items()):
            h8 = x8([reg, g["from"], g["to"]])
            eps = sorted(g["cursor"])
            out.append({"subform": "reinterpret", "law_id": law_id("reinterpret", span, h8),
                        "coercion_id": coercion_id(self.model, "reinterpret", span, h8),
                        "basis": {"kind": "coherence", "model": self.model, "register": reg, "from": g["from"],
                                  "to": g["to"], "span": span, "cursor": dict(sorted(g["cursor"].items())),
                                  "obstructions": sorted(g["obstructions"])},
                        "coercion": {"from": g["from"], "to": g["to"]},
                        "entry_points": eps,
                        "hits": [{"action": a, "at": "effects", "kind": "effects"} for a in eps]})
        return out

    def elements(self, subform: str | None = None) -> list[dict]:
        out = []
        for sub in SUBFORMS:
            if subform is not None and sub != subform:
                continue
            out += getattr(self, sub)()
        ids = [e["law_id"] for e in out]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise SortRuleError(f"two basis elements map to one law id: {dup}")
        return out


def _params_of(t) -> list:
    out = []

    def walk(x):
        if isinstance(x, list):
            if len(x) == 2 and x[0] == "param" and isinstance(x[1], str):
                out.append(x[1])
            for y in x:
                walk(y)
    walk(t)
    return sorted(set(out))


def hash_functions(doc: dict) -> list[str]:
    """The hash functions the document's model threads as law parameters: keccak256 when a term hashes with it or
    a mapping (or dynamic array) is accessed (its slot is a keccak256 of the key and the slot), sha256 when a term
    hashes with it."""
    uses = set()

    def walk(t):
        if isinstance(t, list):
            if t and t[0] in ("keccak256", "sha256"):
                uses.add(t[0])
            if t and t[0] in ("map",) or (t and t[0] == "index" and len(t) == 3):
                uses.add("keccak256")
            for x in t:
                walk(x)
        elif isinstance(t, dict):
            for x in t.values():
                walk(x)
    walk(doc.get("actions") or [])
    for f in X.family_table(doc).values():
        if f.get("kind") == "mapping":
            uses.add("keccak256")
    return [h for h in ("keccak256", "sha256") if h in uses]


# ------------------------------------------------------------------------------------------------ the law IR
def law_ir(e: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str, hashes: list[str]) -> dict:
    binders = [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"}]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    sub = e["subform"]
    notes = {"realize": "every hit of the realization of a signed difference is Some (Thm 6.18: the sign obligation "
                        "as a hole-free coercion premise at its site)",
             "as_member": "at the copy write, the union register's generated tag is the member the write assumes "
                          "(Prop 6.19: ghost-tag exactness at a read site)",
             "reinterpret": "the register the guard reads is the cursor the guard's requirement advances "
                            "(§7.3 obligation coherence as a coercion premise)"}[sub]
    return {"ir_version": "holon-ir/0.3", "law_id": e["law_id"], "milestone": milestone, "rule": RULE,
            "subform": sub, "rule_catalog_version": catalog_version, "facts": doc_rel, "facts_sha256": doc_sha,
            "notes": f"{notes}; coercion {e['coercion_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"coerce": e["coercion_id"], "on": {"var": "a"}, "from": {"var": "s"}},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(e: dict, doc_rel: str) -> dict:
    return {"law_id": e["law_id"], "rule": RULE, "subform": e["subform"], "facts": doc_rel, "basis": e["basis"],
            "coercion": e["coercion"], "entry_points": e["entry_points"],
            "hits": sorted(e["hits"], key=lambda h: (h["action"], h["at"]))}


def coerce_spec(e: dict) -> dict:
    """What the ref "coerce:<ID>" hashes."""
    return {"template": TEMPLATE, "template_version": TEMPLATE_VERSION, "subform": e["subform"], "basis": e["basis"],
            "hits": sorted(e["hits"], key=lambda h: (h["action"], h["at"]))}


# ------------------------------------------------------------------------------------------------ inputs
def load_basis(milestone: str, root: Path, doc_rel: str, assignment: dict | None = None,
               sidecar: str | None = None) -> DocBasis:
    """The basis of one document of a typed milestone, recomputed from the document, the frozen assignment and the
    sidecar's seeds (the coerce ref and the model generator use it; derive passes what it read)."""
    from ..sorts.typed_sidecar import load
    root = Path(root)
    doc = json.loads((root / doc_rel).read_text(encoding="utf-8"))
    if assignment is None:
        assignment = json.loads((root / "gen" / milestone / "sorts" / "assignment.json").read_text(encoding="utf-8"))
    seeds = {}
    try:
        sc = load(milestone, root, sidecar)
        seeds = json.loads(sc.seeds.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001: the coerce ref of a law whose sidecar is gone hashes as absent
        seeds = {}
    return DocBasis(doc_rel, doc, Path(doc_rel).stem, assignment, seeds)


def coerce_ref(cid: str, law: dict, root=None, sidecar: str | None = None) -> dict:
    """The object the ref "coerce:<ID>" hashes, recomputed from the document, the frozen assignment of the law's
    milestone and the sidecars (G2 needs no derive output)."""
    from .. import rules
    root = Path(root or rules.ROOT)
    try:
        b = load_basis(str(law.get("milestone")), root, str(law.get("facts")), sidecar=sidecar)
    except (OSError, ValueError, KeyError) as e:
        return {"absent": cid, "error": type(e).__name__}
    for e in b.elements():
        if e["coercion_id"] == cid:
            return coerce_spec(e)
    return {"absent": cid}


# ------------------------------------------------------------------------------------------------ producers
class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.sort.{subform}"

    def produce(self, ctx) -> list[tuple[dict, dict]]:
        out = []
        for d in getattr(ctx, "typed_documents", []) or []:
            b = d.basis
            for e in b.elements(self.subform):
                law = law_ir(e, ctx.milestone, d.rel, d.sha256, ctx.rule_catalog_version, hash_functions(d.facts))
                out.append((law, entry_of(e, d.rel)))
        return out


REALIZE = _Producer("realize")
AS_MEMBER = _Producer("as_member")
REINTERPRET = _Producer("reinterpret")
PRODUCERS = {"as_member": AS_MEMBER, "realize": REALIZE, "reinterpret": REINTERPRET}
