"""The versioned machine evaluated: each version's module (holon.sorts.model3's model of its document) compiled and run
by holon.sorts.evaluate3, and the versioned layer's step rules (holon.versions.model) applied in Python, for the searches
(PI6, V8) and the replay's model side (V9). Bend then checks what a search found against the layer itself (the
witnesses' and inhabitants' Bend files), so nothing evaluated here is trusted.

A state is {"version": the placeholder or a path version, "storage": {real slot: word}}. A trace step is the contract's
{"label", "kind": "call" | "migrate", "version", "caller", "calldata", "ok", "action" | "call"}.

The environment of a step (A-env, the same rule on the model side and in the versioned harness): the deployment
record's block (timestamp, number, chain id), its target as the proxy's address (this), its immutables, no value and
no blobs, the calldata's length; the code of the deployment record's accounts and, at every address argument of the
record's first call (the binding's stand-ins), the labelled stand-in's runtime code; every external call a run looks
up answered by the labelled stand-in (success, the ABI word 1).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from . import PLACEHOLDER, Ctx, Refused, VersionsError, sha256_bytes
from ..keccak import keccak256

MASK = (1 << 256) - 1
STANDIN_ANSWER = (1).to_bytes(32, "big")
STANDIN_NAME = "HolonVersionsStandIn"
STANDIN_SOURCE = """// SPDX-License-Identifier: MIT
// HOLON I28: the labelled stand-in of the versioned harness (holon.versions.machine). It answers every call with the
// ABI word 1, as the versioned model's environment answers every external call a run makes.
pragma solidity =0.8.24;

contract HolonVersionsStandIn {
    fallback(bytes calldata) external payable returns (bytes memory) {
        return abi.encode(uint256(1));
    }
}
"""


def h32(v: int) -> str:
    return "0x%064x" % (int(v) & MASK)


def hx(b: bytes) -> str:
    return "0x" + bytes(b).hex()


def num(x) -> int:
    if isinstance(x, int):
        return x
    return int(str(x), 0)


def cd_bytes(cd: str) -> bytes:
    return bytes.fromhex(cd[2:] if cd.startswith("0x") else cd)


def solc_standard(cfg: dict, sources: dict, settings: dict, cwd: Path | None = None,
                  include: Path | None = None) -> dict:
    """The pinned solc's standard-json output (holon.frontends.solidity.compile.check_solc refuses an unpinned one)."""
    from ..frontends import Refused as FRefused
    from ..frontends.solidity import compile as comp
    try:
        solc, _sha, _ver = comp.check_solc(cfg, "0.8.24")
    except FRefused as e:
        raise Refused(str(e)) from e
    cmd = [solc, "--standard-json", "--base-path", "."]
    if include is not None:
        cmd += ["--include-path", str(include)]
    req = json.dumps({"language": "Solidity", "sources": sources, "settings": settings}, sort_keys=True)
    p = subprocess.run(cmd, input=req, capture_output=True, text=True, timeout=7200, cwd=str(cwd or Path.cwd()))
    try:
        out = json.loads(p.stdout)
    except ValueError as e:
        raise VersionsError(f"solc gave no JSON (exit {p.returncode}): {p.stderr.strip()[:300]}") from e
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise VersionsError("; ".join((e.get("formattedMessage") or e.get("message", ""))[:300] for e in errs[:3]))
    return out


def standin_runtime(ctx: Ctx) -> bytes:
    """The labelled stand-in's runtime code: STANDIN_SOURCE compiled by the pinned solc (cancun, no optimizer, no
    metadata hash), cached under the build directory."""
    from ..bend import build_dir
    key = hashlib.sha256(STANDIN_SOURCE.encode()).hexdigest()[:16]
    cache = build_dir(ctx.root) / "versions" / f"standin-{key}.hex"
    if cache.is_file():
        return bytes.fromhex(cache.read_text().strip())
    settings = {"evmVersion": "cancun", "optimizer": {"enabled": False}, "metadata": {"bytecodeHash": "none"},
                "outputSelection": {"*": {STANDIN_NAME: ["evm.deployedBytecode.object"]}}}
    out = solc_standard(ctx.cfg, {"StandIn.sol": {"content": STANDIN_SOURCE}}, settings)
    code = bytes.fromhex(out["contracts"]["StandIn.sol"][STANDIN_NAME]["evm"]["deployedBytecode"]["object"])
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + f".{os.getpid()}.tmp")
    tmp.write_text(code.hex())
    os.replace(tmp, cache)
    return code


class Machine:
    """The versioned machine of the committed model (gen/<M>/versions/models): its versions' evaluators, the
    deployment's environment and the layer's step rules."""

    def __init__(self, ctx: Ctx):
        from .model import deployment_admin
        self.ctx = ctx
        md = ctx.root / ctx.out("model_dir")
        ip = md / f"{ctx.model}.init.json"
        if not ip.is_file():
            raise Refused(f"{ip.relative_to(ctx.root)} is missing: run `holon versions model` first")
        self.init = json.loads(ip.read_text(encoding="utf-8"))
        self.vd = ctx.versions_doc()
        self.path = list(self.vd["path"])
        self.edges = {(e["from"], e["to"]): e for e in self.vd["edges"]}
        if self.vd.get("entry"):
            self.edges[(PLACEHOLDER, self.vd["entry"]["to"])] = self.vd["entry"]
        self.admin_slot, self.admin = deployment_admin(ctx)
        self.dep = ctx.deployment_record()
        self.docs = ctx.documents()
        self._models: dict = {}
        self._evals: dict = {}
        self._standin = None

    # ---------------------------------------------------------- versions
    def unit(self, vid: str) -> dict:
        u = (self.init.get("versions") or {}).get(vid)
        if u is None:
            raise Refused(f"the versioned model has no version {vid}")
        return u

    def extracted(self, vid: str):
        """The version's holon.machine.ExtractedModel of its compiled actions (the model debt set aside)."""
        if vid not in self._models:
            from ..machine import ExtractedModel
            from .model import version_info
            p, rel = self.docs[vid]
            data = p.read_bytes()
            doc = json.loads(data.decode("utf-8"))
            sha = sha256_bytes(data)
            info = version_info(self.ctx, rel, doc, sha)
            debt = {d["action"] for d in self.unit(vid).get("debt") or []}
            kept = dict(doc, actions=[a for a in doc.get("actions") or [] if a.get("name") not in debt])
            self._models[vid] = ExtractedModel(kept, info, Path(rel), sha)
        return self._models[vid]

    def evaluator(self, vid: str):
        if vid not in self._evals:
            from ..sorts.evaluate3 import Evaluator
            p = self.ctx.root / self.ctx.out("model_dir") / self.unit(vid)["module"]
            if sha256_bytes(p.read_bytes()) != self.unit(vid)["module_sha256"]:
                raise Refused(f"{p.name} is not the module the versioned model records")
            self._evals[vid] = Evaluator.build(p, self.extracted(vid))
        return self._evals[vid]

    def close(self) -> None:
        for e in self._evals.values():
            e.close()
        self._evals = {}

    def actions(self, vid: str) -> list:
        return list(self.unit(vid).get("actions") or [])

    def function(self, vid: str, name: str) -> dict | None:
        """{name, inputs, selector} of an action of the version (the compiler's ABI)."""
        m = self.extracted(vid)
        if name not in m.actions:
            return None
        ps = m.params(name)
        sel = (m.actions[name].get("selector") or "")
        return {"name": name, "inputs": ps or [], "selector": sel}

    def calldata(self, vid: str, name: str, values: dict) -> str:
        from ..evm_abi import encode_call
        fn = self.function(vid, name)
        if fn is None:
            raise VersionsError(f"{vid} has no compiled action {name}")
        return encode_call({"name": name, "inputs": fn["inputs"]}, values)

    def args(self, vid: str, name: str, cd: str) -> dict:
        """The call's arguments as the evaluator takes them, from the calldata's words (holon.versions.bendlit leaves:
        the same nodes the Bend literal of the step is written from)."""
        from .bendlit import Lit, py_args
        fn = self.function(vid, name)
        if fn is None:
            raise VersionsError(f"{vid} has no compiled action {name}")
        b = cd_bytes(cd)
        if fn["selector"] and b[:4].hex() != fn["selector"].removeprefix("0x"):
            raise VersionsError(f"{cd[:10]} does not call {vid}'s {name} ({fn['selector']})")
        return py_args(fn["inputs"], Lit("M").leaves(fn["inputs"], cd))

    def root_bytes_param(self, vid: str, element: dict) -> str | None:
        """The bytes parameter of the root site's action whose bytes the root site hashes at this version (PI1: its
        committed value ["keccak256" | "sha256", ["param", p]]), or None."""
        from ..rules.par_init import chains
        p, _rel = self.docs[vid]
        doc = json.loads(p.read_text(encoding="utf-8"))
        fam = next((f for f in chains(doc)["families"] if f["family"] == element["family"]), None)
        site = next((r for r in (fam or {}).get("root_sites") or [] if r["action"] == element["root_action"]), None)
        act = next((a for a in doc.get("actions") or [] if a.get("name") == element["root_action"]), None)
        if site is None or act is None:
            return None
        v = act["writes"][int(site["at"][len("writes["):-1])].get("value")
        x = v[1] if isinstance(v, list) and len(v) == 2 else None
        if isinstance(x, list) and len(x) == 2 and x[0] == "param":
            return x[1]
        return None

    def venv_fields(self) -> list:
        return [tuple(x) for x in (self.init.get("layer") or {}).get("venv") or []]

    # ---------------------------------------------------------- environment
    def standin(self) -> bytes:
        if self._standin is None:
            self._standin = standin_runtime(self.ctx)
        return self._standin

    def standin_addresses(self) -> list:
        """The address arguments of the deployment record's first call, decoded by the first path version's function of
        that selector (the binding's stand-ins)."""
        from .bendlit import Lit
        calls = self.dep.get("calls") or []
        if not calls:
            return []
        cd = calls[0]["data"]
        v0 = self.path[0]
        for name in self.actions(v0):
            fn = self.function(v0, name)
            if fn and fn["selector"] and cd[2:10] == fn["selector"].removeprefix("0x"):
                nodes = Lit("M").leaves(fn["inputs"], cd)
                return sorted({n[1] for p, n in zip(fn["inputs"], nodes) if p.get("type") == "address" and n[1]})
        raise Refused("the deployment record's first call calls no function of the path's first version")

    def code_table(self) -> dict:
        """The proxy's code (the deployment record's target's) and the labelled stand-in's at the binding's stand-ins."""
        target = num(self.dep["target"])
        code = {}
        for a, c in (self.dep.get("code") or {}).items():
            if num(a) == target:
                code[target] = cd_bytes(c)
        if target not in code:
            raise Refused("the deployment record holds no code of its target")
        for a in self.standin_addresses():
            code.setdefault(a, self.standin())
        return dict(sorted(code.items()))

    def reads_code(self, vid: str, name: str) -> bool:
        a = self.extracted(vid).actions.get(name) or {}
        return '["code",' in json.dumps(a, separators=(",", ":"))

    def env(self, vid: str, name: str, caller: int, calldata: str, calls: list | None = None) -> dict:
        dep = self.dep
        return {"block.timestamp": num(dep.get("timestamp") or 0), "block.number": num(dep.get("number") or 0),
                "block.chainid": num(dep.get("chainid") or 0), "this": num(dep["target"]), "caller": caller,
                "msg.value": 0, "msg.data.length": len(cd_bytes(calldata)), "blobhash": [],
                "immutable": {k: num(v) for k, v in (dep.get("immutables") or {}).items()},
                "code": self.code_table() if self.reads_code(vid, name) else {}, "calls": list(calls or [])}

    # ---------------------------------------------------------- runs
    def run_action(self, vid: str, name: str, sl: list, caller: int, calldata: str) -> dict:
        """One run of the version's action on the storage list sl (the model's own list: its order and its zero
        entries): {"status", "revert", "sl", "writes", "kh", "sh", "calls", "env", "code"}."""
        from ..machine_bend import bname
        from ..sorts.evaluate3 import word
        ev = self.evaluator(vid)
        args = self.args(vid, name, calldata)
        hst = {"$r": "HSt", "f": {"sl": [{"$r": "KW", "f": {"k": word(k), "v": word(v)}} for k, v in sl]}}
        calls: list = []
        kh, sh = {}, {}
        hs = ev.hashes()
        ans, env = None, None
        for _ in range(64):
            env = self.env(vid, name, caller, calldata, calls)
            for _r in range(64):
                a = [hst, ev.args_in(name, args), ev.env_in(env)]
                if "keccak256" in hs:
                    a.append(ev.table(kh))
                if "sha256" in hs:
                    a.append(ev.table(sh))
                ans = ev.call(f"run_{bname(name)}", a)
                new = False
                for k in ans["keys"].get("kh") or []:
                    if k not in kh:
                        kh[k] = int.from_bytes(keccak256(bytes.fromhex(k[2:])), "big")
                        new = True
                for k in ans["keys"].get("sh") or []:
                    if k not in sh:
                        sh[k] = int.from_bytes(hashlib.sha256(bytes.fromhex(k[2:])).digest(), "big")
                        new = True
                if not new:
                    break
            else:
                raise VersionsError(f"{vid} {name}: the hash lookups did not settle")
            known = {(c["to"], c["data"]) for c in calls}
            fresh = [(to, d) for to, d in ans.get("calls") or [] if (to, d) not in known]
            if not fresh:
                break
            for to, d in fresh:
                calls.append({"to": to, "data": d, "ok": True, "ret": hx(STANDIN_ANSWER)})
        else:
            raise VersionsError(f"{vid} {name}: the external calls did not settle")
        f = ans["out"]["f"]
        c = int(f["c"])
        rv = f["rv"].get("$b", "0x") if isinstance(f["rv"], dict) else "0x"
        base = {"kh": kh, "sh": sh, "calls": calls, "env": env, "code": c}
        if c != 0:
            return {"status": "revert", "revert": rv, "sl": list(sl), "writes": {}, **base}
        post = [(int(kv["f"]["k"], 16), int(kv["f"]["v"], 16)) for kv in f["po"]["f"]["sl"]]
        view = storage_of(post)
        touched = sorted({int(x, 16) for x in f["tw"]})
        return {"status": "ok", "revert": "0x", "sl": post, "writes": {x: view.get(x, 0) for x in touched}, **base}

    def step(self, state: dict, st: dict) -> dict:
        """The versioned layer's step rule on a trace step: {"state", "status", "revert", "writes", "kh", "sh", "calls",
        "env"} (env: the call's environment, None for a step that runs no call)."""
        v, sl = state["version"], list(state["sl"])
        admin = storage_of(sl).get(self.admin_slot, 0)
        same = {"state": {"version": v, "sl": sl}, "status": "revert", "revert": "0x", "writes": {}, "kh": {},
                "sh": {}, "calls": [], "env": None}
        caller = num(st["caller"])
        keys = ("status", "revert", "writes", "kh", "sh", "calls", "env")
        if st["kind"] == "migrate":
            a = PLACEHOLDER if st["label"] == "entry" else st["label"].split("->", 1)[0]
            b = st["version"]
            if v != a or (a, b) not in self.edges:
                return same
            if not st.get("call"):
                return dict(same, state={"version": b, "sl": sl}, status="ok")
            if st["call"] not in self.actions(b):
                return same
            r = self.run_action(b, st["call"], sl, admin, st["calldata"])
            return {"state": {"version": b if r["status"] == "ok" else v, "sl": r["sl"]}, **{k: r[k] for k in keys}}
        if v != st["version"] or caller == admin or st["action"] not in self.actions(v):
            return same
        r = self.run_action(v, st["action"], sl, caller, st["calldata"])
        return {"state": {"version": v, "sl": r["sl"]}, **{k: r[k] for k in keys}}

    def initial(self) -> dict:
        return {"version": PLACEHOLDER, "sl": [(self.admin_slot, self.admin)]}

    def run(self, trace: list) -> tuple[list, dict, dict]:
        """([step outcome], the keccak256 table, the sha256 table) of a trace from vr0."""
        s = self.initial()
        outs, kh, sh = [], {}, {}
        for st in trace:
            o = self.step(s, st)
            kh.update(o["kh"])
            sh.update(o["sh"])
            outs.append(o)
            s = o["state"]
        return outs, dict(sorted(kh.items())), dict(sorted(sh.items()))

    # ---------------------------------------------------------- trace steps
    def migrate_step(self, a: str, b: str, call: str | None, calldata: str = "0x") -> dict:
        label = "entry" if a == PLACEHOLDER else f"{a}->{b}"
        return {"label": label, "kind": "migrate", "version": b, "caller": "0x" + h32(self.admin)[-40:],
                "call": call, "calldata": calldata if call else "0x", "ok": True}

    def call_step(self, vid: str, name: str, caller: int, calldata: str) -> dict:
        return {"label": name, "kind": "call", "action": name, "version": vid, "caller": "0x" + h32(caller)[-40:],
                "calldata": calldata, "ok": True}


def storage_of(sl: list) -> dict:
    """{slot: word} of a storage list, the first entry of a slot winning (the model's kw_get)."""
    out = {}
    for k, v in sl:
        out.setdefault(k, v)
    return out


def keccak_table(entries: dict) -> dict:
    """{hex key: word} with each value the key's real keccak256 (a check of a run's table)."""
    return {k: int.from_bytes(keccak256(bytes.fromhex(k[2:])), "big") for k in entries}
