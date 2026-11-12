"""Rule PAR's record sub-forms (I100; the L7 candidate PAR_record_round_trip of the rule-gap ledger; rules S2-S5 of
tests_m3/test_par_record_i100.py), over a target milestone's linked codec documents.

  instances           in a document, for each carrier of kind bytes, each encoder into it with a versions list, each
                      version N of the encoder and each getter family of the carrier: the decoders of the document
                      from the carrier with one source qualifier (the source before its last "."), the family named by
                      the qualifier's last identifier; its members active at N, in (read offset, read width, name)
                      order. An encoder without a versions list is listed as unversioned and gives nothing.
  components          from the encoder's layout at N and a member's read range, never from laws: a field whose bytes
                      0..w-1 the layout places there in order (rule X7's E1 inverse atom), a constant when every cell
                      there is one, else none (the member is missing).
  constant_read       one law per decoder of the carrier active at N whose read range the layout fills with constants
                      c: d(e(h)) == some(c), under rule P1's version premise.
  record_round_trip   per instance with no missing member, the record law dec(enc(h)) = some(view_N(h)): the
                      conjunction of one conjunct per member, a field's round trip (P1's claim of its atom) or a
                      constant's read-back, under the same premise and nothing else. An instance with a missing member
                      gives no law: it is an obstruction (missing_component) naming each missing member and what its
                      read range holds instead.

basis_doc is gen/<M>/par_record/basis.json (holon derive writes it): every instance with its members, components and
law or missing members, every obstruction and every unversioned encoder. Deterministic; nothing here names a law or
a target.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import par as _par

RULE = "PAR"
SUBFORMS = ("constant_read", "record_round_trip")
TAG = {"constant_read": "rt", "record_round_trip": "rec"}
BASIS_VERSION = "holon-par-record/0.1"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class ParRecordError(ValueError):
    pass


def family_of(f: dict) -> tuple | None:
    """(document, source qualifier, its last identifier) of a decoder, or None when its source has no qualifier."""
    src = f.get("source") or ""
    if "." not in src:
        return None
    q = src.rsplit(".", 1)[0]
    name = re.sub(r"[()*]", "", q).rsplit(".", 1)[-1].rsplit("/", 1)[-1]
    return (f.get("document"), q, name) if IDENT.fullmatch(name) else None


def active(f: dict, v: int) -> bool:
    return f.get("versions") is None or v in f["versions"]


def component(lay: list, rd: dict) -> dict:
    """What a layout holds in a read range: a field's bytes in order, constants, or neither (what it holds instead)."""
    o, w = rd["offset"], rd["width"]
    cells = [lay[i] if i < len(lay) else ["unknown"] for i in range(o, o + w)]
    if cells and cells[0][0] == "field" and all(c == ["field", cells[0][1], k] for k, c in enumerate(cells)):
        return {"component": "field", "field": cells[0][1]}
    if cells and all(c[0] == "const" for c in cells):
        return {"component": "constant", "bytes": "0x" + bytes(int(c[1]) for c in cells).hex()}
    return {"component": None, "holds": {"fields": sorted({c[1] for c in cells if c[0] == "field"}),
                                         "constant_cells": sum(1 for c in cells if c[0] == "const"),
                                         "other_cells": sum(1 for c in cells if c[0] not in ("field", "const"))}}


def _conjunct(enc: str, dec: str, comp: dict) -> dict:
    rhs = {"field": comp["field"], "of": {"var": "h"}} if comp["component"] == "field" else {"bytes": comp["bytes"]}
    return {"eq": [_par._call(dec, _par._call(enc, {"var": "h"})), {"some": rhs}]}


def _statement(src: str, assume: list, claim: dict) -> dict:
    return {"binders": [{"q": "forall", "name": "h", "type": src}], "assume": assume, "claim": claim,
            "scope": dict(_par.UNBOUNDED)}


def _families(doc: dict, carrier: str) -> tuple[dict, dict]:
    decs = {n: f for n, f in doc["functions"].items() if f["kind"] == "decoder" and f["from"] == carrier}
    fams: dict = {}
    for n, f in decs.items():
        k = family_of(f)
        if k is not None:
            fams.setdefault(k, []).append(n)
    return decs, fams


def derive_documents(items: list[tuple[str, dict, dict]]) -> dict:
    """Over (path, linked codec document, its diagram) items, in their order: {"instances", "laws": {law id:
    {"subform", "statement", "notes", "basis"}}, "obstructions", "unversioned"}."""
    out = {"instances": [], "laws": {}, "obstructions": [], "unversioned": []}

    def add(lid: str, x: dict) -> None:
        if lid in out["laws"]:
            raise ParRecordError(f"two basis elements give the law id {lid}")
        out["laws"][lid] = x

    for rel, doc, diag in items:
        pd = _par.ParDoc(rel=rel, facts=doc, diagram=diag, atoms=[])
        fs = doc["functions"]
        for c in sorted(cid for cid, car in doc["carriers"].items() if car.get("kind") == "bytes"):
            decs, fams = _families(doc, c)
            for e in sorted(n for n, f in fs.items() if f["kind"] == "encoder" and f["to"] == c):
                vs = fs[e].get("versions")
                if not vs:
                    out["unversioned"].append({"document": rel, "encoder": e})
                    continue
                src = fs[e]["from"]
                for v in sorted(vs):
                    lay = (fs[e].get("layouts") or {}).get(str(v))
                    if lay is None:
                        raise ParRecordError(f"{rel}: {e} has no layout at version {v}")
                    vp = _par.version_premise(pd, "h", src, v)
                    for d in sorted(n for n in decs if active(decs[n], v)):
                        comp = component(lay, decs[d]["read"])
                        if comp["component"] != "constant":
                            continue
                        add(f"L_par_{TAG['constant_read']}_{e}_{d}_v{v}", {
                            "subform": "constant_read", "statement": _statement(src, vp, _conjunct(e, d, comp)),
                            "notes": f"PAR constant read (holon.rules.par_record): {d} reads {comp['bytes']} from "
                                     f"{e}'s output at version {v}, a constant of {e}'s layout",
                            "basis": {"subform": "constant_read", "model": diag["model"],
                                      "key": {"encoder": e, "getter": d}, "version": v}})
                    for key in sorted(fams, key=lambda k: (k[2], k[0] or "", k[1])):
                        mem = sorted((n for n in fams[key] if active(decs[n], v)),
                                     key=lambda n: (decs[n]["read"]["offset"], decs[n]["read"]["width"], n))
                        if not mem:
                            continue
                        members = [dict(getter=n, reads=[decs[n]["read"]["offset"], decs[n]["read"]["width"]],
                                        **component(lay, decs[n]["read"])) for n in mem]
                        missing = [m["getter"] for m in members if m["component"] is None]
                        lid = None if missing else f"L_par_{TAG['record_round_trip']}_{e}_{key[2]}_v{v}"
                        out["instances"].append({"document": rel, "encoder": e, "carrier": c, "family": key[2],
                                                 "version": v, "members": members, "law": lid, "missing": missing})
                        if missing:
                            out["obstructions"].append({"kind": "missing_component", "document": rel, "encoder": e,
                                                        "family": key[2], "version": v, "getters": missing})
                            continue
                        nf = sum(1 for m in members if m["component"] == "field")
                        add(lid, {
                            "subform": "record_round_trip",
                            "statement": _statement(src, vp, {"all": [_conjunct(e, m["getter"], m) for m in members]}),
                            "notes": f"PAR record round trip (holon.rules.par_record): the getter family {key[2]} "
                                     f"({len(members)} getters at version {v}: {nf} field slots, {len(members) - nf} "
                                     f"constant slots) inverts {e} at version {v}",
                            "basis": {"subform": "record_round_trip", "model": diag["model"],
                                      "key": {"encoder": e, "family": key[2]}, "version": v}})
    return out


# ====================================================================== the milestone's documents
def documents(milestone: str, root: Path, inputs=None) -> list[tuple[str, dict, dict]]:
    """The committed linked codec documents of a milestone with their diagrams, read through `inputs` when given."""
    from ..diagram import linked as L
    out = []
    for p in L.committed_codecs(milestone, root):
        doc = inputs.json(p) if inputs is not None else json.loads(p.read_text(encoding="utf-8"))
        if not L.is_linked(doc):
            continue
        dp = Path(root) / "gen" / milestone / "diagram" / f"{doc['component']}.json"
        diag = inputs.json(dp) if inputs is not None else json.loads(dp.read_text(encoding="utf-8"))
        out.append((p.relative_to(root).as_posix(), doc, diag))
    return out


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def basis_doc(milestone: str, root: Path, res: dict | None = None, items: list | None = None) -> dict:
    root = Path(root)
    items = documents(milestone, root) if items is None else items
    res = derive_documents(items) if res is None else res
    ins = []
    for rel, doc, _ in items:
        ins.append({"path": rel, "sha256": _sha(root / rel)})
        dp = f"gen/{milestone}/diagram/{doc['component']}.json"
        ins.append({"path": dp, "sha256": _sha(root / dp)})
    return {"document": "par_record", "basis_version": BASIS_VERSION, "milestone": milestone,
            "inputs": sorted(ins, key=lambda x: x["path"]), "instances": res["instances"],
            "obstructions": res["obstructions"], "unversioned": res["unversioned"],
            "laws": sorted(res["laws"])}


class _Producer:
    part = "par_record"   # run by derive's par_record part (holon.rules._par_record_part) only

    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.par_record.{subform}"

    def produce(self, ctx) -> list:
        """(law, DERIVATION entry) pairs of this sub-form over the milestone's linked codec documents."""
        items = documents(ctx.milestone, Path(ctx.root), getattr(ctx, "inputs", None))
        res = derive_documents(items)
        out = []
        for lid, x in sorted(res["laws"].items()):
            if x["subform"] != self.subform:
                continue
            rel = next(r for r, d, g in items if g["model"] == x["basis"]["model"])
            law = {"ir_version": "holon-ir/0.3", "law_id": lid, "milestone": ctx.milestone, "rule": RULE,
                   "subform": x["subform"], "rule_catalog_version": ctx.rule_catalog_version, "facts": rel,
                   "facts_sha256": _sha(Path(ctx.root) / rel), "notes": x["notes"], "statement": x["statement"]}
            out.append((law, {"law_id": lid, "rule": RULE, "subform": x["subform"], "facts": rel,
                              "basis": x["basis"], "entry_points": []}))
        return out


PRODUCERS = {sub: _Producer(sub) for sub in SUBFORMS}
