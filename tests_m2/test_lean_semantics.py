"""Audit M2/1 F-M2-20 and F-M2-32: G7's Lean rules.

F-M2-32: a Lean canary counts as rejected only for a semantic reason (holon.lean.semantic_rejection): the kernel
decided the flipped claim false, or found two sides not definitionally equal. A parse, name or goal-shape error
proves nothing about the kernel. The flip of a PROVED law is rejected only for its goal shape ("Expected the goal
to be a binary relation", I9 Surprise 4), so G7 flips a REFUTED law's counter-law, which `decide` decides false.
These tests need the pinned Lean toolchain and fail (never pass) without it: the I9-P4 test accepted 'unavailable'.

F-M2-20: G7 passed vacuously when no M0 record listed lean4. With the pinned toolchain present, every decided M0
law must list lean4 as checked (I2); without it, G7 fails, labelled single-kernel.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, records, write_json

LEAN_DIR = ROOT / "gen" / "M0" / "lean"


class TestCanarySemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L = holon_module("holon.lean")
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-lean-sem-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, src: str, name: str) -> dict:
        r = self.L.check_text(src, self.tmp / name)
        self.assertEqual(r["result"], "rejected", f"{name}: Lean must run and reject it, got {r['result']}: "
                                                  f"{r['out'][-600:]}")
        return r

    def test_the_flipped_counter_law_is_rejected_by_the_kernel_deciding_it_false(self):
        lid = next(l for l, rec in sorted(records("M0").items()) if rec["status"] == "REFUTED")
        r = self.check(self.L.flip_canary((LEAN_DIR / f"{lid}.lean").read_text(encoding="utf-8")), "flip_refuted")
        self.assertTrue(self.L.semantic_rejection(r["out"]), self.L.first_error_block(r["out"]))
        self.assertIn("decide", self.L.first_error_block(r["out"]))

    def test_a_shape_or_parse_rejection_is_not_semantic(self):
        lid = next(l for l, rec in sorted(records("M0").items()) if rec["status"] == "PROVED")
        src = (LEAN_DIR / f"{lid}.lean").read_text(encoding="utf-8")
        r = self.check(self.L.flip_canary(src), "flip_proved")
        self.assertFalse(self.L.semantic_rejection(r["out"]), "the PROVED flip fails on its goal shape only")
        r = self.check(src.replace(":= by", ":= by )", 1), "parse")
        self.assertFalse(self.L.semantic_rejection(r["out"]), "a syntax error is not a semantic rejection")

    def test_eval_and_exit_are_forbidden(self):
        self.assertIn("#eval", self.L.forbidden("theorem t : 1 = 1 := rfl\n#eval IO.println \"x\"\n"))
        self.assertIn("#exit", self.L.forbidden("#exit\ntheorem t : 1 = 2 := rfl\n"))
        self.assertEqual(self.L.forbidden("-- #eval in a comment\ntheorem t : 1 = 1 := rfl\n"), [])


class TestG7RequiresLean(unittest.TestCase):
    def test_m0_records_without_lean4_fail_g7_when_the_toolchain_is_present(self):
        G = holon_module("holon.gate")
        L = holon_module("holon.lean")
        ok, why = L.toolchain_ok(L.config(ROOT))
        self.assertTrue(ok, f"the pinned Lean toolchain must be present for this test: {why}")
        repo = copy_repo()
        try:
            for f in sorted((repo / "results" / "M0").glob("L_*.json")):
                rec = json.loads(f.read_text())
                rec["kernels"] = [k for k in rec["kernels"] if k.get("name") != "lean4"]
                rec["independence_class"] = "I1-shared"
                write_json(f, rec)
            passed, detail = G.Gate("M0", repo).g7_lean()
            self.assertFalse(passed, detail)
            self.assertIn("lean4 not checked for decided laws", detail)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_without_the_pinned_toolchain_g7_fails_labelled_single_kernel(self):
        G = holon_module("holon.gate")
        repo = copy_repo()
        try:
            cfg = load_json(repo / "config" / "holon.json")
            cfg["lean"]["toolchain"] = "leanprover/lean4:v0.0.0-absent"
            write_json(repo / "config" / "holon.json", cfg)
            passed, detail = G.Gate("M0", repo).g7_lean()
            self.assertFalse(passed, detail)
            self.assertIn("single-kernel", detail)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
