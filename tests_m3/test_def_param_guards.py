"""M3: defs_from body guards referencing def params reach call sites (R5).

The blob_hash def (_computeBlobVersionedHash) emits requires that reference
its params ver/blobs. They must appear on commitBatch /
commitBatchWithProof with the call-site args substituted and the enclosing
conds folded in — before R5 they were silently dropped as unbound.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "spec" / "M3" / "extracted" / "morph_rollup.json"


class TestDefParamCallSiteGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = json.loads(FACTS.read_text())

    def guards_at(self, action, src_suffix):
        a = next(x for x in self.facts["actions"] if x["name"] == action)
        return [g["require"] for g in a["guards"] if g.get("src", "").endswith(src_suffix)]

    def test_commitbatch_blob_guards(self):
        # Rollup.sol:913 require(_blobCount > 0, "V2 requires at least 1 blob")
        # inside if (_version == 2); ver substituted from the call-site arg.
        self.assertIn(
            ["||", ["!=", "ver", 2], [">", ["call", "blob_count", "blobs"], 0]],
            self.guards_at("commitBatch", ":913"))
        # Rollup.sol:915 require(blobhash(1) == 0) in the else branch.
        self.assertIn(
            ["||", ["==", "ver", 2], ["==", ["call", "nth", "blobs", 1], 0]],
            self.guards_at("commitBatch", ":915"))

    def test_commitbatchwithproof_conds_folded(self):
        # Same def guards, emitted only under the no-stored-hash else branch
        # (Rollup.sol:409) — the stored==0 cond is folded into the require.
        self.assertIn(
            ["||", ["!=", "stored", 0], ["!=", "ver", 2],
             [">", ["call", "blob_count", "blobs"], 0]],
            self.guards_at("commitBatchWithProof", ":913"))
        self.assertIn(
            ["||", ["!=", "stored", 0], ["==", "ver", 2],
             ["==", ["call", "nth", "blobs", 1], 0]],
            self.guards_at("commitBatchWithProof", ":915"))

    def test_mvrv_notfound_guard_unchanged(self):
        # The R4 guard stays emitted at verifyAggregateProof after the flag
        # removal (params are now bound for every defs_from entry).
        mvrv = json.loads((ROOT / "spec/M3/extracted/mvrv.json").read_text())
        a = next(x for x in mvrv["actions"] if x["name"] == "verifyAggregateProof")
        reqs = [g["require"] for g in a["guards"] if "require" in g]
        self.assertIn(
            ["||",
             ["<=", ["get", ["call", "nth_rec", "lv", "v"], "s"], "idx"],
             ["call", "lv_le_has", ["call", "nthl", "lvv", "v"], "idx"]],
            reqs)
