"""S10 mutation canaries: a refuter that returns fake SAT must be caught.

  fake_sat    an in-domain candidate the sides do NOT differ on is pushed
              through the same acceptance path a real witness takes: emit the
              counter-law and check it. It must be rejected.
  replay_lie  a claim of the form f(h) == f(h) — if the encoding or the solver
              claimed SAT, the 'witness' still has to survive compiled-model
              replay, which it cannot.
"""

import unittest

from . import _util


@unittest.skipUnless(_util.env_ready(), "bend + node required for the canary kernels")
class TestRefuterCanaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon.refute_engines import canary
        cls.out = canary.run(log=lambda *a: None)

    def test_all_canaries_caught(self):
        self.assertEqual(self.out["uncaught"], [])

    def test_fake_sat_rejected_on_proved_laws(self):
        for name, r in self.out["canaries"].items():
            if not name.startswith("fake_sat:"):
                continue
            with self.subTest(canary=name):
                self.assertTrue(r["caught"], f"{name} not caught ({r})")

    def test_reflexive_claim_is_unsat_or_unwitnessed(self):
        for name, r in self.out["canaries"].items():
            if not name.startswith("replay_lie:"):
                continue
            with self.subTest(canary=name):
                self.assertTrue(r["caught"], f"{name} not caught ({r})")


class TestFakeSatCannotPass(unittest.TestCase):
    """A REFUTED status only ever rides on a kernel-checked counter-law."""

    def test_refuted_records_have_checked_counterlaw(self):
        for lid in _util.json.loads((_util.RECORDS / "summary.json").read_text()):
            r = _util.record(lid)
            if r["status"] != "REFUTED":
                continue
            checked = [e for e in r["engines"].values()
                       if isinstance(e.get("counter_law"), dict)
                       and e["counter_law"]["marker"] == "ALL PROOFS CHECK"]
            self.assertTrue(checked, f"{lid} claims REFUTED without a checked counter-law")


if __name__ == "__main__":
    unittest.main()
