"""I43 independent Lean preregistration and RED production acceptance."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests_m3._m3 import ROOT, load_json, predictions
from tests_m3._i43 import (MILESTONES, assert_effective_record, assert_lean_source,
                           assert_lean_matches_ir, assert_target_agnostic, base_rows, census)


class TestI43PromotionPreregContract(unittest.TestCase):
    def test_base_census(self):
        data = census()
        rows, excluded, debt = base_rows()
        counts = {m: sum(r["milestone"] == m for r in rows) for m in MILESTONES}
        self.assertEqual(data["selection"]["base_counts"], counts)
        self.assertEqual(data["selection"]["base_total"], 92)
        self.assertEqual(data["selection"]["milestone_order"], list(MILESTONES))
        self.assertEqual(data["selected"], rows)
        self.assertEqual(len(rows), len({(r["milestone"], r["law_id"]) for r in rows}))
        self.assertEqual([(x["milestone"], x["law_id"], x["status"]) for x in data["excluded"]],
                         excluded)
        self.assertEqual([(x["milestone"], x["law_id"], x["kind"]) for x in data["base_debt"]],
                         debt)
        self.assertIn(("M3", "L_sort_realize_rollup_363_4a64383b", "missing_individual_record"), debt)
        self.assertEqual({law for m, law, kind in debt if kind == "summary_disagreement"},
                         {"L_sort_tag_rollup_279_e01ea84a", "L_sort_tag_rollup_406_e01ea84a"})
        self.assertFalse((ROOT / "gen/core/I42").exists(),
                         "Base census must be updated explicitly if I42 merges before prereg")
        self.assertEqual(predictions("I43")["thresholds"]["base_proved"], counts)


class TestI43LeanPromotedOutcomes(unittest.TestCase):
    def test_independent_promotion(self):
        self.assertTrue((ROOT / "holon/lean_promoted.py").is_file())
        self.assertTrue((ROOT / "gen/M3/I43").is_dir())
        manifest_path = ROOT / "results/M3/I43/lean_promoted_manifest.json"
        self.assertTrue(manifest_path.is_file(), str(manifest_path))
        manifest = load_json(manifest_path)
        rows = census()["selected"]
        expected = {(r["milestone"], r["law_id"]) for r in rows}
        self.assertEqual({(x["milestone"], x["law_id"]) for x in manifest["laws"]}, expected)
        self.assertEqual(manifest["lean_budget_seconds"], 120.0)
        classes = {(r["sort"], r["proof_class"]) for r in rows}
        expected_classes = {(r["sort"], r["proof_class"]) for r in base_rows()[0]}
        self.assertEqual(classes, expected_classes)
        self.assertEqual(len(classes), 7)
        sources = set()
        for result in manifest["laws"]:
            key = (result["milestone"], result["law_id"])
            original = next(r for r in rows if (r["milestone"], r["law_id"]) == key)
            self.assertEqual(result["statement_hash"], original["statement_hash"])
            self.assertEqual(result["primary_status"], "PROVED")
            self.assertEqual(result["lean"]["result"], "checked")
            path = ROOT / result["lean"]["source"]
            self.assertTrue(path.is_file(), str(path))
            self.assertNotIn(path, sources, "each law needs a fresh self-contained Lean file")
            sources.add(path)
            self.assertEqual(result["lean"]["source_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(set(result["lean"]["axioms"]) - {"propext", "Quot.sound"}, set())
            assert_lean_source(self, path, result["law_id"])
            assert_lean_matches_ir(path, result["law_id"], result["milestone"],
                                   {**original, **result})
        for cert in census()["theory_core_ii"]["certificates"]:
            self.assertTrue((ROOT / cert["artifacts"]["lean"]).is_file())
        # Recheck all 92 standalone Lean files directly through holon.lean.check_text,
        # including Lean's per-theorem #print axioms audit.
        import concurrent.futures
        from holon.lean import check_text
        with tempfile.TemporaryDirectory() as tmp:
            def _recheck_one(result):
                src = (ROOT / result["lean"]["source"]).read_text(encoding="utf-8")
                return result["law_id"], check_text(src, tmp, expect=[result["law_id"]], timeout=120)
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                rechecked = list(pool.map(_recheck_one, manifest["laws"]))
        self.assertEqual(len(rechecked), 92)
        for law_id, checked in rechecked:
            self.assertEqual(checked["result"], "checked", (law_id, checked["out"][-2000:]))
            self.assertLessEqual(checked["seconds"], 120)
            self.assertLessEqual(set(checked["axioms"]), {"propext", "Quot.sound"})
        assert_target_agnostic(self)
        source = (ROOT / "holon/lean_promoted.py").read_text()
        self.assertNotIn("tests.reference", source)
        self.assertNotIn("L_par_hdr_v0", source)  # no law-specific promotion exceptions

    def test_q8_core_certificate_selector_inclusion_and_exclusion(self):
        self.assertTrue((ROOT / "holon/lean_promoted.py").is_file())
        from holon.lean_promoted import discover_core_certificates
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            expected = []
            for iteration in ("I42", "I43"):
                for idx, status in enumerate(("PROVED", "UNKNOWN", "REFUTED", "PROVED", "PROVED")):
                    name = f"synthetic_{iteration}_{idx}"
                    folder = root / "gen/core" / iteration / name
                    folder.mkdir(parents=True)
                    if idx == 3:  # missing primary record
                        continue
                    (folder / "record.json").write_text(json.dumps({"status": status, "law_id": name}))
                    (folder / "LAWS.bend").write_text(f"law {name}: {{0 == 0 : U32}}\n")
                    (folder / "PROOF.bend").write_text("from ./LAWS.bend import *\n")
                    if idx != 4:  # missing Lean source
                        (folder / "Proof.lean").write_text(f"theorem {name} : 0 = 0 := rfl\n")
                    if idx == 0:
                        expected.append(name)
            selected = discover_core_certificates(root)
            self.assertEqual([row["law_id"] for row in selected], sorted(expected))

    def test_effective_result_views(self):
        self.assertTrue((ROOT / "holon/result_views.py").is_file())
        self.assertTrue((ROOT / "results/M3/I43/records").is_dir())
        from holon.result_views import (select_effective_records, effective_gate_records,
                                        effective_summary, effective_metrics)

        selected = census()["selected"]
        for row in selected:
            path = ROOT / "results/M3/I43/records" / row["milestone"] / (row["law_id"] + ".json")
            self.assertTrue(path.is_file(), str(path))
            assert_effective_record(self, row, load_json(path))
        for m in ("M0", "M1", "M2"):
            view = select_effective_records(ROOT, m)
            self.assertEqual({r["law_id"] for r in view},
                             set(load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"]))
            self.assertEqual(effective_gate_records(ROOT, m), view)
            self.assertEqual(effective_summary(ROOT, m),
                             {r["law_id"]: r["status"] for r in view})
            self.assertEqual(effective_metrics(ROOT, m)["I2"],
                             sum(r["independence_class"] == "I2" for r in view))
        # The registered M3 realization law has no primary individual record on
        # this base. No complete M3 consumer may invent a status for it.
        for consumer in (select_effective_records, effective_gate_records,
                         effective_summary, effective_metrics):
            with self.assertRaises(Exception, msg=consumer.__name__) as raised:
                consumer(ROOT, "M3")
            for law_id in ("L_sort_realize_rollup_363_4a64383b",
                           "L_sort_tag_rollup_279_e01ea84a", "L_sort_tag_rollup_406_e01ea84a"):
                self.assertIn(law_id, str(raised.exception))
        partial = select_effective_records(ROOT, "M3", require_complete=False)
        self.assertEqual(len([r for r in partial if r["status"] == "PROVED"]), 73)
        self.assertEqual(effective_gate_records(ROOT, "M3", require_complete=False), partial)
        debt = {"L_sort_realize_rollup_363_4a64383b": "missing_individual_record",
                "L_sort_tag_rollup_279_e01ea84a": "summary_disagreement",
                "L_sort_tag_rollup_406_e01ea84a": "summary_disagreement"}
        for view in (effective_summary(ROOT, "M3", require_complete=False),
                     effective_metrics(ROOT, "M3", require_complete=False)):
            self.assertEqual(view["I2"] if "I2" in view else view["proved_count"], 73)
            self.assertEqual({x["law_id"]: x["kind"] for x in view["debt"]}, debt)
        source = (ROOT / "holon/result_views.py").read_text()
        self.assertNotIn("tests.reference", source)
        # A copied selection with a missing effective record must fail closed.
        with tempfile.TemporaryDirectory() as temp:
            import shutil
            copy = Path(temp)
            for relative in ("spec/M3/lib/I43/promotion_census.json", "results/M3/I43/records",
                             "results/M3/I43/lean_promoted_manifest.json", "laws/M0/REGISTRY.json"):
                src = ROOT / relative
                dest = copy / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dest)
                else:
                    shutil.copy2(src, dest)
            missing = copy / "results/M3/I43/records/M0" / (next(
                r["law_id"] for r in selected if r["milestone"] == "M0") + ".json")
            missing.unlink()
            for consumer in (select_effective_records, effective_gate_records,
                             effective_summary, effective_metrics):
                with self.assertRaises(Exception, msg=consumer.__name__):
                    consumer(copy, "M0")
            # A present but stale statement must also fail closed.
            stale = load_json(ROOT / "results/M3/I43/records/M0" / missing.name)
            stale["statement_hash"] = "sha256:" + "0" * 64
            missing.write_text(json.dumps(stale))
            for consumer in (select_effective_records, effective_gate_records,
                             effective_summary, effective_metrics):
                with self.assertRaises(Exception, msg=consumer.__name__):
                    consumer(copy, "M0")


if __name__ == "__main__":
    unittest.main()
