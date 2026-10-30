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


def _label(entry: str) -> str:
    return entry.split(".", 1)[1] if "." in entry else entry


def _contains(term, sub) -> bool:
    if term == sub:
        return True
    if isinstance(term, list):
        return any(_contains(t, sub) for t in term)
    if isinstance(term, dict):
        return any(_contains(t, sub) for t in term.values())
    return False


def _member_reads(term, family: str) -> list:
    out = []
    if isinstance(term, list):
        if (len(term) == 3 and term[0] == "member" and isinstance(term[1], list) and len(term[1]) == 3
                and term[1][0] == "map" and term[1][1] == ["storage", family]):
            out.append(term[2])
        for t in term:
            out.extend(_member_reads(t, family))
    return out


def edge_types(vdoc: dict) -> dict:
    """S1."""
    out: dict = {}
    for t in vdoc.get("in_flight_types") or []:
        e = out.setdefault(t["edge"], {"retyped": [], "reinterpreted": []})
        if t["kind"] == "retyped":
            e["retyped"].append(_label(t["entry"]))
        elif t["kind"] == "reinterpreted":
            e["reinterpreted"].append({"entry": _label(t["entry"]), "reads": sorted(_label(r) for r in t["reads"])})
    for e in out.values():
        e["retyped"].sort()
        e["reinterpreted"].sort(key=lambda r: r["entry"])
    return out


def _credits(action: dict, call: dict) -> list:
    res = ["call", call["fn"], *call["args"]]
    out = []
    for w in action.get("writes") or []:
        path = w.get("path") or []
        if not path or not isinstance(path[0], list) or path[0][0] != "map":
            continue
        if _contains(w.get("value"), res) and _contains(w.get("value"), ["storage", w["family"]]):
            out.append({"family": w["family"], "seq": w.get("seq"), "src": w.get("src")})
    return out


def sites(action: dict, words: list, retyped: list) -> list:
    """S2."""
    out = []
    for c in action.get("calls") or []:
        rec = c.get("receiver")
        if not (isinstance(rec, list) and len(rec) == 2 and rec[0] == "storage" and rec[1] in words):
            continue
        reads = sorted({f"{f}.{m}" for f in retyped for a in c.get("args") or [] for m in _member_reads(a, f)})
        if not reads:
            continue
        cr = _credits(action, c)
        if cr:
            out.append({"fn": c["fn"], "receiver": rec[1], "reads": reads, "seq": c.get("seq"), "src": c.get("src"),
                        "credits": cr})
    return out


def analysis(ctx: Ctx) -> dict:
    """S1-S3 over the versioned document the sidecar names."""
    vrel = ctx.side["inputs"]["versioned"]
    vdoc = ctx.load(vrel)
    contract = vdoc["contract"]["name"]
    types = edge_types(vdoc)
    docs = {v: ctx.load(d["path"]) for v, d in vdoc["documents"].items()}
    pairs = []
    for edge in sorted(types):
        a, b = edge.split("->")
        t = types[edge]
        if not t["retyped"] or not t["reinterpreted"]:
            continue
        words_b = sorted({r["entry"] for r in t["reinterpreted"]})
        words_a = sorted({x for r in t["reinterpreted"] for x in r["reads"]})
        acts_a = {x["name"]: x for x in docs[a]["actions"]}
        for op in sorted(x["name"] for x in docs[b]["actions"]):
            act_b = next(x for x in docs[b]["actions"] if x["name"] == op)
            act_a = acts_a.get(op)
            if act_a is None or act_a.get("selector") != act_b.get("selector"):
                continue
            sa, sb = sites(act_a, words_a, t["retyped"]), sites(act_b, words_b, t["retyped"])
            if sa and sb:
                tag = f"{contract}_{a}_{b}_{op}"
                pairs.append({"edge": edge, "op": op, "selector": act_b.get("selector"), "a": sa, "b": sb,
                              "laws": {"NAT": f"L_nat_slash_{tag}", "SORT": f"L_sort_slash_{tag}"}})
    return {"slash_version": SLASH_VERSION,
            "versioned": {"path": vrel, "sha256": sha256_bytes(ctx.path(vrel).read_bytes())},
            "documents": {v: {"path": d["path"], "sha256": sha256_bytes(ctx.path(d["path"]).read_bytes())}
                          for v, d in sorted(vdoc["documents"].items())},
            "edge_types": types, "pairs": pairs, "law_ids": sorted(x for p in pairs for x in p["laws"].values())}


def build(ctx: Ctx, log=print) -> dict:
    doc = analysis(ctx)
    log(f"{len(doc['pairs'])} site pairs, {len(doc['law_ids'])} law ids")
    return {ctx.out("analysis"): render(doc)}
