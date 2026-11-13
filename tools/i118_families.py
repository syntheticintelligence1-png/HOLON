"""I118 (2), Q92 (2): per rule family, why a composed run derives no law, as pre-decision aggregates (Q72).

  python tools/i118_families.py --vault DIR [--out results/M6/I118/families.json]

A measurement that builds nothing (spec/M6/predictions/I118.json thresholds.families). It reads, per target, only what
the composed run wrote before any decision, from the vault copy of each row's output (<vault>/out/<id>/: laws/
DERIVATION.json (or <vault>/laws/<id>/laws/, where withhold() moves it), gen/sorts/types.json and opaque.json, gen/disch/closure.json and fallback.json, gen/evidence.json, the
generated sidecars undo.json and fact.json). For every (rule, subform) of the protocol's catalog it records the laws
derived and the family's input as counts, and a reason: derived (laws > 0); no_input (an input count is 0: the family
covers nothing the target declares, a reported coverage limit); input_no_law (inputs present, no law); part_absent (a
part that reads milestone inputs the composed route never generates); unmeasured (an input file over the run's storage
limit, recorded by hash only in large_files.json). No law id, verdict or document name is written. Outside holon/:
it only reads files.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABEL = "contaminated: post-I107"
TYPED = {"SORT": ("as_member", "realize", "reinterpret"), "DISCH": ("blocking", "revert", "external", "external_none"),
         "UNDO": ("cancel", "pair", "residue"), "FACT": ("attribution", "kernel"),
         "SYM": ("omega", "pi", "sentinel", "tau")}
ROUTE_C_PAR = ("branch", "consumer", "cross_component_codec", "cycle", "domain_coherence", "init", "recompute",
               "round_trip", "totality", "weak")


def load(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except ValueError:
        return None


def inputs(e: Path) -> dict:
    """The input counts of each typed family and route C's PAR, from one row's pre-decision outputs (None: the file
    is absent or over the storage limit)."""
    large = {x["path"] for x in (load(e / "large_files.json") or [])}

    def get(rel: str):
        return "unmeasured" if rel in large else load(e / rel)
    ty, op, cl = get("gen/sorts/types.json"), get("gen/sorts/opaque.json"), get("gen/disch/closure.json")
    ev, us, fs = get("gen/evidence.json"), get("sidecars/undo.json"), get("sidecars/fact.json")

    def n(x, f):
        return "unmeasured" if x == "unmeasured" else (f(x) if isinstance(x, dict) else 0)
    models = lambda x: (x.get("models") or {}).values()
    typed = n(ty, lambda x: len(x.get("models") or {}))
    sort = {"typed_documents": typed, "coercions": n(ty, lambda x: sum(len(m.get("coercions") or []) for m in models(x))),
            "typed_operations": n(ty, lambda x: sum(len(m.get("ops") or []) for m in models(x)))}
    disch = {"analysed_documents": n(cl, lambda x: len(x.get("models") or {})),
             "permission_classes": n(cl, lambda x: sum(len(m.get("classes") or {}) for m in models(x)))}
    undo = {"typed_documents": typed, "observations": n(us, lambda x: len(x.get("observation") or []))}
    fact = {"hypotheses": n(fs, lambda x: len(x.get("hypotheses") or {}))}
    sym = {"typed_documents": typed, "ghosts": n(ty, lambda x: sum(len(m.get("ghosts") or {}) for m in models(x))),
           "external_guards": n(ty, lambda x: sum(len(m.get("external_guards") or []) for m in models(x)))}
    par = {"component_models": n(ev, lambda x: sum(1 for m in (x.get("models") or {}).values()
                                                   if isinstance(m, dict) and m.get("facts_version") not in
                                                   ("holon-facts/0.3", "holon-versions/0.1")))}
    return {"SORT": sort, "DISCH": disch, "UNDO": undo, "FACT": fact, "SYM": sym, "PAR": par,
            "_opaque": n(op, lambda x: len(x.get("documents") or []))}


def families(e: Path, catalog: dict) -> dict:
    # withhold() (Q56) moves a row's laws into <vault>/laws/<id>/laws; derive's DERIVATION.json is read from either
    der = load(e / "laws" / "DERIVATION.json") or load(e.parent.parent / "laws" / e.name / "laws" / "DERIVATION.json") or {}
    count: dict = {}
    for x in der.get("laws") or []:
        k = f"{x.get('rule')}/{x.get('subform')}"
        count[k] = count.get(k, 0) + 1
    ins = inputs(e)
    out = {}
    for rule in sorted(catalog):
        for sub in sorted(catalog[rule]):
            k = f"{rule}/{sub}"
            laws = count.get(k, 0)
            if rule in TYPED and sub in TYPED[rule]:
                i = ins[rule]
            elif rule == "PAR" and sub in ROUTE_C_PAR:
                i = ins["PAR"]
            else:
                i = None
            if laws:
                why = "derived"
            elif i is None:
                why = "part_absent"
            elif any(v == "unmeasured" for v in i.values()):
                why = "unmeasured"
            elif any(v == 0 for v in i.values()):
                why = "no_input"
            else:
                why = "input_no_law"
            out[k] = {"laws": laws, "input": i, "reason": why}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", required=True)
    ap.add_argument("--out", default=str(ROOT / "results" / "M6" / "I118" / "families.json"))
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    sys.path.insert(0, str(ROOT))
    from holon import rules as R
    raw = json.loads((vault / "out" / "corpus.json").read_text(encoding="utf-8"))
    proto = json.loads((ROOT / "spec" / "M6" / "lib" / "i118_run.json").read_text(encoding="utf-8"))
    cat = {r: sorted(R.CATALOGS[proto["catalog"]][r]) for r in R.CATALOGS[proto["catalog"]]}
    targets = []
    for r in raw["rows"]:
        e = vault / "out" / r["id"]
        fam = families(e, cat)
        targets.append({"id": r["id"], "system": r.get("system"), "families": fam,
                        "reasons": {w: sum(1 for v in fam.values() if v["reason"] == w)
                                    for w in sorted({v["reason"] for v in fam.values()})},
                        "opaque_documents": inputs(e)["_opaque"]})
    doc = {"label": LABEL, "doc": __doc__.split("\n\n")[0].strip(), "catalog": proto["catalog"], "targets": targets}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps({t["id"]: t["reasons"] for t in targets}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
