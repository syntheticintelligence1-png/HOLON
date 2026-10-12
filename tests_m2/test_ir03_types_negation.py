"""Audit M2/1 F-M2-18 (0.3 binder types) and F-M2-19 (the negation of an ∃-law as its own law).

F-M2-18: the 0.3 schema takes record refs (a record type of the law's facts, checked against them by
holon.ir.check_binder_types) and List<Nat>, besides Nat, Bool, State, Trace, Act, Reach, Fn<A,B> and Bytes(n);
the emitter maps a record ref to the model's record type and rejects Bytes(n) as Unsupported (no model type yet).
Before the fix the schema rejected Entry, Hdr, Rec<..> and List<Nat>, and the emitter passed Bytes(n) through.

F-M2-19: holon.ir.negation_law(law) is the generator `holon derive` and the rules engine freeze an ∃-law's
negation subform with: the same binders made universal, the same scope, the claim negated (eq <-> neq), linked
by negation_of; machine-free. The gate (G2, M2+) requires the frozen pair (tests_m2/test_gate_ir03.py).
"""
import copy
import unittest

from tests_m2._m2 import ROOT, holon_module, load_json, validate

SCHEMA = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
FIX = ROOT / "tests_m2" / "fixtures" / "ir03"
M1_FACTS = ROOT / "spec" / "M1" / "facts" / "morph_rollup.json"


def with_binder(ty: str) -> dict:
    law = load_json(FIX / "L3_cf.json")
    law["statement"]["binders"].append({"q": "forall", "name": "x", "type": ty})
    return law


class TestBinderTypes(unittest.TestCase):
    def test_schema_takes_record_refs_and_list_nat(self):
        for ty in ("Entry", "Hdr", "List<Nat>", "Bytes(32)", "Fn<Nat,Nat>", "Nat", "Reach"):
            with self.subTest(type=ty):
                self.assertEqual(validate(with_binder(ty), SCHEMA), [])
        for ty in ("entry", "Rec<Entry>", "List<Entry>", "Bytes(n)", ""):
            with self.subTest(type=ty):
                self.assertNotEqual(validate(with_binder(ty), SCHEMA), [])

    def test_record_refs_are_checked_against_the_facts(self):
        ir = holon_module("holon.ir")
        facts = load_json(M1_FACTS)
        rec = sorted(facts["types"])[0]
        ir.check_binder_types(with_binder(rec), facts)
        ir.check_binder_types(with_binder("List<Nat>"), facts)
        with self.assertRaises(ir.IRError):
            ir.check_binder_types(with_binder("NoSuchRecord"), facts)

    def test_the_emitter_maps_record_refs_and_rejects_bytes(self):
        mlaws = holon_module("holon.gen.mlaws")
        Machine = holon_module("holon.gen.machine").Machine
        facts = load_json(M1_FACTS)
        E = mlaws.Emitter(Machine(facts, M1_FACTS))
        rec = sorted(facts["types"])[0]
        self.assertEqual(E.ty(rec), f"M.H{rec}")
        self.assertEqual(E.ty("List<Nat>"), "List<&2, Nat>")
        with self.assertRaises(mlaws.Unsupported):
            E.ty("Bytes(32)")


class TestNegationLaw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir = holon_module("holon.ir")

    def test_negation_of_a_purely_existential_law(self):
        law = load_json(FIX / "L3_exists_false.json")
        neg = self.ir.negation_law(law)
        st = law["statement"]
        self.assertEqual(neg["law_id"], "L3_exists_false_neg")
        self.assertEqual(neg["negation_of"], "L3_exists_false")
        self.assertEqual(neg["statement"], {"binders": [{"q": "forall", "name": "a", "type": "Act"}], "assume": [],
                                            "claim": {"neq": st["claim"]["eq"]}, "scope": {"kind": "unbounded"}})
        for k in ("ir_version", "rule", "rule_catalog_version", "facts", "facts_sha256", "milestone"):
            self.assertEqual(neg[k], law[k], k)
        self.assertEqual(validate(neg, SCHEMA), [])

    def test_negation_keeps_the_scope_and_flips_an_inequation(self):
        law = load_json(FIX / "L3_exists_false.json")
        law["statement"]["claim"] = {"neq": law["statement"]["claim"]["eq"]}
        law["statement"]["scope"] = {"kind": "bounded", "H": 3}
        neg = self.ir.negation_law(law)
        self.assertEqual(neg["statement"]["claim"], {"eq": law["statement"]["claim"]["neq"]})
        self.assertEqual(neg["statement"]["scope"], {"kind": "bounded", "H": 3})

    def test_negations_the_ir_cannot_state_are_refused(self):
        base = load_json(FIX / "L3_exists_false.json")
        conj = copy.deepcopy(base)
        conj["statement"]["claim"] = {"all": [base["statement"]["claim"], base["statement"]["claim"]]}
        mixed = copy.deepcopy(base)
        mixed["statement"]["binders"].append({"q": "forall", "name": "n", "type": "Nat"})
        univ = load_json(FIX / "L3_and_true.json")
        for name, law in (("conjunction", conj), ("mixed binders", mixed), ("universal", univ)):
            with self.subTest(case=name):
                with self.assertRaises(self.ir.IRError):
                    self.ir.negation_law(law)

    def test_the_run_time_negation_is_the_generated_one(self):
        """The pipeline's fallback (no frozen negation in the milestone) decides exactly negation_law's statement."""
        R = holon_module("holon.gen.refs")
        law = load_json(FIX / "L3_exists_false.json")
        neg = self.ir.negation_law(law)
        self.assertEqual(self.ir.render_statement(neg), "∀ a: Act. n_of(step(a, s0)) != 5")
        self.assertTrue(R.law_hash(neg, load_json(ROOT / law["facts"])).startswith("sha256:"))


if __name__ == "__main__":
    unittest.main()
