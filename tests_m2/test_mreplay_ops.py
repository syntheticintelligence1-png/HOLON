"""Audit M2/1 F-M2-16: the mreplay op table and row encoding are generated from facts.actions.

holon.mreplay.op_table numbers the facts' actions in facts order and the deployment-history pseudo-step after
them; encode_step writes the op code and the step's inputs in facts order. The M1 replay harness
(replay/M1/solidity/HolonTraceReplay.t.sol) decodes fixed rows, so the generated rows must be exactly the rows of
the old hand-written encoder: pinned here against that encoder (copied below as the reference) on every action
kind and on the seeded refinement corpus, and the M1 replay outputs therefore stay unchanged.
"""
import re
import unittest

from tests_m2._m2 import ROOT, holon_module, load_json

FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
HARNESS = ROOT / "replay" / "M1" / "solidity" / "HolonTraceReplay.t.sol"
# the hand table and encoder of holon/mreplay.py before the fix (the harness's numbering and row layout)
HAND_OPS = {"commitBatch": 1, "commitState": 2, "commitBatchWithProof": 3, "revertBatch": 4, "challengeState": 5,
            "proveState": 6, "finalizeBatch": 7, "setPause": 8, "sendMessage": 9, "wait": 10, "@legacy_eta2": 11}


def hand_encode(a: dict) -> list[int]:
    w = [0] * 13
    w[0] = HAND_OPS[a["op"]]
    if a["op"] in ("commitBatch", "commitState", "commitBatchWithProof"):
        bl = a["blobs"]
        w[1:12] = [a["who"], a["ver"], a["parent"], a["n"], a["lbn"], a["prev"], a["post"], len(bl),
                   bl[0] if bl else 0, bl[1] if len(bl) > 1 else 0, a.get("proof", 0)]
    elif a["op"] == "revertBatch":
        w[1:4] = [a["who"], a["idx"], a["count"]]
    elif a["op"] == "challengeState":
        w[1:4] = [a["who"], a["idx"], a["value"]]
    elif a["op"] == "proveState":
        w[1:4] = [a["who"], a["idx"], a["proof"]]
    elif a["op"] == "finalizeBatch":
        w[1:3] = [a["who"], a["idx"]]
    elif a["op"] == "setPause":
        w[1:3] = [a["who"], 1 if a["status"] else 0]
    elif a["op"] == "sendMessage":
        w[1] = a["who"]
    elif a["op"] == "wait":
        w[1] = a["dt"]
    elif a["op"] == "@legacy_eta2":
        w[1] = a["root"]
    return w


def samples() -> list[dict]:
    c = {"who": 2, "ver": 1, "parent": 3, "n": 4, "lbn": 5, "prev": 6, "post": 7}
    out = []
    for op in ("commitBatch", "commitState", "commitBatchWithProof"):
        for bl in ([], [9], [9, 8], [9, 8, 7]):
            out.append({"op": op, **c, "blobs": bl, **({"proof": 1} if op == "commitBatchWithProof" else {})})
    out += [{"op": "revertBatch", "who": 1, "idx": 2, "count": 3}, {"op": "challengeState", "who": 4, "idx": 1, "value": 9},
            {"op": "proveState", "who": 2, "idx": 1, "proof": 2}, {"op": "finalizeBatch", "who": 5, "idx": 1},
            {"op": "setPause", "who": 1, "status": True}, {"op": "setPause", "who": 1, "status": False},
            {"op": "sendMessage", "who": 3}, {"op": "wait", "dt": 11}, {"op": "@legacy_eta2", "root": 123}]
    return out


class TestGeneratedOps(unittest.TestCase):
    def setUp(self):
        self.R = holon_module("holon.mreplay")
        self.facts = load_json(FACTS)

    def test_no_hand_table(self):
        self.assertFalse(hasattr(self.R, "OPS"))

    def test_op_table_is_the_harness_numbering(self):
        self.assertEqual(self.R.op_table(self.facts), HAND_OPS)

    def test_harness_decodes_every_generated_op(self):
        decoded = {int(x) for x in re.findall(r"\bop == (\d+)", HARNESS.read_text(encoding="utf-8"))}
        self.assertEqual(decoded, set(self.R.op_table(self.facts).values()))

    def test_rows_equal_the_hand_encoder_on_every_action_kind(self):
        for a in samples():
            with self.subTest(step=a):
                self.assertEqual(self.R.encode_step(a, self.facts), hand_encode(a))

    def test_rows_equal_the_hand_encoder_on_the_seeded_corpus(self):
        """The first traces of the refinement corpus (seed 20261011, as `holon replay --milestone M1` draws it)."""
        P = holon_module("holon.mpipeline")
        cm = P.CompiledMachine.build(FACTS, holon_module("holon.bend").config(ROOT))
        corpus = self.R.random_corpus(cm, 20, seed=20261011)
        n = 0
        for tr in corpus:
            for a in tr:
                self.assertEqual(self.R.encode_step(a, self.facts), hand_encode(a), a)
                n += 1
        self.assertGreater(n, 60)

    def test_model_logs_apply_the_history_as_before(self):
        P = holon_module("holon.mpipeline")
        cm = P.CompiledMachine.build(FACTS, holon_module("holon.bend").config(ROOT))
        tr = [{"op": "commitBatch", "who": 2, "ver": 1, "parent": 0, "n": 0, "lbn": 1, "prev": 100, "post": 110,
               "blobs": [17]}, {"op": "@legacy_eta2", "root": 5}, {"op": "wait", "dt": 3}]
        (logs,) = self.R.model_logs(cm, [tr])
        expr = {"fn": "s0", "args": []}
        expr = {"fn": "step", "args": [{"val": P._act_val(cm.m, tr[0])}, expr]}
        expr = {"fn": "mig_eta2", "args": [{"fn": "mig_legacy", "args": [expr]}, {"val": 5}]}   # the old expression
        expr = {"fn": "step", "args": [{"val": P._act_val(cm.m, tr[2])}, expr]}
        (want,) = cm.calls([{"fn": "log_of", "args": [expr]}])
        want = list(reversed(want))
        self.assertEqual(logs, [want[0], None, want[1]])


if __name__ == "__main__":
    unittest.main()
