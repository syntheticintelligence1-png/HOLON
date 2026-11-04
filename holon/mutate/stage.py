"""The scratch trees of one run (I61 contract, "The pipeline" steps 1-3): the mutated source tree, the scratch HOLON
tree at the pipeline commit whose config names it, and the re-extraction with the M2 frontends, unchanged.

Every pipeline step runs as `python -m holon ...` inside the scratch HOLON tree (cwd and PYTHONPATH there), so the
code that runs is the pipeline commit's and every path it resolves through its own ROOT is the scratch tree's.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

from . import common as C

SOL_SIDECARS = ("spec/M2/lib/extract_solidity.json", "spec/M2/lib/extract_rollup.json")
GO_CONFIG = "spec/M2/lib/go_frontend.json"
EXCLUDE = ("gen/M3",)          # never read by an M2 pipeline step: kept out of the scratch tree (225 MB)


def _sol_deps_root(nm: Path) -> Path:
    """The directory config replay.sol_deps names (it holds node_modules)."""
    return Path(nm).parent


def source_tree(unit: dict, dest: Path, checkout: Path, sol_deps: Path) -> tuple[Path, Path]:
    """Step 1: a scratch copy of the pinned checkout's tree parts, and the sol_deps node_modules to use (a scratch
    copy only when the unit mutates a unit of it), with the unit's edit applied. Returns (tree, node_modules)."""
    dest = Path(dest).resolve()
    tree = C.copy_tree(checkout, dest / "src")
    nm = Path(sol_deps)
    m = unit.get("mutant")
    if m is not None:
        if m["root"] == "sol_deps":
            nm = dest / "sol_deps" / "node_modules"
            shutil.copytree(sol_deps, nm, symlinks=False, ignore=shutil.ignore_patterns(".git"))
            target = nm / m["file"]
        else:
            target = tree / m["file"]
        from .operators import apply
        data = target.read_bytes()
        new = apply(m, data)
        if C.sha256_bytes(new) != m["mutant_sha256"]:
            raise C.MutateError(f"{unit['id']}: the mutated {m['file']} hashes to {C.sha256_bytes(new)}, the instrument "
                                f"says {m['mutant_sha256']}")
        target.write_bytes(new)
    return tree, nm


def holon_tree(root: Path, commit: str, dest: Path, tree: Path, nm: Path) -> Path:
    """Step 3's scratch HOLON tree: the tree of `commit` (git archive; gen/M3 left out) whose config names the scratch
    source tree (extract.sources, replay.morph) and sol_deps (replay.sol_deps and, for a scratch copy, its tree hash),
    with the Solidity sidecars' target.commit null (the frontends' marker for a tree that is not a pinned checkout)."""
    dest = Path(dest).resolve()
    tree, nm = Path(tree).resolve(), Path(nm).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    spec = [f":(exclude){x}" for x in EXCLUDE]
    p = subprocess.run(["git", "-C", str(root), "archive", "--format=tar", commit, "--", ".", *spec],
                       capture_output=True)
    if p.returncode != 0:
        raise C.MutateError(f"git archive {commit} failed: {p.stderr.decode()[-300:]}")
    with tarfile.open(fileobj=io.BytesIO(p.stdout)) as t:
        t.extractall(dest, filter="data")
    cfgp = dest / "config" / "holon.json"
    cfg = json.loads(cfgp.read_text())
    repo = None
    for rel in SOL_SIDECARS:
        sp = dest / rel
        side = json.loads(sp.read_text())
        repo = side["target"]["repo"]
        side["target"]["commit"] = None
        sp.write_text(json.dumps(side, indent=2, sort_keys=True) + "\n")
    cfg.setdefault("extract", {}).setdefault("sources", {})[repo] = str(tree)
    rp = cfg.setdefault("replay", {})
    rp["morph"] = str(tree)
    if Path(nm).resolve() != Path(C.sol_deps(root)).resolve():
        from ..replay import tree_sha256
        rp["sol_deps"] = str(_sol_deps_root(nm))
        rp["sol_deps_sha256"] = tree_sha256(nm)
    cfgp.write_text(json.dumps(cfg, indent=2) + "\n")
    return dest


def holon(htree: Path, args: list, timeout: int = 7200) -> subprocess.CompletedProcess:
    """`python -m holon <args>` inside a scratch HOLON tree (its own code and ROOT)."""
    htree = Path(htree).resolve()
    env = C.env_tools()
    env["PYTHONPATH"] = str(htree)
    env.pop("HOLON_BUILD_DIR", None)
    try:
        return subprocess.run([sys.executable, "-m", "holon", *[str(a) for a in args]], cwd=str(htree), env=env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        return subprocess.CompletedProcess(e.cmd, None, out, err + f"\n[timeout after {timeout} s]")


def _tail(p: subprocess.CompletedProcess, n: int = 600) -> str:
    """The last n characters of a step's output, scrubbed first (common.scrub), so the cut is the same everywhere."""
    return C.scrub((p.stdout or "") + (p.stderr or ""))[-n:].strip()


def extract(htree: Path, tree: Path, out: Path, log=None) -> tuple[dict, dict, dict]:
    """Step 2: the M2 frontends, unchanged, on the scratch tree: `holon extract solidity` with each Solidity sidecar,
    `holon extract go` with the Go config. Documents go to `out` and then replace the scratch HOLON tree's
    spec/M2/facts/*.extracted.json; a document whose extraction fails twice is removed there (no later step reads a
    stale document) and reported. Returns ({rel: text}, {rel: error}, {step: seconds})."""
    htree, tree, out = Path(htree).resolve(), Path(tree).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    texts, errors, secs = {}, {}, {}
    facts = htree / C.FACTS2
    committed = sorted(p.name for p in facts.glob("*.extracted.json"))
    for rel in SOL_SIDECARS:
        side = json.loads((htree / rel).read_text())
        doc = Path(side["output"]).name
        dst = out / doc
        t0 = time.monotonic()
        for attempt in (1, 2):
            p = holon(htree, ["extract", "solidity", "--root", htree, "--sidecar", htree / rel, "--source", tree,
                              "--out", dst])
            if p.returncode == 0 and dst.is_file():
                break
        secs[f"extract_solidity:{doc}"] = round(time.monotonic() - t0, 1)
        if p.returncode == 0 and dst.is_file():
            texts[f"{C.FACTS2.as_posix()}/{doc}"] = dst.read_text()
        else:
            errors[f"{C.FACTS2.as_posix()}/{doc}"] = f"holon extract solidity (exit {p.returncode}): {_tail(p)}"
    gdir = out / "go"
    t0 = time.monotonic()
    for attempt in (1, 2):
        shutil.rmtree(gdir, ignore_errors=True)
        p = holon(htree, ["extract", "go", "--root", htree, "--src", tree, "--out-dir", gdir])
        if p.returncode == 0:
            break
    secs["extract_go"] = round(time.monotonic() - t0, 1)
    go_docs = sorted(x.name for x in gdir.glob("*.extracted.json")) if p.returncode == 0 else []
    for name in committed:
        rel = f"{C.FACTS2.as_posix()}/{name}"
        if rel in texts or rel in errors:
            continue
        if name in go_docs:
            texts[rel] = (gdir / name).read_text()
        else:
            errors[rel] = (f"holon extract go (exit {p.returncode}): {_tail(p)}" if p.returncode != 0
                           else "holon extract go wrote no such document")
    for name in committed:
        rel = f"{C.FACTS2.as_posix()}/{name}"
        if rel in texts:
            (facts / name).write_text(texts[rel])
        else:
            (facts / name).unlink(missing_ok=True)
    return texts, errors, secs
