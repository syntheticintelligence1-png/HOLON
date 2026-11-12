"""The prereg audit's parallel_outcome amendments (holon/audit/prereg.py, rules 4 and 6): a commit on a branch
parallel to K's prereg commit that writes files under K's outcome paths is licensed, one commit at a time, when
those files are another key L's outcomes: the line lists exactly those files (i), the commit descends from L's
prereg commit (ii), each file lies under one of L's outcome paths (iii), and none lies under an outcome path of K
more specific than L's (iv). Synthetic histories; they need git and fail, never skip, without it.

    I2 (L) outcome_paths ["results/M2/games/"]; prereg commit C_L
    I1 (K) outcome_paths ["results/M2/"] (+ more specific ones in one scenario); prereg commit C_K after C_L
    y      L's outcome commit on a branch from C_L (or from before it), merged after C_K
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests_m2.test_prereg_order import audit, git

L_KEY = {"title": "l", "plan": "p", "prompt": "prompts/l.md", "predictions": [], "regressions": [],
         "outcome_paths": ["results/M2/games/"], "tests": ["tests_m2/test_l.py"], "thresholds": {}}
K_KEY = {"title": "k", "plan": "p", "prompt": "prompts/k.md", "predictions": [], "regressions": [],
         "outcome_paths": ["results/M2/"], "tests": ["tests_m2/test_k.py"], "thresholds": {}}
TEST = "def test_a():\n    assert 1 == 1\n"


class TestParallelOutcome(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="holon-prereg-par-"))
        git(self.repo, "init", "-q")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def write(self, rel: str, text: str) -> None:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg: str) -> str:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg)
        return git(self.repo, "rev-parse", "HEAD").strip()

    def predictions(self, its: dict) -> None:
        self.write("spec/M2/predictions.json", json.dumps({"milestone": "M2", "doc": "d", "iterations": its}))

    def history(self, files: dict, k_key: dict | None = None, fork_before_l: bool = False) -> str:
        """base, C_L, then y (L's files) on a side branch from C_L (or from base), C_K on the main line, the merge.
        Returns y."""
        self.write("README", "base\n")
        base = self.commit("base")
        self.predictions({"I2": L_KEY})
        self.write("tests_m2/test_l.py", TEST)
        self.write("prompts/l.md", "l\n")
        cl = self.commit("prereg I2")
        git(self.repo, "checkout", "-q", "-b", "side", base if fork_before_l else cl)
        for rel, text in files.items():
            self.write(rel, text)
        y = self.commit("I2 outputs")
        git(self.repo, "checkout", "-q", "-")
        self.predictions({"I2": L_KEY, "I1": k_key or K_KEY})
        self.write("tests_m2/test_k.py", TEST)
        self.write("prompts/k.md", "k\n")
        self.commit("prereg I1")
        git(self.repo, "merge", "-q", "--no-edit", "side")
        return y

    def amend(self, *lines: dict) -> None:
        self.write("spec/M2/amendments.jsonl", "".join(json.dumps(x) + "\n" for x in lines))
        self.commit("amendments")

    @staticmethod
    def line(y: str, paths: list, owner: str = "I2", **over) -> dict:
        d = {"iteration": "I1", "kind": "parallel_outcome", "commit": y, "paths": paths, "owner": owner,
             "why": "I2's own outputs under I1's broader outcome path"}
        d.update(over)
        return d

    def run_audit(self):
        p = audit(self.repo)
        return p.returncode, p.stdout + p.stderr

    def test_unlicensed_parallel_outcome_fails(self):
        self.history({"results/M2/games/a.json": "{}"})
        rc, out = self.run_audit()
        self.assertNotEqual(rc, 0, out)
        self.assertIn("does not descend", out)

    def test_licensed_parallel_outcome_passes(self):
        y = self.history({"results/M2/games/a.json": "{}", "results/M2/games/b.json": "{}", "docs/STATUS.md": "s\n"})
        self.amend(self.line(y, ["results/M2/games/b.json", "results/M2/games/a.json"]))
        rc, out = self.run_audit()
        self.assertEqual(rc, 0, out)
        self.assertIn(f"parallel outcome commit {y[:12]} amended (owner I2", out)

    def test_refusals(self):
        cases = [
            ("(i) a file missing", {"results/M2/games/a.json": "{}", "results/M2/games/b.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/a.json"]), {}, "(i)"),
            ("(i) an extra file", {"results/M2/games/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/a.json", "results/M2/games/z.json"]), {}, "(i)"),
            ("(ii) not after L's prereg", {"results/M2/games/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/a.json"]), {"fork_before_l": True}, "(ii)"),
            ("(iii) not L's outcome", {"results/M2/other/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/other/a.json"]), {}, "(iii)"),
            ("(iv) K's more specific path", {"results/M2/games/k/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/k/a.json"]),
             {"k_key": dict(K_KEY, outcome_paths=["results/M2/", "results/M2/games/k/"])}, "(iv)"),
            ("an unknown owner", {"results/M2/games/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/a.json"], owner="I9"), {}, "no key of"),
            ("K as its own owner", {"results/M2/games/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/a.json"], owner="I1"), {}, "K itself"),
            ("a short sha", {"results/M2/games/a.json": "{}"},
             lambda y: self.line(y[:12], ["results/M2/games/a.json"]), {}, "a parallel_outcome line needs"),
            ("a directory path", {"results/M2/games/a.json": "{}"},
             lambda y: self.line(y, ["results/M2/games/"]), {}, "a parallel_outcome line needs"),
        ]
        for name, files, mk, kw, want in cases:
            with self.subTest(case=name):
                self.tearDown()
                self.setUp()
                y = self.history(files, **kw)
                self.amend(mk(y))
                rc, out = self.run_audit()
                self.assertNotEqual(rc, 0, out)
                self.assertIn(want, out)

    def test_a_line_naming_no_parallel_commit_is_a_note(self):
        y = self.history({"results/M2/games/a.json": "{}"})
        other = self.commit_after_merge()
        self.amend(self.line(y, ["results/M2/games/a.json"]), self.line(other, ["results/M2/x.json"]))
        rc, out = self.run_audit()
        self.assertEqual(rc, 0, out)
        self.assertIn(f"names {other[:12]}, which is no parallel outcome commit of I1", out)

    def commit_after_merge(self) -> str:
        """A commit on the main line after the merge (it descends from C_K, so it is no parallel commit)."""
        self.write("results/M2/x.json", "{}")
        return self.commit("I1 outputs")


if __name__ == "__main__":
    unittest.main()
