"""Principal classes Π (whitepaper §8.3: a caller type plus a permission predicate; Def 4.2).

Actions are classified by their permission guard (audit M2/1 F-M2-26), never by their label: the
permission guards of an action are the requires that mention the caller input (`who` in facts 0.2)
once lets are substituted, and two actions are in one class iff both have a caller input or neither
has, and their permission guards are the same set. The class's predicate is the conjunction of those
guards; a class whose actions test no caller has predicate null: `anyone`, and `environment`, the
class of actions no principal calls (time progress, whose action has no caller input at all).

The `principal` label is only the class's name, up to its parenthetical remark ("anyone (through the
messenger; ...)" names the class `anyone`). Every action of a guard class must carry the same name, and
two guard classes may not share one: a label/guard disagreement (a dropped or added permission guard,
a mislabelled action) raises PrincipalError, so the diagram build fails and so does an M2+ model's
generated perm_<class> (holon.gen.machine); it is never debt that erases the predicate.

The facts' `principals` section lists concrete principal ids (the instances the explorer and the
traces use); it does not say which class an id falls in, so the diagram records them as given.
"""
from __future__ import annotations

import json
import re

from .access import Scope, free_vars, render, subst

CALLER = "who"          # the caller input of a facts-0.2 action
ENVIRONMENT = "environment"


class PrincipalError(Exception):
    pass


def class_id(label: str) -> str:
    head = label.split("(", 1)[0].strip().lower()
    cid = re.sub(r"[^a-z0-9]+", "_", head).strip("_")
    if not cid:
        raise PrincipalError(f"principal label {label!r} names no class")
    return cid


def permission_guards(action: dict) -> list[dict]:
    """The requires of an action that test its caller, in guard order, each with its expression
    after let substitution (`expr`: over inputs, state fields and parameters only)."""
    inputs = {n for n, _ in action["inputs"]}
    if CALLER not in inputs:
        return []
    sub: dict = {}
    out = []
    for g in action["guards"]:
        if "let" in g:
            sub[g["let"]] = subst(g["expr"], sub)
        else:
            e = subst(g["require"], sub)
            if CALLER in free_vars(e):
                out.append({"expr": e, "reason": g["reason"]})
    return out


def _key(guards: list[dict]) -> str:
    return json.dumps(sorted(json.dumps(g["expr"], sort_keys=True) for g in guards))


def guard_classes(facts: dict) -> tuple[list[dict], dict[str, str]]:
    """(classes sorted by id, action -> class id): the actions grouped by permission guard (module docstring),
    each class named by its actions' common label. Raises PrincipalError on a label/guard disagreement.
    A class: {id, labels, caller, caller_input, predicate (DSL guard expression or None), predicate_text,
    guard_reasons, actions (sorted), permissionless}."""
    by_guard: dict[tuple, list[dict]] = {}
    for a in facts.get("actions", []):
        if "principal" not in a:
            raise PrincipalError(f"action {a['name']} names no principal")
        caller = any(n == CALLER for n, _ in a["inputs"])
        by_guard.setdefault((caller, _key(permission_guards(a))), []).append(a)
    named: dict[str, list[tuple]] = {}
    for key, acts in by_guard.items():
        ids = sorted({class_id(a["principal"]) for a in acts})
        if len(ids) != 1:
            raise PrincipalError(
                "label/guard disagreement: actions " + ", ".join(sorted(a["name"] for a in acts))
                + f" carry the same permission guard {_guard_text(permission_guards(acts[0]))} but the labels {ids}")
        named.setdefault(ids[0], []).append(key)
    for cid, keys in named.items():
        if len(keys) > 1:
            parts = [", ".join(sorted(a["name"] for a in by_guard[k])) + f": {_guard_text(permission_guards(by_guard[k][0]))}"
                     for k in sorted(keys, key=lambda k: json.dumps(k))]
            raise PrincipalError(f"label/guard disagreement: the label class {cid} holds actions with different "
                                 "permission guards (" + "; ".join(parts) + ")")
    out, of = [], {}
    for cid in sorted(named):
        acts = by_guard[named[cid][0]]
        callers = sorted({t for a in acts for n, t in a["inputs"] if n == CALLER})
        if len(callers) > 1:
            raise PrincipalError(f"class {cid}: caller input {CALLER} has types {callers}")
        gs = permission_guards(acts[0])
        exprs = [g["expr"] for g in gs]
        predicate = None if not exprs else (exprs[0] if len(exprs) == 1 else ["&&", *exprs])
        if cid == ENVIRONMENT and (callers or predicate is not None):
            raise PrincipalError(f"principal class {cid}: an environment action has a caller or a permission guard")
        for a in acts:
            of[a["name"]] = cid
        out.append({
            "id": cid,
            "labels": sorted({a["principal"] for a in acts}),
            "caller": callers[0] if callers else None,
            "caller_input": CALLER if callers else None,
            "predicate": predicate,
            "predicate_text": render(predicate, facts.get("defs", {})) if predicate is not None else None,
            "guard_reasons": sorted({g["reason"] for g in gs}),
            "actions": sorted(a["name"] for a in acts),
            "permissionless": not gs,
        })
    return out, of


def _guard_text(gs: list[dict]) -> str:
    return "[" + ", ".join(render(g["expr"]) for g in gs) + "]"


def principal_classes(facts: dict, walker_for) -> tuple[list[dict], dict[str, str], list[str]]:
    """(classes, action -> class id, problems) for the diagram: guard_classes plus, per class, the state its
    predicate reads and the parameters it uses. `walker_for()` returns a fresh access Walker. A label/guard
    disagreement raises PrincipalError (the build fails); `problems` is kept for the diagram's debt channel
    and is empty."""
    params = set(facts.get("params", {}))
    state = {n for n, *_ in facts["state"]}
    classes, of = guard_classes(facts)
    acts = {a["name"]: a for a in facts.get("actions", [])}
    out = []
    for c in classes:
        reads, used_params = [], []
        if c["predicate"] is not None:
            w = walker_for()
            w.read(c["predicate"], Scope(state, {n for a in c["actions"] for n, _ in acts[a]["inputs"]}, params))
            reads = sorted({f for f, _ in w.reads})
            used_params = sorted(free_vars(c["predicate"]) & params)
        out.append({k: c[k] for k in ("id", "labels", "caller", "caller_input", "predicate", "predicate_text",
                                      "guard_reasons")}
                   | {"reads": reads, "params": used_params, "actions": c["actions"], "permissionless": c["permissionless"]})
    return out, of, []
