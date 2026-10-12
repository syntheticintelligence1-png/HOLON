"""I4 follow-up: checks added after the adversarial review of I4 (not part of the I4 preregistration).

Each test pins one confirmed review finding: G6 bypasses (unhashed labels, self-reported provenance,
flags that disagree with the logged evidence, M1 entries stripped to M0 shape, malformed sides,
an unpinned Go), the model-only fallback, the evidence rules themselves, and the case-study mapping.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2._i4 import expected_bin
from tests_m2._m2 import ROOT, copy_repo, holon_module, laws, load_json, run_holon, write_json

MORPH = Path(os.environ.get("HOLON_MORPH", "/root/work/morph"))


def g6(repo: Path, m: str) -> dict:
    rp = repo / f"g_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", "G6"], cwd=repo)
    assert rp.exists(), p.stdout[-1000:] + p.stderr[-1000:]
    return load_json(rp)["checks"]["G6"]


class _Tamper(unittest.TestCase):
    def run_g6(self, m: str, edit) -> dict:
        repo = copy_repo()
        try:
            edit(repo)
            return g6(repo, m)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def fails(self, m: str, edit, needle: str) -> None:
        g = self.run_g6(m, edit)
        self.assertFalse(g["passed"], g["detail"])
        self.assertIn(needle, g["detail"])
        self.assertNotIn("could not be checked", g["detail"])


def rebin(repo: Path, m: str, lid: str) -> None:
    """Make the record agree with whatever the (edited) report now says, as a careful tamperer would."""
    rep = load_json(repo / "replay" / m / "report.json")
    e = rep["laws"][lid]
    ss = e["sides"] if m == "M1" else e
    r = repo / "results" / m / f"{lid}.json"
    rec = load_json(r)
    rec["witness_provenance"] = {k: s.get("provenance") for k, s in sorted(ss.items()) if isinstance(s, dict)}
    rec["filter_bin"] = expected_bin({k: s for k, s in ss.items() if isinstance(s, dict)})
    write_json(r, rec)


def edit_report(repo: Path, m: str, fn) -> None:
    f = repo / "replay" / m / "report.json"
    d = load_json(f)
    fn(d)
    write_json(f, d)


class TestG6ReviewBypasses(_Tamper):
    def test_unhashed_subform_cannot_drop_a_consumer_side(self):
        def edit(repo):
            for f in (repo / "laws" / "M1" / "L_tag_BVH.json", repo / "results" / "M1" / "L_tag_BVH.json"):
                d = load_json(f)
                d["subform"] = "undo_pair"
                write_json(f, d)
            edit_report(repo, "M1", lambda d: d["laws"]["L_tag_BVH"]["sides"].pop("go_consumer"))
            rebin(repo, "M1", "L_tag_BVH")
        self.fails("M1", edit, "go_consumer")

    def test_relabelled_provenance_fails_even_when_the_record_matches(self):
        def edit(repo):
            edit_report(repo, "M0", lambda d: d["laws"]["L_dom_hdr"]["solidity"].update(provenance="public_schedule"))
            rebin(repo, "M0", "L_dom_hdr")
        self.fails("M0", edit, "the IR implies 'internal_harness'")

    def test_relabelled_emulated_storage_fails(self):
        def edit(repo):
            edit_report(repo, "M1",
                        lambda d: d["laws"]["L_nat_eta2"]["sides"]["solidity"].update(provenance="public_schedule"))
            rebin(repo, "M1", "L_nat_eta2")
        self.fails("M1", edit, "the IR implies 'emulated_storage'")

    def test_header_contradicting_its_commitment_fails(self):
        def edit(repo):
            def fn(d):
                s = d["laws"]["L_par_hdr_v2"]["solidity"]
                s["header"] = "0x01" + s["header"][4:]
            edit_report(repo, "M0", fn)
        self.fails("M0", edit, "evidence contradicts the model")

    def test_unequal_commitments_are_a_model_defect_not_pending(self):
        def edit(repo):
            def fn(d):
                e = d["laws"]["L_fact_Z"]
                s = e["sides"]["solidity"]
                s["committed_hash"]["c2"] = "0x" + "11" * 32
                s["obstruction_observed"] = False
                e["obstruction_reproduced"] = False
            edit_report(repo, "M1", fn)
            rebin(repo, "M1", "L_fact_Z")
        self.fails("M1", edit, "evidence contradicts the model")

    def test_observed_flag_without_evidence_fails(self):
        def edit(repo):
            def fn(d):
                s = d["laws"]["L_own_txspayload"]["sides"]["go"]
                s["observed"] = s["observed"].replace("changed=true", "changed=false")
            edit_report(repo, "M1", fn)
        self.fails("M1", edit, "evidence does not show it")

    def test_enum_check_fires_on_its_own(self):
        def edit(repo):
            edit_report(repo, "M0", lambda d: d["laws"]["L_dom_hdr"]["go"].update(provenance="public"))
            rebin(repo, "M0", "L_dom_hdr")
        self.fails("M0", edit, "provenance 'public' is not one of")

    def test_bool_check_fires_on_its_own(self):
        def edit(repo):
            edit_report(repo, "M1",
                        lambda d: d["laws"]["L_sort_remaining"]["sides"]["solidity"].update(obstruction_observed="true"))
        self.fails("M1", edit, "obstruction_observed is not a boolean")

    def test_m1_entry_stripped_to_sides_fails(self):
        def edit(repo):
            def fn(d):
                d["laws"]["L_undo_BVH"] = dict(d["laws"]["L_undo_BVH"]["sides"])
            edit_report(repo, "M1", fn)
        self.fails("M1", edit, "has no 'sides' object")

    def test_malformed_side_fails_with_a_reason(self):
        def edit(repo):
            edit_report(repo, "M1", lambda d: d["laws"]["L_tag_BVH"]["sides"].update(go_consumer="passed"))
        self.fails("M1", edit, "go_consumer side is not an object")

    def test_replayed_traces_are_bound_to_the_witness(self):
        def edit(repo):
            def fn(d):
                t = d["laws"]["L_undo_BVH"]["traces"][0]
                t["trace"][0]["post"] = t["trace"][0]["post"] + 1
            edit_report(repo, "M1", fn)
        self.fails("M1", edit, "not the ones the witness linearises to")

    def test_go_pin_mismatch_fails(self):
        def edit(repo):
            edit_report(repo, "M1", lambda d: d["toolchain"].update(go_version="go version go1.10 linux/amd64"))
        self.fails("M1", edit, "go_version")


class TestG6VerificationHoles(_Tamper):
    """Holes found when the I4 review fixes were verified."""

    def test_relabelled_outcome_class_fails(self):
        def edit(repo):
            def fn(d):
                e = d["laws"]["L_fact_Z"]
                c = e["sides"]["go_consumer"]
                c["outcome_class"] = {"c1": "rejected", "c2": "accepted"}
                c["obstruction_observed"] = True
                e["obstruction_reproduced"] = True
            edit_report(repo, "M1", fn)
            rebin(repo, "M1", "L_fact_Z")
        self.fails("M1", edit, "outcome classes are not the classes of the logged outcomes")

    def test_logged_trace_disagreement_fails(self):
        def edit(repo):
            def fn(d):
                t = d["laws"]["L_sym_omega"]["traces"][1]
                t["disagree"] = [{"step": 3, "op": "x", "model": "ok", "real": "rev other"}]
                t["agree"] -= 1
            edit_report(repo, "M1", fn)
        self.fails("M1", edit, "logs a model/real disagreement")

    def test_m0_commit_trace_is_bound_to_the_witness(self):
        def edit(repo):
            def fn(d):
                s = d["laws"]["L_par_hdr_v2"]["solidity"]
                s["trace"] = [{"op": "@legacy_eta2", "root": None}, dict(s["trace"][0], who=99, blobs=[])]
            edit_report(repo, "M0", fn)
        self.fails("M0", edit, "not the commit-path trace")

    def test_facts_path_spelling_cannot_swap_sides(self):
        def edit(repo):
            f = repo / "laws" / "M1" / "L_sym_omega.json"
            law = load_json(f)
            old = law["facts"]
            law["facts"] = "./" + old
            write_json(f, law)
            r = repo / "laws" / "M1" / "REGISTRY.json"
            reg = load_json(r)
            reg["facts_files"][law["facts"]] = reg["facts_files"][old]
            write_json(r, reg)

            def fn(d):
                e = d["laws"]["L_sym_omega"]
                e["sides"] = {"go": {"status": "passed", "observed": "changed=true", "command": "x",
                                     "provenance": "library_api", "obstruction_observed": True}}
            edit_report(repo, "M1", fn)
            rebin(repo, "M1", "L_sym_omega")
        self.fails("M1", edit, "differ from the sides its witness claims")

    def test_missing_refinement_block_fails(self):
        self.fails("M1", lambda repo: edit_report(repo, "M1", lambda d: d.pop("refinement")),
                   "lacks a refinement block")

    def test_null_witness_fails(self):
        def edit(repo):
            r = repo / "results" / "M0" / "L_dom_hdr.json"
            rec = load_json(r)
            rec["witness"] = None
            write_json(r, rec)
            edit_report(repo, "M0", lambda d: d["witness_sha256"].update(L_dom_hdr=None))
        self.fails("M0", edit, "has no witness object")

    def test_tampered_aggregate_fails(self):
        def edit(repo):
            edit_report(repo, "M1", lambda d: d["laws"]["L_tag_BVH"]["sides"]["go_consumer"].update(
                aggregate="0x" + "22" * 32))
        self.fails("M1", edit, "not keccak256 of the stored hash")

    def test_go_reading_contradiction_fails(self):
        def edit(repo):
            edit_report(repo, "M1", lambda d: d["laws"]["L_tag_BVH"]["sides"]["go_consumer"].update(v1_version=2))
        self.fails("M1", edit, "Go reads the committed headers differently")


class TestModelOnlyFallback(_Tamper):
    def test_a_labelled_model_only_consumer_side_passes_with_bin_pending(self):
        def edit(repo):
            def fn(d):
                e = d["laws"]["L_tag_BVH"]
                e["sides"]["go_consumer"] = {"status": "not_applicable", "provenance": "library_api",
                                             "obstruction_observed": False, "command": "",
                                             "observed": "model-only pending replay: test"}
                e["obstruction_reproduced"] = False
            edit_report(repo, "M1", fn)
            rebin(repo, "M1", "L_tag_BVH")
            r = repo / "results" / "M1" / "L_tag_BVH.json"
            rec = load_json(r)
            rec["replay"]["detail"] += "; go_consumer: model-only pending replay: test"
            write_json(r, rec)
            self.assertEqual(rec["filter_bin"], "pending")
        g = self.run_g6("M1", edit)
        self.assertTrue(g["passed"], g["detail"])
        self.assertIn("L_tag_BVH/go_consumer", g["detail"])


class TestEvidenceRules(unittest.TestCase):
    def setUp(self):
        self.E = holon_module("holon.evidence")

    def test_claimed_sides_ignore_subform(self):
        law = dict(laws("M1")["L_tag_BVH"], subform="undo_pair")
        sha = load_json(ROOT / "laws" / "M1" / "REGISTRY.json")["facts_sha256"]
        self.assertEqual(self.E.claimed_sides(law, sha), {"solidity", "go_consumer"})

    def test_two_rejections_are_not_a_derivation_divergence(self):
        ph = "0x" + "00" * 249
        sol = {"parent_header": ph, "parent_index": 0}
        side = {"input_parent_header": ph, "parent_index": 0,
                "outcomes": {"c1": "error: a", "c2": "error: b"},
                "outcome_class": {"c1": "rejected", "c2": "rejected"}}
        self.assertEqual(self.E.fact_consumer(side, sol)[0], self.E.NOT_OBSERVED)
        side["outcome_class"] = {"c1": "rejected", "c2": "accepted"}
        self.assertEqual(self.E.fact_consumer(side, sol)[0], self.E.CONTRADICTION, "classes must match outcomes")
        side.update(outcomes={"c1": "error: a", "c2": "ok"})
        self.assertEqual(self.E.fact_consumer(side, sol)[0], self.E.OBSERVED)

    def test_a_correct_v2_header_is_not_a_ghost_tag(self):
        from tests_m2._keccak import keccak256
        rep = load_json(ROOT / "replay" / "M0" / "report.json")["laws"]["L_par_hdr_v2"]["solidity"]
        h = rep["header"]
        vh = "0x" + bytes.fromhex(h[2:])[57:89].hex()
        side = {"header": h, "committed_hash": rep["committed_hash"], "v1_header": h,
                "v1_committed_hash": rep["committed_hash"], "stored_vh": vh}
        self.assertEqual(self.E.ghost_tag(side)[0], self.E.CONTRADICTION)
        cons = {"input_header": h, "input_v1_header": h, "input_stored_vh": vh, "version": 2, "v1_version": 2,
                "blob_commit_hash": vh, "v1_blob_commit_hash": vh,
                "aggregate": "0x" + keccak256(bytes.fromhex(vh[2:])).hex()}
        self.assertEqual(self.E.tag_consumer(cons, {"header": h, "v1_header": h, "stored_vh": vh})[0],
                         self.E.NOT_OBSERVED)


class TestCaseStudyMapping(unittest.TestCase):
    """The law-to-id mapping decides the headline coverage numbers; a change must be explicit here."""
    M0 = {"L_dom_hdr": ["O1"], "L_par_hdr_ssvh": ["D1"], "L_par_hdr_v0": ["D1"], "L_par_hdr_v1": ["D1"],
          "L_par_hdr_v2": ["O2"], "L_rt_go_v0": ["D1"], "L_rt_go_v1": ["D1"], "L_rt_go_v2": ["D1"]}
    M1 = {"L_disch_delay_nofree": "O33 (F7 reconciled)", "L_disch_delay_pay": "O33 (F7 reconciled)",
          "L_disch_delay_prove": "O33 (F7 reconciled)", "L_disch_delay_wait": "O33 (F7 reconciled)",
          "L_disch_stale": "O31 (F4)", "L_disch_stale_commit": "O31 (F4)", "L_fact_Z": "O22 (F2)",
          "L_nat_eta2": "O15 (N1)", "L_own_txspayload": "O36 (F9 sub-item)", "L_sort_remaining": "O27 (F4)",
          "L_sym_omega": "O19 (F5)", "L_tag_BVH": "O26 (F6)", "L_undo_BD": "D5 (whitepaper §11.6)",
          "L_undo_BVH": "O11/O32 (F2)", "L_undo_CSR": "D5 (whitepaper §11.6)", "L_undo_cancel": "O12 (N2)"}

    def test_mapping_is_pinned(self):
        self.assertEqual(load_json(ROOT / "spec" / "ledger" / "maps_to.json")["M0"], self.M0)
        self.assertEqual({lid: law.get("maps_to") for lid, law in laws("M1").items()}, self.M1)


@unittest.skipUnless(os.environ.get("HOLON_REPLAY") == "1" and (MORPH / ".git").exists(),
                     "set HOLON_REPLAY=1 with a morph checkout: runs the Go consumer tests")
class TestConsumersOnRealGo(unittest.TestCase):
    def setUp(self):
        self.C = holon_module("holon.consumers")
        self.work = Path(tempfile.mkdtemp(prefix="holon-cons-"))

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def test_fabricated_parent_header_is_not_passed(self):
        commits = {"c1": {"version": 1, "last_block_number": 1, "num_l1_messages": 0, "prev_state_root": "0x" + "00" * 32,
                          "post_state_root": "0x" + "00" * 32, "withdraw_root": "0x" + "00" * 32, "blobs": 0},
                   "c2": {"version": 1, "last_block_number": 1, "num_l1_messages": 0, "prev_state_root": "0x" + "00" * 32,
                          "post_state_root": "0x" + "00" * 32, "withdraw_root": "0x" + "00" * 32, "blobs": 1}}
        side = self.C.fact_z_side(MORPH, self.work, "0x" + "ff" * 25, commits, 0)
        self.assertNotEqual(side["status"], "passed", side["observed"])
        self.assertIs(side["obstruction_observed"], False)

    def test_correct_v2_header_does_not_observe_a_ghost_tag(self):
        rep = load_json(ROOT / "replay" / "M0" / "report.json")["laws"]["L_par_hdr_v2"]["solidity"]
        h = rep["header"]
        vh = "0x" + bytes.fromhex(h[2:])[57:89].hex()
        side = self.C.tag_bvh_side(MORPH, self.work, h, vh, h)
        self.assertIs(side["obstruction_observed"], False, side["observed"])


if __name__ == "__main__":
    unittest.main()
