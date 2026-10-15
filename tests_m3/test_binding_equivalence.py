"""F31: the equivalence generator for binding changes (holon.gen.equivalence; not preregistered: a fix iteration).

A law is bound to the kernel form of every definition its statement reaches. A binding_change (an emitted definition
changed under a fixed statement) is accepted unsigned only with a generated, kernel-checked equivalence, re-derived
from the entry by holon.statement_diff and never taken from it.

Contract:
  criterion       every root the emitted statement names (holon.bindings' roots) is unchanged in kernel form, or
                  proven extensionally equal old vs new on every input of its types (a function: {o__f(x) == f(x)}
                  for all x; an inductive family: transport both ways); helpers may differ freely. Nothing weaker.
  pair module     the new model verbatim plus the old definitions whose kernel form differs or reaches a difference,
                  renamed o__<name>; its BendTT entries, prefix removed, must be exactly the two models' (linkage).
  accepted        a planted equivalent refactor (an affine list recursion, a fixed-limb operation over bits written
                  by cases, a definition changed only in its callees, an inductive family over a changed step) is
                  PROVED by bend and by BendTT (--verdict) when available.
  rejected        a planted non-equivalent change, one bit (a Boolean result flipped on one input), one limb (a word
                  comparison that ignores a limb), one dropped field (a step that no longer records an entry), is
                  never PROVED: the attempts carry the kernel's message (SOME PROOFS FAIL, expected / observed), and
                  where a concrete input separates old and new the counter-law at that input is accepted (REFUTED).
  supplied proof  a binding_change entry never counts for its own proof or equivalence: check_entry derives it, the
                  acceptance record comes from the check's result only, and a committed line without a kernel-checked
                  equivalence (or a verified signature) is a problem.
  determinism     the same two models and statement give byte-identical pair module, laws and proofs.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT

from holon import bend
from holon import statement_diff as SD
from holon.gen import equivalence as E

OLD = """import Base

def ite(-A: Data, c: Bool, a: A, b: A) -> A:
  match c:
    case True{}:
      a
    case False{}:
      b

type W is Data:
  W{l0: Bool, l1: Bool, l2: Bool}

type KW is Data:
  KW{k: U32, v: U32}

type St is Data:
  St{kv: List<&2, KW>, n: U32}

def b_eq(a: Bool, b: Bool) -> Bool:
  Bool.not(Bool.xor(a, b))

def w_eq(a: W, b: W) -> Bool:
  match a b:
    case W{a0, a1, a2} W{b0, b1, b2}:
      Bool.and(b_eq(a0, b0), Bool.and(b_eq(a1, b1), b_eq(a2, b2)))

def kw_get(+xs: List<&2, KW>, +k: U32) -> U32:
  match xs:
    case Nil{}:
      0
    case Con{+h, +t}:
      match h:
        case KW{+hk, +hv}:
          ite(U32, U32.is_eq(hk, k), hv, kw_get(t, k))

def st_get(s: St, +k: U32) -> U32:
  match s:
    case St{kv, n}:
      kw_get(kv, k)

def look(s: St, +k: U32, a: W, b: W) -> U32:
  ite(U32, w_eq(a, b), st_get(s, k), 7)

def step(+s: St, +k: U32) -> St:
  match s:
    case St{+kv, +n}:
      St{Con{KW{k, (n + 1 : U32)}, kv}, kw_get(kv, k)}

def s0() -> St:
  St{Nil{}, 0}

type Reach<-s: St> is Type:
  R0{e: {s == s0() : St}}
  RS{k: U32, p: St, r: Reach<p>, e: {s == step(p, k) : St}}
"""

# the refactor: b_eq by cases, kw_get recursed on affinely, the counter incremented with U32.inc
NEW = (OLD.replace("""def b_eq(a: Bool, b: Bool) -> Bool:
  Bool.not(Bool.xor(a, b))""", """def b_eq(a: Bool, b: Bool) -> Bool:
  match a:
    case True{}:
      b
    case False{}:
      Bool.not(b)""")
       .replace("def kw_get(+xs: List<&2, KW>, +k: U32) -> U32:", "def kw_get(xs: List<&2, KW>, +k: U32) -> U32:")
       .replace("    case Con{+h, +t}:\n      match h:\n        case KW{+hk, +hv}:",
                "    case Con{h, t}:\n      match h:\n        case KW{hk, hv}:")
       .replace("(n + 1 : U32)", "U32.inc(n)"))

PLANTED = {
    # one bit: b_eq(False, False) is now False
    "bit": NEW.replace("    case False{}:\n      Bool.not(b)", "    case False{}:\n      Bool.and(Bool.not(b), False{})"),
    # one limb: the word comparison ignores l2
    "limb": NEW.replace("Bool.and(b_eq(a1, b1), b_eq(a2, b2))", "Bool.and(b_eq(a1, b1), True{})"),
    # one dropped field: the step no longer records its entry
    "field": NEW.replace("St{Con{KW{k, U32.inc(n)}, kv}, kw_get(kv, k)}", "St{kv, kw_get(kv, k)}"),
}

STATEMENT = """law l_look:
  for +s: M.St
  for r: M.Reach<s>
  for +k: U32
  for +a: M.W
  for +b: M.W
  {M.look(s, k, a, b) == 0 : U32}
"""

_CACHE: dict = {}


def prove(new: str) -> dict:
    if new not in _CACHE:
        _CACHE[new] = E.prove(OLD, new, STATEMENT, counter_tries=300)
    return _CACHE[new]


def roots(r: dict) -> dict:
    return {i["root"]: i for i in r["roots"]}


class TestCriterion(unittest.TestCase):
    def test_roots_are_what_the_statement_names(self):
        pm = E.pair_module(OLD, NEW, STATEMENT)
        self.assertEqual(pm.roots, ["Reach", "St", "W", "look"])
        # the old side is copied for every definition that changed or reaches a change, and only for those
        self.assertEqual(pm.renamed, ["b_eq", "w_eq", "kw_get", "st_get", "look", "step", "Reach"])
        self.assertNotIn("ite", pm.renamed)
        self.assertNotIn("s0", pm.renamed)

    def test_linkage_ties_the_pair_module_to_both_models(self):
        pm = E.pair_module(OLD, NEW, STATEMENT)
        ep = E.kernel_entries_of(pm.text)
        self.assertEqual(E.linkage(pm, ep), [])
        # a pair module whose old side is not the old model is refused
        bad = E.PairModule(**{**pm.__dict__, "text": pm.text.replace("Bool.not(Bool.xor(a, b))", "Bool.xor(a, b)")})
        self.assertTrue(any("o__b_eq" in p or "b_eq" in p for p in E.linkage(bad, E.kernel_entries_of(bad.text))))


class TestEquivalentRefactor(unittest.TestCase):
    def test_accepted_in_both_kernels(self):
        r = prove(NEW)
        self.assertEqual(r["status"], "PROVED", r["reason"])
        self.assertEqual(r["linkage"], [])
        self.assertIn("bend", r["kernels"])
        if bend.verdict_enabled():
            self.assertIn("BendTT", r["kernels"])
        rs = roots(r)
        self.assertEqual(rs["St"]["class"], "unchanged")
        self.assertEqual(rs["W"]["class"], "unchanged")
        self.assertEqual(rs["Reach"]["class"], "family")
        self.assertEqual(rs["look"]["class"], "congruence")
        self.assertEqual(r["lemmas"]["kw_get"]["class"], "induction")
        self.assertEqual(r["lemmas"]["b_eq"]["class"], "normalize")
        self.assertIn("Base identities", r["lemmas"]["step"]["class"])
        # the law file states exactly the root laws, and nothing is an escape hatch
        self.assertEqual(sorted(x.split()[1].rstrip(":") for x in r["laws"].splitlines() if x.startswith("law ")),
                         ["eq_look", "from_Reach", "to_Reach"])
        self.assertEqual(bend.escape_hatches(r["laws"] + r["proof"]), [])


class TestNonEquivalent(unittest.TestCase):
    def test_one_bit_is_refuted(self):
        r = prove(PLANTED["bit"])
        self.assertNotEqual(r["status"], "PROVED")
        self.assertEqual(r["status"], "REFUTED", r["reason"])
        self.assertEqual(roots(r)["look"]["status"], "REFUTED")
        att = "\n".join(r["lemmas"]["b_eq"]["attempts"])
        self.assertIn("SOME PROOFS FAIL", att)
        self.assertIn("expected", att)
        c = r["counters"]["look"]
        self.assertEqual(c["status"], "REFUTED")
        self.assertIn("bend", c["kernels"])
        self.assertIn("!=", c["laws"])

    def test_one_limb_is_refuted(self):
        r = prove(PLANTED["limb"])
        self.assertEqual(r["status"], "REFUTED", r["reason"])
        self.assertIn("observed", "\n".join(r["lemmas"]["w_eq"]["attempts"]))
        self.assertEqual(r["counters"]["w_eq"]["status"], "REFUTED")

    def test_one_dropped_field_is_rejected(self):
        r = prove(PLANTED["field"])
        self.assertNotEqual(r["status"], "PROVED")
        self.assertNotEqual(roots(r)["Reach"]["status"], "PROVED")
        self.assertIn("SOME PROOFS FAIL", "\n".join(r["lemmas"]["step"]["attempts"]))
        self.assertEqual(r["counters"]["step"]["status"], "REFUTED")
        self.assertIn("step", roots(r)["Reach"]["reason"])


class TestSuppliedProofNeverCounts(unittest.TestCase):
    LAW = {"law_id": "L_x", "milestone": "M3", "ir_version": "holon-ir/0.3", "facts": "facts/x.json",
           "statement": {"binders": [], "claim": {"eq": [{"nat": 0}, {"nat": 0}]}}}

    def entry(self, **kw):
        return {"kind": "binding_change", "law_id": "L_x", "old": self.LAW, "new": self.LAW, **kw}

    def test_entry_with_a_proof_and_no_derivation_is_rejected(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            fake = {"status": "PROVED", "kernels": ["bend", "BendTT"], "laws": "law x: ...", "proof": "def ..."}
            r = SD.check_entry(self.entry(proof="def Laws.eq_x(): {==}", equivalence=fake), tmp)
            self.assertFalse(r["ok"])
            self.assertIn("supplied proof does not count", r["reason"])
            r = SD.check_entry(self.entry(milestone="M3", bound_commit="0" * 40, defs=["f"], equivalence=fake), tmp)
            self.assertFalse(r["ok"])
            self.assertIn("git history", r["reason"])
        finally:
            shutil.rmtree(tmp)

    def test_acceptance_comes_from_the_check_only(self):
        e = self.entry(equivalence={"status": "PROVED", "kernels": ["bend"]})
        acc = SD.acceptance(e, {"ok": True, "reason": "", "implication": None}, ROOT)
        self.assertNotIn("equivalence", acc)

    def test_committed_line_needs_a_checked_equivalence(self):
        e = self.entry(milestone="M3", bound_commit="0" * 40, defs=["f"])
        why = SD._verify_committed(e, {"kind": "binding_change", "facts": {}}, "HEAD", ROOT)
        self.assertIn("no kernel-checked equivalence", why)
        why = SD._verify_committed(e, {"kind": "binding_change", "facts": {},
                                       "equivalence": {"kernels": ["bend"], "generator": "someone",
                                                       "bound_commit": "0" * 40}}, "HEAD", ROOT)
        self.assertIn("another generator", why)


class TestDeterminism(unittest.TestCase):
    def test_byte_identical(self):
        a = prove(NEW)
        b = E.prove(OLD, NEW, STATEMENT, counter_tries=300)
        for k in ("pair_sha256", "laws", "proof", "status"):
            self.assertEqual(a[k], b[k], k)
        self.assertEqual(json.dumps(a["lemmas"], sort_keys=True), json.dumps(b["lemmas"], sort_keys=True))
        c1 = prove(PLANTED["limb"])["counters"]["w_eq"]
        c2 = E.prove(OLD, PLANTED["limb"], STATEMENT, counter_tries=300)["counters"]["w_eq"]
        self.assertEqual(c1["proof"], c2["proof"])


class TestTargetAgnostic(unittest.TestCase):
    def test_no_law_ids_or_target_names(self):
        src = (ROOT / "holon" / "gen" / "equivalence.py").read_text()
        for word in ("L_sort", "rollup", "morph", "Rollup", "gh_step", "kw_set", "h_get", "M3"):
            self.assertNotIn(word, src, word)


if __name__ == "__main__":
    unittest.main()
