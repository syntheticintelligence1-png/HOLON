"""F35: congruence lemmas over chains of lets keep every motive to one let's value (not preregistered: a fix iteration).

F34 found that BendTT's pinned fuel refuses the storage-write congruence lemmas of the M3 cone: each motive repeated
the whole chain o1..o6 with every let inlined (each let names the previous one twice), 142 to 200 KB per lemma. Q34
keeps the fuel; the generator must make the lemmas smaller.

Contract:
  shape       a leaf reached through a chain of lets is proved one let at a time: per let, a helper t (the driver's
              rest of the chain as a function of that let's value), a helper u (the other side's), and a lemma
              {u(xs, v) == t(xs, v)} over variables; no motive holds a let's value inlined into a later one.
  generic     chosen by the shape of the definition (lets ending in a leaf), never by a name; a chain whose
              variables' types are not evident is inlined as before, and the inlined text stays a candidate class
              (congruence-flat) after every other.
  verdict     the planted chain (a value that each let names twice, through a changed callee) is PROVED by bend2
              and by BendTT (--verdict, when available); a planted non-equivalent chain is REFUTED by a
              counter-witness, never PROVED.
  determinism two runs give byte-identical proofs.
  deferral    once a batch check of the lemma search hits bend.timeout_s, the remaining candidates are deferred:
              unchecked, never cached, decided by the final whole-proof check alone (a wrong one is refused there and
              searched again); with every batch check timing out, the planted chain is still PROVED by the final check
              and the planted difference never is.
  family      a family index that every recursive field passes on unchanged (Reach<kh, p> of Reach<-kh, -s>) is
              bound reusable by the transport laws (the proof passes it to a lemma), the others erased; such a
              family over a changed step is PROVED in both kernels.
  Q34         equivalence.timeout_s (900) bounds only the final whole-proof check and G2's re-check, each kernel; a
              check that hits it is UNKNOWN; a checker crash is retried and logged, never acceptance.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest import mock

from tests_m3._m3 import ROOT  # noqa: F401  (puts the repository on sys.path)

from holon import bend
from holon.gen import eqsearch as ES
from holon.gen import equivalence as E

OLD = """import Base

type S is Data:
  S{a: Bool, n: U32}

def s_a(x: S) -> Bool:
  match x:
    case S{a, n}:
      a

def s_n(x: S) -> U32:
  match x:
    case S{a, n}:
      n

def b_eq(a: Bool, b: Bool) -> Bool:
  Bool.not(Bool.xor(a, b))

def w(+x: S) -> S:
  +k = {b_eq(s_a(x), True{}) : Bool}
  +o1 = {b_eq(k, b_eq(k, False{})) : Bool}
  +o2 = {b_eq(o1, b_eq(o1, k)) : Bool}
  +o3 = {b_eq(o2, b_eq(o2, k)) : Bool}
  +o4 = {b_eq(o3, b_eq(o3, k)) : Bool}
  S{o4, s_n(x)}
"""

# b_eq by cases (proved by normalize); w matched on its argument instead of projected (proved by the chain)
NEW = (OLD.replace("""def b_eq(a: Bool, b: Bool) -> Bool:
  Bool.not(Bool.xor(a, b))""", """def b_eq(a: Bool, b: Bool) -> Bool:
  match a:
    case True{}:
      b
    case False{}:
      Bool.not(b)""")
       .replace("""def w(+x: S) -> S:
  +k = {b_eq(s_a(x), True{}) : Bool}""", """def w(x: S) -> S:
  match x:
    case S{+a, +n}:
      +k = {b_eq(a, True{}) : Bool}""")
       .replace("""  +o1 = {b_eq(k, b_eq(k, False{})) : Bool}
  +o2 = {b_eq(o1, b_eq(o1, k)) : Bool}
  +o3 = {b_eq(o2, b_eq(o2, k)) : Bool}
  +o4 = {b_eq(o3, b_eq(o3, k)) : Bool}
  S{o4, s_n(x)}""", """      +o1 = {b_eq(k, b_eq(k, False{})) : Bool}
      +o2 = {b_eq(o1, b_eq(o1, k)) : Bool}
      +o3 = {b_eq(o2, b_eq(o2, k)) : Bool}
      +o4 = {b_eq(o3, b_eq(o3, k)) : Bool}
      S{o4, n}"""))

# one let changed: o4 no longer names k, so it is True on every input where the old o4 is k (that is, a): old and new
# differ exactly when a is False. (A change to an earlier let would not differ anywhere: b_eq(x, b_eq(x, y)) is y, so
# each let's value is k whatever the previous let holds.)
PLANTED = NEW.replace("      +o4 = {b_eq(o3, b_eq(o3, k)) : Bool}", "      +o4 = {b_eq(o3, b_eq(o3, True{})) : Bool}")

STATEMENT = """law l_w:
  for +x: M.S
  {M.w(x) == x : M.S}
"""

_CACHE: dict = {}


def prove(new: str) -> dict:
    if new not in _CACHE:
        _CACHE[new] = E.prove(OLD, new, STATEMENT, counter_tries=300, cache=ES.LemmaCache(None))
    return _CACHE[new]


def lemma_text(r: dict, f: str) -> str:
    """The proof text of q_<f> and its helpers, cut from the whole PROOF.bend."""
    out, keep = [], False
    for ln in (r["proof"] or "").splitlines():
        if ln.startswith("def "):
            keep = ln.startswith(f"def {E.LEMMA}{f}(") or ln.startswith(f"def {E.LEMMA}{f}__")
        if keep:
            out.append(ln)
    return "\n".join(out)


class TestChainShape(unittest.TestCase):
    def setUp(self):
        self.pm = E.pair_module(OLD, NEW, STATEMENT)
        self.gen = E.Gen(self.pm)

    def lemmas(self):
        return {"b_eq": "q_b_eq", "w": "q_w"}

    def test_one_lemma_per_let_and_no_inlined_chain(self):
        text, ih = self.gen.congruence("w", "q_w", self.lemmas(), "new")
        self.assertFalse(ih)
        names = re.findall(r"^def (q_w__[a-z]\d+_\d+)\(", text, re.M)
        self.assertTrue(any(n.startswith("q_w__l") for n in names), names)
        self.assertTrue(any(n.startswith("q_w__t") for n in names), names)
        self.assertTrue(any(n.startswith("q_w__u") for n in names), names)
        # no motive or statement holds a let's value inside a later one: at most four b_eq calls in any {...} (one
        # let's value, b_eq(o, b_eq(o, k)), on each side)
        for ln in text.splitlines():
            depth = max((len(re.findall(r"b_eq\(", m)) for m in re.findall(r"\{[^{}]*\}", ln)), default=0)
            self.assertLessEqual(depth, 4, ln)
        flat, _ = self.gen.congruence("w", "q_w", self.lemmas(), "new", chain=False)
        self.assertNotIn("q_w__l", flat)
        # the flat text inlines o1 into o2 into o3 into o4: it holds far more calls than the chain's longest line
        self.assertGreater(max(len(ln) for ln in flat.splitlines()), 4 * max(len(ln) for ln in text.splitlines()))

    def test_old_driver_and_unknown_types_fall_back(self):
        r = self.gen.congruence("w", "q_w", self.lemmas(), "old")
        self.assertIsNotNone(r)
        # a let whose type is not evident is inlined as before; the lets after it are still chained
        pm2 = E.pair_module(OLD, NEW.replace("      +k = {b_eq(a, True{}) : Bool}", "      +k = Bool.and(a, True{})"),
                            STATEMENT)
        g2 = E.Gen(pm2)
        t_chain, _ = g2.congruence("w", "q_w", self.lemmas(), "new")
        t_flat, _ = g2.congruence("w", "q_w", self.lemmas(), "new", chain=False)
        self.assertNotEqual(t_chain, t_flat)
        # four lemmas (o1..o4); k has none
        self.assertEqual(sorted(re.findall(r"^def (q_w__l\d+_\d+)\(", t_chain, re.M)),
                         ["q_w__l1_1", "q_w__l1_2", "q_w__l1_3", "q_w__l1_4"])
        full, _ = self.gen.congruence("w", "q_w", self.lemmas(), "new")
        self.assertEqual(len(re.findall(r"^def (q_w__l\d+_\d+)\(", full, re.M)), 5)
        self.assertIn("Bool.and(a, True{})", t_chain)

    def test_flat_is_the_last_class(self):
        self.assertEqual(ES.CLASSES[-1], "congruence-flat")
        self.assertEqual(ES.CLASSES[0], "congruence")


class TestChainVerdict(unittest.TestCase):
    def test_proved_in_both_kernels(self):
        r = prove(NEW)
        self.assertEqual(r["status"], "PROVED", r["reason"])
        self.assertIn("bend", r["kernels"])
        if bend.verdict_enabled():
            self.assertIn("BendTT", r["kernels"])
        self.assertEqual(r["lemmas"]["w"]["class"], "congruence")
        self.assertIn("q_w__l", lemma_text(r, "w"))
        self.assertEqual(bend.escape_hatches(r["laws"] + r["proof"]), [])
        self.assertEqual(r["final"]["timeout_s"], bend.equivalence_timeout())

    def test_planted_difference_is_never_proved(self):
        r = prove(PLANTED)
        self.assertEqual(r["status"], "REFUTED", r["reason"])
        self.assertNotIn("BendTT", r["kernels"] or [])

    def test_byte_identical(self):
        a = E.prove(OLD, NEW, STATEMENT, counter_tries=0, cache=ES.LemmaCache(None))
        self.assertEqual(a["proof"], prove(NEW)["proof"])
        self.assertEqual(a["laws"], prove(NEW)["laws"])


class TestQ34Bound(unittest.TestCase):
    def test_config(self):
        self.assertEqual(bend.equivalence_timeout(), 900)
        cfg = bend.config()
        self.assertEqual(cfg["bend"]["timeout_s"], 180)
        self.assertEqual(cfg["bend"]["budget_s_per_file"], 120)

    def test_a_crash_is_retried_and_logged_never_accepted(self):
        crash = bend.Run(1, "SOME PROOFS FAIL\nError: the machine stack overflowed", 3.0, [])
        ok = bend.Run(0, "ALL PROOFS CHECK\n", 5.0, [])
        with mock.patch.object(bend, "check", side_effect=[crash, ok]) as m:
            r, log = bend.check_equivalence(ROOT / "x" / "PROOF.bend")
        self.assertTrue(r.ok)
        self.assertEqual(len(log), 1)
        self.assertEqual(m.call_args.kwargs["timeout"], 900)
        n = int(bend.config()["equivalence"]["crash_tries"])
        with mock.patch.object(bend, "check", side_effect=[crash] * n) as m:
            r, log = bend.check_equivalence(ROOT / "x" / "PROOF.bend")
        self.assertEqual(m.call_count, n)
        self.assertFalse(r.ok)
        self.assertTrue(bend.crashed(r))
        self.assertEqual(len(log), n)

    def test_crashes_of_every_final_try_are_kept(self):
        # the first final check crashes once, then refuses q_w (a cached lemma: the search corrects it and checks again)
        real = bend.check_equivalence
        crash = {"kernel": "bend", "seconds": 1.0, "message": "the machine stack overflowed"}
        calls = []

        def fake(p, cfg=None, verdict=False, tries=None):
            calls.append(verdict)
            if len(calls) == 1:
                return bend.Run(1, "SOME PROOFS FAIL\nLocation: q_w\n", 2.0, []), [crash]
            return real(p, cfg, verdict=verdict, tries=tries)
        with mock.patch.object(bend, "check_equivalence", side_effect=fake):
            r = E.prove(OLD, NEW, STATEMENT, counter_tries=0, cache=ES.LemmaCache(None))
        self.assertEqual(r["status"], "PROVED", r.get("reason"))
        self.assertGreater(calls.count(False), 1)          # the final check ran again after the correction
        self.assertIn(crash, r["final"]["crashes"])         # and the first try's crash is still logged

    def test_a_bendtt_run_with_no_verdict_is_not_a_rejection(self):
        real = bend.check_equivalence

        def fake(p, cfg=None, verdict=False, tries=None):
            if verdict:
                return bend.Run(None, "\n[timeout]", 900.0, []), []
            return real(p, cfg, verdict=verdict, tries=tries)
        with mock.patch.object(bend, "check_equivalence", side_effect=fake):
            r = E.prove(OLD, NEW, STATEMENT, counter_tries=0, cache=ES.LemmaCache(None))
        if bend.verdict_enabled():
            self.assertNotEqual(r["status"], "PROVED")
            w = [i for i in r["roots"] if i["root"] == "w"][0]
            self.assertEqual((w["status"], w["bendtt"]), ("UNKNOWN", "timeout"))

    def test_off_git_another_milestones_line_is_decided_by_where_its_law_lives(self):
        import json
        import tempfile
        from holon import statement_diff as SD
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "laws" / "M3").mkdir(parents=True)
            (root / "laws" / "M3" / "L_x.json").write_text("{}")
            line = {"kind": "binding_change", "law_id": "L_x", "milestone": "M2"}   # an M3 law relabelled M2
            (root / "laws" / "STATEMENT_DIFF.jsonl").write_text(json.dumps(line) + "\n")
            own = SD.scan(root / "laws" / "STATEMENT_DIFF.jsonl", root, milestone="M3")
            self.assertFalse(own["git"])
            self.assertNotIn(1, own.get("unchecked", []))     # the gated milestone's own law: checked, not skipped
            self.assertFalse(any(x.get("ok") for x in own["entries"]))
            other = SD.scan(root / "laws" / "STATEMENT_DIFF.jsonl", root, milestone="M2")
            self.assertEqual(other.get("unchecked"), [1])     # not M2's law: listed as not checked, never accepted
            self.assertFalse(other["entries"])

    def test_the_bound_is_only_for_final_checks(self):
        seen = []
        real = bend.check

        def fake_check(p, cfg=None, timeout=None):   # the final check times out; the batch checks really run
            seen.append(timeout)
            if timeout == bend.equivalence_timeout():
                return bend.Run(None, "\n[timeout]", float(timeout), [])
            return real(p, cfg, timeout)
        with mock.patch.object(bend, "check", side_effect=fake_check):
            r = E.prove(OLD, NEW, STATEMENT, counter_tries=0, cache=ES.LemmaCache(None))
        self.assertNotEqual(r["status"], "PROVED")
        self.assertIn(900, seen)   # the final whole-proof check
        self.assertIn(None, seen)  # the lemma search's batch checks keep bend.timeout_s
        w = [i for i in r["roots"] if i["root"] == "w"][0]
        self.assertEqual(w["status"], "UNKNOWN")
        self.assertIn("equivalence.timeout_s", w["reason"])


FAM_OLD = """import Base

def step(p: Bool, k: Bool) -> Bool:
  Bool.not(Bool.xor(p, k))

def s0() -> Bool:
  True{}

type R<-k: Bool, -s: Bool> is Type:
  R0{e: {s == s0() : Bool}}
  RS{p: Bool, r: R<k, p>, e: {s == step(p, k) : Bool}}
"""

FAM_NEW = FAM_OLD.replace("""def step(p: Bool, k: Bool) -> Bool:
  Bool.not(Bool.xor(p, k))""", """def step(p: Bool, k: Bool) -> Bool:
  match p:
    case True{}:
      k
    case False{}:
      Bool.not(k)""")

FAM_STATEMENT = """law l_r:
  for +k: Bool
  for +s: Bool
  for r: M.R<k, s>
  {M.s0() == M.s0() : Bool}
"""


class TestFamilyWithAFixedIndex(unittest.TestCase):
    def test_proved_in_both_kernels(self):
        r = E.prove(FAM_OLD, FAM_NEW, FAM_STATEMENT, counter_tries=0, cache=ES.LemmaCache(None))
        self.assertEqual(r["status"], "PROVED", r["reason"])
        if bend.verdict_enabled():
            self.assertIn("BendTT", r["kernels"])
        self.assertIn("  for +k: Bool\n  for -s: Bool\n", r["laws"])


class TestDeferral(unittest.TestCase):
    def run_deferred(self, new: str) -> dict:
        real = bend.check

        def fake_check(p, cfg=None, timeout=None):   # every batch check of the search times out
            if timeout is None:
                return bend.Run(None, "\n[timeout]", 180.0, [])
            return real(p, cfg, timeout)
        with mock.patch.object(bend, "check", side_effect=fake_check):
            return E.prove(OLD, new, STATEMENT, counter_tries=0, cache=ES.LemmaCache(None))

    def test_deferred_lemmas_are_decided_by_the_final_check(self):
        r = self.run_deferred(NEW)
        self.assertEqual(r["status"], "PROVED", r["reason"])
        self.assertGreater(r["final"].get("deferred_lemmas", 0), 0)
        self.assertGreater(r["search"]["timeouts"], 0)
        if bend.verdict_enabled():
            self.assertIn("BendTT", r["kernels"])
        self.assertTrue(all(v["status"] == "PROVED" for v in r["lemmas"].values()))

    def test_a_deferred_difference_is_never_proved(self):
        r = self.run_deferred(PLANTED)
        self.assertNotEqual(r["status"], "PROVED")
        self.assertNotIn("BendTT", r["kernels"] or [])
        self.assertTrue(any(v["status"] != "PROVED" for v in r["lemmas"].values()))


if __name__ == "__main__":
    unittest.main()
