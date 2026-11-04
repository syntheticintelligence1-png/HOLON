"""`holon derivation extract` (rules D1-D5 of the contract): the Go frontend's document of the sidecar's stem, extracted
by holon.frontends.go with its own config and analyses unchanged, plus the "consumer" section computed from the same
ssadump run.

The frontend is observed, not changed: its extract() runs as it is, and the ssadump document and the computed sections
it builds are captured on their way (two module functions are wrapped for the duration of the call and restored), so
the document less "consumer" is the frontend's byte for byte (D1).

  consumer = {"consumer_version", "entry", "package", "functions", "join", "environment", "builtins", "invokes",
              "globals", "types", "coverage"}
"""
from __future__ import annotations

from pathlib import Path

from . import Refused, dumps
from . import interp, natives

CONSUMER_VERSION = "holon-derivation-consumer/0.1"
FUNCTION_KEYS = ("package", "pos", "params", "freevars", "results", "blocks")
BLOCK_KEYS = ("index", "preds", "succs", "instrs")


def frontend(config_path: Path, root: Path):
    """(documents, ssadump document, sections over the whole program) of one frontend run."""
    import importlib
    GX = importlib.import_module("holon.frontends.go.extract")   # the module (the package re-exports its function)
    captured: dict = {}
    run0, compute0 = GX.run_ssadump, GX.compute

    def run_ssadump(binary, ws, patterns):
        d = run0(binary, ws, patterns)
        captured["dump"] = d
        return d

    def compute(an):
        s = compute0(an)
        captured["sections"] = s
        return s
    GX.run_ssadump, GX.compute = run_ssadump, compute
    try:
        docs = GX.extract(config_path, None, root)
    except GX.Refused as e:
        raise Refused(f"the Go frontend refused: {e}")
    finally:
        GX.run_ssadump, GX.compute = run0, compute0
    return docs, captured["dump"], captured["sections"]


def _body(f: dict) -> bool:
    return bool(f.get("blocks"))


def _ssa(f: dict) -> dict:
    out = {k: f.get(k) for k in FUNCTION_KEYS if k != "blocks"}
    out["blocks"] = [{k: b.get(k) for k in BLOCK_KEYS} for b in f.get("blocks") or []]
    return out


def _instrs(f: dict):
    for b in f.get("blocks") or []:
        for ins in b.get("instrs") or []:
            yield ins


def _operands(ins: dict):
    for o in ins.get("operands") or []:
        if isinstance(o, dict):
            yield o
    c = ins.get("call")
    if isinstance(c, dict):
        for o in [c.get("value")] + list(c.get("args") or []):
            if isinstance(o, dict):
                yield o


def closure(dump: dict, entry: str, boundary: set) -> list:
    """Rule D2: the functions reachable from entry by static calls (Call, Go, Defer) and closures whose bodies the
    dump holds, the boundary's functions excepted."""
    funcs = {f["id"]: f for f in dump["functions"]}
    if entry not in funcs or not _body(funcs[entry]):
        raise Refused(f"the consumer {entry} has no body in the ssadump run")
    seen, todo = set(), [entry]
    while todo:
        fid = todo.pop()
        if fid in seen:
            continue
        seen.add(fid)
        for ins in _instrs(funcs[fid]):
            c = ins.get("call")
            if c and c.get("mode") == "static":
                g = c.get("callee")
                if g in funcs and _body(funcs[g]) and g not in boundary:
                    todo.append(g)
            if ins.get("op") == "MakeClosure" and ins.get("fn") in funcs:
                todo.append(ins["fn"])
    return sorted(seen)


def _types_of(ins: dict, out: set) -> None:
    for k in ("type", "asserted"):
        if ins.get(k):
            out.add(ins[k])
    for o in _operands(ins):
        if "const" in o and isinstance(o["const"], dict) and o["const"].get("type"):
            out.add(o["const"]["type"])
    c = ins.get("call")
    if isinstance(c, dict) and c.get("signature"):
        out.add(c["signature"])


def type_closure(table: dict, keys: set) -> dict:
    todo, seen = list(keys), set()
    while todo:
        k = todo.pop()
        if not k or k in seen or k not in table:
            continue
        seen.add(k)
        t = table[k]
        for f in ("underlying", "elem", "key"):
            if t.get(f):
                todo.append(t[f])
        for f in t.get("fields") or []:
            todo.append(f.get("type"))
        for f in ("elems", "params", "results"):
            todo.extend(t.get(f) or [])
    return {k: table[k] for k in sorted(seen)}


def section(side: dict, dump: dict, sections: dict) -> dict:
    """Rules D2-D4: the consumer section."""
    ex = side["extract"]
    entry, join_fid = ex["consumer"], ex["join"]
    declared = ex.get("environment") or {}
    funcs = {f["id"]: f for f in dump["functions"]}
    fids = closure(dump, entry, set(declared))
    if join_fid not in funcs or not _body(funcs[join_fid]):
        raise Refused(f"the join function {join_fid} has no body in the ssadump run")
    env: dict = {}
    builtins, invokes, globals_, unacc = set(), [], {}, []
    n_ins = 0
    tkeys: set = set()
    for fid in fids:
        f = funcs[fid]
        for v in (f.get("params") or []) + (f.get("freevars") or []):
            tkeys.add(v.get("type"))
        tkeys.update(f.get("results") or [])
        for ins in _instrs(f):
            n_ins += 1
            _types_of(ins, tkeys)
            op = ins.get("op")
            if op not in interp.SUPPORTED_OPS:
                unacc.append({"function": fid, "pos": ins.get("pos") or "", "what": f"op {op}"})
            c = ins.get("call")
            if isinstance(c, dict):
                mode = c.get("mode")
                if mode == "static" and c.get("callee") not in fids:
                    env.setdefault(c["callee"], set()).add(ins.get("pos") or "")
                elif mode == "builtin":
                    builtins.add(c.get("callee"))
                    if c.get("callee") not in natives.BUILTINS:
                        unacc.append({"function": fid, "pos": ins.get("pos") or "",
                                      "what": f"builtin {c.get('callee')}"})
                elif mode == "invoke":
                    invokes.append([fid, c.get("method"), ins.get("pos") or ""])
                elif mode == "dynamic":
                    unacc.append({"function": fid, "pos": ins.get("pos") or "", "what": "dynamic call"})
            for o in _operands(ins):
                if "global" in o:
                    globals_.setdefault(o["global"], None)
    environment = []
    for g, sites in sorted(env.items()):
        if g in declared:
            kind = declared[g]["kind"]
        elif g in natives.FUNCS:
            kind = "native"
        else:
            kind = "unaccounted"
            unacc.append({"function": g, "pos": "", "what": "a callee of no kind"})
        environment.append({"function": g, "kind": kind, "sites": sorted(sites)})
    init = {g["global"]: g for g in sections.get("globals") or []}
    glist = []
    for g in sorted(globals_):
        if g in init and init[g].get("value") is not None:
            glist.append({"global": g, "kind": "initialized", "value": init[g]["value"]})
        elif g in natives.GLOBALS:
            glist.append({"global": g, "kind": "native", "value": None})
        else:
            glist.append({"global": g, "kind": "unaccounted", "value": None})
            unacc.append({"function": g, "pos": "", "what": "a global of no kind"})
    for ins in _instrs(funcs[join_fid]):
        _types_of(ins, tkeys)
    pkg_path = funcs[entry].get("package")
    pk = next((p for p in dump["packages"] if p["path"] == pkg_path), None)
    if pk is None:
        raise Refused(f"the consumer's package {pkg_path} is not in the ssadump run")
    return {
        "consumer_version": CONSUMER_VERSION,
        "entry": entry,
        "package": {"path": pk["path"], "name": pk["name"], "dir": pk["dir"]},
        "functions": {fid: _ssa(funcs[fid]) for fid in fids},
        "join": {"function": join_fid, "ssa": _ssa(funcs[join_fid])},
        "environment": environment,
        "builtins": sorted(builtins),
        "invokes": sorted(invokes),
        "globals": glist,
        "types": type_closure(dump.get("types") or {}, {k for k in tkeys if k}),
        "coverage": {"functions": len(fids), "instructions": n_ins,
                     "unaccounted": sorted(unacc, key=lambda u: (u["function"], u["pos"], u["what"]))},
    }


def document(root: Path, side: dict) -> dict:
    ex = side["extract"]
    docs, dump, sections = frontend(root / ex["frontend_config"], root)
    if ex["document"] not in docs:
        raise Refused(f"{ex['frontend_config']} has no document {ex['document']}")
    doc = dict(docs[ex["document"]])
    doc["consumer"] = section(side, dump, sections)
    return doc


def run(root: Path, side: dict, side_rel: str) -> dict:
    from ..frontends.go.extract import render
    doc = document(root, side)
    text = render(doc)
    assert text == dumps(doc)
    return {side["extract"]["output"]: text}
