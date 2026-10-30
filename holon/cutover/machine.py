"""Rule L1: the linked versioned machine, I69's linked machine (holon.bundle.machine.Bundle, rules L1-L8) over a bundle
whose adopted member is versioned.

The versioned member's program is the document of the state's version (the versioned document's per-version documents,
each with its compile information, holon.versions.model.version_info); every other member's is I69's (the bundle's
members and its extracted-only members). A call by the proxy admin to the versioned member's proxy whose selector is the
proxy's upgradeTo(address) or upgradeToAndCall(address,bytes) is a migration under I28's A-proxy: it writes the EIP-1967
implementation slot, logs Upgraded(implementation) on the proxy, switches the program to the version whose deployed
implementation it names, and runs the call's data (when any) on the new program in the proxy's own frame, with the admin
as the caller. Everything else is I69's: dispatch by selector, nested frames, re-entry, depth, getters and the answers
of non-members from the harness's record.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ..bundle.machine import Bundle, Unsup, _addr
from . import Ctx

UPGRADE_TO = "upgradeTo(address)"
UPGRADE_TO_AND_CALL = "upgradeToAndCall(address,bytes)"
UPGRADED = "Upgraded(address)"


def abi_table(cfg: dict, src: Path, unit: str, name: str) -> dict:
    """{selector or kind: ABI entry with its "signature"} of a contract from the pinned solc (I69's abis, for one
    contract at one tree)."""
    from ..bundle.corpus import _abi_type
    solc = cfg["replay"]["solc"]
    deps = Path(cfg["replay"]["sol_deps"]) / "node_modules"
    text = (src / unit).read_text(encoding="utf-8")
    req = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}},
                      "settings": {"evmVersion": "cancun", "optimizer": {"enabled": False},
                                   "outputSelection": {unit: {name: ["abi", "evm.methodIdentifiers"]}}}})
    p = subprocess.run([solc, "--standard-json", "--base-path", ".", "--include-path", str(deps)], input=req,
                       capture_output=True, text=True, cwd=str(src), timeout=1800)
    o = json.loads(p.stdout)
    errs = [e for e in o.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise Unsup(f"{name}: {errs[0].get('message', '')[:300]}")
    c = o["contracts"][unit][name]
    ids = c["evm"]["methodIdentifiers"]
    table = {}
    for e in c["abi"]:
        if e["type"] == "function":
            sig = f"{e['name']}({','.join(_abi_type(x) for x in e['inputs'])})"
            table["0x" + ids[sig]] = dict(e, signature=sig)
        elif e["type"] in ("receive", "fallback"):
            table[e["type"]] = dict(e, signature=e["type"])
    return table


def decl_table(bctx, name: str) -> dict:
    """{declaration id: {"selector", "inputs"}} of every function with a selector in the member's compile (the
    compile of its extraction: its generated sidecar over its source tree), for abi.encodeCall terms."""
    import os
    from ..bundle.extract import generated_sidecar, source_for
    from ..frontends.solidity import compile as comp
    from ..machine import _node_index, _params
    m = bctx.member(name)
    side = generated_sidecar(bctx, m)
    src = source_for(bctx, m["commit"])
    compiled = comp.compile_sources(bctx.cfg, side, Path(os.path.abspath(src)), storage_layout=True)
    ix = _node_index(compiled.asts)
    out = {}
    for nid, n in ix.items():
        if n.get("nodeType") == "FunctionDefinition" and n.get("functionSelector"):
            out[str(nid)] = {"selector": "0x" + n["functionSelector"], "inputs": _params(n.get("parameters"), ix)}
    return out


class Linked(Bundle):
    def __init__(self, ctx: Ctx, dep: dict, order: list):
        from ..bundle import members as M
        from ..bundle.extract import source_for
        from ..extracted_eval import keccak
        from ..machine import ExtractedModel
        from ..versions.model import version_info
        from .build import edge
        b = ctx.bundle()
        self.ctx = b
        self.cctx = ctx
        self.dep = dep
        self.names = list(order)
        self.addr = {n: dep["members"][n]["address"] for n in self.names}
        self.by_addr = {a: n for n, a in self.addr.items()}
        self.vname = next(m["name"] for m in b.members() if m.get("adopted"))
        self.a, self.b = edge(ctx)
        vctx = ctx.versions()
        vd = ctx.versioned()
        self.vmodels, self.vabi = {}, {}
        for v in (self.a, self.b):
            rel = vd["documents"][v]["path"]
            data = ctx.path(rel).read_bytes()
            doc = json.loads(data)
            from . import sha256_bytes
            sha = sha256_bytes(data)
            self.vmodels[v] = ExtractedModel(doc, version_info(vctx, rel, doc, sha), Path(rel), sha)
            vm = next(m for m in b.members() if m.get("adopted"))
            self.vabi[v] = abi_table(ctx.cfg, Path(source_for(b, doc["target"]["commit"])), vm["source"],
                                     vm["contract"])
        self.impl_version = {dep["named"][v.lower()]: v for v in (self.a, self.b)}
        self.version = self.a
        self.models = {n: (self.vmodels[self.version] if n == self.vname else M.model(b, n)) for n in self.names}
        self.abi = {}
        for n in self.names:
            if n == self.vname:
                continue
            m = b.member(n)
            self.abi[n] = abi_table(ctx.cfg, Path(source_for(b, m["commit"])), m["source"], m["contract"])
        self.depth = int(b.side["link"]["depth"])
        self.code = {a: bytes(n) for a, n in dep["code"].items()}
        self.keccak = keccak
        self.admin = dep["named"]["admin"]
        self.impl_slot = int(b.side["acquisition"]["eip1967"]["implementation_slot"], 16)
        self.decls = {n: decl_table(b, n) for n in self.names if n != self.vname}
        self._index()

    def _index(self) -> None:
        self.abi[self.vname] = self.vabi[self.version]
        self.by_sel, self.getters, self.writes = {}, {}, {}
        for n in self.names:
            doc = self.models[n].doc
            self.by_sel[n] = {(a.get("selector") or a["name"]): a["name"] for a in doc["actions"]}
            self.writes[n] = {a["name"]: bool(a.get("writes") or a.get("effects")) for a in doc["actions"]}
            fams = {s["name"] for s in doc["storage"]} | {s["name"] for s in doc.get("inherited_storage") or []}
            self.getters[n] = {k: e for k, e in self.abi[n].items()
                               if k.startswith("0x") and k not in self.by_sel[n] and e.get("name") in fams}

    def env(self, name: str, caller: str, value: int, data: bytes, idx: int, stack: list) -> dict:
        e = super().env(name, caller, value, data, idx, stack)
        e["decls"] = self.decls.get(name) or {}
        if name == self.vname:
            e["immutable"] = dict(self.dep["versions"][self.version].get("immutables") or {})
        return e

    def decode(self, model, action: str, data: bytes) -> dict:
        """I69's decode, less the unnamed parameters: a body never reads one, and their values would share one key."""
        args = super().decode(model, action, data)
        args.pop("", None)
        return args

    def set_version(self, v: str) -> None:
        self.version = v
        self.models[self.vname] = self.vmodels[v]
        self._index()

    def frame(self, name: str, caller: str, value: int, data: bytes, parent: int, stack: list):
        """(ok, return or revert data, logs [(member, topics, data)]) of a frame on member `name`: I69's frame (rules
        L3-L6, holon.bundle.machine.Bundle.frame), by the cutover evaluator (holon.cutover.evaluate)."""
        from .evaluate import step as eval_step
        idx = len(self.frames)
        sel = "0x" + data[:4].hex() if len(data) >= 4 else ("0x" if not data else "0x" + data.hex())
        self.frames.append([parent, caller, name, sel, value, None])
        if len(stack) >= self.depth:
            raise Unsup("depth")
        saved = ({n: dict(s) for n, s in self.st.items()}, dict(self.bal))
        me = self.addr[name]
        if value:
            if self.bal.get(caller, 0) < value:
                raise Unsup(f"a call of {value} wei from {caller}, whose balance is lower")
            self.bal[caller] = self.bal.get(caller, 0) - value
            self.bal[me] = self.bal.get(me, 0) + value

        def revert(d: bytes):
            self.st, self.bal = saved
            self.frames[idx][5] = False
            return False, d, []
        if not data:
            action = "receive" if "receive" in self.models[name].actions else (
                "fallback" if "fallback" in self.models[name].actions else None)
        elif len(data) >= 4 and sel in self.by_sel[name]:
            action = self.by_sel[name][sel]
        elif len(data) >= 4 and sel in self.getters[name]:
            if name in stack:
                pass                          # a getter writes nothing: re-entry is allowed (L5)
            try:
                ret = self.getter(name, self.getters[name][sel], data[4:])
            except Unsup:
                raise
            self.frames[idx][5] = True
            return True, ret, []
        else:
            action = None
        if action is None:
            return revert(b"")
        if name in stack and self.writes[name].get(action):
            raise Unsup(f"reentry: {name}.{action}")
        model = self.models[name]
        try:
            args = self.decode(model, action, data)
        except Unsup:
            return revert(b"")
        env = self.env(name, caller, value, data, idx, stack + [name])
        r = eval_step(model, self.st[name], action, args, env)
        if r["status"] == "unsupported":
            raise Unsup(f"{name}.{action}: {r.get('reason')}")
        if r["status"] == "revert":
            if r.get("revert_prefix"):
                raise Unsup(f"{name}.{action}: only the revert data's selector is determined")
            return revert(bytes.fromhex(r["revert"][2:]))
        for k, v in r["writes"].items():
            self.st[name][int(k, 16)] = int(v, 16)
        self.frames[idx][5] = True
        logs = [(e.get("emitter", name), [t.lower() for t in e["topics"]], e["data"].lower()) for e in r["events"]]
        return True, bytes.fromhex((r.get("return") or "0x")[2:]), logs

    # ------------------------------------------------------------------------------------------- one step
    def run(self, pre: dict, balances: dict, step) -> dict:
        from ..extracted_eval import keccak
        sel_up = "0x" + keccak(UPGRADE_TO.encode()).to_bytes(32, "big")[:4].hex()
        sel_upc = "0x" + keccak(UPGRADE_TO_AND_CALL.encode()).to_bytes(32, "big")[:4].hex()
        data = bytes.fromhex(step.data[2:])
        sel = "0x" + data[:4].hex() if len(data) >= 4 else None
        if step.to == self.addr[self.vname] and step.caller == self.admin and sel in (sel_up, sel_upc):
            return self.migrate(pre, balances, step, data, sel == sel_upc)
        return super().run(pre, balances, step)

    def migrate(self, pre: dict, balances: dict, step, data: bytes, with_call: bool) -> dict:
        from ..extracted_eval import abi_decode, keccak
        from .evaluate import step as eval_step
        self.st = {n: dict(pre[n]) for n in self.names}
        self.bal = dict(balances)
        self.frames, self.outgoing, self.answers = [], [], {}
        self.step = step
        self.used = set()
        sel = "0x" + data[:4].hex()
        self.frames.append([-1, step.caller, self.vname, sel, step.value, None])
        prior = self.version
        try:
            if with_call:
                impl, cd = abi_decode(data[4:], [{"type": "address"}, {"type": "bytes"}])
            else:
                (impl,), cd = abi_decode(data[4:], [{"type": "address"}]), b""
            impl = _addr(int.from_bytes(impl, "big") if isinstance(impl, (bytes, bytearray)) else impl)
            v = self.impl_version.get(impl)
            if v is None:
                raise Unsup(f"a migration to {impl}, no version's deployed implementation")
            self.set_version(v)
            n = self.vname
            self.st[n][self.impl_slot] = int(impl, 16)
            logs = [(n, ["0x%064x" % keccak(UPGRADED.encode()), "0x%064x" % int(impl, 16)], "0x")]
            ok, ret = True, b""
            if cd:
                model = self.models[n]
                csel = "0x" + bytes(cd)[:4].hex()
                action = self.by_sel[n].get(csel)
                if action is None:
                    raise Unsup(f"the migration's call selector {csel} is no action of {v}")
                args = self.decode(model, action, bytes(cd))
                env = self.env(n, step.caller, 0, bytes(cd), 0, [n])
                r = eval_step(model, self.st[n], action, args, env)
                if r["status"] == "unsupported":
                    raise Unsup(f"{n}@{v}.{action}: {r.get('reason')}")
                if r["status"] == "revert":
                    ok, ret = False, bytes.fromhex(r["revert"][2:])
                else:
                    for k, val in r["writes"].items():
                        self.st[n][int(k, 16)] = int(val, 16)
                    logs += [(e.get("emitter", n), [t.lower() for t in e["topics"]], e["data"].lower())
                             for e in r["events"]]
        except Unsup as e:
            self.set_version(prior)
            return {"status": "unsupported", "reason": str(e)[:500], "frames": self.frames}
        if not ok:
            self.set_version(prior)
            self.frames[0][5] = False
            return {"status": "revert", "revert": "0x" + ret.hex(), "return": None, "frames": self.frames,
                    "storage": {n: dict(pre[n]) for n in self.names}, "logs": [],
                    "balances": {n: balances.get(self.addr[n], 0) for n in self.names}, "outgoing": []}
        self.frames[0][5] = True
        kept = self._kept()
        return {"status": "ok", "revert": None, "return": "0x", "frames": [f[:5] + [kept[i]] for i, f in
                                                                            enumerate(self.frames)],
                "storage": self.st, "logs": logs, "balances": {n: self.bal.get(self.addr[n], 0) for n in self.names},
                "outgoing": [o[:4] for o in self.outgoing if o[4] and kept[o[5]]]}
