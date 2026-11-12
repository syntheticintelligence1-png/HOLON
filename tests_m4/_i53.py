"""I53's instrument (key I53, spec/M4/predictions.json; protocol spec/M4/lib/I53_protocol.json): every score of the
ablations, the calibration and the §13 metrics written a second time, independently of holon/. Nothing here imports a
holon module; it reads committed files only (the map spec/M3/appendixA_map.json, the records, the metrics files, the
baselines' findings files and I53's outputs) and recomputes from them.

  committed_statuses(root, map_doc)     {set: {law: record}} of every record set the map lists
  verdicts(map_doc, records, removed)   §11.3 / §11.8 verdicts per basis (rule A8 of tests_m3/test_blind.py)
  morph_metrics(root, map_doc, ...)     findings, obstructions_reproduced, rows_held, recall_per_rule, precision
  calibration(rows)                     the protocol's calibration metrics
  sources(root)                         every §13 metric read from its recorded source
  baseline(doc, labels)                 recall per rule, precision and time of one baseline findings file
  delta(a, b)                           a - b, or None
"""
from __future__ import annotations

import json
from pathlib import Path

DECIDED = ("PROVED", "REFUTED", "checked", "failed")
NO_RECORD = "no record"
BASES = ("hand", "code")
ABLATIONS = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")
SYSTEMS = ("morph", "corpus", "heldout")
METRICS = ("recall_per_rule", "precision", "witness_replay_rate", "certificate_coverage", "unknown_rate",
           "unknown_calibration", "canary_acceptance", "cross_kernel_agreement", "mutation_adequacy",
           "refinement_disagreement_rate", "from_scratch_gate_time", "prediction_accuracy")
MILESTONES = ("M0", "M1", "M2", "M3")


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def delta(a, b):
    if isinstance(a, bool) or isinstance(b, bool):
        return None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        d = a - b
        return round(d, 12) if isinstance(d, float) else d
    return None


def ratio(n, d):
    return None if not d else n / d


# ------------------------------------------------------------------------------------------- record sets
def committed_statuses(root: Path, map_doc: dict) -> dict:
    """{set name: {law id: record dict}} for every set of the map, from the committed laws and results."""
    out = {}
    for s in map_doc["sets"]:
        res = root / s["results"]
        recs = {}
        if res.is_file():   # the hypotheses set: {hypothesis: {"status": ...}}
            for h, v in sorted(load(res).items()):
                if isinstance(v, dict):
                    recs[h] = {"status": v.get("status")}
        elif res.is_dir():
            for lp in sorted((root / s["laws"]).glob("L*.json")):
                lid = load(lp)["law_id"]
                rp = res / f"{lid}.json"
                if rp.is_file():
                    recs[lid] = load(rp)
        out[s["name"]] = recs
    return out


def apply(records: dict, removed=(), overrides=None, added=None) -> dict:
    """A copy of records with removed [set, law] pairs dropped, partial overrides merged and added records."""
    out = {s: {k: dict(v) for k, v in laws.items()} for s, laws in records.items()}
    for s, lid in removed or ():
        out.get(s, {}).pop(lid, None)
    for s, laws in (overrides or {}).items():
        for lid, fields in laws.items():
            out.setdefault(s, {}).setdefault(lid, {}).update(fields)
    for s, laws in (added or {}).items():
        for lid, st in laws.items():
            out.setdefault(s, {})[lid] = {"status": st}
    return out


def verdicts(map_doc: dict, records: dict) -> dict:
    """{item: {basis: verdict}} for the obstructions (O) and rows (R): a link whose law has no record in its set is
    gone (the report builds links from the laws a set holds); otherwise rule A8."""
    basis = {s["name"]: s["basis"] for s in map_doc["sets"]}
    out = {}
    for ident, it in map_doc["items"].items():
        if it.get("kind") not in ("obstruction", "row"):
            continue
        v = {}
        for b in BASES:
            ls = [lk for lk in it.get("links", []) if basis.get(lk["set"]) == b and lk["law"] in records.get(lk["set"], {})]
            counted = [lk for lk in ls if lk["counted"]]
            res = "open" if ls else "not mechanized"
            if counted:
                st = [records[lk["set"]][lk["law"]].get("status") or NO_RECORD for lk in counted]
                equal = [x == lk["expect"] for x, lk in zip(st, counted)]
                differs = any(x in DECIDED and x != lk["expect"] for x, lk in zip(st, counted))
                if it["kind"] == "obstruction" and any(equal):
                    res = "reproduced"
                elif it["kind"] == "row" and all(equal):
                    res = "held"
                elif differs:
                    res = "missed" if it["kind"] == "row" else "contradicted"
            v[b] = res
        out[ident] = v
    return out


def families(map_doc: dict) -> dict:
    return {i: list(it.get("families") or []) for i, it in map_doc["items"].items() if it.get("kind") == "obstruction"}


def morph_metrics(map_doc: dict, records: dict) -> dict:
    v = verdicts(map_doc, records)
    obs = [i for i in v if i.startswith("O")]
    rows = [i for i in v if i.startswith("R")]
    fam = families(map_doc)
    rec = {}
    for i in obs:
        for f in fam.get(i, []):
            r = rec.setdefault(f, {"reproduced": 0, "total": 0})
            r["total"] += 1
            r["reproduced"] += v[i]["code"] == "reproduced"
    for r in rec.values():
        r["recall"] = ratio(r["reproduced"], r["total"])
    return {"findings": sum(1 for laws in records.values() for r in laws.values() if r.get("status") == "REFUTED"),
            "obstructions_reproduced": {b: sum(v[i][b] == "reproduced" for i in obs) for b in BASES},
            "rows_held": {b: sum(v[i][b] == "held" for i in rows) for b in BASES},
            "recall_per_rule": {f: rec[f] for f in sorted(rec)},
            "precision": precision(map_doc, records, v)}


def precision(map_doc: dict, records: dict, v: dict | None = None) -> dict:
    """The protocol's split over the REFUTED records of the code-basis sets, classes exclusive in order."""
    v = v if v is not None else verdicts(map_doc, records)
    basis = {s["name"]: s["basis"] for s in map_doc["sets"]}
    true_links = set()
    for ident, it in map_doc["items"].items():
        if it.get("kind") == "obstruction" and v.get(ident, {}).get("code") == "reproduced":
            for lk in it.get("links", []):
                if lk["counted"] and basis.get(lk["set"]) == "code":
                    true_links.add((lk["set"], lk["law"]))
    c = {"true_defect": 0, "intended_asymmetry": 0, "model_defect": 0, "unadjudicated": 0}
    for s, laws in records.items():
        if basis.get(s) != "code":
            continue
        for lid, r in laws.items():
            if r.get("status") != "REFUTED":
                continue
            if r.get("filter_bin") == "model_defect":
                c["model_defect"] += 1
            elif r.get("evidence_triage") == "intent_question" or r.get("filter_bin") == "intended_bounded":
                c["intended_asymmetry"] += 1
            elif (s, lid) in true_links:
                c["true_defect"] += 1
            else:
                c["unadjudicated"] += 1
    c["precision"] = ratio(c["true_defect"], c["true_defect"] + c["intended_asymmetry"] + c["model_defect"])
    # the same numerator over every finding, unadjudicated ones included: the floor the adjudicated precision hides
    c["precision_all"] = ratio(c["true_defect"], sum(c[k] for k in ("true_defect", "intended_asymmetry",
                                                                   "model_defect", "unadjudicated")))
    return c


# ------------------------------------------------------------------------------------------- calibration
def bound_of(record: dict) -> bool:
    """Does a record name what was tried: some attempt with a non-empty bound text (L15: UNKNOWN records budgets)."""
    return any(isinstance(a, dict) and isinstance(a.get("bound"), str) and a["bound"].strip()
               for a in record.get("attempts") or [])


def calibration(rows: list[dict]) -> dict:
    status = {True: "PROVED", False: "REFUTED"}
    within = [r for r in rows if r["within_budget"]]
    beyond = [r for r in rows if not r["within_budget"]]
    unk = [r for r in rows if r["outcome"] == "UNKNOWN"]
    return {
        "wrong_decisions": sum(1 for r in rows if r["outcome"] in ("PROVED", "REFUTED") and r["outcome"] != status[r["truth"]]),
        "decided_within_budget": ratio(sum(r["outcome"] == status[r["truth"]] for r in within), len(within)),
        "unknown_beyond_budget": ratio(sum(r["outcome"] == "UNKNOWN" for r in beyond), len(beyond)),
        "unknown_beyond_budget_count": sum(r["outcome"] == "UNKNOWN" for r in beyond),
        "unknown_precision": ratio(sum(not r["within_budget"] for r in unk), len(unk)),
        "agreement": ratio(sum(r["outcome"] == r["expected"] for r in rows), len(rows)),
        "unknown_with_bound": ratio(sum(bool(r.get("bound")) for r in unk), len(unk)),
        "controls": len(rows)}


# ------------------------------------------------------------------------------------------- §13 sources
def _metrics(root: Path, m: str) -> dict:
    p = root / "results" / m / "metrics.json"
    return load(p) if p.is_file() else {}


def sources(root: Path) -> dict:
    """The morph values of every §13 metric that a committed metrics file records (summed over M0-M3)."""
    ms = {m: _metrics(root, m) for m in MILESTONES}
    wr = [ms[m].get("witness_replay_rate") or {} for m in MILESTONES]
    can = [ms[m].get("canary_acceptance") or {} for m in MILESTONES]
    laws = [ms[m].get("laws") or {} for m in MILESTONES]
    ref = [ms[m].get("refinement") or {} for m in MILESTONES]
    kern = {}
    for m in MILESTONES:
        for k, e in ((ms[m].get("cross_kernel_agreement") or {}).get("kernels") or {}).items():
            a = kern.setdefault(k, {"agree": 0, "ran": 0})
            a["agree"] += e.get("agree", 0)
            a["ran"] += e.get("ran", 0)
    for a in kern.values():
        a["rate"] = ratio(a["agree"], a["ran"])
    timing = {}
    for m in ("M0", "M1", "M2"):
        p = root / "results" / m / "metrics_timing.json"
        if p.is_file():
            timing[m] = load(p).get("from_scratch_gate_s")
    hb = root / "results" / "eval" / "holon_budget.json"
    if hb.is_file():
        timing["M3"] = load(hb).get("m3_s")
    mut = ms["M2"].get("mutation_adequacy") or {}
    out = {
        "witness_replay_rate": {"replayed": sum(x.get("replayed", 0) for x in wr), "refuted": sum(x.get("refuted", 0) for x in wr)},
        "canary_acceptance": {"accepted": sum(x.get("accepted", 0) for x in can), "total": sum(x.get("total", 0) for x in can)},
        "unknown_rate": {"unknown": sum(x.get("UNKNOWN", 0) for x in laws), "total": sum(x.get("total", 0) for x in laws)},
        "refinement_disagreement_rate": {"disagreements": sum(x.get("disagreements", 0) for x in ref),
                                         "compared": sum(x.get("compared", 0) for x in ref)},
        "cross_kernel_agreement": {k: kern[k] for k in sorted(kern)},
        "mutation_adequacy": (mut.get("rate_all") or {}).get("value"),
        "from_scratch_gate_time": {"by_milestone": timing,
                                   "total_s": (round(sum(timing.values()), 3) if timing and all(isinstance(x, (int, float)) for x in timing.values()) else None)},
    }
    out["witness_replay_rate"]["rate"] = ratio(out["witness_replay_rate"]["replayed"], out["witness_replay_rate"]["refuted"])
    out["canary_acceptance"]["rate"] = ratio(out["canary_acceptance"]["accepted"], out["canary_acceptance"]["total"])
    out["unknown_rate"]["rate"] = ratio(out["unknown_rate"]["unknown"], out["unknown_rate"]["total"])
    out["refinement_disagreement_rate"]["rate"] = ratio(out["refinement_disagreement_rate"]["disagreements"],
                                                        out["refinement_disagreement_rate"]["compared"])
    return out


# ------------------------------------------------------------------------------------------- baselines
def baseline(doc: dict, label_rule: dict) -> dict:
    """recall per rule over the system's labels ({label: rule}), precision (confirmed / findings over run targets)
    and the summed wall budget of run targets, from one I52 findings file."""
    detected, findings, confirmed, wall, run = set(), 0, set(), 0, 0
    for tn, t in sorted((doc.get("targets") or {}).items()):
        if t.get("status") != "run":
            continue
        run += 1
        detected |= set(t.get("detected") or [])
        findings += len(t.get("findings") or [])
        for a in t.get("adjudications") or []:
            confirmed |= {(tn, f) for f in a.get("confirmed") or []}
        wall += (doc.get("budget") or {}).get("wall_s") or 0
    rec = {}
    for lab, rule in label_rule.items():
        for r in (rule if isinstance(rule, list) else [rule]):
            e = rec.setdefault(r, {"detected": 0, "total": 0})
            e["total"] += 1
            e["detected"] += lab in detected
    for e in rec.values():
        e["recall"] = ratio(e["detected"], e["total"])
    return {"detected": sorted(detected), "recall_per_rule": {r: rec[r] for r in sorted(rec)},
            "precision": ratio(len(confirmed), findings), "findings": findings, "run_targets": run, "wall_s": wall}
