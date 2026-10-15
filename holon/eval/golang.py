"""The Go side of the renaming tool (I48 rules N1-N3): holon's own Go reader, holon/eval/goscan/main.go (go/scanner,
go/parser, go/ast; standard library only), built at run time with the pinned go into ~/.holon/eval/bin and run on the
files of a set.

The pinned go is config/holon.json replay.go_version; any other go is refused, so the facts rule N1 reads (which
identifiers a file declares, which comments it keeps) are those of one go/parser.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import common

SOURCE = Path(__file__).resolve().parent / "goscan" / "main.go"
BUILD_ENV = {"GOFLAGS": "-mod=mod", "GO111MODULE": "on", "GOTOOLCHAIN": "local", "GOWORK": "off", "GOPROXY": "off",
             "CGO_ENABLED": "0"}
_BIN: dict[str, Path] = {}


def pinned_version() -> str:
    return common.load_json(common.ROOT / "config" / "holon.json")["replay"]["go_version"]


def _go() -> str:
    go = shutil.which("go")
    if go is None:
        raise common.Refused(f"go is missing (the renaming tool reads Go files with the pinned {pinned_version()!r})")
    env = {**os.environ, **BUILD_ENV}
    got = subprocess.run([go, "version"], capture_output=True, text=True, env=env).stdout.strip()
    if got != pinned_version():
        raise common.Refused(f"go is {got!r}; the renaming tool needs the pinned {pinned_version()!r}")
    return go


def binary() -> Path:
    """The built reader for the current source (one binary per source sha256 and go version, built once)."""
    src = SOURCE.read_bytes()
    key = common.sha256_bytes(src + pinned_version().encode())[:16]
    if key in _BIN and _BIN[key].exists():
        return _BIN[key]
    out = common.HOME / "bin" / f"goscan-{key}"
    if not out.exists():
        go = _go()
        out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="holon-goscan-") as tmp:
            d = Path(tmp)
            (d / "main.go").write_bytes(src)
            env = {**os.environ, **BUILD_ENV}
            for cmd in (["mod", "init", "goscan"], ["build", "-trimpath", "-o", str(d / "goscan"), "."]):
                p = subprocess.run([go, *cmd], cwd=d, capture_output=True, text=True, env=env, timeout=900)
                if p.returncode != 0:
                    raise RuntimeError(f"go {' '.join(cmd)}: {p.stderr.strip()[:800]}")
            part = out.with_name(out.name + f".{os.getpid()}.partial")
            shutil.copyfile(d / "goscan", part)
            part.chmod(0o755)
            part.replace(out)
    else:
        _go()   # the pinned go is still the one on PATH
    _BIN[key] = out
    return out


def _run(mode: str, paths: list[Path]) -> list[dict]:
    if not paths:
        return []
    out = []
    exe = binary()
    for i in range(0, len(paths), 200):   # keep argv short
        chunk = [str(p) for p in paths[i:i + 200]]
        p = subprocess.run([str(exe), mode, *chunk], capture_output=True, timeout=1800)
        if p.returncode != 0:
            raise RuntimeError(f"goscan {mode}: {p.stderr.decode(errors='replace').strip()[:800]}")
        out += [json.loads(line) for line in p.stdout.decode("utf-8").split("\n") if line]   # one object a line
    if len(out) != len(paths):
        raise RuntimeError(f"goscan {mode}: {len(out)} results for {len(paths)} files")
    return out


def facts(paths: list[Path]) -> list[dict]:
    """goscan facts: per file its package, identifiers (offset, name, declared), literal values, comments (offset, end,
    text, kept), kept texts and cgo selector names; ok false when the file does not parse."""
    return _run("facts", paths)


def tokens(paths: list[Path]) -> list[dict]:
    """goscan tokens: per file its token stream (kept comments in place) and its cgo preamble."""
    return _run("tokens", paths)
