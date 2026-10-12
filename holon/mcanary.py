"""Canaries for state-machine milestones (gate G4, whitepaper §8.8).

A canary is a false law, derived from a PROVED law and emitted through the SAME emitter and proof
generators. Bend must reject every one, for a semantic reason. Each canary carries a counterexample
on which the compiled model shows the canary false. Kinds:

  erase_live   a non-interference law that erases a field the decisions DO read (the relation is not
               a bisimulation): the noninterference generator still runs; Bend must reject it. The live
               fields are the state fields some action's decision reads (Machine.reads), in facts state
               order: no field list is written for a target (audit M2/1 F-M2-05).
  negated      the counter-law of a proved forall law, at a point where the law holds: any binder types
               (State, Trace, Act, Reach, Nat, Bool, Fn, oracle parameters); the point is the law's
               recorded inhabitant (its premises hold there, and it is PROVED) or, without premises,
               the default of every binder; checked on the compiled model before it is used.
  pin_const    an existence (strategy) law with one claimed constant changed (cost, delay, index),
               checked with the original witness.
  flip_const   a proved forall law with one claimed Bool constant flipped (holon-ir/0.2 and 0.3, Reach
               laws included), proved with the generator that proved the source law; the compiled model's
               search must refute the mutant first (else it is no canary).
  shift_const  likewise, with one claimed Nat constant moved up by one.
  core_omit    (M2+ milestones, I8) the core library with one lemma left unproved: a proof that calls it,
               the milestone's own when one does (its committed PROOF.bend), else a generated law restating
               the lemma and proved by calling it, must be rejected (holon.gate.g4_machine requires one).

Kinds are interleaved (one of each in turn) so the canary budget never starves a kind.
"""
from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

from . import bend
from .gen import core as C
from .gen import mlaws, mproofs


def live_fields(m, erased=()) -> list[str]:
    """State fields some action's decision reads (Machine.reads, filled by generation), in facts state order."""
    read = set().union(set(), *m.reads.values())
    return [n for n, _ in m.state if n in read and n not in set(erased) and n != "log"]


def _conjuncts(claim: dict) -> list[dict]:
    return claim["all"] if "all" in claim else [claim]


def _const_nats(claim: dict) -> list[int]:
    """Indices of conjuncts whose right-hand side is a Nat constant."""
    return [i for i, p in enumerate(_conjuncts(claim)) if "eq" in p and "nat" in p["eq"][1]]


def _const_side(p: dict, key: str) -> int | None:
    """The side (0 or 1) of an equation conjunct that is a `key` constant (bool, nat), else None."""
    if "eq" not in p:
        return None
    return next((i for i in (1, 0) if key in p["eq"][i]), None)


def _default_point(law: dict, m) -> dict | None:
    """The default of every binder (no premises): a point every PROVED forall law holds at."""
    pt = {}
    for b in law["statement"]["binders"]:
        t = b["type"]
        if t in ("State", "Reach"):
            pt[b["name"]] = {"run": []}
        elif t == "Trace":
            pt[b["name"]] = []
        elif t == "Nat":
            pt[b["name"]] = 0
        elif t == "Bool":
            pt[b["name"]] = False
        elif t == "Act":
            a = m.actions[0]
            pt[b["name"]] = {"op": a["name"], **{n: m_default(ty) for n, ty in a["inputs"]}}
        elif t.startswith("Fn<") and b["name"] in getattr(m, "oparams", {}):
            pt[b["name"]] = {"table": []}
        elif t == "Fn<Nat,Nat>":
            pt[b["name"]] = {"lam": "id"}
        else:
            return None
    return pt


def m_default(ty: str):
    return {"Nat": 0, "Bool": False}.get(ty, [] if ty.startswith("List<") else 0)


def _point(law: dict, rec: dict, m) -> dict | None:
    """Where the PROVED law holds: its recorded inhabitant when it has premises, else every binder's default."""
    st = law["statement"]
    if st.get("assume") or any(b["type"] == "Reach" for b in st["binders"]):
        nv = rec.get("non_vacuity") or {}
        w = nv.get("witness")
        if nv.get("status") == "inhabited" and isinstance(w, dict):
            return {b["name"]: w[b["name"]] for b in st["binders"] if b["name"] in w} \
                if all(b["name"] in w for b in st["binders"]) else None
        if not st.get("assume"):
            return _default_point(law, m)
        return None
    return _default_point(law, m)


def _generator(rec: dict) -> str | None:
    """The generator that proved the source law (its accepted proof attempt)."""
    for a in reversed(rec.get("attempts") or []):
        if a.get("kind") == "proof" and a.get("marker") == bend.MARK_OK and a.get("generator"):
            return a["generator"]
    return None


def candidates(laws: list[dict], records: dict, m=None) -> list[tuple[str, str, dict, dict | None]]:
    """(kind, source law, canary IR, counterexample-or-point) in a fixed order. `m`: the generated Machine of the
    laws' model (live fields, default points); without it, only the kinds that need none."""
    out = []
    for law in laws:
        lid = law["law_id"]
        rec = records.get(lid)
        if not rec or rec["status"] != "PROVED":
            continue
        st = law["statement"]
        forall = all(b["q"] == "forall" for b in st["binders"])
        if law.get("subform") == "dead_residue":
            erased = st["assume"][0]["eq"][0]["proj"]
            for f in (live_fields(m, erased) if m is not None else []):
                mm = copy.deepcopy(law)
                for p in [mm["statement"]["assume"][0], mm["statement"]["claim"]]:
                    for side in p["eq"]:
                        side["proj"] = [f]
                out.append(("erase_live", lid, mm, None))
            out.append(("negated", lid, copy.deepcopy(law), {"tr": [], "s1": {"run": []}, "s2": {"run": []}}))
        elif [b["type"] for b in st["binders"]] == ["Nat"] and not st.get("assume"):
            out.append(("negated", lid, copy.deepcopy(law), {st["binders"][0]["name"]: 0}))
        elif forall and m is not None:
            pt = _point(law, rec, m)
            if pt is not None:
                out.append(("negated", lid, copy.deepcopy(law), pt))
        if any(b["q"] == "exists" for b in st["binders"]):
            for i in _const_nats(st["claim"])[-2:]:
                mm = copy.deepcopy(law)
                conj = _conjuncts(mm["statement"]["claim"])[i]
                conj["eq"][1]["nat"] = conj["eq"][1]["nat"] + 1
                out.append(("pin_const", lid, mm, rec.get("witness")))
        elif forall and law.get("subform") != "dead_residue":
            for i, p in enumerate(_conjuncts(st["claim"])):
                for kind, key in (("flip_const", "bool"), ("shift_const", "nat")):
                    side = _const_side(p, key)
                    if side is None:
                        continue
                    mm = copy.deepcopy(law)
                    c = _conjuncts(mm["statement"]["claim"])[i]["eq"][side]
                    c[key] = (not c[key]) if key == "bool" else int(c[key]) + 1
                    out.append((kind, lid, mm, None))
    return out


def interleave(cands: list) -> list:
    """One candidate of each kind in turn (kinds in first-appearance order), each kind in its own order."""
    by: dict = {}
    for c in cands:
        by.setdefault(c[0], []).append(c)
    out, i = [], 0
    while any(i < len(v) for v in by.values()):
        out += [v[i] for v in by.values() if i < len(v)]
        i += 1
    return out


def _proof_by(gname: str | None, em, cm, imp: str, d: Path, cfg: dict, tries: int = 24):
    """The source generator's proof of a mutant: (text, check result), or (None, None) when it does not apply.
    reach_invariant searches its slots as holon.mpipeline.reach_search does (no strengthening): every choice Bend
    rejects is a rejection; the last one is recorded."""
    if gname == "reach_invariant":
        try:
            rp = mproofs.ReachProof(em, cm.m, imp, [])
        except mlaws.Unsupported:
            return None, None
        choice: dict = {}
        text, r = None, None
        for _ in range(tries):
            text, slot_at = rp.render(choice)
            (d / "PROOF.bend").write_text(text)
            r = bend.check(d / "PROOF.bend", cfg)
            if r.ok:
                return text, r
            mm = re.search(r"^\s*(\d+)>\|", r.out, re.M)
            slot = slot_at.get(int(mm.group(1))) if mm else None
            if slot is None:
                break
            choice[slot] = choice.get(slot, 0) + 1
            if choice[slot] >= len(rp.candidates(slot[2])):
                break
        return text, r
    if gname == "param_premise":
        texts = mproofs.param_premise(em, cm.m, imp) or []
        text, r = None, None
        for text in texts:
            (d / "PROOF.bend").write_text(text)
            r = bend.check(d / "PROOF.bend", cfg)
            if r.ok:
                return text, r
        return text, r
    g = dict(mproofs.GENERATORS).get(gname or "")
    if g is None or gname == "evaluate":
        return None, None
    text = g(em, cm.m, imp)
    if text is None:
        return None, None
    (d / "PROOF.bend").write_text(text)
    return text, bend.check(d / "PROOF.bend", cfg)


def run_canaries(cm, laws: list[dict], records: dict, workdir, cfg: dict, max_n: int = 24,
                 core: bool = False) -> list[dict]:
    """Emit, prove and check the canaries of `laws` over the compiled machine `cm`. core: the M2+ machinery (the
    proof generators import the core library, emitted into workdir/core)."""
    workdir = Path(workdir)
    imp = "../model/" + cm.source.name
    (workdir / "model").mkdir(parents=True, exist_ok=True)
    (workdir / "model" / cm.source.name).write_text(cm.source.read_text())
    old_mode, old_paste = mproofs.CORE_MODE, mproofs.CORE_PASTE
    if core:
        C.emit(workdir, cfg=cfg)
        mproofs.CORE_MODE, mproofs.CORE_PASTE = "import", ""
    try:
        return _run(cm, laws, records, workdir, cfg, max_n, imp)
    finally:
        mproofs.CORE_MODE, mproofs.CORE_PASTE = old_mode, old_paste


def _resolved(cm, em, law: dict, point: dict) -> dict:
    """A point with its oracle-parameter values resolved to the tables the proof supplies (I12)."""
    if not getattr(cm.m, "oparams", None):
        return point
    from .inhabit import premise_points
    return mlaws.resolve_witness(cm.m, em.binders, point, premise_points(law, cm.m, point))


def _run(cm, laws, records, workdir: Path, cfg: dict, max_n: int, imp: str) -> list[dict]:
    res = []
    counts: dict = {}
    for kind, src, law, point in interleave(candidates(laws, records, cm.m)):
        if len(res) >= max_n:
            break
        k = counts.get(kind, 0)
        law["law_id"] = f"CANARY_{kind}_{k}_{src}"
        law.pop("notes", None)
        E = mlaws.Emitter(cm.m)
        d = workdir / law["law_id"]
        try:
            if kind == "negated":
                ev = cm.evaluate(law, point)
                if not (all(ev["premises"]) and all(ev["claims"])):
                    continue  # not a point where the law holds
                conj = 0 if "all" in law["statement"]["claim"] else None
                em = E.emit(law, imp, counter=True, conjunct=conj)
                wr = _resolved(cm, em, law, point)
                tabs = mlaws.witness_tabs(cm.m, em.binders, wr)
                env = {n: mlaws.value_literal(cm.m, t, wr[n], tabs) for _, n, t in em.binders}
                lhs, _, ty = mlaws.Emitter(cm.m).claims(law["statement"], env, {n: ("State" if t == "Reach" else t)
                                                                               for _, n, t in em.binders})[conj or 0]
                proof = mproofs.counter(em, cm.m, imp, wr, lhs, ty)
                cex = point
            elif kind == "pin_const":
                em = E.emit(law, imp)
                proof = mproofs.evaluate(em, cm.m, imp, point)
                ev = cm.evaluate(law, point)
                if proof is None or all(ev["claims"]):
                    continue
                cex = point
            elif kind in ("flip_const", "shift_const"):
                s = cm.explore(law, {"prefixDepth": 2, "maxPrefixes": 300})
                if s.get("witness") is None:
                    continue  # the mutant is not certified false on the model: not a canary
                em = E.emit(law, imp)
                d.mkdir(parents=True, exist_ok=True)
                (d / "LAWS.bend").write_text(em.text)
                proof, r = _proof_by(_generator(records[src]), em, cm, imp, d, cfg)
                if proof is None:
                    shutil.rmtree(d, ignore_errors=True)
                    continue
                cex = s["witness"]
            else:
                em = E.emit(law, imp)
                proof = mproofs.noninterference(em, cm.m, imp)
                if proof is None:
                    continue
                s = cm.explore(law, {"prefixDepth": 2, "maxPrefixes": 300})
                if s["witness"] is None:
                    continue  # no counterexample found: not certified false, so not a canary
                cex = s["witness"]
        except (mlaws.Unsupported, ValueError, KeyError):
            continue
        if kind not in ("flip_const", "shift_const"):
            d.mkdir(parents=True, exist_ok=True)
            (d / "LAWS.bend").write_text(em.text)
            (d / "PROOF.bend").write_text(proof)
            r = bend.check(d / "PROOF.bend", cfg)
        semantic = r.marker == bend.MARK_FAIL and "- expected :" in r.out
        res.append({"id": law["law_id"], "kind": kind, "source_law": src, "negated": kind == "negated",
                    "rejected": (not r.ok) and semantic, "checker_first_line": r.first_line, "counterexample": cex,
                    "law": law})
        counts[kind] = k + 1
    return res


# ---------------------------------------------------------------- core_omit (M2+, I8)
def core_omit(gen: Path, laws: list[dict], records: dict, workdir: Path, cfg: dict) -> dict:
    """The core-omit canary of an M2+ milestone. A PROVED law whose committed proof calls core lemmas through C
    is re-checked in a copy of gen/<m> whose core leaves the first lemma it calls unproved; when no proof calls
    one, a generated law restating the first catalog lemma that has binders, proved by calling it, is checked
    against a core without it. Either must be rejected, for the semantic reason Bend gives an unproved import
    ("- expected : a filled definition")."""
    workdir = Path(workdir)
    for law in laws:
        rec = records.get(law["law_id"]) or {}
        proof = rec.get("artifacts", {}).get("proof") if rec.get("status") == "PROVED" else None
        p = Path(proof) if proof else None
        if p is not None and not p.is_absolute():
            p = Path(gen).resolve().parents[1] / p
        if p is None or not p.exists():
            continue
        called = C.calls(p.read_text())
        if not called:
            continue
        tmp = workdir / "core_omit" / "gen"
        shutil.rmtree(tmp.parent, ignore_errors=True)
        shutil.copytree(gen, tmp)
        shutil.rmtree(tmp / "core", ignore_errors=True)
        C.emit(tmp, omit=called[0], cfg=cfg)
        target = tmp / p.resolve().relative_to(Path(gen).resolve())
        r = bend.check(target, cfg)
        return _omit_record(f"CANARY_core_omit_0_{law['law_id']}", law["law_id"], called[0], r)
    # no proof of the milestone calls the core: a generated importer of the first lemma with binders
    name, bs, hs, claim, _ = next(e for e in C.CATALOG if e[1])
    d = workdir / "core_omit_synth"
    shutil.rmtree(d, ignore_errors=True)
    C.emit(d, omit=name, cfg=cfg)
    (d / "canary").mkdir(parents=True)
    binders = [f"  for {mo}{n}: {t}" for mo, n, t in bs] + [f"  for {n}: {t}" for n, t in hs]
    (d / "canary" / "LAWS.bend").write_text("\n".join(["# GENERATED by holon.mcanary: a core lemma restated (core_omit "
                                                       "canary)", "import Base", "", "law canary_core:"] + binders
                                                      + [f"  {claim}", ""]))
    args = [n for _, n, _ in bs] + [n for n, _ in hs]
    (d / "canary" / "PROOF.bend").write_text("\n".join(["# GENERATED by holon.mcanary: proved by calling the core lemma",
                                                        "import Base", "import ../core/PROOF.bend as CP",
                                                        "import ../core/LAWS.bend as C", "import ./LAWS.bend as Laws", "",
                                                        f"def Laws.canary_core({', '.join(args)}):",
                                                        f"  C.{name}({', '.join(args)})", ""]))
    r = bend.check(d / "canary" / "PROOF.bend", cfg)
    return _omit_record(f"CANARY_core_omit_0_{name}", None, name, r)


def _omit_record(cid: str, src, lemma: str, r) -> dict:
    semantic = r.marker == bend.MARK_FAIL and "- expected :" in r.out
    return {"id": cid, "kind": "core_omit", "source_law": src, "negated": False, "omitted_lemma": lemma,
            "rejected": (not r.ok) and semantic, "checker_first_line": r.first_line, "counterexample": None,
            "law": None}
