"""M3 R9: code-presence guard on high-level external calls (option c).

require(addr != 0) is emitted only when the callee address is a modelled
value (state register, action input, or let/computed). Unmodelled,
oracle_addr and spec-constant targets get no guard and no inputs -- each
site becomes an `assumed` coverage item.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
MORPH = Path(os.environ.get("HOLON_MORPH_DIR", Path.home() / "ext" / "morph"))

REASON = "call to address without code"


def _guard_sites(facts_path):
    f = json.loads(Path(facts_path).read_text())
    rid = next((k for k, v in f["reasons"].items() if v == REASON), None)
    sites = []
    if rid:
        for a in f["actions"]:
            for g in a.get("guards", []):
                if str(g.get("reason")) == rid:
                    sites.append((a["name"], g["require"], g["src"]))
    return sites


def _new_inputs(facts_path):
    """Inputs that HEAD's committed facts do not have (none allowed)."""
    import subprocess as sp
    old = json.loads(sp.check_output(["git", "-C", str(ROOT), "show",
                                      f"HEAD:{facts_path}"]).decode())
    new = json.loads(Path(facts_path).read_text())
    old_in = {a["name"]: [i[0] for i in a.get("inputs", [])] for a in old["actions"]}
    diff = {}
    for a in new["actions"]:
        if [i[0] for i in a.get("inputs", [])] != old_in.get(a["name"]):
            diff[a["name"]] = (old_in.get(a["name"]), [i[0] for i in a.get("inputs", [])])
    return diff


class TestCodePresenceFacts(unittest.TestCase):
    def test_mvrv_guards(self):
        sites = _guard_sites(ROOT / "spec/M3/extracted/mvrv.json")
        self.assertEqual(
            {(n, json.dumps(r)) for n, r, _ in sites},
            {("updateVerifier", json.dumps(["!=", "rollup", 0])),
             ("verifyAggregateProof", json.dumps(["!=", "v_verifier", 0]))})

    def test_other_specs_have_no_guards(self):
        """Unmodelled/oracle_addr/queue targets get no guard and no inputs."""
        for f in ("submitter", "l1messenger", "morph_rollup"):
            self.assertEqual(_guard_sites(ROOT / f"spec/M3/extracted/{f}.json"), [], f)
            self.assertEqual(_new_inputs(f"spec/M3/extracted/{f}.json"), {}, f)

    def test_no_action_input_added(self):
        for f in ("mvrv", "submitter", "l1messenger", "morph_rollup"):
            self.assertEqual(_new_inputs(f"spec/M3/extracted/{f}.json"), {}, f)

    def test_assumed_debt_items(self):
        """Every unmodelled-address call site records an `assumed` item."""
        cov = json.loads((ROOT / "spec/M3/coverage/l1messenger.json").read_text())
        assumed = [i for i in cov["items"] if i["kind"] == "assumed"]
        self.assertTrue(len(assumed) >= 3, assumed)
        self.assertTrue(all("assumed nonzero with code" in i["reason"] for i in assumed))


class TestTranslator(unittest.TestCase):
    """_addr_expr / _addr_bound on synthetic translator state."""

    @classmethod
    def setUpClass(cls):
        from holon.frontends.solidity import astload, extract
        spec = extract.load_spec(str(ROOT / "holon/frontends/solidity/specs/mvrv.spec.json"))
        cls.world = astload.run_solc(spec, MORPH)
        cls.spec = spec

    def _tr(self):
        from holon.frontends.solidity.translate import Translator
        return Translator(self.world, self.spec)

    def test_unmodelled_target_no_input_added(self):
        tr = self._tr()
        tr.fact_inputs = set()
        self.assertIsNone(tr._addr_expr(("unmodelled", "messageQueue")))
        self.assertIsNone(tr._addr_expr(("addr", "rollupContract")))
        self.assertIsNone(tr._addr_expr(("map", "messageQueue")))
        self.assertEqual(tr.fact_inputs, set())

    def test_modelled_target_kept(self):
        tr = self._tr()
        tr.fact_inputs = set()
        tr.let_names = {}
        tr.pending = []
        tr.guards = []
        tr.hoist_bound = {}
        # rollup is a scalar state register in mvrv
        self.assertEqual(tr._addr_expr("rollup"), "rollup")
        # a let-bound name
        tr.let_names = {"v": ["v_verifier"]}
        self.assertEqual(tr._addr_expr("v_verifier"), "v_verifier")
        # a pending/emitted let
        tr.let_names = {}
        tr.guards = [{"let": "w9", "expr": 0}]
        self.assertEqual(tr._addr_expr("w9"), "w9")


def _bend_available() -> bool:
    return shutil.which("bend") is not None or (Path.home() / ".holon/bin/bend").exists()


@unittest.skipUnless(_bend_available(), "needs bend to compile the model")
class TestMvrvModel(unittest.TestCase):
    def test_unregistered_vap_reverts_in_model(self):
        from holon.mpipeline import CompiledMachine
        from holon.mreplay import model_logs
        cm = CompiledMachine.build(ROOT / "spec/M3/extracted/mvrv.json")
        logs = model_logs(cm, [[{"op": "verifyAggregateProof", "who": 5, "v": 3, "idx": 1}]])
        self.assertEqual(logs, [[{"$": "O_Rev", "code": 3}]])


if __name__ == "__main__":
    unittest.main()
