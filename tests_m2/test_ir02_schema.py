"""I1: the holon-ir/0.2 statements have a schema, written from the emitter's grammar."""
import copy
import unittest

from tests_m2._m2 import SCHEMAS2, laws, validate

S = SCHEMAS2 / "law_ir_0_2.schema.json"


class TestIR02Schema(unittest.TestCase):
    def test_all_m1_laws_validate(self):
        ls = laws("M1")
        self.assertEqual(len(ls), 16)
        for lid, law in ls.items():
            with self.subTest(law=lid):
                self.assertEqual(validate(law, S), [])

    def test_unknown_term_is_rejected(self):
        law = copy.deepcopy(laws("M1")["L_undo_CSR"])
        law["statement"]["claim"]["eq"][0] = {"teleport": {"var": "s1"}}
        self.assertNotEqual(validate(law, S), [])

    def test_unknown_binder_type_is_rejected(self):
        law = copy.deepcopy(laws("M1")["L_undo_CSR"])
        law["statement"]["binders"][0]["type"] = "Oracle"
        self.assertNotEqual(validate(law, S), [])

    def test_wrong_ir_version_is_rejected(self):
        law = copy.deepcopy(laws("M1")["L_undo_CSR"])
        law["ir_version"] = "holon-ir/0.1"
        self.assertNotEqual(validate(law, S), [])


if __name__ == "__main__":
    unittest.main()
