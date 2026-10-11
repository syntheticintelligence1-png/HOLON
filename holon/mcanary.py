"""Canaries for state-machine milestones (gate G4, whitepaper §8.8).

A canary is a false law, derived from a PROVED law and emitted through the SAME emitter and proof
generators. Bend must reject every one, for a semantic reason. Each canary carries a counterexample
on which the compiled model shows the canary false. Kinds:

  erase_live  a non-interference law that erases a field the decisions DO read (the relation is not
              a bisimulation): the noninterference generator still runs; Bend must reject it.
  negated     the counter-law of a proved forall law, at a point where the law holds.
  pin_const   an existence (strategy) law with one claimed constant changed (cost, delay, index),
              checked with the original witness.
  negated     (REFUTED laws) the counter-law certificate re-emitted at a point where the law HOLDS
              (the empty trace / the smallest Nat): the certificate's evaluation premise is false there,
              so Bend must reject it for the semantic reason that the model does not refute the law at
              that point. This is the canary kind of the SORT milestones, whose laws are mostly refuted.
  witness_prefix  the same certificate at the witness shortened by one step (the law still holds there).
"""
from __future__ import annotations

import copy

from . import bend
from .gen import mlaws, mproofs

LIVE_FIELDS = ["s_bvh", "s_tag", "t", "paused", "inch", "qlen"]


def _const_nats(claim: dict) -> list[int]:
    """Indices of conjuncts whose right-hand side is a Nat constant."""
    return [i for i, p in enumerate(claim.get("all", [claim])) if "nat" in p["eq"][1]]


def candidates(laws: list[dict], records: dict) -> list[tuple[str, str, dict, dict | None]]:
    """(kind, source law, canary IR, counterexample-or-None) in a fixed order."""
    out = []
    for law in laws:
        lid = law["law_id"]
        rec = records.get(lid)
        if not rec:
            continue
        st = law["statement"]
        if rec["status"] == "REFUTED" and not st.get("assume"):
            bs = [(b["name"], b["type"]) for b in st["binders"]]
            if len(bs) == 1 and bs[0][1] in ("Trace", "Nat") and all(b["q"] == "forall" for b in st["binders"]):
                name, ty = bs[0]
                out.append(("negated", lid, copy.deepcopy(law), {name: [] if ty == "Trace" else 0}))
                w = (rec.get("witness") or {}).get(name)
                if w and (len(w) if ty == "Trace" else w) > 0:   # one step short of the witness
                    out.append(("witness_prefix", lid, copy.deepcopy(law), {name: w[:-1] if ty == "Trace" else w - 1}))
            continue
        if rec["status"] != "PROVED":
            continue
        if law.get("subform") == "dead_residue":
            erased = st["assume"][0]["eq"][0]["proj"]
            for f in LIVE_FIELDS:
                if f in erased:
                    continue
                m = copy.deepcopy(law)
                for p in [m["statement"]["assume"][0], m["statement"]["claim"]]:
                    for side in p["eq"]:
                        side["proj"] = [f]
                out.append(("erase_live", lid, m, None))
            n = copy.deepcopy(law)
            out.append(("negated", lid, n, {"tr": [], "s1": {"run": []}, "s2": {"run": []}}))
        elif [b["type"] for b in st["binders"]] == ["Nat"] and not st.get("assume"):
            out.append(("negated", lid, copy.deepcopy(law), {st["binders"][0]["name"]: 0}))
        elif any(b["q"] == "exists" for b in st["binders"]):
            for i in _const_nats(st["claim"])[-2:]:
                m = copy.deepcopy(law)
                conj = m["statement"]["claim"]["all"][i]
                conj["eq"][1]["nat"] = conj["eq"][1]["nat"] + 1
                out.append(("pin_const", lid, m, rec.get("witness")))
    return out


def run_canaries(cm, laws: list[dict], records: dict, workdir, cfg: dict, max_n: int = 24) -> list[dict]:
    imp = "../model/" + cm.source.name
    (workdir / "model").mkdir(parents=True, exist_ok=True)
    (workdir / "model" / cm.source.name).write_text(cm.source.read_text())
    res = []
    counts: dict = {}
    for kind, src, law, point in candidates(laws, records):
        if len(res) >= max_n:
            break
        k = counts.get(kind, 0)
        law["law_id"] = f"CANARY_{kind}_{k}_{src}"
        law.pop("notes", None)
        E = mlaws.Emitter(cm.m)
        try:
            if kind in ("negated", "witness_prefix"):
                em = E.emit(law, imp, counter=True)
                env = {n: mlaws.value_literal(cm.m, t, point[n]) for _, n, t in em.binders}
                lhs, _, ty = mlaws.Emitter(cm.m).prop(law["statement"]["claim"], env, {n: t for _, n, t in em.binders})
                proof = mproofs.counter(em, cm.m, imp, point, lhs, ty)
                ev = cm.evaluate(law, point)
                if not (all(ev["premises"]) and all(ev["claims"])):
                    continue  # not a point where the law holds
                cex = point
            elif kind == "pin_const":
                em = E.emit(law, imp)
                proof = mproofs.evaluate(em, cm.m, imp, point)
                ev = cm.evaluate(law, point)
                if all(ev["claims"]):
                    continue
                cex = point
            else:
                em = E.emit(law, imp)
                proof = mproofs.noninterference(em, cm.m, imp)
                s = cm.explore(law, {"prefixDepth": 2, "maxPrefixes": 300})
                if s["witness"] is None:
                    continue  # no counterexample found: not certified false, so not a canary
                cex = s["witness"]
        except mlaws.Unsupported:
            continue
        if proof is None:
            continue
        d = workdir / law["law_id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "LAWS.bend").write_text(em.text)
        (d / "PROOF.bend").write_text(proof)
        r = bend.check(d / "PROOF.bend", cfg)
        semantic = r.marker == bend.MARK_FAIL and "- expected :" in r.out
        res.append({"id": law["law_id"], "kind": kind, "source_law": src, "negated": kind in ("negated", "witness_prefix"),
                    "rejected": (not r.ok) and semantic, "checker_first_line": r.first_line, "counterexample": cex,
                    "law": law})
        counts[kind] = k + 1
    return res
