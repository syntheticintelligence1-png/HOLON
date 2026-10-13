"""A planted defective model for the toy Ledger (tests_m2/test_i20_refine_unit.py): the extracted model's own step
(holon.extracted_eval.step on holon.machine.load_extracted, the one evaluator) with three defects planted on top, each
of which must surface as a disagreement on its own observable:
  status   a deposit the model would revert with Error("fee") is answered ok (the fee guard skipped);
  storage  a successful deposit writes count + 1 more than the model computes;
  events   a successful deposit emits its amount off by one.
"""
from __future__ import annotations

from holon import extracted_eval as X
from holon.machine import load_extracted  # noqa: F401  (holon.replay_fragments.load_evaluator loads the model with it)

COUNT_SLOT = "0x%064x" % 2


def _err(reason: str) -> str:
    b = reason.encode()
    return ("0x08c379a0" + (32).to_bytes(32, "big").hex() + len(b).to_bytes(32, "big").hex()
            + (b + bytes((-len(b)) % 32)).hex())


def step_buggy(model, state, action, args, env):
    r = X.step(model, state, action, args, env)
    if action != "deposit":
        return r
    if r["status"] == "revert" and r["revert"] == _err("fee"):
        return {"status": "ok", "revert": None, "writes": {}, "events": [], "guard": None}
    if r["status"] == "ok":
        w = dict(r["writes"])
        if COUNT_SLOT in w:
            w[COUNT_SLOT] = "0x%064x" % (int(w[COUNT_SLOT], 16) + 1)
        evs = [dict(e, data="0x%064x" % (int(e["data"], 16) + 1)) for e in r["events"]]
        return dict(r, writes=w, events=evs)
    return r
