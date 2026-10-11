"""M2 S2: determinism of the emitted artifacts, coverage-debt format, and the
live re-extraction check (env-gated like tests_m1's replay test).

The committed artifacts must regenerate byte-identically:
  * the Bend source from the committed layouts doc (no solc needed);
  * the layouts doc and debt file from a live solc run (HOLON_EXTRACT=1).
"""
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXTRACTED = ROOT / "spec" / "M2" / "extracted" / "header_layouts.json"
DEBT = ROOT / "spec" / "M2" / "coverage" / "solidity_layout.json"
BEND_SRC = ROOT / "gen" / "M2" / "sol_layout" / "morph_header.bend"


class TestDeterminism(unittest.TestCase):
    def test_bend_regenerates_identically(self):
        from holon.frontends.solidity import layout_bend
        doc = json.loads(EXTRACTED.read_text())
        prog = [{"op": "alloc", "var": "batchPtr", "init": "fmp"}, {"op": "fmp_write"},
                {"op": "comment", "text": "encoder: composed store sequence"}]
        prog += [{"op": op["op"], "offset": op["offset"], "src": op["src"],
                  "when": op.get("when"), "code": op.get("code")}
                 for op in doc["functions"]["enc_sol"]["ops"]]
        prog.append({"op": "edge", "kind": "keccak256"})
        self.assertEqual(layout_bend.generate(doc, {"program": prog}), BEND_SRC.read_text())

    def test_debt_shape(self):
        d = json.loads(DEBT.read_text())
        self.assertEqual(d["frontend"], "solidity/layout")
        self.assertEqual(d["target_commit"], "3e44e795586af3e11285b603ab642c67823add51")
        elems = [i["element"] for i in d["items"]]
        self.assertEqual(elems, sorted(elems))
        for i in d["items"]:
            self.assertTrue(set(i) >= {"element", "kind", "reason"})

    def test_doc_parses_and_names_kinds(self):
        doc = json.loads(EXTRACTED.read_text())
        kinds = {fn: f["kind"] for fn, f in doc["functions"].items()}
        self.assertEqual(kinds, {"enc_sol": "encoder", "ok_sol": "predicate",
                                 "dec_sol": "decoder", "view": "projection"})


@unittest.skipUnless(os.environ.get("HOLON_EXTRACT") == "1",
                     "set HOLON_EXTRACT=1 with solc 0.8.24 + morph checkout present")
class TestLiveExtraction(unittest.TestCase):
    def test_reextract_is_byte_identical(self):
        from holon.frontends.solidity import layout_extract
        doc, debt, aux = layout_extract.extract()
        self.assertEqual(layout_extract._fmt_json(doc), EXTRACTED.read_text())
        debt_doc = {"frontend": "solidity/layout", "target_commit": doc["target"]["commit"],
                    "items": sorted(debt, key=lambda x: x["element"])}
        self.assertEqual(json.dumps(debt_doc, indent=2, ensure_ascii=True) + "\n", DEBT.read_text())


if __name__ == "__main__":
    unittest.main()
