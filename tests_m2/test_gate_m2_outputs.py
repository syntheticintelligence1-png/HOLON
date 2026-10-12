"""Audit M2/1 F-M2-25: G1 for M2+ milestones regenerates gen/<m>/diagram (holon diagram), gen/<m>/sorts (holon sorts)
and gen/<m>/oracles with results/<m>/hypotheses.json (holon oracle check), each by its own generator, and compares
them byte for byte (holon.gate.regenerate_m2_outputs); `holon run`'s own comparison skips those directories.

laws/M2 does not exist yet, so `holon gate --milestone M2` cannot run G1; the comparison function is tested
directly on the committed tree, on a tampered copy, and on a milestone without inputs.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module


class TestM2Outputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.G = holon_module("holon.gate")
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-m2out-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_committed_m2_outputs_regenerate_byte_identical(self):
        diffs, note = self.G.regenerate_m2_outputs("M2", ROOT, self.tmp / "a")
        self.assertEqual(diffs, [])
        for part in ("diagram", "sorts", "oracles"):
            self.assertIn(part, note)

    def test_an_edited_output_is_named(self):
        repo = copy_repo()
        try:
            d = sorted((repo / "gen" / "M2" / "diagram").glob("*.json"))[0]
            d.write_text(d.read_text() + " ")
            s = repo / "gen" / "M2" / "sorts" / "unions.json"
            s.write_text(json.dumps(json.loads(s.read_text()), indent=1))
            h = repo / "results" / "M2" / "hypotheses.json"
            hyp = json.loads(h.read_text())
            next(iter(hyp.values()))["detail"] = "edited"
            h.write_text(json.dumps(hyp, indent=2, sort_keys=True) + "\n")
            o = sorted((repo / "gen" / "M2" / "oracles").rglob("*.bend"))[0]
            o.write_text(o.read_text() + "\n# edited\n")
            diffs, _ = self.G.regenerate_m2_outputs("M2", repo, self.tmp / "b")
            for want in (f"gen/M2/diagram/{d.name}", "gen/M2/sorts/unions.json", "results/M2/hypotheses.json",
                         f"gen/M2/oracles/{o.relative_to(repo / 'gen' / 'M2' / 'oracles').as_posix()}"):
                self.assertIn(want, diffs)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_a_milestone_without_inputs_has_nothing_to_regenerate(self):
        diffs, note = self.G.regenerate_m2_outputs("T7", ROOT, self.tmp / "c")
        self.assertEqual(diffs, [])
        self.assertIn("not applicable", note)

    def test_g1_skips_them_in_the_run_comparison_only_for_m2_plus(self):
        self.assertEqual(set(self.G.M2_OUTPUTS), {"diagram", "sorts", "oracles"})


if __name__ == "__main__":
    unittest.main()
