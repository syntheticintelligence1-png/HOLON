"""P5: refutation witnesses replay on the REAL Morph code (skipped unless HOLON_REPLAY=1).

Model-only obstructions are hypotheses. A witness becomes a finding when the real
implementation shows the same behaviour on the same input.
"""
import os
import unittest

from tests._util import ROOT, load_json

REQUIRED = {
    # law_id: {side: required status}
    "L_par_hdr_v2": {"go": "passed"},
    "L_dom_hdr": {"go": "passed", "solidity": "passed"},
}


@unittest.skipUnless(os.environ.get("HOLON_REPLAY") == "1", "set HOLON_REPLAY=1 after P5")
class TestReplay(unittest.TestCase):
    def test_replay_report(self):
        rep = load_json(ROOT / "replay" / "M0" / "report.json")
        self.assertEqual(rep["morph_commit"][:7], "3e44e79")
        for lid, sides in REQUIRED.items():
            for side, status in sides.items():
                with self.subTest(law=lid, side=side):
                    e = rep["laws"][lid][side]
                    self.assertEqual(e["status"], status, e)
                    self.assertTrue(e.get("command"), "record the exact command that was run")
                    self.assertTrue(e.get("observed"), "record what the real code did on the witness")
        for lid, sides in rep["laws"].items():
            for side, e in sides.items():
                self.assertIn(e["status"], ("passed", "failed", "not_applicable", "not_run"), (lid, side))


if __name__ == "__main__":
    unittest.main()
