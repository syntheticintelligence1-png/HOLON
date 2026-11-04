"""Rule K1 (I94): the legacy registry's initial state, read from the real code's run in the cutover harness.

`holon cutover s0` runs a fresh cutover deployment and the corpus trace the I94 sidecar names (spec/<M>/lib/
slash_decide.json, registry_s0: trace, after_step) through the harness, and writes the registry's storage after that
step: the deployment's storage writes and the trace's writes up to and including the step, applied in order (the
harness's state-diff records of the real code), its non-zero slots. The record (outputs.registry_s0) names its source:
the trace and step, the harness's block number and timestamp at the step, the registry's address, the corpus roles'
addresses, and how it was read. Nothing here names a target: the registry, the trace and the roles come from the
sidecars and the corpus.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from . import Ctx, Refused, render, sha256_bytes

SIDECAR = "spec/{m}/lib/slash_decide.json"
S0_VERSION = "holon-cutover-registry-s0/0.1"


def sidecar(ctx: Ctx) -> dict:
    p = ctx.path(SIDECAR.format(m=ctx.milestone))
    if not p.is_file():
        raise Refused(f"{SIDECAR.format(m=ctx.milestone)} is missing")
    return json.loads(p.read_text(encoding="utf-8"))


def build(ctx: Ctx, log=print) -> dict:
    from ..bundle.harness import toolchain
    from ..bundle.refine import apply_writes
    from . import build as B, harness as H
    from .corpus import ROLES
    from .refine import Encoder, deployment_record
    side = sidecar(ctx)
    want = side["registry_s0"]
    corpus = ctx.load(ctx.out("corpus"))
    trace = next((t for t in corpus["traces"] if t["id"] == want["trace"]), None)
    if trace is None:
        raise Refused(f"the corpus has no trace {want['trace']}")
    k = int(want["after_step"])
    reg = ctx.side["link"]["a"]["registry"]
    order = [m["name"] for m in ctx.bundle().members()] + [reg]
    tc = toolchain(ctx.bundle())
    bs = B.builds(ctx)
    codes = [bytes.fromhex(bs[x]["creation"]) for x in ("a", "b", "registry")]
    init = corpus["deployment"]["init"]
    with tempfile.TemporaryDirectory(prefix="holon-cutover-s0-") as td:
        proj = H.project(ctx, Path(td), tc)
        dtrs, rts = H.run(proj, tc, H.input_doc(codes, init, [], [[]]), "deploy", log)
        drec = deployment_record(ctx, proj, order, dtrs[0], rts, bs)
        enc = Encoder(order, drec["members"], drec["named"])
        trs, _r = H.run(proj, tc, H.input_doc(codes, init, [], [[enc.step(s) for s in trace["steps"][:k + 1]]]),
                        "s0", log)
    rec = trs[0]
    st = {n: {} for n in order}
    apply_writes(st, rec.deploy.writes, order)
    for r in rec.steps[:k + 1]:
        if r.kind == "call" and not r.ok:
            raise Refused(f"{trace['id']} step {r} reverted on the real code")
        apply_writes(st, r.writes, order)
    last = rec.steps[k]
    dep_rel = ctx.out("deployment")
    if render(drec) != ctx.path(dep_rel).read_bytes():
        raise Refused(f"this run's deployment differs from {dep_rel}")
    stakers = {role: enc.addr[v] for role, v in sorted(ROLES.items())}
    log(f"{reg} after {trace['id']} step {k} ({trace['steps'][k]['label']}): "
        f"{len([v for v in st[reg].values() if v])} non-zero slots")
    return {side["outputs"]["registry_s0"]: render({
        "registry_s0_version": S0_VERSION, "member": reg, "address": drec["members"][reg]["address"],
        "trace": trace["id"], "step": k, "label": trace["steps"][k]["label"],
        "block_number": int(last.number), "timestamp": int(last.timestamp), "stakers": stakers,
        "deployment": {"path": dep_rel, "sha256": sha256_bytes(ctx.path(dep_rel).read_bytes())},
        "read": "the cutover harness (forge, the real code): a fresh deployment, then the trace's steps up to and "
                "including this one; the registry's storage is the deployment's storage writes and the steps' writes "
                "(the harness's state-diff records), applied in order; its non-zero slots",
        "storage": {"0x%064x" % s: "0x%064x" % v for s, v in sorted(st[reg].items()) if v}})}
