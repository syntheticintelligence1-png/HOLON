"""I24 instruments for the extracted side, fixed at the I24 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_derive_par.py: rules X0-X9 (the linked codec layer over the adopted
extracted documents), rules P1-P12 applied to its diagrams, and rules B1-B5 (the back-test across documents). This
module writes those rules out a second time, independently of holon/, so that the tests can decide what holon must
write:

- components(root): the linked codec components (rule X1) of the M3 adoption (spec/M3/lib/derive_extracted.json) and
  link roles (spec/M3/lib/link.json): carriers, functions, layouts, versions (rules X2-X5);
- diagram(comp): the holon-diagram/0.1 view of a component (rule X6), and cycle_basis over it (rule P8);
- atoms(comp, diag): the E1, E2 and E6 atoms over it (rule X7);
- expected(comp, diag, atoms): the PAR basis elements, laws and reasons (rules X8 and P0-P12 over the component);
- decide(comp, law): the outcome the compiled component model must give (by direct evaluation here);
- backtest_map(root) and pair(old, new, mu): the back-test name map and the pairing rule (rules B1-B3).

Inputs only: the adopted extracted documents, the two M3 sidecars, the M0 hand fact document (back-test map only:
rule B1 reads it, never the derivation) and the committed laws/M0. Nothing here imports holon/.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from tests_m3 import _i24 as P
from tests_m3._m3 import ROOT, canonical_json, load_json

ADOPTION = Path("spec") / "M3" / "lib" / "derive_extracted.json"
LINK = Path("spec") / "M3" / "lib" / "link.json"
BACKTEST_MAP = Path("spec") / "M3" / "lib" / "backtest_map.json"
FACTS03 = "holon-facts/0.3"
LINKED_VERSION = "holon-linked/0.1"
UNDEF = 57005
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class XError(ValueError):
    """A construct the linked codec layer refuses (holon exits 3, naming it)."""


def _load(root: Path, rel: str) -> dict:
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ names (rule X2)
def go_name(fid: str) -> str:
    """X2: "(pkg.T).M" and "(*pkg.T).M" -> "T_M"; "pkg.F" -> "F" (T, F: the text after the last ".")."""
    m = re.fullmatch(r"\((\*?)(.*)\)\.([^.()]+)", fid)
    name = f"{m.group(2).rsplit('.', 1)[-1]}_{m.group(3)}" if m else fid.rsplit(".", 1)[-1]
    if not NAME.match(name):
        raise XError(f"Go function {fid!r} gives the name {name!r}, which is not an identifier")
    return name


def go_type(t: str) -> str:
    """X2: a Go type string without its leading "*" and its package path."""
    name = t.lstrip("*").rsplit(".", 1)[-1]
    if not NAME.match(name):
        raise XError(f"Go type {t!r} gives the carrier id {name!r}, which is not an identifier")
    return name


def base_type(t: str) -> str:
    """The carrier of a Solidity function's declared type: Maybe<T> -> T."""
    m = re.fullmatch(r"Maybe<(.+)>", t)
    return m.group(1) if m else t


def label(vs: list[int] | None) -> str | None:
    """A version set as a diagram label: maximal runs "a..b" (two or more) or "a", joined by ","."""
    if vs is None:
        return None
    vs = sorted(set(vs))
    out, i = [], 0
    while i < len(vs):
        j = i
        while j + 1 < len(vs) and vs[j + 1] == vs[j] + 1:
            j += 1
        out.append(f"{vs[i]}..{vs[j]}" if j > i else f"{vs[i]}")
        i = j + 1
    return ",".join(out)


# ------------------------------------------------------------------ condition evaluation (rules X4, X5)
def _ev_sol(e, env: dict):
    """A Solidity-document condition (I17 DSL) under env {name: int, ("len", x): int, ("byte", x, k): int}; None when
    it mentions anything env does not give."""
    if isinstance(e, bool):
        return int(e)
    if isinstance(e, int):
        return e
    if isinstance(e, str):
        return env.get(e)
    op = e[0]
    if op == "len" and len(e) == 2:
        return env.get(("len", e[1]))
    if op == "byte" and len(e) == 3:
        return env.get(("byte", e[1], e[2]))
    if op == "!":
        x = _ev_sol(e[1], env)
        return None if x is None else int(not x)
    if op in ("||", "&&"):
        xs = [_ev_sol(a, env) for a in e[1:]]
        if op == "||":
            if any(x for x in xs if x is not None):
                return 1
            return None if None in xs else 0
        if any(x == 0 for x in xs):
            return 0
        return None if None in xs else 1
    a, b = (_ev_sol(x, env) for x in e[1:3])
    if a is None or b is None:
        return None
    return int({"<=": a <= b, "<": a < b, ">=": a >= b, ">": a > b, "==": a == b, "!=": a != b}[op])


def _ev_go(e, env: dict, param: str):
    """A Go path atom or term (I18) under env {("len",): int, ("index", k): int}; None when unknown."""
    if not isinstance(e, list):
        return None
    tag = e[0]
    if tag == "const":
        return e[1]
    if tag == "len" and e[1] == ["param", param]:
        return env.get(("len",))
    if tag == "index" and e[1] == ["param", param] and e[2][0] == "const":
        return env.get(("index", e[2][1]))
    if tag in ("==", "!=", "<", "<=", ">", ">="):
        a, b = _ev_go(e[1], env, param), _ev_go(e[2], env, param)
        if a is None or b is None:
            return None
        return int({"<=": a <= b, "<": a < b, ">=": a >= b, ">": a > b, "==": a == b, "!=": a != b}[tag])
    return None


def _mentions(e, pred) -> bool:
    if pred(e):
        return True
    return isinstance(e, list) and any(_mentions(x, pred) for x in e)


# ------------------------------------------------------------------ the component (rules X1-X5)
def adoption(root: Path = ROOT, rel: str = ADOPTION.as_posix()) -> dict:
    return _load(root, rel)


def link_roles(root: Path = ROOT, rel: str = LINK.as_posix()) -> dict:
    return _load(root, rel)["roles"]


def _sol_cells(op: dict) -> list[list]:
    cells: list[list] = []
    for s in op["src"]:
        if "field" in s:
            cells += [["field", s["field"], k] for k in range(s["from"], s["from"] + s["len"])]
        elif "zeros" in s:
            cells += [["const", 0]] * s["zeros"]
        elif "const" in s:
            cells += [["const", c] for c in (s["const"] if isinstance(s["const"], list) else [s["const"]])]
        else:
            raise XError(f"op source {s} is not a field, zeros or constant cell source")
    if len(cells) != op["width"]:
        raise XError(f"op at {op['offset']} writes {len(cells)} cells, width {op['width']}")
    return cells


def sol_layout(path: dict) -> list[list]:
    """X3: an ok path's store sequence applied in order to dirty memory (later writes override); its first
    "length" cells, an unwritten cell ["unknown"]."""
    mem: dict[int, list] = {}
    for op in path["ops"]:
        for i, c in enumerate(_sol_cells(op)):
            mem[op["offset"] + i] = c
    return [mem.get(i, ["unknown"]) for i in range(path["length"])]


def _field_path(t, param: str):
    if t == ["param", param]:
        return []
    if isinstance(t, list) and t and t[0] == "field":
        inner = _field_path(t[1], param)
        return None if inner is None else inner + [t[2]]
    return None


def go_layout(entry: dict, param: str) -> list[list]:
    """X3: a Go encoder entry's cells; ["byte", <field of the parameter>, k] -> ["field", "<path>", k]."""
    out = []
    for c in entry["cells"]:
        if c[0] == "const":
            out.append(["const", c[1]])
        elif c[0] == "byte":
            fp = _field_path(c[1], param)
            if not fp:
                raise XError(f"{entry['function']}: cell {c} is not a byte of a field of its parameter {param}")
            out.append(["field", ".".join(fp), c[2]])
        else:
            raise XError(f"{entry['function']}: cell {c} is neither a constant nor a field byte")
    return out


def _record_fields(layouts: list[list[list]]) -> list[dict]:
    """X3: a Go record's fields: the field cells of its encoders' layouts, in order of first appearance; width =
    1 + the largest byte index (every index below it must occur)."""
    order, ks = [], {}
    for lay in layouts:
        for c in lay:
            if c[0] == "field":
                if c[1] not in ks:
                    order.append(c[1])
                    ks[c[1]] = set()
                ks[c[1]].add(c[2])
    out = []
    for f in order:
        w = max(ks[f]) + 1
        if ks[f] != set(range(w)):
            raise XError(f"field {f}: bytes {sorted(ks[f])} are not 0..{w - 1}")
        out.append({"name": f, "width": w})
    return out


def components(root: Path = ROOT, adoption_rel: str = ADOPTION.as_posix(),
               link_rel: str = LINK.as_posix()) -> list[dict]:
    """X1: one component per link role whose Solidity source is an "edge" (a loader) and whose Go source is a
    "function" (a tagged predicate), both documents adopted. Sorted by role."""
    root = Path(root)
    adopted = set(adoption(root, adoption_rel)["documents"])
    out = []
    for role, r in sorted(link_roles(root, link_rel).items()):
        s, g = r["solidity"], r["go"]
        if "edge" not in s or "function" not in g:
            continue
        if s["document"] not in adopted or g["document"] not in adopted:
            continue
        out.append(component(root, role, s, g))
    return out


def component(root: Path, role: str, s: dict, g: dict) -> dict:
    sol, go = _load(root, s["document"]), _load(root, g["document"])
    fns = go["go"]["functions"]
    codecs = go["go"]["codecs"]
    preds = [p for p in codecs["predicates"] if p["function"].rsplit(".", 1)[-1] == g["function"]]
    if len(preds) != 1:
        raise XError(f"role {role}: {len(preds)} Go predicates named {g['function']}")
    pred = preds[0]
    loader = sol["functions"][s["edge"]]
    if loader["kind"] != "loader":
        raise XError(f"role {role}: {s['edge']} is not a loader")

    def ptype(fid, pname):
        return next(p["type"] for p in fns[fid]["params"] if p["name"] == pname)

    go_bytes = ptype(pred["function"], pred["param"])
    sol_bytes = loader["from"]
    linked = sol_bytes   # X2: the linked carrier takes its Solidity member's type name
    tag = pred["tag_index"]
    funcs: dict[str, dict] = {}
    carriers: dict[str, dict] = {linked: {"kind": "bytes", "members": sorted([
        {"document": s["document"], "type": sol_bytes}, {"document": g["document"], "type": go_bytes}],
        key=lambda m: m["document"]), "domains": []}}

    def add(name, f):
        if name in funcs:
            raise XError(f"two functions named {name}")
        funcs[name] = f

    # Solidity functions whose input or output is the linked carrier's Solidity member
    for fname, f in sorted(sol["functions"].items()):
        src, tgt = base_type(f["from"]), base_type(f["to"])
        if sol_bytes not in (src, tgt):
            continue
        ok = [p for p in f["paths"] if p["outcome"] == "ok"]
        ent = {"kind": f["kind"], "document": s["document"], "source": f["entry"]["fn"], "lang": f["lang"],
               "partial": f["to"].startswith("Maybe<"),
               "from": linked if src == sol_bytes else src, "to": linked if tgt == sol_bytes else tgt,
               "ok": [p["cond"] for p in ok], "sink": f.get("sink")}
        if f["kind"] == "encoder":
            t = sol["types"][src]
            if t.get("kind") != "record":
                raise XError(f"{fname}: input {src} is not a record")
            _new_record(carriers, src, {"kind": "record", "document": s["document"], "type": src,
                                        "fields": [{"name": x["name"], "width": x["width"]} for x in t["fields"]]})
            layouts = {}
            for p in ok:
                lay = sol_layout(p)
                vs = _sol_versions(p, lay, carriers[src]["fields"], tag)
                for v in vs:
                    if str(v) in layouts and layouts[str(v)] != lay:
                        raise XError(f"{fname}: two ok paths give version {v} different layouts")
                    layouts[str(v)] = lay
            ent["layouts"] = dict(sorted(layouts.items(), key=lambda kv: int(kv[0])))
            ent["versions"] = sorted(int(v) for v in layouts)
        elif f["kind"] == "loader":
            ent["versions"] = _tag_versions_sol(ok, f, tag)
            carriers[linked]["domains"].append(f"ok_{fname}")
        else:
            raise XError(f"{fname}: kind {f['kind']} is not mapped")
        add(fname, ent)

    # Go encoders whose result is the linked carrier's Go member
    enc_names = {}
    for e in codecs["encoders"]:
        fid = e["function"]
        if fns[fid]["results"][e["result"]] != go_bytes:
            continue
        params = fns[fid]["params"]
        if len(params) != 1:
            raise XError(f"{fid}: an encoder of {len(params)} parameters has no record carrier")
        lay = go_layout(e, params[0]["name"])
        name = go_name(fid)
        rec = go_type(params[0]["type"])
        tagc = lay[tag] if tag < len(lay) else ["unknown"]
        vs = [tagc[1]] if tagc[0] == "const" else None
        ent = {"kind": "encoder", "document": g["document"], "source": fid, "lang": "go", "partial": False,
               "from": rec, "to": linked, "domain": e["conds"],
               "layouts": {str(vs[0]) if vs else "*": lay}, "versions": vs}
        if name in funcs:   # a second layout of one function (another length or cell set)
            raise XError(f"{fid}: more than one layout")
        add(name, ent)
        enc_names[fid] = name
        _new_record(carriers, rec, {"kind": "record", "document": g["document"], "type": params[0]["type"],
                                    "layouts": []})["layouts"].append(lay)
    for c in carriers.values():
        if c["kind"] == "record" and "layouts" in c:
            c["fields"] = _record_fields(c.pop("layouts"))

    # Go patches of those encoders
    for pt in codecs.get("patches", []):
        if pt["encoder"] not in enc_names:
            continue
        base = funcs[enc_names[pt["encoder"]]]
        lay = [list(c) for c in next(iter(base["layouts"].values()))]
        for w in pt["writes"]:
            lay[w["index"]] = ["const", w["value"]]
        tagc = lay[tag]
        vs = [tagc[1]] if tagc[0] == "const" else None
        add(go_name(pt["function"]), {"kind": "encoder", "document": g["document"], "source": pt["function"],
                                      "lang": "go", "partial": False, "from": base["from"], "to": linked,
                                      "patch_of": enc_names[pt["encoder"]], "domain": pt["guards"],
                                      "layouts": {str(vs[0]) if vs else "*": lay}, "versions": vs})

    # Go decoders and predicates of the linked carrier's Go member
    for d in codecs["decoders"]:
        fid = d["function"]
        if ptype(fid, d["param"]) != go_bytes:
            continue
        if len(d["reads"]) != 1:
            raise XError(f"{fid}: {len(d['reads'])} reads")
        rd = d["reads"][0]
        slot = f"{linked}@{rd['offset']}+{rd['width']}"
        carriers.setdefault(slot, {"kind": "slot", "of": linked, "offset": rd["offset"], "width": rd["width"]})
        ok = [p["cond"] for p in fns[fid]["paths"] if p["end"] == "return" and p["error"] == "nil"]
        add(go_name(fid), {"kind": "decoder", "document": g["document"], "source": fid, "lang": "go", "partial": True,
                           "from": linked, "to": slot, "read": rd, "param": d["param"], "ok": ok,
                           "versions": _tag_versions_go(ok, d["param"], tag)})
    for p in codecs["predicates"]:
        if ptype(p["function"], p["param"]) != go_bytes:
            continue
        ok = [x["cond"] for x in fns[p["function"]]["paths"] if x["end"] == "return" and x["error"] == "nil"]
        name = go_name(p["function"])
        add(name, {"kind": "predicate", "document": g["document"], "source": p["function"], "lang": "go",
                   "from": linked, "param": p["param"], "ok": ok, "versions": _tag_versions_go(ok, p["param"], tag)})
        carriers[linked]["domains"].append(name)
    carriers[linked]["domains"].sort()
    # HASH sinks (X6)
    return {"linked_version": LINKED_VERSION, "component": role, "role": role, "tag_index": tag,
            "linked_carrier": linked,
            "documents": sorted({s["document"], g["document"]}),
            "carriers": dict(sorted(carriers.items())), "functions": dict(sorted(funcs.items()))}


def _new_record(carriers: dict, cid: str, c: dict) -> dict:
    """X2: one record carrier per id; a second record of another document or type under one id is refused."""
    old = carriers.get(cid)
    if old is None:
        carriers[cid] = c
        return c
    if old["kind"] != "record" or (old["document"], old["type"]) != (c["document"], c["type"]):
        raise XError(f"carrier id {cid} names two carriers")
    return old


def _sol_versions(path: dict, lay: list[list], fields: list[dict], tag: int) -> list[int]:
    """X4: the versions of a Solidity encoder ok path: the values of the field whose byte 0 its layout places at the
    tag index (a one-byte field), 0..255, at which no atom of the path's condition that mentions only that field is
    false."""
    c = lay[tag] if tag < len(lay) else ["unknown"]
    if c[0] == "const":
        return [c[1]]
    if c[0] != "field" or c[2] != 0 or next(f["width"] for f in fields if f["name"] == c[1]) != 1:
        raise XError(f"tag cell {c} is not a constant or a one-byte field")
    name = c[1]
    out = []
    for v in range(256):
        if all(_ev_sol(a, {name: v}) != 0 for a in path["cond"]):
            out.append(v)
    return out


def _tag_versions_sol(ok: list[dict], f: dict, tag: int) -> list[int] | None:
    """X4: a Solidity loader's versions: the values of byte tag of its input at which some ok path's condition has no
    false atom among those that mention only that byte; None when no ok path's condition mentions it."""
    x = next(iter(_names_in(ok)), None)
    if x is None:
        return None
    out = set()
    for v in range(256):
        for p in ok:
            if all(_ev_sol(a, {("byte", x, tag): v}) != 0 for a in p["cond"]):
                out.add(v)
    return sorted(out)


def _names_in(paths: list[dict]) -> list[str]:
    out = []

    def walk(e):
        if isinstance(e, list) and e:
            if e[0] in ("len", "byte") and isinstance(e[1], str):
                out.append(e[1])
            for x in e[1:]:
                walk(x)
    for p in paths:
        walk(p["cond"])
    return sorted(set(out))


def _tag_versions_go(ok: list[list], param: str, tag: int) -> list[int] | None:
    """X4: a Go decoder's or predicate's versions: the values of byte tag of its parameter at which some ok path's
    condition has no false atom among those that mention only that byte; None when no ok path mentions the byte."""
    def is_tag(e):
        return isinstance(e, list) and len(e) == 3 and e[0] == "index" and e[1] == ["param", param] \
            and e[2] == ["const", tag]
    if not any(_mentions(c, is_tag) for c in ok):
        return None
    out = set()
    for v in range(256):
        for cond in ok:
            if all(_ev_go(a, {("index", tag): v}, param) != 0 for a in cond):
                out.add(v)
    return sorted(out)


# ------------------------------------------------------------------ the diagram (rule X6)
def diagram(comp: dict) -> dict:
    """X6: carriers and edges of a component in holon-diagram/0.1 vocabulary (the keys rules P0-P12 and E1/E2/E6 read)."""
    cars = []
    for cid, c in comp["carriers"].items():
        d = {"id": cid, "cls": "rep", "base_type": cid, "interface": False}
        if c["kind"] == "record":
            d["product"] = [f["name"] for f in c["fields"]]
        elif c["kind"] == "bytes":
            d["interface"] = bool(c["domains"])
            d["domains"] = list(c["domains"])
            d["key_space"] = "byte"
        cars.append(d)
    edges = []
    hashes = set()
    for name, f in comp["functions"].items():
        if f["kind"] == "predicate":
            continue
        e = {"id": f"CODEC.{name}", "kind": "CODEC", "model_fn": name, "src": f["from"], "tgt": f["to"],
             "partial": bool(f["partial"]), "version": label(f["versions"]), "fn_kind": f["kind"],
             "source": [{"fn": f["source"]}], "component": f["document"]}
        if f["kind"] == "loader":
            e["domain"] = f"ok_{name}"
        edges.append(e)
        if f.get("sink"):
            hashes.add((f["sink"]["op"], f["to"]))
    for op, src in sorted(hashes):
        cars.append({"id": op, "cls": "digest", "base_type": op, "interface": False})
        edges.append({"id": f"HASH.{op}", "kind": "HASH", "model_fn": None, "src": src, "tgt": op, "partial": False,
                      "version": None, "source": [], "component": None})
    return {"model": comp["component"], "carriers": sorted(cars, key=lambda c: c["id"]),
            "edges": sorted(edges, key=lambda e: e["id"])}


# ------------------------------------------------------------------ evidence over the component (rule X7)
def layout_at(f: dict, v: int | None) -> list[list] | None:
    if f.get("versions") is None:
        return next(iter(f["layouts"].values()))
    return f["layouts"].get(str(v))


def recovers(lay: list[list], read: dict) -> str | None:
    """X7 (E1, §10.2 by position): the field whose bytes 0..w-1 the layout places, in order, at the read."""
    o, w = read["offset"], read["width"]
    if o + w > len(lay):
        return None
    c0 = lay[o]
    if c0[0] != "field":
        return None
    if all(lay[o + k] == ["field", c0[1], k] for k in range(w)):
        return c0[1]
    return None


def _active(f: dict, v) -> bool:
    return f.get("versions") is None or v in f["versions"]


def _cid(model: str, level: str, p: str, q: str, via: dict) -> str:
    return f"{model}:{level}:{p}:{q}:{hashlib.sha256(canonical_json(via)).hexdigest()[:8]}"


def atoms(comp: dict, diag: dict) -> list[dict]:
    model = comp["component"]
    fs = comp["functions"]
    encs = sorted(n for n, f in fs.items() if f["kind"] == "encoder")
    decs = sorted(n for n, f in fs.items() if f["kind"] == "decoder")
    out = []
    inv: dict[tuple, str] = {}
    for e in encs:
        for v in fs[e]["versions"] or []:
            lay = layout_at(fs[e], v)
            for d in decs:
                if fs[d]["from"] != fs[e]["to"] or not _active(fs[d], v):
                    continue
                fld = recovers(lay, fs[d]["read"])
                if fld is None:
                    continue
                inv[(e, d, v)] = fld
                via = {"kind": "inverse", "version": v, "fields": [fld], "not_recovered": []}
                out.append({"id": _cid(model, "E1", f"CODEC.{e}", f"CODEC.{d}", via), "model": model, "level": "E1",
                            "p": f"CODEC.{e}", "q": f"CODEC.{d}", "via": via, "src": None})
    for i, p in enumerate(encs):
        for q in encs[i + 1:]:
            if fs[p]["to"] != fs[q]["to"]:
                continue
            for v in sorted(set(fs[p]["versions"] or []) & set(fs[q]["versions"] or [])):
                for d in decs:
                    if (p, d, v) in inv and (q, d, v) in inv:
                        via = {"kind": "common_decoder", "version": v, "decoder": f"CODEC.{d}",
                               "fields": [inv[(p, d, v)], inv[(q, d, v)]]}
                        out.append({"id": _cid(model, "E1", f"CODEC.{p}", f"CODEC.{q}", via), "model": model,
                                    "level": "E1", "p": f"CODEC.{p}", "q": f"CODEC.{q}", "via": via, "src": None})
    # E2: written via an encoder (its layout cells that are not unknown), read via a decoder (its read range)
    for e in encs:
        written = set()
        for lay in fs[e]["layouts"].values():
            written |= {i for i, c in enumerate(lay) if c[0] != "unknown"}
        for d in decs:
            if fs[d]["from"] != fs[e]["to"]:
                continue
            rd = fs[d]["read"]
            r = set(range(rd["offset"], rd["offset"] + rd["width"]))
            if written & r:
                via = {"carrier": fs[e]["to"], "writes": _ranges(written & r), "reads": _ranges(r & written)}
                out.append({"id": _cid(model, "E2", f"CODEC.{e}", f"CODEC.{d}", via), "model": model, "level": "E2",
                            "p": f"CODEC.{e}", "q": f"CODEC.{d}", "via": via, "src": None})
    # E6: the I14 lexicon over parallel edges
    lex = Lexicon(load_json(ROOT / "spec" / "M2" / "lib" / "evidence_lexical.json"))
    cods = [e for e in diag["edges"] if e["kind"] == "CODEC"]
    for i, a in enumerate(cods):
        for b in cods[i + 1:]:
            if (a["src"], a["tgt"]) != (b["src"], b["tgt"]):
                continue
            ta = set().union(*(lex.tokens(s["fn"]) for s in a["source"]))
            tb = set().union(*(lex.tokens(s["fn"]) for s in b["source"]))
            if ta & tb:
                via = {"tokens": sorted(ta & tb)}
                out.append({"id": _cid(model, "E6", a["id"], b["id"], via), "model": model, "level": "E6",
                            "p": a["id"], "q": b["id"], "via": via, "src": None})
    return sorted(out, key=lambda a: a["id"])


def _ranges(s: set[int]) -> list[str]:
    xs = sorted(s)
    out, i = [], 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        out.append(f"{xs[i]}..{xs[j]}" if j > i else f"{xs[i]}")
        i = j + 1
    return out


class Lexicon:
    """The I14 E6 tokenizer (spec/M2/lib/evidence_lexical.json), written out again."""
    _CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")

    def __init__(self, doc: dict):
        self.ident = re.compile(doc["tokenize"]["identifier"])
        self.min = int(doc["tokenize"]["min_length"])
        self.stop = set(doc["stopwords"])

    def tokens(self, text: str) -> set[str]:
        out = set()
        for ident in self.ident.findall(text):
            for part in ident.split("_"):
                for t in self._CAMEL.split(part) if part else []:
                    t = t.lower()
                    if len(t) >= self.min and t not in self.stop:
                        out.add(t)
        return out


# ------------------------------------------------------------------ PAR over a component (rule X8)
def _bytes_hex(vals: list[int]) -> str:
    return "0x" + bytes(vals).hex()


def _call(fn: str, arg) -> dict:
    return {"call": fn, "args": [arg]}


def _stmt(binders: list[tuple[str, str]], assume: list, lhs, rhs) -> dict:
    return {"binders": [{"q": "forall", "name": n, "type": t} for n, t in binders], "assume": assume,
            "claim": {"eq": [lhs, rhs]}, "scope": {"kind": "unbounded"}}


def _vpremise(var: str, comp: dict, carrier: str, v) -> list:
    """P0 over a component: a record carrier with a field named version gets the premise version = v."""
    c = comp["carriers"].get(carrier, {})
    if v is None or c.get("kind") != "record":
        return []
    w = next((f["width"] for f in c["fields"] if f["name"] == "version"), None)
    if w is None:
        return []
    return [{"eq": [{"field": "version", "of": {"var": var}}, {"bytes": _bytes_hex(list(v.to_bytes(w, "big")))}]}]


def tag_decoder(comp: dict) -> str | None:
    """X8c: the component's tag decoder, the one unversioned decoder whose read is (tag_index, 1); None when there is
    no such decoder or more than one."""
    hits = sorted(n for n, f in comp["functions"].items() if f["kind"] == "decoder" and f["versions"] is None
                  and (f["read"]["offset"], f["read"]["width"]) == (comp["tag_index"], 1))
    return hits[0] if len(hits) == 1 else None


def _tag_premise(var: str, tdec: str, v: int) -> list:
    """X8c: the version premise of a law over the linked carrier: its tag decoder reads the one byte v."""
    return [{"eq": [_call(tdec, {"var": var}), {"some": {"bytes": _bytes_hex([v])}}]}]


def _scope(comp: dict, car: dict, cv):
    """P0 and X8c: how a versioned instance over source carrier car is scoped. Returns (versions, premise function,
    reason): one law per common version with the version premise when the carrier is a record with a field named
    version, or the linked carrier with a tag decoder (the tag premise); the linked carrier without a tag decoder gives
    no law (reason no_version_premise: a version scope is never dropped); otherwise one unversioned law."""
    if cv is None:
        return [None], (lambda var, v: []), None
    if "version" in (car.get("product") or []):
        return cv, (lambda var, v: _vpremise(var, comp, car["id"], v)), None
    if car["id"] == comp["linked_carrier"]:
        tdec = tag_decoder(comp)
        if tdec is None:
            return [], None, "no_version_premise"
        return cv, (lambda var, v: _tag_premise(var, tdec, v)), None
    return [None], (lambda var, v: []), None


def _bname(car: dict) -> str:
    return "h" if car.get("product") else ("b" if car.get("key_space") == "byte" else "x")


def expected(comp: dict, diag: dict, ats: list[dict], milestone: str = "M3") -> dict:
    """Rules P1-P12 over one component (rule X8: P1 and P2 adapted to single-read decoders, the rest as written).
    Returns {"laws": {law_id: {"subform", "statement", "model"}}, "basis": [...], "cycle": cycle_basis summary}."""
    model = comp["component"]
    fs = comp["functions"]
    out = P._Out(facts_path(model, milestone), model)
    carriers = {c["id"]: c for c in diag["carriers"]}
    edges = {e["id"]: e for e in diag["edges"]}
    tag = P.TAG

    # P1 (X8a) round trip: one law per inverse atom; the projection is the field the decoder recovers
    for a in sorted((a for a in ats if a["level"] == "E1" and a["via"]["kind"] == "inverse"), key=lambda a: a["id"]):
        e, d, v = edges[a["p"]], edges[a["q"]], a["via"]["version"]
        vp = _vpremise("h", comp, e["src"], v)
        st = _stmt([("h", e["src"])], vp, _call(d["model_fn"], _call(e["model_fn"], {"var": "h"})),
                   {"some": {"field": a["via"]["fields"][0], "of": {"var": "h"}}})
        out.entry("round_trip", {"atom": a["id"]}, v,
                  [(f"L_par_{tag['round_trip']}_{e['model_fn']}_{d['model_fn']}_v{v}", st)])

    # P2 (X8b) cross-component agreement: one basis element per (p, q, version) with common_decoder atoms
    groups: dict[tuple, list] = {}
    for a in sorted((a for a in ats if a["level"] == "E1" and a["via"]["kind"] == "common_decoder"),
                    key=lambda a: a["id"]):
        groups.setdefault((a["p"], a["q"], a["via"]["version"]), []).append(a)
    for (pid, qid, v), group in sorted(groups.items()):
        p, q = edges[pid], edges[qid]
        hp, hq = "h", ("k" if q["src"] != p["src"] else "h")
        binders = [(hp, p["src"])] + ([(hq, q["src"])] if hq != hp else [])
        vp = _vpremise(hp, comp, p["src"], v) + (_vpremise(hq, comp, q["src"], v) if hq != hp else [])
        corr, seen = [], set()
        for a in sorted(group, key=lambda a: a["via"]["decoder"]):
            fp, fq = a["via"]["fields"]
            if (fp, fq) in seen:
                continue
            seen.add((fp, fq))
            if hq != hp or fp != fq:
                corr.append({"eq": [{"field": fp, "of": {"var": hp}}, {"field": fq, "of": {"var": hq}}]})
        lp, lq = layout_at(fs[p["model_fn"]], v), layout_at(fs[q["model_fn"]], v)
        pins, bad = [], False
        for (var, src, la, lb) in ((hp, p["src"], lp, lq), (hq, q["src"], lq, lp)):
            for fld in comp["carriers"][src]["fields"]:
                name, w = fld["name"], fld["width"]
                pos = [next((i for i, c in enumerate(la) if c == ["field", name, k]), None) for k in range(w)]
                if None in pos:
                    continue
                other = [lb[i] if i < len(lb) else ["unknown"] for i in pos]
                if not all(c[0] == "const" for c in other):
                    continue
                pn = {"eq": [{"field": name, "of": {"var": var}}, {"bytes": _bytes_hex([c[1] for c in other])}]}
                own = _vpremise(var, comp, src, v)
                if name == "version" and own:
                    bad = bad or pn != own[0]
                    continue
                pins.append(pn)
        lhs, rhs = _call(p["model_fn"], {"var": hp}), _call(q["model_fn"], {"var": hq})
        base = f"L_par_{tag['cross_component_codec']}_{p['model_fn']}_{q['model_fn']}_v{v}"
        cands = [(base, _stmt(binders, vp + corr, lhs, rhs))]
        if pins and not bad:
            cands.append((base + "_pinned", _stmt(binders, vp + corr + pins, lhs, rhs)))
        out.entry("cross_component_codec", {"p": pid, "q": qid}, v, cands, "contradictory_pin" if bad else None)

    # P3 branch: two CODEC edges of a component citing one function cannot arise (one edge per function or patch)
    codecs = sorted((e for e in diag["edges"] if e["kind"] == "CODEC"), key=lambda e: e["id"])
    for i, p in enumerate(codecs):
        for q in codecs[i + 1:]:
            if (p["src"], p["tgt"]) == (q["src"], q["tgt"]) and p["source"] == q["source"]:
                raise XError(f"{p['id']} and {q['id']} cite one function")

    # P4 PAR-weak
    for a in sorted((a for a in ats if a["level"] == "E6"), key=lambda a: a["id"]):
        p, q = edges[a["p"]], edges[a["q"]]
        key = {"atom": a["id"]}
        car = carriers[p["src"]]
        var = _bname(car)
        cv = P.common_versions([p, q])
        if cv == []:
            out.entry("weak", key, None, [], "no_common_version")
            continue
        vs, prem, why = _scope(comp, car, cv)
        if why:
            out.entry("weak", key, None, [], why)
            continue
        for v in vs:
            stronger = [b for b in ats if b["level"] != "E6" and {b["p"], b["q"]} == {p["id"], q["id"]}
                        and (v is None or b["via"].get("version") in (None, v))]
            if stronger:
                out.entry("weak", key, v, [], "stronger_evidence")
                continue
            lid = f"L_par_{tag['weak']}_{p['model_fn']}_{q['model_fn']}" + (f"_v{v}" if v is not None else "")
            out.entry("weak", key, v, [(lid, _stmt([(var, car["id"])], prem(var, v),
                                                   _call(p["model_fn"], {"var": var}),
                                                   _call(q["model_fn"], {"var": var})))])

    # P5 domain coherence
    for c in sorted(diag["carriers"], key=lambda c: c["id"]):
        doms = sorted(c.get("domains") or [])
        if not c.get("interface") or len(doms) < 2:
            continue
        var = _bname(c)
        for i, p1 in enumerate(doms):
            for p2 in doms[i + 1:]:
                out.entry("domain_coherence", {"carrier": c["id"], "p": p1, "q": p2}, None,
                          [(f"L_par_{tag['domain_coherence']}_{p1}_{p2}",
                            _stmt([(var, c["id"])], [], _call(p1, {"var": var}), _call(p2, {"var": var})))])

    # P6 totality
    for e in sorted((e for e in diag["edges"] if e["kind"] in ("CODEC", "CONS")), key=lambda e: e["id"]):
        car = carriers.get(e["src"], {})
        if not car.get("interface"):
            continue
        key = {"edge": e["id"]}
        if e.get("partial"):
            out.entry("totality", key, None, [], "explicit_option")
        elif isinstance(e.get("domain"), str):
            var = _bname(car)
            out.entry("totality", key, None, [(f"L_par_{tag['totality']}_{e['model_fn']}", _stmt(
                [(var, car["id"])], [], _call(e["domain"], {"var": var}), {"bool": True}))])
        else:
            out.entry("totality", key, None, [], "no_domain_predicate")

    # P8 cycles
    cb = P.cycle_basis(diag)
    for eid in cb["non_tree"]:
        walk = P.fundamental_cycle(cb, eid)
        key = {"edge": eid}
        kinds = {e["kind"] for e, _ in walk}
        if "TRANS" in kinds:
            out.entry("cycle", key, None, [], "relation")
            continue
        if "HASH" in kinds:
            out.entry("cycle", key, None, [], "hash_edge")
            continue
        pw = P.parallel_walks(walk)
        if pw is None:
            out.entry("cycle", key, None, [], "not_a_parallel_pair")
            continue
        src, Pw, Qw = pw
        if any(e.get("partial") for e in Pw[:-1] + Qw[:-1]):
            out.entry("cycle", key, None, [], "partial_inner")
            continue
        if bool(Pw[-1].get("partial")) != bool(Qw[-1].get("partial")):
            out.entry("cycle", key, None, [], "type_mismatch")
            continue
        car = carriers[src]
        var = _bname(car)

        def term(path, var=var):
            t = {"var": var}
            for e in path:
                t = _call(e["model_fn"], t)
            return t
        cv = P.common_versions([e for e, _ in walk])
        base = f"L_par_{tag['cycle']}_{edges[eid]['model_fn']}"
        if cv == []:
            out.entry("cycle", key, None, [], "no_common_version")
            continue
        vs, prem, why = _scope(comp, car, cv)
        if why:
            out.entry("cycle", key, None, [], why)
        elif vs != [None]:
            for v in vs:
                out.entry("cycle", key, v, [(f"{base}_v{v}", _stmt([(var, src)], prem(var, v),
                                                                     term(Pw), term(Qw)))])
        else:
            out.entry("cycle", key, None, [(base, _stmt([(var, src)], [], term(Pw), term(Qw)))])

    order = {s: n for n, s in enumerate(P.SUBFORMS)}
    basis = sorted(out.basis, key=lambda b: (order[b["subform"]], canonical_json(b["key"]),
                                             -1 if b["version"] is None else b["version"]))
    cycle = {k: v for k, v in cb.items() if not k.startswith("_")}
    return {"laws": out.laws, "basis": basis, "cycle": cycle}


def facts_path(model: str, milestone: str = "M3") -> str:
    """X1: the linked codec document a component's laws are about (their "facts")."""
    return f"gen/{milestone}/codec/{model}.json"


# ------------------------------------------------------------------ outcomes by direct evaluation (rule X9)
def _consts(e, out: set) -> set:
    if isinstance(e, list):
        if len(e) == 2 and e[0] == "const" and isinstance(e[1], int):
            out.add(e[1])
        for x in e:
            _consts(x, out)
    elif isinstance(e, int) and not isinstance(e, bool):
        out.add(e)
    return out


def probes(comp: dict, names: list[str]) -> list[tuple[int, int]]:
    """X9: the (length, tag byte) probes of byte-string laws: every integer constant k of the ok conditions of the
    functions named (directly, or through ok_<loader>), k - 1, k, k + 1 (those >= 0), and 0, as lengths; the same
    set below 256 as tag values; length 0 only with tag 0. Sorted by (length, tag)."""
    ks: set[int] = set()
    for n in names:
        f = comp["functions"].get(n[3:] if n.startswith("ok_") and n[3:] in comp["functions"] else n)
        for cond in f["ok"]:
            _consts(cond, ks)
    vals = sorted({0} | {x for k in ks for x in (k - 1, k, k + 1) if x >= 0})
    tags = [v for v in vals if v < 256]
    return [(n, t) for n in vals for t in tags if n > 0 or t == 0]


def decoder_ok(f: dict, length: int, tagv: int, tag: int) -> bool:
    """Whether some ok path of a Go decoder or predicate holds on a byte string of this length and tag byte."""
    env = {("len",): length, ("index", tag): tagv}
    for cond in f["ok"]:
        vals = [_ev_go(a, env, f["param"]) for a in cond]
        if None in vals:
            raise XError(f"{f['source']}: an ok condition mentions more than the length and the tag byte")
        if all(vals):
            return True
    return False


def loader_ok(f: dict, length: int, tagv: int, tag: int) -> bool:
    for p in f["ok"]:
        names = _names_in([{"cond": p}])
        env = {}
        for x in names:
            env[("len", x)] = length
            env[("byte", x, tag)] = tagv
        vals = [_ev_sol(a, env) for a in p]
        if None in vals:
            raise XError(f"{f['source']}: an ok condition mentions more than the length and the tag byte")
        if all(vals):
            return True
    return False


def _domain_value(comp: dict, name: str, length: int, tagv: int):
    tag = comp["tag_index"]
    if name.startswith("ok_") and name[3:] in comp["functions"]:
        return loader_ok(comp["functions"][name[3:]], length, tagv, tag)
    f = comp["functions"][name]
    if f["kind"] == "predicate":
        return decoder_ok(f, length, tagv, tag)
    if f["kind"] == "decoder":
        return ("read", f["read"]["offset"], f["read"]["width"]) if decoder_ok(f, length, tagv, tag) else None
    raise XError(f"{name} is not a predicate or decoder")


def decide(comp: dict, law: dict) -> dict:
    """X9: the status the compiled component model gives a component law ({"status", "why"} and, for REFUTED, the
    class of witness), decided here by direct evaluation of the layouts and the decoders' conditions."""
    st = law["statement"]
    l, r = st["claim"]["eq"]
    fs = comp["functions"]
    tag = comp["tag_index"]
    sub = law["subform"]
    if sub == "round_trip":
        e = fs[l["args"][0]["call"]]
        d = fs[l["call"]]
        v = int(law["law_id"].rsplit("_v", 1)[1])
        lay = layout_at(e, v)
        ok = decoder_ok(d, len(lay), v, tag) and recovers(lay, d["read"]) == r["some"]["field"]
        return {"status": "PROVED" if ok else "REFUTED", "why": f"{d['source']} accepts length {len(lay)} at tag {v}"}
    if sub == "cross_component_codec":
        v = int(law["law_id"].split("_v")[-1].split("_")[0])
        p, q = fs[l["call"]], fs[r["call"]]
        hp, hq = l["args"][0]["var"], r["args"][0]["var"]
        lp, lq = layout_at(p, v), layout_at(q, v)
        cls: dict = {}
        pinned: dict = {}
        for a in st["assume"]:
            x, y = a["eq"]
            if "field" in x and "field" in y:
                cls[(x["of"]["var"], x["field"])] = cls[(y["of"]["var"], y["field"])] = (x["field"], y["field"])
            else:
                pinned[(x["of"]["var"], x["field"])] = bytes.fromhex(y["bytes"][2:])

        def norm(c, var):
            if c[0] == "field":
                if (var, c[1]) in pinned:
                    return ["const", pinned[(var, c[1])][c[2]]]
                if (var, c[1]) in cls:
                    return ["class", cls[(var, c[1])], c[2]]
                return ["free", var, c[1], c[2]]
            return c
        diffs = [i for i in range(max(len(lp), len(lq)))
                 if i >= len(lp) or i >= len(lq) or norm(lp[i], hp) != norm(lq[i], hq)]
        if not diffs:
            return {"status": "PROVED", "why": "the two layouts agree cell by cell under the premises"}
        fields = sorted({c[2] for i in diffs for c in (norm(lp[i], hp), norm(lq[i], hq)) if c[0] == "free"})
        return {"status": "REFUTED", "why": f"positions {diffs[0]}..{diffs[-1]} differ", "positions": diffs,
                "free_fields": fields}
    if sub in ("weak", "domain_coherence", "cycle"):
        tagv = tag_premise_version(st)
        ps = probes(comp, [l["call"], r["call"]])
        if tagv is not None:   # X8c: only byte strings the tag premise admits (length >= 1, tag byte tagv)
            ps = [(n, tagv) for n in sorted({n for n, _ in ps}) if n > 0]
        for n, t in ps:
            if _domain_value(comp, l["call"], n, t) != _domain_value(comp, r["call"], n, t):
                return {"status": "REFUTED", "why": f"length {n}, tag {t}", "length": n, "tag": t}
        return {"status": "UNKNOWN", "why": "no probe distinguishes the two sides"}
    raise XError(f"no outcome rule for {sub}")


def tag_premise_version(st: dict) -> int | None:
    """X8c: the version a statement's tag premise fixes ({"eq": [{"call": T, ..}, {"some": {"bytes": "0x<v>"}}]}),
    else None."""
    for a in st.get("assume", []):
        x, y = a["eq"]
        if "call" in x and isinstance(y.get("some"), dict) and "bytes" in y["some"]:
            return int(y["some"]["bytes"], 16)
    return None


LEVELS = ("E1", "E2", "E3", "E4", "E5", "E6")


def law_levels(diag: dict, ats: list[dict], law: dict) -> list[str]:
    """I14's law_evidence (L1-L4) over a component model: {"call": f} names CODEC.<f> when f is an edge's model
    function, and the edges whose domain is f when f is a domain predicate; the version is the premise on a field
    named version or the tag premise (X8c); relevant atoms relate two named edges (at that version when the atom has
    one)."""
    st = law["statement"]
    codec = {e["model_fn"]: e["id"] for e in diag["edges"] if e["kind"] == "CODEC"}
    doms = {}
    for c in diag["carriers"]:
        for p in c.get("domains") or []:
            doms[p] = sorted(e["id"] for e in diag["edges"] if e.get("domain") == p)
    named = set()
    for f in _calls(st["assume"]) | _calls(st["claim"]):
        if f in codec:
            named.add(codec[f])
        named |= set(doms.get(f, []))
    v = None
    vs = [int(a["eq"][1]["bytes"], 16) for a in st["assume"]
          if a["eq"][0].get("field") == "version" and "bytes" in a["eq"][1]]
    if tag_premise_version(st) is not None:   # X8c: the tag premise is the version premise (L4)
        vs.append(tag_premise_version(st))
    if len(vs) == 1:
        v = vs[0]
    lv = {a["level"] for a in ats if a["p"] in named and a["q"] in named
          and (v is None or "version" not in a["via"] or a["via"]["version"] == v)}
    return sorted(lv)


def triage(status: str, levels: list[str]) -> str:
    if status != "REFUTED":
        return "none"
    mx = next((x for x in LEVELS if x in levels), None)
    return "intent_question" if mx == "E6" else "finding"


# ------------------------------------------------------------------ the back-test across documents (rules B1-B5)
_CHAIN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
HAND = "facts/morph_header.json"


def code_name(f: dict) -> str:
    """B1: the code name of a component function: Solidity "<function>" (the entry's last segment), Go "T.M" or "F"."""
    if f["lang"] == "go":
        m = re.fullmatch(r"\((\*?)(.*)\)\.([^.()]+)", f["source"])
        return f"{m.group(2).rsplit('.', 1)[-1]}.{m.group(3)}" if m else f["source"].rsplit(".", 1)[-1]
    return f["source"].rsplit(".", 1)[-1]


KIND_OK = {"encoder": ("encoder",), "predicate": ("loader", "predicate"), "decoder": ("decoder",),
           "projection": ()}


def backtest_map(root: Path = ROOT) -> dict:
    """B1: the name map mu from the M0 hand document's names to the M3 component's, computed from the hand document's
    source citations and field annotations and the component's provenance (never from law ids):
      functions  hand g -> the component function whose code name is one of the identifier chains of g's
                 source[].fn strings, of a compatible kind (encoder: encoder; predicate: a loader, whose domain
                 predicate ok_<loader> is the image, or a predicate; decoder: decoder); none or several -> no image
      types      the hand record -> every component record holding an image of one of its fields; the hand byte
                 type -> the linked carrier whose Solidity member has that name
      fields     hand field F of the record -> the Solidity record's field named F; the Go records' fields whose last
                 path segment is the first word of F's "go" annotation"""
    hand = _load(root, HAND)
    out = {"functions": {}, "types": {}, "fields": {}}
    for comp in components(root):
        fs = comp["functions"]
        for g, hf in sorted(hand["functions"].items()):
            chains = set()
            for s in hf.get("source", []):
                chains |= set(_CHAIN.findall(s.get("fn", "")))
            hits = sorted(n for n, f in fs.items() if code_name(f) in chains and f["kind"] in KIND_OK[hf["kind"]])
            if len(hits) == 1:
                n = hits[0]
                out["functions"][g] = f"ok_{n}" if fs[n]["kind"] == "loader" else n
            else:
                out["functions"][g] = None
        for tname, t in sorted(hand["types"].items()):
            if t.get("kind") == "record":
                fmap = {}
                for fld in t["fields"]:
                    imgs = {}
                    for cid, c in comp["carriers"].items():
                        if c["kind"] != "record":
                            continue
                        if c["document"].endswith(".go.extracted.json"):
                            gw = (fld.get("go") or "").split()
                            names = [x["name"] for x in c["fields"] if gw and x["name"].rsplit(".", 1)[-1] == gw[0]]
                        else:
                            names = [x["name"] for x in c["fields"] if x["name"] == fld["name"]]
                        if len(names) == 1:
                            imgs[cid] = names[0]
                    fmap[fld["name"]] = imgs
                out["fields"][tname] = fmap
                out["types"][tname] = sorted({cid for imgs in fmap.values() for cid in imgs})
            elif t.get("kind") == "bytes":
                c = comp["carriers"][comp["linked_carrier"]]
                if any(m["type"] == tname and not m["document"].endswith(".go.extracted.json") for m in c["members"]):
                    out["types"][tname] = [comp["linked_carrier"]]
                else:
                    out["types"][tname] = []
            else:
                out["types"][tname] = []
    return out


def _inverse(mu: dict):
    fn = {}
    for g, n in mu["functions"].items():
        if n is not None:
            fn[n] = g
    ty = {}
    for t, cids in mu["types"].items():
        for c in cids:
            ty[c] = t
    fld = {}
    for t, fmap in mu["fields"].items():
        for hf, imgs in fmap.items():
            for cid, name in imgs.items():
                fld[(cid, name)] = hf
    return fn, ty, fld


def collapse(law: dict, mu: dict) -> dict | None:
    """B2: the M3 law renamed into the hand names by mu (None when some name has no preimage), then its binders of one
    hand type merged wherever every premise relating them equates one hand field of each."""
    fn, ty, fld = _inverse(mu)
    st = law["statement"]
    types = {}
    for b in st["binders"]:
        if b["type"] not in ty:
            return None
        types[b["name"]] = b["type"]

    def ren(t):
        if isinstance(t, list):
            return [ren(x) for x in t]
        if not isinstance(t, dict):
            return t
        if "call" in t:
            if t["call"] not in fn:
                raise KeyError(t["call"])
            return {"call": fn[t["call"]], "args": ren(t["args"])}
        if "field" in t:
            key = (types[t["of"]["var"]], t["field"])
            if key not in fld:
                raise KeyError(key)
            return {"field": fld[key], "of": ren(t["of"])}
        return {k: ren(v) for k, v in t.items()}
    try:
        assume, claim = ren(st["assume"]), ren(st["claim"])
    except KeyError:
        return None
    binders = [{"q": b["q"], "name": b["name"], "type": ty[b["type"]]} for b in st["binders"]]
    changed = True
    while changed:
        changed = False
        for i, x in enumerate(binders):
            for y in binders[i + 1:]:
                if x["type"] != y["type"]:
                    continue
                rel = [a for a in assume if {x["name"], y["name"]} <= _vars(a)]
                if not all(_same_field(a, x["name"], y["name"]) for a in rel):
                    continue
                assume = [a for a in assume if a not in rel]
                assume = _subst(assume, y["name"], x["name"])
                claim = _subst(claim, y["name"], x["name"])
                binders = [b for b in binders if b["name"] != y["name"]]
                changed = True
                break
            if changed:
                break
    uniq = []
    for a in assume:
        if a not in uniq:
            uniq.append(a)
    return {"statement": {"binders": binders, "assume": uniq, "claim": claim, "scope": st.get("scope")}}


def _vars(t) -> set[str]:
    if isinstance(t, list):
        return set().union(set(), *(_vars(x) for x in t))
    if isinstance(t, dict):
        if "var" in t and isinstance(t["var"], str):
            return {t["var"]}
        return set().union(set(), *(_vars(v) for v in t.values()))
    return set()


def _same_field(a: dict, x: str, y: str) -> bool:
    if "eq" not in a:
        return False
    s, t = a["eq"]
    return ("field" in s and "field" in t and s["field"] == t["field"]
            and {s["of"].get("var"), t["of"].get("var")} == {x, y})


def _subst(t, old: str, new: str):
    if isinstance(t, list):
        return [_subst(x, old, new) for x in t]
    if isinstance(t, dict):
        if t.get("var") == old and set(t) == {"var"}:
            return {"var": new}
        return {k: _subst(v, old, new) for k, v in t.items()}
    return t


def paired(old: dict, new: dict, mu: dict) -> bool:
    """B2: an M0 law and an M3 law are paired iff the collapsed M3 law is alpha-equivalent to the M0 law (rule P11's
    normal form, the facts file aside)."""
    c = collapse(new, mu)
    if c is None:
        return False
    a, b = P.canonical(old), P.canonical(c)
    a.pop("facts", None)
    b.pop("facts", None)
    return canonical_json(a) == canonical_json(b)


def _hand_widths(hand: dict) -> dict:
    return {f["name"]: f["width"] for t in hand["types"].values() if t.get("kind") == "record" for f in t["fields"]}


def hand_layout(hand: dict, fn: str, v: int) -> list[list]:
    """The M0 hand encoder's layout at version v (§10.2 over the facts-0.1 ops), written out for bridge outcomes."""
    f = hand["functions"][fn]
    w = _hand_widths(hand)
    if f["lang"] == "solidity-evm-memory":
        length = f["length_by_version"][str(v)]
        mem: dict[int, list] = {}
    else:
        length = f["length"]
        mem = {i: ["const", 0] for i in range(length)}
    for op in f["ops"]:
        when = op.get("when")
        if when and v < when["version_ge"]:
            continue
        cells = []
        for s in op["src"]:
            if "field" in s:
                cells += [["field", s["field"], k] for k in range(w[s["field"]])]
            elif "zeros" in s:
                cells += [["const", 0]] * s["zeros"]
            else:
                cells += [["const", s["const"]]]
        for i, c in enumerate(cells):
            mem[op["offset"] + i] = c
    return [mem.get(i, ["unknown"]) for i in range(length)]


def hand_pred(hand: dict, fn: str, length: int, tagv: int) -> bool:
    for r in hand["functions"][fn]["rules"]:
        cond = r["if"]
        if cond == "empty":
            hit = length == 0
        elif cond == "otherwise":
            hit = True
        else:
            hit = length > 0 and tagv in cond["version_in"]
        if hit:
            t = r["then"]
            if isinstance(t, bool):
                return t
            return length >= t["len_ge"] if "len_ge" in t else length == t["len_eq"]
    return False


def bridges(old: dict, comp: dict, mu: dict, root: Path = ROOT) -> list[dict]:
    """B3/B4: one bridge per function the M0 law names: under the M0 law's premises, the hand function equals its
    mu-image applied to the hand value moved into the image's carrier. Outcome by direct evaluation: an encoder
    bridge (records, fixed version) is PROVED iff the two layouts agree cell by cell after mu (and REFUTED
    otherwise); a predicate bridge over unbounded bytes is REFUTED when a probe distinguishes the sides, else UNKNOWN
    (no proof class decides it)."""
    hand = _load(root, HAND)
    st = old["statement"]
    names = sorted(_calls(st["claim"]) | _calls(st["assume"]))
    fmap = mu["fields"]["Header"]
    v = None
    for a in st["assume"]:
        x, y = a["eq"]
        if x.get("field") == "version":
            v = int(y["bytes"], 16)
    out = []
    for g in names:
        img = mu["functions"].get(g)
        row = {"old": old["law_id"], "fn": g, "image": img}
        if img is None:
            out.append(dict(row, status=None, why="no image"))
            continue
        kind = hand["functions"][g]["kind"]
        if kind == "encoder":
            f = comp["functions"][img]
            hl, cl = hand_layout(hand, g, v), layout_at(f, v)
            rev = {name: hf for hf, imgs in fmap.items() for cid, name in imgs.items() if cid == f["from"]}
            same = len(hl) == len(cl) and all(
                a == b or (a[0] == "field" and b[0] == "field" and rev.get(b[1]) == a[1] and a[2] == b[2])
                for a, b in zip(hl, cl))
            out.append(dict(row, status="PROVED" if same else "REFUTED", why="layouts compared after mu"))
        else:
            diff = None
            for n, t in probes(comp, [img]):
                if diff is None and hand_pred(hand, g, n, t) != _domain_value(comp, img, n, t):
                    diff = (n, t)
            out.append(dict(row, status="REFUTED" if diff else "UNKNOWN",
                            why=f"probe {diff}" if diff else "no probe distinguishes the sides; unbounded bytes"))
    return out


def _transfers(old: dict, comp: dict, exp: dict, new: str, mu: dict, root: Path) -> bool:
    """B4(b) for byte-string laws: the M3 law's probe witness (decide()) distinguishes the M0 law's two sides on the
    hand model too (the hand predicates evaluated at the same length and tag byte)."""
    w = decide(comp, dict(exp["laws"][new], law_id=new))
    if "length" not in w:
        return False
    hand = _load(root, HAND)
    l, r = old["statement"]["claim"]["eq"]
    return hand_pred(hand, l["call"], w["length"], w["tag"]) != hand_pred(hand, r["call"], w["length"], w["tag"])


def uncovered(root: Path = ROOT, adoption_rel: str = ADOPTION.as_posix(), link_rel: str = LINK.as_posix()) -> list:
    """X1: what the adopted documents hold that no component covers: a transitions document as a whole (gap G1), and
    every codec function (Solidity functions; Go encoder, decoder and predicate functions and patches) outside every
    component (gap G2). Sorted by (document, function)."""
    comps = components(root, adoption_rel, link_rel)
    inside = {(f["document"], f["source"]) for c in comps for f in c["functions"].values()}
    out = []
    for rel in sorted(adoption(root, adoption_rel)["documents"]):
        d = _load(root, rel)
        if (d.get("extraction") or {}).get("kind") == "transitions":
            out.append({"document": rel, "function": None, "reason": "transitions"})
            continue
        if "functions" in d and "go" not in d:
            for name, f in sorted(d["functions"].items()):
                if (rel, f["entry"]["fn"]) not in inside:
                    out.append({"document": rel, "function": f["entry"]["fn"], "reason": "outside"})
            continue
        cod = d["go"]["codecs"]
        fids = {e["function"] for e in cod["encoders"]} | {x["function"] for x in cod["decoders"]} \
            | {x["function"] for x in cod["predicates"]} | {x["function"] for x in cod.get("patches", [])}
        for fid in sorted(fids):
            if (rel, fid) not in inside:
                out.append({"document": rel, "function": fid, "reason": "outside"})
    return out


LEXICAL = "spec/M2/lib/evidence_lexical.json"
PAR_BASIS = Path("spec") / "M3" / "lib" / "par_basis.json"
FIXTURE_ADOPTION = "tests_m3/fixtures/par_linked/derive_extracted.json"
FIXTURE_LINK = "tests_m3/fixtures/par_linked/link.json"
# holon-facts/0.3 and linked-document vocabulary that generic code may quote although a target uses the word as a
# name (the Go cache field's conditions mention "len"; a record field is called "version")
GENERIC_WORDS = {"version", "len", "byte", "index", "param", "field", "const", "unknown", "slot", "bytes", "record",
                 "encoder", "decoder", "loader", "predicate", "patch", "Bytes"}


def target_names(root: Path = ROOT) -> set[str]:
    """Every name the M3 components and the linked fixture give (function names and code ids, Go method and type
    names, carrier ids, record fields, roles), derived from the documents, never hand-listed."""
    names: set[str] = set()
    for comp in components(root) + components(root, FIXTURE_ADOPTION, FIXTURE_LINK):
        names.add(comp["role"])
        for cid, c in comp["carriers"].items():
            names.add(cid)
            names |= {f["name"] for f in c.get("fields", [])}
            names |= {f["name"].rsplit(".", 1)[-1] for f in c.get("fields", [])}
            names |= set(c.get("domains") or [])
        for name, f in comp["functions"].items():
            names.add(name)
            names.add(code_name(f))
            names |= set(code_name(f).split("."))
    return {n for n in names if isinstance(n, str) and n}


def _inputs(root: Path, rels: list[str]) -> list[dict]:
    return [{"path": r, "sha256": sha256_file(Path(root) / r)} for r in sorted(set(rels))]


def par_basis_doc(root: Path = ROOT) -> dict:
    """The content of spec/M3/lib/par_basis.json without its "doc": every Morph count, law, reason, outcome and level
    this contract predicts, computed by rules X0-X9 and P0-P12 from the committed inputs listed with their sha256."""
    root = Path(root)
    adopted = adoption(root)["documents"]
    out = {"par_basis_version": "holon-i24-par-basis/0.1",
           "inputs": _inputs(root, [ADOPTION.as_posix(), LINK.as_posix(), LEXICAL] + list(adopted)),
           "edge_kinds": list(P.CYCLE_KINDS), "components": {}}
    tot = {"E": 0, "V": 0, "kappa": 0, "rank": 0, "laws": 0}
    for comp in components(root):
        diag = diagram(comp)
        ats = atoms(comp, diag)
        exp = expected(comp, diag, ats)
        cb = exp["cycle"]
        laws = {}
        for lid, law in sorted(exp["laws"].items()):
            full = dict(law, law_id=lid)
            st = decide(comp, full)["status"]
            lv = law_levels(diag, ats, full)
            laws[lid] = {"subform": law["subform"], "status": st, "levels": lv, "triage": triage(st, lv)}
        reasons: dict[str, int] = {}
        dups = {}
        for b in exp["basis"]:
            if b["reason"]:
                reasons[f"{b['subform']}/{b['reason']}"] = reasons.get(f"{b['subform']}/{b['reason']}", 0) + 1
            dups.update(b["duplicates"])
        kinds: dict[str, int] = {}
        for a in ats:
            k = a["level"] + (f"/{a['via']['kind']}" if a["level"] == "E1" else "")
            kinds[k] = kinds.get(k, 0) + 1
        out["components"][comp["component"]] = {
            "facts": facts_path(comp["component"]), "linked_carrier": comp["linked_carrier"],
            "tag_index": comp["tag_index"],
            "carriers": {cid: c["kind"] for cid, c in comp["carriers"].items()},
            "functions": {n: {"kind": f["kind"], "from": f["from"], "to": f.get("to"), "versions": label(f["versions"]),
                              "source": f["source"]} for n, f in comp["functions"].items()},
            "cycle": {k: cb[k] for k in ("E", "V", "kappa", "rank", "tree", "non_tree")},
            "atoms": dict(sorted(kinds.items())), "laws": laws, "reasons": dict(sorted(reasons.items())),
            "duplicates": dict(sorted(dups.items()))}
        for k in ("E", "V", "kappa", "rank"):
            tot[k] += cb[k]
        tot["laws"] += len(laws)
    out["total"] = tot
    out["uncovered"] = uncovered(root)
    return out


def backtest_map_doc(root: Path = ROOT) -> dict:
    """The content of spec/M3/lib/backtest_map.json without its "doc" (rule B1)."""
    root = Path(root)
    mu = backtest_map(root)
    return {"map_version": "holon-backtest-map/0.1", "against": "M0", "hand": HAND,
            "inputs": _inputs(root, [HAND, ADOPTION.as_posix(), LINK.as_posix()] + list(adoption(root)["documents"])),
            "components": [c["component"] for c in components(root)], **mu}


def _calls(t) -> set[str]:
    if isinstance(t, list):
        return set().union(set(), *(_calls(x) for x in t))
    if isinstance(t, dict):
        s = {t["call"]} if isinstance(t.get("call"), str) else set()
        return s.union(*(_calls(v) for v in t.values()))
    return set()


def backtest_expected(root: Path = ROOT) -> dict:
    """B5: the back-test table's rows, gaps and blockers as rules B1-B4 give them (statuses from laws/M0 records and
    decide())."""
    from tests_m3._m3 import laws, records
    mu = backtest_map(root)
    comp = components(root)[0]
    diag = diagram(comp)
    exp = expected(comp, diag, atoms(comp, diag))
    m0, r0 = laws("M0", root), records("M0", root)
    rows, gaps = [], []
    for old_id, old in sorted(m0.items()):
        hits = [lid for lid, law in sorted(exp["laws"].items()) if paired(old, dict(law, law_id=lid), mu)]
        new = hits[0] if len(hits) == 1 else None
        row = {"old": old_id, "old_status": r0[old_id]["status"], "new": new}
        if new:
            bs = bridges(old, comp, mu, root)
            new_status = decide(comp, dict(exp["laws"][new], law_id=new))["status"]
            if all(b["status"] == "PROVED" for b in bs):
                acc = "bridges"
            elif new_status == "REFUTED" and row["old_status"] == "REFUTED" and _transfers(old, comp, exp, new, mu,
                                                                                          root):
                acc = "witness"   # B4(b): the M3 counter-witness, moved by mu, refutes the M0 law on the hand model
            else:
                acc = None
            row.update(new_status=new_status, bridges=[(b["fn"], b["image"], b["status"]) for b in bs],
                       acceptance=acc, implication="accepted" if acc else "missing")
            row["same_status"] = row["new_status"] == row["old_status"]
            if not acc:
                gaps.append({"id": f"gap:M0:{old_id}", "law": old_id, "kind": "implication"})
        else:
            row.update(new_status=None, bridges=[], acceptance=None, implication=None, same_status=None)
            imgs = {mu["functions"][g] for g in _calls(old["statement"]) if mu["functions"].get(g)}
            cands = [lid for lid, law in exp["laws"].items() if law["subform"] == old["subform"]
                     and imgs <= _calls(law["statement"])]
            v = None
            for a in old["statement"]["assume"]:
                if a["eq"][0].get("field") == "version":
                    v = int(a["eq"][1]["bytes"], 16)
            at_v = [lid for lid in cands if v is not None and lid.endswith(f"_v{v}")]
            gaps.append({"id": f"gap:M0:{old_id}", "law": old_id, "kind": "rule",
                         "candidates": sorted(at_v or cands)})
        rows.append(row)
    return {"rows": rows, "gaps": gaps, "exit_blockers": sorted(g["id"] for g in gaps)}
