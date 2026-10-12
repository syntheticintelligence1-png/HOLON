"""I10: A3, the cross-commit regression audit (whitepaper §9.5 A3; BUILD_PLAN I10; debt D-a).

`python -m holon audit regress --from A --to B --json` reads history with `git show` only (no checkout,
no writes). It reports every statement-hash change between A and B, and for every law the commits that
first added its law file, its result record and its prediction entry. It is an audit tool, not a gate check.

JSON: {"from", "to",
       "hash_changes": [{"milestone", "law_id", "old", "new"}],
       "laws": {"<M>/<law_id>": {"law_commit", "result_commit", "prediction_commit", "flag"}}}
flag: "result_same_commit_prediction_later_or_together" when the result was added in the law's own commit
and the prediction entry in that commit or later; "prediction_first" when the prediction came strictly
before the result; "no_prediction" when no prediction entry names the law.
Commits are given as 7-character prefixes.
"""
import json
import unittest

from tests_m2._m2 import laws, run_holon


class TestRegress(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = run_holon(["audit", "regress", "--from", "8a1dbe7", "--to", "HEAD", "--json"], timeout=600)
        cls.rep = json.loads(cls.proc.stdout) if cls.proc.returncode == 0 else None

    def setUp(self):
        self.assertIsNotNone(self.rep, self.proc.stdout[-1500:] + self.proc.stderr[-1500:])

    def test_no_hash_changes_since_the_seed(self):
        """I10-R1."""
        self.assertEqual(self.rep["hash_changes"], [])

    def test_fifteen_m1_laws_added_with_their_results(self):
        """I10-R2."""
        rows = [r for k, r in self.rep["laws"].items() if k.startswith("M1/") and r["law_commit"] == "9a96037"]
        self.assertEqual(len(rows), 15)
        self.assertTrue(all(r["result_commit"] == "9a96037" for r in rows))

    def test_own_txspayload_added_with_result_and_prediction(self):
        """I10-R3."""
        r = self.rep["laws"]["M1/L_own_txspayload"]
        self.assertEqual((r["law_commit"], r["result_commit"], r["prediction_commit"]), ("3e9cb2a", "3e9cb2a", "3e9cb2a"))

    def test_m1_predictions_file_introduced_later(self):
        """I10-R4: spec/M1/predictions.json appears at bfdb5f2."""
        for lid in laws("M1"):
            if lid != "L_own_txspayload":
                with self.subTest(law=lid):
                    self.assertEqual(self.rep["laws"][f"M1/{lid}"]["prediction_commit"], "bfdb5f2")

    def test_all_sixteen_m1_laws_flagged(self):
        """I10-R5: A3 cannot single out the 2 laws labelled post hoc; it flags all 16."""
        m1 = {k: r for k, r in self.rep["laws"].items() if k.startswith("M1/")}
        self.assertEqual(len(m1), 16)
        for k, r in m1.items():
            with self.subTest(law=k):
                self.assertEqual(r["flag"], "result_same_commit_prediction_later_or_together")


if __name__ == "__main__":
    unittest.main()
