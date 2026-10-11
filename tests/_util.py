"""Shared helpers for the frozen acceptance tests (stdlib only)."""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.reference import mini_schema, ref_ir, ref_model  # noqa: E402

FACTS = ROOT / "facts" / "morph_header.json"
LAWS_DIR = ROOT / "laws" / "M0"
MARK_OK = "ALL PROOFS CHECK"
MARK_FAIL = "SOME PROOFS FAIL"


def load_json(p) -> dict:
    return json.loads(Path(p).read_text())


def schema(name: str) -> dict:
    return load_json(ROOT / "schemas" / f"{name}.schema.json")


def validate(instance, name: str) -> None:
    mini_schema.validate(instance, schema(name))


def config() -> dict:
    p = ROOT / "config" / "holon.json"
    if not p.exists():
        raise AssertionError("config/holon.json is missing (P0 creates it from config/holon.example.json)")
    return load_json(p)


def bend_cmd() -> list[str]:
    env = os.environ.get("HOLON_BEND_CMD")
    if env:
        return shlex.split(env)
    return list(config()["bend"]["cmd"])


def run_bend(args: list[str], cwd=None, timeout: int | None = None) -> tuple[int, str]:
    cmd = bend_cmd() + [str(a) for a in args]
    if shutil.which(cmd[0]) is None and not Path(cmd[0]).exists():
        raise AssertionError(f"bend command not found: {cmd[0]!r} (install it in P0, or set HOLON_BEND_CMD)")
    t = timeout or int(config()["bend"].get("timeout_s", 180))
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=t)
    return p.returncode, p.stdout + p.stderr


def law_ids() -> list[str]:
    return sorted(p.stem for p in LAWS_DIR.glob("L_*.json"))


def load_law(law_id: str) -> dict:
    return load_json(LAWS_DIR / f"{law_id}.json")


def predictions() -> dict:
    return {x["law_id"]: x for x in load_json(ROOT / "predictions" / "M0.json")["laws"]}


def run_holon(args: list[str], cwd=None, timeout: int = 1800) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(cwd or ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd or ROOT,
                          capture_output=True, text=True, timeout=timeout, env=env)


_IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "node_modules", ".venv", "venv", "tmp")


def copy_repo() -> Path:
    """A throwaway copy of the repo for runs that must not touch the working tree."""
    d = Path(tempfile.mkdtemp(prefix="holon-test-"))
    dst = d / "repo"
    shutil.copytree(ROOT, dst, ignore=_IGNORE)
    return dst


def first_difference(a, b):
    """Index of the first differing element of two equal-type sequences (or None)."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))
