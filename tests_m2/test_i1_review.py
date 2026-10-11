"""I1 follow-up: checks added after the adversarial review of I1 (not part of the I1 preregistration).

Each test pins a confirmed review finding: the derived-facts path, the compiled and generator
hashes, the IR fallback roots, records that disclose model-only replay sides, and G1/G6
robustness against malformed or subtly tampered inputs.
"""
import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import (MILESTONES, ROOT, copy_repo, holon_module, laws, load_json, model_file, records, run_holon,
                          write_json)


def run_gate(repo: Path, milestone: str, checks: str | None, report: bool = True):
    rp = repo / f"gate_{milestone}.json"
    args = ["gate", "--milestone", milestone, "--root", str(repo)]
    if report:
        args += ["--report", str(rp)]
    if checks:
        args += ["--checks", checks]
    p = run_holon(args, cwd=repo)
    return p, (load_json(rp) if rp.exists() else None)


class TestLedgerPaths(unittest.TestCase):
    def test_resolve_bundle_exact_derived_and_error(self):
        R = holon_module("holon.records")
        rec = records("M0")["L_par_hdr_v1"]
        self.assertEqual(R.resolve_bundle(rec["facts_sha256"], "facts/morph_header.json")[1], "exact")
        self.assertEqual(R.resolve_bundle("f" * 64, "facts/morph_header.json")[1], "derived")
        with self.assertRaises(R.LedgerError):
            R.resolve_bundle("f" * 64, None)
        with self.assertRaises(R.LedgerError):
            R.resolve_bundle("f" * 64, "facts/not_in_ledger.json")

    def test_derived_run_with_unclassified_definition_fails(self):
        R = holon_module("holon.records")
        text = model_file(records("M0")["L_par_hdr_v1"]).read_text() + "\ndef brand_new(x: Nat) -> Nat:\n  x\n"
        with self.assertRaises(R.LedgerError):
            R.resolve_bundle("f" * 64, "facts/morph_header.json", ROOT, text, {"brand_new", "enc_sol"})
        # a new definition outside the cone does not matter
        self.assertEqual(R.resolve_bundle("f" * 64, "facts/morph_header.json", ROOT, text, {"enc_sol"})[1], "derived")

    def test_ir_fallback_roots_give_the_same_assumptions(self):
        R = holon_module("holon.records")
        for m in MILESTONES:
            ls = laws(m)
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    c = R.cone(R.ir_roots_text(ls[lid]), model_file(rec).read_text())
                    self.assertEqual(R.model_assumptions(rec["facts_sha256"], set(c)), rec["model_assumptions"])
                    self.assertTrue(set(c) <= set(rec["cone"]) or set(c) >= set(rec["cone"]))


class TestHashes(unittest.TestCase):
    def test_generator_files_follow_imports(self):
        R = holon_module("holon.records")
        self.assertIn("holon/facts.py", R.generator_files("holon-ir/0.1"))
        for v in ("holon-ir/0.1", "holon-ir/0.2"):
            for f in R.GENERATORS[v]:
                self.assertIn(f, R.generator_files(v))

    def test_generator_sha_matches_records(self):
        R = holon_module("holon.records")
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    v = load_json(ROOT / "laws" / m / f"{lid}.json")["ir_version"]
                    self.assertEqual(rec["generator_sha256"], R.generator_sha256(v))

    def test_compiled_sha_matches_a_fresh_compile(self):
        build = Path(tempfile.mkdtemp(prefix="holon-test-build-"))
        old = os.environ.get("HOLON_BUILD_DIR")
        os.environ["HOLON_BUILD_DIR"] = str(build)
        try:
            from holon.model_eval import CompiledModel
            from holon.mpipeline import CompiledMachine
            fresh = {
                "morph_header": CompiledModel.build(ROOT / "facts" / "morph_header.json").artifact,
                "morph_rollup": CompiledMachine.build(ROOT / "spec" / "M1" / "facts" / "morph_rollup.json").artifact,
                "morph_batchdata": CompiledMachine.build(ROOT / "spec" / "M1" / "facts" / "morph_batchdata.json").artifact,
            }
            for m in MILESTONES:
                for lid, rec in records(m).items():
                    with self.subTest(law=lid):
                        want = hashlib.sha256(fresh[model_file(rec).stem].read_bytes()).hexdigest()
                        self.assertEqual(rec["compiled_sha256"], want)
        finally:
            if old is None:
                os.environ.pop("HOLON_BUILD_DIR", None)
            else:
                os.environ["HOLON_BUILD_DIR"] = old
            shutil.rmtree(build, ignore_errors=True)


class TestRecordsDiscloseModelOnlySides(unittest.TestCase):
    def test_model_only_side_is_in_the_record(self):
        rep = load_json(ROOT / "replay" / "M0" / "report.json")
        for lid, rec in records("M0").items():
            entry = rep["laws"].get(lid, {})
            for side, v in entry.items():
                if isinstance(v, dict) and v.get("status") == "not_applicable":
                    with self.subTest(law=lid, side=side):
                        self.assertIn(f"{side}: model-only pending replay", rec["replay"]["detail"])


class TestGateRobustness(unittest.TestCase):
    def tampered(self, milestone: str, checks: str, edit, must_fail: str) -> dict:
        repo = copy_repo()
        try:
            edit(repo)
            p, rep = run_gate(repo, milestone, checks)
            self.assertIsNotNone(rep, "the gate must write its report even when a check crashes: "
                                 + p.stdout[-1000:] + p.stderr[-1000:])
            self.assertNotEqual(p.returncode, 0)
            self.assertFalse(rep["checks"][must_fail]["passed"], rep["checks"][must_fail])
            return rep
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def _edit_report(self, m, fn):
        def edit(repo):
            f = repo / "replay" / m / "report.json"
            d = load_json(f)
            fn(d)
            write_json(f, d)
        return edit

    def test_malformed_report_fails_g6_with_a_report(self):
        self.tampered("M1", "G6", self._edit_report("M1", lambda d: d.__setitem__("laws", ["not", "an", "object"])), "G6")

    def test_malformed_record_replay_fails_g6_with_a_report(self):
        def edit(repo):
            f = repo / "results" / "M1" / "L_undo_BVH.json"
            d = load_json(f)
            d["replay"] = "passed"
            write_json(f, d)
        self.tampered("M1", "G6", edit, "G6")

    def test_harness_mismatch_fails_g6(self):
        self.tampered("M1", "G6", self._edit_report("M1", lambda d: d.__setitem__("harness_mismatch", True)), "G6")

    def test_refinement_disagreement_fails_g6(self):
        self.tampered("M1", "G6", self._edit_report("M1", lambda d: d["refinement"].__setitem__("n_disagreements", 1)), "G6")

    def test_stale_report_entry_fails_g6(self):
        def fn(d):
            d["laws"]["L_undo_CSR"] = {"status": "passed", "observed": "stale"}
        rep = self.tampered("M1", "G6", self._edit_report("M1", fn), "G6")
        self.assertIn("L_undo_CSR", rep["checks"]["G6"]["detail"])

    def test_record_hiding_a_model_only_side_fails_g6(self):
        # since I4 the M0 commit-path side is replayed, so the edit first makes it model-only in the
        # report (and rebins the record to match), then hides that in the record's replay detail
        def edit(repo):
            r = repo / "replay" / "M0" / "report.json"
            rep = load_json(r)
            rep["laws"]["L_par_hdr_v2"]["solidity"].update(
                status="not_applicable", obstruction_observed=False, observed="model-only pending replay: test")
            write_json(r, rep)
            f = repo / "results" / "M0" / "L_par_hdr_v2.json"
            d = load_json(f)
            d["filter_bin"] = "pending"
            d["replay"]["detail"] = "go: passed; solidity: not_applicable @ morph 3e44e795586a"
            write_json(f, d)
        rep = self.tampered("M0", "G6", edit, "G6")
        self.assertIn("without saying its solidity side", rep["checks"]["G6"]["detail"])

    def test_g1_distinguishes_0_from_false(self):
        def edit(repo):
            f = repo / "results" / "M0" / "L_dom_hdr.json"
            d = load_json(f)
            self.assertEqual(d["checker"]["exit_code"], 0)
            d["checker"]["exit_code"] = False
            write_json(f, d)
        self.tampered("M0", "G1", edit, "G1")

    def test_partial_run_needs_an_explicit_report(self):
        repo = copy_repo()
        try:
            before = (repo / "results" / "M0" / "gate_report.json").read_bytes()
            p, _ = run_gate(repo, "M0", "G9", report=False)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
            self.assertEqual((repo / "results" / "M0" / "gate_report.json").read_bytes(), before)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
