"""I59 (the I23a track): historical on-chain acquisition and the first per-edge replay on real inputs (human answer Q5 in
docs/HUMAN_ANSWERS.md: on-chain replay is make or break). The frozen instrument is
spec/M2/lib/historical.json, which fixes the chain, the Rollup proxy address, the event topics, the window
[from_block, to_block] and the sources.

CONTRACT

python -m holon historical fetch [--milestone M2] [--from N] [--to M] [--index PATH] [--snapshot DIR]
  - Acquires every log of the Rollup proxy in the window whose topic is one of the sidecar's events, every
    transaction those logs belong to (calldata, type and blob versioned hashes), every receipt, and every
    blob of a commit transaction. Blobs come from the beacon API inside its retention window and from the
    blob archive outside it.
  - Raw bytes go to a content-addressed snapshot outside the repo (default ~/.holon/historical, env
    HOLON_HISTORICAL_DIR), one file per sha256.
  - The index goes to results/M2/historical/index.json (default --index). It is canonical JSON (sorted
    keys, indent=1):
      {"window": {"from_block", "to_block", "to_block_hash"}, "snapshot": "<absolute dir>",
       "items": [{"kind": "log"|"tx"|"receipt"|"blob", "block", "tx", "log_index" (logs), "topic" (logs),
                  "sha256", "source": "<host only, never a URL with a key>", "status": "ok"|"unavailable"}],
       "counts": {"<kind>": n}, "index_sha256": sha256 of the canonical document without index_sha256}
    Items are sorted by (block, tx, kind, log_index, sha256).
  - Resumable: an item already in the snapshot with matching sha256 is not fetched again. Rate limits are
    retried with backoff. The index for a fixed window is byte-identical across runs.
  - --from/--to restrict to a sub-window inside the sidecar's window.
  - No secret (the value of ETH_RPC_URL, ETHERSCAN_API_KEY or any key) appears in any output.

python -m holon historical replay [--milestone M2] [--index PATH] [--out PATH]
  - Reads the index and the snapshot and writes results/M2/historical/replay.json (canonical JSON):
      {"window": {...}, "events": {"CommitBatch": n, "RevertBatch": n, "FinalizeBatch": n,
                                    "ChallengeState": n, "Upgraded": n},
       "last_upgrade_block": <block of the last Upgraded event in the window, or null>,
       "commits": [{"tx", "block", "tx_index", "status": "success"|"failed",
                    "function": "commitBatch"|"commitState"|"commitBatchWithProof"|"other",
                    "abi": "decoded"|"undecodable",
                    "batch_index": <k from the tx's CommitBatch log, or null>, "batch_hash": "0x..",
                    "tx_blob_versioned_hashes": ["0x.."],
                    "parent": null | {"length", "version", "batch_index", "keccak",
                                      "linkage": "ok"|"mismatch"|"no_event",
                                      "ok_sol", "ok_go", "roundtrip": "ok"|"diff", "diff_cells": [int],
                                      "ssvh_zero", "blob_versioned_hash": "0x..",
                                      "go_decoder": "agree"|"disagree"|"not_run"},
                    "blobs": [{"versioned_hash", "source": "beacon"|"blob_archive"|"unavailable",
                               "commitment_ok": true|false|null}]}],
       "reverts": [{"batch_index", "block", "recommitted_block": <block of the next CommitBatch(k), or null>}],
       "summary": {...counts...}}
    commits is sorted by (block, tx_index).
  - "parent" is the batchDataInput.parentBatchHeader of a decoded successful commit:
      - linkage: keccak256(parent) against the batchHash of the latest CommitBatch event (or genesis
        import) with that batch index before the tx;
      - ok_sol, ok_go, roundtrip: from the frozen M0 header model (facts/morph_header.json). roundtrip
        compares enc_sol(dec(parent)) with the parent byte for byte; diff_cells lists the differing indices;
      - ssvh_zero: bytes 185..216 (sequencerSetVerifyHash) are all zero;
      - go_decoder: the real Go decoders of the pinned Morph checkout (common/batch BatchHeaderBytes),
        run on the bytes and compared with dec_go/ok_go.
  - blobs[i].commitment_ok: the KZG commitment's versioned hash (0x01 || sha256(commitment)[1:]) equals
    the tx's versioned hash. null when unavailable.
  - Disagreements go to results/M2/historical/disagreements.json, classified by I16's mechanical link
    rules (holon.refinement), never by label.

holon.historical.header_checks(header: bytes) -> dict
  Keys: length, version, keccak ("0x" + hex), ok_sol, ok_go, roundtrip, diff_cells, ssvh_zero. These are
  the per-header checks of the replay, without the chain.

Rules: pure Python plus the existing models and the Go harness; the snapshot never inside the repo; the
replay never reads the frozen M1 facts for chain values, only the frozen M0 header model; predictions are
never tuned (a miss is a Surprise).
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json, run_holon

SIDE = ROOT / "spec" / "M2" / "lib" / "historical.json"
OUT = ROOT / "results" / "M2" / "historical"
SSVH = range(185, 217)


def replay() -> dict:
    p = OUT / "replay.json"
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing: run python -m holon historical fetch, then replay")
    return load_json(p)


def decoded(r: dict) -> list[dict]:
    return [c for c in r["commits"] if c["status"] == "success" and c["abi"] == "decoded" and c["parent"]]


def toy_header(version: int, **over) -> bytes:
    """A header in the frozen layout (v0: 249 bytes, v1/v2: 257), every field from `over` or a fixed fill."""
    f = {"batchIndex": 7, "l1MessagePopped": 1, "totalL1MessagePopped": 3,
         "dataHash": b"\x11" * 32, "blobVersionedHash": b"\x01" + b"\x22" * 31, "prevStateHash": b"\x33" * 32,
         "postStateHash": b"\x44" * 32, "withdrawRootHash": b"\x55" * 32, "sequencerSetVerifyHash": b"\x00" * 32,
         "parentBatchHash": b"\x66" * 32, "lastBlockNumber": 99}
    f.update(over)
    b = bytes([version]) + f["batchIndex"].to_bytes(8, "big") + f["l1MessagePopped"].to_bytes(8, "big") \
        + f["totalL1MessagePopped"].to_bytes(8, "big") + f["dataHash"] + f["blobVersionedHash"] \
        + f["prevStateHash"] + f["postStateHash"] + f["withdrawRootHash"] + f["sequencerSetVerifyHash"] \
        + f["parentBatchHash"]
    return b + (f["lastBlockNumber"].to_bytes(8, "big") if version >= 1 else b"")


class TestToyHeader(unittest.TestCase):
    """Construction check: header_checks on headers built in the frozen layout."""

    @classmethod
    def setUpClass(cls):
        cls.H = holon_module("holon.historical")
        cls.K = holon_module("holon.keccak")

    def test_a_v1_header_round_trips(self):
        h = toy_header(1)
        c = self.H.header_checks(h)
        self.assertEqual((c["length"], c["version"], c["ok_sol"], c["ok_go"], c["roundtrip"], c["ssvh_zero"]),
                         (257, 1, True, True, "ok", True))
        self.assertEqual(c["keccak"], "0x" + self.K.keccak256(h).hex())

    def test_a_v0_header_round_trips(self):
        c = self.H.header_checks(toy_header(0))
        self.assertEqual((c["length"], c["version"], c["ok_sol"], c["ok_go"], c["roundtrip"]), (249, 0, True, True, "ok"))

    def test_a_nonzero_ssvh_is_seen_and_lost_by_enc_sol(self):
        c = self.H.header_checks(toy_header(1, sequencerSetVerifyHash=b"\x00" * 5 + b"\x09" + b"\x00" * 26))
        self.assertFalse(c["ssvh_zero"])
        self.assertEqual((c["roundtrip"], c["diff_cells"]), ("diff", [190]))

    def test_a_wrong_length_is_rejected_by_both_sides(self):
        c = self.H.header_checks(toy_header(1)[:256])
        self.assertEqual((c["ok_sol"], c["ok_go"]), (False, False))


class TestFetch(unittest.TestCase):
    """Construction checks on the acquisition."""

    def test_the_index_covers_the_frozen_window(self):
        side = load_json(SIDE)
        idx = load_json(OUT / "index.json")
        self.assertEqual(idx["window"], {k: side["window"][k] for k in ("from_block", "to_block", "to_block_hash")})
        self.assertGreater(idx["counts"].get("log", 0), 0)
        self.assertTrue(all(side["window"]["from_block"] <= i["block"] <= side["window"]["to_block"] for i in idx["items"]))

    def test_the_snapshot_is_outside_the_repo(self):
        idx = load_json(OUT / "index.json")
        snap = Path(idx["snapshot"]).resolve()
        self.assertTrue(snap.is_absolute())
        self.assertFalse(str(snap).startswith(str(ROOT.resolve()) + os.sep), snap)

    def test_no_secret_in_any_output(self):
        secrets = [v for k, v in os.environ.items() if k in ("ETH_RPC_URL", "ETHERSCAN_API_KEY") and v]
        for p in sorted(OUT.glob("*.json")):
            text = p.read_text(encoding="utf-8")
            with self.subTest(file=p.name):
                self.assertNotIn("apikey=", text.lower())
                for s in secrets:
                    self.assertNotIn(s, text)

    def test_a_fixed_sub_window_fetches_byte_identically_twice(self):
        side = load_json(SIDE)
        hi = side["window"]["to_block"]
        lo = hi - side["limits"]["get_logs_max_blocks"] + 1
        tmp = Path(tempfile.mkdtemp(prefix="holon-hist-"))
        try:
            outs = []
            for n in (1, 2):
                p = run_holon(["historical", "fetch", "--from", str(lo), "--to", str(hi),
                               "--index", str(tmp / f"i{n}.json"), "--snapshot", str(tmp / "snap")], timeout=1800)
                self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
                outs.append((tmp / f"i{n}.json").read_bytes())
            self.assertEqual(outs[0], outs[1])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestPredictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = replay()
        cls.dec = decoded(cls.r)

    def test_parent_headers_link_to_the_emitted_batch_hashes(self):
        """I59-P1."""
        self.assertTrue(self.dec)
        bad = [(c["tx"], c["parent"]["linkage"]) for c in self.dec if c["parent"]["linkage"] != "ok"]
        self.assertEqual(bad, [])

    def test_real_headers_are_in_the_model_domain_and_round_trip_except_ssvh(self):
        """I59-P2."""
        bad = [c["tx"] for c in self.dec
               if not (c["parent"]["ok_sol"] and c["parent"]["ok_go"] and c["parent"]["length"] in (249, 257))
               or any(i not in SSVH for i in c["parent"]["diff_cells"])]
        self.assertEqual(bad, [])

    def test_nonzero_ssvh_headers_form_a_prefix_of_the_batch_sequence(self):
        """I59-P3."""
        nz = [c["parent"]["batch_index"] for c in self.dec if not c["parent"]["ssvh_zero"]]
        z = [c["parent"]["batch_index"] for c in self.dec if c["parent"]["ssvh_zero"]]
        self.assertTrue(z, "no header with a zero sequencerSetVerifyHash")
        self.assertTrue(not nz or max(nz) < min(z), (max(nz) if nz else None, min(z)))

    def test_observed_header_versions_are_0_and_1_only(self):
        """I59-P4."""
        self.assertLessEqual({c["parent"]["version"] for c in self.dec}, {0, 1})

    def test_header_blob_hashes_equal_the_committing_transactions(self):
        """I59-P5."""
        by_index = {}
        for c in self.r["commits"]:
            if c["status"] == "success" and c["batch_index"] is not None and c["function"] == "commitBatch" \
                    and c["tx_blob_versioned_hashes"]:
                by_index[c["batch_index"]] = c["tx_blob_versioned_hashes"][0]   # the latest commit of k wins
        checked, bad = 0, []
        for c in self.dec:
            k = c["parent"]["batch_index"]
            if k in by_index:
                checked += 1
                if c["parent"]["blob_versioned_hash"] != by_index[k]:
                    bad.append(k)
        self.assertGreater(checked, 0)
        self.assertEqual(bad, [])

    def test_blobs_are_retrievable_and_match_their_commitments(self):
        """I59-P6 (threshold blob_retrievable_min)."""
        blobs = [b for c in self.r["commits"] if c["status"] == "success" for b in c["blobs"]]
        self.assertTrue(blobs)
        got = [b for b in blobs if b["source"] != "unavailable"]
        side = json.loads((ROOT / "spec" / "M2" / "predictions.json").read_text())["iterations"]["I59"]
        self.assertGreaterEqual(len(got) / len(blobs), side["thresholds"]["blob_retrievable_min"])
        self.assertEqual([b["versioned_hash"] for b in got if b["commitment_ok"] is not True], [])

    def test_the_real_go_decoder_agrees_with_the_model_on_every_real_header(self):
        """I59-P7."""
        self.assertEqual([(c["tx"], c["parent"]["go_decoder"]) for c in self.dec
                          if c["parent"]["go_decoder"] != "agree"], [])

    def test_the_window_holds_the_whole_batch_history(self):
        """I59-P8."""
        ks = sorted({c["batch_index"] for c in self.r["commits"] if c["status"] == "success" and c["batch_index"] is not None})
        self.assertEqual(ks[0], 1)
        self.assertEqual(ks, list(range(1, ks[-1] + 1)))
        self.assertEqual([v["batch_index"] for v in self.r["reverts"] if v["recommitted_block"] is None], [])

    def test_every_commit_after_the_last_upgrade_decodes_under_the_pinned_abi(self):
        """I59-P9."""
        last = self.r["last_upgrade_block"] or 0
        self.assertEqual([c["tx"] for c in self.r["commits"]
                          if c["status"] == "success" and c["block"] > last
                          and c["function"] != "other" and c["abi"] != "decoded"], [])


if __name__ == "__main__":
    unittest.main()
