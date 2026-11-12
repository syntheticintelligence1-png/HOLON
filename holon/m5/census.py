"""L10's census (definitions.L10.census, I54): every normative documentation clause in scope, computed mechanically,
so the intent lane's atomizer cannot set its own denominator.

  python -m holon m5 census [--root DIR] [--check]

writes results/M5/l10_census_base.json: the census of M3's scope at the I54 base. The scope is the .sol and .go paths
that the base commit's extracted facts documents (spec/M2/facts and spec/M3/facts, *.extracted.json) cite as
<path>:<line>, each read through git at its document's target.commit from the checkout config/holon.json
extract.sources names for its target.repo (never the working tree). A cited path absent there is unresolved.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .common import ROOT, dumps, git_blobs, git_list

PHRASES = ("must not", "can not", "at most", "at least", "not allowed")
WORDS = ("must", "shall", "should", "only", "cannot", "never", "always", "revert", "reverts", "reverted", "require",
         "requires", "required", "ensure", "ensures", "guarantee", "guarantees", "exactly", "invariant", "forbidden")
_MARK = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(m) for m in PHRASES + WORDS) + r")(?![a-z])")
_TAG = re.compile(r"@[A-Za-z][A-Za-z:-]*")
_DECL = re.compile(r"\s*(?:func|type|var|const)\b")
_CITE = re.compile(r"([A-Za-z0-9_./-]+\.(?:sol|go)):\d+")
_END = re.compile(r"[.;!?](?=\s|$)")


def _sol_comments(lines: list[str]):
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].lstrip()
        if s.startswith("///"):
            j = i
            while j < n and lines[j].lstrip().startswith("///"):
                j += 1
            yield i + 1, j, [x.strip()[3:].strip() for x in lines[i:j]]
            i = j
        elif s.startswith("/**"):
            first = lines[i][lines[i].index("/**") + 3:]
            j, rest = i, first
            while "*/" not in rest and j + 1 < n:
                j += 1
                rest = lines[j]
            body = []
            for k in range(i, j + 1):
                t = first if k == i else lines[k]
                t = t.split("*/", 1)[0].strip()
                if t.startswith("*"):
                    t = t[1:]
                body.append(t.strip())
            yield i + 1, j + 1, body
            i = j + 1
        else:
            i += 1


def _go_comments(lines: list[str]):
    i, n = 0, len(lines)
    while i < n:
        if not lines[i].lstrip().startswith("//"):
            i += 1
            continue
        j = i
        while j < n and lines[j].lstrip().startswith("//"):
            j += 1
        if j < n and _DECL.match(lines[j]):
            yield i + 1, j, [x.strip()[2:].strip() for x in lines[i:j]]
        i = j


def _segments(body: list[str]) -> list[str]:
    segs, cur = [], []
    for ln in body:
        if ln == "" or _TAG.match(ln):
            if cur:
                segs.append(cur)
            cur = [ln] if ln else []
        else:
            cur.append(ln)
    if cur:
        segs.append(cur)
    return [" ".join(" ".join(s).split()) for s in segs]


def _split(seg: str) -> list[str]:
    out, start = [], 0
    for m in _END.finditer(seg):
        piece = seg[start:m.end()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    tail = seg[start:].strip()
    if tail:
        out.append(tail)
    return out


def census_of(path: str, text: str) -> list[dict]:
    lines = text.split("\n")
    if path.endswith(".sol"):
        groups = _sol_comments(lines)
    elif path.endswith(".go"):
        groups = _go_comments(lines)
    else:
        return []
    out = []
    for first, last, body in groups:
        for seg in _segments(body):
            m = _TAG.match(seg)
            tag = m.group(0) if m else None
            for s in _split(seg):
                if _MARK.search(s.lower()):
                    cid = hashlib.sha256(f"{path}:{first}:{s}".encode("utf-8")).hexdigest()[:16]
                    out.append({"id": cid, "file": path, "lines": [first, last], "text": s, "tag": tag})
    return out


def base_census(root: Path = ROOT, commit: str | None = None) -> dict:
    from .definitions import base_commit
    root = Path(root)
    commit = commit or base_commit(root)
    docs = [p for m in ("M2", "M3") for p in git_list(root, commit, f"spec/{m}/facts/") if p.endswith(".extracted.json")]
    texts = git_blobs(root, commit, docs)
    sources = json.loads((root / "config" / "holon.json").read_text(encoding="utf-8"))["extract"]["sources"]
    scope: dict[tuple[str, str], set] = {}
    for p in sorted(texts):
        doc = json.loads(texts[p])
        t = doc["target"]
        scope.setdefault((t["repo"], t["commit"]), set()).update(_CITE.findall(texts[p].decode("utf-8")))
    repos, clauses = {}, []
    for (repo, c), paths in sorted(scope.items()):
        checkout = Path(sources[repo])
        if not (checkout / ".git").exists():
            raise FileNotFoundError(f"the checkout of {repo} ({checkout}) is missing: the census needs it")
        got = git_blobs(checkout, c, sorted(paths))
        ok = sorted(p for p in got if got[p] is not None)
        repos[repo] = {"commit": c, "files": ok, "unresolved": sorted(p for p in got if got[p] is None)}
        for p in ok:
            clauses.extend(census_of(p, got[p].decode("utf-8")))
    clauses.sort(key=lambda x: (x["file"], x["lines"], x["id"]))
    return {"repos": repos, "clauses": clauses}


def path(root: Path = ROOT) -> Path:
    return Path(root) / "results" / "M5" / "l10_census_base.json"


def write(root: Path = ROOT, check: bool = False) -> list[str]:
    text = dumps(base_census(root))
    p = path(root)
    have = p.read_text(encoding="utf-8") if p.is_file() else None
    if check:
        return [] if have == text else [f"{p.relative_to(root)}: differs from the census (python -m holon m5 census)"]
    if have != text:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return [p.relative_to(root).as_posix()]
    return []
