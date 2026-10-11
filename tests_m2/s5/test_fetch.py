"""Tests for holon.hist.fetch (M2 unit S5).

Every test runs against a scripted in-memory chain: no network, no RPC. The
fake implements the same `rpc`/`http_json`/`http_get` surface as
`holon.hist.fetch.Client`.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from holon.hist import fetch as F  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers to build a scripted chain
# ---------------------------------------------------------------------------

def _calldata(selector: str, tail: bytes = b"\x00" * 32) -> str:
    return "0x" + selector + tail.hex()


def _receipt(tx_hash: str, block: int) -> dict:
    return {
        "transactionHash": tx_hash,
        "blockNumber": hex(block),
        "status": "0x1",
        "gasUsed": "0x5208",
    }


class FakeClient:
    """Scripted drop-in for fetch.Client."""

    def __init__(self, chain: dict):
        self.chain = chain
        self.log = io.StringIO()
        self.rpc_calls: list[tuple[str, list]] = []

    # -- JSON-RPC ---------------------------------------------------------
    def rpc(self, rpc_url: str, method: str, params: list):
        self.rpc_calls.append((method, params))
        c = self.chain
        if method == "eth_blockNumber":
            return hex(max(c["blocks"]))
        if method == "eth_getBlockByNumber":
            n = int(params[0], 16)
            if "ts_fn" in c:
                return {"number": params[0], "timestamp": hex(c["ts_fn"](n))}
            if n not in c["blocks"]:
                return {"number": hex(n), "timestamp": "0x0"}
            return {"number": params[0], "timestamp": hex(c["blocks"][n])}
        if method == "eth_getCode":
            return c.get("code", "0x6000")
        if method == "eth_getStorageAt":
            return c.get("impl_slot", "0x" + "00" * 11 + "aa" * 20 + "00" * 0)
        if method == "eth_call":
            data = params[0]["data"]
            sel = data[2:10]
            if sel == "121dcd50":  # lastCommittedBatchIndex()
                return hex(c.get("lci", 0))
            return "0x" + c["calls"].get(data[2:], "00" * 32)
        if method == "eth_getLogs":
            lo, hi = int(params[0]["fromBlock"], 16), int(params[0]["toBlock"], 16)
            if c.get("max_log_span") and hi - lo + 1 > c["max_log_span"]:
                raise F.FetchError("range too large")
            return [l for l in c["logs"] if lo <= int(l["blockNumber"], 16) <= hi]
        if method == "eth_getTransactionByHash":
            return c["txs"][params[0]]
        if method == "eth_getTransactionReceipt":
            return c["receipts"][params[0]]
        raise AssertionError(f"unexpected rpc {method}")

    def rpc_batch(self, rpc_url: str, calls: list):
        if self.chain.get("no_batch"):
            raise F.FetchError("batches unsupported")
        return [self.rpc(rpc_url, m, p) for m, p in calls]

    # -- plain HTTP -------------------------------------------------------
    def http_json(self, url: str, body=None) -> dict:
        if "blob_sidecars" in url:
            slot = int(url.rsplit("/", 1)[1])
            data = self.chain["beacon"].get(slot)
            if data is None:
                raise F.FetchError(f"no sidecars for slot {slot}")
            return {"data": data}
        if "transactions" in url:
            tx = url.rsplit("/", 1)[1]
            return self.chain["blobscan_txs"][tx]
        raise AssertionError(f"unexpected http_json {url}")

    def http_get(self, url: str) -> bytes:
        return self.chain["http_blobs"][url]


def build_chain(n_commits: int, window_lo: int, window_hi: int,
                blobs: int = 1) -> dict:
    """Deterministic scripted chain: commit i in block window_lo + 10*i."""
    chain = {
        "blocks": {},
        "ts_fn": lambda n: 1790000000 - (window_hi - n) * 12,
        "logs": [],
        "txs": {},
        "receipts": {},
        "calls": {},
        "beacon": {},
        "blobscan_txs": {},
        "http_blobs": {},
        "lci": n_commits,
    }
    for n in range(window_lo - 5, window_hi + 1):
        # uniform 12s spacing ending at window_hi
        chain["blocks"][n] = 1790000000 - (window_hi - n) * 12
    for i in range(1, n_commits + 1):
        block = window_lo + 10 * i
        tx = f"0x{i:064x}"
        commitment = bytes([i & 0xFF]) * 48
        blob = bytes([i & 0xFF]) * 131072
        vh = F.versioned_hash_for_commitment(commitment)
        chain["logs"].append({
            "blockNumber": hex(block),
            "transactionHash": tx,
            "transactionIndex": "0x0",
            "topics": [F.COMMIT_BATCH_TOPIC, hex(i)],
        })
        chain["txs"][tx] = {
            "hash": tx,
            "blockNumber": hex(block),
            "input": _calldata("41f756da", i.to_bytes(32, "big")),
            "type": "0x3" if blobs else "0x2",
            "blobVersionedHashes": [vh] * blobs,
        }
        chain["receipts"][tx] = _receipt(tx, block)
        ts = chain["blocks"][block]
        slot = F.slot_for_timestamp(ts)
        chain["beacon"].setdefault(slot, []).append(
            {"index": "0", "kzg_commitment": "0x" + commitment.hex(),
             "blob": "0x" + blob.hex()})
        ipfs = f"https://blobscan.com/ipfs/blob{i}"
        chain["blobscan_txs"][tx] = {"blobs": [{
            "versionedHash": vh,
            "dataStorageReferences": [{"storage": "ipfs", "url": ipfs}]}]}
        chain["http_blobs"][ipfs] = blob
        idx_hex = i.to_bytes(32, "big").hex()
        chain["calls"][F.encode_call_uint256("2362f03e", i)[2:]] = "aa" * 32
        chain["calls"][F.encode_call_uint256("68589dfa", i)[2:]] = "bb" * 32
    return chain


def run_fetch(chain: dict, out: Path, extra: list[str] | None = None):
    """run() with a FakeClient injected (monkey-patching fetch.Client)."""
    cache = out / "cache"
    argv = ["--snapshot-block", "99999", "--cache", str(cache),
            "--out", str(out / "corpus"), "--min-commits", "0"] + (extra or [])
    orig = F.Client
    fake = FakeClient(chain)

    class _Factory:
        def __call__(self, *a, **k):
            fake.min_interval = 0
            return fake

    F.Client = _Factory()
    try:
        rc = F.run(argv)
    finally:
        F.Client = orig
    return rc, fake


def read_manifest(out: Path) -> dict:
    return json.loads((out / "corpus" / "manifest.json").read_text())


# ---------------------------------------------------------------------------
# Tests: primitives
# ---------------------------------------------------------------------------

class TestKeccak(unittest.TestCase):
    def test_known_vectors(self):
        self.assertEqual(
            F.keccak256(b"").hex(),
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(F.keccak256(b"transfer(address,uint256)")[:4].hex(),
                         "a9059cbb")

    def test_selectors_match_abi(self):
        # Values locked from the IRollup.sol signatures at morph 3e44e79.
        self.assertIn("41f756da", F.SELECTOR_METHODS)
        self.assertIn("67caa37a", F.SELECTOR_METHODS)
        self.assertIn("1544ba3a", F.SELECTOR_METHODS)
        self.assertEqual(F.SELECTOR_METHODS["41f756da"], "commitBatch")
        self.assertEqual(F.SELECTOR_METHODS["67caa37a"], "commitState")
        self.assertEqual(F.SELECTOR_METHODS["1544ba3a"], "commitBatchWithProof")
        self.assertEqual(F._sig("CommitBatch(uint256,bytes32)").hex(),
                         "2c32d4ae151744d0bf0b9464a3e897a1d17ed2f1af71f7c9a75f12ce0d28238f")


class TestHelpers(unittest.TestCase):
    def test_versioned_hash(self):
        vh = F.versioned_hash_for_commitment(b"\x00" * 48)
        self.assertTrue(vh.startswith("0x01"))
        self.assertEqual(len(vh), 66)
        self.assertEqual(vh, F.versioned_hash_for_commitment(b"\x00" * 48))

    def test_method_for_calldata(self):
        self.assertEqual(F.method_for_calldata(bytes.fromhex("41f756da") + b"\x00"),
                         "commitBatch")
        self.assertEqual(F.method_for_calldata(bytes.fromhex("67caa37a")),
                         "commitState")
        self.assertTrue(F.method_for_calldata(b"\xde\xad\xbe\xef").startswith("unknown:"))

    def test_parse_and_sort(self):
        logs = [
            {"topics": [F.COMMIT_BATCH_TOPIC, hex(7)], "transactionHash": "0xa",
             "blockNumber": "0x20", "transactionIndex": "0x0"},
            {"topics": [F.COMMIT_BATCH_TOPIC, hex(3)], "transactionHash": "0xb",
             "blockNumber": "0x10", "transactionIndex": "0x0"},
        ]
        evs = sorted((F.parse_commit_event(l) for l in logs),
                     key=lambda e: (e["batch_index"], e["block"], e["tx_index"]))
        self.assertEqual([e["batch_index"] for e in evs], [3, 7])
        self.assertEqual(evs[0]["tx"], "0xb")

    def test_encode_call(self):
        data = F.encode_call_uint256("2362f03e", 5)
        self.assertTrue(data.startswith("0x2362f03e"))
        self.assertEqual(int(data[-8:], 16), 5)


# ---------------------------------------------------------------------------
# Tests: window + enumeration
# ---------------------------------------------------------------------------

class TestWindowAndEvents(unittest.TestCase):
    def _window(self):
        return build_chain(3, 99000, 99999)

    def test_resolve_window(self):
        chain = self._window()
        chain["ts_fn"] = lambda n: 1790000000 - (200000 - n) * 12
        fake = FakeClient(chain)
        w = F.resolve_window(fake, "rpc://x", 200000, 14)
        target = chain["ts_fn"](200000) - 14 * 86400
        self.assertEqual(w["to_block"], 200000)
        self.assertGreaterEqual(chain["ts_fn"](w["from_block"]), target)
        self.assertLess(chain["ts_fn"](w["from_block"] - 1), target)
        # 14 days at 12s spacing -> exactly 100800 blocks back
        self.assertEqual(w["from_block"], 200000 - 100800)

    def test_events_sorted_and_shrinking(self):
        chain = self._window()
        chain["max_log_span"] = 100  # force chunk shrinking
        fake = FakeClient(chain)
        events = F.fetch_commit_events(
            fake, "rpc://x", "0x759894Ced0e6af42c26668076Ffa84d02E3CeF60",
            {"from_block": 99000, "to_block": 99999})
        self.assertEqual([e["batch_index"] for e in events], [1, 2, 3])

    def test_events_reverse_order_input(self):
        chain = self._window()
        chain["logs"] = list(reversed(chain["logs"]))
        fake = FakeClient(chain)
        events = F.fetch_commit_events(
            fake, "rpc://x", "p", {"from_block": 99000, "to_block": 99999})
        self.assertEqual([e["batch_index"] for e in events], [1, 2, 3])


# ---------------------------------------------------------------------------
# Tests: end-to-end determinism and manifest format (§4)
# ---------------------------------------------------------------------------

class TestEndToEnd(unittest.TestCase):
    def test_manifest_shape_and_determinism(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            chain = build_chain(6, 99000, 99999)
            rc, _ = run_fetch(chain, out)
            self.assertEqual(rc, 0)
            first = (out / "corpus" / "manifest.json").read_bytes()

            # Re-run into a fresh corpus with the same snapshot: identical bytes.
            out2 = out / "again"
            rc, _ = run_fetch(chain, out2)
            self.assertEqual(rc, 0)
            second = (out2 / "corpus" / "manifest.json").read_bytes()
            self.assertEqual(first, second)

    def test_serial_fallback_when_batches_unsupported(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            chain = build_chain(6, 99000, 99999)
            rc, _ = run_fetch(chain, out)
            ref = (out / "corpus" / "manifest.json").read_bytes()

            chain["no_batch"] = True
            out2 = out / "serial"
            rc, _ = run_fetch(chain, out2)
            self.assertEqual(rc, 0)
            self.assertEqual(ref, (out2 / "corpus" / "manifest.json").read_bytes())

    def test_manifest_shape_and_determinism_keys(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            chain = build_chain(6, 99000, 99999)
            rc, _ = run_fetch(chain, out)
            self.assertEqual(rc, 0)
            first = (out / "corpus" / "manifest.json").read_bytes()
            m = json.loads(first)
            self.assertEqual(list(m.keys()),
                             ["chain", "rollup_proxy", "window", "commits"])
            self.assertEqual(m["chain"], "ethereum-mainnet")
            self.assertEqual(m["rollup_proxy"],
                             "0x759894Ced0e6af42c26668076Ffa84d02E3CeF60")
            self.assertEqual(list(m["window"].keys()), ["from_block", "to_block"])
            self.assertEqual(m["window"]["to_block"], 99999)

            commits = m["commits"]
            self.assertEqual(len(commits), 6)
            self.assertEqual(
                [c["batch_index"] for c in commits],
                sorted(c["batch_index"] for c in commits))
            for c in commits:
                self.assertEqual(
                    list(c.keys()),
                    ["batch_index", "tx", "block", "method",
                     "calldata_sha256", "blob_versioned_hashes",
                     "blobs_sha256", "post"])
                self.assertEqual(c["method"], "commitBatch")
                self.assertEqual(len(c["calldata_sha256"]), 64)
                self.assertEqual(len(c["blob_versioned_hashes"]), 1)
                self.assertEqual(len(c["blobs_sha256"]), 1)
                self.assertEqual(
                    list(c["post"].keys()),
                    ["committedBatches", "committedStateRoots",
                     "lastCommittedBatchIndex"])
                self.assertEqual(c["post"]["committedBatches"], "0x" + "aa" * 32)
                self.assertEqual(c["post"]["committedStateRoots"],
                                 "0x" + "bb" * 32)
                self.assertEqual(c["post"]["lastCommittedBatchIndex"], 6)
                # cache really holds the artifacts
                cache_dir = out / "cache" / "objects"
                self.assertTrue((cache_dir / c["calldata_sha256"]).exists())
                for h in c["blobs_sha256"]:
                    self.assertTrue((cache_dir / h).exists())

            # fixtures: at most 5, fully self-contained
            fx = sorted((out / "corpus" / "fixtures").glob("*.json"))
            self.assertLessEqual(len(fx), 5)
            self.assertEqual(len(fx), 5)
            f0 = json.loads(fx[0].read_text())
            self.assertIn("calldata", f0)
            self.assertTrue(f0["calldata"].startswith("0x41f756da"))
            self.assertEqual(len(f0["blobs"]), 1)
            self.assertIsNotNone(f0["receipt"])

    def test_min_commits_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            chain = build_chain(2, 99000, 99999)
            with self.assertRaises(F.FetchError):
                rc, _ = run_fetch(chain, out, ["--min-commits", "200"])

    def test_blobscan_fallback_when_beacon_missing(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            chain = build_chain(2, 99000, 99999)
            chain["beacon"] = {}  # beacon unavailable -> blobscan path
            rc, _ = run_fetch(chain, out)
            self.assertEqual(rc, 0)
            m = read_manifest(out)
            self.assertTrue(all(len(c["blobs_sha256"]) == 1
                                for c in m["commits"]))

    def test_commit_state_has_empty_blobs(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            chain = build_chain(1, 99000, 99999)
            tx = chain["logs"][0]["transactionHash"]
            chain["txs"][tx]["blobVersionedHashes"] = []
            chain["txs"][tx]["input"] = _calldata("67caa37a")
            rc, _ = run_fetch(chain, out)
            self.assertEqual(rc, 0)
            c = read_manifest(out)["commits"][0]
            self.assertEqual(c["method"], "commitState")
            self.assertEqual(c["blob_versioned_hashes"], [])
            self.assertEqual(c["blobs_sha256"], [])


if __name__ == "__main__":
    unittest.main()
