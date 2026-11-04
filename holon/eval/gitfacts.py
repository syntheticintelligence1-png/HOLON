"""Git facts of a fix commit (rules C2b-C2c, C3, C5; I48), read from holon's own partial clones (common.repo_cache).

commit_facts(url, sha) says whether sha is reachable from a branch or a tag of the public repository and, when it is,
what the protocol derives from it: the pre-fix commit (its first parent), the fix date (its committer date, UTC), the
changed source files split into test, generated, frontend and other files, their numstat line counts and the frontend
reach. fix_diff(url, prefix, fix, files) is the diff a labeller reads; changed_old_lines(url, prefix, fix, path) the
pre-fix lines the fix deletes or changes. Nothing is ever fetched by sha: blobs of a reachable commit come through the
partial clone's on-demand fetch.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import PurePosixPath

from . import common

_SHA = re.compile(r"[0-9a-f]{40}")

# Every option of `git diff` that a git configuration could change, fixed on the command line (rule C5's labeller diff).
DIFF_OPTIONS = ("-c", "core.quotePath=true", "-c", "diff.suppressBlankEmpty=false", "diff", "--no-color",
                "--no-renames", "--no-ext-diff", "--no-textconv", "--diff-algorithm=myers", "--indent-heuristic",
                "--no-relative", "--inter-hunk-context=0", "--src-prefix=a/", "--dst-prefix=b/")
DIFF_CONTEXT = 5


def _ends_with_any(path: str, suffixes) -> bool:
    return any(path.endswith(s) for s in suffixes)


def test_path(path: str, proto: dict) -> bool:
    """A test file: a directory component named in test_dirs, or a basename matching one of test_file_globs."""
    pp = PurePosixPath(path)
    if set(pp.parts[:-1]) & set(proto["test_dirs"]):
        return True
    return any(fnmatch.fnmatchcase(pp.name, g) for g in proto["test_file_globs"])


def generated_by_path(path: str, proto: dict) -> bool:
    """Generated or vendored by location: a directory component in generated_dirs or a basename in generated_globs."""
    pp = PurePosixPath(path)
    if set(pp.parts[:-1]) & set(proto["generated_dirs"]):
        return True
    return any(fnmatch.fnmatchcase(pp.name, g) for g in proto["generated_globs"])


def frontend_exts(proto: dict) -> list[str]:
    return sorted({e for exts in proto["frontend_extensions"].values() for e in exts})


def _blobs_in(d, rev: str, paths: list[str]) -> set[str]:
    """The paths among `paths` that name a blob in rev's tree (trees only: no blob is read)."""
    out = b"".join(common.git(d, "ls-tree", "-z", rev, "--", *paths[i:i + 500], text=False)
                   for i in range(0, len(paths), 500))
    have = set()
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, name = rec.split(b"\t", 1)
        if meta.split(b" ")[1] == b"blob":
            have.add(name.decode("utf-8", errors="surrogateescape"))
    return have & set(paths)


def _read_blobs(d, specs: list[str]) -> dict[str, bytes]:
    """{"rev:path": bytes} for every spec, through one `git cat-file --batch` (the partial clone fetches the blobs)."""
    if not specs:
        return {}
    data = "".join(s + "\n" for s in specs).encode("utf-8", errors="surrogateescape")
    p = subprocess.run(["git", "-C", str(d), "cat-file", "--batch"], input=data, capture_output=True,
                       env=common.git_env(), timeout=3600)
    if p.returncode != 0:
        raise RuntimeError(f"git cat-file --batch in {d}: {p.stderr.decode(errors='replace')[:500]}")
    out, buf, pos = {}, p.stdout, 0
    for s in specs:
        nl = buf.index(b"\n", pos)
        header = buf[pos:nl].split(b" ")
        if len(header) != 3:
            raise RuntimeError(f"git cat-file: no object for {s}: {buf[pos:nl][:200]!r}")
        size = int(header[2])
        out[s] = buf[nl + 1:nl + 1 + size]
        pos = nl + 1 + size + 1
    return out


def _numstat(d, parent: str, fix: str) -> list[tuple[str, int]]:
    """(path, added + deleted lines) of every file the fix changes (git numstat, renames off; binary files count 0)."""
    raw = common.git(d, "diff-tree", "-r", "-z", "--no-renames", "--numstat", parent, fix)
    rows = []
    for rec in raw.split("\0"):
        if not rec:
            continue
        added, deleted, path = rec.split("\t", 2)
        rows.append((path, sum(int(x) for x in (added, deleted) if x != "-")))
    return rows


def commit_facts(url: str, sha: str) -> dict:
    """Rules C2b-C2c for the fix commit sha of the public repository at url: {"found": False} when sha is not a commit
    reachable from a branch or a tag (decided by git rev-list over the clone's refs, the refs fetched again once), else
    {"found": True, "prefix_commit": the first parent, "fix_date": the committer date (UTC, ...Z), "files": the changed
    non-test, non-generated .go and .sol files that are blobs of the pre-fix tree (sorted), "source_lines" and
    "frontend_lines": the numstat lines (added plus deleted) of the changed non-test, non-generated source files and of
    their .go and .sol subset, "diff_files": every changed non-generated source file, tests included (sorted), "reach":
    files is not empty and .go and .sol files hold at least half of the source lines}. A root commit (no parent) is not
    a fix: found false. Generated: a generated directory or basename (protocol generated_dirs, generated_globs), or a
    .go file holding a line matching generated_go_marker, read at the fix when it is there, else at the pre-fix
    commit."""
    proto = common.protocol()
    if not isinstance(sha, str) or not _SHA.fullmatch(sha):
        return {"found": False}
    if not common.is_reachable(url, sha):
        return {"found": False}
    d = common.repo_cache(url)
    head = common.git(d, "show", "-s", "--no-show-signature", "--format=%P%n%cd",
                      "--date=format-local:%Y-%m-%dT%H:%M:%SZ", sha).split("\n")
    parents = head[0].split()
    if not parents:
        return {"found": False}
    parent, fix_date = parents[0], head[1].strip()

    changed = _numstat(d, parent, sha)
    source = [(p, n) for p, n in changed if _ends_with_any(p, proto["source_extensions"])]
    # Generated by content: Go files only, read at the fix when the fix's tree holds them, else at the pre-fix commit.
    go = [p for p, _ in source if p.endswith(".go") and not generated_by_path(p, proto)]
    at_fix = _blobs_in(d, sha, go)
    specs = {p: f"{sha if p in at_fix else parent}:{p}" for p in go}
    blobs = _read_blobs(d, sorted(set(specs.values())))
    marker = re.compile(proto["generated_go_marker"], re.M)
    gen_go = {p for p in go if marker.search(blobs[specs[p]].decode("utf-8", errors="replace"))}

    kept = [(p, n) for p, n in source if not generated_by_path(p, proto) and p not in gen_go]
    nontest = [(p, n) for p, n in kept if not test_path(p, proto)]
    fe = frontend_exts(proto)
    front = [(p, n) for p, n in nontest if _ends_with_any(p, fe)]
    in_prefix = _blobs_in(d, parent, [p for p, _ in front])
    files = sorted(p for p, _ in front if p in in_prefix)
    source_lines = sum(n for _, n in nontest)
    frontend_lines = sum(n for _, n in front)
    return {"found": True, "prefix_commit": parent, "fix_date": fix_date, "files": files,
            "source_lines": source_lines, "frontend_lines": frontend_lines,
            "diff_files": sorted(p for p, _ in kept),
            "reach": len(files) > 0 and frontend_lines * 2 >= source_lines}


def _diff(url: str, prefix: str, fix: str, paths: list[str], context: int) -> str:
    for c in (prefix, fix):
        if not isinstance(c, str) or not _SHA.fullmatch(c):
            raise common.Refused(f"not a commit sha: {c!r}")
    out = common.git(common.repo_cache(url), *DIFF_OPTIONS, f"-U{context}", prefix, fix, "--", *paths, text=False)
    return out.decode("utf-8", errors="replace")


def fix_diff(url: str, prefix: str, fix: str, files: list[str]) -> str:
    """The diff a labeller reads (rule C5): git diff -U5 from the pre-fix commit to the fix over the given files (an
    entry's diff_files), every option a configuration could change fixed on the command line (DIFF_OPTIONS), decoded
    as UTF-8 with errors replaced."""
    return _diff(url, prefix, fix, list(files), DIFF_CONTEXT)


_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def old_lines(diff_text: str) -> list[int]:
    """The old-side lines of every hunk of a -U0 diff whose old count is above 0 (a missing count means 1)."""
    out: set[int] = set()
    for line in diff_text.split("\n"):
        m = _HUNK.match(line)
        if m:
            start = int(m.group(1))
            count = 1 if m.group(2) is None else int(m.group(2))
            out.update(range(start, start + count))
    return sorted(out)


def changed_old_lines(url: str, prefix: str, fix: str, path: str) -> list[int]:
    """The pre-fix lines of path that the fix deletes or changes: the old lines of the hunks of git diff -U0 whose old
    count is above 0 (a pure insertion contributes none)."""
    return old_lines(_diff(url, prefix, fix, [path], 0))
