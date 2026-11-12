"""Shared helpers of the intent lane: paths, the canonical file format, hashing, names and read-only git."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY = "I55"
SCOPE_DOCS = ("spec/M2/facts/", "spec/M3/facts/")
CONTROLS = "spec/M5/controls/intent"
CONTROL_REPO = "holon-controls"
OUT = "results/M5/intent"
GEN = "gen/M5/intent"
LAWS = "laws/INTENT"
COMPILER = "holon.intent.compile"


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def norm(s) -> str:
    """A name normalized for binding: lower case, every non-alphanumeric removed."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def load_key(root: Path) -> dict:
    return json.loads((root / "spec" / "M5" / "predictions" / f"{KEY}.json").read_text(encoding="utf-8"))


def git(args: list[str], cwd: Path, data: bytes | None = None) -> bytes:
    r = subprocess.run(["git", *args], cwd=cwd, input=data, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {cwd}: {r.stderr.decode('utf-8', 'replace').strip()[:300]}")
    return r.stdout


def git_list(commit: str, prefix: str, cwd: Path) -> list[str]:
    out = git(["ls-tree", "-r", "--name-only", commit, "--", prefix], cwd).decode("utf-8")
    return sorted(p for p in out.split("\n") if p)


def git_blobs(commit: str, paths: list[str], cwd: Path) -> dict:
    """{path: bytes or None (absent)} of paths at commit, one `git cat-file --batch` call."""
    if not paths:
        return {}
    raw = git(["cat-file", "--batch"], cwd, "".join(f"{commit}:{p}\n" for p in paths).encode("utf-8"))
    out, i = {}, 0
    for p in paths:
        nl = raw.index(b"\n", i)
        head = raw[i:nl].decode("utf-8")
        if head.endswith(" missing"):
            out[p], i = None, nl + 1
            continue
        size = int(head.split()[2])
        out[p] = raw[nl + 1:nl + 1 + size]
        i = nl + 1 + size + 1
    return out


def write_or_check(files: dict, check: bool) -> list[str]:
    """files: {Path: text}. Writes them (returns the paths written), or with check returns the paths that differ."""
    out = []
    for p, text in sorted(files.items(), key=lambda kv: str(kv[0])):
        p = Path(p)
        if check:
            if not p.is_file() or p.read_text(encoding="utf-8") != text:
                out.append(str(p))
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            out.append(str(p))
    return out
