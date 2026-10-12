"""Audit M2/1 F-M2-26: principal classes come from the permission guards, and M2+ models generate perm_<class>.

holon.diagram.principals.guard_classes groups actions by (has a caller input, the set of its permission guards);
the `principal` label only names the class. A dropped or added permission guard, or a mislabelled action, is a
label/guard disagreement: the diagram build fails (DiagramError) and so does an M2+ model (FactsError); it is no
longer a PRINCIPAL debt line beside a class whose predicate was erased. An M2+ model (holon.gen.machine,
Machine(m2plus=True)) takes `perm` from the permission guards and generates perm_<class>(a, who) for every
class; M0 and M1 models keep the M1 label-prefix `perm`, byte for byte.
"""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json

FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
CLASSES = {"active_submitter": ["commitBatch", "commitState", "proveState"], "anyone": ["commitBatchWithProof",
           "finalizeBatch", "sendMessage"], "challenger": ["challengeState"], "environment": ["wait"],
           "owner": ["revertBatch", "setPause"]}


def drop_guard(facts: dict, action: str, reason: int) -> dict:
    f = copy.deepcopy(facts)
    a = next(x for x in f["actions"] if x["name"] == action)
    a["guards"] = [g for g in a["guards"] if g.get("reason") != reason]
    return f


class TestGuardClasses(unittest.TestCase):
    def setUp(self):
        self.P = holon_module("holon.diagram.principals")
        self.facts = load_json(FACTS)

    def test_classes_follow_the_guards(self):
        classes, of = self.P.guard_classes(self.facts)
        self.assertEqual({c["id"]: c["actions"] for c in classes}, CLASSES)
        perm_free = sorted(c["id"] for c in classes if c["permissionless"])
        self.assertEqual(perm_free, ["anyone", "environment"])
        for c in classes:
            if c["id"] not in ("anyone", "environment"):
                self.assertTrue(c["predicate"], c)

    def test_dropped_permission_guard_is_a_disagreement(self):
        """The audit's experiment: commitBatch without its mem(who, active) guard (reason 1)."""
        with self.assertRaises(self.P.PrincipalError) as cm:
            self.P.guard_classes(drop_guard(self.facts, "commitBatch", 1))
        self.assertIn("label/guard disagreement", str(cm.exception))

    def test_mislabelled_action_is_a_disagreement(self):
        f = copy.deepcopy(self.facts)
        next(a for a in f["actions"] if a["name"] == "finalizeBatch")["principal"] = "owner"
        with self.assertRaises(self.P.PrincipalError):
            self.P.guard_classes(f)

    def test_diagram_build_fails_on_a_disagreement(self):
        """`holon diagram` over facts with a dropped permission guard fails (exit 1), writing nothing."""
        import json
        dia = holon_module("holon.diagram")
        tmp = Path(tempfile.mkdtemp(prefix="holon-principal-"))
        try:
            for rel in ("facts", "spec/M1/facts", "spec/M1/lib", "spec/lib", "spec/ledger"):
                shutil.copytree(ROOT / rel, tmp / rel)
            p = tmp / "spec" / "M1" / "facts" / "morph_rollup.json"
            self.assertEqual(dia.run("M2", str(tmp / "out_ok"), str(tmp)), 0)
            p.write_text(json.dumps(drop_guard(self.facts, "commitBatch", 1), indent=1))
            self.assertEqual(dia.run("M2", str(tmp / "out_bad"), str(tmp)), 1)
            self.assertFalse((tmp / "out_bad").exists())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestGeneratedPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.F = holon_module("holon.facts")
        cls.Mach = holon_module("holon.gen.machine")

    def test_m1_model_keeps_its_perm(self):
        m = self.Mach.Machine(self.F.load(FACTS), FACTS)
        text = m.generate(self.F.sha256_file(FACTS))
        self.assertEqual(text, (ROOT / "gen" / "M1" / "model" / "morph_rollup.bend").read_text())
        self.assertNotIn("def perm_", text)

    def test_m2plus_model_generates_perm_classes(self):
        m = self.Mach.Machine(self.F.load(FACTS), FACTS, m2plus=True)
        text = m.generate(self.F.sha256_file(FACTS), reach=True)
        for cid in CLASSES:
            self.assertIn(f"def perm_{cid}(a: HAct, who_: Nat) -> Bool:", text)
        self.assertEqual(m.permissionless(), ["commitBatchWithProof", "finalizeBatch", "sendMessage", "wait"])

    def test_m2plus_model_with_a_dropped_guard_does_not_build(self):
        m = self.Mach.Machine(drop_guard(self.F.load(FACTS), "commitBatch", 1), FACTS, m2plus=True)
        with self.assertRaises(self.Mach.FactsError):
            m.generate("0" * 64, reach=True)

    def test_perm_classes_evaluate_on_the_compiled_model(self):
        P = holon_module("holon.mpipeline")
        cm = P.CompiledMachine.build(FACTS, holon_module("holon.bend").config(ROOT), reach=True)
        commit = {"op": "commitBatch", "who": 2, "ver": 0, "parent": 0, "n": 0, "lbn": 0, "prev": 1, "post": 1, "blobs": []}
        wait = {"op": "wait", "dt": 3}
        act = lambda a: {"val": P._act_val(cm.m, a)}   # noqa: E731
        calls = [{"fn": "perm_active_submitter", "args": [act(commit), {"val": 2}]},
                 {"fn": "perm_active_submitter", "args": [act(commit), {"val": 3}]},
                 {"fn": "perm_anyone", "args": [act(commit), {"val": 2}]},
                 {"fn": "perm_environment", "args": [act(wait), {"val": 7}]},
                 {"fn": "perm", "args": [act(commit)]}, {"fn": "perm", "args": [act(wait)]}]
        self.assertEqual(cm.calls(calls), [True, False, False, True, False, True])


if __name__ == "__main__":
    unittest.main()
