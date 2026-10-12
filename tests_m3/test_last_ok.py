"""M3: linearise + verdict for one-sided acceptance claims (last_ok / runs_ok).

Covers the claim shapes B2 hit: eq [{"fn":"last_ok","args":[S]}, {"bool": b}]
and {"fn":"runs_ok","args":[T,S]}, where a REFUTED witness means the model
accepted exactly `not b`. No forge: verdict_obstruction is driven with fake
real-chain outcomes for each polarity, plus a mismatch that must disagree.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from holon.mreplay import linearise, verdict_obstruction  # noqa: E402

ACT = {"act": "sendMessage", "args": {"who": {"nat": 5}}}
FACTS = {"reasons": {"5": "Exceed maximum replay times"}}


def law(fn, arg, b):
    return {"statement": {"claim": {"eq": [{"fn": fn, "args": arg}, {"bool": b}]}, "assume": [], "binders": []}}


def step_state(act=None):
    return {"step": act or ACT, "from": {"s0": {}}}


def fake_outs(run, model, tid=0):
    """The (run, agree, dis, model_obs, tid) tuples verdict_obstruction consumes."""
    return [(run, [], [], model, tid)]


class TestLineariseLastOk(unittest.TestCase):
    def test_closed_last_ok_true(self):
        # claim: last_ok(step(act, s0)) == true  ->  refuted witness: last step NOT ok
        out = linearise(law("last_ok", [step_state()], True), {})
        self.assertEqual(out, [{"label": "trace", "trace": [{"op": "sendMessage", "who": 5}],
                                "split": 0, "kind": "last_ok", "expect_ok": False}])

    def test_last_ok_run_and_step_states(self):
        # S in run/step form: from s0 run two steps then assert on the state
        st = {"run": {"trace": [ACT, {"act": "wait", "args": {}}]}, "from": {"s0": {}}}
        out = linearise(law("last_ok", [st], False), {})
        self.assertEqual(out[0]["kind"], "last_ok")
        self.assertTrue(out[0]["expect_ok"])
        self.assertEqual([a["op"] for a in out[0]["trace"]], ["sendMessage", "wait"])

    def test_binder_law_with_witness(self):
        # runs_ok over a witness trace with a bound who
        arg = [{"trace": [{"act": "sendMessage", "args": {"who": {"var": "w"}}}]}, {"s0": {}}]
        out = linearise(law("runs_ok", arg, True), {"w": 9})
        self.assertEqual(out[0]["kind"], "runs_ok")
        self.assertFalse(out[0]["expect_ok"])  # claim == true refuted -> witness says it ran ok
        self.assertEqual(out[0]["trace"], [{"op": "sendMessage", "who": 9}])


class TestVerdictLastOk(unittest.TestCase):
    def test_expect_revert_reproduced(self):
        # model says last step reverts (O_Rev), real chain reverts too -> agree
        run = {"label": "trace", "trace": [{"op": "sendMessage", "who": 5}],
               "split": 0, "kind": "last_ok", "expect_ok": False}
        real = {(0, 0): ("rev", FACTS["reasons"]["5"])}
        rep, why = verdict_obstruction(FACTS, "last_ok", fake_outs(run, [{"$": "O_Rev", "code": 5}]), real)
        self.assertTrue(rep, why)

    def test_expect_ok_reproduced(self):
        # claim `last_ok == false` refuted: model accepted, real accepts -> agree
        run = {"label": "trace", "trace": [{"op": "sendMessage", "who": 5}],
               "split": 0, "kind": "last_ok", "expect_ok": True}
        real = {(0, 0): ("ok", "0xabc")}
        rep, why = verdict_obstruction(FACTS, "last_ok", fake_outs(run, [{"$": "O_Ok"}]), real)
        self.assertTrue(rep, why)

    def test_mismatch_reports_disagree(self):
        # model reverts but real accepts -> no coercion, verdict disagrees
        run = {"label": "trace", "trace": [{"op": "sendMessage", "who": 5}],
               "split": 0, "kind": "last_ok", "expect_ok": False}
        real = {(0, 0): ("ok", "0xabc")}
        rep, why = verdict_obstruction(FACTS, "last_ok", fake_outs(run, [{"$": "O_Rev", "code": 5}]), real)
        self.assertFalse(rep)
        self.assertIn("expect_ok=False", why)

    def test_runs_ok_needs_whole_trace(self):
        # runs_ok: every real step must be accepted; a mid-trace rev fails it
        tr = [{"op": "sendMessage", "who": 5}, {"op": "wait"}]
        run = {"label": "trace", "trace": tr, "split": 0, "kind": "runs_ok", "expect_ok": True}
        ok_real = {(0, 0): ("ok", "a"), (0, 1): ("ok", "b")}
        rep, _ = verdict_obstruction(FACTS, "runs_ok", fake_outs(run, [{"$": "O_Ok"}, {"$": "O_Ok"}]), ok_real)
        self.assertTrue(rep)
        mid_rev = {(0, 0): ("ok", "a"), (0, 1): ("rev", "x")}
        rep, _ = verdict_obstruction(FACTS, "runs_ok", fake_outs(run, [{"$": "O_Ok"}, {"$": "O_Ok"}]), mid_rev)
        self.assertFalse(rep)


if __name__ == "__main__":
    unittest.main()
