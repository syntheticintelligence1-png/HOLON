"""The static role inferencer (I104; rules R1-R3 of tests_m6/test_i104_roles.py).

Input: extracted documents (paths relative to a root). Each is classified by its own shape:
  go           holon-facts/0.3 with go.functions (the Go frontend)
  layout       holon-facts/0.3 with functions and types and no go section (the Solidity layout frontend, I17)
  transitions  a document with actions (the Solidity transitions frontend; I105's Go state machines share the IR)

Rules of inference (each role records its rule and the facts it rests on):

  link_tag_length   a Solidity loader edge of a layout document and a Go tagged predicate (go.codecs.predicates) whose
                    accepted (first byte, length) pairs share at least one pair, read by holon.frontends.link's own
                    readers. An edge that accepts every first byte has no tag and is no candidate. Per edge, the Go
                    predicate with equal pair sets first, then the most shared pairs; ties: the Go document with the
                    most encoders and decoders (what the codec layer builds the component from), then the smaller
                    document (fewer functions), then the path.
  link_value        a Solidity constant and a Go package variable whose bytes, read by holon.frontends.link, are equal
                    (same width, same value), the value having at least two distinct bytes (a constant fill is no
                    evidence). Ties among value-equal variables: the name overlap of the two names (a tie-breaker
                    only), then the smaller document, then the path. Such a link is equal by construction: it adds the
                    link to the diagram but cannot detect a value mismatch (a coverage limit, never a false finding).
  go_ops_carrier    holon.diagram.goops's own definition applied to every carrier type: a Go type T such that some
                    function of the document takes exactly one parameter of type T and returns error last. Builtin
                    and standard-library types are no carriers (their values are not the system's data): a type is
                    the system's when its package is one of the document's packages or its module path has a host. The
                    sidecar names one document: the one with the most ops, ties by path. A carrier the goops layer
                    refuses (a name clash) is listed as rejected. reach is not inferred: the component records
                    "inferred" and every value of the carrier is taken as environment-supplied, an over-approximation.
  gox_document      the Go document whose go_round_trip and go_branch bases (holon.gox.basis, as they stand) have the
                    most elements without a reason; ties by path. No compression role is inferred, so no go_branch law
                    takes the HypZ_len premise (no premise is ever added).
  hash_store        go_recompute's two sides, as holon.gox.basis accepts them: the Go functions of the gox document
                    with exactly one non-error return of the extraction config's hash primitive over one preimage, and
                    a Solidity action's store of keccak256 over a memory slice. One role per store site (its first
                    action by name).
  transitions_documents   the typed sidecars (sort_types, disch, undo, fact) over every transitions document, with no
                    hypothesis: DISCH and FACT hypotheses are premises and are never inferred; UNDO's action pairs and
                    FACT's commitments are found by those rules' own generators from the documents.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..frontends import link as LK

REACH = ("inferred by holon roles (rule go_ops_carrier): every value of the carrier is taken as supplied by the "
         "environment; whether it is in fact external is not inferred")
GENERIC_SEARCH = {"prefix_depth": 3, "max_prefixes": 3000, "neighbourhood_insertion_length_max": 2,
                  "neighbourhood_prefixes_per_entry_point_max": 20000}
GENERIC_UNDO_SEARCH = {"prefix_depth": 3, "max_prefixes": 3000, "continuation_depth": 2, "max_candidates": 200000}
BUILTIN = {"bool", "byte", "rune", "string", "error", "int", "int8", "int16", "int32", "int64", "uint", "uint8",
           "uint16", "uint32", "uint64", "uintptr", "float32", "float64", "complex64", "complex128", "any",
           "interface{}"}


class RolesError(ValueError):
    pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def ident(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]+", "_", s).strip("_")
    return out if out and not out[0].isdigit() else "r_" + out


def snake(s: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s).lower()


def tokens(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", snake(s).lower()) if t}


class Doc:
    def __init__(self, rel: str, raw: bytes):
        self.rel, self.raw = rel, raw
        try:
            self.doc = json.loads(raw)
        except ValueError as e:
            raise RolesError(f"{rel}: not JSON ({e})") from e
        d = self.doc if isinstance(self.doc, dict) else {}
        go = d.get("go")
        if isinstance(go, dict) and isinstance(go.get("functions"), dict):
            self.kind = "go"
        elif isinstance(d.get("actions"), list):
            self.kind = "transitions"
        elif isinstance(d.get("functions"), dict) and "types" in d:
            self.kind = "layout"
        else:
            self.kind = "other"

    @property
    def size(self) -> int:
        if self.kind == "go":
            return len(self.doc["go"]["functions"])
        return len(self.doc.get("functions") or self.doc.get("actions") or [])


def load(root: Path, rels: list) -> list:
    out = []
    for rel in rels:
        p = Path(root) / rel
        if not p.is_file():
            raise RolesError(f"{rel}: missing")
        out.append(Doc(rel, p.read_bytes()))
    return out


def role(sidecar: str, rid: str, rule: str, facts: list, **body) -> dict:
    return {"sidecar": sidecar, "id": rid, "roles_source": "static",
            "evidence": {"rule": rule, "facts": sorted(set(facts))}, **body}


# ====================================================================== link roles
def _codec_facts(g) -> int:
    """The encoders and decoders of a Go document: what the codec layer builds a link role's component from."""
    c = g.doc["go"].get("codecs") or {}
    return len(c.get("encoders") or []) + len(c.get("decoders") or [])


def _tag_gate(pairs: list) -> bool:
    return bool(pairs) and len({p[0] for p in pairs}) < 256


def link_roles(docs: list) -> list:
    out = []
    gos = [d for d in docs if d.kind == "go"]
    preds = []
    for g in gos:
        names = [str(p.get("function", "")).rsplit(".", 1)[-1]
                 for p in ((g.doc["go"].get("codecs") or {}).get("predicates") or [])]
        for n in sorted(set(names)):
            try:
                b = LK.predicate_pairs(g.doc, n)
            except (LK.LinkError, TypeError, KeyError):
                continue
            if b:
                preds.append((g, n, b))
    for lay in [d for d in docs if d.kind == "layout"]:
        for edge in sorted(lay.doc.get("functions") or {}):
            try:
                a = LK.loader_pairs(lay.doc, edge)
            except (LK.LinkError, KeyError, TypeError, ValueError):
                continue
            if not _tag_gate(a):
                continue
            cands = []
            for g, n, b in preds:
                common = [x for x in b if x in a]
                if common:
                    cands.append(((0 if a == b else 1), -len(common), -_codec_facts(g), g.size, g.rel, n, g,
                                  len(common)))
            if not cands:
                continue
            c = sorted(cands, key=lambda x: x[:6])[0]
            g, n = c[6], c[5]
            out.append(role("link", ident(f"link_{edge}_{n}"), "link_tag_length",
                            [f"{lay.rel}#functions.{edge}", f"{g.rel}#go.codecs.predicates.{n}"],
                            solidity={"document": lay.rel, "edge": edge,
                                      "fact": "accepted (first byte, length) pairs of the loader's ok paths"},
                            go={"document": g.rel, "function": n,
                                "fact": "accepted (tag, length) pairs of the tagged predicate"},
                            detail={"shared_pairs": c[7], "equal_sets": c[0] == 0, "codec_facts": -c[2]}))
    for t in [d for d in docs if d.kind == "transitions"]:
        for cname, val in sorted((t.doc.get("constants") or {}).items()):
            if not (isinstance(val, str) and re.fullmatch(r"0x([0-9a-f]{2})+", val)):
                continue
            if len(set(bytes.fromhex(val[2:]))) < 2:
                continue
            cands = []
            for g in gos:
                for e in g.doc["go"].get("globals") or []:
                    q = e.get("global") if isinstance(e, dict) else None
                    if not isinstance(q, str):
                        continue
                    try:
                        v = LK.global_value(g.doc, q)
                    except (LK.LinkError, TypeError, KeyError):
                        continue
                    if v != val:
                        continue
                    short = q.rsplit(".", 1)[-1]
                    try:
                        key = short if LK.global_value(g.doc, short) == v and \
                            sum(1 for x in g.doc["go"]["globals"] if str(x.get("global", "")).endswith("." + short)
                                or x.get("global") == short) == 1 else q
                    except LK.LinkError:
                        key = q
                    cands.append((-len(tokens(cname) & tokens(short)), g.size, g.rel, q, g, key))
            if not cands:
                continue
            c = sorted(cands, key=lambda x: x[:4])[0]
            g, key = c[4], c[5]
            out.append(role("link", ident(f"link_{cname}_{key.rsplit('.', 1)[-1]}"), "link_value",
                            [f"{t.rel}#constants.{cname}", f"{g.rel}#go.globals.{c[3]}"],
                            solidity={"document": t.rel, "constant": cname}, go={"document": g.rel, "global": key},
                            detail={"width": (len(val) - 2) // 2, "equal_by_construction": True}))
    return _unique_ids(out)


def _unique_ids(rs: list) -> list:
    seen: dict = {}
    for r in rs:
        k = (r["sidecar"], r["id"])
        if k in seen:
            seen[k] += 1
            r["id"] = f"{r['id']}_{seen[k]}"
        else:
            seen[k] = 0
    return rs


# ====================================================================== Go-op components
def _carrier_ok(t: str, own: set) -> bool:
    base = t
    while base.startswith(("*", "[]")):
        base = base[1:] if base.startswith("*") else base[2:]
    if base in BUILTIN or "." not in base or base.startswith(("map[", "func", "chan ", "interface", "struct")):
        return False
    pkg = base.rsplit(".", 1)[0]
    return pkg in own or "." in pkg.split("/", 1)[0]


def go_ops_roles(docs: list) -> tuple[str | None, list, list]:
    from ..diagram import goops as GO
    from ..diagram.linked import LinkedError, SidecarError
    per_doc, rejected = [], []
    for g in [d for d in docs if d.kind == "go"]:
        carriers = sorted({f["params"][0].get("type") for f in g.doc["go"]["functions"].values()
                           if len(f.get("params") or []) == 1 and (f.get("results") or [None])[-1] == "error"
                           and isinstance(f["params"][0].get("type"), str)})
        own = {p if isinstance(p, str) else p.get("path") for p in (g.doc["go"].get("packages") or [])}
        comps = []
        for t in carriers:
            if not _carrier_ok(t, own):
                continue
            try:
                cid = GO.carrier_id(t)
                d = GO.document("c", {"carrier": t, "reach": REACH}, g.rel, g.raw, g.doc)
            except (LinkedError, SidecarError) as e:
                rejected.append({"document": g.rel, "carrier": t, "reason": str(e)})
                continue
            comps.append((t, cid, sorted(op["source"] for op in d["ops"].values())))
        if comps:
            per_doc.append((-sum(len(c[2]) for c in comps), g.rel, g, comps))
    if not per_doc:
        return None, [], rejected
    _, rel, g, comps = sorted(per_doc, key=lambda x: x[:2])[0]
    out = []
    for t, cid, ops in comps:
        out.append(role("go_ops", ident(f"{snake(cid)}_ops"), "go_ops_carrier",
                        [f"{rel}#go.functions.{o}" for o in ops], carrier=t, reach=REACH,
                        detail={"ops": ops}))
    return rel, _unique_ids(out), rejected


# ====================================================================== the gox document and recompute roles
class _Cx:
    """The parts of holon.gox.basis.Ctx its bases read, built from a document without a sidecar."""

    def __init__(self, doc: Doc, config: dict):
        self.doc, self.config = doc.doc, config
        self.compression = {"codec": {"enc": None}}
        self.side = {"hypz_len": None, "recompute": {}}

    @property
    def fns(self):
        return self.doc["go"]["functions"]

    def hash_prims(self) -> set:
        return {n for n, p in (self.config.get("primitives") or {}).items() if isinstance(p, dict)
                and p.get("kind") == "hash"}


def go_config_of(root: Path, g: Doc) -> tuple[str | None, dict]:
    rel = (((g.doc.get("extraction") or {}).get("config")) or {}).get("path")
    if isinstance(rel, str) and (Path(root) / rel).is_file():
        try:
            return rel, json.loads((Path(root) / rel).read_text())
        except ValueError:
            pass
    return None, {}


def _keccak_mem(v) -> bool:
    return isinstance(v, list) and v[:1] == ["keccak256"] and len(v) > 1 and isinstance(v[1], list) \
        and v[1][:1] == ["slice"] and isinstance(v[1][1], list) and v[1][1][:1] == ["mem"]


def gox_roles(root: Path, docs: list) -> tuple[dict | None, list]:
    from ..gox import basis as B
    cands = []
    for g in [d for d in docs if d.kind == "go"]:
        cfg_rel, cfg = go_config_of(root, g)
        cx = _Cx(g, cfg)
        try:
            n = sum(1 for e in B.round_trips(cx) + B.branches(cx) if not e.get("reason"))
        except (KeyError, TypeError, IndexError, ValueError, AttributeError):
            continue
        hp = cx.hash_prims()
        rec = []
        for fn, f in sorted(cx.fns.items()):
            rets = B._hash_returns(f, hp)
            if len(rets) != 1:
                continue
            arg = rets[0][0]["returns"][0][2]
            pre = arg[0][1][0] if (len(arg) == 1 and isinstance(arg[0], list) and arg[0][:1] == ["varargs"]
                                   and len(arg[0][1]) == 1) else None
            if pre is not None and not B._has(pre, "alloc"):
                rec.append(fn)
        if n or rec:
            cands.append((-n, -len(rec), g.rel, g, cfg_rel, rec, n))
    if not cands:
        return None, []
    _, _, rel, g, cfg_rel, rec, n = sorted(cands, key=lambda x: x[:3])[0]
    roles = [role("go_laws", "document", "gox_document", [rel], detail={"basis_elements": n, "config": cfg_rel})]
    stores: dict = {}
    for t in [d for d in docs if d.kind == "transitions"]:
        for a in sorted(t.doc.get("actions") or [], key=lambda a: str(a.get("name"))):
            for m in a.get("mstores") or []:
                if _keccak_mem(m.get("value")) and isinstance(m.get("src"), str):
                    stores.setdefault((t.rel, m["src"]), a["name"])
    recompute = {}
    if rec:
        for (trel, src), act in sorted(stores.items()):
            rid = ident("hash_" + src.rsplit("/", 1)[-1].replace(".sol", "").replace(":", "_"))
            r = role("go_laws", rid, "hash_store",
                     [f"{rel}#go.functions.{fn}" for fn in rec] + [f"{trel}#actions.{act}.mstores.{src}"],
                     go={"document": rel, "functions": rec},
                     solidity={"document": trel, "action": act, "store": src})
            roles.append(r)
            recompute[rid] = r
    return {"document": rel, "config": cfg_rel, "recompute": recompute}, _unique_ids(roles)


# ====================================================================== everything
def infer(root: Path, rels: list) -> dict:
    docs = load(root, rels)
    out = {"docs": docs, "roles": [], "rejected": []}
    out["roles"] += link_roles(docs)
    ops_doc, ops, rej = go_ops_roles(docs)
    out["go_ops_document"] = ops_doc
    out["roles"] += ops
    out["rejected"] += rej
    gox, groles = gox_roles(root, docs)
    out["gox"] = gox
    out["roles"] += groles
    trans = sorted(d.rel for d in docs if d.kind == "transitions")
    out["transitions"] = trans
    if trans:
        out["roles"].append(role("typed", "documents", "transitions_documents", trans))
    return out
