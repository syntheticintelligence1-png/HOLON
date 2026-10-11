"""M2 S2: the extracted layout facts are layout-equal to the hand-written
Solidity encoders/decoders in facts/morph_header.json (acceptance 1).

The extractor itself never reads facts/; this test is the comparison point.
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

from holon import facts as F, layout as L  # noqa: E402

EXTRACTED = ROOT / "spec" / "M2" / "extracted" / "header_layouts.json"
HAND = ROOT / "facts" / "morph_header.json"


def _clean(rules):
    return [{"if": r["if"], "then": r["then"]} for r in rules]


class TestExtractedLayouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ext = json.loads(EXTRACTED.read_text())
        cls.hand = json.loads(HAND.read_text())

    def test_document_shape(self):
        self.assertEqual(self.ext["facts_version"], "holon-facts/0.1")
        self.assertEqual(self.ext["extraction"]["method"].split(" ")[0], "solc")
        self.assertEqual(self.ext["target"]["commit"], "3e44e795586af3e11285b603ab642c67823add51")
        self.assertEqual(set(self.ext["functions"]), {"enc_sol", "ok_sol", "dec_sol", "view"})

    def test_header_fields(self):
        want = [(f["name"], f["width"]) for f in self.hand["types"]["Header"]["fields"]]
        got = [(f["name"], f["width"]) for f in self.ext["types"]["Header"]["fields"]]
        self.assertEqual(got, want)

    def test_layout_equal_all_versions(self):
        for v in (0, 1, 2):
            with self.subTest(version=v):
                a = L.layout(self.ext, "enc_sol", v)
                b = L.layout(self.hand, "enc_sol", v)
                self.assertEqual(L.diff(a, b), [],
                                 [(i, a[i], b[i]) for i in L.diff(a, b)][:10])

    def test_every_hand_op_recovered(self):
        """Every mstore/mstore8 the hand facts record is recovered at the same offset."""
        hand_ops = {(o["op"], o["offset"]) for o in self.hand["functions"]["enc_sol"]["ops"]}
        ext_ops = {(o["op"], o["offset"]) for o in self.ext["functions"]["enc_sol"]["ops"]}
        self.assertEqual(ext_ops, hand_ops)

    def test_rules_equal(self):
        self.assertEqual(_clean(self.ext["functions"]["ok_sol"]["rules"]),
                         _clean(self.hand["functions"]["ok_sol"]["rules"]))

    def test_getters_equal_dec_go(self):
        want = [(g["name"], g["offset"], g["width"], g.get("when"))
                for g in self.hand["functions"]["dec_go"]["getters"]]
        got = [(g["name"], g["offset"], g["width"], g.get("when"))
               for g in self.ext["functions"]["dec_sol"]["getters"]]
        self.assertEqual(got, want)

    def test_view_equal(self):
        self.assertEqual(self.ext["functions"]["view"]["order"], self.hand["functions"]["view"]["order"])
        self.assertEqual(self.ext["functions"]["view"]["when"], self.hand["functions"]["view"]["when"])

    def test_domain_and_lengths(self):
        e = self.ext["functions"]["enc_sol"]
        self.assertEqual(e["domain"], {"version_le": 2})
        self.assertEqual(e["length_by_version"], {"0": 249, "1": 257, "2": 257})
        self.assertEqual(e["memory_init"], "dirty")

    def test_decoder_reads_through_encoder(self):
        """For every version: the extracted getters recover every field the
        extracted encoder wrote (the decode-encode round trip on layouts)."""
        for v in (0, 1, 2):
            lay = L.layout(self.ext, "enc_sol", v)
            for g in self.ext["functions"]["dec_sol"]["getters"]:
                if not F.when_ok(g.get("when"), v):
                    continue
                cells = lay[g["offset"]:g["offset"] + g["width"]]
                name = g["name"]
                if name == "sequencerSetVerifyHash":
                    # the encoder writes constant zeros here (Rollup constant arg)
                    self.assertTrue(all(c[0] == "const" and c[1] == 0 for c in cells), (v, name))
                    continue
                self.assertTrue(all(c[0] == "field" and c[1] == name and c[2] == k
                                    for k, c in enumerate(cells)), (v, name, cells))


if __name__ == "__main__":
    unittest.main()
