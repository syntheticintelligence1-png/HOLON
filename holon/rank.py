"""§10.10's ranking of a milestone's obstructions (BUILD_PLAN row I81 = I44a; whitepaper §10.10 and §11.3's Impact
column; the contract is the docstring of tests_m3/test_ranking.py, rules K1-K8, PE1-PE3, RE1-RE3 and CO1).

  python -m holon rank --milestone M [--root R] [--out PATH] [--check]

writes results/<M>/ranking.json (holon-ranking/0.1, spec/schemas/ranking.schema.json): Def 6.13's measure of every law
(holon.measures) and, for every REFUTED law, its impact and its place in the lexicographic order

  sink class      the sidecar's sink class of the channel on which the witness's two sides diverge (K1-K8)
  persistence     how long the obstruction lasts: a pure-function defect until the code changes, a DISCH guard by
                  I32's class (discharge profiles feed persistence, §10.10), anything else undecided (PE1-PE3)
  reach class     the most privileged principal class the witness schedule needs (RE1-RE3)
  adversary cost  the schedule's state-changing calls (CO1); gas waits on the sidecar's cost key

Each dimension's order is the sidecar's (most severe first); ties go to the law id. --check writes nothing and exits 0
iff the regeneration is byte-identical to the committed document. No checker, solver or node runs.

Nothing here names a target: every name comes from the laws, the records, the documents and the sidecar.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import measures as MS
from .measures import Ctx, claim_term, has_reach

ROOT = Path(__file__).resolve().parents[1]
UNKNOWN_COST = 1 << 30
VIEWS = ("view", "pure")


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _goops(doc: dict) -> bool:
    from .diagram.goops import is_goops
    return is_goops(doc)


def _panic_outcome() -> str:
    from .gen.goloop import OUTS
    return OUTS[0]


def _reverts(ob) -> bool:
    """A model observation that is a revert: the typed replay's outcome string ("ok" | "rev <reason>",
    holon.sorts.run3) or an observation object with a status."""
    if isinstance(ob, str):
        return ob.startswith("rev")
    return isinstance(ob, dict) and ob.get("status") == "revert"


# ====================================================================== channels (K1-K8)
def channel(ctx: Ctx, lid: str, law: dict, rec: dict) -> tuple[str, str]:
    rule, term = law.get("rule"), claim_term(law)
    if rec.get("triage") == "intent_question":
        return "intent", "K1: the record is triaged an intent question"
    if rule == "DISCH":
        return "guard", "K2: the basis element is a guard that blocks a principal class's actions"
    if rule == "UNDO":
        e = ctx.report("undo").get(lid)
        i = MS.first_divergence(e) if e else None
        if i is None:
            return "undecided", f"K3: no model divergence in replay/{ctx.m}/undo/report.json"
        step = e["with"]["trace"][e["t_at"] + i]
        a = step.get("action")
        if (ctx.actions(law).get(a) or {}).get("mutability") in VIEWS:
            return "view", f"K3: the first divergent step, t[{i}], is a call of the view {a}"
        ow, oo = e["with"]["model"][e["t_at"] + i], e["without"]["model"][e["t_at"] - 2 + i]
        if ow.get("status") != oo.get("status"):
            return "revert", (f"K3: the first divergent step, t[{i}], a call of {a}, is {ow.get('status')} in one run and "
                              f"{oo.get('status')} in the other")
        return "store", f"K3: the first divergent step, t[{i}], a call of {a}, succeeds in both runs with other outputs"
    if rule == "FACT":
        sub = rec.get("subform") or law.get("subform")
        if sub == "attribution":
            return "attribution", ("K4: the principal whose bond a call puts at risk is not the chooser of the content "
                                   "it is slashed for")
        fid = term.get("fact")
        hit = next((x for x in ctx.fact_analysis(law)["laws"].values() if x.get("fact_id") == fid), None)
        consumer = ((hit or {}).get("basis") or {}).get("consumer")
        doc = ctx.document(law)
        fams = {s.get("name") for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or [])
                if isinstance(s, dict)}
        if consumer in fams:
            return "store", f"K4: the consumer {consumer} is a storage variable the commitment does not determine"
        return "commitment", (f"K4: the consumer {consumer} is what the transaction carries; equal commitments leave it "
                              "free, and readers off the contract consume it")
    if rule == "SORT":
        e = ctx.report("sorts").get(lid)
        if not e:
            return "undecided", f"K5: no entry in replay/{ctx.m}/sorts/report.json"
        rev = sorted(k for k, x in (e.get("entries") or {}).items() if x.get("model") and _reverts(x["model"][-1]))
        if rev:
            return "revert", f"K5: the witness run of {rev[0]} ends in a revert on the model"
        return "store", "K5: every witness run succeeds on the model; the coercion's failure is a value stored"
    if rule == "PAR":
        doc = ctx.document(law)
        if _goops(doc):
            d = rec.get("difference") or {}
            panic = _panic_outcome()
            if any(v is False or v == panic for v in (d.get("lhs"), d.get("rhs"))):
                return "abort", "K6: one op of the Go-op component panics on the witness (a false domain or a panic)"
            return "representation", "K6: both ops complete on the witness with different outcomes"
        if isinstance(term, dict) and "init" in term:
            return "store", "K7: the versioned machine's root write stores a value the chain relation does not hold of"
        sides = law["statement"]["claim"]["eq"]
        if all(isinstance(s, dict) and "call" in s for s in sides):
            fns = doc.get("functions") or {}

            def fn(n):  # ok_<f> is the model's domain predicate of f
                return fns.get(n) or (fns.get(n[3:]) if n.startswith("ok_") else None) or {}
            la, lb = fn(sides[0]["call"]).get("lang"), fn(sides[1]["call"]).get("lang")
            if la and lb:
                if la != lb:
                    return "representation", f"K8: two components disagree on one value across languages ({la}, {lb})"
                return "store", f"K8: two functions of one language ({la}) disagree"
        return "undecided", "no channel rule applies"
    return "undecided", "no channel rule applies"


# ====================================================================== persistence (PE1-PE3)
def persistence(ctx: Ctx, law: dict, measure: dict) -> tuple[str, str]:
    if law.get("rule") == "PAR" and not has_reach(law):
        return "code", "PE1: its paths are pure functions, so the defect holds on its inputs until the code changes"
    if law.get("rule") == "DISCH":
        k = (measure.get("detail") or {}).get("class") or "undecided"
        return k, f"PE2: I32's class of its basis element ({k})"
    return "undecided", "PE3: no DISCH class decides how long its divergence lasts"


# ====================================================================== reach and cost (RE1-RE3, CO1)
def schedule(ctx: Ctx, lid: str, law: dict, rec: dict) -> tuple[list | None, str | None, str]:
    """(the witness schedule's calls or None, the pending key, where the schedule comes from)."""
    w = rec.get("witness") or {}
    rule, term = law.get("rule"), claim_term(law)
    if rule == "UNDO":
        return list(w.get("prefix") or []) + [w["x"], w["y"]] + list(w.get("t") or []), None, "the witness"
    if rule == "FACT":
        if "runs" in w:
            out = []
            for r in w["runs"]:
                out += list(r.get("prefix") or []) + [r["x"]]
            return out, None, "the witness's runs"
        return list(w.get("prefix") or []) + [w["y"]] + list(w.get("t") or []), None, "the witness"
    if rule in ("SORT", "DISCH"):
        return list(w.get("steps") or []), None, "the witness"
    if rule == "PAR" and isinstance(term, dict) and "init" in term:
        return [s for s in w.get("trace") or [] if s.get("kind") == "call"], None, "the witness's trace (its calls)"
    conc = (ctx.maybe(f"results/{ctx.m}/refute/concretization.json") or {}).get("records") or {}
    c = conc.get(f"{ctx.m}/{lid}") or {}
    if c.get("result") == "path":
        return list(c.get("path") or []), None, "the concretization path"
    pend = (ctx.sidecar.get("pending_reach") or {}).get(c.get("kind"))
    if pend:
        return None, pend, f"no path: the concretization is {c.get('kind')}"
    return None, None, f"no path: the concretization is {c.get('kind') or 'absent'} ({c.get('result') or 'no result'})"


def _holds(t, head) -> bool:
    if isinstance(t, list):
        return (bool(t) and t[0] == head) or any(_holds(x, head) for x in t)
    return False


def _caller_map(t) -> bool:
    if isinstance(t, list):
        return (len(t) == 3 and t[0] == "map" and t[2] == ["caller"]) or any(_caller_map(x) for x in t)
    return False


def pred_kind(pred) -> str:
    """RE2: a principal class's kind from its predicate."""
    if pred is None:
        return "anyone"
    if _holds(pred, "sload"):
        return "slot"
    if isinstance(pred, list) and pred and pred[0] == "call":
        return "call"
    if _caller_map(pred):
        return "mapping"
    if isinstance(pred, list) and pred and pred[0] == "==" and ["caller"] in pred[1:] \
            and any(isinstance(x, list) and x[:1] == ["storage"] for x in pred[1:]):
        return "owner"
    return "undecided"


def principal_classes(ctx: Ctx) -> tuple[dict, dict]:
    """({class id: predicate}, {action: class id}) of I31's principal classes (gen/<M>/disch/closure.json)."""
    d = ctx.maybe(f"gen/{ctx.m}/disch/closure.json") or {}
    preds, of = {}, {}
    for _m, md in sorted((d.get("models") or {}).items()):
        for cid, c in sorted((md.get("classes") or {}).items()):
            preds[cid] = c.get("predicate")
            for a in c.get("actions") or []:
                of.setdefault(a, cid)
    return preds, of


def reach(ctx: Ctx, steps, pending, src: str) -> dict:
    if steps is None:
        kind = "pending" if pending else "undecided"
        return {"class": None, "kind": kind, "classes": [], "pending": pending,
                "why": f"RE1: {src}" + (f"; pending {pending}" if pending else "")}
    preds, of = principal_classes(ctx)
    best, seen = None, set()
    for s in steps:
        cid = of.get(s.get("action"), "anyone")
        seen.add(cid)
        k = pred_kind(preds.get(cid))
        key = (-ctx.tier("reach_order", k), cid)
        if best is None or key < best[0]:
            best = (key, cid, k)
    if best is None:
        return {"class": None, "kind": "undecided", "classes": [], "pending": None, "why": f"RE1: {src} is empty"}
    return {"class": best[1], "kind": best[2], "classes": sorted(seen), "pending": None,
            "why": f"RE3: the most privileged class {src} needs ({best[1]}, {best[2]})"}


def cost(ctx: Ctx, law: dict, steps) -> dict:
    gas = (ctx.sidecar.get("cost") or {}).get("gas")
    if steps is None:
        return {"calls": None, "gas": gas, "why": "CO1: no schedule"}
    acts = ctx.actions(law)
    n = sum(1 for s in steps if (acts.get(s.get("action")) or {}).get("mutability") not in VIEWS)
    return {"calls": n, "gas": gas, "why": "CO1: the schedule's state-changing calls; gas waits on calibrated cost"}


# ====================================================================== the ranking and the document
def impact(ctx: Ctx, lid: str, measure: dict) -> dict:
    law, rec = ctx.laws[lid], ctx.records[lid]
    ch, why = channel(ctx, lid, law, rec)
    sink = ctx.sidecar["channels"].get(ch, "undecided")
    pc, pwhy = persistence(ctx, law, measure)
    steps, pend, src = schedule(ctx, lid, law, rec)
    return {"sink": {"class": sink, "channel": ch, "why": why}, "persistence": {"class": pc, "why": pwhy},
            "reach": reach(ctx, steps, pend, src), "cost": cost(ctx, law, steps)}


def ranking(ctx: Ctx, ms: dict) -> list:
    out = []
    for lid in sorted(ctx.laws):
        rec = ctx.records[lid]
        if rec.get("status") != "REFUTED":
            continue
        imp = impact(ctx, lid, ms[lid])
        c = imp["cost"]["calls"]
        key = [ctx.tier("sink_order", imp["sink"]["class"]), ctx.tier("persistence_order", imp["persistence"]["class"]),
               ctx.tier("reach_order", imp["reach"]["kind"]), c if c is not None else UNKNOWN_COST, lid]
        out.append({"law_id": lid, "rule": ctx.laws[lid].get("rule"), "subform": rec.get("subform"),
                    "triage": rec.get("triage"), "filter_bin": rec.get("filter_bin"),
                    "measure": {"kind": ms[lid]["kind"], "value": ms[lid]["value"]}, "impact": imp, "key": key})
    out.sort(key=lambda e: e["key"])
    for i, e in enumerate(out, 1):
        e["rank"] = i
    return out


def _count(xs) -> dict:
    out: dict = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items()))


def document(root: Path | str, milestone: str) -> dict:
    ctx = Ctx(root, milestone)
    ms = MS.measure_all(ctx)
    rk = ranking(ctx, ms)
    summary = {"laws": len(ms), "refuted": len(rk), "kinds": _count(m["kind"] for m in ms.values()),
               "sinks": _count(e["impact"]["sink"]["class"] for e in rk),
               "persistence": _count(e["impact"]["persistence"]["class"] for e in rk),
               "reach": _count(e["impact"]["reach"]["kind"] for e in rk)}
    return {"ranking_version": MS.RANKING_VERSION, "milestone": milestone,
            "doc": ("Def 6.13's measure of every law of laws/<M> (holon.measures) and §10.10's lexicographic ranking of "
                    "the REFUTED ones (holon.rank) by sink class, persistence, reach class and adversary cost, each "
                    "dimension ordered by the sidecar (most severe first), ties by law id. Computed from the committed "
                    "laws, records, replay reports and documents listed in inputs; the contract is the docstring of "
                    "the I81 tests (tests_m3/test_ranking.py)."),
            "sidecar": {"path": MS.sidecar_rel(milestone), "sha256": ctx.inputs[MS.sidecar_rel(milestone)]},
            "inputs": [{"path": p, "sha256": h} for p, h in sorted(ctx.inputs.items())],
            "rules": MS.rules_summary(ctx, ms), "pending_measures": ctx.sidecar.get("pending_measures") or [],
            "measures": ms, "ranking": rk, "summary": summary}


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon rank", description="Def 6.13's measures and §10.10's ranking")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=None, help="default results/<M>/ranking.json under the root")
    ap.add_argument("--check", action="store_true", help="write nothing; exit 0 iff the committed file is regenerated")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    try:
        text = dumps(document(root, a.milestone))
    except (MS.MeasureError, OSError, KeyError, ValueError) as e:
        print(f"holon rank: {e}", file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else root / "results" / a.milestone / "ranking.json"
    if a.check:
        old = out.read_text() if out.is_file() else None
        if old == text:
            print(f"RANKING OK {out.relative_to(root) if out.is_relative_to(root) else out}")
            return 0
        if old is None:
            print(f"holon rank --check: {out} does not exist", file=sys.stderr)
            return 1
        a_, b_ = old.splitlines(), text.splitlines()
        i = next((k for k in range(min(len(a_), len(b_))) if a_[k] != b_[k]), min(len(a_), len(b_)))
        print(f"holon rank --check: {out} differs from its regeneration at line {i + 1}:\n"
              f"  committed:   {a_[i] if i < len(a_) else '<end>'}\n  regenerated: {b_[i] if i < len(b_) else '<end>'}",
              file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"wrote {out}: {len(json.loads(text)['ranking'])} ranked, {len(json.loads(text)['measures'])} measures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
