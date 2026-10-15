"""holon basis: basis sufficiency, kernel-checked (I42; whitepaper §6 Thm 6.4 and Cor 6.5, §10.3 steps 1-3).

  python -m holon basis --milestone M3 [--root DIR] [--out DIR] [--kernels] [--check]

The contract is the docstring of tests_m3/test_theory_core.py (rules T0-T9). This module:
- reads the linked codec components of a milestone (each byte for byte what holon codecs and holon diagram write now),
  their PAR laws, the versions of their basis elements and the records' statuses (T0);
- builds one instance per PROVED cross-component law: the forward-path diagram rooted at its first record, with both
  encoders, the decoders at its version and the product structure (projections, Some) (T3); a breadth-first spanning
  tree (T4); the available equations (the PROVED laws) and, per non-tree edge, a derivation of its fundamental cycle by
  prefix rewriting (T5, holon.gen.congruence); certificates for constant reads and weak pairs (T6);
- writes each covered instance's statements and their proof by application (T7): every per-edge fact comes from the
  available laws through bridges that only equate pins of one record or a pinned field to its constant, and the
  instance law applies the core's core_parallel_agree (gen/<M>/theory/core, holon.gen.theory);
- writes each instance's semantic canary (T8b): the root cycle at an unpinned start, refuted with a witness that this
  module finds by evaluating the model's two walks with bend (AGENTS rule 5: never an oracle);
- writes the basis document per component and, with --kernels, report.json with every kernel's result (T9).

It names no target: everything specific comes from the documents, the law files and the records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import deque
from pathlib import Path

from . import congruence as CG
from . import theory as TH

BASIS_VERSION = "holon-basis/0.1"
ROOT = Path(__file__).resolve().parents[2]
OWNED = ("core", "lean", "basis")
REPORT = "report.json"
BYTES = "List<&2, U32>"
MAYBE = "Maybe<&2, List<&2, U32>>"
TIMEOUT_S = 900


class Refused(ValueError):
    """An input missing, malformed or stale (exit 2, nothing written)."""


class Construct(ValueError):
    """A construct the rules refuse (exit 3, nothing written)."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _json(p: Path, what: str):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except OSError as e:
        raise Refused(f"{what} is missing: {p}") from e
    except ValueError as e:
        raise Refused(f"{what} is not JSON: {p}: {e}") from e


# ====================================================================== T0: inputs
class Inputs:
    """The milestone's linked components, PAR laws, basis versions, records and registry."""

    def __init__(self, root: Path, milestone: str):
        self.root, self.m = Path(root).resolve(), milestone
        self.comps: list[tuple[str, dict, dict]] = []      # (role, codec document, diagram)
        self.laws: dict[str, dict] = {}
        self.records: dict[str, dict] = {}
        self.versions: dict[str, int | None] = {}
        self.registry: dict[str, str] = {}

    def rel(self, p: Path) -> str:
        return Path(p).resolve().relative_to(self.root).as_posix()

    def status(self, lid: str) -> str | None:
        r = self.records.get(lid)
        return r.get("status") if isinstance(r, dict) else None


def load(root: Path, milestone: str) -> Inputs:
    """Rule T0, refusing a stale codec layer: every codec document and diagram must be what holon codecs and holon
    diagram write now."""
    from ..diagram import DiagramError, linked_diagrams
    from ..diagram import linked as L
    if re.fullmatch(r"M\d+", milestone or "") is None:
        raise Refused(f"{milestone!r} is not a milestone M<k>")
    ins = Inputs(root, milestone)
    root = ins.root
    ad_rel, link_rel = L.default_sidecars(milestone)
    try:
        fresh = L.render_all(root, milestone, ad_rel, link_rel)
    except (L.SidecarError, OSError, ValueError, KeyError) as e:
        raise Refused(f"the linked codec layer cannot be rebuilt: {e}") from e
    have = {p.name: p.read_text(encoding="utf-8") for p in L.committed_codecs(milestone, root)}
    if have != fresh:
        raise Refused(f"gen/{milestone}/codec is stale: it is not what `holon codecs --milestone {milestone}` writes now")
    try:
        dtexts = linked_diagrams(milestone, root)
    except DiagramError as e:
        raise Refused(f"the component diagrams cannot be rebuilt: {e}") from e
    for p in L.committed_codecs(milestone, root):
        doc = json.loads(p.read_text(encoding="utf-8"))
        if not L.is_linked(doc):
            continue
        role = p.stem
        if doc.get("component") != role:
            raise Construct(f"{ins.rel(p)}: its component {doc.get('component')!r} is not its file name")
        dp = root / "gen" / milestone / "diagram" / f"{role}.json"
        if not dp.is_file() or dp.read_text(encoding="utf-8") != dtexts.get(role):
            raise Refused(f"gen/{milestone}/diagram/{role}.json is stale: it is not what `holon diagram --milestone "
                          f"{milestone}` writes now")
        ins.comps.append((role, doc, json.loads(dtexts[role])))
    if not ins.comps:
        raise Refused(f"{milestone}: no linked codec component (gen/{milestone}/codec)")
    for p in sorted((root / "laws" / milestone).glob("L*.json")):
        ins.laws[p.stem] = _json(p, "a law file")
    for p in sorted((root / "results" / milestone).glob("L*.json")):
        ins.records[p.stem] = _json(p, "a record")
    der = _json(root / "laws" / milestone / "DERIVATION.json", "the derivation")
    ins.versions = {e["law_id"]: (e.get("basis") or {}).get("version") for e in der.get("laws", [])}
    reg = _json(root / "laws" / milestone / "REGISTRY.json", "the law registry")
    ins.registry = dict(reg.get("statements") or {})
    return ins


# ====================================================================== T3-T6: the instances
def _versions(label) -> set[int] | None:
    if label is None:
        return None
    s = str(label)
    if ".." in s:
        a, b = s.split("..")
        return set(range(int(a), int(b) + 1))
    return {int(s)}


def _at(label, v: int) -> bool:
    vs = _versions(label)
    return vs is None or v in vs


def _call(t):
    return t.get("call") if isinstance(t, dict) else None


def rt_shape(law: dict):
    """A round trip d(enc(x)) == Some(field F of x): (enc, d, F), or None."""
    c = law["statement"]["claim"].get("eq")
    if not c or len(c) != 2:
        return None
    lhs, rhs = c
    if _call(lhs) is None or len(lhs.get("args", [])) != 1 or _call(lhs["args"][0]) is None:
        return None
    some = rhs.get("some") if isinstance(rhs, dict) else None
    if not isinstance(some, dict) or "field" not in some:
        return None
    return lhs["args"][0]["call"], lhs["call"], some["field"]


def cc_shape(law: dict):
    """A cross-component claim p(h) == q(k) over two record binders: (h, k, p, q), or None."""
    st = law["statement"]
    c = st["claim"].get("eq")
    if not c or len(c) != 2 or len(st["binders"]) != 2:
        return None
    lhs, rhs = c
    if _call(lhs) is None or _call(rhs) is None:
        return None
    h, k = st["binders"]
    if lhs["args"] != [{"var": h["name"]}] or rhs["args"] != [{"var": k["name"]}]:
        return None
    return h, k, lhs["call"], rhs["call"]


def pinned_fields(law: dict) -> dict[tuple[str, str], str]:
    """(binder, field) -> the "0x.." constant a premise equates it to."""
    out = {}
    for a in law["statement"].get("assume", []):
        eq = a.get("eq")
        if not eq or len(eq) != 2:
            continue
        x, y = eq
        if isinstance(x, dict) and "field" in x and isinstance(y, dict) and "bytes" in y:
            out[(x["of"]["var"], x["field"])] = y["bytes"]
    return out


def record_fields(codec: dict, rec: str) -> list[dict]:
    return list(codec["carriers"][rec]["fields"])


def record_width(codec: dict, rec: str) -> int:
    return sum(int(f["width"]) for f in record_fields(codec, rec))


def constant_read(codec: dict, enc: str, d: str, v: int) -> str | None:
    """The "0x.." bytes when enc's layout at v holds only constants in d's read range (T6), else None."""
    try:
        cells = codec["functions"][enc]["layouts"][str(v)]
        r = codec["functions"][d]["read"]
    except KeyError as e:
        raise Construct(f"{enc}/{d}: no layout or read range at version {v}: {e}") from e
    rng = cells[r["offset"]:r["offset"] + r["width"]]
    if len(rng) != r["width"] or any(c[0] != "const" for c in rng):
        return None
    return "0x" + "".join(f"{int(c[1]):02x}" for c in rng)


def spanning_tree(nv: int, edges: list[dict], root: int = 0) -> tuple[list[int], dict[int, list[int]]]:
    """T4: breadth-first from the root over forward edges, a dequeued vertex scanning its outgoing edges in id order."""
    paths, tree, q = {root: []}, [], deque([root])
    while q:
        u = q.popleft()
        for e in edges:
            if e["src"] == u and e["tgt"] not in paths:
                paths[e["tgt"]] = paths[u] + [e["id"]]
                tree.append(e["id"])
                q.append(e["tgt"])
    if len(paths) != nv:
        raise Construct(f"the instance graph is not connected from its root: {nv - len(paths)} vertices unreached")
    return sorted(tree), paths


def instance(ins: Inputs, role: str, codec: dict, diagram: dict, root_law: str) -> dict:
    """Rules T3-T6 for one root law. Keys beyond the document's (T9) start with "_"."""
    facts = f"gen/{ins.m}/codec/{role}.json"
    law = ins.laws[root_law]
    h, k, p, q = cc_shape(law)
    v = ins.versions.get(root_law)
    if v is None:
        raise Construct(f"{root_law}: its basis element has no version (laws/{ins.m}/DERIVATION.json)")
    hrec, krec = h["type"], k["type"]
    decs = sorted((e for e in diagram["edges"] if e["kind"] == "CODEC" and e.get("fn_kind") == "decoder"
                   and _at(e.get("version"), v)), key=lambda e: e["id"])
    slot_of = {e["model_fn"]: e["tgt"] for e in decs}
    slots = sorted(set(slot_of.values()))
    dec_names = [e["model_fn"] for e in decs]

    def rts(enc: str) -> list[tuple[str, str, str]]:
        out = []
        for lid, lw in sorted(ins.laws.items()):
            if lw.get("facts") != facts or lw.get("subform") != "round_trip" or ins.versions.get(lid) != v:
                continue
            shp = rt_shape(lw)
            if shp and shp[0] == enc and shp[1] in slot_of:
                out.append((lid, shp[1], shp[2]))
        return out

    p_rt, q_rt = rts(p), rts(q)
    root_fields = [f["name"] for f in record_fields(codec, hrec) if any(x[2] == f["name"] for x in p_rt)]
    other_fields = [f["name"] for f in record_fields(codec, krec) if any(x[2] == f["name"] for x in q_rt)]

    def field_slot(rt: list, f: str) -> str:
        ss = sorted({slot_of[d] for _, d, ff in rt if ff == f})
        if len(ss) != 1:
            raise Construct(f"{root_law}: field {f} is recovered at {len(ss)} slots (rule T3)")
        return ss[0]

    vertices = [{"id": 0, "kind": "record", "carrier": hrec}, {"id": 1, "kind": "record", "carrier": krec},
                {"id": 2, "kind": "bytes", "carrier": diagram["linked_carrier"]}]
    vid = {}
    for s in slots:
        vid[("slot", s)] = len(vertices)
        vertices.append({"id": len(vertices), "kind": "slot", "carrier": s})
    for side, rec, fields in (("root", hrec, root_fields), ("other", krec, other_fields)):
        for f in fields:
            vid[("field", side, f)] = len(vertices)
            vertices.append({"id": len(vertices), "kind": "field", "carrier": rec, "field": f, "side": side})
    edges = [{"id": 0, "kind": "sigma", "src": 0, "tgt": 1, "law": root_law},
             {"id": 1, "kind": "encoder", "src": 0, "tgt": 2, "fn": p},
             {"id": 2, "kind": "encoder", "src": 1, "tgt": 2, "fn": q}]
    eid = {}
    for d in dec_names:
        eid[("decoder", d)] = len(edges)
        edges.append({"id": len(edges), "kind": "decoder", "src": 2, "tgt": vid[("slot", slot_of[d])], "fn": d})
    for side, fields, rt in (("root", root_fields, p_rt), ("other", other_fields, q_rt)):
        for f in fields:
            fv = vid[("field", side, f)]
            eid[("projection", side, f)] = len(edges)
            edges.append({"id": len(edges), "kind": "projection", "src": 0 if side == "root" else 1, "tgt": fv,
                          "field": f, "side": side})
            eid[("some", side, f)] = len(edges)
            edges.append({"id": len(edges), "kind": "some", "src": fv, "tgt": vid[("slot", field_slot(rt, f))],
                          "field": f, "side": side})
    tree, paths = spanning_tree(len(vertices), edges)
    tset = set(tree)
    non_tree = [e["id"] for e in edges if e["id"] not in tset]
    available = [{"law": root_law, "kind": "root", "lhs": [1], "rhs": [0, 2]}]
    for lid, d, f in p_rt:
        if ins.status(lid) == "PROVED":
            available.append({"law": lid, "kind": "round_trip_p", "lhs": [1, eid[("decoder", d)]],
                              "rhs": [eid[("projection", "root", f)], eid[("some", "root", f)]]})
    for lid, d, f in q_rt:
        if ins.status(lid) == "PROVED":
            available.append({"law": lid, "kind": "round_trip_q", "lhs": [0, 2, eid[("decoder", d)]],
                              "rhs": [0, eid[("projection", "other", f)], eid[("some", "other", f)]]})
    if len({a["law"] for a in available}) != len(available):
        raise Construct(f"{root_law}: one law gives two available equations")
    cycles, uncovered = [], []
    for kk in non_tree:
        e = edges[kk]
        start, goal = paths[e["src"]] + [kk], paths[e["tgt"]]
        der = CG.derivation(start, goal, available)
        cycles.append({"edge": kk, "covered": der is not None, "from": start, "to": goal,
                       "steps": None if der is None else len(der), "derivation": der})
        if der is None:
            uncovered.append(kk)
    pins = pinned_fields(law)
    const_field = {}
    for (b, f), c in pins.items():
        side = "root" if b == h["name"] else "other"
        if ("field", side, f) in vid:
            const_field[vid[("field", side, f)]] = c
    certs, cert_field = [], {}
    for side, enc in (("p", p), ("q", q)):
        for d in dec_names:
            c = constant_read(codec, enc, d, v)
            if c is None:
                continue
            slot = vid[("slot", slot_of[d])]
            hits = sorted(fv for fv, cc in const_field.items() if cc == c and any(
                ed["kind"] == "some" and ed["src"] == fv and ed["tgt"] == slot for ed in edges))
            if hits:
                name = f"const_read_{side}_{d.lower()}_v{v}"
                certs.append({"kind": "constant_read", "side": side, "decoders": [d], "bytes": c, "name": name})
                cert_field[name] = hits[0]
    by_slot: dict[str, list[str]] = {}
    for d in dec_names:
        by_slot.setdefault(slot_of[d], []).append(d)
    for side in ("p", "q"):
        for s in slots:
            ds = sorted(by_slot[s])
            for i in range(len(ds)):
                for j in range(i + 1, len(ds)):
                    certs.append({"kind": "weak_image", "side": side, "decoders": [ds[i], ds[j]], "bytes": None,
                                  "name": f"weak_image_{side}_{ds[i].lower()}_{ds[j].lower()}_v{v}"})
    certs.sort(key=lambda c: c["name"])
    covered = [c["edge"] for c in cycles if c["covered"]]
    return {"name": f"basis_sufficient_{role.lower()}_v{v}", "component": role, "version": v, "root_law": root_law,
            "root": hrec, "other": krec, "p": p, "q": q, "vertices": vertices, "edges": edges, "tree": tree,
            "non_tree": non_tree, "rank": len(edges) - len(vertices) + 1, "kappa": 1, "available": available,
            "cycles": cycles, "uncovered": uncovered, "certificates": certs, "dir": f"basis/{role}_v{v}",
            "status": "uncovered" if uncovered else "emitted", "laws_used": sorted({a["law"] for a in available}),
            "needed": sorted({available[i]["law"] for c in cycles for i, _ in (c["derivation"] or [])}),
            "canary_edge": min(covered) if covered else None, "canary_law": f"canary_unpinned_{role.lower()}_v{v}",
            "_h": h, "_k": k, "_paths": paths, "_cert_field": cert_field, "_pins": pins,
            "_root_width": record_width(codec, hrec), "_other_width": record_width(codec, krec),
            "_root_fields": record_fields(codec, hrec)}


DOC_KEYS = ("name", "component", "version", "root_law", "root", "other", "p", "q", "vertices", "edges", "tree",
            "non_tree", "rank", "kappa", "available", "cycles", "uncovered", "certificates", "dir", "status",
            "laws_used", "needed", "canary_edge", "canary_law")


def instances(ins: Inputs) -> list[dict]:
    """T3: one instance per PROVED cross-component law of each component, sorted by (component, version, root law)."""
    out = []
    for role, codec, diagram in ins.comps:
        facts = f"gen/{ins.m}/codec/{role}.json"
        roots = sorted(lid for lid, lw in ins.laws.items() if lw.get("facts") == facts
                       and lw.get("subform") == "cross_component_codec" and ins.status(lid) == "PROVED"
                       and cc_shape(lw) is not None)
        for lid in roots:
            out.append(instance(ins, role, codec, diagram, lid))
    out.sort(key=lambda i: (i["component"], i["version"], i["root_law"]))
    names = [i["name"] for i in out]
    if len(set(names)) != len(names):
        raise Construct(f"two root laws give one instance name: {sorted(n for n in names if names.count(n) > 1)}")
    return out


def component_inputs(ins: Inputs, role: str, insts: list[dict]) -> list[dict]:
    """T9's inputs of a component: files by sha256, every record of its laws by status."""
    facts = f"gen/{ins.m}/codec/{role}.json"
    mine = sorted(lid for lid, lw in ins.laws.items() if lw.get("facts") == facts)
    files = {facts, f"gen/{ins.m}/diagram/{role}.json", f"gen/{ins.m}/model/{role}.bend",
             f"laws/{ins.m}/DERIVATION.json"}
    files |= {f"laws/{ins.m}/{lid}.json" for lid in mine}
    for inst in insts:
        if inst["component"] == role:
            for lid in inst["laws_used"]:
                art = _artifacts(ins, lid)
                files |= {art["laws"], art["proof"]}
    for f in files:
        if not (ins.root / f).is_file():
            raise Refused(f"{f} is missing")
    out = [{"path": f, "sha256": sha256_file(ins.root / f)} for f in files]
    out += [{"path": f"results/{ins.m}/{lid}.json", "status": ins.status(lid)} for lid in mine]
    return sorted(out, key=lambda i: i["path"])


# ====================================================================== the law files an instance applies
def _artifacts(ins: Inputs, lid: str) -> dict:
    art = (ins.records.get(lid) or {}).get("artifacts") or {}
    if not all(isinstance(art.get(k), str) for k in ("laws", "proof", "law_name")):
        raise Refused(f"results/{ins.m}/{lid}.json names no laws/proof artifacts")
    return art


def check_fresh(ins: Inputs, lid: str) -> None:
    """Stale input (exit 2): the statement_hash header of the law's artifacts differs from the registry's."""
    want = ins.registry.get(lid)
    if want is None:
        raise Refused(f"{lid} is not in laws/{ins.m}/REGISTRY.json")
    art = _artifacts(ins, lid)
    for key in ("laws", "proof"):
        p = ins.root / art[key]
        if not p.is_file():
            raise Refused(f"{art[key]} is missing ({lid})")
        hs = re.findall(r"statement_hash: (sha256:[0-9a-f]{64})", p.read_text(encoding="utf-8"))
        if key == "laws" and not hs:
            raise Refused(f"{art[key]} carries no statement_hash header ({lid})")
        if any(x != want for x in hs):
            raise Refused(f"{art[key]} is stale: its statement_hash is not laws/{ins.m}/REGISTRY.json's for {lid}")


class LawFile:
    """One applied law's generated LAWS.bend: its law name, model alias, pins and claim line."""

    def __init__(self, ins: Inputs, lid: str):
        art = _artifacts(ins, lid)
        self.lid, self.name, self.laws_rel, self.proof_rel = lid, art["law_name"], art["laws"], art["proof"]
        text = (ins.root / art["laws"]).read_text(encoding="utf-8")
        self.text = text
        m = re.search(r"(?m)^import \S+/model/\S+\.bend as (\w+)$", text)
        if not m:
            raise Construct(f"{art['laws']}: imports no model")
        self.ma = m.group(1)
        blk = re.search(rf"(?m)^law {re.escape(self.name)}:\n((?:  .*\n?)*)", text)
        if not blk:
            raise Construct(f"{art['laws']}: no law {self.name}")
        self.lines = [ln.strip() for ln in blk.group(1).splitlines() if ln.strip()]
        self.pins = set(re.findall(r"(?m)^def (pin_\w+)\(", text))

    def expect(self, lines: list[str]) -> None:
        if self.lines != lines:
            raise Construct(f"{self.laws_rel}: the law {self.name} is not of the form rule T7 applies: "
                            f"{self.lines} (expected {lines})")


def _getter(ma: str, rec: str, field: str) -> str:
    return f"{ma}.get_{rec}__{field.replace('.', '__')}"


def _bytes_list(c: str) -> str:
    hx = c[2:]
    return "[" + ", ".join(str(int(hx[i:i + 2], 16)) for i in range(0, len(hx), 2)) + "]"


# ====================================================================== T7: the instance's statements
def _carrier_lines(inst: dict) -> list[str]:
    r, o = inst["root"], inst["other"]
    return ["# the instance's carriers, one constructor per value type (Def 4.1)",
            "type Car is Data:",
            f"  K0{{x: M.R_{r}}}",
            f"  K1{{x: M.R_{o}}}",
            f"  K2{{x: {BYTES}}}",
            f"  K3{{x: {MAYBE}}}",
            "",
            "# a fixed record of the other side: the root law's pin_k keeps only the fields with no counterpart from it",
            f"def zero() -> M.R_{o}:",
            f"  M.R_{o}{{{', '.join(['0'] * inst['_other_width'])}}}",
            "",
            "# sigma: the root law's correspondence, the other side's record built from a root record",
            f"def sigma(x: M.R_{r}) -> M.R_{o}:",
            "  L0.pin_k(zero(), x)",
            ""]


def _edge_map(inst: dict, e: dict) -> tuple[int, str]:
    kinds = {v["id"]: v for v in inst["vertices"]}
    src = kinds[e["src"]]
    src_k = {"record": 0 if e["src"] == 0 else 1, "bytes": 2, "field": 2, "slot": 3}[src["kind"]]
    if e["kind"] == "sigma":
        return 0, "K1{sigma(x)}"
    if e["kind"] == "encoder":
        return src_k, f"K2{{M.{e['fn']}(x)}}"
    if e["kind"] == "decoder":
        return 2, f"K3{{M.{e['fn']}(x)}}"
    if e["kind"] == "projection":
        rec = inst["root"] if e["side"] == "root" else inst["other"]
        return src_k, f"K2{{{_getter('M', rec, e['field'])}(x)}}"
    if e["kind"] == "some":
        return 2, "K3{Some{x}}"
    raise Construct(f"no edge map for an edge of kind {e['kind']}")


def _fwd_lines(inst: dict) -> list[str]:
    lines = ["def fwd(e: Nat, c: Car) -> Car:", "  match e:"]
    for e in inst["edges"]:
        src_k, out = _edge_map(inst, e)
        lines += [f"    case {e['id']}n:", "      match c:"]
        for kk in range(4):
            lines.append(f"        case K{kk}{{x}}:")
            lines.append(f"          {out}" if kk == src_k else f"          K{kk}{{x}}")
    return lines + [f"    case {len(inst['edges'])}n+p:", "      c"]


def laws_text(inst: dict) -> str:
    """<out>/basis/<role>_v<v>/LAWS.bend (rule T7)."""
    r = inst["root"]
    lines = [f"# GENERATED by holon.gen.basis (I42): the basis-sufficiency instance {inst['name']}: any two forward",
             "# walks of its diagram from vertex 0 that end at one vertex agree (Thm 6.4 (ii) in potential form, Cor 6.5),",
             "# by application of the core over the PROVED laws of its basis. Statements frozen in",
             "# spec/M3/lib/theory_core.json.",
             "import Base",
             f"import ../../../model/{inst['component']}.bend as M",
             "import ../../core/LAWS.bend as C",
             "import ../../core/PROOF.bend as CP",
             f"import ../../../laws/{inst['root_law']}/LAWS.bend as L0",
             ""] + _carrier_lines(inst) + [
             "# the graph: edge k is the k-th entry; no edge is traversed backwards (inv False)",
             "def graph() -> List<&2, C.Edge>:",
             "  [" + ", ".join(f"C.Edge{{{e['src']}n, {e['tgt']}n, False{{}}}}" for e in inst["edges"]) + "]",
             ""] + _fwd_lines(inst) + [
             "",
             "def act(s: C.Step, c: Car) -> Car:",
             "  match s:",
             "    case C.Fwd{e}:",
             "      fwd(e, c)",
             "    case C.Bwd{e}:",
             "      c",
             "",
             "def run(w: List<&2, C.Step>, c: Car) -> Car:",
             "  match w:",
             "    case Nil{}:",
             "      c",
             "    case Con{s, t}:",
             "      run(t, act(s, c))",
             "",
             f"def start(h: M.R_{r}) -> Car:",
             "  K0{L0.pin_h(h)}",
             "",
             f"law {inst['name']}:",
             f"  for +h: M.R_{r}",
             "  for +p: List<&2, C.Step>",
             "  for +q: List<&2, C.Step>",
             "  for vp: C.WalkOk(p, graph(), 0n)",
             "  for vq: C.WalkOk(q, graph(), 0n)",
             "  for e: {C.walk_last(p, graph(), 0n) == C.walk_last(q, graph(), 0n) : Nat}",
             "  {run(p, start(h)) == run(q, start(h)) : Car}"]
    for c in inst["certificates"]:
        lhs, rhs = _cert_sides(inst, c, "L0", "sigma")
        lines += ["", f"law {c['name']}:", f"  for +h: M.R_{r}", f"  {{{lhs} == {rhs} : {MAYBE}}}"]
    return "\n".join(lines) + "\n"


def _cert_sides(inst: dict, c: dict, root_alias: str, sigma: str) -> tuple[str, str]:
    enc = inst["p"] if c["side"] == "p" else inst["q"]
    arg = f"{root_alias}.pin_h(h)" if c["side"] == "p" else f"{sigma}({root_alias}.pin_h(h))"
    lhs = f"M.{c['decoders'][0]}(M.{enc}({arg}))"
    if c["kind"] == "constant_read":
        return lhs, f"{{Some{{{_bytes_list(c['bytes'])}}} : {MAYBE}}}"
    return lhs, f"M.{c['decoders'][1]}(M.{enc}({arg}))"


def canary_laws_text(inst: dict) -> str:
    """<out>/basis/<role>_v<v>/canary/LAWS.bend (rule T8b)."""
    lines = [f"# GENERATED by holon.gen.basis (I42): the semantic canary of {inst['name']}: its root cycle (edge 1",
             "# against edges 0 then 2) at an unpinned start, where the root law's pins need not hold. Statements frozen",
             "# in spec/M3/lib/theory_core.json.",
             "import Base",
             f"import ../../../../model/{inst['component']}.bend as M",
             f"import ../../../../laws/{inst['root_law']}/LAWS.bend as L0",
             ""] + _carrier_lines(inst) + _fwd_lines(inst) + [
             "",
             f"law {inst['canary_law']}:",
             f"  exs h: M.R_{inst['root']}",
             "  {fwd(1n, K0{h}) != fwd(2n, fwd(0n, K0{h})) : Car}"]
    return "\n".join(lines) + "\n"


# ====================================================================== T7: the proof by application
def _rel(ins: Inputs, rel: str, d: str) -> str:
    """rel (a path under the root) as seen from <root>/gen/<M>/theory/<d>: the committed location of the outputs,
    whatever --out is, so that the files are byte-identical wherever they are written."""
    return os.path.relpath(ins.root / rel, ins.root / "gen" / ins.m / "theory" / d)


def _walk(steps: list[int]) -> str:
    return "[" + ", ".join(f"C.Fwd{{{e}n}}" for e in steps) + "]"


def _walk_ok(n: int) -> str:
    """The evidence of WalkOk for a concrete valid walk of n steps: one reflexivity per step."""
    return "({==}, " * n + "Unit{}" + ")" * n


def _record_case(alias: str, rec: str, width: int) -> str:
    return f"case {alias}.R_{rec}{{{', '.join(f'+x{i}' for i in range(width))}}}:"


def proof_text(ins: Inputs, inst: dict) -> str:
    """<out>/basis/<role>_v<v>/PROOF.bend (rule T7): the instance law and its certificates by application."""
    r, o, name = inst["root"], inst["other"], inst["name"]
    d = inst["dir"]
    files = {a["law"]: LawFile(ins, a["law"]) for a in inst["available"]}
    alias = {a["law"]: f"A{i}" for i, a in enumerate(inst["available"])}
    root = files[inst["root_law"]]
    a0 = alias[inst["root_law"]]
    hn, kn = inst["_h"]["name"], inst["_k"]["name"]
    # the root law: p(pin_h(h)) == q(pin_k(k, h)) over its two record binders
    if not {"pin_h", "pin_k"} <= root.pins:
        raise Construct(f"{root.laws_rel}: the root law pins neither h nor k (rule T7 needs pin_h and pin_k)")
    ma = root.ma
    root.expect([f"for +{hn}: {ma}.R_{r}", f"for +{kn}: {ma}.R_{o}",
                 f"{{{ma}.{inst['p']}(pin_h({hn})) == {ma}.{inst['q']}(pin_k({kn}, {hn})) : {BYTES}}}"])
    edges = inst["edges"]
    ekind = {e["id"]: e for e in edges}
    out = [f"# GENERATED by holon.gen.basis (I42): the proof of {name} and its certificates by application of the",
           "# core (core_parallel_agree) over the PROVED laws of its basis (rule T7); untrusted, accepted only if bend",
           "# checks it.",
           "import Base",
           "import ./LAWS.bend as Laws",
           "import ../../core/LAWS.bend as C",
           "import ../../core/PROOF.bend as CP",
           f"import {_rel(ins, f'gen/{ins.m}/model/{inst['component']}.bend', d)} as M"]
    for a in inst["available"]:
        i = alias[a["law"]][1:]
        out.append(f"import {_rel(ins, files[a['law']].laws_rel, d)} as A{i}")
        out.append(f"import {_rel(ins, files[a['law']].proof_rel, d)} as P{i}")
    paths = inst["_paths"]
    nv = len(inst["vertices"])
    out += ["", "# the tree walk of every vertex (rule T4)",
            "def tree(v: Nat) -> List<&2, C.Step>:", "  match v:"]
    for v in range(nv):
        out += [f"    case {v}n:", f"      {_walk(paths[v]) if paths[v] else 'Nil{}'}"]
    out += [f"    case {nv}n+p:", "      Nil{}", "",
            "# the potential of vertex v: the value its tree walk carries the start to (Cor 6.5)",
            f"def phi(+h: M.R_{r}, v: Nat) -> Laws.Car:",
            "  Laws.run(tree(v), Laws.start(h))", "",
            "# a walk carries c to its run",
            "def runto_run(w: List<&2, C.Step>, +c: Laws.Car) -> C.RunTo(Laws.Car, Laws.act, w, c, Laws.run(w, c)):",
            "  match w:", "    case Nil{}:", "      {==}", "    case Con{+s, t}:", "      runto_run(t, Laws.act(s, c))",
            "", "# the value of a carrier-3 (Maybe) value",
            f"def un3(c: Laws.Car) -> {MAYBE}:", "  match c:",
            "    case Laws.K0{x}:", "      None{}", "    case Laws.K1{x}:", "      None{}",
            "    case Laws.K2{x}:", "      None{}", "    case Laws.K3{x}:", "      x"]
    root_case = _record_case("M", r, inst["_root_width"])
    pin = f"{a0}.pin_h(h)"
    sig = f"Laws.sigma({pin})"

    def bridge(bname: str, ty: str) -> list[str]:
        return ["", f"def {bname}(+h: M.R_{r}) -> {ty}:", "  match h:", f"    {root_case}", "      {==}"]

    # bridges: the root law's pin is idempotent; an applied law's pins hold on the instance's argument; a pinned
    # field's getter is its constant
    out += ["", "# ---------------------------------------------------------------- bridges (records opened only here)"]
    out += bridge("bridge_root", f"{{{a0}.pin_h({pin}) == {pin} : M.R_{r}}}")
    args = {}
    for i, a in enumerate(inst["available"]):
        if a["kind"] == "root":
            continue
        lf = files[a["law"]]
        on_root = a["kind"] == "round_trip_p"
        rec, arg = (r, pin) if on_root else (o, sig)
        pinned = "pin_h" in lf.pins
        args[i] = f"A{i}.pin_h({arg})" if pinned else arg
        if pinned:
            out += bridge(f"bridge_avail_{i}", f"{{A{i}.pin_h({arg}) == {arg} : M.R_{rec}}}")
    for c in inst["certificates"]:
        if c["kind"] != "constant_read":
            continue
        fv = inst["vertices"][inst["_cert_field"][c["name"]]]
        rec, arg = (r, pin) if fv["side"] == "root" else (o, sig)
        out += bridge(f"bridge_{c['name']}", f"{{{_getter('M', rec, fv['field'])}({arg}) == "
                                             f"{_bytes_list(c['bytes'])} : {BYTES}}}")
    # the available equations, each an application of its law
    out += ["", "# ---------------------------------------------------------------- the available equations (rule T5)"]
    for i, a in enumerate(inst["available"]):
        lf = files[a["law"]]
        ty = (f"{{Laws.run({_walk(a['lhs'])}, Laws.start(h)) == Laws.run({_walk(a['rhs'])}, Laws.start(h)) "
              f": Laws.Car}}")
        out += ["", f"def avail_{i}(+h: M.R_{r}) -> {ty}:"]
        if a["kind"] == "root":
            out += [f"  %bridge_root(h) : {{Laws.K2{{M.{inst['p']}(_)}} == Laws.K2{{M.{inst['q']}({sig})}} : Laws.Car}}",
                    f"  Equal.cong({BYTES}, Laws.Car, x => Laws.K2{{x}}, M.{inst['p']}({a0}.pin_h({pin})), "
                    f"M.{inst['q']}({a0}.pin_k(Laws.zero(), {pin})), {a0}.{lf.name}({pin}, Laws.zero()))"]
            continue
        dec = ekind[a["lhs"][-1]]["fn"]
        some = ekind[a["rhs"][-1]]
        on_root = a["kind"] == "round_trip_p"
        enc, rec = (inst["p"], r) if on_root else (inst["q"], o)
        x = "pin_h(h)" if "pin_h" in lf.pins else "h"
        lf.expect([f"for +h: {lf.ma}.R_{rec}",
                   f"{{{lf.ma}.{dec}({lf.ma}.{enc}({x})) == {{Some{{{_getter(lf.ma, rec, some['field'])}({x})}} : "
                   f"{MAYBE}}} : {MAYBE}}}"])
        get = _getter("M", rec, some["field"])
        arg_in = pin if on_root else sig
        if "pin_h" in lf.pins:
            out.append(f"  %bridge_avail_{i}(h) : {{Laws.K3{{M.{dec}(M.{enc}(_))}} == Laws.K3{{Some{{{get}(_)}}}} "
                       f": Laws.Car}}")
        out.append(f"  Equal.cong({MAYBE}, Laws.Car, x => Laws.K3{{x}}, M.{dec}(M.{enc}({args[i]})), "
                   f"Some{{{get}({args[i]})}}, A{i}.{lf.name}({arg_in}))")
    # the per-edge facts: phi respects every edge
    out += ["", "# ---------------------------------------------------------------- the per-edge facts (Cor 6.5's potentials)"]
    cyc = {c["edge"]: c for c in inst["cycles"]}
    proof_of = [f"avail_{i}(h)" for i in range(len(inst["available"]))]
    for e in edges:
        k = e["id"]
        out += ["", f"def edge_{k}(+h: M.R_{r}) -> {{Laws.act(C.Fwd{{{k}n}}, phi(h, {e['src']}n)) == "
                    f"phi(h, {e['tgt']}n) : Laws.Car}}:"]
        if k in inst["tree"]:
            out.append("  {==}")
        else:
            c = cyc[k]
            out.append("  " + CG.chain(c["from"], c["derivation"], inst["available"], car="Laws.Car", run="Laws.run",
                                       start_term="Laws.start(h)", step="C.Fwd{{{}n}}", proof_of=proof_of))
    # one step of a walk of the graph respects phi
    gty = "Laws.graph()"
    out += ["", "# ---------------------------------------------------------------- a valid step respects the potentials",
            f"def step_fact(+h: M.R_{r}, +s: C.Step, +u: Nat, o: {{C.step_ok(s, {gty}, u) == True{{}} : Bool}}) -> "
            f"{{Laws.act(s, phi(h, u)) == phi(h, C.next_v(s, {gty}, u)) : Laws.Car}}:",
            "  match s:", "    case C.Fwd{+e}:", "      match e:"]
    ne = len(edges)
    for e in edges:
        k = e["id"]
        out += [f"        case {k}n:",
                f"          %C.core_nat_eq_of_is_eq({e['src']}n, u, o) : {{Laws.act(C.Fwd{{{k}n}}, phi(h, _)) == "
                f"phi(h, {e['tgt']}n) : Laws.Car}}",
                f"          edge_{k}(h)"]
    out += [f"        case {ne}n+p:",
            f"          C.core_efq_bool({{Laws.act(C.Fwd{{{ne}n+p}}, phi(h, u)) == phi(h, u) : Laws.Car}}, o)",
            "    case C.Bwd{+e}:", "      match e:"]
    for e in edges:
        k = e["id"]
        out += [f"        case {k}n:",
                f"          C.core_efq_bool({{Laws.act(C.Bwd{{{k}n}}, phi(h, u)) == phi(h, {e['src']}n) : Laws.Car}}, o)"]
    out += [f"        case {ne}n+p:",
            f"          C.core_efq_bool({{Laws.act(C.Bwd{{{ne}n+p}}, phi(h, u)) == phi(h, u) : Laws.Car}}, o)",
            "", "# the per-step bundle of a walk of the graph (C.Cons), from its WalkOk evidence",
            f"def cons_of(+h: M.R_{r}, w: List<&2, C.Step>, +u: Nat, ok: C.WalkOk(w, {gty}, u)) -> "
            f"C.Cons(Laws.Car, Laws.act, v => phi(h, v), w, {gty}, u):",
            "  match w:", "    case Nil{}:", "      Unit{}", "    case Con{+s, t}:", "      match ok:",
            "        case (o, rest):",
            f"          (step_fact(h, s, u, o), cons_of(h, t, C.next_v(s, {gty}, u), rest))",
            "", "# ---------------------------------------------------------------- the instance law (Thm 6.4 (ii))",
            f"def Laws.{name}(h, p, q, vp, vq, e):",
            f"  C.core_parallel_agree(Laws.Car, Laws.act, v => phi(h, v), p, q, {gty}, 0n, e, cons_of(h, p, 0n, vp), "
            f"cons_of(h, q, 0n, vq), Laws.run(p, Laws.start(h)), Laws.run(q, Laws.start(h)), "
            f"runto_run(p, Laws.start(h)), runto_run(q, Laws.start(h)))"]
    # the certificates: the instance law at two concrete walks, read through un3
    out += ["", "# ---------------------------------------------------------------- the certificates (rule T6)"]
    for c in inst["certificates"]:
        enc_walk = [1] if c["side"] == "p" else [0, 2]
        dec_edge = {e["fn"]: e["id"] for e in edges if e["kind"] == "decoder"}
        pa = enc_walk + [dec_edge[c["decoders"][0]]]
        if c["kind"] == "constant_read":
            fv = inst["_cert_field"][c["name"]]
            some = next(e["id"] for e in edges if e["kind"] == "some" and e["src"] == fv)
            pb = paths[fv] + [some]
        else:
            pb = enc_walk + [dec_edge[c["decoders"][1]]]
        lhs, rhs = _cert_sides(inst, c, a0, "Laws.sigma")
        app = (f"Equal.cong(Laws.Car, {MAYBE}, un3, Laws.run({_walk(pa)}, Laws.start(h)), "
               f"Laws.run({_walk(pb)}, Laws.start(h)), Laws.{name}(h, {_walk(pa)}, {_walk(pb)}, {_walk_ok(len(pa))}, "
               f"{_walk_ok(len(pb))}, {{==}}))")
        out += ["", f"def Laws.{c['name']}(h):"]
        if c["kind"] == "constant_read":
            out.append(f"  %bridge_{c['name']}(h) : {{{lhs} == {{Some{{_}} : {MAYBE}}} : {MAYBE}}}")
        out.append(f"  {app}")
    return "\n".join(out) + "\n"


# ====================================================================== T8b: the semantic canary
def _helpers_text() -> list[str]:
    return ["# equality of byte lists and of carrier values, computed (untrusted: a wrong one only fails the check)",
            f"def bytes_eq(a: {BYTES}, b: {BYTES}) -> Bool:",
            "  match a b:", "    case Nil{} Nil{}:", "      True{}", "    case Con{x, xs} Con{y, ys}:",
            "      Bool.and(U32.is_eq(x, y), bytes_eq(xs, ys))", "    case _ _:", "      False{}", "",
            "def car_eq(a: CAR, b: CAR) -> Bool:", "  match a b:", "    case K2{x} K2{y}:", "      bytes_eq(x, y)",
            "    case _ _:", "      False{}", ""]


def _candidates(inst: dict) -> list[list[int]]:
    """Candidate witnesses, in a fixed order: per field the root law pins on h (record order), the zero record with
    that field's first byte moved off its pinned constant."""
    out, off = [], 0
    pinned = {f: c for (b, f), c in inst["_pins"].items() if b == inst["_h"]["name"]}
    for f in inst["_root_fields"]:
        if f["name"] in pinned:
            w = [0] * inst["_root_width"]
            w[off] = (int(pinned[f["name"]][2:4], 16) + 1) % 256
            out.append(w)
        off += int(f["width"])
    return out


def _stage(ins: Inputs, tmp: Path) -> Path:
    """A copy of gen/<M>'s model, laws, proofs and core under tmp (the layout the outputs' imports assume)."""
    g = tmp / "gen" / ins.m
    for sub in ("model", "laws", "proofs", "core"):
        s = ins.root / "gen" / ins.m / sub
        if s.is_dir():
            shutil.copytree(s, g / sub)
    return g


def _bend_cmd() -> list[str]:
    from .. import bend as B
    return B.bend_cmd() if hasattr(B, "bend_cmd") else ["bend"]


def find_witness(ins: Inputs, inst: dict) -> list[int] | None:
    """The first candidate on which the model's two walks differ, evaluated by bend (the model, never an oracle)."""
    cands = _candidates(inst)
    if not cands:
        return None
    r = inst["root"]
    tmp = Path(tempfile.mkdtemp(prefix="holon_basis_eval_"))
    try:
        g = _stage(ins, tmp)
        d = g / "theory" / inst["dir"] / "canary"
        d.mkdir(parents=True)
        root = LawFile(ins, inst["root_law"])
        lines = ["import Base", f"import {_rel(ins, f'gen/{ins.m}/model/{inst['component']}.bend', inst['dir'] + '/canary')} as M",
                 f"import {_rel(ins, root.laws_rel, inst['dir'] + '/canary')} as L0",
                 f"import {_rel(ins, root.proof_rel, inst['dir'] + '/canary')} as P0", ""]
        lines += _carrier_lines(inst) + _fwd_lines(inst) + [""]
        lines += [x.replace("CAR", "Car") for x in _helpers_text()]
        lines += ["def main() -> List<&2, Bool>:",
                  "  [" + ", ".join(f"car_eq(fwd(1n, K0{{M.R_{r}{{{', '.join(map(str, w))}}}}}), "
                                    f"fwd(2n, fwd(0n, K0{{M.R_{r}{{{', '.join(map(str, w))}}}}})))" for w in cands) + "]"]
        (d / "EVAL.bend").write_text("\n".join(lines) + "\n", encoding="utf-8")
        p = subprocess.run(_bend_cmd() + ["EVAL.bend"], cwd=d, capture_output=True, text=True, timeout=TIMEOUT_S)
        out = p.stdout + p.stderr
        vals = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("[")]
        if p.returncode != 0 or not vals:
            raise Construct(f"{inst['name']}: bend could not evaluate the canary's candidates: {out[-1500:]}")
        got = re.findall(r"(True|False)\{\}", vals[-1])
        if len(got) != len(cands):
            raise Construct(f"{inst['name']}: unexpected evaluation output: {vals[-1][:300]}")
        for w, b in zip(cands, got):
            if b == "False":
                return w
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def canary_proof_text(ins: Inputs, inst: dict, witness: list[int]) -> str:
    """<out>/basis/<role>_v<v>/canary/PROOF.bend (rule T8b): the counter-law with the model's witness."""
    r = inst["root"]
    d = inst["dir"] + "/canary"
    root = LawFile(ins, inst["root_law"])
    w = f"witness_{inst['version']}()"
    lines = [f"# GENERATED by holon.gen.basis (I42): the semantic canary of {inst['name']}, refuted with a witness found",
             "# by evaluating the model's two walks with bend (rule T8b); untrusted, accepted only if bend checks it.",
             "import Base",
             "import ./LAWS.bend as Laws",
             f"import {_rel(ins, f'gen/{ins.m}/model/{inst['component']}.bend', d)} as M",
             f"import {_rel(ins, root.laws_rel, d)} as L0",
             f"import {_rel(ins, root.proof_rel, d)} as P0",
             "",
             "# the witness: a root record whose start is not pinned",
             f"def witness_{inst['version']}() -> M.R_{r}:",
             f"  M.R_{r}{{{', '.join(map(str, witness))}}}",
             ""]
    lines += [x.replace("CAR", "Laws.Car").replace("case K2{x} K2{y}", "case Laws.K2{x} Laws.K2{y}")
              for x in _helpers_text()]
    lines += ["# the motive: Unit where the two values are equal, Empty where they differ",
              "def holds(b: Bool) -> Type:", "  match b:", "    case True{}:", "      Unit", "    case False{}:",
              "      Empty", "",
              f"def Laws.{inst['canary_law']}():",
              f"  ({w}, e => (%e : holds(car_eq(_, Laws.fwd(1n, Laws.K0{{{w}}}))); Unit{{}}))"]
    return "\n".join(lines) + "\n"


# ====================================================================== T9 and the build
def document(ins: Inputs, role: str, insts: list[dict]) -> dict:
    mine = [i for i in insts if i["component"] == role]
    return {"basis_version": BASIS_VERSION, "document": "basis", "milestone": ins.m, "component": role,
            "facts": f"gen/{ins.m}/codec/{role}.json", "inputs": component_inputs(ins, role, insts),
            "instances": sorted(({k: i[k] for k in DOC_KEYS} for i in mine),
                                key=lambda i: (i["version"], i["root_law"]))}


def build(root: Path, milestone: str) -> tuple[dict[str, str], list[dict], Inputs]:
    """{path under <out>: text} of every file holon basis writes (report.json aside), the instances, the inputs."""
    ins = load(root, milestone)
    insts = instances(ins)
    for inst in insts:
        for lid in inst["laws_used"]:
            check_fresh(ins, lid)
        model = ins.root / "gen" / ins.m / "model" / f"{inst['component']}.bend"
        if (_artifacts(ins, inst["root_law"]).get("model") or "") != model.relative_to(ins.root).as_posix():
            raise Construct(f"{inst['root_law']}: its record names another model than {model.name}")
    files = {"core/LAWS.bend": TH.CORE_LAWS_TEXT, "core/PROOF.bend": TH.CORE_PROOF_TEXT,
             "lean/Theory.lean": TH.LEAN_TEXT}
    for role, _, _ in ins.comps:
        files[f"basis/{role}.json"] = dumps(document(ins, role, insts))
    for inst in insts:
        if inst["status"] != "emitted":
            continue
        files[f"{inst['dir']}/LAWS.bend"] = laws_text(inst)
        files[f"{inst['dir']}/PROOF.bend"] = proof_text(ins, inst)
        files[f"{inst['dir']}/canary/LAWS.bend"] = canary_laws_text(inst)
        w = find_witness(ins, inst)
        inst["_witness"] = w
        if w is not None:
            files[f"{inst['dir']}/canary/PROOF.bend"] = canary_proof_text(ins, inst, w)
    return files, insts, ins


def kernels(ins: Inputs, files: dict[str, str], insts: list[dict], log=print) -> dict:
    """Check every written proof file (bend, then bend --verdict) and the Lean core; report.json (T9)."""
    from .. import bend as B
    from .. import lean as LN
    rep = {"report_version": BASIS_VERSION, "files": {}, "basis_sufficiency": {}, "canary": {}}
    tmp = Path(tempfile.mkdtemp(prefix="holon_basis_kernels_"))
    try:
        g = _stage(ins, tmp)
        out = g / "theory"
        for rel, text in files.items():
            f = out / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(text, encoding="utf-8")
        for rel in sorted(files):
            if not rel.endswith("PROOF.bend"):
                continue
            f = out / rel
            r1 = B.run([f.name], cwd=f.parent, timeout=TIMEOUT_S)
            ok1 = r1.code == 0 and "ALL PROOFS CHECK" in r1.out
            v = "not_run"
            if ok1:
                r2 = B.check_verdict(f)
                v = "checked" if r2.code == 0 and "ALL PROOFS CHECK" in r2.out else "rejected"
            rep["files"][rel] = {"sha256": hashlib.sha256(files[rel].encode()).hexdigest(),
                                 "bend": "checked" if ok1 else "rejected", "verdict": v}
            log(f"{rel}: bend {rep['files'][rel]['bend']}, verdict {v}")
        lt = files["lean/Theory.lean"]
        res = LN.check_text(lt, tmp / "lean")
        rep["files"]["lean/Theory.lean"] = {"sha256": hashlib.sha256(lt.encode()).hexdigest(), "lean": res["result"],
                                            "axioms": res["axioms"]}
        log(f"lean/Theory.lean: {res['result']} {res['axioms']}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    def ok(rel):
        x = rep["files"].get(rel) or {}
        return x.get("bend") == "checked" and x.get("verdict") == "checked"

    lean_ok = rep["files"]["lean/Theory.lean"]["lean"] == "checked"
    for inst in insts:
        n = inst["name"]
        if inst["status"] != "emitted":
            rep["basis_sufficiency"][n] = "uncovered"
            continue
        good = ok("core/PROOF.bend") and lean_ok and ok(f"{inst['dir']}/PROOF.bend")
        rep["basis_sufficiency"][n] = "kernel_checked" if good else "paper_proof_only"
        cp = f"{inst['dir']}/canary/PROOF.bend"
        rep["canary"][n] = "no_witness" if cp not in files else ("refuted" if ok(cp) else "not_refuted")
    return rep


# ====================================================================== CLI
def _owned(out: Path) -> dict[str, str]:
    have = {}
    for top in OWNED:
        d = out / top
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    have[p.relative_to(out).as_posix()] = p.read_text(encoding="utf-8")
    return have


def _show(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon basis")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/theory)")
    ap.add_argument("--kernels", action="store_true", help="check every proof file and write report.json")
    ap.add_argument("--check", action="store_true", help="compare a fresh build with the files, writing nothing")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    out = Path(a.out).resolve() if a.out else root / "gen" / a.milestone / "theory"
    try:
        files, insts, ins = build(root, a.milestone)
        rep = kernels(ins, files, insts, log=lambda s: print(s, file=sys.stderr)) if a.kernels else None
    except Refused as e:
        print(f"holon basis: refused: {e}", file=sys.stderr)
        return 2
    except Construct as e:
        print(f"holon basis: construct refused: {e}", file=sys.stderr)
        return 3
    want = dict(files)
    if rep is not None:
        want[REPORT] = dumps(rep)
    if a.check:
        have = _owned(out)
        if rep is not None:
            have[REPORT] = (out / REPORT).read_text(encoding="utf-8") if (out / REPORT).is_file() else None
        bad = sorted(k for k in set(have) | set(want) if have.get(k) != want.get(k))
        if bad:
            print(f"holon basis: {len(bad)} file(s) differ from a fresh build: {bad[:10]}", file=sys.stderr)
            return 1
        print(f"holon basis: {_show(out, root)} reproduces ({len(want)} files)")
        return 0
    out.mkdir(parents=True, exist_ok=True)
    for rel in _owned(out):
        if rel not in want:
            (out / rel).unlink()
    for top in OWNED:
        d = out / top
        if d.is_dir():
            for p in sorted(d.rglob("*"), reverse=True):
                if p.is_dir() and not any(p.iterdir()):
                    p.rmdir()
    for rel, text in sorted(want.items()):
        f = out / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    for inst in insts:
        st = inst["status"]
        extra = "" if st != "emitted" else (" canary witness found" if inst.get("_witness") else " no canary witness")
        print(f"{inst['name']}: {st} (|V| {len(inst['vertices'])}, |E| {len(inst['edges'])}, rank {inst['rank']}, "
              f"{len(inst['certificates'])} certificates){extra}")
    if rep is not None:
        print(f"basis sufficiency: {rep['basis_sufficiency']}; canaries: {rep['canary']}")
    print(f"wrote {_show(out, root)} ({len(want)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
