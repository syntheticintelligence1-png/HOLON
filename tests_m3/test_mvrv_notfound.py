"""M3: MVRV getVerifier not-found as an extracted call-site revert.

Model-eval assertions are the faithful outcomes of the extracted facts
(vap(3,1) ok from s0 because latest.s=0 skips the not-found branch and the
oracle verifyBatch always succeeds in the model; see replay/M3/
mvrv_notfound_report.json for the on-chain extcodesize revert). Near-miss
cases check the structural recogniser leaves unmatched loops as
untranslated_loop.
"""
import json
import os
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MORPH = Path(os.environ.get("HOLON_MORPH_DIR", Path.home() / "ext" / "morph"))
SOLC = Path(os.environ.get("HOLON_SOLC", Path.home() / ".local/share/svm/0.8.24/solc-0.8.24"))
FACTS = ROOT / "spec" / "M3" / "extracted" / "mvrv.json"


def _bend_available() -> bool:
    return shutil.which("bend") is not None or (Path.home() / ".holon/bin/bend").exists()


def _world_available() -> bool:
    return MORPH.exists() and SOLC.exists() and shutil.which("solc") is not None or SOLC.exists()


@unittest.skipUnless(_bend_available(), "needs bend to compile the model")
class TestMvrvModelOutcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT))
        from holon.mpipeline import CompiledMachine
        from holon.mreplay import model_logs
        cls.cm = CompiledMachine.build(FACTS)
        cls.model_logs = staticmethod(model_logs)

    def obs(self, trace):
        return self.model_logs(self.cm, [trace])[0][-1]

    def test_unregistered_vap_ok(self):
        # v=3 unregistered: latest.s=0 <= idx -> not-found branch unreachable;
        # model's oracle verifyBatch succeeds. On chain this reverts with empty
        # data (extcodesize), covered by the unmodelled_revert coverage item.
        obs = self.obs([{"op": "verifyAggregateProof", "who": 5, "v": 3, "idx": 1}])
        self.assertEqual(obs, {"$": "O_Ok"})

    def test_registered_latest_not_found_rev(self):
        upd = {"op": "updateVerifier", "who": 1, "v": 3, "st": 10, "a": 7, "lfi": 0}
        obs = self.obs([upd, {"op": "verifyAggregateProof", "who": 5, "v": 3, "idx": 9}])
        # ErrorVerifierNotFound, facts reasons id 6
        self.assertEqual(obs, {"$": "O_Rev", "code": 6})

    def test_registered_latest_at_start_ok(self):
        upd = {"op": "updateVerifier", "who": 1, "v": 3, "st": 10, "a": 7, "lfi": 0}
        obs = self.obs([upd, {"op": "verifyAggregateProof", "who": 5, "v": 3, "idx": 10}])
        self.assertEqual(obs, {"$": "O_Ok"})

    def test_legacy_cover_ok(self):
        tr = [{"op": "updateVerifier", "who": 1, "v": 3, "st": 5, "a": 7, "lfi": 0},
              {"op": "updateVerifier", "who": 1, "v": 3, "st": 10, "a": 8, "lfi": 5},
              {"op": "verifyAggregateProof", "who": 5, "v": 3, "idx": 9}]
        self.assertEqual(self.obs(tr), {"$": "O_Ok"})

    def test_legacy_no_cover_rev(self):
        tr = [{"op": "updateVerifier", "who": 1, "v": 3, "st": 5, "a": 7, "lfi": 0},
              {"op": "updateVerifier", "who": 1, "v": 3, "st": 10, "a": 8, "lfi": 5},
              {"op": "verifyAggregateProof", "who": 5, "v": 3, "idx": 4}]
        self.assertEqual(self.obs(tr), {"$": "O_Rev", "code": 6})


@unittest.skipUnless(_world_available(), "needs morph tree + solc to build the AST world")
class TestScanLoopRecogniser(unittest.TestCase):
    """The recogniser is structural: near-miss loops must stay untranslated_loop."""

    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT))
        from holon.frontends.solidity import astload, extract
        from holon.frontends.solidity.translate import Translator
        spec = extract.load_spec(str(ROOT / "holon/frontends/solidity/specs/mvrv.spec.json"))
        morph = Path(os.path.expanduser(os.environ.get(spec["morph_root_env"], spec["morph_root_default"])))
        cls.world = astload.run_solc(spec, morph)
        cls.spec = spec
        cls.Translator = Translator
        u = cls.world.units["contracts/l1/rollup/MultipleVersionRollupVerifier.sol"]
        fn = [n for n in u.find("FunctionDefinition", name="getVerifier")][0]

        def find(n, t):
            if isinstance(n, dict):
                if n.get("nodeType") == t:
                    yield n
                for v in n.values():
                    if isinstance(v, (dict, list)):
                        yield from find(v, t)
            elif isinstance(n, list):
                for x in n:
                    yield from find(x, t)
        cls.st = [n for n in find(fn, "ForStatement")][0]
        cls.fn = fn

    def _tr(self):
        tr = self.Translator(self.world, self.spec)
        tr.reasons = {}
        tr.cur_fn = ("MultipleVersionRollupVerifier", "getVerifier")
        tr.input_map = {"_version": "v", "_batchIndex": "idx", "v": "v", "idx": "idx",
                        "lv": "lv", "lvv": "lvv"}
        tr.input_names = set(tr.input_map)
        tr.fact_inputs = {"v", "idx", "lv", "lvv"}
        tr.local_names = {}
        tr.pending = []
        tr.pending_notes = []
        tr.let_values = {}
        tr.conds = []
        # bind the pre-loop lets the way the def body does (_verifier, _length)
        tr.env["_verifier"] = ("shadow", "_verifier", {"kind": "abs_map", "field": "lv", "record": "V"}, "v", {})
        tr.env["found"] = ("unbound", "found")
        tr.env["_length"] = "v_length"
        tr.let_values["_verifier"] = ["call", "nth_rec", "lv", "v"]
        tr.let_values["v_length"] = ["call", "len", ["call", "nthl", "lvv", "v"]]
        return tr

    def test_positive_match(self):
        import copy
        tr = self._tr()
        self.assertTrue(tr.h_scan_loop(copy.deepcopy(self.st)))
        self.assertEqual(tr.env["found"], ["call", "lv_le_has", ["call", "nthl", "lvv", "v"], "idx"])

    def test_no_break_is_near_miss(self):
        import copy
        st = copy.deepcopy(self.st)
        body = st["body"]["statements"][1]["trueBody"]["statements"]
        assert body[-1]["nodeType"] == "Break"
        body.pop()  # remove the break
        tr = self._tr()
        self.assertFalse(tr.h_scan_loop(st))

    def test_non_bool_flag_is_near_miss(self):
        import copy
        st = copy.deepcopy(self.st)
        fasg = st["body"]["statements"][1]["trueBody"]["statements"][0]["expression"]
        fasg["leftHandSide"]["name"] = "i_seen"  # a name never declared as bool
        tr = self._tr()
        self.assertFalse(tr.h_scan_loop(st))

    def test_wrong_step_is_near_miss(self):
        import copy
        st = copy.deepcopy(self.st)
        st["loopExpression"]["expression"]["operator"] = "++"
        tr = self._tr()
        self.assertFalse(tr.h_scan_loop(st))
