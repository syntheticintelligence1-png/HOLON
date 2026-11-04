"""The ledger bundle of the Go part of rule PAR's models (I93; holon.records' generated bundles): the assumptions the gox
sidecar's Go document declares, and the gox models' own A-gox-* entries, each introduced by the definitions of the
milestone's gox modules that make it; the modules' list, Nat and Bool helpers are the one no_assumption group. Generated
from the document and the DERIVATION entries (the modules are generated from them), never hand-written.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import model as G

PRELUDE = ("app", "len", "take", "drop", "ite_nat", "is_true", "is_false")
TEXTS = {
    "A-gox-cells": ("one byte is one U32 cell, and an input value of width w is w independent cells (the codec layer's "
                    "convention): a cell of the model may hold a value above 255"),
    "A-gox-nat": "Go int is Nat: non-negative and without overflow (the lengths, the bound and the compressor's length)",
    "A-gox-hypz-len": ("the compressor's output length is a free Nat, bounded by HypZ_len's CB at its argument when the "
                       "call succeeds on a non-empty argument (the compression sidecar's hypothesis, I91)"),
    "A-gox-cap-len": "a slice bound site reads cap as len: the no-panic premise is the stronger hi <= len",
    "A-gox-sol-cells": ("the on-chain preimage's prefix byte cells are free U32 cells and its loop's words one list of "
                        "32 count cells: the counter-law's universal ranges over more than the contract's inputs"),
}
ROLE = {"A-gox-cells": ("_enc", "_sel", "_dec", "_pg", "_fold"), "A-gox-nat": ("_ok", "cb"),
        "A-gox-hypz-len": ("_ok", "cb"), "A-gox-cap-len": ("_safe", "_prem"), "A-gox-sol-cells": ("_ps",)}


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", s)).strip("-")


def module_defs(root: Path, m: str) -> list[str]:
    """The definitions of every gox module of the milestone, but the prelude's, sorted."""
    from .lawrun import gox_entries
    from ..records import model_defs
    out = set()
    for lid, e in sorted(gox_entries(m, root).items()):
        b = e["basis"]
        try:
            if e["subform"] == "go_round_trip":
                text = G.round_trip_module(b, lid)["module"]
            elif e["subform"] == "go_branch":
                text = G.branch_module(b, lid)["module"]
            else:
                text = G.recompute_module(b, lid)["module"]
        except G.ModelDebt:
            continue
        out |= set(model_defs(text))
    return sorted(out - set(PRELUDE))


def declared_bundle(doc: dict, rel: str, sha: str, root: Path, m: str) -> dict:
    defs = module_defs(root, m)
    entries, seen = [], set(TEXTS)
    for i, a in enumerate(doc.get("assumptions") or []):
        if not isinstance(a, dict) or not isinstance(a.get("id"), str):
            continue
        aid = _slug(a["id"])
        while aid in seen:
            aid += "-2"
        seen.add(aid)
        entries.append({"id": aid, "kind": "abstraction", "source": f"{rel}#/assumptions/{i}",
                        "text": a.get("text", ""), "introduced_by": defs})
    for k in sorted(TEXTS):
        intro = [d for d in defs if any(d.endswith(s) or d == s for s in ROLE[k])]
        entries.append({"id": k, "kind": "abstraction", "source": f"{rel}#/go", "text": TEXTS[k],
                        "introduced_by": intro})
    return {"facts": rel, "facts_sha256": sha, "model": "gox",
            "doc": ("The models of PAR's Go laws (holon.gox.model): the assumptions their Go document declares and the "
                    "models' own (generated from the document and the DERIVATION entries, never hand-written)."),
            "entries": entries,
            "no_assumption": [{"defs": list(PRELUDE), "why": "the modules' list, Nat and Bool helpers and the "
                                                            "counter-laws' motives; no modelling choice"}]}


def bundles(root: Path, facts_path) -> list[dict]:
    """The bundle of the gox sidecar's document of the milestone whose sidecar names facts_path, else []."""
    import hashlib
    root = Path(root)
    p = root / facts_path
    if p.suffix != ".json" or not p.is_file():
        return []
    try:
        rel = p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return []
    for side in sorted(root.glob("spec/M*/lib/go_laws.json")):
        try:
            sc = json.loads(side.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if sc.get("document") != rel:
            continue
        raw = p.read_bytes()
        return [declared_bundle(json.loads(raw), rel, hashlib.sha256(raw).hexdigest(), root, side.parent.parent.name)]
    return []
