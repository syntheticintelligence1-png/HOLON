"""M3 R8: the go-machine -> facts lifter (holon/frontends/go/lift.py)."""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from holon.frontends.go import lift as lift_mod

ROOT = Path(__file__).resolve().parents[1]
GO = ROOT / "spec" / "M2" / "extracted" / "go_batchdata.json"
LIFTED = ROOT / "spec" / "M3" / "extracted" / "go_batchdata_machine.json"
HAND = ROOT / "spec" / "M1" / "facts" / "morph_batchdata.json"


def _bend_available() -> bool:
    return shutil.which("bend") is not None or (Path.home() / ".holon/bin/bend").exists()


def _mini_machine(**over):
    m = {"format": "holon-extracted/go-machine/0.1", "extractor": "test",
         "target": {"repo": "x", "commit": "c"},
         "machines": [{"type": "T", "types": {},
                      "state": [["payload", "List<Nat>", "f"], ["log", "List<Obs>", "o"]],
                      "ghost_state": [], "initial": {"payload": [], "log": []},
                      "actions": [{"name": "put", "inputs": [["payload", "List<Nat>"]],
                                   "guards": [{"let": "payload'", "expr": "payload"}], "effects": {}}],
                      "observers": {}, "coverage_debt": []}],
         "coverage": {}}
    m.update(over)
    return m


class TestSanitiser(unittest.TestCase):
    def test_prime_identifier(self):
        self.assertEqual(lift_mod.sanitize("payload'"), "payload_p")
        self.assertEqual(lift_mod.sanitize("blockContexts'"), "blockcontexts_p")

    def test_legal_names_kept(self):
        self.assertEqual(lift_mod.sanitize("txsPayloadV2"), "txspayloadv2")
        # already-legal names are NOT sanitised at all (see Renamer.map)
        R = lift_mod.Renamer()
        self.assertEqual(R.map("txsPayloadV2"), "txsPayloadV2")

    def test_collision_is_hard_error(self):
        R = lift_mod.Renamer()
        R.map("a-b")
        with self.assertRaises(lift_mod.LiftError):
            R.map("a_b")  # a-b -> a_b collides

    def test_input_state_clash(self):
        m = _mini_machine()
        facts, _ = lift_mod.lift(m, "x.json")
        self.assertEqual(facts["actions"][0]["inputs"], [["in_payload", "List<Nat>"]])
        self.assertEqual(facts["extraction"]["renames"]["payload@input"], "in_payload")

    def test_determinism(self):
        src = "spec/M2/extracted/go_batchdata.json"  # as invoked by the CLI
        gm = json.loads(GO.read_text())
        a = lift_mod.lift(gm, src)[0]
        b = lift_mod.lift(gm, src)[0]
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(json.loads(LIFTED.read_text()), a)


@unittest.skipUnless(_bend_available(), "needs bend to compile the model")
class TestLiftedModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon.mpipeline import CompiledMachine
        cls.hand = CompiledMachine.build(HAND)
        cls.lifted = CompiledMachine.build(LIFTED)

    def test_lifted_facts_compile(self):
        from holon import bend
        cfg = bend.config(ROOT)
        r = bend.check(self.lifted.source, cfg)
        self.assertTrue(r.ok, r.out[:500])

    def test_small_differential(self):
        """Hand and lifted machines agree on obs logs over short batchdata traces."""
        from holon.mreplay import model_logs
        k = 1
        cands = [{"op": "append", "bctx": [k] * 8, "payload": [k]},
                 {"op": "append", "bctx": [k] * 8, "payload": []},
                 {"op": "txsPayloadV2"}]

        def lift_act(a):
            if a["op"] == "append":
                return {"op": "append", "blockContext": a["bctx"], "in_txsPayload": a["payload"]}
            return dict(a)

        hand_traces, lift_traces = [], []
        frontier = [[]]
        for _ in range(2):
            nxt = []
            for tr in frontier:
                for a in cands:
                    nxt.append(tr + [a])
            obs = model_logs(self.hand, nxt)
            frontier = [t for t, o in zip(nxt, obs) if all(x.get("$") == "O_Ok" for x in o)]
        for tr in frontier:
            hand_traces.append(tr)
            lift_traces.append([lift_act(a) for a in tr])
        oh = model_logs(self.hand, hand_traces)
        ol = model_logs(self.lifted, lift_traces)
        self.assertEqual(oh, ol)


if __name__ == "__main__":
    unittest.main()
