"""I4: every side the M0 and M1 witnesses claim is replayed, and each side records whether the
obstruction was actually observed (BUILD_PLAN I4; closes D-b and D-f).

The replay harness is the measurement device and is written after this prereg. These tests do
not take its word for the outcome: they recompute what they can from the bytes it logged
(keccak256 of the committed header against committedBatches, byte 0, the ssvh cells, the blob
field, the aggregate a version-2 consumer recomputes) with tests_m2/_keccak.py.
"""
import unittest

from tests_m2._i4 import PROVENANCE, STATUSES, hexbytes, report, sides
from tests_m2._keccak import keccak256
from tests_m2._m2 import MILESTONES, ROOT, load_json, records

ZERO32 = bytes(32)


def m0_witness_version(lid: str) -> int:
    return int(records("M0")[lid]["witness"]["h"]["version"], 16)


class TestKeccakHelper(unittest.TestCase):
    def test_known_vectors(self):
        self.assertEqual(keccak256(b"").hex(), "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470")
        self.assertEqual(keccak256(b"abc").hex(), "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45")
        # padding boundary (rate 136): values from Foundry's `cast keccak`
        self.assertEqual(keccak256(bytes(135)).hex(), "29e3704feeca7fb9ba229f0fa04d9b36449cf3ad6e1d85d9cfff3a10df9abc3e")
        self.assertEqual(keccak256(bytes(136)).hex(), "3a5912a7c5faa06ee4fe906253e339467a9ce87d533c65be3c15cb231cdb25f9")


class TestM0CommitPath(unittest.TestCase):
    """D-b: the Solidity side of the two M0 codec witnesses, replayed on the commit path."""

    def commit_side(self, lid: str) -> tuple[dict, bytes]:
        s = report("M0")["laws"][lid]["solidity"]
        self.assertEqual(s["status"], "passed", s.get("observed"))
        self.assertEqual(s["provenance"], "public_schedule")
        self.assertIs(s["obstruction_observed"], True)
        self.assertTrue(s["command"])
        last = s["trace"][-1]
        self.assertEqual(last["op"], "commitBatch")
        self.assertEqual(last["ver"], m0_witness_version(lid), "the trace commits at the witness's version")
        h = hexbytes(s["header"])
        self.assertEqual(len(h), 257, "version 1 and 2 headers are 257 bytes")
        self.assertEqual(int.from_bytes(h[1:9], "big"), s["batch_index"])
        self.assertEqual(keccak256(h), hexbytes(s["committed_hash"]),
                         "keccak256(header) == committedBatches[batch_index], read on chain")
        return s, h

    def test_v2_byte0_on_chain(self):
        """I4-P1."""
        s, h = self.commit_side("L_par_hdr_v2")
        self.assertEqual(h[0], 0x02)
        # the Go side of the same law: the only 257-byte Go encoder writes byte 0 = 1
        g = report("M0")["laws"]["L_par_hdr_v2"]["go"]
        self.assertEqual(g["status"], "passed")
        self.assertIs(g["obstruction_observed"], True)

    def test_ssvh_zero_on_chain(self):
        """I4-P2."""
        s, h = self.commit_side("L_par_hdr_ssvh")
        self.assertEqual(h[0], 0x01)
        self.assertEqual(h[185:217], ZERO32, "the commit path writes sequencerSetVerifyHash = bytes32(0)")
        g = report("M0")["laws"]["L_par_hdr_ssvh"]["go"]
        self.assertEqual(g["status"], "passed")
        self.assertIs(g["obstruction_observed"], True)


class TestConsumerSides(unittest.TestCase):
    """D-f: L_tag_BVH's obstruction observed on real code, and L_fact_Z's consumer side replayed."""

    def test_tag_bvh_consumer(self):
        """I4-P3."""
        ss = sides("M1", report("M1")["laws"]["L_tag_BVH"])
        sol, con = ss["solidity"], ss["go_consumer"]
        self.assertEqual(sol["status"], "passed", sol.get("observed"))
        self.assertEqual(sol["provenance"], "public_schedule")
        self.assertIs(sol["obstruction_observed"], True)
        h, vh = hexbytes(sol["header"]), hexbytes(sol["stored_vh"])
        self.assertEqual(len(h), 257)
        self.assertEqual(h[0], 0x02, "commitState committed a version-2 header")
        self.assertEqual(keccak256(h), hexbytes(sol["committed_hash"]))
        self.assertEqual(h[57:89], vh, "the v2 blob field holds the stored v1 versioned hash")

        self.assertEqual(con["status"], "passed", con.get("observed"))
        self.assertEqual(con["provenance"], "library_api")
        self.assertIs(con["obstruction_observed"], True)
        self.assertTrue(con["command"])
        self.assertEqual(hexbytes(con["input_header"]), h, "the consumer reads the header the chain committed")
        self.assertEqual(hexbytes(con["blob_commit_hash"]), h[57:89])
        agg = hexbytes(con["aggregate"])
        self.assertEqual(agg, keccak256(vh), "aggregateBlobHashes([vh]) = keccak256(vh)")
        self.assertNotEqual(agg, hexbytes(con["blob_commit_hash"]))

    def test_fact_z_consumer(self):
        """I4-P4."""
        ss = sides("M1", report("M1")["laws"]["L_fact_Z"])
        sol, con = ss["solidity"], ss["go_consumer"]
        self.assertEqual(sol["status"], "passed", sol.get("observed"))
        self.assertEqual(sol["provenance"], "public_schedule")
        self.assertIs(sol["obstruction_observed"], True)
        ch = sol["committed_hash"]
        self.assertEqual(set(ch), {"c1", "c2"})
        self.assertEqual(ch["c1"], ch["c2"], "the no-blob and zero-blob commits commit the same header")

        self.assertEqual(con["status"], "passed", con.get("observed"))
        self.assertEqual(con["provenance"], "library_api")
        self.assertIs(con["obstruction_observed"], True)
        self.assertTrue(con["command"])
        self.assertEqual(con["input_parent_header"], sol["parent_header"],
                         "the consumer is fed the parent header the chain replay used")
        self.assertEqual(con["sidecar_blobs"], {"c1": 0, "c2": 1})
        out = con["outcomes"]
        self.assertEqual(set(out), {"c1", "c2"})
        self.assertIn("blobs length can not be zero", out["c1"])
        self.assertNotEqual(out["c1"], out["c2"], "derivation outcomes differ for equal commitments")


class TestSides(unittest.TestCase):
    def test_every_side_carries_harness_fields(self):
        for m in MILESTONES:
            rep = report(m)
            for lid, entry in rep["laws"].items():
                for name, s in sides(m, entry).items():
                    with self.subTest(milestone=m, law=lid, side=name):
                        self.assertIn(s["status"], STATUSES)
                        self.assertIsInstance(s["obstruction_observed"], bool)
                        self.assertIn(s["provenance"], PROVENANCE)
                        self.assertTrue(s["observed"])
                        if s["status"] in ("passed", "failed"):
                            self.assertTrue(s["command"])
                        if s["status"] != "passed":
                            self.assertIs(s["obstruction_observed"], False, "only a passed side can observe")

    def test_no_side_is_model_only(self):
        for m in MILESTONES:
            for lid, entry in report(m)["laws"].items():
                for name, s in sides(m, entry).items():
                    with self.subTest(milestone=m, law=lid, side=name):
                        self.assertNotIn(s["status"], ("not_applicable", "not_run"), s.get("observed"))

    def test_claimed_sides_are_present(self):
        want = {
            "M0": {"L_par_hdr_v2": {"go", "solidity"}, "L_par_hdr_ssvh": {"go", "solidity"},
                   "L_dom_hdr": {"go", "solidity"}},
            "M1": {"L_undo_BVH": {"solidity"}, "L_undo_cancel": {"solidity"}, "L_sort_remaining": {"solidity"},
                   "L_sym_omega": {"solidity"}, "L_nat_eta2": {"solidity"}, "L_own_txspayload": {"go"},
                   "L_tag_BVH": {"solidity", "go_consumer"}, "L_fact_Z": {"solidity", "go_consumer"}},
        }
        for m, laws in want.items():
            rep = report(m)
            self.assertEqual(set(rep["laws"]), set(laws), m)
            for lid, names in laws.items():
                with self.subTest(milestone=m, law=lid):
                    self.assertEqual(set(sides(m, rep["laws"][lid])), names)

    def test_differ_sides_are_observed_from_their_traces(self):
        """For two-sided claims, obstruction_observed is what the logged real outcomes say: the
        continuations after each trace's split point differ."""
        n = 0
        for lid, entry in report("M1")["laws"].items():
            ts = {t["label"]: t for t in entry["traces"]}
            if set(ts) != {"lhs", "rhs"}:
                continue
            n += 1
            with self.subTest(law=lid):
                a, b = ts["lhs"], ts["rhs"]
                self.assertIsInstance(a["split"], int)
                self.assertIsInstance(b["split"], int)
                differ = a["real"][a["split"]:] != b["real"][b["split"]:]
                self.assertIs(sides("M1", entry)["solidity"]["obstruction_observed"], differ)
                self.assertTrue(differ)
        self.assertEqual(n, 4, "L_undo_BVH, L_undo_cancel, L_sym_omega, L_nat_eta2")

    def test_m1_law_verdict_matches_sides(self):
        for lid, entry in report("M1")["laws"].items():
            ss = sides("M1", entry)
            with self.subTest(law=lid):
                self.assertEqual(entry["status"] == "passed", all(s["status"] == "passed" for s in ss.values()))
                self.assertEqual(entry["obstruction_reproduced"],
                                 all(s["obstruction_observed"] for s in ss.values()))

    def test_records_carry_the_replayed_witness(self):
        for m in MILESTONES:
            rep = report(m)
            for lid, rec in records(m).items():
                if rec["status"] != "REFUTED":
                    continue
                with self.subTest(milestone=m, law=lid):
                    self.assertEqual(rec["replay"]["status"], "passed", rec["replay"])
                    self.assertNotIn("model-only", rec["replay"]["detail"])
                    self.assertIn(lid, rep["witness_sha256"])


class TestToolchainPins(unittest.TestCase):
    def test_config_pins_and_reports_agree(self):
        cfg = load_json(ROOT / "config" / "holon.json")["replay"]
        for k in ("forge", "solc", "morph", "sol_deps"):
            self.assertIsInstance(cfg[k], str, k)
        for k in ("forge_sha256", "solc_sha256", "sol_deps_sha256"):
            self.assertRegex(cfg[k], r"^[0-9a-f]{64}$", k)
        for m in MILESTONES:
            tc = report(m)["toolchain"]
            with self.subTest(milestone=m):
                for k in ("forge_sha256", "solc_sha256", "sol_deps_sha256"):
                    self.assertEqual(tc[k], cfg[k], k)


if __name__ == "__main__":
    unittest.main()
