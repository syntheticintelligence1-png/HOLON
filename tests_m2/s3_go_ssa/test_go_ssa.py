"""S3 differ tests: extracted go facts vs the hand-written targets.

The extractor (holon/frontends/go) never reads hand facts; only
holon.frontends.go.differ does, as the comparison target (M2_SPEC §2).
Every difference must be recovered or recorded as coverage debt.
"""
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTRACTED = REPO / "spec" / "M2" / "extracted"
COVERAGE = REPO / "spec" / "M2" / "coverage" / "go.json"

from holon.frontends.go import differ  # noqa: E402


class ExtractedFilesExist(unittest.TestCase):
    def test_outputs(self):
        for p in (EXTRACTED / "go_codecs.json",
                  EXTRACTED / "go_batchdata.json", COVERAGE):
            self.assertTrue(p.exists(), p)


class TestCodecsDiffer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = differ.diff_codecs()

    def test_no_unresolved(self):
        bad = self.rep["unresolved"]
        self.assertEqual(bad, [],
                         json.dumps(bad, indent=1)[:4000])

    def test_encoders_reproduced(self):
        by_hand = {i["hand"]: i for i in self.rep["items"]}
        for hid in ("enc_go_v0", "enc_go_v1"):
            self.assertIn(hid, by_hand)
            self.assertEqual(by_hand[hid]["status"], "match",
                             by_hand[hid].get("detail"))

    def test_predicate_rules_exact(self):
        item = next(i for i in self.rep["items"] if i["hand"] == "ok_go")
        self.assertEqual(item["status"], "match", item["detail"])

    def test_decoder_getters_covered(self):
        for i in self.rep["items"]:
            if i["hand"].startswith("dec_go."):
                self.assertEqual(i["status"], "match",
                                 f"{i['hand']}: {i['detail']}")

    def test_view_order(self):
        item = next(i for i in self.rep["items"] if i["hand"] == "view")
        self.assertEqual(item["status"], "match", item["detail"])

    def test_duplicate_package_recovered(self):
        item = next(i for i in self.rep["items"]
                    if "node/types" in str(i["hand"]))
        self.assertEqual(item["status"], "recovered")

    def test_debt_shape(self):
        cov = json.loads(COVERAGE.read_text())
        self.assertEqual(cov["frontend"], "go")
        self.assertRegex(cov["target_commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(cov["items"],
                         sorted(cov["items"], key=lambda x: x["element"]))
        for it in cov["items"]:
            self.assertRegex(it["element"], r".*:\d+ \w+ .+")
            self.assertIn("kind", it)
            self.assertIn("reason", it)


class TestBatchDataDiffer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = differ.diff_batchdata()

    def test_no_unresolved(self):
        bad = self.rep["unresolved"]
        self.assertEqual(bad, [],
                         json.dumps(bad, indent=1)[:4000])

    def test_cone_and_actions(self):
        names = {i["hand"] for i in self.rep["items"]}
        self.assertIn("state cone", names)
        self.assertIn("action.append", names)
        self.assertIn("action.txsPayloadV2", names)
        for i in self.rep["items"]:
            self.assertEqual(i["status"], "match",
                             f"{i['hand']}: {i['detail']}")


class TestExtractsNeverReadHandFacts(unittest.TestCase):
    def test_no_hand_fact_reads(self):
        root = REPO / "holon" / "frontends" / "go"
        for py in root.glob("*.py"):
            if py.name == "differ.py":
                continue
            src = py.read_text()
            for pat in ("facts/morph_header", "morph_batchdata",
                        "spec/M1/facts", "reference"):
                self.assertNotIn(pat, src, f"{py.name} reads {pat}")


class TestDeterminism(unittest.TestCase):
    def test_rerun_identical(self):
        import subprocess, sys
        files = [EXTRACTED / "go_codecs.json",
                 EXTRACTED / "go_batchdata.json", COVERAGE]
        before = [p.read_bytes() for p in files]
        subprocess.run([sys.executable, "-m", "holon.frontends.go",
                        "extract"], cwd=REPO, check=True,
                       capture_output=True)
        for p, b in zip(files, before):
            self.assertEqual(b, p.read_bytes(), f"{p} not deterministic")


if __name__ == "__main__":
    unittest.main()
