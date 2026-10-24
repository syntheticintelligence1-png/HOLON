"""Versioned machines over a contract's extracted deployment history (BUILD_PLAN I28, the laws half; whitepaper Def 4.3
S_k/A_k and the MIG edges, §5.1 initialization coherence, §10.1, §11.3, §11.6, §12.3; the contract is the docstring of
tests_m3/test_versions.py, rules V1-V9, PI1-PI6, S1-S3 and G1-G3).

  python -m holon versions extract [--check]     V1-V5: the deployed path, its edges, the per-version documents
  python -m holon versions model [--check]       V6: the versioned model (one module per version and the layer)
  python -m holon versions analyze [--check] [--facts DOC ..] [--out PATH]
                                                 PI1-PI5 and V4's gaps: the PAR-init analysis
  python -m holon versions inhabit [--check]     V8: an in-flight inhabitant for every MIG edge of the path
  python -m holon versions replay [--check]      V9: the upgrade path, the PAR-init witnesses and the cutover's
                                                 inhabitant on the real code
  common options: --sidecar PATH (default spec/M3/lib/versions.json), --root DIR

Every name of the target (the contract, its actions and families, the model's name, the interfaces the gaps name)
comes from the sidecar, I63's committed history and the extracted documents; nothing here names one. Exit codes: 0
written (or --check reproduced), 1 --check differs, 2 refused (a moved or missing input, a path rule broken, a missing
or unpinned tool; nothing written), 3 an error outside the debt rule (nothing written).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = "spec/M3/lib/versions.json"
VERSIONS_VERSION = "holon-versions/0.1"
ANALYSIS_VERSION = "holon-par-init/0.1"
INFLIGHT_VERSION = "holon-inflight/0.1"
REPLAY_VERSION = "holon-versions-replay/0.1"
PLACEHOLDER = "placeholder"
HASHES = ("keccak256", "sha256")


class Refused(Exception):
    """Exit 2: an input is missing, moved or malformed, or a path rule is broken; nothing is written."""


class VersionsError(Exception):
    """Exit 3: an error outside the debt rule; nothing is written."""


def render(doc) -> bytes:
    """Canonical JSON: sorted keys, indent 2, a final newline."""
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def read_json(p: Path, what: str):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{what} {p}: {e}") from e


def vkey(v: str):
    """Version order: V<n> by n, anything else after."""
    return (int(v[1:]) if v[1:].isdigit() else 10 ** 9, v)


class Ctx:
    """The sidecar, the configuration and the inputs every command reads (rule V1-V9's inputs)."""

    def __init__(self, root: Path | None = None, sidecar: str | None = None):
        self.root = Path(root or ROOT).resolve()
        self.side_rel = sidecar or SIDECAR
        p = Path(self.side_rel)
        self.side_path = p if p.is_absolute() else self.root / p
        if p.is_absolute():
            try:
                self.side_rel = p.resolve().relative_to(self.root).as_posix()
            except ValueError:
                self.side_rel = f"<outside>/{p.name}"
        self.side = read_json(self.side_path, "sidecar")
        if self.side.get("versions_version") != VERSIONS_VERSION:
            raise Refused(f"sidecar {self.side_rel}: versions_version is not {VERSIONS_VERSION}")
        for k in ("inputs", "outputs", "model", "proxy", "upgrade_path", "gaps", "search", "replay"):
            if k not in self.side:
                raise Refused(f"sidecar {self.side_rel}: {k} is missing")
        self.inputs = self.side["inputs"]
        self.outputs = self.side["outputs"]
        self.model = self.side["model"]
        m = re.match(r"^spec/(M\d+|T\d+)/lib/", self.side_rel)
        self.milestone = m.group(1) if m else "M3"
        self.cfg = read_json(self.root / "config" / "holon.json", "config")
        self._history = None
        self._timeline = None

    def path(self, rel: str) -> Path:
        return self.root / rel

    def input_path(self, key: str) -> Path:
        rel = self.inputs.get(key)
        if not isinstance(rel, str):
            raise Refused(f"sidecar inputs.{key} is missing")
        return self.root / rel

    def out(self, key: str) -> str:
        rel = self.outputs.get(key)
        if not isinstance(rel, str):
            raise Refused(f"sidecar outputs.{key} is missing")
        return rel

    @property
    def history(self) -> dict:
        if self._history is None:
            self._history = read_json(self.input_path("history"), "history")
        return self._history

    @property
    def timeline(self) -> dict:
        if self._timeline is None:
            self._timeline = read_json(self.input_path("timeline"), "timeline")
        return self._timeline

    def file_ref(self, key: str) -> dict:
        rel = self.inputs[key]
        return {"path": rel, "sha256": sha256_file(self.root / rel)}

    def side_ref(self) -> dict:
        return {"path": self.side_rel, "sha256": sha256_file(self.side_path)}

    def version(self, vid: str) -> dict:
        for v in self.history["versions"]:
            if v["id"] == vid:
                return v
        raise Refused(f"the history has no version {vid}")

    def gap_meta(self, kind: str) -> dict:
        g = (self.side.get("gaps") or {}).get(kind)
        if not isinstance(g, dict) or "obligation" not in g or "question" not in g:
            raise Refused(f"sidecar gaps.{kind} is missing its obligation or question")
        return {"obligation": g["obligation"], "question": g["question"], "status": "open"}

    def deployment_record(self) -> dict:
        return read_json(self.input_path("deployment_record"), "deployment record")

    def versions_doc(self) -> dict:
        p = self.root / self.out("versions")
        if not p.is_file():
            raise Refused(f"{self.out('versions')} is missing: run `holon versions extract` first")
        return read_json(p, "versioned document")

    def documents(self) -> dict:
        """{version: (absolute path, repo-relative path)} of the versioned document's per-version documents, each
        checked against the sha256 it records (else Refused)."""
        vd = self.versions_doc()
        out = {}
        for v, d in sorted(vd.get("documents", {}).items(), key=lambda kv: vkey(kv[0])):
            p = self.root / d["path"]
            if not p.is_file() or sha256_file(p) != d["sha256"]:
                raise Refused(f"{d['path']} is not the document {self.out('versions')} records")
            out[v] = (p, d["path"])
        return out


def write_or_check(path: Path, data: bytes, check: bool) -> bool:
    """Write data to path (atomically), or with check compare; returns whether the file holds data afterwards (check)
    or True (written)."""
    import os
    path = Path(path)
    if check:
        return path.is_file() and path.read_bytes() == data
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return True


def main(argv=None) -> int:
    import argparse
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="holon versions", description="versioned machines over the deployment history")
    ap.add_argument("what", choices=["extract", "model", "analyze", "inhabit", "replay"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sidecar")
    ap.add_argument("--root")
    ap.add_argument("--facts", nargs="+", help="analyze: transitions documents, one version each (V0, V1, ..)")
    ap.add_argument("--out", help="analyze: the output path (default the sidecar's outputs.analysis)")
    a = ap.parse_args(argv)
    try:
        ctx = Ctx(Path(a.root) if a.root else None, a.sidecar)
        if a.what == "extract":
            from . import extract
            return extract.run(ctx, a.check)
        if a.what == "model":
            from . import model
            return model.run(ctx, a.check)
        if a.what == "analyze":
            from . import analyze
            return analyze.run(ctx, a.check, a.facts, a.out)
        if a.what == "inhabit":
            from . import inhabit
            return inhabit.run(ctx, a.check)
        from . import replay
        return replay.run(ctx, a.check)
    except Refused as e:
        print(f"holon versions {a.what}: refused: {e}", file=sys.stderr)
        return 2
    except VersionsError as e:
        print(f"holon versions {a.what}: error: {e}", file=sys.stderr)
        return 3
