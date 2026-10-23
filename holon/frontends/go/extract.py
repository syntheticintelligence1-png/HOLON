"""holon extract go: the Go frontend (holon-facts/0.3, frontend "go").

  python -m holon extract go [--milestone M2] [--root DIR] [--config PATH] [--src DIR] [--out-dir DIR] [--doc STEM ...]

The Go source tree is copied to a scratch workspace outside the repository; the generic helper
holon/frontends/go/ssadump (golang.org/x/tools go/packages + go/ssa, built once into ~/.holon/tools/ssadump/<key>/)
prints the SSA form of every package of every document of the config; everything else is the pure-Python analysis of
that output (analyses.py, paths.py, flow.py). The config is the only target vocabulary. Inputs read: the config, the
JSON file its "source" names, the source tree and the ssadump output; nothing else under the repository.

Exit 0 written; 2 refused, nothing written (toolchain missing or not the pinned version, helper not built, a package
that does not load or type-check, a missing or malformed input).

Additive sections (I19 follow-up A19-13; the contract of the other sections is the docstring of
tests_m2/test_extract_go.py):
  go.globals  [{"global": qualified name, "package", "span": its declaration, "type", "value": term, "cells": [cell]
              | null}] sorted by global: every package-level variable that a package initializer of the document's
              packages assigns as a whole (one Store to the variable itself; a variable assigned more than once has the
              value ["unknown", "stores"]; synthetic variables, whose names hold "$", are left out). value is built from the initializer's definitions as in the slices pass
              (Flow), so a call stays a call term. cells (for a variable of a fixed-size byte-array type, else null):
              the n bytes of the value, ["const", v] where known (the value of a hex_to_array primitive applied to a
              string constant), else ["byte", value, k]. Package initializers stay out of "functions".
  primitive kind "hex_to_array" (width n): the n-byte array of a string argument's hexadecimal digits (an optional
              0x or 0X prefix removed, an odd count left-padded with "0"), right-aligned (zero bytes before it) and
              cropped to its last n bytes; a string that is not hexadecimal leaves the cells unknown.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .analyses import Analysis
from .ctx import Ctx
from .ssaload import DumpError, Program

FRONTEND_VERSION = "holon-go/0.1"
# I67: 0.2 is a superset of 0.1 — it adds the additive `loop_bodies` section (loop-free paths over a counted loop's
# induction variable) and leaves every 0.1 section byte-identical, so a 0.1 config re-extracts unchanged.
CONFIG_VERSION = "holon-go-frontend/0.1"
CONFIG_VERSIONS = ("holon-go-frontend/0.1", "holon-go-frontend/0.2")
FRONTEND_VERSION_OF = {"holon-go-frontend/0.1": "holon-go/0.1", "holon-go-frontend/0.2": "holon-go/0.2"}
PRIMITIVE_KINDS = ("to_array", "hash", "array_bytes", "hex_to_array")
FACTS_VERSION = "holon-facts/0.3"
HERE = Path(__file__).resolve().parent
SSADUMP_DIR = HERE / "ssadump"
REPO_ROOT = HERE.parents[2]
SSADUMP_FILES = ("main.go", "go.mod", "go.sum")
SKIP = re.compile(r"^(\.git|node_modules|\.env.*|bunfig\.toml)$")

GENERIC_ASSUMPTIONS = {
    "go-append-growth": "The capacity append chooses when it grows is not modelled: a grown append's backing is fresh "
                        "and its capacity is [\"unknown\", \"growth\"].",
    "go-errors-nonnil": "errors.New and fmt.Errorf return non-nil errors, and so does a package variable of an error "
                        "type that the package initializer assigns from one of them.",
    "go-nil-deref-not-modelled": "Nil pointer dereferences are not partiality sites.",
    "go-opaque-calls": "Calls outside the analyzed packages that are not primitives are opaque: their results are "
                       "call terms, and what they do to memory they can reach is unknown.",
}


class Refused(Exception):
    """Exit 2: nothing is written."""


# ---------------------------------------------------------------------------------------------- inputs
def _load_json(p: Path, what: str):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise Refused(f"{what} {p} is missing")
    except (OSError, ValueError) as e:
        raise Refused(f"{what} {p} is not valid JSON: {e}")


def load_config(path: Path) -> dict:
    cfg = _load_json(path, "config")
    if not isinstance(cfg, dict) or cfg.get("config_version") not in CONFIG_VERSIONS:
        raise Refused(f"config {path}: config_version must be one of {CONFIG_VERSIONS}")
    t = cfg.get("target")
    if not isinstance(t, dict) or not isinstance(t.get("repo"), str) or not isinstance(t.get("commit"), str):
        raise Refused(f"config {path}: target needs repo and commit")
    docs = cfg.get("documents")
    if not isinstance(docs, dict) or not docs or not all(
            isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9_]*", k) and isinstance(v, list) and v
            and all(isinstance(x, str) and x for x in v) for k, v in docs.items()):
        raise Refused(f"config {path}: documents must map stems to non-empty lists of import paths")
    prims = cfg.get("primitives", {})
    if not isinstance(prims, dict):
        raise Refused(f"config {path}: primitives must be an object")
    for name, p in prims.items():
        if not isinstance(p, dict) or p.get("kind") not in PRIMITIVE_KINDS or not isinstance(p.get("text"), str):
            raise Refused(f"config {path}: primitive {name} needs kind ({' | '.join(PRIMITIVE_KINDS)}) and text")
        if p["kind"] in ("to_array", "array_bytes", "hex_to_array") and not isinstance(p.get("width"), int):
            raise Refused(f"config {path}: primitive {name} needs a width")
    lim = cfg.get("limits", {})
    if not isinstance(lim, dict) or not all(isinstance(lim.get(k), int) and lim.get(k) > 0
                                            for k in ("max_paths", "inline_depth", "flow_depth")):
        raise Refused(f"config {path}: limits need max_paths, inline_depth and flow_depth")
    src = cfg.get("source")
    if not isinstance(src, dict) or not (isinstance(src.get("path"), str) or (
            isinstance(src.get("config"), str) and isinstance(src.get("key"), list))):
        raise Refused(f"config {path}: source must be {{path}} or {{config, key}}")
    return cfg


def resolve_src(cfg: dict, root: Path) -> Path:
    s = cfg["source"]
    if "path" in s:
        return root / s["path"]
    v = _load_json(root / s["config"], "source config")
    for k in s["key"]:
        if not isinstance(v, dict) or k not in v:
            raise Refused(f"source config {s['config']} has no key {'.'.join(s['key'])}")
        v = v[k]
    if not isinstance(v, str) or not v:
        raise Refused(f"source config {s['config']}: {'.'.join(s['key'])} is not a path")
    return Path(v)


def rel_to(p: Path, root: Path) -> str:
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<outside>/" + p.name


# ---------------------------------------------------------------------------------------------- toolchain
def go_binary() -> str:
    found = shutil.which("go")
    if found:
        return found
    if Path("/usr/local/go/bin/go").is_file():
        return "/usr/local/go/bin/go"
    raise Refused("no go toolchain: neither `go` on PATH nor /usr/local/go/bin/go")


def check_go(root: Path) -> tuple[str, str]:
    """(go binary, version token) when `go version` prints the pinned config/holon.json replay.go_version."""
    holon_cfg = _load_json(root / "config" / "holon.json", "config/holon.json")
    want = ((holon_cfg or {}).get("replay") or {}).get("go_version")
    if not want:
        raise Refused("config/holon.json replay.go_version is not pinned")
    go = go_binary()
    try:
        p = subprocess.run([go, "version"], capture_output=True, text=True, timeout=120, cwd=tempfile.gettempdir())
    except OSError as e:
        raise Refused(f"`{go} version` failed: {e}")
    got = p.stdout.strip()
    if got != want:
        raise Refused(f"`go version` prints {got!r}, the pinned toolchain is {want!r} (config/holon.json "
                      f"replay.go_version)")
    return go, got.split()[2]


def ssadump_digest() -> str:
    h = hashlib.sha256()
    for name in SSADUMP_FILES:
        p = SSADUMP_DIR / name
        try:
            with open(p, "rb") as f:
                h.update(f.read())
        except OSError:
            raise Refused(f"{p} is missing")
    return h.hexdigest()


def x_tools_version() -> str:
    with open(SSADUMP_DIR / "go.mod", encoding="utf-8") as f:
        m = re.search(r"(?m)^\s*(?:require\s+)?golang\.org/x/tools\s+(\S+)", f.read())
    if not m:
        raise Refused("holon/frontends/go/ssadump/go.mod requires no golang.org/x/tools")
    return m.group(1)


def go_env(**extra) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS", "GOTOOLCHAIN")}
    env.update(extra)
    return env


def build_ssadump(go: str, digest: str) -> Path:
    out = Path.home() / ".holon" / "tools" / "ssadump" / digest[:16] / "ssadump"
    if out.is_file() and os.access(out, os.X_OK):
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / f"ssadump.tmp{os.getpid()}"
    env = go_env(GOWORK="off", GOFLAGS="-mod=readonly", GOTOOLCHAIN="local")
    try:
        p = subprocess.run([go, "build", "-trimpath", "-o", str(tmp), "."], cwd=SSADUMP_DIR, env=env,
                           capture_output=True, text=True, timeout=1800)
    except OSError as e:
        raise Refused(f"cannot build ssadump: {e}")
    if p.returncode != 0 or not tmp.is_file():
        raise Refused(f"cannot build ssadump (exit {p.returncode}): {(p.stdout + p.stderr)[-3000:]}")
    os.replace(tmp, out)
    return out


# ---------------------------------------------------------------------------------------------- workspace
def _ignore(_dir, names):
    return [n for n in names if SKIP.match(n)]


def go_work_uses(text: str) -> list[str]:
    uses = []
    for m in re.finditer(r"(?ms)^\s*use\s*\((.*?)\)", text):
        for line in m.group(1).splitlines():
            line = line.split("//", 1)[0].strip()
            if line:
                uses.append(line.strip('"'))
    for m in re.finditer(r"(?m)^\s*use\s+([^\s(][^\s]*)\s*$", text):
        uses.append(m.group(1).strip('"'))
    return uses


def make_workspace(src: Path, dst: Path) -> None:
    work = src / "go.work"
    if work.is_file():
        with open(work, encoding="utf-8") as f:
            text = f.read()
        for u in go_work_uses(text):
            rel = Path(u)
            if rel.is_absolute() or ".." in rel.parts:
                raise Refused(f"{work}: use directive {u!r} leaves the source tree")
            s = src / rel
            if not s.is_dir():
                raise Refused(f"{work}: use directory {u!r} is missing")
            shutil.copytree(s, dst / rel, symlinks=True, ignore=_ignore, dirs_exist_ok=True)
        for f in ("go.work", "go.work.sum"):
            if (src / f).is_file():
                shutil.copy2(src / f, dst / f)
    else:
        shutil.copytree(src, dst, symlinks=True, ignore=_ignore, dirs_exist_ok=True)


def run_ssadump(binary: Path, ws: Path, patterns: list[str]) -> dict:
    env = go_env(GOFLAGS="-mod=readonly", GOTOOLCHAIN="local")
    try:
        p = subprocess.run([str(binary), "-dir", str(ws), *patterns], cwd=ws, env=env, capture_output=True,
                           timeout=3600)
    except OSError as e:
        raise Refused(f"ssadump did not run: {e}")
    if p.returncode != 0:
        raise Refused(f"ssadump: packages did not load or type-check (exit {p.returncode}):\n"
                      f"{p.stderr.decode('utf-8', 'replace')[-4000:]}")
    try:
        return json.loads(p.stdout)
    except ValueError as e:
        raise Refused(f"ssadump printed no JSON document: {e}")


# ---------------------------------------------------------------------------------------------- documents
def render(doc: dict) -> str:
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _strings(x, out: set) -> None:
    if isinstance(x, str):
        out.add(x)
    elif isinstance(x, list):
        for y in x:
            _strings(y, out)
    elif isinstance(x, dict):
        for v in x.values():
            _strings(v, out)


def _sha(p: Path) -> str:
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def extract(config_path, src=None, root=None) -> dict:
    """{stem: document} for every document of the config."""
    root = Path(root).resolve() if root else REPO_ROOT
    config_path = Path(config_path)
    cfg = load_config(config_path)
    src = Path(src) if src else resolve_src(cfg, root)
    if not src.is_dir():
        raise Refused(f"source tree {src} is missing")
    go, go_ver = check_go(root)
    digest = ssadump_digest()
    xt = x_tools_version()
    binary = build_ssadump(go, digest)
    patterns = sorted({p for pk in cfg["documents"].values() for p in pk})
    ws_parent = Path(tempfile.mkdtemp(prefix="holon-go-ws-"))
    try:
        ws = ws_parent / "src"
        ws.mkdir()
        make_workspace(src, ws)
        dump = run_ssadump(binary, ws.resolve(), patterns)
        try:
            prog = Program(dump)
        except DumpError as e:
            raise Refused(str(e))
        missing = [p for p in patterns if p not in prog.packages]
        if missing:
            raise Refused(f"packages did not load: {missing}")
        hashes = {}
        for pk in prog.packages.values():
            for f in pk["files"]:
                if f.startswith("<outside>/"):
                    raise Refused(f"package {pk['path']}: compiled file {f} lies outside the source tree")
                hashes[f] = _sha(ws / f)
    finally:
        shutil.rmtree(ws_parent, ignore_errors=True)
    with open(config_path, "rb") as f:
        cfg_sha = hashlib.sha256(f.read()).hexdigest()
    ctx = Ctx(prog, cfg)
    an = Analysis(ctx)
    sections = compute(an)
    docs = {}
    for stem, pks in cfg["documents"].items():
        pkset = set(pks)
        go_sec = split(an, sections, pkset, prog)
        names: set = set()
        _strings(go_sec, names)
        assumptions = [{"id": k, "text": v} for k, v in GENERIC_ASSUMPTIONS.items()]
        for name, p in cfg["primitives"].items():
            if name in names:
                assumptions.append({"id": f"go-prim:{name}", "text": p["text"]})
        assumptions.sort(key=lambda a: a["id"])
        files = sorted(f for p in sorted(pkset) for f in prog.packages[p]["files"])
        docs[stem] = {
            "facts_version": FACTS_VERSION,
            "target": {"repo": cfg["target"]["repo"], "commit": cfg["target"]["commit"],
                       "scope": "go packages: " + ", ".join(pks)},
            "extraction": {"method": "extracted", "frontend": "go",
                           "frontend_version": FRONTEND_VERSION_OF[cfg["config_version"]],
                           "tool": {"go": go_ver, "x_tools": xt, "ssadump_sha256": digest},
                           "config": {"path": rel_to(config_path, root), "sha256": cfg_sha},
                           "inputs": [{"path": f, "sha256": hashes[f]} for f in files]},
            "assumptions": assumptions,
            "go": go_sec,
        }
    return docs


def compute(an: Analysis) -> dict:
    """Every section over the whole program."""
    functions = {fid: an.function_entry(fid) for fid in an.listed}
    encoders = an.encoders()
    preds = an.predicates()
    matches = an.matches(preds)
    sec = {
        "functions": functions,
        "encoders": encoders,
        "decoders": an.decoders(),
        "predicates": preds,
        "matches": matches,
        "absences": an.absences(matches),
        "patches": an.patches(),
        "results": an.results(),
        "writes": an.writes(),
        "stores": an.stores(),
        "lost_writes": an.lost_writes(),
        "edges": an.edges(),
        "flows": an.flows_(),
        "loops": an.loops(),
        "globals": an.globals_(),
    }
    sec["debt"] = sorted({json.dumps(d, sort_keys=True): d for d in an.ctx.debt}.values(),
                         key=lambda d: (d["function"], d["kind"], d["where"], d["what"]))
    return sec


def split(an: Analysis, s: dict, pkset: set, prog: Program) -> dict:
    pkg = lambda fid: prog.funcs[fid].package if fid in prog.funcs else None  # noqa: E731
    mine = lambda fid: pkg(fid) in pkset  # noqa: E731
    functions = {fid: f for fid, f in s["functions"].items() if mine(fid)}
    strip = lambda e: {k: v for k, v in e.items() if not k.startswith("_")}  # noqa: E731
    return {
        "packages": [{"path": p, "dir": prog.packages[p]["dir"], "files": list(prog.packages[p]["files"])}
                     for p in sorted(pkset)],
        "functions": functions,
        "codecs": {
            "encoders": [strip(e) for e in s["encoders"] if mine(e["function"])],
            "decoders": [e for e in s["decoders"] if mine(e["function"])],
            "predicates": [e for e in s["predicates"] if mine(e["function"])],
            "matches": [e for e in s["matches"] if mine(e["predicate"])],
            "absences": [e for e in s["absences"] if mine(e["predicate"])],
            "patches": [e for e in s["patches"] if mine(e["function"])],
        },
        "slices": {
            "results": [e for e in s["results"] if mine(e["function"])],
            "writes": [e for e in s["writes"] if mine(e["function"])],
            "stores": [e for e in s["stores"] if mine(e["function"])],
            "lost_writes": [e for e in s["lost_writes"] if mine(e["function"])],
        },
        "calls": {
            "edges": [e for e in s["edges"] if mine(e["caller"])],
            "flows": [e for e in s["flows"] if mine(e["caller"])],
        },
        "loops": [e for e in s["loops"] if mine(e["function"])],
        "globals": [e for e in s["globals"] if e["package"] in pkset],
        "coverage": {
            "functions": len(functions),
            "with_paths": sum(1 for f in functions.values() if f["paths"] is not None),
            "debt": [d for d in s["debt"] if mine(d["function"])],
        },
    }


# ---------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    ap = argparse.ArgumentParser(prog="holon extract go")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root")
    ap.add_argument("--config")
    ap.add_argument("--src")
    ap.add_argument("--out-dir")
    ap.add_argument("--doc", nargs="+", action="extend", default=[])
    a = ap.parse_args(argv)
    if not re.fullmatch(r"M\d+", a.milestone):
        print(f"holon extract go: milestone {a.milestone!r} is not M<k>", file=sys.stderr)
        return 2
    root = Path(a.root).resolve() if a.root else REPO_ROOT
    config = Path(a.config) if a.config else root / "spec" / a.milestone / "lib" / "go_frontend.json"
    out_dir = Path(a.out_dir) if a.out_dir else root / "spec" / a.milestone / "facts"
    try:
        docs = extract(config, a.src, root)
        unknown = [d for d in a.doc if d not in docs]
        if unknown:
            raise Refused(f"unknown document stems: {unknown}")
        texts = {stem: render(doc) for stem, doc in docs.items() if not a.doc or stem in a.doc}
    except Refused as e:
        print(f"holon extract go: refused: {e}", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem in sorted(texts):
        with open(out_dir / f"{stem}.go.extracted.json", "w", encoding="utf-8") as f:
            f.write(texts[stem])
    print(f"holon extract go: wrote {len(texts)} document(s) to {out_dir}")
    return 0
