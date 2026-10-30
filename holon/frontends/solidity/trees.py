"""Tag-pinned source trees (rule E3 of the I69 contract, the docstring of tests_m3/test_bundle_extraction.py).

  tree(repo, commit, paths, cache=None) -> Path

A sidecar whose target commit is not the source checkout's HEAD is compiled from that commit's tree. The tree is
materialized from the source repository's own objects: a fresh repository outside both repositories (a cache
directory, default ~/.holon/cache/trees, or $HOLON_CACHE/trees) whose object store is the source repository's by
alternates, sparse to `paths`, checked out at the commit with protocol.allow=never. Nothing is fetched: in a partial
clone a blob the source repository lacks fails the checkout, which refuses (Refused, exit 2). The source repository's
refs, index, working tree and objects are never written. The result is a git checkout whose HEAD is the commit and
whose files carry no change, which is what holon.frontends.solidity.compile checks.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .. import Refused


def _env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    return env


def _git(repo, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), "-c", "protocol.allow=never", "-c", "gc.auto=0",
                           "-c", "maintenance.auto=false", *args], capture_output=True, text=True, timeout=1800,
                          env=_env(), stdin=subprocess.DEVNULL)


def cache_root() -> Path:
    return Path(os.environ.get("HOLON_CACHE") or (Path.home() / ".holon" / "cache")) / "trees"


def head(repo) -> str:
    p = _git(repo, "rev-parse", "HEAD")
    if p.returncode != 0:
        raise Refused(f"{repo} is not a git checkout: {p.stderr.strip()[:200]}")
    return p.stdout.strip()


def tree(repo, commit: str, paths: list, cache: Path | None = None) -> Path:
    """A clean checkout of `commit`, sparse to `paths`, over the source repository's objects (module docstring)."""
    repo = Path(repo)
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        raise Refused(f"{repo} is not a git repository: {common.stderr.strip()[:200]}")
    objects = Path(common.stdout.strip()) / "objects"
    t = (cache or cache_root()) / commit
    if (t / ".git").is_dir():
        h = _git(t, "rev-parse", "HEAD")
        clean = _git(t, "status", "--porcelain", "--untracked-files=all")
        if h.returncode == 0 and h.stdout.strip() == commit and clean.returncode == 0 and not clean.stdout.strip():
            return t
    shutil.rmtree(t, ignore_errors=True)
    t.parent.mkdir(parents=True, exist_ok=True)
    tmp = t.with_name(t.name + f".{os.getpid()}.part")
    shutil.rmtree(tmp, ignore_errors=True)
    p = subprocess.run(["git", "init", "-q", str(tmp)], capture_output=True, text=True, timeout=600, env=_env())
    if p.returncode != 0:
        raise Refused(f"git init {tmp}: {p.stderr.strip()[:200]}")
    (tmp / ".git" / "objects" / "info" / "alternates").write_text(str(objects) + "\n")
    for args in (["sparse-checkout", "set", "--no-cone", *[f"/{x.strip('/')}" for x in paths]],
                 ["checkout", "-q", "--detach", commit]):
        p = _git(tmp, *args)
        if p.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise Refused(f"materializing {commit} from {repo}'s objects (nothing is fetched): git {args[0]}: "
                          f"{p.stderr.strip()[:300]}")
    os.replace(tmp, t)
    return t
