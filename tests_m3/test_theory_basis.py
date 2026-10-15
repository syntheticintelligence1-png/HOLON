"""I42 preregistration checks and intentionally RED outcome acceptance tests."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest

from tests._util import run_bend
from holon import lean
from tests_m3 import _i42 as I
from tests_m3._m3 import ROOT, load_json, predictions


class TestI42PreregistrationContract(unittest.TestCase):
    def test_non_comment_guards(self):
        laws = "# law target : True\n/- law target : 0 == 0 -/\nlaw target : {f(x) == g(x) : T}\n"
        proof = "# def Laws.target(): ?TODO\nfrom ./LAWS.bend import target\ndef Laws.target(x):\n  {==}\n"
        I.require_expected_law(laws, proof, "target")
        self.assertEqual(I.statement_hash(laws), hashlib.sha256(
            b"law target : {f(x) == g(x) : T}").hexdigest())
        for bad_law in ("# law target : {==}\n", "law target : True\n",
                        "law target : 0 == 0\n", "law target : Bool.true == Bool.true\n"):
            with self.assertRaises(AssertionError):
                I.require_expected_law(bad_law, proof, "target")
        with self.assertRaises(AssertionError):
            I.require_expected_law(laws, "# def Laws.target(x): {==}", "target")
        with tempfile.TemporaryDirectory() as tmp:
            path = I.Path(tmp) / "probe.bend"
            path.write_text("# Morph\n-- BatchHeader\n/- enc_sol -/\ndef morph_key():\n  0\n")
            self.assertEqual({x.lower() for x in I.morph_identifiers(path)}, {"morph"})

    def test_exact_paths_and_disclosure(self):
        entry = predictions("I42")
        doc = I.instrument()
        prompt = (ROOT / "prompts/I42_basis.md").read_text()
        self.assertEqual(entry["prompt"], "prompts/I42_basis.md")
        self.assertEqual(entry["tests"], ["tests_m3/test_theory_basis.py"])
        self.assertEqual(entry["outcome_paths"], [
            "gen/core/I42/", "results/M3/I42/", "holon/gen/basis.py",
            "holon/gen/lean_basis.py", "docs/iterations/I42.md", "README.md"])
        self.assertEqual(doc["iteration"], "I42")
        self.assertEqual(doc["recovery_disclosure"], entry["recovery_disclosure"])
        disclosure = doc["recovery_disclosure"]
        for phrase in ("24 experimental", "7 exit 0", "17 exit 1",
                       "tc-acf0wtbjr4j", "tc-ewjt1jzxiy5", "tc-ejuzu0ax5wa",
                       "tc-cnuskeubqtg", "tc-hv7szkv2t6u"):
            self.assertIn(phrase, prompt)
        self.assertEqual(disclosure["experimental_checker_invocations"], 24)
        self.assertEqual(disclosure["exit_0"], 7)
        self.assertEqual(disclosure["exit_1"], 17)
        self.assertEqual(disclosure["independent_lean_attempts"], 0)
        self.assertEqual(disclosure["genuine_nonflat_controls"], 0)
        self.assertEqual(disclosure["i48_outcomes"], 0)
        self.assertEqual(disclosure["i43_implementations"], 0)
        for row in doc["observed_regressions"]:
            self.assertIs(row["regression"], True)
            self.assertEqual(row["classification"], "known_observation_or_regression")
            self.assertIs(row["counted_in_novel_accuracy"], False)
        self.assertEqual(disclosure["transcript_sha256"],
                         "92fc41f1c656105802169a1a188fa88f945152b1dc63437c9cf26b8462f50bcb")
        self.assertEqual({x["id"] for x in doc["observed_regressions"]},
                         {"prereq_left_inv_go", "prereq_right_inv_go_on_image",
                          "prereq_right_inv_sol_on_image", "prereq_domain_validate_go",
                          "prereq_domain_load_sol", "prereq_fund_cycle_flat",
                          "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned"})
        for row in doc["theorems"] + doc["prospective_predictions"]:
            self.assertIs(row["regression"], False)
            self.assertEqual(row["classification"], "informed_prospective_forecast")
        self.assertEqual(tuple(x["id"] for x in doc["theorems"]), I.THEOREMS)
        self.assertEqual(doc["kernels"]["bend"]["budget_seconds"], 60.0)
        self.assertEqual(doc["kernels"]["lean4"]["budget_seconds"], 120.0)
        self.assertEqual(doc["kernels"]["lean4"]["allowed_axioms"], ["propext", "Quot.sound"])
        self.assertEqual(doc["header_application"]["prerequisites"], list(I.PREREQUISITES))
        self.assertEqual(set(doc["header_application"]["prerequisite_contracts"]), set(I.PREREQUISITES))
        self.assertEqual(len(doc["header_application"]["vertices"]), 5)
        self.assertEqual(len(doc["header_application"]["directed_edges"]), 6)
        contracts = doc["header_application"]["prerequisite_contracts"]
        for prereq, terms in {
            "prereq_domain_encode_v1": ("enc_v1", "Img(enc_v1)", "89-byte"),
            "prereq_domain_validate_v1": ("validate_v1", "load_v1", "BytesV1"),
            "prereq_right_inv_codec_v1": ("codec_v1", "enc_v1", "validate_v1"),
            "prereq_right_inv_load_v1": ("load_v1", "inverse_load_v1"),
            "prereq_tree_gauge_rooted_at_header_v1": ("HeaderV1", "tree_path", "sol_commit"),
            "prereq_fund_cycle_flat_sol_go_v1": ("go_commit", "sol_commit", "codec_v1"),
        }.items():
            for term in terms:
                self.assertIn(term, contracts[prereq])
        self.assertIn("self-contained", doc["header_application"]["import_contract"])
        self.assertIn("no import", doc["header_application"]["import_contract"])
        self.assertIn("README.md", entry["outcome_paths"])
        self.assertIn("Only the I42 section", prompt)
        self.assertEqual(doc["header_application"]["result_path"],
                         "results/M3/I42/L_par_v1_header_sufficiency.json")
        self.assertEqual({x["id"] for x in doc["controls"]}, {
            "ctrl_omitted_cycle_nonflat", "ctrl_non_invertible_lossy_edge",
            "ctrl_raw_domain_unrestricted_obstruction"})
        self.assertFalse((ROOT / "spec/M3/lib/basis.json").exists())
        self.assertFalse((ROOT / "tests_m3/test_basis.py").exists())
        self.assertFalse(I.INSTRUMENT.name.endswith(".lib.json"))


class TestI42TargetAgnosticism(unittest.TestCase):
    def test_i42_owns_no_target_identifiers(self):
        for rel in ("holon/gen/basis.py", "holon/gen/lean_basis.py", "holon/gen/core.py"):
            path = ROOT / rel
            if path.is_file():
                self.assertEqual(I.morph_identifiers(path), set(), rel)
        for folder in (I.CORE, I.INSTRUMENT.parent):
            for path in folder.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".bend", ".lean", ".json"}:
                    if path == I.INSTRUMENT:
                        # Historical SHA pins must name the target's existing artifacts.
                        continue
                    self.assertEqual(I.morph_identifiers(path), set(), str(path))
        # Existing replay adapters and generic-name allowlists are historical, not
        # I42 additions. Reject any newly introduced target-bearing module.
        proc = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", "holon"],
                              cwd=ROOT, check=True, capture_output=True, text=True)
        new_files = set(proc.stdout.splitlines())
        for rel in new_files - I.BASELINE:
            if rel.endswith(".py"):
                self.assertEqual(I.morph_identifiers(ROOT / rel), set(), rel)


class TestI42CoreTheoryAndControls(unittest.TestCase):
    def assert_checked(self, row):
        laws = I.strip_comments((ROOT / row["bend_laws_path"]).read_text())
        proof = I.strip_comments((ROOT / row["bend_proof_path"]).read_text())
        lean_src = I.strip_comments((ROOT / row["lean_proof_path"]).read_text())
        name = row.get("law_name", row["id"])
        I.require_expected_law(laws, proof, name)
        signatures = row["required_signatures"]
        for source, required in ((laws, signatures["laws"]), (proof, signatures["proof"]),
                                 (lean_src, signatures["lean"])):
            for kind, symbols in required.items():
                for symbol in symbols:
                    with self.subTest(theorem=name, kind=kind, symbol=symbol):
                        if kind == "references":
                            self.assertRegex(source, rf"\b{re.escape(symbol)}\b")
                        else:
                            keyword = {"types": r"(?:data|type|inductive|structure)",
                                       "definitions": r"def",
                                       "laws": r"law",
                                       "theorems": r"(?:theorem|lemma)"}[kind]
                            self.assertRegex(source, rf"(?m)^\s*{keyword}\s+{re.escape(symbol)}\b")
        self.assertRegex(laws, r"(?m)^\s*(?:data|type)\s+Walk\b")
        self.assertRegex(laws, r"\b(?:Nil|nil)\b")
        self.assertRegex(laws, r"\b(?:Cons|cons)\b")
        self.assertRegex(lean_src, r"(?m)^\s*inductive\s+Walk\b")
        self.assertRegex(lean_src, r"\b(?:Nil|nil)\b")
        self.assertRegex(lean_src, r"\b(?:Cons|cons)\b")
        self.assertRegex(proof, r"\bmatch\s+\w+")
        self.assertRegex(proof, r"\b(?:Nil|nil)\b")
        self.assertRegex(proof, r"\b(?:Cons|cons)\b")
        self.assertRegex(proof, r"(?m)^\s*from\s+\./LAWS\.bend\s+import\s+\S+")
        if name == "thm_6_3_domain_coherence":
            self.assertRegex(lean_src, r"\bmatch\s+\w+")
            self.assertRegex(lean_src, r"\b(?:Nil|nil)\b")
            self.assertRegex(lean_src, r"\b(?:Cons|cons)\b")
        self.assertFalse(I.trivial_statement(laws))
        self.assertFalse(I.trivial_statement(lean_src))
        for bad in ("?TODO", "@unsafe", 'import "./'):
            self.assertNotIn(bad, laws + proof)
        code, output = run_bend([row["bend_proof_path"]], cwd=ROOT,
                                timeout=60)
        self.assertEqual(code, 0, output)
        self.assertIn("ALL PROOFS CHECK", output)
        res = I.check_lean_file(ROOT / row["lean_proof_path"], expect=signatures["lean"]["theorems"])
        self.assertEqual(res["result"], "checked", res)
        self.assertTrue(set(res["axioms"]).issubset(lean.ALLOWED_AXIOMS))
        record = load_json(ROOT / row["result_path"])
        self.assertEqual(record["statement_hash"], I.statement_hash(laws))
        self.assertTrue(record["lean_statement_hash"])

    def test_checked_theory_and_independent_results(self):
        self.assertTrue((ROOT / "holon/gen/basis.py").is_file(), "RED: missing Bend generator")
        self.assertTrue((ROOT / "holon/gen/lean_basis.py").is_file(), "RED: missing Lean generator")
        self.assertTrue(I.CORE.is_dir(), "RED: missing generated core")
        for row in I.instrument()["theorems"]:
            for key in ("bend_laws_path", "bend_proof_path", "lean_proof_path", "result_path"):
                with self.subTest(theorem=row["id"], path=key):
                    self.assertTrue((ROOT / row[key]).is_file(), f"RED: missing {row[key]}")
            result = load_json(ROOT / row["result_path"])
            self.assertEqual(result["status"], "PROVED")
            self.assertEqual(set(result["kernels"]), {"bend", "lean4"})
            self.assert_checked(row)

    def test_semantic_controls(self):
        from holon.gen import core

        path = I.RESULTS / "controls.json"
        self.assertTrue(path.is_file(), "RED: missing semantic control results")
        controls = load_json(path)
        for row in I.instrument()["controls"]:
            with self.subTest(control=row["id"]):
                self.assertIn(row["id"], controls)
                self.assertEqual(controls[row["id"]]["status"], row["predicted_status"])
        instrument = I.instrument()["semantic_controls"]
        for control_id in ("ctrl_tree_flat_extension", "ctrl_omitted_cycle_nonflat"):
            row = instrument[control_id]
            laws = (ROOT / row["bend_laws_path"]).read_text()
            proof = (ROOT / row["bend_proof_path"]).read_text()
            I.require_expected_law(laws, proof, row["law_name"])
            code, output = run_bend([row["bend_proof_path"]], cwd=ROOT, timeout=60)
            self.assertEqual(code, 0, output)
            self.assertIn("ALL PROOFS CHECK", output)
        omitted_law = I.strip_comments((ROOT / instrument[
            "ctrl_omitted_cycle_nonflat"]["bend_laws_path"]).read_text())
        self.assertRegex(omitted_law, r"eval_walk\s*\(\s*fund_cycle\b.*?!=\s*w0\b")
        for row in I.instrument()["controls"]:
            verdict = core.verify_control(row["id"])
            self.assertIs(verdict["certificate_emitted"], False)
            self.assertIn(verdict["status"], {"REFUTED", "UNKNOWN"})
            self.assertEqual(verdict["failed_prerequisite"],
                             instrument[row["id"]]["failed_prerequisite"])
        omitted = controls["ctrl_omitted_cycle_nonflat"]
        self.assertNotEqual(omitted["witness"]["path_a"], omitted["witness"]["path_b"])
        self.assertNotEqual(omitted["witness"]["holonomy"], omitted["witness"]["w0"])
        self.assertEqual(omitted["certificate_status"], "MISS")


class TestI42V1HeaderApplication(unittest.TestCase):
    def test_generated_certificate_imports_checked_core(self):
        header = I.instrument()["header_application"]
        for key in ("bend_laws_path", "bend_proof_path", "lean_proof_path", "result_path"):
            self.assertTrue((ROOT / header[key]).is_file(), f"RED: missing {header[key]}")
        laws = I.strip_comments((ROOT / header["bend_laws_path"]).read_text())
        text = I.strip_comments((ROOT / header["bend_proof_path"]).read_text())
        lean_src = I.strip_comments((ROOT / header["lean_proof_path"]).read_text())
        for theorem in I.THEOREMS:
            self.assertRegex(laws, rf"(?m)^\s*from\s+\.\./{theorem}/LAWS\.bend\s+import\s+\S+")
            self.assertRegex(text, rf"(?m)^\s*from\s+\.\./{theorem}/PROOF\.bend\s+import\s+\S+")
            # Self-contained Lean embeds the checked declaration and its proof verbatim.
            core = I.strip_comments((I.CORE / f"{theorem}.lean").read_text()).strip()
            self.assertIn(core, lean_src)
        for lemma in I.PREREQUISITES:
            I.require_expected_law(laws, text, lemma)
            self.assertRegex(lean_src, rf"(?m)^\s*(?:theorem|lemma)\s+{lemma}\b")
        I.require_expected_law(laws, text, header["law_name"])
        self.assertFalse(I.trivial_statement(laws))
        self.assertFalse(I.trivial_statement(lean_src))
        proof_body = re.search(r"(?ms)^\s*def\s+Laws\.L_par_v1_header_sufficiency\s*\(.*?(?=^\s*def\s+|\Z)", text)
        self.assertIsNotNone(proof_body)
        lean_body = re.search(r"(?ms)^\s*theorem\s+L_par_v1_header_sufficiency\b.*?(?=^\s*(?:theorem|lemma)\s+|\Z)", lean_src)
        self.assertIsNotNone(lean_body)
        for name in (*I.THEOREMS, *I.PREREQUISITES):
            self.assertRegex(proof_body.group(), rf"\b{re.escape(name)}\s*\(")
            self.assertRegex(lean_body.group(), rf"\b{re.escape(name)}\b")
        res = I.check_lean_file(ROOT / header["lean_proof_path"],
                                expect=[*I.THEOREMS, *I.PREREQUISITES,
                                        "L_par_v1_header_sufficiency"])
        self.assertEqual(res["result"], "checked", res)
        self.assertTrue(set(res["axioms"]).issubset(lean.ALLOWED_AXIOMS))
        record = load_json(ROOT / header["result_path"])
        self.assertEqual(record["status"], "PROVED")
        self.assertEqual(set(record["kernels"]), {"bend", "lean4"})
        code, output = run_bend([header["bend_proof_path"]], cwd=ROOT, timeout=60)
        self.assertEqual(code, 0, output)
        self.assertIn("ALL PROOFS CHECK", output)
        self.assertEqual(record["statement_hash"], I.statement_hash(laws))
        self.assertTrue(record["lean_statement_hash"])


class TestI42HistoricalPreservation(unittest.TestCase):
    def test_pinned_artifacts_and_prior_predictions(self):
        historical = I.instrument()["historical_preservation"]
        for rel, digest in historical["pinned_sha256"].items():
            with self.subTest(path=rel):
                self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), digest)
        base = subprocess.run(
            ["git", "show", historical["base_predictions_commit"] + ":spec/M3/predictions.json"],
            cwd=ROOT, capture_output=True, check=True)
        self.assertEqual(hashlib.sha256(base.stdout).hexdigest(), historical["base_predictions_sha256"])
        original = json.loads(base.stdout)
        current = load_json(ROOT / "spec/M3/predictions.json")
        self.assertEqual({k: v for k, v in current.items() if k != "iterations"},
                         {k: v for k, v in original.items() if k != "iterations"})
        self.assertEqual({k: v for k, v in current["iterations"].items() if k != "I42"},
                         original["iterations"])
        for name, (status, reason) in historical["result_expectations"].items():
            record = load_json(ROOT / "results/M3" / (name + ".json"))
            self.assertEqual(record["status"], status)
            if reason is not None:
                self.assertEqual(record["reason"], reason)
        self.assertEqual(I.git_changed(*historical["pinned_sha256"]), [])

    def test_existing_results_and_documentation(self):
        historical = I.instrument()["historical_preservation"]
        readme_base = subprocess.run(
            ["git", "show", historical["base_predictions_commit"] + ":README.md"],
            cwd=ROOT, capture_output=True, check=True, text=True).stdout
        readme_current = (ROOT / "README.md").read_text(encoding="utf-8")
        marker = "## I42"
        self.assertTrue(readme_current.startswith(readme_base))
        self.assertTrue(readme_current[len(readme_base):].lstrip().startswith(marker))
        self.assertNotIn(marker, readme_base)
        self.assertTrue((ROOT / "docs/iterations/I42.md").is_file(), "RED: missing I42 report")
        self.assertTrue(I.RESULTS.is_dir(), "RED: missing I42 records")


if __name__ == "__main__":
    unittest.main()
