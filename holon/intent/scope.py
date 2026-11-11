"""The measured scope (key I55 design S0): the .sol and .go paths that the extracted facts documents of M2 and M3 cite as
<path>:<line> at the key's scope_commit, read through git at each document's target.commit in the checkout
config/holon.json extract.sources names. The lane computes the scope itself from the facts documents."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .common import CONTROL_REPO, CONTROLS, SCOPE_DOCS, git_blobs, git_list, load_key, sha256_bytes

_CITE = re.compile(r"([A-Za-z0-9_./-]+\.(?:sol|go)):\d+")


def scope_commit(root: Path) -> str:
    return load_key(root)["thresholds"]["scope_commit"]


def sources(root: Path) -> dict:
    cfg = json.loads((root / "config" / "holon.json").read_text(encoding="utf-8"))
    return (cfg.get("extract") or {}).get("sources") or {}


def target_files(root: Path) -> tuple[dict, dict]:
    """({repo: {commit, files, unresolved}}, {(repo, path): text}) of the measured scope."""
    c = scope_commit(root)
    docs = [p for pre in SCOPE_DOCS for p in git_list(c, pre, root) if p.endswith(".extracted.json")]
    texts = git_blobs(c, docs, root)
    by: dict = {}
    for p in sorted(texts):
        raw = texts[p]
        d = json.loads(raw)
        t = d["target"]
        by.setdefault((t["repo"], t["commit"]), set()).update(_CITE.findall(raw.decode("utf-8")))
    src = sources(root)
    scope, files = {}, {}
    for (repo, commit), paths in sorted(by.items()):
        if repo not in src:
            raise RuntimeError(f"config/holon.json extract.sources has no checkout of {repo}")
        got = git_blobs(commit, sorted(paths), Path(src[repo]))
        ok = sorted(p for p, b in got.items() if b is not None)
        scope[repo] = {"commit": commit, "files": ok, "unresolved": sorted(p for p, b in got.items() if b is None)}
        for p in ok:
            files[(repo, p)] = got[p].decode("utf-8")
    return scope, files


def control_files(root: Path) -> dict:
    """{control id (the file stem, an opaque label): (repo-relative path, text)} of the pinned control sources."""
    pins = load_key(root)["thresholds"]["controls_sha256"]
    out = {}
    for p in sorted((root / CONTROLS).glob("i_*.sol")):
        rel = p.relative_to(root).as_posix()
        b = p.read_bytes()
        if pins.get(rel) != sha256_bytes(b):
            raise RuntimeError(f"{rel} is not at the bytes the key pins")
        out[p.stem] = (rel, b.decode("utf-8"))
    return out


CONTROL_REPO = CONTROL_REPO
