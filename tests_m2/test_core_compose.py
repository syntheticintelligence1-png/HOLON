"""Audit M2/1 F-M2-04 and F-M2-15: the core library carries the lemmas M2+ proofs need, and they use it.

F-M2-04. holon/gen/core.py's proof classes now include nat3 (three binders, for transitivity) and compose
(no case split; candidates call earlier catalog lemmas), and every class's candidates include compositions:
calls of earlier catalog lemmas found by matching their statements against the case's goal. The catalog
holds the M1 lemmas holon.gen.mproofs pasted by hand (CORE), with the same statements, and the guard-to-
subtraction shapes a SORT coercion guard rests on. M2+ generators (deadline, chain_revert) call the core
through its LAWS alias `C`; M0 and M1 keep their pasted CORE byte for byte.

F-M2-15. For M2+ the deadline class proves DISCH blocking for any conjunction (any nesting of &&) of linear
Nat comparisons: the audit's variants of the Morph kappa (a nested conjunction, a three-term sum, swapped
summands, a second deadline conjunct) and a <= form all check; a guard the class cannot show preserved
gets no proof.
"""
import copy
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json

FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
START = ["get", ["call", "nth_ch", "chs", "bc"], "s"]
KAPPA_VARIANTS = {
    "nested_conjunction": ["&&", ["&&", "inch", ["!", "paused"]], ["<", ["+", "W", START], "t"]],
    "three_term_sum": ["&&", "inch", ["<", ["+", ["+", "W", "D"], START], "t"]],
    "swapped_summands": ["&&", "inch", ["<", ["+", START, "W"], "t"]],
    "second_deadline": ["&&", "inch", ["<", ["+", "W", START], "t"], ["<", "F", "t"]],
    "le_form": ["&&", "inch", ["<=", ["+", "W", START], "t"]],
}
# not preserved by time: wait can make t < W + start false, so no proof may be generated
KAPPA_NOT_PRESERVED = ["&&", "inch", ["<", "t", ["+", "W", START]]]
GUARD_SHAPES = ["core_le_of_lt", "core_one_le_of_lt", "core_le_of_ge", "core_lt_of_gt", "core_le_of_not_lt",
                "core_le_of_not_gt", "core_le_trans", "core_lt_of_le_lt", "core_lt_of_lt_le", "core_sub_add",
                "core_sub_add_of_lt", "core_le_add_mono"]


def bend(args: list) -> tuple[int, str]:
    from tests._util import run_bend
    return run_bend([str(a) for a in args])


def _cfg():
    return holon_module("holon.bend").config(ROOT)


def _split(params: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in params:
        depth += ch in "({<"
        depth -= ch in ")}>"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return out + ([cur.strip()] if cur.strip() else [])


def _core_defs(text: str) -> dict:
    """name -> (binder names and types, claim) of the defs of mproofs.CORE."""
    out = {}
    for m in re.finditer(r"^def (core_\w+)\((.*)\) -> (.*):$", text, re.M):
        out[m.group(1)] = ([p.lstrip("+") for p in _split(m.group(2))], m.group(3))
    return out


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.C = holon_module("holon.gen.core")

    def test_new_classes_and_guard_shapes(self):
        classes = {e[4] for e in self.C.CATALOG}
        self.assertLessEqual({"nat3", "compose"}, classes)
        names = [e[0] for e in self.C.CATALOG]
        self.assertEqual(sorted(set(GUARD_SHAPES) - set(names)), [])

    def test_m1_pasted_core_lemmas_are_catalog_lemmas_with_the_same_statements(self):
        """Every lemma of mproofs.CORE (M1's hand-pasted core) is a catalog lemma: same binders, same claim."""
        M = holon_module("holon.gen.mproofs")
        cat = {e[0]: e for e in self.C.CATALOG}
        for name, (params, claim) in _core_defs(M.CORE).items():
            with self.subTest(lemma=name):
                self.assertIn(name, cat)
                _, bs, hs, cclaim, _ = cat[name]
                want = [f"{n}: {t}" for _, n, t in bs] + [f"{n}: {t}" for n, t in hs]
                self.assertEqual(params, want)
                self.assertEqual(claim.replace("M.is_true(_)", "core_is_true(_)"), cclaim)

    def test_compositions_find_earlier_lemmas(self):
        """The matcher proposes calls of earlier lemmas: binders from the goal, hypotheses from the sources or a
        nested call (depth 2)."""
        cat = self.C.CATALOG
        upto = lambda name: cat[:[e[0] for e in cat].index(name)]   # noqa: E731
        got = self.C.compositions("{Nat.add(b, Nat.sub(a, b)) == a : Nat}", [("e", "{Nat.is_lt(b, a) == True{} : Bool}")],
                                  upto("core_sub_add_of_lt"), "")
        self.assertIn("core_sub_add(a, b, core_le_of_lt(b, a, e))", got)
        got = self.C.compositions("{Nat.is_le(1n, 1n+q) == True{} : Bool}", [], upto("core_one_le_of_lt"), "")
        self.assertIn("core_le_zero(q)", got)
        got = self.C.compositions("{Bool.or(Bool.not(True{}), Nat.is_le(t, x)) == False{} : Bool}",
                                  [("e", "{Bool.and(True{}, Nat.is_lt(x, t)) == True{} : Bool}")], upto("core_kappa_site"), "")
        self.assertIn("core_lt_not_le(x, t, e)", got)


class TestCoreChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.C = holon_module("holon.gen.core")
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-core-compose-"))
        cls.names = cls.C.emit(cls.tmp, cfg=_cfg())
        cls.proof = (cls.tmp / "core" / "PROOF.bend").read_text()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def body(self, name: str) -> str:
        i = self.proof.index(f"def Laws.{name}(")
        j = self.proof.find("\n\n", i)
        return self.proof[i:j]

    def test_core_checks_under_both_kernels(self):
        p = self.tmp / "core" / "PROOF.bend"
        code, out = bend([p])
        self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-800:])
        code, out = bend([p, "--verdict"])
        self.assertIn("ALL PROOFS CHECK", out)

    def test_composed_proofs_call_earlier_lemmas(self):
        """F-M2-04: the generated proofs compose: a compose-class lemma and case bodies call earlier lemmas."""
        self.assertIn("Laws.core_sub_add(", self.body("core_sub_add_of_lt"))
        self.assertIn("Laws.core_le_of_lt(", self.body("core_sub_add_of_lt"))
        self.assertIn("Laws.core_le_zero(", self.body("core_one_le_of_lt"))
        self.assertIn("Laws.core_lt_not_le(", self.body("core_kappa_site"))
        self.assertIn("Laws.core_le_succ(", self.body("core_le_add_left"))

    def test_transitivity_is_a_three_binder_induction(self):
        for name in ("core_le_trans", "core_lt_of_le_lt", "core_lt_of_lt_le"):
            with self.subTest(lemma=name):
                b = self.body(name)
                self.assertIn("match a b c:", b)
                self.assertIn(f"Laws.{name}(p, q, r, e1, e2)", b)


class _Morph:
    """An M2+ model of the Morph rollup facts (Reach, guard-derived permissions; no oracle sidecar) with the core
    library emitted beside it, and the M2+ proof generators importing it."""

    @classmethod
    def build(cls, facts: Path, tag: str):
        P = holon_module("holon.mpipeline")
        C = holon_module("holon.gen.core")
        gen = Path(tempfile.mkdtemp(prefix=f"holon-m2dl-{tag}-"))
        C.emit(gen, cfg=_cfg())
        cm = P.CompiledMachine.build(facts, _cfg(), reach=True, anchor=FACTS)
        (gen / "model").mkdir()
        (gen / "model" / cm.source.name).write_text(cm.source.read_text())
        return gen, cm

    @staticmethod
    def proof(cm, gen: Path, lid: str, generator: str, mode: str = "import"):
        mlaws, mproofs = holon_module("holon.gen.mlaws"), holon_module("holon.gen.mproofs")
        law = load_json(ROOT / "laws" / "M1" / f"{lid}.json")
        imp = f"../model/{cm.source.name}"
        old = mproofs.CORE_MODE
        mproofs.CORE_MODE = mode
        try:
            em = mlaws.Emitter(cm.m).emit(law, imp)
            text = dict(mproofs.GENERATORS)[generator](em, cm.m, imp)
        finally:
            mproofs.CORE_MODE = old
        d = gen / lid
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()
        (d / "LAWS.bend").write_text(em.text)
        if text is not None:
            (d / "PROOF.bend").write_text(text)
        return d, text


class TestM2ProofsUseTheCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen, cls.cm = _Morph.build(FACTS, "core")
        cls.dl_dir, cls.dl = _Morph.proof(cls.cm, cls.gen, "L_disch_stale", "deadline")
        cls.cr_dir, cls.cr = _Morph.proof(cls.cm, cls.gen, "L_disch_stale_commit", "chain_revert")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.gen, ignore_errors=True)

    def test_generated_m2_proofs_call_core_lemmas_and_check(self):
        C = holon_module("holon.gen.core")
        for name, d, text in (("deadline", self.dl_dir, self.dl), ("chain_revert", self.cr_dir, self.cr)):
            with self.subTest(generator=name):
                self.assertIsNotNone(text)
                self.assertTrue(C.calls(text), "an M2+ proof calls the core through C")
                self.assertNotIn("def core_", text, "no pasted core in an M2+ proof")
                self.assertIn("import ../core/PROOF.bend as CP", text)
                code, out = bend([d / "PROOF.bend"])
                self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-1200:])
                code, out = bend([d / "PROOF.bend", "--verdict"])
                self.assertIn("ALL PROOFS CHECK", out)
        self.assertIn("core_kappa_site", C.calls(self.cr))
        self.assertLessEqual({"core_lt_of_le_lt", "core_le_add_mono", "core_lt_add"}, set(C.calls(self.dl)))

    def test_proof_fails_when_a_called_core_lemma_is_omitted(self):
        """F-M2-04: the generated proof depends on the core: leaving any lemma it calls unproved rejects it."""
        C = holon_module("holon.gen.core")
        try:
            for lemma in C.calls(self.dl):
                with self.subTest(omitted=lemma):
                    shutil.rmtree(self.gen / "core")
                    C.emit(self.gen, omit=lemma, cfg=_cfg())
                    code, out = bend([self.dl_dir / "PROOF.bend"])
                    self.assertFalse(out.strip().startswith("ALL PROOFS CHECK"), out[-600:])
                    self.assertIn("- expected :", out)
        finally:
            shutil.rmtree(self.gen / "core", ignore_errors=True)
            C.emit(self.gen, cfg=_cfg())

    def test_m1_disch_proofs_are_unchanged(self):
        """M0 and M1 keep their pasted CORE: the M1 generators regenerate gen/M1 byte for byte."""
        P, mlaws, mproofs = (holon_module(n) for n in ("holon.mpipeline", "holon.gen.mlaws", "holon.gen.mproofs"))
        cm = P.CompiledMachine.build(FACTS, _cfg())
        imp = "../model/morph_rollup.bend"
        for lid, g in (("L_disch_stale", "deadline"), ("L_disch_stale_commit", "chain_revert")):
            with self.subTest(law=lid):
                law = load_json(ROOT / "laws" / "M1" / f"{lid}.json")
                em = mlaws.Emitter(cm.m).emit(law, imp, note=load_json(ROOT / "results" / "M1" / f"{lid}.json")["statement_hash"])
                self.assertIsNone(mproofs.CORE_MODE)
                self.assertEqual(dict(mproofs.GENERATORS)[g](em, cm.m, imp), (ROOT / "gen" / "M1" / lid / "PROOF.bend").read_text())


class TestDeadlineLinear(unittest.TestCase):
    """F-M2-15: the M2+ deadline class over linear Nat conjunctions."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-kappa-"))
        cls.base = load_json(FACTS)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def variant(self, name: str, body) -> tuple:
        f = copy.deepcopy(self.base)
        f["observers"]["kappa"]["body"] = body
        p = self.tmp / f"{name}.json"
        p.write_text(json.dumps(f, indent=1))
        gen, cm = _Morph.build(p, name)
        d, text = _Morph.proof(cm, gen, "L_disch_stale", "deadline")
        return gen, d, text

    def test_kappa_variants_are_proved(self):
        for name, body in KAPPA_VARIANTS.items():
            with self.subTest(kappa=name):
                gen, d, text = self.variant(name, body)
                try:
                    self.assertIsNotNone(text, f"the deadline class does not apply to {name}")
                    code, out = bend([d / "PROOF.bend"])
                    self.assertTrue(out.strip().startswith("ALL PROOFS CHECK"), out[-1200:])
                finally:
                    shutil.rmtree(gen, ignore_errors=True)

    def test_guard_not_preserved_by_time_gets_no_proof(self):
        gen, d, text = self.variant("not_preserved", KAPPA_NOT_PRESERVED)
        shutil.rmtree(gen, ignore_errors=True)
        self.assertIsNone(text)


if __name__ == "__main__":
    unittest.main()
