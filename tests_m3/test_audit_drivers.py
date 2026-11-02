"""The external auditor's A1 and A2 drivers (holon/audit/mutation.py, holon/audit/hostile_input.py), the round check
of their records (holon/audit/rounds.py, RD5), and the human's Q9a (docs/HUMAN_ANSWERS.md): a different-family round
by Devin counts like any other.

  Specs      malformed specs are refused before anything runs; a path outside the checkout is refused per mutant.
  Records    RD5: a driver record in a round's directory is schema-valid, names the round, lists each mutant or case
             once in its summary and is cited by an attack that ran, of its auditor type; I21's M2 a2.json is not a
             driver record.
  Q9a        a round whose auditor.family is "different" and whose A1-A4 attacks ran qualifies (CV1) and counts
             (holon audit converge), whoever ran it; nothing reads docs/HUMAN_ANSWERS.md.
  Smoke      the drivers on the fixtures under tests_m3/fixtures/audit_drivers/ (never a round's spec), on the pinned
             checkout and toolchain: A1 with no law run (edit, re-extraction, regeneration, re-derivation), A2 on
             action and Go-op cases. These need config/holon.json's checkout, solc, forge, Go and Bend, and fail
             without them.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests_m3" / "fixtures" / "audit_drivers"
sys.path.insert(0, str(ROOT))

from holon.audit import converge, hostile_input, mutation, rounds  # noqa: E402

C40 = "a" * 40


def _round(n: int, session: str, family: str, counts: bool, ran=("A1", "A2", "A3", "A4"), evidence=None) -> dict:
    cats = {"A1": "mutation_adequacy", "A2": "model_vs_code", "A3": "statement_fidelity", "A4": "vacuity",
            "A5": "bindings_ledger", "A6": "determinism", "A7": "gate_evasion"}
    types = {"A1": "A1", "A2": "A2", "A3": "A3", "A4": "A4", "A5": "A4"}
    attacks = []
    for aid, cat in cats.items():
        a = {"id": aid, "category": cat, "tried": "t", "result": "no_finding", "findings": []}
        if aid in types:
            a["auditor_type"] = types[aid]
            a["run"] = types[aid] in ran
        if evidence and aid in evidence:
            a["evidence"] = evidence[aid]
        attacks.append(a)
    return {"round": n, "milestone": "M3", "target_commit": C40, "round_version": "holon-audit-round/0.2",
            "dry_run": False, "auditor": {"session": session, "family": family, "counts_toward_convergence": counts},
            "attacks": attacks, "findings": []}


def _a1(n: int, attack: dict | None = None) -> dict:
    return {"a1_version": "holon-audit-a1/0.1", "milestone": "M3", "round": n, "target_commit": C40,
            "checkout": {"repo": "r", "commit": "b" * 40},
            "spec": {"path": f"audit/rounds/M3/round{n}/a1_spec.json", "sha256": "c" * 64, "body": {}},
            "budget": {"law_timeout_s": 1, "max_law_runs": 0}, "law_runs": 0,
            "scope": {"documents": [], "reachable": [], "out_of_reach": []},
            "baseline": {"documents": {}, "runs": {}},
            "mutations": [{"id": "m1", "file": "f", "spec_sha256": "d" * 64, "diff": None, "documents": {},
                           "derivation": None, "runs": {}, "not_run": {}, "verdict": "missed", "why": "w",
                           "obstructions": []}],
            "summary": {"detected": [], "missed": ["m1"], "incomplete": [], "refused": []},
            "attack": attack or {"id": "A1", "category": "mutation_adequacy", "auditor_type": "A1", "run": True,
                                 "tried": "t", "result": "finding", "findings": [],
                                 "evidence": [f"audit/rounds/M3/round{n}/a1.json"]}}


class TempRoot:
    def __init__(self):
        self.d = Path(tempfile.mkdtemp(prefix="holon-test-a1a2-"))
        (self.d / "audit" / "rounds" / "M3").mkdir(parents=True)

    def write(self, rel: str, obj) -> Path:
        p = self.d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=1) + "\n")
        return p

    def close(self):
        shutil.rmtree(self.d, ignore_errors=True)


class TestSpecs(unittest.TestCase):
    def test_a1_fixture_is_well_formed(self):
        spec = json.loads((FIX / "a1_spec.json").read_text())
        self.assertEqual(mutation.spec_problems(spec, "M3"), [])

    def test_a1_malformed_specs_are_refused(self):
        good = json.loads((FIX / "a1_spec.json").read_text())
        for bad in ({}, {**good, "spec_version": "x"}, {**good, "mutations": []},
                    {**good, "mutations": [{"id": "m", "file": "f"}]},
                    {**good, "mutations": [{"id": "m", "file": "f", "edit": {"line": 0, "old": "a", "new": "b"}}]},
                    {**good, "mutations": [{"id": "m", "file": "f", "edit": {"line": 1, "old": "a", "new": "a"}}]},
                    {**good, "mutations": [{"id": "m", "file": "f", "patch": "p", "edit": {"line": 1, "old": "a",
                                                                                         "new": "b"}}]},
                    {**good, "mutations": good["mutations"][:1] * 2},
                    {**good, "budget": {"max_law_runs": -1}}, {**good, "extra": 1}):
            self.assertTrue(mutation.spec_problems(bad, "M3"), bad)

    def test_a2_fixture_is_well_formed(self):
        spec = json.loads((FIX / "a2_spec.json").read_text())
        self.assertEqual(hostile_input.spec_problems(spec, "M3"), [])

    def test_a2_malformed_specs_are_refused(self):
        good = json.loads((FIX / "a2_spec.json").read_text())
        act, go = good["cases"][0], good["cases"][3]
        for bad in ({}, {**good, "cases": []}, {**good, "cases": [act, act]},
                    {**good, "cases": [{**act, "call": {"args": {}, "calldata": "0x"}}]},
                    {**good, "cases": [{**act, "call": {"calldata": "0x1"}}]},
                    {**good, "cases": [{**act, "call": {"args": {}, "caller": "0x12"}}]},
                    {**good, "cases": [{**act, "pre": {"storage": {"5": "0x1"}}}]},
                    {**good, "cases": [{**go, "input": {"set": [[0, 256]]}}]},
                    {**good, "cases": [{**go, "input": {"set": [[0, 1], [0, 2]]}}]},
                    {**good, "cases": [{**go, "entry": {"kind": "rust", "document": "d", "function": "f"}}]}):
            self.assertTrue(hostile_input.spec_problems(bad, "M3"), bad)


class TestEdits(unittest.TestCase):
    """apply_mutation on a scratch git repository: outside paths are refused, an edit replaces one occurrence."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="holon-test-edit-"))
        self.co = self.d / "co"
        (self.co / "src").mkdir(parents=True)
        (self.co / "src" / "a.txt").write_text("one two\nthree two two\n")
        (self.d / "outside.txt").write_text("secret\n")
        os.symlink("../outside.txt", self.co / "src" / "link.txt")
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "t"]):
            subprocess.run(["git", "-C", str(self.co), *args], check=True, capture_output=True, env=env)
        self.src = self.d / "src"
        shutil.copytree(self.co, self.src, symlinks=True)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def m(self, **kw):
        return {"id": "m", **kw}

    def test_outside_paths_are_refused(self):
        for f in ("../outside.txt", "/etc/passwd", "src/../src/a.txt", "src/link.txt", "src/missing.txt", "./src/a.txt"):
            diff, why = mutation.apply_mutation(self.m(file=f, edit={"line": 1, "old": "o", "new": "x"}), self.src,
                                                self.co)
            self.assertIsNone(diff, f)
            self.assertTrue(why, f)
        self.assertEqual((self.d / "outside.txt").read_text(), "secret\n")

    def test_edit_needs_one_occurrence_on_its_line(self):
        _d, why = mutation.apply_mutation(self.m(file="src/a.txt", edit={"line": 2, "old": "two", "new": "2"}),
                                          self.src, self.co)
        self.assertIn("2 times", why)
        diff, why = mutation.apply_mutation(self.m(file="src/a.txt", edit={"line": 1, "old": "two", "new": "2"}),
                                            self.src, self.co)
        self.assertIsNone(why)
        self.assertIn("+one 2", diff)
        self.assertEqual((self.src / "src" / "a.txt").read_text(), "one 2\nthree two two\n")
        self.assertEqual((self.co / "src" / "a.txt").read_text(), "one two\nthree two two\n")

    def test_patch_touches_its_file_only(self):
        other = "--- a/src/b.txt\n+++ b/src/b.txt\n@@ -1 +1 @@\n-x\n+y\n"
        _d, why = mutation.apply_mutation(self.m(file="src/a.txt", patch=other), self.src, self.co)
        self.assertIn("must modify src/a.txt only", why)
        good = "--- a/src/a.txt\n+++ b/src/a.txt\n@@ -1,2 +1,2 @@\n-one two\n+one 2\n three two two\n"
        diff, why = mutation.apply_mutation(self.m(file="src/a.txt", patch=good), self.src, self.co)
        self.assertIsNone(why)
        self.assertEqual((self.src / "src" / "a.txt").read_text(), "one 2\nthree two two\n")


class TestRecords(unittest.TestCase):
    def setUp(self):
        self.t = TempRoot()

    def tearDown(self):
        self.t.close()

    def problems(self):
        return [p for p in rounds.check(self.t.d, "M3")["problems"] if p.startswith("RD5")]

    def test_a_cited_valid_record_passes(self):
        self.t.write("audit/rounds/M3/round1.json",
                     _round(1, "s1", "same", False, evidence={"A1": ["audit/rounds/M3/round1/a1.json"]}))
        self.t.write("audit/rounds/M3/round1/a1.json", _a1(1))
        self.assertEqual(self.problems(), [])

    def test_records_that_do_not_match_their_round_fail(self):
        self.t.write("audit/rounds/M3/round1.json",
                     _round(1, "s1", "same", False, evidence={"A1": ["audit/rounds/M3/round1/a1.json"]}))
        bad = _a1(1)
        bad["target_commit"] = "b" * 40
        bad["summary"]["missed"] = []
        self.t.write("audit/rounds/M3/round1/a1.json", bad)
        got = " ".join(self.problems())
        self.assertIn("target_commit", got)
        self.assertIn("summary", got)

    def test_an_uncited_record_and_a_missing_one_fail(self):
        self.t.write("audit/rounds/M3/round1.json",
                     _round(1, "s1", "same", False, evidence={"A2": ["audit/rounds/M3/round1/a2.json"]}))
        self.t.write("audit/rounds/M3/round1/a1.json", _a1(1))
        got = " ".join(self.problems())
        self.assertIn("a1.json: no attack that ran", got)
        self.assertIn("cites audit/rounds/M3/round1/a2.json, which does not exist", got)

    def test_a_schema_violation_fails(self):
        self.t.write("audit/rounds/M3/round1.json",
                     _round(1, "s1", "same", False, evidence={"A1": ["audit/rounds/M3/round1/a1.json"]}))
        bad = _a1(1)
        bad["mutations"][0]["verdict"] = "killed"
        self.t.write("audit/rounds/M3/round1/a1.json", bad)
        self.assertTrue(any("schema" in p for p in self.problems()))

    def test_another_instruments_record_is_not_a_driver_record(self):
        self.t.write("audit/rounds/M3/round1.json",
                     _round(1, "s1", "same", False, evidence={"A2": ["audit/rounds/M3/round1/a2.json"]}))
        self.t.write("audit/rounds/M3/round1/a2.json", {"surfaces": {}, "seed": 1})
        self.assertEqual(self.problems(), [])

    def test_the_committed_rounds_stay_valid(self):
        for m in ("M2", "M3"):
            self.assertEqual(rounds.check(ROOT, m)["problems"], [], m)


class TestQ9a(unittest.TestCase):
    """A round run by Devin at the human's request, family "different", A1-A4 run: it qualifies and counts."""

    def setUp(self):
        self.t = TempRoot()
        self.t.write("spec/M3/lib/audit_loop.json", json.loads((ROOT / "spec/M3/lib/audit_loop.json").read_text()))

    def tearDown(self):
        self.t.close()

    def test_a_devin_round_counts(self):
        r = _round(1, "Devin, model unknown, 2026-11-02, task t1", "different", True)
        self.t.write("audit/rounds/M3/round1.json", r)
        pol, _p = rounds.load_policy(self.t.d, "M3")
        self.assertEqual(rounds.qualifies(r, set(), pol), (True, ""))
        self.assertEqual(rounds.check(self.t.d, "M3")["problems"], [])
        st = converge.compute(self.t.d, "M3")
        self.assertEqual(json.dumps(st).count('"counted": true'), 1, st)

    def test_a_devin_round_missing_an_auditor_type_does_not_count(self):
        r = _round(1, "Devin, model unknown, 2026-11-02, task t1", "different", True, ran=("A3", "A4"))
        self.t.write("audit/rounds/M3/round1.json", r)
        self.assertTrue(any(p.startswith("RD2") for p in rounds.check(self.t.d, "M3")["problems"]))

    def test_the_session_must_be_fresh(self):
        self.t.write("audit/rounds/M3/round1.json", _round(1, "Devin, s", "different", True))
        self.t.write("audit/rounds/M3/round2.json", _round(2, "Devin, s", "different", True))
        self.assertTrue(any(p.startswith("RD2: round2") for p in rounds.check(self.t.d, "M3")["problems"]))

    def test_nothing_reads_the_answers_file(self):
        for f in ("rounds.py", "converge.py"):
            self.assertNotIn("HUMAN_ANSWERS.md", (ROOT / "holon" / "audit" / f).read_text())


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=str(ROOT), env=env, capture_output=True,
                          text=True, timeout=timeout)


class TestSmoke(unittest.TestCase):
    """The drivers on the fixtures, on the pinned checkout and toolchain (minutes)."""

    @classmethod
    def setUpClass(cls):
        cls.d = Path(tempfile.mkdtemp(prefix="holon-test-drivers-"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.d, ignore_errors=True)

    def _no_scratch(self, text: str):
        for bad in (str(self.d), "/tmp/", str(Path.home())):
            self.assertNotIn(bad, text)
        self.assertEqual(json.dumps(json.loads(text), indent=1, sort_keys=True, ensure_ascii=False) + "\n", text)

    def test_a1_on_the_fixture(self):
        out = self.d / "a1.json"
        p = _run(["audit", "mutation", "--milestone", "M3", "--round", "1", "--spec", str(FIX / "a1_spec.json"),
                  "--out", str(out)], 3600)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-3000:])
        text = out.read_text()
        self._no_scratch(text)
        rec = json.loads(text)
        v = {m["id"]: m for m in rec["mutations"]}
        self.assertEqual(v["outside"]["verdict"], "refused")
        self.assertEqual(v["no-reader"]["verdict"], "missed")
        self.assertTrue(all(b["reproduces"] for b in rec["baseline"]["documents"].values()), rec["baseline"])
        sol = v["sol-guard-constant"]
        self.assertIn("changed", [d["status"] for d in sol["documents"].values()])
        self.assertEqual(sol["derivation"]["steps"].get("derive"), "ok", sol["derivation"])
        self.assertIn(sol["verdict"], ("detected", "incomplete"))
        go = v["go-blob-offset"]
        self.assertTrue(go["documents"], go)
        self.assertEqual(rec["law_runs"], 0)
        self.assertEqual(rec["attack"]["auditor_type"], "A1")
        self.assertTrue(rec["attack"]["run"])
        self.assertEqual(mutation.spec_problems(rec["spec"]["body"], "M3"), [])
        self.assertTrue((self.d / "a1.timings.json").is_file())

    def test_a2_on_the_fixture(self):
        out = self.d / "a2.json"
        p = _run(["audit", "hostile-input", "--milestone", "M3", "--round", "1", "--spec",
                  str(FIX / "a2_spec.json"), "--out", str(out)], 3600)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-3000:])
        text = out.read_text()
        self._no_scratch(text)
        rec = json.loads(text)
        v = {c["id"]: c for c in rec["cases"]}
        self.assertEqual(v["act-no-such-action"]["verdict"], "unsupported")
        for cid in ("act-zero-period", "act-short-calldata", "go-high-byte", "go-low-bytes"):
            self.assertIn(v[cid]["verdict"], ("agree", "disagree"), v[cid])
        self.assertEqual(v["go-high-byte"]["real"]["class"], "OErr", v["go-high-byte"])
        self.assertEqual(v["go-low-bytes"]["real"]["class"], "ORet", v["go-low-bytes"])
        self.assertEqual(v["act-zero-period"]["real"]["status"], "revert", v["act-zero-period"])
        self.assertEqual(rec["attack"]["auditor_type"], "A2")


if __name__ == "__main__":
    unittest.main()
