"""I13: the planted Time+Time fixture (BUILD_PLAN I13: "the planted fixture's minimal core has exactly 2
constraints") and the "nothing is guessed" fallback. Contract: tests_m2/test_sorts_morph.py docstring.

tests_m2/fixtures/sorts/time_plus_time.json is a holon-facts/0.2 clock with the same time cues as the M1
rollup facts: a state field t documented "block.timestamp (environment)", an environment action wait(dt) with
t := t + dt, and disch.delay naming wait.dt. The planted defect is stamp's let due = t + t
(src toy/Clock.sol:11): a sum of two Times, ill-sorted under §7.2. No other register is seeded: k is moved
only by bump(d) with k := k + d, and r only receives the ill-sorted sum.

Operationalization of "minimal core has exactly 2 constraints": run
  python -m holon sorts --facts tests_m2/fixtures/sorts/time_plus_time.json --out DIR
The run reports exactly one conflict (the fixture plants one); its core lists exactly 2 constraint ids of
constraints.json, one of them the affine constraint of the planted sum (src toy/Clock.sol:11) and the other
one naming t (whatever makes t a Time). The core is checked through holon.sorts.solve.satisfiable: it is
unsatisfiable and each 1-constraint deletion of it is satisfiable; the whole constraint set is unsatisfiable
and becomes satisfiable once the planted affine constraint is removed. Because a seed is a unit constraint
(at most one per variable, all grounds listed in it), an arithmetic node is one affine constraint, and
Dur + Dur = Dur (tests_m2/test_sorts_unit.py: Dur is the group Time is a torsor over, so wait's t := t + dt
does not by itself force t to be a Time), every minimal core of this fixture is {what makes t a Time, the
planted sum}: 2 constraints, whichever one deletion order finds.
"""
import unittest

from tests_m2._m2 import holon_module
from tests_m2._sorts import UNREFINED, Run

FIX = "tests_m2/fixtures/sorts/time_plus_time.json"
PLANTED = "toy/Clock.sol:11"


class TestPlantedTimePlusTime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sr = Run(["--facts", FIX])

    @classmethod
    def tearDownClass(cls):
        cls.sr.cleanup()

    def only_model(self) -> str:
        models = self.sr.doc("assignment")["models"]
        self.assertEqual(len(models), 1, sorted(models))
        return next(iter(models))

    def constraints(self) -> dict:
        cs = self.sr.doc("constraints")["constraints"]
        return {c["id"]: c for c in cs}

    def conflict(self) -> dict:
        self.assertEqual(self.sr.code, 0, self.sr.log)
        conflicts = self.sr.doc("conflicts")["conflicts"]
        self.assertEqual(len(conflicts), 1, conflicts)
        return conflicts[0]

    def planted_affine(self, ids) -> list[dict]:
        cons = self.constraints()
        return [cons[i] for i in ids if cons[i]["kind"] == "affine" and cons[i]["src"] == PLANTED]

    def test_planted_conflict_has_a_two_constraint_minimal_core(self):
        """I13-P6: the planted Time+Time fixture's minimal unsat core has exactly 2 constraints."""
        m = self.only_model()
        A = self.sr.assignment(m)
        self.assertEqual(A.get("t"), "Time", "the fixture's timestamp is a Time")
        c = self.conflict()
        self.assertEqual(c["kind"], "affine")
        self.assertEqual(c["src"], PLANTED, "the clash is located at the planted sum")
        cons = self.constraints()
        for i in c["core"]:
            self.assertIn(i, cons)
        self.assertEqual(len(c["core"]), 2, [cons.get(i) for i in c["core"]])
        planted = self.planted_affine(c["core"])
        self.assertEqual(len(planted), 1, "the core holds the planted sum's affine constraint")
        other = [cons[i] for i in c["core"] if cons[i] is not planted[0]]
        self.assertEqual(len(other), 1)
        self.assertIn("t", other[0]["vars"], "the other constraint makes t a Time")

    def test_core_is_unsatisfiable_and_irreducible(self):
        """I13-P6: the reported core is a minimal unsatisfiable subset, and the planted sum is the only conflict."""
        S = holon_module("holon.sorts.solve")
        cons = self.constraints()
        core = [cons[i] for i in self.conflict()["core"]]
        self.assertFalse(S.satisfiable(core), "the core is unsatisfiable")
        for k in range(len(core)):
            self.assertTrue(S.satisfiable(core[:k] + core[k + 1:]), f"dropping core[{k}] leaves it unsatisfiable")
        everything = self.sr.doc("constraints")["constraints"]
        self.assertFalse(S.satisfiable(everything))
        planted = self.planted_affine(list(cons))
        self.assertEqual(len(planted), 1, "one affine constraint at the planted span")
        self.assertTrue(S.satisfiable([x for x in everything if x is not planted[0]]),
                        "without the planted sum the fixture is well sorted")

    def test_weakly_seeded_registers_stay_unrefined(self):
        """Fallback (nothing is guessed): k and bump.d have no seed and no flow to a seeded variable, so they stay
        "Nat (unrefined)" and are listed in unresolved.json; the delay input wait.dt is a Dur."""
        self.assertEqual(self.sr.code, 0, self.sr.log)
        m = self.only_model()
        A = self.sr.assignment(m)
        self.assertEqual(A.get("wait.dt"), "Dur")
        listed = {(e["model"], e["var"]) for e in self.sr.doc("unresolved")["unresolved"]}
        for v in ("k", "bump.d"):
            with self.subTest(var=v):
                self.assertEqual(A.get(v), UNREFINED)
                self.assertIn((m, v), listed)


if __name__ == "__main__":
    unittest.main()
