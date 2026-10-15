"""§13 metrics per milestone (whitepaper §13 "Metrics"; BUILD_PLAN I16, invariant 6).

    python -m holon metrics --milestone M [--root DIR]

writes <root>/results/<M>/metrics.json, a deterministic function of the committed records
(results/<M>/L*.json: L_* and L3_* etc.), the canaries of results/<M>/gate_report.json, the trace corpus of
replay/<M>/report.json, the per-edge refinement records results/M2/refinement/*.json, the historical refinement
records results/M2/refinement/historical/*.json (I23: refinement.historical, included in refinement's compared and
disagreements, with the instrument's windows), the entries of spec/M2/disagreements.json and the files
holon.refinement.classify reads; and
<root>/results/<M>/metrics_timing.json, the only place timings go (G1 excludes it). Its
from_scratch_gate_s is the wall time the last full `holon gate` run recorded there.

Computed: laws, unknown_rate, witness_replay_rate, canary_acceptance, refinement {compared,
disagreements, unexplained}, refinement_disagreement_rate, cross_kernel_agreement, where the milestone has Lean
directories (I43: M1, M2 with the view's results/M2/extracted_m1, M3) cross_kernel_coverage, where the milestone has
PAR-lossy documents (gen/<M>/par_lossy/*.json, I25) evidenced_pair_coverage, and, where the
milestone's predictions were preregistered, prediction_accuracy. Every other §13 metric is listed under
not_applicable with the reason it cannot be measured yet. G1 regenerates metrics.json and compares it
byte for byte.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_VERSION = "holon-metrics/0.1"
TIMING = "metrics_timing.json"
OTHER_S13 = ("recall_per_rule", "precision", "certificate_coverage", "unknown_calibration",
             "cross_kernel_agreement", "mutation_adequacy", "prediction_accuracy")
# milestones whose §11.8 predictions were preregistered before any mechanized run (frozen files)
PREREGISTERED = {"M0": "predictions/M0.json"}


def _load(p: Path):
    return json.loads(Path(p).read_text())


def _rate(k: int, n: int) -> float | None:
    return k / n if n else None


def records(milestone: str, results: Path) -> dict[str, dict]:
    from .ir import record_files   # every law-id pattern ir.load_laws_any reads, L3_* included (audit F-M2-02)
    return {p.stem: _load(p) for p in record_files(results)}


def refinement(milestone: str, root: Path) -> dict:
    from .refinement import DISAGREEMENTS, REF_DIR, classify
    root = Path(root)
    if milestone == "M1":
        rf = (_load(root / "replay" / "M1" / "report.json").get("refinement") or {})
        compared, dis = rf.get("steps", 0), rf.get("n_disagreements", 0)
    else:
        allrecs = [_load(f) for f in sorted((root / REF_DIR).glob("*.json"))]
        recs = [r for r in allrecs if r.get("milestone") == milestone]
        compared, dis = sum(r["compared"] for r in recs), sum(r["disagreements"] for r in recs)
        # the extracted model's step refinement (I20, holon.replay_fragments): its compared steps and its distinct
        # disagreements (one per (action, input)), counted for the milestone of its transitions document
        for r in allrecs:
            fp = str(r.get("facts") or "").split("/")
            if r.get("kind") == "extracted" and len(fp) > 2 and fp[0] == "spec" and fp[1] == milestone:
                compared += int(r.get("steps") or 0)
                dis += len(r.get("disagreements") or [])
    p = root / DISAGREEMENTS
    entries = _load(p)["disagreements"] if p.exists() else []
    unexplained = sum(1 for e in entries if e.get("milestone") == milestone and classify(e, root) == "unexplained")
    out = {"compared": compared, "disagreements": dis, "unexplained": unexplained}
    hist = historical(milestone, root, entries)
    if hist is not None:
        out["compared"] += hist["compared"]
        out["disagreements"] += hist["disagreements"]
        out["historical"] = hist
    return out


def historical(milestone: str, root: Path, entries: list) -> dict | None:
    """refinement.historical (I23): the sums over the historical refinement records of the milestone
    (results/M2/refinement/historical/*.json, written by holon historical codec and trans), the entries of
    spec/M2/disagreements.json they list that classify unexplained, and the instrument's windows. None when the
    milestone has no historical record."""
    from .refinement import REF_DIR, classify
    recs = [_load(f) for f in sorted((Path(root) / REF_DIR / "historical").glob("*.json"))]
    recs = [r for r in recs if r.get("milestone") == milestone and r.get("kind") == "historical"]
    if not recs:
        return None
    by_id = {e.get("id"): e for e in entries if isinstance(e, dict)}
    ids = sorted({d for r in recs for d in r.get("disagreement_ids") or []})
    inst = Path(root) / "spec" / milestone / "lib" / "historical_exit.json"
    wins = {}
    if inst.is_file():
        w = _load(inst).get("windows") or {}
        wins = {k: [w[k]["from_block"], w[k]["to_block"]] for k in sorted(w)}
    return {"compared": sum(int(r["compared"]) for r in recs),
            "disagreements": sum(int(r["disagreements"]) for r in recs),
            "unexplained": sum(1 for d in ids if d not in by_id or classify(by_id[d], root) == "unexplained"),
            "windows": wins}


def cross_kernel(recs: dict[str, dict]) -> dict:
    """For each second kernel listed in the records: on how many checked records it ran and agreed."""
    checked = [r for r in recs.values() if r["status"] in ("PROVED", "REFUTED")]
    by: dict[str, dict] = {}
    for r in checked:
        for k in r.get("kernels", []):
            if k.get("role") == "primary":
                continue
            e = by.setdefault(k["name"], {"role": k.get("role"), "ran": 0, "agree": 0})
            if k.get("result") not in (None, "not_run"):
                e["ran"] += 1
                e["agree"] += int(k.get("result") == "checked")
    for e in by.values():
        e["rate"] = _rate(e["agree"], e["ran"])
    indep = [e for e in by.values() if e["role"] == "second-independent"]
    return {"checked_records": len(checked), "kernels": dict(sorted(by.items())),
            "independent_rate": _rate(sum(e["agree"] for e in indep), sum(e["ran"] for e in indep)) if indep else None}


def lean_coverage(recs: dict[str, dict]) -> dict:
    """One Lean directory's cross-kernel coverage (I43 rule L10) from its records: the PROVED records, those of them
    whose lean4 entry is checked and the rate (None without a PROVED record), the lean4 entries not run by reason
    (only reasons that occur, as a list: a reason is never a key, so no key reads like a timing) and the failed ones
    (a failed entry is a cross-kernel finding)."""
    def lean4(r: dict) -> dict | None:
        ks = [k for k in r.get("kernels") or [] if k.get("name") == "lean4"]
        return ks[0] if len(ks) == 1 else None
    proved = [r for r in recs.values() if r.get("status") == "PROVED"]
    checked = sum(1 for r in proved if (lean4(r) or {}).get("result") == "checked")
    entries = [lean4(r) for r in recs.values() if r.get("status") in ("PROVED", "REFUTED")]
    entries = [k for k in entries if k is not None]
    reasons: dict[str, int] = {}
    for k in entries:
        if k.get("result") == "not_run":
            reasons[str(k.get("reason"))] = reasons.get(str(k.get("reason")), 0) + 1
    return {"proved": len(proved), "lean4_checked": checked, "rate": _rate(checked, len(proved)),
            "not_run_by_reason": [{"reason": r, "count": n} for r, n in sorted(reasons.items())],
            "failed": sum(1 for k in entries if k.get("result") == "failed")}


def cross_kernel_coverage(milestone: str, root: Path, recs: dict[str, dict]) -> dict | None:
    """cross_kernel_coverage (I43 rule L10) for a milestone with Lean directories (holon.lean.lean_dirs: M1, M2, M3):
    the milestone's own directory from recs (the records being measured, so G1's regeneration from a scratch results
    directory measures its own), and every other directory of the milestone (M2: results/M2/extracted_m1, as
    "extracted_m1") from the committed records under root. None for every other milestone (M0 keeps its metrics)."""
    from . import lean
    dirs = lean.lean_dirs(milestone, root)
    if not dirs:
        return None
    out = lean_coverage(recs)
    for d in dirs:
        if d.key != milestone:
            out[d.key.split("/", 1)[-1]] = lean_coverage(records(d.milestone, Path(root) / d.records))
    return out


def prediction_accuracy(milestone: str, recs: dict[str, dict], root: Path) -> dict | None:
    rel = PREREGISTERED.get(milestone)
    if rel is None or not (Path(root) / rel).exists():
        return None
    preds = _load(Path(root) / rel)["laws"]
    met = sum(1 for p in preds if (recs.get(p["law_id"]) or {}).get("status") == p["status"])
    return {"source": rel, "predicted": len(preds), "met": met, "rate": _rate(met, len(preds))}


# sections read from the gate's own outputs (gate_report.json): G1 does not compare them (holon.gate G1_EXCLUDED)
GATE_DERIVED = ("canary_acceptance",)


def compute(milestone: str, root: Path = ROOT, results: Path | None = None) -> dict:
    root = Path(root)
    recs = records(milestone, results or root / "results" / milestone)
    st = [r["status"] for r in recs.values()]
    laws = {"total": len(st), **{s: st.count(s) for s in ("PROVED", "REFUTED", "UNKNOWN")}}
    refuted = [r for r in recs.values() if r["status"] == "REFUTED"]
    replayed = sum(1 for r in refuted if (r.get("replay") or {}).get("status") == "passed")
    gr = root / "results" / milestone / "gate_report.json"
    can = _load(gr).get("canaries", []) if gr.exists() else []
    rf = refinement(milestone, root)
    doc = {
        "metrics_version": METRICS_VERSION,
        "milestone": milestone,
        "laws": laws,
        "unknown_rate": _rate(laws["UNKNOWN"], laws["total"]),
        "witness_replay_rate": {"refuted": len(refuted), "replayed": replayed, "rate": _rate(replayed, len(refuted))},
        "canary_acceptance": {"total": len(can), "accepted": sum(1 for c in can if not c.get("rejected"))},
        "refinement": rf,
        "refinement_disagreement_rate": _rate(rf["disagreements"], rf["compared"]),
        "cross_kernel_agreement": cross_kernel(recs),
    }
    na = {
        "recall_per_rule": "needs a corpus of historical defects, each labelled with its minimal rule and analysed "
                           "at its pre-fix commit (§13 corpus; BUILD_PLAN I48, I51); this milestone has none",
        "precision": "needs adjudicated findings split into true defects, intended asymmetries and model defects "
                     "(BUILD_PLAN I51, I53); the records' filter_bin is provisional (I4)",
        "certificate_coverage": (
            "no record has a coverage entry: every law's facts document is hand-written, so its coverage is null "
            "(holon.records.coverage_field, I19) and no certificate is about an extracted document yet (BUILD_PLAN "
            "I20 adopts the extracted rollup facts)" if not any(isinstance(r.get("coverage"), dict)
                                                               for r in recs.values()) else
            f"{sum(isinstance(r.get('coverage'), dict) for r in recs.values())} records carry a coverage entry "
            "(gen/<M>/coverage.json); the share of covered code elements is not computed yet"),
        "unknown_calibration": "the UNKNOWN rate's calibration is measured on unsolved controls (BUILD_PLAN I48, I53); "
                               "this milestone has none",
        "mutation_adequacy": "A1 mutation adequacy on real code is BUILD_PLAN I22 (blocked by Q6); the M0/M1 "
                             "mutations edit the facts, not the code (BUILD_PLAN V14)",
    }
    # I25 (rule L8): evidenced-pair coverage, relative to the frozen evidence set (Prop 6.11), from
    # gen/<M>/par_lossy/*.json and spec/<M>/evidence_review.jsonl; absent for a milestone without PAR-lossy documents
    from .rules.par_lossy import metric as lossy_metric
    epc = lossy_metric(milestone, root)
    if epc is not None:
        doc["evidenced_pair_coverage"] = epc
    ckc = cross_kernel_coverage(milestone, root, recs)
    if ckc is not None:
        doc["cross_kernel_coverage"] = ckc
    pa = prediction_accuracy(milestone, recs, root)
    if pa is not None:
        doc["prediction_accuracy"] = pa
    else:
        na["prediction_accuracy"] = ("no preregistered §11.8 prediction file for this milestone: spec/M1/predictions.json "
                                     "was committed after the M1 results (BUILD_PLAN §1.1 D-a, V18), so it is not a "
                                     "preregistration" if milestone == "M1" else
                                     "no preregistered §11.8 prediction file for this milestone")
    doc["not_applicable"] = {k: v for k, v in sorted(na.items()) if k not in doc}
    return doc


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def write(milestone: str, root: Path = ROOT) -> tuple[Path, Path]:
    root = Path(root)
    t0 = time.monotonic()
    out = root / "results" / milestone / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(compute(milestone, root)))
    tp = root / "results" / milestone / TIMING
    try:
        timing = _load(tp) if tp.exists() else {}
    except ValueError:
        timing = {}
    timing = {k: v for k, v in timing.items() if k in ("from_scratch_gate_s", "from_scratch_gate_passed")}
    timing.update({"milestone": milestone, "metrics_s": round(time.monotonic() - t0, 3),
                   "note": "timings only; G1 never compares this file. from_scratch_gate_s is written by the last "
                           "full `holon gate` run (a fresh build directory, every check)"})
    tp.write_text(json.dumps(timing, indent=2, sort_keys=True) + "\n")
    return out, tp


def record_gate_time(milestone: str, root: Path, seconds: float, passed: bool) -> Path:
    """Called by a full `holon gate` run: its wall time goes to metrics_timing.json (G1 excludes it)."""
    tp = Path(root) / "results" / milestone / TIMING
    try:
        timing = _load(tp) if tp.exists() else {}
    except ValueError:
        timing = {}
    timing.update({"milestone": milestone, "from_scratch_gate_s": round(seconds, 3), "from_scratch_gate_passed": passed})
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(json.dumps(timing, indent=2, sort_keys=True) + "\n")
    return tp


def main_metrics(args) -> int:
    root = Path(args.root).resolve() if getattr(args, "root", None) else ROOT
    out, tp = write(args.milestone, root)
    print(out.read_text(), end="")
    print(f"wrote {out} and {tp}")
    return 0
