"""Rule L4: the cutover corpus on the real code and on the linked versioned machine, step by step.

`holon cutover refine` builds the harness project, runs a deployment (replay/<M>/cutover/deployment.json), runs every
corpus trace from a fresh deployment, and compares every call step with the linked machine (holon.cutover.machine) from
the real pre-state, by I69's comparison (holon.bundle.refine.compare): status, revert key on two reverts, return data on
two oks, every member's storage at every slot a write of the step touches on either side, the members' logs, balances,
outgoing calls and frames. Environment steps (waits, rolls) are run and tracked, not compared. Per-step rows in
results/<M>/cutover/steps.json, totals in results/<M>/cutover/refinement.json (their recount is the instrument's).
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
    log(f"{len(rows)} steps, {sum(1 for r in rows if not r['agree'])} disagreements, "
        f"{sum(1 for r in rows if r['unsupported'])} unsupported")
    return files
