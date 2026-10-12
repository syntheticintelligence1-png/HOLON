"""§13 metrics per milestone (whitepaper §13 "Metrics"; BUILD_PLAN I16, invariant 6).

    python -m holon metrics --milestone M [--root DIR]

writes <root>/results/<M>/metrics.json, a deterministic function of the committed records
(results/<M>/L*.json: L_* and L3_* etc.), the canaries of results/<M>/gate_report.json, the trace corpus of
replay/<M>/report.json, the per-edge refinement records results/M2/refinement/*.json, the entries of
spec/M2/disagreements.json and the files holon.refinement.classify reads; and
<root>/results/<M>/metrics_timing.json, the only place timings go (G1 excludes it). Its
from_scratch_gate_s is the wall time the last full `holon gate` run recorded there.

Computed: laws, unknown_rate, witness_replay_rate, canary_acceptance, refinement {compared,
disagreements, unexplained}, refinement_disagreement_rate, cross_kernel_agreement and, where the
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
        recs = [r for r in (_load(f) for f in sorted((root / REF_DIR).glob("*.json"))) if r.get("milestone") == milestone]
        compared, dis = sum(r["compared"] for r in recs), sum(r["disagreements"] for r in recs)
    p = root / DISAGREEMENTS
    entries = _load(p)["disagreements"] if p.exists() else []
    unexplained = sum(1 for e in entries if e.get("milestone") == milestone and classify(e, root) == "unexplained")
    return {"compared": compared, "disagreements": dis, "unexplained": unexplained}


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
        "certificate_coverage": "every record's coverage field is still pending:I19 (BUILD_PLAN I19 fills it)",
        "unknown_calibration": "the UNKNOWN rate's calibration is measured on unsolved controls (BUILD_PLAN I48, I53); "
                               "this milestone has none",
        "mutation_adequacy": "A1 mutation adequacy on real code is BUILD_PLAN I22 (blocked by Q6); the M0/M1 "
                             "mutations edit the facts, not the code (BUILD_PLAN V14)",
    }
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
