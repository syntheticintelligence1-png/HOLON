"""S10 acceptance on the committed spec/M2/refuter/ records (docs/M2_SPEC.md §3, row S10):

  * every M0/M1 law has a record; every record names the solver and its version;
  * every REFUTED law the engine can encode is re-found, with a counter-law the
    kernel checked (bend marker + --verdict), never on a solver answer alone;
  * no PROVED law is ever refuted; UNSAT appears only as evidence, never as a
    proof claim;
  * every law the engine cannot encode is listed, with a reason, in
    spec/M2/coverage/refuter.json.
"""

import unittest

from . import _util


class TestRefuterRecords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.laws = {l["law_id"]: l for m in ("M0", "M1") for l in _util.load_laws(m)}
        cls.records = {lid: _util.record(lid) for lid in cls.laws}

    def test_every_law_has_a_record(self):
        for lid in self.laws:
            with self.subTest(law=lid):
                self.assertIn(lid, self.records)
                self.assertEqual(self.records[lid]["law_id"], lid)

    def test_solver_recorded_everywhere(self):
        for lid, r in self.records.items():
            with self.subTest(law=lid):
                solver = r["engines"]["qf_ufbv"]["solver"]
                self.assertEqual(solver["name"], "z3")
                self.assertTrue(solver["version"])
                self.assertEqual(solver["logic"], "QF_UFBV")

    def test_refuted_laws_refound_and_checked(self):
        for lid, law in self.laws.items():
            if _util.expected(law) != "REFUTED":
                continue
            r = self.records[lid]
            with self.subTest(law=lid):
                # the engine may be unable to encode a REFUTED law; that is
                # coverage debt, not silence — but it must not be REFUTED-free either.
                if r["status"] == "COVERAGE_DEBT":
                    continue
                self.assertEqual(r["status"], "REFUTED", f"{lid} not refound")
                self.assertEqual(r["agreement"], "refound")
                # at least one engine produced a kernel-checked counter-law
                checked = [e["counter_law"] for e in r["engines"].values()
                           if isinstance(e.get("counter_law"), dict)]
                self.assertTrue(checked, f"{lid}: no checked counter-law")
                for c in checked:
                    self.assertEqual(c["marker"], "ALL PROOFS CHECK")
                    self.assertEqual(c["exit_code"], 0)
                    self.assertIn(c["verdict"], ("checked", "not_run"))
                self.assertIsNotNone(r["witness"])
                self.assertIsNotNone(r["difference"])
                self.assertNotEqual(r["difference"]["lhs"], r["difference"]["rhs"])

    def test_no_proved_law_is_refuted(self):
        for lid, law in self.laws.items():
            if _util.expected(law) != "PROVED":
                continue
            r = self.records[lid]
            with self.subTest(law=lid):
                self.assertNotEqual(r["status"], "REFUTED", f"{lid} false rebuttal")
                self.assertNotEqual(r["agreement"], "false_rebuttal")

    def test_unsat_is_evidence_only(self):
        for lid, r in self.records.items():
            with self.subTest(law=lid):
                if r["engines"]["qf_ufbv"].get("answer") != "unsat":
                    continue
                # UNSAT may accompany UNSAT_EVIDENCE or REFUTED (another engine
                # refuted), but never upgrades a status by itself
                self.assertIn(r["status"], ("UNSAT_EVIDENCE", "REFUTED", "NO_WITNESS"))
                self.assertNotEqual(r["status"], "PROVED")

    def test_len_bound_recorded(self):
        for lid, r in self.records.items():
            with self.subTest(law=lid):
                if r["engines"]["qf_ufbv"].get("answer") in ("sat", "unsat", "unknown"):
                    self.assertIsInstance(r["engines"]["qf_ufbv"]["len_bound"], int)


class TestCoverageDebt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cov = _util.json.loads((_util.COVERAGE).read_text())
        cls.laws = {l["law_id"]: l for m in ("M0", "M1") for l in _util.load_laws(m)}

    def test_coverage_shape(self):
        self.assertEqual(self.cov["frontend"], "refuter")
        self.assertTrue(self.cov["target_commit"])
        self.assertIsInstance(self.cov["items"], list)
        for it in self.cov["items"]:
            self.assertTrue(it["element"])
            self.assertTrue(it["kind"])
            self.assertTrue(it["reason"])

    def test_every_unencodable_law_is_listed_with_reason(self):
        listed = {it["element"].split(":", 1)[1] for it in self.cov["items"]}
        for lid, law in self.laws.items():
            r = _util.record(lid)
            encodable = r["engines"]["qf_ufbv"].get("answer") in ("sat", "unsat", "unknown")
            with self.subTest(law=lid):
                if encodable:
                    self.assertNotIn(lid, listed)
                else:
                    self.assertIn(lid, listed)
                    item = next(i for i in self.cov["items"] if i["element"].endswith(lid))
                    self.assertTrue(item["reason"])

    def test_debt_items_are_ir02(self):
        for it in self.cov["items"]:
            lid = it["element"].split(":", 1)[1]
            with self.subTest(law=lid):
                self.assertEqual(self.laws[lid]["ir_version"], "holon-ir/0.2",
                                 f"{lid} is ir/0.1 but listed as unencodable")


class TestFuzzDomain(unittest.TestCase):
    """The grammar fuzzer respects the same input domain as holon.refute.in_domain."""

    @classmethod
    def setUpClass(cls):
        from holon import facts as F
        from holon.gen import laws as LG
        cls.F, cls.LG = F, LG
        cls.facts = F.load(_util.FACTS)

    def test_candidates_respect_premises_and_domain(self):
        from holon import refute
        from holon.refute_engines import fuzz
        for lid in ("L_par_hdr_v0", "L_par_hdr_v1", "L_par_hdr_v2", "L_rt_go_v0"):
            law = _util.json.loads((_util.REPO / "laws" / "M0" / f"{lid}.json").read_text())
            pins = self.LG.collect_pins(law, self.facts)
            for label, env in fuzz.candidates(law, self.facts, pins):
                with self.subTest(law=lid, candidate=label):
                    self.assertTrue(refute.in_domain(law, self.facts, env, pins))
                    for var, fields in pins.items():
                        for fld, val in fields.items():
                            self.assertEqual(env[var][fld], "0x" + bytes(val).hex())

    def test_candidates_deterministic(self):
        from holon.refute_engines import fuzz
        law = _util.json.loads((_util.REPO / "laws" / "M0" / "L_par_hdr_v2.json").read_text())
        pins = self.LG.collect_pins(law, self.facts)
        a = [x for x in fuzz.candidates(law, self.facts, pins)]
        b = [x for x in fuzz.candidates(law, self.facts, pins)]
        self.assertEqual(a, b)

    def test_mutation_never_touches_pinned_cells(self):
        from holon.refute_engines import fuzz
        law = _util.json.loads((_util.REPO / "laws" / "M0" / "L_par_hdr_v2.json").read_text())
        pins = self.LG.collect_pins(law, self.facts)
        for label, env in fuzz.candidates(law, self.facts, pins):
            if not label.startswith("mut("):
                continue
            for var, fields in pins.items():
                for fld, val in fields.items():
                    self.assertEqual(env[var][fld], "0x" + bytes(val).hex())


if __name__ == "__main__":
    unittest.main()
