"""M2 A1 adequacy tests (docs/M2_SPEC.md §1).

Skipped unless the environment provides the pinned morph checkout
(~/ext/morph @3e44e79), go, solc 0.8.24 and bend — the assembler runs the
live S2 (solc IR) and S3 (gossa) extractors, and the mutation harness runs
the full M0 pipeline per mutant.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from holon.frontends.solidity import layout_extract

ROOT = Path(__file__).resolve().parents[2]
MORPH = Path(os.environ.get("HOLON_MORPH_DIR", Path.home() / "ext" / "morph"))
PIN = "3e44e795586af3e11285b603ab642c67823add51"
SPEC = ROOT / "spec" / "M2" / "mutants.json"
NODE_MODULES = Path(os.environ.get(
    "HOLON_NODE_MODULES", Path.home() / "ext" / "replay_sol" / "node_modules"))


def _solc() -> Path | None:
    if layout_extract.SOLC.exists():
        return layout_extract.SOLC
    svm = sorted(Path.home().glob(".local/share/svm/0.8.24/solc-*"))
    return svm[0] if svm else None


def _available() -> bool:
    if not (MORPH.is_dir() and shutil.which("go") and _solc()
            and (NODE_MODULES / "@openzeppelin").is_dir()):
        return False
    r = subprocess.run(["git", "-C", str(MORPH), "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return r.stdout.strip() == PIN


def _statuses(results_dir: Path) -> dict:
    return json.loads((results_dir / "summary.json").read_text())


def _worktree(work: Path, name: str) -> Path:
    wt = work / f"wt-{name}"
    subprocess.run(["git", "-C", str(MORPH), "worktree", "add", "--detach",
                    str(wt), PIN], check=True, capture_output=True)
    if not (wt / "contracts" / "node_modules").exists():
        (wt / "contracts" / "node_modules").symlink_to(NODE_MODULES)
    return wt


def _rm(wt: Path) -> None:
    subprocess.run(["git", "-C", str(MORPH), "worktree", "remove", "--force", str(wt)],
                   capture_output=True)


@unittest.skipUnless(_available(), "needs morph @3e44e79 + go + solc + node_modules")
class TestAssembleHeader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon.assemble.header import assemble, write_docs
        cls.work = Path(tempfile.mkdtemp(prefix="holon-adequacy-", dir=Path.home()))
        cls.wt = _worktree(cls.work, "assemble")
        cls.doc, cls.cov = assemble(cls.wt, _solc())
        write_docs(cls.doc, cls.cov, cls.work / "facts.json")
        cls.results = cls.work / "results"
        cls.gen = cls.work / "gen"
        from holon import pipeline
        cls.statuses = pipeline.run("M0", str(cls.work / "facts.json"),
                                    str(cls.results), str(cls.gen),
                                    no_registry=True, log=lambda *a: None)
        from holon import mpipeline
        from holon.assemble.header import M1_HEADER_FACTS, M1_HEADER_LAWS
        cls.m1_statuses = mpipeline.run_m1(
            "M1", None, str(cls.work / "results_m1"), str(cls.work / "gen_m1"),
            no_registry=True, log=lambda *a: None,
            law_ids=set(M1_HEADER_LAWS),
            facts_overrides={M1_HEADER_FACTS: cls.work / "facts.json"})

    @classmethod
    def tearDownClass(cls):
        _rm(cls.wt)

    def test_deterministic(self):
        from holon.assemble.header import assemble
        doc2, cov2 = assemble(self.wt, _solc())
        self.assertEqual(json.dumps(self.doc, sort_keys=True),
                         json.dumps(doc2, sort_keys=True))
        self.assertEqual(json.dumps(self.cov, sort_keys=True),
                         json.dumps(cov2, sort_keys=True))

    def test_facts_loads(self):
        from holon import facts
        f = facts.load(self.work / "facts.json")
        self.assertEqual(f["facts_version"], "holon-facts/0.1")
        self.assertIn("enc_go_v0", f["functions"])

    def test_statuses_match_results_m0(self):
        want = _statuses(ROOT / "results" / "M0")
        self.assertEqual(self.statuses, want)

    def test_m1_header_laws_match_results_m1(self):
        want = _statuses(ROOT / "results" / "M1")
        for lid, st in self.m1_statuses.items():
            self.assertEqual(st, want[lid], lid)

    def test_baseline_no_link_fallbacks(self):
        """The unmutated pinned checkout must link every Go src field by wire
        offset: zero ordinal-position fallbacks in the baseline coverage."""
        fallbacks = [d for d in self.cov["debt"]
                     if d["kind"] == "offset_link_ordinal"]
        self.assertEqual(fallbacks, [])


@unittest.skipUnless(_available(), "needs morph @3e44e79 + go + solc + node_modules")
class TestMutate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from holon.mutate.runner import run_mutants
        cls.work = Path(tempfile.mkdtemp(prefix="holon-muttest-", dir=Path.home()))
        out = cls.work / "report.json"
        run_mutants(SPEC, MORPH, ["G03", "S03"], cls.work / "mut", _solc(), out)
        cls.report = json.loads(out.read_text())

    def test_g03_detected_via_l_par_hdr_v1(self):
        (g03,) = [r for r in self.report["mutants"] if r["id"] == "G03"]
        self.assertTrue(g03["valid"])
        self.assertTrue(g03["detected"])
        changed = {c["law"] for c in g03["changed"]}
        self.assertIn("L_par_hdr_v1", changed)

    def test_s03_width_mismatch_is_pipeline_error(self):
        """S03's shl(184) makes the extracted batchIndex field wider than
        put_uint64_be's op width: the pipeline must reject the facts
        (check_op_width), the mutant stays valid and counts as not detected."""
        (s03,) = [r for r in self.report["mutants"] if r["id"] == "S03"]
        self.assertTrue(s03["valid"])
        self.assertFalse(s03["detected"])
        self.assertIn("pipeline_error", s03)
        self.assertEqual(s03["label"], "rule_gap")

    def test_noop_mutant_is_extraction_gap(self):
        """A synthetic mutant whose replacement equals the original: the
        extraction is byte-identical, so the label is extraction_gap and
        nothing is detected."""
        from holon.mutate.runner import run_mutants
        spec = json.loads(SPEC.read_text())
        noop = dict(spec)
        noop["mutants"] = [{"id": "S99", "file": m["file"], "line": m["line"],
                            "original": m["original"], "replacement": m["original"],
                            "operator": "noop", "equivalent": False}
                           for m in spec["mutants"] if m["id"] == "G01"]
        sp = self.work / "noop_mutants.json"
        sp.write_text(json.dumps(noop))
        out = self.work / "noop_report.json"
        run_mutants(sp, MORPH, ["S99"], self.work / "mut2", _solc(), out)
        rep = json.loads(out.read_text())
        (r,) = rep["mutants"]
        self.assertTrue(r["valid"])
        self.assertFalse(r["detected"])
        self.assertEqual(r["label"], "extraction_gap")


if __name__ == "__main__":
    unittest.main()
