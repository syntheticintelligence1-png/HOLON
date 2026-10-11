"""Preregistration audit (docs/BUILD_PLAN.md 0.1): ``python -m holon audit prereg --milestone M2 [--root PATH]``.

The audit reads git history and nothing else (``rev-parse``, ``rev-list``, ``cat-file``, ``diff-tree``,
``status``; it never writes to the repository, its index or its config). It audits the committed tree at HEAD
only. Uncommitted edits are ignored, with one exception: a working-tree change to ``spec/<M>/predictions.json``
is itself a failure, so a passing audit always describes the predictions file on disk.

What is checked, for every iteration key K that appears in any committed version of
``spec/<M>/predictions.json`` reachable from HEAD:

1. Prereg commit. C_K is the first commit, oldest first in topological order, whose version of the file holds K.
2. Immutability. K's value at HEAD equals its value at C_K, compared as canonical JSON: key order and
   whitespace do not matter, but ``true`` is not ``1`` and ``1`` is not ``1.0``. A key removed at HEAD fails.
3. Order. C_K changes no file under K's ``outcome_paths``. An outcome path is a literal prefix of a
   repo-relative path: ``results/M2/`` covers that directory, ``replay/M0/report.json`` that file. Outcome
   paths must be plain relative paths (no globs, ``.`` or ``..``). In addition, every commit reachable from
   HEAD but not from C_K that changes an outcome path must descend from C_K: an outcome written on a
   parallel branch and merged later did not come after the prereg.
4. Tests. Each file in K's ``tests`` exists at C_K and holds at least one test function there. Every tracked
   function present at C_K is unchanged at HEAD; new functions may be added. Tracked functions are those whose
   name starts with ``test`` plus the unittest fixtures (``setUp``, ``setUpClass``, ``setUpModule``,
   ``load_tests``, ...), at module level (key ``func``) or in a module-level class (key ``Class.func``). A
   function's fingerprint is its source lines including its decorators (so an added ``@skip`` counts),
   trailing whitespace stripped; for a method, also its class's decorators, bases and keywords; and how many
   times the name is bound in its scope (a later redefinition shadows the original).
5. Amendments. A changed or removed function is not a failure when ``spec/<M>/amendments.jsonl`` at HEAD
   holds a line ``{"iteration": K, "test": "<file>::<func or Class.func>", "why": "..."}`` for it; it is
   printed as amended, to be reported under Surprises. The file is append-only: every line of every committed
   version must still be present at HEAD.

Missing history (no repository at ROOT, no commit, a shallow clone) is a failure, never a skip. A
predictions file with no iteration keys is a failure too: an audit of nothing proves nothing. Exit status
is 0 iff nothing failed; output is deterministic (sorted keys, fixed 12-character shas, no timestamps).

Residual risk, stated plainly:
- Local runs made before a prereg commit cannot be detected. The audit sees commits, not experiments.
- Order is commit topology, not wall-clock time. Unpushed history can be rewritten; the pushed remote
  timeline is the only external witness.
- This tool, the predictions file, the amendments file and the tests are agent-writable until the human
  freezes them (BUILD_PLAN 0.3, Q1). Until then the protocol is self-certified, and the audit prints which
  of those files are not listed in FROZEN.sha256.
- Only tracked functions are fingerprinted. Helpers, module constants, class attributes, other methods and
  imported modules (e.g. ``tests_m2/_m2.py``) can change what a test does without being reported.
- An amendment licenses every later change to the function it names.
- A merge commit on a parallel branch is not inspected for outcome changes of its own (an "evil merge").
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = "holon/audit/prereg.py"
SHA = 12  # fixed abbreviation: `git rev-parse --short` grows with the object count
FIXTURES = frozenset({"setUp", "tearDown", "setUpClass", "tearDownClass", "asyncSetUp", "asyncTearDown",
                      "setUpModule", "tearDownModule", "load_tests"})
_MILESTONE = re.compile(r"^M[0-9]+$")
_GLOB_CHARS = frozenset("*?[")
_FP_WHAT = {"source": "source", "class": "class decorators or bases", "class_bindings": "class name rebound",
            "bindings": "name rebound in its scope", "star": "star import added or removed"}


class Fatal(Exception):
    """The audit cannot run at all."""


# ------------------------------------------------------------------ git, read-only
class Git:
    def __init__(self, root: Path):
        self.root = root
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # no GIT_DIR redirection
        env.update(GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")  # status must not write the index
        self.env = env

    def run(self, *args: str) -> subprocess.CompletedProcess:
        cmd = ["git", "-C", str(self.root), "-c", "core.fsmonitor=false", "-c", "core.quotepath=off", *args]
        try:
            return subprocess.run(cmd, capture_output=True, env=self.env, stdin=subprocess.DEVNULL)
        except OSError as e:
            raise Fatal(f"cannot run git: {e}") from None

    def out(self, *args: str) -> str:
        p = self.run(*args)
        if p.returncode != 0:
            raise Fatal(f"git {' '.join(args)} failed: {p.stderr.decode(errors='replace').strip()}")
        return p.stdout.decode("utf-8", "surrogateescape")

    def blob(self, rev: str, path: str) -> bytes | None:
        p = self.run("cat-file", "blob", f"{rev}:{path}")
        return p.stdout if p.returncode == 0 else None

    def commits(self, *args: str) -> list[str]:
        return self.out("rev-list", *args).split()

    def changed(self, commit: str, merges: bool) -> set[str]:
        """Files a commit changes. A root commit adds everything; with merges=True a merge counts the union over
        its parents, otherwise a merge contributes nothing of its own."""
        args = ["diff-tree", "-r", "--root", "--no-commit-id", "--name-only", "--no-renames", "-z"]
        out = self.out(*args, *(["-m"] if merges else []), commit)
        return {f for f in out.split("\0") if f}


def preflight(git: Git, root: Path) -> str:
    p = git.run("rev-parse", "--show-toplevel")
    if p.returncode != 0:
        raise Fatal(f"no git history at {root}: {p.stderr.decode(errors='replace').strip()}")
    top = Path(p.stdout.decode("utf-8", "surrogateescape").strip()).resolve()
    if top != root:
        raise Fatal(f"{root} is not the top of a git checkout (git found {top})")
    p = git.run("rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if p.returncode != 0:
        raise Fatal(f"no git history at {root}: HEAD names no commit")
    if git.out("rev-parse", "--is-shallow-repository").strip() == "true":
        raise Fatal(f"{root} is a shallow clone: its history is incomplete (git fetch --unshallow)")
    return p.stdout.decode().strip()


# ------------------------------------------------------------------ JSON
def _no_duplicates(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError(f"duplicate key {k!r}")
        d[k] = v
    return d


def parse_json(data: bytes | str):
    """Strict JSON: UTF-8, and a duplicated object key is an error (json.loads would silently keep the last)."""
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    return json.loads(text, object_pairs_hook=_no_duplicates)


def canon(v) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def iterations_of(doc) -> dict | None:
    its = doc.get("iterations") if isinstance(doc, dict) else None
    return its if isinstance(its, dict) else None


# ------------------------------------------------------------------ paths
def bad_path(p) -> str | None:
    if not isinstance(p, str) or not p:
        return "is not a non-empty string"
    if p.startswith("/") or "\\" in p:
        return "is not repo-relative"
    if any(seg in ("", ".", "..") for seg in p.rstrip("/").split("/")):
        return "has an empty, '.' or '..' segment"
    if _GLOB_CHARS & set(p):
        return "is a glob (outcome paths are literal prefixes)"
    return None


def natural(k: str) -> list:
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", k)]


def plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


# ------------------------------------------------------------------ test fingerprints
def tracked(name: str) -> bool:
    return name.startswith("test") or name in FIXTURES


def _bindings(stmts: list[ast.stmt]) -> Counter:
    """How many times each name is bound or deleted directly in this scope (nested scopes are skipped)."""
    c: Counter = Counter()
    todo: list[ast.AST] = list(stmts)
    while todo:
        n = todo.pop()
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            c[n.name] += 1
            continue
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            continue
        if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
            c[n.id] += 1
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                c[a.asname or a.name.split(".")[0]] += 1  # `from x import *` counts under "*"
        elif isinstance(n, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and n.name:
            c[n.name] += 1
        elif isinstance(n, ast.MatchMapping) and n.rest:
            c[n.rest] += 1
        todo.extend(ast.iter_child_nodes(n))
    return c


def _segment(lines: list[str], node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    start = min([d.lineno for d in node.decorator_list] + [node.lineno])
    return "\n".join(line.rstrip() for line in lines[start - 1:node.end_lineno])


def _class_header(node: ast.ClassDef) -> str:
    return canon({"decorators": [ast.dump(d) for d in node.decorator_list],
                  "bases": [ast.dump(b) for b in node.bases],
                  "keywords": [ast.dump(k) for k in node.keywords],
                  "type_params": [ast.dump(t) for t in getattr(node, "type_params", [])]})


def fingerprints(source: str) -> dict[str, dict]:
    """Tracked function key ("func" or "Class.func") -> fingerprint. Raises SyntaxError/ValueError."""
    tree = ast.parse(source)
    lines = re.split(r"\r\n|\r|\n", source)  # the line breaks ast counts (str.splitlines also splits on \f etc.)
    mod = _bindings(tree.body)
    star = mod.get("*", 0)
    fps: dict[str, dict] = {}
    funcs = (ast.FunctionDef, ast.AsyncFunctionDef)
    for node in tree.body:
        if isinstance(node, funcs) and tracked(node.name):
            fp = fps.setdefault(node.name, {"source": [], "bindings": mod[node.name], "star": star})
            fp["source"].append(_segment(lines, node))
        elif isinstance(node, ast.ClassDef):
            inner = _bindings(node.body)
            for sub in node.body:
                if isinstance(sub, funcs) and tracked(sub.name):
                    fp = fps.setdefault(f"{node.name}.{sub.name}", {"class": [], "class_bindings": mod[node.name],
                                                                     "source": [], "bindings": 0, "star": star})
                    fp["class"].append(_class_header(node))
                    fp["source"].append(_segment(lines, sub))
                    fp["bindings"] += inner[sub.name]
    return fps


# ------------------------------------------------------------------ amendments
def load_amendments(git: Git, head: str, path: str) -> tuple[dict[tuple[str, str], list[str]], list[str]]:
    """(iteration, "file::name") -> reasons, from HEAD; plus problems (malformed lines, broken append-only)."""
    amend: dict[tuple[str, str], list[str]] = {}
    problems: list[str] = []
    data = git.blob(head, path)
    if data is None:
        return amend, problems
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        return amend, [f"{path} at HEAD is not UTF-8: {e}"]
    for i, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            obj = parse_json(line)
        except ValueError as e:
            problems.append(f"{path} line {i} is not JSON: {e}")
            continue
        ok = (isinstance(obj, dict) and isinstance(obj.get("iteration"), str) and isinstance(obj.get("test"), str)
              and "::" in obj["test"] and isinstance(obj.get("why"), str) and obj["why"].strip())
        if not ok:
            problems.append(f"{path} line {i} needs string fields iteration, test (\"file::name\") and a non-empty why")
            continue
        amend.setdefault((obj["iteration"], obj["test"]), []).append(obj["why"].strip())
    head_lines = {ln.rstrip() for ln in text.split("\n") if ln.strip()}
    seen: set[str] = set()
    for c in git.commits("--full-history", "--topo-order", "--reverse", head, "--", path):
        old = git.blob(c, path)
        for ln in (old or b"").decode("utf-8", "replace").split("\n"):
            ln = ln.rstrip()
            if ln and ln not in head_lines and ln not in seen:
                seen.add(ln)
                problems.append(f"{path} is append-only, but a line committed in {c[:SHA]} is gone at HEAD: {ln[:120]}")
    return amend, problems


def frozen_paths(git: Git, head: str) -> set[str]:
    data = git.blob(head, "FROZEN.sha256") or b""
    out = set()
    for line in data.decode("utf-8", "replace").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            out.add(parts[1].strip())
    return out


# ------------------------------------------------------------------ the audit
def audit_key(git: Git, head: str, k: str, intro: tuple[str, object, list[str]] | None, head_its: dict,
              amend: dict, pred: str) -> tuple[str, list[str], list[str], list[str]]:
    """-> (summary line, problems, notes, test files)."""
    if intro is None:
        return f"{k}: FAIL", [f"{k}: no commit reachable from HEAD introduces the key"], [], []
    c, v0, unparsed = intro
    cs = c[:SHA]
    probs: list[str] = [f"{k}: {pred} at {u} does not parse, so the prereg commit is uncertain" for u in unparsed]
    notes: list[str] = []

    # immutability
    if k not in head_its:
        probs.append(f"{k}: key removed after its prereg commit {cs} (a prereg key is never edited or removed)")
    elif canon(head_its[k]) != canon(v0):
        v1 = head_its[k]
        fields = ""
        if isinstance(v0, dict) and isinstance(v1, dict):
            diff = sorted(f for f in set(v0) | set(v1) if canon(v0.get(f)) != canon(v1.get(f)) or (f in v0) != (f in v1))
            fields = f" (fields: {', '.join(diff)})"
        probs.append(f"{k}: key edited after its prereg commit {cs}{fields}")
    if not isinstance(v0, dict):
        probs.append(f"{k}: value at the prereg commit {cs} is not an object")
        return f"{k}: FAIL prereg {cs}", probs, notes, []

    # the preregistered contract is the value at C_K (HEAD's may have been edited)
    ops, tests = v0.get("outcome_paths"), v0.get("tests")
    if not isinstance(ops, list) or not ops:
        probs.append(f"{k}: outcome_paths at the prereg commit {cs} is not a non-empty list")
        ops = []
    if not isinstance(tests, list) or not tests:
        probs.append(f"{k}: tests at the prereg commit {cs} is not a non-empty list")
        tests = []
    good_ops = []
    for p in ops:
        why = bad_path(p)
        if why:
            probs.append(f"{k}: outcome path {p!r} {why}")
        else:
            good_ops.append(p)
    good_tests = []
    for f in tests:
        why = bad_path(f)
        if why or not str(f).endswith(".py"):
            probs.append(f"{k}: test file {f!r} {why or 'is not a .py file'}")
        else:
            good_tests.append(f)

    # order: the prereg commit itself
    changed = git.changed(c, merges=True)
    for p in good_ops:
        hit = sorted(f for f in changed if f.startswith(p))
        if hit:
            more = f" and {len(hit) - 1} more" if len(hit) > 1 else ""
            probs.append(f"{k}: prereg commit {cs} also changes outcome path {p} ({hit[0]}{more})")
    # order: outcome commits on branches parallel to the prereg commit
    if good_ops and c != head:
        after = set(git.commits("--ancestry-path", f"{c}..{head}"))
        for x in git.commits("--topo-order", "--reverse", head, f"^{c}"):
            if x in after:
                continue
            ch = git.changed(x, merges=False)
            for p in good_ops:
                hit = sorted(f for f in ch if f.startswith(p))
                if hit:
                    probs.append(f"{k}: commit {x[:SHA]} changes outcome path {p} ({hit[0]}) but does not descend "
                                 f"from the prereg commit {cs}")

    # tests
    nfun = 0
    for f in good_tests:
        old = git.blob(c, f)
        if old is None:
            probs.append(f"{k}: test file {f} is missing at the prereg commit {cs}")
            continue
        try:
            fp0 = fingerprints(old.decode("utf-8"))
        except (SyntaxError, ValueError) as e:
            probs.append(f"{k}: test file {f} does not parse at the prereg commit {cs}: {e}")
            continue
        if not fp0:
            probs.append(f"{k}: test file {f} has no test functions at the prereg commit {cs}")
            continue
        nfun += len(fp0)
        new = git.blob(head, f)
        fp1: dict[str, dict] = {}
        if new is not None:
            try:
                fp1 = fingerprints(new.decode("utf-8"))
            except (SyntaxError, ValueError) as e:
                probs.append(f"{k}: test file {f} does not parse at HEAD: {e}")
                continue
        for name in sorted(fp0, key=natural):
            if fp1.get(name) == fp0[name]:
                continue
            if name not in fp1:
                what = "removed at HEAD" if new is not None else "file removed at HEAD"
            else:
                what = "differs in " + ", ".join(_FP_WHAT[x] for x in _FP_WHAT if fp0[name].get(x) != fp1[name].get(x))
            tid = f"{f}::{name}"
            whys = amend.get((k, tid))
            if whys:
                notes.append(f"{k}: test {tid} amended: {'; '.join(whys)}")
            else:
                probs.append(f"{k}: test {tid} changed after the prereg commit {cs} ({what})")

    counts = f"({plural(len(ops), 'outcome path')}, {plural(len(tests), 'test file')}, {plural(nfun, 'tracked function')})"
    return f"{k}: {'FAIL' if probs else 'OK'} prereg {cs} {counts}", probs, notes, good_tests


def run_audit(root: Path, m: str) -> tuple[list[str], bool]:
    git = Git(root)
    head = preflight(git, root)
    pred, amend_path = f"spec/{m}/predictions.json", f"spec/{m}/amendments.jsonl"
    out = [f"prereg audit: milestone {m}, HEAD {head[:SHA]} (committed tree only)"]
    glob: list[str] = []

    if git.out("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", pred).strip("\0"):
        glob.append(f"uncommitted change to {pred} (the audit checks HEAD only: commit or revert it)")

    head_blob = git.blob(head, pred)
    if head_blob is None:
        raise Fatal(f"{pred} does not exist at HEAD {head[:SHA]}")
    try:
        head_doc = parse_json(head_blob)
    except ValueError as e:
        raise Fatal(f"{pred} at HEAD does not parse: {e}") from None
    head_its = iterations_of(head_doc)
    if head_its is None:
        raise Fatal(f"{pred} at HEAD has no 'iterations' object")
    if head_doc.get("milestone") != m:
        glob.append(f"{pred} says milestone {head_doc.get('milestone')!r}, expected {m!r}")

    # C_K for every key that ever appeared, oldest version first
    intro: dict[str, tuple[str, object, list[str]]] = {}
    unparsed: list[str] = []
    for c in git.commits("--full-history", "--topo-order", "--reverse", head, "--", pred):
        data = git.blob(c, pred)
        if data is None:  # the file is deleted in c
            continue
        try:
            its = iterations_of(parse_json(data)) or {}
        except ValueError as e:
            unparsed.append(f"{c[:SHA]} ({e})")
            continue
        for k, v in its.items():
            intro.setdefault(k, (c, v, list(unparsed)))
    keys = sorted(set(head_its) | set(intro), key=natural)
    if not keys:
        raise Fatal(f"{pred} has no iteration keys at HEAD or in its history: nothing to audit")

    amend, aprobs = load_amendments(git, head, amend_path)
    glob.extend(aprobs)
    out.extend(f"prereg: FAIL {p}" for p in glob)

    nfail = len(glob)
    test_files: set[str] = set()
    for k in keys:
        summary, probs, notes, files = audit_key(git, head, k, intro.get(k), head_its, amend, pred)
        test_files.update(files)
        out.append(summary)
        out.extend(f"  {line}" for line in probs + notes)
        nfail += len(probs)

    frozen = frozen_paths(git, head)
    loose = [p for p in (TOOL_PATH, pred) if p not in frozen]
    nloose = sum(1 for f in test_files if f not in frozen)
    if nloose:
        loose.append(plural(nloose, "test file"))
    if git.blob(head, amend_path) is not None and amend_path not in frozen:
        loose.append(amend_path)
    if loose:
        out.append(f"note: self-certified until the human freezes them (BUILD_PLAN 0.1, Q1); not in FROZEN.sha256 "
                   f"at HEAD: {', '.join(loose)}")
    out.append("note: local runs made before a prereg commit cannot be detected")
    out.append("PREREG OK" if nfail == 0 else "PREREG FAILED")
    return out, nfail == 0


def _emit(lines: list[str]) -> None:
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text.encode(enc, "backslashreplace").decode(enc))
    sys.stdout.flush()


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon audit prereg",
                                 description="Check from git history that predictions were committed before their "
                                             "outcomes and never edited (docs/BUILD_PLAN.md 0.1).")
    ap.add_argument("--milestone", required=True, help="e.g. M2; audits spec/<M>/predictions.json")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="top of the git checkout (default: this repo)")
    a = ap.parse_args(argv)
    if not _MILESTONE.match(a.milestone):
        ap.error(f"--milestone must look like M2, got {a.milestone!r}")
    root = Path(a.root).resolve()
    try:
        lines, ok = run_audit(root, a.milestone)
    except Fatal as e:
        lines, ok = [f"prereg: FAIL {e}", "PREREG FAILED"], False
    _emit(lines)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
