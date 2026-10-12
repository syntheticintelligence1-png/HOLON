"""Audit M2/1, the I10 lifecycle findings: F-M2-07, -08, -09, -21, -22, -23, -24.

F-M2-07  every acceptance point requires the PROOF.bend to import exactly its LAWS.bend as Laws
         (holon.mpipeline.law_import_problem): apart from its law file, an import-less proof checks vacuously.
F-M2-08  G2 ties every statement-hash change of a registry, against its committed versions since the log was
         introduced and in the working tree, to an accepted STATEMENT_DIFF entry carrying exactly those statements
         (holon.statement_diff.tie_problems); off git it says the tie was not run.
F-M2-09  `holon bind` changes an existing binding only with an accepted STATEMENT_DIFF entry covering that law;
         G2 checks every binding change logged after I10 (holon.bindings.check_change_log).
F-M2-21  G3's law scan removes comments as Bend does (holon.gate.laws_in_proofs).
F-M2-22  an entry is checked once, against the tree that appended it: committed lines are verified by their
         acceptance record against that commit, never re-proved against later facts.
F-M2-23  the implication obligation unifies binders up to renaming (explicit map, name, position and type).
F-M2-24  an added premise is rejected; `pick` proves a 3-vs-2-conjunct strengthening; a strengthening dropping a
         conjunct that is false on the model is rejected because the implication is false (refutable on the model).
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests_m2._ir03_fx import (TOY, cleanup, commit_all, copy_repo, git_init, holon, holon_module, law03, load_json,
                               write_json, write_milestone)
from tests_m2._m2 import ROOT

SDFIX = ROOT / "tests_m2" / "fixtures" / "statement_diff"
LOG = "laws/STATEMENT_DIFF.jsonl"


def small_step(var: str = "a") -> dict:
    return {"eq": [{"obsv": "small", "of": {"step": {"var": var}, "from": {"s0": {}}}}, {"bool": True}]}


def n_is(k: int, var: str = "a") -> dict:
    return {"eq": [{"fn": "eq_nat", "args": [{"obsv": "n_of", "of": {"step": {"var": var}, "from": {"s0": {}}}},
                                              {"nat": k}]}, {"bool": False}]}


def act_law(lid: str, claim: dict, assume=(), binder="a") -> dict:
    return law03(lid, {"binders": [{"q": "forall", "name": binder, "type": "Act"}], "assume": list(assume),
                       "claim": claim, "scope": {"kind": "unbounded"}}, milestone="T3")


# ====================================================================== F-M2-07
class TestProofMustImportItsLaw(unittest.TestCase):
    def test_law_import_problem(self):
        mp = holon_module("holon.mpipeline")
        tmp = Path(tempfile.mkdtemp(prefix="holon-imp-"))
        try:
            (tmp / "laws" / "x").mkdir(parents=True)
            (tmp / "proofs" / "x").mkdir(parents=True)
            laws, proof = tmp / "laws" / "x" / "LAWS.bend", tmp / "proofs" / "x" / "PROOF.bend"
            laws.write_text("import Base\n\nlaw l_x:\n  {1n == 1n : Nat}\n")
            proof.write_text("import Base\n\ndef helper() -> Nat:\n  0n\n")
            self.assertIn("does not import its law", mp.law_import_problem(proof, laws))
            proof.write_text("import Base\nimport ../../laws/y/LAWS.bend as Laws\n\ndef Laws.l_x():\n  {==}\n")
            self.assertIn("does not import its law", mp.law_import_problem(proof, laws))
            proof.write_text("import Base\n# import ../../laws/x/LAWS.bend as Laws\n")
            self.assertIn("does not import its law", mp.law_import_problem(proof, laws))
            proof.write_text("import Base\nimport ../../laws/x/LAWS.bend as Laws\n\ndef Laws.l_x():\n  {==}\n")
            self.assertIsNone(mp.law_import_problem(proof, laws))
            side = tmp / "laws" / "x" / "PROOF.bend"
            side.write_text("import Base\nimport ./LAWS.bend as Laws\n")
            self.assertIsNone(mp.law_import_problem(side, laws), "the colocated M0/M1 form")
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_an_import_less_proof_never_proves_an_implication(self):
        """The audit's reproduction: a generator returning a proof without the Laws import made a strengthening
        accepted. With every generator replaced by it, the honest entry must now be rejected."""
        SD = holon_module("holon.statement_diff")
        mproofs = holon_module("holon.gen.mproofs")
        implication = holon_module("holon.gen.implication")
        bad = lambda *a, **k: "import Base\n\ndef helper() -> Nat:\n  0n\n"  # noqa: E731
        with mock.patch.object(mproofs, "GENERATORS", [("vacuous", bad)]), mock.patch.object(implication, "pick", bad):
            r = SD.check_entry(load_json(SDFIX / "strengthening_checked.json"), ROOT)
        self.assertFalse(r["ok"], r)
        self.assertTrue(any("does not import its law" in str(a.get("error", "")) for a in r["implication"]["attempts"]),
                        r["implication"]["attempts"])
        self.assertTrue(SD.check_entry(load_json(SDFIX / "strengthening_checked.json"), ROOT)["ok"])


# ====================================================================== F-M2-21
class TestLawScan(unittest.TestCase):
    def scan(self, text: str) -> list:
        G = holon_module("holon.gate")
        tmp = Path(tempfile.mkdtemp(prefix="holon-g3-"))
        try:
            (tmp / "proofs" / "L_x").mkdir(parents=True)
            (tmp / "proofs" / "L_x" / "PROOF.bend").write_text(text)
            return G.laws_in_proofs(tmp)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_comment_between_the_name_and_the_colon_does_not_hide_a_law(self):
        """The audit's probe; bend/notes/p_ir03_import_depth/proofs/law_in_proof shows Bend parses it as a law."""
        self.assertTrue(self.scan("import Base\n\nlaw sneaky # c\n:\n  {1n == 1n : Nat}\n\ndef sneaky():\n  {==}\n"))
        self.assertTrue(self.scan("import Base\n  law  sneaky   :  {1n == 1n : Nat}\n"))

    def test_comments_and_strings_are_not_declarations(self):
        self.assertFalse(self.scan("import Base\n# law fake: {1n == 1n : Nat}\ndef f() -> Nat:\n  0n\n"))
        self.assertFalse(self.scan('import Base\ndef f() -> String:\n  "x" # law y: z\n'))


# ====================================================================== F-M2-23
class TestBinderUnification(unittest.TestCase):
    def test_an_alpha_renamed_cross_milestone_link_is_discharged(self):
        SD = holon_module("holon.statement_diff")
        I = holon_module("holon.gen.implication")
        f = load_json(SDFIX / "cross_with_implication.json")
        new = I.rename_binders(f["laws"]["L10_xm_new2"], {"a": "b2"})
        self.assertEqual(new["statement"]["binders"][0]["name"], "b2")
        f["laws"]["L10_xm_new2"] = new
        f["entries"][0]["new"] = new
        self.assertEqual(SD.check_cross_milestone(f["derivation"], f["laws"], f["entries"], ROOT), [])

    def test_explicit_positional_and_rejected_binder_maps(self):
        I = holon_module("holon.gen.implication")
        mlaws = holon_module("holon.gen.mlaws")
        old = act_law("L_o", small_step("a"))
        old["statement"]["binders"].append({"q": "forall", "name": "n", "type": "Nat"})
        new = act_law("L_n", small_step("x"), binder="x")
        self.assertEqual(I.unify_binders(old, new), {"x": "a"}, "by position and type")
        self.assertEqual(I.unify_binders(old, new, {"x": "a"}), {"x": "a"})
        with self.assertRaises(mlaws.Unsupported):
            I.unify_binders(old, new, {"x": "n"})   # wrong type
        nat_first = act_law("L_n2", small_step("x"), binder="x")
        nat_first["statement"]["binders"] = [{"q": "forall", "name": "k", "type": "Nat"}]
        with self.assertRaises(mlaws.Unsupported):
            I.unify_binders(old, nat_first)   # neither by name nor by position


# ====================================================================== F-M2-24
class TestImplicationSoundness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.SD = holon_module("holon.statement_diff")
        cls.sha = __import__("hashlib").sha256((ROOT / TOY).read_bytes()).hexdigest()

    def entry(self, old: dict, new: dict) -> dict:
        old, new = copy.deepcopy(old), copy.deepcopy(new)
        for x in (old, new):
            x["law_id"], x["facts_sha256"] = "L10_sd", self.sha
        return {"kind": "strengthening", "law_id": "L10_sd", "old": old, "new": new, "reason": "test"}

    def test_an_added_premise_is_rejected(self):
        """Fails if implication.premises_included is bypassed (the audit's mutation): S' with an extra premise is
        a weakening, whatever the prover can show."""
        old = act_law("L10_sd", small_step())
        new = act_law("L10_sd", small_step(), assume=[{"eq": [{"obsv": "n_of", "of": {"step": {"var": "a"},
                                                                                       "from": {"s0": {}}}},
                                                                {"nat": 7}]}])
        r = self.SD.check_entry(self.entry(old, new), ROOT)
        self.assertFalse(r["ok"], r)
        self.assertIn("premises", r["reason"])

    def test_pick_proves_a_three_versus_two_conjunct_strengthening(self):
        tr = [{"q": "forall", "name": "p", "type": "Trace"}]
        c1 = {"eq": [{"obsv": "small", "of": {"run": {"var": "p"}, "from": {"s0": {}}}}, {"bool": True}]}
        c2 = {"eq": [{"fn": "runs_ok", "args": [{"var": "p"}, {"s0": {}}]}, {"bool": True}]}
        c3 = {"eq": [{"fn": "last_ok", "args": [{"run": {"var": "p"}, "from": {"s0": {}}}]}, {"bool": True}]}
        old = law03("L10_sd", {"binders": tr, "assume": [], "claim": {"all": [c1, c2]}})
        new = law03("L10_sd", {"binders": tr, "assume": [], "claim": {"all": [c3, c2, c1]}})
        r = self.SD.check_entry(self.entry(old, new), ROOT)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["implication"]["generator"], "pick", r["implication"]["attempts"])

    def test_dropping_a_conjunct_false_on_the_model_is_rejected_and_the_obligation_is_refutable(self):
        e = load_json(SDFIX / "strengthening_false_semantic.json")
        for x in (e["old"], e["new"]):
            x["facts_sha256"] = self.sha
        r = self.SD.check_entry(e, ROOT)
        self.assertFalse(r["ok"], r)
        I = holon_module("holon.gen.implication")
        mp = holon_module("holon.mpipeline")
        cm = mp.CompiledMachine.build(ROOT / TOY)
        s = cm.explore(I.obligation_ir(e["old"], e["new"]))
        self.assertIsNotNone(s["witness"], "S' => S is false on the model, not merely unproved")


# ====================================================================== F-M2-08, F-M2-22, F-M2-09 (git copies)
class TestLifecycleInHistory(unittest.TestCase):
    """A copy of the tree with its own git history: T3 holds L10_sd (a law over the toy queue), registered and run;
    the seed commit introduces laws/STATEMENT_DIFF.jsonl (empty), so it is the I10 cutoff of this history."""

    def setUp(self):
        self.SD = holon_module("holon.statement_diff")
        self.repo = copy_repo()
        self.law = write_milestone(self.repo, "T3", [act_law("L10_sd", small_step())])["L10_sd"]
        p = holon(self.repo, "run", "--milestone", "T3")
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        p = holon(self.repo, "bind", "--milestone", "T3")
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        git_init(self.repo)

    def tearDown(self):
        cleanup(self.repo)

    def change_law(self, new: dict) -> None:
        R = holon_module("holon.gen.refs")
        write_json(self.repo / "laws" / "T3" / "L10_sd.json", new)
        reg = load_json(self.repo / "laws" / "T3" / "REGISTRY.json")
        reg["statements"]["L10_sd"] = R.law_hash(new, load_json(self.repo / TOY), root=self.repo)
        write_json(self.repo / "laws" / "T3" / "REGISTRY.json", reg)

    def tie(self) -> list:
        return self.SD.tie_problems("T3", self.repo, self.SD.scan(self.repo / LOG, self.repo))[0]

    def test_a_weakened_law_with_an_updated_registry_fails_the_tie(self):
        weak = copy.deepcopy(self.law)
        weak["statement"]["assume"] = [{"eq": [{"obsv": "n_of", "of": {"step": {"var": "a"}, "from": {"s0": {}}}},
                                               {"nat": 7}]}]
        self.change_law(weak)
        self.assertTrue(any("L10_sd" in p for p in self.tie()), "uncommitted change")
        commit_all(self.repo, "weaken L10_sd")
        self.assertTrue(any("L10_sd" in p for p in self.tie()), "committed change, gated afterwards")
        self.assertTrue(self.SD.registry_changes("T3", self.repo)["git"])

    def test_an_accepted_strengthening_covers_its_change_and_stays_accepted_after_a_facts_edit(self):
        strong = copy.deepcopy(self.law)
        strong["statement"]["claim"] = {"all": [n_is(5), small_step()]}
        r = self.SD.append({"kind": "strengthening", "law_id": "L10_sd", "old": self.law, "new": strong,
                            "reason": "test: adds a conjunct"}, self.repo)
        self.assertTrue(r["ok"], r)
        line = json.loads((self.repo / LOG).read_text().splitlines()[0])
        self.assertTrue(line["accepted"]["implication"]["proof_sha256"])
        self.change_law(strong)
        self.assertEqual(self.tie(), [])
        commit_all(self.repo, "strengthen L10_sd")
        self.assertEqual(self.tie(), [])
        facts = load_json(self.repo / TOY)
        facts["abstractions"] = facts["abstractions"] + ["a doc-only edit after the entry was accepted"]
        write_json(self.repo / TOY, facts)
        commit_all(self.repo, "doc-only facts edit")
        s = self.SD.scan(self.repo / LOG, self.repo)
        self.assertEqual(s["problems"], [], "a committed entry is not re-proved against later facts")
        self.assertTrue(s["entries"][0]["committed"] and s["entries"][0]["ok"])

    def test_a_committed_line_with_a_forged_acceptance_record_fails(self):
        strong = copy.deepcopy(self.law)
        strong["statement"]["claim"] = {"all": [n_is(5), small_step()]}
        forged = {"kind": "strengthening", "law_id": "L10_sd", "old": self.law, "new": strong, "reason": "forged",
                  "accepted": {"kind": "strengthening", "facts": {TOY: "0" * 64},
                               "implication": {"law_id": "x", "generator": "x", "kernels": [], "laws_sha256": "0" * 64,
                                               "proof_sha256": "0" * 64}}}
        (self.repo / LOG).write_text(json.dumps(forged, sort_keys=True) + "\n")
        commit_all(self.repo, "forged line")
        s = self.SD.scan(self.repo / LOG, self.repo)
        self.assertTrue(any("acceptance names" in p for p in s["problems"]), s["problems"])

    def test_a_new_line_without_an_acceptance_record_fails(self):
        e = load_json(SDFIX / "strengthening_checked.json")
        (self.repo / LOG).write_text(json.dumps(e, sort_keys=True) + "\n")
        s = self.SD.scan(self.repo / LOG, self.repo)
        self.assertTrue(any("acceptance record" in p or "facts" in p for p in s["problems"]), s["problems"])

    def test_bind_refuses_to_change_a_binding_without_a_binding_change_entry(self):
        bp = self.repo / "spec" / "bindings" / "T3.json"
        b = load_json(bp)
        cone = b["laws"]["L10_sd"]["cone"]
        d = sorted(cone)[0]
        cone[d] = "0" * 64   # the committed binding no longer matches the kernel form derived from the model
        write_json(bp, b)
        p = holon(self.repo, "bind", "--milestone", "T3", "--accept-change", "a free-text reason")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("binding_change", p.stderr)
        self.assertEqual(load_json(bp)["laws"]["L10_sd"]["cone"][d], "0" * 64, "nothing rebound")

    def test_a_post_i10_change_line_without_an_entry_fails_g2(self):
        B = holon_module("holon.bindings")
        self.assertEqual(B.check_change_log("T3", self.repo)[0], [])
        with (self.repo / "spec" / "bindings" / "changes.jsonl").open("a") as fh:
            fh.write(json.dumps({"milestone": "T3", "laws": ["L10_sd"], "defs": ["x"], "reason": "free text"}) + "\n")
        bad, _ = B.check_change_log("T3", self.repo)
        self.assertTrue(any("L10_sd" in x for x in bad), bad)


class TestOffGitAndCommittedTree(unittest.TestCase):
    def test_off_git_the_tie_reports_not_run(self):
        SD = holon_module("holon.statement_diff")
        repo = copy_repo()
        try:
            bad, note = SD.tie_problems("M1", repo, SD.scan(repo / LOG, repo))
            self.assertEqual(bad, [])
            self.assertIn("not run", note)
        finally:
            cleanup(repo)

    def test_the_committed_m0_m1_history_needs_no_entry(self):
        """M0/M1 registries last changed before the log existed; their two I2-era binding lines are grandfathered."""
        SD = holon_module("holon.statement_diff")
        B = holon_module("holon.bindings")
        s = SD.scan(ROOT / LOG, ROOT)
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                self.assertEqual(SD.tie_problems(m, ROOT, s)[0], [])
                self.assertEqual(B.check_change_log(m, ROOT)[0], [])


if __name__ == "__main__":
    unittest.main()
