"""Rules S1-S3: a migration's slash sites, from the versioned machine's MIG-edge data and its per-version documents.

S1 For each MIG edge a->b of the versioned document: its retyped in-flight entries T and its reinterpreted entries R
   (each the entry at b and its reads at a).
S2 A slash site of an action at version v is a call (i) whose receiver is a registry word of R at v (the entry at b, a
   read at a), (ii) one of whose arguments reads a member of an entry of T, and (iii) whose result is credited to a
   mapping cell: a write of a mapping family whose value reads that family and holds the call's result term.
S3 One site pair per (edge a->b, action op of b with an action of a of the same selector) with a site at a and a site
   at b; two law ids per pair: L_nat_slash_<contract>_<a>_<b>_<op> and L_sort_slash_<contract>_<a>_<b>_<op>.

gen/<M>/cutover/slash.json: {"slash_version", "versioned": {path, sha256}, "documents": {version: {path, sha256}},
"edge_types", "pairs": [{"edge", "op", "selector", "a": [site], "b": [site], "laws": {"NAT", "SORT"}}], "law_ids"}, a site
{"fn", "receiver", "reads": ["<family>.<member>"], "seq", "src", "credits": [{"family", "seq", "src"}]}. Nothing here names
a target, a law id or an action: every name comes from the documents.
"""
from __future__ import annotations

from . import Ctx, render, sha256_bytes

SLASH_VERSION = "holon-cutover-slash/0.1"


from ..rules.slash import edge_types, pairs_of  # noqa: E402  (S1-S3, the catalog producers' own analysis)


def analysis(ctx: Ctx) -> dict:
    """S1-S3 over the versioned document the sidecar names."""
    vrel = ctx.side["inputs"]["versioned"]
    vdoc = ctx.load(vrel)
    docs = {v: ctx.load(d["path"]) for v, d in vdoc["documents"].items()}
    types = edge_types(vdoc)
    pairs = pairs_of(vdoc, docs)
    return {"slash_version": SLASH_VERSION,
            "versioned": {"path": vrel, "sha256": sha256_bytes(ctx.path(vrel).read_bytes())},
            "documents": {v: {"path": d["path"], "sha256": sha256_bytes(ctx.path(d["path"]).read_bytes())}
                          for v, d in sorted(vdoc["documents"].items())},
            "edge_types": types, "pairs": pairs, "law_ids": sorted(x for p in pairs for x in p["laws"].values())}


def build(ctx: Ctx, log=print) -> dict:
    doc = analysis(ctx)
    log(f"{len(doc['pairs'])} site pairs, {len(doc['law_ids'])} law ids")
    return {ctx.out("analysis"): render(doc)}
