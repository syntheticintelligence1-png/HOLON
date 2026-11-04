"""`python -m holon historical laws`: the historical evidence of every M0 law and every M2 law record (the contract is
the docstring of tests_m2/test_historical_exit.py, "historical laws").

    python -m holon historical laws [--milestone M2]

results/<M>/historical/laws.json: {"laws": {"<M>/<law id>": {"status", "edges": {"<edge>": {"compared", "agree",
"disagreements"}}, "premise_inhabitants", "realized", "site", "reached", "why"?}}}, one entry per law of laws/M0 and per
record results/<M>/L_*.json. Each edge's evidence is its historical refinement record's (results/<M>/refinement/
historical/<edge>.json) compared, agree and disagreements.

M0 laws (the frozen header model; the corpus of holon.historical.codec: every real parent header, in replay.json's
order):
  edges                the historical records of the law's facts whose edge the statement calls;
  premise_inhabitants  a Header law (one binder of type Header): the real parent headers h with ok_go(h) on the model
                       whose H = dec_go(h) satisfies every assume clause, each clause evaluated on the model; a Bytes
                       law: every real parent header (its assume clauses evaluated the same way);
  realized             for a REFUTED law, the inhabitants on which its claim (an eq) is false on the model; null
                       otherwise.
M2 law records:
  edges                the actions with a historical record (results/<M>/refinement/historical/, a TRANS diagram
                       edge) that the record's cone names: a cone entry one of whose "_"-separated tokens is the
                       action's name exactly;
  premise_inhabitants  null;
  site                 the law's span (width_site.span, else the record's "site" without its leading document name
                       and trailing digest: "<path>:<lines>") when its path is code the trans replay runs: a unit some
                       record of the replayed transitions document lies in (the implementation and the libraries it
                       inlines); else null, with "why";
  reached              the steps of trans.json whose "sites" hold a line of the span;
  realized             the reached steps at which the site's obstruction occurs: the model reverted at a check whose
                       span lies within the law's span (a Panic or revert attributed to it), or, for a width law, a
                       value outside the field's width at the store (trans.json width_sites).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import ir
from ..machine import source_span

ROOT = Path(__file__).resolve().parents[2]


def write(doc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(ir.canonical_json(doc) + b"\n")
    tmp.replace(path)


def statement_calls(node) -> set:
    if isinstance(node, dict):
        out = {node["call"]} if isinstance(node.get("call"), str) else set()
        for v in node.values():
            out |= statement_calls(v)
        return out
    if isinstance(node, list):
        out = set()
        for v in node:
            out |= statement_calls(v)
        return out
    return set()


def records(milestone: str, root: Path) -> dict:
    d = Path(root) / "results" / milestone / "refinement" / "historical"
    return {p.stem: json.loads(p.read_text()) for p in sorted(d.glob("*.json"))}


def evidence(rec: dict) -> dict:
    return {k: rec[k] for k in ("compared", "agree", "disagreements")}


def _eval(model, facts, law: dict, xs: list, terms: list) -> list:
    """The model's values of `terms` (law IR terms over the law's single binder) on each x."""
    from ..gen import laws as LG
    from ..model_eval import value_in
    v = law["statement"]["forall"][0]
    t = LG.binder_types(law)[v["name"]]
    out = []
    for k in range(0, len(xs), 4000):
        out += model.run_jobs([{"terms": terms, "env": {v["name"]: value_in(t, x, facts)}} for x in xs[k:k + 4000]])
    return out


def _holds(vals: list, pairs: int) -> bool:
    return all(not (isinstance(vals[2 * i], dict) and "error" in vals[2 * i])
               and ir.canonical_json(vals[2 * i]) == ir.canonical_json(vals[2 * i + 1]) for i in range(pairs))


def m0_entries(milestone: str, root: Path, recs: dict) -> dict:
    from .codec import corpus, load_replay, model_view
    from .context import Window
    from .checks import model as header_model
    hm = header_model(root)
    w = Window(milestone, root)
    rep, _p = load_replay(milestone, root)
    items = corpus(w, rep)
    model_view(hm, items)
    out = {}
    for law in sorted(ir.load_laws("M0", root), key=lambda x: x["law_id"]):
        lid = law["law_id"]
        res = json.loads((Path(root) / "results" / "M0" / f"{lid}.json").read_text())
        mine = {e: r for e, r in recs.items() if r.get("facts") == law["facts"]}
        edges = {e: evidence(mine[e]) for e in sorted(statement_calls(law["statement"]) & set(mine))}
        st = law["statement"]
        b = st["forall"]
        if len(b) != 1 or b[0]["type"] not in ("Header", "Bytes"):
            out[f"M0/{lid}"] = {"status": res["status"], "edges": edges, "premise_inhabitants": None,
                                "realized": None, "site": None, "reached": None,
                                "why": "not a law over one Header or Bytes binder"}
            continue
        if b[0]["type"] == "Header":
            xs = [it["H"] for it in items if it["ok_go"] and it["H"] is not None]
        else:
            xs = ["0x" + it["bytes"].hex() for it in items]
        prem = st.get("assume") or []
        if prem:
            vals = _eval(hm.model, hm.facts, law, xs, [s for p in prem for s in p["eq"]])
            inh = [x for x, v in zip(xs, vals) if _holds(v, len(prem))]
        else:
            inh = xs
        realized = None
        if res["status"] == "REFUTED":
            vals = _eval(hm.model, hm.facts, law, inh, list(st["claim"]["eq"])) if inh else []
            realized = sum(1 for v in vals if not _holds(v, 1))
        out[f"M0/{lid}"] = {"status": res["status"], "edges": edges, "premise_inhabitants": len(inh),
                            "realized": realized, "site": None, "reached": None}
    return out


def code_units(doc: dict) -> set:
    """The source units the records of a transitions document lie in (src and stack spans)."""
    units = set()

    def add(src):
        sp = source_span(src)
        if sp is not None:
            units.add(sp[0])
    for a in doc.get("actions") or []:
        for sec in ("guards", "panics", "calls", "checks", "writes", "mstores", "events", "loops"):
            for r in a.get(sec) or []:
                if not isinstance(r, dict):
                    continue
                add(r.get("src"))
                for x in r.get("stack") or []:
                    add(x)
                for x in r.get("reaches") or []:
                    for y in x.get("stack") or []:
                        add(y)
    return units


def law_span(rec: dict) -> str | None:
    ws = rec.get("width_site") or {}
    if ws.get("span"):
        return ws["span"]
    s = rec.get("site")
    if not isinstance(s, str):
        return None
    return ":".join(s.split(":")[1:3])


def m2_entries(milestone: str, root: Path, recs: dict) -> dict:
    trans = json.loads((Path(root) / "results" / milestone / "historical" / "trans.json").read_text())
    doc = json.loads((Path(root) / trans["facts"]).read_text())
    units = code_units(doc)
    actions = sorted(e for e, r in recs.items() if str(r.get("diagram_edge") or "").startswith("TRANS."))
    out = {}
    for p in sorted((Path(root) / "results" / milestone).glob("L_*.json")):
        rec = json.loads(p.read_text())
        lid = rec.get("law_id") or p.stem
        cone = rec.get("cone") or []
        edges = {a: evidence(recs[a]) for a in actions if any(a in str(c).split("_") for c in cone)}
        span = law_span(rec)
        sp = source_span(span) if span else None
        e = {"status": rec["status"], "edges": edges, "premise_inhabitants": None, "realized": None,
             "site": None, "reached": None}
        if sp is None:
            e["why"] = (f"the law's span {span!r} is a facts definition ({rec.get('site')}), not source code the trans "
                        "replay runs") if span else "the record names no site"
        elif sp[0] not in units:
            e["why"] = (f"{sp[0]} is not code the trans replay runs: the replayed implementation's code is "
                        f"{', '.join(sorted(units))} (another contract's code)")
        else:
            unit, lo, hi = sp
            lines = {f"{unit}:{n}" for n in range(lo, hi + 1)}
            reached = [x for x in trans["steps"] if lines & set(x["sites"])]
            if (rec.get("width_site") or {}).get("span"):
                realized = int((trans.get("width_sites") or {}).get(span, {}).get("over", 0))
            else:
                realized = 0
                for x in reached:
                    g = (x.get("revert") or {}).get("guard")
                    gs = source_span(str(g).split("#")[1]) if g and "#" in str(g) else None
                    if gs is not None and gs[0] == unit and lo <= gs[1] and gs[2] <= hi:
                        realized += 1
            e.update({"site": span, "reached": len(reached), "realized": realized})
        out[f"{milestone}/{lid}"] = e
    return out


def run(milestone: str = "M2", root: Path = ROOT) -> dict:
    recs = records(milestone, root)
    laws = {**m0_entries(milestone, root, recs), **m2_entries(milestone, root, recs)}
    return {"doc": "I23 per-law historical evidence (holon.historical.laws): edges are the historical refinement "
                   "records the law's statement (M0) or cone (M2) uses; premise inhabitants and realizations are "
                   "evaluated on the frozen M0 model over every real parent header; M2 site reach and realization "
                   "are read from the trans replay's evaluated source lines (results/<M>/historical/trans.json).",
            "laws": dict(sorted(laws.items()))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon historical laws")
    ap.add_argument("--milestone", default="M2")
    a = ap.parse_args(argv)
    try:
        doc = run(a.milestone, ROOT)
    except (OSError, ValueError, KeyError) as e:
        print(f"historical laws: {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    out = ROOT / "results" / a.milestone / "historical" / "laws.json"
    write(doc, out)
    for k, v in doc["laws"].items():
        print(f"{k:60s} {v['status']:8s} inhabitants {v['premise_inhabitants']} realized {v['realized']} "
              f"reached {v['reached']} edges {sorted(v['edges'])}")
    print(f"wrote {out}")
    return 0
