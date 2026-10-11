"""The pinned Bend 2 checker: configuration, invocation and environment safety.

Bend's verdicts are final (AGENTS.md rule 6), so everything here is about running the
*right* checker in a *clean* environment and reading its output strictly.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK_OK = "ALL PROOFS CHECK"
MARK_FAIL = "SOME PROOFS FAIL"
UNSAFE_ENV_FILES = ("bunfig.toml", ".env")


def config(root: Path | None = None) -> dict:
    root = Path(root or ROOT)
    p = root / "config" / "holon.json"
    if not p.exists():
        p = root / "config" / "holon.example.json"
    return json.loads(p.read_text())


def bend_cmd(cfg: dict | None = None) -> list[str]:
    env = os.environ.get("HOLON_BEND_CMD")
    if env:
        return shlex.split(env)
    return list((cfg or config())["bend"]["cmd"])


def _env() -> dict:
    env = dict(os.environ)
    elan = Path.home() / ".elan" / "bin"
    if elan.is_dir():  # `--verdict` builds the BendTT kernel with Lean
        env["PATH"] = str(elan) + os.pathsep + env.get("PATH", "")
    return env


@dataclass
class Run:
    code: int | None
    out: str
    seconds: float

    @property
    def first_line(self) -> str:
        lines = self.out.strip().splitlines()
        return lines[0].strip() if lines else ""

    @property
    def ok(self) -> bool:
        return self.code == 0 and self.first_line == MARK_OK

    @property
    def marker(self) -> str:
        if self.first_line in (MARK_OK, MARK_FAIL):
            return self.first_line
        return MARK_FAIL if self.code not in (0, None) else "not_run"


def run(args: list, cwd=None, timeout: int | None = None, cfg: dict | None = None) -> Run:
    cfg = cfg or config()
    cmd = bend_cmd(cfg) + [str(a) for a in args]
    if shutil.which(cmd[0]) is None and not Path(cmd[0]).exists():
        raise FileNotFoundError(f"bend command not found: {cmd[0]!r} (see tools/install_bend.sh)")
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=_env(),
                           timeout=timeout or int(cfg["bend"].get("timeout_s", 180)))
        return Run(p.returncode, p.stdout + p.stderr, round(time.monotonic() - t0, 3))
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return Run(None, out + "\n[timeout]", round(time.monotonic() - t0, 3))


def version(cfg: dict | None = None) -> str:
    r = run(["version"], cfg=cfg)
    m = re.search(r"bend (\d+\.\d+\.\d+)", r.out)
    if r.code != 0 or not m:
        raise RuntimeError(f"cannot read bend version: {r.out[:300]}")
    return m.group(1)


def check(proof_file: Path, cfg: dict | None = None) -> Run:
    """Check a PROOF.bend in its own directory (Bend resolves imports relative to it)."""
    proof_file = Path(proof_file)
    return run([proof_file.name], cwd=proof_file.parent, cfg=cfg)


def verdict_available() -> bool:
    if os.environ.get("BENDTT"):
        return True
    return shutil.which("lean", path=_env()["PATH"]) is not None


def verdict_enabled(cfg: dict | None = None) -> bool:
    v = (cfg or config())["bend"].get("verdict", "auto")
    return verdict_available() if v == "auto" else bool(v)


def check_verdict(proof_file: Path, cfg: dict | None = None) -> Run:
    """Second kernel (whitepaper §8.8): BendTT, whose soundness is proved in Lean."""
    proof_file = Path(proof_file)
    return run([proof_file.name, "--verdict"], cwd=proof_file.parent, cfg=cfg, timeout=1800)


def unsafe_env_files(root: Path) -> list[str]:
    """Bun reads bunfig.toml/.env from the working directory; a preload there patches the checker."""
    root = Path(root)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.name in UNSAFE_ENV_FILES and ".git" not in p.relative_to(root).parts)


# Escape hatches (BEND_PRIMER §3.2), scanned textually in addition to the checker's verdict.
ESCAPE_PATTERNS = {
    "unsafe": re.compile(r"@unsafe"),
    "unsafe_sugar": re.compile(r"^\s*def\s+[\w.]+\?\s*\(", re.M),
    "hole": re.compile(r"\?[A-Za-z_][\w]*"),
    "foreign_import": re.compile(r"^\s*import\s+\"", re.M),
}


def escape_hatches(src: str) -> list[str]:
    """Strict on purpose: comments are scanned too, so generators never write '?' anywhere."""
    return sorted(k for k, rx in ESCAPE_PATTERNS.items() if rx.search(src))
