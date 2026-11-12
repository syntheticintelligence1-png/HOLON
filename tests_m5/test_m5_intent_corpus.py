"""I55b: the intent lane on the corpus, L10's corpus_recall (key I55b, spec/M5/predictions/I55b.json; a follow-up of
I55 once the corpus-truth key I54b committed spec/M5/truth/corpus.json). This docstring is the contract.

The design is thresholds.design of the key, immutable under the prereg audit. Pinned by the key before any corpus
record exists: the truth file's sha256 (I54 common.truth_pinning), the corpus's, the corpus-sources sidecar's, and the
scored entries (truth l10 yes or no, less the protocol's known_exclusions). Instruments pinned in PINNED: the prompt and
spec/M5/lib/intent_corpus_sources.json. I55's instrument (tests_m5/_i55.py) checks the spans.

Rules
  K1 The key pins the truth, the corpus and the sources sidecar at their bytes; its scored list is what the truth gives
     (l10 in yes, no; c13 excluded); an undocumented entry is never scored.
  K2 `python -m holon intent corpus --check` exits 0: results/M5/intent/corpus/atoms.json and compile.json are I55's
     atomizer and compiler run on each scored entry's files at its prefix_commit, read through git in the checkout the
     sidecar names (a missing checkout fails, never skips).
  K3 Every corpus atom's pieces are exact against the file at the entry's prefix_commit.
  K4 The run stage never reads spec/M5/truth/ or the census (audit hook).
  K5 `python -m holon intent corpus-score --check` exits 0: results/M5/intent/corpus/l10_corpus.json's corpus_recall is
     the proportion of scored yes entries with an intent obstruction (a REFUTED law passing W1 and W2), labelled by
     min_n; it pins the truth's sha256.

Predictions (I55b-P1..P3): c17's file yields at least one atom; none of its atoms compiles; corpus_recall is 0 of 1,
insufficient_n. Regressions: I55's outputs do not move.
"""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from tests_m5 import _i54 as I54
from tests_m5 import _i55 as I
from tests_m5._m5 import ROOT, file_sha256, load_json, predictions
from tests_m5.test_m5_intent import audited, holon, mentions

KEY = "I55b"
PINNED = {
    "prompts/I55b_intent_corpus.md": "353cc2479d34055e8ff4c65e7dce4fec35163ac5b0698c8dd80e65e769235bcf",
    "spec/M5/lib/intent_corpus_sources.json": "aada973431046581799ee2d6ffbec4645c4dbbf1580729a7527d561ed905d1ad",
}
OUT = ROOT / "results" / "M5" / "intent" / "corpus"
TRUTH = ROOT / "spec" / "M5" / "truth" / "corpus.json"


def key() -> dict:
    return predictions(KEY)


def scored_from_truth() -> list[str]:
    excl = load_json(ROOT / "spec" / "M5" / "lib" / "truth_protocol.json")["known_exclusions"]
    return sorted(k for k, v in load_json(TRUTH)["entries"].items() if v["l10"] in ("yes", "no") and k not in excl)


class TestPreregistration(unittest.TestCase):
    def test_pins(self):  # K1
        for p, h in sorted(PINNED.items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)
        th = key()["thresholds"]
        self.assertEqual(sorted(th["instruments"]), sorted(PINNED))
        self.assertEqual(th["truth_sha256"], file_sha256(TRUTH))
        self.assertEqual(th["corpus_sha256"], file_sha256(ROOT / "spec" / "eval" / "corpus.json"))
        self.assertEqual(th["scored"], scored_from_truth())


class TestCorpus(unittest.TestCase):
    def test_run_check(self):  # K2
        r = holon("intent", "corpus", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = load_json(OUT / "atoms.json")
        self.assertEqual(sorted(d["entries"]), key()["thresholds"]["scored"])
        c = load_json(OUT / "compile.json")
        self.assertEqual(sorted(e["atom"] for e in c["entries"]),
                         sorted(a["id"] for v in d["entries"].values() for a in v["atoms"]))

    def test_spans(self):  # K3
        src = load_json(ROOT / "spec" / "M5" / "lib" / "intent_corpus_sources.json")
        d = load_json(OUT / "atoms.json")
        for eid, v in sorted(d["entries"].items()):
            for a in v["atoms"]:
                text = subprocess.run(["git", "show", f"{a['commit']}:{a['file']}"], cwd=src[a["repo"]],
                                      capture_output=True, check=True).stdout.decode("utf-8")
                self.assertEqual(I.span_problems(a, text.split("\n")), [], (eid, a["id"]))

    def test_run_is_truth_blind(self):  # K4
        got = audited("intent", "corpus", "--check")
        self.assertEqual(got["code"], 0)
        self.assertEqual(mentions(got["log"], r"spec/M5/truth|l10_census"), [])

    def test_score(self):  # K5
        r = holon("intent", "corpus-score", "--check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = load_json(OUT / "l10_corpus.json")
        self.assertEqual(out["truth_sha256"], key()["thresholds"]["truth_sha256"])
        truth = load_json(TRUTH)["entries"]
        yes = [e for e in key()["thresholds"]["scored"] if truth[e]["l10"] == "yes"]
        hit = [e for e in yes if out["entries"][e]["obstructions"]]
        self.assertEqual(out["corpus_recall"], I54.prop(len(hit), len(yes)))
        self.assertEqual(out["label"], I54.label(len(yes)))


class TestPredictions(unittest.TestCase):
    def test_p1_atoms(self):
        self.assertGreaterEqual(len(load_json(OUT / "atoms.json")["entries"]["c17"]["atoms"]), 1)

    def test_p2_none_compiles(self):
        self.assertEqual([e for e in load_json(OUT / "compile.json")["entries"] if e["outcome"] == "compiled"], [])

    def test_p3_recall(self):
        out = load_json(OUT / "l10_corpus.json")
        self.assertEqual((out["corpus_recall"]["numerator"], out["corpus_recall"]["denominator"]), (0, 1))
        self.assertEqual(out["label"], "insufficient_n")


class TestRegressions(unittest.TestCase):
    def test_i55_outputs(self):
        for p, h in sorted(key()["regressions"][0]["expected"].items()):
            self.assertEqual(file_sha256(ROOT / p), h, p)


if __name__ == "__main__":
    unittest.main()
