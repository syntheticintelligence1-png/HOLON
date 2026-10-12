"""Toolchain checks and the compiler run of the Solidity frontend (rule W1 of the I17 contract).

The pinned solc (config/holon.json replay.solc, its sha256 replay.solc_sha256) compiles the sidecar's source units with
`--standard-json`: base path the source tree, include path <replay.sol_deps>/node_modules when that directory exists,
settings the sidecar's compiler.settings plus outputSelection {"*": {"": ["ast"]}} (the AST only: no IR, no bytecode,
no optimizer influence). What the walker reads is solc's compact JSON AST of every unit (inline assembly carries the
compiler's Yul AST and its resolved external references) and the bytes of every unit (spans and hashes).

Refusals (Refused, exit 2): solc missing, its sha256 not the pin, its --version not the sidecar's compiler.version, a
source tree that is not a git checkout whose HEAD is the sidecar's target.commit, or whose files solc read carry
uncommitted changes (target.commit null: no checkout check). Compile errors are an ExtractionError (exit 3).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import ExtractionError, Refused


@dataclass
class Compiled:
    """solc's output, reduced to what the walker reads."""
    version: str                                   # the text after "Version: " in solc --version
    solc_sha256: str
    settings: dict                                 # the settings passed (outputSelection included)
    asts: dict = field(default_factory=dict)       # unit -> compact JSON AST
    units: dict = field(default_factory=dict)      # unit -> bytes
    file_ids: dict = field(default_factory=dict)   # solc source id -> unit


def load_config(root: Path) -> dict:
    p = Path(root) / "config" / "holon.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"cannot read {p}: {e}") from e


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _clean_env() -> dict:
    env = dict(os.environ)
    for k in list(env):
        if k.startswith("GIT_"):
            env.pop(k)
    return env


def check_solc(cfg: dict, want_version: str) -> tuple[str, str, str]:
    """(solc path, sha256, version text) of the pinned compiler; Refused unless it is the pin."""
    rep = cfg.get("replay") or {}
    solc, pin = rep.get("solc"), rep.get("solc_sha256")
    if not solc or not Path(solc).is_file():
        raise Refused(f"solc missing: config replay.solc = {solc!r}")
    got = _sha256(Path(solc))
    if not pin or got != pin:
        raise Refused(f"solc {solc}: sha256 {got} is not the pin config replay.solc_sha256 = {pin}")
    p = subprocess.run([solc, "--version"], capture_output=True, text=True, timeout=120)
    text = next((ln.split("Version: ", 1)[1].strip() for ln in p.stdout.splitlines() if "Version: " in ln), None)
    if p.returncode != 0 or not text:
        raise Refused(f"solc {solc} --version failed: {p.stderr.strip()[:300]}")
    if text.split("+", 1)[0] != want_version:
        raise Refused(f"solc {solc} is version {text}, the sidecar wants {want_version}")
    return solc, got, text


def check_checkout(source: Path, commit: str | None) -> None:
    """A git checkout whose top level is `source` and whose HEAD is `commit` (None: no check)."""
    if commit is None:
        return
    if not source.is_dir():
        raise Refused(f"source tree {source} does not exist")
    env = _clean_env()
    top = subprocess.run(["git", "-C", str(source), "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                         timeout=120, env=env)
    if top.returncode != 0 or os.path.realpath(top.stdout.strip()) != os.path.realpath(source):
        raise Refused(f"source tree {source} is not a git checkout (its own top level)")
    head = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], capture_output=True, text=True,
                          timeout=120, env=env)
    if head.returncode != 0 or head.stdout.strip() != commit:
        raise Refused(f"source tree {source}: HEAD is {head.stdout.strip() or '?'}, the sidecar wants {commit}")


def check_clean(source: Path, commit: str | None, units: list[str]) -> None:
    """The files solc read from the checkout carry no uncommitted change (None: no check)."""
    if commit is None or not units:
        return
    p = subprocess.run(["git", "-C", str(source), "status", "--porcelain", "--untracked-files=all", "--", *units],
                       capture_output=True, text=True, timeout=300, env=_clean_env())
    if p.returncode != 0:
        raise Refused(f"source tree {source}: git status failed: {p.stderr.strip()[:300]}")
    if p.stdout.strip():
        raise Refused(f"source tree {source}: files solc read carry uncommitted changes:\n{p.stdout.strip()[:1000]}")


def compile_sources(cfg: dict, side: dict, source: Path) -> Compiled:
    """Run the pinned solc on the sidecar's units (rule W1)."""
    comp = side.get("compiler") or {}
    solc, sha, version = check_solc(cfg, comp.get("version"))
    check_checkout(source, side["target"]["commit"])
    settings = dict(comp.get("settings") or {})
    settings["outputSelection"] = {"*": {"": ["ast"]}}
    sources = {}
    for u in side["sources"]:
        p = source / u
        try:
            sources[u] = {"content": p.read_bytes().decode("utf-8")}
        except (OSError, UnicodeDecodeError) as e:
            raise ExtractionError(f"source unit {u}: cannot read {p}: {e}") from e
    cmd = [solc, "--standard-json", "--base-path", "."]   # run in the source tree (cwd below)
    deps = (cfg.get("replay") or {}).get("sol_deps")
    include = Path(deps) / "node_modules" if deps else None
    if include is not None and include.is_dir():
        cmd += ["--include-path", str(include)]
    else:
        include = None
    inp = json.dumps({"language": "Solidity", "sources": sources, "settings": settings}, sort_keys=True)
    p = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=1800, cwd=str(source))
    try:
        out = json.loads(p.stdout)
    except ValueError as e:
        raise ExtractionError(f"solc produced no JSON (exit {p.returncode}): {p.stderr.strip()[:500]}") from e
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise ExtractionError("compile errors:\n" + "\n".join(e.get("formattedMessage") or e.get("message", "")
                                                             for e in errs)[:4000])
    res = Compiled(version=version, solc_sha256=sha, settings=settings)
    from_tree = []
    for unit in sorted(out.get("sources", {})):
        s = out["sources"][unit]
        res.asts[unit] = s["ast"]
        res.file_ids[s["id"]] = unit
        here = source / unit
        if here.is_file():
            res.units[unit] = here.read_bytes()
            from_tree.append(unit)
        elif include is not None and (include / unit).is_file():
            res.units[unit] = (include / unit).read_bytes()
        else:
            raise ExtractionError(f"solc read unit {unit}, which is neither in the source tree nor on the include path")
    check_clean(source, side["target"]["commit"], from_tree)
    return res
