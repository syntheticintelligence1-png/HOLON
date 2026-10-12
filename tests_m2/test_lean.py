"""I9: a Lean 4 second kernel for M0, emitted from the IR by emitters independent of the Bend ones
(whitepaper §8.8, §8.9; BUILD_PLAN I9; closes D-d for M0).

gen/M0/lean/<law_id>.lean holds, per M0 law, the model (Hdr as a structure of byte fields), the
statement (with the IR statement hash in a doc comment) and its proof: the law for a PROVED law, the
counter-law at the recorded witness for a REFUTED one. `python -m holon lean --milestone M0` (holon/lean.py)
regenerates and checks them in a temporary lake project with Lean v4.34.0 and no Mathlib, and audits
`#print axioms`. Records list the Lean kernel in kernels[] and get independence_class I2 only when the
Bend and Lean verdicts agree.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, laws, load_json, records, run_holon

LEAN_DIR = ROOT / "gen" / "M0" / "lean"
ALLOWED_AXIOMS = {"propext", "Quot.sound"}
FORBIDDEN = re.compile(r"\b(sorry|admit|native_decide|bv_decide|axiom|unsafe|implemented_by|extern)\b")


def lean_files() -> dict[str, Path]:
    return {p.stem: p for p in sorted(LEAN_DIR.glob("L_*.lean"))}


class TestLeanFiles(unittest.TestCase):
    def test_one_file_per_m0_law_with_its_statement_hash(self):
        fs = lean_files()
        self.assertEqual(set(fs), set(laws("M0")))
        reg = load_json(ROOT / "laws" / "M0" / "REGISTRY.json")["statements"]
        for lid, p in fs.items():
            with self.subTest(law=lid):
                text = p.read_text(encoding="utf-8")
                self.assertIn(reg[lid], text, "the IR statement hash is in a doc comment")
                self.assertIsNone(FORBIDDEN.search(re.sub(r"--[^\n]*|/-.*?-/", "", text, flags=re.S)))

    def test_lean_emitters_do_not_import_the_bend_emitters(self):
        for rel in ("holon/gen/lean_model.py", "holon/gen/lean_laws.py", "holon/gen/lean_proofs.py"):
            with self.subTest(file=rel):
                src = (ROOT / rel).read_text(encoding="utf-8")
                self.assertNotRegex(src, r"from \.(laws|proofs|model) import|import holon\.gen\.(laws|proofs|model)\b|"
                                         r"from holon\.gen\.(laws|proofs|model) import")


class TestLeanVerdicts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc = run_holon(["lean", "--milestone", "M0", "--json"], timeout=1800)
        cls.report = json.loads(cls.proc.stdout) if cls.proc.returncode == 0 else None

    def test_every_file_checks_with_only_standard_axioms(self):
        """I9-P1, I9-P2: the 5 PROVED laws are re-proved and the 3 counter-laws check."""
        self.assertIsNotNone(self.report, self.proc.stdout[-2000:] + self.proc.stderr[-2000:])
        res = self.report["laws"]
        self.assertEqual(set(res), set(laws("M0")))
        for lid, r in res.items():
            with self.subTest(law=lid):
                self.assertEqual(r["result"], "checked", r)
                self.assertLessEqual(set(r["axioms"]), ALLOWED_AXIOMS)
                self.assertLessEqual(r["seconds"], 120)

    def test_cross_kernel_agreement(self):
        """I9-P3: 8/8 records list both kernels as checked and get independence class I2."""
        for lid, rec in records("M0").items():
            with self.subTest(law=lid):
                ks = {k["name"]: k for k in rec["kernels"]}
                self.assertEqual(ks["lean4"]["result"], "checked")
                self.assertEqual(ks["lean4"]["version"], "4.34.0")
                self.assertEqual(rec["independence_class"], "I2")

    def test_flipped_equality_canary_is_rejected(self):
        """I9-P4."""
        L = holon_module("holon.lean")
        tmp = Path(tempfile.mkdtemp(prefix="holon-lean-canary-"))
        try:
            src = (LEAN_DIR / "L_par_hdr_v0.lean").read_text(encoding="utf-8")
            r = L.check_text(L.flip_canary(src), tmp)
            self.assertNotEqual(r["result"], "checked", r)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
