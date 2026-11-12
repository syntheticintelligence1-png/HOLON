"""`python -m holon drift --target NAME [--remote URL]` (I47; whitepaper L22, §9.4 re-extraction).

1. `git ls-remote` of the target's upstream (upstream.url, or --remote), restricted to the watched ref prefix
   (upstream.watch), each ref at the commit it names (a tag's peeled ^{} commit when the remote lists one), compared with
   upstream.pinned_refs, the refs seen when the target was pinned. No ref new or moved: changed false, nothing more.
2. Otherwise the newest of the new or moved refs (by commit date, then by name) is fetched into a scratch repository and
   checked out, and the target's documents are re-extracted from it (extract.method "copy": each upstream path of
   extract.documents read from the checkout; "commands": each command of extract.commands run with {checkout} and {out}
   substituted, the documents read from {out}).
3. Every re-extracted document whose bytes differ from the committed one (its repo path) is remodelled with the
   generator of the run (holon.mpipeline.milestone_model, under run.milestone, anchored at the committed document so it
   takes the same target libraries), and the kernel index of the new model (holon.bindings.defs_index: each definition's
   kernel form, as the pinned checker translates it) is compared with the committed one (index.models). A definition
   whose kernel form changed, or that disappeared, is changed.
4. The stale set is every law whose cone holds a changed definition: index.deps, dependents_by_model of the document's
   model. A document whose model cannot be regenerated makes every law over it stale, and says why.

Writes drift.out (deterministic: the refs seen, the new ref, the documents, the changed definitions, the stale laws) and
drift.timing (stale_closure_latency_s: wall seconds from the ls-remote that showed the change to the stale set, and its
parts; a timing file nothing compares). Never writes under targets/ and never edits a committed document: re-extracted
documents live in the scratch directory, which is removed.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import targets as T

ROOT = Path(__file__).resolve().parents[1]
REPORT_VERSION = "holon-drift/0.1"


def _git(args: list[str], cwd: Path | None = None, timeout: int = 600) -> str:
    env = dict(os.environ)
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    p = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()[-800:]}")
    return p.stdout


def ls_remote(url: str, prefix: str) -> dict[str, str]:
    """{ref: commit} for the refs under prefix; a tag's peeled commit (<ref>^{}) replaces the tag object."""
    raw: dict[str, str] = {}
    for ln in _git(["ls-remote", url]).splitlines():
        if "\t" not in ln:
            continue
        sha, ref = ln.split("\t", 1)
        raw[ref] = sha
    out = {}
    for ref, sha in raw.items():
        if ref.endswith("^{}") or not ref.startswith(prefix):
            continue
        out[ref] = raw.get(ref + "^{}", sha)
    return dict(sorted(out.items()))


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch(url: str, refs: list[str], where: Path) -> dict[str, int]:
    """Fetch refs into a scratch repository (no blobs until checked out); {ref: committer time}."""
    where.mkdir(parents=True, exist_ok=True)
    _git(["init", "-q"], where)
    times = {}
    for i, ref in enumerate(refs):
        _git(["fetch", "-q", "--depth=1", "--filter=blob:none", url, f"+{ref}:refs/holon-drift/{i}"], where, timeout=1800)
        times[ref] = int(_git(["log", "-1", "--format=%ct", f"refs/holon-drift/{i}"], where).strip())
    return times


def extract(t: dict, checkout: Path, out: Path) -> dict[str, Path]:
    """{upstream document path: re-extracted file}."""
    ex = t["extract"]
    docs = ex.get("documents") or {}
    if ex["method"] == "copy":
        res = {}
        for up in sorted(docs):
            src = checkout / up
            if not src.is_file():
                raise RuntimeError(f"the upstream has no {up} at the new ref")
            dst = out / up
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            res[up] = dst
        return res
    if ex["method"] == "commands":
        for cmd in ex.get("commands") or []:
            argv = [c.replace("{checkout}", str(checkout)).replace("{out}", str(out)).replace("{python}", sys.executable)
                    for c in cmd]
            p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError(f"extraction command {cmd[:3]} failed: {(p.stdout + p.stderr)[-800:]}")
        return {up: out / up for up in sorted(docs) if (out / up).is_file()}
    raise RuntimeError(f"unknown extract.method {ex['method']!r}")


def kernel_index(t: dict, doc: Path, committed: Path, root: Path) -> dict:
    """The kernel index of the model the run would build from doc (holon.bindings.defs_index)."""
    from . import bend, bindings
    from .mpipeline import milestone_model
    cfg = bend.config(root)
    m = (t.get("run") or {}).get("milestone")
    if not m:
        raise RuntimeError("the target names no run.milestone, so no model generator")
    cm = milestone_model(m, doc, cfg, anchor=committed, root=root)
    return bindings.defs_index(cm.source, cfg)


def model_of(index_path: str) -> str:
    """The model name a kernel index file belongs to (gen/.../model/<model>.defs.json)."""
    return Path(index_path).name[: -len(".defs.json")]


def changed_defs(old: dict, new: dict) -> list[str]:
    def sha(x):
        return x.get("sha256") if isinstance(x, dict) else x
    o, n = old.get("defs", old), new.get("defs", new)
    return sorted(d for d in o if d not in n or sha(o[d]) != sha(n[d]))


def drift(name: str, root: Path = ROOT, remote: str | None = None, log=print) -> dict:
    t = T.load(name, root)
    up = t["upstream"]
    url = remote or up.get("url")
    if not url:
        raise T.TargetError(f"target {name} has no upstream url; give --remote")
    rep = {"report_version": REPORT_VERSION, "target": name, "upstream": "--remote" if remote else url,
           "pinned_commit": up["pinned_commit"], "watch": up["watch"], "changed": False, "new_ref": None,
           "refs_seen": {}, "refs_new_or_moved": [], "documents": {}, "changed_definitions": [], "stale": [],
           "notes": []}
    timing: dict = {"stale_closure_latency_s": None}
    seen = ls_remote(url, up["watch"])
    t0 = time.monotonic()
    rep["refs_seen"] = seen
    pinned = up.get("pinned_refs") or {}
    moved = sorted(r for r, c in seen.items() if pinned.get(r) != c)
    rep["refs_new_or_moved"] = moved
    gone = sorted(set(pinned) - set(seen))
    if gone:
        rep["notes"].append(f"pinned refs no longer listed: {', '.join(gone)}")
    if not moved:
        log(f"drift {name}: no new or moved ref under {up['watch']} ({len(seen)} seen)")
        return {"report": rep, "timing": timing}
    rep["changed"] = True
    work = Path(tempfile.mkdtemp(prefix="holon-drift-"))
    try:
        t1 = time.monotonic()
        times = fetch(url, moved, work / "repo")
        newest = sorted(moved, key=lambda r: (-times[r], r))[0]
        commit = seen[newest]
        rep["new_ref"] = {"ref": newest, "commit": commit}
        _git(["checkout", "-q", "--detach", commit], work / "repo", timeout=1800)
        timing["fetch_s"] = round(time.monotonic() - t1, 3)
        t2 = time.monotonic()
        docs = extract(t, work / "repo", work / "out")
        timing["extract_s"] = round(time.monotonic() - t2, 3)
        t3 = time.monotonic()
        deps = {}
        dp = t["index"].get("deps")
        for p in ([dp] if isinstance(dp, str) else list(dp or [])):
            if (root / p).is_file():
                d = json.loads((root / p).read_text())
                for mdl, ds in (d.get("dependents_by_model") or {}).items():
                    for k, ls in ds.items():
                        deps.setdefault(mdl, {}).setdefault(k, set()).update(ls)
            else:
                rep["notes"].append(f"dependency index {p} is missing")
        stale: set = set()
        changed_all: set = set()
        mapping = (t["extract"].get("documents") or {})
        for upath in sorted(mapping):
            repo_path = mapping[upath]
            committed = root / repo_path
            new = docs.get(upath)
            entry = {"repo_path": repo_path, "sha256_committed": _sha(committed.read_bytes()) if committed.is_file()
                     else None, "sha256_new": _sha(new.read_bytes()) if new else None}
            entry["changed"] = entry["sha256_committed"] != entry["sha256_new"]
            rep["documents"][upath] = entry
            if not entry["changed"] or new is None:
                continue
            idx = (t["index"].get("models") or {}).get(repo_path)
            mdl = model_of(idx) if idx else None
            try:
                if not idx or not (root / idx).is_file():
                    raise RuntimeError(f"no committed kernel index for {repo_path}")
                old = json.loads((root / idx).read_text())
                newi = kernel_index(t, new, committed, root)
                ch = changed_defs(old, newi)
                entry["changed_definitions"] = ch
                changed_all |= set(ch)
                for dname in ch:
                    stale |= deps.get(mdl, {}).get(dname, set())
            except Exception as e:  # noqa: BLE001  (no new model: every law over the document is stale)
                entry["remodel_error"] = f"{type(e).__name__}: {e}"[:600]
                for ds in (deps.get(mdl, {}) if mdl else {}).values():
                    stale |= ds
                rep["notes"].append(f"{upath}: not remodelled ({entry['remodel_error'][:200]}); every law over it "
                                    "is stale")
        rep["changed_definitions"] = sorted(changed_all)
        rep["stale"] = sorted(stale)
        timing["remodel_and_stale_s"] = round(time.monotonic() - t3, 3)
        timing["stale_closure_latency_s"] = round(time.monotonic() - t0, 3)
        log(f"drift {name}: {newest} at {commit[:12]}: {sum(e['changed'] for e in rep['documents'].values())} "
            f"document(s) changed, {len(rep['changed_definitions'])} definition(s), stale {rep['stale']}")
        return {"report": rep, "timing": timing}
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="holon drift")
    ap.add_argument("--target", required=True)
    ap.add_argument("--remote")
    ap.add_argument("--root")
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    try:
        t = T.load(a.target, root)
        res = drift(a.target, root, a.remote)
    except (T.TargetError, RuntimeError) as e:
        print(f"holon drift: {e}", file=sys.stderr)
        return 2
    for key, rel in (("report", t["drift"]["out"]), ("timing", t["drift"]["timing"])):
        p = root / rel
        if p.resolve().is_relative_to((root / "targets").resolve()):
            print(f"holon drift: {rel} is under targets/", file=sys.stderr)
            return 2
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res[key], indent=2, sort_keys=True) + "\n")
    return 0
