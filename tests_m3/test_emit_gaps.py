"""M3 R7: proj[log] erasure, conjunction counter-laws, messenger t=1.

Drives the real pipeline (mpipeline.run_m1, no_registry) on the test
milestone laws/TEST_r7 — statuses come from the checker only.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "spec" / "M3" / "extracted" / "l1messenger.json"


def _bend_available() -> bool:
    return shutil.which("bend") is not None or (Path.home() / ".holon/bin/bend").exists()


@unittest.skipUnless(_bend_available(), "needs bend to compile the model")
class TestEmitGaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(ROOT))
        from holon import mpipeline
        cls._td = tempfile.TemporaryDirectory()
        td = Path(cls._td.name)
        mpipeline.run_m1("TEST_r7", None, str(td / "out"), str(td / "gen"),
                         no_registry=True, log=lambda *a: None)
        cls.out = {}
        for p in (td / "out").glob("L_*.json"):
            r = json.loads(p.read_text())
            cls.out[r["law_id"]] = r

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()

    def test_proj_log_law_proved(self):
        # proj [log] now emits a View omitting log; the law is true (a reverted
        # step changes only the log) and the checker accepts it
        self.assertEqual(self.out["L_r7_proj_log"]["status"], "PROVED")

    def test_conjunction_refutes_lowest_false_conjunct(self):
        r = self.out["L_r7_conj_false"]
        self.assertEqual(r["status"], "REFUTED")
        self.assertEqual(r["refuted_conjunct"], 1)
        # counter-law accepted by Bend
        self.assertEqual(r["checker"]["marker"], "ALL PROOFS CHECK")

    def test_true_conjunction_proved(self):
        self.assertEqual(self.out["L_r7_conj_true"]["status"], "PROVED")


@unittest.skipUnless(_bend_available(), "needs bend to compile the model")
class TestMessengerT1(unittest.TestCase):
    def test_s0_timestamp_is_one(self):
        f = json.loads(FACTS.read_text())
        self.assertEqual(f["initial"]["t"], 1)

    def test_send_then_replay_same_time_is_enqueued(self):
        from holon.mpipeline import CompiledMachine
        from holon.mreplay import model_logs
        cm = CompiledMachine.build(FACTS)
        tr = [{"op": "sendMessage", "who": 1, "to": 0, "val": 0, "gl": 0, "xh": 1, "value": 0, "mn": 0, "amt": 0},
              {"op": "replayMessage", "who": 1, "xh": 1, "value": 0, "qi": 0, "from": 0, "mn": 0, "amt": 0}]
        obs = model_logs(cm, [tr])[0]
        # at t=0 the send would leave messageSendTimestamp == 0 and the replay
        # would read "not enqueued" (reason 2); at t=1 both steps succeed
        self.assertEqual(obs, [{"$": "O_Ok"}, {"$": "O_Ok"}])
