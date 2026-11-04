"""python -m holon eval index --system ID --out FILE (rule C2; I48): what a collector of one system needs from its indexes.

For every index of the system, in the protocol's order, one record:
- ghsa and geth (mechanical): the snapshot (the protocol's pin), the exact item list at the pin (enumeration,
  published, order, item URL, title, the pre-filter's excluded_by), and, for every item the pre-filter lets through
  ("opened"), the text its description must be an excerpt of (whitespace collapsed), the URLs it gives, the commits it
  names in the system's repositories (each with its reachability and committer date) and the fix the rule names (the
  earliest reachable named commit by committer date, ties by sha) or null. A pre-filtered item is listed with its
  item, published, title null and excluded_by, and nothing of it is printed or stored;
- folder: the snapshot (the pin) and the reports the folder holds there (every .pdf or .md file under it other than a
  README.md), each with its item URL and the earliest commit of the pin's first-parent history adding the path (the
  date a report without its own date takes);
- page: the page's URL (the collector fetches it and records the final URL and the sha256 of the bytes).

FILE must lie outside the repository. The advisory database is read at its pin only: holon's commit-graph clone
(--filter=tree:0) proves the pin reachable from the pinned branch, and only then is the pin fetched by sha, depth 1,
into a separate bare repository; every advisory file there is parsed once and the matches of every system cached
under ~/.holon/eval/index/ (pre-filtered advisories without their text).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import threading
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from . import common

ADVISORY_DB = "https://github.com/github/advisory-database"
ADVISORY_DIRS = ("advisories/github-reviewed", "advisories/unreviewed")
INDEX_VERSION = "holon-eval-index/0.1"


# ---------------------------------------------------------------------------------------------- dates and the pre-filter
def published_utc(value) -> datetime | None:
    """An index entry's published value as a UTC instant (an ISO date or timestamp; no offset means UTC), or None when
    it is missing or does not parse (such an entry is no item)."""
    if not isinstance(value, str):
        return None
    try:
        t = datetime.fromisoformat(value)
    except ValueError:
        return None
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def cutoff(proto: dict) -> datetime:
    t = published_utc(proto["cutoff"])
    if t is None:
        raise common.Refused(f"the protocol's cutoff {proto['cutoff']!r} does not parse")
    return t


def strings_of(obj) -> list[str]:
    """Every string value of a JSON document at any depth (object keys are not values)."""
    out: list[str] = []

    def walk(x):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(obj)
    return out


def first_pattern(texts, proto: dict) -> str | None:
    """The first excluded_repos pattern, in the protocol's order, that one of the texts holds (case-insensitive)."""
    low = [t.lower() for t in texts if isinstance(t, str)]
    for x in proto["excluded_repos"]:
        pat = x["pattern"].lower()
        if any(pat in t for t in low):
            return x["pattern"]
    return None


def first_subject(texts, proto: dict) -> str | None:
    """The first excluded subject, in the protocol's order, that one of the texts names as a whole word
    (case-insensitive; dots and dashes literal)."""
    ts = [t for t in texts if isinstance(t, str)]
    for subj in proto["excluded_subjects"]["subjects"]:
        rx = re.compile(r"(?<!\w)" + re.escape(subj) + r"(?!\w)", re.IGNORECASE)
        if any(rx.search(t) for t in ts):
            return subj
    return None


def prefilter(doc, proto: dict) -> dict | None:
    """The pre-filter of a mechanical item (excluded_subjects.rule): {"pattern": P} when a string value of the item
    holds an excluded_repos pattern, else {"subject": S} when one names an excluded subject, else None."""
    vals = strings_of(doc)
    pat = first_pattern(vals, proto)
    if pat is not None:
        return {"pattern": pat}
    subj = first_subject(vals, proto)
    return None if subj is None else {"subject": subj}


# ---------------------------------------------------------------------------------------------- repository names
def slug(url: str) -> str:
    owner, name = common.gh_slug(url)
    return f"github.com/{owner}/{name}".lower()


def names_repo(text: str, repo_slug: str) -> bool:
    """text names the repository: its lowercase form holds the slug with no [a-z0-9.-] character before it and, after
    it, the end, one of / ? # @, or .git followed by the end or one of those."""
    rx = r"(?<![a-z0-9.-])" + re.escape(repo_slug) + r"(?:\.git)?(?=\Z|[/?#@])"
    return re.search(rx, text.lower()) is not None


def _strs(x) -> list:
    return x if isinstance(x, list) else []


def _ref_urls(doc: dict) -> list[str]:
    return [r["url"] for r in _strs(doc.get("references")) if isinstance(r, dict) and isinstance(r.get("url"), str)]


def _link_urls(doc: dict) -> list[str]:
    return [u for u in _strs(doc.get("links")) if isinstance(u, str)]


_COMMIT = re.compile(r"(?<![A-Za-z0-9.-])github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/commit/([0-9A-Fa-f]{40})"
                     r"(?![0-9A-Za-z])")


def named_commits(doc: dict, repos: list[str]) -> list[tuple[str, str]]:
    """The commits an item names in the system's repositories: github.com/<owner>/<repo>/commit/<40 hex> in its
    references[].url or links[] (owner and repo case-insensitive), as (repo as the protocol writes it, lowercase sha),
    sorted, without duplicates."""
    by_slug = {slug(r): r for r in repos}
    found = set()
    for u in _ref_urls(doc) + _link_urls(doc):
        for m in _COMMIT.finditer(u):
            r = by_slug.get(f"github.com/{m.group(1)}/{m.group(2)}".lower())
            if r is not None:
                found.add((r, m.group(3).lower()))
    return sorted(found)


def committer_time(url: str, sha: str) -> tuple[int, str]:
    out = common.git(common.repo_cache(url), "show", "-s", "--no-show-signature", "--format=%ct%n%cd",
                     "--date=format-local:%Y-%m-%dT%H:%M:%SZ", sha).split("\n")
    return int(out[0]), out[1].strip()


def commit_record(doc: dict, repos: list[str]) -> tuple[list[dict], dict | None]:
    """The named commits of an opened item with their reachability and committer date, and the fix the rule names:
    the earliest reachable one by committer date (ties: the sha), or None."""
    named, best = [], None
    for repo, sha in named_commits(doc, repos):
        if common.is_reachable(repo, sha):
            ct, date = committer_time(repo, sha)
            named.append({"repo": repo, "commit": sha, "reachable": True, "committer_date": date})
            if best is None or (ct, sha) < best[0]:
                best = ((ct, sha), {"repo": repo, "commit": sha, "committer_date": date})
        else:
            named.append({"repo": repo, "commit": sha, "reachable": False, "committer_date": None})
    return named, (best[1] if best else None)


def collapse(text: str) -> str:
    return " ".join(text.split())


def excerpt_source(doc: dict, enumeration: str) -> str:
    """What a mechanical item's description is a verbatim excerpt of, whitespace collapsed: the advisory's details
    (ghsa) or the entry's description (geth), each its summary when blank."""
    main = doc.get("details" if enumeration == "ghsa" else "description")
    text = main if isinstance(main, str) and main.strip() else doc.get("summary")
    return collapse(text) if isinstance(text, str) else ""


# ---------------------------------------------------------------------------------------------- the enumerations
def _package_names(doc: dict) -> list[str]:
    """affected[].package.name of an advisory (the string ones)."""
    out = []
    for a in _strs(doc.get("affected")):
        pkg = a.get("package") if isinstance(a, dict) else None
        if isinstance(pkg, dict) and isinstance(pkg.get("name"), str):
            out.append(pkg["name"])
    return out


def _names_one_of(doc, slugs: list[str]) -> bool:
    """The protocol's GHSA match: an advisory object without a withdrawn field one of whose affected[].package.name
    or references[].url names one of the repository slugs (names_repo)."""
    if not isinstance(doc, dict) or "withdrawn" in doc:
        return False
    texts = _package_names(doc) + _ref_urls(doc)
    return any(names_repo(t, s) for s in slugs for t in texts)


def ghsa_items(advisories, repos: list[str], proto: dict) -> list[tuple[dict, dict]]:
    """The GHSA index of a system from (path, advisory JSON) pairs: advisory files under advisories/github-reviewed/
    or advisories/unreviewed/ without a withdrawn field whose affected[].package.name or references[].url names one of
    the repos, published (parsable, UTC) before the cutoff; newest first, ties by GHSA id. (item record, advisory)."""
    slugs = [slug(r) for r in repos]
    cut = cutoff(proto)
    rows = []
    for path, doc in advisories:
        if not path.endswith(".json") or not any(path.startswith(d + "/") for d in ADVISORY_DIRS):
            continue
        if not _names_one_of(doc, slugs):
            continue
        t = published_utc(doc.get("published"))
        if t is None or not t < cut:
            continue
        gid = doc["id"]
        ex = prefilter(doc, proto)
        summary = doc.get("summary")
        title = None if ex is not None else (summary if isinstance(summary, str) and summary.strip() else gid)
        rec = {"item": f"https://github.com/advisories/{gid}", "published": t.date().isoformat(), "title": title,
               "excluded_by": ex}
        rows.append(((-t.timestamp(), gid), rec, doc))
    rows.sort(key=lambda r: r[0])
    return [(rec, doc) for _, rec, doc in rows]


def geth_items(data: bytes, proto: dict, list_url: str) -> list[tuple[dict, dict]]:
    """The geth vulnerabilities index from the list's bytes: every entry published (parsable, UTC) before the cutoff,
    newest first, ties in list order; item <list_url>#<uid percent-encoded> when every entry's uid is a distinct
    string holding a non-space character, else <list_url>#<1-based position>; title the entry's name."""
    entries = json.loads(data)
    uids = [e.get("uid") if isinstance(e, dict) else None for e in entries]
    distinct = all(isinstance(u, str) and u.strip() != "" for u in uids) and len(set(uids)) == len(uids)
    cut = cutoff(proto)
    rows = []
    for pos, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            continue
        t = published_utc(e.get("published"))
        if t is None or not t < cut:
            continue
        ex = prefilter(e, proto)
        name = e.get("name")
        if ex is None and not (isinstance(name, str) and name.strip()):
            raise common.Refused(f"entry {pos} of the geth list has no name")
        frag = urllib.parse.quote(e["uid"], safe="") if distinct else str(pos)
        rec = {"item": f"{list_url}#{frag}", "published": t.date().isoformat(),
               "title": None if ex is not None else name, "excluded_by": ex}
        rows.append(((-t.timestamp(), pos), rec, e))
    rows.sort(key=lambda r: r[0])
    return [(rec, e) for _, rec, e in rows]


def report_item(repo: str, commit: str, path: str) -> str:
    return repo.rstrip("/") + "/blob/" + commit + "/" + urllib.parse.quote(path, safe="/")


def folder_reports(paths: list[str], folder: str) -> list[str]:
    """The reports of an in-repo folder: files under folder/ (any depth) ending .pdf or .md (any case), README.md (any
    case) aside, sorted by path."""
    pre = folder.strip("/") + "/"
    return sorted(p for p in paths if p.startswith(pre) and p.lower().endswith((".pdf", ".md"))
                  and PurePosixPath(p).name.lower() != "readme.md")


# ---------------------------------------------------------------------------------------------- git snapshots
def on_branch(d: Path, sha: str, branch: str) -> bool:
    """sha is reachable from refs/heads/<branch> of the clone (rev-list alone; the refs fetched again once)."""
    if not re.fullmatch(r"[0-9a-f]{40}", sha or ""):
        return False
    for attempt in (0, 1):
        if attempt:
            filt = common.git(d, "config", "--get", "remote.origin.partialclonefilter", check=False).strip()
            common.git(d, "fetch", "--no-progress", "--prune", *([f"--filter={filt}"] if filt else []), "origin",
                       "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*", timeout=7200)
        p = subprocess.run(["git", "-C", str(d), "rev-list", f"refs/heads/{branch}", "--"], capture_output=True,
                           text=True, env=common.git_env(), timeout=3600)
        if p.returncode == 0 and sha in set(p.stdout.split()):
            return True
    return False


PIN_REF = "refs/holon/advisory-pin"


def _bare_clone(url: str, d: Path, filt: str) -> Path:
    if common.excluded(url):
        raise common.Refused(f"{url} is an excluded repository: never cloned")
    if not (d / "HEAD").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        tmp = common.staging(d)
        p = subprocess.run(["git", "clone", "--bare", f"--filter={filt}", "--no-progress", url, str(tmp)],
                           capture_output=True, text=True, timeout=7200, env=common.git_env())
        common._no_excluded_redirect(p.stderr)
        if p.returncode != 0:
            raise RuntimeError(f"git clone {url}: {p.stderr.strip()[:500]}")
        tmp.rename(d)
    return d


def advisory_repo(pin: dict) -> Path:
    """A bare repository holding the advisory database's pinned commit: the pin is first shown reachable from its
    branch on holon's commit-graph clone (--filter=tree:0); only then is it fetched by sha, depth 1, into a separate
    bare repository (under the ref PIN_REF)."""
    commit = pin["commit"]
    graph = _bare_clone(pin["repo"], common.REPOS / "github__advisory-database.graph.git", "tree:0")
    if not on_branch(graph, commit, pin["branch"]):
        raise common.Refused(f"{commit} is not reachable from branch {pin['branch']} of {pin['repo']}")
    d = common.REPOS / "github__advisory-database.at-pin.git"
    if not (d / "HEAD").exists():
        d.parent.mkdir(parents=True, exist_ok=True)
        tmp = common.staging(d)
        subprocess.run(["git", "init", "--bare", "--quiet", str(tmp)], check=True, capture_output=True,
                       env=common.git_env())
        tmp.rename(d)
    have = subprocess.run(["git", "-C", str(d), "cat-file", "-e", f"{commit}^{{commit}}"], capture_output=True,
                          env=common.git_env())
    if have.returncode != 0:
        common.git(d, "fetch", "--no-progress", "--depth", "1", "--no-tags", pin["repo"],
                   f"+{commit}:{PIN_REF}", timeout=7200)
    return d


def _advisory_files(d: Path, commit: str):
    """(path, bytes) of every .json blob under the advisory folders at commit, streamed through git cat-file."""
    out = common.git(d, "ls-tree", "-r", "-z", commit, "--", *ADVISORY_DIRS, text=False)
    blobs = []
    for rec in out.split(b"\0"):
        if not rec:
            continue
        meta, name = rec.split(b"\t", 1)
        _, kind, oid = meta.split(b" ")
        path = name.decode("utf-8", errors="surrogateescape")
        if kind == b"blob" and path.endswith(".json"):
            blobs.append((path, oid.decode()))
    p = subprocess.Popen(["git", "-C", str(d), "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL, env=common.git_env())

    def feed():
        try:
            for _, oid in blobs:
                p.stdin.write(oid.encode() + b"\n")
        finally:
            p.stdin.close()
    t = threading.Thread(target=feed, daemon=True)
    t.start()
    for path, oid in blobs:
        header = p.stdout.readline().split()
        if len(header) != 3 or header[0].decode() != oid:
            raise RuntimeError(f"git cat-file --batch: unexpected header for {path}")
        data = p.stdout.read(int(header[2]))
        p.stdout.read(1)
        yield path, data
    t.join()
    if p.wait() != 0:
        raise RuntimeError("git cat-file --batch over the advisory database failed")


def ghsa_scan(proto: dict) -> dict[str, list[dict]]:
    """Every system's GHSA rows at the advisory-database pin: {system: [{"item": item record, "doc": the advisory, or
    None when pre-filtered}]}. Every .json file under the advisory folders at the pin is parsed (a file that is not
    JSON is no advisory), and the advisories that name a repository of any system (_names_one_of) are kept; each
    system's index is then ghsa_items over them. The result is cached under ~/.holon/eval/index/ by pin and protocol
    digest (a pre-filtered advisory's text is never stored)."""
    pin = proto["snapshots"]["pins"]["advisory-database"]
    digest = common.sha256_bytes(common.dumps(proto).encode("utf-8"))
    cache = common.HOME / "index" / f"advisories-{pin['commit']}-{digest[:16]}.json"
    if cache.exists():
        return common.load_json(cache)
    d = advisory_repo(pin)
    slugs = sorted({slug(r) for s in proto["systems"] for r in s["repos"]})
    kept = []
    for path, data in _advisory_files(d, pin["commit"]):
        try:
            doc = json.loads(data)
        except ValueError:
            continue
        if _names_one_of(doc, slugs):
            kept.append((path, doc))
    out = {}
    for s in proto["systems"]:
        out[s["id"]] = [{"item": rec, "doc": None if rec["excluded_by"] else doc}
                        for rec, doc in ghsa_items(kept, s["repos"], proto)]
    cache.parent.mkdir(parents=True, exist_ok=True)
    part = cache.with_name(f".{cache.name}.writing")
    part.write_text(json.dumps(out, sort_keys=True), encoding="utf-8")
    part.rename(cache)
    return out


def geth_list(pin: dict) -> bytes:
    d = common.repo_cache(pin["repo"])
    if not on_branch(d, pin["commit"], pin["branch"]):
        raise common.Refused(f"{pin['repo']}@{pin['commit']} is not reachable from its branch {pin['branch']}")
    data = common.git(d, "cat-file", "blob", f"{pin['commit']}:{pin['path']}", text=False)
    if common.sha256_bytes(data) != pin["sha256"]:
        raise common.Refused(f"{pin['path']} at {pin['commit']} does not have the pinned sha256")
    return data


def folder_listing(pin: dict) -> list[dict]:
    """The reports of an in-repo folder at its pin (reachable from the pinned branch), sorted by item URL, each with the
    earliest commit of the pin's first-parent history that adds its path (renames not followed) and its committer
    date."""
    d = common.repo_cache(pin["repo"])
    if not on_branch(d, pin["commit"], pin["branch"]):
        raise common.Refused(f"{pin['repo']}@{pin['commit']} is not reachable from its branch {pin['branch']}")
    names = common.git(d, "ls-tree", "-r", "-z", "--name-only", pin["commit"], "--", pin["path"]).split("\0")
    paths = folder_reports([n for n in names if n], pin["path"])
    log = common.git(d, "-c", "core.quotePath=false", "log", "--first-parent", "--diff-merges=first-parent",
                     "--no-renames", "--diff-filter=A", "--name-only", "--format=@@%H %cd",
                     "--date=format-local:%Y-%m-%dT%H:%M:%SZ", pin["commit"], "--", pin["path"])
    added: dict[str, dict] = {}
    cur = None
    for line in log.split("\n"):
        if line.startswith("@@"):
            sha, date = line[2:].split(" ", 1)
            cur = {"commit": sha, "committer_date": date}
        elif line and cur is not None:
            added[line] = cur   # the walk goes newest first: the last assignment is the earliest commit adding it
    rows = [{"item": report_item(pin["repo"], pin["commit"], p), "path": p, "added": added.get(p)} for p in paths]
    return sorted(rows, key=lambda r: r["item"])


# ---------------------------------------------------------------------------------------------- the index records
def git_snapshot(pin: dict) -> dict:
    snap = {"kind": "git", "repo": pin["repo"], "commit": pin["commit"]}
    if "path" in pin:
        snap["path"] = pin["path"]
    return snap


def _opened(rows: list[tuple[dict, dict | None]], system: dict, enumeration: str) -> list[dict]:
    out = []
    for rec, doc in rows:
        if rec["excluded_by"] is not None:
            continue
        named, fix = commit_record(doc, system["repos"])
        out.append({"item": rec["item"], "text": excerpt_source(doc, enumeration),
                    "urls": _ref_urls(doc) if enumeration == "ghsa" else _link_urls(doc),
                    "named_commits": named, "named_fix": fix})
    return out


def system_index(system_id: str, proto: dict | None = None) -> dict:
    """The collector's record of every index of the system, in the protocol's order (see the module docstring)."""
    proto = proto or common.protocol()
    systems = {s["id"]: s for s in proto["systems"]}
    if system_id not in systems:
        raise common.Refused(f"unknown system {system_id!r} (the protocol's: {', '.join(systems)})")
    system = systems[system_id]
    records = []
    for ix in system["indexes"]:
        kind = ix["enumeration"]
        rec = {"index": ix["id"], "enumeration": kind}
        if kind == "ghsa":
            pin = proto["snapshots"]["pins"][ix["snapshot"]]
            rows = [(r["item"], r["doc"]) for r in ghsa_scan(proto)[system_id]]
            rec.update(snapshot=git_snapshot(pin), items=[r for r, _ in rows], opened=_opened(rows, system, kind))
        elif kind == "geth":
            pin = proto["snapshots"]["pins"][ix["snapshot"]]
            rows = geth_items(geth_list(pin), proto, ix["url"])
            rows = [(r, None if r["excluded_by"] else e) for r, e in rows]
            rec.update(snapshot=git_snapshot(pin), items=[r for r, _ in rows], opened=_opened(rows, system, kind))
        elif kind == "folder":
            pin = proto["snapshots"]["pins"][ix["snapshot"]]
            rec.update(snapshot=git_snapshot(pin), reports=folder_listing(pin))
        elif kind == "page":
            rec.update(snapshot={"kind": "page", "url": ix["url"]})
        else:
            raise common.Refused(f"{ix['id']}: unknown enumeration {kind!r}")
        records.append(rec)
    return {"index_version": INDEX_VERSION, "system": system_id, "indexes": records}


def _counts(doc: dict) -> str:
    parts = []
    for r in doc["indexes"]:
        if "items" in r:
            pre = sum(1 for x in r["items"] if x["excluded_by"] is not None)
            fixes = sum(1 for x in r["opened"] if x["named_fix"] is not None)
            parts.append(f"{r['index']}: {len(r['items'])} items, {pre} pre-filtered, {len(r['opened'])} opened, "
                         f"{fixes} with a named reachable fix")
        elif "reports" in r:
            parts.append(f"{r['index']}: {len(r['reports'])} reports")
        else:
            parts.append(f"{r['index']}: page")
    return "; ".join(parts)


def cli_index(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon eval index")
    ap.add_argument("--system", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    if out == common.ROOT or common.ROOT in out.parents:
        raise common.Refused(f"{a.out} lies inside the repository; the index is written outside it")
    doc = system_index(a.system)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(common.dumps(doc), encoding="utf-8")
    print(f"holon eval index: {a.system}: {_counts(doc)}", file=sys.stderr)
    return 0
