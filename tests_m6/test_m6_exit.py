"""The M6 exit record, docs/M6_EXIT.md: the lead's decision under docs/BUILD_PLAN.md's M6 exit criterion.

The criterion: "The generality run (I107) is reported. Its prereg comes before the reveal of I106's sealed targets.
It covers the corpus rerun (labelled contaminated), the fresh sealed targets, and Morph under `--roles auto`,
scored against I48 and I52/I52b's baselines. No number is a gate: a miss is a result. Tests live in `tests_m6/`."

Each clause is recomputed from committed files and the git history:

  X1 I107 is reported: docs/iterations/I107.md scores each of the key's predictions P1-P12, and the summary
     regenerates from the committed outcomes (tools/i107_generality.py assemble --check).
  X2 its prereg comes before the reveal: `holon audit prereg --milestone M6` passes and names I107's prereg commit,
     whose committer time is earlier than that of the commit that added spec/heldout2/target.json; and the reveal
     verifies (spec/M6/lib/I106_draw.py verify prints VERIFY OK).
  X3 the three runs: results/eval/generality/summary.json covers the corpus (labelled contaminated, one row per entry
     of spec/eval/corpus.json), the sealed targets (exactly target.json's systems) and Morph under --roles auto
     (labelled contaminated, with role precision and recall and the new laws' counts).
  X4 scored against the baselines: I107's report has the scoring table's agent-reviewer and slither columns (I52)
     with a delta row, and results/eval/generality/sealed/slither.json covers every sealed target.
  X5 no number is a gate: the record names every prediction the report scores as missed or withheld.
  X6 tests live in tests_m6/: every M6 key's prereg names its test files under tests_m6/, and CI runs a
     tests-m6-<key> job for each key.
  X7 the record's clause table states each clause's verdict as X1-X6 compute it, and its decision line says the
     exit is met iff they all hold.

The test reads committed files and git only. It runs no analysis of a sealed target (HUMAN_ANSWERS Q56 (5)).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "docs" / "M6_EXIT.md"
REPORT = ROOT / "docs" / "iterations" / "I107.md"
OUT = ROOT / "results" / "eval" / "generality"
HELD = ROOT / "spec" / "heldout2"
PRED = ROOT / "spec" / "M6" / "predictions"
CI = ROOT / ".github" / "workflows" / "holon-ci.yml"
CLAUSES = ("X1", "X2", "X3", "X4", "X5", "X6")


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def run(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def git(*args: str) -> str:
    return run(["git", *args]).stdout.strip()


def scored() -> dict:
    """{prediction id: outcome word} from I107's prediction table ("held", "missed" or "withheld")."""
    out = {}
    for line in REPORT.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (P\d+) \|", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        last = " ".join(cells[2:]).lower()
        out[m.group(1)] = ("withheld" if "withheld" in last else "missed" if "**missed**" in last
                           else "held" if "**held**" in last else "")
    return out


def clauses() -> dict:
    """{clause: holds} for X1-X6."""
    out = {}
    key = load(PRED / "I107.json")
    want = sorted((p["id"].split("-")[-1] for p in key["predictions"]), key=lambda s: int(s[1:]))
    sc = scored()
    out["X1"] = (sorted(sc, key=lambda s: int(s[1:])) == want and all(sc.values())
                 and run([sys.executable, "tools/i107_generality.py", "assemble", "--check"]).returncode == 0)

    audit = run([sys.executable, "-m", "holon", "audit", "prereg", "--milestone", "M6"], timeout=1800).stdout
    m = re.search(r"^I107: OK prereg ([0-9a-f]{7,40})", audit, re.M)
    added = git("log", "--diff-filter=A", "--format=%H", "--", "spec/heldout2/target.json").split()
    ok = bool(m) and "PREREG OK" in audit and bool(added)
    if ok:
        prereg_t = int(git("show", "-s", "--format=%ct", m.group(1)))
        reveal_t = int(git("show", "-s", "--format=%ct", added[-1]))
        verify = run([sys.executable, "spec/M6/lib/I106_draw.py", "verify", "--target", str(HELD / "target.json"),
                      "--salt", str(HELD / "salt.txt"), "--commitment", str(HELD / "commitment.json")])
        ok = prereg_t < reveal_t and "VERIFY OK" in verify.stdout
    out["X2"] = ok

    s = load(OUT / "summary.json")
    corpus = load(ROOT / "spec" / "eval" / "corpus.json")["entries"]
    systems = sorted(t["id"] for t in load(HELD / "target.json")["targets"])
    morph = s["morph"]
    out["X3"] = ("contaminated" in s["corpus"]["label"] and len(s["corpus"]["rows"]) == len(corpus)
                 and sorted(t["system"] for t in s["sealed"]["targets"]) == systems
                 and "contaminated" in morph["label"]
                 and all(k in morph for k in ("precision", "recall", "new_laws", "new_decided", "new_unknown")))

    text = REPORT.read_text(encoding="utf-8")
    sealed_ids = sorted(t["id"] for t in s["sealed"]["targets"])
    out["X4"] = ("agent reviewer (I52)" in text and "slither (I52)" in text
                 and re.search(r"^\| delta, I107 minus baseline \|", text, re.M) is not None
                 and sorted(load(OUT / "sealed" / "slither.json")["targets"]) == sealed_ids)

    rec = RECORD.read_text(encoding="utf-8")
    m5 = re.search(r"^Misses and withheld predictions of I107: (.*)$", rec, re.M)
    named = set(re.findall(r"\bP\d+\b", m5.group(1))) if m5 else set()
    out["X5"] = bool(m5) and named == {p for p, o in sc.items() if o in ("missed", "withheld")}

    ci = CI.read_text(encoding="utf-8")
    keys = sorted(p.stem for p in PRED.glob("I1*.json"))
    out["X6"] = bool(keys) and all(
        load(PRED / f"{k}.json")["tests"] and all(t.startswith("tests_m6/") for t in load(PRED / f"{k}.json")["tests"])
        and f"name: tests-m6-{k.lower()}\n" in ci for k in keys)
    return out


class TestM6Exit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.computed = clauses()
        cls.rec = RECORD.read_text(encoding="utf-8")

    def test_x1_to_x6(self):
        for c in CLAUSES:
            with self.subTest(clause=c):
                self.assertTrue(self.computed[c], f"{c} does not hold")

    def test_x7_the_table_and_the_decision(self):
        rows = {}
        for line in self.rec.splitlines():
            m = re.match(r"^\| (X\d) \| .*\| (yes|no) \|", line)
            if m:
                rows[m.group(1)] = m.group(2) == "yes"
        self.assertEqual(sorted(rows), list(CLAUSES))
        self.assertEqual(rows, {c: bool(self.computed[c]) for c in CLAUSES})
        met = all(self.computed[c] for c in CLAUSES)
        self.assertEqual("**The M6 exit is met.**" in self.rec, met)
        self.assertEqual("**The M6 exit is not met.**" in self.rec, not met)


if __name__ == "__main__":
    unittest.main()
