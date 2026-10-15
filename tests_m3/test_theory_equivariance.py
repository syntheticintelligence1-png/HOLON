"""I43 theory preregistration. Outcome tests intentionally fail before the build."""
from __future__ import annotations

import tempfile
import unittest
import re

from tests_m3._m3 import ROOT, load_json, predictions, run_bend
from tests_m3._i43 import (census, assert_lean_source, canonical_lean_statement_hash,
                           canonical_bend_statement_hash)


class TestI43EquivariancePreregContract(unittest.TestCase):
    def test_contract(self):
        pred = predictions("I43")
        self.assertEqual(pred["prompt"], "prompts/I43_promotion.md")
        self.assertEqual(
            pred["outcome_paths"],
            ["gen/core/I43/", "gen/M3/I43/", "results/M3/I43/",
             "holon/gen/equivariance.py", "holon/lean_promoted.py", "holon/result_views.py",
             "docs/iterations/I43.md", "README.md"],
        )
        self.assertEqual(len(pred["predictions"]), 5)
        prompt = (ROOT / pred["prompt"]).read_text()
        for phrase in ("Q8", "I42", "I29", "I34", "non-equivariant", "naturality",
                       "subgroup", "submonoid", "summary.json"):
            self.assertIn(phrase, prompt)
        data = census()
        self.assertEqual(data["base_commit"], "153bb5eb6e32d30182e6b6781d2c36b2157be9da")
        self.assertEqual(data["kernels"]["bend_budget_seconds"], 60.0)
        self.assertEqual(data["kernels"]["lean_budget_seconds"], 120.0)
        self.assertEqual(data["kernels"]["external_imports"], [])
        self.assertEqual(set(data["kernels"]["allowed_axioms"]), {"propext", "Quot.sound"})
        self.assertTrue({"sorry", "admit", "axiom", "unsafe", "partial",
                         "implemented_by", "extern", "native_decide"} <= set(data["kernels"]["forbidden"]))
        core = data["theory_core_ii"]
        self.assertIn("Stab(T_a)", core["base_statement_note"])
        self.assertEqual([x["id"] for x in core["certificates"]],
                         ["thm_6_6_equivariance", "thm_6_7_naturality_pasting"])
        self.assertTrue(all("structural induction" in x["proof_method"] for x in core["certificates"]))
        self.assertTrue(all(x["bend_budget_seconds"] == 60.0 and x["lean_budget_seconds"] == 120.0
                            for x in core["certificates"]))
        self.assertEqual({x["id"]: x["expected"] for x in core["controls"]["negative"]},
                         {"ctrl_non_equivariant_edge": "REFUTED",
                          "ctrl_broken_naturality_square": "REFUTED"})
        self.assertIn("not on this base", core["controls"]["downstream"])
        self.assertIn("none is fabricated", data["core_certificate_inclusion"]["before_i42_merge"].lower())


class TestI43TheoryCoreIIOutcomes(unittest.TestCase):
    def _check_certificate(self, cert):
        from holon.bend import strip_comments as strip_bend
        from holon.lean import strip_comments as strip_lean, check_text
        paths = {k: ROOT / v for k, v in cert["artifacts"].items()}
        for path in paths.values():
            self.assertTrue(path.is_file(), str(path))
        laws = strip_bend(paths["bend_laws"].read_text(encoding="utf-8"))
        proof = strip_bend(paths["bend_proof"].read_text(encoding="utf-8"))
        lean = strip_lean(paths["lean"].read_text(encoding="utf-8"))
        self.assertRegex(proof, r"(?m)^\s*from\s+\./LAWS\.bend\s+import\s+\S+")
        self.assertRegex(proof, r"\bmatch\s+\+?w\b")
        self.assertRegex(proof, r"case\s+(?:\w+\.)?(?:Walk/)?Nil\b")
        self.assertRegex(proof, r"case\s+(?:\w+\.)?(?:Walk/)?Cons\b")
        self.assertIn("Walk", laws)
        for law_id in cert["required_laws"]:
            with self.subTest(law_id=law_id):
                self.assertRegex(laws, r"(?m)^\s*law\s+" + re.escape(law_id) + r"\s*:")
                self.assertRegex(proof, r"(?m)^\s*def\s+Laws\." + re.escape(law_id) + r"\s*\(")
                self.assertRegex(lean, r"(?m)^\s*theorem\s+" + re.escape(law_id) + r"\b")
                assert_lean_source(self, paths["lean"], law_id)
        code, output = run_bend([str(paths["bend_proof"]), "--verdict"], cwd=paths["bend_proof"].parent,
                                timeout=65)
        self.assertEqual(code, 0, output)
        self.assertIn("ALL PROOFS CHECK", output)
        record = load_json(paths["record"])
        self.assertEqual(record["status"], "PROVED")
        self.assertEqual(record["kernels"]["bend2"], "checked")
        self.assertEqual(record["kernels"]["lean4"], "checked")
        self.assertEqual(record["statement_hash"],
                         {law_id: canonical_bend_statement_hash(laws, law_id)
                          for law_id in cert["required_laws"]})
        self.assertEqual(record["lean_statement_hash"],
                         {law_id: canonical_lean_statement_hash(lean, law_id)
                          for law_id in cert["required_laws"]})
        self.assertEqual(record["induction"]["scrutinee"], "Walk")
        self.assertIn("nil", record["induction"]["cases"])
        self.assertIn("cons", record["induction"]["cases"])
        with tempfile.TemporaryDirectory() as tmp:
            checked = check_text(paths["lean"].read_text(encoding="utf-8"), tmp,
                                 expect=cert["required_laws"], timeout=120)
        self.assertEqual(checked["result"], "checked", checked["out"][-2000:])
        self.assertLessEqual(checked["seconds"], 120)
        self.assertLessEqual(set(checked["axioms"]), {"propext", "Quot.sound"})

    def test_thm_6_6_equivariance_and_stab_closure(self):
        self.assertTrue((ROOT / "holon/gen/equivariance.py").is_file())
        import ast
        module = ast.parse((ROOT / "holon/gen/equivariance.py").read_text())
        source = (ROOT / "holon/gen/equivariance.py").read_text()
        self.assertIn("Walk", source)
        self.assertIn("induction", source.lower())
        self.assertNotIn("tests.reference", source)
        self.assertNotIn("I29", source)
        self.assertNotIn("I34", source)
        self.assertTrue(module.body)
        self._check_certificate(census()["theory_core_ii"]["certificates"][0])

    def test_thm_6_7_naturality_and_pasting(self):
        self._check_certificate(census()["theory_core_ii"]["certificates"][1])

    def test_positive_and_negative_controls(self):
        self.assertTrue((ROOT / "holon/gen/equivariance.py").is_file())
        from holon.bend import strip_comments as strip_bend
        from holon.lean import check_text
        from holon.gen.equivariance import evaluate_control_witness
        path = ROOT / census()["theory_core_ii"]["controls"]["record"]
        self.assertTrue(path.is_file(), str(path))
        controls = load_json(path)
        for entry in census()["theory_core_ii"]["controls"]["positive"]:
            paths = {k: ROOT / v for k, v in entry["artifacts"].items()}
            self.assertTrue(all(p.is_file() for p in paths.values()), entry["kind"])
            self.assertRegex(strip_bend(paths["bend_laws"].read_text()),
                             r"(?m)^\s*law\s+" + re.escape(entry["law_id"]) + r"\s*:")
            code, output = run_bend([str(paths["bend_proof"]), "--verdict"],
                                    cwd=paths["bend_proof"].parent, timeout=65)
            self.assertEqual(code, 0, output)
            self.assertIn("ALL PROOFS CHECK", output)
            with tempfile.TemporaryDirectory() as tmp:
                checked = check_text(paths["lean"].read_text(), tmp,
                                     expect=[entry["law_id"]], timeout=120)
            self.assertEqual(checked["result"], "checked", checked["out"][-2000:])
            self.assertTrue(controls["positive"][entry["kind"]]["checked"])
        for entry in census()["theory_core_ii"]["controls"]["negative"]:
            control = controls["negative"][entry["id"]]
            self.assertEqual(control["status"], "REFUTED")
            self.assertEqual(set(control["witness"]), set(entry["witness_keys"]))
            lhs, rhs = evaluate_control_witness(entry["kind"], control["witness"])
            self.assertNotEqual(lhs, rhs)
            self.assertEqual(control["difference"], {"lhs": lhs, "rhs": rhs})
            self.assertEqual(control["bend2"], "checked")
            laws, proof = (ROOT / entry["artifacts"]["bend_laws"],
                           ROOT / entry["artifacts"]["bend_proof"])
            self.assertEqual(control["counter_law"], entry["artifacts"]["bend_laws"])
            self.assertEqual(control["counter_proof"], entry["artifacts"]["bend_proof"])
            law_src = strip_bend(laws.read_text())
            self.assertRegex(law_src, r"(?m)^\s*law\s+cl_" + re.escape(entry["id"]) + r"\s*:")
            self.assertIn(re.sub(r"\s+", "", entry["counter_claim"]),
                          re.sub(r"\s+", "", law_src))
            for value in control["witness"].values():
                self.assertIn(str(value), law_src)
            self.assertRegex(strip_bend(proof.read_text()),
                             r"(?m)^\s*def\s+Laws\.cl_" + re.escape(entry["id"]) + r"\s*\(")
            code, output = run_bend([str(proof)], cwd=proof.parent, timeout=65)
            self.assertEqual(code, 0, output)
            self.assertIn("ALL PROOFS CHECK", output)
        self.assertFalse(controls["negative"]["ctrl_non_equivariant_edge"]["certificate_emitted"])


if __name__ == "__main__":
    unittest.main()
