"""I13 construction checks (not preregistered; added with the implementation): the solver's decision procedure
and the R2-R5 rules on toy machines that are not the Morph facts. Contract: tests_m2/test_sorts_morph.py.

  - satisfiable is exact on the torsor roles (x + x = a Time has no solution, though every class alone could
    be a point or a group element), and mixing index families, digest arithmetic and two seeded families
    meeting by flow are unsatisfiable;
  - forced sorts come only from constraints: an unseeded component forces nothing;
  - R3: a one-way copy keeps two writer labels apart; registers that copy each other share one label;
  - R5: a register with a lexical seed that also receives another digest kind carries the union, and a Time
    flowing into a digest is a base conflict whose core is minimal.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module


def cons(*items):
    out = []
    for i, (kind, vars_, extra) in enumerate(items):
        out.append({"id": f"t.c{i}", "model": "t", "kind": kind, "vars": list(vars_), "src": None, "text": kind,
                    **extra})
    return out


class TestSolver(unittest.TestCase):
    def setUp(self):
        self.S = holon_module("holon.sorts.solve")

    def test_exact_roles(self):
        cs = cons(("seed", ["a"], {"sort": "Time", "grounds": ["lexical:x"]}),
                  ("affine", ["x", "x", "a"], {"op": "+"}))
        self.assertFalse(self.S.satisfiable(cs), "x + x is never a Time (P+P and G+G are not P)")
        cs2 = cons(("seed", ["a"], {"sort": "Dur", "grounds": ["lexical:x"]}),
                   ("affine", ["x", "x", "a"], {"op": "+"}))
        self.assertTrue(self.S.satisfiable(cs2))
        sysm = self.S.System(cs2)
        self.assertEqual(sysm.family("t", "x"), "Dur")

    def test_ill_sorted_combinations(self):
        def seeded(sa, sb, op):
            return cons(("seed", ["a"], {"sort": sa, "grounds": ["lexical:x"]}),
                        ("seed", ["b"], {"sort": sb, "grounds": ["lexical:x"]}),
                        ("affine", ["a", "b", "c"], {"op": op}))
        self.assertFalse(self.S.satisfiable(seeded("Idx[queue]", "Idx[batch]", "-")), "mixed index families")
        self.assertFalse(self.S.satisfiable(seeded("Idx[queue]", "Cnt[batch]", "+")), "mixed index families")
        self.assertTrue(self.S.satisfiable(seeded("Idx[queue]", "Cnt[queue]", "+")))
        self.assertFalse(self.S.satisfiable(seeded("Dig[VH]", "Dur", "+")), "digest arithmetic")
        self.assertFalse(self.S.satisfiable(cons(("seed", ["a"], {"sort": "Time", "grounds": ["lexical:x"]}),
                                                 ("seed", ["b"], {"sort": "Dur", "grounds": ["lexical:x"]}),
                                                 ("flow", ["a", "b"], {}))), "two families meet by flow")
        self.assertTrue(self.S.satisfiable(cons(("seed", ["a"], {"sort": "Dig[VH]", "grounds": ["lexical:x"]}),
                                                ("seed", ["b"], {"sort": "Dig[Agg]", "grounds": ["lexical:x"]}),
                                                ("flow", ["a", "b"], {}))), "digest kinds make unions, not clashes")

    def test_nothing_is_guessed(self):
        cs = cons(("affine", ["k", "d", "o"], {"op": "+"}), ("flow", ["o", "k"], {}))
        sysm = self.S.System(cs)
        self.assertTrue(sysm.ok)
        for v in ("k", "d", "o"):
            self.assertIsNone(sysm.family("t", v))


FACTS = {
    "facts_version": "holon-facts/0.2",
    "target": {"repo": "toy/rules", "commit": "0" * 40, "scope": "R3 and R5 on a toy machine"},
    "params": {},
    "types": {},
    "state": [["t", "Nat", "block.timestamp"],
              ["p", "Nat", "pendingQueueIndex of the consumer"],
              ["q", "Nat", "nextQueueIndex of the producer"],
              ["r", "Nat", "headQueueIndex"],
              ["s", "Nat", "tailQueueIndex"],
              ["h", "Nat", "stored versioned hash"],
              ["g", "Nat", "another versioned hash"],
              ["log", "List<Obs>", "observations"]],
    "ghost_state": [],
    "initial": {"t": 0, "p": 0, "q": 0, "r": 0, "s": 0, "h": 0, "g": 0, "log": []},
    "defs": {},
    "actions": [
        {"name": "commitOne", "src": "toy/Q.sol:1-3", "principal": "anyone", "inputs": [["n", "Nat"], ["xs", "List<Nat>"]],
         "guards": [], "effects": {"q": ["+", "q", "n"], "r": "s", "h": ["call", "agg", "xs"]}},
        {"name": "finalizeOne", "src": "toy/Q.sol:5-7", "principal": "anyone", "inputs": [],
         "guards": [], "effects": {"p": "q", "s": "r"}},
        {"name": "stampTime", "src": "toy/Q.sol:9-11", "principal": "anyone", "inputs": [],
         "guards": [], "effects": {"g": "t"}},
    ],
    "coverage": {"modelled": [], "debt": []},
}
LIB = {"lib_version": "holon-lib/0.1", "name": "toy_rules", "doc": "toy", "builtins": {
    "agg": {"arity": 1, "bend": "b_agg($0)", "type": "Nat"}}}


class TestRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-sorts-rules-"))
        root = cls.tmp / "root"
        (root / "spec" / "M2" / "lib").mkdir(parents=True)
        shutil.copy(ROOT / "spec" / "M2" / "lib" / "sort_seeds.json", root / "spec" / "M2" / "lib" / "sort_seeds.json")
        (root / "toy" / "facts").mkdir(parents=True)
        (root / "toy" / "lib").mkdir(parents=True)
        (root / "toy" / "facts" / "rules.json").write_text(json.dumps(FACTS))
        (root / "toy" / "lib" / "toy.lib.json").write_text(json.dumps(LIB))
        P = holon_module("holon.sorts.assign")
        cls.docs = P.run_pass([root / "toy" / "facts" / "rules.json"], root, None)
        cls.A = cls.docs["assignment"]["models"]["rules"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_one_way_copy_keeps_labels_apart(self):
        a = self.A["assignment"]
        self.assertEqual(a["p"], "Idx[queue]_fin")
        self.assertEqual(a["q"], "Idx[queue]_inc")
        self.assertEqual(a["commitOne.n"], "Cnt[queue]")

    def test_two_way_copy_shares_one_label(self):
        a, prov = self.A["assignment"], self.A["provenance"]
        self.assertEqual(a["r"], a["s"])
        self.assertRegex(a["r"], r"^Idx\[queue\]_w[0-9a-f]{8}$")
        self.assertEqual(prov["r"]["component"], ["r", "s"])
        self.assertEqual(prov["r"]["writers"], ["commitOne"])
        self.assertEqual(prov["s"]["writers"], ["finalizeOne"])

    def test_seeded_register_receiving_another_kind_is_a_union(self):
        self.assertEqual(self.A["assignment"]["h"], "Dig[Agg] + Dig[VH]")
        us = [u for u in self.docs["unions"]["unions"] if "h" in u["vars"]]
        self.assertEqual(len(us), 1)
        self.assertEqual(us[0]["writers"], {"Dig[Agg]": ["commitOne"], "Dig[VH]": []})

    def test_time_into_a_digest_is_a_base_conflict(self):
        S = holon_module("holon.sorts.solve")
        cs = {c["id"]: c for c in self.docs["constraints"]["constraints"]}
        conflicts = self.docs["conflicts"]["conflicts"]
        self.assertEqual(len(conflicts), 1, conflicts)
        c = conflicts[0]
        self.assertEqual(c["kind"], "base")
        core = [cs[i] for i in c["core"]]
        self.assertEqual(sorted(x["kind"] for x in core), ["flow", "seed", "seed"])
        self.assertFalse(S.satisfiable(core))
        for k in range(len(core)):
            self.assertTrue(S.satisfiable(core[:k] + core[k + 1:]))
        self.assertEqual(c["src"], "toy/Q.sol:9-11")


if __name__ == "__main__":
    unittest.main()
