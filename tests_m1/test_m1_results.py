"""M1: a fresh run reproduces the preregistered outcomes (whitepaper §11.8), with checked evidence."""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._util import MARK_OK, ROOT, config, load_json, run_bend, run_holon, validate
from tests_m1._m1 import LAWS, law_ids, predictions


def names(p: Path) -> list[str]:
    return re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", p.read_text(), re.M)


class TestM1Results(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-m1-"))
        cls.out, cls.gen = cls.tmp / "results", cls.tmp / "gen"
        p = run_holon(["run", "--milestone", "M1", "--out", str(cls.out), "--gen-dir", str(cls.gen)])
        if p.returncode != 0:
            raise AssertionError("holon run M1 failed:\n" + p.stdout[-3000:] + p.stderr[-3000:])
        cls.reg = load_json(LAWS / "REGISTRY.json")["statements"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def rec(self, lid):
        return load_json(self.out / f"{lid}.json")

    def res(self, p):
        p = Path(p)
        return p if p.is_absolute() else ROOT / p

    def test_statuses_match_predictions(self):
        self.assertEqual(load_json(self.out / "summary.json"), {k: v["status"] for k, v in predictions().items()})

    def test_records_complete(self):
        for lid in law_ids():
            with self.subTest(law=lid):
                r = self.rec(lid)
                validate(r, "result_record")
                self.assertEqual(r["statement_hash"], self.reg[lid])
                self.assertEqual(r["kernel"]["version"], config()["bend"]["pinned_version"])
                self.assertEqual(r["scope"], "unbounded")

    def test_checked_files_recheck(self):
        for lid, pred in predictions().items():
            with self.subTest(law=lid):
                r = self.rec(lid)
                laws, proof = self.res(r["artifacts"]["laws"]), self.res(r["artifacts"]["proof"])
                want = lid.lower() if pred["status"] == "PROVED" else "cl_" + lid.lower()
                self.assertEqual(names(laws), [want])
                code, out = run_bend([proof.name], cwd=proof.parent)
                self.assertEqual(code, 0, out[:2000])
                self.assertEqual(out.strip().splitlines()[0], MARK_OK)
                self.assertNotRegex(proof.read_text() + laws.read_text(), r"@unsafe|def\s+[\w.]+\?\s*\(|\?TODO|import\s+\"")

    def test_refuted_witnesses_hold_on_the_compiled_model(self):
        from holon.mpipeline import CompiledMachine
        cm = CompiledMachine.build(ROOT / "spec" / "M1" / "facts" / "morph_rollup.json")
        for lid, pred in predictions().items():
            if pred["status"] != "REFUTED":
                continue
            with self.subTest(law=lid):
                r = self.rec(lid)
                self.assertEqual(r["triage"], pred.get("triage", "finding"))
                ev = cm.evaluate(load_json(LAWS / f"{lid}.json"), r["witness"])
                self.assertTrue(all(ev["premises"]), ev)
                self.assertFalse(all(ev["claims"]), ev)

    def test_committed_results_match_fresh_run(self):
        self.assertEqual(load_json(ROOT / "results" / "M1" / "summary.json"), load_json(self.out / "summary.json"))


if __name__ == "__main__":
    unittest.main()
