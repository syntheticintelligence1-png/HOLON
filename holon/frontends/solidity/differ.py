"""Differ: compare extracted transition facts against the hand-written facts.

The extractor (holon.frontends.solidity.extract) never reads the hand facts;
this differ is the only component allowed to read both sides.

For every hand-written guard (require/let) and every hand-written write
(effects entry) the differ reports one of:

  - "recovered": canonical-equal item exists on the extracted side;
  - "strengthened": the extracted item is strictly more precise (a guard the
    hand dropped, or a write refined by an emitted require);
  - "debt:<kind>": not recovered, with a reason string. Kinds mirror the
    coverage debt kinds used by the extractor (unmodelled_value, oracle_gap,
    hand_simplification, not_extracted).

Output is byte-deterministic: sorted keys, sorted items, no timestamps.
"""

from __future__ import annotations

import json

from .sexpr import normalize


def _canon(e):
    return repr(normalize(e))


def _let_env(guards):
    """name -> expr for the {'let': name, 'expr': e} items in `guards`, in order."""
    env = {}
    for g in guards:
        if "let" in g:
            env[g["let"]] = g["expr"]
    return env


def _expand(e, env, depth=0):
    """Replace leaf names bound in `env` by their exprs (bounded expansion)."""
    if depth > 8:
        return e
    if isinstance(e, str) and e in env and env[e] != e:
        return _expand(env[e], env, depth + 1)
    if isinstance(e, list):
        return [_expand(x, env, depth) for x in e]
    return e


def _canon_expanded(e, env):
    return _canon(_expand(e, env))


def _classify_guard(hand, extracted, h_env, e_env):
    """Decide whether an extracted guard recovers `hand` (expanded-canonical)."""
    hc = _canon_expanded(hand.get("require", hand.get("let")), h_env)
    for x in extracted:
        xf = x.get("require", x.get("let"))
        if _canon_expanded(xf, e_env) == hc:
            return True, None
        # let-names are bound vars: compare raw too in case both sides use them
        if _canon(xf) == _canon(hand.get("require", hand.get("let"))):
            return True, None
    return False, hc


def diff_action(hand_a, ext_a, spec_guards=None, spec_fields=None):
    """Return {recovered_from_ast, spec_bound, missing, extra}.

    `hand_a`/`ext_a` are action dicts: guards (require/let) + effects.
    spec_guards: indices of extracted guards whose value is spec-bound.
    spec_fields: extracted effect fields whose value is spec-bound.
    A matched item is counted `spec_bound`, never `recovered_from_ast`, when the
    extracted value it matched came from the spec rather than the AST.
    """
    spec_guards = spec_guards or set()
    spec_fields = spec_fields or set()
    hg = hand_a.get("guards", [])
    eg = ext_a.get("guards", [])
    h_env, e_env = _let_env(hg), _let_env(eg)

    used = [False] * len(eg)
    rec_ast, rec_spec, missing = 0, 0, []
    for g in hg:
        if "require" in g:
            tgt, tgt_env, src = g["require"], h_env, "require"
        else:
            tgt, tgt_env, src = g["expr"], h_env, "let"
        found = -1
        hc = _canon_expanded(tgt, tgt_env)
        for i, x in enumerate(eg):
            if used[i]:
                continue
            xf = x.get("require", x.get("expr"))
            if _canon_expanded(xf, e_env) == hc or _canon(xf) == _canon(tgt):
                found = i
                break
        if found >= 0:
            used[found] = True
            if found in spec_guards:
                rec_spec += 1
            else:
                rec_ast += 1
            continue
        # classify why it was not recovered
        kind, reason = _miss_reason(g, eg, src)
        missing.append({"item": {src: tgt}, "kind": kind, "reason": reason})

    # extracted guards not consumed by the match are strengthenings
    extra = [
        {"item": eg[i], "kind": "strengthened",
         "reason": "extracted guard/write not present in hand facts"}
        for i in range(len(eg)) if not used[i] and "require" in eg[i]
    ]

    he, ee = hand_a.get("effects", {}), ext_a.get("effects", {})
    wr_missing = []
    for field in sorted(he):
        hv = he[field]
        if field in ee and (_canon_expanded(ee[field], e_env) == _canon_expanded(hv, h_env)
                            or _canon(ee[field]) == _canon(hv)):
            if field in spec_fields:
                rec_spec += 1
            else:
                rec_ast += 1
            continue
        kind, reason = ("hand_simplification", "hand write simplified relative to extracted semantics") \
            if field in ee else ("not_extracted", f"hand effect on '{field}' has no extracted counterpart")
        wr_missing.append({"item": {field: hv}, "kind": kind, "reason": reason})
    for field in sorted(ee):
        if field not in he:
            extra.append({"item": {field: ee[field]}, "kind": "strengthened",
                          "reason": "extracted effect not present in hand facts"})

    return {
        "recovered_from_ast": rec_ast,
        "spec_bound": rec_spec,
        "missing": missing + wr_missing,
        "extra": extra,
    }


def _miss_reason(g, eg, src):
    """Heuristic reason a hand guard was not recovered."""
    expr = g.get("require", g.get("expr"))
    s = json.dumps(expr)
    if src == "let":
        return ("hand_simplification",
                "hand let-binding does not match any extracted let; the extracted side "
                "models the value differently (e.g. a full ?-merge across branches)")
    if "challengeSuccess" in s or "nth_ch" in s:
        return ("oracle_gap", "challenge-state predicate not fully recovered")
    if is_oracle(s):
        return ("oracle_gap", "hand guard relies on an oracle the extractor models differently")
    return ("not_extracted", "hand guard has no extracted counterpart")


def is_oracle(s):
    return any(k in s for k in ("proof", "slash", "isActive", "popCrossDomainMessage"))


def spec_index(coverage):
    """Map spec_bound coverage items to per-action guard indices / effect fields.

    Elements look like 'action:<name>.guards[<i>]' or 'action:<name>.effects.<f>'.
    Returns {name: (set_of_guard_indices, set_of_field_names)}.
    """
    out = {}
    for it in (coverage or {}).get("items", []):
        if it.get("kind") != "spec_bound":
            continue
        el = it.get("element", "")
        if el.startswith("action:") and ".guards[" in el:
            name, rest = el[len("action:"):].split(".guards[", 1)
            out.setdefault(name, (set(), set()))[0].add(int(rest.rstrip("]")))
        elif el.startswith("action:") and ".effects." in el:
            name, f = el[len("action:"):].split(".effects.", 1)
            out.setdefault(name, (set(), set()))[1].add(f)
    return out


def diff_facts(hand, ext, coverage=None):
    """Diff two holon-facts/0.2 documents. Returns a deterministic report.

    `coverage` is the extractor's coverage JSON; its spec_bound items decide
    which matched items count as spec_bound rather than recovered_from_ast.
    """
    si = spec_index(coverage)
    h_actions = {a["name"]: a for a in hand.get("actions", [])}
    e_actions = {a["name"]: a for a in ext.get("actions", [])}
    report = {}
    for name in sorted(set(h_actions) | set(e_actions)):
        if name not in h_actions:
            report[name] = {"recovered_from_ast": 0, "spec_bound": 0, "missing": [], "extra": [
                {"item": {"action": name}, "kind": "strengthened",
                 "reason": "extracted action not in hand facts"}]}
            continue
        if name not in e_actions:
            report[name] = {"recovered_from_ast": 0, "spec_bound": 0, "missing": [
                {"item": {"action": name}, "kind": "not_extracted",
                 "reason": "hand action has no extracted counterpart"}], "extra": []}
            continue
        sg, sf = si.get(name, (set(), set()))
        report[name] = diff_action(h_actions[name], e_actions[name], sg, sf)
    # defs
    h_defs, e_defs = hand.get("defs", {}), ext.get("defs", {})
    prov = ext.get("provenance", {})
    def_missing = []
    def_spec = 0
    for k in sorted(h_defs):
        if k not in e_defs:
            def_missing.append({"item": {"def": k}, "kind": "not_extracted",
                                "reason": "hand def has no extracted counterpart"})
        elif _canon(e_defs[k].get("body")) != _canon(h_defs[k].get("body")):
            def_missing.append({"item": {"def": k}, "kind": "diverged",
                                "reason": "extracted def body differs canonically from hand def"})
        elif prov.get(f"defs.{k}") == "spec":
            def_spec += 1
    report["_defs"] = {"recovered_from_ast": sum(1 for k in h_defs if k in e_defs) - len(def_missing) - def_spec,
                       "spec_bound": def_spec,
                       "missing": def_missing, "extra": [
            {"item": {"def": k}, "kind": "strengthened", "reason": "extracted def not in hand facts"}
            for k in sorted(e_defs) if k not in h_defs]}
    return report


def summary(report):
    """One-line rollup of a differ report."""
    rec = sum(v.get("recovered_from_ast", v.get("recovered", 0)) for v in report.values())
    sb = sum(v.get("spec_bound", 0) for v in report.values())
    miss = sum(len(v["missing"]) for v in report.values())
    extra = sum(len(v["extra"]) for v in report.values())
    unaccounted = sum(1 for v in report.values()
                      for m in v["missing"] if m["kind"] == "not_extracted")
    return (f"recovered_from_ast={rec} spec_bound={sb} missing={miss} "
            f"extra={extra} unaccounted_missing={unaccounted}")
