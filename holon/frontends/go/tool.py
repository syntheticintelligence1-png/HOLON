"""Build and run the gossa SSA dump tool and parse its output.

The tool lives in ``holon/frontends/go/tool`` (a self-contained Go module).
It is rebuilt only when its sources change; the binary is cached under
``$HOLON_CACHE/m2`` (default ``~/.holon/cache/m2``).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR = Path(__file__).resolve().parent / "tool"

DUMP_FORMAT = "gossa-dump/0.1"


class ToolError(RuntimeError):
    """gossa build or invocation failed."""


def _cache_dir() -> Path:
    base = Path(os.environ.get("HOLON_CACHE", Path.home() / ".holon" / "cache"))
    d = base / "m2"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _go() -> str:
    for cand in ("go", "/usr/local/go/bin/go"):
        p = shutil.which(cand) if "/" not in cand else (cand if Path(cand).exists() else None)
        if p:
            return p
    raise ToolError(
        "go toolchain not found on PATH; install Go 1.24.x or set PATH"
    )


def _source_hash() -> str:
    h = hashlib.sha256()
    for name in sorted(os.listdir(TOOL_DIR)):
        p = TOOL_DIR / name
        if p.is_file():
            h.update(name.encode())
            h.update(b"\0")
            h.update(p.read_bytes())
            h.update(b"\0")
    h.update(_go().encode())
    return h.hexdigest()[:16]


def build_tool() -> Path:
    """Build the gossa binary into the cache; returns its path."""
    tag = _source_hash()
    binary = _cache_dir() / f"gossa-{tag}"
    marker = binary.with_suffix(".ok")
    if binary.exists() and marker.exists():
        return binary
    env = dict(os.environ)
    env.setdefault("GOFLAGS", "-mod=mod")
    env.setdefault("GOTOOLCHAIN", "local")
    proc = subprocess.run(
        [_go(), "build", "-o", str(binary), "."],
        cwd=TOOL_DIR, env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ToolError(
            "gossa build failed\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (proc.stdout, proc.stderr)
        )
    marker.write_text("ok\n")
    return binary


def run_dump(morph_dir: Path, packages: list[str], cache: bool = True) -> dict:
    """Run gossa over ``packages`` under ``morph_dir``; returns the dump dict.

    The dump is cached per (morph_dir, packages, tool-hash) so repeated
    test runs are cheap.
    """
    binary = build_tool()
    tag = _source_hash()
    key = hashlib.sha256(
        (str(morph_dir.resolve()) + "|" + "|".join(packages)).encode()
    ).hexdigest()[:16]
    out = _cache_dir() / f"gossa-out-{tag}-{key}.json"
    if cache and out.exists():
        return json.loads(out.read_text())

    env = dict(os.environ)
    env.setdefault("GOTOOLCHAIN", "local")
    env["GO111MODULE"] = "on"
    go_bin = str(Path(_go()).resolve().parent)
    env["PATH"] = go_bin + os.pathsep + env.get("PATH", "")
    gopath = os.environ.get("GOPATH") or str(Path.home() / "go")
    env.setdefault("GOPATH", gopath)
    env.setdefault("GOCACHE", str(Path.home() / ".cache" / "go-build"))
    env.setdefault("GOMODCACHE", str(Path(gopath) / "pkg" / "mod"))
    proc = subprocess.run(
        [str(binary), "--dir", str(morph_dir)]
        + sum((["--pkg", p] for p in packages), [])
        + ["--out", str(out)],
        env=env, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise ToolError(
            "gossa run failed\nSTDOUT:\n%s\nSTDERR:\n%s"
            % (proc.stdout, proc.stderr)
        )
    return json.loads(out.read_text())
