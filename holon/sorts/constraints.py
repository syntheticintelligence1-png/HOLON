"""Sort constraints of one fact document (whitepaper §7.7 step 1; BUILD_PLAN I13).

Constraints come from types, value flow, the affine rules, comparisons, cross-component linking and lexical
seeds. Each is a JSON object of constraints.json carrying everything holon.sorts.solve.satisfiable reads:

  type     {"vars": [v], "sort"}: a Bool binder is Bool; a holon-facts/0.1 record field of width n bytes is
           Mach(8n) (see holon.sorts.grammar)
  seed     {"vars": [v], "sort", "grounds"}: a unit constraint, at most one per variable, listing every
           ground: lexical rules of the frozen sidecar spec/M2/lib/sort_seeds.json ("lexical:<rule id>") and
           structural facts ("structural:disch.delay": the delay input of the DISCH cost model is time waited,
           a Dur). When grounds name different sorts the seed's sort is their union, so grounds that disagree
           on the family make the seed unsatisfiable by itself.
  flow     {"vars": [from, to]}: a value moves (holon.sorts.flow); unifies base sorts (R2)
  affine   {"op", "vars": [lhs, rhs, out]}: one + or - node under §7.2
  compare  {"op", "vars": [lhs, rhs]}: one comparison of two Nat terms ("via": the builtin, for mem, remove
           and eq_nats, which compare an element with a list's elements)
  writer   {"vars": [register], "writers"}: the register's writer set (provenance; labels are not unified)
  link     cross-component sort equations. No fact document of this milestone names a correspondence between
           components (linking is I19), so none is emitted.

Lexical rules read only what the sidecar names: a state field's doc, a record field's doc (doc_fields), a
parameter's constants_doc ("match": "doc"), and library builtin or facts definition names ("match":
"builtin", seeding the result of each call). Ghost state, ghost record fields and their docs are not read.
No rule keys on a fact variable's name.

src: the span of the facts entry a constraint comes from (holon.sorts.flow.Ctx.src); null for types, seeds,
writer sets, observers and definitions without a src.
"""
from __future__ import annotations

import re

from . import grammar as G
from .flow import Program


class ConstraintError(ValueError):
    pass


# ------------------------------------------------------------------ text
_PREC = {"?": 0, "||": 1, "&&": 2, "<": 3, "<=": 3, ">": 3, ">=": 3, "==": 3, "!=": 3, "+": 4, "-": 4, "!": 5}


def text(e, ctx: int = 0) -> str:
    """Infix text of a DSL expression (for constraint texts only)."""
    if isinstance(e, bool):
        return "true" if e else "false"
    if isinstance(e, (int, str)):
        return str(e)
    if not isinstance(e, list) or not e:
        return repr(e)
    op, *a = e
    if op in ("+", "-") and len(a) == 2:
        p = _PREC[op]
        out = f"{text(a[0], p)} {op} {text(a[1], p + 1)}"
    elif op in _PREC and op not in ("?", "!") and len(a) >= 2:
        p = _PREC[op]
        out = f" {op} ".join(text(x, p + 1) for x in a)
    elif op == "!":
        p = _PREC[op]
        out = "!" + text(a[0], p + 1)
    elif op == "?":
        p = 0
        out = f"{text(a[0], 1)} ? {text(a[1], 1)} : {text(a[2], 0)}"
    elif op == "call":
        return f"{a[0]}(" + ", ".join(text(x) for x in a[1:]) + ")"
    elif op == "get":
        return f"{text(a[0], 6)}.{a[1]}"
    elif op == "mk":
        return a[0] + "{" + ", ".join(f"{k}: {text(v)}" for k, v in a[1].items()) + "}"
    elif op == "with":
        return text(a[1], 6) + "{" + ", ".join(f"{k} := {text(v)}" for k, v in a[2].items()) + "}"
    elif op == "list":
        return "[" + ", ".join(text(x) for x in a[1:]) + "]"
    else:
        return repr(e)
    return f"({out})" if p < ctx else out


# ------------------------------------------------------------------ seeds
def _doc_sources(facts: dict) -> list[tuple[str, str, str]]:
    """(key, what, doc) for every doc a "doc" rule may read: state fields, record fields (doc_fields) and
    parameters (constants_doc). Ghosts are left out."""
    out = []
    ghosts = set(facts.get("ghost_state", []))
    for row in facts.get("state", []):
        if len(row) > 2 and row[0] not in ghosts and isinstance(row[2], str):
            out.append((row[0], f"doc of state field {row[0]}", row[2]))
    for tname, t in facts.get("types", {}).items():
        gf = set(t.get("ghost", []))
        for g, d in t.get("doc_fields", {}).items():
            if g not in gf and isinstance(d, str):
                out.append((f"{tname}.{g}", f"doc of field {g} of {tname}", d))
    for name, d in facts.get("constants_doc", {}).items():
        if isinstance(d, str):
            out.append((name, f"constants_doc of {name}", d))
    return out


def seed_grounds(facts: dict, prog: Program, seeds: dict) -> dict[str, list[tuple[str, str]]]:
    """variable -> [(ground, sort text)] from the sidecar's lexical rules and the structural facts."""
    rules = seeds.get("lexical", [])
    for r in rules:
        if r.get("match") not in ("doc", "builtin"):
            raise ConstraintError(f"seed rule {r.get('id')}: match {r.get('match')!r} is not doc or builtin")
        G.canonical(r["sort"])
    out: dict[str, list] = {}
    for key, _what, doc in _doc_sources(facts):
        if key not in prog.keys or prog.keys[key]["type"] not in ("Nat", "List<Nat>"):
            continue
        for r in rules:
            if r["match"] == "doc" and re.search(r["pattern"], doc):
                out.setdefault(key, []).append((f"lexical:{r['id']}", G.canonical(r["sort"])))
    for e in prog.events:
        if e[0] == "call":
            _, name, var, _ctx = e
            for r in rules:
                if r["match"] == "builtin" and re.search(r["pattern"], name):
                    out.setdefault(var, []).append((f"lexical:{r['id']}", G.canonical(r["sort"])))
    delay = facts.get("disch", {}).get("delay")
    if isinstance(delay, dict) and "action" in delay and "input" in delay:
        key = f"{delay['action']}.{delay['input']}"
        if key in prog.keys and prog.keys[key]["type"] == "Nat":
            out.setdefault(key, []).append(("structural:disch.delay", "Dur"))
    return out


# ------------------------------------------------------------------ build
def build_02(model: str, facts: dict, prog: Program, seeds: dict) -> list[dict]:
    cs: list[dict] = []

    def add(kind: str, vars_: list, src, txt: str, **extra) -> None:
        c = {"model": model, "kind": kind, "vars": list(vars_), "src": src, "text": txt}
        c.update(extra)
        cs.append(c)

    for key in sorted(prog.keys):
        ty = prog.keys[key]["type"]
        if ty in ("Bool", "List<Bool>"):
            add("type", [key], None, f"{key} : {ty} (facts type)", sort="Bool")
    grounds = seed_grounds(facts, prog, seeds)
    for var in sorted(grounds):
        gs = sorted(set(grounds[var]))
        sort = G.render(G.union([G.parse(s) for _, s in gs]))
        add("seed", [var], None, f"{var} : {sort} ({', '.join(g for g, _ in gs)})",
            sort=sort, grounds=sorted({g for g, _ in gs}))
    for e in prog.events:
        kind = e[0]
        if kind == "flow":
            _, a, b, ctx = e
            add("flow", [a, b], ctx.src, f"{ctx.actor}: {a} flows into {b}")
        elif kind == "affine":
            _, op, lhs, rhs, out, node, ctx = e
            add("affine", [lhs, rhs, out], ctx.src, f"{ctx.actor}: {text(node)} ({lhs} {op} {rhs} = {out})", op=op)
        elif kind == "compare":
            _, op, x, y, node, ctx, via = e
            extra = {"op": op}
            if via:
                extra["via"] = via
                txt = f"{ctx.actor}: {via}: {x} {op} an element {y}"
            else:
                txt = f"{ctx.actor}: {text(node)} ({x} {op} {y})"
            add("compare", [x, y], ctx.src, txt, **extra)
    for reg in sorted(prog.registers):
        ws = sorted(prog.writers.get(reg, ()))
        if ws:
            add("writer", [reg], None, f"{reg} is written by {', '.join(ws)}", writers=ws)
    return cs


SECTIONS_01 = {"facts_version", "target", "extraction", "types", "functions", "assumptions"}


def build_01(model: str, facts: dict) -> tuple[dict, list[dict]]:
    """Keys and type constraints of a holon-facts/0.1 document (see holon.sorts.grammar). Only "types" is
    read: functions are byte codecs (layouts, no Nat arithmetic or value flow between fields), assumptions are
    text; any other section is an error."""
    unknown = sorted(set(facts) - SECTIONS_01)
    if unknown:
        raise ConstraintError(f"unmapped facts sections {unknown}")
    keys, cs = {}, []
    for tname, t in facts.get("types", {}).items():
        if t.get("kind") != "record":
            continue
        for fld in t.get("fields", []):
            key = f"{tname}.{fld['name']}"
            w = fld.get("width")
            if not isinstance(w, int) or w <= 0:
                raise ConstraintError(f"types.{tname}.{fld.get('name')}: width {w!r} is not a positive byte count")
            keys[key] = {"type": f"Bytes{w}", "binder": "field", "ghost": False}
            cs.append({"model": model, "kind": "type", "vars": [key], "src": None, "sort": f"Mach({8 * w})",
                       "text": f"{key} : Mach({8 * w}) ({w}-byte field of {tname})"})
    return keys, cs


def number(constraints: list[dict]) -> list[dict]:
    """Stable ids: <model>.c<nnnn> in order within each model."""
    count: dict[str, int] = {}
    out = []
    for c in constraints:
        count[c["model"]] = count.get(c["model"], 0) + 1
        out.append({"id": f"{c['model']}.c{count[c['model']]:04d}", **c})
    return out
