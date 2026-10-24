"""Rule V5: one extracted transitions document per version of the deployed path.

For every path version, the generated extraction sidecar <outputs.sidecars>/<version>.json is the I19 sidecar
(inputs.extract_sidecar) with its target commit replaced by the version's commit in the history and its output by
<outputs.documents>/<version>.json; the document is what the Solidity frontend's walk (holon.frontends.solidity
.extract_document: the pinned solc and dependency tree) extracts from that commit's tree. The tree is materialized from
the source repository's git objects (a checkout at the commit whose object store is the repository's, by alternates:
nothing is fetched and the repository is not written), in a cache directory outside this repository. A version whose
extraction fails (the frontend's ExtractionError) is debt with its error and has no document; a refusal (a missing or
unpinned tool, a tree that is not the commit) refuses the whole command.

The versioned document <outputs.versions> holds V1-V4's fields (holon.versions.history), the inputs' sha256, the
documents with their sha256 and commits, and the debt. Byte-identical across runs; no timestamps, no absolute paths.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from . import VERSIONS_VERSION, Ctx, Refused, VersionsError, render, sha256_bytes, write_or_check
from .history import basis_fields


def _git(repo: str, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=1200, env=env)


def source_repo(ctx: Ctx, repo_name: str) -> str:
    srcs = (ctx.cfg.get("extract") or {}).get("sources") or {}
    repo = srcs.get(repo_name)
    if not repo or not Path(repo).is_dir():
        raise Refused(f"config extract.sources has no checkout of {repo_name}")
    return repo


def cache_root() -> Path:
    return Path(os.environ.get("HOLON_CACHE") or (Path.home() / ".holon" / "cache")) / "versions"


def tree(ctx: Ctx, repo_name: str, commit: str, paths: list) -> Path:
    """A checkout of `commit` holding `paths` (sparse), whose objects are the source repository's (alternates): its
    HEAD is the commit and its files carry no change (the frontend checks both)."""
    repo = source_repo(ctx, repo_name)
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode != 0:
        raise Refused(f"{repo} is not a git repository: {common.stderr.strip()[:200]}")
    objects = Path(common.stdout.strip()) / "objects"
    t = cache_root() / "trees" / commit
    if (t / ".git").is_dir():
        head = _git(str(t), "rev-parse", "HEAD")
        clean = _git(str(t), "status", "--porcelain", "--untracked-files=all")
        if head.returncode == 0 and head.stdout.strip() == commit and clean.returncode == 0 and not clean.stdout.strip():
            return t
    import shutil
    shutil.rmtree(t, ignore_errors=True)
    t.parent.mkdir(parents=True, exist_ok=True)
    tmp = t.with_name(t.name + f".{os.getpid()}.part")
    shutil.rmtree(tmp, ignore_errors=True)
    steps = [["init", "-q", str(tmp)]]
    p = subprocess.run(["git", *steps[0]], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise VersionsError(f"git init: {p.stderr.strip()[:200]}")
    (tmp / ".git" / "objects" / "info" / "alternates").write_text(str(objects) + "\n")
    for args in (["sparse-checkout", "set", "--no-cone", *[f"/{x.strip('/')}" for x in paths]],
                 ["-c", "protocol.allow=never", "checkout", "-q", "--detach", commit]):
        p = _git(str(tmp), *args)
        if p.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise VersionsError(f"materializing {commit}: git {' '.join(args[:2])}: {p.stderr.strip()[:300]}")
    os.replace(tmp, t)
    return t


def version_sidecar(ctx: Ctx, base: dict, vid: str, commit: str) -> dict:
    side = json.loads(json.dumps(base))
    side["target"]["commit"] = commit
    side["output"] = f"{ctx.out('documents')}/{vid}.json"
    return side


def extract_all(ctx: Ctx, log=None) -> dict:
    """{relative path: bytes} of every file extract writes: the sidecars, the documents and the versioned document."""
    from ..frontends import ExtractionError, Refused as FRefused
    from ..frontends.solidity import extract_document
    fields = basis_fields(ctx)
    base_rel = ctx.inputs["extract_sidecar"]
    base = json.loads((ctx.root / base_rel).read_text(encoding="utf-8"))
    repo_name = base["target"]["repo"]
    paths = (ctx.history.get("contract") or {}).get("build_paths") or ["."]
    files, documents, debt = {}, {}, []
    for vid in fields["path"]:
        commit = ctx.version(vid)["commit"]
        side = version_sidecar(ctx, base, vid, commit)
        srel = f"{ctx.out('sidecars')}/{vid}.json"
        sdata = render(side)
        files[srel] = sdata
        sp = ctx.root / srel
        # the frontend reads the sidecar from disk (its path and sha256 enter the document): write it first, in place,
        # only when it differs (a --check run compares the bytes below and leaves a matching file untouched)
        tmpdir = None
        if not (sp.is_file() and sp.read_bytes() == sdata):
            import tempfile
            tmpdir = Path(tempfile.mkdtemp(prefix="holon-versions-"))
            sp_eff = tmpdir / sp.name
            sp_eff.write_bytes(sdata)
        else:
            sp_eff = sp
        try:
            t = tree(ctx, repo_name, commit, paths)
            try:
                doc = extract_document(side, sp_eff, ctx.root, str(t))
            except ExtractionError as e:
                debt.append({"version": vid, "reason": str(e)[:1000]})
                if log:
                    log(f"{vid}: debt: {str(e)[:200]}")
                continue
            except FRefused as e:
                raise Refused(f"{vid}: {e}") from e
        finally:
            if tmpdir is not None:
                import shutil
                shutil.rmtree(tmpdir, ignore_errors=True)
        # the document names its sidecar by the path the frontend read: always the generated sidecar's own path
        ext = doc.get("extraction") or {}
        if isinstance(ext.get("sidecar"), dict):
            ext["sidecar"] = {"path": srel, "sha256": sha256_bytes(sdata)}
        drel = side["output"]
        ddata = render(doc)
        files[drel] = ddata
        documents[vid] = {"path": drel, "sha256": sha256_bytes(ddata), "commit": commit}
        if log:
            log(f"{vid}: {drel} ({len(doc.get('actions') or [])} actions)")
    vd = {"versions_version": VERSIONS_VERSION, "history": ctx.file_ref("history"),
          "timeline": ctx.file_ref("timeline"), "sidecar": ctx.side_ref(),
          "contract": {"name": base["transitions"]["contract"], "source": (ctx.history.get("contract") or {}).get("source")},
          **fields, "documents": documents, "debt": debt}
    files[ctx.out("versions")] = render(vd)
    return files


def run(ctx: Ctx, check: bool) -> int:
    files = extract_all(ctx, log=lambda m: print(f"holon versions extract: {m}"))
    if check:
        bad = [rel for rel, data in sorted(files.items()) if not write_or_check(ctx.root / rel, data, True)]
        for rel in bad:
            print(f"holon versions extract: {rel} differs from a fresh extraction", file=sys.stderr)
        print(f"holon versions extract: {len(files) - len(bad)} of {len(files)} files reproduce")
        return 1 if bad else 0
    for rel, data in sorted(files.items()):
        write_or_check(ctx.root / rel, data, False)
    print(f"holon versions extract: wrote {len(files)} files")
    return 0
