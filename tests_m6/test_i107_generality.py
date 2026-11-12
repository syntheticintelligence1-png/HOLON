"""I107 (M6 exit): the generality run's contract (key spec/M6/predictions/I107.json, protocol
spec/M6/lib/i107_protocol.json).

Runs (the protocol's runs):
  (a) the corpus rerun, all 20 entries of spec/eval/corpus.json, labelled contaminated: post-I51;
  (b) the fresh sealed targets of I106 (spec/heldout2/target.json, read only after this key's prereg is pushed);
  (c) Morph under --roles auto (I104's measure recomputed on the merged tools; never substituted for M3's record).
Routes: A (holon eval holon --roles static), B (holon eval go-machines), C (I104's role-installing derive), each run
unchanged; an entry's laws are their union, its decided laws are A's.

Outcomes: results/eval/generality/, summarised in summary.json (tools/i107_generality.py assemble). Its shape:
  corpus.rows[]          {id, reached_extraction, reached_derive, toolchain_refused, laws: {A, B, C}, decided,
                          detected, detected_any, classes: {true_defect, ...}, miss: {stage, reason} | null}
  corpus.totals          {extracted, toolchain_refused, entries_with_law, decided_laws, detected, true_defect}
  sealed.verify          the verify output's last line
  sealed.targets[]       {id, system, attempted, extracted, derive_status, laws: {A, C}, decided, refuted,
                          refuted_unreplayed, adjudicated: {class: n}, static_ai, slither: {status, ...}}
  sealed.withheld        {class: n}
  sealed.hand_written_target_files   a list of paths (empty)
  morph                  {precision, recall, role_dependent_decided, role_dependent_rederived, new_laws,
                          new_by_status}

TestProtocol is green at the prereg. TestPredictions is the measured outcome (red until the run, and a miss is a result).
TestRegressions holds once the outcomes are committed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = ROOT / "spec" / "M6" / "predictions" / "I107.json"
OUT = ROOT / "results" / "eval" / "generality"
SUMMARY = OUT / "summary.json"
WITHHELD_STATUS = "withheld: pending coordinated disclosure"


def load(p: Path):
    return json.loads(Path(p).read_text())


def th() -> dict:
    return load(KEY)["thresholds"]


def summary() -> dict:
    if not SUMMARY.is_file():
        raise AssertionError(f"{SUMMARY.relative_to(ROOT)} is missing (the run has not been assembled)")
    return load(SUMMARY)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def prereg_commit() -> str:
    out = git("log", "--diff-filter=A", "--format=%H", "--", "spec/M6/predictions/I107.json").split()
    if not out:
        raise AssertionError("the key has no commit")
    return out[-1]


def changed_after_prereg(merges: bool = False) -> list[tuple[str, list[str]]]:
    c = prereg_commit()
    flag = [] if merges else ["--no-merges"]
    shas = git("rev-list", *flag, f"{c}..HEAD").split()
    res = []
    for s in shas:
        files = git("diff-tree", "--no-commit-id", "--name-only", "-r", s).split()
        res.append((s, files))
    return res


def scope_module():
    spec = importlib.util.spec_from_file_location("i107_sealed_entries", ROOT / "spec/M6/lib/i107_sealed_entries.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestProtocol(unittest.TestCase):
    def test_run_protocols_are_i103s(self):
        t = th()["run_protocols"]
        base = load(ROOT / t["from"])
        for k in ("corpus", "sealed"):
            p = load(ROOT / t[k])
            diff = sorted(x for x in set(base) | set(p) if base.get(x) != p.get(x))
            self.assertTrue(set(diff) <= set(t["differ_only_in"]), (k, diff))
            self.assertEqual(p["iteration"], "I107")
            self.assertTrue(p["out"].startswith("results/eval/generality/"), p["out"])

    def test_scope_rule(self):
        m = scope_module()
        keep = ["src/Pool.sol", "contracts/protocol/pool/Pool.sol", "contracts/dependencies/openzeppelin/Ownable.sol",
                "src/core/DelegationManager.sol"]
        drop = ["test/Pool.t.sol", "src/test/Foo.sol", "lib/openzeppelin/ERC20.sol", "script/Deploy.s.sol",
                "contracts/mocks/MockToken.sol", "src/MockOracle.sol", "node_modules/x/A.sol", ".github/A.sol",
                "certora/harness/H.sol", "src/TestHelper.sol", "src/Pool.ts", "src/FooHarness.sol"]
        for f in keep:
            self.assertTrue(m.in_scope(f), f)
        for f in drop:
            self.assertFalse(m.in_scope(f), f)

    def test_protocol_names_the_rules(self):
        p = load(ROOT / th()["protocol"])
        self.assertEqual(sorted(p["runs"]), ["a_corpus", "b_sealed", "c_morph_auto"])
        self.assertEqual(sorted(p["runs"]["b_sealed"]["scope"]), ["G1", "G2", "G3", "G4"])
        self.assertIn("withheld: pending coordinated disclosure", p["disclosure"]["rule"])
        self.assertEqual(sorted(p["routes"]), ["A", "B", "C", "doc", "union"])


class TestPredictions(unittest.TestCase):
    def test_p1_corpus_extraction_reach(self):
        t, s = th()["corpus"], summary()["corpus"]
        self.assertEqual(len(s["rows"]), t["entries"])
        self.assertGreaterEqual(s["totals"]["extracted"], t["extracted_at_least"])
        self.assertEqual(s["totals"]["toolchain_refused"], t["toolchain_refused_entries"])

    def test_p2_corpus_laws(self):
        t, s = th()["corpus"], summary()["corpus"]["totals"]
        self.assertLessEqual(s["entries_with_law"], t["entries_with_law_at_most"])
        self.assertLessEqual(s["decided_laws"], t["decided_laws_at_most"])

    def test_p3_corpus_detections(self):
        t, s = th()["corpus"], summary()["corpus"]
        det = sorted(r["id"] for r in s["rows"] if r["detected"])
        self.assertEqual(len(det), t["detected"], det)
        self.assertEqual(len(det) - len(t["baselines"]["agent_review"]), -5)
        self.assertEqual(len(det) - len(t["baselines"]["slither"]), -1)

    def test_p4_corpus_findings_unreplayed(self):
        self.assertEqual(summary()["corpus"]["totals"]["true_defect"], th()["corpus"]["true_defect"])

    def test_p5_sealed_extraction(self):
        t, s = th()["sealed"], summary()["sealed"]
        self.assertEqual(len(s["targets"]), t["targets"])
        ext = [x for x in s["targets"] if x["extracted"] > 0]
        self.assertGreaterEqual(len(ext), t["extracting_targets_at_least"])
        for x in s["targets"]:
            if x["attempted"]:
                self.assertLess(x["extracted"] / x["attempted"], t["extraction_rate_below"], x["id"])

    def test_p6_sealed_derive_completes(self):
        for x in summary()["sealed"]["targets"]:
            if x["extracted"] > 0:
                self.assertEqual(x["derive_status"], "ok", x["id"])

    def test_p7_sealed_decided(self):
        t, s = th()["sealed"], summary()["sealed"]
        dec = [x for x in s["targets"] if x["decided"] > 0]
        self.assertGreaterEqual(sum(x["decided"] for x in s["targets"]), t["decided_laws_at_least"])
        self.assertGreaterEqual(len(dec), t["decided_on_targets_at_least"])
        self.assertEqual(len(s["hand_written_target_files"]), t["hand_written_target_files"])

    def test_p8_sealed_refuted_classified(self):
        s = summary()["sealed"]
        self.assertEqual(sum(s["withheld"].values()), th()["sealed"]["withheld"])
        for x in s["targets"]:
            self.assertEqual(sum(x["adjudicated"].values()), x["refuted"], x["id"])
            self.assertEqual(x["refuted_unreplayed"], x["refuted"], x["id"])

    def test_p9_sealed_static_ai(self):
        for x in summary()["sealed"]["targets"]:
            self.assertEqual(x["static_ai"], th()["sealed"]["static_ai"], x["id"])

    def test_p10_sealed_slither(self):
        failed = [x for x in summary()["sealed"]["targets"] if x["slither"]["status"] == "compile_failed"]
        self.assertGreaterEqual(len(failed), th()["sealed"]["slither_compile_failed_targets_at_least"])

    def test_p11_morph_roles(self):
        t, s = th()["morph"], summary()["morph"]
        self.assertEqual(s["precision"], t["precision"])
        self.assertEqual(s["recall"], t["recall"])

    def test_p12_morph_auto(self):
        t, s = th()["morph"], summary()["morph"]
        self.assertEqual(s["role_dependent_decided"], t["role_dependent_decided"])
        self.assertGreaterEqual(s["role_dependent_rederived"], t["role_dependent_rederived"])
        self.assertEqual(s["new_laws"], t["new_laws"])
        self.assertEqual(sum(v for k, v in s["new_by_status"].items() if k in ("PROVED", "REFUTED")), t["new_decided"])


MORPH_PATHS = re.compile(r"^(laws/M[0-3]/|gen/M[0-3]/|results/M[0-3]/|replay/|spec/M[0-3]/)")
I107_OWN = re.compile(r"^(results/eval/generality/|docs/iterations/I107|tools/i107_generality\.py$|prompts/I107_|"
                      r"tests_m6/test_i107|spec/M6/)")


class TestRegressions(unittest.TestCase):
    def test_r1_morph_outputs_untouched(self):
        bad = [(s[:12], f) for s, fs in changed_after_prereg() for f in fs
               if MORPH_PATHS.match(f) and git("log", "-1", "--format=%s", s).startswith("I107")]
        self.assertEqual(bad, [])

    def test_r2_disclosure(self):
        wp = OUT / "sealed" / "withheld.jsonl"
        ids = []
        if wp.is_file():
            for ln in wp.read_text().splitlines():
                w = json.loads(ln)
                self.assertRegex(w["commitment"], r"^[0-9a-f]{64}$")
                self.assertEqual(w["status"], WITHHELD_STATUS)
                self.assertIn(w["class"], ("potential_defect",))
                ids.append(w["id"])
        for p in sorted((OUT / "sealed").rglob("*")) if (OUT / "sealed").is_dir() else []:
            if p.is_file() and p.name not in ("withheld.jsonl", "adjudication.json", "summary.json"):
                txt = p.read_text(errors="replace")
                for i in ids:
                    self.assertNotIn(i, txt, f"{p.relative_to(ROOT)} names withheld {i}")

    def test_r3_no_hand_target_files(self):
        bad = [(s[:12], f) for s, fs in changed_after_prereg() for f in fs
               if git("log", "-1", "--format=%s", s).startswith("I107")
               and (f.startswith("targets/") or (f.startswith("spec/") and not f.startswith("spec/M6/")))]
        self.assertEqual(bad, [])

    def test_r4_summary_regenerates(self):
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "i107_generality.py"), "assemble", "--check"],
                           cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_r5_no_model_identifiers(self):
        rx = re.compile(th()["model_id_pattern"])
        paths = [p for p in OUT.rglob("*") if p.is_file()] + [ROOT / "docs" / "iterations" / "I107.md"]
        hits = [str(p.relative_to(ROOT)) for p in paths if p.is_file() and rx.search(p.read_text(errors="replace"))]
        self.assertEqual(hits, [])

    def test_r6_commitment_verified(self):
        c = th()["commitment"]
        tj = ROOT / "spec" / "heldout2" / "target.json"
        salt = ROOT / "spec" / "heldout2" / "salt.txt"
        self.assertEqual(hashlib.sha256(tj.read_bytes()).hexdigest(), c["target_sha256"])
        raw = bytes.fromhex(salt.read_text().strip())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), c["salt_sha256"])
        self.assertEqual(load(OUT / "sealed" / "verify.json")["verify"], "VERIFY OK")


if __name__ == "__main__":
    unittest.main()
