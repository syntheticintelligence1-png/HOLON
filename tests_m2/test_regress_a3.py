"""Audit M2/1 F-M2-34: A3 (holon audit regress) compares law sets, premises and proof strengths across commits
(whitepaper §9.5 A3), and names the STATEMENT_DIFF entry covering each statement-hash change.

New report keys: additions (law files added in A..B), transitions (per law: status, kernels with their results,
independence_class and premises, at A and at B, where they differ) and, on each hash change, covered_by (the
laws/STATEMENT_DIFF.jsonl lines at B carrying exactly the two statements). The preregistered I10 expectations
(tests_m2/test_regress.py) are unchanged.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._ir03_fx import commit_all, git, holon_module
from tests_m2._m2 import run_holon


class TestRealHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = run_holon(["audit", "regress", "--from", "8a1dbe7", "--to", "HEAD", "--json"], timeout=600)
        cls.rep = json.loads(cls.proc.stdout) if cls.proc.returncode == 0 else None

    def setUp(self):
        self.assertIsNotNone(self.rep, self.proc.stdout[-1500:] + self.proc.stderr[-1500:])

    def test_law_set_additions(self):
        adds = self.rep["additions"]
        self.assertEqual(sum(1 for a in adds if a["milestone"] == "M1" and a["commit"] == "9a96037"), 15)
        self.assertIn({"milestone": "M1", "law_id": "L_own_txspayload", "commit": "3e9cb2a"}, adds)
        self.assertFalse(any(a["milestone"] == "M0" for a in adds), "M0's laws predate 8a1dbe7..")

    def test_status_kernel_and_independence_transitions(self):
        tr = {t["law"]: t for t in self.rep["transitions"]}
        m2 = sorted(k for k in tr if k.startswith("M2/"))
        self.assertEqual(len(tr) - len(m2), 24, "every M0/M1 law gained its result record after the seed")
        self.assertEqual(m2, sorted("M2/" + p.stem for p in (Path(__file__).resolve().parents[1] / "results" / "M2").glob("L_*.json")),
                         "and every M2 law record (I15)")
        for key, t in tr.items():
            with self.subTest(law=key):
                self.assertIsNone(t["status"][0])
                self.assertIn(t["status"][1], ("PROVED", "REFUTED", "UNKNOWN"))
        self.assertIn("lean4:checked", tr["M0/L_par_hdr_v0"]["kernels"][1])
        self.assertEqual(tr["M0/L_par_hdr_v0"]["independence_class"], [None, "I2"])

    def test_every_hash_change_names_its_covering_entries(self):
        for h in self.rep["hash_changes"]:
            self.assertIn("covered_by", h)


class TestSyntheticHistory(unittest.TestCase):
    """A two-commit history: a strengthening with its STATEMENT_DIFF entry, and the result record's transition."""

    def test_covered_change_and_transition(self):
        R = holon_module("holon.audit.regress")
        tmp = Path(tempfile.mkdtemp(prefix="holon-a3-"))
        try:
            root = tmp / "repo"
            (root / "laws" / "M9").mkdir(parents=True)
            (root / "results" / "M9").mkdir(parents=True)
            v1 = {"ir_version": "holon-ir/0.1", "law_id": "L_x", "rule": "PAR", "facts_sha256": "", "milestone": "M9",
                  "statement": {"forall": [{"name": "h", "type": "Hdr"}], "assume": [],
                                "claim": {"eq": [{"var": "h"}, {"var": "h"}]}}}
            v2 = json.loads(json.dumps(v1))
            v2["statement"]["claim"] = {"eq": [{"field": "version", "of": {"var": "h"}},
                                               {"field": "version", "of": {"var": "h"}}]}
            (root / "laws" / "M9" / "L_x.json").write_text(json.dumps(v1))
            (root / "laws" / "M9" / "L_y.json").write_text(json.dumps({**v1, "law_id": "L_y"}))
            (root / "laws" / "STATEMENT_DIFF.jsonl").write_text("")
            (root / "results" / "M9" / "L_x.json").write_text(json.dumps(
                {"status": "PROVED", "independence_class": "I1-shared", "premises": [],
                 "kernels": [{"name": "bend2", "result": "checked"}, {"name": "bendtt", "result": "checked"}]}))
            self.assertEqual(git(root, "init", "-q", "-b", "main").returncode, 0)
            a = commit_all(root, "seed")
            (root / "laws" / "M9" / "L_x.json").write_text(json.dumps(v2))
            (root / "laws" / "M9" / "L_y.json").write_text(json.dumps({**v2, "law_id": "L_y"}))
            (root / "laws" / "M9" / "L_z.json").write_text(json.dumps({**v1, "law_id": "L_z"}))
            (root / "laws" / "STATEMENT_DIFF.jsonl").write_text(json.dumps(
                {"kind": "strengthening", "law_id": "L_x", "old": v1, "new": v2, "reason": "t"}) + "\n")
            (root / "results" / "M9" / "L_x.json").write_text(json.dumps(
                {"status": "UNKNOWN", "independence_class": "none", "premises": [],
                 "kernels": [{"name": "bend2", "result": "not_run"}]}))
            b = commit_all(root, "change")
            rep = R.audit(root.resolve(), a, b)
            ch = {h["law_id"]: h for h in rep["hash_changes"]}
            self.assertEqual(ch["L_x"]["covered_by"], [1])
            self.assertEqual(ch["L_y"]["covered_by"], [], "no entry carries L_y's change")
            self.assertEqual(rep["additions"], [{"milestone": "M9", "law_id": "L_z", "commit": b[:7]}])
            t = next(t for t in rep["transitions"] if t["law"] == "M9/L_x")
            self.assertEqual(t["status"], ["PROVED", "UNKNOWN"])
            self.assertEqual(t["independence_class"], ["I1-shared", "none"])
            self.assertEqual(t["kernels"], [["bend2:checked", "bendtt:checked"], ["bend2:not_run"]])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
