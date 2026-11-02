"""Rule M1: the legacy registry's model (the contract: tests_m3/test_cutover_slash.py, M1).

`holon cutover model` compiles the registry the link runs at the edge's old version (the sidecar's link.a.registry,
its document under inputs.documents) with holon.sorts.model3's untyped compiler, as `holon bundle model` compiles a
head member, with model3's language extension EXT1 (holon.sorts.model3.Model3X: storage arrays' push, pop and length,
an element of a dynamic array, a call named by an overload's suffix, a loop's valueless return, memory arrays of value
types, abi.encodeCall, repeated unnamed parameters). EXT1 is off in every other model, so every model compiled before
it compiles byte for byte. An action the compiler still refuses is left out as debt, with its error.

The initial state is the registry's storage in the cutover harness's deployment (outputs.deployment, written by
`holon cutover refine` from the real code's run: the deployment's storage writes, each non-zero slot as the harness
read it). The compiler information is the bundle's (holon.bundle.members.info's compile of the member's generated
sidecar over its source tree), plus the declaration table EXT1's abi.encodeCall reads: every function with a selector,
by its AST id (holon.machine's own index and parameter rule).

Outputs under outputs.models: <registry>.bend, <registry>.init.json and models.json ({"models_version", <registry>:
{"path", "sha256", "document", "document_sha256", "init", "debt": [{"action", "error"}]}}).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import BundleError, Ctx, Refused, render, sha256_bytes

MODELS_VERSION = "holon-cutover-models/0.1"


def registry(ctx: Ctx) -> str:
    return ctx.side["link"]["a"]["registry"]


def document_rel(ctx: Ctx, name: str) -> str:
    rel = (ctx.side["inputs"].get("documents") or {}).get(name)
    if not rel:
        raise Refused(f"the sidecar's inputs.documents names no document for {name}")
    return rel


def info_of(ctx: Ctx, name: str) -> dict:
    """holon.bundle.members.info's compiler information for member `name`, plus EXT1's declaration table."""
    from ..bundle.extract import generated_sidecar, source_for
    from ..frontends import ExtractionError, Refused as FRefused
    from ..frontends.solidity import compile as comp
    from ..machine import _node_index, _params, compiler_info
    bctx = ctx.bundle()
    m = bctx.member(name)
    side = generated_sidecar(bctx, m)
    src = source_for(bctx, m["commit"])
    try:
        compiled = comp.compile_sources(bctx.cfg, side, Path(os.path.abspath(src)), storage_layout=True)
    except (FRefused, ExtractionError) as e:
        raise BundleError(f"{name}: the extraction's compile failed: {e}") from e
    doc = bctx.load(bctx.document_rel(m))
    want = {i["unit"]: i["sha256"] for i in doc["extraction"].get("inputs") or []}
    have = {u: sha256_bytes(b) for u, b in compiled.units.items()}
    if want != have:
        raise BundleError(f"{name}: the compiled units are not the document's extraction inputs")
    inf = compiler_info(compiled.asts, compiled.layouts, doc.get("contract"))
    inf["provenance"] = {"sidecar": doc["extraction"]["sidecar"]["path"],
                         "sidecar_sha256": doc["extraction"]["sidecar"]["sha256"], "solc": compiled.version,
                         "solc_sha256": compiled.solc_sha256}
    ix = _node_index(compiled.asts)
    inf["decls"] = {str(i): {"selector": "0x" + n["functionSelector"], "inputs": _params(n.get("parameters"), ix)}
                    for i, n in sorted(ix.items(), key=lambda kv: str(kv[0]))
                    if n.get("nodeType") == "FunctionDefinition" and n.get("functionSelector")}
    return inf


def init_of(ctx: Ctx, name: str) -> dict:
    rel = ctx.out("deployment")
    p = ctx.path(rel)
    if not p.is_file():
        raise Refused(f"{rel} is missing (holon cutover refine writes it)")
    dep = json.loads(p.read_text(encoding="utf-8"))
    mem = dep["members"][name]
    return {"binding": rel, "deployment_sha256": sha256_bytes(p.read_bytes()), "address": mem["address"],
            "implementation": mem["implementation"],
            "read": "the cutover harness's deployment record: every storage write the real code's deployment made, "
                    "applied in order, its non-zero slots",
            "storage": dict(mem["storage"])}


def compile_registry(ctx: Ctx, name: str, init: dict) -> tuple:
    """(model text, debt [(action, error)]): model3's untyped machine with EXT1, an action it cannot compile left out
    as debt (holon.bundle.model.compile_member's loop)."""
    from ..machine import ExtractedModel
    from ..rules.sort import DocBasis, hash_functions
    from ..sorts import model3
    from ..sorts.typed_sidecar import load as load_ts
    rel = document_rel(ctx, name)
    data = ctx.path(rel).read_bytes()
    doc = json.loads(data)
    info = info_of(ctx, name)
    seeds = json.loads(load_ts(ctx.milestone, ctx.root, None).seeds.read_text(encoding="utf-8"))
    mname = model3.model_name(rel)
    assignment = {"models": {mname: {"assignment": {}}}, "sorts_sha256": None, "sites": []}
    storage = {int(k, 16): int(v, 16) for k, v in init["storage"].items()}
    debt: dict = {}
    names = {a["name"] for a in doc["actions"]}
    while True:
        d2 = dict(doc, actions=[a for a in doc["actions"] if a["name"] not in debt])
        m = ExtractedModel(d2, info, None, sha256_bytes(data))
        header = [f"# GENERATED by holon.cutover.model (holon.sorts.model3, language extension EXT1) from {rel}; do not "
                  "edit.",
                  f"# facts_sha256: {sha256_bytes(data)}",
                  f"# model_version: {model3.MODEL3_VERSION} + EXT1 (untyped: the sort section off)",
                  f"# initial state: the deployment of {init['binding']} "
                  f"({len([v for v in storage.values() if v])} non-zero slots)",
                  f"# model debt (actions left out): {', '.join(sorted(debt)) or 'none'}"]
        try:
            text, _mm = model3.build_text(m, typed=False, sorts={}, seeds=seeds, init=storage,
                                          hashes=hash_functions(d2) or ["keccak256"],
                                          basis=DocBasis(rel, d2, mname, assignment, seeds), site_rows=[],
                                          header=header, ext1=True)
            return text, sorted(debt.items())
        except model3.GenError as e:
            a = str(e).split(":", 1)[0].strip()
            if a not in names or a in debt:
                return None, [("*", str(e)[:1000])]
            debt[a] = str(e)[:1000]


def build(ctx: Ctx, log=print) -> dict:
    name = registry(ctx)
    out = ctx.out("models")
    init = init_of(ctx, name)
    text, debt = compile_registry(ctx, name, init)
    log(f"{name}: {len(debt)} actions in model debt ({', '.join(a for a, _e in debt) or 'none'})")
    if text is None:
        raise BundleError(f"{name}: the model does not compile: {debt[0][1][:300]}")
    rel = document_rel(ctx, name)
    bp = f"{out}/{name}.bend"
    files = {bp: text.encode("utf-8"), f"{out}/{name}.init.json": render(init)}
    files[f"{out}/models.json"] = render({
        "models_version": MODELS_VERSION,
        name: {"path": bp, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "document": rel,
               "document_sha256": sha256_bytes(ctx.path(rel).read_bytes()), "init": f"{out}/{name}.init.json",
               "language": "holon.sorts.model3 EXT1 (holon.sorts.model3.Model3X)",
               "debt": [{"action": a, "error": e} for a, e in debt]}})
    return files
