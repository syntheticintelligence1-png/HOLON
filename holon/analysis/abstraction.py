"""The finite abstraction of a discharge-profile obligation (whitepaper Prop 6.21, §10.7 step 1; BUILD_PLAN I32).

Prop 6.21 computes DP_X exactly on a finite abstraction. The abstraction here is made of:

- the obligation: a target action, its guard conjunct kappa => rho (a facts guard `!kappa || rho` with a reason),
  the agent who plays for the class X, and the representative state s* (a prefix from the initial state);
- X's actions: those labelled with X's own principal, and the permissionless ones (Machine.permissionless: an M0 or
  M1 label starting with "anyone" or "environment"; an M2+ machine's permission classes);
- the move alphabets, read from the target's search hints by holon/js/profile.mjs: X's moves (hints whose action X
  may call, with who set to the agent, and the hinted waits), the E-alphabet (the hints' moves for the schedule's
  principals at every state at most H E-moves reach), the dominance alphabet (the hints' X-moves at every state at
  most K - 1 X-moves reach) and each point's game alphabet (the hints' X-moves at every decision state its bounded
  game reaches);
- the time abstraction: a strategy waits only to the hints' deadlines at s*. pairs() lists, for every wait of dt
  seconds up to the horizon, its representative, the greatest deadline <= dt (0: no wait); the abstraction law
  says every alphabet move's outcome after dt is its outcome after the representative, so a wait elsewhere never
  reaches an outcome sooner.

Exactness of a profile is relative to this abstraction and to H; the records say so (EXACT).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..gen.machine import Machine

EXACT = ("exact relative to the abstraction: the hints' move alphabets (X's, the schedule's E-closure, the dominance "
         "closure and each point's game alphabet), the time abstraction at s* (waits to the hinted deadlines), at "
         "most K strategy moves and at most H schedule events")


@dataclass(frozen=True)
class Obligation:
    id: str
    facts: str
    target: str
    reason: int
    src: str
    cls: str
    principal: str
    agent: int
    prefix: list
    x_actions: list
    schedule_principals: list
    H: int


def x_actions(machine: Machine, principal: str) -> list[str]:
    """The actions X may call, in facts order: its own principal's, then none twice, the permissionless ones."""
    free = set(machine.permissionless())
    return [a["name"] for a in machine.actions
            if a["name"] != "wait" and (a.get("principal") == principal or a["name"] in free)]


def obligation(side: dict, machine: Machine, i: int = 0) -> Obligation:
    ob = side["obligations"][i]
    return Obligation(id=ob["id"], facts=side["facts"], target=ob["target"], reason=int(ob["guard"]["reason"]),
                      src=ob["guard"]["src"], cls=ob["class"]["name"], principal=ob["class"]["principal"],
                      agent=int(ob["agent"]), prefix=ob["prefix"], x_actions=x_actions(machine, ob["class"]["principal"]),
                      schedule_principals=list(side["schedule"]["principals"]), H=int(side["schedule"]["H"]))


def pairs(deadlines: list[int], horizon: int) -> list[list[int]]:
    """[dt, representative] for dt = 0 .. horizon: the representative is the greatest deadline <= dt (0 if none)."""
    ds = sorted(set(int(d) for d in deadlines))
    return [[dt, max([0] + [d for d in ds if d <= dt])] for dt in range(int(horizon) + 1)]


def engine_request(ob: Obligation, module: Path, hints: Path, facts: dict, bounds: dict,
                   kappa: dict | None) -> dict:
    """The request holon/js/profile.mjs answers for the obligation."""
    req = {"module": str(module), "hints": str(hints), "facts": facts, "task": "analyze",
           "obligation": {"target": ob.target, "agent": ob.agent, "x_actions": ob.x_actions, "prefix": ob.prefix},
           "schedule": {"H": ob.H, "principals": ob.schedule_principals}, "bounds": bounds}
    if kappa:
        req["kappa"] = kappa
    return req
