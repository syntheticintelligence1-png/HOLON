"""Project layout for the corpus and target protocols (I108; holon-layout/0.1; the contract is the docstring of
tests_m6/test_i108_pipeline_totality.py, rules L1-L3).

Two statements a project makes about how it builds, read at the pinned commit only and never invented (Q59):

  L1  remappings: a unit's Foundry project is the nearest directory at or above the unit (inside the checkout) that
      holds foundry.toml. Its remappings are foundry.toml's [profile.default] remappings, in order, then the lines of
      the project's remappings.txt (blank lines and # comments skipped); the first remapping of each (context, prefix)
      is kept. A target and a context are paths relative to the project, rewritten relative to the checkout root (the
      solc base path of the Solidity frontend). No remapping is auto-detected from lib/ (forge's auto_detect_remappings
      is a heuristic, not the project's statement).
  L2  foundry's base path is the project root: a non-relative import resolves against the project, so for every
      top-level directory D of the project that no L1 remapping has as its prefix, the context-scoped remapping
      <project>/:D/=<project>/D/ is added (it applies to units of the project only). A unit outside any Foundry
      project gets no remapping.
  L3  submodules: every gitlink (mode 160000) of the checkout's tree at the pinned commit whose path .gitmodules (read
      at that commit) names; its URL is .gitmodules' url (a relative url resolved against the superproject's
      repository URL; https://github.com/o/r and git@github.com:o/r only, anything else refused). A URL the clone rule
      excludes (the corpus protocol's excluded_repos, or a repository named in spec/M6/predictions/I106.json) is
      refused and never cloned. The gitlinked commit must be reachable from a branch or tag of the submodule's clone
      (nothing is fetched by sha); the submodule is then a detached worktree of that clone at exactly that commit.
      Nested submodules recurse to depth MAX_DEPTH. Every submodule is recorded {path, url, commit, status, reason}.

Nothing here names a target: every name comes from the checkout.
"""
from __future__ import annotations

import posixpath
import re
import subprocess
import tomllib
from pathlib import Path

from . import common

LAYOUT_VERSION = "holon-layout/0.1"
MAX_DEPTH = 3
_SSH = re.compile(r"git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?")


# ------------------------------------------------------------------------------------------------ L1, L2 remappings
def project_of(ck: Path, unit: str) -> str | None:
    """The unit's Foundry project, relative to the checkout ("" for its root), or None."""
    ck = Path(ck)
    d = (ck / unit).parent
    while True:
        if (d / "foundry.toml").is_file():
            rel = d.relative_to(ck).as_posix()
            return "" if rel == "." else rel
        if d == ck or ck not in d.parents:
            return None
        d = d.parent


def _join(proj: str, p: str) -> str:
    trail = p.endswith("/")
    j = posixpath.normpath(posixpath.join(proj, p)) if proj else posixpath.normpath(p)
    return j + ("/" if trail and not j.endswith("/") else "")


def _split(r: str):
    """(context, prefix, target) of a remapping "[context:]prefix=target"; None when malformed."""
    if "=" not in r:
        return None
    left, target = r.split("=", 1)
    ctx, prefix = (left.split(":", 1) if ":" in left else ("", left))
    if not prefix:
        return None
    return ctx.strip(), prefix.strip(), target.strip()


def remappings(ck: Path, proj: str | None) -> list[dict]:
    """[{remapping, source}] of a Foundry project (L1, L2); [] for None."""
    if proj is None:
        return []
    ck = Path(ck)
    pd = ck / proj if proj else ck
    raw = []
    try:
        toml = tomllib.loads((pd / "foundry.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        toml = {}
    rs = ((toml.get("profile") or {}).get("default") or {}).get("remappings") or []
    raw += [(x, "foundry.toml") for x in rs if isinstance(x, str)]
    txt = pd / "remappings.txt"
    if txt.is_file():
        for ln in txt.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                raw.append((ln, "remappings.txt"))
    out, seen = [], set()
    for r, src in raw:
        p = _split(r)
        if p is None:
            continue
        ctx, prefix, target = p
        if (ctx, prefix) in seen:
            continue
        seen.add((ctx, prefix))
        c = (_join(proj, ctx) if ctx else "")
        if ctx and ctx.endswith("/") and not c.endswith("/"):
            c += "/"
        out.append({"remapping": f"{c + ':' if c else ''}{prefix}={_join(proj, target)}", "source": src})
    if proj:
        prefixes = {p for (_c, p) in seen}
        for d in sorted(x.name for x in pd.iterdir() if x.is_dir() and not x.name.startswith(".")):
            if f"{d}/" in prefixes:
                continue
            out.append({"remapping": f"{proj}/:{d}/={proj}/{d}/", "source": "base_path"})
    return out


# ------------------------------------------------------------------------------------------------ L3 submodules
def _git(d: Path, *args, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(d), *args], capture_output=True, text=True, timeout=timeout,
                          env=common.git_env())


def _gitmodules(d: Path, commit: str) -> dict:
    """{path: url} of .gitmodules at the commit."""
    p = _git(d, "config", "--blob", f"{commit}:.gitmodules", "--get-regexp", r"^submodule\..*\.(path|url)$")
    if p.returncode != 0:
        return {}
    by: dict = {}
    for ln in p.stdout.splitlines():
        k, _, v = ln.partition(" ")
        m = re.fullmatch(r"submodule\.(.*)\.(path|url)", k)
        if m:
            by.setdefault(m.group(1), {})[m.group(2)] = v.strip()
    return {x["path"]: x.get("url") for x in by.values() if x.get("path")}


def _gitlinks(d: Path, commit: str) -> dict:
    p = _git(d, "ls-tree", "-r", "-z", commit)
    out = {}
    for ent in p.stdout.split("\0"):
        if ent.startswith("160000 commit "):
            meta, _, path = ent.partition("\t")
            out[path] = meta.split()[2]
    return out


def _candidates(root: Path) -> str:
    p = Path(root) / "spec" / "M6" / "predictions" / "I106.json"
    try:
        return p.read_text(encoding="utf-8").lower()
    except OSError:
        return ""


def resolve_url(url: str | None, parent_url: str) -> str:
    """The https GitHub URL of a submodule url (common.Refused otherwise)."""
    if not url:
        raise common.Refused("no url in .gitmodules")
    u = url.strip()
    if u.startswith("./") or u.startswith("../"):
        po, pn = common.gh_slug(parent_url)
        u = "https://github.com/" + posixpath.normpath(posixpath.join(f"{po}/{pn}", u))
    m = _SSH.fullmatch(u)
    if m:
        u = f"https://github.com/{m.group(1)}/{m.group(2)}"
    try:
        o, n = common.gh_slug(u)
    except common.Refused:
        raise common.Refused(f"{url}: not a GitHub repository URL (the clone rule clones GitHub repositories only)")
    return f"https://github.com/{o}/{n}"


def submodules(ck: Path, commit: str, parent_url: str, init: bool = False, prefix: str = "", depth: int = 0,
               root: Path | None = None) -> list[dict]:
    """L3: the records of every submodule of the checkout at commit (initialized when init)."""
    ck = Path(ck)
    mods = _gitmodules(ck, commit)
    links = _gitlinks(ck, commit)
    cands = _candidates(root or common.ROOT)
    out = []
    for path in sorted(links):
        sha = links[path]
        rec = {"path": prefix + path, "url": mods.get(path), "commit": sha, "status": "refused", "reason": None}
        out.append(rec)
        if path not in mods:
            rec["reason"] = "a gitlink .gitmodules does not name"
            continue
        try:
            url = resolve_url(mods[path], parent_url)
            rec["url"] = url
            o, n = common.gh_slug(url)
            if common.excluded(url):
                raise common.Refused(f"{url} is excluded by the clone rule (protocol excluded_repos): never cloned")
            if cands and (f"github.com/{o}/{n}".lower() in cands or f"\"{o}/{n}\"".lower() in cands):
                raise common.Refused(f"{url} is excluded by the clone rule (an I106 candidate): never cloned")
            if not init:
                rec["status"], rec["reason"] = "listed", "not initialized (init False)"
                continue
            if depth >= MAX_DEPTH:
                raise common.Refused(f"nested deeper than {MAX_DEPTH}")
            clone = common.repo_cache(url)
            if sha not in common.reachable(clone) and sha not in common.reachable(clone, refresh=True):
                raise common.Refused(f"{url}@{sha} is not reachable from a branch or tag (nothing is fetched by sha)")
            dest = ck / path
            if dest.exists() and any(dest.iterdir()):
                raise common.Refused(f"{path} is not empty in the checkout")
            if dest.exists():
                dest.rmdir()
            subprocess.run(["git", "-C", str(clone), "worktree", "prune"], capture_output=True, env=common.git_env())
            common.git(clone, "worktree", "add", "--detach", "--force", str(dest), sha, timeout=7200)
            rec["status"], rec["reason"] = "initialized", None
            out += submodules(dest, sha, url, init=True, prefix=prefix + path + "/", depth=depth + 1, root=root)
        except (common.Refused, RuntimeError, subprocess.TimeoutExpired) as e:
            rec["reason"] = str(e)[:500]
    return out


def drop_submodules(ck: Path, recs: list[dict]) -> None:
    """Remove the worktrees submodules() added (deepest first)."""
    for r in sorted(recs, key=lambda x: -x["path"].count("/")):
        if r["status"] == "initialized" and r.get("url"):
            try:
                clone = common.repo_cache(r["url"])
            except (common.Refused, RuntimeError):
                continue
            subprocess.run(["git", "-C", str(clone), "worktree", "remove", "--force", str(Path(ck) / r["path"])],
                           capture_output=True, env=common.git_env())
