"""I13: the sort grammar and affine table, the minimal-core extractor, and the shape of holon/sorts/
(whitepaper §7.1, §7.2, §7.7 steps 2 and 4; BUILD_PLAN I13). Contract: tests_m2/test_sorts_morph.py docstring.

API these tests read:
  holon/sorts/{grammar, constraints, flow, solve, core, unions}.py all exist and import.
  holon.sorts.grammar.parse(text) -> object; holon.sorts.grammar.render(object) -> text
      render(parse(s)) == s for every canonical sort string; a union renders its members in lexicographic
      order joined by " + ".
  holon.sorts.grammar.affine(op, a, b) -> str | None
      op is "+" or "-", a and b are sort strings; the result sort string, or None when the combination is
      ill-sorted. The rows of the §7.2 table are pinned below. "+" is commutative. Time is a torsor over the
      group Dur and Idx[k] over the group Cnt[k], so the group sums are pinned too (Dur + Dur = Dur,
      Cnt[k] + Cnt[k] = Cnt[k]), and Idx[k] + Idx[k] is ill-sorted like Time + Time.
  holon.sorts.core.minimal_core(items: list, satisfiable: Callable[[list], bool]) -> list
      items: an unsatisfiable list (any element type, hashable or not); satisfiable: an oracle on sublists.
      Returns a sublist of items, in their original order and without repeats, that is unsatisfiable and
      irreducible (removing any one element makes it satisfiable), found by deletion (QuickXplain). The
      result depends only on the items' order and the oracle. A satisfiable input raises ValueError.

Static checks on holon/sorts/*.py: pure Python (imports only the standard library and holon; no subprocess,
ctypes, os.system or os.popen: the solver is an in-process union-find, no external solver), no Morph
identifiers (the I6 list) and no quoted Morph field names (no special-casing of the target's variables), and
no use of the test oracle tests/reference/ (AGENTS rule 5).
"""
import ast
import re
import sys
import unittest

from tests_m2._m2 import ROOT, holon_module

MODULES = ("grammar", "constraints", "flow", "solve", "core", "unions")
SORTS_DIR = ROOT / "holon" / "sorts"
# The I6 list of Morph identifiers (tests_m2/test_target_agnostic.py), repeated here.
MORPH = re.compile(r"\b(win_at|win_last|nth_ch|set_ch|bump_f|any_open|clear_chs|zero_csr|set_last_csr|tags_exact|"
                   r"hdr_of|empty_entry|empty_ch|HEntry|HCh|HBD|AGG_BASE|blob_count|commitBatch|commitState|"
                   r"commitBatchWithProof|revertBatch|challengeState|proveState|finalizeBatch|setPause|sendMessage|"
                   r"batchdata|Rollup|Morph|morph)\b")
# Morph fact names as string literals: a generic solver never names the target's variables.
FIELDS = re.compile(r"[\"'](qpend|qlen|cstart|prt|btot|s_bvh|s_tag|s_csr|s_bd|bvh|tot|lfi|enq|inch|chs|win|"
                    r"Entry|Ch|BD|proofWindow|rollupDelayPeriod|finalizationPeriodSeconds|pendingQueueIndex)[\"']")
BANNED_MODULES = {"subprocess", "ctypes", "multiprocessing"}

AFFINE_ROWS = [
    ("-", "Time", "Time", "SDur"),
    ("+", "Time", "Dur", "Time"),
    ("+", "Dur", "Time", "Time"),
    ("+", "Time", "Time", None),
    ("+", "Dur", "Dur", "Dur"),
    ("-", "Idx[queue]", "Idx[queue]", "SCnt[queue]"),
    ("+", "Idx[queue]", "Cnt[queue]", "Idx[queue]"),
    ("+", "Cnt[queue]", "Idx[queue]", "Idx[queue]"),
    ("-", "Idx[queue]", "Cnt[queue]", "SIdx[queue]"),
    ("+", "Cnt[queue]", "Cnt[queue]", "Cnt[queue]"),
    ("+", "Idx[queue]", "Idx[queue]", None),
    ("+", "Idx[queue]", "Cnt[batch]", None),
    ("-", "Idx[queue]", "Idx[batch]", None),
    ("-", "Idx[queue]", "Cnt[batch]", None),
]
CANONICAL = ["Time", "Dur", "SDur", "Idx[queue]", "Idx[queue]_fin", "Idx[queue]_inc", "SIdx[queue]", "Cnt[queue]",
             "SCnt[queue]", "Prin[owner]", "Amt[eth]", "Dig[VH]", "Dig[Agg]", "Ver", "Bool", "Mach(64)",
             "Nat (unrefined)", "Dig[Agg] + Dig[VH]"]


class TestModules(unittest.TestCase):
    def test_the_six_modules_import(self):
        for n in MODULES:
            with self.subTest(module=n):
                holon_module(f"holon.sorts.{n}")

    def test_sorts_code_is_pure_python_and_target_agnostic(self):
        files = sorted(SORTS_DIR.glob("*.py"))
        self.assertTrue({f"{n}.py" for n in MODULES} <= {f.name for f in files},
                        f"holon/sorts/ holds {[f.name for f in files]}, not the six modules")
        std = set(sys.stdlib_module_names)
        for f in files:
            text = f.read_text(encoding="utf-8")
            with self.subTest(file=f.name):
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Import):
                        names = [a.name.split(".")[0] for a in node.names]
                    elif isinstance(node, ast.ImportFrom):
                        names = [] if node.level else [(node.module or "").split(".")[0]]
                    else:
                        continue
                    for n in names:
                        self.assertTrue(n == "holon" or n in std, f"import of {n}: not the standard library or holon")
                        self.assertNotIn(n, BANNED_MODULES)
                self.assertNotRegex(text, r"\bos\.(system|popen)\b")
                self.assertIsNone(MORPH.search(text), f"Morph identifier in {f.name}")
                self.assertIsNone(FIELDS.search(text), f"quoted Morph field name in {f.name}")
                self.assertNotIn("tests.reference", text)
                self.assertNotIn("tests/reference", text)


class TestGrammar(unittest.TestCase):
    def setUp(self):
        self.G = holon_module("holon.sorts.grammar")

    def test_affine_table(self):
        """§7.2: Time - Time = SDur, Time + Dur = Time, Time + Time ill-sorted, Idx - Idx = SCnt, Idx + Cnt = Idx,
        Idx - Cnt = SIdx, and any operation mixing index families is ill-sorted; plus the group sums of the two
        torsors' groups (Dur + Dur, Cnt + Cnt)."""
        for op, a, b, want in AFFINE_ROWS:
            with self.subTest(expr=f"{a} {op} {b}"):
                self.assertEqual(self.G.affine(op, a, b), want)

    def test_render_parse_round_trip(self):
        for s in CANONICAL:
            with self.subTest(sort=s):
                self.assertEqual(self.G.render(self.G.parse(s)), s)

    def test_union_renders_its_members_in_lexicographic_order(self):
        self.assertEqual(self.G.render(self.G.parse("Dig[VH] + Dig[Agg]")), "Dig[Agg] + Dig[VH]")


class TestMinimalCore(unittest.TestCase):
    ITEMS = ["a", "b", "c", "d", "e", "f", "g", "h"]

    @staticmethod
    def sat(xs) -> bool:
        s = set(xs)
        return not ({"b", "e"} <= s or {"c", "d", "g"} <= s)

    def setUp(self):
        self.C = holon_module("holon.sorts.core")

    def check_core(self, items, core, sat):
        self.assertFalse(sat(core), "the core is unsatisfiable")
        for k in range(len(core)):
            self.assertTrue(sat(core[:k] + core[k + 1:]), f"core minus element {k} is still unsatisfiable")
        pos = [next(i for i, x in enumerate(items) if x is c) for c in core]
        self.assertEqual(pos, sorted(set(pos)), "a sublist in the original order, without repeats")

    def test_minimal_core_is_unsatisfiable_irreducible_ordered_and_deterministic(self):
        core = self.C.minimal_core(list(self.ITEMS), self.sat)
        self.check_core(self.ITEMS, core, self.sat)
        self.assertIn(core, (["b", "e"], ["c", "d", "g"]))
        self.assertEqual(self.C.minimal_core(list(self.ITEMS), self.sat), core, "deterministic")

    def test_unhashable_items(self):
        items = [{"id": x} for x in self.ITEMS]

        def sat(ds):
            return self.sat([d["id"] for d in ds])
        core = self.C.minimal_core(items, sat)
        self.check_core(items, core, sat)

    def test_satisfiable_input_is_rejected(self):
        with self.assertRaises(ValueError):
            self.C.minimal_core(["a", "f", "h"], self.sat)


if __name__ == "__main__":
    unittest.main()
