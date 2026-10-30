"""Rules V1-V4 over I63's committed history and timeline (read, never written): the deployed path, its deployments,
the entry edge and the MIG edges, the in-flight types, and every path edge reversed with its downgrade gap.

  path(ctx)            V1: the versions of the timeline's matched upgrades in upgrade order, consecutive repeats
                       collapsed (Refused when an upgrade matches several versions, a step is not a history edge, or the
                       path goes back), the history's versions in no match, the unmatched upgrades
  deployments(ctx)     V1: every matched upgrade keyed by (version, the words of its committed code at the immutable
                       ranges of the matched build)
  edges(ctx)           V2: the entry edge from the placeholder and one MIG edge per consecutive pair of the path
  inflight_types(ctx)  V3: the in-flight entries of the path's edges whose kind is not unchanged
  reverse(ctx)         V4: every path edge a -> b reversed, with I63's H5 diff of layout b to layout a and its H6 in-flight
                       set, and a downgrade gap for every reverse edge whose diff is incompatible

The layout diff and the in-flight set are I63's own (holon.frontends.solidity.history.diff_layouts and reads_of_old).
"""
from __future__ import annotations

from ..frontends.solidity.history import diff_layouts, reads_of_old
from . import PLACEHOLDER, Ctx, Refused


def path(ctx: Ctx) -> dict:
    order = [v["id"] for v in ctx.history["versions"]]
    edges = {(e["from"], e["to"]) for e in ctx.history["edges"]}
    seq = []
    for u in ctx.timeline["upgrades"]:
        vs = sorted({m["version"] for m in u.get("matches") or []})
        if len(vs) > 1:
            raise Refused(f"the upgrade at block {u['block']} matches several versions {vs}")
        if vs and (not seq or seq[-1] != vs[0]):
            seq.append(vs[0])
    for a, b in zip(seq, seq[1:]):
        if (a, b) not in edges:
            raise Refused(f"the path's step {a} -> {b} is not an edge of the history")
        if order.index(b) < order.index(a):
            raise Refused(f"the path's step {a} -> {b} goes back (a downgrade)")
    on = set(seq)
    return {"path": seq, "never_deployed": [v for v in order if v not in on],
            "unmatched": [{"block": c["block"], "implementation": c["implementation"], "reason": c["reason"]}
                          for c in ctx.timeline.get("coverage_debt") or []]}


def deployments(ctx: Ctx) -> list:
    code_dir = ctx.input_path("code_dir")
    out = []
    for u in ctx.timeline["upgrades"]:
        ms = u.get("matches") or []
        if not ms:
            continue
        m = ms[0]
        p = code_dir / f"{u['implementation']}.hex"
        try:
            code = bytes.fromhex(p.read_text().strip().removeprefix("0x"))
        except (OSError, ValueError) as e:
            raise Refused(f"the committed code {p}: {e}") from e
        ranges = ctx.version(m["version"])["code"][m["config"]]["ranges"]
        out.append({"block": u["block"], "implementation": u["implementation"], "version": m["version"],
                    "config": m["config"], "immutables": [int.from_bytes(code[o:o + n], "big") for o, n in ranges]})
    return out


def _reinit(r: dict) -> dict:
    return {"name": r["name"], "version": r["version"]}


def edges(ctx: Ctx, p: list | None = None) -> dict:
    p = path(ctx)["path"] if p is None else p
    by = {(e["from"], e["to"]): e for e in ctx.history["edges"]}
    out = []
    for a, b in zip(p, p[1:]):
        e = by[(a, b)]
        out.append({"from": a, "to": b, "introduced": [_reinit(r) for r in e["introduced"]],
                    "compatible": e["compatible"], "in_flight": e["in_flight"], "in_flight_count": len(e["in_flight"])})
    entry = None
    if p:
        entry = {"from": PLACEHOLDER, "to": p[0], "introduced": [_reinit(r) for r in ctx.version(p[0])["reinitializers"]]}
    return {"entry": entry, "edges": out}


def inflight_types(ctx: Ctx, es: list | None = None) -> list:
    es = edges(ctx)["edges"] if es is None else es
    return [{"edge": f"{e['from']}->{e['to']}", "entry": x["entry"], "kind": x["kind"], "reads": x["reads"]}
            for e in es for x in e["in_flight"] if x["kind"] != "unchanged"]


def _names(rows: list) -> list:
    return [f"{r['contract']}.{r['label']}" for r in rows]


def reverse(ctx: Ctx, es: list | None = None) -> dict:
    es = edges(ctx)["edges"] if es is None else es
    rev, gaps = [], []
    for e in es:
        a, b = e["from"], e["to"]
        la, lb = ctx.version(a)["layout"], ctx.version(b)["layout"]
        d = diff_layouts(lb, la)
        inf = reads_of_old(lb, la, d)
        rev.append({"from": b, "to": a, "compatible": d["compatible"], "diff": d,
                    "in_flight_changed": [x for x in inf if x["kind"] != "unchanged"]})
        if not d["compatible"]:
            gaps.append({"id": f"gap:{ctx.milestone}:downgrade:{b}->{a}", "kind": "downgrade", "from": b, "to": a,
                         "retyped": _names(d["retyped"]),
                         "overlap": [f"{o['contract']}.{o['label']} meets {o['meets']['contract']}.{o['meets']['label']}"
                                     for o in d["overlap"]],
                         "removed": _names(d["removed"]), "added": _names(d["added"]), **ctx.gap_meta("downgrade")})
    return {"reverse": rev, "gaps": gaps}


def basis_fields(ctx: Ctx) -> dict:
    """V1-V4's fields of the versioned document: path, never_deployed, unmatched, deployments, entry, edges,
    in_flight_types, reverse, downgrade_gaps."""
    p = path(ctx)
    e = edges(ctx, p["path"])
    rv = reverse(ctx, e["edges"])
    return {"path": p["path"], "never_deployed": p["never_deployed"], "unmatched": p["unmatched"],
            "deployments": deployments(ctx), "entry": e["entry"], "edges": e["edges"],
            "in_flight_types": inflight_types(ctx, e["edges"]), "reverse": rv["reverse"], "downgrade_gaps": rv["gaps"]}
