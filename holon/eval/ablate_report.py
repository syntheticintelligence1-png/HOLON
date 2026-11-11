"""`holon eval ablate calibrate|metrics|report` (BUILD_PLAN I53; protocol spec/M4/lib/I53_protocol.json): the UNKNOWN
calibration on I48's controls, every §13 metric from its recorded source with the baseline deltas, and the generated
docs/M4_EVAL.md. Nothing here names a target: systems, labels and baselines come from the protocol, the map, the
corpus manifest and the findings files present. No generator closure imports this module.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from . import ablate as A

ROOT = A.ROOT
OUT = A.OUT
MILESTONES = ("M0", "M1", "M2", "M3")
METRICS = ("recall_per_rule", "precision", "witness_replay_rate", "certificate_coverage", "unknown_rate",
           "unknown_calibration", "canary_acceptance", "cross_kernel_agreement", "mutation_adequacy",
           "refinement_disagreement_rate", "from_scratch_gate_time", "prediction_accuracy")
CONTROLS = Path("spec") / "eval" / "controls.json"


# =========================================================================================== calibration
def _scrub(x):
    if isinstance(x, dict):
        return {k: _scrub(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_scrub(v) for v in x]
    if isinstance(x, str):
        return re.sub(r"(/tmp|/root|/home)/[^\s'\"]*", "<scratch>", x)
    return x


def bound_of(record: dict) -> bool:
    return any(isinstance(a, dict) and isinstance(a.get("bound"), str) and a["bound"].strip()
               for a in record.get("attempts") or [])


def calibrate() -> int:
    from .. import facts as F
    ctl = A.load(ROOT / CONTROLS)
    run = dict(ctl["budgets"]["run"])
    repo = A.scratch_copy("calibration")
    outd = ROOT / OUT / "calibration"
    if outd.exists():
        shutil.rmtree(outd)
    outd.mkdir(parents=True)
    rows = []
    for c in ctl["controls"]:
        law = A.load(ROOT / c["law"])
        ld = repo / "laws" / "T48"
        if ld.exists():
            shutil.rmtree(ld)
        ld.mkdir(parents=True)
        (ld / f"{law['law_id']}.json").write_text(A.dumps(law), encoding="utf-8")
        reg_src = (f"import json,sys; from pathlib import Path; from holon import facts as F; from holon.gen import refs as R;"
                   f"law=json.load(open(sys.argv[1])); fp=sys.argv[2];"
                   f"print(json.dumps({{'sha': F.sha256_file(Path(fp)), 'h': R.law_hash(law, F.load(Path(fp)), oracles=None, root=Path('.'))}}))")
        import subprocess
        q = subprocess.run([sys.executable, "-c", reg_src, str(ld / f"{law['law_id']}.json"), c["facts"]], cwd=repo,
                           capture_output=True, text=True, env={**__import__("os").environ, "PYTHONPATH": str(repo)},
                           check=True)
        hh = json.loads(q.stdout)
        reg = {"milestone": "T48", "facts": c["facts"], "facts_sha256": hh["sha"], "facts_files": {c["facts"]: hh["sha"]},
               "statements": {law["law_id"]: hh["h"]}}
        (ld / "REGISTRY.json").write_text(A.dumps(reg), encoding="utf-8")
        res = repo / ".ablate" / "cal" / c["id"]
        r = A.child(repo, ["run", "--milestone", "T48", "--out", str(res), "--gen-dir", str(res) + "_gen"], ["budget"],
                    params={"budget": run}, tag=c["id"])
        rp = res / f"{law['law_id']}.json"
        rec = A.load(rp) if rp.is_file() else {"law_id": law["law_id"], "status": "UNKNOWN",
                                               "attempts": [{"kind": "run", "bound": f"the run failed: {r['tail'][-300:]}"}]}
        rec = _scrub(rec)
        (outd / f"{c['id']}.json").write_text(A.dumps(rec), encoding="utf-8")
        rows.append({"id": c["id"], "family": c["family"], "size": c["size"], "truth": c["truth"],
                     "within_budget": c["within_budget"], "expected": c["expected"], "outcome": rec.get("status"),
                     "statement_hash": rec.get("statement_hash"), "bound": bound_of(rec), "run_rc": r["rc"]})
        print(f"calibrate {c['id']}: {rec.get('status')} (expected {c['expected']})", flush=True)
    doc = {"schema": "holon-calibration/0.1", "controls_sha256": A.sha256(ROOT / CONTROLS), "budgets": run,
           "rows": rows, "metrics": calibration_metrics(rows)}
    (ROOT / OUT / "calibration.json").write_text(A.dumps(doc), encoding="utf-8")
    shutil.rmtree(repo.parent, ignore_errors=True)
    return 0


def calibration_metrics(rows: list[dict]) -> dict:
    status = {True: "PROVED", False: "REFUTED"}
    within = [r for r in rows if r["within_budget"]]
    beyond = [r for r in rows if not r["within_budget"]]
    unk = [r for r in rows if r["outcome"] == "UNKNOWN"]
    R = A.ratio
    return {"wrong_decisions": sum(1 for r in rows if r["outcome"] in ("PROVED", "REFUTED") and r["outcome"] != status[r["truth"]]),
            "decided_within_budget": R(sum(r["outcome"] == status[r["truth"]] for r in within), len(within)),
            "unknown_beyond_budget": R(sum(r["outcome"] == "UNKNOWN" for r in beyond), len(beyond)),
            "unknown_beyond_budget_count": sum(r["outcome"] == "UNKNOWN" for r in beyond),
            "unknown_precision": R(sum(not r["within_budget"] for r in unk), len(unk)),
            "agreement": R(sum(r["outcome"] == r["expected"] for r in rows), len(rows)),
            "unknown_with_bound": R(sum(bool(r.get("bound")) for r in unk), len(unk)),
            "controls": len(rows)}


# =========================================================================================== §13 sources
def _m(m: str) -> dict:
    p = ROOT / "results" / m / "metrics.json"
    return A.load(p) if p.is_file() else {}


def recorded(root: Path = ROOT) -> dict:
    ms = {m: _m(m) for m in MILESTONES}
    R = A.ratio
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
        a["rate"] = R(a["agree"], a["ran"])
    timing = {}
    for m in ("M0", "M1", "M2"):
        p = root / "results" / m / "metrics_timing.json"
        if p.is_file():
            timing[m] = A.load(p).get("from_scratch_gate_s")
    hb = root / OUT / "holon_budget.json"
    if hb.is_file():
        timing["M3"] = A.load(hb).get("m3_s")
    out = {
        "witness_replay_rate": {"replayed": sum(x.get("replayed", 0) for x in wr), "refuted": sum(x.get("refuted", 0) for x in wr)},
        "canary_acceptance": {"accepted": sum(x.get("accepted", 0) for x in can), "total": sum(x.get("total", 0) for x in can)},
        "unknown_rate": {"unknown": sum(x.get("UNKNOWN", 0) for x in laws), "total": sum(x.get("total", 0) for x in laws)},
        "refinement_disagreement_rate": {"disagreements": sum(x.get("disagreements", 0) for x in ref),
                                         "compared": sum(x.get("compared", 0) for x in ref)},
        "cross_kernel_agreement": {k: kern[k] for k in sorted(kern)},
        "mutation_adequacy": ((ms["M2"].get("mutation_adequacy") or {}).get("rate_all") or {}).get("value"),
        "from_scratch_gate_time": {"by_milestone": timing,
                                   "total_s": (round(sum(timing.values()), 3) if timing and all(isinstance(x, (int, float)) for x in timing.values()) else None)}}
    out["witness_replay_rate"]["rate"] = R(out["witness_replay_rate"]["replayed"], out["witness_replay_rate"]["refuted"])
    out["canary_acceptance"]["rate"] = R(out["canary_acceptance"]["accepted"], out["canary_acceptance"]["total"])
    out["unknown_rate"]["rate"] = R(out["unknown_rate"]["unknown"], out["unknown_rate"]["total"])
    out["refinement_disagreement_rate"]["rate"] = R(out["refinement_disagreement_rate"]["disagreements"],
                                                    out["refinement_disagreement_rate"]["compared"])
    return out


def _val(v, src) -> dict:
    return {"value": v, "source": src}


def _missing(why) -> dict:
    return {"missing": why}


def systems_of() -> tuple[str, str, str]:
    """(development, corpus, held-out) system names, from the protocol's scopes."""
    P = A.protocol()
    dev = A.dev_system(P)
    corp = next(s for a in P["ablations"].values() for s, v in a["systems"].items()
                if v["status"] == "run" and re.search(r"(?<!\w)[c]\d\d(?!\w)", v.get("how", "")))
    held = next(s for s in P["ablations"]["A1"]["systems"] if s not in (dev, corp))
    return dev, corp, held


def label_rules() -> dict:
    """{system: {label: rule or [families]}}: the development system's §11.3 obstructions (their families in the map),
    the corpus entries' final rules (spec/eval/corpus.json)."""
    dev, corp, held = systems_of()
    md = A.load(ROOT / A.MAP)
    out = {dev: {i: list(it.get("families") or []) for i, it in md["items"].items() if it.get("kind") == "obstruction"},
           corp: {e["id"]: e["label"] for e in A.load(ROOT / "spec" / "eval" / "corpus.json")["entries"]}}
    out[held] = {}
    return out


def baseline_doc(doc: dict, labels: dict) -> dict:
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
    for lab, rule in labels.items():
        for r in (rule if isinstance(rule, list) else [rule]):
            e = rec.setdefault(r, {"detected": 0, "total": 0})
            e["total"] += 1
            e["detected"] += lab in detected
    for e in rec.values():
        e["recall"] = A.ratio(e["detected"], e["total"])
    return {"detected": sorted(detected), "recall_per_rule": {r: rec[r] for r in sorted(rec)},
            "precision": A.ratio(len(confirmed), findings), "findings": findings, "run_targets": run, "wall_s": wall}


def metrics() -> int:
    doc = build_metrics()
    (ROOT / OUT / "metrics.json").write_text(A.dumps(doc), encoding="utf-8")
    return 0


def build_metrics() -> dict:
    dev, corp, held = systems_of()
    rec = recorded()
    full, verd = A.scores(ROOT)
    m3 = _m("M3")
    cal = ROOT / OUT / "calibration.json"
    calv = A.load(cal)["metrics"] if cal.is_file() else None
    S = {}
    S[dev] = {
        "recall_per_rule": _val(full["recall_per_rule"], "holon.report verdicts on the committed records (code basis, §11.3 families)"),
        "precision": _val(full["precision"], "REFUTED records of the code-basis sets, classes per the protocol"),
        "witness_replay_rate": _val(rec["witness_replay_rate"], "results/M0-M3/metrics.json witness_replay_rate"),
        "certificate_coverage": _missing("results/M3/metrics.json records no value: " +
                                         ((m3.get("not_applicable") or {}).get("certificate_coverage") or "absent")),
        "unknown_rate": _val(rec["unknown_rate"], "results/M0-M3/metrics.json laws"),
        "unknown_calibration": _val(calv, "results/eval/calibration.json") if calv else _missing("calibration not run"),
        "canary_acceptance": _val(rec["canary_acceptance"], "results/M0-M3/metrics.json canary_acceptance"),
        "cross_kernel_agreement": _val(rec["cross_kernel_agreement"], "results/M0-M3/metrics.json cross_kernel_agreement"),
        "mutation_adequacy": _val(rec["mutation_adequacy"], "results/M2/metrics.json mutation_adequacy (I62)"),
        "refinement_disagreement_rate": _val(rec["refinement_disagreement_rate"], "results/M0-M3/metrics.json refinement"),
        "from_scratch_gate_time": _val(rec["from_scratch_gate_time"],
                                       "results/M0-M2/metrics_timing.json, results/eval/holon_budget.json m3_s"),
        "prediction_accuracy": _val({b: {"held": full["rows_held"][b], "rows": sum(1 for i in verd if i.startswith("R")),
                                         "rate": A.ratio(full["rows_held"][b], sum(1 for i in verd if i.startswith("R")))}
                                     for b in A.BASES}, "holon.report §11.8 rows R1-R14")}
    cj = A.load(ROOT / OUT / "holon" / "corpus.json")
    ct = A.load(ROOT / OUT / "holon" / "corpus_timing.json")
    tsum = round(sum(v for e in ct.values() if isinstance(e, dict) for v in e.values() if isinstance(v, (int, float))), 3)
    na_c = "I51 derived no law on the corpus, so no record carries it"
    S[corp] = {
        "recall_per_rule": _val(cj["summary"]["recall"], "results/eval/holon/corpus.json summary.recall (I51)"),
        "precision": _val({"classes": cj["summary"]["classes"], "precision": cj["summary"]["precision"]},
                          "results/eval/holon/corpus.json summary (I51)"),
        **{k: _missing(na_c) for k in ("witness_replay_rate", "certificate_coverage", "unknown_rate", "canary_acceptance",
                                       "cross_kernel_agreement", "refinement_disagreement_rate")},
        "unknown_calibration": _missing(f"the controls are synthetic machines, not a system's code: reported once, under {dev}"),
        "mutation_adequacy": _missing("no mutation run on the corpus (I61/I62 mutate the development target only)"),
        "from_scratch_gate_time": _val({"total_s": tsum}, "results/eval/holon/corpus_timing.json (I51)"),
        "prediction_accuracy": _missing("§11.8 rows are the development target's"),
    }
    na_h = "I50 derived no law on the held-out target (derive refused in holon sorts), so no record carries it"
    S[held] = {k: _missing(na_h) for k in METRICS}
    S[held]["unknown_calibration"] = _missing(f"reported once, under {dev}")
    hb = heldout_recall()
    S[held]["recall_per_rule"] = _missing(
        "undefined: the held-out labels are obligation labels, not known-defect labels (the lead's ruling on I52b, "
        "2026-11-11); known-defect labels are a post-M4 key. Detections against the obligation labels are reported "
        "beside it (obligation_label_detections)")
    if hb is not None:
        S[held]["obligation_label_detections"] = hb
    deltas = baseline_deltas(S, full)
    return {"schema": "holon-eval-metrics/0.1", "protocol_sha256": A.sha256(ROOT / A.PROTOCOL), "systems": S,
            "baseline_deltas": deltas, "baselines_present": baselines_present()}


def heldout_recall():
    dev, corp, held = systems_of()
    d = ROOT / OUT / held
    if not d.is_dir():
        return None
    labels = set()
    for p in sorted(d.glob("*.json")):
        x = A.load(p)
        for t in (x.get("targets") or {}).values():
            for a in t.get("adjudications") or []:
                labels.add(a.get("label"))
    labels.discard(None)
    if not labels:
        return None
    return _val({"detected": 0, "labels": len(labels)},
                "I50: no held-out law, so no detection; the obligation labels named by the held-out baseline files' "
                "adjudications (I52b's primary, equal-budget tier)")


def baselines_present() -> dict:
    out = {}
    for s in systems_of():
        d = ROOT / OUT / s
        out[s] = sorted(p.stem for p in d.glob("*.json") if not p.stem.endswith(".timing") and
                        "baseline" in (A.load(p).get("schema") or "")) if d.is_dir() else []
    return out


def baseline_deltas(S: dict, full: dict) -> list:
    dev, corp, held = systems_of()
    labels = label_rules()
    rows = []
    holon_counts = {dev: full["obstructions_reproduced"]["code"],
                    corp: sum(len(v.get("detected") or []) for v in S[corp]["recall_per_rule"]["value"].values())}
    holon_time = {dev: (S[dev]["from_scratch_gate_time"]["value"] or {}).get("total_s"),
                  corp: S[corp]["from_scratch_gate_time"]["value"]["total_s"]}
    for s in (dev, corp, held):
        for b in baselines_present()[s]:
            doc = A.load(ROOT / OUT / s / f"{b}.json")
            v = baseline_doc(doc, labels.get(s, {}))
            n = len([x for x in v["detected"] if x in labels.get(s, {})]) if labels.get(s) else len(v["detected"])
            hc = holon_counts.get(s, 0 if s == held else None)
            rows.append({"system": s, "name": b, "metric": {dev: "obstructions_detected", corp: "labels_detected"}.get(s, "obligation_labels_detected"),
                         "holon": hc, "baseline": n, "delta": A.delta(hc, n), "run_targets": v["run_targets"]})
            if s == dev:
                hp = full["precision"]["precision"]
            elif s == corp:
                hp = S[corp]["precision"]["value"]["precision"]
            else:
                hp = None
            rows.append({"system": s, "name": b, "metric": "precision", "holon": hp, "baseline": v["precision"],
                         "delta": A.delta(hp, v["precision"]), "run_targets": v["run_targets"]})
            ht = holon_time.get(s)
            rows.append({"system": s, "name": b, "metric": "from_scratch_time_s", "holon": ht, "baseline": v["wall_s"],
                         "delta": A.delta(ht, v["wall_s"]), "run_targets": v["run_targets"]})
            hr = full["recall_per_rule"] if s == dev else (S[corp]["recall_per_rule"]["value"] if s == corp else {})
            for r, e in (v["recall_per_rule"].items() if s != held else []):
                hv = (hr.get(r) or {}).get("recall") if s != held else 0.0
                rows.append({"system": s, "name": b, "metric": f"recall:{r}", "holon": hv, "baseline": e["recall"],
                             "delta": A.delta(hv, e["recall"]), "run_targets": v["run_targets"]})
    return rows


# =========================================================================================== docs/M4_EVAL.md
def _f(x) -> str:
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.3f}"
    return str(x)


def render(summary: dict, mx: dict, cal: dict | None) -> str:
    P = A.protocol()
    dev, corp, held = systems_of()
    L = ["# M4 evaluation: the §13 protocol (ablations, UNKNOWN calibration, metrics, baseline deltas)", "",
         "Generated by `python -m holon eval ablate report` (holon/eval/ablate_report.py, BUILD_PLAN I53) from "
         "results/eval/ablations.json, results/eval/ablations/, results/eval/calibration.json and results/eval/metrics.json; "
         "do not edit. The protocol is spec/M4/lib/I53_protocol.json; every number below is read from a recorded result.",
         "", f"**Contamination.** {dev} is the development target: its numbers carry the contamination stated in "
         "docs/M3_COMPARISON.md. The corpus and the held-out target are the uncontaminated systems, and there HOLON "
         "derives (nearly) nothing (I51, I50), so no ablation can move them.", "",
         "## Ablations", "",
         "Delta = ablated - full (the protocol's delta rule). Findings: REFUTED records over every record set. "
         "Obstructions: §11.3 items reproduced; rows: §11.8 rows held; per basis hand / code.", "",
         "| id | ablation | ran | Δ findings | Δ obstructions (hand / code) | Δ rows (hand / code) | items changed | other systems |",
         "|---|---|---|---|---|---|---|---|"]
    for aid in sorted(summary["ablations"]):
        a = summary["ablations"][aid]
        d = (a["systems"].get(dev) or {}).get("delta") or {}
        det = A.load(ROOT / OUT / "ablations" / f"{aid}.json") if (ROOT / OUT / "ablations" / f"{aid}.json").is_file() else {}
        ch = sorted(((det.get("systems") or {}).get(dev) or {}).get("items_changed") or {})
        oth = []
        for s in (corp, held):
            b = a["systems"].get(s) or {}
            if b.get("status") == "run":
                x = b.get("extra") or {}
                if "laws" in x:
                    oth.append(f"{s}: rerun, {x['laws']} laws (full {x.get('full_laws')})")
                elif "refused" in x:
                    oth.append(f"{s}: sort pass {'still refuses' if x['refused'] else 'accepts'}")
                else:
                    oth.append(f"{s}: run")
            else:
                oth.append(f"{s}: n/a")
        ob, rw = d.get("obstructions_reproduced") or {}, d.get("rows_held") or {}
        L.append(f"| {aid} | {a['name']} | {'yes' if a['ran'] else '**no**'} | {_f(d.get('findings'))} | "
                 f"{_f(ob.get('hand'))} / {_f(ob.get('code'))} | {_f(rw.get('hand'))} / {_f(rw.get('code'))} | "
                 f"{', '.join(ch) or '—'} | {'; '.join(oth)} |")
    L += ["", "### Per-ablation measurements", ""]
    for aid in sorted(summary["ablations"]):
        p = ROOT / OUT / "ablations" / f"{aid}.json"
        if not p.is_file():
            L.append(f"- **{aid}**: not run. The M4 exit is not met.")
            continue
        det = A.load(p)
        b = det["systems"][dev]
        lw = "; ".join(f"{m}: {v.get('derived')} derived, {len(v['lost'])} lost, {len(v['gained'])} gained, "
                       f"{len(v['changed'])} changed" for m, v in sorted((b.get("laws") or {}).items()))
        x = b.get("extra") or {}
        xs = {k: v for k, v in x.items() if k not in ("attempts", "cases", "by_milestone")}
        L.append(f"- **{aid} {det['name']}** ({det['component']}). Switch: {det['switch']}. "
                 f"Laws: {lw or 'no derivation rerun'}. Measured: `{json.dumps(xs, sort_keys=True)}`")
    L += ["", "## UNKNOWN calibration (I48 controls)", ""]
    if cal:
        L += ["| control | family | size | truth | within budget | expected | outcome | names a bound |",
              "|---|---|---|---|---|---|---|---|"]
        for r in cal["rows"]:
            L.append(f"| {r['id']} | {r['family']} | {r['size']} | {r['truth']} | {r['within_budget']} | {r['expected']} | "
                     f"{r['outcome']} | {r['bound']} |")
        L += ["", "Metrics: " + ", ".join(f"{k} {_f(v)}" for k, v in sorted(cal["metrics"].items())), ""]
    else:
        L += ["Not run.", ""]
    L += ["## The §13 metrics", "", "| metric | " + " | ".join((dev, corp, held)) + " |", "|---|---|---|---|"]
    for k in METRICS:
        cells = []
        for s in (dev, corp, held):
            e = mx["systems"][s][k]
            cells.append("missing: " + e["missing"] if "missing" in e else f"`{json.dumps(e['value'], sort_keys=True)}` ({e['source']})")
        L.append(f"| {k} | " + " | ".join(c.replace("|", "/") for c in cells) + " |")
    L += ["", "## Deltas against the baselines", "",
          "Delta = holon - baseline; a baseline file that does not exist is missing, never substituted. Present: " +
          "; ".join(f"{s}: {', '.join(v) or 'none'}" for s, v in sorted(mx["baselines_present"].items())), ""]
    if mx["baseline_deltas"]:
        L += ["| system | baseline | metric | holon | baseline | delta | run targets |", "|---|---|---|---|---|---|---|"]
        for r in mx["baseline_deltas"]:
            L.append(f"| {r['system']} | {r['name']} | {r['metric']} | {_f(r['holon'])} | {_f(r['baseline'])} | "
                     f"{_f(r['delta'])} | {r['run_targets']} |")
    L += ["", "## Threats to validity", ""] + [f"- {t}" for t in P["threats"]]
    L += [f"- The {held} rows follow the lead's ruling on I52b (2026-11-11): the baselines' equal-budget figure is "
          "I52b's primary tier, a degenerate budget since HOLON's own route took under a second (its 3600 s tier is a "
          "sensitivity row in results/eval/" + held + "/secondary/, not compared here); the labels are obligation labels, "
          "so held-out recall is undefined and only detections against them are reported; halmos is vacuous there "
          "(its frozen harness never calls the initializer, so every path reverts).", ""]
    return "\n".join(L)


def report(check: bool) -> int:
    summary = A.summarize()
    mx = build_metrics()
    calp = ROOT / OUT / "calibration.json"
    cal = A.load(calp) if calp.is_file() else None
    want = {ROOT / OUT / "ablations.json": A.dumps(summary), ROOT / OUT / "metrics.json": A.dumps(mx),
            ROOT / "docs" / "M4_EVAL.md": render(summary, mx, cal)}
    if check:
        bad = [str(p.relative_to(ROOT)) for p, t in want.items() if not p.is_file() or p.read_text(encoding="utf-8") != t]
        for b in bad:
            print(f"ablate report --check: {b} differs from its regeneration", file=sys.stderr)
        if not bad:
            print("ablate report --check: OK")
        return 1 if bad else 0
    for p, t in want.items():
        p.write_text(t, encoding="utf-8")
    return 0
