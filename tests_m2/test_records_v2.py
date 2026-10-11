"""I1: v2 result records carry one field per §8.6 item, validate against v1 and v2, and change no outcome."""
import hashlib
import unittest

from tests_m2._m2 import MILESTONES, ROOT, SCHEMAS2, item, load_json, model_file, records, validate

V1 = ROOT / "schemas" / "result_record.schema.json"
V2 = SCHEMAS2 / "result_record_v2.schema.json"

# whitepaper §8.6: the orthogonal fields of a result record -> the record field that carries each
SECTION_8_6 = {
    "status (proved, refuted, split, unknown)": "status",
    "law hash": "statement_hash",
    "model hash": "model_sha256",
    "premises": "premises",
    "scope (bounded with horizon H, or unbounded)": "scope_v2",
    "kernel or kernels": "kernels",
    "independence class": "independence_class",
    "refinement records of the edges used": "refinement_refs",
    "witness replay status": "replay",
    "coverage": "coverage",
}


class TestRecordsV2(unittest.TestCase):
    def test_schema_covers_8_6(self):
        sch = load_json(V2)
        for what, field in SECTION_8_6.items():
            with self.subTest(item=what):
                self.assertIn(field, sch["required"])
                self.assertIn(field, sch["properties"])
        for f in ("model_assumptions", "cone", "generator_sha256", "non_vacuity", "witness_provenance", "filter_bin"):
            self.assertIn(f, sch["required"])

    def test_every_record_validates_v1_and_v2(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    self.assertEqual(validate(rec, V1), [])
                    self.assertEqual(validate(rec, V2), [])

    def test_model_sha_matches_generated_model(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    self.assertEqual(rec["model_sha256"], hashlib.sha256(model_file(rec).read_bytes()).hexdigest())

    def test_kernels_and_independence_are_honest(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    ks = {k["role"]: k for k in rec["kernels"]}
                    self.assertEqual(ks["primary"]["name"], "bend2")
                    if rec["status"] == "UNKNOWN":
                        self.assertEqual(rec["independence_class"], "none")
                        continue
                    self.assertEqual(ks["primary"]["result"], "checked")
                    second = ks.get("second")
                    if rec["kernel"]["verdict"] == "checked":
                        self.assertEqual(second["name"], "bendtt")
                        self.assertEqual(second["result"], "checked")
                        self.assertEqual(second["shares_frontend_with"], "bend2")
                        self.assertEqual(rec["independence_class"], "I1-shared",
                                         "BendTT re-checks bend2's elaboration: not an independent kernel")
                    else:
                        self.assertEqual(rec["independence_class"], "I1")

    def test_scope_v2(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    sc = rec["scope_v2"]
                    if rec["status"] == "UNKNOWN":
                        self.assertEqual(sc["kind"], "bounded")
                        self.assertEqual(sc["horizon"], rec["bound"])
                    else:
                        self.assertEqual(sc["kind"], "unbounded")
                        self.assertIsNone(sc["horizon"])
                    self.assertIn(sc["at_state"], ("s0", "any", None))

    def test_pending_fields_name_their_iteration(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    self.assertEqual(rec["refinement_refs"], "pending:I16")
                    self.assertEqual(rec["coverage"], "pending:I19")

    def test_statuses_unchanged(self):
        want = item("I1", "I1-R1")["expected"]
        for m in MILESTONES:
            with self.subTest(milestone=m):
                self.assertEqual(load_json(ROOT / "results" / m / "summary.json"), want[m])
                self.assertEqual({lid: r["status"] for lid, r in records(m).items()}, want[m])

    def test_statement_hashes_unchanged(self):
        for m in MILESTONES:
            reg = load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"]
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    self.assertEqual(rec["statement_hash"], reg[lid])


if __name__ == "__main__":
    unittest.main()
