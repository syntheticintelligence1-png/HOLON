"""The M5 report (key I58): L6, L9 and L10 as measured, and docs/M5_REPORT.md.

  python -m holon m5 report [--root DIR] [--check]

writes results/M5/metrics.json (holon.metrics' document for M5, which carries metrics_block's L6, L9 and L10; `python
-m holon metrics --milestone M5` writes the same bytes, so a landing's regen keeps them) and docs/M5_REPORT.md. --check
writes nothing and exits 1 unless both files are what the committed records give.

Each metric is computed by I54's stub (holon.m5.metrics) from the committed records, through the input assembly of the
iteration that measured it, and never from a number written by hand:
  L6   holon.games.cli.corpus_files (I56b): holon.games.metric.l6_v9, I56's V9 wrapper over holon.m5.metrics.l6
  L9   holon.m5.env.l9_doc (I57): holon.m5.metrics.l9
  L10  holon.intent.metrics.compute (I55): holon.m5.metrics.l10; corpus_recall from holon.intent.corpus.score (I55b)

The generator refuses (ReportError), writing nothing, when:
  - a metric differs from the measuring iteration's committed output (spec/M5/lib/I58_report.json agrees_with);
  - a truth file's sha256 is not the measuring key's pin (the sidecar's pins and pin_sets);
  - validate() finds a verdict rounded up: an overall other than common.overall of the thresholds, a threshold judged
    on a measure whose label is not measured, a label that is not the denominator's (common.labels);
  - an evidence check of a condition or limitation fails;
  - an iteration report's prediction table does not give exactly one outcome for each prediction of its key.

Constructed truth and documented truth are never pooled: I55's pooled precision is not carried. Output is
deterministic: sorted keys, no timestamps, no absolute paths.
"""
from __future__ import annotations

import glob as _glob
import hashlib
import json
import re
from pathlib import Path

from . import common
from .common import ROOT

SIDECAR = "spec/M5/lib/I58_report.json"
DEFS = "spec/M5/preregistration.json"
REPORT = "docs/M5_REPORT.md"
METRICS = "results/M5/metrics.json"
NAMES = ("L6", "L9", "L10")
REPORT_KEY = "I58"
# the measure each threshold is judged on (definitions.<L>.thresholds and holon.m5.metrics): its label must be measured
# for the threshold to be judged; None: judged by its own rule (validated_categories, a zero count over controls)
JUDGED_ON = {
    "L6": {"decided": "decided", "controls_decided_accuracy": "controls.decided_accuracy",
           "controls_strict_accuracy": "controls.strict_accuracy", "controls_beats_majority": "controls.strict_accuracy",
           "false_rational": "controls.strict_accuracy", "false_irrational": "controls.strict_accuracy",
           "corpus_decided_accuracy": "corpus.decided_accuracy"},
    "L9": {"coverage": "coverage", "base_coverage": "base_coverage", "validated_categories": None,
           "sensitivity_unreplayed": None},
    "L10": {"coverage": "coverage", "precision": "precision", "review": "review", "control_recall": "control_recall",
            "false_obstruction": None},
}


class ReportError(ValueError):
    """The committed records give no report that can be stated without overstating it."""


def _load(root: Path, rel: str):
    p = Path(root) / rel
    if not p.is_file():
        raise ReportError(f"{rel}: missing")
    return json.loads(p.read_text(encoding="utf-8"))


def _sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _ptr(doc, pointer: str):
    for t in [x for x in pointer.split("/") if x != ""]:
        t = t.replace("~1", "/").replace("~0", "~")
        doc = doc[int(t)] if isinstance(doc, list) else doc[t]
    return doc


def _key(root: Path, k: str) -> dict:
    return _load(root, f"spec/M5/predictions/{k}.json")


def _split(ref: str) -> tuple[str, str]:
    return tuple(ref.split("#", 1)) if "#" in ref else (ref, "")


# ------------------------------------------------------------------ the metrics, from the iterations' assembly
def _compute(root: Path) -> dict:
    from ..games import cli as games_cli
    from ..intent import corpus as intent_corpus
    from ..intent import metrics as intent_metrics
    from . import env
    out = games_cli.Out(root)
    games_cli.corpus_files(root, out)
    l6 = json.loads(out.files["results/M5/corpus/l6_corpus.json"])
    l9doc = env.l9_doc(root)
    l10doc = intent_metrics.compute(root)["l10"]
    return {"L6": {"value": l6},
            "L9": {"value": l9doc["L9"], "inputs": l9doc["inputs"]},
            "L10": {"value": l10doc["l10"], "trivially_true": l10doc["trivially_true"],
                    "corpus_recall": intent_corpus.score(root)}}


LAW_LINE = re.compile(r"^law (\S+):\s*\n\s*(.*)$", re.M)
# where the iterations' generated Bend modules live: a record that claims checker evidence must name a law that a
# committed LAWS.bend under these states (the checker itself is re-run only by the iterations' --check commands)
GEN_DIRS = {"L6": "gen/M5/games/bend", "L9": "gen/M5/env", "L10": "gen/M5/intent"}
RECORDS = {"L6": "results/M5/games/records/*.json", "L9": "results/M5/L_*.json",
           "L10": "results/M5/intent/records/*.json"}


def _law_index(root: Path, rel: str) -> dict:
    out: dict[str, list] = {}
    for f in sorted((Path(root) / rel).rglob("LAWS.bend")):
        for m in LAW_LINE.finditer(f.read_text(encoding="utf-8")):
            out.setdefault(m.group(1), []).append(m.group(2).strip())
    return out


def bound(root: Path) -> list[str]:
    """Records whose checker evidence names no committed law, and game records whose class verdicts are not the
    vector their committed module states (I56's B1); [] when every record is bound to its module."""
    from ..games.bendgen import VCODE
    probs = []
    for n in NAMES:
        idx = _law_index(root, GEN_DIRS[n])
        for f in sorted(Path(root).glob(RECORDS[n])):
            r = json.loads(f.read_text(encoding="utf-8"))
            evs = [r.get("evidence")] + ([r["axiom_form"].get("evidence")] if isinstance(r.get("axiom_form"), dict)
                                         else [])
            for ev in evs:
                if not common.checked(ev):
                    continue
                stated = idx.get(ev.get("law"), [])
                if not stated:
                    probs.append(f"{f.relative_to(root).as_posix()}: its evidence law {ev.get('law')} is stated "
                                 f"by no LAWS.bend under {GEN_DIRS[n]}")
                    continue
                if n == "L6":
                    vec = "[" + ", ".join("G." + VCODE[c["verdict"]] for c in r.get("classes") or []) + "]"
                    if len(stated) != 1 or not stated[0].startswith("{G.verdicts() == " + vec + " "):
                        probs.append(f"{f.relative_to(root).as_posix()}: its class verdicts are not the vector its "
                                     "committed module states")
    return probs


def labels(value: dict, prefix: str = "") -> dict:
    """{dotted measure: common.size_label(denominator)} for every proportion in a metric's document."""
    out = {}
    for k in sorted(value):
        v = value[k]
        if isinstance(v, dict) and {"numerator", "denominator", "value", "wilson95"} <= set(v):
            out[prefix + k] = common.size_label(v["denominator"])
        elif isinstance(v, dict) and k in ("controls", "corpus"):
            out.update(labels(v, f"{prefix}{k}."))
    return out


def _pins(root: Path, spec: dict) -> tuple[list, list]:
    pins, sets = [], []
    for p in spec["pins"]:
        want = _ptr(_key(root, p["key"]), p["field"])
        got = _sha(Path(root) / p["path"]) if (Path(root) / p["path"]).is_file() else None
        if got != want:
            raise ReportError(f"{p['path']}: sha256 {got} is not {p['key']}'s pin {want} ({p['role']})")
        pins.append({"role": p["role"], "path": p["path"], "sha256": got, "key": p["key"], "field": p["field"]})
    for s in spec["pin_sets"]:
        files = {}
        for rel, want in sorted(_ptr(_key(root, s["key"]), s["field"]).items()):
            got = _sha(Path(root) / rel) if (Path(root) / rel).is_file() else None
            if got != want:
                raise ReportError(f"{rel}: sha256 {got} is not {s['key']}'s pin {want} ({s['role']})")
            files[rel] = got
        sets.append({"role": s["role"], "key": s["key"], "field": s["field"], "files": files})
    return pins, sets


def _evidence(root: Path, ev: dict) -> str:
    """'' when the check holds, else what failed."""
    root = Path(root)
    kind = ev["kind"]
    if kind == "absent":
        return "" if not (root / ev["path"]).exists() else f"{ev['path']} exists"
    if kind == "glob":
        n = len(_glob.glob(str(root / ev["pattern"])))
        return "" if n == ev["count"] else f"{ev['pattern']}: {n} files, not {ev['count']}"
    try:
        v = _ptr(_load(root, ev["path"]), ev["pointer"])
    except (KeyError, IndexError, ReportError) as e:
        return f"{ev['path']}#{ev['pointer']}: {e}"
    if kind == "json_len":
        v = len(v)
    return "" if v == ev["equals"] else f"{ev['path']}#{ev['pointer']} is {v!r}, not {ev['equals']!r}"


def _describe(ev: dict) -> str:
    if ev["kind"] == "absent":
        return f"`{ev['path']}` does not exist"
    if ev["kind"] == "glob":
        return f"`{ev['pattern']}` matches {ev['count']} file(s)"
    what = "length of " if ev["kind"] == "json_len" else ""
    return f"{what}`{ev['path']}#{ev['pointer']}` = `{json.dumps(ev['equals'])}`"


def metrics_block(root: Path = ROOT) -> dict:
    """{"L6", "L9", "L10", "m5_report"} for results/M5/metrics.json; ReportError when it cannot be stated."""
    root = Path(root)
    side = _load(root, SIDECAR)
    own = (_key(root, REPORT_KEY)["thresholds"].get("pins") or {}).get(DEFS)
    if own is not None and _sha(root / DEFS) != own:
        raise ReportError(f"{DEFS} is not at the sha256 the key {REPORT_KEY} pins (python -m holon m5 prereg --check)")
    defs = _load(root, DEFS)["definitions"]
    try:
        got = _compute(root)
    except (RuntimeError, ValueError, KeyError, OSError) as e:   # an iteration's assembly refused its inputs
        raise ReportError(f"an iteration's input assembly refused: {type(e).__name__}: {e}") from e
    unbound = bound(root)
    if unbound:
        raise ReportError("records not bound to their committed modules: " + "; ".join(unbound[:5])
                          + (f" and {len(unbound) - 5} more" if len(unbound) > 5 else ""))
    out = {}
    for n in NAMES:
        spec = side["metrics"][n]
        g = got[n]
        rel, ptr = _split(spec["agrees_with"])
        committed = _ptr(_load(root, rel), ptr)
        if committed != g["value"]:
            raise ReportError(f"{n}: the recomputed metric differs from {spec['agrees_with']} (the measuring "
                              "iteration's committed output)")
        pins, sets = _pins(root, spec)
        truth = [p["sha256"] for p in pins if p["role"] == "corpus truth"]
        if len(set(truth)) > 1:
            raise ReportError(f"{n}: two corpus-truth pins")
        b = {"name": _ptr(defs, spec["name_from"].replace("definitions.", "").replace(".", "/")),
             "measured_by": spec["measured_by"], "value": g["value"], "overall": g["value"]["overall"],
             "thresholds": g["value"]["thresholds"], "labels": labels(g["value"]), "pins": pins, "pin_sets": sets,
             "corpus_truth_sha256": truth[0] if truth else None,
             "agrees_with": {"path": spec["agrees_with"], "equal": True}}
        if n == "L9":
            b["inputs"] = g["inputs"]
        if n == "L10":
            cr = g["corpus_recall"]
            b["corpus_recall"] = {"corpus_recall": cr["corpus_recall"], "label": cr["label"],
                                  "entries": cr["entries"], "truth_sha256": cr["truth_sha256"],
                                  "from": spec["corpus_recall_from"]}
            have = _load(root, spec["corpus_recall_from"])
            if have != cr:
                raise ReportError(f"L10: corpus_recall differs from {spec['corpus_recall_from']}")
            b["trivially_true"] = g["trivially_true"]
        out[n] = b
    checks = {}
    for c in side["conditions"] + side["limitations"]:
        bad = [x for x in (_evidence(root, e) for e in c["evidence"]) if x]
        if bad:
            raise ReportError(f"{c['id']}: an evidence check fails: {'; '.join(bad)}")
        checks[c["id"]] = len(c["evidence"])
    out["m5_report"] = {
        "key": REPORT_KEY, "exit": side["exit"], "sidecar": SIDECAR, "sidecar_sha256": _sha(root / SIDECAR),
        "definitions": DEFS, "definitions_sha256": _sha(root / DEFS),
        "computed_by": "holon.m5.metrics (I54's stub), through holon.games.metric.l6_v9 (L6), holon.m5.env.l9_doc "
                       "(L9) and holon.intent.metrics.compute with holon.intent.corpus.score (L10)",
        "evidence_checks": checks, "reported": list(NAMES),
        "overall": {n: out[n]["overall"] for n in NAMES}}
    probs = validate(out, root)
    if probs:
        raise ReportError("; ".join(probs))
    return out


def _get(val: dict, dotted: str):
    for part in dotted.split("."):
        val = val.get(part) if isinstance(val, dict) else None
    return val


def rejudge(n: str, t: str, val: dict, spec: dict) -> str | None:
    """A threshold's verdict recomputed from the metric's numbers and the preregistered op and target (I54
    common.labels and common.zero_counts); None when the numbers alone do not decide it."""
    lab = lambda k: common.size_label(k)  # noqa: E731
    if n == "L6":
        c, k = val["controls"], val.get("corpus") or {}
        if t == "decided" and not (val.get("v9") or {}).get("holds", True):
            return "not_judged"
        if t == "controls_beats_majority":
            return common.verdict(c["strict_correct"], ">", c["majority_baseline"], lab(c["items"]))
        if t == "false_rational":
            return common.verdict(len(c["false_rational"]) + len(k.get("false_rational", [])), "==", 0,
                                  lab(c["items"]))
        if t == "false_irrational":
            return common.verdict(len(c["false_irrational"]), "==", 0, lab(c["items"]))
        if t == "corpus_decided_accuracy" and "decided_accuracy" not in k:
            return "not_measured"
    if n == "L9" and t == "validated_categories":
        return "meets" if sorted(val["validated_categories"]) == sorted(spec["value"]) else "misses"
    if n == "L9" and t == "sensitivity_unreplayed":
        s = val["sensitivity"]
        return common.verdict(len(s["unreplayed"]), "==", 0,
                              "measured" if s["counted"] or s["unreplayed"] else "not_measured")
    if n == "L10" and t == "false_obstruction":
        return "misses" if val["false_obstruction"] else None
    m = JUDGED_ON[n].get(t)
    x = _get(val, m) if m else None
    if not isinstance(x, dict) or "denominator" not in x or not isinstance(spec.get("value"), (int, float)):
        return None
    return common.verdict(x["value"], spec["op"], spec["value"], lab(x["denominator"]))


def validate(block: dict, root: Path = ROOT) -> list[str]:
    """What would overstate a metric (common.labels, common.overall, the preregistered thresholds re-judged from the
    numbers, the V9 rule); [] when nothing does."""
    probs = []
    defs = _load(root, DEFS)["definitions"]
    for n in NAMES:
        val = block[n]["value"]
        for t in sorted(set(block[n]["thresholds"]) | set(val["thresholds"])):
            spec = defs[n]["thresholds"].get(t)
            if spec is None:
                continue
            want = rejudge(n, t, val, spec)
            for got in (block[n]["thresholds"].get(t), val["thresholds"].get(t)):
                if want is not None and got != want:
                    probs.append(f"{n}.{t}: reported {got}, the numbers give {want}")
                if want is None and got == "meets" and n == "L10" and t == "false_obstruction" and val[t]:
                    probs.append(f"{n}.{t}: reported meets with obstructions")
    for n in NAMES:
        b = block[n]
        th, val = b["thresholds"], b["value"]
        if b["overall"] != val["overall"]:
            probs.append(f"{n}: overall {b['overall']} is not the metric's {val['overall']}")
        if th != val["thresholds"]:
            probs.append(f"{n}: thresholds differ from the metric's")
        if b["overall"] != common.overall(th) or val["overall"] != common.overall(val["thresholds"]):
            probs.append(f"{n}: overall is not common.overall of its thresholds")
        lab = labels(val)
        if b["labels"] != lab:
            probs.append(f"{n}: labels are not the denominators' (common.labels)")
        for t, v in sorted(set(th.items()) | set(val["thresholds"].items())):
            m = JUDGED_ON[n].get(t, "?")
            if m == "?":
                probs.append(f"{n}.{t}: a threshold the definitions do not name")
                continue
            if m is None:
                continue
            want = lab.get(m, "not_measured")
            for lb in (b["labels"].get(m, "not_measured"), want):
                if lb != "measured" and v in ("meets", "misses"):
                    probs.append(f"{n}.{t}: judged {v} on {m}, which is {lb}")
        if b.get("agrees_with", {}).get("equal") is not True:
            probs.append(f"{n}: not shown equal to the measuring iteration's output")
    v9 = block["L6"]["value"].get("v9") or {}
    if not v9.get("holds") and block["L6"]["thresholds"].get("decided") in ("meets", "misses"):
        probs.append("L6.decided: judged while V9 does not hold (the lead's condition 1: not_judged)")
    cr = block["L10"].get("corpus_recall") or {}
    if cr and cr.get("label") != common.size_label(cr["corpus_recall"]["denominator"]):
        probs.append("L10.corpus_recall: its label is not its denominator's")
    if "pooled_precision" in json.dumps(block["L10"]):
        probs.append("L10: a pooled measure (constructed with documented truth)")
    return probs


# ------------------------------------------------------------------ the iterations' prediction outcomes
_ROW = re.compile(r"^\|\s*(?P<id>(?:I\d+[a-z]*-)?P\d+)(?:\s*\((?P<note>[^)|]*)\))?\s*\|(?P<cells>.*)\|\s*$")


def report_path(root: Path, k: str) -> str:
    own = f"docs/iterations/{k}.md"
    return own if (Path(root) / own).is_file() else f"docs/iterations/{re.sub(r'[a-z]+$', '', k)}.md"


def outcomes(root: Path, k: str) -> dict:
    """{prediction id: {"result": held | missed, "outcome": the report's outcome cell}} from the key's report."""
    rel = report_path(root, k)
    main = Path(rel).stem
    preds = [p["id"] for p in _key(root, k)["predictions"]]
    found: dict[str, list] = {}
    p = Path(root) / rel
    if not p.is_file():
        raise ReportError(f"{k}: no iteration report ({rel})")
    for line in p.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        pid = m["id"] if "-" in m["id"] else f"{main}-{m['id']}"
        if pid not in preds:
            continue
        cells = [c.strip() for c in m["cells"].split("|")]
        res = cells[-1].strip("* ")
        if res not in ("PASS", "MISS", "held"):
            raise ReportError(f"{rel}: {pid}: result {cells[-1]!r} is not PASS, MISS or held")
        found.setdefault(pid, []).append({"result": "missed" if res == "MISS" else "held",
                                          "outcome": cells[-2] if len(cells) >= 2 else ""})
    out = {}
    for pid in preds:
        rows = found.get(pid, [])
        if len(rows) != 1:
            raise ReportError(f"{rel}: {len(rows)} outcome rows for {pid} (one needed)")
        out[pid] = rows[0]
    return out


def _informed(k: dict) -> set:
    return set((((k.get("thresholds") or {}).get("counting") or {}).get("informed") or {}).get("ids", []))


# ------------------------------------------------------------------ rendering
def _cell(s) -> str:
    return re.sub(r"\s+", " ", str(s)).replace("|", "\\|").strip()


def _prop(p) -> str:
    if not isinstance(p, dict) or "denominator" not in p:
        return _cell(json.dumps(p))
    if p["value"] is None:
        return f"{p['numerator']}/{p['denominator']} (no value)"
    w = p["wilson95"]
    return f"{p['numerator']}/{p['denominator']} = {p['value']:g} [{w[0]:g}, {w[1]:g}]"


def _measure_text(n: str, t: str, b: dict) -> str:
    val = b["value"]
    if n == "L6" and t == "controls_beats_majority":
        c = val["controls"]
        return f"strict correct {c['strict_correct']}, majority baseline {c['majority_baseline']}"
    if n == "L6" and t in ("false_rational", "false_irrational"):
        ids = list(val["controls"][t]) + list((val.get("corpus") or {}).get(t, []) if t == "false_rational" else [])
        return f"{len(ids)} items" + (f": {', '.join(ids)}" if ids else "")
    if n == "L9" and t == "validated_categories":
        return "validated: " + (", ".join(val["validated_categories"]) or "none")
    if n == "L9" and t == "sensitivity_unreplayed":
        s = val["sensitivity"]
        return f"{len(s['unreplayed'])} unreplayed, {s['count']} counted"
    if n == "L10" and t == "false_obstruction":
        return f"{len(val['false_obstruction'])} items"
    m = JUDGED_ON[n].get(t)
    v = val
    for part in (m or t).split("."):
        v = v.get(part) if isinstance(v, dict) else None
    lab = b["labels"].get(m or t)
    return _prop(v) + (f" ({lab})" if lab else "") if v is not None else "no measure (not_measured)"


def _target(spec: dict) -> str:
    v = spec.get("value")
    of = f" ({spec['of']})" if spec.get("of") else ""
    mn = f", min_n {spec['min_n']}" if spec.get("min_n") else ""
    return _cell(f"{spec.get('op', '')} {json.dumps(v) if not isinstance(v, str) else v}{mn}{of}")


def _headline(n: str, b: dict) -> str:
    v = b["value"]
    if n == "L6":
        return f"decided {_prop(v['decided'])} of F(M3)"
    if n == "L9":
        return f"coverage {_prop(v['coverage'])}"
    return f"intent-law coverage {_prop(v['coverage'])} of the census"


def render(root: Path = ROOT, block: dict | None = None) -> str:
    root = Path(root)
    block = metrics_block(root) if block is None else block
    probs = validate(block, root)
    if probs:
        raise ReportError("; ".join(probs))
    side = _load(root, SIDECAR)
    defs = _load(root, DEFS)["definitions"]
    mr = block["m5_report"]
    L = []
    w = L.append
    w("# M5 report: L6, L9 and L10 as measured")
    w("")
    w(f"Generated by `python -m holon m5 report` (holon/m5/report.py, key {REPORT_KEY}) from the committed records, "
      f"the definitions `{DEFS}` (sha256 `{mr['definitions_sha256']}`) and the report sidecar `{SIDECAR}` (sha256 "
      f"`{mr['sidecar_sha256']}`). Do not edit: `python -m holon m5 report --check` fails on any difference. The "
      f"numbers are in `{METRICS}`, under the keys L6, L9 and L10.")
    w("")
    w(_cell(side["exit"]))
    w("")
    w(f"Computed by {mr['computed_by']}. Every metric equals the measuring iteration's committed output, every truth "
      "file is at the measuring key's pin, and a measure labelled insufficient_n or not_measured is never judged "
      "(I54 common.labels): the generator refuses to write otherwise.")
    w("")
    w("## Summary")
    w("")
    w("| metric | definition | measured by | headline | overall |")
    w("|---|---|---|---|---|")
    for n in NAMES:
        b = block[n]
        w(f"| {n} | {_cell(b['name'])} | {', '.join(b['measured_by'])} | {_cell(_headline(n, b))} | {b['overall']} |")
    w("")
    met = [n for n in NAMES if block[n]["overall"] == "meets"]
    w((f"Meeting its preregistered level: {', '.join(met)}. " if met else
       "No metric meets its preregistered level. ") +
      "Each overall verdict above is I54's common.overall of the thresholds below: "
      + "; ".join(f"{n} {block[n]['overall']}" for n in NAMES) + ". The M5 exit criterion is that the metrics are "
      "reported, which this report does; it is not that they meet.")
    w("")
    w("## Thresholds")
    w("")
    w("| metric | threshold | measure | preregistered | verdict |")
    w("|---|---|---|---|---|")
    for n in NAMES:
        b = block[n]
        for t in sorted(b["thresholds"]):
            w(f"| {n} | `{t}` | {_cell(_measure_text(n, t, b))} | {_target(defs[n]['thresholds'].get(t, {}))} | "
              f"{b['thresholds'][t]} |")
    w("")
    w("A verdict other than meets or misses is the measure's label: the threshold was not judged.")
    w("")
    w("## Labels: what is not measured")
    w("")
    w("| metric | measure | label |")
    w("|---|---|---|")
    rows = 0
    for n in NAMES:
        for m, lab in sorted(block[n]["labels"].items()):
            if lab != "measured":
                w(f"| {n} | `{m}` | {lab} |")
                rows += 1
        for t, v in sorted(block[n]["thresholds"].items()):
            if v not in ("meets", "misses") and JUDGED_ON[n].get(t) not in block[n]["labels"]:
                w(f"| {n} | `{t}` (threshold) | {v} |")
                rows += 1
    cr = block["L10"]["corpus_recall"]
    if cr["label"] != "measured":
        w(f"| L10 | `corpus_recall` | {cr['label']} |")
        rows += 1
    if not rows:
        w("| - | - | every measure is measured |")
    w("")
    for n in NAMES:
        _detail(w, n, block[n])
    _predictions(w, root, side)
    w("## The lead's conditions (PR #134)")
    w("")
    for c in side["conditions"]:
        _item(w, c)
    w("## Deviations and limitations")
    w("")
    for c in side["limitations"]:
        _item(w, c)
    return "\n".join(L).rstrip("\n") + "\n"


def _item(w, c: dict) -> None:
    ev = "; ".join(_describe(e) for e in c["evidence"])
    w(f"- **{c['id']}.** {_cell(c['text'])}" + (f" Checked: {ev}." if ev else " (disclosed; no mechanical check)"))
    w("")


def _pins_table(w, b: dict) -> None:
    w("| role | file | sha256 | pinned by |")
    w("|---|---|---|---|")
    for p in b["pins"]:
        w(f"| {_cell(p['role'])} | `{p['path']}` | `{p['sha256']}` | {p['key']} `{p['field']}` |")
    for s in b["pin_sets"]:
        w(f"| {_cell(s['role'])} | {len(s['files'])} files | each at its pin | {s['key']} `{s['field']}` |")
    w("")
    w(f"Corpus-truth sha256 this metric pins: "
      + (f"`{b['corpus_truth_sha256']}`." if b["corpus_truth_sha256"] else "none."))
    w("")


def _detail(w, n: str, b: dict) -> None:
    v = b["value"]
    w(f"## {n}: {_cell(b['name'])}")
    w("")
    w(f"Measured by {', '.join(b['measured_by'])}; equal to `{b['agrees_with']['path']}`. Overall: **{b['overall']}**.")
    w("")
    w("| measure | value | label |")
    w("|---|---|---|")
    for m, lab in sorted(b["labels"].items()):
        x = v
        for part in m.split("."):
            x = x[part]
        w(f"| `{m}` | {_prop(x)} | {lab} |")
    w("")
    if n == "L6":
        w(f"Population: {v['population']} findings (F(M3), I54's base.l6_findings). Verdicts: "
          + ", ".join(f"{k} {v['verdicts'][k]}" for k in sorted(v["verdicts"]))
          + f". Invalid target records: {len(v['invalid'])}. V9 (the lead's condition 1): "
          f"{v['v9']['numerator']} of {v['v9']['denominator']} value-moving actions covered, holds "
          f"{str(v['v9']['holds']).lower()}.")
        w("")
        c, k = v["controls"], v["corpus"]
        w(f"Constructed truth (controls, never pooled): {c['items']} items, strict correct {c['strict_correct']}, "
          f"majority baseline {c['majority_baseline']}, false_rational {len(c['false_rational'])}, false_irrational "
          f"{len(c['false_irrational'])}, invalid {len(c['invalid'])}.")
        w("")
        w(f"Documented truth (corpus): {k.get('items', 0)} items" +
          (f" ({_cell(k['reason'])})" if k.get("reason") else "") + ".")
        w("")
    if n == "L9":
        w("| module | category | admissible sets | worst held-out slice | R1 | R2 | R3 | R4 | R5 | R6 | validated |")
        w("|---|---|---|---|---|---|---|---|---|---|---|")
        for mid, m in sorted(v["modules"].items()):
            r = m["rules"]
            w(f"| `{mid}` | {m['category']} | {', '.join(m['admissible']) or 'none'} | {m['worst']} | "
              + " | ".join("yes" if r[x] else "no" for x in ("R1", "R2", "R3", "R4", "R5", "R6"))
              + f" | {'yes' if m['validated'] else 'no'} |")
        w("")
        w("| category | dependent | covered | forms |")
        w("|---|---|---|---|")
        for cat, s in sorted(v["by_category"].items()):
            w(f"| {cat} | {s['dependent']} | {s['covered']} | "
              + ", ".join(f"{f} {k}" for f, k in sorted(s["forms"].items())) + " |")
        w("")
        s = v["sensitivity"]
        w(f"Sensitivity: counted {s['count']} ({', '.join(f'`{x}`' for x in s['counted']) or 'none'}), unreplayed "
          f"{len(s['unreplayed'])}, to UNKNOWN {len(s['to_unknown'])}. Base laws that lost their environment "
          f"premises: {len(v['base_dropped'])}. Unclassified ids: {len(v['unclassified'])}.")
        w("")
        sets = b["inputs"]["observation_sets"]
        w("Observation sets (history truth): " + "; ".join(
            f"`{k}` {'admitted' if x['admitted'] else 'not admitted'}, sha256 `{x['sha256']}`"
            for k, x in sorted(sets.items())) + ".")
        w("")
    if n == "L10":
        tt = b["trivially_true"]
        w(f"Census: {v['census']} clauses (the frozen base census; no second census). Beside coverage (the lead's "
          f"condition G2(b)): trivially true covering laws {_prop(tt['covering'])} "
          f"({common.size_label(tt['covering']['denominator'])}), trivially true control laws "
          f"{_prop(tt['controls'])}. False obstructions: {len(v['false_obstruction'])}.")
        w("")
        cr = b["corpus_recall"]
        w(f"Documented truth (corpus_recall, never pooled with the controls): {_prop(cr['corpus_recall'])}, "
          f"**{cr['label']}** (never judged); scored entries: "
          + ", ".join(f"{e} (l10 {x['l10']}, {x['atoms']} atoms, {len(x['obstructions'])} obstructions)"
                      for e, x in sorted(cr["entries"].items())) + ".")
        w("")
    w(f"Pins of {n}:")
    w("")
    _pins_table(w, b)


def _predictions(w, root: Path, side: dict) -> None:
    w("## The M5 predictions and their outcomes")
    w("")
    w("Each outcome is the one the iteration's own report records (its prediction table); `informed` predictions "
      "were known in part before their prereg and are not counted (the key's thresholds.counting). Misses stand: "
      "BUILD_PLAN §0.1 forbids editing a prediction.")
    w("")
    tally = []
    for k in side["keys"]:
        key = _key(root, k)
        inf = _informed(key)
        oc = outcomes(root, k) if key["predictions"] else {}
        w(f"### {k} (`{report_path(root, k)}`)")
        w("")
        if not key["predictions"]:
            w("No counted prediction: the key's outcome followed from the repository's state.")
            w("")
            tally.append((k, 0, 0, 0, 0))
            continue
        w("| id | counted | claim | outcome (as recorded) | result |")
        w("|---|---|---|---|---|")
        for p in key["predictions"]:
            o = oc[p["id"]]
            w(f"| {p['id']} | {'informed' if p['id'] in inf else 'counted'} | {_cell(p['claim'])} | "
              f"{_cell(o['outcome'])} | {o['result']} |")
        w("")
        counted = [p["id"] for p in key["predictions"] if p["id"] not in inf]
        tally.append((k, sum(oc[i]["result"] == "held" for i in counted), len(counted),
                      sum(oc[i]["result"] == "held" for i in inf), len(inf)))
    w("### Tally")
    w("")
    w("| key | counted held | counted | informed held | informed |")
    w("|---|---|---|---|---|")
    for k, h, c, ih, i in tally:
        w(f"| {k} | {h} | {c} | {ih} | {i} |")
    th, tc = sum(t[1] for t in tally), sum(t[2] for t in tally)
    w(f"| all | {th} | {tc} | {sum(t[3] for t in tally)} | {sum(t[4] for t in tally)} |")
    w("")
    w(f"{th} of {tc} counted predictions held; {tc - th} missed.")
    w("")
    own = _key(root, REPORT_KEY)
    rel = report_path(root, REPORT_KEY)
    w(f"### {REPORT_KEY} (this report's own key)")
    w("")
    try:
        oc = outcomes(root, REPORT_KEY) if (Path(root) / rel).is_file() else None
    except ReportError:
        oc = None
    inf = _informed(own)
    w("| id | counted | claim | result |")
    w("|---|---|---|---|")
    for p in own["predictions"]:
        res = oc[p["id"]]["result"] if oc else f"recorded in `{rel}`"
        w(f"| {p['id']} | {'informed' if p['id'] in inf else 'counted'} | {_cell(p['claim'])} | {res} |")
    w("")


# ------------------------------------------------------------------ files
def files(root: Path = ROOT) -> dict[str, str]:
    from .. import metrics as M
    root = Path(root)
    doc = M.compute("M5", root)
    block = {n: doc[n] for n in NAMES} | {"m5_report": doc["m5_report"]}
    return {METRICS: M.render(doc), REPORT: render(root, block)}


def write(root: Path = ROOT, check: bool = False) -> list[str]:
    root = Path(root)
    out = []
    for rel, text in sorted(files(root).items()):
        p = root / rel
        have = p.read_text(encoding="utf-8") if p.is_file() else None
        if have != text:
            if check:
                out.append(f"{rel}: differs (python -m holon m5 report)")
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                out.append(rel)
    return out
