"""Audit M2/1 F-M2-03: holon-ir/0.3 statement refs are the transitive closure of what a statement depends on.

holon.gen.refs.refs(law, facts, oracles, lib) covers, transitively over the facts def graph and the target library:
an observer's defs and library builtins, cost/elapsed's facts.disch, each action a step can reach (src and doc
text excluded), and generator-synthesized helpers as {template_id, template_version}. Before the fix the step
ref hashed every action's source text, cost and elapsed ignored disch, observers ignored the defs and builtins they
call, and helpers had no template id.

The facts are the M1 rollup facts and their library (spec/M1/facts, spec/M1/lib); the constructs each test edits
are found by walking the facts, so the tests name no target identifier.
"""
import copy
import unittest

from tests_m2._m2 import ROOT, holon_module, load_json

FACTS_REL = "spec/M1/facts/morph_rollup.json"


def law(statement: dict) -> dict:
    return {"ir_version": "holon-ir/0.3", "law_id": "L3_refs", "milestone": "T1", "rule": "SORT",
            "rule_catalog_version": "holon-rules/0.1", "facts": FACTS_REL, "facts_sha256": "", "statement": statement}


def calls(e, out: set) -> set:
    if isinstance(e, list) and e:
        if e[0] == "call" and len(e) > 1 and isinstance(e[1], str):
            out.add(e[1])
        for x in e[1:]:
            calls(x, out)
    elif isinstance(e, dict):
        for x in e.values():
            calls(x, out)
    return out


def literal(ty: str) -> dict:
    return {"Nat": {"nat": 0}, "Bool": {"bool": False}, "List<Nat>": {"nats": []}}[ty]


class TestRefs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = holon_module("holon.gen.refs")
        cls.facts = load_json(ROOT / FACTS_REL)
        cls.lib = cls.R.lib_docs_for(law({"binders": []}), ROOT)

    def h(self, lw: dict, facts: dict | None = None, lib=None) -> str:
        return self.R.law_hash(lw, facts if facts is not None else self.facts, lib=lib if lib is not None else self.lib)

    def obs_law(self, name: str) -> dict:
        ty = self.facts["observers"][name]["type"]
        rhs = {"Nat": {"nat": 0}, "Bool": {"bool": True}}.get(ty)
        self.assertIsNotNone(rhs, f"observer {name} of type {ty}: callers pick Nat or Bool observers")
        return law({"binders": [{"q": "forall", "name": "s", "type": "State"}], "assume": [],
                    "claim": {"eq": [{"obsv": name, "of": {"var": "s"}}, rhs]}})

    def observer_calling(self, pred):
        for name, o in sorted(self.facts["observers"].items()):
            if o["type"] in ("Nat", "Bool") and any(pred(c) for c in calls(o["body"], set())):
                return name
        raise AssertionError("no observer of the facts calls such a definition")

    def test_an_observer_covers_the_facts_defs_it_calls(self):
        defs = self.facts["defs"]
        name = self.observer_calling(lambda c: c in defs)
        lw = self.obs_law(name)
        d = sorted(c for c in calls(self.facts["observers"][name]["body"], set()) if c in defs)[0]
        base = self.h(lw)
        f2 = copy.deepcopy(self.facts)
        f2["defs"][d]["body"] = ["+", f2["defs"][d]["body"], 0] if defs[d]["type"] == "Nat" else ["&&", f2["defs"][d]["body"], True]
        self.assertNotEqual(self.h(lw, f2), base, f"editing def {d}, which observer {name} calls")
        f3 = copy.deepcopy(self.facts)
        f3["defs"][d]["doc"] = "edited documentation"
        self.assertEqual(self.h(lw, f3), base, "a doc edit changes no hash")
        other = sorted(x for x in defs if x not in self.R.refs(lw, self.facts) and "def:" + x not in self.R.refs(lw, self.facts))
        if other:
            f4 = copy.deepcopy(self.facts)
            f4["defs"][other[0]]["body"] = ["+", f4["defs"][other[0]]["body"], 0]
            self.assertEqual(self.h(lw, f4), base, f"def {other[0]} is outside the observer's closure")

    def test_an_observer_covers_the_library_builtins_it_reaches(self):
        lib_names = {k for d in self.lib for k in d.get("builtins", {})}
        name = next((n for n in sorted(self.facts["observers"]) if self.facts["observers"][n]["type"] in ("Nat", "Bool")
                     and any(k.startswith("lib:") for k in self.R.refs(self.obs_law(n), self.facts, lib=self.lib))), None)
        self.assertIsNotNone(name, "no observer reaches a library builtin")
        lw = self.obs_law(name)
        reached = sorted(k[4:] for k in self.R.refs(lw, self.facts, lib=self.lib) if k.startswith("lib:"))
        base = self.h(lw)
        lib2 = copy.deepcopy(self.lib)
        for d in lib2:
            if reached[0] in d.get("builtins", {}):
                d["builtins"][reached[0]]["bend"] += " "
        self.assertNotEqual(self.h(lw, lib=lib2), base, f"editing builtin {reached[0]}")
        unreached = sorted(lib_names - set(reached))
        if unreached:
            lib3 = copy.deepcopy(self.lib)
            for d in lib3:
                if unreached[0] in d.get("builtins", {}):
                    d["builtins"][unreached[0]]["bend"] += " "
            self.assertEqual(self.h(lw, lib=lib3), base, f"builtin {unreached[0]} is not reached")

    def test_cost_and_elapsed_cover_facts_disch(self):
        tr = [{"q": "forall", "name": "p", "type": "Trace"}]
        cost = law({"binders": tr, "assume": [], "claim": {"eq": [{"fn": "cost", "args": [{"var": "p"}]}, {"nat": 0}]}})
        el = law({"binders": tr, "assume": [], "claim": {"eq": [{"fn": "elapsed", "args": [{"var": "p"}]}, {"nat": 0}]}})
        c0, e0 = self.h(cost), self.h(el)
        f2 = copy.deepcopy(self.facts)
        k = sorted(f2["disch"]["cost"])[0]
        f2["disch"]["cost"][k] += 100
        self.assertNotEqual(self.h(cost, f2), c0, "a disch.cost edit restales the cost law")
        self.assertEqual(self.h(el, f2), e0, "and leaves the elapsed law")
        f3 = copy.deepcopy(self.facts)
        f3["disch"]["delay"]["input"] = f3["disch"]["delay"]["input"] + "_x"
        self.assertNotEqual(self.h(el, f3), e0, "a disch.delay edit restales the elapsed law")
        self.assertEqual(self.h(cost, f3), c0)

    def test_src_and_doc_text_change_no_hash(self):
        lw = law({"binders": [{"q": "forall", "name": "a", "type": "Act"}], "assume": [],
                  "claim": {"eq": [{"fn": "last_ok", "args": [{"step": {"var": "a"}, "from": {"s0": {}}}]}, {"bool": True}]}})
        base = self.h(lw)
        f2 = copy.deepcopy(self.facts)
        for a in f2["actions"]:
            a["src"] = a.get("src", "") + ":1-999"
            for g in a.get("guards", []):
                if "src" in g:
                    g["src"] += " (shifted)"
        f2["initial"]["doc"] = "edited"
        self.assertEqual(self.h(lw, f2), base, "re-extraction that shifts spans restales nothing")

    def test_step_refs_are_per_action_reached(self):
        acts = sorted(self.facts["actions"], key=lambda a: (len(a["inputs"]), a["name"]))
        a0 = next(a for a in acts if all(t in ("Nat", "Bool", "List<Nat>") for _, t in a["inputs"]))
        other = next(a for a in self.facts["actions"] if a["name"] != a0["name"] and a.get("effects"))
        lit = {"act": a0["name"], "args": {n: literal(t) for n, t in a0["inputs"]}}
        lw = law({"binders": [], "assume": [],
                  "claim": {"eq": [{"fn": "last_ok", "args": [{"step": lit, "from": {"s0": {}}}]}, {"bool": True}]}})
        base = self.h(lw)
        f2 = copy.deepcopy(self.facts)
        f2o = next(a for a in f2["actions"] if a["name"] == other["name"])
        k = sorted(f2o["effects"])[0]
        f2o["effects"][k] = ["?", True, f2o["effects"][k], f2o["effects"][k]]
        self.assertEqual(self.h(lw, f2), base, f"{other['name']} is not reached by a step of the literal {a0['name']}")
        f3 = copy.deepcopy(self.facts)
        f3a = next(a for a in f3["actions"] if a["name"] == a0["name"])
        f3a["guards"] = f3a.get("guards", []) + [{"require": True, "reason": 99}]
        self.assertNotEqual(self.h(lw, f3), base, f"{a0['name']} is reached")
        var = law({"binders": [{"q": "forall", "name": "a", "type": "Act"}], "assume": [],
                   "claim": {"eq": [{"fn": "last_ok", "args": [{"step": {"var": "a"}, "from": {"s0": {}}}]}, {"bool": True}]}})
        self.assertNotEqual(self.h(var, f2), self.h(var), "a step of an Act binder reaches every action")

    def test_synthesized_helpers_map_to_template_ids(self):
        tr = [{"q": "forall", "name": "p", "type": "Trace"}]
        lw = law({"binders": tr, "assume": [],
                  "claim": {"eq": [{"fn": "runs_ok", "args": [{"var": "p"}, {"s0": {}}]}, {"bool": True}]}})
        r = self.R.refs(lw, self.facts, lib=self.lib)
        for helper in ("runs_ok", "step", "s0"):
            with self.subTest(helper=helper):
                t = r["tmpl:" + helper]
                self.assertEqual(set(t), {"template_id", "template_version"})
                self.assertIsInstance(t["template_version"], int)
        self.assertFalse(any(isinstance(v, str) and k == "step" for k, v in r.items()), "no whole-step bundle hash")

    def test_default_library_is_the_facts_library(self):
        lw = self.obs_law(self.observer_calling(lambda c: True))
        self.assertEqual(self.R.law_hash(lw, self.facts), self.h(lw))


if __name__ == "__main__":
    unittest.main()
