"""A hand-written stand-in for A's evaluator (holon.extracted_eval.step) on the planted toy Ledger only
(tests_m2/test_i20_refine_unit.py). It is a test fixture: it knows the toy's compiled layout and semantics by
construction, so that the harness, the state tracking and the comparison can be checked end to end without A's side.

step(model, state, action, args, env) follows the A/B interface (holon/replay_fragments.py docstring). Guard ids use
the spans of the toy's extracted document; the checked accumulator at src/Ledger.sol:51 is reported as reach 0 of
that span. step_buggy plants three defects: it skips the fee guard, it writes count + 2, and it emits the deposit
amount off by one; each must surface as a disagreement on its own observable. step_planned adds the implicit checks of
the planned sections (toy/planned_ledger.json: call value, ABI range) in front of step, with the reach ids
holon.fragments_doc gives them (a check without a span takes its action's span).
"""
from __future__ import annotations

from holon.keccak import keccak256

M64 = (1 << 64) - 1
M160 = (1 << 160) - 1
SRC = "src/Ledger.sol"


def _w(state: dict, slot: int) -> int:
    return int(state.get("0x%064x" % slot, "0x0"), 16)


def _err(reason: str) -> str:
    b = reason.encode()
    return ("0x08c379a0" + (32).to_bytes(32, "big").hex() + len(b).to_bytes(32, "big").hex()
            + (b + bytes((-len(b)) % 32)).hex())


def _panic(code: int) -> str:
    return "0x4e487b71" + code.to_bytes(32, "big").hex()


def _answer(env: dict, fn: str):
    for c in env.get("calls") or []:
        if c.get("fn") == fn:
            return c
    raise LookupError(f"no answer for {fn}")


def _topic(sig: str) -> str:
    return "0x" + keccak256(sig.encode()).hex()


def _entry_slot(i: int) -> int:
    return int.from_bytes(keccak256(i.to_bytes(32, "big") + (3).to_bytes(32, "big")), "big")


def _rev(action, guard_src, data, k=0):
    return {"status": "revert", "revert": data, "writes": {}, "events": [], "guard": f"{action}#{guard_src}#{k}"}


def step(model, state, action, args, env, buggy=False):
    caller = int(env["caller"], 16)
    s0 = _w(state, 0)
    owner, paused = s0 & M160, (s0 >> 160) & 0xFF
    if action == "deposit":
        if paused:
            return _rev(action, f"{SRC}:21", _err("paused"))
        ok = _answer(env, "IGate.allowed")
        if not (ok["ok"] and int(ok["ret"], 16)):
            return _rev(action, f"{SRC}:48", _err("not allowed"))
        amount = args["amount"]
        if amount == 0:
            return _rev(action, f"{SRC}:49", _err("zero"))
        if not buggy:
            fee = int(_answer(env, "IGate.fee")["ret"], 16)
            if env["msg.value"] < fee:
                return _rev(action, f"{SRC}:50", _err("fee"))
        s1 = _w(state, 1)
        total = (s1 >> 160) & M64
        if total + amount > M64:
            return _rev(action, f"{SRC}:51", _panic(0x11))
        count = _w(state, 2) + (2 if buggy else 1)
        writes = {"0x%064x" % 1: "0x%064x" % ((s1 & ~(M64 << 160)) | ((total + amount) << 160)),
                  "0x%064x" % 2: "0x%064x" % count,
                  "0x%064x" % _entry_slot(count): "0x%064x" % (amount | (caller << 64))}
        ev = {"topics": [_topic("Deposited(address,uint256,uint64)"), "0x%064x" % caller, "0x%064x" % count],
              "data": "0x%064x" % (amount + (1 if buggy else 0))}
        return {"status": "ok", "revert": None, "writes": writes, "events": [ev], "guard": None}
    if action == "withdraw":
        if paused:
            return _rev(action, f"{SRC}:21", _err("paused"))
        i = args["id"]
        e = _w(state, _entry_slot(i))
        if (e >> 64) & M160 != caller:
            sel = keccak256(b"NotYours(uint256)")[:4].hex()
            return _rev(action, f"{SRC}:59", "0x" + sel + i.to_bytes(32, "big").hex())
        s1 = _w(state, 1)
        total = (s1 >> 160) & M64
        amount = e & M64
        if amount > total:
            return _rev(action, f"{SRC}:60", _panic(0x11))
        writes = {"0x%064x" % 1: "0x%064x" % ((s1 & ~(M64 << 160)) | ((total - amount) << 160)),
                  "0x%064x" % _entry_slot(i): "0x%064x" % 0}
        return {"status": "ok", "revert": None, "writes": writes, "events": [], "guard": None}
    if action == "setPaused":
        if caller != owner:
            return _rev(action, f"{SRC}:16", _err("not owner"))
        on = 1 if args["on"] else 0
        writes = {"0x%064x" % 0: "0x%064x" % ((s0 & ~(0xFF << 160)) | (on << 160))}
        ev = {"topics": [_topic("Paused(bool)")], "data": "0x%064x" % on}
        return {"status": "ok", "revert": None, "writes": writes, "events": [ev], "guard": None}
    raise NotImplementedError(action)


def step_buggy(model, state, action, args, env):
    return step(model, state, action, args, env, buggy=True)


ACTION_SRC = {"withdraw": f"{SRC}:57-62", "setPaused": f"{SRC}:64-67"}


def step_planned(model, state, action, args, env):
    """step, with the implicit checks of the planned sections (toy/planned_ledger.json): the call value of the
    non-payable actions, then the ABI range of narrow parameters (both revert with empty data), then the body."""
    if action in ACTION_SRC and int(env.get("msg.value") or 0) != 0:
        return _rev(action, ACTION_SRC[action], "0x")
    if action == "deposit" and not 0 <= int(args["amount"]) < (1 << 64):
        return _rev(action, f"{SRC}:47", "0x")
    if action == "setPaused" and not isinstance(args["on"], bool) and args["on"] not in (0, 1):
        return _rev(action, f"{SRC}:64", "0x")
    return step(model, state, action, args, env)


def load_extracted(path):
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text())
