"""I4: provisional finding filter (witness_provenance, filter_bin) and strict G6.

The bin rule is tests_m2/_i4.py::expected_bin, fixed at the I4 prereg. holon/filter.py must
agree with it on every small input, records must carry the bins it gives on the committed replay
reports, and the gate (G6) must reject records and reports that disagree.
"""
import itertools
import shutil
import unittest
from pathlib import Path

from tests_m2._i4 import BINS, PROVENANCE, STATUSES, expected_bin, report, sides
from tests_m2._m2 import MILESTONES, ROOT, copy_repo, holon_module, item, load_json, records, run_holon, write_json


def all_sides():
    for st, ob, pv in itertools.product(STATUSES, (True, False), PROVENANCE):
        yield {"status": st, "obstruction_observed": ob, "provenance": pv}


class TestFilterRule(unittest.TestCase):
    def test_module_agrees_with_the_rule_on_all_small_inputs(self):
        F = holon_module("holon.filter")
        self.assertEqual(F.bin_of({}), expected_bin({}))
        one = list(all_sides())
        for a in one:
            self.assertEqual(F.bin_of({"x": dict(a)}), expected_bin({"x": a}), a)
        for a, b in itertools.product(one, one):
            ss = {"x": dict(a), "y": dict(b)}
            self.assertEqual(F.bin_of(ss), expected_bin({"x": a, "y": b}), ss)

    def test_rule_cases(self):
        ok = {"status": "passed", "obstruction_observed": True}
        self.assertEqual(expected_bin({"s": {**ok, "provenance": "public_schedule"}}), "finding")
        self.assertEqual(expected_bin({"s": {**ok, "provenance": "public_schedule"},
                                       "g": {**ok, "provenance": "library_api"}}), "finding")
        self.assertEqual(expected_bin({"g": {**ok, "provenance": "library_api"}}), "pending")
        self.assertEqual(expected_bin({"s": {**ok, "provenance": "public_schedule"},
                                       "h": {**ok, "provenance": "internal_harness"}}), "pending")
        self.assertEqual(expected_bin({"s": {**ok, "provenance": "emulated_storage"}}), "pending")
        self.assertEqual(expected_bin({"s": {"status": "passed", "obstruction_observed": False,
                                             "provenance": "public_schedule"}}), "pending")
        self.assertEqual(expected_bin({"s": {"status": "not_applicable", "obstruction_observed": False,
                                             "provenance": "public_schedule"}}), "pending")
        self.assertEqual(expected_bin({"s": {**ok, "provenance": "public_schedule"},
                                       "g": {"status": "failed", "obstruction_observed": False,
                                             "provenance": "library_api"}}), "model_defect")


class TestBins(unittest.TestCase):
    def test_records_follow_the_rule(self):
        for m in MILESTONES:
            rep = report(m)
            for lid, rec in records(m).items():
                with self.subTest(milestone=m, law=lid):
                    if rec["status"] != "REFUTED":
                        self.assertIsNone(rec["witness_provenance"])
                        self.assertIsNone(rec["filter_bin"])
                        continue
                    ss = sides(m, rep["laws"][lid])
                    self.assertIn(rec["filter_bin"], BINS, "known_limitation is never assigned before I40")
                    self.assertEqual(rec["filter_bin"], expected_bin(ss))
                    self.assertEqual(rec["witness_provenance"], {k: s["provenance"] for k, s in ss.items()})

    def bins(self) -> dict:
        out = {}
        for m in MILESTONES:
            for lid, rec in records(m).items():
                if rec["status"] == "REFUTED":
                    out[lid] = rec["filter_bin"]
        return out

    def test_predicted_bins_new_replays(self):
        """I4-P5: the bins that depend on the new replays (I4-P1..P4)."""
        want = item("I4", "I4-P5")["expected"]
        got = self.bins()
        self.assertEqual({k: got.get(k) for k in want}, want)

    def test_bins_of_recorded_replays(self):
        """I4-P7 (construction): bins that follow from replays already recorded."""
        want = item("I4", "I4-P7")["expected"]
        got = self.bins()
        self.assertEqual({k: got.get(k) for k in want}, want)

    def test_every_refuted_law_has_a_predicted_bin(self):
        want = {**item("I4", "I4-P5")["expected"], **item("I4", "I4-P7")["expected"]}
        self.assertEqual(set(want), set(self.bins()))

    def test_predicted_provenance(self):
        """I4-P6 (construction): per-side provenance."""
        want = item("I4", "I4-P6")["expected"]
        got = {}
        for m in MILESTONES:
            for lid, rec in records(m).items():
                if rec["status"] == "REFUTED":
                    got[lid] = rec["witness_provenance"]
        self.assertEqual(got, want)


def gate(repo: Path, m: str, checks: str = "G6"):
    rp = repo / f"g_{m}.json"
    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rp), "--checks", checks], cwd=repo)
    return p, (load_json(rp) if rp.exists() else None)


class TestStrictG6(unittest.TestCase):
    def g6(self, m: str, edit=None) -> dict:
        repo = copy_repo()
        try:
            if edit:
                edit(repo)
            p, rep = gate(repo, m)
            self.assertIsNotNone(rep, p.stdout[-1000:] + p.stderr[-1000:])
            return rep["checks"]["G6"]
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def fails(self, m: str, edit, needle: str) -> None:
        g = self.g6(m, edit)
        self.assertFalse(g["passed"], g["detail"])
        self.assertIn(needle, g["detail"])

    def test_g6_passes(self):
        for m in MILESTONES:
            with self.subTest(milestone=m):
                g = self.g6(m)
                self.assertTrue(g["passed"], g["detail"])

    def test_flipped_bin_fails(self):
        def edit(repo):
            f = repo / "results" / "M1" / "L_undo_BVH.json"
            d = load_json(f)
            d["filter_bin"] = "pending" if d["filter_bin"] != "pending" else "finding"
            write_json(f, d)
        self.fails("M1", edit, "L_undo_BVH")

    def test_changed_provenance_fails(self):
        def edit(repo):
            f = repo / "results" / "M0" / "L_par_hdr_v2.json"
            d = load_json(f)
            d["witness_provenance"]["solidity"] = "library_api"
            write_json(f, d)
        self.fails("M0", edit, "L_par_hdr_v2")

    def test_non_bool_observed_fails(self):
        def edit(repo):
            f = repo / "replay" / "M1" / "report.json"
            d = load_json(f)
            d["laws"]["L_sort_remaining"]["sides"]["solidity"]["obstruction_observed"] = "true"
            write_json(f, d)
        self.fails("M1", edit, "L_sort_remaining")

    def test_unknown_provenance_fails(self):
        def edit(repo):
            f = repo / "replay" / "M0" / "report.json"
            d = load_json(f)
            d["laws"]["L_dom_hdr"]["go"]["provenance"] = "public"
            write_json(f, d)
        self.fails("M0", edit, "L_dom_hdr")

    def test_missing_claimed_side_fails(self):
        """Dropping a consumer side fails even when the record is rebinned to match what is left."""
        def edit(repo):
            f = repo / "replay" / "M1" / "report.json"
            d = load_json(f)
            ss = d["laws"]["L_tag_BVH"]["sides"]
            del ss["go_consumer"]
            write_json(f, d)
            r = repo / "results" / "M1" / "L_tag_BVH.json"
            rec = load_json(r)
            rec["witness_provenance"] = {k: s["provenance"] for k, s in ss.items()}
            rec["filter_bin"] = expected_bin(ss)
            write_json(r, rec)
        self.fails("M1", edit, "go_consumer")

    def test_toolchain_pin_mismatch_fails(self):
        def edit(repo):
            f = repo / "config" / "holon.json"
            d = load_json(f)
            d["replay"]["solc_sha256"] = "0" * 64
            write_json(f, d)
        for m in MILESTONES:
            with self.subTest(milestone=m):
                self.fails(m, edit, "solc")


if __name__ == "__main__":
    unittest.main()
