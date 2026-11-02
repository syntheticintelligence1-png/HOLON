"""Go count components (BUILD_PLAN row I90 = I38b; whitepaper §7.6 width obligations, §5.1 PAR; the contract is rules C1
and C2 of the docstring of tests_m3/test_go_counts.py).

A count component is named in the sidecar spec/<M>/lib/go_counts.json with one carrier: a Go type whose values the
environment supplies. Its channels are the stores of the Go document's pointer-receiver methods that record the length
of one parameter of that type in a field of the receiver:

  wrap  f = f + uintW(len(P))                 the length realized in W bits (W = 8, 16, 32)
  item  f = append(f, G(P[i])) in a range     one fixed-width item per element (G a document primitive of a width)
        loop over P

`holon codecs --milestone M` writes each component's holon-gocount/0.1 document to gen/<M>/goops/<component>.json,
beside the Go-op documents (holon.diagram.goops renders, lists and diagrams both kinds by their version key);
document() builds it, diagram() its holon-diagram/0.1 diagram (one CODEC edge per channel, from the carrier to its
length count, citing its function), atoms() its evidence atoms (none) and anchors() what laws over it name. Rule PAR
derives over the diagram with its producers as they are; holon.gen.gocount models and decides the laws
(holon.codecrun).

Nothing here names a target: every name comes from the sidecar, the document and the document's extraction config.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .linked import NAME, LinkedError, SidecarError, dumps

GOCOUNT_VERSION = "holon-gocount/0.1"
SIDECAR_VERSION = "holon-go-counts/0.1"
DIAGRAM_VERSION = "holon-diagram/0.1"
GO_METHOD = re.compile(r"\((\*?)(.*)\)\.([^.()]+)")
WRAP_WIDTHS = {"uint8": 8, "uint16": 16, "uint32": 32}
ITEM_KINDS = ("array_bytes", "to_array")


def is_gocount(doc) -> bool:
    return isinstance(doc, dict) and doc.get("gocount_version") == GOCOUNT_VERSION


def sidecar_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/go_counts.json"


# ====================================================================== names (C1)
def model_name(fid: str) -> str:
    """I67's model name: "(*<path>/<pkg>.T).M" -> "<pkg>_T_M"; "<path>/<pkg>.F" -> "<pkg>_F"."""
    from .goops import model_name as go_model_name
    return go_model_name(fid)


def type_word(t: str) -> str:
    """A Go type as an identifier: every leading "[]" as Slice and "*" as Ptr, then the last name segment with its first
    letter upper-cased (I67's result-carrier words)."""
    word = ""
    while t.startswith(("[]", "*")):
        word += "Slice" if t.startswith("[]") else "Ptr"
        t = t[2:] if t.startswith("[]") else t[1:]
    last = t.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
    out = word + last[:1].upper() + last[1:]
    if not NAME.match(out):
        raise LinkedError(f"Go type {t!r} gives the carrier id {out!r}, which is not an identifier")
    return out


def count_id(carrier: str) -> str:
    return f"Len_{carrier}"


# ====================================================================== channels (C1)
def _mentions_rangeindex(t) -> bool:
    if isinstance(t, list):
        if len(t) == 3 and t[0] == "var" and t[2] == "rangeindex":
            return True
        return any(_mentions_rangeindex(x) for x in t)
    return False


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def channel(store: dict, recv: str, param: str, loops: list, prims: dict):
    """(kind, width, field) when one store fact is a count channel of the parameter param of a method whose receiver
    is recv (loops: the method's go.loops entries; prims: the extraction config's primitives), else None."""
    tgt, val = store.get("target"), store.get("value")
    if not (isinstance(tgt, list) and len(tgt) == 3 and tgt[0] == "field" and tgt[1] == ["param", recv]
            and isinstance(tgt[2], str) and NAME.match(tgt[2])):
        return None
    f = tgt[2]
    me = ["field", ["param", recv], f]
    if (isinstance(val, list) and len(val) == 4 and val[0] == "op" and val[1] == "+" and val[2] == me
            and isinstance(val[3], list) and len(val[3]) == 3 and val[3][0] == "convert"
            and val[3][1] in WRAP_WIDTHS and val[3][2] == ["len", ["param", param]]):
        return "wrap", WRAP_WIDTHS[val[3][1]], f
    if not (isinstance(val, list) and len(val) == 3 and val[0] == "append" and val[1] == me):
        return None
    x = val[2]
    if not (isinstance(x, list) and len(x) == 3 and x[0] == "call" and isinstance(x[1], str)
            and isinstance(x[2], list) and len(x[2]) == 1):
        return None
    prim = prims.get(x[1]) if isinstance(prims.get(x[1]), dict) else {}
    k = prim.get("width")
    if prim.get("kind") not in ITEM_KINDS or not _int(k) or k < 1:
        return None
    arg = x[2][0]
    if not (isinstance(arg, list) and len(arg) == 3 and arg[0] == "index" and arg[1] == ["param", param]
            and _mentions_rangeindex(arg[2])):
        return None
    ranges = [lp for lp in loops if lp.get("kind") == "range"]
    if len(ranges) != 1:
        return None
    lp = ranges[0]
    if (lp.get("limit"), lp.get("init"), lp.get("step"), lp.get("exits")) != (["len", ["param", param]],
                                                                              ["const", 0], 1, []):
        return None
    return "item", k, f


def _config(go: dict, root: Path) -> dict:
    rel = ((go.get("extraction") or {}).get("config") or {}).get("path")
    if not isinstance(rel, str):
        raise SidecarError("the Go document names no extraction config")
    try:
        return json.loads((Path(root) / rel).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise SidecarError(f"{rel}: unreadable ({type(e).__name__}: {e})") from e


def document(name: str, comp: dict, doc_rel: str, raw: bytes, go: dict, config: dict) -> dict:
    """The holon-gocount/0.1 document of one component (rule C1)."""
    g = go.get("go") or {}
    fns, stores, loops = g.get("functions"), (g.get("slices") or {}).get("stores"), g.get("loops")
    if go.get("facts_version") != "holon-facts/0.3" or not isinstance(fns, dict) or not isinstance(stores, list) \
            or not isinstance(loops, list):
        raise SidecarError(f"{doc_rel}: not an extracted Go document with store and loop facts")
    prims = config.get("primitives") or {}
    chans = {}
    for fid, f in sorted(fns.items()):
        m = GO_METHOD.fullmatch(fid)
        ps = f.get("params") or []
        hits = [p.get("name") for p in ps if isinstance(p, dict) and p.get("type") == comp["carrier"]]
        if not m or m.group(1) != "*" or not ps or not hits:
            continue
        if len(hits) > 1:
            raise LinkedError(f"component {name}: {fid} has two parameters of the carrier's type")
        recv, param = ps[0].get("name"), hits[0]
        mine = [lp for lp in loops if isinstance(lp, dict) and lp.get("function") == fid]
        for s in stores:
            if not isinstance(s, dict) or s.get("function") != fid:
                continue
            ch = channel(s, recv, param, mine, prims)
            if ch is None:
                continue
            kind, width, field = ch
            cname = f"{model_name(fid)}_{field}"
            if not NAME.match(cname):
                raise LinkedError(f"component {name}: channel name {cname!r} is not an identifier")
            if cname in chans:
                raise LinkedError(f"component {name}: two channels named {cname}")
            chans[cname] = {"source": fid, "params": ps, "param": param, "receiver": recv, "field": field,
                            "kind": kind, "width": width, "site": s.get("site"), "store": s.get("value")}
    if not chans:
        raise LinkedError(f"component {name}: no count channel of a parameter of type {comp['carrier']} in {doc_rel}")
    cid = type_word(comp["carrier"])
    return {"gocount_version": GOCOUNT_VERSION, "component": name, "document": doc_rel,
            "document_sha256": hashlib.sha256(raw).hexdigest(),
            "carrier": {"id": cid, "type": comp["carrier"], "reach": comp["reach"]}, "count": count_id(cid),
            "channels": dict(sorted(chans.items()))}


def load_sidecar(root: Path, milestone: str) -> tuple[dict | None, bytes | None]:
    p = Path(root) / sidecar_rel(milestone)
    if not p.exists():
        return None, None
    raw = p.read_bytes()
    try:
        sc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise SidecarError(f"{sidecar_rel(milestone)}: not JSON ({e})") from e
    if not isinstance(sc, dict) or sc.get("go_counts_version") != SIDECAR_VERSION:
        raise SidecarError(f"{sidecar_rel(milestone)}: go_counts_version is not {SIDECAR_VERSION}")
    comps = sc.get("components")
    if not isinstance(sc.get("document"), str) or not isinstance(comps, dict) or not comps:
        raise SidecarError(f"{sidecar_rel(milestone)}: needs a document and components")
    for name, c in comps.items():
        if not NAME.match(name) or not isinstance(c, dict) or not isinstance(c.get("carrier"), str) \
                or not isinstance(c.get("reach"), str):
            raise SidecarError(f"{sidecar_rel(milestone)}: component {name!r} needs a carrier and a reach")
    return sc, raw


def documents(root: Path | str, milestone: str) -> list[dict]:
    """The count document of every component of the milestone's sidecar (none without one), sorted by name."""
    root = Path(root)
    sc, _ = load_sidecar(root, milestone)
    if sc is None:
        return []
    rel = sc["document"]
    try:
        raw = (root / rel).read_bytes()
        go = json.loads(raw.decode("utf-8"))
    except OSError as e:
        raise SidecarError(f"{rel}: unreadable ({type(e).__name__}: {e})") from e
    except (UnicodeDecodeError, ValueError) as e:
        raise SidecarError(f"{rel}: not JSON ({e})") from e
    cfg = _config(go, root)
    return [document(name, c, rel, raw, go, cfg) for name, c in sorted(sc["components"].items())]


def render_all(root: Path | str, milestone: str) -> dict[str, str]:
    """{file name: text} of every count document holon codecs writes."""
    return {f"{d['component']}.json": dumps(d) for d in documents(root, milestone)}


# ====================================================================== diagram (C2)
def diagram(doc: dict, rel: str, sha: str) -> dict:
    """The component's holon-diagram/0.1 diagram: the carrier (no domain: a channel is total and has no error result),
    its length count, and one CODEC edge per channel from the carrier to the count, citing its function (rule C2)."""
    car, cnt = doc["carrier"]["id"], doc["count"]
    cars = [{"id": car, "cls": "rep", "base_type": car, "sort_ref": None, "interface": False, "reach": "external"},
            {"id": cnt, "cls": "rep", "base_type": cnt, "sort_ref": None, "interface": False, "reach": None}]
    edges = []
    for name, c in sorted(doc["channels"].items()):
        edges.append({"id": f"CODEC.{name}", "kind": "CODEC", "model_fn": name, "src": car, "tgt": cnt,
                      "partial": False, "version": None, "fn_kind": "count", "source": [{"fn": c["source"]}],
                      "component": doc["document"], "env": False, "pseudo": False, "principal_class": None,
                      "access": {"reads": [], "writes": []}})
    return {"diagram_version": DIAGRAM_VERSION, "model": doc["component"], "facts": rel, "facts_sha256": sha,
            "facts_version": GOCOUNT_VERSION, "carriers": sorted(cars, key=lambda c: c["id"]),
            "edges": sorted(edges, key=lambda e: e["id"]), "principal_classes": [], "index_terms": [],
            "coverage_debt": [],
            "mapped_sections": {"carrier": "the carrier and its length count (rule C2)",
                                "channels": "CODEC edges from the carrier to its length count (rule C2)"}}


def atoms(doc: dict, diag: dict, lexicon) -> list[dict]:
    """No atom (rule C2): a channel has no layout and no machine, and two channels of one function are related by P3's
    basis, not by name tokens."""
    return []


def anchors(diag: dict) -> dict:
    """What laws over the component name: its CODEC edges by model function (holon.diagram.linked.anchors)."""
    from .linked import anchors as linked_anchors
    return linked_anchors(diag)
