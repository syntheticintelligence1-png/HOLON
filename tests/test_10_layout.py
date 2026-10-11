"""P1: holon.layout computes the same symbolic byte layouts as the oracle."""
import json
import unittest

from tests._util import FACTS, ROOT, load_json
from tests.reference import ref_model as M
from tests.reference import ref_mutate as X

CASES = [("enc_sol", 0), ("enc_sol", 1), ("enc_sol", 2), ("enc_go_v0", 0), ("enc_go_v1", 1)]


class TestLayout(unittest.TestCase):
    def test_layouts_match_oracle(self):
        from holon import layout as L
        facts = M.load_facts(FACTS)
        for fn, v in CASES:
            with self.subTest(fn=fn, version=v):
                got = json.loads(json.dumps(L.layout(facts, fn, v)))
                self.assertEqual(got, M.layout(facts, fn, v))

    def test_layouts_follow_mutated_facts(self):
        from holon import layout as L
        base = M.load_facts(FACTS)
        for m in load_json(ROOT / "predictions" / "M0_mutations.json")["mutations"]:
            facts = X.apply(base, m["edit"])
            for fn, v in CASES:
                with self.subTest(mutation=m["id"], fn=fn, version=v):
                    got = json.loads(json.dumps(L.layout(facts, fn, v)))
                    self.assertEqual(got, M.layout(facts, fn, v))

    def test_overlapping_writes_last_wins(self):
        from holon import layout as L
        facts = {"types": {"Header": {"fields": [{"name": "x", "width": 1}, {"name": "y", "width": 2}]}},
                 "functions": {"t": {"kind": "encoder", "lang": "solidity-evm-memory", "memory_init": "dirty",
                                     "domain": {"version_le": 9}, "length_by_version": {"0": 36},
                                     "ops": [{"op": "mstore", "offset": 0, "src": [{"field": "y"}, {"zeros": 30}]},
                                             {"op": "mstore8", "offset": 1, "src": [{"field": "x"}]},
                                             {"op": "mstore", "offset": 2, "src": [{"zeros": 32}]}]}}}
        got = json.loads(json.dumps(L.layout(facts, "t", 0)))
        self.assertEqual(got, M.layout(facts, "t", 0))
        self.assertEqual(got[:3], [["field", "y", 0], ["field", "x", 0], ["const", 0]])
        self.assertEqual(len(got), 36)
        self.assertEqual(got[33:], [["const", 0], ["unknown"], ["unknown"]])


if __name__ == "__main__":
    unittest.main()
