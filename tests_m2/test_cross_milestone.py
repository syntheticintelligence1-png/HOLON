"""I10: cross-milestone weakening (whitepaper §9.5 A3, L22; BUILD_PLAN I10).

A later milestone that re-derives an analogue of an earlier law under a new id needs a checked
S_new => S_old, or a signed weakening entry. Pairs come from DERIVATION.json back-test links, never
from ids.

API: holon.statement_diff.check_cross_milestone(derivation, laws, entries, root) -> [problem]
  derivation  {"links": [{"old", "old_milestone", "new", "new_milestone", "basis"}]}
  laws        {law_id: IR}
  entries     STATEMENT_DIFF entries (cross_milestone or weakening) that cover the links
"""
import unittest

from tests_m2._m2 import ROOT, holon_module, load_json

FIX = ROOT / "tests_m2" / "fixtures" / "statement_diff"


class TestCrossMilestone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.SD = holon_module("holon.statement_diff")

    def test_link_without_an_implication_proof_is_rejected(self):
        """I10-P4."""
        f = load_json(FIX / "cross_no_proof.json")
        problems = self.SD.check_cross_milestone(f["derivation"], f["laws"], f["entries"], ROOT)
        self.assertTrue(problems)
        self.assertTrue(any("L10_xm_new" in p for p in problems), problems)

    def test_link_with_a_checked_implication_is_accepted(self):
        f = load_json(FIX / "cross_with_implication.json")
        self.assertEqual(self.SD.check_cross_milestone(f["derivation"], f["laws"], f["entries"], ROOT), [])


if __name__ == "__main__":
    unittest.main()
