"""P1: holon.ir hashes laws exactly like the oracle and the frozen registry."""
import copy
import unittest

from tests._util import LAWS_DIR, law_ids, load_json, load_law
from tests.reference import ref_ir as I


class TestIR(unittest.TestCase):
    def test_canonical_json(self):
        from holon import ir
        obj = {"b": [1, {"z": "é", "a": None}], "a": True}
        self.assertEqual(ir.canonical_json(obj), I.canonical_json(obj))

    def test_statement_hashes_match_registry(self):
        from holon import ir
        reg = load_json(LAWS_DIR / "REGISTRY.json")["statements"]
        for lid in law_ids():
            self.assertEqual(ir.statement_hash(load_law(lid)), reg[lid], lid)

    def test_hash_ignores_metadata_but_not_statement(self):
        from holon import ir
        law = load_law("L_par_hdr_v1")
        h0 = ir.statement_hash(law)
        meta = copy.deepcopy(law)
        meta["notes"] = "changed"
        meta["evidence"] = ["E6"]
        self.assertEqual(ir.statement_hash(meta), h0)
        weak = copy.deepcopy(law)
        weak["statement"]["assume"].append(weak["statement"]["assume"][0])
        self.assertNotEqual(ir.statement_hash(weak), h0)
        other = copy.deepcopy(law)
        other["statement"]["claim"]["eq"][1]["call"] = "enc_go_v0"
        self.assertNotEqual(ir.statement_hash(other), h0)

    def test_load_laws(self):
        from holon import ir
        laws = ir.load_laws("M0")
        self.assertEqual(sorted(l["law_id"] for l in laws), law_ids())


if __name__ == "__main__":
    unittest.main()
