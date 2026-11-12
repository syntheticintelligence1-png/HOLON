"""I58's instrument (key I58): L6, L9 and L10 recomputed by I54's reference (tests_m5/_i54.py), over inputs this module
assembles from the committed records itself, and the iteration reports' prediction tables read independently.

Nothing here imports holon/. It is the decider of I58's counted predictions (I58-P5..P7) and of the contract tests in
tests_m5/test_m5_report.py: holon's results/M5/metrics.json must agree with what this module computes.

  l6_inputs(root)      population (spec/M5/preregistration.json base.l6_findings), the game records
                       (results/M5/games/records/), the 14 game controls at the sha256 I56 pins, expected classes from
                       the trusted-flags sidecar I56 pins, witness_length recomputed from each finding's M3 REFUTED
                       record (never from its game record), value_flows_sha256 from I56's flows pin, and corpus truth
                       from the I54b truth file at the sha256 I56b pins, through I54's corpus_mapping (a finding is an
                       item only from I51's run on the pre-fix commit; with no I51 rows there is no item)
  l9_inputs(root)      every results/{M2,M3,M5}/L_*.json, the classification, I57's modules and pinned parameters, the
                       observation sets admitted by I57's rule (producer and tool sha256 the key pins), I57's
                       sensitivity pairs and base.l9_dependent
  l10_inputs(root)     the census at I55's pin, the atoms, the intent laws from their records, the 12 controls at I55's
                       pins
  corpus_recall(root)  L10's corpus_recall over I55b's scored entries, from the truth file at I55b's pin
  metrics(root)        {"L6", "L9", "L10"} by tests_m5._i54.l6/l9/l10
  outcomes(root, key)  {prediction id: {"result": held|missed, "cell": text}} from the key's iteration report table
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from tests_m5 import _i54

ROOT = Path(__file__).resolve().parents[1]
KEYS = ("I54", "I54b", "I55", "I55b", "I56", "I56b", "I57")


def _load(root: Path, rel: str):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key(root: Path, k: str) -> dict:
    return _load(root, f"spec/M5/predictions/{k}.json")


def _pinned(root: Path, rel: str, want: str) -> dict:
    got = sha(Path(root) / rel)
    if got != want:
        raise AssertionError(f"{rel}: sha256 {got} is not the pin {want}")
    return _load(root, rel)


# ------------------------------------------------------------------ L6
def witness_length(rec: dict):
    """The length of an M3 REFUTED record's call-schedule witness (I56's witness forms G-W1..G-W4), else None."""
    w = rec.get("witness")
    if not isinstance(w, dict):
        return None
    lst = lambda x: x if isinstance(x, list) else None  # noqa: E731
    if isinstance(w.get("steps"), list):
        return len(w["steps"])
    ks = set(w)
    if {"prefix", "y", "t", "bonded", "chooser"} <= ks:
        p, t = lst(w["prefix"]), lst(w["t"])
        return None if p is None or t is None else len(p) + 1 + len(t)
    if {"prefix", "x", "y", "t"} <= ks and "bonded" not in ks:
        p, t = lst(w["prefix"]), lst(w["t"])
        return None if p is None or t is None else len(p) + 2 + len(t)
    if {"prefix", "x"} <= ks and "y" not in ks:
        p = lst(w["prefix"])
        return None if p is None else len(p) + 1
    return None


def l6_inputs(root: Path = ROOT) -> dict:
    root = Path(root)
    k56, k56b = key(root, "I56")["thresholds"], key(root, "I56b")["thresholds"]
    pop = sorted(_load(root, "spec/M5/preregistration.json")["base"]["l6_findings"])
    side = _pinned(root, "spec/M5/lib/games_M3.json", k56["pins"]["sidecar"]["spec/M5/lib/games_M3.json"])
    classes = {c["id"]: c["trusted"] for c in side["classes"]}
    flows = _load(root, "spec/M5/lib/games_M3_flows.json")["value_flows_sha256"]
    expect = {}
    for f in pop:
        m3 = _load(root, f"results/M3/{f}.json")
        expect[f] = {"classes": dict(sorted(classes.items())), "witness_length": witness_length(m3),
                     "value_flows_sha256": flows}
    recs = [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((root / "results/M5/games/records").glob("*.json"))]
    controls = [_pinned(root, rel, s) for rel, s in sorted(k56["pins"]["controls"].items())]
    truth = _pinned(root, "spec/M5/truth/corpus.json", k56b["pins"]["spec/M5/truth/corpus.json"])["entries"]
    excl = set(_load(root, "spec/M5/lib/truth_protocol.json").get("known_exclusions", {}))
    i51 = root / "results/eval/holon/corpus.json"
    if i51.is_file():
        raise AssertionError("I51's rows exist: the corpus mapping to fix lines is not implemented by this instrument")
    # no I51 rows: no entry maps a finding, so the corpus has no item (I54 corpus_mapping)
    items: dict = {}
    del excl, truth   # read (and pinned) for the record; with no I51 rows no entry, c13 included, maps a finding
    return {"population": pop, "expect": expect, "records": recs, "controls": controls, "corpus_truth": items,
            "corpus_expect": {}}


def v9(root: Path = ROOT) -> dict:
    return _load(root, "results/M5/games/v9.json")


# ------------------------------------------------------------------ L9
def _admitted(doc: dict, tool: dict, sources: list[str]) -> bool:
    if doc.get("producer") != tool["producer"] or doc.get("source_sha256") != tool["sha256"]:
        return False
    reads = doc.get("reads") or []
    alt = "|".join(map(re.escape, sources))
    ok = re.compile(r"^(FILE [A-Za-z0-9_./-]+(#[A-Za-z0-9_,]+)?|GET (%s)/\S+|RPC (%s) eth_[A-Za-z]+)$" % (alt, alt))
    return bool(reads) and all(ok.match(r) for r in reads) and "FILE spec/M5/lib/I57_modules.json" not in reads


def l9_inputs(root: Path = ROOT) -> dict:
    root = Path(root)
    th = key(root, "I57")["thresholds"]
    tool = th["observation_tool"]
    if sha(root / tool["path"]) != tool["sha256"]:
        raise AssertionError("the observation tool is not at the sha256 I57 pins")
    plan = _load(root, tool["plan"])
    sources = sorted(plan["sources"].values())
    sets = []
    for name in sorted(plan["sets"]):
        p = root / "results/M5/env/observations" / f"{name}.json"
        if p.is_file():
            doc = json.loads(p.read_text(encoding="utf-8"))
            if _admitted(doc, tool, sources):
                sets.append(doc)
    recs = []
    for m in ("M2", "M3", "M5"):
        recs += [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "results" / m).glob("L_*.json"))]
    mods = _load(root, "spec/M5/lib/I57_modules.json")
    mods = mods["modules"] if isinstance(mods, dict) else mods
    return {"records": recs, "classification": _load(root, "spec/M5/lib/environment_classes.json"),
            "modules": mods, "observation_sets": sets,
            "sensitivity": _load(root, "results/M5/env/sensitivity.json")["pairs"],
            "base_dependent": _load(root, "spec/M5/preregistration.json")["base"]["l9_dependent"],
            "pinned_parameters": th["pinned_parameters"]}


# ------------------------------------------------------------------ L10
def l10_inputs(root: Path = ROOT) -> dict:
    root = Path(root)
    th = key(root, "I55")["thresholds"]
    census = _pinned(root, "results/M5/l10_census_base.json", th["census_sha256"])["clauses"]
    atoms = _load(root, "results/M5/intent/atoms.json")["atoms"]
    laws = []
    for p in sorted((root / "results/M5/intent/records").glob("L_intent_*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        laws.append({"law": r["law_id"], "clauses": list(r["clauses"]), "status": r["status"],
                     "evidence": dict(r["evidence"]), "review": dict(r["review"]), "control": r["control"]})
    controls = [_pinned(root, rel, s) for rel, s in sorted(th["controls_sha256"].items()) if rel.endswith(".json")]
    return {"census": census,
            "atomized": [{"id": a["id"], "file": a["file"], "lines": list(a["lines"]), "text": a["text"]}
                         for a in atoms],
            "laws": laws, "controls": controls}


def corpus_recall(root: Path = ROOT) -> dict:
    """definitions.L10.measures.corpus_recall over I55b's scored entries (truth at I55b's pin)."""
    root = Path(root)
    th = key(root, "I55b")["thresholds"]
    truth = _pinned(root, "spec/M5/truth/corpus.json", th["truth_sha256"])["entries"]
    atoms = _load(root, "results/M5/intent/corpus/atoms.json")["entries"]
    recdir = root / "results/M5/intent/corpus/records"
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(recdir.glob("*.json"))] if recdir.is_dir() else []
    yes = [e for e in th["scored"] if truth[e]["l10"] == "yes"]
    hit = []
    for e in yes:
        ids = {a["id"] for a in atoms[e]["atoms"]}
        if any(set(r.get("clauses", [])) & ids and r.get("obstruction") for r in recs):
            hit.append(e)
    return {"corpus_recall": _i54.prop(len(hit), len(yes)), "label": _i54.label(len(yes))}


def metrics(root: Path = ROOT) -> dict:
    return {"L6": _i54.l6(l6_inputs(root)), "L9": _i54.l9(l9_inputs(root)), "L10": _i54.l10(l10_inputs(root))}


# ------------------------------------------------------------------ the iteration reports' prediction tables
ROW = re.compile(r"^\|\s*((?:I\d+[a-z]?-)?P\d+)(?:\s*\([^|]*\))?\s*\|(.*)\|\s*\**\s*(PASS|MISS|held)\s*\**\s*\|\s*$")


def report_of(root: Path, k: str) -> Path:
    p = Path(root) / "docs/iterations" / f"{k}.md"
    return p if p.is_file() else Path(root) / "docs/iterations" / f"{re.sub(r'[a-z]+$', '', k)}.md"


def outcomes(root: Path, k: str) -> dict:
    main = re.sub(r"[a-z]+$", "", k) if not report_of(root, k).name.startswith(k + ".") else k
    out = {}
    for line in report_of(root, k).read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if not m:
            continue
        pid = m.group(1) if "-" in m.group(1) else f"{main}-{m.group(1)}"
        if not pid.startswith(k + "-"):
            continue
        out[pid] = {"result": "missed" if m.group(3) == "MISS" else "held"}
    return out
