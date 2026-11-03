"""Rule D4 (I94; I70's RP1-RP2): every witness of the search replayed on the real code through the cutover harness.

`holon cutover replay` runs, from a fresh cutover deployment, the corpus traces the I94 sidecar's replay names (left:
the commit at the edge's old version, the migration, the challenge at the new version, the proof window, the op by the
new registry's principal, the claim; right: the same without the migration, at the old version), each step compared
with the linked machine (holon.cutover.machine) by I69's comparison, as `holon cutover refine` compares the corpus.
The observed reward of a run is the challenger's batchChallengeReward after the op, read from the real code's storage
(the versioned member's mapping family the site pair credits, at the challenger's address), less the deposit the
challenge step sent. A run passes when every step agrees and its observed reward equals the witness's answer of its
side (results/<M>/cutover/search.json). Runs are named <law id>:left and <law id>:right for each law the search
refutes. Nothing here names a target: traces, roles, families and members come from the sidecars and documents.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import Ctx, Refused, render

REPLAY_VERSION = "holon-cutover-replay/0.1"


def build(ctx: Ctx, log=print) -> dict:
    from ..bundle.harness import toolchain
    from ..bundle.refine import apply_writes, compare, real_frames
    from ..keccak import keccak256
    from ..rules import slash as S
    from . import build as B, harness as H
    from .claims import family
    from .corpus import ROLES
    from .machine import Linked
    from .refine import Encoder, deployment_record
    from .s0 import sidecar
    side = sidecar(ctx)
    found = (ctx.load(side["outputs"]["search"]).get("found") or {})
    if not found:
        raise Refused("the search found no witness: nothing to replay")
    corpus = ctx.load(ctx.out("corpus"))
    want = {"left": side["replay"]["left"], "right": side["replay"]["right"]}
    traces = {t["id"]: t for t in corpus["traces"]}
    order = [m["name"] for m in ctx.bundle().members()] + [ctx.side["link"]["a"]["registry"]]
    tc = toolchain(ctx.bundle())
    bs = B.builds(ctx)
    codes = [bytes.fromhex(bs[k]["creation"]) for k in ("a", "b", "registry")]
    init = corpus["deployment"]["init"]
    with tempfile.TemporaryDirectory(prefix="holon-cutover-replay-") as td:
        proj = H.project(ctx, Path(td), tc)
        dtrs, rts = H.run(proj, tc, H.input_doc(codes, init, [], [[]]), "deploy", log)
        drec = deployment_record(ctx, proj, order, dtrs[0], rts, bs)
        enc = Encoder(order, drec["members"], drec["named"])
        ids = [want["left"], want["right"]]
        trs, _r = H.run(proj, tc, H.input_doc(codes, init, [], [[enc.step(s) for s in traces[i]["steps"]]
                                                                for i in ids]), "replay", log)
    by_addr = {drec["members"][n]["address"]: n for n in order}
    actors = {enc.addr[v]: k for k, v in ROLES.items()}
    _rel, _sha, vdoc, docs, _model = S.read_inputs(ctx.milestone, ctx.root)
    pair = S.pairs_of(vdoc, docs)[0]
    credit = pair["a"][0]["credits"][0]["family"]
    vname = next(m["name"] for m in ctx.bundle().members() if m.get("adopted"))
    challenger = int(enc.addr[ROLES["c"]], 16)
    results = {}
    for side_, tid, rec in zip(("left", "right"), ids, trs):
        machine = Linked(ctx, drec, order)
        machine.set_version(machine.a)
        st = {n: {} for n in order}
        apply_writes(st, rec.deploy.writes, order)
        agree, steps, deposit, reward = True, [], None, None
        for k, (step, r) in enumerate(zip(traces[tid]["steps"], rec.steps)):
            pre = {n: dict(st[n]) for n in order}
            post = {n: dict(pre[n]) for n in order}
            apply_writes(post, r.writes, order)
            row = {"index": k, "label": step["label"], "version": machine.version, "agree": True}
            if r.kind == "call":
                frames = real_frames(r, order, by_addr, actors)
                touched = {n: sorted({w[1] for w in r.writes if order[w[0]] == n and not w[3]}) for n in order}
                real = {"status": "ok" if r.ok else "revert", "revert": None if r.ok else r.ret,
                        "return": r.ret if r.ok else None, "pre": pre, "post": post, "touched": touched,
                        "logs": [(order[mi], tp, d) for mi, tp, d in r.logs] if r.ok else [],
                        "balances": {order[i]: v for i, v in sorted(r.balances.items())},
                        "outgoing": [[order[o[0]], o[1], o[2], o[3]] for o in r.outgoing if not o[4]],
                        "frames": frames}
                mach = machine.run(pre, dict(r.before), r)
                if mach["status"] != "unsupported":
                    mach["frames"] = [[p, by_addr.get(c, actors.get(c, c)), m_, s_, v, ok]
                                      for p, c, m_, s_, v, ok in mach["frames"]]
                diff = compare(real, mach) if mach["status"] != "unsupported" else ["unsupported"]
                row["agree"] = not diff
                agree = agree and not diff
                if frames and frames[0][2] == vname and frames[0][1] == "c" and int(frames[0][4]) > 0:
                    deposit = int(frames[0][4])
                if f".{pair['op']} " in step["label"] or step["label"].endswith(f".{pair['op']}"):
                    v = machine.version
                    f = family(docs[v], credit)
                    slot = int.from_bytes(keccak256(challenger.to_bytes(32, "big") + int(f["slot"]).to_bytes(32, "big")),
                                          "big")
                    reward = post[vname].get(slot, 0)
            steps.append(row)
            st = post
        results[side_] = {"trace": tid, "agree": agree, "steps": steps, "deposit": deposit,
                          "credited": reward}
    runs = []
    for rule, w in sorted(found.items()):
        lid = next(p for p in pair["laws"].values() if p.startswith(f"L_{rule.lower()}_"))
        for s_ in ("left", "right"):
            r = results[s_]
            obs = None if r["credited"] is None or r["deposit"] is None else r["credited"] - r["deposit"]
            runs.append({"id": f"{lid}:{s_}", "trace": r["trace"], "steps": len(r["steps"]), "agree": r["agree"],
                         "deposit": r["deposit"], "credited": r["credited"], "observed_reward": obs,
                         "model_reward": int(w[s_]["ret"]),
                         "passed": bool(r["agree"] and obs is not None and obs == int(w[s_]["ret"]))})
    log(f"{len(runs)} runs, {sum(1 for x in runs if x['passed'])} passed")
    return {side["outputs"]["replay"]: render({"replay_version": REPLAY_VERSION, "runs": runs,
                                               "traces": {k: v for k, v in results.items()}})}
