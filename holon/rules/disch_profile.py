"""Rule DISCH II: discharge profiles in the §8.4 form, bounded dominance, the persistent variant and classification
(whitepaper Def 6.20, Prop 6.21, §5.7, §8.4, §10.7; BUILD_PLAN I32).

From the engine's answer (holon/js/profile.mjs) for one obligation (holon.analysis.abstraction), this module writes:

- the profile document: every outcome of the one-occurrence search, the frontier (Pareto-minimal outcomes) with a
  strategy each, the dominated outcomes with the frontier point that dominates each, the class (§5.7), the persistent
  frontier and its class, the schedule (H, principals, E-alphabet), each frontier point's game (its game alphabet,
  and either the priority list that wins every schedule with the table it plays, or the adversary's answers that
  beat every strategy), the robust frontier (the Pareto-minimal outcomes that some priority list wins against every
  schedule), the dominance alphabet and gaps, and the time abstraction;
- the laws, one statement each (the statement hash is the sha256 of its canonical JSON):
    L_dp_<ob>_point_<c>_<d>        every frontier point, the §8.4 form over the point's game alphabet;
    L_dp_<ob>_dominance            the bounded ∀ form: no strategy reaches a target outcome below the staircase;
    L_dp_<ob>_persistent_<c>_<d>   every persistent frontier point: a strategy with that outcome after which kappa
                                   is false;
    L_dp_<ob>_abstraction          the time abstraction's soundness at s*;
The rule is not registered in holon/rules/__init__.py nor in a rule catalog: it decides the test milestone T32, and
no generator closure imports it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROFILE_VERSION = "holon-disch-profile/0.1"
LAW_IR = "holon-disch-profile/0.1"


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def statement_hash(statement: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical(statement)).hexdigest()


def pareto(points) -> list[list[int]]:
    pts = sorted({(int(c), int(d)) for c, d in points})
    return [list(p) for p in pts if not any(q != p and q[0] <= p[0] and q[1] <= p[1] for q in pts)]


def classify(points) -> str | None:
    """§5.7's class of a profile (None when empty): immediate if (0, 0) is a point; cost-bearing if every point is
    (c, 0) with c > 0; delay if every point is (0, d) with d > 0; mixed otherwise."""
    pts = pareto(points)
    if not pts:
        return None
    if [0, 0] in pts:
        return "immediate"
    if all(c > 0 and d == 0 for c, d in pts):
        return "cost-bearing"
    if all(c == 0 and d > 0 for c, d in pts):
        return "delay"
    return "mixed"


def point_id(ob: str, c: int, d: int) -> str:
    return f"L_dp_{ob}_point_{c}_{d}"


def document(ob, side: dict, facts_sha256: str, eng: dict, bounds: dict, deadlines_pairs: list) -> dict:
    """The profile document of one obligation from the engine's answer."""
    outcomes = sorted({(c, d): (c, d, tr) for c, d, tr in eng["outcomes"]}.values(), key=lambda x: (x[0], x[1]))
    front = pareto([(c, d) for c, d, _ in outcomes])
    first = {(c, d): tr for c, d, tr in outcomes}
    frontier = [{"cost": c, "delay": d, "strategy": first[(c, d)]} for c, d in front]
    dominated = []
    for c, d, tr in outcomes:
        if [c, d] in front:
            continue
        by = next(p for p in front if p[0] <= c and p[1] <= d)
        dominated.append({"cost": c, "delay": d, "strategy": tr, "by": by})
    pers = sorted({(c, d): (c, d, tr) for c, d, tr in eng["persistent"]}.values(), key=lambda x: (x[0], x[1]))
    pfront = pareto([(c, d) for c, d, _ in pers])
    pfirst = {(c, d): tr for c, d, tr in pers}
    points, tables = [], {}
    for c, d in front:
        g = eng["points"][f"{c}_{d}"]
        p = {"cost": c, "delay": d, "plan": g["plan"], "alphabet": g["ax"], "robust": bool(g["robust"])}
        if g["robust"] and g.get("policy_ix") is not None:
            p["policy"] = g["policy_ix"]
            tables[f"{c}_{d}"] = g["rows"]
        elif g["robust"]:
            p["why"] = g.get("why")
        else:
            p["adversary"] = g.get("adversary")
        points.append(p)
    return {
        "profile_version": PROFILE_VERSION, "milestone": side["milestone"], "obligation": ob.id,
        "facts": ob.facts, "facts_sha256": facts_sha256,
        "obligation_spec": {"target": ob.target, "agent": ob.agent, "class": ob.cls, "principal": ob.principal,
                            "x_actions": ob.x_actions, "prefix": ob.prefix,
                            "guard": {"reason": ob.reason, "src": ob.src}},
        "bounds": bounds,
        "outcomes": [[c, d] for c, d, _ in outcomes],
        "frontier": frontier, "dominated": dominated, "class": classify(front),
        "persistent": {"frontier": [{"cost": c, "delay": d, "strategy": pfirst[(c, d)]} for c, d in pfront],
                       "class": classify(pfront)},
        "schedule": {"H": ob.H, "principals": ob.schedule_principals, "alphabet": eng["ae"]},
        "points": points, "tables": tables,
        "robust_frontier": [{"cost": c, "delay": d, "policy": pol} for c, d, pol in eng.get("robust_frontier", [])],
        "dominance": {"alphabet": eng["ax"], "gaps": eng["gaps"], "moves": bounds["dominance_moves"]},
        "abstraction": {"deadlines": eng["deadlines"], "horizon_s": bounds["horizon"], "pairs": deadlines_pairs,
                        "moves": eng["abs_moves"]},
    }


def laws(doc: dict) -> list[dict]:
    """The law files of one profile document (without facts_sha256 bookkeeping beyond the document's)."""
    ob = doc["obligation"]
    spec = doc["obligation_spec"]
    base = {"obligation": ob, "target": spec["target"], "agent": spec["agent"], "class": spec["class"],
            "guard": spec["guard"], "prefix": spec["prefix"]}
    common = {"milestone": doc["milestone"], "rule": "DISCH", "ir_version": LAW_IR, "facts": doc["facts"],
              "facts_sha256": doc["facts_sha256"]}
    out = []
    for p in doc["points"]:
        st = {**base, "form": "profile_point", "cost": p["cost"], "delay": p["delay"], "H": doc["schedule"]["H"],
              "principals": doc["schedule"]["principals"], "schedule_alphabet": doc["schedule"]["alphabet"],
              "moves": doc["bounds"]["moves"], "game_alphabet": p["alphabet"],
              "claim": "there is a priority list over game_alphabet such that, for every schedule of at most H events "
                       "over schedule_alphabet (each before one of the turns 0 .. moves - 1, in turn order), the greedy "
                       "play from s* (at each turn the first listed move within (cost, delay) that succeeds) reaches "
                       "a successful target move within cost and delay"}
        out.append({"law_id": point_id(ob, p["cost"], p["delay"]), "subform": "profile_point", **common, "statement": st})
    d = doc["dominance"]
    out.append({"law_id": f"L_dp_{ob}_dominance", "subform": "profile_dominance", **common,
                "statement": {**base, "form": "profile_dominance", "alphabet": d["alphabet"], "moves": d["moves"],
                              "gaps": d["gaps"],
                              "claim": "every sequence of at most moves moves over alphabet from s*, each succeeding, "
                                       "whose last move is a successful target move, has cost >= gc or delay >= gd "
                                       "for every gap [gc, gd]"}})
    for f in doc["persistent"]["frontier"]:
        out.append({"law_id": f"L_dp_{ob}_persistent_{f['cost']}_{f['delay']}", "subform": "profile_persistent",
                    **common, "statement": {**base, "form": "profile_persistent", "cost": f["cost"],
                                            "delay": f["delay"],
                                            "claim": "there is a sequence of moves from s*, each succeeding, whose last "
                                                     "move is the target, within cost and delay, after which kappa (the "
                                                     "guard's left side) is false"}})
    a = doc["abstraction"]
    out.append({"law_id": f"L_dp_{ob}_abstraction", "subform": "profile_abstraction", **common,
                "statement": {**base, "form": "profile_abstraction", "horizon_s": a["horizon_s"],
                              "deadlines": a["deadlines"], "pairs": a["pairs"], "moves": a["moves"],
                              "claim": "for every [dt, rep] in pairs and every move of moves, the move's outcome (0, or "
                                       "its revert reason) after a wait of dt from s* equals its outcome after a wait "
                                       "of rep"}})
    return out
