"""I14: the evidence calculus on planted fixtures (construction checks; the contract is the docstring of
tests_m2/test_evidence.py). tests_m2/fixtures/evidence/ holds two fact documents built into diagrams by I11's
holon.diagram.build at test time, a fixture library whose builtin `smear` declares no access kind, a planted sorts
assignment, the exact evidence set those inputs must give (every planted-absent case is an atom that must not
appear), fixture laws with their exact law_evidence result, and the evidence_triage table. They pin each level's
definition before the pass first runs on the Morph diagrams.
"""
import unittest

from tests_m2._evidence import (FIXTURES, LEVELS, fixture, fixture_doc, fixture_law, project, project_unresolved)
from tests_m2._m2 import ROOT, holon_module, load_json


class _Fixture(unittest.TestCase):
    doc: dict = None

    @classmethod
    def setUpClass(cls):
        if _Fixture.doc is None:
            _Fixture.doc = fixture_doc()


class TestFixtureAtoms(_Fixture):
    def test_every_planted_atom_and_nothing_else(self):
        want = {project(a) for a in fixture()["atoms"]}
        got = {project(a) for a in self.doc["atoms"]}
        self.assertEqual(sorted(got - want), [], "atoms the rules do not license (a planted-absent case appeared)")
        self.assertEqual(sorted(want - got), [], "planted atoms missing")

    def test_unresolved_pairs_through_a_kindless_builtin(self):
        want = {project_unresolved(u) for u in fixture()["unresolved"]}
        self.assertEqual({project_unresolved(u) for u in self.doc["unresolved"]}, want)

    def test_levels_planted_absent_by_kind(self):
        """Spot checks of the absent cases, by name, so a failure says which rule broke."""
        A = self.doc["atoms"]

        def has(level, p, q):
            return any(a["level"] == level and a["p"] == p and a["q"] == q for a in A)
        self.assertFalse(has("E1", "CODEC.enc_go_t0", "CODEC.enc_go_t1"), "E1 needs a common version")
        self.assertFalse(has("E6", "CODEC.enc_go_t0", "CODEC.enc_sol_t"), "E6 needs a shared token")
        self.assertFalse(has("E4", "TRANS.putValue", "TRANS.peekValue"), "digest(store) reads state: no recompute")
        self.assertFalse(has("E2", "TRANS.smudge", "TRANS.readBuf"), "an imprecise write is no E2")
        sync = [a["via"]["operands"] for a in A if a["level"] == "E3" and a["p"] == "TRANS.sync"]
        self.assertNotIn(["x", "K"], sync, "a comparison with a parameter is no E3")
        e5 = [(a["p"], a["via"]["operands"]) for a in A if a["level"] == "E5"]
        for p, ops in (("TRANS.sync", ["u", "v"]), ("TRANS.sync", ["on", "off"]), ("TRANS.sync", ["m1", "m2"]),
                       ("TRANS.zap", ["seen", "store"]), ("TRANS.tick", ["t", "dt"])):
            self.assertNotIn((p, ops), e5, f"{p} {ops}: a union, Bool, Mach, unrefined or unequal pair is no E5")

    def test_document_shape_on_the_fixture(self):
        d = self.doc
        self.assertEqual(sorted(d["models"]), ["toy_codec", "toy_machine"])
        for m, rel in fixture()["facts"].items():
            self.assertEqual(d["models"][m]["facts"], rel)
            self.assertIsNone(d["models"][m]["diagram"], "diagrams passed in are not files")
        self.assertIsNone(d["sorts_sha256"])
        self.assertEqual(d["models"]["toy_codec"]["anchors"]["domains"], {"ok_go_t": ["CODEC.dec_t"], "ok_sol_t": []})
        self.assertEqual(d["models"]["toy_machine"]["anchors"]["carriers"]["buf"],
                         {"writers": ["TRANS.putValue", "TRANS.smudge"], "readers": ["LOAD.obs.smeared", "TRANS.readBuf"]})
        self.assertIn("spec/M2/lib/evidence_lexical.json", [i["path"] for i in d["inputs"]])
        self.assertIn("tests_m2/fixtures/evidence/lib/toy_smear.lib.json", [i["path"] for i in d["inputs"]])

    def test_build_does_not_depend_on_the_order_of_the_documents(self):
        E = holon_module("holon.diagram.evidence")
        fx = fixture()
        build = holon_module("holon.diagram").build
        paths = [ROOT / rel for _, rel in sorted(fx["facts"].items())]
        diagrams = {p.stem: build(p, ROOT).to_json() for p in paths}
        again = E.build(list(reversed(paths)), ROOT, diagrams=diagrams, assignment=fx["assignment"])
        self.assertEqual(E.render(again), E.render(self.doc))


class TestFixtureLaws(_Fixture):
    KEYS = ("model", "covered", "named", "context", "version", "levels", "max")

    def test_law_evidence_on_every_fixture_law(self):
        E = holon_module("holon.diagram.evidence")
        ids = {a["id"]: a for a in self.doc["atoms"]}
        for entry in fixture()["laws"]:
            law = fixture_law(entry)
            with self.subTest(law=law["law_id"]):
                got = E.law_evidence(law, self.doc)
                self.assertEqual({k: got[k] for k in self.KEYS}, entry["expect"])
                self.assertEqual(got["atoms"], sorted(got["atoms"]))
                self.assertTrue(set(got["atoms"]) <= set(ids))
                self.assertEqual(sorted({ids[i]["level"] for i in got["atoms"]}), got["levels"])

    def test_triage_table(self):
        E = holon_module("holon.diagram.evidence")
        for status, mx, want in fixture()["triage"]:
            with self.subTest(status=status, max=mx):
                self.assertEqual(E.evidence_triage(status, mx), want)
        self.assertEqual(tuple(E.LEVELS), LEVELS)


class TestLayoutAPI(unittest.TestCase):
    def test_recovers_and_evidence(self):
        L = holon_module("holon.layout")
        toy = load_json(FIXTURES / "codec" / "toy_codec.json")
        lay = L.layout(toy, "enc_go_t1", 1)
        self.assertTrue(L.recovers(lay, {"name": "a", "offset": 1, "width": 2}))
        self.assertFalse(L.recovers(lay, {"name": "version", "offset": 0, "width": 1}), "a constant byte")
        self.assertFalse(L.recovers(lay, {"name": "a", "offset": 2, "width": 2}), "positions out of order")
        self.assertFalse(L.recovers(lay, {"name": "c", "offset": 5, "width": 2}), "past the end")
        self.assertEqual(L.evidence(toy, "enc_sol_t", "dec_t", 0), {"fields": ["version", "a"], "not_recovered": ["b"]})
        self.assertEqual(L.evidence(toy, "enc_sol_t", "dec_t", 1),
                         {"fields": ["version", "a", "c"], "not_recovered": ["b"]})
        self.assertEqual(L.evidence(toy, "enc_go_t1", "dec_t", 1),
                         {"fields": ["a", "b", "c"], "not_recovered": ["version"]})


if __name__ == "__main__":
    unittest.main()
