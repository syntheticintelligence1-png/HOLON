"""I1: the preregistration file is well formed, and every test it names exists."""
import unittest

from tests_m2._m2 import ROOT, SCHEMAS2, SPEC2, load_json, validate


class TestPredictionsSchema(unittest.TestCase):
    def test_predictions_validate(self):
        doc = load_json(SPEC2 / "predictions.json")
        self.assertEqual(validate(doc, SCHEMAS2 / "predictions.schema.json"), [])
        self.assertEqual(doc["milestone"], "M2")

    def test_named_tests_and_prompts_exist(self):
        doc = load_json(SPEC2 / "predictions.json")
        for key, it in doc["iterations"].items():
            with self.subTest(iteration=key):
                self.assertTrue((ROOT / it["prompt"]).exists(), it["prompt"])
                for t in it["tests"]:
                    self.assertTrue((ROOT / t).exists(), t)
                ids = [x["id"] for x in it["predictions"] + it["regressions"]]
                self.assertEqual(len(ids), len(set(ids)))
                self.assertTrue(all(i.startswith(key + "-") for i in ids))


if __name__ == "__main__":
    unittest.main()
