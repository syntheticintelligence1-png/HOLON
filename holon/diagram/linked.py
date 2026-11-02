"""The linked codec layer (BUILD_PLAN I24; whitepaper §10.1 Linking, §10.2 layout algebra, Def 4.1-4.5). The contract is
the docstring of tests_m3/test_derive_par.py, rules X0-X7 (rule X9, deciding laws, is holon.gen.linked).

  python -m holon codecs --milestone M [--root DIR] [--adoption PATH] [--link PATH] [--out DIR] [--check]

writes <out, default <root>/gen/<M>/codec>/<role>.json: the linked codec document of every component (rule X1) of the
adoption sidecar (default spec/<M>/lib/derive_extracted.json: the extracted holon-facts/0.3 documents a milestone
adopts) and the link sidecar (default spec/<M>/lib/link.json: I19's link roles), and removes a stale <role>.json.
Exit 0 written; 1 (--check, nothing written) the files differ from a fresh build; 2 refused, nothing written (a
sidecar or document missing or malformed); 3 a construct the layer refuses, named, nothing written.

What a component is (X1). One per link role whose Solidity source names a loader edge of a Solidity layout document
("edge") and whose Go source names a tagged predicate of a Go document ("function": the last name segment of one
go.codecs.predicates entry), both documents adopted. The loader's input type (Solidity) and the predicate's parameter
type (Go) are taken as one carrier, the linked carrier, named after its Solidity member (X2). The component holds every
Solidity function whose input or option-stripped output is that member, every Go encoder whose result is the Go
member, the patches of those encoders, and every Go decoder and predicate of the Go member. Constant and global roles
compare values (holon.frontends.link) and form no component; what no component covers is listed by uncovered().

Names (X2), layouts and records (X3), versions (X4) and values (X5) follow the contract; diagram() is rule X6 (the
holon-diagram/0.1 vocabulary), atoms() rule X7 (E1 by position, E2 written and read bytes, E6 through the I14
lexicon). Nothing here names a target: every name comes from the sidecars and the documents they list.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from ..frontends.go.document import encoder_layout

ROOT = Path(__file__).resolve().parents[2]
LINKED_VERSION = "holon-linked/0.1"
DIAGRAM_VERSION = "holon-diagram/0.1"
FACTS03 = "holon-facts/0.3"
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GO_METHOD = re.compile(r"\((\*?)(.*)\)\.([^.()]+)")
MAYBE = re.compile(r"Maybe<(.+)>")


class LinkedError(ValueError):
    """A construct the linked codec layer refuses (exit 3, named)."""


class SidecarError(ValueError):
    """A sidecar or document missing or malformed (exit 2)."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _read(root: Path, rel: str) -> tuple[bytes, dict]:
    p = Path(root) / rel
    try:
        raw = p.read_bytes()
    except OSError as e:
        raise SidecarError(f"{rel}: unreadable ({type(e).__name__}: {e})") from e
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise SidecarError(f"{rel}: not JSON ({e})") from e
    if not isinstance(doc, dict):
        raise SidecarError(f"{rel}: not a JSON object")
    return raw, doc


def default_sidecars(milestone: str) -> tuple[str, str]:
    return (f"spec/{milestone}/lib/derive_extracted.json", f"spec/{milestone}/lib/link.json")


# ====================================================================== names (X2)
def go_name(fid: str) -> str:
    """"(pkg.T).M" and "(*pkg.T).M" -> "T_M"; "pkg.F" -> "F" (T and F the text after the last ".")."""
    m = GO_METHOD.fullmatch(fid)
    name = f"{m.group(2).rsplit('.', 1)[-1]}_{m.group(3)}" if m else fid.rsplit(".", 1)[-1]
    if not NAME.match(name):
        raise LinkedError(f"Go function {fid!r} gives the name {name!r}, which is not an identifier")
    return name


def go_type(t: str) -> str:
    """A Go type without its leading "*" and its package path."""
    name = t.lstrip("*").rsplit(".", 1)[-1]
    if not NAME.match(name):
        raise LinkedError(f"Go type {t!r} gives the carrier id {name!r}, which is not an identifier")
    return name


def strip_option(t: str) -> str:
    m = MAYBE.fullmatch(t)
    return m.group(1) if m else t


def label(vs) -> str | None:
    """A version set as a diagram version label: maximal runs "a..b" (two or more values) or "a", joined by ","."""
    if vs is None:
        return None
    xs = sorted(set(vs))
    out, i = [], 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
            j += 1
        out.append(f"{xs[i]}..{xs[j]}" if j > i else f"{xs[i]}")
        i = j + 1
    return ",".join(out)


# ====================================================================== conditions (X4, X5)
def eval_sol(e, env: dict):
    """A Solidity-document condition (the I17 DSL) under env {name: int, ("len", x): int, ("byte", x, k): int}: an int
    (booleans as 0/1), or None when it mentions something env does not give."""
    if isinstance(e, bool):
        return int(e)
    if isinstance(e, int):
        return e
    if isinstance(e, str):
        return env.get(e)
    if not isinstance(e, list) or not e:
        return None
    op = e[0]
    if op == "len" and len(e) == 2:
        return env.get(("len", e[1]))
    if op == "byte" and len(e) == 3:
        return env.get(("byte", e[1], e[2]))
    if op == "!" and len(e) == 2:
        x = eval_sol(e[1], env)
        return None if x is None else int(not x)
    if op in ("||", "&&"):
        xs = [eval_sol(a, env) for a in e[1:]]
        if op == "||":
            if any(x for x in xs if x is not None):
                return 1
            return None if None in xs else 0
        if any(x == 0 for x in xs):
            return 0
        return None if None in xs else 1
    if op in ("<=", "<", ">=", ">", "==", "!=") and len(e) == 3:
        a, b = eval_sol(e[1], env), eval_sol(e[2], env)
        if a is None or b is None:
            return None
        return int({"<=": a <= b, "<": a < b, ">=": a >= b, ">": a > b, "==": a == b, "!=": a != b}[op])
    return None


def eval_go(e, env: dict, param: str):
    """A Go path atom or term (I18) under env {("len",): int, ("index", k): int}: an int, or None when unknown."""
    if not isinstance(e, list) or not e:
        return None
    op = e[0]
    if op == "const" and len(e) == 2 and isinstance(e[1], int) and not isinstance(e[1], bool):
        return e[1]
    if op == "len" and len(e) == 2 and e[1] == ["param", param]:
        return env.get(("len",))
    if (op == "index" and len(e) == 3 and e[1] == ["param", param] and isinstance(e[2], list) and len(e[2]) == 2
            and e[2][0] == "const"):
        return env.get(("index", e[2][1]))
    if op in ("<=", "<", ">=", ">", "==", "!=") and len(e) == 3:
        a, b = eval_go(e[1], env, param), eval_go(e[2], env, param)
        if a is None or b is None:
            return None
        return int({"<=": a <= b, "<": a < b, ">=": a >= b, ">": a > b, "==": a == b, "!=": a != b}[op])
    return None


def _mentions(e, pred) -> bool:
    if pred(e):
        return True
    return isinstance(e, list) and any(_mentions(x, pred) for x in e)


def sol_input_names(conds: list) -> list[str]:
    """The input names a Solidity condition list reads through ["len", x] or ["byte", x, k], sorted."""
    out: set = set()

    def walk(e):
        if isinstance(e, list) and e:
            if e[0] in ("len", "byte") and len(e) >= 2 and isinstance(e[1], str):
                out.add(e[1])
            for x in e[1:]:
                walk(x)
    for c in conds:
        walk(c)
    return sorted(out)


def sol_tag_versions(ok: list[list], tag: int) -> list[int] | None:
    """X4, a Solidity loader: the values of its input's tag byte at which some ok path's condition has no false atom
    among those that mention only that byte; None when no ok condition reads an input byte or length."""
    names = sol_input_names(ok)
    if not names:
        return None
    x = names[0]
    out = set()
    for v in range(256):
        for cond in ok:
            if all(eval_sol(a, {("byte", x, tag): v}) != 0 for a in cond):
                out.add(v)
    return sorted(out)


def go_tag_versions(ok: list[list], param: str, tag: int) -> list[int] | None:
    """X4, a Go decoder or predicate: the values of its parameter's tag byte at which some ok path's condition has no
    false atom among those that mention only that byte; None when no ok condition mentions the tag byte."""
    def is_tag(e):
        return isinstance(e, list) and len(e) == 3 and e[0] == "index" and e[1] == ["param", param] \
            and e[2] == ["const", tag]
    if not any(_mentions(c, is_tag) for c in ok):
        return None
    out = set()
    for v in range(256):
        for cond in ok:
            if all(eval_go(a, {("index", tag): v}, param) != 0 for a in cond):
                out.add(v)
    return sorted(out)


# ====================================================================== layouts and records (X3)
def _sol_op_cells(op: dict) -> list[list]:
    cells: list[list] = []
    for s in op.get("src") or []:
        if "field" in s:
            cells += [["field", s["field"], k] for k in range(s["from"], s["from"] + s["len"])]
        elif "zeros" in s:
            cells += [["const", 0]] * s["zeros"]
        elif "const" in s:
            cells += [["const", c] for c in (s["const"] if isinstance(s["const"], list) else [s["const"]])]
        else:
            raise LinkedError(f"a store at offset {op.get('offset')} has a source {s} that is no field, zeros or "
                              "constant cell source")
    if len(cells) != op.get("width"):
        raise LinkedError(f"a store at offset {op.get('offset')} writes {len(cells)} cells, width {op.get('width')}")
    return cells


def sol_layout(path: dict) -> list[list]:
    """An ok path's store sequence applied in order to dirty memory (later writes override earlier ones), its first
    "length" cells; a cell no store writes is ["unknown"]."""
    mem: dict[int, list] = {}
    for op in path.get("ops") or []:
        if not isinstance(op.get("offset"), int):
            raise LinkedError(f"a store at a non-constant offset {op.get('offset')!r}")
        for i, c in enumerate(_sol_op_cells(op)):
            mem[op["offset"] + i] = c
    n = path.get("length")
    if not isinstance(n, int):
        raise LinkedError(f"an encoder ok path of non-constant length {n!r}")
    return [mem.get(i, ["unknown"]) for i in range(n)]


def _field_path(t, param: str):
    if t == ["param", param]:
        return []
    if isinstance(t, list) and len(t) == 3 and t[0] == "field":
        inner = _field_path(t[1], param)
        return None if inner is None else inner + [t[2]]
    return None


def go_layout(entry: dict, param: str) -> list[list]:
    """A Go encoder's cells: ["const", v] as extracted, ["byte", <field path of its parameter>, k] as
    ["field", "<path joined by '.'>", k]; any other cell is refused."""
    out = []
    for c in encoder_layout(entry):
        if isinstance(c, list) and len(c) == 2 and c[0] == "const":
            out.append(["const", c[1]])
        elif isinstance(c, list) and len(c) == 3 and c[0] == "byte":
            fp = _field_path(c[1], param)
            if not fp:
                raise LinkedError(f"{entry['function']}: cell {c} is not a byte of a field of its parameter {param}")
            out.append(["field", ".".join(fp), c[2]])
        else:
            raise LinkedError(f"{entry['function']}: cell {c} is neither a constant nor a field byte")
    return out


def record_fields(layouts: list[list[list]]) -> list[dict]:
    """A Go record's fields: the field cells of its encoders' layouts in order of first appearance, width 1 + the
    largest byte index (every smaller index occurring)."""
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
            raise LinkedError(f"record field {f}: bytes {sorted(ks[f])} are not 0..{w - 1}")
        out.append({"name": f, "width": w})
    return out


def _sol_encoder_versions(path: dict, lay: list[list], fields: list[dict], tag: int) -> list[int]:
    """X4, a Solidity encoder ok path: a constant tag cell is its one version; a tag cell that is byte 0 of a one-byte
    record field F has the values of F (0..255) at which no atom of the path's condition mentioning only F is false."""
    c = lay[tag] if tag < len(lay) else ["unknown"]
    if c[0] == "const":
        return [c[1]]
    widths = {f["name"]: f["width"] for f in fields}
    if c[0] != "field" or c[2] != 0 or widths.get(c[1]) != 1:
        raise LinkedError(f"the tag cell {c} of an encoder ok path is neither a constant nor a one-byte record field")
    return [v for v in range(256) if all(eval_sol(a, {c[1]: v}) != 0 for a in path.get("cond") or [])]


# ====================================================================== components (X1)
def load_sidecars(root: Path, adoption_rel: str, link_rel: str) -> tuple[dict, dict, dict]:
    """(adoption sidecar, link roles, {path: sha256} of what was read)."""
    root = Path(root)
    shas = {}
    raw, ad = _read(root, adoption_rel)
    shas[adoption_rel] = sha256_bytes(raw)
    if not isinstance(ad.get("documents"), list) or not all(isinstance(d, str) for d in ad["documents"]):
        raise SidecarError(f"{adoption_rel}: no list of documents")
    raw, ln = _read(root, link_rel)
    shas[link_rel] = sha256_bytes(raw)
    roles = ln.get("roles")
    if not isinstance(roles, dict):
        raise SidecarError(f"{link_rel}: no roles")
    for role, r in roles.items():
        if not isinstance(r, dict) or not all(isinstance(r.get(x), dict) for x in ("solidity", "go")):
            raise SidecarError(f"{link_rel}: role {role} does not name both languages")
        for x in ("solidity", "go"):
            if not isinstance(r[x].get("document"), str):
                raise SidecarError(f"{link_rel}: role {role}: its {x} source names no document")
    return ad, roles, shas


def component_roles(ad: dict, roles: dict) -> list[tuple[str, dict, dict]]:
    """(role, Solidity source, Go source) of every role that forms a component, sorted by role."""
    adopted = set(ad["documents"])
    out = []
    for role, r in sorted(roles.items()):
        s, g = r["solidity"], r["go"]
        if "edge" not in s or "function" not in g:
            continue
        if s["document"] not in adopted or g["document"] not in adopted:
            continue
        out.append((role, s, g))
    return out


def codec_documents(root: Path | str, adoption_rel: str, link_rel: str) -> list[dict]:
    """The linked codec document of every component (rule X1), sorted by role."""
    root = Path(root)
    ad, roles, shas = load_sidecars(root, adoption_rel, link_rel)
    out = []
    docs: dict[str, tuple[bytes, dict]] = {}
    for role, s, g in component_roles(ad, roles):
        for rel in (s["document"], g["document"]):
            if rel not in docs:
                docs[rel] = _read(root, rel)
        doc = component(role, s, g, docs[s["document"]][1], docs[g["document"]][1])
        inputs = {adoption_rel: shas[adoption_rel], link_rel: shas[link_rel]}
        for rel in (s["document"], g["document"]):
            inputs[rel] = sha256_bytes(docs[rel][0])
        doc["inputs"] = [{"path": p, "sha256": h} for p, h in sorted(inputs.items())]
        out.append(doc)
    return out


def _new_record(carriers: dict, cid: str, c: dict) -> dict:
    old = carriers.get(cid)
    if old is None:
        carriers[cid] = c
        return c
    if old.get("kind") != "record" or (old["document"], old["type"]) != (c["document"], c["type"]):
        raise LinkedError(f"carrier id {cid} names two carriers")
    return old


def component(role: str, s: dict, g: dict, sol: dict, go: dict) -> dict:
    """The linked codec document of one component (without "inputs"; rules X1-X5)."""
    if sol.get("facts_version") != FACTS03 or go.get("facts_version") != FACTS03:
        raise SidecarError(f"role {role}: its documents are not {FACTS03}")
    if not isinstance(sol.get("functions"), dict) or not isinstance((go.get("go") or {}).get("codecs"), dict):
        raise SidecarError(f"role {role}: {s['document']} is no Solidity layout document or {g['document']} no Go "
                           "codec document")
    fns = go["go"]["functions"]
    codecs = go["go"]["codecs"]
    preds = [p for p in codecs.get("predicates") or [] if p["function"].rsplit(".", 1)[-1] == g["function"]]
    if len(preds) != 1:
        raise LinkedError(f"role {role}: {len(preds)} Go predicates named {g['function']}")
    pred = preds[0]
    if s["edge"] not in sol["functions"] or sol["functions"][s["edge"]].get("kind") != "loader":
        raise LinkedError(f"role {role}: {s['edge']} is not a loader of {s['document']}")
    loader = sol["functions"][s["edge"]]

    def ptype(fid: str, pname: str) -> str:
        hits = [p["type"] for p in fns[fid]["params"] if p["name"] == pname]
        if len(hits) != 1:
            raise LinkedError(f"{fid}: no parameter {pname}")
        return hits[0]

    go_member = ptype(pred["function"], pred["param"])
    sol_member = loader["from"]
    linked = sol_member
    if not NAME.match(linked):
        raise LinkedError(f"role {role}: the linked carrier {linked!r} is not an identifier")
    tag = pred["tag_index"]
    if not isinstance(tag, int) or isinstance(tag, bool) or tag < 0:
        raise LinkedError(f"role {role}: tag index {tag!r}")
    funcs: dict[str, dict] = {}
    carriers: dict[str, dict] = {linked: {"kind": "bytes", "members": sorted(
        [{"document": s["document"], "type": sol_member}, {"document": g["document"], "type": go_member}],
        key=lambda m: m["document"]), "domains": []}}

    def add(name: str, f: dict) -> None:
        if not NAME.match(name):
            raise LinkedError(f"the function name {name!r} is not an identifier")
        if name in funcs:
            raise LinkedError(f"two functions named {name}")
        funcs[name] = f

    # Solidity functions whose input or option-stripped output is the linked carrier's Solidity member
    for fname, f in sorted(sol["functions"].items()):
        src, tgt = strip_option(f["from"]), strip_option(f["to"])
        if sol_member not in (src, tgt):
            continue
        ok = [p for p in f.get("paths") or [] if p.get("outcome") == "ok"]
        ent = {"kind": f["kind"], "document": s["document"], "source": f["entry"]["fn"], "lang": f["lang"],
               "partial": f["to"].startswith("Maybe<"), "from": linked if src == sol_member else src,
               "to": linked if tgt == sol_member else tgt, "ok": [p.get("cond") or [] for p in ok],
               "sink": f.get("sink")}
        if f["kind"] == "encoder":
            t = (sol.get("types") or {}).get(src) or {}
            if t.get("kind") != "record":
                raise LinkedError(f"{fname}: its input {src} is not a record type")
            rec = _new_record(carriers, src, {"kind": "record", "document": s["document"], "type": src,
                                               "fields": [{"name": x["name"], "width": x["width"]} for x in t["fields"]]})
            layouts: dict[str, list] = {}
            for p in ok:
                lay = sol_layout(p)
                for v in _sol_encoder_versions(p, lay, rec["fields"], tag):
                    if str(v) in layouts and layouts[str(v)] != lay:
                        raise LinkedError(f"{fname}: two ok paths give version {v} different layouts")
                    layouts[str(v)] = lay
            ent["layouts"] = dict(sorted(layouts.items(), key=lambda kv: int(kv[0])))
            ent["versions"] = sorted(int(v) for v in layouts)
        elif f["kind"] == "loader":
            ent["versions"] = sol_tag_versions(ent["ok"], tag)
            carriers[linked]["domains"].append(f"ok_{fname}")
        else:
            raise LinkedError(f"{fname}: a Solidity function of kind {f['kind']!r} is not mapped")
        add(fname, ent)

    # Go encoders whose result is the Go member, one layout each
    enc_names: dict[str, str] = {}
    for e in codecs.get("encoders") or []:
        fid = e["function"]
        results = fns[fid]["results"]
        if not (0 <= e["result"] < len(results)) or results[e["result"]] != go_member:
            continue
        params = fns[fid]["params"]
        if len(params) != 1:
            raise LinkedError(f"{fid}: an encoder of {len(params)} parameters has no record carrier")
        lay = go_layout(e, params[0]["name"])
        name = go_name(fid)
        if name in funcs:
            raise LinkedError(f"{fid}: more than one layout")
        rec = go_type(params[0]["type"])
        tc = lay[tag] if tag < len(lay) else ["unknown"]
        vs = [tc[1]] if tc[0] == "const" else None
        add(name, {"kind": "encoder", "document": g["document"], "source": fid, "lang": "go", "partial": False,
                   "from": rec, "to": linked, "domain": e.get("conds"), "layouts": {str(vs[0]) if vs else "*": lay},
                   "versions": vs})
        enc_names[fid] = name
        _new_record(carriers, rec, {"kind": "record", "document": g["document"], "type": params[0]["type"],
                                    "layouts": []})["layouts"].append(lay)
    for c in carriers.values():
        if c["kind"] == "record" and "layouts" in c:
            c["fields"] = record_fields(c.pop("layouts"))

    # the patches of those encoders: the encoder's layout with each write's cell replaced by the constant written
    for pt in codecs.get("patches") or []:
        if pt["encoder"] not in enc_names:
            continue
        base = funcs[enc_names[pt["encoder"]]]
        lay = [list(c) for c in next(iter(base["layouts"].values()))]
        for w in pt["writes"]:
            if not (0 <= w["index"] < len(lay)):
                raise LinkedError(f"{pt['function']}: a write at {w['index']} outside its encoder's layout")
            lay[w["index"]] = ["const", w["value"]]
        tc = lay[tag] if tag < len(lay) else ["unknown"]
        vs = [tc[1]] if tc[0] == "const" else None
        add(go_name(pt["function"]), {"kind": "encoder", "document": g["document"], "source": pt["function"],
                                      "lang": "go", "partial": False, "from": base["from"], "to": linked,
                                      "patch_of": enc_names[pt["encoder"]], "domain": pt.get("guards"),
                                      "layouts": {str(vs[0]) if vs else "*": lay}, "versions": vs})

    def ok_paths(fid: str) -> list:
        return [p["cond"] for p in fns[fid]["paths"] if p.get("end") == "return" and p.get("error") == "nil"]

    # Go decoders and predicates of the Go member
    for d in codecs.get("decoders") or []:
        fid = d["function"]
        if ptype(fid, d["param"]) != go_member:
            continue
        if len(d["reads"]) != 1:
            raise LinkedError(f"{fid}: a decoder of {len(d['reads'])} reads")
        rd = d["reads"][0]
        slot = f"{linked}@{rd['offset']}+{rd['width']}"
        old = carriers.setdefault(slot, {"kind": "slot", "of": linked, "offset": rd["offset"], "width": rd["width"]})
        if old.get("kind") != "slot":
            raise LinkedError(f"carrier id {slot} names two carriers")
        ok = ok_paths(fid)
        add(go_name(fid), {"kind": "decoder", "document": g["document"], "source": fid, "lang": "go", "partial": True,
                           "from": linked, "to": slot, "read": rd, "param": d["param"], "ok": ok,
                           "versions": go_tag_versions(ok, d["param"], tag)})
    for p in codecs.get("predicates") or []:
        if ptype(p["function"], p["param"]) != go_member:
            continue
        ok = ok_paths(p["function"])
        name = go_name(p["function"])
        add(name, {"kind": "predicate", "document": g["document"], "source": p["function"], "lang": "go",
                   "from": linked, "param": p["param"], "ok": ok, "versions": go_tag_versions(ok, p["param"], tag)})
        carriers[linked]["domains"].append(name)
    carriers[linked]["domains"].sort()
    for cid in carriers:
        if not NAME.match(cid.split("@", 1)[0]):
            raise LinkedError(f"carrier id {cid!r} is not an identifier")
    return {"linked_version": LINKED_VERSION, "component": role, "role": role, "tag_index": tag,
            "linked_carrier": linked, "documents": sorted({s["document"], g["document"]}),
            "carriers": dict(sorted(carriers.items())), "functions": dict(sorted(funcs.items()))}


def is_linked(doc) -> bool:
    return isinstance(doc, dict) and doc.get("linked_version") == LINKED_VERSION


# ====================================================================== what no component covers (X1, G1, G2)
def uncovered(root: Path | str, adoption_rel: str, link_rel: str, comps: list[dict] | None = None) -> list[dict]:
    """A transitions document as a whole (reason "transitions"), and every codec function of an adopted layout or Go
    codec document that no component holds (reason "outside"), sorted by (document, function)."""
    root = Path(root)
    ad, _, _ = load_sidecars(root, adoption_rel, link_rel)
    comps = codec_documents(root, adoption_rel, link_rel) if comps is None else comps
    inside = {(f["document"], f["source"]) for c in comps for f in c["functions"].values()}
    out = []
    for rel in sorted(ad["documents"]):
        _, d = _read(root, rel)
        if (d.get("extraction") or {}).get("kind") == "transitions":
            out.append({"document": rel, "function": None, "reason": "transitions"})
            continue
        if isinstance(d.get("functions"), dict) and "go" not in d:
            for _, f in sorted(d["functions"].items()):
                if (rel, f["entry"]["fn"]) not in inside:
                    out.append({"document": rel, "function": f["entry"]["fn"], "reason": "outside"})
            continue
        cod = (d.get("go") or {}).get("codecs")
        if not isinstance(cod, dict):
            raise SidecarError(f"{rel}: neither a transitions, a layout nor a Go codec document")
        fids = {e["function"] for e in cod.get("encoders") or []} | {x["function"] for x in cod.get("decoders") or []} \
            | {x["function"] for x in cod.get("predicates") or []} | {x["function"] for x in cod.get("patches") or []}
        for fid in sorted(fids):
            if (rel, fid) not in inside:
                out.append({"document": rel, "function": fid, "reason": "outside"})
    return sorted(out, key=lambda u: (u["document"], u["function"] or ""))


# ====================================================================== the diagram (X6)
def diagram(doc: dict, rel: str, sha: str) -> dict:
    """The component's diagram in holon-diagram/0.1 vocabulary: carriers (records with "product", the linked carrier
    an interface iff it has domains, slots, digests), a CODEC edge per function but predicates, and one HASH edge per
    (sink op, source carrier) of the Solidity functions' selected sinks."""
    cars, edges, hashes = [], [], {}
    for cid, c in doc["carriers"].items():
        d = {"id": cid, "cls": "rep", "base_type": cid, "sort_ref": None, "interface": False, "reach": None}
        if c["kind"] == "record":
            d["product"] = [f["name"] for f in c["fields"]]
        elif c["kind"] == "bytes":
            d["interface"] = bool(c["domains"])
            d["reach"] = "external" if c["domains"] else None
            d["domains"] = list(c["domains"])
            d["key_space"] = "byte"
        elif c["kind"] == "slot":
            d["reach"] = "image"
            d["slot_of"] = c["of"]
        cars.append(d)
    ids = set()
    for name, f in doc["functions"].items():
        if f["kind"] == "predicate":
            continue
        e = {"id": f"CODEC.{name}", "kind": "CODEC", "model_fn": name, "src": f["from"], "tgt": f["to"],
             "partial": bool(f["partial"]), "version": label(f["versions"]), "fn_kind": f["kind"],
             "source": [{"fn": f["source"]}], "component": f["document"], "env": False, "pseudo": False,
             "principal_class": None, "access": {"reads": [], "writes": []}}
        if f["kind"] == "loader":
            e["domain"] = f"ok_{name}"
        edges.append(e)
        ids.add(e["id"])
        if f.get("sink"):
            hashes.setdefault((f["sink"]["op"], f["to"]), set()).add(f["document"])
    for (op, src), docs in sorted(hashes.items()):
        if not NAME.match(op):
            raise LinkedError(f"hash op {op!r} is not an identifier")
        eid = f"HASH.{op}"
        if eid in ids:
            raise LinkedError(f"two HASH edges {eid} (one op over two source carriers)")
        ids.add(eid)
        if op in doc["carriers"]:
            raise LinkedError(f"carrier id {op} names two carriers")
        if not any(c["id"] == op for c in cars):
            cars.append({"id": op, "cls": "digest", "base_type": op, "sort_ref": None, "interface": False,
                         "reach": "image"})
        edges.append({"id": eid, "kind": "HASH", "model_fn": None, "src": src, "tgt": op, "partial": False,
                      "version": None, "source": [], "component": sorted(docs)[0] if len(docs) == 1 else None,
                      "env": False, "pseudo": False, "principal_class": None, "access": {"reads": [], "writes": []}})
    return {"diagram_version": DIAGRAM_VERSION, "model": doc["component"], "facts": rel, "facts_sha256": sha,
            "facts_version": LINKED_VERSION, "carriers": sorted(cars, key=lambda c: c["id"]),
            "edges": sorted(edges, key=lambda e: e["id"]), "principal_classes": [], "index_terms": [],
            "coverage_debt": [], "linked_carrier": doc["linked_carrier"], "tag_index": doc["tag_index"],
            "mapped_sections": {"carriers": "records, the linked byte carrier and decoder slots (rule X6)",
                                "functions": "CODEC edges (predicates: domains of the linked carrier) and HASH edges "
                                             "of the selected sinks (rule X6)"}}


# ====================================================================== evidence (X7)
def layout_at(f: dict, v) -> list[list] | None:
    if f.get("versions") is None:
        return next(iter(f["layouts"].values()))
    return f["layouts"].get(str(v))


def recovers(lay: list[list], read: dict) -> str | None:
    """E1 by position (§10.2): the field whose bytes 0..w-1 the layout places, in order, at the read range."""
    o, w = read["offset"], read["width"]
    if o + w > len(lay) or lay[o][0] != "field":
        return None
    f = lay[o][1]
    return f if all(lay[o + k] == ["field", f, k] for k in range(w)) else None


def _ranges(xs: set[int]) -> list[str]:
    ys = sorted(xs)
    out, i = [], 0
    while i < len(ys):
        j = i
        while j + 1 < len(ys) and ys[j + 1] == ys[j] + 1:
            j += 1
        out.append(f"{ys[i]}..{ys[j]}" if j > i else f"{ys[i]}")
        i = j + 1
    return out


def _active(f: dict, v) -> bool:
    return f.get("versions") is None or v in f["versions"]


def atoms(doc: dict, diag: dict, lexicon) -> list[dict]:
    """E1 (inverse, common_decoder), E2 and E6 atoms over a component (rule X7), sorted by id."""
    from .evidence import _atom, e6
    model = doc["component"]
    fs = doc["functions"]
    encs = sorted(n for n, f in fs.items() if f["kind"] == "encoder")
    decs = sorted(n for n, f in fs.items() if f["kind"] == "decoder")
    out, inv = [], {}
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
                out.append(_atom(model, "E1", f"CODEC.{e}", f"CODEC.{d}",
                                 {"kind": "inverse", "version": v, "fields": [fld], "not_recovered": []}, None))
    for i, p in enumerate(encs):
        for q in encs[i + 1:]:
            if fs[p]["to"] != fs[q]["to"]:
                continue
            for v in sorted(set(fs[p]["versions"] or []) & set(fs[q]["versions"] or [])):
                for d in decs:
                    if (p, d, v) in inv and (q, d, v) in inv:
                        out.append(_atom(model, "E1", f"CODEC.{p}", f"CODEC.{q}",
                                         {"kind": "common_decoder", "version": v, "decoder": f"CODEC.{d}",
                                          "fields": [inv[(p, d, v)], inv[(q, d, v)]]}, None))
    for e in encs:
        written: set = set()
        for lay in fs[e]["layouts"].values():
            written |= {i for i, c in enumerate(lay) if c[0] != "unknown"}
        for d in decs:
            if fs[d]["from"] != fs[e]["to"]:
                continue
            rd = fs[d]["read"]
            r = set(range(rd["offset"], rd["offset"] + rd["width"]))
            if written & r:
                out.append(_atom(model, "E2", f"CODEC.{e}", f"CODEC.{d}",
                                 {"carrier": fs[e]["to"], "writes": _ranges(written & r), "reads": _ranges(r & written)},
                                 None))
    out += e6(model, diag, lexicon)
    return sorted(out, key=lambda a: a["id"])


def anchors(diag: dict) -> dict:
    """What laws over a component name (I14's L2 over a linked codec document): its CODEC edges by model function, and
    the domain predicates of its interface carriers with the edges whose domain each is."""
    es = diag["edges"]
    doms = {}
    for c in diag["carriers"]:
        for p in c.get("domains") or []:
            doms[p] = sorted(e["id"] for e in es if e.get("domain") == p)
    return {"codec": {e["model_fn"]: e["id"] for e in es if e["kind"] == "CODEC"}, "domains": dict(sorted(doms.items())),
            "actions": {}, "reasons": {}, "permissionless": [], "observers": {}, "migrations": {}, "consumers": {},
            "carriers": {}, "trans": [], "sites": {}}


# ====================================================================== committed files of a milestone
def codec_dir(milestone: str, root: Path | str = ROOT) -> Path:
    return Path(root) / "gen" / milestone / "codec"


def committed_codecs(milestone: str, root: Path | str = ROOT) -> list[Path]:
    """The linked codec documents of a milestone (gen/<M>/codec/*.json), sorted."""
    return sorted(codec_dir(milestone, root).glob("*.json"))


def milestone_k(milestone: str) -> int | None:
    m = re.fullmatch(r"M(\d+)", milestone or "")
    return int(m.group(1)) if m else None


def linked_milestone(milestone: str) -> bool:
    """Milestones whose diagrams and evidence are over linked codec documents (M3 on, rule X6)."""
    k = milestone_k(milestone)
    return k is not None and k >= 3


def render_all(root: Path, milestone: str, adoption_rel: str, link_rel: str) -> dict[str, str]:
    """{file name: text} of every linked codec document holon codecs writes."""
    texts = {}
    for d in codec_documents(root, adoption_rel, link_rel):
        texts[f"{d['component']}.json"] = dumps(d)
    return texts


def _rel(root: Path, p: str) -> str:
    q = Path(p)
    if q.is_absolute():
        try:
            return q.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            raise SidecarError(f"{p} is not inside the root {root}") from None
    return q.as_posix()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon codecs")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the sidecars and documents (default: this checkout)")
    ap.add_argument("--adoption", help="the adoption sidecar (default spec/<M>/lib/derive_extracted.json)")
    ap.add_argument("--link", help="the link sidecar (default spec/<M>/lib/link.json)")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/codec)")
    ap.add_argument("--check", action="store_true", help="compare a fresh build with the files, writing nothing")
    ap.add_argument("--goops-out", help="output directory of the Go-op documents (default <root>/gen/<M>/goops; I67)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    da, dl = default_sidecars(a.milestone)
    from . import goops as GO
    try:
        texts = render_all(root, a.milestone, _rel(root, a.adoption or da), _rel(root, a.link or dl))
        gtexts = GO.render_all(root, a.milestone)   # I67 (rule Y3 of tests_m3/test_go_loop.py): the Go-op components
    except SidecarError as e:
        print(f"holon codecs: refused: {e}", file=sys.stderr)
        return 2
    except LinkedError as e:
        print(f"holon codecs: refused construct: {e}", file=sys.stderr)
        return 3
    except (KeyError, TypeError, IndexError) as e:
        print(f"holon codecs: refused: a document holds a construct the layer cannot read ({type(e).__name__}: {e})",
              file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else codec_dir(a.milestone, root)
    # the Go-op documents go to --goops-out, by default gen/<M>/goops; with --out alone none is written (rule Y3)
    gout = Path(a.goops_out) if a.goops_out else (None if a.out else GO.goops_dir(a.milestone, root))
    if gout is None:
        gtexts = {}
    if a.check:
        for d, want in ((out, texts), (gout, gtexts)):
            if d is None:
                continue
            have = {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.json"))} if d.is_dir() else {}
            if have != want:
                print(f"holon codecs: {d} differs from a fresh build", file=sys.stderr)
                return 1
        print(f"holon codecs: {out} reproduces ({len(texts)} components), {gout} too ({len(gtexts)} Go-op components)")
        return 0
    for d, want in ((out, texts), (gout, gtexts)):
        if d is None or (not want and not d.is_dir()):
            continue
        d.mkdir(parents=True, exist_ok=True)
        for p in sorted(d.glob("*.json")):
            if p.name not in want:
                p.unlink()
        for name, text in sorted(want.items()):
            (d / name).write_text(text, encoding="utf-8")
            print(f"{name[:-5]}: {d / name}")
    return 0
