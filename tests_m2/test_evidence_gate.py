"""I14: GEVID, evidence_triage in the v2 records, overrides and the registry (the contract is the docstring of
tests_m2/test_evidence.py). Predictions I14-P9..P13 read GEVID on the committed tree through
holon.diagram.evidence.gevid; the gate tests run `holon gate --checks GEVID` on a copy; the failure and override
tests run gevid in-process on a light copy (tests_m2/_evidence.py::light_copy), never on the working tree.
"""
import json
import shutil
import unittest

from tests_m2._evidence import (ASSIGNMENT, OUT, OVERRIDES, RECORD_SCHEMA, ROLLUP, facts, gevid, light_copy, run_gate,
                                write_json)
from tests_m2._m2 import ROOT, copy_repo, holon_module, laws, load_json, records, validate

M0_COMPUTED = {"L_dom_hdr": [], "L_par_hdr_ssvh": ["E1", "E6"], "L_par_hdr_v0": ["E1", "E6"],
               "L_par_hdr_v1": ["E1", "E6"], "L_par_hdr_v2": ["E6"], "L_rt_go_v0": ["E1", "E2"],
               "L_rt_go_v1": ["E1", "E2"], "L_rt_go_v2": ["E1", "E2"]}
# v1 triage of every M0/M1 record before I14 (frozen tests pin it to the predictions; regression I14-R2)
V1_TRIAGE = {"L_dom_hdr": "finding", "L_par_hdr_ssvh": "intent_question", "L_par_hdr_v0": "none",
             "L_par_hdr_v1": "none", "L_par_hdr_v2": "finding", "L_rt_go_v0": "none", "L_rt_go_v1": "none",
             "L_rt_go_v2": "none", "L_disch_delay_nofree": "none", "L_disch_delay_pay": "none",
             "L_disch_delay_prove": "none", "L_disch_delay_wait": "none", "L_disch_stale": "none",
             "L_disch_stale_commit": "none", "L_fact_Z": "finding", "L_nat_eta2": "finding",
             "L_own_txspayload": "finding", "L_sort_remaining": "finding", "L_sym_omega": "finding",
             "L_tag_BVH": "finding", "L_undo_BD": "none", "L_undo_BVH": "finding", "L_undo_CSR": "none",
             "L_undo_cancel": "finding"}
EVIDENCE_FIELDS = ("evidence_levels", "evidence_triage", "evidence_override")


class _Reports(unittest.TestCase):
    g: dict = None

    @classmethod
    def setUpClass(cls):
        if _Reports.g is None:
            _Reports.g = {m: gevid(m) for m in ("M0", "M1")}


# ---------------------------------------------------------------- predictions on the committed tree
class TestGevidPredictions(_Reports):
    def test_gevid_verdicts_on_the_e5_claims(self):
        """I14-P9: GEVID's verdict on the E5 claims, against I13's frozen assignment: L_sort_remaining's computed
        evidence includes E5 (its statement names reason 16, so the three commits; their :363 guard compares t with
        W + cstart, both Time); L_tag_BVH's does not (its statement names only the observer tags_ok, whose body
        tags_exact(win) holds no comparison, and the bvh registers carry the union Dig[Agg] + Dig[VH], which is no
        identical refined sort), so GEVID lists E5 as missing for L_tag_BVH only."""
        L = self.g["M1"]["laws"]
        self.assertIn("E5", L["L_sort_remaining"]["computed"])
        self.assertNotIn("E5", L["L_sort_remaining"]["missing"])
        self.assertNotIn("E5", L["L_tag_BVH"]["computed"])
        self.assertIn("E5", L["L_tag_BVH"]["missing"])
        E = holon_module("holon.diagram.evidence")
        doc = load_json(OUT)
        m1 = laws("M1")
        self.assertEqual(E.law_evidence(m1["L_sort_remaining"], doc)["named"],
                         ["TRANS.commitBatch", "TRANS.commitBatchWithProof", "TRANS.commitState"])
        self.assertEqual(E.law_evidence(m1["L_tag_BVH"], doc)["named"], ["LOAD.obs.tags_ok"])

    def test_m0_report_shape(self):
        """I14-P10: GEVID on M0 is report-only and passes; exactly two laws carry metadata evidence that is not
        computed, L_dom_hdr (E2: its predicates name only dec_go, and no atom relates dec_go to itself) and
        L_par_hdr_v2 (E1: the encoders' common-decoder atom is at version 1, the law fixes version 2); the computed
        levels per law are exactly M0_COMPUTED."""
        g = self.g["M0"]
        self.assertEqual((g["mode"], g["passed"], g["problems"]), ("report-only", True, []), g.get("problems"))
        self.assertIn("report-only", g["detail"])
        self.assertEqual(g["mismatches"], [{"law": "L_dom_hdr", "missing": ["E2"]},
                                           {"law": "L_par_hdr_v2", "missing": ["E1"]}])
        self.assertEqual({k: v["computed"] for k, v in g["laws"].items()}, M0_COMPUTED)
        self.assertEqual(g["uncovered"], [])

    def test_m1_report_shape(self):
        """I14-P11: GEVID on M1 is report-only and passes; exactly two laws carry metadata evidence that is not
        computed: L_nat_eta2 (E2: every write-then-read through eta2, legacy or csr_last passes win through a
        builtin with no access kind, so it is unresolved) and L_tag_BVH (E2 for the same reason through tags_exact,
        and E5); L_fact_Z's E4 is computed (commitBatchWithProof recomputes blob_hash, which commitBatch stores);
        every other M1 law's metadata evidence is computed."""
        g = self.g["M1"]
        self.assertEqual((g["mode"], g["passed"], g["problems"]), ("report-only", True, []), g.get("problems"))
        self.assertEqual(g["mismatches"], [{"law": "L_nat_eta2", "missing": ["E2"]},
                                           {"law": "L_tag_BVH", "missing": ["E2", "E5"]}])
        self.assertIn("E4", g["laws"]["L_fact_Z"]["computed"])
        for lid, row in g["laws"].items():
            if lid not in ("L_nat_eta2", "L_tag_BVH"):
                with self.subTest(law=lid):
                    self.assertEqual(row["missing"], [])
        self.assertEqual(g["uncovered"], [])

    def test_ssvh_evidence_triage_is_finding_and_a_divergence(self):
        """I14-P12: L_par_hdr_ssvh's evidence_triage is finding (E1 at version 1 is its strongest level), against its
        v1 triage intent_question, and GEVID lists it as a divergence; its record says the same."""
        row = self.g["M0"]["laws"]["L_par_hdr_ssvh"]
        self.assertEqual((row["evidence_triage"], row["v1_triage"], row["effective"], row["max"]),
                         ("finding", "intent_question", "finding", "E1"))
        self.assertIn("L_par_hdr_ssvh", [d["law"] for d in self.g["M0"]["divergences"]])
        rec = records("M0")["L_par_hdr_ssvh"]
        self.assertEqual((rec["evidence_triage"], rec["triage"]), ("finding", "intent_question"))

    def test_the_divergence_list(self):
        """I14-P13: across M0 and M1 exactly two laws' evidence_triage differs from their v1 triage: L_par_hdr_ssvh
        (finding vs intent_question) and L_par_hdr_v2 (intent_question vs finding: at version 2 only E6 relates
        enc_sol and enc_go_v1); M1 has none."""
        self.assertEqual(self.g["M0"]["divergences"], [
            {"law": "L_par_hdr_ssvh", "v1_triage": "intent_question", "evidence_triage": "finding",
             "effective": "finding"},
            {"law": "L_par_hdr_v2", "v1_triage": "finding", "evidence_triage": "intent_question",
             "effective": "intent_question"}])
        self.assertEqual(self.g["M1"]["divergences"], [])
        self.assertEqual(records("M0")["L_par_hdr_v2"]["evidence_triage"], "intent_question")


# ---------------------------------------------------------------- records (construction, regression)
class TestRecords(unittest.TestCase):
    def test_records_carry_the_recomputed_evidence_fields(self):
        E = holon_module("holon.diagram.evidence")
        doc = load_json(OUT)
        for m in ("M0", "M1"):
            ls = laws(m)
            for lid, rec in records(m).items():
                with self.subTest(milestone=m, law=lid):
                    for k in EVIDENCE_FIELDS:
                        self.assertIn(k, rec)
                    le = E.law_evidence(ls[lid], doc)
                    self.assertTrue(le["covered"])
                    self.assertEqual(rec["evidence_levels"], le["levels"])
                    self.assertEqual(rec["evidence_triage"], E.evidence_triage(rec["status"], le["max"]))
                    self.assertIsNone(rec["evidence_override"], "I14 commits no override")

    def test_the_v2_schema_requires_the_fields(self):
        sch = load_json(RECORD_SCHEMA)
        for k in EVIDENCE_FIELDS:
            self.assertIn(k, sch["required"])
        rec = dict(records("M0")["L_par_hdr_ssvh"])
        self.assertEqual(validate(rec, RECORD_SCHEMA), [])
        for k, bad in (("evidence_triage", "maybe"), ("evidence_levels", ["E7"]),
                       ("evidence_override", {"evidence_triage": "finding"})):
            with self.subTest(field=k):
                self.assertNotEqual(validate(dict(rec, **{k: bad}), RECORD_SCHEMA), [])

    def test_v1_triage_is_unchanged(self):
        """I14-R2 (regression): the v1 triage of all 24 M0/M1 records is what it was before I14."""
        got = {lid: r["triage"] for m in ("M0", "M1") for lid, r in records(m).items()}
        self.assertEqual(got, V1_TRIAGE)

    def test_no_override_is_committed(self):
        p = ROOT / OVERRIDES
        if p.exists():
            self.assertEqual({m: v for m, v in load_json(p).items() if v}, {}, "I14 commits no override")


# ---------------------------------------------------------------- the gate (construction)
class TestGateWiring(_Reports):
    def test_gevid_follows_gref_in_the_check_order(self):
        order = holon_module("holon.gate").CHECK_ORDER
        self.assertIn("GEVID", order)
        self.assertEqual(order.index("GEVID"), order.index("GREF") + 1)

    def test_the_gate_runs_gevid_report_only_on_m0_and_m1(self):
        repo = copy_repo()
        try:
            for m in ("M0", "M1"):
                with self.subTest(milestone=m):
                    p, rep = run_gate(repo, m)
                    self.assertIsNotNone(rep, p.stderr[-2000:])
                    c = rep["checks"]["GEVID"]
                    self.assertTrue(c["passed"], c.get("detail"))
                    self.assertEqual(c["mode"], "report-only")
                    for k in ("mismatches", "divergences", "laws", "evidence_sha256"):
                        self.assertEqual(c[k], self.g[m][k], k)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestGevidFailures(unittest.TestCase):
    def setUp(self):
        self.repo = light_copy()

    def tearDown(self):
        shutil.rmtree(self.repo.parent, ignore_errors=True)

    def problems(self, m: str) -> list[str]:
        g = gevid(m, self.repo)
        self.assertFalse(g["passed"])
        self.assertTrue(g["problems"])
        return g["problems"]

    def test_a_tampered_evidence_file_fails(self):
        p = self.repo / "gen" / "M2" / "evidence.json"
        d = load_json(p)
        d["atoms"] = d["atoms"][1:]
        write_json(p, d)
        self.problems("M0")

    def test_a_drifted_input_fails(self):
        p = self.repo / "spec" / "M2" / "lib" / "evidence_lexical.json"
        lex = load_json(p)
        lex["stopwords"] = lex["stopwords"] + ["batch"]
        write_json(p, lex)
        self.problems("M0")

    def test_a_stale_record_field_fails_naming_the_law(self):
        p = self.repo / "results" / "M0" / "L_dom_hdr.json"
        rec = load_json(p)
        rec["evidence_triage"] = "intent_question"
        write_json(p, rec)
        self.assertTrue(any("L_dom_hdr" in x for x in self.problems("M0")))

    def plant_override(self, m: str, lid: str, entry: dict) -> None:
        write_json(self.repo / OVERRIDES, {m: {lid: entry}})
        p = self.repo / "results" / m / f"{lid}.json"
        rec = load_json(p)
        rec["evidence_override"] = entry
        write_json(p, rec)

    def test_a_malformed_override_fails(self):
        self.plant_override("M0", "L_par_hdr_ssvh", {"evidence_triage": "intent_question", "why": ""})
        self.assertTrue(any("L_par_hdr_ssvh" in x for x in self.problems("M0")))

    def test_an_override_on_a_law_that_is_not_refuted_fails(self):
        self.plant_override("M0", "L_par_hdr_v0", {"evidence_triage": "finding", "why": "planted by the I14 test"})
        self.assertTrue(any("L_par_hdr_v0" in x for x in self.problems("M0")))

    def test_an_override_naming_no_law_fails(self):
        write_json(self.repo / OVERRIDES, {"M0": {"L_no_such_law": {"evidence_triage": "finding", "why": "planted"}}})
        self.assertTrue(any("L_no_such_law" in x for x in self.problems("M0")))

    def plant_m2(self, evidence: list, registry_sha: str | None) -> None:
        """laws/M2 holding one probe law: an M1 rollup statement (covered by the set) with the given metadata
        evidence. E1 is never computed on the rollup model (it has no CODEC edge), whatever I14-P11's outcome."""
        shutil.rmtree(self.repo / "laws" / "M2", ignore_errors=True)
        law = dict(laws("M1")["L_undo_BVH"], law_id="L_probe_gevid", milestone="M2", evidence=evidence)
        write_json(self.repo / "laws" / "M2" / "L_probe_gevid.json", law)
        write_json(self.repo / "laws" / "M2" / "REGISTRY.json", {"evidence_sha256": registry_sha})

    def test_enforcing_from_m2_fails_on_a_metadata_mismatch(self):
        sha = load_json(OUT)["evidence_sha256"]
        self.plant_m2(["E1"], sha)
        g = gevid("M2", self.repo)
        self.assertEqual(g["mode"], "enforcing")
        self.assertIn("enforcing", g["detail"])
        self.assertEqual(g["problems"], [])
        self.assertEqual(g["mismatches"], [{"law": "L_probe_gevid", "missing": ["E1"]}])
        self.assertFalse(g["passed"])
        self.plant_m2([], sha)
        g = gevid("M2", self.repo)
        self.assertEqual((g["passed"], g["mismatches"], g["problems"]), (True, [], []))

    def test_an_ir_0_3_site_law_without_metadata_passes_enforcing(self):
        """Merge contract with I15: a generated SORT-site law (holon-ir/0.3, binders Reach and Act, the site term, no
        "evidence" key) is read by GEVID from M2 on: its metadata is the empty set, L2 names the site's actions through
        anchors.sites, L3 adds every TRANS edge as context, and enforcing mode passes on it."""
        doc = load_json(OUT)
        acts = {a["name"] for a in facts(ROLLUP)["actions"]}
        site = next(s for s in sorted(load_json(ASSIGNMENT)["sites"], key=lambda s: s["id"])
                    if s["model"] == ROLLUP and all(o["action"] in acts for o in s["occurrences"]))
        mo = doc["models"][ROLLUP]
        law = {"ir_version": "holon-ir/0.3", "law_id": "L_probe_site", "milestone": "M2", "rule": "SORT",
               "subform": "site", "rule_catalog_version": "holon-rules/1.0", "facts": mo["facts"],
               "facts_sha256": mo["facts_sha256"], "notes": "planted by the I14 test",
               "statement": {"binders": [{"q": "forall", "name": "s", "type": "Reach"},
                                         {"q": "forall", "name": "a", "type": "Act"}],
                             "assume": [],
                             "claim": {"eq": [{"site": site["id"], "on": {"var": "a"}, "from": {"var": "s"}},
                                              {"bool": True}]},
                             "scope": {"kind": "unbounded"}}}
        shutil.rmtree(self.repo / "laws" / "M2", ignore_errors=True)
        write_json(self.repo / "laws" / "M2" / "L_probe_site.json", law)
        write_json(self.repo / "laws" / "M2" / "REGISTRY.json", {"evidence_sha256": doc["evidence_sha256"]})
        g = gevid("M2", self.repo)
        self.assertEqual((g["mode"], g["problems"], g["mismatches"]), ("enforcing", [], []))
        self.assertTrue(g["passed"])
        self.assertEqual(g["laws"]["L_probe_site"]["metadata"], [])
        le = holon_module("holon.diagram.evidence").law_evidence(law, doc)
        want = sorted({f"TRANS.{o['action']}" for o in site["occurrences"]})
        self.assertEqual((le["covered"], le["named"], le["context"]), (True, want, mo["anchors"]["trans"]))

    def test_from_m2_the_registry_must_carry_the_evidence_sha(self):
        self.plant_m2([], "0" * 64)
        self.assertTrue(any("evidence_sha256" in x for x in self.problems("M2")))


class TestOverrides(unittest.TestCase):
    def test_a_valid_override_is_listed_and_moves_the_divergence(self):
        repo = light_copy()
        try:
            entry = {"evidence_triage": "intent_question", "why": "planted by the I14 test"}
            write_json(repo / OVERRIDES, {"M0": {"L_par_hdr_ssvh": entry}})
            p = repo / "results" / "M0" / "L_par_hdr_ssvh.json"
            write_json(p, dict(load_json(p), evidence_override=entry))
            g = gevid("M0", repo)
            self.assertEqual((g["passed"], g["problems"]), (True, []))
            self.assertEqual(g["overrides"], [{"law": "L_par_hdr_ssvh", **entry}])
            row = g["laws"]["L_par_hdr_ssvh"]
            self.assertEqual((row["evidence_triage"], row["override"], row["effective"]),
                             ("finding", entry, "intent_question"))
            self.assertEqual([d["law"] for d in g["divergences"]], ["L_par_hdr_v2"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


# ---------------------------------------------------------------- the registry (cross-iteration with I15)
class TestRegistry(unittest.TestCase):
    def test_the_m2_registry_carries_the_evidence_sha_whenever_it_exists(self):
        doc = load_json(OUT)
        self.assertRegex(doc["evidence_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(doc["models"][ROLLUP]["facts"], "spec/M1/facts/morph_rollup.json")
        reg = ROOT / "laws" / "M2" / "REGISTRY.json"
        if reg.exists():  # created by I15 (holon derive); until then the identity lives in gen/M2/evidence.json
            self.assertEqual(load_json(reg).get("evidence_sha256"), doc["evidence_sha256"])
            g = gevid("M2")
            self.assertTrue(g["passed"], json.dumps({k: g[k] for k in ("problems", "mismatches")}))

    def test_m2_site_laws_name_their_actions_whenever_they_exist(self):
        """Whenever laws/M2 holds I15's SORT-site laws (after the merge), each names exactly the actions of its site's
        occurrences (anchors.sites), so its record's evidence comes from the frozen set, never from a hand-typed list."""
        E = holon_module("holon.diagram.evidence")
        doc = load_json(OUT)
        if not (ROOT / "laws" / "M2" / "REGISTRY.json").exists():  # created by I15 (holon derive)
            return
        sites = {s["id"]: s for s in load_json(ASSIGNMENT)["sites"]}
        for lid, law in laws("M2").items():
            claim = law["statement"]["claim"]
            term = claim.get("eq", [{}])[0] if isinstance(claim, dict) else {}
            if not (isinstance(term, dict) and "site" in term):
                continue
            with self.subTest(law=lid):
                self.assertNotIn("evidence", law, "a generated law carries no hand-typed evidence")
                le = E.law_evidence(law, doc)
                acts = {a["name"] for a in facts(ROLLUP)["actions"]}
                want = sorted({f"TRANS.{o['action']}" for o in sites[term["site"]]["occurrences"] if o["action"] in acts})
                self.assertEqual(le["named"], want)


if __name__ == "__main__":
    unittest.main()
