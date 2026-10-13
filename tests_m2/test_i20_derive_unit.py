"""I20 builder A (model side), unit tests of the derivation on extracted facts: rule SORT-width
(holon.sorts.width), the adoption sidecar (holon.sorts.reextract) and the reextraction acceptance
(holon.statement_diff). Not preregistered, not an outcome: the laws, records and STATEMENT_DIFF entries these
modules produce for the rollup are the integrator's to generate once the I19 follow-up's re-extraction is in.

The adoption is tested in throwaway roots: a planted toy (tests_m2/fixtures/i20_model/toy/book.extracted.json, its
follow-up extraction), the committed I17 header document, and, for the reextraction channel, a throwaway copy of the
repository with the rollup adoption (tests_m2/fixtures/i20_model/morph/derive_extracted.json) put in place.
"""
from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, copy_repo, load_json

TOY = ROOT / "tests_m2" / "fixtures" / "i20_model" / "toy"
MORPH = ROOT / "tests_m2" / "fixtures" / "i20_model" / "morph"
HEADER = "spec/M2/facts/morph_header.extracted.json"


def adopt(root: Path, milestone: str, docs: list[str], reextraction=(), width=True, corpus=None) -> None:
    p = root / "spec" / milestone / "lib" / "derive_extracted.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    d = {"derive_extracted_version": "holon-derive-extracted/0.1", "doc": "test", "documents": docs,
         "reextraction": list(reextraction), "width": width}
    if corpus:
        d["width_corpus"] = corpus
    p.write_text(json.dumps(d, indent=2, sort_keys=True) + "\n")


class TestWidthBasis(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="holon-i20w-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def put(self, rel: str, src: Path) -> None:
        (self.root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, self.root / rel)

    def test_without_an_adoption_nothing_is_derived(self):
        from holon.sorts import width
        self.assertEqual(width.basis_elements("T20", self.root), [])
        self.assertEqual(width.basis_elements("T21", ROOT), [])   # a milestone without the sidecar

    def test_the_header_documents_truncating_stores_come_out(self):
        """The two width sites of the rollup header encoder (the I17 document's truncating fields), not tuned."""
        from holon.sorts import width
        self.put(HEADER, ROOT / HEADER)
        adopt(self.root, "T20", [HEADER])
        got = [(s["field"], s["width"], s["value_bits"], s["span"]) for s in width.basis_elements("T20", self.root)]
        self.assertEqual(got, [("batchIndex", 64, 256, "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:144"),
                               ("totalL1MessagePopped", 64, 256,
                                "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol:166")])
        ids = [width.law_id(s["span"], s["record"], s["field"], s["width"]) for s in width.basis_elements("T20", self.root)]
        self.assertTrue(all(i.startswith("L_sort_width_batchheadercodecv0_1") for i in ids), ids)

    def test_a_memory_store_of_a_wide_value_into_a_narrow_field_is_a_site_and_an_explicit_conversion_is_not(self):
        from holon.sorts import width
        self.put("toy/book.json", TOY / "book.extracted.json")
        adopt(self.root, "T20", ["toy/book.json"])
        sites = width.basis_elements("T20", self.root)
        self.assertEqual([(s["field"], s["width"], s["value_bits"], s["span"], s["entry_points"]) for s in sites],
                         [("mem@0", 64, 256, "src/Book.sol:86", ["stamp"])])

    def test_widths_of_terms(self):
        from holon.sorts.width import width_of
        p, f = {"x": 64, "y": 256}, {"total": 64}
        self.assertEqual(width_of(["param", "x"], p, f), 64)
        self.assertEqual(width_of(["+", ["param", "x"], 1], p, f), 65)
        self.assertEqual(width_of([">>", ["word", ["param", "h"], 1], 192], p, f), 64)
        self.assertEqual(width_of(["trunc", 32, ["param", "y"]], p, f), 32)
        self.assertEqual(width_of(["storage", "total"], p, f), 64)
        self.assertEqual(width_of(["param", "unknown"], p, f), 256)

    def test_law_ir_and_decision_on_a_corpus(self):
        from holon import machine
        from holon.sorts import width
        self.put("toy/book.json", TOY / "book.extracted.json")
        adopt(self.root, "T20", ["toy/book.json"])
        site = width.basis_elements("T20", self.root)[0]
        law = width.law_ir(site, "T20", "0" * 64, "holon-rules/1.0")
        self.assertEqual(law["law_id"], width.law_id("src/Book.sol:86", None, "mem@0", 64))
        self.assertEqual(width.width_law(law), "width:src/Book.sol:86:-.mem@0")
        model = machine.load_extracted(TOY / "book.extracted.json", ROOT, source=TOY)
        state = {"0x%064x" % 0: "0x%064x" % 0xA11CE}
        env = {"caller": 0xA11CE, "msg.value": 0}
        corpus = {"steps": [{"id": f"s{i}", "state": state, "action": "stamp", "args": {"idx": v}, "env": env}
                            for i, v in enumerate((5, (1 << 64) - 1))]}
        d = width.decide(law, self.root, corpus, model=model)
        self.assertEqual(d["status"], "UNKNOWN")
        self.assertNotIn("witness_candidate", d)
        self.assertIn("2 steps, 2 reaching", d["bound"])
        corpus["steps"].append({"id": "s2", "state": state, "action": "stamp", "args": {"idx": 1 << 64}, "env": env})
        d = width.decide(law, self.root, corpus, model=model)
        self.assertEqual((d["status"], d["witness_candidate"]["step"]), ("UNKNOWN", "s2"))
        d = width.decide(law, self.root, None, model=model)
        self.assertEqual(d["status"], "UNKNOWN")
        self.assertIn("no corpus", d["bound"])


class TestReextraction(unittest.TestCase):
    """The reextraction channel on the rollup documents, in a throwaway copy with the rollup adoption in place."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        from holon import statement_diff as SD
        cls.SD = SD
        log = cls.repo / "laws" / "STATEMENT_DIFF.jsonl"
        committed = [e for e in (json.loads(x) for x in log.read_text().splitlines() if x.strip())
                     if e.get("kind") == "reextraction"]
        if committed:   # the tree adopted the extracted documents (the I20 integration): its committed entries
            cls.entries = committed
        else:
            shutil.copy(MORPH / "derive_extracted.json", cls.repo / "spec" / "M2" / "lib" / "derive_extracted.json")
            cls.entries = SD.reextraction_entries("M2", cls.repo)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_the_source_span_site_laws_are_re_derived_and_their_entries_accepted(self):
        laws = sorted(e["law_id"] for e in self.entries)
        self.assertTrue(laws and all(l.startswith("L_sort_site_") for l in laws), laws)
        self.assertNotIn("L_sort_site_def_w_b4cd5068", laws)    # a definition site has no source span
        for e in self.entries:
            with self.subTest(law=e["law_id"]):
                self.assertFalse(e.get("signature"))
                self.assertEqual(e["old"], e["new"])
                self.assertTrue(all(k.startswith("site:") for k in e["refs"]))
                r = self.SD.check_entry(e, self.repo)
                self.assertTrue(r["ok"], r)

    def test_tampered_entries_are_rejected(self):
        e = self.entries[0]
        bad = copy.deepcopy(e)
        bad["new_hash"] = "sha256:" + "0" * 64
        self.assertFalse(self.SD.check_entry(bad, self.repo)["ok"])
        bad = copy.deepcopy(e)
        bad["derivation"]["subform"] = "other"
        self.assertFalse(self.SD.check_entry(bad, self.repo)["ok"])
        bad = copy.deepcopy(e)
        bad["new"]["statement"]["scope"] = {"kind": "bounded", "H": 1}
        self.assertFalse(self.SD.check_entry(bad, self.repo)["ok"])
        bad = copy.deepcopy(e)
        bad["facts"] = "tests_m2/fixtures/toy_queue/toy_queue.facts.json"
        r = self.SD.check_entry(bad, self.repo)
        self.assertFalse(r["ok"])
        self.assertIn("hand-written", r["reason"])


if __name__ == "__main__":
    unittest.main()
