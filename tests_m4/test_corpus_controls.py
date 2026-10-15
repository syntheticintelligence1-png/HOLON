"""Preregistered tests for Iteration I48: Evaluation corpus and unsolved controls."""
from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import jsonschema

from holon import bend, ir
from holon.gen import machine, mlaws
from tests_m2 import test_target_agnostic_exhaustive as tae
from tests_m4 import _i48, _m4


class TestPreregAndSidecar(unittest.TestCase):
    """P48-1: Preregistration and sidecar integrity."""

    def test_sidecar_integrity(self) -> None:
        schema = json.loads(
            (_m4.ROOT / "spec" / "schemas" / "predictions.schema.json").read_text(encoding="utf-8")
        )
        pred_doc = _m4.load_predictions()
        jsonschema.validate(pred_doc, schema)
        self.assertEqual(pred_doc["milestone"], "M4")

        it = _m4.iteration("I48")
        self.assertEqual(it["tests"], ["tests_m4/test_corpus_controls.py"])
        self.assertGreaterEqual(len(it["predictions"]), 9)
        self.assertGreaterEqual(len(it["regressions"]), 3)
        self.assertTrue((_m4.ROOT / it["prompt"]).is_file())

        # Verify every check target resolves to a real class and test method in this module.
        for item in it["predictions"] + it["regressions"]:
            tf, cls_name, fn_name = item["check"].split("::")
            self.assertEqual(tf, "tests_m4/test_corpus_controls.py")
            cls_obj = globals().get(cls_name)
            self.assertIsNotNone(cls_obj, f"missing class {cls_name}")
            self.assertTrue(hasattr(cls_obj, fn_name), f"missing method {cls_name}.{fn_name}")

        sidecar = _m4.load_sidecar()
        self.assertEqual(sidecar["schema"], "holon-eval-sidecar/0.1")
        self.assertEqual(sidecar["iteration"], "I48")
        self.assertEqual(sidecar["milestone"], "M4")
        self.assertEqual(sidecar["corpus_spec"]["double_labelled_count"], 20)
        self.assertEqual(sidecar["corpus_spec"]["inter_rater_kappa"], 1.0)

        # Validate 20 historical defect commits across 4 systems and all 8 rules.
        corpus = sidecar["corpus"]
        self.assertEqual(len(corpus), 20)
        expected_ids = [f"CORPUS-{i:02d}" for i in range(1, 21)]
        self.assertEqual([c["corpus_id"] for c in corpus], expected_ids)

        sys_counts = Counter(c["system"] for c in corpus)
        for sys_name in _i48.EXPECTED_SYSTEMS:
            self.assertEqual(sys_counts[sys_name], 5, f"expected 5 commits for {sys_name}")

        corpus_rules = {c["rule"] for c in corpus}
        self.assertEqual(corpus_rules, set(_i48.EXPECTED_RULES))

        corpus_langs = {c["language"] for c in corpus}
        self.assertEqual(corpus_langs, set(_i48.EXPECTED_LANGUAGES))

        seen_commits: set[tuple[str, str]] = set()
        for entry in corpus:
            self.assertRegex(entry["pre_fix_commit"], _i48.HEX40_RE)
            self.assertRegex(entry["fix_commit"], _i48.HEX40_RE)
            self.assertNotEqual(entry["pre_fix_commit"], entry["fix_commit"])
            self.assertRegex(entry["pre_fix_blob_sha"], _i48.HEX40_RE)
            self.assertRegex(entry["fix_blob_sha"], _i48.HEX40_RE)
            self.assertNotEqual(entry["pre_fix_blob_sha"], entry["fix_blob_sha"])
            self.assertRegex(entry["patch_sha256"], _i48.HEX64_RE)
            self.assertEqual(entry["target_files"], [entry["file_path"]])
            self.assertEqual(entry["label_1"], entry["rule"])
            self.assertEqual(entry["label_2"], entry["rule"])
            self.assertTrue(entry["agreement"])
            self.assertGreaterEqual(len(entry["excerpt_identifiers"]), 3)
            self.assertTrue(entry["defect_summary"].strip())
            key = (entry["system"], entry["fix_commit"])
            self.assertNotIn(key, seen_commits)
            seen_commits.add(key)

        # Validate control facts and SHA-256.
        ctrl_facts_raw = sidecar["control_facts"]
        self.assertEqual(ctrl_facts_raw["schema"], "holon-facts/0.2")
        ctrl_facts_txt = (json.dumps(ctrl_facts_raw, indent=2) + "\n").encode("utf-8")
        self.assertEqual(_m4.sha256_bytes(ctrl_facts_txt), sidecar["control_facts_sha256"])
        m = machine.Machine(ctrl_facts_raw)
        self.assertIn("HSt", machine.generate(ctrl_facts_raw, sidecar["control_facts_sha256"]))
        emitter = mlaws.Emitter(m)

        # Validate 12 control obligations (6 FALSE_BEYOND_BOUND + 6 TRUE_UNPROVED).
        law_schema = json.loads((_m4.ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json").read_text(encoding="utf-8"))
        controls = sidecar["controls"]
        self.assertEqual(len(controls), 12)
        self.assertEqual([c["control_id"] for c in controls], [f"CTRL-{i:02d}" for i in range(1, 13)])
        self.assertEqual([c["law_id"] for c in controls], [f"L_ctrl_{i:02d}" for i in range(1, 13)])

        false_ctrls = [c for c in controls if c["category"] == "FALSE_BEYOND_BOUND"]
        true_ctrls = [c for c in controls if c["category"] == "TRUE_UNPROVED"]
        self.assertEqual(len(false_ctrls), 6)
        self.assertEqual(len(true_ctrls), 6)

        ctrl_rules = {c["rule"] for c in controls}
        self.assertEqual(ctrl_rules, set(_i48.EXPECTED_RULES))

        budget = sidecar["controls_spec"]["evaluation_budget"]
        for c in controls:
            self.assertEqual(c["expected_status"], "UNKNOWN")
            self.assertEqual(c["law"]["facts_sha256"], sidecar["control_facts_sha256"])
            jsonschema.validate(c["law"], law_schema)
            ir.check_premises(c["law"])
            self.assertTrue(ir.render_statement(c["law"]))
            emitted = emitter.emit(c["law"], model_import="../../model/eval_ctrl_machine.bend")
            self.assertIn(f"law {c['law_id'].lower()}:", emitted.text)

        for c in false_ctrls:
            self.assertIn("ground_truth_witness", c)
            self.assertTrue(_i48.witness_exceeds_budget(c["law"], c["ground_truth_witness"], budget))

        for c in true_ctrls:
            proof_txt = c.get("ground_truth_proof", "")
            self.assertIn(f"def Laws.{c['law_id'].lower()}(", proof_txt)
            for tok in _i48.FORBIDDEN_PROOF_TOKENS:
                self.assertNotIn(tok, proof_txt)


class TestDefectCorpus(unittest.TestCase):
    """P48-2 & P48-3: Materialized 20-defect evaluation corpus, excerpts, and git provenance."""

    def test_corpus_commits_and_coverage(self) -> None:
        from holon import eval as heval

        self.assertTrue(_m4.CORPUS_MANIFEST.is_file(), "spec/eval/corpus_manifest.json missing")
        manifest = heval.load_corpus_manifest(_m4.CORPUS_MANIFEST)
        sidecar = _m4.load_sidecar()

        self.assertEqual(manifest["schema"], "holon-corpus-manifest/0.1")
        self.assertEqual(manifest["iteration"], "I48")
        self.assertEqual(manifest["milestone"], "M4")
        self.assertEqual(manifest["double_labelled_count"], 20)
        self.assertEqual(manifest["inter_rater_kappa"], 1.0)

        entries = manifest["entries"]
        self.assertEqual(len(entries), 20)
        by_system = Counter(e["system"] for e in entries)
        for sys_name in _i48.EXPECTED_SYSTEMS:
            self.assertEqual(by_system[sys_name], 5)
        self.assertEqual({e["rule"] for e in entries}, set(_i48.EXPECTED_RULES))

        for got, exp in zip(entries, sidecar["corpus"]):
            for k in (
                "corpus_id",
                "system",
                "repo_url",
                "language",
                "file_path",
                "target_files",
                "pre_fix_commit",
                "fix_commit",
                "commit_subject",
                "pre_fix_blob_sha",
                "fix_blob_sha",
                "patch_sha256",
                "rule",
                "subform",
                "label_1",
                "label_2",
                "labeller_1",
                "labeller_2",
                "agreement",
                "defect_summary",
                "excerpt_identifiers",
            ):
                self.assertEqual(got[k], exp[k], f"mismatch on {exp['corpus_id']}.{k}")

    def test_corpus_excerpts_and_patches(self) -> None:
        from holon import eval as heval

        self.assertTrue(_m4.CORPUS_MANIFEST.is_file(), "spec/eval/corpus_manifest.json missing")
        summary = heval.verify_corpus(
            manifest_path=_m4.CORPUS_MANIFEST,
            sidecar_path=_m4.SIDECAR,
            root=_m4.ROOT,
        )
        self.assertEqual(summary["verified_count"], 20)
        self.assertEqual(summary["by_system"], {s: 5 for s in _i48.EXPECTED_SYSTEMS})

        prov = heval.verify_git_provenance(
            manifest_path=_m4.CORPUS_MANIFEST,
            cache_dir=_m4.GIT_CACHE_DIR,
            root=_m4.ROOT,
        )
        self.assertEqual(prov["verified_count"], 20)

        manifest = heval.load_corpus_manifest(_m4.CORPUS_MANIFEST)
        for entry in manifest["entries"]:
            cid = entry["corpus_id"]
            pre_path = _m4.ROOT / entry["pre_fix_excerpt"]
            fix_path = _m4.ROOT / entry["fix_excerpt"]
            patch_path = _m4.ROOT / entry["patch_file"]

            self.assertTrue(pre_path.is_file(), f"missing {pre_path}")
            self.assertTrue(fix_path.is_file(), f"missing {fix_path}")
            self.assertTrue(patch_path.is_file(), f"missing {patch_path}")

            pre_bytes = pre_path.read_bytes()
            fix_bytes = fix_path.read_bytes()
            patch_bytes = patch_path.read_bytes()

            self.assertEqual(_m4.git_blob_sha1(pre_bytes), entry["pre_fix_blob_sha"], cid)
            self.assertEqual(_m4.git_blob_sha1(fix_bytes), entry["fix_blob_sha"], cid)
            self.assertEqual(_m4.sha256_bytes(patch_bytes), entry["patch_sha256"], cid)

            pre_txt = pre_bytes.decode("utf-8")
            fix_txt = fix_bytes.decode("utf-8")
            patch_txt = patch_bytes.decode("utf-8")
            self.assertIn("@@", patch_txt)
            for ident in entry["excerpt_identifiers"]:
                self.assertIn(ident, pre_txt, f"{cid}: {ident} missing in pre_fix")
                self.assertIn(ident, fix_txt, f"{cid}: {ident} missing in fix")

            # Live git provenance check against /tmp/holon-corpus-cache when present.
            repo_dir = _m4.GIT_CACHE_DIR / _m4.GIT_CACHE_REPOS[entry["system"]]
            if repo_dir.is_dir():
                target_rel = entry["target_files"][0]
                t_fix = subprocess.run(
                    ["git", "-C", str(repo_dir), "cat-file", "-t", entry["fix_commit"]],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                self.assertEqual(t_fix, "commit", cid)
                parent_sha = subprocess.run(
                    ["git", "-C", str(repo_dir), "rev-parse", f"{entry['fix_commit']}^1"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                self.assertEqual(parent_sha, entry["pre_fix_commit"], cid)
                pre_blob = subprocess.run(
                    ["git", "-C", str(repo_dir), "rev-parse", f"{entry['pre_fix_commit']}:{target_rel}"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                fix_blob = subprocess.run(
                    ["git", "-C", str(repo_dir), "rev-parse", f"{entry['fix_commit']}:{target_rel}"],
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout.strip()
                self.assertEqual(pre_blob, entry["pre_fix_blob_sha"], cid)
                self.assertEqual(fix_blob, entry["fix_blob_sha"], cid)


class TestUnsolvedControls(unittest.TestCase):
    """P48-4 & P48-5: Materialized FALSE_BEYOND_BOUND and TRUE_UNPROVED control suite."""

    def test_false_beyond_bound_controls(self) -> None:
        from holon import eval as heval

        self.assertTrue(_m4.CONTROLS_DIR.is_dir(), "spec/eval/controls/ missing")
        cman = heval.load_controls_manifest(_m4.CONTROLS_DIR)
        sidecar = _m4.load_sidecar()

        facts_path = _m4.ROOT / cman["facts_file"]
        self.assertTrue(facts_path.is_file())
        self.assertEqual(_m4.sha256_file(facts_path), sidecar["control_facts_sha256"])
        law_schema = json.loads((_m4.ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json").read_text(encoding="utf-8"))
        ctrl_facts_doc = json.loads(facts_path.read_text(encoding="utf-8"))
        m = machine.Machine(ctrl_facts_doc)
        self.assertIn("HSt", machine.generate(ctrl_facts_doc, sidecar["control_facts_sha256"]))

        false_ctrls = [c for c in cman["controls"] if c["category"] == "FALSE_BEYOND_BOUND"]
        self.assertEqual(len(false_ctrls), 6)
        self.assertEqual([c["control_id"] for c in false_ctrls], [f"CTRL-{i:02d}" for i in range(1, 7)])

        budget = cman["evaluation_budget"]
        self.assertEqual(budget, sidecar["controls_spec"]["evaluation_budget"])

        for ctrl in false_ctrls:
            law_path = _m4.ROOT / ctrl["law_file"]
            self.assertTrue(law_path.is_file(), f"missing {law_path}")
            law = json.loads(law_path.read_text(encoding="utf-8"))
            jsonschema.validate(law, law_schema)
            ir.check_premises(law)
            self.assertEqual(law["law_id"], ctrl["law_id"])
            self.assertEqual(ctrl["expected_status"], "UNKNOWN")
            self.assertTrue(_i48.witness_exceeds_budget(law, ctrl["ground_truth_witness"], budget))

    def test_true_unproved_controls(self) -> None:
        from holon import eval as heval

        self.assertTrue(_m4.CONTROLS_DIR.is_dir(), "spec/eval/controls/ missing")
        cman = heval.load_controls_manifest(_m4.CONTROLS_DIR)
        sidecar = _m4.load_sidecar()

        facts_path = _m4.ROOT / cman["facts_file"]
        self.assertTrue(facts_path.is_file())
        law_schema = json.loads((_m4.ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json").read_text(encoding="utf-8"))

        true_ctrls = [c for c in cman["controls"] if c["category"] == "TRUE_UNPROVED"]
        self.assertEqual(len(true_ctrls), 6)
        self.assertEqual([c["control_id"] for c in true_ctrls], [f"CTRL-{i:02d}" for i in range(7, 13)])

        sidecar_by_id = {c["control_id"]: c for c in sidecar["controls"]}
        for ctrl in true_ctrls:
            law_path = _m4.ROOT / ctrl["law_file"]
            self.assertTrue(law_path.is_file(), f"missing {law_path}")
            law = json.loads(law_path.read_text(encoding="utf-8"))
            jsonschema.validate(law, law_schema)
            ir.check_premises(law)
            self.assertEqual(law["law_id"], ctrl["law_id"])
            self.assertEqual(ctrl["expected_status"], "UNKNOWN")
            proof_txt = ctrl["ground_truth_proof"]
            self.assertEqual(proof_txt, sidecar_by_id[ctrl["control_id"]]["ground_truth_proof"])
            self.assertIn(f"def Laws.{ctrl['law_id'].lower()}(", proof_txt)
            for tok in _i48.FORBIDDEN_PROOF_TOKENS:
                self.assertNotIn(tok, proof_txt)


class TestControlExecution(unittest.TestCase):
    """P48-6 & P48-7: Unassisted HOLON execution, L15 calibration, and ground-truth Bend verification."""

    def test_unassisted_holon_reports_unknown_with_bounds(self) -> None:
        from holon import eval as heval

        sidecar = _m4.load_sidecar()
        expected_bound = sidecar["controls_spec"]["expected_bound"]
        cfg = bend.config(_m4.ROOT)

        res = heval.run_controls_evaluation(
            controls_dir=_m4.CONTROLS_DIR,
            sidecar_path=_m4.SIDECAR,
        )
        self.assertEqual(res["total_controls"], 12)
        self.assertEqual(res["unassisted_unknown_count"], 12)
        self.assertEqual(res["false_positive_proofs"], 0)
        self.assertEqual(res["false_negative_refutations"], 0)

        # Verify materialized Bend control model exists and checks in Bend.
        model_bend = _m4.GEN_CONTROLS_DIR / "model" / "eval_ctrl_machine.bend"
        self.assertTrue(model_bend.is_file(), f"missing {model_bend}")
        model_check = bend.check(model_bend, cfg)
        self.assertTrue(model_check.ok, model_check.out)

        records_on_disk: list[dict] = []
        for item in res["controls"]:
            self.assertEqual(item["unassisted_status"], "UNKNOWN", item["control_id"])
            self.assertEqual(item["bound"], expected_bound, item["control_id"])
            self.assertEqual(tuple(item["tried_generators"]), _i48.EXPECTED_GENERATORS, item["control_id"])

            rec_path = _m4.RESULTS_CONTROLS_DIR / f"{item['law_id']}.json"
            self.assertTrue(rec_path.is_file(), f"missing {rec_path}")
            rec = json.loads(rec_path.read_text(encoding="utf-8"))
            self.assertEqual(rec["law_id"], item["law_id"])
            self.assertEqual(rec["control_id"], item["control_id"])
            self.assertEqual(rec["category"], item["category"])
            self.assertEqual(rec["status"], "UNKNOWN")
            self.assertEqual(rec["bound"], expected_bound)
            self.assertEqual(rec["facts_sha256"], sidecar["control_facts_sha256"])
            self.assertRegex(rec["model_sha256"], _i48.HEX64_RE)
            self.assertRegex(rec["compiled_sha256"], _i48.HEX64_RE)
            self.assertRegex(rec["statement_hash"], _i48.HEX64_RE)

            proof_gens = [a["generator"] for a in rec["attempts"] if a.get("kind") == "proof"]
            self.assertEqual(tuple(proof_gens), _i48.EXPECTED_GENERATORS)
            refute_attempts = [a for a in rec["attempts"] if a.get("kind") == "refute"]
            self.assertEqual(len(refute_attempts), 1)
            self.assertEqual(refute_attempts[0]["engine"], "compiled-model trace search")
            self.assertEqual(refute_attempts[0]["bound"], expected_bound)
            self.assertGreater(refute_attempts[0]["tried"], 0)
            self.assertFalse(refute_attempts[0]["hit"])
            records_on_disk.append(rec)

        # L15 UNKNOWN calibration positive & negative-control (tamper/mutation) checks.
        cal_ok = heval.compute_calibration(records_on_disk)
        self.assertEqual(cal_ok["unknown_count"], 12)
        self.assertEqual(cal_ok["confidently_wrong"], 0)
        self.assertEqual(cal_ok["false_positive_proofs"], 0)
        self.assertEqual(cal_ok["false_negative_refutations"], 0)
        self.assertTrue(cal_ok["calibration_ok"])

        forged_fp = copy.deepcopy(records_on_disk)
        forged_fp[0]["status"] = "PROVED"  # CTRL-01 is FALSE_BEYOND_BOUND
        cal_fp = heval.compute_calibration(forged_fp)
        self.assertEqual(cal_fp["false_positive_proofs"], 1)
        self.assertEqual(cal_fp["confidently_wrong"], 1)
        self.assertFalse(cal_fp["calibration_ok"])

        forged_fn = copy.deepcopy(records_on_disk)
        forged_fn[6]["status"] = "REFUTED"  # CTRL-07 is TRUE_UNPROVED
        cal_fn = heval.compute_calibration(forged_fn)
        self.assertEqual(cal_fn["false_negative_refutations"], 1)
        self.assertEqual(cal_fn["confidently_wrong"], 1)
        self.assertFalse(cal_fn["calibration_ok"])

        forged_bound = copy.deepcopy(records_on_disk)
        forged_bound[0]["bound"] = ""
        cal_bound = heval.compute_calibration(forged_bound)
        self.assertGreaterEqual(cal_bound["missing_bound_count"], 1)
        self.assertFalse(cal_bound["calibration_ok"])

    def test_ground_truth_verifications_accepted_by_bend(self) -> None:
        from holon import eval as heval

        cfg = bend.config(_m4.ROOT)
        verdict_on = bend.verdict_enabled(cfg)

        res = heval.run_controls_evaluation(
            controls_dir=_m4.CONTROLS_DIR,
            sidecar_path=_m4.SIDECAR,
        )
        self.assertEqual(res["false_beyond_bound_verified_count"], 6)
        self.assertEqual(res["true_unproved_verified_count"], 6)

        for item in res["controls"]:
            lid = item["law_id"]
            self.assertTrue(item["ground_truth_verified"], item["control_id"])
            gdir = _m4.GEN_CONTROLS_DIR / "ground_truth" / lid
            laws_f = gdir / "LAWS.bend"
            proof_f = gdir / "PROOF.bend"
            self.assertTrue(laws_f.is_file(), f"missing {laws_f}")
            self.assertTrue(proof_f.is_file(), f"missing {proof_f}")

            laws_txt = laws_f.read_text(encoding="utf-8")
            proof_txt = proof_f.read_text(encoding="utf-8")
            self.assertEqual(bend.escape_hatches(laws_txt + proof_txt), [])

            rr = bend.check(proof_f, cfg)
            self.assertTrue(rr.ok, f"{lid} failed bend.check: {rr.out}")
            if verdict_on:
                vr = bend.check_verdict(proof_f, cfg)
                self.assertTrue(vr.ok, f"{lid} failed bend.check_verdict: {vr.out}")

            if item["category"] == "FALSE_BEYOND_BOUND":
                self.assertEqual(item["ground_truth_kind"], "COUNTER_LAW_ACCEPTED")
                self.assertEqual(
                    item["ground_truth_symbol"],
                    f"Laws.cl_{lid.lower()}",
                )
                self.assertIn(f"law cl_{lid.lower()}:", laws_txt)
            else:
                self.assertEqual(item["ground_truth_kind"], "PROOF_ACCEPTED")
                self.assertEqual(
                    item["ground_truth_symbol"],
                    f"Laws.{lid.lower()}",
                )
                self.assertIn(f"law {lid.lower()}:", laws_txt)


class TestEvaluationReport(unittest.TestCase):
    """P48-8: Deterministic evaluation report for §12 Limitations and §13 Evaluation."""

    def test_report_reproducibility_and_limitations_table(self) -> None:
        from holon import eval as heval

        self.assertTrue(_m4.RESULTS_I48.is_file(), "results/eval/I48_corpus_controls.json missing")
        saved_txt = _m4.RESULTS_I48.read_text(encoding="utf-8")
        saved = json.loads(saved_txt)

        fresh = heval.build_evaluation_report(
            manifest_path=_m4.CORPUS_MANIFEST,
            controls_dir=_m4.CONTROLS_DIR,
            sidecar_path=_m4.SIDECAR,
            root=_m4.ROOT,
        )
        fresh_txt = json.dumps(fresh, indent=2, sort_keys=True) + "\n"
        self.assertEqual(saved_txt, fresh_txt)

        self.assertEqual(saved["schema"], "holon-eval-report/0.1")
        self.assertEqual(saved["iteration"], "I48")
        self.assertEqual(saved["milestone"], "M4")
        self.assertEqual(saved["corpus_summary"]["verified_count"], 20)
        self.assertEqual(saved["corpus_summary"]["by_system"], {s: 5 for s in _i48.EXPECTED_SYSTEMS})
        self.assertEqual(set(saved["corpus_summary"]["by_rule"].keys()), set(_i48.EXPECTED_RULES))

        ctrl_sum = saved["controls_summary"]
        self.assertEqual(ctrl_sum["total_controls"], 12)
        self.assertEqual(ctrl_sum["unassisted_unknown_count"], 12)
        self.assertEqual(ctrl_sum["false_beyond_bound_verified_count"], 6)
        self.assertEqual(ctrl_sum["true_unproved_verified_count"], 6)
        self.assertEqual(len(saved["limitations_table"]), 12)


class TestIsomorphicRenaming(unittest.TestCase):
    """P48-9: Bijective isomorphic renaming of Solidity/Go source, facts JSON, and law IR."""

    def test_isomorphic_renaming_and_tamper_rejection(self) -> None:
        from holon.eval import rename as hrename

        sidecar = _m4.load_sidecar()

        # 1. Dynamic Solidity & Go source snippets constructed at test runtime (cannot be hardcoded).
        sol_src = (
            "pragma solidity ^0.8.20;\n"
            "// Audit comment mentioning customVaultAlpha_91\n"
            "contract CustomVaultAlpha_91 {\n"
            "    uint256 public constant EPOCH_LIMIT_77 = 86400;\n"
            "    mapping(address => uint256) public userBalances_42;\n"
            "    function rebalanceEpoch_42(uint256 deltaAmount_19) external returns (uint256) {\n"
            "        require(deltaAmount_19 <= EPOCH_LIMIT_77, \"ERR_LIMIT_77\");\n"
            "        userBalances_42[msg.sender] += deltaAmount_19;\n"
            "        return userBalances_42[msg.sender];\n"
            "    }\n"
            "}\n"
        )
        renamed_sol, sol_map = hrename.rename(sol_src, language="solidity", seed=42)
        self.assertTrue(hrename.validate_mapping(sol_map))
        self.assertEqual(hrename.unrename(renamed_sol, sol_map), sol_src)
        for kw in ("pragma", "solidity", "contract", "uint256", "mapping", "address", "function", "require", "return"):
            self.assertIn(kw, renamed_sol)
        for usr_id in ("CustomVaultAlpha_91", "EPOCH_LIMIT_77", "userBalances_42", "rebalanceEpoch_42", "deltaAmount_19"):
            self.assertNotIn(usr_id, renamed_sol)
        self.assertNotIn("customVaultAlpha_91", renamed_sol)  # comment scrubbed

        # Seed determinism & distinctness.
        renamed_sol_again, sol_map_again = hrename.rename(sol_src, language="solidity", seed=42)
        self.assertEqual(renamed_sol, renamed_sol_again)
        self.assertEqual(sol_map, sol_map_again)
        renamed_sol_other, _ = hrename.rename(sol_src, language="solidity", seed=99)
        self.assertNotEqual(renamed_sol, renamed_sol_other)
        self.assertEqual(hrename.unrename(renamed_sol_other, _), sol_src)

        go_src = (
            "package batchrollup\n\n"
            "// dynamic comment referencing SequencerQueue_88\n"
            "type SequencerQueue_88 struct {\n"
            "    headCursor_33 uint64\n"
            "    maxWindow_55  uint64\n"
            "}\n\n"
            "func (q *SequencerQueue_88) AdvanceCursor_33(stepDelta_11 uint64) uint64 {\n"
            "    if stepDelta_11 > q.maxWindow_55 {\n"
            "        return q.headCursor_33\n"
            "    }\n"
            "    q.headCursor_33 = q.headCursor_33 + stepDelta_11\n"
            "    return q.headCursor_33\n"
            "}\n"
        )
        renamed_go, go_map = hrename.rename(go_src, language="go", seed=42)
        self.assertTrue(hrename.validate_mapping(go_map))
        self.assertEqual(hrename.unrename(renamed_go, go_map), go_src)
        for kw in ("package", "type", "struct", "uint64", "func", "if", "return"):
            self.assertIn(kw, renamed_go)
        for usr_id in ("batchrollup", "SequencerQueue_88", "headCursor_33", "maxWindow_55", "AdvanceCursor_33", "stepDelta_11"):
            self.assertNotIn(usr_id, renamed_go)

        # 2. Corpus excerpt round-trip on real Solidity and Go excerpts.
        sol_excerpt = (_m4.EXCERPTS_DIR / "CORPUS-01" / "pre_fix.sol").read_text(encoding="utf-8")
        r_ex_sol, m_ex_sol = hrename.rename(sol_excerpt, language="solidity", seed=7)
        self.assertEqual(hrename.unrename(r_ex_sol, m_ex_sol), sol_excerpt)
        for ident in sidecar["corpus"][0]["excerpt_identifiers"]:
            self.assertNotIn(ident, r_ex_sol)

        go_excerpt = (_m4.EXCERPTS_DIR / "CORPUS-04" / "pre_fix.go").read_text(encoding="utf-8")
        r_ex_go, m_ex_go = hrename.rename(go_excerpt, language="go", seed=7)
        self.assertEqual(hrename.unrename(r_ex_go, m_ex_go), go_excerpt)
        for ident in sidecar["corpus"][3]["excerpt_identifiers"]:
            self.assertNotIn(ident, r_ex_go)

        # 3. HOLON facts JSON and law IR JSON round-trip.
        ctrl_facts = sidecar["control_facts"]
        renamed_facts, facts_map = hrename.rename_facts(ctrl_facts, seed=42)
        self.assertEqual(hrename.unrename_facts(renamed_facts, facts_map), ctrl_facts)
        renamed_facts_str = json.dumps(renamed_facts)
        for ident in ("eval_ctrl_machine", "advance_stage", "bump_both", "obsv_alert", "obsv_breach"):
            self.assertNotIn(ident, renamed_facts_str)

        ctrl_law = sidecar["controls"][0]["law"]
        renamed_law, law_map = hrename.rename_law(ctrl_law, mapping=facts_map, seed=42)
        self.assertEqual(hrename.unrename_law(renamed_law, law_map), ctrl_law)
        self.assertNotIn("obsv_alert", json.dumps(renamed_law))

        # 4. Bijection tamper / collision rejection.
        tampered = copy.deepcopy(sol_map)
        fwd_keys = list(tampered["forward"].keys())
        self.assertGreaterEqual(len(fwd_keys), 2)
        tampered["forward"][fwd_keys[1]] = tampered["forward"][fwd_keys[0]]
        with self.assertRaises(ValueError):
            hrename.validate_mapping(tampered)
        with self.assertRaises(ValueError):
            hrename.unrename(renamed_sol, tampered)

        # 5. CLI round-trip via `python3 -m holon.eval.rename`.
        with tempfile.TemporaryDirectory(prefix="holon-i48-rename-") as td:
            tdir = Path(td)
            in_f = tdir / "input.sol"
            out_f = tdir / "renamed.sol"
            map_f = tdir / "map.json"
            restored_f = tdir / "restored.sol"
            in_f.write_text(sol_src, encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "holon.eval.rename",
                    "--input",
                    str(in_f),
                    "--language",
                    "solidity",
                    "--seed",
                    "42",
                    "--out",
                    str(out_f),
                    "--map-out",
                    str(map_f),
                ],
                cwd=_m4.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "holon.eval.rename",
                    "--unrename",
                    "--input",
                    str(out_f),
                    "--map",
                    str(map_f),
                    "--out",
                    str(restored_f),
                ],
                cwd=_m4.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(restored_f.read_text(encoding="utf-8"), sol_src)


class TestI48Regressions(unittest.TestCase):
    """R48-1..R48-3: Frozen files, target-agnostic holon/, and held-out seal integrity."""

    def test_frozen_hashes_intact(self) -> None:
        rc, out = _m4.check_frozen()
        self.assertEqual(rc, 0, out)
        self.assertIn("FROZEN OK", out)

    def test_target_agnostic_holon_package(self) -> None:
        ids = tae.identifiers()
        pat = re.compile(
            r"(?<![\w$])(" + "|".join(sorted(map(re.escape, ids), key=len, reverse=True)) + r")(?![\w$])"
        )
        eval_dir = _m4.ROOT / "holon" / "eval"
        if eval_dir.is_dir():
            for f in sorted(eval_dir.rglob("*.py")):
                rel = f.relative_to(_m4.ROOT).as_posix()
                code = tae.code_py(f.read_text(encoding="utf-8"))
                self.assertEqual(sorted(set(pat.findall(code))), [], rel)

        forbidden_eval_ids = {f"CORPUS-{i:02d}" for i in range(1, 21)} | {f"L_ctrl_{i:02d}" for i in range(1, 13)}
        id_pat = re.compile(
            r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, forbidden_eval_ids))) + r")(?![A-Za-z0-9_])"
        )
        for f in sorted((_m4.ROOT / "holon").rglob("*.py")):
            rel = f.relative_to(_m4.ROOT).as_posix()
            code = tae.code_py(f.read_text(encoding="utf-8"))
            self.assertEqual(sorted(set(id_pat.findall(code))), [], rel)

    def test_heldout_seal_untouched(self) -> None:
        self.assertTrue(_m4.HELDOUT_SEAL.is_file())
        status = subprocess.run(
            ["git", "-C", str(_m4.ROOT), "status", "--porcelain", "--", "spec/heldout/target.json"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(status.stdout.strip(), "")
        diff = subprocess.run(
            ["git", "-C", str(_m4.ROOT), "diff", "HEAD", "--", "spec/heldout/target.json"],
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(diff.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
