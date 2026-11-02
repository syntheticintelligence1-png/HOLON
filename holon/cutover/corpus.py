"""Rule L3: the cutover corpus, the sidecar's planted traces made concrete (gen/<M>/cutover/corpus.json).

A planted step's label is "<member>.<action>[(<roles>)] by <role>", "<member>@<version>.<action> by <role>", "cutover by
<role>" or "warp <parameter>[ blocks]". Steps on the versioned member are abstract rows of the harness (its commit,
challenge, prove and claim rows, built at whatever version the proxy runs); the others are calls whose calldata is the
action's ABI signature (its document's parameter types) and arguments filled by fixed rules from the deployment and the
earlier steps only: a role or member is its name (resolved to an address after the deployment run); a bytes parameter
takes the length a guard of the action equates its length with (else 0), its bytes and every bytes32 parameter the
keccak256 expansion of (trace, step, parameter); a payable call carries the deployment parameter its label's member names
for it. The cutover is the admin's upgradeToAndCall to the edge's new implementation with the edge's introduced
initializer, called with the new registry and the trace's last committed batch index. Nothing here names a target.
"""
from __future__ import annotations

import re

from . import Ctx, render

CORPUS_VERSION = "holon-cutover-corpus/0.1"
# The deployment's parameters (the harness's init, in its order). F, W, D, t and the genesis post-state root are I69's
# bundle deployment's (spec/M3/lib/bundle.json deployment.init); the legacy registry is given the new registry's
# parameters of I69's deployment (a 1 ether bond, a challenge deposit of 1 wei, a 20 % reward); a lock of 3 blocks and
# message gas limits of 1,000,000 are the harness's own.
KEYS = ["t", "chain_id", "F", "W", "D", "genesis_post", "a.bond", "a.deposit", "a.lock_blocks", "a.reward",
        "a.gas_add", "a.gas_remove", "b.bond", "b.deposit", "b.reward"]
ROLES = {"owner": "@harness", "admin": "@admin", "s1": "@w2", "s2": "@w3", "c": "@w4", "p": "@w5"}
WHO = {"@harness": 1, "@w2": 2, "@w3": 3, "@w4": 4, "@w5": 5}
_LABEL = re.compile(r"^(?P<member>\w+)(@(?P<version>\w+))?\.(?P<action>\w+)(\((?P<roles>[\w,]*)\))? by (?P<by>\w+)$")


def init_values(ctx: Ctx) -> list:
    b = ctx.bundle().side["deployment"]["init"]
    v = dict(zip(b["keys"], b["values"]))
    return [v["t"], 53077, v["F"], v["W"], v["D"], v[b["keys"][-1]], 10 ** 18, 1, 3, 20, 1_000_000, 1_000_000,
            10 ** 18, 1, 20]


def _expand(tag: str, n: int) -> str:
    from ..extracted_eval import keccak
    out = b""
    k = 0
    while len(out) < n:
        out += keccak(f"{tag}#{k}".encode()).to_bytes(32, "big")
        k += 1
    return "0x" + out[:n].hex()


def _len_of(action: dict, param: str) -> int:
    for g in action.get("guards") or []:
        for t in _eqs(g.get("expr")):
            if t[1] == ["len", ["param", param]] and isinstance(t[2], int):
                return t[2]
    return 0


def _eqs(t) -> list:
    out = []
    if isinstance(t, list):
        if len(t) == 3 and t[0] == "==":
            out.append(t)
        for x in t:
            out.extend(_eqs(x))
    return out


def signature(action: dict) -> str:
    return f"{action['name']}({','.join(p['type'] for p in action['params'])})"


def documents(ctx: Ctx) -> dict:
    """{member: document} of the members a planted label may name; the versioned member's per version."""
    out = {}
    for m in ctx.bundle().all_members():
        out[m["name"]] = ctx.load(ctx.bundle().document_rel(m))
    return out


def versioned_member(ctx: Ctx) -> str:
    """The bundle's adopted member: the one whose program is the versioned document's."""
    names = [m["name"] for m in ctx.bundle().members() if m.get("adopted")]
    if len(names) != 1:
        raise ValueError(f"{len(names)} adopted members; the link versions exactly one")
    return names[0]


def rows_table(ctx: Ctx) -> dict:
    return ctx.load(f"{ctx.out('harness')}/rows.json")


def _token(tok, k: int, par: dict, deposit: int) -> int:
    if isinstance(tok, int):
        return tok
    return {"k": k, "k+1": k + 1, "root(k)": par["genesis_post"] + k, "root(k+1)": par["genesis_post"] + k + 1,
            "deposit": deposit}[tok]


def concrete(ctx: Ctx, tid: str, labels: list, docs: dict, init: list) -> list:
    from .build import edge
    a, b = edge(ctx)
    par = dict(zip(KEYS, init))
    rt = rows_table(ctx)
    new_registry = ctx.side["link"]["b"]["registry"]
    old_registry = ctx.side["link"]["a"]["registry"]
    vdocs = {v: ctx.load(d["path"]) for v, d in ctx.versioned()["documents"].items()}
    committed, steps = 0, []
    for k, lab in enumerate(labels):
        st = {"label": lab}
        if lab.startswith("warp "):
            what = lab.split()[1]
            n = par[rt["waits"][what]] if what in rt["waits"] else int(what)
            st["row"] = [rt["roll"] if lab.endswith(" blocks") else rt["wait"], n]
            steps.append(st)
            continue
        if lab.startswith("cutover by "):
            init_fn = next(x for x in vdocs[b]["actions"] if x["name"] in _introduced(ctx, a, b))
            fill = []
            for p in init_fn["params"]:
                fill.append(f"@{new_registry}" if p["type"] == "address" else committed)
            st["call"] = {"caller": ROLES[lab.split(" by ", 1)[1].split(":", 1)[0].strip()], "to": versioned_member(ctx),
                          "fn": "upgradeToAndCall(address,bytes)",
                          "args": [f"@{b.lower()}", {"fn": signature(init_fn), "args": fill}], "value": 0}
            st["version"] = f"{a}->{b}"
            steps.append(st)
            continue
        m = _LABEL.match(lab)
        if not m:
            raise ValueError(f"{tid}: an unreadable planted label {lab!r}")
        member, version, action, by = m.group("member"), m.group("version"), m.group("action"), m.group("by")
        who = ROLES[by]
        if version:
            spec = rt["rows"][action]
            dep = par["a.deposit" if version == a else "b.deposit"]
            st["row"] = [spec["op"], WHO[who]] + [_token(x, committed, par, dep) for x in spec["args"]]
            st["version"] = version
            if spec.get("commits"):
                committed += 1
            steps.append(st)
            continue
        doc = docs[member]
        act = next(x for x in doc["actions"] if x["name"] == action)
        roles = [r for r in (m.group("roles") or "").split(",") if r]
        args = []
        for p in act["params"]:
            t = p["type"]
            if t.endswith("[]"):
                args.append([ROLES[r] for r in roles])
                roles = []
            elif t == "address":
                args.append(ROLES[roles.pop(0)] if roles else who)
            elif t == "bytes":
                args.append(_expand(f"{tid}|{k}|{p['name']}", _len_of(act, p["name"])))
            elif t == "bytes32":
                args.append(_expand(f"{tid}|{k}|{p['name']}", 32))
            else:
                raise ValueError(f"{tid}: no fill rule for {member}.{action}'s {t} parameter")
        value = 0
        if act.get("payable"):
            value = par["a.bond"] if member == old_registry else par["b.bond"]
        st["call"] = {"caller": who, "to": member, "fn": signature(act), "args": args, "value": value}
        steps.append(st)
    return steps


def _introduced(ctx: Ctx, a: str, b: str) -> set:
    vd = ctx.versioned()
    e = next(x for x in vd["edges"] if x["from"] == a and x["to"] == b)
    return {i["name"] for i in e.get("introduced") or []}


def build(ctx: Ctx, log=print) -> dict:
    init = init_values(ctx)
    docs = documents(ctx)
    traces = []
    for tid, labels in sorted(ctx.side["corpus"]["traces"].items()):
        traces.append({"id": tid, "steps": concrete(ctx, tid, labels, docs, init)})
    log(f"{len(traces)} traces, {sum(len(t['steps']) for t in traces)} steps")
    return {ctx.out("corpus"): render({"corpus_version": CORPUS_VERSION, "sidecar": ctx.ref(ctx.side_rel),
                                       "deployment": {"keys": KEYS, "init": init}, "roles": ROLES,
                                       "traces": traces})}
