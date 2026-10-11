"""Modifier handling in S1's transition extraction.

Every modifier on an action either translates its body (from the AST) into
guards, or — if it is listed in spec["modifiers_abstracted"] or its definition
cannot be found — produces an explicit `abstracted_modifier` coverage item.
A silently skipped modifier is a bug.
"""
import json
import unittest
from pathlib import Path

from holon.frontends.solidity import astload
from holon.frontends.solidity import extract as ex

REPO = Path(__file__).resolve().parents[2]
COVERAGE = REPO / "spec" / "M2" / "coverage" / "solidity_transitions.json"


def _world_spec():
    import os
    spec = ex.load_spec()
    morph = os.path.expanduser(
        os.environ.get(spec["morph_root_env"], spec["morph_root_default"]))
    return ex.astload.run_solc(spec, morph), spec


class TestModifierDebt(unittest.TestCase):
    def test_every_abstracted_skip_produces_debt(self):
        """Each spec["modifiers_abstracted"] name used by an action must leave an
        action:<a>.modifier:<name> coverage item of kind abstracted_modifier."""
        world, spec = _world_spec()
        reasons, call_guards = {}, {}
        produced = []
        for a in spec["actions"]:
            try:
                tr, contract, fname = ex.init_tr(world, spec, a, reasons, call_guards)
            except Exception:
                continue
            fn = tr.find_fn(contract, fname)
            if fn is None:
                continue
            used = [((mi.get("modifierName") or {}).get("name") or "")
                    for mi in fn.get("modifiers", [])]
            for name in used:
                if name in spec.get("modifiers_abstracted", []):
                    produced.append((a["name"], name))
        items = {i["element"] for i in json.loads(COVERAGE.read_text())["items"]
                 if i["kind"] == "abstracted_modifier"}
        for action, name in produced:
            self.assertIn(f"action:{action}.modifier:{name}", items,
                          f"abstracted modifier {name} on {action} left no coverage item")


if __name__ == "__main__":
    unittest.main()
