"""Auditor A1 of an audit round, M3 on: the auditor's mutants of the target's real code, applied, re-extracted,
re-derived and re-run by HOLON (whitepaper §9.5 A1; spec/<M>/lib/audit_loop.json auditor_types.A1).

    python -m holon audit mutation --milestone M --round n --spec FILE [--target COMMIT] [--checkout DIR]
                                   [--out PATH] [--work DIR] [--law-timeout S] [--max-law-runs N] [--check]

The auditor chooses the mutants; this command chooses none. It applies them and judges the result.

The spec (holon-audit-a1-spec/0.1, JSON):
  {"spec_version": "holon-audit-a1-spec/0.1", "milestone": "M3",
   "budget": {"law_timeout_s": 900, "max_law_runs": 24},                  (optional; the flags override it)
   "mutations": [
     {"id": "m1", "file": "<path in the checkout>", "edit": {"line": 412, "old": "<text on that line>", "new": "..."},
      "laws": ["<law id>", ...], "expect": "<free text>"},                (laws and expect optional)
     {"id": "m2", "file": "<path in the checkout>", "patch": "<unified diff of that one file>"}]}
An edit replaces the only occurrence of `old` on line `line` (1-based) by `new`; a patch is applied with `git apply`
and may modify that one file only (no creation, deletion, rename or mode change). A path that is absolute, holds `..`,
leaves the checkout through a link or is not a tracked regular file at the checkout's HEAD is refused.

Per round:
  0. the target commit's tree (git archive; gen/<M>/refute and spec/heldout left out) is staged in a scratch directory;
     the checkout is the one the facts documents name (config extract.sources[<their target.repo>], or --checkout),
     at the documents' commit and clean; it is only read (each mutant gets a shared scratch clone of it);
  1. the documents in scope are every law's facts document of laws/<M>/ and, transitively, the documents those list as
     inputs; a frontend document (extraction.frontend solidity or go) is re-extracted with its own sidecar or config
     (extraction.sidecar.path, extraction.config.path) by `holon extract solidity|go`; a frontend document at another
     commit than the checkout's (a version's history) is out of reach and listed as such;
  2. a baseline re-extraction from the unmutated checkout, written in the committed document's JSON format, must
     reproduce the committed bytes (a1.json says whether it did).
Per mutant, in its own copy of the staged tree:
  3. the edit is applied in a scratch clone at the documents' commit, where git is told to treat the mutated file as
     unchanged (update-index --assume-unchanged): the frontends' and holon run's guards (a clean checkout at the
     documents' commit) then hold in that clone, and only there, and the mutant's own code is what they compile and
     deploy (the scratch tree's config names the clone in place of the checkout); the documents whose extraction
     inputs list the file are re-extracted (an extraction that fails is "extraction rejects"); a document whose
     content, its extraction inputs' hashes aside, equals the baseline's leaves the mutant invisible ("missed");
  4. otherwise the committed sha256 of every changed document is re-pinned to the new one in the tree's spec/*/lib/
     sidecars and spec/*/ledger.json, the generators `holon sorts|codecs|own|diagram|evidence|disch --milestone M`
     run in that order (the derived documents' pins follow), and `holon derive --milestone M` re-derives laws/<M>/;
     a law added, dropped or whose statement differs from the committed one is a "derivation change", and a
     generator or derive that refuses is a "derivation refusal";
  5. the laws whose law file differs only in facts_sha256 (their facts or closure moved, their statement did not) are
     re-run with `holon run --milestone M --laws <id>`, on the mutant's tree and on an unmutated copy (the baseline,
     run once per law and round), each under --law-timeout seconds, at most --max-law-runs runs in the round: first
     the spec's own `laws` of the mutant, then those whose law file names a changed entry of a changed document, then
     the rest, each group by id. A re-run whose status differs from the baseline's is a "flip".
Verdicts: "detected" (extraction rejects, a derivation change or refusal, or a flip), "missed" (every touched law ran
and nothing moved, or nothing reached a document), "incomplete" (nothing moved among what ran, but a touched law did
not run or finish within the caps), "refused" (the mutation could not be applied).

Output: audit/rounds/<M>/round<n>/a1.json (holon-audit-a1/0.1; json.dumps(indent=1, sort_keys=True) + newline; no
timestamps, no scratch paths), whose "attack" is the round file's attack entry (run true; the auditor files each miss
it judges a finding and lists the ids); the measured seconds go to a1.timings.json beside it. --check reruns and
compares a1.json byte for byte. Nothing here names a law or a target: names come from the spec, the documents, the
sidecars and the configuration.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC_VERSION = "holon-audit-a1-spec/0.1"
A1_VERSION = "holon-audit-a1/0.1"
DEFAULT_BUDGET = {"law_timeout_s": 900, "max_law_runs": 24}
MAX_BUDGET = {"law_timeout_s": 7200, "max_law_runs": 400}
FRONTENDS = ("solidity", "go")
REGEN = ("sorts", "codecs", "own", "diagram", "evidence", "disch")   # derive's inputs, in dependency order
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
LAW_ID = re.compile(r"^L_[A-Za-z0-9_]+$")
TAIL = 600


class MutationError(RuntimeError):
    """Refused: nothing is written."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# ================================================================================================ the spec
def load_spec(path: Path, milestone: str) -> dict:
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise MutationError(f"the spec {path} does not parse: {e}") from None
    bad = spec_problems(spec, milestone)
    if bad:
        raise MutationError("the spec is malformed:\n  " + "\n  ".join(bad))
    return spec


def spec_problems(spec, milestone: str) -> list[str]:
    if not isinstance(spec, dict):
        return ["not a JSON object"]
    bad = []
    extra = sorted(set(spec) - {"spec_version", "milestone", "budget", "mutations", "note"})
    if extra:
        bad.append(f"unknown fields {extra}")
    if spec.get("spec_version") != SPEC_VERSION:
        bad.append(f"spec_version must be {SPEC_VERSION!r}")
    if spec.get("milestone", milestone) != milestone:
        bad.append(f"milestone {spec.get('milestone')!r} is not {milestone!r}")
    b = spec.get("budget", {})
    if not isinstance(b, dict) or set(b) - set(DEFAULT_BUDGET):
        bad.append(f"budget takes only {sorted(DEFAULT_BUDGET)}")
    else:
        for k, v in b.items():
            if not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= MAX_BUDGET[k]):
                bad.append(f"budget.{k} must be an integer in 0..{MAX_BUDGET[k]}")
    ms = spec.get("mutations")
    if not isinstance(ms, list) or not ms:
        return bad + ["mutations must be a non-empty list"]
    seen = set()
    for i, m in enumerate(ms):
        w = f"mutations[{i}]"
        if not isinstance(m, dict):
            bad.append(f"{w}: not an object")
            continue
        extra = sorted(set(m) - {"id", "file", "edit", "patch", "laws", "expect", "note"})
        if extra:
            bad.append(f"{w}: unknown fields {extra}")
        if not isinstance(m.get("id"), str) or not ID.match(m["id"]):
            bad.append(f"{w}: id must match {ID.pattern}")
        elif m["id"] in seen:
            bad.append(f"{w}: id {m['id']} repeats")
        else:
            seen.add(m["id"])
        if not isinstance(m.get("file"), str) or not m["file"]:
            bad.append(f"{w}: file must be a path in the checkout")
        if ("edit" in m) == ("patch" in m):
            bad.append(f"{w}: give exactly one of edit and patch")
        if "edit" in m:
            e = m["edit"]
            if not (isinstance(e, dict) and set(e) == {"line", "old", "new"} and isinstance(e["line"], int)
                    and not isinstance(e["line"], bool) and e["line"] >= 1 and isinstance(e["old"], str) and e["old"]
                    and "\n" not in e["old"] and isinstance(e["new"], str) and e["new"] != e["old"]):
                bad.append(f"{w}: edit must be {{line >= 1, old: non-empty text of one line, new: other text}}")
        if "patch" in m and not (isinstance(m["patch"], str) and m["patch"].strip()):
            bad.append(f"{w}: patch must be a non-empty unified diff")
        if "laws" in m and not (isinstance(m["laws"], list) and all(isinstance(x, str) and LAW_ID.match(x)
                                                                    for x in m["laws"])):
            bad.append(f"{w}: laws must be a list of law ids")
        for k in ("expect", "note"):
            if k in m and not isinstance(m[k], str):
                bad.append(f"{w}: {k} must be text")
    return bad


def budget_of(spec: dict, law_timeout: int | None, max_runs: int | None) -> dict:
    b = {**DEFAULT_BUDGET, **(spec.get("budget") or {})}
    if law_timeout is not None:
        b["law_timeout_s"] = law_timeout
    if max_runs is not None:
        b["max_law_runs"] = max_runs
    for k, v in b.items():
        if not 0 <= v <= MAX_BUDGET[k]:
            raise MutationError(f"{k} {v} is outside 0..{MAX_BUDGET[k]}")
    return b


# ================================================================================================ trees
def git_out(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True)


def resolve_commit(c: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "-q", f"{c}^{{commit}}"],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise MutationError(f"{c} is not a commit of this repository")
    return p.stdout.strip()


def archive(repo: Path, commit: str, dest: Path, exclude: tuple = ()) -> Path:
    """The commit's tree in dest (git archive | tar), without the excluded paths."""
    dest.mkdir(parents=True, exist_ok=True)
    spec = ["--", "."] + [f":(exclude){x}" for x in exclude] if exclude else []
    a = subprocess.Popen(["git", "-C", str(repo), "archive", "--format=tar", commit, *spec], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    t = subprocess.run(["tar", "-x", "-C", str(dest)], stdin=a.stdout, capture_output=True)
    a.stdout.close()
    err = a.stderr.read().decode(errors="replace")
    if a.wait() != 0 or t.returncode != 0:
        raise MutationError(f"git archive {commit} of {repo} failed: {(err + t.stderr.decode(errors='replace'))[-400:]}")
    return dest


def copy_tree(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest, symlinks=True)
    return dest


def clone_at(checkout: Path, commit: str, dest: Path) -> Path:
    """A scratch clone of the checkout (its objects shared, read-only) with `commit` checked out."""
    for args in (["clone", "-q", "--shared", "--no-checkout", str(checkout), str(dest)],
                 ["-C", str(dest), "checkout", "-q", "--detach", commit]):
        p = subprocess.run(["git", *args], capture_output=True, text=True)
        if p.returncode != 0:
            raise MutationError(f"git {args[0]} failed: {(p.stdout + p.stderr).strip()[-300:]}")
    return dest


def point_config(tree: Path, checkout: Path, src: Path) -> None:
    """The scratch tree's config/holon.json with every path naming the checkout replaced by the mutant's clone."""
    cp = tree / "config" / "holon.json"
    cfg = json.loads(cp.read_text(encoding="utf-8"))
    forms = {str(checkout), os.path.realpath(checkout)}

    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return str(src) if isinstance(x, str) and (x in forms or os.path.realpath(x) in forms) and x.startswith("/") \
            else x
    cp.write_text(json.dumps(walk(cfg), indent=2) + "\n", encoding="utf-8")


def holon_in(tree: Path, args: list, timeout: int) -> tuple[int | None, str]:
    """`python -m holon <args>` inside a scratch HOLON tree (its own code, cwd and ROOT): (exit, output); None on a
    timeout."""
    from ..mutate.common import env_tools
    env = env_tools()
    env["PYTHONPATH"] = str(tree)
    env.pop("HOLON_BUILD_DIR", None)
    try:
        p = subprocess.run([sys.executable, "-m", "holon", *[str(a) for a in args]], cwd=str(tree), env=env,
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        return None, out + f"\n[timeout after {timeout} s]"


# ================================================================================================ documents
def json_format(text: str):
    """The (indent, ensure_ascii) whose json.dumps(sort_keys=True) + newline gives `text` back, else None."""
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    for ind in (1, 2, None, 4):
        for asc in (False, True):
            if json.dumps(obj, indent=ind, sort_keys=True, ensure_ascii=asc) + "\n" == text:
                return ind, asc
    return None


def upstream(doc: dict) -> list[str]:
    """The documents a derived document lists as its inputs (inputs[].path, document, documents)."""
    out = []
    for i in doc.get("inputs") or []:
        if isinstance(i, dict) and isinstance(i.get("path"), str):
            out.append(i["path"])
    if isinstance(doc.get("document"), str):
        out.append(doc["document"])
    ds = doc.get("documents")
    if isinstance(ds, list):
        out += [x for x in ds if isinstance(x, str)]
    elif isinstance(ds, dict):
        out += [v["path"] for v in ds.values() if isinstance(v, dict) and isinstance(v.get("path"), str)]
    return sorted({x for x in out if x.endswith(".json")})


class Doc:
    """A document in scope: its path, committed bytes and, for a frontend document, how it is re-extracted."""

    def __init__(self, tree: Path, rel: str):
        self.rel = rel
        self.text = (tree / rel).read_text(encoding="utf-8")
        self.data = json.loads(self.text)
        self.sha256 = sha256_bytes(self.text.encode())
        ex = self.data.get("extraction") if isinstance(self.data.get("extraction"), dict) else {}
        self.frontend = ex.get("frontend") if ex.get("frontend") in FRONTENDS else None
        self.units = sorted({i.get("unit") or i.get("path") for i in ex.get("inputs") or [] if isinstance(i, dict)
                             and isinstance(i.get("unit") or i.get("path"), str)})
        self.sidecar = (ex.get("sidecar") or {}).get("path") if self.frontend == "solidity" else None
        self.config = (ex.get("config") or {}).get("path") if self.frontend == "go" else None
        t = self.data.get("target") if isinstance(self.data.get("target"), dict) else {}
        self.repo, self.commit = t.get("repo"), t.get("commit")
        self.ups = [] if self.frontend else upstream(self.data)


def docs_in_scope(tree: Path, milestone: str) -> dict[str, Doc]:
    facts = set()
    for p in sorted((tree / "laws" / milestone).glob("L*.json")):
        f = json.loads(p.read_text(encoding="utf-8")).get("facts")
        if isinstance(f, str):
            facts.add(f)
    out: dict[str, Doc] = {}
    todo = sorted(facts)
    while todo:
        rel = todo.pop()
        if rel in out or not (tree / rel).is_file() or not rel.endswith(".json"):
            continue
        try:
            out[rel] = Doc(tree, rel)
        except ValueError:
            continue
        todo += out[rel].ups
    return dict(sorted(out.items()))


def content(doc: dict) -> dict:
    """A document without its extraction inputs' hashes (what changes with any byte of an input file)."""
    d = json.loads(json.dumps(doc))
    ex = d.get("extraction")
    if isinstance(ex, dict):
        for i in ex.get("inputs") or []:
            if isinstance(i, dict):
                i.pop("sha256", None)
    return d


def diff_paths(a, b, path: str = "", out: list | None = None, limit: int = 12) -> list[str]:
    """The first `limit` JSON paths where a and b differ, in a fixed order."""
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if type(a) is not type(b):
        out.append(path or "/")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}")
            else:
                diff_paths(a[k], b[k], f"{path}/{k}", out, limit)
            if len(out) >= limit:
                break
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}[len {len(a)} -> {len(b)}]")
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{path}/{i}", out, limit)
            if len(out) >= limit:
                break
    elif a != b:
        out.append(path or "/")
    return out[:limit]


def _named(x) -> str | None:
    if isinstance(x, dict):
        for k in ("name", "id", "function", "fn"):
            if isinstance(x.get(k), str):
                return x[k]
    return None


def _collection(d) -> bool:
    return isinstance(d, dict) and len(d) >= 2 and all(isinstance(v, dict) for v in d.values())


def changed_names(a, b, depth: int = 0, out: set | None = None) -> set:
    """The names of the entries of a document's collections (the named elements of a top-level list; the keys of a
    dict of objects, two levels down at most) whose content differs between a and b: what a law file can mention of
    a changed document (an action, a function, a storage family)."""
    out = set() if out is None else out
    if isinstance(a, dict) and isinstance(b, dict) and depth <= 2:
        coll = depth >= 1 and _collection(a) and _collection(b)
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                if coll:
                    out.add(k)
                if k in a and k in b:
                    changed_names(a[k], b[k], depth + 1, out)
    elif isinstance(a, list) and isinstance(b, list) and depth == 1:
        na = {_named(x): x for x in a if _named(x)}
        nb = {_named(x): x for x in b if _named(x)}
        out |= {n for n in set(na) | set(nb) if na.get(n) != nb.get(n)}
    return out


# ================================================================================================ the checkout
def inside(checkout: Path, rel: str) -> str | None:
    """None when rel names a tracked regular file inside the checkout, else why not."""
    if not rel or rel.startswith("/") or "\\" in rel or "\0" in rel:
        return "not a relative path"
    parts = rel.split("/")
    if any(p in ("", ".", "..") for p in parts) or os.path.normpath(rel) != rel:
        return "not a normalized path inside the checkout (no '.', '..' or empty parts)"
    p = checkout / rel
    try:
        real = Path(os.path.realpath(p))
        real.relative_to(Path(os.path.realpath(checkout)))
    except ValueError:
        return "it leaves the checkout through a link"
    if p.is_symlink() or not p.is_file():
        return "not a regular file of the checkout"
    if git_out(checkout, "cat-file", "-e", f"HEAD:{rel}").returncode != 0:
        return "not tracked at the checkout's HEAD"
    return None


def patch_paths(patch: str) -> tuple[set, list[str]]:
    """(paths the patch touches, problems): a patch modifies existing files only."""
    paths, bad = set(), []
    for line in patch.splitlines():
        if line.startswith(("--- ", "+++ ")):
            p = line[4:].split("\t")[0].strip()
            if p == "/dev/null":
                bad.append("creates or deletes a file")
                continue
            if p.startswith(("a/", "b/")):
                p = p[2:]
            paths.add(p)
        elif line.startswith("diff --git "):
            for tok in line[len("diff --git "):].split(" "):
                paths.add(tok[2:] if tok.startswith(("a/", "b/")) else tok)
        elif line.startswith(("rename ", "copy ", "new file mode", "deleted file mode", "old mode", "new mode",
                              "GIT binary patch", "Binary files")):
            bad.append(f"not a plain modification ({line.split(' ')[0]} ...)")
    return paths, bad


def apply_mutation(m: dict, src: Path, checkout: Path) -> tuple[str | None, str | None]:
    """(unified diff of the mutated file, None) or (None, why it was refused); src is a scratch copy of the checkout."""
    rel = m["file"]
    why = inside(checkout, rel)
    if why:
        return None, f"{rel}: {why}"
    target = src / rel
    before = target.read_bytes()
    try:
        old_text = before.decode("utf-8")
    except UnicodeDecodeError:
        return None, f"{rel}: not UTF-8 text"
    if "edit" in m:
        e = m["edit"]
        lines = old_text.splitlines(keepends=True)
        if e["line"] > len(lines):
            return None, f"{rel}: line {e['line']} is past the end ({len(lines)} lines)"
        ln = lines[e["line"] - 1]
        body = ln.rstrip("\r\n")
        if body.count(e["old"]) != 1:
            return None, f"{rel}:{e['line']}: the old text occurs {body.count(e['old'])} times on that line, not once"
        lines[e["line"] - 1] = body.replace(e["old"], e["new"]) + ln[len(body):]
        new_text = "".join(lines)
    else:
        paths, bad = patch_paths(m["patch"])
        if bad or paths != {rel}:
            return None, f"the patch must modify {rel} only: " + "; ".join(bad or [f"it touches {sorted(paths)}"])
        pf = src.parent / f"{src.name}.patch"
        pf.write_text(m["patch"] if m["patch"].endswith("\n") else m["patch"] + "\n", encoding="utf-8")
        for args in (["--check"], []):
            p = subprocess.run(["git", "apply", *args, "--whitespace=nowarn", str(pf)], cwd=str(src),
                               capture_output=True, text=True)
            if p.returncode != 0:
                pf.unlink(missing_ok=True)
                return None, f"git apply refused the patch: {(p.stdout + p.stderr).strip()[-300:]}"
        pf.unlink(missing_ok=True)
        new_text = target.read_text(encoding="utf-8")
    if new_text == old_text:
        return None, f"{rel}: the mutation changes nothing"
    target.write_text(new_text, encoding="utf-8")
    diff = "".join(difflib.unified_diff(old_text.splitlines(keepends=True), new_text.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}", n=2))
    return diff, None


# ================================================================================================ one round
class Round:
    def __init__(self, milestone: str, rnd: int, spec_path: Path, spec: dict, commit: str, work: Path,
                 checkout_arg: str | None, budget: dict):
        self.milestone, self.rnd, self.spec, self.commit, self.work = milestone, rnd, spec, commit, work
        self.spec_path = spec_path
        self.budget = budget
        self.runs_used = 0
        self.timings: dict = {"mutations": {}, "baseline": {}}
        self.base_runs: dict = {}
        t0 = time.monotonic()
        self.exclude = (f"gen/{milestone}/refute", "spec/heldout")
        self.T0 = archive(ROOT, commit, work / "target", self.exclude)   # also where the baseline laws run
        self.timings["stage_s"] = round(time.monotonic() - t0, 1)
        self.docs = docs_in_scope(self.T0, milestone)
        self.base_laws = self.law_files(self.T0)
        self.cfg = json.loads((self.T0 / "config" / "holon.json").read_text(encoding="utf-8"))
        front = [d for d in self.docs.values() if d.frontend]
        repos = sorted({d.repo for d in front if isinstance(d.repo, str)})
        if not repos:
            raise MutationError(f"no frontend document of laws/{milestone} names its target repository")
        if len(repos) > 1 and checkout_arg:
            raise MutationError(f"the documents name several repositories {repos}: --checkout is ambiguous")
        self.repo = repos[0] if len(repos) == 1 else None
        srcs = (self.cfg.get("extract") or {}).get("sources") or {}
        if len(repos) > 1:
            raise MutationError(f"the documents name several repositories {repos}; this driver takes one")
        co = checkout_arg or srcs.get(self.repo)
        if not co:
            raise MutationError(f"no checkout of {self.repo}: config extract.sources names none; pass --checkout")
        self.checkout = Path(co).resolve()
        p = git_out(self.checkout, "rev-parse", "HEAD")
        self.head = p.stdout.decode().strip() if p.returncode == 0 else None
        if not self.head:
            raise MutationError(f"{self.checkout} is not a git checkout")
        dirty = git_out(self.checkout, "status", "--porcelain", "--untracked-files=no").stdout.decode().strip()
        if dirty:
            raise MutationError(f"the checkout {self.checkout} has local changes: {dirty[:300]}")
        pinned = sorted({d.commit for d in front if isinstance(d.commit, str)})
        if self.head not in pinned:
            raise MutationError(f"the checkout is at {self.head}; the documents are at {pinned}")
        self.places = {"work": work, "checkout": self.checkout, "root": ROOT, "home": Path.home()}
        self.reach = {r: d for r, d in self.docs.items() if d.frontend and d.commit == self.head}
        self.baseline: dict = {}
        self.keep = False

    # ---------------------------------------------------------------- helpers
    def scrub(self, text: str) -> str:
        from ..mutate.common import scrub
        return scrub(text or "", self.places)[-TAIL:].strip()

    def readers(self, rel: str) -> list[str]:
        return sorted(r for r, d in self.reach.items() if rel in d.units)

    def extract(self, d: Doc, tree: Path, src: Path, tag: str) -> tuple[str | None, str | None]:
        """(the document text in the committed format with the committed provenance, None) or (None, error)."""
        out = self.work / "x" / tag
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        if d.frontend == "solidity":
            if not d.sidecar or not (tree / d.sidecar).is_file():
                return None, f"its sidecar {d.sidecar} is not in the target tree"
            rc, txt = holon_in(tree, ["extract", "solidity", "--root", tree, "--sidecar", tree / d.sidecar,
                                      "--source", src, "--out", out / "doc.json"], 1800)
            res = out / "doc.json"
        else:
            if not d.config or not (tree / d.config).is_file():
                return None, f"its configuration {d.config} is not in the target tree"
            stem = Path(d.rel).name[: -len(".json")]
            stem = stem[: -len(".extracted")] if stem.endswith(".extracted") else stem
            stem = stem[: -len(".go")] if stem.endswith(".go") else stem
            rc, txt = holon_in(tree, ["extract", "go", "--root", tree, "--config", tree / d.config, "--src", src,
                                      "--out-dir", out / "go", "--doc", stem], 1800)
            res = out / "go" / f"{stem}.go.extracted.json"
        if rc != 0 or not res.is_file():
            return None, f"holon extract {d.frontend} (exit {rc}): {self.scrub(txt)}"
        new = json.loads(res.read_text(encoding="utf-8"))
        fmt = json_format(d.text) or (2, False)
        return json.dumps(new, indent=fmt[0], sort_keys=True, ensure_ascii=fmt[1]) + "\n", None

    def base_doc(self, rel: str) -> dict:
        """The baseline re-extraction of a document (once per round)."""
        if rel not in self.baseline:
            d = self.docs[rel]
            t0 = time.monotonic()
            text, err = self.extract(d, self.T0, self.checkout, "baseline")
            self.timings["baseline"][f"extract:{rel}"] = round(time.monotonic() - t0, 1)
            self.baseline[rel] = {"text": text, "error": err,
                                  "reproduces": text == d.text if text is not None else False}
        return self.baseline[rel]

    def repin(self, tree: Path, old: str, new: str) -> list[str]:
        """Replace a document's committed sha256 by its new one in the tree's sidecars and ledgers."""
        hit = []
        cands = sorted(set((tree / "spec").glob("*/lib/**/*.json")) | set((tree / "spec").glob("*/ledger.json")))
        for p in cands:
            t = p.read_text(encoding="utf-8")
            if old in t:
                p.write_text(t.replace(old, new), encoding="utf-8")
                hit.append(p.relative_to(tree).as_posix())
        return hit

    def law_files(self, tree: Path) -> dict[str, dict]:
        return {p.stem: json.loads(p.read_text(encoding="utf-8"))
                for p in sorted((tree / "laws" / self.milestone).glob("L*.json"))}

    def run_law(self, tree: Path, lid: str) -> dict:
        t0 = time.monotonic()
        rc, txt = holon_in(tree, ["run", "--milestone", self.milestone, "--laws", lid], self.budget["law_timeout_s"])
        secs = round(time.monotonic() - t0, 1)
        rp = tree / "results" / self.milestone / f"{lid}.json"
        if rc is None:
            return {"status": "timeout", "detail": f"over {self.budget['law_timeout_s']} s", "_s": secs}
        if rc != 0 or not rp.is_file():
            return {"status": "error", "detail": f"holon run (exit {rc}): {self.scrub(txt)}", "_s": secs}
        r = json.loads(rp.read_text(encoding="utf-8"))
        w = r.get("witness")
        return {"status": r.get("status"), "statement_hash": r.get("statement_hash"),
                "witness_sha256": sha256_bytes(json.dumps(w, sort_keys=True).encode()) if w is not None else None,
                "_s": secs}

    def baseline_run(self, lid: str) -> dict:
        if lid not in self.base_runs:
            self.runs_used += 1
            self.base_runs[lid] = self.run_law(self.T0, lid)
            self.timings["baseline"][f"run:{lid}"] = self.base_runs[lid].pop("_s")
        return self.base_runs[lid]

    # ---------------------------------------------------------------- one mutant
    def mutant(self, m: dict) -> dict:
        tm: dict = {}
        self.timings["mutations"][m["id"]] = tm
        rec = {"id": m["id"], "file": m["file"], "spec_sha256": sha256_bytes(dumps(m).encode()), "diff": None,
               "documents": {}, "derivation": None, "runs": {}, "not_run": {}, "verdict": None, "why": None,
               "obstructions": []}
        if "expect" in m:
            rec["expect"] = m["expect"]
        mdir = self.work / "m" / m["id"]
        shutil.rmtree(mdir, ignore_errors=True)
        mdir.mkdir(parents=True)
        try:
            t0 = time.monotonic()
            src = clone_at(self.checkout, self.head, mdir / "src")
            diff, why = apply_mutation(m, src, self.checkout)
            tm["apply_s"] = round(time.monotonic() - t0, 1)
            if why:
                rec["verdict"], rec["why"] = "refused", why
                return rec
            # the mutant is planted at the documents' commit: git treats the file as unchanged in this scratch clone,
            # so the frontends' and holon run's checkout guards (a clean checkout at that commit) hold here, and only
            # here; the record carries the diff
            git_out(src, "update-index", "--assume-unchanged", "--", m["file"])
            rec["diff"] = diff
            readers = self.readers(m["file"])
            if not readers:
                rec["verdict"] = "missed"
                rec["why"] = (f"no document in scope lists {m['file']} among its extraction inputs at the checkout's "
                              f"commit, so no law can see the mutation (an extraction or scope gap)")
                return rec
            U = archive(ROOT, self.commit, mdir / "tree", self.exclude)
            point_config(U, self.checkout, src)
            changed: dict[str, tuple[str, str]] = {}
            names: set = set()
            for rel in readers:
                d = self.docs[rel]
                b = self.base_doc(rel)
                t0 = time.monotonic()
                text, err = self.extract(d, U, src, m["id"])
                tm[f"extract:{rel}"] = round(time.monotonic() - t0, 1)
                e = {"baseline_reproduces": b["reproduces"]}
                if err is not None:
                    e["status"] = "rejected" if b["error"] is None else "error"
                    e["error"] = err
                    if b["error"] is None:
                        rec["obstructions"].append(f"extraction rejects: {rel}")
                    else:
                        e["baseline_error"] = b["error"]
                elif b["error"] is not None:
                    e["status"], e["baseline_error"] = "no_baseline", b["error"]
                else:
                    old, new = json.loads(b["text"]), json.loads(text)
                    if content(old) == content(new):
                        e["status"] = "unchanged"
                    else:
                        e["status"] = "changed"
                        e["paths"] = diff_paths(content(old), content(new))
                        nm = changed_names(content(old), content(new))
                        e["names"] = sorted(nm)[:40]
                        names |= nm
                        changed[rel] = (d.sha256, sha256_bytes(text.encode()))
                        (U / rel).write_text(text, encoding="utf-8")
                rec["documents"][rel] = e
            if rec["obstructions"]:
                rec["verdict"] = "detected"
                return rec
            if any(e["status"] == "no_baseline" for e in rec["documents"].values()):
                rec["verdict"], rec["why"] = "incomplete", "a document's baseline extraction failed"
                return rec
            if not changed:
                rec["verdict"] = "missed"
                rec["why"] = ("the frontends extract the same content from the mutant (only the input files' hashes "
                              "differ): no law can see it")
                return rec
            self.derive(rec, U, changed, names, m, tm)
            return rec
        finally:
            if not self.keep:
                shutil.rmtree(mdir, ignore_errors=True)

    def derive(self, rec: dict, U: Path, changed: dict, names: set, m: dict, tm: dict) -> None:
        der: dict = {"repinned": [], "steps": {}, "added": [], "dropped": [], "statement_changed": [],
                     "facts_changed": 0, "derived_documents": {}}
        rec["derivation"] = der
        pins = set()
        for rel, (old, new) in sorted(changed.items()):
            pins |= set(self.repin(U, old, new))
        before = {r: d.sha256 for r, d in self.docs.items() if not d.frontend and r.startswith("gen/")}
        for step in REGEN:
            t0 = time.monotonic()
            rc, txt = holon_in(U, [step, "--milestone", self.milestone, "--root", U], 3600)
            tm[f"regen:{step}"] = round(time.monotonic() - t0, 1)
            der["steps"][step] = "ok" if rc == 0 else f"exit {rc}: {self.scrub(txt)[-300:]}"
            if rc != 0:
                der["refused"] = f"holon {step} --milestone {self.milestone}"
                rec["obstructions"].append(f"derivation refusal: holon {step}")
                rec["verdict"] = "detected"
                der["repinned"] = sorted(pins)
                return
        for rel, old in sorted(before.items()):
            p = U / rel
            new = sha256_file(p) if p.is_file() else None
            if new != old:
                der["derived_documents"][rel] = "changed" if new else "absent"
                if new:
                    pins |= set(self.repin(U, old, new))
        der["repinned"] = sorted(pins)
        t0 = time.monotonic()
        rc, txt = holon_in(U, ["derive", "--milestone", self.milestone, "--root", U], 3600)
        tm["derive"] = round(time.monotonic() - t0, 1)
        der["steps"]["derive"] = "ok" if rc == 0 else f"exit {rc}: {self.scrub(txt)[-300:]}"
        if rc != 0:
            der["refused"] = f"holon derive --milestone {self.milestone}"
            rec["obstructions"].append("derivation refusal: holon derive")
            rec["verdict"] = "detected"
            return
        base, new = self.base_laws, self.law_files(U)
        der["added"] = sorted(set(new) - set(base))
        der["dropped"] = sorted(set(base) - set(new))
        cands = []
        for lid in sorted(set(base) & set(new)):
            if base[lid] == new[lid]:
                continue
            if {k: v for k, v in base[lid].items() if k != "facts_sha256"} != \
                    {k: v for k, v in new[lid].items() if k != "facts_sha256"}:
                der["statement_changed"].append(lid)
            else:
                cands.append(lid)
        der["facts_changed"] = len(cands)
        for k in ("added", "dropped", "statement_changed"):
            if der[k]:
                rec["obstructions"].append(f"derivation change: {len(der[k])} law(s) {k.replace('_', ' ')}")
        self.reruns(rec, U, cands, names, m, new, tm)

    def reruns(self, rec: dict, U: Path, cands: list, names: set, m: dict, laws: dict, tm: dict) -> None:
        asked = [x for x in m.get("laws") or []]
        for lid in asked:
            if lid not in cands:
                rec["not_run"][lid] = ("its law file is unchanged: the mutation touches neither its facts nor its "
                                       "closure" if lid in laws else "no such law after the re-derivation")
        long = sorted(n for n in names if len(n) >= 4)

        def mentions(lid: str) -> bool:
            t = json.dumps(laws[lid], sort_keys=True)
            return any(n in t for n in long)
        order = [x for x in asked if x in cands]
        order += [x for x in cands if x not in order and mentions(x)]
        order += [x for x in cands if x not in order]
        flips = []
        for lid in order:
            need = (0 if lid in self.base_runs else 1) + 1
            if self.runs_used + need > self.budget["max_law_runs"]:
                rec["not_run"][lid] = f"the round's cap of {self.budget['max_law_runs']} law runs is reached"
                continue
            b = self.baseline_run(lid)
            self.runs_used += 1
            r = self.run_law(U, lid)
            tm[f"run:{lid}"] = r.pop("_s")
            moved = (b["status"] in ("PROVED", "REFUTED", "UNKNOWN") and r["status"] in ("PROVED", "REFUTED", "UNKNOWN")
                     and b["status"] != r["status"])
            rec["runs"][lid] = {"baseline": b, "mutant": r, "flip": moved,
                                "selected": "spec" if lid in asked else ("names" if mentions(lid) else "rest")}
            if moved:
                flips.append(lid)
        if flips:
            rec["obstructions"].append(f"law flips: {', '.join(flips)}")
        if rec["obstructions"]:
            rec["verdict"] = "detected"
            return
        unfinished = [lid for lid, x in rec["runs"].items()
                      if x["mutant"]["status"] in ("timeout", "error") or x["baseline"]["status"] in ("timeout", "error")]
        skipped = [lid for lid in order if lid not in rec["runs"]]
        if unfinished or skipped:
            rec["verdict"] = "incomplete"
            rec["why"] = (f"nothing moved among the {len(rec['runs']) - len(unfinished)} law(s) that finished; "
                          f"{len(skipped)} touched law(s) not run within the caps, {len(unfinished)} run(s) unfinished")
        else:
            rec["verdict"] = "missed"
            rec["why"] = (f"the documents changed but no statement did, and none of the {len(rec['runs'])} touched "
                          f"law(s) changed status on re-run")

    # ---------------------------------------------------------------- the record
    def build(self) -> dict:
        muts = [self.mutant(m) for m in self.spec["mutations"]]
        verdicts = {v: sorted(r["id"] for r in muts if r["verdict"] == v)
                    for v in ("detected", "missed", "incomplete", "refused")}
        base_docs = {rel: {"reproduces": b["reproduces"], "error": b["error"]}
                     for rel, b in sorted(self.baseline.items())}
        out_of_reach = sorted(r for r, d in self.docs.items() if d.frontend and d.commit != self.head)
        spec_rel = rel_path(self.spec_path)
        rd = f"audit/rounds/{self.milestone}/round{self.rnd}"
        evidence = [f"{rd}/a1.json"] + ([spec_rel] if spec_rel.startswith(rd + "/") else [])
        tried = (f"`python -m holon audit mutation --milestone {self.milestone} --round {self.rnd} --spec {spec_rel}`: "
                 f"{len(muts)} mutant(s) of the auditor's choosing on {self.repo}@{self.head[:12]}; "
                 f"{len(verdicts['detected'])} detected, {len(verdicts['missed'])} missed, "
                 f"{len(verdicts['incomplete'])} incomplete, {len(verdicts['refused'])} refused; caps "
                 f"{self.budget['law_timeout_s']} s per law run, {self.budget['max_law_runs']} runs per round "
                 f"({self.runs_used} used).")
        if verdicts["missed"]:
            tried += (" Each missed mutant is an extraction or rule gap unless the auditor judged it equivalent from "
                      "its diff before the run; file the misses as findings and list their ids.")
        return {
            "a1_version": A1_VERSION, "milestone": self.milestone, "round": self.rnd, "target_commit": self.commit,
            "checkout": {"repo": self.repo, "commit": self.head},
            "spec": {"path": spec_rel, "sha256": sha256_file(self.spec_path), "body": self.spec},
            "budget": dict(self.budget), "law_runs": self.runs_used,
            "scope": {"documents": sorted(self.docs), "reachable": sorted(self.reach), "out_of_reach": out_of_reach},
            "baseline": {"documents": base_docs,
                         "runs": {k: v for k, v in sorted(self.base_runs.items())}},
            "mutations": muts, "summary": verdicts,
            "attack": {"id": "A1", "category": "mutation_adequacy", "auditor_type": "A1", "run": True,
                       "tried": tried, "result": "finding" if verdicts["missed"] else "no_finding", "findings": [],
                       "evidence": evidence}}


def rel_path(p: Path) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.name


def build(milestone: str, rnd: int, spec_path: Path, commit: str, work: Path, checkout: str | None,
          law_timeout: int | None, max_runs: int | None, keep: bool = False) -> tuple[dict, dict]:
    spec = load_spec(spec_path, milestone)
    budget = budget_of(spec, law_timeout, max_runs)
    R = Round(milestone, rnd, spec_path, spec, commit, work, checkout, budget)
    R.keep = keep
    rec = R.build()
    return rec, R.timings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit mutation", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--spec", required=True, help="the auditor's mutation spec (holon-audit-a1-spec/0.1)")
    ap.add_argument("--target", help="the audited commit of this repository (default HEAD)")
    ap.add_argument("--checkout", help="the target's checkout (default: config extract.sources of its repository)")
    ap.add_argument("--out", help="default audit/rounds/<M>/round<n>/a1.json")
    ap.add_argument("--work", help="scratch directory, kept (default: a fresh temporary directory, removed after)")
    ap.add_argument("--keep-trees", action="store_true", help="keep each mutant's scratch trees under --work")
    ap.add_argument("--law-timeout", type=int, help="seconds per `holon run` of one law")
    ap.add_argument("--max-law-runs", type=int, help="law runs per round, baseline runs included")
    ap.add_argument("--check", action="store_true", help="rerun and compare with the committed a1.json byte for byte")
    a = ap.parse_args(argv)
    if a.round < 1:
        print("mutation: rounds are numbered from 1", file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else ROOT / "audit" / "rounds" / a.milestone / f"round{a.round}" / "a1.json"
    out = out if out.is_absolute() else ROOT / out
    target = a.target
    if a.check:
        if not out.is_file():
            print(f"mutation --check: {out} does not exist", file=sys.stderr)
            return 2
        target = json.loads(out.read_text(encoding="utf-8"))["target_commit"]
    work = Path(a.work).resolve() if a.work else Path(tempfile.mkdtemp(prefix="holon-a1-"))
    try:
        commit = resolve_commit(target or "HEAD")
        rec, timings = build(a.milestone, a.round, Path(a.spec).resolve(), commit, work, a.checkout,
                             a.law_timeout, a.max_law_runs, keep=bool(a.work and a.keep_trees))
    except MutationError as e:
        print(f"mutation: refused: {e}", file=sys.stderr)
        return 2
    finally:
        if not a.work:
            shutil.rmtree(work, ignore_errors=True)
    text = dumps(rec)
    if a.check:
        same = out.read_text(encoding="utf-8") == text
        print(f"mutation --check: {'identical' if same else 'DIFFERS from'} {rel_path(out)}")
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    (out.parent / (out.stem + ".timings.json")).write_text(dumps(timings), encoding="utf-8")
    s = rec["summary"]
    print(f"mutation: wrote {rel_path(out)}: " + ", ".join(f"{len(v)} {k}" for k, v in s.items()) +
          f"; {rec['law_runs']} law run(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
