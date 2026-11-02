"""Go-op components (BUILD_PLAN row I67; whitepaper §5.1 PAR-totality and A2; the contract is rules Y3 and Y4 of the
docstring of tests_m3/test_go_loop.py).

A Go-op component is named in the sidecar spec/<M>/lib/go_ops.json with one interface carrier: a Go type whose values
the environment supplies (R^ext). It holds every function of the sidecar's Go document whose one parameter has that
type and whose last result is error (an op). `holon codecs --milestone M` writes each component's holon-goops/0.1
document to gen/<M>/goops/<component>.json (holon.diagram.linked.main); document() builds it, diagram() its
holon-diagram/0.1 diagram (one CODEC edge per op, the carrier an interface carrier whose domains are the ops' ok_<op>),
atoms() its E6 atoms and anchors() what laws over it name. Rule PAR derives over the diagram with its producers as they
are (holon.rules._committed_par_inputs); holon.gen.goloop models and decides the laws (holon.codecrun).

Nothing here names a target: every name comes from the sidecar and the document.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .linked import NAME, LinkedError, SidecarError, dumps

GOOPS_VERSION = "holon-goops/0.1"
SIDECAR_VERSION = "holon-go-ops/0.1"
DIAGRAM_VERSION = "holon-diagram/0.1"
GO_METHOD = re.compile(r"\((\*?)(.*)\)\.([^.()]+)")
OP_KEYS = ("params", "results", "span", "loop_bodies", "paths", "paths_reason", "sites")


def is_goops(doc) -> bool:
    return isinstance(doc, dict) and doc.get("goops_version") == GOOPS_VERSION


def sidecar_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/go_ops.json"


def goops_dir(milestone: str, root: Path | str) -> Path:
    return Path(root) / "gen" / milestone / "goops"


def committed(milestone: str, root: Path | str) -> list[Path]:
    """The Go-op documents of a milestone (gen/<M>/goops/*.json), sorted."""
    return sorted(goops_dir(milestone, root).glob("*.json"))


# ====================================================================== names (Y3)
def model_name(fid: str) -> str:
    """"<path>/<pkg>.F" -> "<pkg>_F"; "(<path>/<pkg>.T).M" and "(*<path>/<pkg>.T).M" -> "<pkg>_T_M"."""
    m = GO_METHOD.fullmatch(fid)
    if m:
        pkg_path, typ = m.group(2).rsplit(".", 1)
        name = f"{pkg_path.rsplit('/', 1)[-1]}_{typ}_{m.group(3)}"
    else:
        pkg_path, fn = fid.rsplit(".", 1)
        name = f"{pkg_path.rsplit('/', 1)[-1]}_{fn}"
    if not NAME.match(name):
        raise LinkedError(f"Go function {fid!r} gives the model name {name!r}, which is not an identifier")
    return name


def carrier_id(go_type: str) -> str:
    """A Go type without its leading "*" and its package path."""
    name = go_type.lstrip("*").rsplit(".", 1)[-1]
    if not NAME.match(name):
        raise LinkedError(f"Go type {go_type!r} gives the carrier id {name!r}, which is not an identifier")
    return name


def _type_word(t: str) -> str:
    word = ""
    while t.startswith(("[]", "*")):
        word += "Slice" if t.startswith("[]") else "Ptr"
        t = t[2:] if t.startswith("[]") else t[1:]
    last = t.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
    return word + last[:1].upper() + last[1:]


def result_carrier_id(results: list[str]) -> str:
    """"R_" and the result types, each an identifier ([] Slice, * Ptr, the last name segment capitalized)."""
    name = "R_" + "_".join(_type_word(t) for t in results)
    if not NAME.match(name):
        raise LinkedError(f"the results {results} give the carrier id {name!r}, which is not an identifier")
    return name


# ====================================================================== documents (Y3)
def load_sidecar(root: Path, milestone: str) -> tuple[dict | None, bytes | None]:
    p = Path(root) / sidecar_rel(milestone)
    if not p.exists():
        return None, None
    raw = p.read_bytes()
    try:
        sc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise SidecarError(f"{sidecar_rel(milestone)}: not JSON ({e})") from e
    if not isinstance(sc, dict) or sc.get("go_ops_version") != SIDECAR_VERSION:
        raise SidecarError(f"{sidecar_rel(milestone)}: go_ops_version is not {SIDECAR_VERSION}")
    comps = sc.get("components")
    if not isinstance(sc.get("document"), str) or not isinstance(comps, dict) or not comps:
        raise SidecarError(f"{sidecar_rel(milestone)}: needs a document and components")
    for name, c in comps.items():
        if not NAME.match(name) or not isinstance(c, dict) or not isinstance(c.get("carrier"), str) \
                or not isinstance(c.get("reach"), str):
            raise SidecarError(f"{sidecar_rel(milestone)}: component {name!r} needs a carrier and a reach")
    return sc, raw


def document(name: str, comp: dict, doc_rel: str, raw: bytes, go: dict) -> dict:
    """The holon-goops/0.1 document of one component."""
    fns = (go.get("go") or {}).get("functions")
    if go.get("facts_version") != "holon-facts/0.3" or not isinstance(fns, dict):
        raise SidecarError(f"{doc_rel}: not an extracted Go document")
    ops, results = {}, {}
    for fid, f in sorted(fns.items()):
        ps, rs = f.get("params") or [], f.get("results") or []
        if len(ps) != 1 or ps[0].get("type") != comp["carrier"] or not rs or rs[-1] != "error":
            continue
        mn = model_name(fid)
        if mn in ops:
            raise LinkedError(f"component {name}: two ops named {mn}")
        ops[mn] = {"source": fid, **{k: f.get(k) for k in OP_KEYS}}
        results[result_carrier_id(rs)] = list(rs)
    if not ops:
        raise LinkedError(f"component {name}: no function of {doc_rel} takes one {comp['carrier']}")
    cid = carrier_id(comp["carrier"])
    if cid in results:
        raise LinkedError(f"component {name}: carrier id {cid} names two carriers")
    return {"goops_version": GOOPS_VERSION, "component": name, "document": doc_rel,
            "document_sha256": hashlib.sha256(raw).hexdigest(),
            "carrier": {"id": cid, "type": comp["carrier"], "reach": comp["reach"]},
            "ops": ops, "results": dict(sorted(results.items()))}


def documents(root: Path | str, milestone: str) -> list[dict]:
    """The Go-op document of every component of the milestone's sidecar (none without one), sorted by name."""
    root = Path(root)
    sc, _ = load_sidecar(root, milestone)
    if sc is None:
        return []
    rel = sc["document"]
    p = root / rel
    try:
        raw = p.read_bytes()
        go = json.loads(raw.decode("utf-8"))
    except OSError as e:
        raise SidecarError(f"{rel}: unreadable ({type(e).__name__}: {e})") from e
    except (UnicodeDecodeError, ValueError) as e:
        raise SidecarError(f"{rel}: not JSON ({e})") from e
    return [document(name, c, rel, raw, go) for name, c in sorted(sc["components"].items())]


def render_all(root: Path | str, milestone: str) -> dict[str, str]:
    """{file name: text} of every Go-op document holon codecs writes, and (I90, rule C1 of tests_m3/test_go_counts.py)
    every count document of holon.diagram.gocount, which shares the directory: the Go-level components."""
    from . import gocount as GC
    out = {f"{d['component']}.json": dumps(d) for d in documents(root, milestone)}
    for name, text in GC.render_all(root, milestone).items():
        if name in out:
            raise LinkedError(f"a Go-op component and a count component share the name {name[:-5]}")
        out[name] = text
    return dict(sorted(out.items()))


# ====================================================================== diagram (Y4)
def diagram(doc: dict, rel: str, sha: str) -> dict:
    """The component's holon-diagram/0.1 diagram: the interface carrier (one domain ok_<op> per op), one carrier per
    result tuple, one CODEC edge per op (partial false: the error result is part of the op's value; its domain is where
    it does not panic)."""
    car = doc["carrier"]["id"]
    ops = doc["ops"]
    cars = [{"id": car, "cls": "rep", "base_type": car, "sort_ref": None, "interface": True, "reach": "external",
             "domains": sorted(f"ok_{op}" for op in ops), "key_space": "byte"}]
    for rid in doc["results"]:
        cars.append({"id": rid, "cls": "rep", "base_type": rid, "sort_ref": None, "interface": False, "reach": None})
    edges = []
    for op, o in sorted(ops.items()):
        edges.append({"id": f"CODEC.{op}", "kind": "CODEC", "model_fn": op, "src": car,
                      "tgt": result_carrier_id(o["results"]), "partial": False, "version": None, "fn_kind": "op",
                      "source": [{"fn": o["source"]}], "component": doc["document"], "domain": f"ok_{op}",
                      "env": False, "pseudo": False, "principal_class": None, "access": {"reads": [], "writes": []}})
    return {"diagram_version": DIAGRAM_VERSION, "model": doc["component"], "facts": rel, "facts_sha256": sha,
            "facts_version": GOOPS_VERSION, "carriers": sorted(cars, key=lambda c: c["id"]),
            "edges": sorted(edges, key=lambda e: e["id"]), "principal_classes": [], "index_terms": [],
            "coverage_debt": [],
            "mapped_sections": {"carrier": "the interface carrier, its domains the ops' ok_<op> (rule Y4)",
                                "ops": "CODEC edges from the carrier to their result carriers (rule Y4)"}}


def atoms(doc: dict, diag: dict, lexicon) -> list[dict]:
    """E6 atoms over the component (I14's lexicon over the edges' source names); an op has no layout (no E1, E2)."""
    from .evidence import e6
    return sorted(e6(doc["component"], diag, lexicon), key=lambda a: a["id"])


def anchors(diag: dict) -> dict:
    """What laws over the component name: its CODEC edges by model function and the carrier's domain predicates with
    the edges whose domain each is (as holon.diagram.linked.anchors gives them for a linked component)."""
    from .linked import anchors as linked_anchors
    return linked_anchors(diag)


def diagrams(milestone: str, root: Path | str) -> dict[str, dict]:
    """{model: diagram} of every committed Go-op document of the milestone, and (I90, rule C2 of
    tests_m3/test_go_counts.py) of every committed count document there (holon.diagram.gocount)."""
    from . import gocount as GC
    out = {}
    root = Path(root)
    for p in committed(milestone, root):
        raw = p.read_bytes()
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise LinkedError(f"{p}: not JSON ({e})") from e
        rel = p.resolve().relative_to(root.resolve()).as_posix()
        if GC.is_gocount(doc):
            out[doc["component"]] = GC.diagram(doc, rel, hashlib.sha256(raw).hexdigest())
            continue
        if not is_goops(doc):
            raise LinkedError(f"{p}: not a Go-op document ({GOOPS_VERSION}) or a count document ({GC.GOCOUNT_VERSION})")
        out[doc["component"]] = diagram(doc, rel, hashlib.sha256(raw).hexdigest())
    return out
