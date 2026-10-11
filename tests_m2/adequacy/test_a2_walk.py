"""A2 held-out campaign walk (runner.run_a2), with compile and pipeline
steps stubbed. The frozen rule: walk spec/M2/A2/mutants.json `order`, keep the
first `take` mutants that compile; invalids are recorded and skipped."""
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from holon.mutate import runner

REPO = Path(__file__).resolve().parents[2]
A2 = json.loads((REPO / runner.A2_SPEC).read_text())
A1 = json.loads((REPO / runner.A1_SPEC).read_text())
COMMIT = A1["target"]["commit"]
ROLLUP_REL = "contracts/contracts/l1/rollup/Rollup.sol"
PINNED = A1["target"]["file_sha256"][ROLLUP_REL]
BASELINE = {"m0": {"L_m0": "PROVED"}, "m1": {"L_m1": "PROVED"}, "a2": {"L_a2_x": "PROVED"}}


class A2Env:
    """Patch every external step of run_a2; mutants still go through _apply
    on a fake worktree file built from their `original` text."""

    def __init__(self, case, compile_fail_ids=frozenset(), pipeline_fail_ids=frozenset(),
                 flips=None):
        self.case = case
        self.compile_fail = set(compile_fail_ids)
        self.pipeline_fail = set(pipeline_fail_ids)
        self.flips = flips or {}
        self.morph = Path(tempfile.mkdtemp())
        (self.morph / Path(ROLLUP_REL).parent).mkdir(parents=True)
        (self.morph / ROLLUP_REL).write_text("pinned\n")
        self.work = Path(tempfile.mkdtemp())
        self.out = self.work / "report.json"
        self.patches = []

    def _wt_file(self, wt: Path, m: dict):
        p = wt / m["file"]
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = ["// pad\n"] * m["line"]
        lines[m["line"] - 1] = "    " + m["original"].strip() + "\n"
        p.write_text("".join(lines))

    def start(self):
        r = runner
        real_sha = r._file_sha
        real_apply = r._apply
        def sha(p):
            p = Path(p)
            if p.name == "Rollup.sol" and self.morph in p.parents:
                return PINNED
            return real_sha(p)
        def worktree(morph, commit, dest):
            Path(dest).mkdir(parents=True, exist_ok=True)
            self.current_wt = Path(dest)
        def apply(wt, m):
            self._wt_file(wt, m)
            real_apply(wt, m)
        def s1_extract(wt, solc, scratch):
            mid = Path(wt).name[3:]
            if mid in self.compile_fail:
                raise runner.CompileError("solc failed: mocked")
            Path(scratch).mkdir(parents=True, exist_ok=True)
            fp = Path(scratch) / "rollup_facts.json"
            fp.write_text(json.dumps({"id": mid}))
            return {"facts_p": fp, "facts_sha": r._file_sha(fp),
                    "facts_bytes": fp.read_bytes(), "doc": {}, "cov": {}}
        def extract_and_run(wt, solc, scratch):
            fp = Path(scratch) / "facts.json"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text("{}")
            return {"doc": {}, "coverage": {"debt": []}, "facts_p": fp,
                    "facts_sha": r._file_sha(fp), "facts_bytes": fp.read_bytes(),
                    "link_fallbacks": []}
        def a2_pipeline(header_p, rollup_p, scratch):
            tag = Path(scratch).name
            mid = tag[3:] if tag.startswith("a2-") else None
            if mid in self.pipeline_fail:
                raise ValueError("mocked pipeline crash")
            st = json.loads(json.dumps(BASELINE))
            for fam, law, new in self.flips.get(mid or "", []):
                st[fam][law] = new
            return st
        for name, fn in [
                ("_git", lambda morph, *a: COMMIT if a[0] == "rev-parse" else ""),
                ("_file_sha", sha), ("_worktree", worktree),
                ("_node_modules", lambda *a: None), ("_verify_shas", lambda *a: None),
                ("_rm_worktree", lambda *a: None), ("_apply", apply),
                ("_s1_extract", s1_extract), ("_extract_and_run", extract_and_run),
                ("_run_a2_pipeline", a2_pipeline)]:
            p = unittest.mock.patch.object(r, name, fn)
            p.start()
            self.patches.append(p)
        return self

    def stop(self):
        for p in self.patches:
            p.stop()


class TestA2Walk(unittest.TestCase):
    def test_walk_skips_invalid_stops_at_take(self):
        env = A2Env(self, compile_fail_ids={m["id"] for m in A2["order"][:5]}).start()
        try:
            runner.run_a2(env.morph, env.work, None, env.out, limit=None,
                          log=lambda *a: None)
            rep = json.loads(env.out.read_text())
        finally:
            env.stop()
        self.assertTrue(rep["final"])
        self.assertEqual(len(rep["walked"]), A2["take"] + 5)
        self.assertEqual(rep["walked"], [m["id"] for m in A2["order"][:A2["take"] + 5]])
        self.assertEqual(sorted(rep["invalid_skipped"]),
                         sorted(m["id"] for m in A2["order"][:5]))
        scored = [r for r in rep["mutants"] if r["label"] != "invalid"]
        self.assertEqual(len(scored), A2["take"])
        self.assertEqual(rep["counts"]["invalid"], 5)
        self.assertEqual(rep["counts"]["valid"], A2["take"])

    def test_detection_families(self):
        flips = {"A001": [("m0", "L_m0", "REFUTED")],
                 "A002": [("m1", "L_m1", "UNKNOWN")],
                 "A003": [("a2", "L_a2_x", "REFUTED")]}
        env = A2Env(self, flips=flips).start()
        try:
            runner.run_a2(env.morph, env.work, None, env.out, limit=3,
                          log=lambda *a: None)
            rep = json.loads(env.out.read_text())
        finally:
            env.stop()
        self.assertFalse(rep["final"])
        fams = {r["id"]: [c["family"] for c in r["changed"]] for r in rep["mutants"]}
        self.assertEqual(fams["A001"], ["m0"])
        self.assertEqual(fams["A002"], ["m1"])
        self.assertEqual(fams["A003"], ["a2"])
        self.assertTrue(all(r["detected"] for r in rep["mutants"]))
        self.assertEqual(rep["detected_via_counts"]["flip"], 2)
        self.assertEqual(rep["detected_via_counts"]["unknown_only"], 1)

    def test_limit_never_final(self):
        env = A2Env(self).start()
        try:
            runner.run_a2(env.morph, env.work, None, env.out, limit=2,
                          log=lambda *a: None)
            rep = json.loads(env.out.read_text())
        finally:
            env.stop()
        self.assertFalse(rep["final"])
        self.assertEqual(rep["counts"]["valid"], 2)

    def test_pipeline_crash_is_valid_miss(self):
        env = A2Env(self, pipeline_fail_ids={"A002"}).start()
        try:
            runner.run_a2(env.morph, env.work, None, env.out, limit=3,
                          log=lambda *a: None)
            rep = json.loads(env.out.read_text())
        finally:
            env.stop()
        crash = next(r for r in rep["mutants"] if r["id"] == "A002")
        self.assertTrue(crash["valid"])
        self.assertFalse(crash["detected"])
        self.assertEqual(crash["miss_cause"], "pipeline_error")
        self.assertTrue(crash["pipeline_error"].startswith("pipeline: "))
        self.assertEqual(crash["label"], "rule_gap")  # facts differ from baseline stub


if __name__ == "__main__":
    unittest.main()
