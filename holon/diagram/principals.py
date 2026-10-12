"""Principal classes Π (whitepaper §8.3: a caller type plus a permission predicate; Def 4.2).

A class is named by the `principal` label of the actions in it, up to its parenthetical remark
("anyone (through the messenger; ...)" is the class `anyone`). Its permission predicate is taken
from the actions' guards: the requires that mention the caller input (`who` in facts 0.2) once lets
are substituted. Every action of a class must carry the same permission guards, else the class has
no predicate and the disagreement is reported. A class whose actions test no caller has predicate
null: `anyone`, and `environment`, the class of actions no principal calls (time progress, whose
action has no caller input at all).

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


def principal_classes(facts: dict, walker_for) -> tuple[list[dict], dict[str, str], list[str]]:
    """(classes, action -> class id, problems). `walker_for()` returns a fresh access Walker, used to
    compute the state each predicate reads."""
    actions = facts.get("actions", [])
    params = set(facts.get("params", {}))
    state = {n for n, *_ in facts["state"]}
    by_class: dict[str, list[dict]] = {}
    of: dict[str, str] = {}
    for a in actions:
        if "principal" not in a:
            raise PrincipalError(f"action {a['name']} names no principal")
        cid = class_id(a["principal"])
        by_class.setdefault(cid, []).append(a)
        of[a["name"]] = cid
    out, problems = [], []
    for cid in sorted(by_class):
        acts = by_class[cid]
        callers = sorted({t for a in acts for n, t in a["inputs"] if n == CALLER})
        if len(callers) > 1:
            raise PrincipalError(f"class {cid}: caller input {CALLER} has types {callers}")
        guards = {a["name"]: permission_guards(a) for a in acts}
        keys = {_key(g) for g in guards.values()}
        predicate, reasons, reads, used_params = None, [], [], []
        permissionless = len(keys) == 1 and not next(iter(guards.values()))
        if len(keys) != 1:
            problems.append(f"principal class {cid}: actions disagree on the permission guard: "
                            + "; ".join(f"{n}: {[render(g['expr']) for g in gs]}" for n, gs in sorted(guards.items())))
        else:
            gs = next(iter(guards.values()))
            if gs:
                exprs = [g["expr"] for g in gs]
                predicate = exprs[0] if len(exprs) == 1 else ["&&", *exprs]
                reasons = sorted({g["reason"] for g in gs})
                w = walker_for()
                w.read(predicate, Scope(state, {n for a in acts for n, _ in a["inputs"]}, params))
                reads = sorted({f for f, _ in w.reads})
                used_params = sorted(free_vars(predicate) & params)
        if cid == ENVIRONMENT and (callers or predicate is not None):
            problems.append(f"principal class {cid}: an environment action has a caller or a permission guard")
        out.append({
            "id": cid,
            "labels": sorted({a["principal"] for a in acts}),
            "caller": callers[0] if callers else None,
            "caller_input": CALLER if callers else None,
            "predicate": predicate,
            "predicate_text": render(predicate, facts.get("defs", {})) if predicate is not None else None,
            "guard_reasons": reasons,
            "reads": reads,
            "params": used_params,
            "actions": sorted(a["name"] for a in acts),
            "permissionless": permissionless,
        })
    return out, of, problems
