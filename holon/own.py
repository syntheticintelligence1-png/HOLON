"""Rule OWN's carrier documents (BUILD_PLAN I35; whitepaper §5.8; the contract is rules W1-W7 of the docstring of
tests_m3/test_own.py).

  python -m holon own --milestone M [--root DIR] [--out DIR] [--check]

reads the OWN sidecar spec/<M>/lib/own.json and its Go document's go.slices section (I18's backing identities) and
writes, for every named type with a view or a lost write, gen/<M>/own/<pkg>_<T>.json (holon-own/0.1). diagram() is the
document's holon-diagram/0.1 diagram (one OWN.<method> edge per method, with the fields it reads and writes), atoms()
its E2 atoms (holon.diagram.evidence.e2 over those access sets) and anchors() what laws over it name.

  W1 methods     "(T).M" or "(*T).M" is a method M of T; its receiver is its first parameter (a value receiver
                 without "*")
  W2 views       a slice result case of a method whose backing is ["of", ["field", ["param", R], F]], R the receiver
  W3 writers     a go.slices.writes entry of a method whose backing is ["of", ["field", ["param", R], G]]
  W5 lost writes a go.slices.lost_writes entry of a value-receiver method, with the methods of T that read the field
                 through their receiver in a slice result case (E2: written via m, read via them); a law iff one does

Exit 0 written (or --check: nothing differs); 1 a difference under --check or an unreadable input; 2 refused (a
sidecar or document missing or malformed). Deterministic: sorted keys and lists, no timestamps.

Nothing here names a target: every type, method and field comes from the sidecar and the document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OWN_VERSION = "holon-own/0.1"
SIDECAR_VERSION = "holon-own-sidecar/0.1"
DIAGRAM_VERSION = "holon-diagram/0.1"
GO_METHOD = re.compile(r"\((\*?)([^()]*)\)\.([A-Za-z_][A-Za-z0-9_]*)")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
METHOD_KEYS = ("params", "results", "span")


class OwnError(ValueError):
    """A sidecar or document missing or malformed: exit 2, nothing written."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def is_own(doc) -> bool:
    return isinstance(doc, dict) and doc.get("own_version") == OWN_VERSION


def sidecar_rel(milestone: str) -> str:
    return f"spec/{milestone}/lib/own.json"


def own_dir(milestone: str, root: Path | str) -> Path:
    return Path(root) / "gen" / milestone / "own"


def committed(milestone: str, root: Path | str) -> list[Path]:
    return sorted(own_dir(milestone, root).glob("*.json"))


def load_sidecar(root: Path | str, milestone: str) -> dict | None:
    p = Path(root) / sidecar_rel(milestone)
    if not p.exists():
        return None
    try:
        sc = json.loads(p.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise OwnError(f"{sidecar_rel(milestone)}: not JSON ({e})") from e
    if not isinstance(sc, dict) or sc.get("own_sidecar_version") != SIDECAR_VERSION or \
            not isinstance(sc.get("document"), str) or not isinstance(sc.get("growth"), dict):
        raise OwnError(f"{sidecar_rel(milestone)}: own_sidecar_version {SIDECAR_VERSION} with a document and growth")
    return sc


# ====================================================================== W1-W5
def method(fid: str):
    """(type, method, pointer receiver) of a method id, else None."""
    m = GO_METHOD.fullmatch(fid)
    return (m.group(2), m.group(3), m.group(1) == "*") if m else None


def type_stem(typ: str) -> str:
    """"<path>/<pkg>.T" -> "<pkg>_T"."""
    pkg, name = typ.rsplit(".", 1)
    stem = f"{pkg.rsplit('/', 1)[-1]}_{name}"
    if not NAME.match(stem):
        raise OwnError(f"the Go type {typ!r} gives the stem {stem!r}, which is not an identifier")
    return stem


def _receiver(go: dict, fid: str) -> str | None:
    ps = (go["functions"].get(fid) or {}).get("params") or []
    return ps[0].get("name") if ps else None


def _field_of(backing, recv: str | None):
    if recv is not None and isinstance(backing, list) and len(backing) == 2 and backing[0] == "of":
        t = backing[1]
        if isinstance(t, list) and len(t) == 3 and t[0] == "field" and t[1] == ["param", recv] and isinstance(t[2], str):
            return t[2]
    return None


def _occurs(t, target) -> bool:
    if t == target:
        return True
    if isinstance(t, list):
        return any(_occurs(x, target) for x in t)
    if isinstance(t, dict):
        return any(_occurs(x, target) for x in t.values())
    return False


def analyse(go: dict) -> dict[str, dict]:
    """{type: {"views", "writers", "lost_writes", "methods": {method: function id}}} over a Go document's go section."""
    out: dict[str, dict] = {}

    def entry(typ: str) -> dict:
        return out.setdefault(typ, {"views": [], "writers": [], "lost_writes": [], "methods": {}})
    for fid in sorted(go.get("functions") or {}):
        mt = method(fid)
        if mt is not None:
            out.setdefault(mt[0], {"views": [], "writers": [], "lost_writes": [], "methods": {}})["methods"][mt[1]] = fid
    sl = go.get("slices") or {}
    for r in sl.get("results") or []:
        mt = method(r.get("function", ""))
        if mt is None:
            continue
        recv = _receiver(go, r["function"])
        for i, c in enumerate(r.get("cases") or []):
            f = _field_of(c.get("backing"), recv)
            if f is not None:
                entry(mt[0])["views"].append({"method": mt[1], "field": f, "result": r.get("result"), "case": i,
                                              "cond": c.get("cond"), "offset": c.get("offset"), "len": c.get("len"),
                                              "cap": c.get("cap")})
    for w in sl.get("writes") or []:
        mt = method(w.get("function", ""))
        if mt is None:
            continue
        f = _field_of(w.get("backing"), _receiver(go, w["function"]))
        if f is not None:
            entry(mt[0])["writers"].append({"method": mt[1], "field": f, "site": w.get("site"), "from": w.get("from"),
                                            "to": w.get("to"), "cond": w.get("cond"), "via": w.get("via")})
    for e in sl.get("lost_writes") or []:
        mt = method(e.get("function", ""))
        fld = e.get("field")
        if mt is None or mt[2] or not (isinstance(fld, list) and len(fld) == 1 and isinstance(fld[0], str)):
            continue
        entry(mt[0])["lost_writes"].append({"method": mt[1], "field": fld[0], "site": e.get("site"),
                                            "value": e.get("value")})
    for typ, t in out.items():
        for lw in t["lost_writes"]:
            readers = set()
            for r in sl.get("results") or []:
                mt = method(r.get("function", ""))
                if mt is None or mt[0] != typ:
                    continue
                target = ["field", ["param", _receiver(go, r["function"])], lw["field"]]
                if any(_occurs([c.get(k) for k in ("cond", "backing", "len", "cap", "offset")], target)
                       for c in r.get("cases") or []):
                    readers.add(mt[1])
            lw["readers"] = sorted(readers)
            lw["law"] = bool(readers)
        t["views"].sort(key=lambda v: (v["method"], v["result"], v["case"]))
        t["writers"].sort(key=lambda w: (w["method"], str(w["site"])))
        t["lost_writes"].sort(key=lambda x: (x["method"], x["field"]))
    return {k: v for k, v in sorted(out.items()) if v["views"] or v["lost_writes"]}


# ====================================================================== documents (W6)
def document(typ: str, t: dict, doc_rel: str, raw: bytes, go: dict) -> dict:
    fns = go["functions"]
    stores = (go.get("slices") or {}).get("stores") or []
    names = {v["method"] for v in t["views"]} | {w["method"] for w in t["writers"]} | \
        {x["method"] for x in t["lost_writes"]} | {r for x in t["lost_writes"] for r in x["readers"]}
    results: dict[str, list] = {}   # every slice result's cases, each with its result index
    for r in (go.get("slices") or {}).get("results") or []:
        results.setdefault(r.get("function"), []).extend(dict(c, result=r.get("result")) for c in r.get("cases") or [])
    methods = {}
    for m in sorted(names):
        fid = t["methods"][m]
        methods[m] = {"source": fid, **{k: fns[fid].get(k) for k in METHOD_KEYS},
                      "receiver": _receiver(go, fid), "pointer": method(fid)[2],
                      "stores": [s for s in stores if s.get("function") == fid],
                      "writes": [w for w in t["writers"] if w["method"] == m],
                      "cases": results.get(fid) or []}
    viewed = sorted({v["field"] for v in t["views"]})
    modelled = viewed if t["views"] else []
    stored = set()
    for m in methods.values():
        for s in m["stores"]:
            tg = s.get("target")
            if isinstance(tg, list) and len(tg) == 3 and tg[0] == "field" and tg[1] == ["param", m["receiver"]]:
                stored.add(tg[2])
    slice_stored = {s for s in stored for m in methods.values() for st in m["stores"]
                    if st.get("target", [None, None, None])[2:] == [s] and isinstance(st.get("value"), list)
                    and st["value"][:1] == ["append"]}
    return {"own_version": OWN_VERSION, "type": typ, "stem": type_stem(typ), "document": doc_rel,
            "document_sha256": hashlib.sha256(raw).hexdigest(), "views": t["views"], "writers": t["writers"],
            "lost_writes": t["lost_writes"], "methods": methods, "modelled": modelled,
            "abstracted": sorted(slice_stored - set(modelled)),
            "constructors": constructors(typ, go)}


def constructors(typ: str, go: dict) -> list[dict]:
    """The functions of the document (not methods) whose one result is *T or T, sorted, each with its go.slices.stores
    entries (W9 reads the constructor's value from them)."""
    out = []
    for fid, f in sorted((go.get("functions") or {}).items()):
        if method(fid) is None and (f.get("results") or []) in ([f"*{typ}"], [typ]):
            out.append({"function": fid, "stores": [s for s in go["slices"]["stores"] if s.get("function") == fid]})
    return out


def documents(root: Path | str, milestone: str) -> list[dict]:
    root = Path(root)
    sc = load_sidecar(root, milestone)
    if sc is None:
        return []
    rel = sc["document"]
    try:
        raw = (root / rel).read_bytes()
        d = json.loads(raw.decode("utf-8"))
    except OSError as e:
        raise OwnError(f"{rel}: unreadable ({type(e).__name__}: {e})") from e
    except (UnicodeDecodeError, ValueError) as e:
        raise OwnError(f"{rel}: not JSON ({e})") from e
    go = d.get("go") if isinstance(d, dict) else None
    if d.get("facts_version") != "holon-facts/0.3" or not isinstance(go, dict) or not isinstance(go.get("functions"),
                                                                                                  dict):
        raise OwnError(f"{rel}: not an extracted Go document")
    return [document(typ, t, rel, raw, go) for typ, t in analyse(go).items()]


def render_all(root: Path | str, milestone: str) -> dict[str, str]:
    return {f"{d['stem']}.json": dumps(d) for d in documents(root, milestone)}


# ====================================================================== diagram, atoms, anchors (W7)
def model_name(doc: dict) -> str:
    return f"own_{doc['stem']}"


def access(doc: dict) -> dict[str, dict]:
    """{method: {"reads": [[field, "*"]], "writes": [[field, "*"]]}}: a method reads the fields its views return and
    the lost-write fields it reads (W5), and writes the fields it writes in place (W3) or loses (W5)."""
    out = {m: {"reads": set(), "writes": set()} for m in doc["methods"]}
    for v in doc["views"]:
        out[v["method"]]["reads"].add(v["field"])
    for w in doc["writers"]:
        out[w["method"]]["writes"].add(w["field"])
    for x in doc["lost_writes"]:
        out[x["method"]]["writes"].add(x["field"])
        for r in x["readers"]:
            out[r]["reads"].add(x["field"])
    return {m: {"reads": [[f, "*"] for f in sorted(a["reads"])], "writes": [[f, "*"] for f in sorted(a["writes"])]}
            for m, a in sorted(out.items())}


def diagram(doc: dict, rel: str, sha: str) -> dict:
    """The carrier document's holon-diagram/0.1 diagram: one carrier per field a method reads or writes, one OWN edge
    per method with its access sets."""
    acc = access(doc)
    fields = sorted({f for a in acc.values() for side in ("reads", "writes") for f, _ in a[side]})
    cars = [{"id": f, "cls": "rep", "base_type": f, "sort_ref": None, "interface": False, "reach": None,
             "key_space": None} for f in fields]
    edges = []
    for m, a in acc.items():
        edges.append({"id": f"OWN.{m}", "kind": "OWN", "model_fn": m, "src": None, "tgt": None, "partial": False,
                      "version": None, "fn_kind": "method", "source": [{"fn": doc["methods"][m]["source"]}],
                      "component": doc["document"], "domain": None, "env": False, "pseudo": False,
                      "principal_class": None, "access": a})
    return {"diagram_version": DIAGRAM_VERSION, "model": model_name(doc), "facts": rel, "facts_sha256": sha,
            "facts_version": OWN_VERSION, "carriers": cars, "edges": sorted(edges, key=lambda e: e["id"]),
            "principal_classes": [], "index_terms": [], "coverage_debt": [],
            "mapped_sections": {"methods": "OWN edges with the fields each reads and writes (rule W7)"}}


def atoms(doc: dict, diag: dict) -> list[dict]:
    """E2 atoms over the methods' access sets (holon.diagram.evidence.e2, no imprecise terms: the access sets are the
    document's)."""
    from .diagram.evidence import e2
    at, unresolved = e2(diag["model"], diag, {})
    if unresolved:
        raise OwnError(f"{diag['model']}: unresolved E2 pairs {unresolved}")
    return sorted(at, key=lambda a: a["id"])


def anchors(diag: dict) -> dict:
    """What laws over the carrier name, in the evidence schema's anchor shape: every OWN edge by its method
    ("actions"), each field's writers and readers ("carriers"), and the edges a trace binder ranges over ("trans":
    every method's, holon.diagram.evidence rule L3); nothing else."""
    cars: dict[str, dict] = {}
    for e in diag["edges"]:
        for side, key in (("writes", "writers"), ("reads", "readers")):
            for f, _ in e["access"][side]:
                cars.setdefault(f, {"writers": [], "readers": []})[key].append(e["id"])
    return {"codec": {}, "domains": {}, "actions": {e["model_fn"]: e["id"] for e in diag["edges"]}, "reasons": {},
            "permissionless": [], "observers": {}, "migrations": {}, "consumers": {},
            "carriers": {f: {k: sorted(v) for k, v in c.items()} for f, c in sorted(cars.items())},
            "trans": sorted(e["id"] for e in diag["edges"]), "sites": {}}


def diagrams(milestone: str, root: Path | str) -> dict[str, dict]:
    out = {}
    root = Path(root)
    for p in committed(milestone, root):
        raw = p.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
        if not is_own(doc):
            raise OwnError(f"{p}: not an OWN carrier document ({OWN_VERSION})")
        rel = p.resolve().relative_to(root.resolve()).as_posix()
        dg = diagram(doc, rel, hashlib.sha256(raw).hexdigest())
        out[dg["model"]] = dg
    return out


# ====================================================================== the CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon own")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root (default: this checkout)")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/own)")
    ap.add_argument("--check", action="store_true", help="exit 1 when a written document would differ")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        texts = render_all(root, a.milestone)
    except OwnError as e:
        print(f"holon own: refused: {e}", file=sys.stderr)
        return 2
    except (OSError, KeyError, TypeError) as e:
        print(f"holon own: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out = Path(a.out).resolve() if a.out else own_dir(a.milestone, root)
    have = {p.name: p.read_text(encoding="utf-8") for p in sorted(out.glob("*.json"))} if out.is_dir() else {}
    if a.check:
        bad = sorted(set(texts) ^ set(have)) + sorted(n for n in texts if n in have and texts[n] != have[n])
        if bad:
            print(f"holon own: differs: {bad}", file=sys.stderr)
            return 1
        print(f"holon own: {len(texts)} carrier documents match")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for name in sorted(set(have) - set(texts)):
        (out / name).unlink()
    for name, text in sorted(texts.items()):
        (out / name).write_text(text, encoding="utf-8")
        print(f"holon own: {name}")
    return 0
