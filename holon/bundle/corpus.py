"""Rule C3: the bundle's corpus, gen/<M>/bundle/corpus.json.

Three sources, in this order: m1, the base corpus of the adopted member's M1 model (holon.mreplay.random_corpus on
corpus.m1.facts, with its seed and size), each step {"row": the row}; seed, the sidecar's planted traces verbatim; and
random, drawn by the rule below from random.Random(corpus.random.seed), over the members' actions (each document's
actions sorted by name, with the compiler's ABI entry of each, by selector) and the sidecar's pools. Draw order per
step: the warp (num/den), the member (sorted names), the action, the caller, the value (payable actions only), then
every ABI input in order (arrays: a length for T[], then the elements; tuples: the components; address, bool, uintN and
intN from the uint pool modulo 2^N or 2^(N-1), appended when new, bytes, bytesN as the first N bytes of a word).
"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

from . import BundleError, Ctx, render, write_or_check

CORPUS_VERSION = "holon-bundle-corpus/0.1"


def _abi_type(x: dict) -> str:
    t = x["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_abi_type(c) for c in x["components"]) + ")" + t[len("tuple"):]
    return t


def abis(ctx: Ctx) -> dict:
    """{member: {selector or kind: ABI entry with its "signature"}} of every member, from the pinned solc at the
    member's commit (the checkout at the head, else the commit's tree from git objects)."""
    from .extract import source_for
    solc = ctx.cfg["replay"]["solc"]
    deps = Path(ctx.cfg["replay"]["sol_deps"]) / "node_modules"
    out = {}
    for m in ctx.members():
        src = Path(source_for(ctx, ctx.commit_of(m)))
        unit, name = m["source"], m["contract"]
        text = (src / unit).read_text(encoding="utf-8")
        req = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}},
                          "settings": {"evmVersion": "cancun", "optimizer": {"enabled": False},
                                       "outputSelection": {unit: {name: ["abi", "evm.methodIdentifiers"]}}}})
        p = subprocess.run([solc, "--standard-json", "--base-path", ".", "--include-path", str(deps)], input=req,
                           capture_output=True, text=True, cwd=str(src), timeout=1800)
        o = json.loads(p.stdout)
        errs = [e for e in o.get("errors", []) if e.get("severity") == "error"]
        if errs:
            raise BundleError(f"{m['name']}: {errs[0].get('message', '')[:300]}")
        c = o["contracts"][unit][name]
        ids = c["evm"]["methodIdentifiers"]
        table = {}
        for e in c["abi"]:
            if e["type"] == "function":
                sig = f"{e['name']}({','.join(_abi_type(x) for x in e['inputs'])})"
                table["0x" + ids[sig]] = dict(e, signature=sig)
            elif e["type"] in ("receive", "fallback"):
                table[e["type"]] = dict(e, signature=e["type"])
        out[m["name"]] = table
    return out


def member_actions(ctx: Ctx, table: dict) -> dict:
    """{member: [(action name, ABI entry)] sorted by name}: each document's actions with their ABI entries."""
    out = {}
    for m in ctx.members():
        doc = ctx.load(ctx.document_rel(m))
        acts = []
        for a in sorted(doc["actions"], key=lambda a: a["name"]):
            key = a.get("selector") or a["name"]
            if key not in table[m["name"]]:
                raise BundleError(f"{m['name']}.{a['name']}: no ABI entry for {key}")
            acts.append((a["name"], table[m["name"]][key]))
        out[m["name"]] = acts
    return out


def random_part(ctx: Ctx, acts: dict) -> list:
    R = ctx.side["corpus"]["random"]
    rng = random.Random(R["seed"])
    members = sorted(m["name"] for m in ctx.members())
    num, den = (int(x) for x in R["warp"]["probability"].split("/"))
    out = []
    for t in range(R["traces"]):
        pool = list(R["uints"])

        def draw(x: dict):
            ty = x["type"]
            if ty.endswith("]"):
                base, n = ty[:ty.rindex("[")], ty[ty.rindex("[") + 1:-1]
                k = rng.choice(R["array_lengths"]) if n == "" else int(n)
                return [draw(dict(x, type=base)) for _ in range(k)]
            if ty == "tuple":
                return [draw(c) for c in x["components"]]
            if ty == "address":
                return rng.choice(R["addresses"])
            if ty == "bool":
                return rng.choice([False, True])
            if ty.startswith("uint") or ty.startswith("int"):
                bits = int(ty[4:] or 256) if ty.startswith("uint") else int(ty[3:] or 256) - 1
                v = rng.choice(pool) % (1 << bits)
                if v not in pool:
                    pool.append(v)
                return v
            if ty == "bytes":
                return rng.choice(R["bytes"])
            if ty.startswith("bytes"):
                return rng.choice(R["words"])[:2 + 2 * int(ty[5:])]
            raise BundleError(f"C3: no pool for the ABI type {ty}")
        steps = []
        for _ in range(R["steps"]):
            warp = rng.choice(R["warp"]["seconds"]) if rng.randrange(den) < num else 0
            m = rng.choice(members)
            _name, abi = rng.choice(acts[m])
            caller = rng.choice(R["callers"])
            value = rng.choice(R["values"]) if abi.get("stateMutability") == "payable" else 0
            args = [draw(x) for x in abi.get("inputs") or []]
            st = {"call": {"to": m, "fn": abi["signature"], "caller": caller, "value": value, "args": args}}
            if warp:
                st["warp"] = warp
            steps.append(st)
        out.append({"id": f"random/{t:03d}", "source": "random", "steps": steps})
    return out


def m1_part(ctx: Ctx, log=print) -> list:
    from ..mpipeline import CompiledMachine
    from ..mreplay import random_corpus
    c = ctx.side["corpus"]["m1"]
    cm = CompiledMachine.build(ctx.path(c["facts"]))
    traces = random_corpus(cm, c["traces"], seed=c["seed"])
    log(f"m1: {len(traces)} traces, {sum(len(t) for t in traces)} rows")
    return [{"id": f"m1/{i:03d}", "source": "m1", "steps": [{"row": a} for a in tr]} for i, tr in enumerate(traces)]


def build(ctx: Ctx, log=print) -> dict:
    traces = m1_part(ctx, log)
    traces += [{"id": f"seed/{k}", "source": "seed", "steps": v} for k, v in ctx.side["corpus"]["seed"].items()]
    traces += random_part(ctx, member_actions(ctx, abis(ctx)))
    srcs = [t["source"] for t in traces]
    return {"corpus_version": CORPUS_VERSION, "sidecar": ctx.ref(ctx.side_rel),
            "sources": {k: srcs.count(k) for k in ("m1", "seed", "random")}, "traces": traces}


def main(ctx: Ctx, check: bool, log) -> int:
    return write_or_check(ctx, {ctx.out("corpus"): render(build(ctx, log))}, check, log=log)
