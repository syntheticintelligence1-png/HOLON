"""A2 {"reason": msg} resolution.

Reason codes are numbered per facts file: a law names a revert by message and
ir.resolve_reasons maps it to the code in the facts file the law runs on
(hand-written code 12 "incorrect batch index" is code 7 in the S1-extracted
facts). resolve_reasons is a pre-pass in mpipeline.run_m1: emit/explore see a
resolved statement; the record's statement_hash/premises come from the
original law; a missing reason is UNKNOWN (emitter-Unsupported shape), never a
crash.
"""
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from holon import facts, ir, mpipeline
from holon.gen import mlaws

REPO = Path(__file__).resolve().parents[2]
HAND = json.loads((REPO / "spec/M1/facts/morph_rollup.json").read_text())
EXTRACTED = json.loads((REPO / "spec/M2/extracted/morph_rollup.json").read_text())


def _rev_statement(msg):
    return {"binders": [], "assume": [],
            "claim": {"eq": [{"fn": "no_code",
                              "args": [{"obs": {"trace": [{"act": "wait", "args": {"dt": {"nat": 1}}}]},
                                        "from": {"run": {"trace": []}, "from": {"s0": {}}}},
                                       {"reason": msg}]},
                             {"bool": False}]}}


class TestResolveReasons(unittest.TestCase):
    def test_hand_code(self):
        st = ir.resolve_reasons(_rev_statement("incorrect batch index"), HAND)
        self.assertEqual(st["claim"]["eq"][0]["args"][1], {"nat": 12})

    def test_extracted_code(self):
        st = ir.resolve_reasons(_rev_statement("incorrect batch index"), EXTRACTED)
        self.assertEqual(st["claim"]["eq"][0]["args"][1], {"nat": 7})

    def test_missing_raises_unsupported(self):
        with self.assertRaises(mlaws.Unsupported):
            ir.resolve_reasons(_rev_statement("no such revert message"), HAND)

    def test_original_untouched(self):
        st = _rev_statement("incorrect batch index")
        ir.resolve_reasons(st, HAND)
        self.assertEqual(st["claim"]["eq"][0]["args"][1], {"reason": "incorrect batch index"})


class TestPipeline(unittest.TestCase):
    def _law(self, msg):
        return {"ir_version": "holon-ir/0.2", "law_id": "L_a2_t_rev",
                "milestone": "A2", "rule": "GUARD", "subform": "scenario",
                "facts": "spec/M1/facts/morph_rollup.json",
                "facts_sha256": "0" * 64, "statement": _rev_statement(msg),
                "predicted": "PROVED"}

    def test_hash_stable_across_resolution(self):
        """Resolution is a copy, not a mutation: the law's statement hash (the
        recorded identity) is identical before and after resolving."""
        law = self._law("incorrect batch index")
        before = ir.statement_hash(law)
        resolved = ir.resolve_law_reasons(law, HAND)
        self.assertEqual(ir.statement_hash(law), before)
        self.assertNotEqual(ir.statement_hash(resolved), before)

    def test_missing_reason_is_unknown_record(self):
        """A law naming a reason absent from its facts file is UNKNOWN (emitter
        Unsupported shape), not a crash."""
        law = self._law("no such revert message")
        reg = {"facts": "spec/M1/facts/morph_rollup.json",
               "facts_files": {"spec/M1/facts/morph_rollup.json": "0" * 64},
               "facts_sha256": "0" * 64, "milestone": "A2",
               "statements": {"L_a2_t_rev": ir.statement_hash(law)}}
        with tempfile.TemporaryDirectory() as td, \
                unittest.mock.patch.object(ir, "load_laws_any", return_value=[law]), \
                unittest.mock.patch.object(ir, "load_registry", return_value=reg):
            td = Path(td)
            summary = mpipeline.run_m1("A2", None, str(td / "out"), str(td / "gen"),
                                     no_registry=True, log=lambda *a: None)
            self.assertEqual(summary, {"L_a2_t_rev": "UNKNOWN"})
            rec = json.loads((td / "out" / "L_a2_t_rev.json").read_text())
            self.assertEqual(rec["status"], "UNKNOWN")
            self.assertEqual(rec["attempts"],
                             [{"kind": "emit",
                               "error": "unsupported statement form: reason not in facts: no such revert message"}])


if __name__ == "__main__":
    unittest.main()
