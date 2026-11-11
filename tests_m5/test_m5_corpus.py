"""I56b: L6's corpus accuracy scored against the corpus-truth key I54b (the lead's condition 5 on PR #134). This
docstring is the contract that tests_m5/test_m5_corpus.py checks.

The key I56b (spec/M5/predictions/I56b.json) pins spec/M5/truth/corpus.json, its run sidecar and spec/eval/corpus.json
by sha256 before any score. L6 is I54's definition through I56's l6_v9 (tests_m5/_i56.py, pinned by I56), unchanged.

Rules
  Q1 The pins hold.
  Q2 results/M5/corpus/mapping.json has one row per truth entry: its L6 truth as the truth file gives it, its fix
     commit and pre-fix commit (fix_commit + "^", named, not resolved), its mapped findings and, when none, the
     reason. An undocumented entry maps none and contributes no item; c13 never. Without I51's
     results/eval/holon/corpus.json no entry maps a finding.
  Q3 results/M5/corpus/l6_corpus.json is tests_m5/_i56.py's l6_v9 over I56's committed records with corpus_truth the
     mapped items' truth; with 0 items the corpus measures are not_measured.
  Q4 `python -m holon games corpus --check` exits 0.
Regressions I56b-R1..R3: I56's outputs unchanged; the truth pinned; the truth's L6 counts.
"""
from __future__ import annotations

import collections
import json
import subprocess
import sys
import unittest

from tests_m5 import _i56 as G
from tests_m5._m5 import ROOT, file_sha256, git, load_json, predictions
from tests_m5 import test_m5_games as TG

KEY = "I56b"
OUT = ROOT / "results" / "M5" / "corpus"
I51 = ROOT / "results" / "eval" / "holon" / "corpus.json"


def key() -> dict:
    return predictions(KEY)


def truth() -> dict:
    return load_json(ROOT / "spec" / "M5" / "truth" / "corpus.json")["entries"]


def reference_mapping() -> dict:
    excl = set(load_json(ROOT / "spec" / "M5" / "lib" / "truth_protocol.json").get("known_exclusions", {}))
    ent = {e["id"]: e for e in load_json(ROOT / "spec" / "eval" / "corpus.json")["entries"]}
    rows = {}
    for cid, t in sorted(truth().items()):
        v = t["l6"]
        if cid in excl:
            why = "excluded (truth_protocol known_exclusions)"
        elif v not in ("rational", "irrational"):
            why = f"truth {v}: the entry contributes no item"
        elif not I51.is_file():
            why = "I51 has not run: results/eval/holon/corpus.json does not exist, so no finding comes from a run on the pre-fix commit"
        else:
            why = None
        rows[cid] = {"l6": v, "fix_commit": ent[cid]["fix_commit"], "pre_fix": ent[cid]["fix_commit"] + "^",
                     "findings": [], "reason": why}
    return rows


def holon(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=ROOT, capture_output=True, text=True,
                          timeout=3600)


class TestCorpus(unittest.TestCase):
    def test_pins(self):  # Q1
        for p, h in sorted(key()["thresholds"]["pins"].items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)

    def test_mapping(self):  # Q2
        got = load_json(OUT / "mapping.json")
        self.assertEqual(got["entries"], reference_mapping())

    def test_score(self):  # Q3
        items = {f: r["l6"] for r in reference_mapping().values() for f in r["findings"]}
        inp = TG.TestL6().inputs()
        inp["corpus_truth"] = items
        inp["corpus_expect"] = {}
        want = G.l6_v9(inp, load_json(ROOT / "results" / "M5" / "games" / "v9.json"))
        self.assertEqual(load_json(OUT / "l6_corpus.json"), want)
        if not items:
            self.assertEqual(want["thresholds"]["corpus_decided_accuracy"], "not_measured")

    def test_check(self):  # Q4
        r = holon("games", "corpus", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestRegressions(unittest.TestCase):
    def test_r1_i56_unchanged(self):
        r = holon("games", "run", "--check")
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
        base = key()["thresholds"]["base_commit"]
        own = git("rev-list", "--first-parent", "--no-merges", f"{base}..HEAD").decode().split()
        changed = set()
        for c in own:
            changed |= set(git("show", "--name-only", "--format=", c).decode().split())
        hit = sorted(f for f in changed if f.startswith(("results/M5/games/", "gen/M5/games/", "laws/M5/games/")))
        self.assertEqual(hit, [])

    def test_r2_truth_pinned(self):
        self.assertEqual(file_sha256(ROOT / "spec/M5/truth/corpus.json"),
                         key()["thresholds"]["pins"]["spec/M5/truth/corpus.json"])
        r = holon("audit", "prereg", "--milestone", "M5")
        self.assertIn("PREREG OK", r.stdout)

    def test_r3_truth_counts(self):
        self.assertEqual(dict(collections.Counter(t["l6"] for t in truth().values())),
                         {"irrational": 1, "undocumented": 19})


if __name__ == "__main__":
    unittest.main()
