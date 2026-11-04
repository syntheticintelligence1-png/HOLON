"""The members' loaded models (holon.machine.ExtractedModel) and their compiler information.

The adopted member's document is loaded as holon.machine.load_extracted loads it. A generated member's compiler
information is the compile of its generated sidecar (rule E1) over its source tree (the checkout at the head, else the
commit's tree, rule E3): the same compiler_info holon.machine.toolchain_info computes, with the same provenance, here
from the sidecar dict (a generated sidecar's output lies under the bundle's documents, not at an .extracted.json path,
which holon.frontends.load_sidecar requires of a milestone's own sidecars).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import BundleError, Ctx, sha256_bytes

_CACHE: dict = {}


def info(ctx: Ctx, name: str) -> dict:
    from ..frontends import ExtractionError, Refused as FRefused
    from ..frontends.solidity import compile as comp
    from ..machine import compiler_info
    from .extract import generated_sidecar, source_for
    m = ctx.member(name)
    key = ("info", str(ctx.root), name)
    if key in _CACHE:
        return _CACHE[key]
    side = generated_sidecar(ctx, m)
    src = source_for(ctx, m["commit"])
    try:
        compiled = comp.compile_sources(ctx.cfg, side, Path(os.path.abspath(src)), storage_layout=True)
    except (FRefused, ExtractionError) as e:
        raise BundleError(f"{name}: the extraction's compile failed: {e}") from e
    doc = ctx.load(ctx.document_rel(m))
    want = {i["unit"]: i["sha256"] for i in doc["extraction"].get("inputs") or []}
    have = {u: sha256_bytes(b) for u, b in compiled.units.items()}
    if want != have:
        raise BundleError(f"{name}: the compiled units are not the document's extraction inputs")
    inf = compiler_info(compiled.asts, compiled.layouts, doc.get("contract"))
    srel = doc["extraction"]["sidecar"]["path"]
    inf["provenance"] = {"sidecar": srel, "sidecar_sha256": doc["extraction"]["sidecar"]["sha256"],
                         "solc": compiled.version, "solc_sha256": compiled.solc_sha256}
    _CACHE[key] = inf
    return inf


def model(ctx: Ctx, name: str):
    """The member's ExtractedModel."""
    from ..machine import ExtractedModel, load_extracted
    key = ("model", str(ctx.root), name)
    if key in _CACHE:
        return _CACHE[key]
    m = ctx.member(name)
    rel = ctx.document_rel(m)
    if m.get("adopted"):
        mod = load_extracted(rel, ctx.root)
    else:
        data = ctx.path(rel).read_bytes()
        mod = ExtractedModel(json.loads(data), info(ctx, name), Path(rel), sha256_bytes(data))
    _CACHE[key] = mod
    return mod
