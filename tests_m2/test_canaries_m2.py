"""Audit M2/1 F-M2-05 and F-M2-06: G4 canaries for any target, IR 0.3 and Reach laws, and the core-omit canary.

F-M2-05. holon.mcanary takes the live fields of an erase_live canary from Machine.reads (the state fields some
action's decision reads), in facts state order; it holds no field list of a target.

F-M2-06. Canary kinds beyond M1's shapes: `negated` for any PROVED forall law at a point where it holds (its
recorded inhabitant, or the binders' defaults), `flip_const` / `shift_const` mutations of a claim's Bool / Nat
constant (refuted on the model, proved with the source law's own generator), the single-equation pin_const no
longer crashes, and for M2+ milestones holon.gate.g4_machine builds each facts file's model as the milestone does
(Reach, guard-derived permissions, oracle parameters, the core library) and requires a rejected core_omit canary.
The fixtures of I6 (toy queue), I7 (IR 0.3), I8 (Reach) and I12 (oracle parameters) together, as one test
milestone, reach at least MIN_CANARIES canaries of at least 3 kinds, all rejected for a semantic reason.
"""
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, holon_module, load_json, run_holon, write_json

FX = ROOT / "tests_m2" / "fixtures"
# I7 (IR 0.3), I8 (Reach) and I12 (oracle parameters): one IR 0.3 test milestone over three facts files; I6's toy
# queue laws are IR 0.2, and a milestone holds one IR version, so they form a second one
MILESTONES = {
    "T46": {
        "tests_m2/fixtures/toy_queue/toy_queue.facts.json": [FX / "ir03" / f"{x}.json" for x in
                                                             ("L3_and_true", "L3_and_false", "L3_cf", "L3_exists_false")],
        "tests_m2/fixtures/toy_reach/toy_reach.facts.json": [FX / "reach" / f"L8_reach_{x}.json" for x in ("x", "y", "k", "flag")],
        "tests_m2/fixtures/oracles/facts/toy_oracle.facts.json": [FX / "oracles" / "laws" / f"{x}.json" for x in
                                                                  ("L_orc_cf_commit", "L_orc_runs_ok", "L_orc_run_post",
                                                                   "L_orc_dec_pad", "L_orc_dec_exact")]},
    "T47": {"tests_m2/fixtures/toy_queue/toy_queue.facts.json": [FX / "toy_queue" / "L_toy_reach.json",
                                                                 FX / "toy_queue" / "L_toy_small.json"]},
}


class TestLiveFields(unittest.TestCase):
    def test_no_target_field_list(self):
        mc = holon_module("holon.mcanary")
        self.assertFalse(hasattr(mc, "LIVE_FIELDS"))

    def test_live_fields_come_from_the_decisions(self):
        mc, P = holon_module("holon.mcanary"), holon_module("holon.mpipeline")
        cfg = holon_module("holon.bend").config(ROOT)
        toy = P.CompiledMachine.build(FX / "toy_queue" / "toy_queue.facts.json", cfg)
        self.assertEqual(mc.live_fields(toy.m), ["q"])
        roll = P.CompiledMachine.build(ROOT / "spec" / "M1" / "facts" / "morph_rollup.json", cfg)
        live = mc.live_fields(roll.m)
        self.assertEqual(live, [n for n, _ in roll.m.state if n in set().union(*roll.m.reads.values())])
        self.assertLessEqual({"s_bvh", "s_tag", "t", "paused", "inch", "qlen"}, set(live))   # M1's former list
        self.assertNotIn("s_bvh", mc.live_fields(roll.m, ["s_bvh"]))


class TestCandidates(unittest.TestCase):
    def test_single_equation_pin_const(self):
        """L3_exists_false (one equation, no `all`) crashed with KeyError: 'all'."""
        mc = holon_module("holon.mcanary")
        law = load_json(FX / "ir03" / "L3_exists_false.json")
        cands = mc.candidates([law], {law["law_id"]: {"status": "PROVED", "witness": {"a": {"op": "push", "x": 5}}}})
        self.assertEqual([(k, c["statement"]["claim"]["eq"][1]) for k, _, c, _ in cands], [("pin_const", {"nat": 6})])

    def test_interleave_keeps_every_kind(self):
        mc = holon_module("holon.mcanary")
        cands = [("a", "x", {}, None)] * 30 + [("b", "y", {}, None), ("c", "z", {}, None)]
        self.assertEqual([k for k, *_ in mc.interleave(cands)[:3]], ["a", "b", "c"])


class TestFixtureCanaries(unittest.TestCase):
    """The I6/I7/I8/I12 fixtures as M2+ test milestones, run, then G4 (g4_machine) over their records."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        repo = cls.repo
        G = holon_module("holon.gate")
        cls.runs, cls.gates = {}, {}
        for m, groups in MILESTONES.items():
            d = repo / "laws" / m
            d.mkdir(parents=True)
            files, stmts = {}, {}
            for rel, paths in groups.items():
                sha = hashlib.sha256((repo / rel).read_bytes()).hexdigest()
                files[rel] = sha
                for p in paths:
                    law = load_json(p)
                    law["facts"], law["facts_sha256"] = rel, sha
                    write_json(d / p.name, law)
                    stmts[law["law_id"]] = None
            first = next(iter(groups))
            write_json(d / "REGISTRY.json", {"milestone": m, "facts": first, "facts_sha256": files[first],
                                             "facts_files": files, "statements": stmts})
            cls.runs[m] = run_holon(["run", "--milestone", m, "--no-registry"], cwd=repo, timeout=3000)
            cls.gates[m] = G.Gate(m, repo)
            cls.gates[m].g4_machine()
        cls.gate = cls.gates["T46"]
        cls.res = cls.gate.checks["G4"]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_run_decided_the_fixtures(self):
        for m, r in self.runs.items():
            with self.subTest(milestone=m):
                self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])

    def test_g4_passes_with_three_kinds(self):
        """The IR 0.3 milestone alone passes G4: at least MIN_CANARIES canaries of at least 3 kinds, all rejected."""
        G = holon_module("holon.gate")
        kinds = {c["kind"] for c in self.gate.canaries}
        self.assertTrue(self.res["passed"], self.res["detail"])
        self.assertGreaterEqual(len(self.gate.canaries), G.MIN_CANARIES)
        self.assertGreaterEqual(len(kinds), 3, kinds)
        self.assertEqual([c["id"] for c in self.gate.canaries if not c["rejected"]], [])

    def test_i6_toy_canaries_are_rejected(self):
        """I6's toy machine (IR 0.2, few laws: below G4's minimum on its own) gets the pin_const of its strategy law
        and the core_omit canary, all rejected."""
        cs = self.gates["T47"].canaries
        self.assertLessEqual({"pin_const", "core_omit"}, {c["kind"] for c in cs})
        self.assertEqual([c["id"] for c in cs if not c["rejected"]], [])

    def test_canaries_cover_ir03_and_reach_laws(self):
        srcs = {c["source_law"] for c in self.gate.canaries}
        self.assertTrue(srcs & {"L3_and_true", "L3_cf"}, srcs)          # holon-ir/0.3 shapes
        self.assertTrue(srcs & {"L8_reach_x", "L8_reach_y"}, srcs)      # Reach laws
        self.assertTrue(srcs & {"L_orc_cf_commit", "L_orc_runs_ok", "L_orc_run_post", "L_orc_dec_pad"}, srcs)  # parameters

    def test_core_omit_canary_is_required_and_rejected(self):
        for m, g in self.gates.items():
            with self.subTest(milestone=m):
                om = [c for c in g.canaries if c["kind"] == "core_omit"]
                self.assertEqual(len(om), 1, g.canaries)
                self.assertTrue(om[0]["rejected"], om[0])

    def test_core_omit_proof_that_calls_the_lemma_fails(self):
        """The core_omit check itself: with no milestone proof calling the core, a generated law restating a core
        lemma and proved by calling it is checked against a core without that lemma (and checks with it)."""
        mc, C, bend = holon_module("holon.mcanary"), holon_module("holon.gen.core"), holon_module("holon.bend")
        tmp = Path(tempfile.mkdtemp(prefix="holon-core-omit-"))
        try:
            rec = mc.core_omit(tmp / "nogen", [], {}, tmp, bend.config(ROOT))
            self.assertTrue(rec["rejected"], rec)
            d = tmp / "core_omit_synth"
            shutil.rmtree(d / "core")
            C.emit(d, cfg=bend.config(ROOT))   # the same law with the full core checks
            self.assertTrue(bend.check(d / "canary" / "PROOF.bend", bend.config(ROOT)).ok)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
