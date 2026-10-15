"""Shared helpers of holon.eval (I48): paths, the frozen sidecars, canonical JSON, and git through holon's own partial
clones (~/.holon/eval/repos; the instrument keeps separate clones, so the two never share a fetched object).

Rule C0: an excluded repository (the sealed held-out target and the development target, corpus_protocol.json
excluded_repos) is never cloned, fetched or read, and a clone that git reports redirected to one is refused.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "spec" / "M4" / "lib"
EVAL = ROOT / "spec" / "eval"
GEN = ROOT / "gen" / "eval"
HOME = Path(os.environ.get("HOLON_EVAL_HOME") or Path.home() / ".holon" / "eval")
REPOS = HOME / "repos"

GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "TZ": "UTC", "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0",
           "GIT_LITERAL_PATHSPECS": "1"}


class Refused(Exception):
    """A request the tool refuses (exit 2): a missing input, an excluded repository, an unsupported language."""


def dumps(obj) -> str:
    """The repo's canonical JSON file format."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(p) -> str:
    return sha256_bytes(Path(p).read_bytes())


def protocol() -> dict:
    return load_json(LIB / "corpus_protocol.json")


def write_or_check(path: Path, text: str, check: bool) -> bool:
    """Write text to path (creating directories), or with check compare only. Returns True when the file differs."""
    path = Path(path)
    old = path.read_bytes() if path.exists() else None
    differs = old != text.encode("utf-8")
    if differs and not check:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    return differs


def git_env() -> dict:
    return {**os.environ, **GIT_ENV}


def git(d, *args: str, check: bool = True, text: bool = True, timeout: int = 3600):
    """git -C d ARGS; its stdout. A failure raises RuntimeError with git's message."""
    p = subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=text, timeout=timeout, env=git_env())
    if check and p.returncode != 0:
        err = p.stderr if text else p.stderr.decode(errors="replace")
        raise RuntimeError(f"git {' '.join(args)} in {d}: {err.strip()[:500]}")
    _no_excluded_redirect(p.stderr if text else p.stderr.decode(errors="replace"))
    return p.stdout


def excluded(url, proto: dict | None = None) -> bool:
    """Rule C0: the URL lies under an excluded_repos pattern (case-insensitive)."""
    if not url:
        return False
    p = proto or protocol()
    return any(x["pattern"].lower() in str(url).lower() for x in p["excluded_repos"])


def _no_excluded_redirect(stderr: str) -> None:
    for m in re.finditer(r"redirecting to (\S+)", stderr or ""):
        if excluded(m.group(1)):
            raise Refused(f"git was redirected to an excluded repository ({m.group(1)}): refused")


_GH = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?")


def gh_slug(url: str) -> tuple[str, str]:
    """(owner, repo) of a GitHub repository URL; anything else is refused."""
    m = _GH.fullmatch(url or "")
    if not m:
        raise Refused(f"not a GitHub repository URL: {url}")
    return m.group(1), m.group(2)


def repo_cache(url: str, root: Path | None = None) -> Path:
    """holon's partial bare clone of a public GitHub repository (blobs fetched on demand), created when missing.
    Every branch and tag is fetched; nothing is ever fetched by sha here."""
    if excluded(url):
        raise Refused(f"{url} is an excluded repository (protocol excluded_repos): never cloned")
    owner, name = gh_slug(url)
    d = (root or REPOS) / f"{owner}__{name}.git"
    if not (d / "HEAD").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        tmp = d.with_name(d.name + ".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        p = subprocess.run(["git", "clone", "--bare", "--filter=blob:none", "--no-progress", url, str(tmp)],
                           capture_output=True, text=True, timeout=7200, env=git_env())
        _no_excluded_redirect(p.stderr)
        if p.returncode != 0:
            raise RuntimeError(f"git clone {url}: {p.stderr.strip()[:500]}")
        tmp.rename(d)
    return d


_REACH: dict[str, set] = {}


def reachable(d: Path, refresh: bool = False) -> set:
    """Every commit reachable from a branch or a tag of the clone (refreshing the refs from the remote on request)."""
    key = str(d)
    if refresh or key not in _REACH:
        if refresh:
            git(d, "fetch", "--no-progress", "--prune", "--filter=blob:none", "origin",
                "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", timeout=7200)
        _REACH[key] = set(git(d, "rev-list", "--branches", "--tags").split())
    return _REACH[key]


def is_reachable(url: str, sha: str | None) -> bool:
    """Rule C2b: sha (40 hex) is reachable from a branch or tag of the public repository, decided from rev-list alone;
    the refs are fetched again once when it is not there."""
    if not sha or not re.fullmatch(r"[0-9a-f]{40}", sha):
        return False
    d = repo_cache(url)
    return sha in reachable(d) or sha in reachable(d, refresh=True)
