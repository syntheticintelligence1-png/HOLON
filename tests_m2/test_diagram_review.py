"""I11 review checks beyond the preregistered tests_m2/test_diagram.py (not predictions).

  * every edge's model link (Def 4.7) names a definition of the committed generated model;
  * TRANS write sets cover exactly the effects (plus the log), and TRANS read sets cover every state
    field the generated model's decide function reads (holon.gen.machine's own computation);
  * zero unmapped constructs is enforced, not just listed: an unknown section, function kind, guard
    key or operator stops the build;
  * the output does not depend on where the repository lives (--root);
  * index terms and shadow bases are derived from the facts: renaming a field or shifting the shadow
    offset in a definition changes them accordingly;
  * no diagram is ever written under the pinned gen/M0 or gen/M1.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json, run_holon

OUT = ROOT / "gen" / "M2" / "diagram"
DOCS = {"morph_header": "facts/morph_header.json",
        "morph_rollup": "spec/M1/facts/morph_rollup.json",
        "morph_batchdata": "spec/M1/facts/morph_batchdata.json"}
MODELS = {"morph_header": "gen/M0/model/morph_header.bend",
          "morph_rollup": "gen/M1/model/morph_rollup.bend",
          "morph_batchdata": "gen/M1/model/morph_batchdata.bend"}


def mini_root() -> Path:
    """A temp root holding just what the diagram reads: the facts, their libraries and the ledger."""
    tmp = Path(tempfile.mkdtemp(prefix="holon-dia-review-"))
    for rel in ("facts", "spec/M1/facts", "spec/M1/lib", "spec/lib", "spec/ledger"):
        shutil.copytree(ROOT / rel, tmp / rel)
    return tmp


def build(root: Path, rel: str) -> dict:
    dia = holon_module("holon.diagram")
    return dia.build(root / rel, root).to_json()


class TestModelLinks(unittest.TestCase):
    def test_model_fn_names_a_definition_of_the_generated_model(self):
        for model, mf in MODELS.items():
            defs = set(re.findall(r"^def ([A-Za-z_][A-Za-z0-9_]*)\(", (ROOT / mf).read_text(), re.M))
            d = load_json(OUT / f"{model}.json")
            names = [e["model_fn"] for e in d["edges"] if e.get("model_fn")]
            names += [p["model_fn"] for p in d.get("predicates", {}).values()]
            names += [p["model_fn"] for c in d["carriers"] for p in c.get("projections", [])]
            self.assertTrue(names, model)
            for n in names:
                with self.subTest(model=model, fn=n):
                    self.assertIn(n, defs)
            for e in d["edges"]:
                if e["kind"] in ("CODEC", "TRANS", "MIG", "CONS"):
                    with self.subTest(model=model, edge=e["id"]):
                        self.assertTrue(e["model_fn"], "a CODEC/TRANS/MIG/CONS edge compiles to a function")


class TestAccessAgainstFacts(unittest.TestCase):
    def test_trans_writes_are_the_effects_and_the_log(self):
        for model in ("morph_rollup", "morph_batchdata"):
            facts = load_json(ROOT / DOCS[model])
            trans = {e["component"]: e for e in load_json(OUT / f"{model}.json")["edges"] if e["kind"] == "TRANS"}
            for a in facts["actions"]:
                with self.subTest(model=model, action=a["name"]):
                    written = {f for f, _ in trans[a["name"]]["access"]["writes"]}
                    self.assertEqual(written, set(a["effects"]) | {"log"})

    def test_trans_reads_cover_what_the_model_decides_on(self):
        machine = holon_module("holon.gen.machine")
        for model in ("morph_rollup", "morph_batchdata"):
            path = ROOT / DOCS[model]
            m = machine.Machine(load_json(path), path)
            trans = {e["component"]: e for e in load_json(OUT / f"{model}.json")["edges"] if e["kind"] == "TRANS"}
            for a in m.actions:
                m.gen_action(a)
                with self.subTest(model=model, action=a["name"]):
                    read = {f for f, _ in trans[a["name"]]["access"]["reads"]}
                    self.assertLessEqual(set(m.reads[a["name"]]), read)

    def test_restricted_predicates_are_guards_of_every_action_in_the_class(self):
        facts = load_json(ROOT / DOCS["morph_rollup"])
        acts = {a["name"]: a for a in facts["actions"]}
        for c in load_json(OUT / "morph_rollup.json")["principal_classes"]:
            if c["predicate"] is None:
                continue
            conj = c["predicate"][1:] if c["predicate"][0] == "&&" else [c["predicate"]]
            for name in c["actions"]:
                with self.subTest(cls=c["id"], action=name):
                    reqs = [g["require"] for g in acts[name]["guards"] if "require" in g]
                    for p in conj:
                        self.assertIn(p, reqs)


class TestStrictness(unittest.TestCase):
    def setUp(self):
        self.root = mini_root()
        self.dia = holon_module("holon.diagram")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def mutate(self, rel: str, fn) -> None:
        p = self.root / rel
        f = json.loads(p.read_text())
        fn(f)
        p.write_text(json.dumps(f, indent=2))

    def assert_unmapped(self, rel: str, fn, needle: str) -> None:
        self.mutate(rel, fn)
        with self.assertRaises(self.dia.DiagramError) as cm:
            self.dia.build(self.root / rel, self.root)
        self.assertIn(needle, str(cm.exception))

    def test_unknown_section(self):
        self.assert_unmapped(DOCS["morph_rollup"], lambda f: f.update(oracles={}), "unmapped facts sections")

    def test_unknown_function_kind(self):
        def add(f):
            f["functions"]["h"] = {"kind": "hash", "from": "Bytes", "to": "Bytes"}
        self.assert_unmapped(DOCS["morph_header"], add, "fits no edge kind")

    def test_unknown_guard_key(self):
        def add(f):
            f["actions"][0]["guards"][0]["assume"] = True
        self.assert_unmapped(DOCS["morph_rollup"], add, "unmapped keys")

    def test_unknown_operator(self):
        def add(f):
            f["actions"][-1]["effects"]["t"] = ["*", "t", "dt"]
        self.assert_unmapped(DOCS["morph_rollup"], add, "unknown operator")


class TestDerived(unittest.TestCase):
    def setUp(self):
        self.root = mini_root()

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_root_independent(self):
        out = self.root / "out"
        p = run_holon(["diagram", "--milestone", "M2", "--root", str(self.root), "--out", str(out)])
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        for model in DOCS:
            with self.subTest(model=model):
                self.assertEqual((out / f"{model}.json").read_bytes(), (OUT / f"{model}.json").read_bytes())

    def test_renamed_field_renames_its_index_terms(self):
        p = self.root / DOCS["morph_rollup"]
        p.write_text(p.read_text().replace('"bc"', '"bcx"'))
        terms = {tuple(t) for t in build(self.root, DOCS["morph_rollup"])["index_terms"]}
        self.assertIn(("chs", "bcx"), terms)
        self.assertNotIn(("chs", "bc"), terms)

    def test_shadow_offset_follows_the_definitions(self):
        p = self.root / DOCS["morph_rollup"]
        f = json.loads(p.read_text())
        for name in ("bvh_at", "tag_at"):
            body = json.dumps(f["defs"][name]["body"])
            old = '["-", ["-", "idx", ["call", "lci", "lfi", "win"]], 1]'
            self.assertIn(old, body)
            f["defs"][name]["body"] = json.loads(body.replace(old, old[:-2] + "2]"))
        p.write_text(json.dumps(f, indent=2))
        d = build(self.root, DOCS["morph_rollup"])
        bases = {c["id"]: c.get("slot_base") for c in d["carriers"] if c["id"].startswith("s_")}
        self.assertEqual(bases, {"s_bd": "lci+2", "s_bvh": "lci+2", "s_csr": "lci+2", "s_tag": "lci+2"})
        self.assertIn(["s_csr", "lci+2"], d["index_terms"])


class TestPinnedTrees(unittest.TestCase):
    def test_no_diagram_under_m0_or_m1(self):
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                p = run_holon(["diagram", "--milestone", m])
                self.assertNotEqual(p.returncode, 0)
                self.assertFalse((ROOT / "gen" / m / "diagram").exists())


if __name__ == "__main__":
    unittest.main()
