"""I47 instruments (target-agnostic factory, parallel checking, performance loop, drift trigger).

Pinned by sha256 in tests_m4/test_i47_factory.py. Nothing here imports holon/: the tests run holon as a subprocess
(`python -m holon ...`) in copies of the repo, and these helpers only build inputs and read outputs.

  BASE              the lead commit I47 starts from (4fd64a52). The regressions compare HEAD against it.
  upstream_repo     a deterministic local git upstream for the toy target (fixed author, committer and dates), so a
                    commit's sha is a function of its content and its parent only
  closures          runs tests_m4/_i47_probe.py on a tree: every generator_sha256 digest and the record-pinned files
  export_tree       `git archive` of a commit's holon/ and spec/ into a fresh directory (read only on the repo)
  target_names      the identity names every targets/<name>/target.json declares (its "names")
  prereg_commit     C_K: the first commit that adds spec/M4/predictions/I47.json
  exit_commit       I47's exit: the first commit on HEAD's first-parent chain after C_K that adds docs/iterations/I47.md
                    (HEAD while there is none). Claims about the tree (R1, the residue, the scan) are evaluated at
                    the exit, so a later iteration's legitimate edit does not turn I47's tests red
  i47_commits       the non-merge commits of I47 itself: HEAD's first-parent chain from C_K to the exit
  scan              the target-agnostic scan: every holon/ file whose code (comments and docstrings removed, as
                    tests_m2/test_target_agnostic_exhaustive.py does) names a declared target, case-insensitively,
                    bounded by non-alphanumerics (so morph_commit, replay.morph and --morph all count)
  normalized_tree   a run's output tree with every key named "seconds" removed from its JSON files (G1's
                    normalization, holon.gate.Gate.norm_records); every other byte compared as is
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import tokenize
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "4fd64a52f030438cac06595f8673840d6c5c6525"
FIXTURE = ROOT / "tests_m4" / "fixtures" / "i47_abacus"
PROBE = ROOT / "tests_m4" / "_i47_probe.py"

GIT_ENV = {"GIT_AUTHOR_NAME": "holon-fixture", "GIT_AUTHOR_EMAIL": "fixture@holon.invalid",
           "GIT_COMMITTER_NAME": "holon-fixture", "GIT_COMMITTER_EMAIL": "fixture@holon.invalid",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "TZ": "UTC"}


def git(cwd: Path, *args: str, env_extra: dict | None = None) -> str:
    env = {**os.environ, **GIT_ENV, **(env_extra or {})}
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr}")
    return p.stdout.strip()


def upstream_repo(where: Path, versions: list[str]) -> dict[str, str]:
    """A git repository at `where` with one commit per version in `versions` (each the directory
    FIXTURE/upstream_<version>, copied to the root of the tree), each tagged <version> (a lightweight tag), on branch
    main. Dates are fixed (version i at 2026-01-01T00:00:0i Z), so the shas depend only on the content. Returns
    {version: commit sha}."""
    where.mkdir(parents=True, exist_ok=True)
    git(where, "init", "-q", "-b", "main")
    out = {}
    for i, v in enumerate(versions):
        for f in sorted(where.iterdir()):
            if f.name != ".git":
                f.unlink()
        for f in sorted((FIXTURE / f"upstream_{v}").iterdir()):
            (where / f.name).write_bytes(f.read_bytes())
        date = f"2026-01-01T00:00:0{i}Z"
        git(where, "add", "-A")
        git(where, "commit", "-q", "-m", f"abacus {v}", env_extra={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date})
        git(where, "tag", v)
        out[v] = git(where, "rev-parse", "HEAD")
    return out


def prereg_commit() -> str:
    out = git(ROOT, "log", "--format=%H", "--diff-filter=A", "--topo-order", "--reverse", "--",
              "spec/M4/predictions/I47.json").split()
    if not out:
        raise RuntimeError("no commit adds spec/M4/predictions/I47.json")
    return out[0]


def exit_commit() -> str:
    ck = prereg_commit()
    chain = git(ROOT, "rev-list", "--first-parent", "--reverse", f"{ck}..HEAD").split()
    for c in chain:
        files = git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "--diff-filter=A", "-r", f"{c}^", c).split()
        if "docs/iterations/I47.md" in files:
            return c
    return git(ROOT, "rev-parse", "HEAD")


def i47_commits() -> list[tuple[str, list[str]]]:
    """(commit, its parents) for HEAD's first-parent chain from C_K (included) to the exit (included), oldest first."""
    ck, ex = prereg_commit(), exit_commit()
    out = []
    for ln in git(ROOT, "rev-list", "--first-parent", "--reverse", "--parents", f"{ck}^..{ex}").splitlines():
        c, *ps = ln.split()
        out.append((c, ps))
    return out


def changed_files(c: str, parent: str) -> list[str]:
    return git(ROOT, "diff-tree", "--no-commit-id", "--name-only", "-r", parent, c).splitlines()


def export_tree(commit: str, paths: list[str]) -> Path:
    d = Path(tempfile.mkdtemp(prefix="holon-i47-tree-"))
    data = subprocess.run(["git", "archive", "--format=tar", commit, *paths], cwd=ROOT, capture_output=True,
                          check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(d, filter="data")
    return d


def closures(tree: Path) -> dict:
    p = subprocess.run([sys.executable, "-I", str(PROBE), str(tree)], cwd=tree, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-3000:])
    return json.loads(p.stdout)


def target_names(root: Path = ROOT) -> dict[str, list[str]]:
    out = {}
    for f in sorted((root / "targets").glob("*/target.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["name"]] = sorted(set(d.get("names", [])) | {d["name"]})
    return out


def _code_py(text: str) -> str:
    """Python source without comments and docstrings (the form of tests_m2/test_target_agnostic_exhaustive.code_py)."""
    lines = text.splitlines(keepends=True)
    drop: set = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                drop |= set(range(first.lineno - 1, first.end_lineno))
    src = "".join("\n" if i in drop else line for i, line in enumerate(lines))
    toks = [t for t in tokenize.generate_tokens(io.StringIO(src).readline) if t.type != tokenize.COMMENT]
    return tokenize.untokenize(toks)


def _code_c_like(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"(?<![:\\])//[^\n]*", "", text)


def name_pattern(names) -> re.Pattern:
    alts = "|".join(sorted(map(re.escape, names), key=len, reverse=True))
    return re.compile(r"(?<![A-Za-z0-9])(" + alts + r")(?![A-Za-z0-9])", re.I)


def scan(root: Path, names) -> dict[str, list[str]]:
    """{repo-relative file: sorted distinct matches} for every file under root/holon whose path or code names one of names.
    .py files: code without comments and docstrings; .mjs, .js, .go: without // and /* */ comments; every other text
    file (json, mod, sum, ...): whole. Binary files and __pycache__ are skipped."""
    pat = name_pattern(names)
    out = {}
    for f in sorted((root / "holon").rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts or f.suffix in (".pyc",):
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if f.suffix == ".py":
            code = _code_py(text)
        elif f.suffix in (".mjs", ".js", ".go"):
            code = _code_c_like(text)
        else:
            code = text
        rel = f.relative_to(root).as_posix()
        hits = pat.findall(rel + "\n" + code)   # the file's own path counts (holon/<name>_x.py names a target)
        if hits:
            out[rel] = sorted(set(hits))
    return out


def _strip_seconds(x):
    if isinstance(x, dict):
        return {k: _strip_seconds(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_strip_seconds(v) for v in x]
    return x


def normalized_tree(d: Path) -> dict[str, str]:
    """{relative path: sha256} of every file under d; JSON files hashed after removing every "seconds" key and
    re-dumping canonically, every other file as its bytes."""
    out = {}
    for f in sorted(d.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        b = f.read_bytes()
        if f.suffix == ".json":
            try:
                b = json.dumps(_strip_seconds(json.loads(b)), sort_keys=True, separators=(",", ":")).encode()
            except ValueError:
                pass
        out[f.relative_to(d).as_posix()] = hashlib.sha256(b).hexdigest()
    return out
