"""I52b's instrument (the baselines on the held-out target): the labels' generation rule, applicability, the matching
rule and the predictions' readers, written independently of holon/ (holon.eval.baselines is the tool; this module is
what the tests trust).

It reads only the frozen sidecars (spec/M4/lib/I52b_heldout.json, its labels file and match prompt; I52's protocol,
schema and review prompt through tests_m4/_i52.py), I49's committed document and target file, the results under
results/eval/heldout/ and git. It imports nothing from holon/ and nothing from tests/reference/.

Labels (I52b_heldout.json labels.rule): the state-moving actions of I49's document declared in a labelled file, sorted
by name; per action the rules DISCH, FACT, SORT, SYM, UNDO; ids O1.. action-major; anchors the distinct spans of every
src of the action in a labelled file.
Matching: a finding is located at O<k> iff one of its locations names a labelled file and its span meets an anchor
span of O<k> (I52's 150-line rule); detected: the labels with at least one finding the adjudicator confirmed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

from tests_m4 import _i52, _m4

ROOT = _m4.ROOT
LIB = ROOT / "spec" / "M4" / "lib"
PROTOCOL = LIB / "I52b_heldout.json"
LABELS = LIB / "I52b_heldout_labels.json"
MATCH_PROMPT = LIB / "I52b_match_prompt.md"
RESULTS = ROOT / "results" / "eval" / "heldout"
HOLON_BUDGET = RESULTS / "holon_budget.json"
TARGET_FILE = ROOT / "targets" / "scroll" / "target.json"
RULES = ("DISCH", "FACT", "SORT", "SYM", "UNDO")
TIERS = ("primary", "secondary")
SYSTEM = "heldout"
_SRC = re.compile(r"^(.+):(\d+)(?:-(\d+))?$")

load = _i52.load
sha256_file = _i52.sha256_file
BASELINES = _i52.BASELINES
SOLIDITY = _i52.SOLIDITY
GO = _i52.GO


def protocol() -> dict:
    return load(PROTOCOL)


def target() -> str:
    return protocol()["system"]["target"]


def targets() -> list[str]:
    return [target()]


def labelled_files() -> list[str]:
    return list(protocol()["system"]["labelled_files"])


def document_path() -> Path:
    t = load(TARGET_FILE)
    (rel,) = t["extract"]["documents"].values()
    return ROOT / rel


# ------------------------------------------------------------------------------------------------- labels
def _srcs(obj, acc: set) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "src" and isinstance(v, str):
                acc.add(v)
            else:
                _srcs(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _srcs(v, acc)


def _span(src: str):
    m = _SRC.match(src)
    if not m:
        return None
    a = int(m.group(2))
    return m.group(1), [a, int(m.group(3) or a)]


def labels() -> dict:
    """The labels file's "labels" object, generated from I49's document by the rule (I52b_heldout.json labels.rule)."""
    files = set(labelled_files())
    doc = load(document_path())
    acts = []
    for a in doc["actions"]:
        own = _span(a["src"])
        if own is None or own[0] not in files or a.get("mutability") in ("view", "pure"):
            continue
        acc: set = set()
        _srcs(a, acc)
        spans = sorted({(f, s[0], s[1]) for f, s in (x for x in map(_span, acc) if x) if f in files})
        acts.append((a["name"], [{"file": f, "lines": [x, y]} for f, x, y in spans]))
    acts.sort(key=lambda t: t[0])
    out, k = {}, 0
    for name, anchors in acts:
        for r in RULES:
            k += 1
            out[f"O{k}"] = {"action": name, "rule": r, "anchors": anchors}
    return out


def label_table() -> dict:
    return load(LABELS)["labels"]


def label_key(k: str):
    return (k[0], int(k[1:]))


# ------------------------------------------------------------------------------------------------- scope, budget, files
def scope_dirs() -> list[str]:
    return sorted({PurePosixPath(f).parent.as_posix() for f in labelled_files()})


def languages() -> set:
    return {"go" if f.endswith(".go") else "solidity" for f in labelled_files()}


def applicable(baseline: str) -> bool:
    if baseline in SOLIDITY:
        return "solidity" in languages()
    if baseline in GO:
        return "go" in languages()
    return True


def budget(tier: str) -> dict:
    b = protocol()["budget"][tier]
    if tier == "primary":
        hb = load(HOLON_BUDGET)
        h = hb["sum_s"]
        assert abs(h - sum(s["wall_s"] for s in hb["steps"])) < 1e-6, hb
        w = 60 * -(-int(round(h * 1000)) // 60000)
        assert hb["heldout_wall_s"] == w, hb
        return {"wall_s": w, "cpus": b["cpus"], "setup_cap_s": b["setup_cap_s"]}
    return {"wall_s": b["wall_s"], "cpus": b["cpus"], "setup_cap_s": b["setup_cap_s"]}


def result_dir(tier: str) -> Path:
    return RESULTS if tier == "primary" else RESULTS / "secondary"


def result_path(tier: str, baseline: str) -> Path:
    return result_dir(tier) / f"{baseline}.json"


def timing_path(tier: str, baseline: str) -> Path:
    return result_dir(tier) / f"{baseline}.timing.json"


# ------------------------------------------------------------------------------------------------- matching
def located(finding: dict) -> list[str]:
    files = set(labelled_files())
    out = []
    for lab, v in label_table().items():
        if any(loc["file"] in files and loc["file"] == a["file"] and _i52._meets(loc["lines"], *a["lines"])
               for a in v["anchors"] for loc in finding["locations"]):
            out.append(lab)
    return sorted(out, key=label_key)


def expected_matches(record: dict) -> list[tuple[str, str]]:
    return sorted((f["id"], lab) for f in record["findings"] for lab in located(f))


def detected(record: dict) -> list[str]:
    return sorted({a["label"] for a in record["adjudications"] if a["confirmed"]}, key=label_key)


def match_prompt(action: str, findings: list[dict]) -> str:
    """The adjudicator's prompt for one (baseline, action) group: the frozen template filled in."""
    t = MATCH_PROMPT.read_text(encoding="utf-8")
    obl = protocol()["labels"]["obligations"]
    rows = "\n".join(json.dumps({k: f[k] for k in ("id", "kind", "message", "locations")}, sort_keys=True,
                                ensure_ascii=False) for f in findings)
    return (t.replace("{{ACTION}}", action)
            .replace("{{OBLIGATIONS}}", "\n".join(f"- {r}: {obl[r]}" for r in RULES))
            .replace("{{FINDINGS}}", rows))


# ------------------------------------------------------------------------------------------------- the predictions
def record(tier: str, baseline: str) -> dict:
    return load(result_path(tier, baseline))["targets"][target()]


def ran(tier: str, baseline: str) -> bool:
    """non_vacuity on a one-target system: the baseline ran (status run) on the target."""
    return record(tier, baseline)["status"] == "run"


def detected_set(tier: str, baseline: str) -> set:
    return set(record(tier, baseline)["detected"])


def located_set(tier: str, baseline: str) -> set:
    return set(record(tier, baseline)["located"])


LABELS_DOC = ("I52b prereg sidecar, generated by tests_m4/_i52b.py labels_doc() from I49's committed document by the rule "
              "of spec/M4/lib/I52b_heldout.json labels.rule (never hand-edited, never from a baseline's output). Each "
              "label is one (rule, action) obligation of the sealed contract; its anchors are the action's source spans "
              "in the labelled file. Used only by the matcher and the adjudicator; never shown to a baseline.")


def labels_doc() -> dict:
    return {"doc": LABELS_DOC, "commit": protocol()["system"]["commit"],
            "document": document_path().relative_to(ROOT).as_posix(),
            "document_sha256": sha256_file(document_path()), "labels": labels()}
