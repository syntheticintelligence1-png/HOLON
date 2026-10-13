"""Unit tests of the I23 modules (not preregistered; the contract is tests_m2/test_historical_exit.py). They need no
network and no snapshot: a toy state, a toy diagram and scratch roots.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module


class TestStepper(unittest.TestCase):
    def setUp(self):
        self.S = holon_module("holon.historical.stepper")
        self.X = holon_module("holon.extracted_eval")

    def test_a_missing_slot_is_never_read_as_zero(self):
        reads, missing = set(), set()
        st = self.S.SlotState({1: 7}, reads, missing)
        self.assertEqual(st.get(1, 0), 7)
        with self.assertRaises(self.X.Unsupported):
            st.get(2, 0)
        self.assertEqual((reads, missing), ({1, 2}, {2}))

    def test_context_of_a_guarded_check(self):
        Check = holon_module("holon.machine").Check
        c = Check("a#s#0", "a", "u.sol:1", "u.sol:1", "require", None, ["||", ["!", ["storage", "f"]], ["fits", 256, 1]])
        self.assertEqual(self.S.context(c), ["storage", "f"])
        c2 = Check("a#s#1", "a", "u.sol:2", "u.sol:2", "require", None, ["||", ["==", 1, 1], 0])
        self.assertEqual(self.S.context(c2), 1)
        c3 = Check("a#s#2", "a", "u.sol:3", "u.sol:3", "call", None, ["||", ["!", 5], ["callok", "I.f", 1]],
                   section="calls", entry={"cond": ["env", "x"]})
        self.assertEqual(self.S.context(c3), ["env", "x"])

    def test_span_lines_and_keys(self):
        self.assertEqual(self.S.span_lines("a/b.sol:3-5"), ["a/b.sol:3", "a/b.sol:4", "a/b.sol:5"])
        self.assertEqual(self.S.span_lines("model:def"), [])
        k = self.S.call_key("0xAB" + "00" * 19, "0x12345678", "0xCD" + "00" * 19)
        self.assertTrue(k.startswith("0xab" + "00" * 19 + ":"))
        self.assertTrue(k.endswith(":0xcd" + "00" * 19))
        self.assertEqual(self.S.slot_key("0xAB", 1), "0xab:0x" + "0" * 63 + "1")


class TestRpcClassification(unittest.TestCase):
    def test_kinds(self):
        Rpc = holon_module("holon.historical.supplement").Rpc
        self.assertEqual(Rpc._kind("eth_getStorageAt", {"result": "0x01"}), "ok")
        self.assertEqual(Rpc._kind("eth_call", {"error": {"code": 3, "message": "execution reverted"}}), "answer")
        self.assertEqual(Rpc._kind("eth_getStorageAt", {"error": {"code": -32005, "message": "rate limit exceeded"}}),
                         "limit")
        self.assertEqual(Rpc._kind("eth_getStorageAt",
                                   {"error": {"message": "Archive requests require a personal token"}}), "refused")
        self.assertEqual(Rpc._kind("eth_getStorageAt", {"error": {"message": "historical state abc is not available"}}),
                         "refused")
        self.assertEqual(Rpc._kind("eth_getStorageAt", None), "missing")
        self.assertEqual(Rpc._kind("eth_getBlockByNumber", {"result": None}), "missing")


class TestMetricsAndGref(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i23-unit-"))
        (self.tmp / "results" / "M2" / "refinement" / "historical").mkdir(parents=True)
        (self.tmp / "spec" / "M2" / "lib").mkdir(parents=True)
        shutil.copyfile(ROOT / "spec" / "M2" / "lib" / "historical_exit.json",
                        self.tmp / "spec" / "M2" / "lib" / "historical_exit.json")
        (self.tmp / "spec" / "M2" / "disagreements.json").write_text(json.dumps({"disagreements": []}))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rec(self, name, compared, ids):
        r = {"record_version": "holon-refinement/0.1", "kind": "historical", "milestone": "M2", "edge": name,
             "compared": compared, "agree": compared - len(ids), "disagreements": len(ids), "disagreement_ids": ids}
        (self.tmp / "results" / "M2" / "refinement" / "historical" / f"{name}.json").write_text(json.dumps(r))

    def test_historical_sums_and_unexplained(self):
        M = holon_module("holon.metrics")
        self.rec("a", 10, [])
        self.rec("b", 5, ["D-historical.b-0000"])
        h = M.historical("M2", self.tmp, [])
        self.assertEqual((h["compared"], h["disagreements"], h["unexplained"]), (15, 1, 1))
        self.assertEqual(h["windows"]["trans"][0], 26031670)
        R = holon_module("holon.refinement")
        problems = R.check_disagreements(self.tmp)
        self.assertTrue(any("D-historical.b-0000" in p and "historical/b.json" in p for p in problems), problems)

    def test_no_historical_record_no_section(self):
        M = holon_module("holon.metrics")
        self.assertIsNone(M.historical("M2", self.tmp, []))


class TestExitCoverage(unittest.TestCase):
    def test_every_other_edge_has_a_why(self):
        E = holon_module("holon.historical.exit_report")
        tmp = Path(tempfile.mkdtemp(prefix="holon-i23-cov-"))
        try:
            d = tmp / "gen" / "M2" / "diagram"
            d.mkdir(parents=True)
            (d / "toy.json").write_text(json.dumps({"facts": "spec/M1/facts/toy.json", "edges": [
                {"id": "TRANS.go", "kind": "TRANS", "component": "go"},
                {"id": "TRANS.stop", "kind": "TRANS", "component": "stop", "source": "x.sol:1"},
                {"id": "TRANS.tick", "kind": "TRANS", "component": "tick", "env": True, "source": "time"},
                {"id": "CONS.out", "kind": "CONS", "component": "out", "doc": "the payload to L2"},
                {"id": "CODEC.enc", "kind": "CODEC", "model_fn": "enc"},
                {"id": "LOAD.x", "kind": "LOAD"}]}))
            inst = json.loads((ROOT / "spec" / "M2" / "lib" / "historical_exit.json").read_text())
            recs = [{"edge": "go", "facts": "spec/M2/facts/toy.extracted.json", "diagram_edge": "TRANS.go",
                     "compared": 3}]
            cov = E.coverage("M2", tmp, inst, recs)
            self.assertEqual(cov["replayed"], ["spec/M2/facts/toy.extracted.json#TRANS.go"])
            nr = cov["not_replayed"]
            self.assertEqual(sorted(nr), sorted(f"spec/M1/facts/toy.json#{x}" for x in
                                                ("TRANS.go", "TRANS.stop", "TRANS.tick", "CONS.out", "CODEC.enc")))
            self.assertIn("extracted counterpart", nr["spec/M1/facts/toy.json#TRANS.go"])
            self.assertIn("no in-scope transaction", nr["spec/M1/facts/toy.json#TRANS.stop"])
            self.assertIn("environment edge", nr["spec/M1/facts/toy.json#TRANS.tick"])
            self.assertIn("consumer", nr["spec/M1/facts/toy.json#CONS.out"])
            self.assertIn("no historical record", nr["spec/M1/facts/toy.json#CODEC.enc"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestPinnedMask(unittest.TestCase):
    def test_masking_zeroes_ranges_on_both_sides(self):
        P = holon_module("holon.historical.pinned")
        self.assertEqual(P.masked(b"\x01\x02\x03\x04", [[1, 2]]), b"\x01\x00\x00\x04")
        self.assertEqual(P.masked(b"\x01\x02", [[1, 4]]), b"\x01\x00")


if __name__ == "__main__":
    unittest.main()
