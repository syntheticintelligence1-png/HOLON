"""Scanner test: emitted Lean files carry no escape hatches.

Fails on any of `sorry`, `admit`, `axiom`, `native_decide`, `implemented_by`,
`unsafe`, `partial`, `opaque`, `extern`, `noncomputable`, `#eval` in an emitted
proof file, or `decide` anywhere except inside an instantiated witness
`exact ⟨.., by decide⟩` (a fully concrete goal — never an unbounded domain).
"""

import tempfile
import unittest
from pathlib import Path

from holon.lean import scan

REPO = Path(__file__).resolve().parents[2]
GEN = REPO / "gen" / "lean"


class TestScanEmitted(unittest.TestCase):
    def test_generated_files_clean(self):
        if not GEN.is_dir():
            self.skipTest("gen/lean not generated yet")
        violations = scan.scan_dir(GEN)
        self.assertEqual(violations, [])

    def test_scanner_catches_every_banned_construct(self):
        bad = {
            "sorry": "theorem t : True := by\n  sorry",
            "admit": "theorem t : True := by\n  admit",
            "axiom": "axiom hold : True",
            "native_decide": "theorem t : 1 = 1 := by\n  native_decide",
            "implemented_by": "def f : Nat := 0\n@[implemented_by f]\ndef g : Nat := 0",
            "unsafe": "unsafe def f : Nat := 0",
            "partial": "partial def f : Nat := f",
            "opaque": "opaque f : Nat",
            "extern": "@[extern \"x\"] def f : Nat := 0",
            "noncomputable": "noncomputable def f : Nat := 0",
            "eval": "#eval 1 + 1",
            "decide_unbounded": "theorem t (n : Nat) : n + 0 = n := by\n  decide",
            "decide_forall": "theorem t : forall (n : Nat), n = n := by\n  exact fun n => by decide",
        }
        for name, text in bad.items():
            vs = scan.scan_text(text)
            self.assertTrue(vs, f"{name} not flagged")

    def test_scanner_allows_witness_decide(self):
        ok = "theorem cl : exists (b : Nat), b = 1 := by\n  exact ⟨1, by decide⟩"
        self.assertEqual(scan.scan_text(ok), [])


if __name__ == "__main__":
    unittest.main()
