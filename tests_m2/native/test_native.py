"""S7 native-harness tests: the emitted model library, the worker protocol,
deterministic corpora, and the refinement record contract."""
import json
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "replay" / "M2" / "refinement"
WORKER = ROOT / "holon" / "native" / "js" / "worker.mjs"


def have_node():
    return shutil.which("node") is not None


class TestModelLibrary(unittest.TestCase):
    """bend driver.bend -o model.mjs emits a library exposing hcall/hcall2."""

    @classmethod
    def setUpClass(cls):
        from holon.native import bendc
        cls.build = bendc.build_model("m0")

    @unittest.skipUnless(have_node(), "node required")
    def test_worker_flat_call(self):
        from holon.native.refine import JsonLine, node_bin
        w = JsonLine([node_bin(), str(WORKER), self.build["lib"]], greeting=True)
        try:
            out = w.call({"call": "flat", "op": 0, "args": [0] * 257})
            self.assertTrue(out["ok"])
            self.assertEqual(len(out["out"]), 249)  # enc_go_v0 of the zero header
            out = w.call({"call": "flat", "op": 1, "args": [0] * 257})
            self.assertEqual(len(out["out"]), 257)  # enc_go_v1
        finally:
            w.close()

    @unittest.skipUnless(have_node(), "node required")
    def test_worker_bad_call_returns_error(self):
        from holon.native.refine import JsonLine, node_bin
        w = JsonLine([node_bin(), str(WORKER), self.build["lib"]], greeting=True)
        try:
            out = w.call({"call": "nope"})
            self.assertFalse(out["ok"])
        finally:
            w.close()

    def test_emitted_exports(self):
        src = Path(self.build["lib"]).read_text()
        self.assertIn('"hcall":', src)
        self.assertIn('"hcall2":', src)


class TestCorpus(unittest.TestCase):
    def test_hdr_corpus_covers_sources(self):
        from holon.native import corpus
        corp = corpus.hdr_corpus("t")
        srcs = {x["src"].split(":")[0] for x in corp}
        self.assertIn("grammar", srcs)
        self.assertIn("boundary", srcs)
        self.assertIn("witness", srcs)
        self.assertTrue(all(len(x["cells"]) == 257 for x in corp))

    def test_deterministic_seeds(self):
        from holon.native import corpus
        a = corpus.hdr_corpus("m0_enc_go_v0")
        b = corpus.hdr_corpus("m0_enc_go_v0")
        self.assertEqual([x["cells"] for x in a], [x["cells"] for x in b])
        self.assertEqual(corpus.edge_seed("m0_enc_go_v0"), corpus.edge_seed("m0_enc_go_v0"))

    def test_bytes_corpus(self):
        from holon.native import corpus
        corp = corpus.bytes_corpus("t")
        self.assertTrue(all(isinstance(x["b"], list) for x in corp))
        self.assertTrue(all(all(0 <= v <= 255 for v in x["b"]) for x in corp))


class TestRefinementRecords(unittest.TestCase):
    """Every record has the contract fields and no unexplained disagreements."""

    def test_records_present_and_classified(self):
        expected = [
            "m0_enc_go_v0", "m0_enc_go_v1", "m0_enc_sol", "m0_ok_go", "m0_ok_sol",
            "m0_dec_go", "m1_batchdata_append", "m1_batchdata_txsPayloadV2",
        ] + [f"m1_rollup_{op}" for op in
             ["commitBatch", "commitState", "commitBatchWithProof", "revertBatch",
              "challengeState", "proveState", "finalizeBatch", "setPause",
              "sendMessage", "wait", "@legacy_eta2"]]
        for name in expected:
            p = RECORDS / f"{name}.json"
            self.assertTrue(p.exists(), f"missing record {name}")
            r = json.loads(p.read_text())
            self.assertEqual(r["agreement"]["unexplained"], 0, name)
            for d in r["disagreements"]:
                self.assertIn(d["class"],
                              ("extraction_defect", "real_defect", "oracle_mismatch"), name)
            self.assertIn("seed", r["corpus"])

    def test_record_schema(self):
        for p in sorted(RECORDS.glob("*.json")):
            r = json.loads(p.read_text())
            for k in ("edge", "model", "implementation", "corpus", "agreement",
                      "disagreements"):
                self.assertIn(k, r, p.name)


if __name__ == "__main__":
    unittest.main()


class TestClassification(unittest.TestCase):
    def test_unmatched_disagreement_stays_unexplained(self):
        from holon.native import refine
        d = {"input_id": 0, "src": "injected", "edge": "m0_ok_go",
             "model": 1, "real": 0, "note": "no rule covers this"}
        refine.classify(d)
        self.assertEqual(d["class"], "unexplained")
        self.assertIsNone(d["rule"])

    def test_getter_absent_rule(self):
        from holon.native import refine
        # v0 header: real has 12 fields with ERR at index 11 (no lastBlockNumber
        # getter for v0), model has the 11 real fields — bytes identical.
        mfields = [[0]] + [[0] * 8] * 3 + [[0] * 32] * 7
        real = [0, 0, 0, 0] + [[0] * 32] * 7 + ["ERR"]
        d = {"edge": "m0_dec_go", "version": 0, "model": mfields, "real": real}
        refine.classify(d)
        self.assertEqual(d["class"], "oracle_mismatch")
        self.assertEqual(d["rule"], "getter_absent_for_version")
        self.assertIn("dec_go", d["evidence"])

    def test_encoder_domain_split(self):
        from holon.native import refine
        keep, out = refine.split_by_domain(
            "m0_enc_sol",
            [{"kind": "hdr", "src": "v0", "cells": [0] * 257},
             {"kind": "hdr", "src": "v2", "cells": [2] + [0] * 256},
             {"kind": "hdr", "src": "v3", "cells": [3] + [0] * 256},
             {"kind": "hdr", "src": "v255", "cells": [255] * 257}])
        self.assertEqual([x["src"] for x in keep], ["v0", "v2"])
        self.assertEqual([x["src"] for x in out], ["v3", "v255"])
        self.assertTrue(all(x["reason"] == "out_of_encoder_domain" for x in out))
        keep2, out2 = refine.split_by_domain("m0_ok_go", [{"kind": "bytes", "src": "b", "b": [255]}])
        self.assertEqual(len(keep2), 1)
        self.assertEqual(out2, [])
