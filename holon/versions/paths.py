"""The sidecar's traces over the versioned machine: the upgrade path (rule V7) and the reinitializer arguments (the
sidecar's upgrade_path.arguments, reverting_last_edge and inflight_arguments).

An argument is {"word": hex}, {"deployment_call": i, "argument": j} (the j-th ABI word of the deployment record's
call i) or {"storage": family} (the family's value in the state the step runs at, read at its slot in the layout of the
state's version: I63's history). A reinitializer's calldata is its selector and its arguments' words (static
parameters only).
"""
from __future__ import annotations

from . import PLACEHOLDER, Refused
from .machine import Machine, cd_bytes, num, storage_of


def deployment_word(m: Machine, i: int, j: int) -> int:
    calls = m.dep.get("calls") or []
    if i >= len(calls):
        raise Refused(f"the deployment record has no call {i}")
    b = cd_bytes(calls[i]["data"])[4:]
    if 32 * (j + 1) > len(b):
        raise Refused(f"the deployment record's call {i} has no argument word {j}")
    return int.from_bytes(b[32 * j:32 * (j + 1)], "big")


def family_value(m: Machine, state: dict, family: str) -> int:
    lay = [e for e in m.ctx.version(state["version"])["layout"] if e["label"] == family]
    if len(lay) != 1:
        raise Refused(f"the layout of {state['version']} has {len(lay)} entries named {family}")
    e = lay[0]
    w = storage_of(state["sl"]).get(e["slot"], 0)
    return (w >> (8 * e["offset"])) & ((1 << (8 * e["bytes"])) - 1) if e["bytes"] < 32 else w


def arg_value(m: Machine, spec: dict, state: dict | None) -> int:
    if "word" in spec:
        return num(spec["word"])
    if "deployment_call" in spec:
        return deployment_word(m, int(spec["deployment_call"]), int(spec["argument"]))
    if "storage" in spec:
        if state is None:
            raise Refused("a storage argument needs the state the step runs at")
        return family_value(m, state, spec["storage"])
    raise Refused(f"an argument {spec} of no known form")


def reinit_calldata(m: Machine, vid: str, name: str, specs: list, state: dict | None) -> str:
    fn = m.function(vid, name)
    if fn is None:
        raise Refused(f"{vid} has no compiled reinitializer {name}")
    from ..evm_abi import is_dynamic
    if len(fn["inputs"]) != len(specs) or any(is_dynamic(p) for p in fn["inputs"]):
        raise Refused(f"{vid} {name}: the sidecar gives {len(specs)} words for {len(fn['inputs'])} static parameters")
    words = b"".join((arg_value(m, s, state) % (1 << 256)).to_bytes(32, "big") for s in specs)
    return fn["selector"] + words.hex()


def migration(m: Machine, a: str, b: str, args: dict, state: dict | None) -> dict:
    """The admin's migration along a -> b: upgradeToAndCall with the reinitializer the edge introduces called with
    `args` (the sidecar's arguments by reinitializer name), else upgradeTo."""
    e = m.edges[(a, b)]
    intro = [r["name"] for r in e["introduced"] if r["name"] in args]
    if not intro:
        return m.migrate_step(a, b, None)
    r = intro[0]
    return m.migrate_step(a, b, r, reinit_calldata(m, b, r, args[r], state))


def upgrade_path(m: Machine) -> list:
    """V7: the sidecar's upgrade path as a trace, each step's "ok" the model's."""
    up = m.ctx.side["upgrade_path"]
    calls = m.dep.get("calls") or []
    v0 = m.path[0]
    trace = []
    state = m.initial()

    def push(st: dict) -> None:
        nonlocal state
        o = m.step(state, st)
        trace.append(dict(st, ok=o["status"] == "ok"))
        state = o["state"]

    def call(i: int) -> dict:
        c = calls[i]
        name = action_of(m, v0, c["data"])
        return m.call_step(v0, name, num(c["caller"]), c["data"])

    push(m.migrate_step(PLACEHOLDER, v0, None))
    for i in up["first_calls"]:
        push(call(i))
    for i in up["reverting_calls"]:
        push(call(i))
    pairs = list(zip(m.path, m.path[1:]))
    for a, b in pairs[:-1]:
        push(migration(m, a, b, up["arguments"], state))
    if pairs:
        a, b = pairs[-1]
        push(migration(m, a, b, up["reverting_last_edge"], state))
        push(migration(m, a, b, up["arguments"], state))
    return trace


def action_of(m: Machine, vid: str, cd: str) -> str:
    sel = cd[2:10] if cd.startswith("0x") else cd[:8]
    for name in m.actions(vid):
        fn = m.function(vid, name)
        if fn and fn["selector"] and fn["selector"].removeprefix("0x") == sel:
            return name
    raise Refused(f"{vid} has no compiled action of selector 0x{sel}")
