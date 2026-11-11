"""I51 instrument, fixed at the I51 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m4/test_i51_corpus_run.py (rules H0-H9, S1-S6). This module writes the scoring
rules out a second time, independently of holon/, so that the tests can decide from the committed artifacts and the
public repositories what holon eval holon must have written:

- hunk_lines(diff_text) and locus(entry): rule S1, the defect locus, the pre-fix lines the fix deletes or changes (and,
  for a pure insertion, the two old lines it sits between), from the instrument's own clones (tests_m4/_i48.py's cache,
  never holon's);
- spans_in(obj, files) and sites(law, entry_dir, files): rule S2, the source sites of a law;
- localized(sites, locus): rule S3;
- finding_class(record, is_localized): rule S4;
- score(rows): rules S5-S6, per-entry detection, per-rule recall and the precision split, recomputed from the rows' laws;
- recheck(entry_dir, record): rule H7, Bend's verdict on a committed counter-law, re-run in a scratch copy.

Inputs only: spec/eval/corpus.json, spec/M4/lib/i51_run.json, results/eval/holon/ and public git repositories. Nothing
here imports holon/.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests_m4 import _i48, _m4

ROOT = _m4.ROOT
CORPUS = ROOT / "spec" / "eval" / "corpus.json"
PROTOCOL = ROOT / "spec" / "M4" / "lib" / "i51_run.json"
OUT = ROOT / "results" / "eval" / "holon"
ROWS = OUT / "corpus.json"
MILESTONE = "T510"
RULES = ("PAR", "SORT", "DISCH", "UNDO", "NAT", "FACT", "SYM", "OWN")   # the rules a label can name (none aside)
CLASSES = ("true_defect", "intended_asymmetry", "model_defect", "unreplayed")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def entries() -> list[dict]:
    return load(CORPUS)["entries"]


# ---------------------------------------------------------------------------------------------- S1: the locus
def hunk_lines(text: str) -> list[list[int]]:
    """Old-side intervals of every hunk of a -U0 diff: @@ -a,b +c,d @@ with b > 0 is [a, a+b-1]; b = 0 (a pure
    insertion after old line a) is [max(a,1), a+1]; b omitted means 1. Sorted, merged when they overlap or touch."""
    iv = []
    for m in _HUNK.finditer(text):
        a, b = int(m.group(1)), int(m.group(2)) if m.group(2) is not None else 1
        iv.append([a, a + b - 1] if b > 0 else [max(a, 1), a + 1])
    iv.sort()
    out: list[list[int]] = []
    for s, t in iv:
        if out and s <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], t)
        else:
            out.append([s, t])
    return out


def locus(entry: dict) -> dict[str, list[list[int]]]:
    """{file: intervals} for every entry file, from git diff -U0 prefix fix -- file in the instrument's clone."""
    d = _i48.repo_cache(entry["repo"])
    for sha in (entry["prefix_commit"], entry["fix_commit"]):
        if not _i48.ensure_commit(d, sha):
            raise AssertionError(f"{entry['repo']}@{sha} is not reachable")
    out = {}
    for f in entry["files"]:
        txt = _i48.git(d, *_i48._DIFF, "-U0", entry["prefix_commit"], entry["fix_commit"], "--", f, text=False)
        out[f] = hunk_lines(txt.decode("utf-8", errors="replace"))
    return out


def prefix_tree(entry: dict) -> str:
    d = _i48.repo_cache(entry["repo"])
    return _i48.git(d, "rev-parse", entry["prefix_commit"] + "^{tree}").strip()


# ---------------------------------------------------------------------------------------------- S2-S3: sites
def _strings(x, out: list) -> None:
    if isinstance(x, str):
        out.append(x)
    elif isinstance(x, list):
        for y in x:
            _strings(y, out)
    elif isinstance(x, dict):
        for k in sorted(x):
            _strings(k, out)
            _strings(x[k], out)


def spans_in(obj, files: list[str]) -> list[list]:
    """Every span `<file>:<a>` or `<file>:<a>-<b>` in a string of obj whose file is one of files (exact path; the
    character before the path is not a path character), as [file, a, b], sorted and unique."""
    found = set()
    strs: list[str] = []
    _strings(obj, strs)
    for f in files:
        pat = re.compile(r"(?<![A-Za-z0-9_./-])" + re.escape(f) + r":([1-9][0-9]*)(?:-([1-9][0-9]*))?")
        for s in strs:
            for m in pat.finditer(s):
                a = int(m.group(1))
                b = int(m.group(2)) if m.group(2) else a
                found.add((f, a, max(a, b)))
    return [list(x) for x in sorted(found)]


def witness_actions(record: dict) -> list[str]:
    w = record.get("witness") or {}
    return sorted({s["action"] for s in (w.get("steps") or []) if isinstance(s, dict) and isinstance(s.get("action"), str)})


def sites(law_id: str, entry_dir: Path, files: list[str]) -> list[list]:
    """Rule S2: the spans in the law file, its DERIVATION entry and its record, and the src span of every action of
    the law's facts document that the record's witness steps name."""
    law = load(entry_dir / "laws" / f"{law_id}.json")
    der = {e["law_id"]: e for e in load(entry_dir / "laws" / "DERIVATION.json")["laws"]}.get(law_id, {})
    rp = entry_dir / "records" / f"{law_id}.json"
    rec = load(rp) if rp.is_file() else {}
    objs = [law, der, rec]
    acts = witness_actions(rec)
    if acts:
        fp = entry_dir / "facts" / Path(law["facts"]).name
        doc = load(fp) if fp.is_file() else {}
        objs += [a.get("src") for a in doc.get("actions") or [] if a.get("name") in acts]
    return spans_in(objs, files)


def localized(site_list: list[list], loc: dict[str, list[list[int]]]) -> bool:
    for f, a, b in site_list:
        for s, t in loc.get(f, []):
            if a <= t and s <= b:
                return True
    return False


# ---------------------------------------------------------------------------------------------- S4-S6: scoring
def finding_class(record: dict, is_localized: bool) -> str:
    st = (record.get("replay") or {}).get("status")
    if st == "failed":
        return "model_defect"
    if is_localized:
        return "true_defect"
    if st == "passed":
        return "intended_asymmetry"
    return "unreplayed"


def score(rows: list[dict]) -> dict:
    """Rules S5-S6 over rows whose laws carry rule, status, localized and class."""
    per_rule = {}
    for r in RULES:
        es = [x for x in rows if x["label"] == r]
        if es:
            det = [x["id"] for x in es if x["detected"]]
            per_rule[r] = {"entries": len(es), "detected": det, "recall": len(det) / len(es)}
    any_det = [x["id"] for x in rows if x["detected_any"]]
    counts = {c: 0 for c in CLASSES}
    for x in rows:
        for law in x["laws"]:
            if law["status"] == "REFUTED":
                counts[law["class"]] += 1
    n = sum(counts.values())
    return {"recall": per_rule, "detected_any": any_det, "findings": n, "classes": counts,
            "precision": (counts["true_defect"] / n) if n else None}


def detected(row: dict) -> tuple[bool, bool]:
    ref = [law for law in row["laws"] if law["status"] == "REFUTED" and law["localized"]]
    return any(law["rule"] == row["label"] for law in ref), bool(ref)


# ---------------------------------------------------------------------------------------------- H7: Bend's verdict
def recheck(entry_dir: Path, record: dict) -> tuple[bool, str]:
    """Bend re-checks a REFUTED record's counter-law: its proof file under the entry's gen/ (the record's artifacts.proof,
    gen/<milestone>/... mapped to <entry>/gen/...) checks in a scratch copy, and its laws file names the counter-law."""
    art = record.get("artifacts") or {}
    pre = f"gen/{MILESTONE}/"
    proof, laws, name = art.get("proof"), art.get("laws"), art.get("law_name")
    if not (isinstance(proof, str) and proof.startswith(pre) and isinstance(laws, str) and laws.startswith(pre) and name):
        return False, f"artifacts {art}"
    tmp = Path(tempfile.mkdtemp(prefix="i51-recheck-"))
    try:
        g = tmp / "gen" / MILESTONE
        shutil.copytree(entry_dir / "gen", g)
        lt = (g / laws[len(pre):]).read_text(encoding="utf-8")
        if not re.search(r"\b" + re.escape(name) + r"\b", lt):
            return False, f"{laws} does not name {name}"
        pf = g / proof[len(pre):]
        p = subprocess.run(["bend", pf.name], cwd=pf.parent, capture_output=True, text=True, timeout=1800,
                           env={**_i48._env(), "BEND_NO_TELEMETRY": "1"})
        out = p.stdout + p.stderr
        return (p.returncode == 0 and "ALL PROOFS CHECK" in out), out[-800:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
