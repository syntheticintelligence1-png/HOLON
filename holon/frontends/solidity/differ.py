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


def diff_action(hand_a, ext_a):
    """Return {recovered, strengthened, missing:[{item,kind,reason}], extra}.

    `hand_a`/`ext_a` are action dicts: guards (require/let) + effects.
    """
    hg = hand_a.get("guards", [])
    eg = ext_a.get("guards", [])
    h_env, e_env = _let_env(hg), _let_env(eg)

    used = [False] * len(eg)
    recovered, missing, strengthened = 0, [], 0
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
            recovered += 1
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
            recovered += 1
            continue
        kind, reason = ("hand_simplification", "hand write simplified relative to extracted semantics") \
            if field in ee else ("not_extracted", f"hand effect on '{field}' has no extracted counterpart")
        wr_missing.append({"item": {field: hv}, "kind": kind, "reason": reason})
    for field in sorted(ee):
        if field not in he:
            extra.append({"item": {field: ee[field]}, "kind": "strengthened",
                          "reason": "extracted effect not present in hand facts"})

    return {
        "recovered": recovered,
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


def diff_facts(hand, ext):
    """Diff two holon-facts/0.2 documents. Returns a deterministic report."""
    h_actions = {a["name"]: a for a in hand.get("actions", [])}
    e_actions = {a["name"]: a for a in ext.get("actions", [])}
    report = {}
    for name in sorted(set(h_actions) | set(e_actions)):
        if name not in h_actions:
            report[name] = {"recovered": 0, "missing": [], "extra": [
                {"item": {"action": name}, "kind": "strengthened",
                 "reason": "extracted action not in hand facts"}]}
            continue
        if name not in e_actions:
            report[name] = {"recovered": 0, "missing": [
                {"item": {"action": name}, "kind": "not_extracted",
                 "reason": "hand action has no extracted counterpart"}], "extra": []}
            continue
        report[name] = diff_action(h_actions[name], e_actions[name])
    # defs
    h_defs, e_defs = hand.get("defs", {}), ext.get("defs", {})
    def_missing = []
    for k in sorted(h_defs):
        if k not in e_defs:
            def_missing.append({"item": {"def": k}, "kind": "not_extracted",
                                "reason": "hand def has no extracted counterpart"})
        elif _canon(e_defs[k].get("body")) != _canon(h_defs[k].get("body")):
            def_missing.append({"item": {"def": k}, "kind": "diverged",
                                "reason": "extracted def body differs canonically from hand def"})
    report["_defs"] = {"recovered": sum(1 for k in h_defs if k in e_defs) - len(def_missing),
                       "missing": def_missing, "extra": [
            {"item": {"def": k}, "kind": "strengthened", "reason": "extracted def not in hand facts"}
            for k in sorted(e_defs) if k not in h_defs]}
    return report


def summary(report):
    """One-line rollup of a differ report."""
    rec = sum(v["recovered"] for v in report.values())
    miss = sum(len(v["missing"]) for v in report.values())
    extra = sum(len(v["extra"]) for v in report.values())
    unaccounted = sum(1 for v in report.values()
                      for m in v["missing"] if m["kind"] == "not_extracted")
    return f"recovered={rec} missing={miss} extra={extra} unaccounted_missing={unaccounted}"
