"""Audit M2/1 F-M2-31: stronger I7 fixtures than L3_cf (which proves P => P) and the I7-P2/P3 checks.

  L3_and_false_second  a false conjunction failing at conjunct 1: failing_conjunct is 1, not 0
  L3_exists_false      its run-time negation is exactly holon.ir.negation_law's statement (rendered and hashed)
  L3_cf_model          CF through the parametric model (the commit step applies agg at two points): PROVED, and its
                       premise inhabited by the oracle sidecar's concrete instance of agg, not the explorer's identity
  L3_cf_model_nocf     the same claim without the CF premise: REFUTED, so the CF law's proof depends on its premise
"""
import unittest

from tests_m2._ir03_fx import cleanup, copy_repo, fixture, holon, holon_module, load_json, write_milestone

IDS = ["L3_and_false_second", "L3_exists_false", "L3_cf_model", "L3_cf_model_nocf"]


class TestStrongerFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        cls.laws = write_milestone(cls.repo, "T1", [fixture(i) for i in IDS])
        cls.proc = holon(cls.repo, "run", "--milestone", "T1")
        cls.recs = {i: load_json(cls.repo / "results" / "T1" / f"{i}.json") for i in IDS
                    if (cls.repo / "results" / "T1" / f"{i}.json").exists()}

    @classmethod
    def tearDownClass(cls):
        cleanup(cls.repo)

    def rec(self, lid: str) -> dict:
        self.assertIn(lid, self.recs, self.proc.stdout[-2000:] + self.proc.stderr[-2000:])
        return self.recs[lid]

    def test_the_counter_law_names_the_second_conjunct(self):
        r = self.rec("L3_and_false_second")
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        self.assertEqual(r["failing_conjunct"], 1)

    def test_the_negation_decided_is_the_generated_one(self):
        ir = holon_module("holon.ir")
        R = holon_module("holon.gen.refs")
        r = self.rec("L3_exists_false")
        want = ir.negation_law(self.laws["L3_exists_false"])
        self.assertEqual(r["negation"]["statement"], ir.render_statement(want))
        self.assertEqual(r["negation"]["statement_hash"],
                         R.law_hash(want, load_json(self.repo / want["facts"]), root=self.repo))
        self.assertEqual(r["negation"]["status"], "PROVED")
        self.assertFalse(r["negation"]["frozen"], "no frozen negation in this milestone: decided at run time, labelled")

    def test_cf_through_the_model_is_proved_and_inhabited_by_the_concrete_instance(self):
        r = self.rec("L3_cf_model")
        self.assertEqual(r["status"], "PROVED", r.get("attempts"))
        nv = r["non_vacuity"]
        self.assertEqual(nv["status"], "inhabited", nv)
        self.assertIn("instance", nv["witness"]["agg"], nv["witness"])

    def test_without_its_cf_premise_the_claim_is_refuted(self):
        r = self.rec("L3_cf_model_nocf")
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))


if __name__ == "__main__":
    unittest.main()
