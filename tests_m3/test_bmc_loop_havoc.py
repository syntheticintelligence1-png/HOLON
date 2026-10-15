"""I40 review (blocking finding): a check inside a loop the BMC encoding havocs (a loop whose values it cannot carry,
or the iterations past the unroll bound) may still fail. Before the fix, Sym.loop restored the failure terms, loads
and stores from before the loop, so the target's goal folded to the literal "false" and the search reported no_path
"its condition is constant" for every k <= H, although a 4-step path exists on the real Rollup (updateProofWindow to
2^256-1, two commits, challengeState: Rollup.sol:491 `finalizeTimestamp += proofWindow` panics 0x11).

This is a builder regression test, not a preregistered one: it encodes the target's last step from a free state and
checks that the loop-internal checks keep a failure term that is not constant false, so the constant-condition
shortcut (Unrolled.trivial) does not fire for them.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOOP_REACHES = ("challengeState#contracts/contracts/l1/rollup/Rollup.sol:491#0",
                "challengeState#contracts/contracts/l1/rollup/Rollup.sol:489#1")


class TestLoopHavocKeepsChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon import refute_m3 as R
        side = R.load(ROOT / "spec" / "M3" / "lib" / "refute.json")
        env = R.load(ROOT / "spec" / "M3" / "refute_env.json")
        cls.p, _ = R.problem(ROOT, side, env)

    def test_loop_internal_checks_are_not_constant(self):
        from holon import bmc as B
        for rid in LOOP_REACHES:
            with self.subTest(reach=rid):
                action = rid.split("#")[0]
                c = next(c for c in self.p.m.progs[action].checks() if c.id == rid)
                self.assertIsNotNone(c.loop, "the regression is about a check inside a loop")
                u = B.Unrolled(self.p, {"kind": "check", "action": action, "check": rid}, 2)
                self.assertFalse(u.trivial, "a check inside a havoc loop may fail: no constant-condition shortcut")
                last = u.steps[-1]["acts"][0]["sym"]
                self.assertIn(rid, last.fails)
                self.assertNotEqual(u.goal({"sym": last}), "false")

    def test_unreached_check_is_not_constant(self):
        """_goal_false answers True only for a check the evaluation reached whose every fail term is literally false."""
        from holon import bmc as B
        rid = LOOP_REACHES[0]
        action = rid.split("#")[0]
        u = B.Unrolled(self.p, {"kind": "check", "action": action, "check": rid}, 1)
        u.target = {"kind": "check", "action": action, "check": rid + "-absent"}
        state = B.r0_symbolic(B.E.Query(self.p.rlimit), self.p)
        names = {n: B.lit(a) for n, a in self.p.principals}
        self.assertFalse(u._goal_false([action], state, names))


if __name__ == "__main__":
    unittest.main()
