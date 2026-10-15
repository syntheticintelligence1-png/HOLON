"""SORT-site predicates in Lean (I43 rules L1, L2, L4, L11; kind machine_oracle), the site laws' proofs.

Lean's own reading of rules R8-R10 of the SORT-site rule, written again from the facts document, the derivation
entry of each site (its site id, span, subtraction and hits) and the realization-check reasons of the sort sites
sidecar; it imports neither holon.sorts nor any Bend emitter (rule L1).

Hit points (R8-R10). The site's occurrences are the evaluation positions of its subtraction, as written, whose span
is the site's: in a definition body (span: the definition's src span, else <model>:<definition>), or in an action's
guard or effect (span: the guard's or the effects' src span, else the action's, narrowed to the smallest require of
the action inside it that checks minuend >= subtrahend; without a span, <model>:<action>). An action site is hit at
its occurrence, unless a require g of the action before it (any require, for an effect occurrence) is a realization
check of the site: g's own span is the site's span and the text of its reason is one of the sidecar's
realization-check reasons. Then the hit is at the first such g, evaluated just before g's require (R8). A
definition site is hit at every guard or effect of an action whose expression calls a definition whose evaluation
reaches the site's definition (R9). Evaluation order (R10): guards in order up to the first failing require,
effects only when every require holds; ["?", c, x, y] evaluates x only when c holds and y only when it fails, && and
|| short-circuit, a definition call evaluates its body with the arguments bound, any other node evaluates every
operand. hit_points must equal the derivation entry's "hits": section and theorems refuse a site where they differ.

The declarations (inside namespace Model), for a site with x = site_name(site id) without its "site_":

  ro_<x>       the site's raw obligation: subtrahend <= minuend of its subtraction, a Bool function (Nat.ble) of the
               subtraction's free variables in order of first occurrence (Nat for an operand of + or -, the
               parameter's type for an argument of a facts definition call), with the model's own reading of each
               facts definition; it takes the oracle parameters first when the subtraction reaches one;
  gd_<x>_<f>   per definition f whose evaluation reaches a definition site: the conjunction, over the evaluations in
               f's body that reach the site (the subtraction itself: ro_<x> of its operands; a call of such a
               definition: its gd_<x>_<g>), of each under its path condition (bif c then .. else true);
  gs_<x>_<a>   per entry point a: a's guards walked as the decision chain walks them (a let binds; a require that
               fails stops the action: true) and, at each hit, the obligations of what the hit evaluates under their
               path conditions, conjoined with the rest of the chain;
  site_<x>     matches the action: gs_<x>_<a> for an entry point, true for any other action. It reaches ro_<x>
               (rule L4), so it goes false when the site loses its protection (rule L11's mutation canary);
  gdh_<x>_<f>, gh_<x>_<a>, hit_<x>
               the same chains read as "the subtraction is evaluated at least once": disjunctions, false where the
               action stops, a reached subtraction true;
  wi_<p>       for each modelled oracle parameter p that names a builtin of the library twin: that builtin as a
               function, the oracle instance a REFUTED site law's witness names ({"instance": p}).

A site's name comes from its site id (rule R7: site_<where>_<x8>), never from a law id.

Classes: coercion_guard (a PROVED site law: every entry point's chain mirrored step by step, each hit's obligation
from the conditions the evaluation has passed, by omega; Reach is never used) and counter_decide (a REFUTED site
law: the record's witness, its oracle instance as a Lean function, its state as a run from s0 with an explicit
Reach proof, the predicate decided).
"""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from .lean_common import Theorem, Unsupported, ident
from .lean_machine import Ctx

SORT_SITES_VERSION = "holon-sort-sites/0.1"
_SPAN = re.compile(r"^(\S+?):(\d+)(?:-(\d+))?")
_SPAN_FULL = re.compile(r"(\S+?):(\d+)(?:-(\d+))?")
_ATOM = re.compile(r"[A-Za-z_][A-Za-z0-9_.']*|\d+")
STATE = "x_s"     # the state binder of the site declarations
ACTION = "x_a"    # the action binder of site_<x> and hit_<x>


# ------------------------------------------------------------------------------------------------ R7: names
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def site_name(site_id: str) -> str:
    """Rule R7: site_<where>_<x8> of a site id "<model>:<span>:<x8>"; <where> is slug(file stem)_<lo>[_<hi>] for a
    source span "<path>:<lo>[-<hi>]", def_<slug(definition)> for a definition span "<model>:<definition>"."""
    if not isinstance(site_id, str) or site_id.count(":") < 2:
        raise Unsupported(f"site id {site_id!r}")
    head, x8 = site_id.rsplit(":", 1)
    model, span = head.split(":", 1)
    m = re.match(r"^(?P<path>\S+?):(?P<lo>\d+)(?:-(?P<hi>\d+))?$", span)
    if m:
        where = _slug(PurePosixPath(m["path"]).stem) + f"_{m['lo']}" + (f"_{m['hi']}" if m["hi"] else "")
    elif span.startswith(model + ":"):
        where = "def_" + _slug(span.split(":", 1)[1])
    else:
        raise Unsupported(f"site {site_id}: span {span!r} is neither a source span nor a definition of {model}")
    return ident("site_", f"{where}_{x8}")


# ------------------------------------------------------------------------------------------------ R10: evaluation
def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _kids(e: list) -> list:
    """The operands a node evaluates (a callee, a field or a type name is not one)."""
    op = e[0]
    if op == "?" and len(e) == 4:
        return [e[1], e[2], e[3]]
    if op == "call":
        return list(e[2:])
    if op == "get":
        return [e[1]]
    if op == "mk":
        return list(e[2].values()) if len(e) > 2 and isinstance(e[2], dict) else []
    if op == "with":
        return [e[2], *(e[3].values() if len(e) > 3 and isinstance(e[3], dict) else [])]
    if op == "list":
        return list(e[2:])
    return list(e[1:])


def _walk(e, conds: tuple = ()):
    """Every node of e in pre-order, left to right, with its path condition ((condition, polarity), ..), outermost
    first (R10). A definition call's body is not entered."""
    if not isinstance(e, list) or not e:
        return
    yield e, conds
    op = e[0]
    if op == "?" and len(e) == 4:
        yield from _walk(e[1], conds)
        yield from _walk(e[2], conds + ((e[1], True),))
        yield from _walk(e[3], conds + ((e[1], False),))
        return
    if op in ("&&", "||"):
        pol = op == "&&"   # && evaluates an operand only when the earlier ones hold, || only when they fail
        pre = conds
        for x in e[1:]:
            yield from _walk(x, pre)
            pre = pre + ((x, pol),)
        return
    for k in _kids(e):
        yield from _walk(k, conds)


def _node_positions(e, node) -> list[tuple]:
    key = _canon(node)
    return [c for n, c in _walk(e) if _canon(n) == key]


def _call_positions(e, targets) -> list[tuple]:
    """(callee, call node, path condition) of every call in e of a definition in targets, in pre-order."""
    return [(n[1], n, c) for n, c in _walk(e) if n[0] == "call" and len(n) > 1 and n[1] in targets]


def _free(e, out: set) -> set:
    """The names e reads in operand positions (variables, and constants the compiler resolves)."""
    if isinstance(e, str):
        out.add(e)
    elif isinstance(e, list) and e:
        for k in _kids(e):
            _free(k, out)
    return out


def _entries(action: dict) -> list[tuple[str, object]]:
    """(at, expression) of every guard (let or require) of an action, then of every effect (by field name)."""
    out = [(f"guards[{i}]", g.get("require", g.get("expr"))) for i, g in enumerate(action.get("guards", []))]
    out += [(f"effects.{k}", x) for k, x in sorted((action.get("effects") or {}).items())]
    return out


def _entry_expr(action: dict, at: str):
    for a, x in _entries(action):
        if a == at:
            return x
    raise Unsupported(f"{action.get('name')}: no guard or effect {at}")


def _defs(facts: dict) -> dict:
    return {n: d for n, d in (facts.get("defs") or {}).items() if not d.get("ghost")}


def _def_reach(facts: dict) -> dict[str, set]:
    """For each non-ghost definition, the non-ghost definitions its evaluation can call (itself included)."""
    defs = _defs(facts)
    direct = {n: {c for c, _, _ in _call_positions(d.get("body"), defs)} for n, d in defs.items()}
    out = {}
    for n in defs:
        seen, todo = set(), [n]
        while todo:
            y = todo.pop()
            if y in seen:
                continue
            seen.add(y)
            todo.extend(direct[y] - seen)
        out[n] = seen
    return out


def _reaching(facts: dict, site_defs: list[str]) -> dict[str, list[str]]:
    """Definition f -> the site's definitions its evaluation reaches (non-ghost f only, sorted by f)."""
    return {f: [d for d in site_defs if d in r] for f, r in sorted(_def_reach(facts).items())
            if any(d in r for d in site_defs)}


# ------------------------------------------------------------------------------------------------ the site's span
def _span(src) -> str | None:
    if not isinstance(src, str):
        return None
    m = _SPAN.match(src)
    if not m:
        return None
    return f"{m.group(1)}:{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")


def _span_lines(sp) -> tuple | None:
    m = _SPAN_FULL.fullmatch(sp or "")
    if not m:
        return None
    lo = int(m.group(2))
    return m.group(1), lo, int(m.group(3) or lo)


def _inside(inner: str, outer: str) -> bool:
    pi, po = _span_lines(inner), _span_lines(outer)
    return bool(pi and po and pi[0] == po[0] and po[1] <= pi[1] and pi[2] <= po[2])


def _nlines(sp: str) -> int:
    p = _span_lines(sp)
    return p[2] - p[1] + 1


def _implies_nonneg(cmp, a, b) -> bool:
    """Does the comparison cmp state a >= b (a the minuend, b the subtrahend)?"""
    if not isinstance(cmp, list) or len(cmp) != 3 and not (len(cmp) == 2 and cmp[0] == "!"):
        return False
    op = cmp[0]
    if op in ("<=", "<") and cmp[1] == b and cmp[2] == a:
        return True
    if op in (">=", ">") and cmp[1] == a and cmp[2] == b:
        return True
    if op == "!" and isinstance(cmp[1], list) and len(cmp[1]) == 3:
        inner = cmp[1]
        return (inner[0] == "<" and inner[1] == a and inner[2] == b) or \
            (inner[0] == ">" and inner[1] == b and inner[2] == a)
    return False


def _contains_nonneg(e, a, b) -> bool:
    if _implies_nonneg(e, a, b):
        return True
    if isinstance(e, list):
        return any(_contains_nonneg(x, a, b) for x in e[1:] if isinstance(x, (list, dict)))
    if isinstance(e, dict):
        return any(_contains_nonneg(x, a, b) for x in e.values())
    return False


def _action_span(model: str, action: dict, base: str | None, node: list) -> str:
    """The span of a subtraction an action evaluates: its entry's span narrowed to the smallest require of the action
    inside it that checks the subtraction's sign."""
    if base is None:
        return f"{model}:{action['name']}"
    best, best_n = base, _nlines(base) if _span_lines(base) else None
    for g in action.get("guards", []):
        if "require" not in g:
            continue
        gs = _span(g.get("src"))
        if gs is None or not _inside(gs, base) or not _contains_nonneg(g["require"], node[1], node[2]):
            continue
        n = _nlines(gs)
        if best_n is None or n < best_n:
            best, best_n = gs, n
    return best


def _subtractions(e, key: str) -> list:
    return [n for n, _ in _walk(e) if n[0] == "-" and len(n) == 3 and _canon(n) == key]


def _occurrences(facts: dict, basis: dict) -> list[tuple[str, str]]:
    """(actor, where) of every evaluation position of the site's subtraction at the site's span, sorted: the actor an
    action (where guards[i].expr|require or effects.<f>) or a definition (where defs.<d>.body)."""
    model, span, key = basis["model"], basis["span"], _canon(basis["expr"])
    out = set()
    for name, d in _defs(facts).items():
        if _subtractions(d.get("body"), key) and (_span(d.get("src")) or f"{model}:{name}") == span:
            out.add((name, f"defs.{name}.body"))
    for a in facts["actions"]:
        asrc = _span(a.get("src"))
        places = []
        for i, g in enumerate(a.get("guards", [])):
            gsrc = _span(g.get("src")) or asrc
            places.append((f"guards[{i}].expr", g.get("expr"), gsrc) if "let" in g else
                          (f"guards[{i}].require", g.get("require"), gsrc))
        esrc = _span(a.get("effects_src")) or asrc
        places += [(f"effects.{k}", x, esrc) for k, x in sorted((a.get("effects") or {}).items())]
        for where, e, base in places:
            if any(_action_span(model, a, base, n) == span for n in _subtractions(e, key)):
                out.add((a["name"], where))
    others = []
    for kind in ("migrations", "observers"):
        for name, o in sorted((facts.get(kind) or {}).items()):
            exprs = [o.get("body")] if kind == "observers" else list((o.get("effects") or {}).values())
            sp = (_span(o.get("src")) if kind == "migrations" else None) or f"{model}:{name}"
            if sp == span and any(_subtractions(x, key) for x in exprs):
                others.append(f"{kind}.{name}")
    if others:
        raise Unsupported(f"site {basis['site_id']}: occurrences outside actions and definitions ({others})")
    return sorted(out)


# ------------------------------------------------------------------------------------------------ R8, R9: hit points
def _hits(facts: dict, basis: dict, real: set) -> tuple[list[dict], list[str]]:
    """(the hits of a site, each {"action", "at", "kind", "via"?, "occurrences"?}, sorted by (action, at); the site's
    definitions: [] for an action site)."""
    occ = _occurrences(facts, basis)
    if not occ:
        raise Unsupported(f"site {basis['site_id']}: the facts hold no such site")
    kinds = {w.startswith("defs.") for _, w in occ}
    if len(kinds) > 1:
        raise Unsupported(f"site {basis['site_id']}: occurrences in definitions and in actions at once")
    out: dict[tuple, dict] = {}
    if kinds == {True}:
        site_defs = sorted({w.split(".")[1] for _, w in occ})
        reach = _reaching(facts, site_defs)
        for a in facts["actions"]:
            for at, e in _entries(a):
                cs = _call_positions(e, reach)
                if cs:
                    f = cs[0][0]
                    d = reach[f][0]
                    out[(a["name"], at)] = {"action": a["name"], "at": at, "kind": "call",
                                            "via": [f] + ([d] if f != d else [])}
        return [out[k] for k in sorted(out)], site_defs
    reasons = {str(k): v for k, v in (facts.get("reasons") or {}).items()}
    acts = {a["name"]: a for a in facts["actions"]}
    for actor, where in occ:
        a = acts[actor]
        at = where.split(".")[0] if where.startswith("guards[") else where
        hit = (at, "occurrence")
        for i, g in enumerate(a.get("guards", [])):
            if f"guards[{i}]" == at:
                break
            if "require" in g and _span(g.get("src")) == basis["span"] and reasons.get(str(g.get("reason"))) in real:
                hit = (f"guards[{i}]", "realization_check")
                break
        cur = out.setdefault((actor, hit[0]), {"action": actor, "at": hit[0], "kind": hit[1], "occurrences": []})
        if cur["kind"] != hit[1]:
            raise Unsupported(f"site {basis['site_id']}: {actor} {hit[0]} is both an occurrence and a realization "
                              f"check")
        cur["occurrences"].append(where)
    return [out[k] for k in sorted(out)], []


def _public(hs: list[dict]) -> list[dict]:
    return [{k: h[k] for k in ("action", "at", "kind", "via") if k in h} for h in hs]


def hit_points(facts: dict, entry: dict, real_reasons: list[str]) -> dict[str, list[dict]]:
    """Rules R8-R10: per action, where it evaluates the site's subtraction ({"action", "at", "kind", "via"}, as a
    derivation entry's "hits" lists them); flattened in action order it equals the entry's "hits"."""
    out: dict[str, list[dict]] = {}
    for h in _public(_hits(facts, entry["basis"], set(real_reasons))[0]):
        out.setdefault(h["action"], []).append(h)
    return out


def _entry_reasons(facts: dict, entry: dict) -> set:
    """The realization-check reasons a derivation entry's own hits show (the reason texts of its realization-check
    guards). For the entry's site they give the hits the sidecar's list gives: an earlier guard with the site's span
    and a sidecar reason would itself be the hit."""
    reasons = {str(k): v for k, v in (facts.get("reasons") or {}).items()}
    acts = {a["name"]: a for a in facts["actions"]}
    out = set()
    for h in entry.get("hits") or []:
        m = re.fullmatch(r"guards\[(\d+)\]", str(h.get("at")))
        if h.get("kind") == "realization_check" and m and h.get("action") in acts:
            gs = acts[h["action"]].get("guards", [])
            if int(m.group(1)) < len(gs):
                out.add(reasons.get(str(gs[int(m.group(1))].get("reason"))))
    return out - {None}


# ------------------------------------------------------------------------------------------------ the raw obligation
def obligation_vars(expr, facts: dict) -> list[tuple[str, str]]:
    """The free variables of a site's subtraction ["-", minuend, subtrahend], in order of first occurrence (pre-order,
    left to right), each with its facts type: Nat for an operand of + or -, the parameter's type for an argument of a
    facts definition call. Literals are Nat; any other form is unsupported."""
    defs = facts.get("defs") or {}
    out: dict[str, str] = {}

    def go(e, want: str):
        if isinstance(e, bool) or e is None:
            raise Unsupported(f"obligation term {e!r}")
        if isinstance(e, int):
            if want != "Nat":
                raise Unsupported(f"a literal where {want} is expected")
            return
        if isinstance(e, str):
            if out.setdefault(e, want) != want:
                raise Unsupported(f"variable {e} used at {out[e]} and {want}")
            return
        if isinstance(e, list) and len(e) == 3 and e[0] in ("+", "-"):
            if want != "Nat":
                raise Unsupported(f"{e[0]} where {want} is expected")
            go(e[1], "Nat")
            go(e[2], "Nat")
            return
        if isinstance(e, list) and len(e) >= 2 and e[0] == "call" and e[1] in defs:
            d = defs[e[1]]
            ps = d.get("params") or []
            if d.get("type") != want or len(ps) != len(e) - 2:
                raise Unsupported(f"call of {e[1]}")
            for (_, pt), a in zip(ps, e[2:]):
                go(a, pt)
            return
        raise Unsupported(f"obligation term {_canon(e)[:80]}")

    if not (isinstance(expr, list) and len(expr) == 3 and expr[0] == "-"):
        raise Unsupported(f"a site expression that is not a subtraction: {_canon(expr)[:80]}")
    go(expr, "Nat")
    return list(out.items())


def _calls(e, names: set, out: set) -> set:
    if isinstance(e, list) and e:
        if e[0] == "call" and len(e) > 1 and e[1] in names:
            out.add(e[1])
        for x in e[1:]:
            _calls(x, names, out)
    elif isinstance(e, dict):
        for x in e.values():
            _calls(x, names, out)
    return out


def _reaches_param(e, facts: dict, params) -> bool:
    """Does facts expression e evaluate a call of a modelled oracle parameter (directly or through definitions)?"""
    defs = facts.get("defs") or {}
    seen, todo = set(), [e]
    while todo:
        x = todo.pop()
        if _calls(x, set(params), set()):
            return True
        for d in sorted(_calls(x, set(defs), set()) - seen):
            seen.add(d)
            todo.append(defs[d].get("body"))
    return False


# ------------------------------------------------------------------------------------------------ chains as terms
# A chain is a tree: ("lit", bool) | ("cond", c, then, else) | ("and"|"or", left, right) | ("let", name, value, body)
# | ("app", kind, name, [args]), kind "ro" (the raw obligation) or "gd"/"gdh" (a definition ghost).

def _balanced_outer(t: str) -> bool:
    """Does t's first bracket close at its last character?"""
    depth = 0
    for i, ch in enumerate(t):
        depth += ch in "([{⟨"
        depth -= ch in ")]}⟩"
        if depth == 0:
            return i == len(t) - 1
    return False


def _paren(t: str) -> str:
    """t as an application argument."""
    if _ATOM.fullmatch(t) or (t[:1] in "([" and _balanced_outer(t)):
        return t
    return f"({t})"


def _render(n, ind: int = 2) -> str:
    pad = " " * ind
    k = n[0]
    if k == "lit":
        return "true" if n[1] else "false"
    if k == "cond":
        return f"(bif {n[1]} then\n{pad}  {_render(n[2], ind + 2)}\n{pad}else\n{pad}  {_render(n[3], ind + 2)})"
    if k in ("and", "or"):
        return f"({_render(n[1], ind + 1)} {'&&' if k == 'and' else '||'}\n{pad} {_render(n[2], ind + 1)})"
    if k == "let":
        return f"(let {n[1]} := {n[2]};\n{pad}{_render(n[3], ind)})"
    if k == "app":
        return "(" + " ".join([n[2]] + [_paren(a) for a in n[3]]) + ")"
    raise Unsupported(f"chain node {k}")


def _join(parts: list, hit: bool):
    """The conjunction (site) or disjunction (hit) of parts, textual duplicates dropped, right-nested."""
    seen, keys = [], []
    for p in parts:
        r = _render(p)
        if r not in keys:
            keys.append(r)
            seen.append(p)
    if not seen:
        return ("lit", not hit)
    out = seen[-1]
    for p in reversed(seen[:-1]):
        out = ("or" if hit else "and", p, out)
    return out


class _Site:
    """The declarations of one site over a compiled document, and the chains its proofs mirror."""

    def __init__(self, ctx: Ctx, entry: dict, real: set):
        self.ctx, self.entry = ctx, entry
        self.f = ctx.facts
        b = entry["basis"]
        self.site_id, self.expr = b["site_id"], b["expr"]
        self.x = site_name(self.site_id)[len("site_"):]
        self.hits, self.D = _hits(self.f, b, real)
        if _public(self.hits) != entry.get("hits"):
            raise Unsupported(f"site {self.site_id}: the facts give the hits {_public(self.hits)}, the derivation "
                              f"says {entry.get('hits')}")
        self.reach = _reaching(self.f, self.D) if self.D else {}
        self.acts = {a["name"]: a for a in self.f["actions"]}
        self.state = [(s[0], s[1]) for s in self.f["state"]]
        self.eps = sorted({h["action"] for h in self.hits})
        self.ovars = self._obligation_vars()
        self.ro_param = _reaches_param(self.expr, self.f, ctx.params)
        self.pargs = ctx.pargs().split()
        self.order = self._def_order()
        self.takes_p: dict[str, bool] = {}
        self.trees: dict[str, tuple] = {}     # Lean name -> (binders [(name, facts type)], tree): the site chains

    # ---------------------------------------------------------- names
    def ro(self) -> str:
        return "ro_" + self.x

    def gd(self, f: str, hit: bool) -> str:
        return ident(f"{'gdh' if hit else 'gd'}_{self.x}_", f)

    def gs(self, a: str, hit: bool) -> str:
        return ident(f"{'gh' if hit else 'gs'}_{self.x}_", a)

    def pred(self, hit: bool) -> str:
        return f"{'hit' if hit else 'site'}_{self.x}"

    # ---------------------------------------------------------- pieces
    def _obligation_vars(self) -> list[tuple[str, str]]:
        """ro_<x>'s variables: obligation_vars, or, for a subtraction whose operands call a builtin, its free
        variables in order of first occurrence typed where the site evaluates it (a definition site: its
        definition's parameters; an action site: the state, the inputs and the lets before its first hit)."""
        try:
            return obligation_vars(self.expr, self.f)
        except Unsupported:
            pass
        names: list[str] = []

        def leaves(e) -> None:
            if isinstance(e, str):
                if e not in names:
                    names.append(e)
            elif isinstance(e, list) and e:
                for k in _kids(e):
                    leaves(k)
        leaves(self.expr)
        if self.D:
            d = self.f["defs"][self.D[0]]
            env = {p: (ident("l_", p), t) for p, t in d.get("params") or []}
        else:
            h = self.hits[0]
            a = self.acts[h["action"]]
            m = re.fullmatch(r"guards\[(\d+)\]", h["at"])
            env = self.action_env(a, int(m.group(1)) if m else len(a.get("guards", [])))
        return [(v, self.ex(v, env)[1]) for v in names]

    def action_env(self, a: dict, upto: int) -> dict:
        """The state fields, the inputs and the lets of a's guards before index upto, each as (Lean term, type)."""
        env = {f: (self.ctx.field(STATE, f), t) for f, t in self.state}
        env.update({i: (self.ctx.inp(i), t) for i, t in a["inputs"]})
        for g in a.get("guards", [])[:upto]:
            if "let" in g:
                env[g["let"]] = (ident("l_", g["let"]), self.ex(g.get("expr"), env)[1])
        return env

    def _def_order(self) -> list[str]:
        order: list[str] = []

        def visit(f: str, stack: tuple) -> None:
            if f in order:
                return
            if f in stack:
                raise Unsupported(f"site {self.site_id}: definition {f} is recursive")
            for g, _, _ in _call_positions(self.f["defs"][f].get("body"), self.reach):
                if g != f:
                    visit(g, stack + (f,))
            order.append(f)
        for f in self.reach:
            visit(f, ())
        return order

    def ex(self, e, env: dict) -> tuple[str, str]:
        try:
            return self.ctx.expr(e, env)
        except Unsupported as err:
            raise Unsupported(f"site {self.site_id}: {err}") from err

    def term(self, e, env: dict) -> str:
        return self.ex(e, env)[0]

    def obligation(self, env: dict):
        """ro_<x> of the subtraction's free variables, read in env."""
        return ("app", "ro", self.ro(), (self.pargs if self.ro_param else []) +
                [self.term(v, env) for v, _ in self.ovars])

    def guarded(self, conds: tuple, base, env: dict, hit: bool):
        out = base
        for c, pol in reversed(conds):
            ct = self.term(c, env)
            skip = ("lit", not hit)
            out = ("cond", ct, out, skip) if pol else ("cond", ct, skip, out)
        return out

    def call(self, g: str, node: list, env: dict, hit: bool):
        name = self.gd(g, hit)
        args = [self.term(y, env) for y in node[2:]]
        return ("app", "gdh" if hit else "gd", name, (self.pargs if self.takes_p[name] else []) + args)

    def hit_parts(self, a: dict, hl: list[dict], env: dict, hit: bool):
        parts = []
        for h in hl:
            if h["kind"] == "call":
                for g, node, conds in _call_positions(_entry_expr(a, h["at"]), self.reach):
                    parts.append(self.guarded(conds, self.call(g, node, env, hit), env, hit))
            else:
                for w in h["occurrences"]:
                    e = _entry_expr(a, w.split(".")[0] if w.startswith("guards[") else w)
                    for conds in _node_positions(e, self.expr):
                        base = ("lit", True) if hit else self.obligation(env)
                        parts.append(self.guarded(conds, base, env, hit))
        return _join(parts, hit)

    def hit_reads(self, a: dict, hl: list[dict]) -> set:
        """The names the evaluation at these hits reads."""
        out: set = set()
        for h in hl:
            if h["kind"] == "call":
                for _, node, conds in _call_positions(_entry_expr(a, h["at"]), self.reach):
                    for y in node[2:]:
                        _free(y, out)
                    for c, _ in conds:
                        _free(c, out)
            else:
                for w in h["occurrences"]:
                    e = _entry_expr(a, w.split(".")[0] if w.startswith("guards[") else w)
                    for conds in _node_positions(e, self.expr):
                        _free(self.expr, out)
                        for c, _ in conds:
                            _free(c, out)
        return out

    def _needs_p(self, body: str) -> bool:
        return any(re.search(rf"(?<![A-Za-z0-9_.']){re.escape(p)}(?![A-Za-z0-9_'])", body) for p in self.pargs)

    # ---------------------------------------------------------- definition ghosts
    def def_ghost(self, f: str, hit: bool) -> str:
        d = self.f["defs"][f]
        params = [(ident("l_", p), p, t) for p, t in d.get("params") or []]
        env = {p: (lp, t) for lp, p, t in params}
        parts = []
        if f in self.D:
            for conds in _node_positions(d.get("body"), self.expr):
                base = ("lit", True) if hit else self.obligation(env)
                parts.append(self.guarded(conds, base, env, hit))
        for g, node, conds in _call_positions(d.get("body"), self.reach):
            if g != f:
                parts.append(self.guarded(conds, self.call(g, node, env, hit), env, hit))
        tree = _join(parts, hit)
        body = _render(tree)
        name = self.gd(f, hit)
        self.takes_p[name] = self._needs_p(body)
        binders = ([self.ctx.pbinders()] if self.takes_p[name] else []) + \
            [f"({lp} : {self.ctx.ty(t)})" for lp, _, t in params]
        self.trees[name] = ([(lp, t) for lp, _, t in params], tree)
        return f"def {name} {' '.join(binders)} : Bool :=\n  {body}"

    # ---------------------------------------------------------- one action's chain
    def chain_tree(self, a: dict, hit: bool):
        guards = a.get("guards", [])
        n = len(guards)
        at_guard: dict[int, list] = {}
        at_effects: list = []
        for h in self.hits:
            if h["action"] != a["name"]:
                continue
            m = re.fullmatch(r"guards\[(\d+)\]", h["at"])
            if m:
                at_guard.setdefault(int(m.group(1)), []).append(h)
            else:
                at_effects.append(h)
        last = n if at_effects else max(at_guard)
        reads: list[set] = [set() for _ in range(n + 2)]   # reads[i]: what the chain reads from guard i on
        reads[n] = self.hit_reads(a, at_effects) if last == n else set()
        for i in range(n - 1, -1, -1):
            if i > last:
                continue
            r = set() if i == last and last < n else set(reads[i + 1])
            if i < last:
                g = guards[i]
                if "let" in g:
                    r.discard(g["let"])
                    _free(g.get("expr"), r)
                else:
                    _free(g.get("require"), r)
            if i in at_guard:
                r |= self.hit_reads(a, at_guard[i])
            reads[i] = r
        env = {f: (self.ctx.field(STATE, f), t) for f, t in self.state}
        env.update({i: (self.ctx.inp(i), t) for i, t in a["inputs"]})
        stop = ("lit", not hit)

        def seq(i: int, env: dict, done: bool):
            if i == n:
                return self.hit_parts(a, at_effects, env, hit)
            if i in at_guard and not done:
                ob = self.hit_parts(a, at_guard[i], env, hit)
                if i == last:
                    return ob
                return ("or" if hit else "and", ob, seq(i, env, True))
            g = guards[i]
            if "let" in g:
                if g["let"] not in reads[i + 1]:   # a let nothing later reads binds nothing
                    return seq(i + 1, env, False)
                xt, ty = self.ex(g.get("expr"), env)
                ln = ident("l_", g["let"])
                env2 = dict(env)
                env2[g["let"]] = (ln, ty)
                return ("let", ln, xt, seq(i + 1, env2, False))
            return ("cond", self.term(g.get("require"), env), seq(i + 1, env, False), stop)

        return seq(0, env, False)

    def action_chain(self, an: str, hit: bool) -> str:
        a = self.acts[an]
        tree = self.chain_tree(a, hit)
        body = _render(tree)
        name = self.gs(an, hit)
        self.takes_p[name] = self._needs_p(body)
        ins = [(self.ctx.inp(i), t) for i, t in a["inputs"]]
        binders = ([self.ctx.pbinders()] if self.takes_p[name] else []) + [f"({STATE} : St)"] + \
            [f"({i} : {self.ctx.ty(t)})" for i, t in ins]
        self.trees[name] = (ins, tree)
        return f"def {name} {' '.join(binders)} : Bool :=\n  {body}"

    def dispatch(self, hit: bool) -> str:
        pb = self.ctx.pbinders()
        lines = [f"def {self.pred(hit)} {pb + ' ' if pb else ''}({ACTION} : Act) ({STATE} : St) : Bool :=",
                 f"  match {ACTION} with"]
        for a in self.f["actions"]:
            ins = [self.ctx.inp(i) for i, _ in a["inputs"]]
            if a["name"] in self.eps:
                name = self.gs(a["name"], hit)
                args = (self.pargs if self.takes_p[name] else []) + [STATE] + ins
                lines.append(f"  | {self.ctx.ctor(a['name'])}{''.join(' ' + i for i in ins)} => "
                             f"{name} {' '.join(args)}")
            else:
                lines.append(f"  | {self.ctx.ctor(a['name'])}{' _' * len(ins)} => {'false' if hit else 'true'}")
        return "\n".join(lines)

    def ro_decl(self) -> str:
        names = {v: ident("l_", v) for v, _ in self.ovars}
        env = {v: (names[v], t) for v, t in self.ovars}
        sub, mnd = self.term(self.expr[2], env), self.term(self.expr[1], env)
        binders = ([self.ctx.pbinders()] if self.ro_param and self.pargs else []) + \
            [f"({names[v]} : {self.ctx.ty(t)})" for v, t in self.ovars]
        return f"def {self.ro()} {' '.join(binders)} : Bool :=\n  Nat.ble {_paren(sub)} {_paren(mnd)}"

    def decls(self) -> list[str]:
        out = []
        for hit in (False, True):
            out += [self.def_ghost(f, hit) for f in self.order]
            out += [self.action_chain(a, hit) for a in self.eps]
            out.append(self.dispatch(hit))
        return out


def _fn_type(t: str) -> tuple[str, str] | None:
    m = re.fullmatch(r"Fn<(.+),(.+)>", t.replace(" ", ""))
    base = {"Nat": "Nat", "Bool": "Bool", "List<Nat>": "List Nat"}
    if not m or m.group(1) not in base or m.group(2) not in base:
        return None
    return m.group(1), m.group(2)


def _template(ctx: Ctx, tmpl: str, arg: str) -> str | None:
    """A one-argument twin template with $0 the argument and ${param:<name>:<default>} the facts parameter (else
    the default); None for any other placeholder."""
    out = []
    pos = 0
    for m in re.finditer(r"\$\{param:(\w+):([^{}]*)\}|\$(\w+)", tmpl):
        out.append(tmpl[pos:m.start()])
        pos = m.end()
        if m.group(1):
            v = (ctx.facts.get("params") or {}).get(m.group(1), m.group(2))
            if isinstance(v, bool) or not re.fullmatch(r"\d+", str(v)):
                return None
            out.append(str(v))
        elif m.group(3) == "0":
            out.append(arg)
        else:
            return None
    return "".join(out) + tmpl[pos:]


def _instances(ctx: Ctx) -> list[str]:
    """wi_<p> for each modelled oracle parameter p that names a one-argument builtin of the library twin."""
    out = []
    builtins = (ctx.lib or {}).get("builtins") or {}
    lt = {"Nat": "Nat", "Bool": "Bool", "List<Nat>": "List Nat"}
    for p, ty in ctx.params.items():
        b = builtins.get(p)
        tmpl = b.get("lean") if isinstance(b, dict) else None
        ft = _fn_type(ty)
        body = _template(ctx, tmpl, "x_0") if isinstance(tmpl, str) and b.get("arity") in (1, None) else None
        if body is None or ft is None:
            continue
        out.append(f"def {ident('wi_', p)} : {lt[ft[0]]} → {lt[ft[1]]} :=\n  fun x_0 => {body}")
    return out


def _site_entries(entries: list[dict]) -> list[dict]:
    return sorted((e for e in entries if e.get("subform") == "site" and (e.get("basis") or {}).get("kind") == "site"),
                  key=lambda e: e["law_id"])


def section(ctx: Ctx, entries: list[dict], sidecar: dict) -> list[str]:
    """The site declarations of ctx's model (inside namespace Model): the oracle instances wi_<p>, every ro_<x>, then
    for each site its definition ghosts, per-action chains and site_<x>, and the same for hit_<x>; over the SORT-site
    derivation entries in entries (those of ctx's facts document), in law-id order."""
    sites = []
    if _site_entries(entries):
        if sidecar.get("sort_sites_version") != SORT_SITES_VERSION:
            raise Unsupported(f"sort sites sidecar version {sidecar.get('sort_sites_version')!r}")
        real = sidecar.get("realization_check_reasons")
        if not isinstance(real, list) or not all(isinstance(r, str) for r in real):
            raise Unsupported("the sort sites sidecar has no list of realization-check reasons")
        sites = [_Site(ctx, e, set(real)) for e in _site_entries(entries)]
    names = [s.x for s in sites]
    if len(set(names)) != len(names):
        raise Unsupported(f"two sites share a name: {sorted(names)}")
    out = _instances(ctx) + [s.ro_decl() for s in sites]
    for s in sites:
        out += s.decls()
    return out


def inputs(root: Path, milestone: str, facts_rel: str) -> tuple[list[dict], dict]:
    """The section's inputs for a document of a milestone: the SORT-site entries of laws/<M>/DERIVATION.json over
    facts_rel (none without a derivation), and the sort sites sidecar (spec/<M>/lib/sort_sites.json, else M2's; {}
    when there is no entry)."""
    root = Path(root)
    dp = root / "laws" / milestone / "DERIVATION.json"
    entries = []
    if dp.is_file():
        doc = json.loads(dp.read_text(encoding="utf-8"))
        entries = [e for e in _site_entries(doc.get("laws", [])) if e.get("facts") == facts_rel]
    if not entries:
        return [], {}
    sp = root / "spec" / milestone / "lib" / "sort_sites.json"
    sp = sp if sp.is_file() else root / "spec" / "M2" / "lib" / "sort_sites.json"
    return entries, json.loads(sp.read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ coercion_guard
_HELPERS = {
    "ct": ("theorem holon_cg_ct (c x : Bool) (h : c = true → x = true) : (bif c then x else true) = true := by\n"
           "  cases c\n  · rfl\n  · exact h rfl"),
    "cf": ("theorem holon_cg_cf (c y : Bool) (h : c = false → y = true) : (bif c then true else y) = true := by\n"
           "  cases c\n  · exact h rfl\n  · rfl"),
    "cb": ("theorem holon_cg_cb (c x y : Bool) (hx : c = true → x = true) (hy : c = false → y = true) :\n"
           "    (bif c then x else y) = true := by\n  cases c\n  · exact hy rfl\n  · exact hx rfl"),
    "and": ("theorem holon_cg_and (x y : Bool) (hx : x = true) (hy : y = true) : (x && y) = true := by\n"
            "  cases x\n  · exact hx\n  · exact hy"),
}
# Bool to Prop (Lean core lemmas), each used when all its triggers occur in what a leaf has passed ("¬": a
# condition that failed, whose equation is c = false)
_NEG = "¬"
_PROP_LEMMAS = (("Nat.ble_eq", ("Nat.ble",)), ("Nat.blt_eq", ("Nat.blt",)), ("Nat.beq_eq", ("Nat.beq",)),
                ("Bool.and_eq_true", ("&&",)), ("Bool.or_eq_true", ("||",)), ("Bool.not_eq_true'", ("!",)),
                ("Bool.and_eq_false_iff", ("&&", _NEG)), ("Bool.or_eq_false_iff", ("||", _NEG)),
                ("Bool.eq_false_iff", (_NEG,)), ("ne_eq", (_NEG,)), ("beq_iff_eq", ("==",)), ("bne_iff_ne", ("!=",)),
                ("decide_eq_true_eq", ("decide",)))


class _Proof:
    """coercion_guard: a tactic script per site chain (site reading), mirroring its steps: at a decision or a path
    condition the condition's equation is introduced; a conjunction proves both sides; a definition ghost is its
    lemma; the raw obligation is omega over the passed conditions read as Prop (the document's Bool definitions
    unfolded)."""

    def __init__(self, s: _Site, bool_defs: dict[str, str]):
        self.s, self.bool_defs = s, bool_defs     # Lean name -> the body the unfolding exposes
        self.used: set = set()

    def leaf(self, conds: list[str]) -> list[str]:
        text = " ".join(conds)
        unfold, todo = [], [n for n in self.bool_defs if re.search(rf"\b{re.escape(n)}\b", text)]
        while todo:
            n = todo.pop(0)
            if n not in unfold:
                unfold.append(n)
                todo += [m for m in self.bool_defs if re.search(rf"\b{re.escape(m)}\b", self.bool_defs[n])]
        text += " Nat.ble " + " ".join(self.bool_defs[n] for n in unfold)
        lemmas = [f"Model.{self.s.ro()}"] + [f"Model.{n}" for n in sorted(unfold)] + \
            [lm for lm, trig in _PROP_LEMMAS if all(t in text for t in trig)]
        return [f"(simp only [{', '.join(lemmas)}] at *) <;> omega"]

    def tac(self, n, conds: list[str], d: int) -> list[str]:
        k = n[0]
        if k == "lit":
            if not n[1]:
                raise Unsupported(f"site {self.s.site_id}: a chain that is false")
            return ["rfl"]
        if k == "let":
            return self.tac(n[3], conds + [n[2]], d)
        if k == "cond":
            c = conds + [n[1]]
            if n[3] == ("lit", True):
                self.used.add("ct")
                return [f"refine holon_cg_ct _ _ (fun h{d} => ?_)"] + self.tac(n[2], c, d + 1)
            if n[2] == ("lit", True):
                self.used.add("cf")
                return [f"refine holon_cg_cf _ _ (fun h{d} => ?_)"] + self.tac(n[3], c + [_NEG], d + 1)
            self.used.add("cb")
            return ([f"refine holon_cg_cb _ _ _ (fun h{d} => ?_) (fun h{d} => ?_)"]
                    + self.focus(self.tac(n[2], c, d + 1)) + self.focus(self.tac(n[3], c + [_NEG], d + 1)))
        if k == "and":
            self.used.add("and")
            return ["refine holon_cg_and _ _ ?_ ?_"] + self.focus(self.tac(n[1], conds, d)) + \
                self.focus(self.tac(n[2], conds, d))
        if k == "app" and n[1] == "ro":
            return self.leaf(conds)
        if k == "app" and n[1] == "gd":
            return [f"exact {self.lemma(n[2])}" + " _" * len(n[3])]
        raise Unsupported(f"site {self.s.site_id}: coercion_guard has no step for {k}")

    @staticmethod
    def focus(lines: list[str]) -> list[str]:
        return ["· " + lines[0]] + ["  " + ln for ln in lines[1:]]

    @staticmethod
    def lemma(name: str) -> str:
        return "holon_cg_" + name

    def helper(self, name: str, qual, with_state: bool) -> str:
        """The lemma `Model.<name> <args> = true` of a site chain or definition ghost, for every argument."""
        binders, tree = self.s.trees[name]
        ps = [self.s.ctx.pbinders()] if self.s.takes_p[name] else []
        args = list(self.s.pargs) if self.s.takes_p[name] else []
        if with_state:
            ps.append(f"({STATE} : Model.St)")
            args.append(STATE)
        ps += [f"({b} : {qual(t)})" for b, t in binders]
        args += [b for b, _ in binders]
        body = self.tac(tree, [], 0)
        return (f"theorem {self.lemma(name)} {' '.join(ps)} :\n    Model.{name} {' '.join(args)} = true := by\n"
                f"  unfold Model.{name}\n" + "\n".join("  " + ln for ln in body))


def _qual_type(records: dict):
    """A facts type as a Lean type outside namespace Model."""
    def lt(t: str) -> str:
        if t in ("Nat", "Bool"):
            return t
        m = re.fullmatch(r"List<(.+)>", t)
        if m:
            inner = lt(m.group(1))
            return f"List {inner}" if " " not in inner else f"List ({inner})"
        if t in records:
            return "Model." + ident("T_", t)
        if t == "Obs":
            return "Model.Obs"
        raise Unsupported(f"facts type {t}")
    return lt


def _bool_defs(ctx: Ctx) -> dict[str, str]:
    """The document's Bool definitions: Lean name -> its body as the model reads it (what unfolding it exposes)."""
    out = {}
    for n, d in sorted(_defs(ctx.facts).items()):
        if d.get("type") == "Bool":
            env = {p: (ident("l_", p), t) for p, t in d.get("params") or []}
            out[ctx.def_name(n)] = ctx.expr(d.get("body"), env)[0]
    return out


def _site_law_shape(law: dict, ctx: Ctx) -> None:
    """A site law: ∀ s : Reach, ∀ a : Act, the oracle parameters (the model's), no premise, claim site = true."""
    st = law.get("statement") or {}
    bs = st.get("binders") or []
    kinds = [(b.get("q"), b.get("type")) for b in bs]
    ok = (len(bs) == 2 + len(ctx.params) and kinds[:2] == [("forall", "Reach"), ("forall", "Act")]
          and [b.get("name") for b in bs[2:]] == list(ctx.params) and not st.get("assume")
          and all(q == "forall" for q, _ in kinds))
    if not ok:
        raise Unsupported("not a SORT-site law statement (∀ s : Reach, ∀ a : Act, the oracle parameters)")


def _coercion_guard(law: dict, ctx: Ctx, stmts: list[tuple[str, str]], entry: dict) -> tuple[Theorem, ...]:
    if len(stmts) != 1 or stmts[0][0] != law["law_id"]:
        raise Unsupported(f"coercion_guard proves one theorem named {law['law_id']}")
    _site_law_shape(law, ctx)
    s = _Site(ctx, entry, _entry_reasons(ctx.facts, entry))
    s.decls()
    qual = _qual_type(ctx.facts.get("types") or {})
    pr = _Proof(s, _bool_defs(ctx))
    helpers = [pr.helper(s.gd(f, False), qual, False) for f in s.order]
    helpers += [pr.helper(s.gs(a, False), qual, True) for a in s.eps]
    lines = [f"intro {' '.join(s.pargs + [STATE, '_', ACTION])}", f"cases {ACTION} with"]
    for a in ctx.facts["actions"]:
        ins = [ctx.inp(i) for i, _ in a["inputs"]]
        ctor = ctx.ctor(a["name"]).rsplit(".", 1)[-1]
        if a["name"] in s.eps:
            name = s.gs(a["name"], False)
            args = (s.pargs if s.takes_p[name] else []) + [STATE] + ins
            lines.append(f"| {ctor}{''.join(' ' + i for i in ins)} => exact {pr.lemma(name)} {' '.join(args)}")
        else:
            lines.append(f"| {ctor}{' _' * len(ins)} => rfl")
    before = tuple(_HELPERS[k] for k in ("ct", "cf", "cb", "and") if k in pr.used) + tuple(helpers)
    return (Theorem(law["law_id"], stmts[0][1], "by\n" + "\n".join("  " + ln for ln in lines), before=before),)


# ------------------------------------------------------------------------------------------------ counter_decide
def _value(t: str, v, records: dict) -> str:
    """A facts value as a Lean term outside namespace Model."""
    if t == "Nat":
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise Unsupported(f"Nat value {v!r}")
        return str(v)
    if t == "Bool":
        if not isinstance(v, bool):
            raise Unsupported(f"Bool value {v!r}")
        return "true" if v else "false"
    m = re.fullmatch(r"List<(.+)>", t)
    if m:
        if not isinstance(v, list):
            raise Unsupported(f"list value {v!r}")
        if not v:
            return f"([] : {_qual_type(records)(t)})"
        return "[" + ", ".join(_value(m.group(1), x, records) for x in v) + "]"
    if t in records:
        if not isinstance(v, dict):
            raise Unsupported(f"record value {v!r}")
        fs = records[t]["fields"]
        return "({ " + ", ".join(f"{ident('f_', fn)} := {_value(ft, v[fn], records)}" for fn, ft in fs) + \
            f" }} : Model.{ident('T_', t)})"
    raise Unsupported(f"facts type {t} of a witness value")


def _act(ctx: Ctx, a) -> str:
    acts = {x["name"]: x for x in ctx.facts["actions"]}
    if not isinstance(a, dict) or a.get("op") not in acts:
        raise Unsupported(f"witness action {a!r}")
    d = acts[a["op"]]
    records = ctx.facts.get("types") or {}
    if any(n not in a for n, _ in d["inputs"]):
        raise Unsupported(f"witness action {a!r} lacks an input")
    args = "".join(" " + _paren(_value(t, a[n], records)) for n, t in d["inputs"])
    return f"(Model.{ctx.ctor(a['op'])}{args})" if args else f"Model.{ctx.ctor(a['op'])}"


def _oracle_value(ctx: Ctx, name: str, w) -> str:
    """A witness's oracle parameter as a Lean function: {"instance": p} -> Model.wi_<p>; {"table": [[k, v], ..]} ->
    the value of the first entry whose key is the argument, else the default (0, false)."""
    ft = _fn_type(ctx.params[name])
    if ft is None:
        raise Unsupported(f"oracle type {ctx.params[name]}")
    if isinstance(w, dict) and isinstance(w.get("instance"), str):
        b = ((ctx.lib or {}).get("builtins") or {}).get(w["instance"])
        if w["instance"] != name or not isinstance(b, dict) or not isinstance(b.get("lean"), str):
            raise Unsupported(f"oracle instance {w['instance']!r} for parameter {name}")
        return f"Model.{ident('wi_', name)}"
    if isinstance(w, dict) and isinstance(w.get("table"), list):
        records = ctx.facts.get("types") or {}
        body = _value(ft[1], 0 if ft[1] == "Nat" else [] if ft[1].startswith("List") else False, records)
        for row in reversed(w["table"]):
            if not (isinstance(row, list) and len(row) == 2):
                raise Unsupported(f"oracle table row {row!r}")
            body = (f"bif x_0 == {_paren(_value(ft[0], row[0], records))} then {_paren(_value(ft[1], row[1], records))}"
                    f" else {_paren(body)}")
        return f"(fun x_0 => {body})"
    raise Unsupported(f"oracle witness {w!r}")


def _counter(law: dict, record: dict, ctx: Ctx, stmts: list[tuple[str, str]]) -> tuple[Theorem, ...]:
    lid = law["law_id"]
    names = [n for n, _ in stmts]
    if names != [f"{lid}_counter", f"{lid}_refuted"]:
        raise Unsupported(f"counter_decide proves {lid}_counter and {lid}_refuted, not {names}")
    _site_law_shape(law, ctx)
    w = record.get("witness")
    if not isinstance(w, dict):
        raise Unsupported("a REFUTED record without a witness")
    bs = law["statement"]["binders"]
    pv = [_oracle_value(ctx, b["name"], w.get(b["name"])) for b in bs[2:]]
    run = (w.get(bs[0]["name"]) or {}).get("run") if isinstance(w.get(bs[0]["name"]), dict) else None
    if not isinstance(run, list):
        raise Unsupported(f"Reach witness {w.get(bs[0]['name'])!r}")
    acts = [_act(ctx, a) for a in run]
    trace = "[" + ", ".join(acts) + "]" if acts else "([] : List Model.Act)"
    state = " ".join(["Model.run"] + [_paren(p) for p in pv] + [trace, "Model.s0"])
    reach = "Model.Reach.r0"
    for a in acts:
        reach = f"(Model.Reach.rstep {a} _ {reach})"
    parts = pv + [state, reach, _act(ctx, w.get(bs[1]["name"]))]
    counter = Theorem(names[0], stmts[0][1], "⟨" + ", ".join(parts) + ", by decide⟩")
    ws = [f"w_{i}" for i in range(len(parts) + 1)]
    refuted = Theorem(names[1], stmts[1][1], f"fun h_all => match {names[0]} with\n"
                                             f"  | ⟨{', '.join(ws)}⟩ => {ws[-1]} (h_all {' '.join(ws[:-1])})")
    return counter, refuted


def theorems(cls: str, law: dict, status: str, record: dict, ctx: Ctx, stmts: list[tuple[str, str]],
             entry: dict) -> tuple[Theorem, ...]:
    """The theorems of a site law file: cls is coercion_guard (PROVED) or counter_decide (REFUTED); entry: the law's
    derivation entry."""
    if cls == "coercion_guard" and status == "PROVED":
        return _coercion_guard(law, ctx, stmts, entry)
    if cls == "counter_decide" and status == "REFUTED":
        return _counter(law, record, ctx, stmts)
    raise Unsupported(f"site laws have no Lean class {cls} for a {status} verdict")
