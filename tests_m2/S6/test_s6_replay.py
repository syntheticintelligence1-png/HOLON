"""S6: the committed report.json shows every fixture commit agreeing with the
compiled model (HOLON_REPLAY=1 — like tests_m1's replay test)."""
import os
import unittest

from tests._util import ROOT, load_json


@unittest.skipUnless(os.environ.get("HOLON_REPLAY") == "1",
                     "set HOLON_REPLAY=1 after `python -m holon.hist.replay`")
class TestS6Replay(unittest.TestCase):
    def test_report(self):
        rep = load_json(ROOT / "replay" / "M2" / "report.json")
        self.assertEqual(rep["unit"], "S6")
        self.assertGreaterEqual(rep["summary"]["n_commits"], 1)
        for idx, v in rep["summary"]["commit_verdicts"].items():
            with self.subTest(batch_index=idx):
                self.assertIn(v, ("agree", "coverage_debt"), v)
        for d in rep["disagreements"]:
            self.assertIn(d["verdict"],
                          ("extraction_defect", "real_defect",
                           "oracle_mismatch", "coverage_debt"))
        # the transition edge must have run on every commit; the blob check
        # is `bvh_stored_vs_contract` for every version, plus the model-side
        # atom-vs-concrete comparison only on legacy-versioned commits
        # (v2's batchBlobVersionedHash is a symbolic atom in the model)
        for r in rep["commits"]:
            names = {c["check"] for c in r["checks"]}
            self.assertIn("outcome", names, r["batch_index"])
            self.assertIn("parent_batch_hash", names, r["batch_index"])
            self.assertIn("bvh_stored_vs_contract", names,
                          r["batch_index"])
            self.assertIn("post.bvh", names, r["batch_index"])
        self.assertIn("n_unexplained", rep["summary"])
        self.assertEqual(rep["summary"]["n_unexplained"], 0)


if __name__ == "__main__":
    unittest.main()
