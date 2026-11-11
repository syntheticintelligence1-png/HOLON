"""A finding's witness game (key I56: G-W1..G-W5, G-T1..G-T4).

The strategy space is the finding's own REFUTED witness: a call schedule, run on the run member's model. A class may
run it iff every step's action's group is the class or anyone; its payoff is the flows to the schedule's callers
(holon.games.run). Rational iff the class may run it and that payoff is nonneg; otherwise UNKNOWN: a witness game
under-approximates a target's strategy space, so no target class is ever irrational.
"""
from __future__ import annotations

from .engine import finding_verdict
from .run import Ledger, Runner, classify


def _step(x) -> bool:
    return isinstance(x, dict) and isinstance(x.get("action"), str) and isinstance(x.get("env"), dict) \
        and isinstance(x.get("args"), dict)


def _lst(x):
    return list(x) if isinstance(x, list) else None


def schedule(rec: dict) -> tuple[list | None, str]:
    """(steps, form) or (None, reason): the witness-form table G-W1..G-W5."""
    w = rec.get("witness")
    if not isinstance(w, dict):
        return None, "the witness is not a call schedule"
    keys = set(w)
    if isinstance(w.get("steps"), list):
        seq, form = list(w["steps"]), "G-W1"
    elif {"prefix", "y", "t", "bonded", "chooser"} <= keys:
        p, t = _lst(w["prefix"]), _lst(w["t"])
        seq, form = (None if p is None or t is None else p + [w["y"]] + t), "G-W2"
    elif {"prefix", "x", "y", "t"} <= keys and "bonded" not in keys:
        p, t = _lst(w["prefix"]), _lst(w["t"])
        seq, form = (None if p is None or t is None else p + [w["x"], w["y"]] + t), "G-W3"
    elif {"prefix", "x"} <= keys and "y" not in keys:
        p = _lst(w["prefix"])
        seq, form = (None if p is None else p + [w["x"]]), "G-W4"
    else:
        return None, "the witness is not a call schedule (G-W5)"
    if not seq or any(s is None for s in seq):
        return None, "the witness's schedule refers to steps it does not hold (G-W5)"
    if not all(_step(s) for s in seq):
        return None, ("a step of the witness is not an explicit call (a reference into a corpus trace, or a "
                      "migration move) (G-W5)")
    return seq, form


def witness_game(rec: dict, runner: Runner) -> tuple[dict | None, str | None]:
    """(game, None) or (None, reason)."""
    t = runner.t
    steps, form = schedule(rec)
    if steps is None:
        return None, form
    member = runner.member
    if any(s["action"] not in runner.acts for s in steps):
        return None, f"a step is not an action of the run member {member} (G-T1)"
    probe = Ledger(set())
    statuses = runner.run(steps, [probe])
    if len(statuses) != len(steps) or any(x != "ok" for x in statuses):
        return None, f"the schedule does not run on the model from its initial state: {statuses} (G-T1)"
    groups = [t.klass(member, runner.acts[s["action"]]) for s in steps]
    callers = sorted({str(s["env"].get("caller", "")).lower() for s in steps})
    lg = Ledger(set(callers))
    runner.run(steps, [lg])
    pay = classify(lg.total())
    rows, legal = [], []
    for x in t.classes():
        ok = all(g is not None and g in (x, "anyone") for g in groups)
        if ok:
            legal.append(x)
        if ok and pay == "nonneg":
            rows.append({"class": x, "trusted": t.trusted[x], "verdict": "rational", "payoff": "nonneg",
                         "strategy_length": len(steps)})
        else:
            rows.append({"class": x, "trusted": t.trusted[x], "verdict": "UNKNOWN",
                         "payoff": (pay if pay != "undetermined" else None) if ok else None, "strategy_length": None})
    return {"form": form, "steps": steps, "groups": groups, "callers": callers, "classes": rows,
            "verdict": finding_verdict(rows), "payoff": pay, "legal": legal, "ledger": lg}, None
