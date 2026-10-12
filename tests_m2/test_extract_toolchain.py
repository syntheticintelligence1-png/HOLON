"""I17 toolchain (construction checks, not counted; BUILD_PLAN I17 deliverable `tools/setup_env.sh --extract`).

`tools/setup_env.sh --extract` installs the pinned slither-analyzer, crytic-compile and z3-solver (the I17 key's
thresholds.tool_pins) into a virtual environment at ${HOLON_PREFIX:-~/.holon}/tools/extract, never into the repo
(BUILD_PLAN §0.2.6), from tools/extract-requirements.txt, where every requirement is `name==version` with at least one
`--hash=sha256:<64 hex>` and is installed with `pip install --require-hashes --only-binary=:all:`. I17's extraction uses
none of them: it reads solc's AST and inline-assembly Yul only (rule W1 of tests_m2/test_extract_solidity_layout.py).
So if they cannot be installed, nothing in I17 changes and I19 takes the plan's fallback (the AST walker without
SlithIR); the failure is reported, never skipped (AGENTS). The prereg checked availability only: the three pinned
wheels resolve from PyPI for CPython 3.13 on linux x86_64 (pip download into a scratch directory).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i17 as H
from tests_m2._m2 import ROOT, load_json, predictions

SETUP = ROOT / "tools" / "setup_env.sh"
REQS = ROOT / "tools" / "extract-requirements.txt"


def pins() -> dict:
    return predictions("I17")["thresholds"]["tool_pins"]


def venv() -> Path:
    return Path(os.environ.get("HOLON_PREFIX") or (Path.home() / ".holon")) / "tools" / "extract"


def logical_lines(text: str) -> list[str]:
    out, cur = [], ""
    for line in text.splitlines():
        line = line.split(" #", 1)[0].rstrip() if not line.lstrip().startswith("#") else ""
        if line.endswith("\\"):
            cur += line[:-1] + " "
            continue
        cur += line
        if cur.strip():
            out.append(cur.strip())
        cur = ""
    return out


class TestSetupScript(unittest.TestCase):
    def test_setup_env_has_an_extract_option(self):
        text = SETUP.read_text(encoding="utf-8")
        self.assertIn("--extract", text, "tools/setup_env.sh has no --extract option")
        self.assertIn("extract-requirements.txt", text)
        self.assertIn("--require-hashes", text)
        self.assertRegex(text, r"\$\{?PREFIX\}?/tools/extract", "the venv is not under the HOLON prefix")

    def test_requirements_are_hash_pinned_and_hold_the_tool_pins(self):
        self.assertTrue(REQS.exists(), "tools/extract-requirements.txt is missing")
        reqs = {}
        for line in logical_lines(REQS.read_text(encoding="utf-8")):
            if line.startswith("--"):   # global options only: hashes required, wheels only
                self.assertIn(line, ("--require-hashes", "--only-binary=:all:", "--only-binary :all:"), line)
                continue
            with self.subTest(line=line[:80]):
                self.assertNotRegex(line, r"(git\+|https?://|^-e\s|file:)")
                m = re.match(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", line)
                self.assertIsNotNone(m, "every requirement is name==version")
                self.assertRegex(line, r"--hash=sha256:[0-9a-f]{64}")
                reqs[m.group(1).lower().replace("_", "-")] = m.group(2)
        for name, version in pins().items():
            self.assertEqual(reqs.get(name), version, name)


class TestInstalled(unittest.TestCase):
    def test_the_pinned_tools_are_installed_under_holon_tools(self):
        py = venv() / "bin" / "python"
        self.assertTrue(py.exists(), f"{py} is missing: run tools/setup_env.sh --extract")
        self.assertFalse(os.path.realpath(py).startswith(os.path.realpath(ROOT) + os.sep), "the venv is inside the repo")
        code = ("import importlib.metadata as m, json, sys; "
                "print(json.dumps({k: m.version(k) for k in sys.argv[1:]}))")
        p = subprocess.run([str(py), "-I", "-c", code, *pins()], capture_output=True, text=True, timeout=300)
        self.assertEqual(p.returncode, 0, p.stderr[-2000:])
        self.assertEqual(json.loads(p.stdout), pins())
        q = subprocess.run([str(py), "-I", "-c", "import slither, z3; print(z3.get_version_string())"],
                           capture_output=True, text=True, timeout=300)
        self.assertEqual(q.returncode, 0, q.stderr[-2000:])


HOOKLESS = r'''
import json, os, sys
from holon.__main__ import main
code = main(json.loads(os.environ["HOLON_I17_ARGS"]))
tools = sorted({m.split(".")[0] for m in sys.modules} & {"slither", "crytic_compile", "z3", "solcx"})
print("HOLON-I17 " + json.dumps({"code": code, "tools": tools}))
'''


class TestNoToolDependency(unittest.TestCase):
    def test_the_extraction_loads_neither_slither_nor_z3(self):
        tmp = Path(tempfile.mkdtemp(prefix="holon-i17-tools-"))
        try:
            env = dict(os.environ, HOLON_I17_ARGS=json.dumps(["extract", *H.morph_args(), "--out", str(tmp / "o.json")]))
            env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
            p = subprocess.run([sys.executable, "-c", HOOKLESS], cwd=ROOT, env=env, capture_output=True, text=True,
                               timeout=1800)
            line = next((ln for ln in p.stdout.splitlines() if ln.startswith("HOLON-I17 ")), None)
            self.assertIsNotNone(line, p.stdout[-2000:] + p.stderr[-2000:])
            res = json.loads(line[len("HOLON-I17 "):])
            self.assertEqual(res, {"code": 0, "tools": []})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_config_names_the_source_checkout_by_repository(self):
        cfg = load_json(ROOT / "config" / "holon.json")
        target = load_json(H.SIDECAR)["target"]["repo"]
        self.assertEqual(cfg.get("extract", {}).get("sources", {}).get(target), cfg["replay"]["morph"])


if __name__ == "__main__":
    unittest.main()
