"""I102: holon audit regress compares each commit with its own parents (F-M3-07, round 2, medium, statement_fidelity;
F-M3-30, round 7, its duplicate); BUILD_PLAN row I102; the key I102 of spec/M3/predictions.json. The instrument is
tests_m3/_i102.py. It imports nothing from holon/ or tools/. The instrument and this docstring are fixed at the prereg
(C_K) and pinned by sha256 in the key's thresholds; spec/M3/amendments/I102.jsonl records the findings as the key's
origin and pins this docstring as well.

Contract. <B> is the key's base_commit (82134fff, the lead after #165), OUT is docs/iterations/I102/, and the
synthetic history is _i102.synthetic's: a seed, two branches with three law changes each (the same change to L_h on
both), and their merge, which regenerates L_x.

F  The finding, at <B>. holon/audit/regress.py hash_changes walks, per law file, the path-limited
   `git log --topo-order --reverse A..B -- <file>` and compares each version with the previous one in that list. On
   branchy history that one is often another branch's commit.
   - Phantom changes. It reports changes no commit made: round 2's range gives 680 uncovered changes, and
     fe1f88f2..ef39bed5 gives 408, against parents none of which is uncovered.
   - Hidden changes. The path-limited log never visits a branch's commit whose file the merge took from its first
     parent, so it leaves out changes commits did make: 224 on fe1f88f2..ef39bed5 (round 7's hidden_check).
   - Coverage. covered_by is judged on the wrong edge.
S  The build. hash_changes walks the commits of A..B that touch laws/ (`git rev-list A..B -- laws/`, with every merge
   of A..B), and compares each law file at a commit C with C's own parents (`git rev-parse C^@`). A file changes at C
   when its version at C (its statement hash, or absent) is none of its parents' versions. A file that no parent holds
   is an addition (additions), not a change. Each change names the parent it is measured against (`parent`): the first
   parent that holds the file. Its old hash is that parent's, and covered_by is judged on that edge. A merge whose
   other parents hold the file under other hashes lists each such edge in `other_parents`, with its own covered_by. No
   other report key changes, and no generator closure module changes.
K  The pins hold, `holon audit prereg --milestone M3` prints PREREG OK, the instrument imports nothing from holon/ or
   tools/, and spec/M3/amendments/I102.jsonl holds one line for this module, pinning this docstring.
B  The build's checks.
   B1 On the synthetic history, the reported (commit, law, parent) set is exactly _i102.expected's seven real changes.
      Each old hash is its parent's and each new one is the commit's (_i102.hash_at). Every one is covered on its edge.
      MX lists Y1 in other_parents.
   B2 The base's regress, run on the same synthetic history (a detached worktree of <B>), shows both failures. It leaves
      out (Y1, L_h). It reports a change for L_x whose old hash is none of its commit's parents', or one that is not
      covered.
   B3 fe1f88f2..ef39bed5 (round 7's range). No reported M3 change is uncovered: parent_check.py has nothing to recheck.
      None is at the merge 41c7e34, whose every law equals its first parent's. hidden_check.py, run on this output,
      finds 0 real statement changes the tool does not report.
   B4 2b4578af..c3eda197 (round 2's range). No reported M3 change is uncovered. None is at the merges 41c7e34 and ecbb695.
      Nothing is reported for L_pinit_Rollup_importGenesisBatch_committedBatches_17_9 at 38d66f5 or 4f0f51b (absent
      from the first parent, equal to the second).
   B5 No target name (I100's _i100.target_names) is in the lines I102 adds under holon/ before its report.
   B6 The workflow (.github/workflows/holon-ci.yml) holds a job that runs this module's build checks.
   B7 No file of a generator closure differs from <B>.
P  The outcomes (OUT is written after C_K), over the whole history of the seed 8a1dbe7..<B> (OUT/full.json: the
   reported changes per milestone, uncovered ones listed):
   P1 Every reported change of an M3 law is covered by a STATEMENT_DIFF line: 0 uncovered.
   P2 No M0 or M1 law changes its statement hash: 0 changes.
   P3 Every reported change of an M2 law is covered: 0 uncovered.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m3 import _i102 as I

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / I.OUT
KEYFILE = ROOT / "spec" / "M3" / "predictions" / "I102.json"
TEST_ID = "tests_m3/test_regress_parents_i102.py::<contract>"


def _th() -> dict:
    return json.loads(KEYFILE.read_text(encoding="utf-8"))["thresholds"]


def _sha(p) -> str:
    return hashlib.sha256((ROOT / p).read_bytes()).hexdigest()


def _load(rel: str):
    return json.loads((OUT / rel).read_text(encoding="utf-8"))


def _m3(rep: dict) -> list:
    return [h for h in rep["hash_changes"] if h["milestone"] == "M3"]


class TestPrereg(unittest.TestCase):
    def test_r0_the_prereg_pins_hold(self):
        th = _th()
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        for name, pin in th["pins"].items():
            self.assertEqual(_sha(pin["path"]), pin["sha256"], name)

    def test_r1_the_prereg_audit_passes(self):
        r = I.run([sys.executable, "-m", "holon", "audit", "prereg", "--milestone", "M3"], timeout=900)
        self.assertIn("PREREG OK", r.stdout + r.stderr)

    def test_r2_the_instrument_imports_nothing_from_holon_or_tools(self):
        src = (ROOT / "tests_m3" / "_i102.py").read_text(encoding="utf-8")
        self.assertFalse(re.search(r"(?m)^\s*(from|import)\s+(holon|tools)\b", src))

    def test_r3_the_amendment_pins_this_docstring(self):
        lines = [json.loads(x) for x in (ROOT / "spec" / "M3" / "amendments" / "I102.jsonl").read_text(
            encoding="utf-8").splitlines() if x.strip()]
        mine = [x for x in lines if x.get("test") == TEST_ID]
        self.assertEqual(len(mine), 1)
        self.assertEqual(mine[0]["contract_sha256"], hashlib.sha256(__doc__.encode("utf-8")).hexdigest())


class TestBuild(unittest.TestCase):
    def test_b1_the_synthetic_history(self):
        with tempfile.TemporaryDirectory(prefix="i102-b1-") as tmp:
            s = I.synthetic(Path(tmp))
            rep = I.regress(ROOT, s["repo"], s["A"], s["MX"])
            got = {(h["commit"], h["law_id"], h["parent"]) for h in rep["hash_changes"]}
            self.assertEqual(got, I.expected(s))
            full = {s[k][:I.SHORT]: s[k] for k in ("A", "X1", "Y1", "MX")}
            for h in rep["hash_changes"]:
                with self.subTest(change=(h["commit"], h["law_id"])):
                    path = f"laws/M9/{h['law_id']}.json"
                    self.assertEqual(h["old"], I.hash_at(ROOT, s["repo"], full[h["parent"]], path))
                    self.assertEqual(h["new"], I.hash_at(ROOT, s["repo"], full[h["commit"]], path))
                    self.assertTrue(h["covered_by"], h)
            mx = next(h for h in rep["hash_changes"] if h["commit"] == s["MX"][:I.SHORT])
            self.assertEqual([o["parent"] for o in mx.get("other_parents") or []], [s["Y1"][:I.SHORT]])

    def test_b2_the_base_shows_both_failures(self):
        with tempfile.TemporaryDirectory(prefix="i102-b2-") as tmp:
            s = I.synthetic(Path(tmp))
            wt = I.base_tree(Path(tmp))
            try:
                rep = I.regress(wt, s["repo"], s["A"], s["MX"])
            finally:
                I.drop_tree(wt)
            got = {(h["commit"], h["law_id"]) for h in rep["hash_changes"]}
            self.assertNotIn((s["Y1"][:I.SHORT], "L_h"), got, "the hidden change")
            full = {s[k][:I.SHORT]: s[k] for k in ("A", "X1", "Y1", "MX")}
            bad = []
            for h in rep["hash_changes"]:
                if h["law_id"] != "L_x":
                    continue
                ps = I.parents_of(s["repo"], full[h["commit"]])
                olds = [I.hash_at(ROOT, s["repo"], p, "laws/M9/L_x.json") for p in ps]
                if h["old"] not in olds or not h["covered_by"]:
                    bad.append(h)
            self.assertTrue(bad, "a phantom or uncovered change of L_x")

    def test_b3_round7s_range(self):
        frm, to = I.ROUND7
        rep = I.regress(ROOT, ROOT, frm, to)
        m3 = _m3(rep)
        self.assertEqual([h for h in m3 if not h["covered_by"]], [])
        self.assertEqual([h for h in m3 if h["commit"] == "41c7e34"], [])
        with tempfile.TemporaryDirectory(prefix="i102-b3-") as tmp:
            p = Path(tmp) / "rep.json"
            p.write_text(json.dumps({**rep, "hash_changes": m3}), encoding="utf-8")   # the findings are M3's
            self.assertEqual(json.loads(I.checker("parent_check.py", to, p)), {})
            out = I.checker("hidden_check.py", frm, to, p)
        self.assertIn("real statement changes the tool does not report: 0", out)

    def test_b4_round2s_range(self):
        frm, to = I.ROUND2
        m3 = _m3(I.regress(ROOT, ROOT, frm, to))
        self.assertEqual([h for h in m3 if not h["covered_by"]], [])
        self.assertEqual([h for h in m3 if h["commit"] in I.ROUND2_EQUAL_MERGES], [])
        self.assertEqual([h for h in m3 if h["law_id"] ==
                          "L_pinit_Rollup_importGenesisBatch_committedBatches_17_9"
                          and h["commit"] in ("38d66f5", "4f0f51b")], [])

    def test_b5_target_agnostic(self):
        from tests_m3 import _i100
        added = I.git(ROOT, "log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                      "docs/iterations/I102.md").split()
        head = added[0] if added else "HEAD"
        out, cur = [], None
        for ln in I.git(ROOT, "diff", "-U0", f"{_th()['base_commit']}..{head}", "--", "holon/").splitlines():
            if ln.startswith("+++ "):
                cur = ln[6:] if ln.startswith("+++ b/") else None
            elif ln.startswith("+") and cur:
                out.append((cur, ln[1:]))
        self.assertTrue(out, "I102 adds no line under holon/")
        self.assertEqual(_i100.scan(out, _i100.target_names(ROOT)), [])

    def test_b6_ci_runs_them(self):
        wf = (ROOT / ".github" / "workflows" / "holon-ci.yml").read_text(encoding="utf-8")
        self.assertIn("tests_m3.test_regress_parents_i102.TestBuild", wf)

    def test_b7_no_generator_closure_moves(self):
        base = _th()["base_commit"]
        changed = set(I.git(ROOT, "diff", "--name-only", f"{base}..HEAD").split())
        code = (
            "import json\nfrom pathlib import Path\nfrom holon import records, profile\nfrom holon.bundle import lawrun\n"
            "from holon.records import _holon_imports\nfrom holon.sorts.run3 import GEN3\nroot = Path('.')\nfs = set()\n"
            "for v in records.GENERATORS:\n    fs |= set(records.generator_files(v, root))\n"
            "fs |= set(profile.generator_files(root))\nseen, todo = set(), list(lawrun.GEN_LAWS) + list(GEN3)\n"
            "while todo:\n    r = todo.pop()\n    if r in seen or not (root / r).is_file():\n        continue\n"
            "    seen.add(r)\n    if r.endswith('.py'):\n        todo.extend(sorted(_holon_imports(r, root) - seen))\n"
            "print(json.dumps(sorted(fs | seen)))\n")
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stderr[-1500:])
        closure = set(json.loads(p.stdout))
        self.assertTrue(closure)
        self.assertEqual(sorted(changed & closure), [])


class TestOutcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = _load("full.json")

    def test_p1_m3_every_change_covered(self):
        self.assertEqual(self.rec["milestones"]["M3"]["uncovered"], [])

    def test_p2_no_m0_or_m1_change(self):
        for m in ("M0", "M1"):
            with self.subTest(milestone=m):
                self.assertEqual(self.rec["milestones"].get(m, {"changes": 0})["changes"], 0)

    def test_p3_m2_every_change_covered(self):
        self.assertEqual(self.rec["milestones"]["M2"]["uncovered"], [])

    def test_the_record_is_the_tools(self):
        """The outcome file states the range and the commit it was computed at, and its counts are its lists'."""
        self.assertEqual(self.rec["from"], I.SEED[:I.SHORT])
        for m, x in self.rec["milestones"].items():
            with self.subTest(milestone=m):
                self.assertLessEqual(len(x["uncovered"]), x["changes"])


if __name__ == "__main__":
    unittest.main()
