"""M1: every REFUTED witness replays on the real Rollup (Foundry), and the refinement corpus agrees (HOLON_REPLAY=1)."""
import os
import unittest

from tests._util import ROOT, load_json
from tests_m1._m1 import predictions


@unittest.skipUnless(os.environ.get("HOLON_REPLAY") == "1", "set HOLON_REPLAY=1 after `holon replay --milestone M1`")
class TestM1Replay(unittest.TestCase):
    def test_report(self):
        rep = load_json(ROOT / "replay" / "M1" / "report.json")
        self.assertTrue(rep["morph_commit"].startswith("3e44e79"))
        self.assertFalse(rep["harness_mismatch"])
        for lid, p in predictions().items():
            if p["status"] != "REFUTED":
                continue
            with self.subTest(law=lid):
                e = rep["laws"][lid]
                self.assertEqual(e["status"], "passed", e.get("observed"))
                self.assertTrue(e["obstruction_reproduced"])
                for t in e["traces"]:
                    self.assertEqual(t["disagree"], [])
        rf = rep["refinement"]
        self.assertGreaterEqual(rf["steps"], 2000)
        self.assertEqual(rf["n_disagreements"], 0, rf["disagreements"][:5])
        self.assertGreaterEqual(len(rf["per_action"]), 10, "every modelled action is exercised")


if __name__ == "__main__":
    unittest.main()
