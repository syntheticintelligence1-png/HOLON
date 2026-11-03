"""Rule L4: the cutover corpus on the real code and on the linked versioned machine, step by step.

`holon cutover refine` builds the harness project, runs a deployment (replay/<M>/cutover/deployment.json), runs every
corpus trace from a fresh deployment, and compares every call step with the linked machine (holon.cutover.machine) from
the real pre-state, by I69's comparison (holon.bundle.refine.compare): status, revert key on two reverts, return data on
two oks, every member's storage at every slot a write of the step touches on either side, the members' logs, balances,
outgoing calls and frames. Environment steps (waits, rolls) are run and tracked, not compared. Per-step rows in
results/<M>/cutover/steps.json, totals in results/<M>/cutover/refinement.json (their recount is the instrument's).

Rule M2 (RegistryModel): every corpus step whose top frame is the legacy registry also runs on the registry's model3
model (holon.cutover.model, compiled to JavaScript: holon.sorts.evaluate3), from the registry's real pre-state with the
answers its own calls received (the linked machine's, which agreed with the harness on the step), as I69's M4 runs a
head member's steps: status, revert key, return data, the registry's storage at every slot either side writes, and its
logs. A step in an action of the model's debt counts as unsupported. A frame of the registry under another member's
call (the versioned member's calls at its sites) is counted, not compared: its calldata and answers are the linked machine's
inner frame's, which M4's comparison does not take. Results in outputs.model_refinement.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import Ctx, render

STEPS_VERSION = "holon-cutover-steps/0.1"
REFINEMENT_VERSION = "holon-cutover-refinement/0.1"
DEPLOYMENT_VERSION = "holon-cutover-deployment/0.1"


def _enc(values: list, types: list) -> bytes:
    from ..extracted_eval import abi_encode, parse_types
    return abi_encode(values, parse_types(",".join(types)))


class Encoder:
    """Corpus steps as harness steps: names resolved to the deployment's addresses."""

    def __init__(self, order: list, members: dict, named: dict):
        self.addr = {f"@{n}": members[n]["address"] for n in order}
        self.addr.update({f"@{k}": v for k, v in named.items()})
        for k in range(2, 10):
            self.addr[f"@w{k}"] = "0x%040x" % (0x1000 + k)

    def resolve(self, v):
        if isinstance(v, str) and v.startswith("@"):
            return self.addr[v]
        if isinstance(v, list):
            return [self.resolve(x) for x in v]
        if isinstance(v, dict) and "fn" in v:
            return self.calldata(v["fn"], v["args"])
        return v

    def calldata(self, fn: str, args: list) -> bytes:
        from ..extracted_eval import abi_encode, keccak, parse_types
        rest = fn.split("(", 1)[1][:-1]
        types = parse_types(rest) if rest else []
        vals = []
        for a, t in zip(args, rest.split(",") if rest else []):
            v = self.resolve(a)
            if t == "bytes" and isinstance(v, str):
                v = bytes.fromhex(v[2:])
            elif t == "bytes32" and isinstance(v, str):
                v = int(v, 16)
            vals.append(v)
        return keccak(fn.encode()).to_bytes(32, "big")[:4] + abi_encode(vals, types)

    def step(self, st: dict) -> bytes:
        if "row" in st:
            return _enc([1, _enc([st["row"]], ["uint256[]"])], ["uint8", "bytes"])
        c = st["call"]
        payload = _enc([self.resolve(c["caller"]), c["value"], 0, self.addr[f"@{c['to']}"],
                        self.calldata(c["fn"], c["args"])], ["address", "uint256", "uint256", "address", "bytes"])
        return _enc([2, payload], ["uint8", "bytes"])


def deployment_record(ctx: Ctx, proj: Path, order: list, tr, rts: dict, bs: dict) -> dict:
    from ..bundle.refine import apply_writes
    from ..replay_fragments import artifact, immutables_of
    from .build import edge
    from .corpus import versioned_member
    a, b = edge(ctx)
    vname = versioned_member(ctx)
    st = {n: {} for n in order}
    apply_writes(st, tr.deploy.writes, order)
    bctx = ctx.bundle()

    def words(code_hex: str, ranges: dict) -> dict:
        code = bytes.fromhex(code_hex[2:])
        return {k: "0x" + code[r[0][0]:r[0][0] + r[0][1]].hex() for k, r in sorted(ranges.items())}
    members = {}
    reg = ctx.side["link"]["a"]["registry"]
    for i, n in enumerate(order):
        addr, impl = tr.members[i]
        if n == vname:
            imm = words(rts["a"], bs["a"]["immutables"])
        elif n == reg:
            imm = words(rts["registry"], bs["registry"]["immutables"])
        else:
            m = bctx.member(n)
            art = artifact(proj, m["source"], m["contract"])
            code = bytes.fromhex(tr.runtime[i][2:])
            imm = {k: "0x" + code[s:s + ln].hex() for k, (s, ln) in sorted(immutables_of(proj, art).items())}
        members[n] = {"address": addr, "implementation": None if int(impl, 16) == 0 else impl, "immutables": imm,
                      "balance": tr.deploy.balances.get(i, 0),
                      "storage": {"0x%064x" % k: "0x%064x" % v for k, v in sorted(st[n].items()) if v}}
    versions = {a: {"implementation": tr.named[a.lower()], "immutables": words(rts["a"], bs["a"]["immutables"])},
                b: {"implementation": tr.named[b.lower()], "immutables": words(rts["b"], bs["b"]["immutables"])}}
    return {"deployment_version": DEPLOYMENT_VERSION, "sidecar": ctx.ref(ctx.side_rel), "order": order,
            "versioned_member": vname, "versions": versions, "members": members,
            "named": dict(sorted(tr.named.items())), "code": dict(sorted(tr.code.items()))}


def run(ctx: Ctx, log=print) -> dict:
    from ..bundle.harness import toolchain
    from ..bundle.refine import apply_writes, compare, real_frames
    from . import build as B, harness as H
    from .corpus import ROLES, versioned_member
    from .machine import Linked
    corpus = ctx.load(ctx.out("corpus"))
    order = [m["name"] for m in ctx.bundle().members()] + [ctx.side["link"]["a"]["registry"]]
    tc = toolchain(ctx.bundle())
    bs = B.builds(ctx)
    codes = [bytes.fromhex(bs[k]["creation"]) for k in ("a", "b", "registry")]
    init = corpus["deployment"]["init"]
    files = {}
    with tempfile.TemporaryDirectory(prefix="holon-cutover-refine-") as td:
        proj = H.project(ctx, Path(td), tc)
        dtrs, rts = H.run(proj, tc, H.input_doc(codes, init, [], [[]]), "deploy", log)
        drec = deployment_record(ctx, proj, order, dtrs[0], rts, bs)
        enc = Encoder(order, drec["members"], drec["named"])
        traces = [[enc.step(s) for s in t["steps"]] for t in corpus["traces"]]
        trs, _r = H.run(proj, tc, H.input_doc(codes, init, [], traces), "corpus", log)
    files[ctx.out("deployment")] = render(drec)
    by_addr = {drec["members"][n]["address"]: n for n in order}
    actors = {enc.addr[v]: k for k, v in ROLES.items()}
    vname = versioned_member(ctx)
    rows, dis = [], []
    machine = Linked(ctx, drec, order)
    regm = RegistryModel(ctx, drec, machine, log)
    for t, rec in zip(corpus["traces"], trs):
        machine.set_version(machine.a)
        st = {n: {} for n in order}
        apply_writes(st, rec.deploy.writes, order)
        for k, (step, r) in enumerate(zip(t["steps"], rec.steps)):
            pre = {n: dict(st[n]) for n in order}
            post = {n: dict(pre[n]) for n in order}
            apply_writes(post, r.writes, order)
            frames = real_frames(r, order, by_addr, actors)
            row = {"trace": t["id"], "index": k, "label": step["label"], "version": machine.version,
                   "agree": True, "unsupported": None, "frames": frames, "status": None}
            if r.kind == "call":
                row["status"] = "ok" if r.ok else "revert"
                touched = {n: sorted({w[1] for w in r.writes if order[w[0]] == n and not w[3]}) for n in order}
                real = {"status": row["status"], "revert": None if r.ok else r.ret, "return": r.ret if r.ok else None,
                        "pre": pre, "post": post, "touched": touched,
                        "logs": [(order[mi], tp, d) for mi, tp, d in r.logs] if r.ok else [],
                        "balances": {order[i]: v for i, v in sorted(r.balances.items())},
                        "outgoing": [[order[o[0]], o[1], o[2], o[3]] for o in r.outgoing if not o[4]],
                        "frames": frames}
                mach = machine.run(pre, dict(r.before), r)
                if mach["status"] == "unsupported":
                    row["unsupported"] = mach["reason"]
                else:
                    mach["frames"] = [[p, by_addr.get(c, actors.get(c, c)), m, s, v, ok]
                                      for p, c, m, s, v, ok in mach["frames"]]
                diff = compare(real, mach)
                if diff:
                    row["agree"] = False
                    dis.append({"trace": t["id"], "index": k, "label": step["label"], "observables": diff,
                                "reason": mach.get("reason")})
                regm.compare(t["id"], k, step["label"], r, real, frames, machine)
            rows.append(row)
            st = post
    by_version: dict = {}
    links: dict = {}
    for r in rows:
        by_version[r["version"]] = by_version.get(r["version"], 0) + 1
        for f in r["frames"]:
            if f[5]:
                key = f"{f[1]}->{f[2]}:{f[3]}"
                links[key] = links.get(key, 0) + 1
    files[ctx.out("steps")] = render({"steps_version": STEPS_VERSION, "corpus": ctx.ref(ctx.out("corpus")),
                                      "versioned_member": vname, "steps": rows})
    files[ctx.out("refinement")] = render({
        "refinement_version": REFINEMENT_VERSION, "corpus": ctx.ref(ctx.out("corpus")), "steps": len(rows),
        "compared": sum(1 for r in rows if r["status"] is not None),
        "disagreements": sum(1 for r in rows if not r["agree"]),
        "unsupported": sum(1 for r in rows if r["unsupported"]), "by_version": dict(sorted(by_version.items())),
        "links": dict(sorted(links.items())), "details": dis,
        "toolchain": {k: tc[k] for k in ("forge_sha256", "solc_sha256", "sol_deps_sha256")}})
    files[ctx.out("model_refinement")] = render(regm.record())
    regm.close()
    log(f"{len(rows)} steps, {sum(1 for r in rows if not r['agree'])} disagreements, "
        f"{sum(1 for r in rows if r['unsupported'])} unsupported")
    return files


class RegistryModel:
    """Rule M2 (module docstring)."""

    VERSION = "holon-cutover-refinement-models/0.1"

    def __init__(self, ctx: Ctx, drec: dict, machine, log=print):
        import hashlib
        import json
        from ..machine import ExtractedModel
        from ..sorts.evaluate3 import Evaluator
        from . import model as MD
        self.ctx, self.name = ctx, MD.registry(ctx)
        self.td = tempfile.TemporaryDirectory(prefix="holon-cutover-m2-")
        text, debt = MD.compile_registry(ctx, self.name, MD.init_of(ctx, self.name))   # M1's model (its init)
        self.debt = {a for a, _e in debt}
        self.rec = {"model": f"{ctx.out('models')}/{self.name}.bend", "steps": 0, "disagreements": 0,
                    "unexplained": 0, "unsupported": 0, "nested_frames": 0, "debt": sorted(self.debt),
                    "model_sha256": hashlib.sha256((text or "").encode("utf-8")).hexdigest()}
        self.details: list = []
        self.ev = None
        if text is not None:
            p = Path(self.td.name) / f"{self.name}.bend"
            p.write_text(text, encoding="utf-8")
            rel = MD.document_rel(ctx, self.name)
            data = ctx.path(rel).read_bytes()
            doc = ExtractedModel(json.loads(data), MD.info_of(ctx, self.name), None, hashlib.sha256(data).hexdigest())
            self.ev = Evaluator.build(p, doc)
            log(f"M2: {self.name}'s model built ({len(self.debt)} actions in debt)")

    def compare(self, trace: str, k: int, label: str, r, real: dict, frames: list, machine) -> None:
        from ..replay_fragments import revert_key
        n = self.name
        if not frames:
            return
        if frames[0][2] != n:
            self.rec["nested_frames"] += sum(1 for f in frames if f[2] == n)
            return
        self.rec["steps"] += 1
        model = machine.models[n]
        action = machine.by_sel[n].get(frames[0][3]) if frames[0][3] != "0x" else (
            "receive" if "receive" in model.actions else None)
        diff, reason, slots_bad = [], None, []
        if action is None:
            reason = "no action at the step's selector"
        elif action in self.debt or self.ev is None:
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
                pre = {"0x%064x" % s_: "0x%064x" % v for s_, v in real["pre"][n].items()}
                try:
                    out = self.ev.step(pre, action, args, env)
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
                    slots_bad = [{"slot": "0x%064x" % s_, "real": "0x%064x" % real["post"][n].get(s_, 0),
                                  "model": "0x%064x" % post.get(s_, 0)}
                                 for s_ in sorted(slots) if post.get(s_, 0) != real["post"][n].get(s_, 0)]
                    if slots_bad:
                        diff.append("storage")
                    mine = [(t_, d) for m_, t_, d in real["logs"] if m_ == n]
                    if mine != [([x.lower() for x in e["topics"]], e["data"].lower()) for e in out["events"]]:
                        diff.append("events")
                    outs = ((model.info.get("functions") or {}).get(model.actions[action].get("selector") or action)
                            or {}).get("outputs")
                    if outs and not diff:
                        reason = "the model gives no return data (holon.sorts.model3 has no return value)"
        if reason is not None:
            self.rec["unsupported"] += 1
        elif diff:
            self.rec["disagreements"] += 1
            self.rec["unexplained"] += 1
        if reason is not None or diff:
            self.details.append({"trace": trace, "step": k, "label": label, "action": action,
                                 "observables": diff or ["unsupported"], "reason": reason, "slots": slots_bad[:16]})

    def record(self) -> dict:
        return {"refinement_models_version": self.VERSION, "corpus": self.ctx.ref(self.ctx.out("corpus")),
                "observables": ["status", "revert", "return", "storage", "events"],
                "members": {self.name: dict(self.rec)}, "details": {self.name: self.details}}

    def close(self) -> None:
        if self.ev is not None:
            self.ev.close()
        self.td.cleanup()
