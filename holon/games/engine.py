"""The complete solver of a game document (key I56: G-K1..G-K3; I54's semantics).

A game document (holon-game/0.1, the shape of I54's control documents): actors {id, trusted}, assets, vars, actions
{id, by, guard, effect, flows}, bad, witness. One actor acts (single deviator), the others take no action, each action
at most once, holdings start at 0, the payoff is read at the schedule's end. The search visits every schedule of
distinct actions, so its verdicts are unbounded (a schedule has at most as many steps as there are actions). It reads
no field but those: never the document's truth, id, family, file name or horizon field.
"""
from __future__ import annotations


def holds(conds, vs: dict) -> bool:
    for op, var, k in conds:
        x = vs[var]
        if op == "ge" and not x >= k or op == "eq" and not x == k or op == "lt" and not x < k:
            return False
        if op not in ("ge", "eq", "lt"):
            raise ValueError(f"unknown guard operator {op!r}")
    return True


def apply(effect, vs: dict) -> dict:
    out = dict(vs)
    for op, var, k in effect:
        if op == "add":
            out[var] = out[var] + k
        elif op == "set":
            out[var] = k
        else:
            raise ValueError(f"unknown effect {op!r}")
    return out


def sign(vec: list[int]) -> str:
    neg, pos = any(x < 0 for x in vec), any(x > 0 for x in vec)
    if not neg:
        return "nonneg"
    return "negative" if not pos else "incomparable"


def solve_actor(doc: dict, x: str) -> dict:
    """{verdict, strategy (shortest nonneg schedule or None), strategy_length, payoff, pays}."""
    assets = list(doc["assets"])
    mine = [a for a in doc["actions"] if x in a["by"]]
    pays: set = set()
    best: list = [None]

    def delta(a: dict, hold: list) -> list:
        h = list(hold)
        for who, d in a["flows"].items():
            if (x if who == "caller" else who) == x:
                for s, q in d.items():
                    h[assets.index(s)] += q
        return h

    def go(vs, hold, used, trig, path):
        for i, a in enumerate(mine):
            if i in used or not holds(a["guard"], vs):
                continue
            vs2 = apply(a["effect"], vs)
            h2 = delta(a, hold)
            t2 = trig or holds(doc["bad"], vs2)
            p2 = path + [a["id"]]
            if t2:
                p = sign(h2)
                pays.add(p)
                if p == "nonneg" and (best[0] is None or len(p2) < len(best[0])):
                    best[0] = p2
            go(vs2, h2, used | {i}, t2, p2)

    go(dict(doc["vars"]), [0] * len(assets), frozenset(), False, [])
    if "nonneg" in pays:
        v = "rational"
    elif pays <= {"negative"}:
        v = "irrational"
    else:
        v = "UNKNOWN"
    payoff = "nonneg" if v == "rational" else ("negative" if pays == {"negative"} else
                                                 ("incomparable" if "incomparable" in pays else None))
    return {"verdict": v, "strategy": best[0], "strategy_length": len(best[0]) if best[0] else None,
            "payoff": payoff, "pays": sorted(pays)}


def finding_verdict(classes: list[dict]) -> str:
    """I54's finding_verdict (definitions.L6)."""
    unt = [c["verdict"] for c in classes if not c["trusted"]]
    if "rational" in unt:
        return "rational"
    if unt and set(unt) == {"irrational"}:
        return "irrational"
    if unt and set(unt) <= {"irrational", "irrational_bounded"}:
        return "irrational_bounded"
    return "UNKNOWN"


def solve(doc: dict) -> dict:
    """{"classes": {actor: solve_actor}, "verdict", "horizon" (the number of actions)}."""
    cls = {a["id"]: solve_actor(doc, a["id"]) for a in sorted(doc["actors"], key=lambda a: a["id"])}
    rows = [{"class": a["id"], "trusted": a["trusted"], "verdict": cls[a["id"]]["verdict"]} for a in doc["actors"]]
    return {"classes": cls, "verdict": finding_verdict(rows), "horizon": len(doc["actions"])}
