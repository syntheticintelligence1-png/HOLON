"""I1: the gate regenerates records (G1), binds REFUTED records to replay (G6), checks completeness (G9)."""
import json
import shutil
import unittest
from pathlib import Path

from tests_m2._m2 import copy_repo, load_json, run_holon, write_json


def run_gate(repo: Path, milestone: str, checks: str | None = None):
    report = repo / f"gate_report_{milestone}.json"
    args = ["gate", "--milestone", milestone, "--root", str(repo), "--report", str(report)]
    if checks:
        args += ["--checks", checks]
    p = run_holon(args, cwd=repo)
    return p, (load_json(report) if report.exists() else None)


class _FullGate:
    milestone = ""
    n_records = 0

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        cls.proc, cls.report = run_gate(cls.repo, cls.milestone)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_gate_passes(self):
        self.assertIsNotNone(self.report, self.proc.stdout[-2000:] + self.proc.stderr[-2000:])
        for g, c in self.report["checks"].items():
            self.assertTrue(c["passed"], f"{g}: {c['detail']}")
        self.assertEqual(self.proc.returncode, 0)

    def test_g6_g9_pass(self):
        for g in ("G6", "G9"):
            self.assertIn(g, self.report["checks"])
            self.assertTrue(self.report["checks"][g]["passed"], self.report["checks"][g]["detail"])

    def test_g1_covers_records(self):
        self.assertIn(f"{self.n_records} records identical", self.report["checks"]["G1"]["detail"])


class TestGateM0(_FullGate, unittest.TestCase):
    milestone, n_records = "M0", 8


class TestGateM1(_FullGate, unittest.TestCase):
    milestone, n_records = "M1", 16


class TestGateCatchesTampering(unittest.TestCase):
    def tampered(self, milestone: str, checks: str, edit) -> dict:
        repo = copy_repo()
        try:
            edit(repo)
            p, rep = run_gate(repo, milestone, checks)
            self.assertIsNotNone(rep, p.stdout[-1500:] + p.stderr[-1500:])
            self.assertNotEqual(p.returncode, 0, "gate passed on a tampered tree")
            self.assertFalse(rep["passed"])
            return rep
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_flipped_witness_hash_fails_g6(self):
        def edit(repo):
            f = repo / "replay" / "M1" / "report.json"
            d = load_json(f)
            h = d["witness_sha256"]["L_undo_BVH"]
            d["witness_sha256"]["L_undo_BVH"] = ("0" if h[0] != "0" else "1") + h[1:]
            write_json(f, d)
        rep = self.tampered("M1", "G6", edit)
        self.assertFalse(rep["checks"]["G6"]["passed"])
        self.assertIn("L_undo_BVH", rep["checks"]["G6"]["detail"])

    def test_unlabelled_not_applicable_side_fails_g6(self):
        def edit(repo):
            f = repo / "replay" / "M0" / "report.json"
            d = load_json(f)
            d["laws"]["L_par_hdr_v2"]["solidity"].update(status="not_applicable", obstruction_observed=False,
                                                         observed="needs a full commitBatch deployment: M1")
            write_json(f, d)
            r = repo / "results" / "M0" / "L_par_hdr_v2.json"
            rec = load_json(r)
            rec["filter_bin"] = "pending"
            write_json(r, rec)
        rep = self.tampered("M0", "G6", edit)
        self.assertIn("L_par_hdr_v2", rep["checks"]["G6"]["detail"])
        self.assertIn("not labelled 'model-only pending replay'", rep["checks"]["G6"]["detail"])

    def test_failed_replay_in_record_fails_g6(self):
        def edit(repo):
            f = repo / "results" / "M1" / "L_sort_remaining.json"
            d = load_json(f)
            d["replay"]["status"] = "failed"
            write_json(f, d)
        rep = self.tampered("M1", "G6", edit)
        self.assertIn("L_sort_remaining", rep["checks"]["G6"]["detail"])

    def test_wrong_morph_commit_fails_g6(self):
        def edit(repo):
            f = repo / "replay" / "M1" / "report.json"
            d = load_json(f)
            d["morph_commit"] = "0" * 40
            write_json(f, d)
        self.tampered("M1", "G6", edit)

    def test_tampered_record_fails_g1(self):
        def edit(repo):
            f = repo / "results" / "M0" / "L_dom_hdr.json"
            d = load_json(f)
            d["replay"]["status"] = "failed"
            write_json(f, d)
        rep = self.tampered("M0", "G1", edit)
        self.assertIn("L_dom_hdr", rep["checks"]["G1"]["detail"])

    def test_missing_v2_field_fails_g9(self):
        def edit(repo):
            f = repo / "results" / "M1" / "L_undo_CSR.json"
            d = load_json(f)
            del d["model_sha256"]
            write_json(f, d)
        rep = self.tampered("M1", "G9", edit)
        self.assertIn("L_undo_CSR", rep["checks"]["G9"]["detail"])

    def test_v1_violation_fails_g9(self):
        def edit(repo):
            f = repo / "results" / "M0" / "L_par_hdr_v1.json"
            d = load_json(f)
            d["status"] = "MAYBE"
            write_json(f, d)
        self.tampered("M0", "G9", edit)


if __name__ == "__main__":
    unittest.main()
