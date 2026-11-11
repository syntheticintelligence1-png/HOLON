"""I52's instrument (the baselines): the matching rules, applicability, statuses and the predictions' outcomes, written a
second time, independently of holon/ (holon.eval.baselines is the tool; this module is what the tests trust).

It reads only the frozen sidecars (spec/M4/lib/I52_*.json and .md), spec/eval/corpus.json, the results under
results/eval/<system>/ and git (through tests_m4/_i48.py's own partial clones, never holon's cache). It imports nothing
from holon/ and nothing from tests/reference/.

Matching (I52_baselines.json "matching"):
  corpus: a finding on entry e is located at e iff one of its locations names a file of e.files and its line span [a, b]
          intersects [l - W, l + W] for some l of L(e, file), W = 10, where L is the old side of every hunk of
          `git diff -U0 prefix fix -- file` (a..a+n-1), and lines a and a + 1 for a pure insertion (@@ -a,0 ...);
  morph:  a finding is located at O<k> iff one of its locations names an anchor's file and its span intersects the
          anchor's span.
  detected: the labels for which the blinded match adjudicator confirmed at least one located finding (its confirmed ids
          a subset of the located ones).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from tests_m4 import _i48, _m4

ROOT = _m4.ROOT
LIB = ROOT / "spec" / "M4" / "lib"
PROTOCOL = LIB / "I52_baselines.json"
SCHEMA = LIB / "I52_findings.schema.json"
ANCHORS = LIB / "I52_morph_anchors.json"
REVIEW_PROMPT = LIB / "I52_review_prompt.md"
MATCH_PROMPT = LIB / "I52_match_prompt.md"
CORPUS = ROOT / "spec" / "eval" / "corpus.json"
RESULTS = ROOT / "results" / "eval"
BASELINES = ("slither", "echidna", "medusa", "hevm", "halmos", "go_fuzz", "two_cycle", "spec_mining", "agent_review")
SOLIDITY = ("slither", "echidna", "medusa", "hevm", "halmos")
GO = ("go_fuzz", "two_cycle")
BOTH = ("spec_mining", "agent_review")
SYSTEMS = ("morph", "corpus")
WINDOW = 10
STATUSES = ("run", "not_applicable", "missing", "error")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)
RUNTIME_STATE = ("_LINES",)
_LINES: dict = {}


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def protocol() -> dict:
    return load(PROTOCOL)


def entries() -> list[dict]:
    return load(CORPUS)["entries"]


def anchors() -> dict:
    return load(ANCHORS)["obstructions"]


def result_path(system: str, baseline: str) -> Path:
    return RESULTS / system / f"{baseline}.json"


def timing_path(system: str, baseline: str) -> Path:
    return RESULTS / system / f"{baseline}.timing.json"


# ------------------------------------------------------------------------------------------------- scope, applicability
def is_test(path: str) -> bool:
    proto = load(_i48.PROTOCOL)
    return _i48.is_test_path(path, proto)


def scope_dirs(system: str, target: str) -> list[str]:
    """The directories whose non-test .go/.sol files are the scope (I52_baselines.json scope.rule)."""
    if system == "morph":
        files = [a["file"] for o in anchors().values() for a in o["anchors"]]
    else:
        files = next(e for e in entries() if e["id"] == target)["files"]
    return sorted({PurePosixPath(f).parent.as_posix() for f in files})


def languages(system: str, target: str) -> set:
    """The languages of the target. Morph: those of the anchored files; a corpus entry: its manifest languages (the
    languages of its labelled files)."""
    if system == "morph":
        return {"go" if a["file"].endswith(".go") else "solidity" for o in anchors().values() for a in o["anchors"]}
    return set(next(e for e in entries() if e["id"] == target)["languages"])


def applicable(baseline: str, system: str, target: str) -> bool:
    langs = languages(system, target)
    if baseline in SOLIDITY:
        return "solidity" in langs
    if baseline in GO:
        return "go" in langs
    return True


HOLON_BUDGET = RESULTS / "holon_budget.json"


def budget(system: str) -> dict:
    """The system's budget: corpus as the protocol states it; Morph's wall_s by the protocol's rule, 60 * ceil(H / 60)
    over results/eval/holon_budget.json's sum_s, which must be m0_s + m1_s + m2_s + m3_s."""
    b = dict(protocol()["budget"][system])
    if "wall_s_rule" in b:
        hb = load(HOLON_BUDGET)
        h = hb["m0_s"] + hb["m1_s"] + hb["m2_s"] + hb["m3_s"]
        assert abs(hb["sum_s"] - h) < 1e-6, (hb["sum_s"], h)
        b = {"wall_s": 60 * -(-int(round(h * 1000)) // 60000), "cpus": b["cpus"], "setup_cap_s": b["setup_cap_s"]}
        assert hb["morph_wall_s"] == b["wall_s"], hb
    return b


def targets(system: str) -> list[str]:
    return ["morph"] if system == "morph" else [e["id"] for e in entries()]


# ------------------------------------------------------------------------------------------------- matching
def lines_from_diff(text: str) -> list[int]:
    """L of the matching rule from a -U0 diff: a..a+n-1 per hunk, and a, a+1 for a pure insertion."""
    out = set()
    for m in _HUNK.finditer(text):
        a = int(m.group(1))
        n = int(m.group(2)) if m.group(2) is not None else 1
        if n == 0:
            out.update((a, a + 1))
        else:
            out.update(range(a, a + n))
    return sorted(out)


def fix_lines(entry: dict, path: str) -> list[int]:
    key = (entry["id"], path)
    if key not in _LINES:
        d = _i48.repo_cache(entry["repo"])
        out = _i48.git(d, *_i48._DIFF, "-U0", entry["prefix_commit"], entry["fix_commit"], "--", path, text=False)
        _LINES[key] = lines_from_diff(out.decode("utf-8", errors="replace"))
    return _LINES[key]


MAX_SPAN = 150


def _meets(span, lo: int, hi: int) -> bool:
    """span intersects [lo, hi]; a span longer than MAX_SPAN lines counts as its first line only (matching.spans)."""
    a, b = span
    if b - a + 1 > MAX_SPAN:
        b = a
    return a <= hi and lo <= b


def located_corpus(finding: dict, entry: dict) -> bool:
    for loc in finding["locations"]:
        if loc["file"] in entry["files"]:
            if any(_meets(loc["lines"], l - WINDOW, l + WINDOW) for l in fix_lines(entry, loc["file"])):
                return True
    return False


def located_morph(finding: dict) -> list[str]:
    out = []
    for oid, o in anchors().items():
        for a in o["anchors"]:
            if any(loc["file"] == a["file"] and _meets(loc["lines"], *a["lines"]) for loc in finding["locations"]):
                out.append(oid)
                break
    return sorted(out, key=lambda k: int(k[1:]))


def expected_matches(system: str, target: str, record: dict) -> list[tuple[str, str]]:
    """(finding id, label) of every located pair, sorted."""
    pairs = []
    if system == "morph":
        for f in record["findings"]:
            pairs += [(f["id"], o) for o in located_morph(f)]
    else:
        e = next(x for x in entries() if x["id"] == target)
        pairs += [(f["id"], target) for f in record["findings"] if located_corpus(f, e)]
    return sorted(pairs)


def detected(record: dict) -> list[str]:
    """The labels with at least one confirmed finding (each confirmation a subset of its located findings)."""
    out = {a["label"] for a in record["adjudications"] if a["confirmed"]}
    return sorted(out, key=lambda k: (k[0], int(k[1:])))


# ------------------------------------------------------------------------------------------------- the predictions
def detected_by(system: str, baseline: str) -> dict[str, list[str]]:
    """target -> its detected labels, from the committed result file."""
    doc = load(result_path(system, baseline))
    return {t: r["detected"] for t, r in doc["targets"].items()}


def ran_enough(system: str, baseline: str) -> bool:
    """non_vacuity: the baseline ran (status run) on at least half of the targets where it applies on the system."""
    doc = load(result_path(system, baseline))
    app = [t for t in targets(system) if applicable(baseline, system, t)]
    ran = [t for t in app if doc["targets"][t]["status"] == "run"]
    return bool(app) and 2 * len(ran) >= len(app)


def corpus_detected(baseline: str) -> set:
    return {t for t, d in detected_by("corpus", baseline).items() if t in d}


def morph_detected(baseline: str) -> set:
    return set(detected_by("morph", baseline).get("morph", []))
