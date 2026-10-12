"""I9 follow-up checks, added with the implementation (not preregistered; see docs/iterations/I9.md).

  * honesty of kernels[] and independence_class once a Lean kernel exists: I2 exactly when lean4 checked
    the same verdict; BendTT alone stays I1-shared (the rule tests_m2/test_records_v2.py states for a world
    without Lean; its amendment is a question for the human);
  * the lean4 entry is bound to the exact text Lean checked (a stale report never yields I2);
  * the Lean emitters are deterministic and agree with the Bend emitter on canonical binders and premises
    (BUILD_PLAN I9 "emitter cross-check");
  * the runner's source audit and axiom parsing;
  * the gate catches a tampered Lean file, an unbacked I2 and a forbidden tactic.
"""
import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import MILESTONES, ROOT, copy_repo, holon_module, laws, load_json, records, run_holon

LEAN_DIR = ROOT / "gen" / "M0" / "lean"
FACTS = ROOT / "facts" / "morph_header.json"


def facts_and_sha():
    return load_json(FACTS), hashlib.sha256(FACTS.read_bytes()).hexdigest()


class TestHonesty(unittest.TestCase):
    def test_i2_exactly_when_an_independent_kernel_checked(self):
        for m in MILESTONES:
            for lid, rec in records(m).items():
                with self.subTest(law=lid):
                    ks = {k["name"]: k for k in rec["kernels"]}
                    self.assertEqual(len(ks), len(rec["kernels"]), "one entry per kernel")
                    self.assertEqual(ks["bend2"]["role"], "primary")
                    if "bendtt" in ks:
                        self.assertEqual(ks["bendtt"]["role"], "second")
                        self.assertEqual(ks["bendtt"]["shares_frontend_with"], "bend2")
                    lean_ok = ks.get("lean4", {}).get("result") == "checked"
                    if rec["status"] == "UNKNOWN":
                        self.assertEqual(rec["independence_class"], "none")
                        self.assertFalse(lean_ok)
                    elif lean_ok:
                        self.assertEqual(ks["bend2"]["result"], "checked")
                        self.assertEqual(ks["lean4"]["role"], "second-independent")
                        self.assertEqual(rec["independence_class"], "I2")
                    elif rec["kernel"]["verdict"] == "checked":
                        self.assertEqual(rec["independence_class"], "I1-shared")
                    else:
                        self.assertEqual(rec["independence_class"], "I1")

    def test_m0_lean_entries_point_at_the_committed_files(self):
        for lid, rec in records("M0").items():
            with self.subTest(law=lid):
                k = next(k for k in rec["kernels"] if k["name"] == "lean4")
                f = ROOT / k["source"]
                self.assertEqual(hashlib.sha256(f.read_bytes()).hexdigest(), k["source_sha256"])
                self.assertLessEqual(set(k["axioms"]), {"propext", "Quot.sound"})


class TestReportBinding(unittest.TestCase):
    def setUp(self):
        self.L = holon_module("holon.lean")
        self.facts, self.fsha = facts_and_sha()
        self.report = self.L.load_report("M0", ROOT)
        self.laws = laws("M0")
        self.recs = records("M0")

    def entry(self, lid, status=None, witness="same", report="same"):
        rec = self.recs[lid]
        return self.L.kernel_entry(self.laws[lid], self.facts, self.fsha, status or rec["status"],
                                   rec["witness"] if witness == "same" else witness,
                                   self.report if report == "same" else report)

    def test_committed_report_backs_every_record(self):
        for lid in self.laws:
            with self.subTest(law=lid):
                self.assertEqual(self.entry(lid)["result"], "checked")

    def test_another_witness_is_not_backed(self):
        w = copy.deepcopy(self.recs["L_par_hdr_v2"]["witness"])
        w["h"]["dataHash"] = "0x" + "11" * 32
        self.assertEqual(self.entry("L_par_hdr_v2", witness=w)["result"], "not_run")

    def test_another_verdict_is_not_backed(self):
        self.assertEqual(self.entry("L_par_hdr_v0", status="REFUTED", witness=self.recs["L_par_hdr_v2"]["witness"])
                         ["result"], "not_run")

    def test_missing_or_failed_report(self):
        self.assertEqual(self.entry("L_rt_go_v0", report=None)["result"], "not_run")
        bad = copy.deepcopy(self.report)
        bad["laws"]["L_rt_go_v0"]["result"] = "rejected"
        self.assertEqual(self.entry("L_rt_go_v0", report=bad)["result"], "failed")
        stale = copy.deepcopy(self.report)
        stale["laws"]["L_rt_go_v0"]["source_sha256"] = "0" * 64
        self.assertEqual(self.entry("L_rt_go_v0", report=stale)["result"], "not_run")
        badax = copy.deepcopy(self.report)
        badax["laws"]["L_rt_go_v0"]["axioms"] = ["propext", "Classical.choice"]
        self.assertEqual(self.entry("L_rt_go_v0", report=badax)["result"], "failed")


class TestEmitters(unittest.TestCase):
    def test_regeneration_is_byte_identical(self):
        L = holon_module("holon.lean")
        facts, fsha = facts_and_sha()
        for lid, law in laws("M0").items():
            rec = records("M0")[lid]
            with self.subTest(law=lid):
                a, _ = L.emit_for(law, facts, fsha, rec["status"], rec["witness"])
                b, _ = L.emit_for(law, facts, fsha, rec["status"], rec["witness"])
                self.assertEqual(a, b)
                self.assertEqual(a.encode("utf-8"), (LEAN_DIR / f"{lid}.lean").read_bytes())

    def test_canonical_binders_and_premises_agree_with_the_bend_emitter(self):
        LG = holon_module("holon.gen.laws")
        LL = holon_module("holon.gen.lean_laws")
        ir = holon_module("holon.ir")
        facts, _ = facts_and_sha()
        for lid, law in laws("M0").items():
            with self.subTest(law=lid):
                b = LG.emit(law, facts, "../model/m.bend")
                ll = LL.emit(law, facts, ir.statement_hash(law))
                self.assertEqual([tuple(x) for x in b.binders], ll.binders)
                self.assertEqual(len(ll.premises), len(law["statement"].get("assume", [])))
                pins = {}
                for var, fld, bs in ll.premise_pins:
                    pins.setdefault(var, {})[fld] = bs
                self.assertEqual(pins, b.pins)
                self.assertEqual(b.claim_type, ll.claim_type)

    def test_files_hold_one_marked_claim_and_the_statement_hash(self):
        reg = load_json(ROOT / "laws" / "M0" / "REGISTRY.json")["statements"]
        for lid in laws("M0"):
            with self.subTest(law=lid):
                text = (LEAN_DIR / f"{lid}.lean").read_text(encoding="utf-8")
                self.assertEqual(text.count("-- holon:claim"), 1)
                self.assertIn(f"statement_hash: {reg[lid]}", text)


class TestSourceAudit(unittest.TestCase):
    def setUp(self):
        self.L = holon_module("holon.lean")

    def test_forbidden_is_refused_before_lean_runs(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-lean-audit-"))
        try:
            for src in ("theorem t : False := sorry", "axiom a : False\ntheorem t : False := a",
                        "theorem t : 1 = 1 := by native_decide", 'def s := "--"\naxiom a : False',
                        "set_option debug.skipKernelTC true\ntheorem t : 1 = 1 := rfl",
                        "import Std\ntheorem t : 1 = 1 := rfl"):
                with self.subTest(src=src):
                    self.assertEqual(self.L.check_text(src, tmp)["result"], "forbidden")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_comments_do_not_count(self):
        self.assertEqual(self.L.forbidden("/- sorry /- nested axiom -/ unsafe -/\n-- native_decide\ntheorem t : 1 = 1 := rfl"),
                         [])

    def test_axiom_lines_are_parsed(self):
        out = ("info: X.lean:1:0: 'a' does not depend on any axioms\n"
               "info: X.lean:2:0: 'b' depends on axioms: [propext,\n Quot.sound]\n")
        self.assertEqual(self.L.parse_axioms(out), {"a": [], "b": ["Quot.sound", "propext"]})

    def test_toolchain_is_pinned(self):
        cfg = self.L.config(ROOT)
        self.assertTrue(cfg.get("pinned_fingerprint"), "config/holon.json lean.pinned_fingerprint")
        ok, detail = self.L.toolchain_ok(cfg)
        self.assertTrue(ok, detail)
        ok, detail = self.L.toolchain_ok({**cfg, "pinned_fingerprint": "sha256:" + "0" * 64})
        self.assertFalse(ok)
        self.assertIn("not the pinned", detail)
        ok, detail = self.L.toolchain_ok({**cfg, "pinned_version": "4.33.0"})
        self.assertFalse(ok)

    def test_flip_canary_flips_exactly_the_marked_claim(self):
        src = (LEAN_DIR / "L_par_hdr_v2.lean").read_text(encoding="utf-8")
        flipped = self.L.flip_canary(src)
        self.assertNotEqual(flipped, src)
        self.assertEqual(sum(1 for a, b in zip(src.splitlines(), flipped.splitlines()) if a != b), 1)
        with self.assertRaises(ValueError):
            self.L.flip_canary(src.replace("-- holon:claim", ""))


def run_gate(repo: Path, checks: str):
    report = repo / "gate_report_lean.json"
    p = run_holon(["gate", "--milestone", "M0", "--root", str(repo), "--report", str(report), "--checks", checks],
                  cwd=repo)
    return p, (load_json(report) if report.exists() else None)


class TestGateCatchesLeanTampering(unittest.TestCase):
    def tampered(self, checks: str, edit) -> dict:
        repo = copy_repo()
        try:
            edit(repo)
            p, rep = run_gate(repo, checks)
            self.assertIsNotNone(rep, p.stdout[-2000:] + p.stderr[-2000:])
            self.assertNotEqual(p.returncode, 0)
            return rep
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_edited_lean_file_fails_g7(self):
        def edit(repo):
            f = repo / "gen" / "M0" / "lean" / "L_rt_go_v1.lean"
            f.write_text(f.read_text(encoding="utf-8") + "\n-- edited\n", encoding="utf-8")
        rep = self.tampered("G7", edit)
        self.assertFalse(rep["checks"]["G7"]["passed"])
        self.assertIn("L_rt_go_v1", rep["checks"]["G7"]["detail"])

    def test_unbacked_i2_fails_g7(self):
        def edit(repo):
            f = repo / "results" / "M0" / "L_par_hdr_v1.json"
            rec = json.loads(f.read_text())
            for k in rec["kernels"]:
                if k["name"] == "lean4":
                    k["result"] = "not_run"
            f.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
        rep = self.tampered("G7", edit)
        self.assertIn("independence_class I2 but lean4 not_run", rep["checks"]["G7"]["detail"])

    def test_sorry_in_a_lean_file_fails_g3(self):
        def edit(repo):
            f = repo / "gen" / "M0" / "lean" / "L_par_hdr_v0.lean"
            f.write_text(f.read_text(encoding="utf-8") + "\ntheorem extra : False := sorry\n", encoding="utf-8")
        rep = self.tampered("G3", edit)
        self.assertFalse(rep["checks"]["G3"]["passed"])
        self.assertIn("sorry", rep["checks"]["G3"]["detail"])


if __name__ == "__main__":
    unittest.main()
