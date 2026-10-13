"""I59 build: offline checks of holon.historical's pieces (no network, no chain data). Not a preregistered test:
the preregistered contract is tests_m2/test_historical.py. These pin behaviours the contract relies on:
provider-independent item bytes, strict ABI decoding, gap computation of the resumable state, host-only sources
and secret scrubbing, and the replay's linkage helper semantics."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import holon_module


class TestCanonicalItems(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = holon_module("holon.historical.store")

    def test_provider_differences_do_not_change_the_bytes(self):
        a = {"address": "0xABC", "topics": ["0xAA"], "data": "0x", "blockNumber": "0x0a", "blockHash": "0xBB",
             "transactionHash": "0xCC", "transactionIndex": "0x1", "logIndex": "0x02", "removed": False}
        b = {"logIndex": "0x2", "transactionIndex": "0x1", "transactionHash": "0xcc", "blockHash": "0xbb",
             "blockNumber": "0xa", "data": "0x", "topics": ["0xaa"], "address": "0xabc", "blockTimestamp": "0x5"}
        self.assertEqual(self.S.canon_bytes(a, "log"), self.S.canon_bytes(b, "log"))

    def test_a_tx_without_blobs_has_an_empty_list(self):
        tx = {"hash": "0x1", "type": "0x2", "input": "0x", "blockNumber": "0x1"}
        self.assertEqual(json.loads(self.S.canon_bytes(tx, "tx"))["blobVersionedHashes"], [])

    def test_the_snapshot_refuses_the_repo_and_reports_gaps(self):
        with self.assertRaises(self.S.StoreError):
            self.S.resolve_snapshot(str(self.S.ROOT / "results"))
        with tempfile.TemporaryDirectory() as d:
            snap = self.S.Snapshot(Path(d))
            snap.page_done(10, 19, "h", [])
            snap.page_done(30, 39, "h", [])
            self.assertEqual(snap.covered(5, 45), [(5, 9), (20, 29), (40, 45)])
            self.assertEqual(snap.covered(10, 19), [])
            sha = snap.put(b"x" * 100, gz=True)
            self.assertEqual(snap.read(sha), b"x" * 100)
            snap.close()


class TestAbi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.A = holon_module("holon.historical.abi")
        cls.fn = {"name": "commitBatch", "type": "function", "inputs": [{"name": "batchDataInput", "type": "tuple", "components": [
            {"name": "version", "type": "uint8"}, {"name": "parentBatchHeader", "type": "bytes"},
            {"name": "lastBlockNumber", "type": "uint64"}, {"name": "numL1Messages", "type": "uint16"},
            {"name": "prevStateRoot", "type": "bytes32"}, {"name": "postStateRoot", "type": "bytes32"},
            {"name": "withdrawalRoot", "type": "bytes32"}]}]}

    def encode(self, version=2, header=b"\x02" * 257, num=3):
        w = lambda x: x.to_bytes(32, "big")  # noqa: E731
        head = w(32)                                     # offset of the tuple
        body = w(version) + w(7 * 32) + w(99) + w(num) + b"\x11" * 32 + b"\x22" * 32 + b"\x33" * 32
        pad = header + b"\x00" * (-len(header) % 32)
        return bytes.fromhex(self.A.selector(self.A.signature(self.fn))[2:]) + head + body + w(len(header)) + pad

    def test_the_pinned_selector(self):
        self.assertEqual(self.A.selector(self.A.signature(self.fn)), "0x41f756da")

    def test_a_clean_call_decodes(self):
        d = self.A.decode(self.fn, self.encode())
        self.assertEqual(d["batchDataInput"]["parentBatchHeader"], b"\x02" * 257)
        self.assertEqual((d["batchDataInput"]["version"], d["batchDataInput"]["numL1Messages"]), (2, 3))

    def test_dirty_or_truncated_calls_do_not_decode(self):
        with self.assertRaises(self.A.AbiError):
            self.A.decode(self.fn, self.encode(version=256))
        with self.assertRaises(self.A.AbiError):
            self.A.decode(self.fn, self.encode(num=1 << 16))
        with self.assertRaises(self.A.AbiError):
            self.A.decode(self.fn, self.encode()[:-64])
        with self.assertRaises(self.A.AbiError):
            self.A.decode(self.fn, b"\x00\x00\x00\x00" + self.encode()[4:])


class TestNet(unittest.TestCase):
    def test_hosts_only_and_secrets_scrubbed(self):
        N = holon_module("holon.historical.net")
        self.assertEqual(N.host("https://eth-mainnet.example.com/v2/SECRETKEY123?x=1"), "eth-mainnet.example.com")
        old = os.environ.get("ETH_RPC_URL")
        os.environ["ETH_RPC_URL"] = "https://rpc.example.com/v2/SECRETKEY123"
        try:
            self.assertNotIn("SECRETKEY123", N.scrub("failed: https://rpc.example.com/v2/SECRETKEY123 and SECRETKEY123"))
        finally:
            if old is None:
                os.environ.pop("ETH_RPC_URL", None)
            else:
                os.environ["ETH_RPC_URL"] = old

    def test_versioned_hash(self):
        F = holon_module("holon.historical.fetch")
        import hashlib
        c = bytes(range(48))
        self.assertEqual(F.versioned_hash(c), "0x01" + hashlib.sha256(c).hexdigest()[2:])


if __name__ == "__main__":
    unittest.main()
