"""F34: what Bend 2 does with imports (not preregistered: a fix iteration's probe, kept as a test).

The question F34 had to answer before splitting an equivalence proof into modules: when a file imports another, does
the checker trust the imported definitions or check them again? The answer decides whether a DAG of proof modules
can be cheaper to check than one file.

Contract (each a behaviour of the pinned checker, observed by running it; docs/iterations/F34.md has the evidence):
  recheck        bend2 checks every definition of every imported file again, in the same process, each time a file
                 that imports it is checked. A wrong proof in an imported module fails the importing file, with the
                 imported definition's location (bend2 builds one book from the file and all its imports and checks
                 the whole book; only Base is exempt).
  verdict        BendTT (--verdict) follows imports the same way: the kernel text it checks (bend -o F.bendtt) holds
                 every imported definition, and a wrong imported proof fails --verdict too.
  several        a PROOF.bend may import several lemma modules beside ./LAWS.bend; a module two of them import (a
                 diamond) is loaded once, and the law is accepted in both kernels.
So a module's check costs at least the check of everything it imports: the top module of a proof DAG costs as much as
the one-file proof. Splitting does not move the 120 s per-file budget or the 180 s bend timeout.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from holon import bend

S = """import Base

def dbl(n: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      2n+dbl(p)
"""

A_OK = """import Base
import ./S.bend as S

def lem_a(x: Nat) -> {Nat.add(x, 0n) == x : Nat}:
  match x:
    case 0n:
      {==}
    case 1n+p:
      %lem_a(p) : {1n+Nat.add(p, 0n) == 1n+_ : Nat}
      {==}
"""

# the same statement with a proof bend2 refuses (Nat.add(x, 0n) does not reduce to x on a variable)
A_BAD = """import Base
import ./S.bend as S

def lem_a(x: Nat) -> {Nat.add(x, 0n) == x : Nat}:
  {==}
"""

B = """import Base
import ./S.bend as S

def lem_b() -> {S.dbl(2n) == 4n : Nat}:
  {==}
"""

LAWS = """import Base
import ./S.bend as S

law both:
  {S.dbl(Nat.add(2n, 0n)) == 4n : Nat}
"""

PROOF = """import Base
import ./S.bend as S
import ./LAWS.bend as Laws
import ./A.bend as A
import ./B.bend as B

def Laws.both():
  %A.lem_a(2n) : {S.dbl(Nat.add(2n, 0n)) == S.dbl(_) : Nat}
  B.lem_b()
"""

USE = """import Base
import ./A.bend as A

def use(x: Nat) -> {Nat.add(x, 0n) == x : Nat}:
  A.lem_a(x)
"""


class TestBendImports(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="holon-f34-imports-"))

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def write(self, a: str):
        for name, text in (("S.bend", S), ("A.bend", a), ("B.bend", B), ("LAWS.bend", LAWS), ("PROOF.bend", PROOF),
                           ("USE.bend", USE)):
            (self.d / name).write_text(text)

    def test_an_imported_module_is_checked_again(self):
        self.write(A_OK)
        self.assertTrue(bend.check(self.d / "USE.bend").ok)
        self.write(A_BAD)
        r = bend.check(self.d / "USE.bend")
        self.assertFalse(r.ok, "bend2 accepted a file importing a module with a wrong proof: imports are trusted")
        self.assertIn("Location: lem_a", r.out, "the failure is the imported definition's")

    def test_the_kernel_text_holds_every_imported_definition(self):
        self.write(A_OK)
        r = bend.run(["PROOF.bend", "-o", "PROOF.bendtt"], cwd=self.d)
        self.assertEqual(r.code, 0, r.out)
        tt = (self.d / "PROOF.bendtt").read_text()
        for name in ("A.lem_a :", "B.lem_b :", "S.dbl :", "LAWS.both :"):
            self.assertIn(name, tt, f"BendTT's text of PROOF.bend lacks {name!r}: the kernel would not check it")

    def test_a_law_file_imports_several_lemma_modules(self):
        self.write(A_OK)
        self.assertTrue(bend.check(self.d / "PROOF.bend").ok)
        if bend.verdict_enabled():
            self.assertTrue(bend.check_verdict(self.d / "PROOF.bend").ok)
        self.write(A_BAD)
        self.assertFalse(bend.check(self.d / "PROOF.bend").ok)
        if bend.verdict_enabled():
            self.assertFalse(bend.check_verdict(self.d / "PROOF.bend").ok)


if __name__ == "__main__":
    unittest.main()
