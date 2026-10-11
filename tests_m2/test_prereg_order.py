"""I1: `holon audit prereg` checks that predictions were committed before their outcomes, and never edited.

These tests need git history. They fail (never skip) when it is missing.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m2._m2 import ROOT, run_holon

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def git(repo: Path, *args: str) -> str:
    env = dict(os.environ, **GIT_ENV)
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise AssertionError(f"git {args}: {p.stderr}")
    return p.stdout


def audit(repo: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "holon", "audit", "prereg", "--milestone", "M2", "--root", str(repo)],
                          cwd=ROOT, capture_output=True, text=True, env=env, timeout=600)


KEY = {"title": "t", "plan": "p", "prompt": "prompts/x.md", "predictions": [], "regressions": [],
       "outcome_paths": ["results/M2/"], "tests": ["tests_m2/test_x.py"], "thresholds": {}}
TEST_V1 = "def test_a():\n    assert 1 == 1\n"


class TestRealCheckout(unittest.TestCase):
    def test_history_present(self):
        self.assertTrue((ROOT / ".git").exists(), "test_prereg_order needs the git checkout: it fails, never skips")
        self.assertTrue(git(ROOT, "rev-list", "--count", "HEAD").strip().isdigit())

    def test_real_checkout_passes(self):
        p = run_holon(["audit", "prereg", "--milestone", "M2"])
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-2000:])
        self.assertIn("I1", p.stdout)


class TestSyntheticHistories(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix="holon-prereg-"))
        git(self.repo, "init", "-q")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def write(self, rel: str, text: str) -> None:
        p = self.repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg: str) -> None:
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", msg)

    def prereg(self, key=None) -> None:
        self.write("spec/M2/predictions.json", json.dumps({"milestone": "M2", "doc": "d", "iterations": {"I1": key or KEY}}))
        self.write("tests_m2/test_x.py", TEST_V1)
        self.write("prompts/x.md", "prompt\n")
        self.commit("prereg")

    def test_good_order_passes(self):
        self.prereg()
        self.write("results/M2/a.json", "{}")
        self.commit("outcome")
        p = audit(self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_outcome_in_prereg_commit_fails(self):
        self.write("results/M2/a.json", "{}")
        self.prereg()
        p = audit(self.repo)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("results/M2/", p.stdout)

    def test_edited_key_fails(self):
        self.prereg()
        k = dict(KEY, predictions=[{"id": "I1-P1", "claim": "added later", "check": "x"}])
        self.write("spec/M2/predictions.json", json.dumps({"milestone": "M2", "doc": "d", "iterations": {"I1": k}}))
        self.commit("edit key")
        p = audit(self.repo)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("edited", p.stdout)

    def test_changed_test_function_fails(self):
        self.prereg()
        self.write("tests_m2/test_x.py", "def test_a():\n    assert True\n")
        self.commit("weaken test")
        p = audit(self.repo)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("test_a", p.stdout)

    def test_added_test_function_passes(self):
        self.prereg()
        self.write("tests_m2/test_x.py", TEST_V1 + "\n\ndef test_b():\n    assert 2 == 2\n")
        self.commit("add test")
        p = audit(self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_amendment_allows_a_fixed_test(self):
        self.prereg()
        self.write("tests_m2/test_x.py", "def test_a():\n    assert 1 + 0 == 1\n")
        self.write("spec/M2/amendments.jsonl",
                   json.dumps({"iteration": "I1", "test": "tests_m2/test_x.py::test_a", "why": "typo"}) + "\n")
        self.commit("fix test with amendment")
        p = audit(self.repo)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("amended", p.stdout)

    def test_missing_history_fails(self):
        shutil.rmtree(self.repo / ".git")
        self.write("spec/M2/predictions.json", json.dumps({"milestone": "M2", "doc": "d", "iterations": {"I1": KEY}}))
        p = audit(self.repo)
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
