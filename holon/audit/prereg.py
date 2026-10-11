"""Preregistration audit (docs/BUILD_PLAN.md 0.1): ``python -m holon audit prereg --milestone M2 [--root PATH]``.

The audit reads git history and nothing else (``rev-parse``, ``rev-list``, ``cat-file``, ``diff-tree``,
``for-each-ref``, ``status``; it never writes to the repository, its index or its config). It audits the
committed tree at HEAD only. Uncommitted edits are ignored, with one exception: a working-tree change to
``spec/<M>/predictions.json`` is itself a failure, so a passing audit always describes the predictions file on
disk. Replace objects are ignored (``GIT_NO_REPLACE_OBJECTS``), and a repository with grafts or
``refs/replace/`` refs, or a shallow clone, is refused: its history is not the history that was pushed.

What is checked, for every iteration key K that appears in any committed version of
``spec/<M>/predictions.json`` reachable from HEAD:

1. Prereg commit. C_K is the first commit, oldest first in topological order, whose version of the file holds K.
2. Immutability. K's value at HEAD equals its value at C_K, compared as canonical JSON: key order and
   whitespace do not matter, but ``true`` is not ``1`` and ``1`` is not ``1.0``. A key removed at HEAD fails.
3. Prereg contents. C_K changes only prereg inputs: the predictions file; the prompts and tests of the keys
   introduced at C_K, and anything under those tests' package directories; ``spec/ledger/``, ``spec/lib/``,
   ``spec/M*/lib/``, ``spec/schemas/predictions.schema.json`` and ``spec/M*/amendments.jsonl``. Anything
   else (``holon/``, ``tools/``, ``results/``, ``gen/``, ``replay/``, ``laws/``, ...) fails.
4. Order. C_K changes no file under K's ``outcome_paths``. An outcome path is a literal prefix of a
   repo-relative path: ``results/M2/`` covers that directory, ``replay/M0/report.json`` that file. Outcome
   paths must be plain relative paths (no globs, ``.`` or ``..``). In addition, every commit reachable from
   HEAD but not from C_K that changes an outcome path must descend from C_K: an outcome written on a
   parallel branch and merged later did not come after the prereg.
5. Tests. Each file in K's ``tests`` exists at C_K and holds at least one test function there. What existed at
   C_K must be unchanged at HEAD; new test functions, helpers and constants may be added. Fingerprinted at C_K:
   - every function, keyed ``func`` at module level and ``Class.func`` in a module-level class. Methods are
     keyed by every class that collects them: a method a class inherits from a base class defined in the
     same module is also keyed under that class (``TestGateM0.test_g6_g9_pass`` from ``_FullGate``), so
     deleting the collecting class is a change. A function's fingerprint is its source lines including its
     decorators (an added ``@skip`` counts), trailing whitespace stripped; for a method, also the header
     (decorators, bases, keywords) and the non-function body statements (class attributes such as
     ``n_records = 8``) of the class and of each same-module class it inherits from; and how many times the
     name is bound in its scope (a later redefinition shadows the original);
   - each module-level statement that is neither a def, a class nor the docstring, grouped by the names it
     binds (constants, ``key = "NAME"``); each imported name with its origin (``from x import y``);
     statements binding no name (``<module code>``, including star imports), so that added top-level code
     is a change;
   - a unittest fixture (``setUp``, ``setUpClass``, ``asyncSetUp``, ..., ``setUpModule``, ``load_tests``) that
     appears at HEAD in a class that existed at C_K, or at module level, is a change: a new ``setUp`` can skip
     every test of its class;
   - the package ``__init__.py`` of each test file, whole (amendment id ``<pkg>/__init__.py::*``);
   - every helper module of the same package that a test file (or such a helper) imports at C_K, e.g.
     ``tests_m2/_m2.py``: the same per-function, per-statement and per-import fingerprints, so a changed or
     removed helper is a change, while new helpers and docstring-only edits are not.
6. Amendments. A change is not a failure when ``spec/<M>/amendments.jsonl`` at HEAD holds a line
   ``{"iteration": K, "test": "<file>::<key>", "why": "..."}`` for it; it is printed as amended, with what
   changed, to be reported under Surprises. The file is append-only: every line of every committed version
   must still be present at HEAD, so emptying, deleting or renaming it fails.

Notes (never failures): a prediction or regression ``check`` naming ``file.py::Class::method`` (several may be
joined by `` and ``) that does not resolve to a test fingerprinted at C_K; and each sidecar input (a file C_K
changed other than the predictions file, the keys' tests and prompts, the fingerprinted package files and the
amendments file) whose content at HEAD differs from C_K.

Missing history (no repository at ROOT, no commit, a shallow clone) is a failure, never a skip. A
predictions file with no iteration keys is a failure too: an audit of nothing proves nothing. Exit status
is 0 iff nothing failed; output is deterministic (sorted keys, fixed 12-character shas, no timestamps).

Residual risk, stated plainly:
- Local runs made before a prereg commit cannot be detected. The audit sees commits, not experiments.
- Outcome-path commits that are ancestors of C_K are attributed to no iteration: an outcome committed before
  its prereg commit passes, exactly like a local run.
- Order is commit topology, not wall-clock time. Unpushed history can be rewritten, and the local ``.git`` is
  trusted. The authoritative audit is a run on a fresh clone of the pushed remote.
- This tool, the predictions file, the amendments file and the tests are agent-writable until the human
  freezes them (BUILD_PLAN 0.3, Q1). Until then the protocol is self-certified, and the audit prints which
  of those files are not listed in FROZEN.sha256.
- Sidecar inputs (``spec/ledger/``, schemas, ...) are not immutable after the prereg; changes are only noted.
- An amendment licenses every later change to what it names.
- Newly added sibling test modules or helpers, new classes (their bodies run at import) and decorators of new
  functions can still monkeypatch at import time. Modules outside the test package (``tests/``, ``holon/``)
  are not fingerprinted.
- A merge commit on a parallel branch is not inspected for outcome changes of its own (an "evil merge").
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import posixpath
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
TOOL_PATH = "holon/audit/prereg.py"
SHA = 12  # fixed abbreviation: `git rev-parse --short` grows with the object count
CLASS_FIXTURES = frozenset({"setUp", "tearDown", "setUpClass", "tearDownClass", "asyncSetUp", "asyncTearDown"})
MODULE_FIXTURES = frozenset({"setUpModule", "tearDownModule", "load_tests"})
MODULE_CODE = "<module code>"
FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
_MILESTONE = re.compile(r"^M[0-9]+$")
_GLOB_CHARS = frozenset("*?[")
_ALWAYS_ALLOWED = (re.compile(r"^spec/ledger/"), re.compile(r"^spec/lib/"), re.compile(r"^spec/M[0-9]+/lib/"),
                   re.compile(r"^spec/schemas/predictions\.schema\.json$"),
                   re.compile(r"^spec/M[0-9]+/amendments\.jsonl$"))
_KIND_RANK = {"code": 0, "helper": 1, "fixture": 2, "test": 3}
_LABEL = {"code": "module code", "helper": "helper", "fixture": "fixture", "test": "test"}
_FIELD_WHAT = {"what": "kind of definition", "source": "source", "classes": "class header, attributes or bases",
               "class_bindings": "class name rebound", "bindings": "name rebound in its scope",
               "import": "import origin"}
_CHECK_FILE = re.compile(r"^([\w./-]+\.py)(?:::(\S+))?$")
_CHECK_REST = re.compile(r"^[A-Za-z_][\w]*(?:::[A-Za-z_][\w]*)*$")


class Fatal(Exception):
    """The audit cannot run at all."""


# ------------------------------------------------------------------ git, read-only
class Git:
    def __init__(self, root: Path):
        self.root = root
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}  # no GIT_DIR redirection
        env.update(GIT_OPTIONAL_LOCKS="0",  # status must not write the index
                   GIT_NO_REPLACE_OBJECTS="1",  # refs/replace cannot rewrite history for us
                   GIT_TERMINAL_PROMPT="0", LC_ALL="C")
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
    grafts = git.out("rev-parse", "--git-path", "info/grafts").strip()
    if grafts and (root / grafts).exists():
        raise Fatal(f"{root} has a grafts file ({grafts}): its history is rewritten locally")
    replace = git.out("for-each-ref", "--format=%(refname)", "refs/replace/").split()
    if replace:
        raise Fatal(f"{root} has replace refs ({', '.join(sorted(replace)[:3])}): its history is rewritten locally")
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


def str_list(v) -> list[str]:
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


# ------------------------------------------------------------------ module fingerprints
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


def _is_docstring(s: ast.stmt) -> bool:
    return isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str)


def _body(stmts: list[ast.stmt]) -> list[ast.stmt]:
    return stmts[1:] if stmts and _is_docstring(stmts[0]) else stmts


def _src(lines: list[str], node: ast.stmt) -> str:
    """The statement's full source lines, decorators included, trailing whitespace stripped."""
    start = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
    return "\n".join(line.rstrip() for line in lines[start - 1:node.end_lineno])


def _class_context(lines: list[str], node: ast.ClassDef) -> str:
    return canon({"decorators": [ast.dump(d) for d in node.decorator_list],
                  "bases": [ast.dump(b) for b in node.bases],
                  "keywords": [ast.dump(k) for k in node.keywords],
                  "type_params": [ast.dump(t) for t in getattr(node, "type_params", [])],
                  "body": [_src(lines, s) for s in _body(node.body) if not isinstance(s, FUNCS)]})


def _linearize(node: ast.ClassDef, bases: list[ast.ClassDef], lin: dict[int, list[ast.ClassDef]]) -> list:
    """C3 over the bases defined earlier in the same module (other bases are opaque)."""
    seqs = [list(s) for s in [lin[id(b)] for b in bases] + [bases] if s]
    out = [node]
    while seqs:
        for s in seqs:
            cand = s[0]
            if not any(cand in t[1:] for t in seqs):
                break
        else:  # inconsistent order (Python would refuse the class): depth-first, first occurrence
            for b in bases:
                out.extend(x for x in lin[id(b)] if x not in out)
            return out
        out.append(cand)
        seqs = [t for t in ([t[1:] if t[0] is cand else t for t in seqs]) if t]
    return out


def _kind(name: str, method: bool) -> str:
    if name in (CLASS_FIXTURES if method else MODULE_FIXTURES):
        return "fixture"
    return "test" if name.startswith("test") else "helper"


@dataclass
class Analysis:
    fps: dict[str, list[dict]] = field(default_factory=lambda: {MODULE_CODE: []})
    kinds: dict[str, str] = field(default_factory=lambda: {MODULE_CODE: "code"})
    classes: set[str] = field(default_factory=set)
    imports: list[tuple[int, str, list[str]]] = field(default_factory=list)

    def add(self, key: str, kind: str, record: dict) -> None:
        self.fps.setdefault(key, []).append(record)
        if _KIND_RANK[kind] > _KIND_RANK[self.kinds.get(key, "code")]:
            self.kinds[key] = kind
        self.kinds.setdefault(key, kind)

    def tracked(self) -> list[str]:
        return [k for k, v in self.kinds.items() if v in ("test", "fixture")]


def analyse(source: str, test_module: bool) -> Analysis:
    """Fingerprints of a module's definitions and top-level code. Raises SyntaxError/ValueError."""
    tree = ast.parse(source)
    lines = re.split(r"\r\n|\r|\n", source)  # the line breaks ast counts (str.splitlines also splits on \f etc.)
    mod = _bindings(tree.body)
    a = Analysis()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            a.imports.extend((0, al.name, []) for al in n.names)
        elif isinstance(n, ast.ImportFrom):
            a.imports.append((n.level, n.module or "", [al.name for al in n.names]))
    latest: dict[str, ast.ClassDef] = {}
    lin: dict[int, list[ast.ClassDef]] = {}
    for node in _body(tree.body):
        if isinstance(node, FUNCS):
            kind = _kind(node.name, method=False) if test_module else "helper"
            a.add(node.name, kind, {"what": "def", "source": _src(lines, node), "bindings": mod[node.name]})
        elif isinstance(node, ast.ClassDef):
            bases = [latest[b.id] for b in node.bases if isinstance(b, ast.Name) and b.id in latest]
            order = lin[id(node)] = _linearize(node, bases, lin)
            latest[node.name] = node
            a.classes.add(node.name)
            ctx = [_class_context(lines, x) for x in order]
            names: list[str] = []
            for x in order:
                names.extend(s.name for s in x.body if isinstance(s, FUNCS) and s.name not in names)
            for m in names:
                definer = next(x for x in order if any(isinstance(s, FUNCS) and s.name == m for s in x.body))
                defs = [s for s in definer.body if isinstance(s, FUNCS) and s.name == m]
                kind = _kind(m, method=True) if test_module else "helper"
                a.add(f"{node.name}.{m}", kind, {"what": "method", "classes": ctx,
                                                 "source": [_src(lines, d) for d in defs],
                                                 "bindings": _bindings(definer.body)[m],
                                                 "class_bindings": mod[node.name]})
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for al in node.names:
                if al.name == "*":
                    a.fps[MODULE_CODE].append({"what": "stmt", "source": _src(lines, node)})
                    continue
                name = al.asname or al.name.split(".")[0]
                origin = (f"import {al.name}" if isinstance(node, ast.Import)
                          else f"from {'.' * node.level}{node.module or ''} import {al.name}")
                a.add(name, "code", {"what": "import", "import": origin, "bindings": mod[name]})
        else:
            names = sorted(n for n in _bindings([node]) if n != "*")
            if names:
                a.add(",".join(names), "code", {"what": "stmt", "source": _src(lines, node),
                                                "bindings": [mod[n] for n in names]})
            else:
                a.fps[MODULE_CODE].append({"what": "stmt", "source": _src(lines, node)})
    return a


def same_package_modules(imports: list[tuple[int, str, list[str]]], pkg: str) -> list[str]:
    """Candidate repo paths of modules of package directory `pkg` that these imports name."""
    dotted = pkg.replace("/", ".")
    out: list[str] = []
    for level, module, names in imports:
        if level == 0 and module == dotted:
            cands = names
        elif level == 0 and module.startswith(dotted + "."):
            cands = [module[len(dotted) + 1:]]
        elif level == 1:
            cands = [module] if module else names
        else:
            continue
        for c in cands:
            if c != "*":
                rel = c.replace(".", "/")
                out += [f"{pkg}/{rel}.py", f"{pkg}/{rel}/__init__.py"]
    return out


def describe(r0: list[dict], r1: list[dict]) -> str:
    if len(r0) != len(r1):
        return f"number of definitions {len(r0)} -> {len(r1)}"
    diff = {f for a, b in zip(r0, r1) for f in set(a) | set(b) if a.get(f) != b.get(f)}
    return "differs in " + ", ".join(_FIELD_WHAT.get(f, f) for f in _FIELD_WHAT if f in diff)


# ------------------------------------------------------------------ amendments
def load_amendments(git: Git, head: str, path: str) -> tuple[dict[tuple[str, str], list[str]], list[str]]:
    """(iteration, "file::key") -> reasons, from HEAD; plus problems (malformed lines, broken append-only).
    The append-only history check runs even when the file is gone at HEAD (deleted or renamed)."""
    amend: dict[tuple[str, str], list[str]] = {}
    problems: list[str] = []
    data = git.blob(head, path)
    text = ""
    if data is not None:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            problems.append(f"{path} at HEAD is not UTF-8: {e}")
            text = data.decode("utf-8", "replace")
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
            problems.append(f"{path} line {i} needs string fields iteration, test (\"file::key\") and a non-empty why")
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
                where = "gone at HEAD" if data is not None else f"gone: {path} does not exist at HEAD"
                problems.append(f"{path} is append-only, but a line committed in {c[:SHA]} is {where}: {ln[:120]}")
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
@dataclass
class Ctx:
    git: Git
    head: str
    pred: str
    head_its: dict
    amend: dict
    cohorts: dict[str, list]  # commit -> values of the keys introduced there


@dataclass
class KeyReport:
    k: str
    cs: str
    probs: list[str] = field(default_factory=list)
    amended: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def change(self, amend: dict, f: str, key: str, kind: str, what: str) -> None:
        tid = f"{f}::{key}"
        whys = amend.get((self.k, tid))
        if whys:
            self.amended.append(f"{self.k}: {_LABEL[kind]} {tid} amended ({what}): {'; '.join(whys)}")
        else:
            self.probs.append(f"{self.k}: {_LABEL[kind]} {tid} changed after the prereg commit {self.cs} ({what})")


def _compare(r: KeyReport, amend: dict, f: str, a0: Analysis, a1: Analysis | None, test_module: bool) -> None:
    for key in sorted(a0.fps, key=natural):
        r0 = a0.fps[key]
        r1 = a1.fps.get(key) if a1 is not None else None
        if r1 == r0 or (r1 is None and not r0):
            continue
        what = ("file removed at HEAD" if a1 is None else "removed at HEAD") if r1 is None else describe(r0, r1)
        r.change(amend, f, key, a0.kinds[key], what)
    if test_module and a1 is not None:
        for key in sorted(set(a1.fps) - set(a0.fps), key=natural):
            if a1.kinds[key] == "fixture" and ("." not in key or key.split(".", 1)[0] in a0.classes):
                r.change(amend, f, key, "fixture", "added at HEAD")


def _analyse_blob(r: KeyReport, data: bytes, f: str, where: str, test_module: bool) -> Analysis | None:
    try:
        return analyse(data.decode("utf-8"), test_module)
    except (SyntaxError, ValueError) as e:
        r.probs.append(f"{r.k}: {f} does not parse at {where}: {e}")
        return None


def audit_key(x: Ctx, k: str, intro: tuple[str, object, list[str]] | None) -> tuple[str, KeyReport, list[str]]:
    """-> (summary line, report, test files)."""
    if intro is None:
        r = KeyReport(k, "")
        r.probs.append(f"{k}: no commit reachable from HEAD introduces the key")
        return f"{k}: FAIL", r, []
    git, head = x.git, x.head
    c, v0, unparsed = intro
    r = KeyReport(k, c[:SHA])
    cs = r.cs
    r.probs += [f"{k}: {x.pred} at {u} does not parse, so the prereg commit is uncertain" for u in unparsed]

    # immutability
    if k not in x.head_its:
        r.probs.append(f"{k}: key removed after its prereg commit {cs} (a prereg key is never edited or removed)")
    elif canon(x.head_its[k]) != canon(v0):
        v1 = x.head_its[k]
        fields = ""
        if isinstance(v0, dict) and isinstance(v1, dict):
            diff = sorted(f for f in set(v0) | set(v1) if canon(v0.get(f)) != canon(v1.get(f)) or (f in v0) != (f in v1))
            fields = f" (fields: {', '.join(diff)})"
        r.probs.append(f"{k}: key edited after its prereg commit {cs}{fields}")
    if not isinstance(v0, dict):
        r.probs.append(f"{k}: value at the prereg commit {cs} is not an object")
        return f"{k}: FAIL prereg {cs}", r, []

    # the preregistered contract is the value at C_K (HEAD's may have been edited)
    ops, tests = v0.get("outcome_paths"), v0.get("tests")
    if not isinstance(ops, list) or not ops:
        r.probs.append(f"{k}: outcome_paths at the prereg commit {cs} is not a non-empty list")
        ops = []
    if not isinstance(tests, list) or not tests:
        r.probs.append(f"{k}: tests at the prereg commit {cs} is not a non-empty list")
        tests = []
    good_ops = []
    for p in ops:
        why = bad_path(p)
        if why:
            r.probs.append(f"{k}: outcome path {p!r} {why}")
        else:
            good_ops.append(p)
    good_tests = []
    for f in tests:
        why = bad_path(f)
        if why or not str(f).endswith(".py"):
            r.probs.append(f"{k}: test file {f!r} {why or 'is not a .py file'}")
        else:
            good_tests.append(f)

    # prereg contents: only prereg inputs
    changed = git.changed(c, merges=True)
    cohort = [v for v in x.cohorts.get(c, []) if isinstance(v, dict)]
    prompts = {p for v in cohort for p in [v.get("prompt")] if isinstance(p, str) and not bad_path(p)}
    ctests = {t for v in cohort for t in str_list(v.get("tests")) if not bad_path(t)}
    pkgs = sorted({posixpath.dirname(t) for t in ctests} - {""})

    def allowed(f: str) -> bool:
        return (f == x.pred or f in prompts or f in ctests or any(f.startswith(pk + "/") for pk in pkgs)
                or any(rx.match(f) for rx in _ALWAYS_ALLOWED))
    outside = sorted(f for f in changed if not allowed(f))
    if outside:
        more = f" and {len(outside) - 5} more" if len(outside) > 5 else ""
        r.probs.append(f"{k}: prereg commit {cs} also changes files that are not prereg inputs: "
                       f"{', '.join(outside[:5])}{more}")

    # order: the prereg commit itself
    for p in good_ops:
        hit = sorted(f for f in changed if f.startswith(p))
        if hit:
            more = f" and {len(hit) - 1} more" if len(hit) > 1 else ""
            r.probs.append(f"{k}: prereg commit {cs} also changes outcome path {p} ({hit[0]}{more})")
    # order: outcome commits on branches parallel to the prereg commit
    if good_ops and c != head:
        after = set(git.commits("--ancestry-path", f"{c}..{head}"))
        for y in git.commits("--topo-order", "--reverse", head, f"^{c}"):
            if y in after:
                continue
            ch = git.changed(y, merges=False)
            for p in good_ops:
                hit = sorted(f for f in ch if f.startswith(p))
                if hit:
                    r.probs.append(f"{k}: commit {y[:SHA]} changes outcome path {p} ({hit[0]}) but does not descend "
                                   f"from the prereg commit {cs}")

    # tests, then the helper modules they import, then the package __init__.py files
    nfun = 0
    test_ids: dict[str, set[str]] = {}
    helpers: list[str] = []
    seen_helpers: set[str] = set(good_tests)
    for f in good_tests:
        old = git.blob(c, f)
        if old is None:
            r.probs.append(f"{k}: test file {f} is missing at the prereg commit {cs}")
            continue
        a0 = _analyse_blob(r, old, f, f"the prereg commit {cs}", True)
        if a0 is None:
            continue
        test_ids[f] = {t for t in a0.tracked() if a0.kinds[t] == "test"}
        if not test_ids[f]:
            r.probs.append(f"{k}: test file {f} has no test functions at the prereg commit {cs}")
            continue
        nfun += len(a0.tracked())
        new = git.blob(head, f)
        a1 = None if new is None else _analyse_blob(r, new, f, "HEAD", True)
        if new is not None and a1 is None:
            continue
        _compare(r, x.amend, f, a0, a1, True)
        pkg = posixpath.dirname(f)
        todo = [(pkg, a0)] if pkg else []
        while todo:
            pk, an = todo.pop()
            for h in same_package_modules(an.imports, pk):
                if h in seen_helpers or h == f"{pk}/__init__.py":
                    continue
                hb = git.blob(c, h)
                if hb is None:
                    continue
                seen_helpers.add(h)
                h0 = _analyse_blob(r, hb, h, f"the prereg commit {cs}", False)
                if h0 is None:
                    continue
                helpers.append(h)
                hn = git.blob(head, h)
                h1 = None if hn is None else _analyse_blob(r, hn, h, "HEAD", False)
                if hn is None or h1 is not None:
                    _compare(r, x.amend, h, h0, h1, False)
                todo.append((pk, h0))
    inits = sorted({f"{posixpath.dirname(t)}/__init__.py" for t in good_tests if posixpath.dirname(t)})
    for init in inits:
        b0, b1 = git.blob(c, init), git.blob(head, init)
        if b0 != b1:
            what = "added at HEAD" if b0 is None else "removed at HEAD" if b1 is None else "content differs"
            whys = x.amend.get((k, f"{init}::*"))
            if whys:
                r.amended.append(f"{k}: package file {init}::* amended ({what}): {'; '.join(whys)}")
            else:
                r.probs.append(f"{k}: package file {init} changed after the prereg commit {cs} ({what})")

    # notes: checks that name no preregistered test; sidecar inputs edited since the prereg
    items = [i for f in ("predictions", "regressions") for i in (v0.get(f) if isinstance(v0.get(f), list) else [])
             if isinstance(i, dict)]
    for item in items:
        chk, prev = item.get("check"), None
        if not isinstance(chk, str):
            continue
        for part in (s.strip() for s in chk.split(" and ")):
            m = _CHECK_FILE.match(part)
            if m:
                prev, rest = m.group(1), m.group(2)
            elif prev and _CHECK_REST.match(part) and "::" in part:
                rest = part
            else:
                continue
            if rest and rest.replace("::", ".") not in test_ids.get(prev, set()):
                r.notes.append(f"{k}: note: check {part!r} of {item.get('id', '?')} does not resolve to a "
                               f"preregistered test")
    covered = {x.pred, *prompts, *ctests, *helpers, *inits}
    for f in sorted(changed):
        if f in covered or f in outside or _ALWAYS_ALLOWED[-1].match(f):
            continue
        b0 = git.blob(c, f)
        if b0 is not None and git.blob(head, f) != b0:
            r.notes.append(f"{k}: note: sidecar changed after prereg: {f}")

    counts = (f"({plural(len(ops), 'outcome path')}, {plural(len(tests), 'test file')}, "
              f"{plural(len(helpers), 'helper module')}, {plural(nfun, 'tracked function')})")
    return f"{k}: {'FAIL' if r.probs else 'OK'} prereg {cs} {counts}", r, good_tests


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
    cohorts: dict[str, list] = {}
    for c, v, _ in intro.values():
        cohorts.setdefault(c, []).append(v)

    amend, aprobs = load_amendments(git, head, amend_path)
    glob.extend(aprobs)
    out.extend(f"prereg: FAIL {p}" for p in glob)

    x = Ctx(git, head, pred, head_its, amend, cohorts)
    nfail = len(glob)
    test_files: set[str] = set()
    for k in keys:
        summary, r, files = audit_key(x, k, intro.get(k))
        test_files.update(files)
        out.append(summary)
        out.extend(f"  {line}" for line in r.probs + r.amended + r.notes)
        nfail += len(r.probs)

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
    out.append("note: local runs, and outcomes committed before their prereg commit, cannot be detected; "
               "the authoritative run is on a fresh clone of the pushed remote")
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
