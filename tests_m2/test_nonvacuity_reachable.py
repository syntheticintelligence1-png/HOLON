"""Audit M2/1 F-M2-13 (closes M1/1 F-M1-05): G11V recomputes reachability from the inhabitant's witness.

holon.inhabit.unreachable is None only when every State and Reach binder of the witness is a run from s0
({"run": [..]}) and every Reach binder's evidence in the inhabitant's proof is its R0 / RStep chain; the record's
`reachable` flag is never trusted. The audit's reproduction: L_disch_stale's inhabitant moved to a constructed
state (an open challenge with no challenge and no batch 7: no trace reaches it), with reachable: true and the
nonvac files regenerated so they match, passed G11V; it must fail.
"""
import json
import shutil
import unittest

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json

LAW = "L_disch_stale"


class TestRecomputed(unittest.TestCase):
    def setUp(self):
        self.I = holon_module("holon.inhabit")
        self.law = load_json(ROOT / "laws" / "M1" / f"{LAW}.json")
        self.w = load_json(ROOT / "results" / "M1" / f"{LAW}.json")["non_vacuity"]["witness"]

    def test_recorded_witness_is_reachable(self):
        self.assertIsNone(self.I.unreachable(self.law, self.w, ""))

    def test_constructed_state_is_not(self):
        init = load_json(ROOT / "spec" / "M1" / "facts" / "morph_rollup.json")["initial"]
        w = {**self.w, "s": {"state": {**init, "t": 50, "inch": True, "bc": 7}}}
        self.assertIn("not runs from s0", self.I.unreachable(self.law, w, ""))
        self.assertIn("not runs from s0", self.I.unreachable(self.law, {"a": self.w["a"]}, ""))

    def test_reach_binder_needs_its_chain(self):
        law = load_json(ROOT / "tests_m2" / "fixtures" / "reach" / "L8_reach_y.json")
        w = {"s": {"run": [{"op": "tick", "d": 1}]}}
        self.assertIn("R0 / RStep chain", self.I.unreachable(law, w, "def Laws.nv(): (M.s0(), {==})"))
        self.assertIsNone(self.I.unreachable(law, w, "(M.run([M.A_tick{1n}], M.s0()), M.RStep{M.A_tick{1n}, M.s0(), M.R0{{==}}, {==}})"))
        self.assertIn("not runs from s0", self.I.unreachable(law, {"s": {"state": {"x": 0}}}, ""))


class TestGateRejectsUnreachableInhabitant(unittest.TestCase):
    def test_g11v_rejects_a_constructed_state_with_a_true_flag(self):
        repo = copy_repo()
        try:
            I = holon_module("holon.inhabit")
            G = holon_module("holon.gate")
            rp = repo / "results" / "M1" / f"{LAW}.json"
            rec = json.loads(rp.read_text())
            init = load_json(repo / "spec" / "M1" / "facts" / "morph_rollup.json")["initial"]
            nv = rec["non_vacuity"]
            nv["witness"] = {**nv["witness"], "s": {"state": {**init, "t": 50, "inch": True, "bc": 7}}}
            nv["reachable"] = True
            law = load_json(repo / "laws" / "M1" / f"{LAW}.json")
            name, laws_text, proof = I.expected_texts(law, "M1", repo, rec)   # the files match the tampered witness
            d = repo / "gen" / "M1" / LAW / "nonvac"
            (d / "LAWS.bend").write_text(laws_text)
            (d / "PROOF.bend").write_text(proof)
            rp.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
            ok, detail = I.g11v(G.Gate("M1", repo))
            self.assertFalse(ok, detail)
            self.assertIn(f"{LAW}: inhabitant states ['s'] are not runs from s0", detail)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_g11v_passes_on_the_committed_m1_records(self):
        I = holon_module("holon.inhabit")
        G = holon_module("holon.gate")
        ok, detail = I.g11v(G.Gate("M1", ROOT))
        self.assertTrue(ok, detail)


if __name__ == "__main__":
    unittest.main()
