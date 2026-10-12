"""I7: law IR 0.3 (whitepaper §8.9, §8.5, §8.6, §9.4, Thm 6.17, Cor 6.16; BUILD_PLAN I7).

IR 0.3 adds function types (Fn<A,B>) for hashes and oracles, collision-freedom premises
{"cf": {"fn": h, "set": [terms]}} over finite sets, a scope separate from status, counter-laws for
conjunctions (naming the failing conjunct), and the rule that an existential law is never REFUTED: it
stays UNKNOWN with a bounded negative search and its generated negation (for all, not P) is decided
instead. The 0.3 statement hash covers {ir_version, law_id, rule, rule_catalog_version, statement,
refs}, where refs maps each model definition the statement names to the content hash of its source.

Fixtures (tests_m2/fixtures/ir03/) run on the toy queue machine through `holon run`.
"""
import hashlib
import json
import shutil
import unittest
from pathlib import Path

from tests_m2._m2 import MILESTONES, ROOT, copy_repo, holon_module, laws, load_json, run_holon, validate, write_json

FIX = ROOT / "tests_m2" / "fixtures" / "ir03"
TOY_FACTS = "tests_m2/fixtures/toy_queue/toy_queue.facts.json"
SCHEMA = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
RUN_IDS = ["L3_and_false", "L3_and_true", "L3_exists_false", "L3_cf"]


def run_fixtures(ids: list[str]) -> tuple[dict, str]:
    repo = copy_repo()
    try:
        sha = hashlib.sha256((repo / TOY_FACTS).read_bytes()).hexdigest()
        d = repo / "laws" / "T1"
        d.mkdir(parents=True)
        for lid in ids:
            law = load_json(FIX / f"{lid}.json")
            law["facts_sha256"] = sha
            write_json(d / f"{lid}.json", law)
        write_json(d / "REGISTRY.json", {"milestone": "T1", "facts": TOY_FACTS, "facts_sha256": sha,
                                         "facts_files": {TOY_FACTS: sha}, "statements": {i: None for i in ids}})
        out = repo / "t1_results"
        p = run_holon(["run", "--milestone", "T1", "--no-registry", "--out", str(out), "--gen-dir", str(repo / "t1_gen")],
                      cwd=repo)
        recs = {lid: load_json(out / f"{lid}.json") for lid in ids if (out / f"{lid}.json").exists()}
        return recs, p.stdout[-2000:] + p.stderr[-2000:]
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)


class TestSchemaAndHash(unittest.TestCase):
    def test_fixtures_validate_against_the_0_3_schema(self):
        for p in sorted(FIX.glob("L3_*.json")):
            with self.subTest(law=p.stem):
                self.assertEqual(validate(load_json(p), SCHEMA), [])

    def test_existing_hashes_recompute_equal(self):
        """I7-R1: introducing 0.3 changes none of the 24 frozen 0.1/0.2 statement hashes."""
        ir = holon_module("holon.ir")
        for m in MILESTONES:
            reg = load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"]
            for lid, law in laws(m).items():
                with self.subTest(law=lid):
                    self.assertEqual(ir.statement_hash(law), reg[lid])

    def test_0_3_hash_covers_refs_not_whole_bundles(self):
        ir = holon_module("holon.ir")
        law = load_json(FIX / "L3_cf.json")
        refs = {"eq_nat": "sha256:" + "1" * 64}
        h1 = ir.statement_hash(law, refs=refs)
        self.assertNotEqual(h1, ir.statement_hash(law, refs={"eq_nat": "sha256:" + "2" * 64}))
        self.assertEqual(h1, ir.statement_hash(dict(law, notes="edited notes"), refs=refs))
        self.assertNotEqual(h1, ir.statement_hash(dict(law, rule_catalog_version="holon-rules/0.2"), refs=refs))


class TestFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recs, cls.log = run_fixtures(RUN_IDS)

    def rec(self, lid: str) -> dict:
        self.assertIn(lid, self.recs, self.log)
        return self.recs[lid]

    def test_false_conjunction_is_refuted_naming_the_failing_conjunct(self):
        """I7-P2."""
        r = self.rec("L3_and_false")
        self.assertEqual(r["status"], "REFUTED", r.get("attempts"))
        self.assertEqual(r["failing_conjunct"], 0)

    def test_true_conjunction_is_never_refuted(self):
        """I7-P2."""
        self.assertNotEqual(self.rec("L3_and_true")["status"], "REFUTED")

    def test_false_existential_is_unknown_with_its_negation_proved(self):
        """I7-P3."""
        r = self.rec("L3_exists_false")
        self.assertEqual(r["status"], "UNKNOWN", r.get("attempts"))
        bn = r["bounded_negative"]
        self.assertTrue(bn["H"])
        self.assertGreater(bn["space"], 0)
        self.assertEqual(r["negation"]["status"], "PROVED", r["negation"])
        self.assertTrue(r["negation"]["law_id"].startswith("L3_exists_false"))

    def test_cf_law_proved_and_its_premise_inhabited(self):
        """I7-P5."""
        r = self.rec("L3_cf")
        self.assertEqual(r["status"], "PROVED", r.get("attempts"))
        self.assertEqual(r["non_vacuity"]["status"], "inhabited", r["non_vacuity"])


class TestGlobalInjectivity(unittest.TestCase):
    def test_global_injectivity_premise_is_rejected(self):
        """I7-P4 (G3, whitepaper L13): no premise may state injectivity over all values."""
        ir = holon_module("holon.ir")
        with self.assertRaises(ir.IRError):
            ir.check_premises(load_json(FIX / "L3_global_injectivity.json"))
        ir.check_premises(load_json(FIX / "L3_cf.json"))


class TestFnProbe(unittest.TestCase):
    def test_fn_and_cf_probe_checks_under_both_kernels(self):
        """I7-P1: a Fn binder with pairwise CF premises checks under bend and BendTT --verdict."""
        from tests._util import run_bend
        proof = ROOT / "bend" / "notes" / "p_ir03_fn_verdict" / "PROOF.bend"
        code, out = run_bend([str(proof)])
        self.assertEqual(code, 0, out[-800:])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])
        code, out = run_bend([str(proof), "--verdict"])
        self.assertEqual(code, 0, out[-800:])
        self.assertIn("ALL PROOFS CHECK", out)


if __name__ == "__main__":
    unittest.main()
