"""HUMAN_ANSWERS Q104 (1) and Q109: the measured base spec/M6/lib/base_run.json and its generator tools/base_protocol.py.

The base is I116's landed protocol plus the union of the landed opt-in keys (tools/base_protocol.py names both). For
the root and every landed protocol the tool names:

- B1: the committed file is the tool's output (its --check).
- B2: no key is lost. Every key path of the root and of each landed protocol is in the base, with an empty dict or
  list counting as a value of its own, except the meta keys. The base holds no other key but its own meta keys.
- B3: each base value is the root's, or the value of the landed protocols that set it as an opt-in.
- B4: the tool's flattening keeps an empty dict at every depth (a planted protocol round-trips exactly).
- B5: each protocol of a later generation (Q109's note) names the base it measured on: its `base_protocol` is the
  base, and its `doc` names the sha256 of the base built from the generations before it.
- B6 (planted): a later-generation protocol is compared with the base it measured on, so its opt-in survives a
  regeneration (the build is a fixed point once written), while a dropped key or a wrong base_protocol is refused.

F-M6-12 is why: until the fix the flattening dropped every empty dict, so six keys that every landed protocol carries
as {} were missing from the base, and every run on it broke at Go extraction and the typed part. B1 alone could not
see it, because it regenerates by the same rule. B2 reads the protocols with its own flattening.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("base_protocol", ROOT_DIR / "tools" / "base_protocol.py")
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)

BASE_META = {"base_protocol", "doc", "go_machines.out", "iteration", "out"}   # the meta keys the base writes itself
_ABSENT = object()


def leaves(d: dict, p: str = "") -> dict:
    """Every key path to a value, written independently of the tool: an empty dict, like a list, is a value."""
    o = {}
    for k, v in d.items():
        if isinstance(v, dict) and v:
            o.update(leaves(v, p + k + "."))
        else:
            o[p + k] = v
    return o


def load(rel: str) -> dict:
    return json.loads((ROOT_DIR / rel).read_text(encoding="utf-8"))


class TestBaseProtocol(unittest.TestCase):
    def test_b1_current(self):
        self.assertEqual((ROOT_DIR / bp.OUT).read_text(encoding="utf-8"), bp.build(),
                         "spec/M6/lib/base_run.json differs from tools/base_protocol.py's output")

    def test_b2_no_key_lost(self):
        base = set(leaves(load(bp.OUT)))
        union = set().union(*(leaves(load(r)) for r in (bp.ROOT, *bp.LANDED)))
        self.assertEqual(sorted(union - bp.META - base), [], "keys of a landed protocol missing from the base")
        self.assertEqual(sorted(base - bp.META - union), [], "keys in the base that no landed protocol has")
        self.assertEqual(base & bp.META, BASE_META)

    def test_b3_each_value_from_the_root_or_its_opt_in(self):
        root = leaves(load(bp.ROOT))
        opt_ins: dict = {}
        for g, gen in enumerate(bp.GENERATIONS):
            for r in gen:
                p = leaves(load(r))
                # a later generation's own base is the base built from the generations before it (B5 checks its sha)
                own = (leaves(json.loads(bp.build(bp.GENERATIONS[:g]))) if g
                       else leaves(load(p.get("base_protocol") or bp.ROOT)))
                for k, v in p.items():
                    if k not in bp.META and own.get(k, _ABSENT) != v:
                        opt_ins.setdefault(k, []).append((r, v))
        for k, v in leaves(load(bp.OUT)).items():
            if k in bp.META:
                continue
            if k in opt_ins:
                for r, w in opt_ins[k]:
                    self.assertEqual(v, w, f"{k}: the base's value is not {r}'s opt-in value")
            else:
                self.assertEqual(v, root.get(k, _ABSENT), f"{k}: the base's value is not the root's")

    def test_b4_flattening_keeps_empty_dicts(self):
        planted = {"a": {}, "b": {"c": {}, "d": {"e": {}}, "f": [], "g": None}, "h": {"i": 0, "j": {}}}
        self.assertEqual(bp._unflat(bp._flat(planted)), planted)

    def test_b5_later_generations_name_the_base_they_measured_on(self):
        for g, gen in enumerate(bp.GENERATIONS):
            if not g:
                continue
            sha = hashlib.sha256(bp.build(bp.GENERATIONS[:g]).encode("utf-8")).hexdigest()
            for r in gen:
                p = load(r)
                self.assertEqual(p.get("base_protocol"), bp.OUT, r)
                self.assertIn(sha, p.get("doc", ""), f"{r}: its doc does not name the sha256 of the base it measured on")


class TestGenerationsPlanted(unittest.TestCase):
    """B6: a planted generation-1 protocol over a copy of the root and the generation-0 protocols."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "spec/M6/lib").mkdir(parents=True)
        for r in (bp.ROOT, *bp.GENERATIONS[0]):
            shutil.copy(ROOT_DIR / r, self.tmp / r)
        self.saved, bp.ROOT_DIR = bp.ROOT_DIR, self.tmp
        self.g0 = (bp.GENERATIONS[0],)
        self.base0 = bp.build(self.g0)
        (self.tmp / bp.OUT).write_text(self.base0, encoding="utf-8")   # as on the lead before the planted key lands

    def tearDown(self):
        bp.ROOT_DIR = self.saved
        shutil.rmtree(self.tmp)

    def plant(self, edit) -> tuple:
        p = json.loads(self.base0)
        p.update({"iteration": "I999", "base_protocol": bp.OUT, "out": "results/M6/I999/holon",
                  "doc": "planted: the base (sha256 " + hashlib.sha256(self.base0.encode()).hexdigest() + ") plus go.planted"})
        edit(p)
        (self.tmp / "spec/M6/lib/i999_run.json").write_text(json.dumps(p, indent=2), encoding="utf-8")
        return self.g0 + (("spec/M6/lib/i999_run.json",),)

    def test_b6_opt_in_survives_and_is_a_fixed_point(self):
        gens = self.plant(lambda p: p["go"].update({"planted": "x"}))
        text = bp.build(gens)
        f, f0 = bp._flat(json.loads(text)), bp._flat(json.loads(self.base0))
        self.assertEqual(sorted(k for k in f if k not in bp.META and f.get(k) != f0.get(k)), ["go.planted"])
        (self.tmp / bp.OUT).write_text(text, encoding="utf-8")   # written: the next build must not lose the opt-in
        self.assertEqual(bp.build(gens), text)

    def test_b6_dropped_key_and_wrong_base_are_refused(self):
        with self.assertRaises(SystemExit):
            bp.build(self.plant(lambda p: p["go"].pop("primitives")))
        with self.assertRaises(SystemExit):
            bp.build(self.plant(lambda p: p.update({"base_protocol": bp.ROOT})))


if __name__ == "__main__":
    unittest.main()
