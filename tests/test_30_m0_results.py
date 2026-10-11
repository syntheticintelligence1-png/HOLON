"""P3: a fresh run of the M0 pipeline reproduces the preregistered outcomes, with checked evidence."""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests._util import (FACTS, LAWS_DIR, MARK_OK, ROOT, config, first_difference, law_ids, load_json,
                         load_law, predictions, run_bend, run_holon, validate)
from tests.reference import ref_ir as I
from tests.reference import ref_model as M


def bend_law_names(laws_file: Path) -> list[str]:
    return re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", laws_file.read_text(), re.M)


class TestM0Results(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-m0-"))
        cls.out, cls.gen = cls.tmp / "results", cls.tmp / "gen"
        p = run_holon(["run", "--milestone", "M0", "--out", str(cls.out), "--gen-dir", str(cls.gen)])
        if p.returncode != 0:
            raise AssertionError("holon run failed:\n" + p.stdout[-3000:] + p.stderr[-3000:])
        cls.facts = M.load_facts(FACTS)
        cls.reg = load_json(LAWS_DIR / "REGISTRY.json")["statements"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def record(self, lid):
        return load_json(self.out / f"{lid}.json")

    def resolve(self, p):
        p = Path(p)
        return p if p.is_absolute() else ROOT / p

    def test_statuses_match_predictions(self):
        summary = load_json(self.out / "summary.json")
        want = {lid: p["status"] for lid, p in predictions().items()}
        self.assertEqual(summary, want)

    def test_records_are_complete(self):
        for lid in law_ids():
            with self.subTest(law=lid):
                r = self.record(lid)
                validate(r, "result_record")
                self.assertEqual(r["law_id"], lid)
                self.assertEqual(r["statement_hash"], self.reg[lid])
                self.assertEqual(r["facts_sha256"], M.facts_sha256(FACTS))
                self.assertEqual(r["kernel"]["version"], config()["bend"]["pinned_version"])
                self.assertEqual(r["scope"], "unbounded")
                n_assume = len(load_law(lid)["statement"].get("assume", []))
                self.assertGreaterEqual(len(r["premises"]), n_assume)

    def test_proved_laws_recheck(self):
        for lid, pred in predictions().items():
            if pred["status"] != "PROVED":
                continue
            with self.subTest(law=lid):
                r = self.record(lid)
                self.assertEqual(r["triage"], "none")
                laws, proof = self.resolve(r["artifacts"]["laws"]), self.resolve(r["artifacts"]["proof"])
                self.assertEqual(bend_law_names(laws), [lid.lower()], "exactly the expected law, nothing else")
                code, out = run_bend([proof.name], cwd=proof.parent)
                self.assertEqual(code, 0, out[:2000])
                self.assertEqual(out.strip().splitlines()[0], MARK_OK)
                src = proof.read_text() + laws.read_text()
                self.assertNotRegex(src, r"@unsafe|def\s+[\w.]+\?\s*\(|\?TODO|import\s+\"", "no escape hatches")

    def test_refuted_laws_have_checked_witnesses(self):
        for lid, pred in predictions().items():
            if pred["status"] != "REFUTED":
                continue
            with self.subTest(law=lid):
                r = self.record(lid)
                law = load_law(lid)
                self.assertEqual(r["triage"], pred["triage"])
                env = I.env_from_witness(law, self.facts, r["witness"])
                chk = I.check(law, self.facts, env)
                self.assertTrue(chk["premises"], "witness must satisfy the premises")
                self.assertIs(chk["claim"], False, "witness must falsify the claim (oracle)")
                self.assertEqual(r["difference"], {"lhs": M.value_to_json(chk["lhs"]), "rhs": M.value_to_json(chk["rhs"])})
                c = pred.get("witness_constraints", {})
                if "first_difference" in c:
                    i = first_difference(chk["lhs"], chk["rhs"])
                    fd = c["first_difference"]
                    if "index" in fd:
                        self.assertEqual((i, chk["lhs"][i], chk["rhs"][i]), (fd["index"], fd["lhs"], fd["rhs"]))
                    else:
                        self.assertTrue(fd["index_range"][0] <= i < fd["index_range"][1], i)
                if "lhs" in c:
                    self.assertEqual((chk["lhs"], chk["rhs"]), (c["lhs"], c["rhs"]))
                laws, proof = self.resolve(r["artifacts"]["laws"]), self.resolve(r["artifacts"]["proof"])
                self.assertEqual(bend_law_names(laws), ["cl_" + lid.lower()])
                code, out = run_bend([proof.name], cwd=proof.parent)
                self.assertEqual(code, 0, out[:2000])
                self.assertEqual(out.strip().splitlines()[0], MARK_OK)

    def test_committed_results_match_fresh_run(self):
        committed = ROOT / "results" / "M0" / "summary.json"
        self.assertTrue(committed.is_file(), "commit results/M0 (python -m holon run --milestone M0)")
        self.assertEqual(load_json(committed), load_json(self.out / "summary.json"))


if __name__ == "__main__":
    unittest.main()
