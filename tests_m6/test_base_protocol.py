"""HUMAN_ANSWERS Q104 (1) and Q109: the measured base spec/M6/lib/base_run.json and its generator tools/base_protocol.py.

The base is I116's landed protocol plus the union of the landed opt-in keys (tools/base_protocol.py names both). For
the root and every landed protocol the tool names:

- B1: the committed file is the tool's output (its --check).
- B2: no key is lost. Every key path of the root and of each landed protocol is in the base, with an empty dict or
  list counting as a value of its own, except the meta keys. The base holds no other key but its own meta keys.
- B3: each base value is the root's, or the value of the landed protocols that set it as an opt-in.
- B4: the tool's flattening keeps an empty dict at every depth (a planted protocol round-trips exactly).

F-M6-12 is why: until the fix the flattening dropped every empty dict, so six keys that every landed protocol carries
as {} were missing from the base, and every run on it broke at Go extraction and the typed part. B1 alone could not
see it, because it regenerates by the same rule. B2 reads the protocols with its own flattening.
"""
from __future__ import annotations

import importlib.util
import json
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
        for r in bp.LANDED:
            p = leaves(load(r))
            own = leaves(load(p.get("base_protocol") or bp.ROOT))
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


if __name__ == "__main__":
    unittest.main()
