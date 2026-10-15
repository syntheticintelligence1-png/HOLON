"""F32: the Base lemma library and the generic proof classes of the equivalence generator (docs/HUMAN_ANSWERS.md Q31;
holon.gen.eqlib, holon.gen.eqprove, holon.sorts.prelude3_lemmas; not preregistered: a fix iteration).

Contract:
  library        holon.gen.eqlib's text is fixed (byte-identical when generated twice), names no model and no target,
                 holds no escape hatch, and every lemma in it checks in bend2 and in BendTT (--verdict) alone, each
                 stated for all inputs of its types. Its rules and reflections name lemmas the text defines.
  prelude lemmas holon.sorts.prelude3_lemmas' text checks in both kernels against the M3 prelude, and is used only for
                 a model that holds the prelude's definitions with the prelude's own text.
  classes        on the pair of the I30 prelude (bound at 2778fa0) and the A30 prelude, the definitions F31 left
                 UNKNOWN (w_eq, w_add, w_add_ok, w_sub, u_b4, u_be4, h_get) and kw_set behind w_eq are PROVED equal by
                 holon.gen.equivalence, in bend2 and BendTT, by the F32 classes (eqprove), with no escape hatch.
  rejected       a planted non-equivalent change (a word equality that ignores its last limb; a slot write that
                 rewrites every matching entry, A30's first kw_set) is never PROVED.
  determinism    the same two models give byte-identical laws and proofs.
  agnostic       the classes and the Base library name no law, target, or model definition.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT

from holon import bend
from holon import statement_diff as SD
from holon.gen import eqlib
from holon.gen import equivalence as E

BOUND = "2778fa0"   # F30's rebinding of the I30 model: the prelude the three typed laws are bound to
HELPERS = ["w_eq", "w_add", "w_add_ok", "w_sub", "u_b4", "u_be4", "h_get", "kw_set"]


def _prelude(src: str) -> str:
    ns: dict = {}
    exec(compile(src, "prelude3", "exec"), ns)   # the module's own text: PRELUDE is assembled from fixed strings
    return "import Base\n\n" + ns["PRELUDE"]


def preludes() -> tuple[str, str]:
    old = SD.blob_at(ROOT, BOUND, "holon/sorts/prelude3.py")
    if old is None:
        raise AssertionError(f"the bound prelude at {BOUND} is not in this checkout's history")
    new = (ROOT / "holon" / "sorts" / "prelude3.py").read_text()
    return _prelude(old.decode()), _prelude(new)


def check_text(text: str, pair: str | None = None, verdict: bool = True) -> list:
    """[(kernel, ok, output)] of a library text checked alone (beside a pair module when given)."""
    tmp = Path(tempfile.mkdtemp(prefix="holon-f32-"))
    try:
        head = "import Base\n"
        if pair is not None:
            (tmp / "pair.bend").write_text(pair)
            head += "import ./pair.bend as P\n"
        (tmp / "LIB.bend").write_text(head + "\n" + text)
        out = [("bend", *_res(bend.check(tmp / "LIB.bend")))]
        if verdict and bend.verdict_enabled():
            out.append(("BendTT", *_res(bend.check_verdict(tmp / "LIB.bend"))))
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _res(r):
    return r.ok, r.out[:2000]


_CACHE: dict = {}


def prove(new: str, names=tuple(HELPERS)) -> dict:
    key = (new, names)
    if key not in _CACHE:
        old, _ = preludes()
        _CACHE[key] = E.prove(old, new, " ".join("M." + n for n in names), counter_tries=0)
    return _CACHE[key]


class TestBaseLibrary(unittest.TestCase):
    def test_fixed_and_checked_in_both_kernels(self):
        t = eqlib.text()
        self.assertEqual(t, eqlib._gen())
        self.assertEqual(bend.escape_hatches(t), [])
        defs = re.findall(r"^def ([\w.]+)\(", t, re.M)
        self.assertGreater(len(defs), 30)
        self.assertTrue(all(d.startswith("lb") for d in defs), [d for d in defs if not d.startswith("lb")])
        self.assertNotIn("P.", t)
        for name, *_ in eqlib.RULES + eqlib.REFLECT:
            self.assertIn(name, defs)
        for kernel, ok, out in check_text(t):
            self.assertTrue(ok, f"{kernel}: {out}")

    def test_a_false_lemma_is_refused(self):
        bad = eqlib.text().replace("{U32.is_lt(x, 1) == U32.is_eq(x, 0) : Bool}", "{U32.is_lt(x, 2) == U32.is_eq(x, 0) : Bool}")
        self.assertNotEqual(bad, eqlib.text())
        self.assertFalse(check_text(bad, verdict=False)[0][1])


class TestPreludeLemmas(unittest.TestCase):
    def test_checked_in_both_kernels_and_guarded(self):
        from holon.sorts import prelude3_lemmas as PL
        _, new = preludes()
        self.assertEqual(bend.escape_hatches(PL.text()), [])
        for kernel, ok, out in check_text(eqlib.text() + "\n" + PL.text(), pair=new):
            self.assertTrue(ok, f"{kernel}: {out}")
        _, items = E.parse_items(new)
        self.assertTrue(PL.applies({i.name: i for i in items}))
        old, _ = preludes()
        _, items = E.parse_items(old)
        self.assertFalse(PL.applies({i.name: i for i in items}))


class TestClasses(unittest.TestCase):
    def test_the_a30_helpers_are_proved(self):
        _, new = preludes()
        r = prove(new)
        self.assertEqual(r["status"], "PROVED", r["reason"])
        self.assertIn("bend", r["kernels"])
        if bend.verdict_enabled():
            self.assertIn("BendTT", r["kernels"])
        for f in HELPERS:
            self.assertEqual(r["lemmas"][f]["status"], "PROVED", f)
            self.assertTrue(r["lemmas"][f]["class"].startswith("eqprove"), (f, r["lemmas"][f]["class"]))
        self.assertIn("case split with reflection", r["lemmas"]["kw_set"]["class"])
        self.assertIn("lemma discovery with induction", r["lemmas"]["kw_set"]["class"])
        self.assertIn("prelude library", r["lemmas"]["h_get"]["class"])
        self.assertIn("bit by bit", r["lemmas"]["u_b4"]["class"])
        self.assertEqual(sorted(x.split()[1].rstrip(":") for x in r["laws"].splitlines() if x.startswith("law ")),
                         sorted(f"eq_{f}" for f in HELPERS))
        self.assertEqual(bend.escape_hatches(r["laws"] + r["proof"]), [])
        self.assertEqual(r["libraries"], ["holon.sorts.prelude3_lemmas"])

    def test_planted_non_equivalences_are_not_proved(self):
        _, new = preludes()
        limb = new.replace("Bool.and(U32.is_eq(a6, b6), U32.is_eq(a7, b7))", "U32.is_eq(a6, b6)")
        self.assertNotEqual(limb, new)
        r = prove(limb, ("w_eq",))
        self.assertNotEqual(r["status"], "PROVED")
        self.assertNotEqual(r["lemmas"]["w_eq"]["status"], "PROVED")
        every = new.replace("ite(W, Bool.and(eq, Bool.not(done)), v, hv)", "ite(W, eq, v, hv)")
        self.assertNotEqual(every, new)
        r = prove(every, ("kw_set",))
        self.assertNotEqual(r["status"], "PROVED")
        self.assertNotEqual(r["lemmas"]["kw_set"]["status"], "PROVED")

    def test_deterministic(self):
        _, new = preludes()
        a = prove(new, ("w_eq", "kw_set"))
        old, _ = preludes()
        b = E.prove(old, new, "M.w_eq M.kw_set", counter_tries=0)
        for k in ("pair_sha256", "laws", "proof", "status"):
            self.assertEqual(a[k], b[k], k)


class TestTargetAgnostic(unittest.TestCase):
    def test_no_law_target_or_definition_names(self):
        for rel in ("holon/gen/eqprove.py", "holon/gen/eqlib.py", "holon/gen/eqterms.py", "holon/gen/equivalence.py"):
            src = (ROOT / rel).read_text()
            for word in ("L_sort", "rollup", "morph", "Rollup", "gh_step", "kw_set", "kw_put", "h_get", "h_filt",
                         "w_add", "w_eq", "u_b4", "u_be4", "M3"):
                self.assertNotIn(word, src, f"{rel}: {word}")


if __name__ == "__main__":
    unittest.main()
