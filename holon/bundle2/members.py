"""The members' documents as holon.machine.ExtractedModel, with their compiler information.

The adopted document loads as holon.machine.load_extracted loads it. A generated document's sidecar
(gen/M3/bundle2/sidecars/<member>.json) names a document that is not an .extracted.json of a milestone's spec (the
common sidecar format of holon.frontends.load_sidecar requires one), so its compiler information is computed here the
way holon.machine.toolchain_info computes it: the sidecar is the one the document records (path and sha256), checked
by the Solidity frontend's own rules, compiled with the pinned solc, and the compiled units must be the document's
extraction inputs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import Ctx, Refused, file_sha


def doc_rel(ctx: Ctx, m: dict) -> str:
    return m["document"] if m.get("adopted") else f"{ctx.out['documents']}/{m['name']}.json"


def load_member(ctx: Ctx, m: dict):
    from ..machine import ExtractedModel, ModelError, compiler_info, load_extracted, sha256_bytes
    from ..frontends import ExtractionError, Refused as FRefused
    from ..frontends.solidity import _check_sidecar
    from ..frontends.solidity import compile as comp
    rel = doc_rel(ctx, m)
    p = ctx.root / rel
    if not p.is_file():
        raise Refused(f"{rel} is missing (run holon bundle2 extract)")
    if m.get("adopted"):
        return load_extracted(p, ctx.root, source=Path(ctx.source()))
    data = p.read_bytes()
    doc = json.loads(data)
    sref = (doc.get("extraction") or {}).get("sidecar") or {}
    sp = ctx.root / str(sref.get("path"))
    if not sp.is_file() or file_sha(sp) != sref.get("sha256"):
        raise Refused(f"{rel}: its extraction sidecar {sref.get('path')} is missing or differs from the recorded one")
    side = json.loads(sp.read_text(encoding="utf-8"))
    try:
        _check_sidecar(side, sp)
        cfg = comp.load_config(ctx.root)
        compiled = comp.compile_sources(cfg, side, Path(os.path.abspath(ctx.source())), storage_layout=True)
    except (FRefused, ExtractionError) as e:
        raise Refused(f"{rel}: the extraction's compile failed: {e}")
    want = {i["unit"]: i["sha256"] for i in (doc.get("extraction") or {}).get("inputs") or []}
    have = {u: sha256_bytes(b) for u, b in compiled.units.items()}
    if want != have:
        raise Refused(f"{rel}: the compiled units are not the document's extraction inputs")
    try:
        info = compiler_info(compiled.asts, compiled.layouts, doc.get("contract"))
    except ModelError as e:
        raise Refused(f"{rel}: {e}")
    info["provenance"] = {"sidecar": sref["path"], "sidecar_sha256": sref["sha256"], "solc": compiled.version,
                          "solc_sha256": compiled.solc_sha256}
    return ExtractedModel(doc, info, Path(rel), sha256_bytes(data))
