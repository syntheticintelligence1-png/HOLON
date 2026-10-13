"""I24 instruments, fixed at the I24 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_derive_par.py (rules P1-P12). This module writes those rules out a
second time, independently of holon/rules/par.py, so that the tests can decide what holon derive must emit:

- cycle_basis(diagram): the deterministic BFS spanning forest of rule P8 and its non-tree edges; the computation
  behind spec/M3/lib/par_basis.json (|E| - |V| + kappa per diagram);
- canonical(law), alpha_equivalent(a, b): rule P11 (alpha-equivalence, used by the back-test links and the dedupe);
- expected(facts_rel, facts, diagram, evidence, ...): the PAR basis elements, laws (statements) and reasons that
  rules P1-P10 give for one fact document, from its diagram (I11), the frozen evidence set (I14) and the layout
  algebra (holon.layout, the §10.2 instrument I14's rule E1 already reads).

Inputs only: the instrument reads the diagram, the evidence document and the facts it is given, the layout algebra
(holon.layout.layout) and the access roles of the I11 walker (holon.diagram.access.GENERIC_ROLES, LIB_KIND_ROLES).
It never imports holon.rules. For a fixture, the tests build the diagram and the evidence set with I11's and I14's
committed code (diagram_of, evidence_of below). This module serves the holon-facts 0.1/0.2 fixtures; the Morph
component, a linked codec document over the extracted documents (Q19), is computed by tests_m3/_i24x.py, which reuses
the P-rules written here.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests_m3._m3 import ROOT, canonical_json, load_json

FIX = ROOT / "tests_m3" / "fixtures"
CATALOG_VERSION = "holon-rules/1.1"
# the sub-forms in the order rule P11 dedupes them (an earlier sub-form keeps an equation a later one restates)
SUBFORMS = ("round_trip", "cross_component_codec", "branch", "weak", "domain_coherence", "totality", "cycle",
            "recompute", "consumer", "init")
TAG = {"round_trip": "rt", "cross_component_codec": "cc", "branch": "br", "weak": "weak",
       "domain_coherence": "dom", "totality": "tot", "cycle": "cy", "recompute": "rc", "consumer": "cs",
       "init": "init"}
CYCLE_KINDS = ("CODEC", "HASH", "TRANS")
PAIR_KINDS = ("CODEC", "CONS")
CONTAINER_ROLES = ("snoc", "set_at", "concat")
REASONS = ("branch_pair", "contradictory_pin", "explicit_option", "hash_edge", "inputs_differ", "mentions_input",
           "no_commitment", "no_common_version", "no_domain_predicate", "no_projection", "not_a_parallel_pair",
           "partial_inner", "reflexive", "relation", "stronger_evidence", "total_by_construction", "type_mismatch")
UNBOUNDED = {"kind": "unbounded"}


# ------------------------------------------------------------------ inputs for fixtures (I11 and I14 code)
def diagram_of(facts_path: Path, root: Path = ROOT) -> dict:
    from holon.diagram.build import build
    return build(Path(facts_path), root).to_json()


def evidence_of(facts_paths: list, assignment: dict, root: Path = ROOT, milestone: str = "T24") -> dict:
    from holon.diagram import evidence as EV
    diagrams = {Path(p).stem: diagram_of(Path(p), root) for p in facts_paths}
    return EV.build([Path(p) for p in facts_paths], root, diagrams=diagrams, assignment=assignment,
                    milestone=milestone)


# ------------------------------------------------------------------ versions (rule P0)
def versions(label) -> list[int] | None:
    """The diagram's version label as integers ("a..b" a range, "a,b" a list, "a" one); None when unlabelled."""
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
    """Rule P0: the intersection of the labels of the edges that carry one; None when none carries one (an
    unversioned instance); [] when the labels do not meet."""
    labels = [versions(e.get("version")) for e in edges]
    labels = [x for x in labels if x is not None]
    if not labels:
        return None
    out = set(labels[0])
    for x in labels[1:]:
        out &= set(x)
    return sorted(out)


# ------------------------------------------------------------------ alpha-equivalence (rule P11)
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


def _prop(p):
    for rel in ("eq", "neq"):
        if isinstance(p, dict) and rel in p and isinstance(p[rel], list) and len(p[rel]) == 2:
            a, b = sorted(p[rel], key=canonical_json)
            return {**p, rel: [a, b]}
    return p


def canonical(law: dict) -> dict:
    """The alpha-normal form of a law's statement (rule P11): binders renamed x0, x1, .. in binder order (holon-ir/0.1
    `forall` binders are universal), premises as a sorted set, each eq/neq with its two sides sorted, a conjunction as
    a sorted set, the scope (unbounded when absent), and the facts file the statement is about."""
    st = law["statement"]
    if "binders" in st:
        bs = [(b.get("q", "forall"), b["name"], b["type"]) for b in st["binders"]]
    else:
        bs = [("forall", b["name"], b["type"]) for b in st.get("forall", [])]
    m = {name: f"x{i}" for i, (_, name, _) in enumerate(bs)}
    assume = sorted({canonical_json(_prop(_rename(p, m))) for p in st.get("assume", [])})
    claim = _rename(st["claim"], m)
    if isinstance(claim, dict) and "all" in claim:
        claim = {"all": [json.loads(x) for x in sorted({canonical_json(_prop(c)) for c in claim["all"]})]}
    else:
        claim = _prop(claim)
    return {"facts": law.get("facts"), "binders": [[q, t] for q, _, t in bs],
            "assume": [json.loads(x) for x in assume], "claim": claim, "scope": st.get("scope") or UNBOUNDED}


def alpha_equivalent(a: dict, b: dict) -> bool:
    return canonical_json(canonical(a)) == canonical_json(canonical(b))


# ------------------------------------------------------------------ the cycle basis (rule P8)
def cycle_basis(diagram: dict) -> dict:
    """BFS spanning forest over the TRANS, CODEC and HASH edges: vertices are every carrier of the diagram, in sorted
    id order; a root is the smallest unvisited carrier; at each dequeued vertex its incident edges (either direction,
    a self-loop once) are examined in sorted edge-id order, an edge reaching an unvisited carrier enters the tree, every
    other edge examined for the first time (self-loops included) is a non-tree edge. kappa is the number of roots."""
    V = sorted(c["id"] for c in diagram["carriers"])
    E = sorted((e for e in diagram["edges"] if e["kind"] in CYCLE_KINDS), key=lambda e: e["id"])
    inc: dict[str, list] = {v: [] for v in V}
    for e in E:
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
    assert rank == len(non_tree), (diagram.get("model"), rank, non_tree)
    return {"E": len(E), "V": len(V), "kappa": kappa, "rank": rank, "edges": [e["id"] for e in E],
            "tree": tree, "non_tree": non_tree, "_parent": parent, "_edges": {e["id"]: e for e in E}}


def _to_root(v: str, parent: dict) -> list[tuple[dict, str, str]]:
    """Tree edges from v up to its root: (edge, child, parent vertex)."""
    out = []
    while v in parent:
        e, u = parent[v]
        out.append((e, v, u))
        v = u
    return out


def fundamental_cycle(cb: dict, eid: str) -> list[tuple[dict, bool]]:
    """The closed walk of non-tree edge eid: (edge, traversed forward) from eid's src through eid, then back through
    the tree. A self-loop is the one-edge walk."""
    e = cb["_edges"][eid]
    u, w = e["src"], e["tgt"]
    walk = [(e, True)]
    if u == w:
        return walk
    pu, pw = _to_root(u, cb["_parent"]), _to_root(w, cb["_parent"])
    vu = [u] + [p for _, _, p in pu]
    vw = [w] + [p for _, _, p in pw]
    lca = next(x for x in vw if x in vu)
    up_w = []   # w -> lca
    for edge, child, par in pw:
        if child == lca:
            break
        up_w.append((edge, edge["src"] == child))   # walking child -> parent: forward iff the edge leaves child
        if par == lca:
            break
    down_u = []   # lca -> u (reverse of u -> lca)
    for edge, child, par in pu:
        if child == lca:
            break
        down_u.append((edge, edge["src"] == par))   # walking parent -> child: forward iff the edge leaves the parent
        if par == lca:
            break
    return walk + up_w + list(reversed(down_u))


def parallel_walks(walk: list[tuple[dict, bool]]):
    """Rule P8: a cycle states an equation iff, as a closed walk, it has exactly one source (both incident edges point
    away) and one sink. Returns (source, P, Q) with P the walk containing the first edge (the non-tree edge), each a
    list of edges in forward order from the source to the sink, or None."""
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
    a = [walk[(s + j) % n][0] for j in range((k - s) % n)]                       # forward from the source
    b = [walk[(s - 1 - j) % n][0] for j in range((s - k) % n)]                    # the other way round
    P, Q = (a, b) if any(x is walk[0][0] for x in a) else (b, a)
    return verts[s], P, Q


# ------------------------------------------------------------------ facts expressions (rules P9, P10)
def subst(e, sub: dict):
    """holon.diagram.access.subst, written out: names in call, field, type and key positions are not variables."""
    if isinstance(e, bool) or isinstance(e, int):
        return e
    if isinstance(e, str):
        return sub.get(e, e)
    op, *a = e
    if op == "call":
        return ["call", a[0], *(subst(x, sub) for x in a[1:])]
    if op == "get":
        return ["get", subst(a[0], sub), a[1]]
    if op == "mk":
        return ["mk", a[0], {k: subst(v, sub) for k, v in a[1].items()}]
    if op == "with":
        return ["with", a[0], subst(a[1], sub), {k: subst(v, sub) for k, v in a[2].items()}]
    if op == "list":
        return ["list", a[0], *(subst(x, sub) for x in a[1:])]
    return [op, *(subst(x, sub) for x in a)]


def free_vars(e) -> set[str]:
    if isinstance(e, bool) or isinstance(e, int):
        return set()
    if isinstance(e, str):
        return {e}
    op, *a = e
    if op in ("call", "list"):
        return set().union(set(), *(free_vars(x) for x in a[1:]))
    if op == "get":
        return free_vars(a[0])
    if op == "mk":
        return set().union(set(), *(free_vars(v) for v in a[1].values()))
    if op == "with":
        return free_vars(a[1]).union(*(free_vars(v) for v in a[2].values()))
    return set().union(set(), *(free_vars(x) for x in a))


def lets(action: dict) -> dict:
    """The action's lets, in guard order, each with the earlier lets substituted."""
    sub: dict = {}
    for g in action.get("guards", []):
        if "let" in g:
            sub[g["let"]] = subst(g["expr"], sub)
    return sub


def calls(e, out: list | None = None) -> list:
    """Every call node of an expression, pre-order, left to right."""
    out = [] if out is None else out
    if isinstance(e, list) and e:
        if e[0] == "call":
            out.append(e)
            for x in e[2:]:
                calls(x, out)
        elif e[0] == "get":
            calls(e[1], out)
        elif e[0] == "mk":
            for v in e[2].values():
                calls(v, out)
        elif e[0] == "with":
            calls(e[2], out)
            for v in e[3].values():
                calls(v, out)
        elif e[0] == "list":
            for x in e[2:]:
                calls(x, out)
        else:
            for x in e[1:]:
                calls(x, out)
    return out


def contains(e, k) -> bool:
    return any(canonical_json(c) == canonical_json(k) for c in calls(e)) or canonical_json(e) == canonical_json(k)


class Doc:
    """A holon-facts/0.2 document: state, inputs, lets, the functions E4 may call, the access roles."""

    def __init__(self, facts: dict, lib_builtins: dict | None = None):
        from holon.diagram.access import GENERIC_ROLES, LIB_KIND_ROLES
        self.f = facts
        self.state = {s[0] for s in facts.get("state", [])} | {s[0] for s in facts.get("ghost_state", [])}
        self.params = set(facts.get("params", {}))
        self.defs = set(facts.get("defs", {}))
        self.lib = dict(lib_builtins or {})
        self.generic = dict(GENERIC_ROLES)
        self.lib_roles = {n: LIB_KIND_ROLES.get(b.get("kind")) for n, b in self.lib.items()}
        self.actions = {a["name"]: a for a in facts.get("actions", [])}

    def role(self, name: str) -> str | None:
        return self.generic.get(name) or self.lib_roles.get(name)

    def inputs(self, a: str) -> dict[str, str]:
        return {n: t for n, t in self.actions[a]["inputs"]}

    def qualifying(self, call, a: str, f: str | None = None) -> bool:
        """I14's E4 qualifying call (lets substituted): a facts def or library builtin (never a generic builtin, never a
        shadow projection es_<field>), n >= 1 arguments, none mentioning a state field, one at least an input."""
        name, args = call[1], call[2:]
        if f is not None and name != f:
            return False
        if name in self.generic or name.startswith("es_") or not (name in self.defs or name in self.lib):
            return False
        if not args:
            return False
        fv = [free_vars(x) for x in args]
        ins = set(self.inputs(a))
        return not any(v & self.state for v in fv) and any(v & ins for v in fv)

    def effect(self, a: str, field: str):
        return subst(self.actions[a]["effects"][field], lets(self.actions[a]))

    def stored_values(self, e, k) -> list:
        """Rule P9: descend from an effect through record literals ["mk", T, {..}] and calls whose access role builds
        a container (snoc, set_at, concat), into the parts that contain k; the first other node that contains k is a
        stored value. Distinct values (canonical JSON), sorted."""
        out = []

        def walk(n):
            if not contains(n, k):
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
        return [json.loads(x) for x in sorted({canonical_json(v) for v in out})]


# ------------------------------------------------------------------ statements
def _binder_name(carrier: dict) -> str:
    return "h" if carrier.get("product") else ("b" if carrier.get("key_space") == "byte" else "x")


def _version_premise(var: str, carrier: dict, facts: dict, v: int | None) -> list:
    if v is None or "version" not in (carrier.get("product") or []):
        return []
    width = next(f["width"] for t in facts["types"].values() if t.get("kind") == "record"
                 for f in t["fields"] if f["name"] == "version")
    return [{"eq": [{"field": "version", "of": {"var": var}}, {"bytes": "0x" + v.to_bytes(width, "big").hex()}]}]


def _pin(var: str, field: str, vals: list[int]) -> dict:
    return {"eq": [{"field": field, "of": {"var": var}}, {"bytes": "0x" + bytes(vals).hex()}]}


def _call(fn: str, arg) -> dict:
    return {"call": fn, "args": [arg]}


def _codec_statement(var: str, carrier: dict, assume: list, lhs, rhs) -> dict:
    return {"binders": [{"q": "forall", "name": var, "type": carrier["base_type"]}], "assume": assume,
            "claim": {"eq": [lhs, rhs]}, "scope": dict(UNBOUNDED)}


def _expr(e, action: str | None = None, on="a", frm=None, bind: dict | None = None) -> dict:
    t = {"expr": e, "from": frm if frm is not None else {"var": "s"}}
    if action is not None:
        t["action"] = action
        t["on"] = {"var": on}
    if bind:
        t["bind"] = bind
    return t


def _machine_statement(p: str, lhs, rhs, oracle_binders) -> dict:
    return {"binders": [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"}]
            + [{"q": "forall", "name": n, "type": t} for n, t in oracle_binders],
            "assume": [{"eq": [{"fn": f"is_{p}", "args": [{"var": "a"}]}, {"bool": True}]},
                       {"eq": [{"fn": "last_ok", "args": [{"step": {"var": "a"}, "from": {"var": "s"}}]},
                               {"bool": True}]}],
            "claim": {"eq": [lhs, rhs]}, "scope": dict(UNBOUNDED)}


# ------------------------------------------------------------------ the PAR derivation of one document
class _Out:
    def __init__(self, facts_rel: str, model: str):
        self.facts_rel, self.model = facts_rel, model
        self.laws: dict[str, dict] = {}
        self.canon: dict[bytes, str] = {}
        self.basis: list[dict] = []

    def entry(self, subform: str, key: dict, version, candidates: list[tuple[str, dict]], reason: str | None = None):
        laws, dups, reflexive = [], {}, 0
        for lid, st in candidates:
            sides = st["claim"].get("eq") if isinstance(st.get("claim"), dict) else None
            if isinstance(sides, list) and len(sides) == 2 and canonical_json(sides[0]) == canonical_json(sides[1]):
                reflexive += 1   # rule P0: [t, t] holds by reflexivity (Lemma 6.2) and states nothing
                continue
            c = canonical_json(canonical({"facts": self.facts_rel, "statement": st}))
            if c in self.canon:
                dups[lid] = self.canon[c]
                continue
            if lid in self.laws:
                raise AssertionError(f"two basis elements give the law id {lid}")
            self.canon[c] = lid
            self.laws[lid] = {"subform": subform, "statement": st, "model": self.model}
            laws.append(lid)
        if reflexive and not laws and not dups and reason is None:
            reason = "reflexive"
        self.basis.append({"subform": subform, "model": self.model, "key": key, "version": version,
                           "laws": laws, "duplicates": dups, "reason": reason})


def expected(facts_rel: str, facts: dict, diagram: dict, evidence: dict, oracle_binders=(),
             lib_builtins: dict | None = None) -> dict:
    """Rules P1-P10 applied to one fact document. Returns {"laws": {law_id: {"subform", "statement", "model"}},
    "basis": [par_basis entries], "cycle": cycle_basis summary}."""
    model = diagram["model"]
    out = _Out(facts_rel, model)
    carriers = {c["id"]: c for c in diagram["carriers"]}
    edges = {e["id"]: e for e in diagram["edges"]}
    atoms = [a for a in evidence["atoms"] if a["model"] == model]
    v01 = facts.get("facts_version") == "holon-facts/0.1"
    tag = TAG

    def fn(eid):
        return edges[eid]["model_fn"]

    # P1 round trip: E1 inverse atoms
    for a in sorted((a for a in atoms if a["level"] == "E1" and a["via"]["kind"] == "inverse"), key=lambda a: a["id"]):
        e, d, v = edges[a["p"]], edges[a["q"]], a["via"]["version"]
        car = carriers[e["src"]]
        proj = [p for p in car.get("projections", []) if p["to"] == d["tgt"]]
        key = {"atom": a["id"]}
        if not proj:
            out.entry("round_trip", key, v, [], "no_projection")
            continue
        var = _binder_name(car)
        vp = _version_premise(var, car, facts, v)
        from holon.layout import layout
        lay = layout(facts, e["model_fn"], v)
        getters = {g["name"]: g for g in facts["functions"][d["model_fn"]]["getters"]}
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
        base = f"L_par_{tag['round_trip']}_{e['model_fn']}_{d['model_fn']}_v{v}"
        cands = [(base, _codec_statement(var, car, vp, lhs, rhs))]
        if pins and not bad:
            cands.append((base + "_pinned", _codec_statement(var, car, vp + pins, lhs, rhs)))
        out.entry("round_trip", key, v, cands, "contradictory_pin" if bad else None)

    # P2 cross-component codec agreement: E1 common-decoder atoms
    for a in sorted((a for a in atoms if a["level"] == "E1" and a["via"]["kind"] == "common_decoder"),
                    key=lambda a: a["id"]):
        p, q, v = edges[a["p"]], edges[a["q"]], a["via"]["version"]
        car = carriers[p["src"]]
        var = _binder_name(car)
        vp = _version_premise(var, car, facts, v)
        from holon.layout import layout
        lp, lq = layout(facts, p["model_fn"], v), layout(facts, q["model_fn"], v)
        pins, bad = [], False
        for t in facts["types"].values():
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
        base = f"L_par_{tag['cross_component_codec']}_{p['model_fn']}_{q['model_fn']}_v{v}"
        cands = [(base, _codec_statement(var, car, vp, lhs, rhs))]
        if pins and not bad:
            cands.append((base + "_pinned", _codec_statement(var, car, vp + pins, lhs, rhs)))
        out.entry("cross_component_codec", {"atom": a["id"]}, v, cands, "contradictory_pin" if bad else None)

    def versioned(subform: str, key: dict, es: list[dict], car: dict, var: str, lhs, rhs, base: str):
        cv = common_versions(es)
        if cv == []:
            out.entry(subform, key, None, [], "no_common_version")
            return
        if cv is not None and "version" in (car.get("product") or []):
            for v in cv:
                out.entry(subform, key, v, [(f"{base}_v{v}", _codec_statement(
                    var, car, _version_premise(var, car, facts, v), lhs, rhs))])
            return
        out.entry(subform, key, None, [(base, _codec_statement(var, car, [], lhs, rhs))])

    # P3 branch agreement: parallel CODEC edges citing the same code
    codecs = sorted((e for e in diagram["edges"] if e["kind"] == "CODEC"), key=lambda e: e["id"])
    branch_pairs = set()
    for i, p in enumerate(codecs):
        for q in codecs[i + 1:]:
            if (p["src"], p["tgt"]) == (q["src"], q["tgt"]) and canonical_json(p.get("source")) == canonical_json(
                    q.get("source")) and p.get("source"):
                branch_pairs.add((p["id"], q["id"]))
                car = carriers[p["src"]]
                var = _binder_name(car)
                versioned("branch", {"p": p["id"], "q": q["id"]}, [p, q], car, var, _call(p["model_fn"], {"var": var}),
                          _call(q["model_fn"], {"var": var}), f"L_par_{tag['branch']}_{p['model_fn']}_{q['model_fn']}")

    # P4 PAR-weak: E6 atoms between CODEC or CONS edges with nothing stronger
    for a in sorted((a for a in atoms if a["level"] == "E6"), key=lambda a: a["id"]):
        p, q = edges[a["p"]], edges[a["q"]]
        key = {"atom": a["id"]}
        if p["kind"] not in PAIR_KINDS:
            out.entry("weak", key, None, [], "relation")
            continue
        if (p["id"], q["id"]) in branch_pairs:
            out.entry("weak", key, None, [], "branch_pair")
            continue
        car = carriers[p["src"]]
        var = _binder_name(car)
        cv = common_versions([p, q])
        if cv == []:
            out.entry("weak", key, None, [], "no_common_version")
            continue
        vs = cv if (cv is not None and "version" in (car.get("product") or [])) else [None]
        for v in vs:
            stronger = [b for b in atoms if b["level"] != "E6" and {b["p"], b["q"]} == {p["id"], q["id"]}
                        and (v is None or b["via"].get("version") in (None, v))]
            if stronger:
                out.entry("weak", key, v, [], "stronger_evidence")
                continue
            lid = f"L_par_{tag['weak']}_{p['model_fn']}_{q['model_fn']}" + (f"_v{v}" if v is not None else "")
            out.entry("weak", key, v, [(lid, _codec_statement(var, car, _version_premise(var, car, facts, v),
                                                              _call(p["model_fn"], {"var": var}),
                                                              _call(q["model_fn"], {"var": var})))])

    # P5 domain coherence at each interface carrier
    for c in sorted(diagram["carriers"], key=lambda c: c["id"]):
        doms = sorted(c.get("domains") or [])
        if not c.get("interface") or len(doms) < 2:
            continue
        var = _binder_name(c)
        for i, p1 in enumerate(doms):
            for p2 in doms[i + 1:]:
                out.entry("domain_coherence", {"carrier": c["id"], "p": p1, "q": p2}, None,
                          [(f"L_par_{tag['domain_coherence']}_{p1}_{p2}",
                            _codec_statement(var, c, [], _call(p1, {"var": var}), _call(p2, {"var": var})))])

    # P6 totality on R^ext
    for e in sorted((e for e in diagram["edges"] if e["kind"] in ("CODEC", "CONS")), key=lambda e: e["id"]):
        car = carriers.get(e["src"], {})
        if not car.get("interface"):
            continue
        key = {"edge": e["id"]}
        if e.get("partial"):
            out.entry("totality", key, None, [], "explicit_option")
        elif e["kind"] == "CONS":
            out.entry("totality", key, None, [], "total_by_construction")
        elif isinstance(e.get("domain"), str):
            var = _binder_name(car)
            out.entry("totality", key, None, [(f"L_par_{tag['totality']}_{e['model_fn']}", _codec_statement(
                var, car, [], _call(e["domain"], {"var": var}), {"bool": True}))])
        else:
            out.entry("totality", key, None, [], "no_domain_predicate")

    # P8 cycles
    cb = cycle_basis(diagram)
    for eid in cb["non_tree"]:
        walk = fundamental_cycle(cb, eid)
        key = {"edge": eid}
        kinds = {e["kind"] for e, _ in walk}
        if "TRANS" in kinds:
            out.entry("cycle", key, None, [], "relation")
            continue
        if "HASH" in kinds:
            out.entry("cycle", key, None, [], "hash_edge")
            continue
        pw = parallel_walks(walk)
        if pw is None:
            out.entry("cycle", key, None, [], "not_a_parallel_pair")
            continue
        src, P, Q = pw
        if any(e.get("partial") for e in P[:-1] + Q[:-1]):
            out.entry("cycle", key, None, [], "partial_inner")
            continue
        if bool(P[-1].get("partial")) != bool(Q[-1].get("partial")):
            out.entry("cycle", key, None, [], "type_mismatch")
            continue
        car = carriers[src]
        var = _binder_name(car)

        def term(path):
            t = {"var": var}
            for e in path:
                t = _call(e["model_fn"], t)
            return t
        versioned("cycle", key, [e for e, _ in walk], car, var, term(P), term(Q),
                  f"L_par_{tag['cycle']}_{edges[eid]['model_fn']}")

    if not v01:
        D = Doc(facts, lib_builtins)

        # P9 recomputation: E4 atoms
        for a in sorted((a for a in atoms if a["level"] == "E4"), key=lambda a: a["id"]):
            p, q, f = a["p"].split(".", 1)[1], a["q"].split(".", 1)[1], a["via"]["fn"]
            qlets = lets(D.actions[q])
            cs = []
            for pos in a["via"]["recomputed"]:
                head, rest = pos.split(".", 1)
                if head == "effects":
                    ex = D.actions[q]["effects"][rest]
                else:
                    i = int(head[len("guards["):-1])
                    g = D.actions[q]["guards"][i]
                    ex = g["require"] if rest == "require" else g["expr"]
                for c in calls(subst(ex, qlets)):
                    if D.qualifying(c, q, f):
                        cs.append(c)
            cs = [json.loads(x) for x in sorted({canonical_json(c) for c in cs})]
            for pos in a["via"]["stored"]:
                field = pos.split(".", 1)[1]
                eff = D.effect(p, field)
                ks = [c for c in calls(eff) if D.qualifying(c, p, f)]
                vs = []
                for k in ks:
                    vs += D.stored_values(eff, k)
                vs = [json.loads(x) for x in sorted({canonical_json(v) for v in vs})]
                pin, qin = D.inputs(p), D.inputs(q)
                cands, reason = [], None
                pairs = [(v, c) for v in vs for c in cs]
                for n, (v, c) in enumerate(pairs, 1):
                    need = free_vars(c) & set(qin)
                    if any(pin.get(x) != qin[x] for x in need):
                        reason = "inputs_differ"
                        continue
                    lid = f"L_par_{tag['recompute']}_{p}_{q}_{f}_{field}" + (f"_{n}" if len(pairs) > 1 else "")
                    cands.append((lid, _machine_statement(p, _expr(v, p), _expr(c, p), oracle_binders)))
                out.entry("recompute", {"atom": a["id"], "field": field}, None, cands, reason if not cands else None)

        # P10 consumer agreement: CONS edges against the stored commitments of their input
        for cname, c in sorted(facts.get("consumers", {}).items()):
            i = c["input"]
            for p in [x["name"] for x in facts["actions"]]:
                if i not in D.inputs(p):
                    continue
                found = False
                for field in D.actions[p]["effects"]:
                    eff = D.effect(p, field)
                    ks = [k for k in calls(eff) if D.qualifying(k, p) and any(i in free_vars(x) for x in k[2:])]
                    ks = [json.loads(x) for x in sorted({canonical_json(k) for k in ks})]
                    cands = []
                    pairs = [(k, v) for k in ks for v in D.stored_values(eff, k)]
                    for n, (k, v) in enumerate(pairs, 1):
                        lid = f"L_par_{tag['consumer']}_{cname}_{p}_{k[1]}_{field}" + (f"_{n}" if len(pairs) > 1 else "")
                        cands.append((lid, _machine_statement(
                            p, _expr(v, p), _expr(k, p, bind={i: {"fn": cname, "args": [{"var": "a"}]}}),
                            oracle_binders)))
                    if cands:
                        found = True
                        out.entry("consumer", {"consumer": f"CONS.{cname}", "action": f"TRANS.{p}", "field": field},
                                  None, cands)
                if not found:
                    out.entry("consumer", {"consumer": f"CONS.{cname}", "action": f"TRANS.{p}", "field": None}, None,
                              [], "no_commitment")

        # P7 initialization coherence: E3 equations at S0
        for a in sorted((a for a in atoms if a["level"] == "E3"), key=lambda a: a["id"]):
            act = a["p"].split(".", 1)[1]
            i = int(a["via"]["where"][len("guards["):].split("]")[0])
            sub = lets(D.actions[act])
            L, R = (subst(x, sub) for x in a["via"]["operands"])
            if (free_vars(L) | free_vars(R)) & set(D.inputs(act)):
                out.entry("init", {"atom": a["id"]}, None, [], "mentions_input")
                continue
            s0 = {"s0": {}}
            st = {"binders": [{"q": "forall", "name": n, "type": t} for n, t in oracle_binders], "assume": [],
                  "claim": {"eq": [_expr(L, frm=s0), _expr(R, frm=s0)]}, "scope": dict(UNBOUNDED)}
            out.entry("init", {"atom": a["id"]}, None, [(f"L_par_{tag['init']}_{act}_g{i}", st)])

    order = {s: n for n, s in enumerate(SUBFORMS)}
    basis = sorted(out.basis, key=lambda b: (order[b["subform"]], canonical_json(b["key"]),
                                             -1 if b["version"] is None else b["version"]))
    cycle = {k: v for k, v in cb.items() if not k.startswith("_")}
    return {"laws": out.laws, "basis": basis, "cycle": cycle}


def lib_builtins_of(facts_path: Path, root: Path = ROOT) -> dict:
    """The target-library builtins of a fact document (holon.gen.targetlib.lib_files: spec/lib, then <facts>/../lib)."""
    from holon.gen.targetlib import lib_files
    out: dict = {}
    for p in lib_files(Path(facts_path), root):
        out.update(load_json(p).get("builtins", {}))
    return out


# ------------------------------------------------------------------ honesty: names generic code must not hold
# facts-schema and IR vocabulary that generic code may quote even where a target happens to use the word; the last
# line is the contract's own vocabulary: the keys of an I14 E4 atom's via ("stored", "recomputed"), the totality tag of
# rule P0's law ids ("tot") and a key of P12's cycle_rank ("kappa"), which the rollup also happens to use as names (a
# let "stored", a let "tot", the DISCH guard "kappa"), so a correct par.py must be able to quote them
GENERIC_WORDS = {"status", "value", "count", "next", "len", "append", "view", "off", "cap", "ctx", "proof", "site",
                 "sites", "expr", "kind", "via", "at", "action", "hits", "guards", "effects", "body", "bool", "nth",
                 "version", "fields", "source", "domain", "domains", "input", "inputs", "state", "consumers",
                 "params", "types", "functions", "getters", "ops", "rules", "projections", "data", "log",
                 "Bool", "Byte", "Bytes", "Fields", "Nat", "Obs", "State", "Act", "List",
                 "stored", "recomputed", "tot", "kappa"}
# the hand documents M0-M2 derived from: never an M3 input (Q19); their names are target names all the same, so the
# no-special-casing test also catches a hand name written into the new code
TARGET_DOCS = ("facts/morph_header.json", "spec/M1/facts/morph_rollup.json", "spec/M1/facts/morph_batchdata.json")


def _names_of(f: dict) -> set[str]:
    names: set[str] = set()
    if f.get("facts_version") == "holon-facts/0.1":
        names |= set(f.get("functions", {})) | set(f.get("types", {}))
        for t in f.get("types", {}).values():
            names |= {fld["name"] for fld in t.get("fields", []) if isinstance(fld, dict)}
        for fn in f.get("functions", {}).values():
            names |= {g["name"] for g in fn.get("getters", [])}
        return names
    names |= set(f.get("observers", {})) | set(f.get("defs", {})) | set(f.get("migrations", {}))
    names |= set(f.get("consumers", {})) | set(f.get("params", {}) if isinstance(f.get("params"), dict) else [])
    names |= {s[0] for s in f.get("state", [])} | {s[0] for s in f.get("ghost_state", []) if isinstance(s, list)}
    for t, ty in (f.get("types") or {}).items():
        names.add(t)
        for fld in (ty.get("fields", []) if isinstance(ty, dict) else []):
            names.add(fld[0] if isinstance(fld, list) else fld.get("name"))
    for a in f.get("actions", []):
        names.add(a["name"])
        names |= {x for x, *_ in a.get("inputs", [])}
        names |= {g["let"] for g in a.get("guards", []) if "let" in g}
    for d in f.get("defs", {}).values():
        names |= {x for x, *_ in d.get("params", [])}
    return names


def target_names() -> set[str]:
    """Every name the hand documents of M0-M2, their libraries and the I24 facts fixtures give, derived (never
    hand-listed); tests_m3/_i24x.py::target_names adds the extracted documents and the linked fixture."""
    names: set[str] = set()
    for rel in TARGET_DOCS:
        names |= _names_of(load_json(ROOT / rel))
    for lib in sorted((ROOT / "spec").glob("**/*.lib.json")):
        names |= set(load_json(lib).get("builtins", {}))
    for p in sorted(FIX.glob("par_*.facts.json")):
        names |= _names_of(load_json(p))
    return {n for n in names if isinstance(n, str) and n}


def basis_rows(basis: list[dict]) -> list[tuple]:
    """A par_basis list as comparable rows (rule P12's entry fields)."""
    return sorted((b["subform"], b["model"], canonical_json(b["key"]).decode(), b["version"], tuple(sorted(b["laws"])),
                   canonical_json(b.get("duplicates") or {}).decode(), b["reason"]) for b in basis)
