"""Audit M2/1 F-M2-01: statement.scope is enforced, and recorded separately from the status (whitepaper §8.6).

bounded{H} bounds every Trace binder to at most H actions: the emitter states len(p) <= H as a premise (a claim
conjunct for an existential binder), so the kernel checks the horizon, and the explorer never proposes a longer
witness. at_state{ref} is Unsupported until a generator resolves the referenced state. A 0.3 record's scope,
statement_scope and scope_v2 come from statement.scope, never from the status; the search bound of an UNKNOWN law
stays in `bound`.

Before the fix a bounded law true within its horizon (L3_small_bounded, H = 2) was REFUTED with a 3-action witness
and its record said scope 'unbounded'.
"""
import unittest

from tests_m2._ir03_fx import cleanup, copy_repo, fixture, holon, holon_module, load_json, write_milestone

IDS = ["L3_small_bounded", "L3_small_bounded_false", "L3_at_state", "L3_exists_false", "L3_bounded_vacuous"]


class TestScopeRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        write_milestone(cls.repo, "T1", [fixture(i) for i in IDS])
        cls.proc = holon(cls.repo, "run", "--milestone", "T1")
        cls.recs = {i: load_json(cls.repo / "results" / "T1" / f"{i}.json") for i in IDS
                    if (cls.repo / "results" / "T1" / f"{i}.json").exists()}

    @classmethod
    def tearDownClass(cls):
        cleanup(cls.repo)

    def rec(self, lid: str) -> dict:
        self.assertIn(lid, self.recs, self.proc.stdout[-2000:] + self.proc.stderr[-2000:])
        return self.recs[lid]

    def test_a_bounded_law_true_within_its_horizon_is_never_refuted(self):
        r = self.rec("L3_small_bounded")
        self.assertNotEqual(r["status"], "REFUTED", r.get("witness"))
        self.assertEqual(r["scope"], "bounded")
        self.assertEqual(r["statement_scope"], {"kind": "bounded", "H": 2})
        self.assertEqual(r["scope_v2"]["kind"], "bounded")
        self.assertIn("at most 2 actions", r["scope_v2"]["horizon"])

    def test_a_bounded_law_false_within_its_horizon_is_refuted_by_a_short_witness(self):
        r = self.rec("L3_small_bounded_false")
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        self.assertLessEqual(len(r["witness"]["p"]), 3)
        laws = (self.repo / r["artifacts"]["laws"]).read_text()
        self.assertIn("Nat.is_le(List.length(&2, M.HAct, p), 3n)", laws, "the counter-law states the horizon")

    def test_scope_is_recorded_separately_from_status(self):
        unknown_unbounded = self.rec("L3_exists_false")
        self.assertEqual(unknown_unbounded["status"], "UNKNOWN")
        self.assertEqual(unknown_unbounded["scope"], "unbounded")
        self.assertEqual(unknown_unbounded["scope_v2"]["kind"], "unbounded")
        self.assertTrue(unknown_unbounded["bound"], "the search bound stays in `bound`")
        refuted_bounded = self.rec("L3_small_bounded_false")
        self.assertEqual(refuted_bounded["scope"], "bounded")

    def test_at_state_is_unsupported_until_its_state_is_resolved(self):
        r = self.rec("L3_at_state")
        self.assertEqual(r["status"], "UNKNOWN")
        self.assertTrue(any("at_state" in str(a.get("error", "")) for a in r["attempts"]), r["attempts"])
        self.assertEqual(r["scope"], "bounded")
        self.assertEqual(r["statement_scope"], {"kind": "at_state", "ref": "s0"})

    def test_a_law_vacuous_within_its_horizon_is_never_inhabited(self):
        """Its premise holds only after 3 pushes; the inhabitant ∃p. len(p) <= 2 ∧ premise has no witness."""
        r = self.rec("L3_bounded_vacuous")
        self.assertEqual(r["status"], "PROVED", r.get("attempts"))
        self.assertNotEqual(r["non_vacuity"]["status"], "inhabited", r["non_vacuity"])
        self.assertIsNone(r["non_vacuity"]["witness"])

    def test_records_validate_against_the_v2_schema(self):
        from tests_m2._m2 import ROOT, validate
        for lid in IDS:
            with self.subTest(law=lid):
                self.assertEqual(validate(self.rec(lid), ROOT / "spec" / "schemas" / "result_record_v2.schema.json"), [])


class TestScopeUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests_m2._m2 import ROOT
        cls.mp = holon_module("holon.mpipeline")
        cls.mlaws = holon_module("holon.gen.mlaws")
        cls.cm = cls.mp.CompiledMachine.build(ROOT / "tests_m2/fixtures/toy_queue/toy_queue.facts.json")

    def test_the_emitter_states_the_horizon_for_every_trace_binder(self):
        law = fixture("L3_small_bounded")
        law["statement"]["binders"].append({"q": "forall", "name": "q", "type": "Trace"})
        em = self.mlaws.Emitter(self.cm.m).emit(law, "../model/m.bend")
        bounds = [a for a, b, t in em.assume if a.startswith("Nat.is_le(List.length(")]
        self.assertEqual(len(bounds), 2, em.text)
        cl = self.mlaws.Emitter(self.cm.m).emit(law, "../model/m.bend", counter=True)
        self.assertIn("exs h0: {Nat.is_le(List.length(&2, M.HAct, p), 2n)", cl.text)

    def test_bounded_scope_without_a_trace_binder_is_unsupported(self):
        law = fixture("L3_and_true")
        law["statement"]["scope"] = {"kind": "bounded", "H": 1}
        with self.assertRaises(self.mlaws.Unsupported):
            self.mlaws.Emitter(self.cm.m).emit(law, "../model/m.bend")

    def test_the_inhabitant_states_the_horizon_too(self):
        """G11V's inhabitant (∃ binders. premises) keeps the law's scope, so its emitted law bounds the trace."""
        inh = holon_module("holon.inhabit").inhabitant_ir(fixture("L3_bounded_vacuous"))
        self.assertEqual(inh["statement"]["scope"], {"kind": "bounded", "H": 2})
        em = self.mlaws.Emitter(self.cm.m).emit(inh, "../model/m.bend")
        self.assertTrue(any(a.startswith("Nat.is_le(List.length(") for a, _, _ in em.claims), em.text)

    def test_the_explorer_never_proposes_a_witness_beyond_the_horizon(self):
        s = self.cm.explore(fixture("L3_small_bounded"))
        self.assertIsNone(s["witness"], s)
        self.assertIn("at most 2 actions", s["bound"])
        s = self.cm.explore(fixture("L3_small_bounded_false"))
        self.assertIsNotNone(s["witness"])
        self.assertLessEqual(len(s["witness"]["p"]), 3)


if __name__ == "__main__":
    unittest.main()
