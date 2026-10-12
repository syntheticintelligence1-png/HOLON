"""I11: one deterministic diagram 𝔇 per fact document (whitepaper §4, Defs 4.1-4.4, 4.7; §8.3).

`python -m holon diagram --milestone M2 [--root DIR]` writes gen/M2/diagram/<model>.json for every
fact document (facts/morph_header.json, spec/M1/facts/*.json), validated by
spec/schemas/diagram.schema.json. Every top-level section of every fact document is mapped (zero
unmapped constructs), and the diagram regenerates byte for byte.

Diagram JSON (the fields these tests read):
  {"model": str, "facts": path, "facts_sha256": hex,
   "carriers": [{"id", "cls": rep|state|env|digest|buffer, "base_type", ...}],
   "edges": [{"id", "kind": CODEC|HASH|STORE|LOAD|CONS|TRANS|MIG|SYM, "src", "tgt", "component",
              "partial": bool, "env": bool, "pseudo": bool, "principal_class": str|null,
              "access": {"reads": [term], "writes": [term]}, ...}],
   "principal_classes": [{"id", "caller", "predicate": DSL guard expression or null}],
   "index_terms": [[field, term-as-text]],
   "coverage_debt": [{"kind", "what"}],
   "mapped_sections": {section: what it became}}
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, load_json, run_holon, validate

OUT = ROOT / "gen" / "M2" / "diagram"
SCHEMA = ROOT / "spec" / "schemas" / "diagram.schema.json"
DOCS = {"morph_header": ROOT / "facts" / "morph_header.json",
        "morph_rollup": ROOT / "spec" / "M1" / "facts" / "morph_rollup.json",
        "morph_batchdata": ROOT / "spec" / "M1" / "facts" / "morph_batchdata.json"}


def diagram(model: str) -> dict:
    return load_json(OUT / f"{model}.json")


def kinds(d: dict, kind: str) -> list[dict]:
    return [e for e in d["edges"] if e["kind"] == kind]


class TestDiagramFiles(unittest.TestCase):
    def test_every_fact_document_has_a_valid_diagram(self):
        for model, src in DOCS.items():
            with self.subTest(model=model):
                d = diagram(model)
                self.assertEqual(validate(d, SCHEMA), [])
                self.assertEqual(d["facts"], src.relative_to(ROOT).as_posix())

    def test_zero_unmapped_constructs(self):
        for model, src in DOCS.items():
            with self.subTest(model=model):
                facts = load_json(src)
                d = diagram(model)
                self.assertEqual(set(d["mapped_sections"]), set(facts) - {"facts_version"})

    def test_regeneration_is_byte_identical(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-dia-"))
        try:
            for i in range(2):
                p = run_holon(["diagram", "--milestone", "M2", "--out", str(tmp / str(i))])
                self.assertEqual(p.returncode, 0, p.stdout[-1000:] + p.stderr[-1000:])
            for model in DOCS:
                a = (tmp / "0" / f"{model}.json").read_bytes()
                self.assertEqual(a, (tmp / "1" / f"{model}.json").read_bytes(), model)
                self.assertEqual(a, (OUT / f"{model}.json").read_bytes(), f"{model}: committed diagram is stale")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestPredictedShapes(unittest.TestCase):
    def test_m0_header_diagram(self):
        """I11-P1."""
        d = diagram("morph_header")
        codec = kinds(d, "CODEC")
        self.assertEqual(len(codec), 4, [e["id"] for e in codec])
        self.assertEqual(sum(1 for e in codec if e["partial"]), 1, "the decoder is partial")
        self.assertEqual([e for e in d["edges"] if e.get("projection")], [], "projections are product metadata")
        iface = [c for c in d["carriers"] if c["base_type"] == "Bytes"]
        self.assertEqual(len(iface), 1)
        self.assertEqual(sorted(iface[0]["domains"]), ["ok_go", "ok_sol"])

    def test_rollup_diagram(self):
        """I11-P2."""
        d = diagram("morph_rollup")
        trans = kinds(d, "TRANS")
        self.assertEqual(len(trans), 10)
        self.assertEqual([e["component"] for e in trans if e["env"]], ["wait"])
        mig = kinds(d, "MIG")
        self.assertEqual(sorted(e["component"] for e in mig), ["eta2", "legacy"])
        self.assertEqual([e["component"] for e in mig if e["pseudo"]], ["legacy"])
        self.assertEqual(len(kinds(d, "CONS")), 1)
        self.assertEqual(kinds(d, "HASH"), [])
        self.assertIn("HASH", {x["kind"] for x in d["coverage_debt"]})
        facts = load_json(DOCS["morph_rollup"])
        fields = [s[0] for s in facts["state"]]
        stores = sorted(e["tgt"] for e in kinds(d, "STORE"))
        loads = sorted(e["src"] for e in kinds(d, "LOAD") if e["src"] in set(fields))
        for f in fields:
            with self.subTest(field=f):
                self.assertIn(f, stores)
                self.assertIn(f, loads)
        classes = {c["id"]: c for c in d["principal_classes"]}
        self.assertEqual(set(classes), {"owner", "active_submitter", "challenger", "anyone", "environment"})
        for cid, c in classes.items():
            with self.subTest(principal=cid):
                if cid not in ("anyone", "environment"):
                    self.assertTrue(c["predicate"], "a restricted class has a permission predicate")

    def test_batchdata_diagram(self):
        """I11-P3."""
        self.assertEqual(len(kinds(diagram("morph_batchdata"), "TRANS")), 2)

    def test_index_terms(self):
        """I11-P4."""
        terms = {(f, t) for f, t in diagram("morph_rollup")["index_terms"]}
        for want in (("win", "idx-lfi"), ("chs", "bc")):
            with self.subTest(term=want):
                self.assertIn(want, terms)
        self.assertTrue(any(f.startswith("s_") and "lci+1" in t.replace(" ", "") for f, t in terms),
                        "the shadow slot at lci+1")


if __name__ == "__main__":
    unittest.main()
