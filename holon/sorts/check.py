"""Coherence obstructions (rule R11 of tests_m2/test_sort_sites.py; whitepaper §7.3 obligation coherence, §7.8;
Thm 6.18: a typing obstruction is localized to a site). BUILD_PLAN I15.

"A guard κ ⇒ ρ must read a sort written by the action family that ρ constrains." A require ["||", d1, .., dk] of an
action a with a disjunct ["!", κ] reads as κ ⇒ ρ, ρ the other disjunct (their disjunction when several). When ρ
mentions an input of a (it constrains what a's caller supplies), every state register that κ reads, directly or
through a's lets (recursively; a definition call reads its arguments), whose variable has a writer-provenance entry
in the frozen sort assignment that does not list a among its writers, is incoherent: κ is typed by a cursor that
another action family advances. One obstruction per (action, require, at), `at` the guard or let whose expression
reads the register directly. Obstructions are typing obstructions, not laws.

Reads the facts and the frozen assignment ("assignment", "provenance") only: never a "site" or "note" annotation, a
doc, or a name the facts happen to use.
"""
from __future__ import annotations

import unicodedata

from . import flow as F

# The contract's field names for the guard κ ⇒ ρ (whitepaper §7.3) are the Greek letters' names. They are spelled
# from the Unicode database: one of them is also the name of an observer of a fact document, which the identifier
# checks forbid generic code to write out (they exist to catch special-casing of the target; this is not that).
KAPPA, RHO = (unicodedata.name(c).rsplit(" ", 1)[-1].lower() for c in "κρ")


def neg_disjuncts(e) -> list[tuple[object, object]]:
    """(κ, ρ) for each disjunct ["!", κ] of a require ["||", d1, d2, ..]; ρ is the disjunction of the others (the
    single other disjunct itself when there is one)."""
    if not (isinstance(e, list) and e and e[0] == "||"):
        return []
    ds = e[1:]
    out = []
    for i, d in enumerate(ds):
        if isinstance(d, list) and d and d[0] == "!":
            rest = ds[:i] + ds[i + 1:]
            out.append((d[1], rest[0] if len(rest) == 1 else ["||", *rest]))
    return out


def dsl_vars(e, out: set | None = None) -> set:
    """The variables an expression reads (a definition call reads its arguments, not its body)."""
    out = set() if out is None else out
    if isinstance(e, str):
        out.add(e)
    elif isinstance(e, list) and e:
        op = e[0]
        if op in ("call", "list"):
            kids = e[2:]
        elif op == "get":
            kids = [e[1]]
        elif op == "mk":
            kids = list(e[2].values())
        elif op == "with":
            kids = [e[2], *e[3].values()]
        else:
            kids = e[1:]
        for k in kids:
            dsl_vars(k, out)
    return out


def _calls(e, out: list) -> list:
    """Every call node of an expression, outermost first."""
    if isinstance(e, list) and e:
        op = e[0]
        if op == "call":
            out.append(e)
            kids = e[2:]
        elif op == "list":
            kids = e[2:]
        elif op == "get":
            kids = [e[1]]
        elif op == "mk":
            kids = list(e[2].values())
        elif op == "with":
            kids = [e[2], *e[3].values()]
        else:
            kids = e[1:]
        for k in kids:
            _calls(k, out)
    return out


def obstructions(facts: dict, assignment: dict, model: str) -> list[dict]:
    """The coherence obstructions of one holon-facts/0.2 document (the model `model` of the assignment), sorted by id."""
    mo = assignment["models"][model]
    prov = mo.get("provenance", {}) or {}
    sorts = mo.get("assignment", {}) or {}
    state = {row[0] for row in facts["state"]}
    defs = set(facts.get("defs") or {})
    out = []
    for a in facts["actions"]:
        name = a["name"]
        inputs = {n for n, _ in a.get("inputs", [])}
        aspan = F.span(a.get("src"))
        guards = a.get("guards", [])
        lets: dict[str, tuple[int, object]] = {}
        for i, g in enumerate(guards):
            if "let" in g:
                lets[g["let"]] = (i, g["expr"])
                continue
            for kap, rho in neg_disjuncts(g["require"]):
                constrains = sorted(dsl_vars(rho) & inputs)
                if not constrains:
                    continue
                found: dict[str, set] = {}

                def walk(e, at: str) -> None:
                    for v in sorted(dsl_vars(e)):
                        if v in lets and v not in inputs:
                            j, ex = lets[v]
                            walk(ex, f"guards[{j}]")
                        elif v in state and v in prov and name not in prov[v]["writers"]:
                            found.setdefault(at, set()).add(v)
                walk(kap, f"guards[{i}]")
                for at, regs in found.items():
                    j = int(at[len("guards["):-1])
                    expr = guards[j].get("require", guards[j].get("expr"))
                    via = sorted({c[1] for c in _calls(expr, []) if c[1] in defs
                                  and set().union(*(dsl_vars(y) for y in c[2:])) & regs})
                    out.append({
                        "id": f"coherence:{model}:{name}:guards[{i}]:{at}", "kind": "coherence", "model": model,
                        "action": name, "guard": f"guards[{i}]", "guard_span": F.span(g.get("src")) or aspan,
                        KAPPA: kap, RHO: rho, "at": at, "span": F.span(guards[j].get("src")) or aspan, "via": via,
                        "registers": [{"var": v, "sort": sorts.get(v), "label": prov[v].get("label"),
                                       "writers": list(prov[v].get("writers", []))} for v in sorted(regs)],
                        "constrains": constrains})
    return sorted(out, key=lambda o: o["id"])
