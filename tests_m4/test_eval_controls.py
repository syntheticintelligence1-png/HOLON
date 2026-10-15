"""I48 matched scale controls and solver-isolation acceptance."""
from __future__ import annotations

import unittest
import importlib
import subprocess

from tests_m4._i48 import ROOT, inside, instrument, load


EXPECTED = [
    ("PAR", 1, "par_codec_width", 8, 16, 4801, 12),
    ("PAR", 2, "par_codec_width", 8, 24, 4802, 19),
    ("SORT", 1, "sort_list_depth", 4, 10, 4803, 7),
    ("SORT", 2, "sort_list_depth", 4, 14, 4804, 11),
    ("UNDO", 1, "undo_journal_steps", 3, 8, 4805, 6),
    ("UNDO", 2, "undo_journal_steps", 3, 12, 4806, 9),
]


class TestControlsInstrument(unittest.TestCase):
    def test_preregistered_contract(self):
        rules = instrument()["control_rules"]
        self.assertEqual(rules["manifest"], "spec/eval/controls.json")
        self.assertEqual(rules["generated_dir"], "gen/M4/I48/controls/")
        self.assertEqual(rules["verification_report"], "results/M4/I48/controls_report.json")
        self.assertEqual(rules["families"],
                         ["par_codec_width", "sort_list_depth", "undo_journal_steps"])
        self.assertEqual(rules["pairs"], [
            {"true_id": f"C{i:02d}_known_true_{i:02d}",
             "false_id": f"C{i+6:02d}_known_false_{i:02d}",
             "family": family, "standard_budget": budget,
             "control_scale": scale, "seed": seed, "witness_scale": witness}
            for i, (_, _, family, budget, scale, seed, witness) in enumerate(EXPECTED, 1)
        ])
        self.assertIn("outside holon/eval/", rules["isolation"])


class TestControlsOutcome(unittest.TestCase):
    def test_controls(self):
        rules = instrument()["control_rules"]
        rows = load(rules["manifest"])["controls"]
        expected = {p[k]: (p, outcome) for p in rules["pairs"]
                    for k, outcome in (("true_id", "known_true"),
                                       ("false_id", "known_false"))}
        self.assertEqual(len(rows), 12)
        self.assertEqual({r["control_id"] for r in rows}, set(expected))
        self.assertEqual(sum(r["known_outcome"] == "known_true" for r in rows), 6)
        self.assertEqual(sum(r["known_outcome"] == "known_false" for r in rows), 6)
        for row in rows:
            with self.subTest(control=row["control_id"]):
                pair, outcome = expected[row["control_id"]]
                self.assertEqual(row["known_outcome"], outcome)
                for key in ("family", "standard_budget", "control_scale", "seed"):
                    self.assertEqual(row[key], pair[key])
                self.assertGreater(row["control_scale"], row["standard_budget"])
                if outcome == "known_true":
                    self.assertTrue(row["invariant_justification"].strip())
                else:
                    self.assertEqual(row["witness_scale"], pair["witness_scale"])
                    self.assertGreater(row["witness_scale"], row["standard_budget"])
                    self.assertLessEqual(row["witness_scale"], row["control_scale"])
                    self.assertIsNotNone(row["witness"])

    def test_verification(self):
        rules = instrument()["control_rules"]
        rows = load(rules["manifest"])["controls"]
        report = load(rules["verification_report"])["controls"]
        module = importlib.import_module("holon.eval.controls")
        evaluator = module.evaluate_control
        self.assertEqual(set(report), {r["control_id"] for r in rows})
        for row in rows:
            with self.subTest(control=row["control_id"]):
                control_id = row["control_id"]
                self.assertEqual(load(f"spec/eval/I48/controls/{control_id}.json")["control_id"],
                                 control_id)
                generated = inside(f"gen/M4/I48/controls/{control_id}", "gen/M4/I48/controls")
                self.assertTrue(generated.is_dir())
                check = report[row["control_id"]]
                self.assertTrue(check["verified"])
                artifact = inside(check["artifact"], f"gen/M4/I48/controls/{control_id}")
                self.assertTrue(artifact.is_file(), f"Missing verification artifact: {artifact}")
                self.assertEqual(artifact.suffix, ".bend")
                self.assertIn("law ", artifact.read_text(), "Vacuous Bend artifact")
                def bend_check():
                    result = subprocess.run(["bend", str(artifact)], capture_output=True,
                                            text=True, check=False, cwd=generated)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("ALL PROOFS CHECK", result.stdout)
                bend_check()
                standard = evaluator(control_id, budget_scale=row["standard_budget"])
                if row["known_outcome"] == "known_false":
                    self.assertEqual(standard["verdict"], "PASSED_BOUNDED")
                    self.assertIsNone(standard["witness"])
                    for scale in range(row["standard_budget"] + 1):
                        bounded = evaluator(control_id, budget_scale=scale)
                        self.assertEqual(bounded["verdict"], "PASSED_BOUNDED")
                        self.assertIsNone(bounded["witness"])
                    found = evaluator(control_id, budget_scale=row["witness_scale"])
                    self.assertEqual(found["verdict"], "REFUTED")
                    self.assertIsNotNone(found["witness"])
                    lhs, rhs = module.evaluate_sides(control_id, found["witness"])
                    self.assertNotEqual(lhs, rhs)
                    self.assertEqual(found["witness"], row["witness"])
                    self.assertTrue(check["passed_through_budget"])
                    self.assertTrue(check["violates_at_witness"])
                    self.assertEqual(check["witness_scale"], row["witness_scale"])
                    self.assertEqual(check["witness"], row["witness"])
                else:
                    self.assertEqual(standard["verdict"], "PROVED")
                    self.assertIsNone(standard["witness"])
                    self.assertTrue(check["invariant_verified"])

    def test_solver_isolation(self):
        directory = ROOT / "holon/eval"
        self.assertTrue(directory.is_dir(), "Missing build outcome: holon/eval/")
        paths = (list((ROOT / "holon").rglob("*.py")) +
                 list((ROOT / "holon").rglob("*.bend")))
        for milestone in range(4):
            for suffix in ("*.py", "*.bend"):
                paths.extend((ROOT / f"gen/M{milestone}").rglob(suffix))
        for path in paths:
            if path.is_relative_to(directory):
                continue
            text = path.read_text()
            for marker in ("spec/eval", "results/M4", "holon.eval",
                           "C01_known_true", "C07_known_false"):
                self.assertNotIn(marker, text, str(path))


if __name__ == "__main__":
    unittest.main()
