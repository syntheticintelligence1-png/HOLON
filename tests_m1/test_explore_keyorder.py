"""The witness explorer must read law statements structurally, not by
JSON.stringify key order. For every ir/0.2 law in laws/M1, the explorer is
run on three serializations of the same statement — the original, a copy
with dict keys recursively reversed, and a copy with them sorted — and the
result (witness / difference / tried) must be identical."""
import json
import unittest
from pathlib import Path

from holon.mpipeline import CompiledMachine, ROOT

FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"
LAWS = ROOT / "laws" / "M1"


def reverse_keys(v):
    if isinstance(v, list):
        return [reverse_keys(x) for x in v]
    if isinstance(v, dict):
        return {k: reverse_keys(v[k]) for k in reversed(list(v.keys()))}
    return v


def sort_keys(v):
    if isinstance(v, list):
        return [sort_keys(x) for x in v]
    if isinstance(v, dict):
        return {k: sort_keys(v[k]) for k in sorted(v.keys())}
    return v


def ir02_laws():
    for p in sorted(LAWS.glob("L_*.json")):
        law = json.loads(p.read_text())
        if law.get("ir_version") == "holon-ir/0.2":
            yield law


class TestExploreKeyOrder(unittest.TestCase):
    _machines: dict = {}

    @classmethod
    def machine_for(cls, law):
        fp = ROOT / law["facts"]
        if fp not in cls._machines:
            cls._machines[fp] = CompiledMachine.build(fp)
        return cls._machines[fp]

    def _result(self, law, cm):
        try:
            out = cm.explore(law)
        except RuntimeError:
            # The explorer crashing identically on every serialization is
            # still a consistent outcome (e.g. laws the pipeline never
            # searches because a proof generator answers first).
            return {"error": True}
        return {k: out.get(k) for k in ("witness", "difference", "tried")}

    def test_key_order_invariance(self):
        for law in ir02_laws():
            cm = self.machine_for(law)
            orig = self._result(law, cm)
            with self.subTest(law=law["law_id"], variant="reversed"):
                rev = dict(law, statement=reverse_keys(law["statement"]))
                self.assertEqual(self._result(rev, cm), orig)
            with self.subTest(law=law["law_id"], variant="sorted"):
                srt = dict(law, statement=sort_keys(law["statement"]))
                self.assertEqual(self._result(srt, cm), orig)

    def test_no_prefix_vars_without_run_from_s0(self):
        # A Trace binder that is never observed from s0 must not be treated
        # as a prefix var: the statement contains no {run|obs, from: {s0}} node.
        law = {"law_id": "L_test_no_prefix", "ir_version": "holon-ir/0.2",
               "statement": {
                   "binders": [{"q": "forall", "name": "t2", "type": "Trace"}],
                   "claim": {"eq": [{"var": "t2"}, {"var": "t2"}]}}}
        res = self.machine_for({"facts": "spec/M1/facts/morph_rollup.json"}).explore(law)
        self.assertIsNone(res.get("witness"))


if __name__ == "__main__":
    unittest.main()
