"""Acceptance checks on the committed spec/M2/extracted/migrations.json:

the migration list matches the on-chain Upgraded events — every entry has a
block number, a tx hash and a log index, implementations are consistent with
the EIP-1967 implementation slot, the reinitializer calls are decoded with
their versions, and the storage-layout diffs line up with the reinitializers.
"""

import json
import unittest

from . import _util

ROLLUP = "0x759894ced0e6af42c26668076ffa84d02e3cef60"
QUEUE = "0x3931ade842f5bb8763164bdd81e5361dce6cc1ef"
EMPTY = "0x98df320641c2e65ab4bbef1e6f6c66d9b50ede5f"
PA = "0x31110622d6ca24c9ff307d6ae1715f16e47f16a0"


class TestUpgradeHistory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _util.load("migrations.json")
        cls.proxies = {p["name"]: p for p in cls.doc["proxies"]}

    def test_event_fields(self):
        for p in self.proxies.values():
            for u in p["upgrades"]:
                self.assertIsInstance(u["block"], int)
                self.assertRegex(u["tx"], r"^0x[0-9a-f]{64}$")
                self.assertIsInstance(u["log_index"], int)
                self.assertRegex(u["impl"], r"^0x[0-9a-f]{40}$")

    def test_rollup_has_12_upgraded_events(self):
        # constructor (EmptyContract) + 11 subsequent upgrades, on-chain count
        ups = self.proxies["Rollup"]["upgrades"]
        self.assertEqual(len(ups), 12)
        self.assertEqual(ups[0]["impl"], EMPTY)
        self.assertEqual(ups[0]["via"], [{"kind": "constructor"}])

    def test_queue_has_4_upgraded_events(self):
        ups = self.proxies["L1MessageQueue"]["upgrades"]
        self.assertEqual(len(ups), 4)
        self.assertEqual(ups[0]["impl"], EMPTY)

    def test_impl_slot_matches_last_upgrade(self):
        for p in self.proxies.values():
            self.assertEqual(p["current_impl_slot"], p["upgrades"][-1]["impl"])

    def test_blocks_strictly_increase(self):
        for p in self.proxies.values():
            blocks = [u["block"] for u in p["upgrades"]]
            self.assertEqual(blocks, sorted(blocks))
            seqs = [u["seq"] for u in p["upgrades"]]
            self.assertEqual(seqs, list(range(len(seqs))))

    def test_admin_history(self):
        for p in self.proxies.values():
            hist = p["admin_history"]
            self.assertGreaterEqual(len(hist), 2)
            self.assertEqual(hist[-1]["new_admin"], PA)

    def test_deploy_ctors(self):
        for p in self.proxies.values():
            d = p["deploy"]
            self.assertEqual(d["initial_impl"], EMPTY)
            self.assertTrue(d["init_data_empty"])


class TestReinitializers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proxies = {p["name"]: p for p in _util.load("migrations.json")["proxies"]}
        cls.ups = cls.proxies["Rollup"]["upgrades"]

    def _reinit(self, fn):
        return next(u for u in self.ups if (u.get("reinit") or {}).get("function") == fn)

    def test_initialize_v1(self):
        u = self._reinit("initialize")
        self.assertEqual(u["block"], 20998835)
        self.assertEqual(u["reinit"]["reinitializer_version"], 1)

    def test_initialize2_v2(self):
        u = self._reinit("initialize2")
        self.assertEqual(u["block"], 21283676)
        self.assertEqual(u["reinit"]["reinitializer_version"], 2)
        self.assertIn("_prevStateRoot", u["reinit"]["args"])

    def test_initialize3_v3(self):
        u = self._reinit("initialize3")
        self.assertEqual(u["block"], 24575030)
        self.assertEqual(u["reinit"]["reinitializer_version"], 3)

    def test_initialize4_v4(self):
        u = self._reinit("initialize4")
        self.assertEqual(u["block"], 26031669)
        self.assertEqual(u["reinit"]["reinitializer_version"], 4)
        self.assertEqual(u["reinit"]["args"]["_expectedLegacyCutoverBatchIndex"], 60477)

    def test_queue_initialize(self):
        ups = self.proxies["L1MessageQueue"]["upgrades"]
        u = next(u for u in ups if (u.get("reinit") or {}).get("function") == "initialize")
        self.assertEqual(u["block"], 20998777)
        self.assertEqual(u["reinit"]["args"]["_maxGasLimit"], 100000000)


class TestStorageDiffs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = _util.load("migrations.json")
        cls.diffs = cls.doc["storage_diffs"]

    def _diff(self, frm, to):
        frm = frm[:10]
        to = to[:10]
        return next(d for d in self.diffs
                    if d["from_impl"].startswith(frm) and d["to_impl"].startswith(to))

    def test_consecutive_pairs_covered(self):
        for p in self.doc["proxies"]:
            impls = [u["impl"] for u in p["upgrades"]]
            pairs = {(d["from_impl"], d["to_impl"]) for d in self.diffs
                     if d["proxy"] == p["name"]}
            for a, b in zip(impls, impls[1:]):
                if a != b:
                    self.assertIn((a, b), pairs)

    def test_eta2_adds_committed_state_roots(self):
        # the initialize2 upgrade is the only one that adds committedStateRoots
        d = self._diff("0x073403e1", "0xad900db3")
        self.assertEqual(d["status"], "diffed")
        labels = [f["label"] for f in d["added"]]
        self.assertEqual(labels, ["committedStateRoots"])
        self.assertEqual(d["added"][0]["slot"], 171)

    def test_initialize3_adds_rollup_delay_period(self):
        d = self._diff("0xdf0749e6", "0x1320d6a4")
        self.assertEqual([f["label"] for f in d["added"]], ["rollupDelayPeriod"])

    def test_initialize4_renames_staking_to_submitter(self):
        d = self._diff("0xac3c379d", "0x213ce22b")
        added = sorted(f["label"] for f in d["added"])
        removed = [f["label"] for f in d["removed"]]
        self.assertIn("submitterContract", added)
        self.assertIn("legacyCutoverBatchIndex", added)
        self.assertEqual(removed, ["l1StakingContract"])

    def test_unverified_impl_marked(self):
        d = self._diff("0xb2f539ae", "0x9e2fb684")
        self.assertEqual(d["status"], "unverifiable")

    def test_m1_facts_anchor(self):
        eta2 = self.doc["m1_facts"]["eta2"]
        self.assertEqual(eta2["block"], 21283676)
        self.assertEqual(eta2["reinitializer_version"], 2)
        self.assertEqual(eta2["function"], "initialize2")


class TestCoverageDebt(unittest.TestCase):
    def test_unverified_impl_in_coverage(self):
        cov = json.loads((_util.COVERAGE / "link.json").read_text())
        els = [i["element"] for i in cov["items"]]
        self.assertTrue(any("0x9e2fb684935a32ced121972f23bd0e4634377ca2" in e
                            for e in els))


if __name__ == "__main__":
    unittest.main()
