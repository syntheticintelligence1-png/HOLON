"""M3: derivedPolicy trace search for non-Rollup machines.

Each machine gets a test-only quantified trace law that is false; the old
selection (Rollup heuristics on a machine without them) could never produce
the violating step, so the law came out UNKNOWN by construction. Under
derivedPolicy the explorer finds a witness, which is then checked by
evaluating the claim on the compiled model (claims == [False]).
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node") or "/usr/bin/node"
LIB = ROOT / "holon" / "js" / "policy_lib.mjs"

FACTS = {
    "mvrv": ROOT / "spec" / "M3" / "extracted" / "mvrv.json",
    "l1messenger": ROOT / "spec" / "M3" / "extracted" / "l1messenger.json",
    "submitter": ROOT / "spec" / "M3" / "extracted" / "submitter.json",
}


def _bend_available() -> bool:
    return shutil.which("bend") is not None or (Path.home() / ".holon/bin/bend").exists()


def law_forall_trace(obs, args, rhs):
    return {
        "ir_version": "holon-ir/0.2",
        "law_id": f"TEST_{obs}",
        "rule": "safety",
        "facts": "",
        "facts_sha256": "",
        "predicted": "PROVED",
        "statement": {
            "binders": [{"q": "forall", "name": "p", "type": "Trace"}],
            "assume": [],
            "claim": {"eq": [{"obsv": obs, "of": {"run": {"var": "p"}, "from": {"s0": {}}}, "args": args}, rhs]},
        },
    }


def rollup_policy_throws(state, facts_path):
    """True when the Rollup hand policy cannot even run on this decoded state —
    the old selection therefore produced no candidates (UNKNOWN by construction)."""
    code = (
        'import {rollupPolicy} from "file://%s";\n'
        "const s=%s, facts=%s;\n"
        "try { const o=rollupPolicy(s,facts); console.log(JSON.stringify({ok:true,n:o.length})); }\n"
        "catch(e) { console.log(JSON.stringify({ok:false,err:String(e)})); }"
    ) % (LIB, json.dumps(state), Path(facts_path).read_text())
    r = subprocess.run([NODE, "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout.strip())
    return not out["ok"]


def policy_output(state, facts_path):
    code = (
        'import {policyOf} from "file://%s";\n'
        "console.log(JSON.stringify(policyOf(%s,%s)));"
    ) % (LIB, json.dumps(state), Path(facts_path).read_text())
    r = subprocess.run([NODE, "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout


class TestDerivedPolicy(unittest.TestCase):
    def test_determinism(self):
        s = {"own": 1, "rollup": 0, "lv": [], "lvv": [], "log": []}
        a = policy_output(s, FACTS["mvrv"])
        b = policy_output(s, FACTS["mvrv"])
        self.assertEqual(a, b)
        c = policy_output(s, FACTS["mvrv"])
        self.assertEqual(a, c)

    def test_derived_candidates_cover_machine_ops(self):
        s = {"own": 1, "rollup": 0, "lv": [], "lvv": [], "log": []}
        out = json.loads(policy_output(s, FACTS["mvrv"]))
        ops = {a["op"] for a in out}
        self.assertEqual(ops, {"initialize", "updateVerifier", "verifyAggregateProof"})

    def test_old_policy_cannot_run_on_mvrv(self):
        s = {"own": 1, "rollup": 0, "lv": [], "lvv": [], "log": []}
        self.assertTrue(rollup_policy_throws(s, FACTS["mvrv"]))

    def test_old_policy_cannot_run_on_submitter(self):
        s = {"t": 0, "own": 1, "min_stake": 1, "dep": 1, "rew": 1, "srem": 1,
             "reg": [], "stake": [], "wdr": [], "wbi": [], "log": []}
        self.assertTrue(rollup_policy_throws(s, FACTS["submitter"]))

    def test_old_policy_cannot_run_on_messenger(self):
        s = {"t": 0, "own": 1, "maxr": 0, "mrt": [], "pri": [], "mst": [], "wl": [],
             "dr": [], "paused": False, "log": []}
        self.assertTrue(rollup_policy_throws(s, FACTS["l1messenger"]))


@unittest.skipUnless(_bend_available(), "needs bend to compile the model")
class TestDerivedPolicyWitnesses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT))
        from holon.mpipeline import CompiledMachine
        cls.cms = {k: CompiledMachine.build(v) for k, v in FACTS.items()}

    def check(self, machine, law):
        cm = self.cms[machine]
        res = cm.explore(law)
        self.assertIsNotNone(res.get("witness"), f"{machine}: explore found no witness: {res}")
        ev = cm.evaluate(law, res["witness"])
        self.assertEqual(ev["claims"], [False], f"{machine}: witness does not refute the claim: {ev}")
        return res["witness"]

    def test_submitter_stake_stays_zero_false(self):
        # forall trace from s0, stake of sub 2 stays 0
        w = self.check("submitter", law_forall_trace("stake_of", [{"nat": 2}], {"nat": 0}))
        self.assertTrue(any(a.get("op") == "stake" for a in w["p"]))

    def test_messenger_replay_count_stays_zero_false(self):
        w = self.check("l1messenger", law_forall_trace("times_of", [{"nat": 1}], {"nat": 0}))
        self.assertTrue(any(a.get("op") in ("sendMessage", "sendMessage2", "replayMessage") for a in w["p"]))

    def test_mvrv_latest_verifier_stays_zero_false(self):
        w = self.check("mvrv", law_forall_trace("verifier_of", [{"nat": 0}, {"nat": 1}], {"nat": 0}))
        self.assertTrue(any(a.get("op") == "updateVerifier" for a in w["p"]))
