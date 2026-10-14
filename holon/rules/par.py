"""Rule PAR, all sub-forms (whitepaper §5.1 parallel-path commutation and domain coherence, §3.2 fundamental cycles,
Thm 6.4 use, §10.3 steps 1-3, §8.4 PAR rows, Def 4.1-4.5, App. E PAR row, §11.3 sub-forms; BUILD_PLAN I24). The
contract is the docstring of tests_m3/test_derive_par.py: rules P0-P12 over a diagram and its evidence atoms, and
rule X8 over a linked codec component.

One producer per sub-form, run in SUBFORMS order (rule P11's dedupe order) over one document at a time:

  round_trip             P1   E1 inverse atoms (encoder, decoder, version)
  cross_component_codec  P2   E1 common-decoder atoms (two encoders, one decoder, version)
  branch                 P3   parallel CODEC edges that cite one function
  weak                   P4   E6 atoms with nothing stronger (an E6-only REFUTED law is an intent question)
  domain_coherence       P5   pairs of domain predicates of an interface carrier
  totality               P6   CODEC and CONS edges out of an interface carrier
  cycle                  P8   the fundamental cycles of a deterministic BFS spanning forest
  recompute              P9   E4 atoms (stored by one action, recomputed by another)
  consumer               P10  CONS edges against the commitments stored from their input
  init                   P7   E3 equations at the initial state

A document is a holon-facts/0.1 codec document, a holon-facts/0.2 machine document or a linked codec document
(holon.diagram.linked, rule X8: P1 and P2 adapted to single-read decoders, X8c's tag premise for versioned laws over
the linked carrier). Every name in a law comes from the document's diagram, its evidence atoms and the document
itself; nothing here names a target, and law ids are a deterministic function of (rule, sub-form, basis element).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from ..diagram.access import GENERIC_ROLES, LIB_KIND_ROLES, free_vars, subst

SUBFORMS = ("round_trip", "cross_component_codec", "branch", "weak", "domain_coherence", "totality", "cycle",
            "recompute", "consumer", "init")
TAG = {"round_trip": "rt", "cross_component_codec": "cc", "branch": "br", "weak": "weak",
       "domain_coherence": "dom", "totality": "tot", "cycle": "cy", "recompute": "rc", "consumer": "cs",
       "init": "init"}
CYCLE_KINDS = ("CODEC", "HASH", "TRANS")
PAIR_KINDS = ("CODEC", "CONS")
CONTAINER_ROLES = ("snoc", "set_at", "concat")
REASONS = ("branch_pair", "contradictory_pin", "explicit_option", "hash_edge", "inputs_differ", "mentions_input",
           "no_commitment", "no_common_version", "no_domain_predicate", "no_projection", "no_version_premise",
           "not_a_parallel_pair", "partial_inner", "reflexive", "relation", "stronger_evidence",
           "total_by_construction", "type_mismatch")
UNBOUNDED = {"kind": "unbounded"}
FACTS01, FACTS02, LINKED = "holon-facts/0.1", "holon-facts/0.2", "holon-linked/0.1"


class ParError(ValueError):
    """A basis element that cannot be derived (holon derive exits 3, naming it)."""


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# ====================================================================== versions (P0)
def versions(label) -> list[int] | None:
    """A diagram version label as integers ("a..b" a range, "a,b" a list, "a" one); None when unlabelled."""
    if label is None:
        return None
    out: list[int] = []
    for part in str(label).split(","):
        if ".." in part:
            a, b = part.split("..")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def common_versions(edges: list[dict]) -> list[int] | None:
    """The intersection of the labels of the edges that carry one; None when none carries one (unversioned); []
    when they do not meet."""
    labels = [x for x in (versions(e.get("version")) for e in edges) if x is not None]
    if not labels:
        return None
    out = set(labels[0])
    for x in labels[1:]:
        out &= set(x)
    return sorted(out)


# ====================================================================== alpha-equivalence (P11)
def _rename(t, m: dict):
    if isinstance(t, list):
        return [_rename(x, m) for x in t]
    if not isinstance(t, dict):
        return t
    out = {}
    for k, v in t.items():
        if k in ("var", "app") and isinstance(v, str):
            out[k] = m.get(v, v)
        elif k == "cf" and isinstance(v, dict):
            out[k] = {kk: (m.get(vv, vv) if kk == "fn" and isinstance(vv, str) else _rename(vv, m))
                      for kk, vv in v.items()}
        else:
            out[k] = _rename(v, m)
    return out


def _sides_sorted(p):
    for rel in ("eq", "neq"):
        if isinstance(p, dict) and rel in p and isinstance(p[rel], list) and len(p[rel]) == 2:
            return {**p, rel: sorted(p[rel], key=canonical_json)}
    return p


def canonical(law: dict) -> dict:
    """The alpha-normal form of a law's statement (P11): binders renamed x0, x1, .. in binder order, premises as a
    sorted set, each eq/neq with its sides sorted by canonical JSON, a conjunction as a sorted set, the scope
    (unbounded when absent), and the facts file the statement is about."""
    st = law["statement"]
    if "binders" in st:
        bs = [(b.get("q", "forall"), b["name"], b["type"]) for b in st["binders"]]
    else:
        bs = [("forall", b["name"], b["type"]) for b in st.get("forall", [])]
    m = {name: f"x{i}" for i, (_, name, _) in enumerate(bs)}
    assume = sorted({canonical_json(_sides_sorted(_rename(p, m))) for p in st.get("assume", [])})
    claim = _rename(st["claim"], m)
    if isinstance(claim, dict) and "all" in claim:
        claim = {"all": [json.loads(x) for x in sorted({canonical_json(_sides_sorted(c)) for c in claim["all"]})]}
    else:
        claim = _sides_sorted(claim)
    return {"facts": law.get("facts"), "binders": [[q, t] for q, _, t in bs], "assume": [json.loads(x) for x in assume],
            "claim": claim, "scope": st.get("scope") or dict(UNBOUNDED)}


def alpha_equivalent(a: dict, b: dict) -> bool:
    return canonical_json(canonical(a)) == canonical_json(canonical(b))


# ====================================================================== the cycle basis (P8)
def cycle_basis(diagram: dict) -> dict:
    """The deterministic BFS spanning forest over the TRANS, CODEC and HASH edges (carriers in sorted id order, a root
    the smallest unvisited carrier, a dequeued carrier's incident edges in sorted edge-id order, either direction, a
    self-loop once) and its non-tree edges; kappa is the number of roots."""
    V = sorted(c["id"] for c in diagram["carriers"])
    E = sorted((e for e in diagram["edges"] if e["kind"] in CYCLE_KINDS), key=lambda e: e["id"])
    inc: dict[str, list] = {v: [] for v in V}
    for e in E:
        if e["src"] not in inc or e["tgt"] not in inc:
            raise ParError(f"{e['id']}: an endpoint is not a carrier of the diagram")
        inc[e["src"]].append(e)
        if e["tgt"] != e["src"]:
            inc[e["tgt"]].append(e)
    for v in V:
        inc[v].sort(key=lambda e: e["id"])
    seen_v, seen_e, tree, non_tree, parent = set(), set(), [], [], {}
    kappa = 0
    for root in V:
        if root in seen_v:
            continue
        kappa += 1
        seen_v.add(root)
        queue = [root]
        while queue:
            u = queue.pop(0)
            for e in inc[u]:
                if e["id"] in seen_e:
                    continue
                seen_e.add(e["id"])
                w = e["tgt"] if e["src"] == u else e["src"]
                if e["src"] != e["tgt"] and w not in seen_v:
                    seen_v.add(w)
                    tree.append(e["id"])
                    parent[w] = (e, u)
                    queue.append(w)
                else:
                    non_tree.append(e["id"])
    rank = len(E) - len(V) + kappa
    if rank != len(non_tree):
        raise ParError(f"{diagram.get('model')}: {len(non_tree)} non-tree edges, but |E| - |V| + kappa = {rank}")
    return {"E": len(E), "V": len(V), "kappa": kappa, "rank": rank, "tree": tree, "non_tree": non_tree,
            "_parent": parent, "_edges": {e["id"]: e for e in E}}


def _to_root(v: str, parent: dict) -> list[tuple[dict, str, str]]:
    out = []
    while v in parent:
        e, u = parent[v]
        out.append((e, v, u))
        v = u
    return out


def fundamental_cycle(cb: dict, eid: str) -> list[tuple[dict, bool]]:
    """The closed walk of a non-tree edge (u -> w): the edge, then the tree path from w back to u; each step (edge,
    traversed forward). A self-loop is the one-edge walk."""
    e = cb["_edges"][eid]
    u, w = e["src"], e["tgt"]
    walk = [(e, True)]
    if u == w:
        return walk
    pu, pw = _to_root(u, cb["_parent"]), _to_root(w, cb["_parent"])
    vu = [u] + [p for _, _, p in pu]
    vw = [w] + [p for _, _, p in pw]
    lca = next(x for x in vw if x in vu)
    up_w = []
    for edge, child, par in pw:
        if child == lca:
            break
        up_w.append((edge, edge["src"] == child))
        if par == lca:
            break
    down_u = []
    for edge, child, par in pu:
        if child == lca:
            break
        down_u.append((edge, edge["src"] == par))
        if par == lca:
            break
    return walk + up_w + list(reversed(down_u))


def parallel_walks(walk: list[tuple[dict, bool]]):
    """A cycle states an equation iff, as a closed walk, it has exactly one source and one sink. Returns (source, P,
    Q), P the walk through the non-tree edge, each the list of its edges from the source to the sink; else None."""
    n = len(walk)
    verts = []
    v = walk[0][0]["src"] if walk[0][1] else walk[0][0]["tgt"]
    for e, fwd in walk:
        verts.append(v)
        v = e["tgt"] if fwd else e["src"]
    sources = [i for i in range(n) if (not walk[i - 1][1]) and walk[i][1]]
    sinks = [i for i in range(n) if walk[i - 1][1] and not walk[i][1]]
    if len(sources) != 1 or len(sinks) != 1:
        return None
    s, k = sources[0], sinks[0]
    a = [walk[(s + j) % n][0] for j in range((k - s) % n)]
    b = [walk[(s - 1 - j) % n][0] for j in range((s - k) % n)]
    P, Q = (a, b) if any(x is walk[0][0] for x in a) else (b, a)
    return verts[s], P, Q


# ====================================================================== documents
@dataclass
class ParDoc:
    """One document PAR derives over: its law "facts" path, the document, its diagram and evidence atoms; for a
    holon-facts/0.2 document the oracle parameters its model threads ((name, Fn<A,B>), sidecar order) and its target
    library builtins."""
    rel: str
    facts: dict
    diagram: dict
    atoms: list
    oracle_binders: list = field(default_factory=list)
    lib_builtins: dict = field(default_factory=dict)

    @property
    def model(self) -> str:
        return self.diagram["model"]

    @property
    def kind(self) -> str:
        if self.facts.get("linked_version") == LINKED:
            return LINKED
        return self.facts.get("facts_version")


class Acc:
    """The laws, duplicates and basis elements of one document, in production order (P11's dedupe)."""

    def __init__(self, doc: ParDoc):
        self.doc = doc
        self.laws: dict[str, dict] = {}
        self.canon: dict[bytes, str] = {}
        self.basis: list[dict] = []
        self.branch_pairs: set = set()

    def entry(self, subform: str, key: dict, version, candidates: list, reason: str | None = None) -> None:
        laws, dups, reflexive = [], {}, 0
        for lid, st, notes in candidates:
            sides = st["claim"].get("eq") if isinstance(st.get("claim"), dict) else None
            if isinstance(sides, list) and len(sides) == 2 and canonical_json(sides[0]) == canonical_json(sides[1]):
                reflexive += 1   # P0: [t, t] holds by reflexivity (Lemma 6.2) and states nothing
                continue
            c = canonical_json(canonical({"facts": self.doc.rel, "statement": st}))
            if c in self.canon:
                dups[lid] = self.canon[c]
                continue
            if lid in self.laws:
                raise ParError(f"two basis elements give the law id {lid}")
            self.canon[c] = lid
            self.laws[lid] = {"subform": subform, "statement": st, "notes": notes,
                              "basis": {"subform": subform, "model": self.doc.model, "key": key, "version": version},
                              "entry_points": _entry_points(st)}
            laws.append(lid)
        if reflexive and not laws and not dups and reason is None:
            reason = "reflexive"
        if reason is not None and reason not in REASONS:
            raise ParError(f"unknown reason {reason}")
        self.basis.append({"subform": subform, "model": self.doc.model, "key": key, "version": version,
                           "laws": laws, "duplicates": dups, "reason": reason})


def _entry_points(st: dict) -> list[str]:
    """The action a P9/P10 law steps (its is_<A> premise), else []."""
    out = []
    for p in st.get("assume", []):
        eq = p.get("eq") if isinstance(p, dict) else None
        if isinstance(eq, list) and isinstance(eq[0], dict) and str(eq[0].get("fn", "")).startswith("is_"):
            out.append(eq[0]["fn"][3:])
    return sorted(set(out))


# ====================================================================== statements
def _bname(carrier: dict) -> str:
    return "h" if carrier.get("product") else ("b" if carrier.get("key_space") == "byte" else "x")


def _hex(vals: list[int]) -> str:
    return "0x" + bytes(vals).hex()


def _call(fn: str, arg) -> dict:
    return {"call": fn, "args": [arg]}


def _stmt(binders: list[tuple[str, str]], assume: list, lhs, rhs) -> dict:
    return {"binders": [{"q": "forall", "name": n, "type": t} for n, t in binders], "assume": assume,
            "claim": {"eq": [lhs, rhs]}, "scope": dict(UNBOUNDED)}


def _pin(var: str, fld: str, vals: list[int]) -> dict:
    return {"eq": [{"field": fld, "of": {"var": var}}, {"bytes": _hex(vals)}]}


def version_premise(doc: ParDoc, var: str, carrier_id: str, v) -> list:
    """P0: a record carrier with a field named version gets, at version v, the premise version = v (the field's width
    in bytes); anything else gets none."""
    if v is None:
        return []
    car = next((c for c in doc.diagram["carriers"] if c["id"] == carrier_id), {})
    if "version" not in (car.get("product") or []):
        return []
    if doc.kind == LINKED:
        rec = doc.facts["carriers"].get(carrier_id) or {}
        widths = [f["width"] for f in rec.get("fields", []) if f["name"] == "version"]
    else:
        widths = [f["width"] for t in doc.facts["types"].values() if t.get("kind") == "record"
                  for f in t.get("fields", []) if isinstance(f, dict) and f.get("name") == "version"]
    if not widths:
        raise ParError(f"{carrier_id}: a version field without a width")
    return [_pin(var, "version", list(v.to_bytes(widths[0], "big")))]


def tag_decoder(doc: ParDoc) -> str | None:
    """X8c: the component's one unversioned decoder whose read is (tag_index, 1); None when none or several."""
    fs = doc.facts["functions"]
    hits = sorted(n for n, f in fs.items() if f["kind"] == "decoder" and f["versions"] is None
                  and (f["read"]["offset"], f["read"]["width"]) == (doc.facts["tag_index"], 1))
    return hits[0] if len(hits) == 1 else None


def scope_of(doc: ParDoc, car: dict, cv):
    """How a versioned instance over source carrier car is scoped (P0, X8c): (versions, premise(var, v), reason)."""
    if cv is None:
        return [None], (lambda var, v: []), None
    if "version" in (car.get("product") or []):
        return cv, (lambda var, v: version_premise(doc, var, car["id"], v)), None
    if doc.kind == LINKED and car["id"] == doc.facts["linked_carrier"]:
        t = tag_decoder(doc)
        if t is None:
            return [], None, "no_version_premise"
        return cv, (lambda var, v: [{"eq": [_call(t, {"var": var}), {"some": {"bytes": _hex([v])}}]}]), None
    return [None], (lambda var, v: []), None


def _carriers(doc: ParDoc) -> dict:
    return {c["id"]: c for c in doc.diagram["carriers"]}


def _edges(doc: ParDoc) -> dict:
    return {e["id"]: e for e in doc.diagram["edges"]}


def _layout01(doc: ParDoc, fn: str, v: int) -> list[list]:
    from ..layout import layout
    return layout(doc.facts, fn, v)


def _layout_linked(doc: ParDoc, fn: str, v) -> list[list] | None:
    f = doc.facts["functions"][fn]
    if f.get("versions") is None:
        return next(iter(f["layouts"].values()))
    return f["layouts"].get(str(v))


def _note(sub: str, what: str) -> str:
    return f"PAR {sub.replace('_', ' ')} (holon.rules.par): {what}"


# ====================================================================== P1 round trip
def produce_round_trip(doc: ParDoc, acc: Acc) -> None:
    carriers, edges = _carriers(doc), _edges(doc)
    sub, tag = "round_trip", TAG["round_trip"]
    for a in sorted((a for a in doc.atoms if a["level"] == "E1" and a["via"]["kind"] == "inverse"),
                    key=lambda a: a["id"]):
        e, d, v = edges[a["p"]], edges[a["q"]], a["via"]["version"]
        car = carriers[e["src"]]
        key = {"atom": a["id"]}
        base = f"L_par_{tag}_{e['model_fn']}_{d['model_fn']}_v{v}"
        note = _note(sub, f"{d['model_fn']} inverts {e['model_fn']} at version {v} (E1 atom {a['id']})")
        if doc.kind == LINKED:   # X8 (P1 over single-read decoders): the projection is the field the decoder recovers
            vp = version_premise(doc, "h", e["src"], v)
            st = _stmt([("h", e["src"])], vp, _call(d["model_fn"], _call(e["model_fn"], {"var": "h"})),
                       {"some": {"field": a["via"]["fields"][0], "of": {"var": "h"}}})
            acc.entry(sub, key, v, [(base, st, note)])
            continue
        proj = [p for p in car.get("projections", []) if p["to"] == d["tgt"]]
        if not proj:
            acc.entry(sub, key, v, [], "no_projection")
            continue
        var = _bname(car)
        vp = version_premise(doc, var, car["id"], v)
        lay = _layout01(doc, e["model_fn"], v)
        getters = {g["name"]: g for g in doc.facts["functions"][d["model_fn"]]["getters"]}
        pins, bad = [], False
        for name in a["via"]["not_recovered"]:
            g = getters[name]
            cells = lay[g["offset"]:g["offset"] + g["width"]]
            if len(cells) == g["width"] and all(c[0] == "const" for c in cells):
                p = _pin(var, name, [c[1] for c in cells])
                if vp and name == "version":
                    bad = bad or p != vp[0]
                    continue
                pins.append(p)
        lhs = _call(d["model_fn"], _call(e["model_fn"], {"var": var}))
        rhs = {"some": _call(proj[0]["model_fn"], {"var": var})}
        cands = [(base, _stmt([(var, car["base_type"])], vp, lhs, rhs), note)]
        if pins and not bad:
            cands.append((base + "_pinned", _stmt([(var, car["base_type"])], vp + pins, lhs, rhs),
                          note + "; pinned: the getters it does not recover are constants of the layout"))
        acc.entry(sub, key, v, cands, "contradictory_pin" if bad else None)


# ====================================================================== P2 cross-component codec agreement
def produce_cross_component_codec(doc: ParDoc, acc: Acc) -> None:
    if doc.kind == LINKED:
        return _cross_linked(doc, acc)
    carriers, edges = _carriers(doc), _edges(doc)
    sub, tag = "cross_component_codec", TAG["cross_component_codec"]
    for a in sorted((a for a in doc.atoms if a["level"] == "E1" and a["via"]["kind"] == "common_decoder"),
                    key=lambda a: a["id"]):
        p, q, v = edges[a["p"]], edges[a["q"]], a["via"]["version"]
        car = carriers[p["src"]]
        var = _bname(car)
        vp = version_premise(doc, var, car["id"], v)
        lp, lq = _layout01(doc, p["model_fn"], v), _layout01(doc, q["model_fn"], v)
        pins, bad = [], False
        for t in doc.facts["types"].values():
            if t.get("kind") != "record":
                continue
            for fld in t["fields"]:
                name, w = fld["name"], fld["width"]
                for la, lb in ((lp, lq), (lq, lp)):
                    pos = [next((i for i, c in enumerate(la) if c == ["field", name, k]), None) for k in range(w)]
                    if None in pos or any(c[:2] == ["field", name] for c in lb):
                        continue
                    other = [lb[i] if i < len(lb) else ["unknown"] for i in pos]
                    if all(c[0] == "const" for c in other):
                        pn = _pin(var, name, [c[1] for c in other])
                        if vp and name == "version":
                            bad = bad or pn != vp[0]
                        else:
                            pins.append(pn)
        lhs, rhs = _call(p["model_fn"], {"var": var}), _call(q["model_fn"], {"var": var})
        base = f"L_par_{tag}_{p['model_fn']}_{q['model_fn']}_v{v}"
        note = _note(sub, f"{p['model_fn']} and {q['model_fn']} at version {v}, both inverted by "
                          f"{a['via']['decoder']} (E1 atom {a['id']})")
        cands = [(base, _stmt([(var, car["base_type"])], vp, lhs, rhs), note)]
        if pins and not bad:
            cands.append((base + "_pinned", _stmt([(var, car["base_type"])], vp + pins, lhs, rhs),
                          note + "; pinned: a field one layout writes whole where the other holds constants"))
        acc.entry(sub, {"atom": a["id"]}, v, cands, "contradictory_pin" if bad else None)


def _cross_linked(doc: ParDoc, acc: Acc) -> None:
    """X8 (P2 over a component): one basis element per (p, q, version) with common-decoder atoms; two binders when the
    encoders' sources are two carriers, related by one correspondence premise per pair of recovered fields."""
    edges = _edges(doc)
    sub, tag = "cross_component_codec", TAG["cross_component_codec"]
    groups: dict[tuple, list] = {}
    for a in sorted((a for a in doc.atoms if a["level"] == "E1" and a["via"]["kind"] == "common_decoder"),
                    key=lambda a: a["id"]):
        groups.setdefault((a["p"], a["q"], a["via"]["version"]), []).append(a)
    for (pid, qid, v), group in sorted(groups.items()):
        p, q = edges[pid], edges[qid]
        hp, hq = "h", ("k" if q["src"] != p["src"] else "h")
        binders = [(hp, p["src"])] + ([(hq, q["src"])] if hq != hp else [])
        vp = version_premise(doc, hp, p["src"], v) + (version_premise(doc, hq, q["src"], v) if hq != hp else [])
        corr, seen = [], set()
        for a in sorted(group, key=lambda a: a["via"]["decoder"]):
            fp, fq = a["via"]["fields"]
            if (fp, fq) in seen:
                continue
            seen.add((fp, fq))
            if hq != hp or fp != fq:
                corr.append({"eq": [{"field": fp, "of": {"var": hp}}, {"field": fq, "of": {"var": hq}}]})
        lp, lq = _layout_linked(doc, p["model_fn"], v), _layout_linked(doc, q["model_fn"], v)
        pins, bad = [], False
        for var, src, la, lb in ((hp, p["src"], lp, lq), (hq, q["src"], lq, lp)):
            for fld in doc.facts["carriers"][src]["fields"]:
                name, w = fld["name"], fld["width"]
                pos = [next((i for i, c in enumerate(la) if c == ["field", name, k]), None) for k in range(w)]
                if None in pos:
                    continue
                other = [lb[i] if i < len(lb) else ["unknown"] for i in pos]
                if not all(c[0] == "const" for c in other):
                    continue
                pn = _pin(var, name, [c[1] for c in other])
                own = version_premise(doc, var, src, v)
                if name == "version" and own:
                    bad = bad or pn != own[0]
                    continue
                pins.append(pn)
        lhs, rhs = _call(p["model_fn"], {"var": hp}), _call(q["model_fn"], {"var": hq})
        base = f"L_par_{tag}_{p['model_fn']}_{q['model_fn']}_v{v}"
        decs = ", ".join(sorted({a["via"]["decoder"] for a in group}))
        note = _note(sub, f"{p['model_fn']} and {q['model_fn']} at version {v}, decoded by {decs} (E1 common-decoder "
                          "atoms)")
        cands = [(base, _stmt(binders, vp + corr, lhs, rhs), note)]
        if pins and not bad:
            cands.append((base + "_pinned", _stmt(binders, vp + corr + pins, lhs, rhs),
                          note + "; pinned: a field one layout writes where the other holds constants"))
        acc.entry(sub, {"p": pid, "q": qid}, v, cands, "contradictory_pin" if bad else None)


# ====================================================================== P3 branch agreement
def _versioned(doc: ParDoc, acc: Acc, subform: str, key: dict, es: list[dict], car: dict, var: str, lhs, rhs,
               base: str, note: str) -> None:
    cv = common_versions(es)
    if cv == []:
        acc.entry(subform, key, None, [], "no_common_version")
        return
    vs, prem, why = scope_of(doc, car, cv)
    if why:
        acc.entry(subform, key, None, [], why)
        return
    if vs != [None]:
        for v in vs:
            acc.entry(subform, key, v, [(f"{base}_v{v}", _stmt([(var, car["base_type"])], prem(var, v), lhs, rhs),
                                         f"{note}; at version {v}")])
        return
    acc.entry(subform, key, None, [(base, _stmt([(var, car["base_type"])], [], lhs, rhs), note)])


def produce_branch(doc: ParDoc, acc: Acc) -> None:
    carriers = _carriers(doc)
    sub, tag = "branch", TAG["branch"]
    codecs = sorted((e for e in doc.diagram["edges"] if e["kind"] == "CODEC"), key=lambda e: e["id"])
    for i, p in enumerate(codecs):
        for q in codecs[i + 1:]:
            if (p["src"], p["tgt"]) != (q["src"], q["tgt"]) or not p.get("source") \
                    or canonical_json(p.get("source")) != canonical_json(q.get("source")):
                continue
            if doc.kind == LINKED:   # X8: a component has one edge per function or patch
                raise ParError(f"{p['id']} and {q['id']} cite one function")
            acc.branch_pairs.add((p["id"], q["id"]))
            car = carriers[p["src"]]
            var = _bname(car)
            _versioned(doc, acc, sub, {"p": p["id"], "q": q["id"]}, [p, q], car, var, _call(p["model_fn"], {"var": var}),
                       _call(q["model_fn"], {"var": var}), f"L_par_{tag}_{p['model_fn']}_{q['model_fn']}",
                       _note(sub, f"{p['model_fn']} and {q['model_fn']} are two paths of one function"))


# ====================================================================== P4 PAR-weak
def produce_weak(doc: ParDoc, acc: Acc) -> None:
    carriers, edges = _carriers(doc), _edges(doc)
    sub, tag = "weak", TAG["weak"]
    for a in sorted((a for a in doc.atoms if a["level"] == "E6"), key=lambda a: a["id"]):
        p, q = edges[a["p"]], edges[a["q"]]
        key = {"atom": a["id"]}
        if p["kind"] not in PAIR_KINDS:
            acc.entry(sub, key, None, [], "relation")
            continue
        if (p["id"], q["id"]) in acc.branch_pairs:
            acc.entry(sub, key, None, [], "branch_pair")
            continue
        car = carriers[p["src"]]
        var = _bname(car)
        cv = common_versions([p, q])
        if cv == []:
            acc.entry(sub, key, None, [], "no_common_version")
            continue
        vs, prem, why = scope_of(doc, car, cv)
        if why:
            acc.entry(sub, key, None, [], why)
            continue
        for v in vs:
            stronger = [b for b in doc.atoms if b["level"] != "E6" and {b["p"], b["q"]} == {p["id"], q["id"]}
                        and (v is None or b["via"].get("version") in (None, v))]
            if stronger:
                acc.entry(sub, key, v, [], "stronger_evidence")
                continue
            lid = f"L_par_{tag}_{p['model_fn']}_{q['model_fn']}" + (f"_v{v}" if v is not None else "")
            note = _note(sub, f"{p['model_fn']} and {q['model_fn']} share only name tokens {a['via'].get('tokens')} "
                              f"(E6 atom {a['id']})" + (f"; at version {v}" if v is not None else ""))
            acc.entry(sub, key, v, [(lid, _stmt([(var, car["base_type"])], prem(var, v),
                                                _call(p["model_fn"], {"var": var}),
                                                _call(q["model_fn"], {"var": var})), note)])


# ====================================================================== P5 domain coherence
def produce_domain_coherence(doc: ParDoc, acc: Acc) -> None:
    sub, tag = "domain_coherence", TAG["domain_coherence"]
    for c in sorted(doc.diagram["carriers"], key=lambda c: c["id"]):
        doms = sorted(c.get("domains") or [])
        if not c.get("interface") or len(doms) < 2:
            continue
        var = _bname(c)
        for i, p1 in enumerate(doms):
            for p2 in doms[i + 1:]:
                acc.entry(sub, {"carrier": c["id"], "p": p1, "q": p2}, None,
                          [(f"L_par_{tag}_{p1}_{p2}", _stmt([(var, c["base_type"])], [], _call(p1, {"var": var}),
                                                            _call(p2, {"var": var})),
                            _note(sub, f"{p1} and {p2} are domains of the interface carrier {c['id']} (R^ext)"))])


# ====================================================================== P6 totality
def produce_totality(doc: ParDoc, acc: Acc) -> None:
    carriers = _carriers(doc)
    sub, tag = "totality", TAG["totality"]
    for e in sorted((e for e in doc.diagram["edges"] if e["kind"] in PAIR_KINDS), key=lambda e: e["id"]):
        car = carriers.get(e["src"], {})
        if not car.get("interface"):
            continue
        key = {"edge": e["id"]}
        if e.get("partial"):
            acc.entry(sub, key, None, [], "explicit_option")
        elif e["kind"] == "CONS":
            acc.entry(sub, key, None, [], "total_by_construction")
        elif isinstance(e.get("domain"), str):
            var = _bname(car)
            acc.entry(sub, key, None, [(f"L_par_{tag}_{e['model_fn']}", _stmt([(var, car["base_type"])], [],
                                                                            _call(e["domain"], {"var": var}),
                                                                            {"bool": True}),
                                        _note(sub, f"{e['model_fn']} is defined on all of R^ext of {car['id']} "
                                                   f"(its domain {e['domain']})"))])
        else:
            acc.entry(sub, key, None, [], "no_domain_predicate")


# ====================================================================== P8 cycles
def produce_cycle(doc: ParDoc, acc: Acc) -> None:
    carriers, edges = _carriers(doc), _edges(doc)
    sub, tag = "cycle", TAG["cycle"]
    cb = cycle_basis(doc.diagram)
    acc.cycle = {k: v for k, v in cb.items() if not k.startswith("_")}
    for eid in cb["non_tree"]:
        walk = fundamental_cycle(cb, eid)
        key = {"edge": eid}
        kinds = {e["kind"] for e, _ in walk}
        if "TRANS" in kinds:
            acc.entry(sub, key, None, [], "relation")
            continue
        if "HASH" in kinds:
            acc.entry(sub, key, None, [], "hash_edge")
            continue
        pw = parallel_walks(walk)
        if pw is None:
            acc.entry(sub, key, None, [], "not_a_parallel_pair")
            continue
        src, P, Q = pw
        if any(e.get("partial") for e in P[:-1] + Q[:-1]):
            acc.entry(sub, key, None, [], "partial_inner")
            continue
        if bool(P[-1].get("partial")) != bool(Q[-1].get("partial")):
            acc.entry(sub, key, None, [], "type_mismatch")
            continue
        car = carriers[src]
        var = _bname(car)

        def term(path, var=var):
            t = {"var": var}
            for e in path:
                t = _call(e["model_fn"], t)
            return t
        _versioned(doc, acc, sub, key, [e for e, _ in walk], car, var, term(P), term(Q),
                   f"L_par_{tag}_{edges[eid]['model_fn']}",
                   _note(sub, f"the fundamental cycle of {eid}: {' ; '.join(e['id'] for e in P)} against "
                              f"{' ; '.join(e['id'] for e in Q)} from {src}"))


# ====================================================================== facts expressions (P7, P9, P10)
def _calls(e, out: list | None = None) -> list:
    out = [] if out is None else out
    if isinstance(e, list) and e:
        if e[0] == "call":
            out.append(e)
            for x in e[2:]:
                _calls(x, out)
        elif e[0] == "get":
            _calls(e[1], out)
        elif e[0] == "mk":
            for v in e[2].values():
                _calls(v, out)
        elif e[0] == "with":
            _calls(e[2], out)
            for v in e[3].values():
                _calls(v, out)
        elif e[0] == "list":
            for x in e[2:]:
                _calls(x, out)
        else:
            for x in e[1:]:
                _calls(x, out)
    return out


def _contains(e, k) -> bool:
    ck = canonical_json(k)
    return any(canonical_json(c) == ck for c in _calls(e)) or canonical_json(e) == ck


def _distinct(xs: list) -> list:
    return [json.loads(x) for x in sorted({canonical_json(x) for x in xs})]


def lets(action: dict) -> dict:
    """An action's lets, in guard order, each with the earlier lets substituted."""
    sub: dict = {}
    for g in action.get("guards", []):
        if "let" in g:
            sub[g["let"]] = subst(g["expr"], sub)
    return sub


class Machine02:
    """What P7, P9 and P10 read of a holon-facts/0.2 document."""

    def __init__(self, facts: dict, lib_builtins: dict):
        self.f = facts
        self.state = {s[0] for s in facts.get("state", [])} | {s[0] for s in facts.get("ghost_state", [])
                                                              if isinstance(s, list)}
        self.defs = set(facts.get("defs", {}))
        self.lib = dict(lib_builtins or {})
        self.lib_roles = {n: LIB_KIND_ROLES.get(b.get("kind")) for n, b in self.lib.items()}
        self.actions = {a["name"]: a for a in facts.get("actions", [])}

    def role(self, name: str) -> str | None:
        return GENERIC_ROLES.get(name) or self.lib_roles.get(name)

    def inputs(self, a: str) -> dict[str, str]:
        return {n: t for n, t in self.actions[a]["inputs"]}

    def qualifying(self, call, a: str, f: str | None = None) -> bool:
        """I14's E4 qualifying call (lets substituted): a facts def or library builtin (never a generic builtin or a
        shadow projection es_<field>), at least one argument, none mentioning a state field, one an input of a."""
        name, args = call[1], call[2:]
        if f is not None and name != f:
            return False
        if name in GENERIC_ROLES or name.startswith("es_") or not (name in self.defs or name in self.lib):
            return False
        if not args:
            return False
        fv = [free_vars(x) for x in args]
        ins = set(self.inputs(a))
        return not any(v & self.state for v in fv) and any(v & ins for v in fv)

    def effect(self, a: str, fld: str):
        return subst(self.actions[a]["effects"][fld], lets(self.actions[a]))

    def stored_values(self, e, k) -> list:
        """P9: descend from an effect through record literals and container-building calls into the parts that
        contain k; the first other node that contains k is a stored value (distinct, sorted)."""
        out = []

        def walk(n):
            if not _contains(n, k):
                return
            if isinstance(n, list) and n and n[0] == "mk":
                for v in n[2].values():
                    walk(v)
                return
            if (isinstance(n, list) and n and n[0] == "call" and canonical_json(n) != canonical_json(k)
                    and self.role(n[1]) in CONTAINER_ROLES):
                for x in n[2:]:
                    walk(x)
                return
            out.append(n)
        walk(e)
        return _distinct(out)


def _expr(e, action: str | None = None, on: str = "a", frm=None, bind: dict | None = None) -> dict:
    t = {"expr": e, "from": frm if frm is not None else {"var": "s"}}
    if action is not None:
        t["action"] = action
        t["on"] = {"var": on}
    if bind:
        t["bind"] = bind
    return t


def _machine_stmt(p: str, lhs, rhs, oracle_binders) -> dict:
    return {"binders": [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"}]
            + [{"q": "forall", "name": n, "type": t} for n, t in oracle_binders],
            "assume": [{"eq": [{"fn": f"is_{p}", "args": [{"var": "a"}]}, {"bool": True}]},
                       {"eq": [{"fn": "last_ok", "args": [{"step": {"var": "a"}, "from": {"var": "s"}}]},
                               {"bool": True}]}],
            "claim": {"eq": [lhs, rhs]}, "scope": dict(UNBOUNDED)}


# ====================================================================== P9 recomputation
def produce_recompute(doc: ParDoc, acc: Acc) -> None:
    if doc.kind != FACTS02:
        return
    D = Machine02(doc.facts, doc.lib_builtins)
    sub, tag = "recompute", TAG["recompute"]
    for a in sorted((a for a in doc.atoms if a["level"] == "E4"), key=lambda a: a["id"]):
        p, q, f = a["p"].split(".", 1)[1], a["q"].split(".", 1)[1], a["via"]["fn"]
        qlets = lets(D.actions[q])
        cs = []
        for pos in a["via"]["recomputed"]:
            head, rest = pos.split(".", 1)
            if head == "effects":
                ex = D.actions[q]["effects"][rest]
            else:
                g = D.actions[q]["guards"][int(head[len("guards["):-1])]
                ex = g["require"] if rest == "require" else g["expr"]
            cs += [c for c in _calls(subst(ex, qlets)) if D.qualifying(c, q, f)]
        cs = _distinct(cs)
        for pos in a["via"]["stored"]:
            fld = pos.split(".", 1)[1]
            eff = D.effect(p, fld)
            vs = []
            for k in (c for c in _calls(eff) if D.qualifying(c, p, f)):
                vs += D.stored_values(eff, k)
            vs = _distinct(vs)
            pin, qin = D.inputs(p), D.inputs(q)
            cands, reason = [], None
            pairs = [(v, c) for v in vs for c in cs]
            for n, (v, c) in enumerate(pairs, 1):
                if any(pin.get(x) != qin[x] for x in free_vars(c) & set(qin)):
                    reason = "inputs_differ"
                    continue
                lid = f"L_par_{tag}_{p}_{q}_{f}_{fld}" + (f"_{n}" if len(pairs) > 1 else "")
                cands.append((lid, _machine_stmt(p, _expr(v, p), _expr(c, p), doc.oracle_binders),
                              _note(sub, f"what {p} stores in {fld} is what {q} recomputes with {f} from the same "
                                         f"inputs (E4 atom {a['id']})")))
            acc.entry(sub, {"atom": a["id"], "field": fld}, None, cands, reason if not cands else None)


# ====================================================================== P10 consumer agreement
def produce_consumer(doc: ParDoc, acc: Acc) -> None:
    if doc.kind != FACTS02:
        return
    D = Machine02(doc.facts, doc.lib_builtins)
    sub, tag = "consumer", TAG["consumer"]
    for cname, c in sorted((doc.facts.get("consumers") or {}).items()):
        i = c["input"]
        for p in [x["name"] for x in doc.facts["actions"]]:
            if i not in D.inputs(p):
                continue
            found = False
            for fld in D.actions[p]["effects"]:
                eff = D.effect(p, fld)
                ks = _distinct([k for k in _calls(eff) if D.qualifying(k, p) and any(i in free_vars(x) for x in k[2:])])
                pairs = [(k, v) for k in ks for v in D.stored_values(eff, k)]
                cands = []
                for n, (k, v) in enumerate(pairs, 1):
                    lid = f"L_par_{tag}_{cname}_{p}_{k[1]}_{fld}" + (f"_{n}" if len(pairs) > 1 else "")
                    cands.append((lid, _machine_stmt(p, _expr(v, p),
                                                     _expr(k, p, bind={i: {"fn": cname, "args": [{"var": "a"}]}}),
                                                     doc.oracle_binders),
                                  _note(sub, f"the commitment {p} stores in {fld} agrees with {k[1]} applied to what "
                                             f"the consumer {cname} receives")))
                if cands:
                    found = True
                    acc.entry(sub, {"consumer": f"CONS.{cname}", "action": f"TRANS.{p}", "field": fld}, None, cands)
            if not found:
                acc.entry(sub, {"consumer": f"CONS.{cname}", "action": f"TRANS.{p}", "field": None}, None, [],
                          "no_commitment")


# ====================================================================== P7 initialization coherence
def produce_init(doc: ParDoc, acc: Acc) -> None:
    if doc.kind != FACTS02:
        return
    D = Machine02(doc.facts, doc.lib_builtins)
    sub, tag = "init", TAG["init"]
    for a in sorted((a for a in doc.atoms if a["level"] == "E3"), key=lambda a: a["id"]):
        act = a["p"].split(".", 1)[1]
        i = int(a["via"]["where"][len("guards["):].split("]")[0])
        sub_l = lets(D.actions[act])
        L, R = (subst(x, sub_l) for x in a["via"]["operands"])
        if (free_vars(L) | free_vars(R)) & set(D.inputs(act)):
            acc.entry(sub, {"atom": a["id"]}, None, [], "mentions_input")
            continue
        s0 = {"s0": {}}
        st = {"binders": [{"q": "forall", "name": n, "type": t} for n, t in doc.oracle_binders], "assume": [],
              "claim": {"eq": [_expr(L, frm=s0), _expr(R, frm=s0)]}, "scope": dict(UNBOUNDED)}
        acc.entry(sub, {"atom": a["id"]}, None,
                  [(f"L_par_{tag}_{act}_g{i}", st,
                    _note(sub, f"the equation {act} requires at guard {i} (E3 atom {a['id']}) holds in the initial "
                               "state"))])


PRODUCERS = {"round_trip": produce_round_trip, "cross_component_codec": produce_cross_component_codec,
             "branch": produce_branch, "weak": produce_weak, "domain_coherence": produce_domain_coherence,
             "totality": produce_totality, "cycle": produce_cycle, "recompute": produce_recompute,
             "consumer": produce_consumer, "init": produce_init}


def derive_document(doc: ParDoc, producers: dict | None = None) -> Acc:
    """Run the producers (default every sub-form's) over one document, in SUBFORMS order."""
    producers = PRODUCERS if producers is None else producers
    acc = Acc(doc)
    acc.cycle = None
    for sub in SUBFORMS:
        if sub in producers:
            producers[sub](doc, acc)
    if acc.cycle is None:
        cb = cycle_basis(doc.diagram)
        acc.cycle = {k: v for k, v in cb.items() if not k.startswith("_")}
    return acc


def basis_sort_key(b: dict) -> tuple:
    """P12: par_basis sorted by (SUBFORMS order, canonical JSON of key, version with null first), then model."""
    order = {s: n for n, s in enumerate(SUBFORMS)}
    return (order[b["subform"]], canonical_json(b["key"]), -1 if b["version"] is None else b["version"], b["model"])
