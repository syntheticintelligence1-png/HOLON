"""The back-test across documents (BUILD_PLAN I24 exit; whitepaper §9.4, L22; rules B1-B5 of the docstring of
tests_m3/test_derive_par.py): `python -m holon backtest --milestone M3 [--out FILE] [--root DIR]`.

  B1 The name map mu is spec/<M>/lib/backtest_map.json, frozen at the prereg; it is read here and never recomputed
     (the derivation never reads it). It maps the names of the hand document every M0 law is about to the names of
     the milestone's linked codec components.
  B2 Pairing. An M3 law S and an M0 law O are paired iff every binder type, function and field of S has a preimage
     under mu and the collapse of S (renamed into the hand names; two binders of one hand type merged wherever every
     premise relating them equates one hand field of each, those premises dropped) is alpha-equivalent to O (rule
     P11's normal form, holon.rules.par.canonical, the facts file aside). A row pairs only when exactly one M3 law
     does.
  B3 Bridges. For a paired row and every function g the M0 law names, B_<old>_<g>: under the M0 law's binders and
     premises (pinned, as holon.gen.laws pins them), the hand function g of the M0 model gen/M0/model/<stem>.bend
     equals mu(g) of the component model gen/<M>/model/<role>.bend applied to the hand value moved into mu(g)'s
     carrier by mu (each image field takes the bytes of its hand preimage). LAWS.bend imports both models; PROOF.bend
     is a proof (an encoder bridge over records at the pinned version: open the record, {==}) or a counter-law. A
     bridge over unbounded byte strings is REFUTED only at a probe (rule X9's probes over the constants of both
     sides' conditions), else UNKNOWN; an UNKNOWN bridge writes no file. Every status is Bend's.
  B4 Acceptance: "bridges" when every bridge is PROVED (S_new instantiated at the moved hand value, with the functions
     equal, implies S_old); "witness" when both laws are REFUTED and the M3 counter-witness, moved by mu, refutes the
     M0 law on the hand model by a Bend-checked counter-law (gen/<M>/backtest/W_<old>/). Otherwise the implication
     is missing (a gap of kind "implication").
  B5 The table results/<M>/backtest.json (sorted rows, gaps, completeness, exit blockers). A row without a paired
     law is a rule gap, never added by hand; its candidates are the M3 laws of the M0 law's sub-form that name the
     image of every M0 function that has one, those at the M0 law's version (its version premise, L4) when any.

Deterministic: no timestamps, no timings; the files under gen/<M>/backtest/ and the table are pure functions of the
committed inputs and Bend's verdicts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from . import bend
from . import facts as F

ROOT = Path(__file__).resolve().parents[1]
HAND_ALIAS = "M"
COMP_ALIAS = "C"


class BacktestError(Exception):
    pass


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _laws(root: Path, m: str) -> dict:
    return {p.stem: _load(p) for p in sorted((root / "laws" / m).glob("L*.json"))}


def _records(root: Path, m: str) -> dict:
    return {p.stem: _load(p) for p in sorted((root / "results" / m).glob("L*.json"))}


def _calls(t) -> set[str]:
    if isinstance(t, list):
        return set().union(set(), *(_calls(x) for x in t))
    if isinstance(t, dict):
        s = {t["call"]} if isinstance(t.get("call"), str) else set()
        return s.union(*(_calls(v) for v in t.values()))
    return set()


def _vars(t) -> set[str]:
    if isinstance(t, list):
        return set().union(set(), *(_vars(x) for x in t))
    if isinstance(t, dict):
        if set(t) == {"var"} and isinstance(t["var"], str):
            return {t["var"]}
        return set().union(set(), *(_vars(v) for v in t.values()))
    return set()


def _subst(t, old: str, new: str):
    if isinstance(t, list):
        return [_subst(x, old, new) for x in t]
    if isinstance(t, dict):
        if set(t) == {"var"} and t["var"] == old:
            return {"var": new}
        return {k: _subst(v, old, new) for k, v in t.items()}
    return t


# ====================================================================== B2: collapse and pairing
def inverse(mu: dict) -> tuple[dict, dict, dict]:
    """(image function -> hand function, component type -> hand type, (carrier, field) -> hand field)."""
    fn = {img: h for h, img in mu["functions"].items() if img}
    ty = {c: h for h, cs in mu["types"].items() for c in cs}
    fld = {(cid, name): hf for _, fmap in mu["fields"].items() for hf, imgs in fmap.items()
           for cid, name in imgs.items()}
    return fn, ty, fld


def collapse(law: dict, mu: dict) -> dict | None:
    """Rule B2's collapse of an M3 law into the hand names (None when a binder type, function or field has no
    preimage), with its binder map {M3 binder: kept hand binder}."""
    fn, ty, fld = inverse(mu)
    st = law["statement"]
    types = {}
    for b in st.get("binders", []):
        if b["type"] not in ty:
            return None
        types[b["name"]] = b["type"]

    def ren(t):
        if isinstance(t, list):
            return [ren(x) for x in t]
        if not isinstance(t, dict):
            return t
        if isinstance(t.get("call"), str):
            if t["call"] not in fn:
                raise KeyError(t["call"])
            return {"call": fn[t["call"]], "args": ren(t["args"])}
        if "field" in t and "of" in t:
            v = t["of"].get("var") if isinstance(t["of"], dict) else None
            key = (types.get(v), t["field"])
            if key not in fld:
                raise KeyError(key)
            return {"field": fld[key], "of": ren(t["of"])}
        return {k: ren(v) for k, v in t.items()}
    try:
        assume, claim = ren(st.get("assume", [])), ren(st["claim"])
    except KeyError:
        return None
    binders = [{"q": b.get("q", "forall"), "name": b["name"], "type": ty[b["type"]]} for b in st.get("binders", [])]
    bmap = {b["name"]: b["name"] for b in binders}

    def same_field(a: dict, x: str, y: str) -> bool:
        if set(a) != {"eq"}:
            return False
        s, t = a["eq"]
        return (isinstance(s, dict) and isinstance(t, dict) and "field" in s and "field" in t
                and s["field"] == t["field"] and {s["of"].get("var"), t["of"].get("var")} == {x, y})
    changed = True
    while changed:
        changed = False
        for i, x in enumerate(binders):
            for y in binders[i + 1:]:
                if x["type"] != y["type"]:
                    continue
                rel = [a for a in assume if {x["name"], y["name"]} <= _vars(a)]
                if not all(same_field(a, x["name"], y["name"]) for a in rel):
                    continue
                assume = _subst([a for a in assume if a not in rel], y["name"], x["name"])
                claim = _subst(claim, y["name"], x["name"])
                binders = [b for b in binders if b["name"] != y["name"]]
                for k, v in bmap.items():
                    if v == y["name"]:
                        bmap[k] = x["name"]
                changed = True
                break
            if changed:
                break
    uniq = []
    for a in assume:
        if a not in uniq:
            uniq.append(a)
    return {"statement": {"binders": binders, "assume": uniq, "claim": claim, "scope": st.get("scope")},
            "binder_map": bmap}


def paired(old: dict, new: dict, mu: dict) -> bool:
    from .rules.par import canonical, canonical_json
    c = collapse(new, mu)
    if c is None:
        return False
    a, b = canonical(old), canonical({"statement": c["statement"]})
    a.pop("facts", None)
    b.pop("facts", None)
    return canonical_json(a) == canonical_json(b)


def version_of(law: dict) -> int | None:
    """The version premise of a law as law_evidence reads it (L4; the tag premise of rule X8c too)."""
    from .diagram.evidence import _version
    st = law["statement"]
    v = _version(st, tag_premise=True) if law.get("ir_version") == "holon-ir/0.3" else _version(st)
    return v


# ====================================================================== B3: bridges
class Context:
    def __init__(self, root: Path, milestone: str, mu: dict, cfg: dict):
        from .diagram import linked as L
        self.root, self.m, self.mu, self.cfg = root, milestone, mu, cfg
        self.hand_rel = mu["hand"]
        self.hand = F.load(root / self.hand_rel)
        from .model_eval import model_name
        self.hand_stem = model_name(root / self.hand_rel)
        self.hand_model = root / "gen" / mu["against"] / "model" / f"{self.hand_stem}.bend"
        self.comps = {}
        for p in L.committed_codecs(milestone, root):
            d = _load(p)
            if d.get("component") in mu["components"]:
                self.comps[p.relative_to(root).as_posix()] = d
        self._hand_cm = None
        self._comp_cm: dict = {}
        self.out = root / "gen" / milestone / "backtest"

    def comp_model_path(self, rel: str) -> Path:
        return self.root / "gen" / self.m / "model" / f"{self.comps[rel]['role']}.bend"

    def hand_cm(self):
        if self._hand_cm is None:
            from .model_eval import CompiledModel
            self._hand_cm = CompiledModel.build(self.root / self.hand_rel, cfg=self.cfg)
        return self._hand_cm

    def comp_cm(self, rel: str):
        if rel not in self._comp_cm:
            from .gen import linked as GL
            raw = (self.root / rel).read_bytes()
            d = json.loads(raw)
            self._comp_cm[rel] = GL.CompiledModel.build(d, hashlib.sha256(raw).hexdigest(), d["role"], self.cfg)
        return self._comp_cm[rel]


def _imports(ctx: Context, rel: str) -> list[str]:
    d = ctx.out / "X"
    import os
    hand = Path(os.path.relpath(ctx.hand_model, d)).as_posix()
    comp = Path(os.path.relpath(ctx.comp_model_path(rel), d)).as_posix()
    return ["import Base", f"import {hand} as {HAND_ALIAS}", f"import {comp} as {COMP_ALIAS}"]


def _move_def(ctx: Context, doc: dict, cid: str) -> list[str]:
    """mv_<carrier>: the hand record moved into component record carrier cid by mu (each image field the bytes of its
    hand preimage), or Unsupported when an image field has no preimage of its width."""
    from .gen import linked as GL
    from .gen import model as G
    _, _, fld = inverse(ctx.mu)
    w = F.widths(ctx.hand)
    cells = []
    for f in GL.records(doc)[cid]:
        hf = fld.get((cid, f["name"]))
        if hf is None or w.get(hf) != f["width"]:
            raise GL.Unsupported(f"{cid}.{f['name']} has no hand preimage of width {f['width']}")
        cells += [f"{hf}_{k}" for k in range(f["width"])]
    return [f"# the hand value moved into {cid} by the name map (each field the bytes of its hand preimage)",
            f"def mv_{cid}(h: {HAND_ALIAS}.Hdr) -> {COMP_ALIAS}.{GL.rec_type(cid)}:", "  match h:",
            f"    case {HAND_ALIAS}.{G.hdr_pattern(ctx.hand)}:",
            f"      {COMP_ALIAS}.{GL.rec_type(cid)}{{{', '.join(cells)}}}"]


def _write(d: Path, laws_text: str, proof_text: str) -> Path:
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    (d / "LAWS.bend").write_text(laws_text)
    (d / "PROOF.bend").write_text(proof_text)
    return d / "PROOF.bend"


def _check(pf: Path, laws_text: str, proof_text: str, name: str, cfg: dict) -> tuple[bool, str | None]:
    r = bend.check(pf, cfg)
    if not r.ok:
        return False, "\n".join(r.out.strip().splitlines()[:6])
    if re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", laws_text, re.M) != [name]:
        return False, f"the law file does not state exactly {name}"
    if bend.escape_hatches(laws_text + proof_text):
        return False, "escape hatch"
    return True, None


def _hand_pins(ctx: Context, old: dict) -> dict:
    from .gen import laws as LG
    return LG.collect_pins(old, ctx.hand)


def encoder_bridge(ctx: Context, old: dict, g: str, img: str, rel: str) -> dict:
    """B_<old>_<g> for an encoder: for h (the M0 law's binder, its premises pinned), g(h) == img(mv(h))."""
    from .gen import laws as LG
    from .gen import linked as GL
    from .gen import model as G
    doc = ctx.comps[rel]
    lid = f"B_{old['law_id']}_{g}"
    name = lid.lower()
    binders = old["statement"]["forall"]
    row = {"fn": g, "image": img, "law": lid}
    f = doc["functions"][img]
    if len(binders) != 1 or binders[0]["type"] != "Header":
        return dict(row, status="UNKNOWN", bound="not generated: an encoder bridge has one hand record binder")
    v = binders[0]["name"]
    try:
        pins = _hand_pins(ctx, old)
        mv = _move_def(ctx, doc, f["from"])
    except (LG.Unsupported, GL.Unsupported) as e:
        return dict(row, status="UNKNOWN", bound=f"not generated: {e}")
    arg = f"pin_{v}({v})" if v in pins else v
    lines = [f"# GENERATED by holon.backtest (rule B3): the hand function {g} of {ctx.hand_rel} equals its image {img} "
             "of the component under the name map,", f"# at the hand value moved by the map, under the premises of "
             f"{old['law_id']}; do not edit.", *_imports(ctx, rel), ""]
    if v in pins:
        lines += LG.pin_def(ctx.hand, v, pins[v]) + [""]
    lines += mv + ["", f"law {name}:", f"  for {v}: {HAND_ALIAS}.Hdr",
                   f"  {{{HAND_ALIAS}.{g}({arg}) == {COMP_ALIAS}.{img}(mv_{f['from']}({arg})) : {G.BYTES}}}"]
    laws_text = "\n".join(lines) + "\n"
    proof = "\n".join(["# GENERATED by holon.backtest; untrusted, accepted only if Bend checks it.", *_imports(ctx, rel),
                       "import ./LAWS.bend as Laws", "",
                       "# class open_refl: open the hand record, then reflexivity",
                       f"def Laws.{name}({v}):", f"  match {v}:",
                       f"    case {HAND_ALIAS}.{G.hdr_pattern(ctx.hand, reuse=False)}:", "      {==}"]) + "\n"
    d = ctx.out / lid
    pf = _write(d, laws_text, proof)
    ok, why = _check(pf, laws_text, proof, name, ctx.cfg)
    if ok:
        return dict(row, status="PROVED")
    shutil.rmtree(d, ignore_errors=True)
    # no proof: the bridge is refuted only through a Bend-checked counter-law at a witness (the hand fills of
    # holon.refute's header candidates, premises pinned); none is attempted here: an encoder bridge that does not
    # compute equal stays UNKNOWN with the checker's answer
    return dict(row, status="UNKNOWN", bound=f"the open_refl proof was rejected: {why}")


def _int_consts(e, out: set) -> set:
    if isinstance(e, bool):
        return out
    if isinstance(e, int):
        out.add(e)
    elif isinstance(e, list):
        for x in e:
            _int_consts(x, out)
    elif isinstance(e, dict):
        for k, x in e.items():
            if k != "code":
                _int_consts(x, out)
    return out


def predicate_bridge(ctx: Context, old: dict, g: str, img: str, rel: str) -> dict:
    """B_<old>_<g> over unbounded byte strings: REFUTED only at a probe (rule X9's probes over the integer constants
    of both sides' conditions), else UNKNOWN (no file is written)."""
    from .gen import linked as GL
    doc = ctx.comps[rel]
    lid = f"B_{old['law_id']}_{g}"
    row = {"fn": g, "image": img, "law": lid}
    ks = sorted(_int_consts(ctx.hand["functions"][g].get("rules", []), set()) | set(GL.probe_constants(doc, [img])))
    ps = GL.probes(ks)
    wits = [GL.probe_bytes(n, t) for n, t in ps]
    hv = ctx.hand_cm().run_jobs([{"terms": [{"call": g, "args": [{"var": "b"}]}], "env": {"b": list(bytes.fromhex(w[2:]))}}
                                 for w in wits])
    cv = ctx.comp_cm(rel).calls([{"fn": img, "args": [{"val": list(bytes.fromhex(w[2:]))}]} for w in wits])
    bound = (f"probes (length, tag byte) from the integer constants {ks} of {g} and {img}: lengths "
             f"{sorted({n for n, _ in ps})} x tag bytes {sorted({t for _, t in ps})} (length 0 with tag 0 only), "
             f"{len(ps)} probes; filler bytes ((i * 37) mod 255) + 1")
    for (n, t), w, a, b in zip(ps, wits, hv, cv):
        if a[0] != b:
            return dict(row, status="UNKNOWN", bound=bound + f"; the sides differ at length {n}, tag byte {t}, but no "
                        "counter-law generator for a predicate bridge exists here")
    return dict(row, status="UNKNOWN", bound=bound + "; no probe distinguishes the sides, and a bridge over unbounded "
                                                     "byte strings has no proof route here (gap G6)")


# ====================================================================== B4: witness transfer
def move_witness(ctx: Context, new: dict, old: dict, w: dict) -> dict | None:
    """The M3 witness in the hand names: a byte string as is; a record binder's fields at their hand preimages
    (binders merged by the collapse must agree on every shared field). None when some hand binder's field gets no
    value or two values."""
    c = collapse(new, ctx.mu)
    if c is None:
        return None
    _, ty, fld = inverse(ctx.mu)
    types = {b["name"]: b["type"] for b in new["statement"]["binders"]}
    out: dict = {}
    for nb, ob in c["binder_map"].items():
        val = w.get(nb)
        if ctx.hand["types"].get(ty.get(types[nb]), {}).get("kind") == "bytes":   # a byte string moves as itself
            if ob in out and out[ob] != val:
                return None
            out[ob] = val
            continue
        if not isinstance(val, dict):
            return None
        rec = out.setdefault(ob, {})
        for cf, hexv in val.items():
            hf = fld.get((types[nb], cf))
            if hf is None:
                continue
            if hf in rec and rec[hf] != hexv:
                return None
            rec[hf] = hexv
    hb = {b["name"]: b["type"] for b in old["statement"]["forall"]}
    for b, t in hb.items():
        if t == "Header":
            if set(out.get(b, {})) != set(F.widths(ctx.hand)):
                return None
        elif not isinstance(out.get(b), str):
            return None
    if set(out) != set(hb):
        return None
    return out


def witness_transfer(ctx: Context, old: dict, new: dict, new_rec: dict) -> dict:
    """W_<old>: the M0 law's counter-law on the hand model at the moved M3 witness (holon.gen.laws and
    holon.gen.proofs.counter, the M0 machinery), Bend-checked."""
    from .gen import laws as LG
    from .gen import proofs as PG
    lid = f"W_{old['law_id']}"
    out = {"law": lid, "status": "UNKNOWN", "witness": None}
    w = move_witness(ctx, new, old, new_rec.get("witness") or {})
    if w is None:
        return dict(out, bound="the M3 witness has no image in the hand names")
    out["witness"] = w
    import os
    imp = Path(os.path.relpath(ctx.hand_model, ctx.out / lid)).as_posix()
    try:
        em = LG.emit(old, ctx.hand, imp, counter=True, header_note=f"the counter-law of {old['law_id']} at the moved "
                                                                    f"witness of {new['law_id']} (rule B4)")
        text = PG.counter(em, ctx.hand, imp, w)
    except (LG.Unsupported, ValueError, KeyError) as e:
        return dict(out, bound=f"not generated: {e}")
    text = text.replace("# GENERATED by holon.gen.proofs", "# GENERATED by holon.backtest (rule B4) with holon.gen.proofs", 1)
    pf = _write(ctx.out / lid, em.text, text)
    ok, why = _check(pf, em.text, text, em.name, ctx.cfg)
    if not ok:
        shutil.rmtree(ctx.out / lid, ignore_errors=True)
        return dict(out, bound=f"the counter-law was rejected: {why}")
    return dict(out, status="REFUTED")


# ====================================================================== B5: the table
def build(milestone: str, root: Path, cfg: dict) -> dict:
    root = Path(root)
    map_rel = Path("spec") / milestone / "lib" / "backtest_map.json"
    mu = _load(root / map_rel)
    against = mu["against"]
    ctx = Context(root, milestone, mu, cfg)
    if not ctx.comps:
        raise BacktestError(f"no committed codec document of {mu['components']} under gen/{milestone}/codec")
    shutil.rmtree(ctx.out, ignore_errors=True)
    old_laws, old_recs = _laws(root, against), _records(root, against)
    new_laws = {lid: law for lid, law in _laws(root, milestone).items()
                if law.get("rule") == "PAR" and law.get("facts") in ctx.comps}
    new_recs = _records(root, milestone)
    rows, gaps = [], []
    for oid, old in sorted(old_laws.items()):
        hits = sorted(lid for lid, law in new_laws.items() if paired(old, law, mu))
        new = hits[0] if len(hits) == 1 else None
        row = {"old": oid, "old_status": (old_recs.get(oid) or {}).get("status"), "new": new, "new_status": None,
               "same_status": None, "bridges": [], "acceptance": None, "implication": None, "gap": None}
        if new is None:
            gap = rule_gap(ctx, old, new_laws, hits)
            gaps.append(gap)
            row["gap"] = gap["id"]
            rows.append(row)
            continue
        law = new_laws[new]
        rel = law["facts"]
        nst = (new_recs.get(new) or {}).get("status")
        row["new_status"] = nst
        row["same_status"] = (nst == row["old_status"]) if nst and row["old_status"] else None
        names = sorted(_calls(old["statement"]["claim"]) | _calls(old["statement"].get("assume", [])))
        for g in names:
            img = mu["functions"].get(g)
            if img is None:
                row["bridges"].append({"fn": g, "image": None, "law": None, "status": None,
                                       "bound": "no image under the name map"})
                continue
            kind = ctx.hand["functions"][g]["kind"]
            if kind == "encoder":
                row["bridges"].append(encoder_bridge(ctx, old, g, img, rel))
            elif kind == "predicate":
                row["bridges"].append(predicate_bridge(ctx, old, g, img, rel))
            else:
                row["bridges"].append({"fn": g, "image": img, "law": f"B_{oid}_{g}", "status": "UNKNOWN",
                                       "bound": f"no bridge generator for a hand {kind}"})
        if row["bridges"] and all(b["status"] == "PROVED" for b in row["bridges"]):
            row["acceptance"] = "bridges"
            if row["old_status"] == "REFUTED" and nst == "REFUTED":
                row["note"] = ("Accepted by bridges: the hand functions equal their extracted images, so the M3 "
                               "statement, instantiated at the moved hand value, implies the M0 statement. Both laws "
                               "are REFUTED, and that implication says nothing about either counter-witness: the "
                               "bridges carry no obstruction-transfer content (no witness was moved or re-checked "
                               "for this row).")
        elif row["old_status"] == "REFUTED" and nst == "REFUTED":
            tr = witness_transfer(ctx, old, law, new_recs[new])
            row["transfer"] = tr
            if tr["status"] == "REFUTED":
                row["acceptance"] = "witness"
        row["implication"] = "accepted" if row["acceptance"] else "missing"
        if not row["acceptance"]:
            gap = {"id": f"gap:{against}:{oid}", "law": oid, "milestone": against, "kind": "implication",
                   "status": "open", "reason": "paired, but no bridge set is PROVED and no counter-witness transfers "
                                               "(rule B4)", "candidates": [new]}
            gaps.append(gap)
            row["gap"] = gap["id"]
        rows.append(row)
    gaps.sort(key=lambda g: g["id"])
    complete = all(r["implication"] == "accepted" or r["gap"] is not None for r in rows)
    return {"document": "backtest", "milestone": milestone, "against": against,
            "map": {"path": map_rel.as_posix(), "sha256": _sha(root / map_rel)},
            "rows": rows, "gaps": gaps, "complete": complete,
            "exit_blockers": sorted(g["id"] for g in gaps if g["status"] == "open")}


def rule_gap(ctx: Context, old: dict, new_laws: dict, hits: list) -> dict:
    """B5: a missed M0 law (no M3 law, or more than one, pairs with it): a rule gap with its candidates."""
    mu = ctx.mu
    oid = old["law_id"]
    names = sorted(_calls(old["statement"]))
    imgs = {mu["functions"][g] for g in names if mu["functions"].get(g)}
    noimg = [g for g in names if not mu["functions"].get(g)]
    cands = [lid for lid, law in sorted(new_laws.items())
             if law.get("subform") == old.get("subform") and imgs <= _calls(law["statement"])]
    v = version_of(old)
    at_v = [lid for lid in cands if v is not None and version_of(new_laws[lid]) == v]
    chosen = sorted(at_v or cands)
    if hits:
        why = f"{len(hits)} M3 laws collapse to it ({', '.join(hits)}): the pairing is ambiguous (rule B2)"
    elif noimg:
        why = (f"{', '.join(noimg)} {'has' if len(noimg) == 1 else 'have'} no image under the name map, so no M3 law's "
               "collapse can be alpha-equivalent to it (rule B2)")
    elif not at_v and v is not None:
        vs = sorted({version_of(new_laws[c]) for c in cands if version_of(new_laws[c]) is not None})
        why = (f"no M3 law of sub-form {old.get('subform')} naming {', '.join(sorted(imgs))} is at version {v}: the "
               f"candidates are at version(s) {vs} (rule B2 finds no alpha-equivalent collapse)")
    else:
        why = "no M3 law's collapse under the name map is alpha-equivalent to it (rule B2)"
    return {"id": f"gap:{mu['against']}:{oid}", "law": oid, "milestone": mu["against"], "kind": "rule",
            "status": "open", "reason": why + "; a missed M0 law is a rule gap, never added by hand (rule admission "
                                              "and closing it are I45's)", "candidates": chosen}


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon backtest", description="the back-test across documents (rules B1-B5)")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=None)
    ap.add_argument("--out", default=None, help="the table (default <root>/results/<milestone>/backtest.json)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    cfg = bend.config(root)
    try:
        doc = build(a.milestone, root, cfg)
    except (BacktestError, OSError, ValueError, KeyError) as e:
        print(f"holon backtest: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out = Path(a.out) if a.out else root / "results" / a.milestone / "backtest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(doc), encoding="utf-8")
    acc = sum(1 for r in doc["rows"] if r["implication"] == "accepted")
    print(f"holon backtest: {len(doc['rows'])} {doc['against']} laws, {acc} accepted, {len(doc['gaps'])} open gaps "
          f"-> {out}")
    for r in doc["rows"]:
        print(f"  {r['old']:16s} {r['new'] or '-':52s} {r['acceptance'] or r['gap']}")
    return 0
