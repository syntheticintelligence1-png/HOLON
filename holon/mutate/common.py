"""Shared helpers of holon.mutate (I61): the instrument, the pinned target, canonical JSON and scratch trees.

Paths are relative to a HOLON root (default: this checkout). Committed outputs are canonical JSON (dump: sorted keys,
indent 2, a final newline); hashes are over compact canonical JSON (compact: sorted keys, separators ',' ':', UTF-8).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

INSTRUMENT = Path("spec/M2/lib/mutation_catalog_i61.json")
SHEET = Path("spec/M2/lib/mutation_diff_sheet_i61.md")
REVIEW = Path("docs/iterations/I61_catalog_review.json")
ADJUDICATION = Path("spec/M2/equivalent_mutants_i61.json")
RESULTS = Path("results/M2/mutation_i61")
CONTROLS = RESULTS / "controls"
GATE = RESULTS / "gate.json"
SUMMARY = RESULTS / "summary.json"
GEN = Path("gen/M2/mutation_i61")
PROJECTED = GEN / "header.projected.json"
HARNESS = Path("replay/M2/mutation_i61")
FACTS2 = Path("spec/M2/facts")
HEADER_FACTS = Path("facts/morph_header.json")


class MutateError(Exception):
    """A refusal or a failed step, reported with what was tried."""


def root(r=None) -> Path:
    return Path(r).resolve() if r else ROOT


def load_json(p):
    return json.loads(Path(p).read_text())


def dump(obj) -> str:
    """Canonical JSON of a committed output."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def compact(obj) -> str:
    """Canonical JSON of a hashed value."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode())


def sha256_file(p) -> str:
    return sha256_bytes(Path(p).read_bytes())


def write_text(p: Path, text: str) -> bool:
    """Write text when it differs; True when the file changed."""
    p = Path(p)
    if p.is_file() and p.read_text() == text:
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return True


def instrument(r=None) -> dict:
    return load_json(root(r) / INSTRUMENT)


def instrument_ref(r=None) -> dict:
    return {"path": INSTRUMENT.as_posix(), "sha256": sha256_file(root(r) / INSTRUMENT)}


def config(r=None) -> dict:
    return load_json(root(r) / "config" / "holon.json")


def checkout(r=None) -> Path:
    """The pinned target checkout (config replay.morph), read only."""
    return Path(config(r)["replay"]["morph"])


def sol_deps(r=None) -> Path:
    """The pinned OpenZeppelin units: config replay.sol_deps/node_modules, read only."""
    return Path(config(r)["replay"]["sol_deps"]) / "node_modules"


def normalized(doc: dict) -> dict:
    """A document without its provenance (instrument law_sets.own_input): the top-level 'extraction' block and the
    'commit' of its top-level 'target'."""
    d = {k: v for k, v in doc.items() if k != "extraction"}
    if isinstance(d.get("target"), dict):
        d["target"] = {k: v for k, v in d["target"].items() if k != "commit"}
    return d


def normalized_sha256(doc: dict) -> str:
    return sha256_text(compact(normalized(doc)))


def pipeline_commit(r=None) -> str:
    p = subprocess.run(["git", "-C", str(root(r)), "rev-parse", "HEAD"], capture_output=True, text=True)
    if p.returncode != 0:
        raise MutateError(f"git rev-parse HEAD failed in {root(r)}: {p.stderr.strip()[-300:]}")
    return p.stdout.strip()


def scratch_dir(prefix: str, base=None) -> Path:
    base = Path(base) if base else None
    if base:
        base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(base) if base else None))


def tree_parts(src: Path) -> list:
    """The checkout parts a source tree needs: contracts/ and the modules go.work uses."""
    parts = {"contracts"}
    gw = Path(src) / "go.work"
    if gw.is_file():
        inside = False
        for line in gw.read_text().splitlines():
            t = line.split("//")[0].strip()
            if t.startswith("use ("):
                inside = True
                continue
            if inside and t == ")":
                inside = False
                continue
            if inside and t:
                parts.add(t.lstrip("./").rstrip("/"))
            elif t.startswith("use ") and not t.startswith("use ("):
                parts.add(t[4:].strip().lstrip("./").rstrip("/"))
    return sorted(parts)


def copy_tree(src: Path, dest: Path, parts=None) -> Path:
    """A scratch copy of a source tree laid out as the checkout: the named parts (default tree_parts: contracts/ and the
    go.work modules), go.work and go.work.sum; node_modules and .git are never copied."""
    src, dest = Path(src), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    names = parts if parts is not None else tree_parts(src)
    for x in names:
        s = src / x
        if not s.exists():
            continue
        (dest / x).parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(s, dest / x, symlinks=True, ignore=shutil.ignore_patterns(".git", "node_modules"))
        else:
            shutil.copy2(s, dest / x)
    for f in ("go.work", "go.work.sum"):
        if (src / f).is_file() and not (dest / f).exists():
            shutil.copy2(src / f, dest / f)
    return dest


def env_tools() -> dict:
    """The environment every child tool runs in: Bend without telemetry, Go offline at the pinned toolchain."""
    e = dict(os.environ)
    e["BEND_NO_TELEMETRY"] = "1"
    e.setdefault("GOTOOLCHAIN", "local")
    e.setdefault("GOFLAGS", "-mod=readonly")
    e.setdefault("GOPROXY", "off")
    return e
