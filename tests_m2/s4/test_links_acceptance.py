"""Acceptance checks on the committed spec/M2/extracted/links.json:

every M0/M1 cross-language constant is linked; the wire layout is recovered on
both encoders; the Go bindings cover the deployed ABIs; event schemas carry a
recomputed topic0.
"""

import json
import unittest

from holon.frontends.link.keccak import keccak256

from . import _util


class TestConstantsLinked(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _util.load("links.json")
        cls.consts = {c["id"]: c for c in cls.doc["constants"]}

    def test_every_named_constant_linked(self):
        # the M2 spec names these; the registry must report each as linked
        for cid in ("batch_header_v0_length", "batch_header_v1_length",
                    "batch_header_v2_length", "batch_header_max_version",
                    "zero_versioned_hash", "blob_payload_bytes",
                    "sequencer_set_verify_hash_write"):
            c = self.consts[cid]
            self.assertIn(c["linked"], (True, "one_sided", "asymmetric"),
                          f"{cid} not linked")
            if c["linked"] == "one_sided":
                self.assertTrue(c.get("reason"), f"{cid} one-sided without reason")

    def test_linked_values_agree(self):
        for cid, c in self.consts.items():
            if c["linked"] is not True:
                continue
            vals = [s["value"] for s in c["go"] + c["solidity"] if s.get("value") is not None]
            norm = [v.lower() if isinstance(v, str) and v.startswith("0x") else v for v in vals]
            self.assertTrue(all(v == (c["value"].lower() if isinstance(c["value"], str) else c["value"])
                                for v in norm), f"{cid} sides disagree")

    def test_zero_versioned_hash_value(self):
        self.assertEqual(
            self.consts["zero_versioned_hash"]["value"],
            "0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014")


class TestWireLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fields = {f["name"]: f for f in _util.load("links.json")["wire_layout"]}

    def test_all_fields_linked(self):
        self.assertEqual(len(self.fields), 12)
        for name, f in self.fields.items():
            self.assertTrue(f["linked"], f"header field {name} unlinked")

    def test_offsets_match_facts(self):
        expected = {"version": 0, "batchIndex": 1, "l1MessagePopped": 9,
                    "totalL1MessagePopped": 17, "dataHash": 25,
                    "blobVersionedHash": 57, "prevStateRoot": 89,
                    "postStateRoot": 121, "withdrawalRoot": 153,
                    "sequencerSetVerifyHash": 185, "parentBatchHash": 217,
                    "lastBlockNumber": 249}
        self.assertEqual({n: f["offset"] for n, f in self.fields.items()}, expected)


class TestAbiBindings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bindings = {b["contract"]: b for b in _util.load("links.json")["abi_bindings"]}

    def test_rollup_binding_covers_deployed(self):
        b = self.bindings["Rollup"]
        self.assertTrue(b["linked"])
        self.assertEqual(b["functions"]["deployed_only"], [])
        self.assertEqual(b["events"]["deployed_only"], [])
        self.assertGreaterEqual(len(b["functions"]["shared"]), 50)

    def test_queue_binding_covers_deployed(self):
        b = self.bindings["L1MessageQueueWithGasPriceOracle"]
        self.assertTrue(b["linked"])
        self.assertEqual(b["functions"]["deployed_only"], [])
        self.assertEqual(b["events"]["deployed_only"], [])


class TestEventSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = _util.load("links.json")["event_schemas"]

    def test_topic0_recomputed(self):
        for e in self.events:
            self.assertEqual(e["topic0"], "0x" + keccak256(e["signature"].encode()).hex())

    def test_known_events_present(self):
        sigs = {e["signature"] for e in self.events}
        self.assertIn("CommitBatch(uint256,bytes32)", sigs)
        self.assertIn("RevertBatch(uint256,bytes32)", sigs)
        self.assertIn("FinalizeBatch(uint256,bytes32,bytes32,bytes32)", sigs)

    def test_indexed_flags_captured(self):
        cb = next(e for e in self.events if e["signature"] == "CommitBatch(uint256,bytes32)")
        self.assertEqual([i["indexed"] for i in cb["inputs"]], [True, True])


if __name__ == "__main__":
    unittest.main()
