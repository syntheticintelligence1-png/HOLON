"""Audit M2/1 F-M2-02, F-M2-10 (and the gate sides of F-M2-07, F-M2-19): the gate on a holon-ir/0.3 milestone.

A toy 0.3 milestone T7 over the toy queue (laws/T7 in a throwaway copy): L3_and_true (PROVED), L3_and_false
(REFUTED, a conjunction's counter-law), L3_exists_false (an ∃-law, UNKNOWN) and its frozen negation
L3_exists_false_neg (holon.ir.negation_law, PROVED), registered with holon.gen.refs.law_hash. `holon run`, `holon
bind` and `holon metrics` write its outputs; `holon gate --checks` runs every check but G6 (a toy has no replay).

Before the fix: G2 hashed 0.3 laws without refs (hash mismatch), G1 compared 0 records (glob L_*.json), G9 required
^L_ ids, G4 took the header-canary path (error 'Header'), and a milestone without REGISTRY.json crashed the gate.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._ir03_fx import cleanup, copy_repo, fixture, holon, holon_module, load_json, write_json, write_milestone

CHECKS = "G2,G1,G3,G5,G11,G11V,G9,GREF,G7,G4"


def toy_laws(ir) -> list[dict]:
    ex = fixture("L3_exists_false")
    ex["negation"] = "L3_exists_false_neg"
    return [fixture("L3_and_true"), fixture("L3_and_false"), ex, ir.negation_law(ex)]


class TestToyIR03Gate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ir = holon_module("holon.ir")
        cls.repo = copy_repo()
        write_milestone(cls.repo, "T7", toy_laws(ir))
        cls.log = ""
        for args in (["run", "--milestone", "T7"], ["bind", "--milestone", "T7"], ["metrics", "--milestone", "T7"],
                     ["gate", "--milestone", "T7", "--checks", CHECKS, "--report", str(cls.repo / "gate_T7.json")]):
            p = holon(cls.repo, *args)
            cls.log += f"$ holon {' '.join(args)} -> {p.returncode}\n{p.stdout[-3000:]}{p.stderr[-3000:]}\n"
        rp = cls.repo / "gate_T7.json"
        cls.rep = load_json(rp) if rp.exists() else None

    @classmethod
    def tearDownClass(cls):
        cleanup(cls.repo)

    def check(self, g: str) -> dict:
        self.assertIsNotNone(self.rep, self.log)
        return self.rep["checks"][g]

    def test_g2_checks_0_3_hashes_with_their_refs(self):
        c = self.check("G2")
        self.assertTrue(c["passed"], c["detail"])
        self.assertIn("holon-ir/0.3", c["detail"])

    def test_g1_regenerates_and_compares_the_l3_records(self):
        c = self.check("G1")
        self.assertTrue(c["passed"], c["detail"])
        self.assertIn("4 records identical", c["detail"])

    def test_g9_accepts_the_0_3_law_id_pattern(self):
        c = self.check("G9")
        self.assertTrue(c["passed"], c["detail"])

    def test_g4_takes_the_state_machine_path(self):
        c = self.check("G4")
        self.assertNotIn("Header", c["detail"])
        self.assertNotRegex(c["detail"], r"^error")

    def test_other_checks_pass(self):
        for g in ("G3", "G5", "G11", "G11V", "GREF", "G7"):
            with self.subTest(check=g):
                c = self.check(g)
                self.assertTrue(c["passed"], c["detail"])

    def test_the_existential_law_links_its_frozen_negation(self):
        rec = load_json(self.repo / "results" / "T7" / "L3_exists_false.json")
        neg = load_json(self.repo / "results" / "T7" / "L3_exists_false_neg.json")
        self.assertEqual(rec["status"], "UNKNOWN")
        self.assertEqual(neg["status"], "PROVED", neg.get("attempts"))
        self.assertEqual(rec["negation"]["law_id"], "L3_exists_false_neg")
        self.assertTrue(rec["negation"]["frozen"])
        self.assertEqual(rec["negation"]["status"], "PROVED")
        self.assertEqual(rec["negation"]["statement_hash"], neg["statement_hash"])

    def test_an_existential_law_without_its_frozen_negation_fails_g2(self):
        G = holon_module("holon.gate")
        repo = copy_repo()
        try:
            src = self.repo / "laws" / "T7"
            shutil.rmtree(repo / "laws" / "T7", ignore_errors=True)
            shutil.copytree(src, repo / "laws" / "T7")
            law = load_json(repo / "laws" / "T7" / "L3_exists_false.json")
            law.pop("negation")
            write_json(repo / "laws" / "T7" / "L3_exists_false.json", law)
            bad = G.Gate("T7", repo).negation_problems()
            self.assertTrue(any("without its frozen negation" in b for b in bad), bad)
            neg = load_json(repo / "laws" / "T7" / "L3_exists_false_neg.json")
            neg["statement"]["claim"] = {"eq": neg["statement"]["claim"]["neq"]}   # not the generated negation
            law["negation"] = "L3_exists_false_neg"
            write_json(repo / "laws" / "T7" / "L3_exists_false.json", law)
            write_json(repo / "laws" / "T7" / "L3_exists_false_neg.json", neg)
            bad = G.Gate("T7", repo).negation_problems()
            self.assertTrue(any("not the generated negation" in b for b in bad), bad)
        finally:
            cleanup(repo)

    def test_a_proof_that_does_not_import_its_law_fails_g5_and_g11(self):
        """F-M2-07 at the gate: Bend accepts the import-less proof (vacuously); G5 and G11 must not."""
        G = holon_module("holon.gate")
        repo = copy_repo()
        try:
            for d in ("laws/T7", "results/T7", "gen/T7", "spec/bindings"):
                shutil.rmtree(repo / d, ignore_errors=True)
                shutil.copytree(self.repo / d, repo / d)
            pf = repo / "gen" / "T7" / "proofs" / "L3_and_true" / "PROOF.bend"
            self.assertRegex(pf.read_text(), r"(?m)^import \S+ as Laws$")
            pf.write_text("import Base\n\ndef helper() -> Nat:\n  0n\n")   # the audit's probe: checks vacuously
            g = G.Gate("T7", repo)
            g.g11()
            self.assertFalse(g.checks["G11"]["passed"])
            self.assertIn("does not import its law", g.checks["G11"]["detail"])
            g.g5()
            self.assertFalse(g.checks["G5"]["passed"])
            self.assertIn("does not import its law", g.checks["G5"]["detail"])
        finally:
            cleanup(repo)


class TestUncheckableMilestone(unittest.TestCase):
    def test_a_milestone_without_a_registry_fails_every_check_clearly(self):
        """F-M2-10: `holon gate --milestone M2` crashed with FileNotFoundError while laws/M2 does not exist."""
        tmp = Path(tempfile.mkdtemp(prefix="holon-gate-noreg-"))
        try:
            p = holon(Path(__file__).resolve().parents[1], "gate", "--milestone", "M9", "--checks", "G2,G1,G9",
                      "--report", str(tmp / "r.json"))
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
            self.assertNotIn("Traceback", p.stderr)
            rep = load_json(tmp / "r.json")
            for g in ("G2", "G1", "G9"):
                with self.subTest(check=g):
                    self.assertFalse(rep["checks"][g]["passed"])
                    self.assertIn("REGISTRY.json does not exist", rep["checks"][g]["detail"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestRecordGlobs(unittest.TestCase):
    def test_every_reader_takes_the_law_ids_load_laws_any_reads(self):
        """F-M2-02: G1, checker-upgrade and metrics read L3_* records as well as L_* (ir.LAW_GLOB)."""
        ir = holon_module("holon.ir")
        CU = holon_module("holon.checker_upgrade")
        MT = holon_module("holon.metrics")
        G = holon_module("holon.gate")
        tmp = Path(tempfile.mkdtemp(prefix="holon-globs-"))
        try:
            res = tmp / "results" / "T9"
            res.mkdir(parents=True)
            (tmp / "gen" / "T9").mkdir(parents=True)
            for lid in ("L_a", "L3_b", "L8_c"):
                (res / f"{lid}.json").write_text(json.dumps({"law_id": lid, "status": "UNKNOWN", "artifacts": {}}))
            (res / "summary.json").write_text("{}")
            want = ["L3_b", "L8_c", "L_a"]
            self.assertEqual([p.stem for p in ir.record_files(res)], want)
            self.assertEqual(sorted(CU.norm_records(tmp, "T9")), want)
            self.assertEqual(sorted(MT.records("T9", res)), want)
            g = G.Gate.__new__(G.Gate)
            g.root = tmp
            self.assertEqual(sorted(G.Gate.norm_records(g, res, tmp / "gen" / "T9")), want)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
