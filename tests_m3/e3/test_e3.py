"""M3 E3: Go derivation facts must regenerate deterministically, keep the
M2 outputs byte-identical, and respond to one source mutant per E3 item.
"""
import filecmp
import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MORPH = Path(os.environ.get("HOLON_MORPH_DIR", Path.home() / "ext" / "morph"))
PINNED = "3e44e795586af3e11285b603ab642c67823add51"

M2_FILES = ("go_codecs.json", "go_batchdata.json")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _copy_morph(dst):
    ignore = shutil.ignore_patterns(
        ".git", "node_modules", ".cache", "target", "dist", "tmp")
    return shutil.copytree(MORPH, dst, ignore=ignore, dirs_exist_ok=True)


def _derivation(morph, commit="mutant"):
    from holon.frontends.go import derivation, model, tool
    from holon.frontends.go.__main__ import DERIVATION_PACKAGES
    raw = tool.run_dump(Path(morph), DERIVATION_PACKAGES, debug=True)
    return derivation.extract_derivation(model.Dump(raw), commit)


@unittest.skipUnless((MORPH / "go.work").exists() and
                     (MORPH / "node/derivation/batch_info.go").exists(),
                     "pinned Morph checkout unavailable")
class TestE3Extraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon.frontends.go import __main__ as go_main
        cls.go_main = go_main
        cls.committed = json.loads(
            (REPO / "spec/M3/extracted/go_derivation.json").read_text())

    def test_deterministic_and_m2_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            d1, d2, d3 = Path(td, "d1"), Path(td, "d2"), Path(td, "m2")
            self.go_main.extract_derivation(MORPH, d1)
            self.go_main.extract_derivation(MORPH, d2)
            self.assertEqual((d1 / "go_derivation.json").read_bytes(),
                             (d2 / "go_derivation.json").read_bytes())
            self.assertEqual((d1 / "go_derivation.coverage.json").read_bytes(),
                             (d2 / "go_derivation.coverage.json").read_bytes())

            self.go_main.extract(MORPH, d3)
            for name in M2_FILES:
                with self.subTest(m2_output=name):
                    self.assertTrue(filecmp.cmp(
                        d3 / name, REPO / "spec/M2/extracted" / name,
                        shallow=False))

    def _mutant_facts(self, mutate):
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "morph"
            _copy_morph(work)
            mutate(work)
            return _derivation(work)

    def test_mutant_datahash_slice_bound(self):
        def mutate(m):
            p = m / "common/batch/batch_data.go"
            p.write_text(p.read_text().replace("i*60+58", "i*60+60", 1))
        f = self._mutant_facts(mutate)
        self.assertNotEqual(
            self.committed["hash_encoders"]["DataHash"],
            f["hash_encoders"]["DataHash"])
        self.assertTrue(any("[i * 60:i * 60 + 60]" in s["expression"]
                            for s in f["hash_encoders"]["DataHash"]["block_context_slices"]))

    def test_mutant_delete_zero_block_check(self):
        def mutate(m):
            p = m / "node/derivation/batch_info.go"
            text = p.read_text()
            old = "\tif blockCount == 0 {\n\t\treturn fmt.Errorf(\"invalid batch: zero block count\")\n\t}\n\n"
            self.assertIn(old, text)
            p.write_text(text.replace(old, "", 1))
        f = self._mutant_facts(mutate)
        self.assertIsNone(f["parse_batch"]["zero_block_check"]["condition"])
        self.assertNotEqual(self.committed["parse_batch"]["error_exits"],
                            f["parse_batch"]["error_exits"])

    def test_mutant_twin_error_argument(self):
        def mutate(m):
            p = m / "common/batch/blob.go"
            p.write_text(p.read_text().replace("data[i*32]", "blob[i*32]", 1))
        f = self._mutant_facts(mutate)
        differ = f["retrieve_blob_bytes"]["differ"]
        self.assertNotEqual(differ, self.committed["retrieve_blob_bytes"]["differ"])
        self.assertFalse(
            differ["error_reports_unchecked_value"]["common_batch"])

    def test_mutant_parse_batch_value_id_shift(self):
        def mutate(m):
            p = m / "node/derivation/batch_info.go"
            text = p.read_text()
            old = "func (bi *BatchInfo) ParseBatch(batch geth.RPCRollupBatch) error {\n"
            self.assertIn(old, text)
            p.write_text(text.replace(
                old, old + "\t_ = len(batch.Sidecar.Blobs)\n", 1))
        f = self._mutant_facts(mutate)

        def exits(facts):
            return [{k: v for k, v in e.items() if k != "line"}
                    for e in facts["parse_batch"]["error_exits"]]
        self.assertEqual(exits(self.committed), exits(f))

    def test_mutant_combine_payloads_term(self):
        def mutate(m):
            p = m / "common/batch/batch_data.go"
            p.write_text(p.read_text().replace(
                "totalLength := len(cks.blockContexts) + len(newBlockContext)",
                "totalLength := len(newBlockContext)", 1))
        f = self._mutant_facts(mutate)
        self.assertNotEqual(
            self.committed["size_estimators"]["combinePayloads"],
            f["size_estimators"]["combinePayloads"])

    def test_mutant_delete_zero_tx_terminator(self):
        def mutate(m):
            p = m / "common/batch/blob.go"
            text = p.read_text()
            old = "\t\tif typeByte == 0 {\n\t\t\tbreak\n\t\t}\n\n"
            self.assertIn(old, text)
            p.write_text(text.replace(old, "", 1))
        f = self._mutant_facts(mutate)
        decode = f["decode_txs_from_bytes"]
        self.assertNotEqual(decode["dispatch_table"],
                            self.committed["decode_txs_from_bytes"]["dispatch_table"])
        self.assertIsNone(decode["byte_zero_termination"])


if __name__ == "__main__":
    unittest.main()
