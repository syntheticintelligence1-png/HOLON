"""Rules C1, C5, C6 and M4: the deployment record, the comparison of every step with the linked machine, the per-step
evidence and the records.

`holon bundle refine` builds the harness project, runs the deployment, writes replay/<M>/bundle/deployment.json, runs
the corpus, and compares every call step with the linked machine (holon.bundle.machine) from the real pre-state: status,
revert key on two reverts, return data on two oks, every member's storage at every slot a write of the step touches on
either side, the members' logs, the members' balances, the outgoing calls and the frames. Environment steps (wait and
reinitialisation rows) are run and tracked, not compared. The member models' refinement (M4) runs each head member's
top-level steps on its model (holon.bundle.model). It is the one command that runs forge; --check re-runs everything and
compares the outputs.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from . import Ctx, render, write_or_check

STEPS_VERSION = "holon-bundle-steps/0.1"
REFINEMENT_VERSION = "holon-bundle-refinement/0.1"
DEPLOYMENT_VERSION = "holon-bundle-deployment/0.1"
ZVH = 0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014


# ------------------------------------------------------------------------------------------------------ deployment
def apply_writes(state: dict, writes: list, names: list) -> None:
    for mi, slot, val, reverted in writes:
        if not reverted:
            state[names[mi]][slot] = val


def deployment_record(ctx: Ctx, proj: Path, dep) -> dict:
    from ..replay_fragments import artifact, immutables_of
    names = [m["name"] for m in ctx.members()]
    st = {n: {} for n in names}
    apply_writes(st, dep.deploy.writes, names)
    out = {}
    for i, m in enumerate(ctx.members()):
        addr, impl = dep.members[i]
        art = artifact(proj, m["source"], m["contract"])
        code = bytes.fromhex(dep.runtime[i][2:])
        imm = {k: "0x" + code[s:s + n].hex() for k, (s, n) in immutables_of(proj, art).items()}
        out[m["name"]] = {"address": addr, "implementation": None if int(impl, 16) == 0 else impl,
                          "immutables": imm, "balance": dep.deploy.balances.get(i, 0),
                          "storage": {"0x%064x" % k: "0x%064x" % v for k, v in sorted(st[m["name"]].items()) if v}}
    return {"deployment_version": DEPLOYMENT_VERSION, "sidecar": ctx.ref(ctx.side_rel), "members": out,
            "named": dict(sorted(dep.named.items())), "code": dict(sorted(dep.code.items()))}


# ------------------------------------------------------------------------------------------------------ comparison
def _caller_name(addr: str, by_addr: dict, actors: dict) -> str:
    if addr in by_addr:
        return by_addr[addr]
    return actors.get(addr, addr)


def blobs_of(row: list) -> list:
    """The blob hashes the harness sets for a commit row (I20's encoding: s[8] blobs, s[9] and s[10])."""
    if not row or row[0] not in (1, 2, 3):
        return []
    enc = [0 if v == 0 else ZVH if v == 1 else (1 << 248) | v for v in (row[9], row[10])]
    return enc[:row[8]]


def compare(real: dict, mach: dict) -> list:
    """The observables in which the machine's result differs from the real one."""
    from ..replay_fragments import revert_key
    if mach["status"] == "unsupported":
        return ["unsupported"]
    if mach["status"] != real["status"]:
        return ["status"]
    diff = []
    if real["status"] == "revert":
        if revert_key(real["revert"]) != revert_key(mach["revert"]):
            diff.append("revert")
    else:
        if real["return"] != mach["return"]:
            diff.append("return")
        for n in real["post"]:
            slots = set(real["touched"][n]) | {k for k, v in mach["storage"][n].items() if real["pre"][n].get(k, 0) != v}
            if any(real["post"][n].get(k, 0) != mach["storage"][n].get(k, 0) for k in slots):
                diff.append("storage")
                break
        if real["logs"] != mach["logs"]:
            diff.append("events")
        if real["balances"] != mach["balances"]:
            diff.append("balances")
        if real["outgoing"] != [list(o) for o in mach["outgoing"]]:
            diff.append("outgoing")
    if real["frames"] != mach["frames"]:
        diff.append("frames")
    return diff


def real_frames(rec, names: list, by_addr: dict, actors: dict) -> list:
    out = []
    for parent, caller, mi, sel, value, reverted in rec.frames:
        ok = not reverted and (parent < 0 or out[parent][5])
        out.append([parent, _caller_name(caller, by_addr, actors), names[mi], sel, value, ok])
    return out


def disagreement_id(trace: str, k: int, data: str) -> str:
    return "D" + hashlib.sha256(f"{trace}#{k}#{data}".encode()).hexdigest()[:12]


def run(ctx: Ctx, jobs: int, log=print) -> dict:
    """{relative path: bytes} of every file refine writes."""
    from . import harness as H
    from .machine import Bundle
    from ..mreplay import encode_step
    corpus = ctx.load(ctx.out("corpus"))
    tc = H.toolchain(ctx)
    files = {}
    with tempfile.TemporaryDirectory(prefix="holon-bundle-refine-") as td:
        proj = H.project(ctx, Path(td), tc)
        dep = H.deployment(proj, tc, ctx, log)
        drec = deployment_record(ctx, proj, dep)
        files[ctx.out("deployment")] = render(drec)
        trs = H.run_corpus(proj, tc, ctx, corpus, dep, jobs or 4, log)
    names = [m["name"] for m in ctx.members()]
    by_addr = {drec["members"][n]["address"]: n for n in names}
    actors = {}
    for k, v in ctx.side["deployment"]["actors"].items():
        actors[(dep.named["harness"] if v == "harness" else v).lower()] = f"@{k}"
    machine = Bundle(ctx, drec)
    m4 = MemberModels(ctx, drec, machine, log)
    facts = ctx.load(ctx.side["corpus"]["m1"]["facts"])
    steps, dis = [], []
    compared = unsupported = 0
    for tr, rec in zip(corpus["traces"], trs):
        st = {n: {} for n in names}
        apply_writes(st, rec.deploy.writes, names)
        for k, (step, r) in enumerate(zip(tr["steps"], rec.steps)):
            pre = {n: dict(st[n]) for n in names}
            for acct, slot, word in r.pokes:          # C4: a relay step's poke precedes its call
                pre[by_addr[acct]][slot] = word
            frames = real_frames(r, names, by_addr, actors)
            item = {"trace": tr["id"], "step": k, "compared": r.kind == "call", "frames": frames,
                    "status": ("ok" if r.ok else "revert") if r.kind == "call" else None, "agree": True,
                    "unsupported": None}
            post = {n: dict(pre[n]) for n in names}
            apply_writes(post, r.writes, names)
            if r.kind == "call":
                compared += 1
                r.blobs = blobs_of(encode_step(step["row"], facts)) if "row" in step else []
                touched = {n: sorted({w[1] for w in r.writes if names[w[0]] == n and not w[3]}) for n in names}
                real = {"status": "ok" if r.ok else "revert", "revert": None if r.ok else r.ret,
                        "return": r.ret if r.ok else None, "pre": pre, "post": post, "touched": touched,
                        "logs": [(names[mi], t, d) for mi, t, d in r.logs] if r.ok else [],
                        "balances": {names[i]: b for i, b in sorted(r.balances.items())},
                        "outgoing": [[names[o[0]], o[1], o[2], o[3]] for o in r.outgoing if not o[4]],
                        "frames": frames}
                mach = machine.run(pre, dict(r.before), r)
                if mach["status"] == "unsupported":
                    unsupported += 1
                    item["unsupported"] = mach["reason"]
                else:
                    mach["frames"] = [[p, _caller_name(c, by_addr, actors), m, s, v, ok]
                                      for p, c, m, s, v, ok in mach["frames"]]
                    mach["logs"] = [(m, t, d) for m, t, d in mach["logs"]]
                m4.compare(tr["id"], k, r, real, frames, machine)
                diff = compare(real, mach)
                if diff:
                    item["agree"] = False
                    dis.append({"id": disagreement_id(tr["id"], k, r.data), "class": "unexplained", "links": [],
                                "trace": tr["id"], "step": k, "observables": diff,
                                "member": frames[0][2] if frames else None,
                                "reason": mach.get("reason")})
            steps.append(item)
            st = post
        log(f"{tr['id']}: done") if tr["id"].endswith("0") else None
    files[ctx.out("steps")] = render({"steps_version": STEPS_VERSION, "corpus": ctx.ref(ctx.out("corpus")),
                                      "steps": steps})
    rc = recount(ctx, steps)
    srcs = corpus["sources"]
    files[ctx.out("refinement")] = render({
        "refinement_version": REFINEMENT_VERSION,
        "corpus": dict(ctx.ref(ctx.out("corpus")), sources=srcs), "traces": rc["traces"], "steps": rc["steps"],
        "observables": ctx.side["observables"],
        "disagreements": [{"id": d["id"], "class": d["class"], "links": d["links"]} for d in dis],
        "unexplained": sum(1 for d in dis if d["class"] == "unexplained"), "unsupported": unsupported,
        "frames_ok": rc["frames_ok"], "links_ok": rc["links_ok"], "by_member_action": rc["by_member_action"],
        "toolchain": {"forge_sha256": tc["forge_sha256"], "solc_sha256": tc["solc_sha256"],
                      "sol_deps_sha256": tc["sol_deps_sha256"]}})
    files[ctx.out("disagreements")] = render({"disagreements": dis})
    files[ctx.out("refinement_models")] = render(m4.record())
    m4.close()
    log(f"{compared} compared steps, {len(dis)} disagreements, {unsupported} unsupported")
    return files


# ------------------------------------------------------------------------------------------------------ M4
class MemberModels:
    """Rule M4: every top-level step on a head member, run on the member's model (holon.sorts.evaluate3), from the
    member's real pre-state, with the answers its own call terms received (the linked machine's answers, which agreed
    with the harness on the step) and the step's environment; status, revert key, return data, the member's storage
    at every slot a write touches on either side, and its logs are compared."""

    def __init__(self, ctx: Ctx, drec: dict, machine, log=print):
        from . import model as MD
        from . import members as M
        from ..sorts.evaluate3 import Evaluator
        self.ctx, self.machine = ctx, machine
        self.td = tempfile.TemporaryDirectory(prefix="holon-bundle-m4-")
        self.ev, self.debt, self.rec = {}, {}, {}
        for m in MD.head_members(ctx):
            n = m["name"]
            init = {"binding": ctx.out("deployment"), "storage": drec["members"][n]["storage"]}
            text, debt = MD.compile_member(ctx, n, init)
            self.debt[n] = {a for a, _e in debt}
            self.rec[n] = {"model": f"{ctx.out('models')}/{n}.bend", "steps": 0, "disagreements": [],
                           "unexplained": 0, "unsupported": 0,
                           "model_sha256": hashlib.sha256((text or "").encode("utf-8")).hexdigest()}
            if text is None:
                continue
            p = Path(self.td.name) / f"{n}.bend"
            p.write_text(text, encoding="utf-8")
            self.ev[n] = Evaluator.build(p, M.model(ctx, n))
            log(f"M4: {n}'s model built ({len(self.debt[n])} actions in debt)")

    def compare(self, trace: str, k: int, r, real: dict, frames: list, machine) -> None:
        from ..replay_fragments import revert_key
        if not frames or frames[0][2] not in self.rec:
            return
        n = frames[0][2]
        rec = self.rec[n]
        rec["steps"] += 1
        model = machine.models[n]
        action = machine.by_sel[n].get(frames[0][3]) if frames[0][3] != "0x" else (
            "receive" if "receive" in model.actions else None)
        diff, reason = [], None
        if action is None:
            reason = "no action at the step's selector"
        elif action in self.debt[n] or n not in self.ev:
            reason = f"model debt: {action}"
        else:
            data = bytes.fromhex(r.data[2:])
            try:
                args = machine.decode(model, action, data)
            except Exception as e:  # noqa: BLE001
                args, reason = None, f"calldata: {e}"
            if args is not None:
                env = machine.env(n, r.caller, r.value, data, 0, [n])
                env.pop("call_hook", None)
                env.pop("return_data", None)
                env["calls"] = machine.answers.get(0, [])
                pre = {"0x%064x" % s: "0x%064x" % v for s, v in real["pre"][n].items()}
                try:
                    out = self.ev[n].step(pre, action, args, env)
                except Exception as e:  # noqa: BLE001
                    out = {"status": "unsupported", "reason": f"{type(e).__name__}: {e}"[:300]}
                if out["status"] == "unsupported":
                    reason = out.get("reason") or "unsupported"
                elif out["status"] != real["status"]:
                    diff.append("status")
                elif out["status"] == "revert":
                    if revert_key(out["revert"]) != revert_key(real["revert"]):
                        diff.append("revert")
                else:
                    slots = set(real["touched"][n]) | {int(x, 16) for x in out["writes"]}
                    post = dict(real["pre"][n])
                    post.update({int(a, 16): int(b, 16) for a, b in out["writes"].items()})
                    if any(post.get(s, 0) != real["post"][n].get(s, 0) for s in slots):
                        diff.append("storage")
                    mine = [(t, d) for m_, t, d in real["logs"] if m_ == n]
                    if mine != [([x.lower() for x in e["topics"]], e["data"].lower()) for e in out["events"]]:
                        diff.append("events")
                    outs = ((model.info.get("functions") or {}).get(model.actions[action].get("selector") or action)
                            or {}).get("outputs")
                    if outs and not diff:
                        reason = "the model gives no return data (holon.sorts.model3 has no return value)"
        if reason is not None:
            rec["unsupported"] += 1
            diff = ["unsupported"]
        if diff:
            rec["disagreements"].append({"id": disagreement_id(trace, k, r.data), "class": "unexplained", "links": [],
                                         "action": action, "observables": diff, "reason": reason})
            rec["unexplained"] += 1

    def record(self) -> dict:
        return {"refinement_models_version": "holon-bundle-refinement-models/0.1",
                "corpus": self.ctx.ref(self.ctx.out("corpus")),
                "observables": ["status", "revert", "return", "storage", "events"],
                "members": {n: dict(v, disagreements=[{k: d[k] for k in ("id", "class", "links")}
                                                      for d in v["disagreements"]])
                            for n, v in sorted(self.rec.items())},
                "details": {n: v["disagreements"] for n, v in sorted(self.rec.items())}}

    def close(self) -> None:
        for e in self.ev.values():
            e.close()
        self.td.cleanup()


# ------------------------------------------------------------------------------------------------------ C6 recount
def recount(ctx: Ctx, steps: list) -> dict:
    from .corpus import abis
    table = abis(ctx)
    names = {}
    for m in ctx.members():
        doc = ctx.load(ctx.document_rel(m))
        names[m["name"]] = {(a.get("selector") or "0x"): a["name"] for a in doc["actions"]}
    decl = ctx.load(ctx.out("declaration"))
    want = {}
    for r in decl["links"]:
        member, action, _src, _fn, callee, kind, target = r
        if kind == "receive":
            sel = "0x"
        elif kind == "getter":
            sel = next(k for k, e in table[callee].items() if k.startswith("0x") and e.get("name") == target)
        else:
            sel = next(k for k, v in names[callee].items() if v == target)
        want[(member, action, callee, sel)] = r
    frames_ok, bma, lk = {}, {}, {}
    traces = set()
    compared = 0
    for st in steps:
        traces.add(st["trace"])
        fr = st["frames"]
        for parent, _c, callee, sel, _v, ok in fr:
            act = names.get(callee, {}).get(sel)
            if ok and act is not None:
                frames_ok.setdefault(callee, {}).setdefault(act, 0)
                frames_ok[callee][act] += 1
            if ok and parent >= 0:
                p = fr[parent]
                key = (p[2], names.get(p[2], {}).get(p[3]), callee, sel)
                if key in want:
                    lk[key] = lk.get(key, 0) + 1
        if st["compared"]:
            compared += 1
            top = [f for f in fr if f[0] < 0]
            if top:
                act = names.get(top[0][2], {}).get(top[0][3])
                if act is not None:
                    e = bma.setdefault(top[0][2], {}).setdefault(act, {"ok": 0, "revert": 0})
                    e["ok" if st["status"] == "ok" else "revert"] += 1
    return {"traces": len(traces), "steps": compared,
            "frames_ok": {m: dict(sorted(v.items())) for m, v in sorted(frames_ok.items())},
            "by_member_action": {m: dict(sorted(v.items())) for m, v in sorted(bma.items())},
            "links_ok": sorted([*r[:4], lk.get(k, 0)] for k, r in want.items())}


def main(ctx: Ctx, check: bool, log, jobs: int = 0) -> int:
    files = run(ctx, jobs, log)
    return write_or_check(ctx, files, check, log=log)
