"""S6 offline unit tests: keccak vectors, atom map, ABI decode, fixture schema.

Everything here runs without bend/node/RPC — the heavy end-to-end check is in
test_s6_replay.py, gated on HOLON_REPLAY=1 (like tests_m1's replay test).
"""
import json
import unittest
from pathlib import Path

from holon.hist.replay_keccak import keccak256, selector
from holon.hist.replay_atoms import AtomMap, canon_b32, canon_addr, ZERO32, ZERO_VH
from holon.hist.replay import decode_commit_input, METHOD_BY_SELECTOR
from tests._util import ROOT

FIX = ROOT / "replay" / "M2" / "corpus" / "fixtures"


class TestKeccak(unittest.TestCase):
    def test_vectors(self):
        # canonical keccak-256 vectors (keccak, not FIPS sha3)
        self.assertEqual(keccak256(b"").hex(),
                         "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7"
                         "bfad8045d85a470")
        self.assertEqual(keccak256(b"abc").hex(),
                         "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f5"
                         "8fa12d6c45")
        self.assertEqual(selector("commitBatch((uint8,bytes,uint64,uint16,"
                                  "bytes32,bytes32,bytes32))").hex(), "41f756da")


class TestAtoms(unittest.TestCase):
    def test_reserved_and_fresh(self):
        m = AtomMap()
        self.assertEqual(m.atom(ZERO32), 0)
        self.assertEqual(m.atom(ZERO_VH), 1)
        a = m.atom("0x" + "ab" * 32)
        b = m.atom("0x" + "cd" * 32)
        self.assertGreaterEqual(a, 10_000)
        self.assertNotEqual(a, b)
        self.assertEqual(m.atom("0x" + "ab" * 32), a)  # idempotent
        self.assertEqual(m.concrete(a), "0x" + "ab" * 32)

    def test_canon(self):
        self.assertEqual(canon_b32("0x" + "0" * 63), "0x" + "0" * 64)
        self.assertEqual(canon_addr("0xabc"), "0x" + "0" * 37 + "abc")


class TestCalldataDecode(unittest.TestCase):
    def test_commit_batch(self):
        # synthetic commitBatch calldata: selector + tuple head + dyn bytes
        ph = bytes.fromhex("02" + "00" * 256)  # fake v2 parent header
        body = (
            (2).to_bytes(32, "big") +                       # version
            (7 * 32).to_bytes(32, "big") +                  # offset to bytes
            (12345).to_bytes(32, "big") +                   # lastBlockNumber
            (7).to_bytes(32, "big") +                       # numL1Messages
            bytes.fromhex("aa" * 32) +                      # prevStateRoot
            bytes.fromhex("bb" * 32) +                      # postStateRoot
            bytes.fromhex("cc" * 32) +                      # withdrawalRoot
            len(ph).to_bytes(32, "big") + ph +
            b"\x00" * ((32 - len(ph) % 32) % 32))
        inp = decode_commit_input("commitBatch",
                                  bytes.fromhex("41f756da") + body)
        self.assertEqual(inp["version"], 2)
        self.assertEqual(inp["lastBlockNumber"], 12345)
        self.assertEqual(inp["numL1Messages"], 7)
        self.assertEqual(inp["prevStateRoot"], "0x" + "aa" * 32)
        self.assertEqual(inp["postStateRoot"], "0x" + "bb" * 32)
        self.assertEqual(inp["parentBatchHeader"], ph)


@unittest.skipUnless(FIX.exists(), "fixture not built yet")
class TestFixtureShape(unittest.TestCase):
    def test_manifest_schema(self):
        man = json.loads((FIX / "manifest.json").read_text())
        self.assertEqual(man["chain"], "ethereum-mainnet")
        self.assertIn(man["rollup_proxy"], (
            "0x759894ced0e6af42c26668076ffa84d02e3cef60",))
        self.assertLessEqual(len(man["commits"]), 5)
        idxs = [c["batch_index"] for c in man["commits"]]
        self.assertEqual(idxs, sorted(idxs))
        for c in man["commits"]:
            for k in ("batch_index", "tx", "block", "method",
                      "calldata_sha256", "blob_versioned_hashes",
                      "blobs_sha256", "post"):
                self.assertIn(k, c)
            for k in ("committedBatches", "committedStateRoots",
                      "lastCommittedBatchIndex"):
                self.assertIn(k, c["post"])

    def test_payloads_resolve(self):
        man = json.loads((FIX / "manifest.json").read_text())
        for c in man["commits"]:
            p = FIX / "payload" / f"{c['calldata_sha256']}.json"
            self.assertTrue(p.exists(), c["calldata_sha256"])
            obj = json.loads(p.read_text())
            self.assertEqual(obj["sha256"], c["calldata_sha256"])
            sel = obj["data"][2:10]
            self.assertEqual(obj["data"][2:10],
                             {"commitBatch": "41f756da",
                              "commitState": "67caa37a",
                              "commitBatchWithProof": "2a58a723"}[
                                  c["method"]] if c["method"] in
                             METHOD_BY_SELECTOR.values() or True else sel)

    def test_records_present(self):
        man = json.loads((FIX / "manifest.json").read_text())
        for c in man["commits"]:
            p = FIX / "commits" / f"{c['batch_index']}.json"
            self.assertTrue(p.exists())
            rec = json.loads(p.read_text())
            self.assertEqual(rec["batch_index"], c["batch_index"])
            self.assertEqual(rec["tx"], c["tx"])
            for k in ("scalars", "queue", "window", "residues",
                      "committedBatches"):
                self.assertIn(k, rec["pre"])
            w = rec["pre"]["window"]
            self.assertEqual(w["expected_len"] - len(w["missing_inputs"]),
                             len(w["entries"]))
            # window must end at lastCommittedBatchIndex-? actually at lci
            if w["entries"]:
                self.assertEqual(w["entries"][-1]["index"],
                                 c["batch_index"] - 1)


if __name__ == "__main__":
    unittest.main()
