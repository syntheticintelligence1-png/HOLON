"""I15, builder A (not preregistered; construction checks beside tests_m2/test_sort_sites.py): the SORT-site ghost
instrumentation changes no non-ghost behaviour, and its predicates follow rules R8-R10.

  1. Text. The instrumented rollup model above GHOST_MARKER is byte for byte the model `holon run --milestone M2`
     builds for the document (holon.mpipeline.milestone_model: Reach, the guard-derived permissions, the threaded
     oracle tables), and the ghost section declares no type and only ghost functions.
  2. Behaviour. Compiled with the pinned Bend, the plain model and the instrumented model give the same final state
     and the same observations for run(trace, s0) on a seeded corpus of traces over every action (generic input
     values), so the ghost section cannot change what any non-ghost definition computes.
  3. Semantics. On the compiled instrumented model: for every law, every action that is not an entry point gives
     site_<x> true and hit_<x> false; at s0, finalizeBatch with idx 0 reaches the :636 site at its realization check
     (hit true) and violates it (site false), while idx 1 is stopped by an earlier require (hit false, site true).
  4. The toy fixture (milestone T15): the same text and behaviour checks.
"""
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i15 as H
from tests_m2._m2 import ROOT, holon_module, load_json, run_holon

ROLLUP_REL = "spec/M1/facts/morph_rollup.json"
TOY_REL = "tests_m2/fixtures/sort_sites/toy_sites.json"
LAW_636 = "L_sort_site_rollup_636_e68daf06"
GHOST_PREFIXES = ("site_", "hit_", "gs_", "gh_", "gd_", "gdh_")


def compile_bend(src: Path) -> Path:
    bend = holon_module("holon.bend")
    art = src.with_suffix(".mjs")
    r = bend.run([src.name, "-o", art.name], cwd=src.parent)
    if r.code != 0 or not art.exists():
        raise AssertionError(f"bend failed to compile {src.name}: {r.out[-2000:]}")
    return art


def calls(module: Path, cs: list) -> list:
    mp = holon_module("holon.mpipeline")
    p = subprocess.run(["node", str(mp.MACHINE_JS)], input=json.dumps({"module": str(module), "calls": cs}),
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise AssertionError(p.stderr[-2000:])
    return json.loads(p.stdout)["results"]


def corpus(facts: dict, n: int, seed: int) -> list[list[dict]]:
    """Seeded traces over every action, inputs from small generic values."""
    rnd = random.Random(seed)
    nats = [0, 1, 2, 3, 5, 10, 11, 21]

    def val(t: str):
        if t == "Nat":
            return rnd.choice(nats)
        if t == "Bool":
            return rnd.random() < 0.5
        if t == "List<Nat>":
            return [rnd.choice(nats) for _ in range(rnd.randint(0, 2))]
        raise AssertionError(f"no generator for {t}")
    out = []
    for _ in range(n):
        tr = []
        for _ in range(rnd.randint(1, 6)):
            a = rnd.choice(facts["actions"])
            tr.append({"$": f"A_{a['name']}", **{x: val(t) for x, t in a["inputs"]}})
        out.append(tr)
    return out


class _Ghost:
    milestone = "M2"
    facts_rel = ROLLUP_REL
    derivation: dict = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-i15-ghost-"))
        cls.sites = holon_module("holon.sorts.sites")
        cls.mp = holon_module("holon.mpipeline")
        cls.fp = ROOT / cls.facts_rel
        cls.derivation = cls.load_derivation()
        cls.text = cls.sites.instrumented_model(cls.fp, cls.derivation)
        cls.head, cls.ghost = cls.text.split(H.GHOST_MARKER)
        cls.cm = cls.mp.milestone_model(cls.milestone, cls.fp)
        src = cls.tmp / "inst" / cls.cm.source.name
        src.parent.mkdir()
        src.write_text(cls.text)
        cls.inst = compile_bend(src)
        cls.tables = [[] for _ in cls.cm.m.threaded]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_text_above_the_marker_is_the_run_model(self):
        self.assertEqual(self.text.count(H.GHOST_MARKER), 1)
        self.assertEqual(self.head.rstrip("\n"), self.cm.source.read_text().rstrip("\n"))

    def test_ghost_section_declares_only_ghost_functions(self):
        import re
        self.assertIsNone(re.search(r"(?m)^type\s", self.ghost))
        names = re.findall(r"(?m)^def\s+(\w+)\(", self.ghost)
        self.assertTrue(names)
        for n in names:
            self.assertTrue(n.startswith(GHOST_PREFIXES), n)
        for e in self.derivation["laws"]:
            if e["facts"] == self.facts_rel:
                x = e["law_id"][len("L_sort_site_"):]
                self.assertIn(f"site_{x}", names)
                self.assertIn(f"hit_{x}", names)

    def test_plain_and_instrumented_models_behave_alike(self):
        facts = load_json(self.fp)
        trs = corpus(facts, 120, 20261015)
        tabs = [{"val": t} for t in self.tables]
        cs = []
        for tr in trs:
            cs.append({"fn": "run", "args": [{"val": tr}, {"fn": "s0", "args": []}, *tabs]})
            cs.append({"fn": "obs", "args": [{"val": tr}, {"fn": "s0", "args": []}, *tabs]})
        plain = calls(self.cm.artifact, cs)
        inst = calls(self.inst, cs)
        self.assertEqual(len(plain), len(cs))
        self.assertFalse([r for r in plain if isinstance(r, dict) and "error" in r][:1])
        oks = sum(1 for r in plain[1::2] for o in r if o == {"$": "O_Ok"})
        self.assertGreater(oks, 10, "the corpus exercises successful steps")
        self.assertEqual(plain, inst)

    def test_non_entry_actions_neither_hit_nor_violate(self):
        facts = load_json(self.fp)
        tabs = [{"val": t} for t in self.tables]
        cs, keys = [], []
        for e in self.derivation["laws"]:
            if e["facts"] != self.facts_rel:
                continue
            x = e["law_id"][len("L_sort_site_"):]
            for a in facts["actions"]:
                if a["name"] in e["entry_points"]:
                    continue
                act = {"$": f"A_{a['name']}", **{n: ([] if t.startswith("List<") else (False if t == "Bool" else 1))
                                                  for n, t in a["inputs"]}}
                for fn in ("site_", "hit_"):
                    cs.append({"fn": fn + x, "args": [{"val": act}, {"fn": "s0", "args": []}, *tabs]})
                    keys.append((e["law_id"], a["name"], fn))
        got = calls(self.inst, cs)
        for k, v in zip(keys, got):
            self.assertEqual(v, k[2] == "site_", k)

    @classmethod
    def load_derivation(cls) -> dict:
        return load_json(H.LAWS2 / "DERIVATION.json")


class TestRollupGhost(_Ghost, unittest.TestCase):
    def test_636_is_hit_at_its_realization_check(self):
        x = LAW_636[len("L_sort_site_"):]
        tabs = [{"val": t} for t in self.tables]
        s0 = {"fn": "s0", "args": []}
        cs = []
        for idx in (0, 1):
            act = {"val": {"$": "A_finalizeBatch", "who": 1, "idx": idx}}
            cs += [{"fn": f"site_{x}", "args": [act, s0, *tabs]}, {"fn": f"hit_{x}", "args": [act, s0, *tabs]}]
        self.assertEqual(calls(self.inst, cs), [False, True, True, False])


class TestToyGhost(_Ghost, unittest.TestCase):
    milestone = "T15"
    facts_rel = TOY_REL

    @classmethod
    def load_derivation(cls) -> dict:
        d = cls.tmp / "toy"
        a = run_holon(["sorts", "--facts", TOY_REL, "--out", str(d / "sorts")])
        b = run_holon(["derive", "--milestone", "T15", "--facts", TOY_REL, "--assignment", str(d / "sorts" / "assignment.json"),
                       "--out", str(d / "laws"), "--obstructions", str(d / "obstructions.json")])
        if a.returncode or b.returncode:
            raise AssertionError(a.stdout + a.stderr + b.stdout + b.stderr)
        return load_json(d / "laws" / "DERIVATION.json")


if __name__ == "__main__":
    unittest.main()
