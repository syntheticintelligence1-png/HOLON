"""S9(1): result-record v2 schema and the v1 -> v2 converter.

The converter reads the frozen-format v1 records and produces v2 records; it
never rewrites them. Every converted M1 record must validate against
spec/M2/schemas/result_v2.json.
"""

import copy
import unittest
from pathlib import Path

from holon import ir, records_v2
from holon.replay import witness_sha256

from tests_m2.s9._util import REPO, m1_law, m1_record


class TestResultV2Schema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = records_v2.load_schema(REPO)
        cls.converted = records_v2.convert_milestone("M1", REPO)

    def test_all_records_convert_and_validate(self):
        self.assertGreater(len(self.converted), 0)
        for lid, rec in self.converted.items():
            problems = records_v2.validate(rec, self.schema)
            self.assertEqual(problems, [], f"{lid}: {problems}")

    def test_superset_fields(self):
        for lid, v2 in self.converted.items():
            v1 = m1_record(lid)
            for k in ("law_id", "statement_hash", "facts_sha256", "status", "scope",
                      "premises", "artifacts", "checker", "triage", "replay"):
                self.assertIn(k, v2, f"{lid} missing v1 field {k}")
            self.assertEqual(v2["law_id"], v1["law_id"])
            self.assertEqual(v2["status"], v1["status"])
            self.assertEqual(v2["record_version"], 2)

    def test_new_fields(self):
        rec = self.converted["L_undo_CSR"]
        self.assertEqual(rec["independence_class"], "I2")
        names = [k["name"] for k in rec["kernels"]]
        self.assertEqual(names, ["bend2", "bendtt"])
        bend2 = rec["kernels"][0]
        self.assertEqual(bend2["version"], rec["kernel"]["version"])
        self.assertEqual(bend2["result"], "ALL PROOFS CHECK")
        self.assertEqual(rec["kernels"][1]["result"], "checked")
        # the witness hash is bound to the record's witness
        self.assertEqual(rec["witness_sha256"], witness_sha256(rec["witness"]))
        # coverage debt comes from the law's facts file
        self.assertTrue(rec["coverage_debt"])
        self.assertTrue(all(d["source"] == "spec/M1/facts/morph_rollup.json"
                            for d in rec["coverage_debt"]))
        # a REFUTED record carries the replay evidence pointer bound to its witness
        ref = self.converted["L_nat_eta2"]
        self.assertEqual(ref["status"], "REFUTED")
        ev = ref["replay"]["evidence"]
        self.assertEqual(ev["report"], "replay/M1/report.json")
        self.assertEqual(ev["entry"], "laws.L_nat_eta2")
        self.assertEqual(ev["witness_sha256"], ref["witness_sha256"])
        # a PROVED record's replay evidence is null (certificates are not replayed)
        self.assertIsNone(rec["replay"]["evidence"])

    def test_does_not_rewrite_v1(self):
        v1 = m1_record("L_undo_CSR")
        self.assertNotIn("record_version", v1)
        self.assertNotIn("kernels", v1)
        # the on-disk file is untouched: converting twice gives the same bytes
        v1_text = (REPO / "results" / "M1" / "L_undo_CSR.json").read_text()
        records_v2.convert_milestone("M1", REPO)
        self.assertEqual((REPO / "results" / "M1" / "L_undo_CSR.json").read_text(), v1_text)

    def test_proved_record_has_null_witness_sha(self):
        rec = self.converted["L_undo_CSR"]
        self.assertEqual(rec["status"], "PROVED")
        self.assertIsNone(rec["witness_sha256"])

    # ------------------------------------------------------- negative tests
    def test_missing_required_key_fails(self):
        rec = copy.deepcopy(self.converted["L_undo_CSR"])
        del rec["statement_hash"]
        problems = records_v2.validate(rec, self.schema)
        self.assertTrue(any("statement_hash" in p for p in problems))

    def test_malformed_hashes_fail(self):
        # the schema checks the hash format; the *value* consistency is G9's job
        for lid in ("L_undo_CSR", "L_nat_eta2"):
            rec = copy.deepcopy(self.converted[lid])
            rec["facts_sha256"] = "not-a-sha"
            self.assertTrue(records_v2.validate(rec, self.schema), f"{lid}")
        rec = copy.deepcopy(self.converted["L_nat_eta2"])
        rec["witness_sha256"] = "0" * 63  # too short
        self.assertTrue(records_v2.validate(rec, self.schema))

    def test_refuted_without_witness_fails(self):
        rec = copy.deepcopy(self.converted["L_nat_eta2"])
        self.assertEqual(rec["status"], "REFUTED")
        del rec["witness"]
        problems = records_v2.validate(rec, self.schema)
        self.assertTrue(any("witness" in p for p in problems))

    def test_v1_record_does_not_validate_as_v2(self):
        v1 = m1_record("L_undo_CSR")
        problems = records_v2.validate(v1, self.schema)
        self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
