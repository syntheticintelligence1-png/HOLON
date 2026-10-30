"""The creation codes the cutover harness deploys from, with each contract's immutables named: the edge's two path
versions' implementations (built from their commits under the configuration their matched upgrades used, the versioned
machine's history) and the legacy registry (built from its pinned commit under the configuration the bundle's
acquisition matched), by the pinned solc. Cached under the build directory; nothing here names a target.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import BundleError, Ctx, Refused


def compile_contract(ctx: Ctx, repo: str, commit: str, paths: list, unit: str, name: str, conf: dict) -> dict:
    """{"creation": hex, "immutables": {name: [[start, length]..]}} of contract `name` in `unit` at the commit's tree."""
    from ..bend import build_dir
    from ..replay import ensure_sol_deps
    from ..versions.extract import tree
    from ..versions.machine import solc_standard
    key = hashlib.sha256(json.dumps([commit, conf, unit, name], sort_keys=True).encode()).hexdigest()[:16]
    cache = build_dir(ctx.root) / "cutover" / "impl" / f"{name}-{key}.json"
    if cache.is_file():
        return json.loads(cache.read_text())
    t = tree(ctx.versions(), repo, commit, paths)
    deps = ensure_sol_deps(Path((ctx.cfg.get("replay") or {}).get("sol_deps") or ""))
    settings = {"evmVersion": conf["evm_version"], "optimizer": {"enabled": True, "runs": int(conf["optimizer_runs"])},
                "metadata": {"bytecodeHash": conf["bytecode_hash"]},
                "outputSelection": {unit: {name: ["evm.bytecode.object", "evm.bytecode.linkReferences",
                                                  "evm.deployedBytecode.immutableReferences"]},
                                    "*": {"": ["ast"]}}}
    out = solc_standard(ctx.cfg, {unit: {"content": (t / unit).read_text(encoding="utf-8")}}, settings, cwd=t,
                        include=deps)
    c = out["contracts"][unit][name]
    if c["evm"]["bytecode"].get("linkReferences"):
        raise BundleError(f"{name} links libraries; the harness deploys no library")
    names = {}
    for src in out["sources"].values():
        stack = [src["ast"]]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                if n.get("nodeType") == "VariableDeclaration" and n.get("mutability") == "immutable":
                    names[str(n["id"])] = n["name"]
                stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
            elif isinstance(n, list):
                stack.extend(n)
    imm = {}
    for aid, rs in (c["evm"].get("deployedBytecode") or {}).get("immutableReferences", {}).items():
        imm.setdefault(names.get(str(aid), f"ast:{aid}"), []).extend([[r["start"], r["length"]] for r in rs])
    d = {"creation": c["evm"]["bytecode"]["object"], "immutables": {k: sorted(v) for k, v in sorted(imm.items())}}
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, sort_keys=True))
    os.replace(tmp, cache)
    return d


def version_build(ctx: Ctx, vid: str) -> dict:
    from ..versions.replay import matched_configs
    vctx = ctx.versions()
    config = matched_configs(vctx).get(vid)
    if config is None:
        raise Refused(f"no matched configuration for {vid}")
    hside = json.loads((ctx.root / vctx.inputs["history_sidecar"]).read_text(encoding="utf-8"))
    repo = json.loads((ctx.root / vctx.inputs["extract_sidecar"]).read_text(encoding="utf-8"))["target"]["repo"]
    return compile_contract(ctx, repo, vctx.version(vid)["commit"], hside["contract"]["build_paths"],
                            hside["contract"]["source"], hside["contract"]["name"],
                            hside["compiler_configs"][config])


def registry_build(ctx: Ctx) -> dict:
    acq = ctx.side["acquisition"]
    bside = ctx.bundle().side
    conf = bside["acquisition"]["compiler_configs"][acq["registry"]["match"][1]]
    return compile_contract(ctx, bside["target"]["repo"], acq["unit"]["commit"],
                            bside["acquisition"]["registry"]["contract"]["build_paths"], acq["unit"]["path"],
                            acq["registry"]["contract"], conf)


def builds(ctx: Ctx) -> dict:
    """{"a": the old version's build, "b": the new version's, "registry": the legacy registry's}."""
    a, b = edge(ctx)
    return {"a": version_build(ctx, a), "b": version_build(ctx, b), "registry": registry_build(ctx)}


def codes(ctx: Ctx) -> list:
    """[old version's implementation, new version's implementation, the legacy registry]: the creation codes."""
    bs = builds(ctx)
    return [bytes.fromhex(bs[k]["creation"]) for k in ("a", "b", "registry")]


def edge(ctx: Ctx) -> tuple:
    """The MIG edge whose reinterpreted entry the link follows: the versioned document's one edge with a reinterpreted
    in-flight type (refused when there are several)."""
    edges = sorted({t["edge"] for t in ctx.versioned().get("in_flight_types") or [] if t["kind"] == "reinterpreted"})
    if len(edges) != 1:
        raise Refused(f"{len(edges)} edges reinterpret an in-flight entry; the link follows exactly one")
    a, b = edges[0].split("->")
    return a, b
