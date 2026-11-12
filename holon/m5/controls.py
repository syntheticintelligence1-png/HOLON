"""The constructed controls of definitions.controls (I54): 14 game controls (L6) and 12 intent controls (L10).

  python -m holon m5 controls [--root DIR] [--check]

writes spec/M5/controls/games/<id>.json, spec/M5/controls/intent/<id>.json and <id>.sol. A game control's truth is
computed here by a depth-first search over the schedules of each class (game_truth); the instrument recomputes it by
its own enumeration. Names are tokens of sha256('<family>/<n>/<role>'), so no other module can name a control without
copying a token (K4 checks that none does).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .common import ROOT, dumps

GAME_FAMILIES = ("free_trigger", "profit", "recoup", "deep", "trusted_only", "costly", "incomparable")
INTENT_FAMILIES = ("bound", "access", "monotone")
INSTANCES = (1, 2)
SEMANTICS = ("single deviator: one class acts, the others take no action; each action at most once per schedule; "
             "holdings start at 0; payoff at the schedule's end")


def _t(family: str, n: int, role: str) -> str:
    return hashlib.sha256(f"{family}/{n}/{role}".encode()).hexdigest()[:6]


def _action(aid, by, guard=(), effect=(), flows=None) -> dict:
    return {"id": aid, "by": list(by), "guard": [list(g) for g in guard], "effect": [list(e) for e in effect],
            "flows": flows or {}}


def game(family: str, n: int) -> dict:
    T = lambda role: _t(family, n, role)  # noqa: E731
    hi, lo = "a" + T("trusted"), "a" + T("untrusted")
    a0, a1, v = "s" + T("asset0"), "s" + T("asset1"), "v" + T("var")
    f = lambda role: "f" + T(role)  # noqa: E731
    assets, horizon = [a0], 2
    if family == "free_trigger":
        acts = [_action(f("poke"), [lo], effect=[("add", v, n)])]
        bad, wit = [("ge", v, 1)], [(f("poke"), lo)]
    elif family == "profit":
        acts = [_action(f("claim"), sorted([hi, lo]), [("eq", v, 0)], [("set", v, 1)], {"caller": {a0: n}})]
        bad, wit = [("ge", v, 1)], [(f("claim"), lo)]
    elif family == "recoup":
        acts = [_action(f("deposit"), [lo], [("eq", v, 0)], [("set", v, 1)], {"caller": {a0: -n}}),
                _action(f("trigger"), [lo], [("eq", v, 1)], [("set", v, 2)]),
                _action(f("withdraw"), [lo], [("eq", v, 2)], [("set", v, 3)], {"caller": {a0: n}})]
        bad, wit, horizon = [("ge", v, 2)], [(f("deposit"), lo), (f("trigger"), lo)], 3
    elif family == "deep":
        horizon = n + 1
        acts = [_action(f("force"), [hi], effect=[("set", v, horizon + 1)])]
        acts += [_action(f(f"step{i}"), [lo], [("eq", v, i)], [("set", v, i + 1)]) for i in range(horizon + 1)]
        bad, wit = [("ge", v, horizon + 1)], [(f("force"), hi)]
    elif family == "trusted_only":
        acts = [_action(f("set"), [hi], effect=[("set", v, n)]), _action(f("ping"), [lo])]
        bad, wit = [("ge", v, 1)], [(f("set"), hi)]
    elif family == "costly":
        acts = [_action(f("challenge"), [lo], [("eq", v, 0)], [("set", v, 1)], {"caller": {a0: -n}}),
                _action(f("refund"), [hi], [("eq", v, 1)], [("set", v, 2)], {lo: {a0: n}})]
        bad, wit = [("ge", v, 1)], [(f("challenge"), lo)]
    elif family == "incomparable":
        assets = [a0, a1]
        acts = [_action(f("swap"), [lo], effect=[("set", v, 1)], flows={"caller": {a0: n, a1: -n}})]
        bad, wit = [("ge", v, 1)], [(f("swap"), lo)]
    else:
        raise ValueError(f"unknown game family {family!r}")
    doc = {"id": f"g_{family}_{n}", "family": family, "semantics": SEMANTICS,
           "actors": [{"id": hi, "trusted": True}, {"id": lo, "trusted": False}], "assets": assets, "vars": {v: 0},
           "actions": acts, "bad": [list(b) for b in bad], "horizon": horizon,
           "witness": [{"action": a, "caller": c} for a, c in wit]}
    doc["truth"] = game_truth(doc)
    return doc


def _cond(c, state) -> bool:
    op, var, k = c
    x = state[var]
    if op == "ge":
        return x >= k
    if op == "eq":
        return x == k
    if op == "lt":
        return x < k
    raise ValueError(op)


def _class_payoffs(doc: dict, actor: str) -> tuple[set, int | None]:
    """The payoff classes of every triggering schedule of one actor, and the shortest nonneg one (depth-first)."""
    mine = [a for a in doc["actions"] if actor in a["by"]]
    found, shortest = set(), [None]

    def go(state, holdings, used, triggered, length):
        if length and triggered:
            mine_h = [holdings.get(s, 0) for s in doc["assets"]]
            if all(x >= 0 for x in mine_h):
                p = "nonneg"
            elif all(x <= 0 for x in mine_h):
                p = "negative"
            else:
                p = "incomparable"
            found.add(p)
            if p == "nonneg" and (shortest[0] is None or length < shortest[0]):
                shortest[0] = length
        for i, a in enumerate(mine):
            if i in used or not all(_cond(g, state) for g in a["guard"]):
                continue
            st = dict(state)
            for op, var, k in a["effect"]:
                st[var] = st[var] + k if op == "add" else k
            h = dict(holdings)
            for who, d in a["flows"].items():
                if (actor if who == "caller" else who) == actor:
                    for s, q in d.items():
                        h[s] = h.get(s, 0) + q
            go(st, h, used | {i}, triggered or all(_cond(b, st) for b in doc["bad"]), length + 1)

    go(dict(doc["vars"]), {}, frozenset(), False, 0)
    return found, shortest[0]


def game_truth(doc: dict) -> dict:
    classes, depth = {}, None
    for a in doc["actors"]:
        pays, short = _class_payoffs(doc, a["id"])
        if "nonneg" in pays:
            classes[a["id"]] = "rational"
        elif pays <= {"negative"}:
            classes[a["id"]] = "irrational"
        else:
            classes[a["id"]] = "UNKNOWN"
        if not a["trusted"] and short is not None:
            depth = short if depth is None else min(depth, short)
    untrusted = [classes[a["id"]] for a in doc["actors"] if not a["trusted"]]
    if "rational" in untrusted:
        v = "rational"
    elif untrusted and all(x == "irrational" for x in untrusted):
        v = "irrational"
    else:
        v = "UNKNOWN"
    return {"verdict": v, "classes": classes, "depth": depth}


def intent(family: str, wrong: bool, n: int) -> dict:
    kind = "wrong" if wrong else "right"
    name = "C" + _t(f"{family}_{kind}", n, "contract")
    lines = ["// SPDX-License-Identifier: UNLICENSED", "pragma solidity 0.8.24;", "", f"contract {name} {{"]
    if family == "bound":
        rate = 2 * n if wrong else n
        clause = f"@notice The fee charged is at most {n} percent of the amount."
        lines += [f"    /// {clause}", "    function fee(uint256 amount) external pure returns (uint256) {",
                  f"        return (amount * {rate}) / 100;", "    }"]
        why = f"rate {rate} percent against the documented bound {n}"
    elif family == "access":
        clause = "@notice Only the owner can pause the contract."
        lines += ["    address public owner;", "    bool public stopped;", "", "    constructor() {",
                  "        owner = msg.sender;", "    }", "", f"    /// {clause}", "    function pause() external {"]
        if not wrong:
            lines.append("        require(msg.sender == owner);")
        lines += ["        stopped = true;", "    }"]
        why = "pause has no owner check" if wrong else "pause checks the owner"
    elif family == "monotone":
        clause = "@notice The count never decreases."
        lines += ["    uint256 public count;", "", f"    /// {clause}", "    function step() external {"]
        if wrong:
            lines += [f"        if (count > {n}) {{", "            count -= 1;", "        } else {",
                      f"            count += {n + 1};", "        }"]
        else:
            lines.append(f"        count += {n};")
        lines.append("    }")
        why = "step decreases the count once it exceeds the threshold" if wrong else "step only adds"
    else:
        raise ValueError(f"unknown intent family {family!r}")
    lines.append("}")
    return {"id": f"i_{family}_{kind}_{n}", "family": family, "file": f"{name}.sol", "source": "\n".join(lines) + "\n",
            "clause": clause, "truth": {"obstruction": wrong, "why": why}}


def all_games() -> list[dict]:
    return [game(f, n) for f in GAME_FAMILIES for n in INSTANCES]


def all_intents() -> list[dict]:
    return [intent(f, w, n) for f in INTENT_FAMILIES for w in (True, False) for n in INSTANCES]


def files(root: Path = ROOT) -> dict[Path, str]:
    base = Path(root) / "spec" / "M5" / "controls"
    out = {base / "games" / f"{g['id']}.json": dumps(g) for g in all_games()}
    for c in all_intents():
        out[base / "intent" / f"{c['id']}.json"] = dumps(c)
        out[base / "intent" / f"{c['id']}.sol"] = c["source"]
    return out


def write(root: Path = ROOT, check: bool = False) -> list[str]:
    """Write (or, with check, compare) every control file; the problems (check) or the paths written."""
    want = files(root)
    probs, done = [], []
    for d in sorted({p.parent for p in want}):
        if d.is_dir():
            for p in sorted(d.iterdir()):
                if p not in want:
                    probs.append(f"{p.relative_to(root)}: not a control file")
    for p, text in sorted(want.items()):
        have = p.read_text(encoding="utf-8") if p.is_file() else None
        if have != text:
            if check:
                probs.append(f"{p.relative_to(root)}: differs from the generated control")
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                done.append(p.relative_to(root).as_posix())
    return probs if check else done
