"""holon bundle2: a bundle of extracted contracts beside the adopted document, linked into one machine and refined on
the real code (BUILD_PLAN row I80 = I37a; whitepaper §10.1 Solidity and linking, §8.5, §8.7, App. D; the contract is
the docstring of tests_m3/test_bundle2_extraction.py).

  python -m holon bundle2 extract|deploy|model|corpus|refine|acquire [--check] [--sidecar PATH] [--root DIR]

  extract  generated extraction sidecars and transitions documents of the sidecar's members (I19's frontend, each in a
           child process bounded by the sidecar's extract.timeout_s), and the declaration (coverage, static links,
           public-input views, cost sites)                                              holon.bundle2.extract
  model    the members' models: holon.sorts.model3's untyped machine with the storage-dynamic-array extension
                                                                                        holon.bundle2.modelx
  corpus   the step corpus (I20's m1 traces, the sidecar's seed traces, its random traces)  holon.bundle2.harness
  deploy   the harness's deployment record (one forge run)                              holon.bundle2.harness
  refine   the linked machine and the member models against the real code (forge)       holon.bundle2.harness
  acquire  acquisition notes from committed records and the target's git objects       holon.bundle2.acquire

Everything specific to a target comes from the sidecar (default spec/M3/lib/bundle2.json), the documents it names and
the compiler's output. Exit codes: 0 written (or --check reproduced), 1 --check differs, 2 refused (nothing written),
3 an extraction, model or harness error (nothing written). Outputs are canonical JSON (sorted keys, indent 1, a final
newline). This package is imported by no generator closure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = "spec/M3/lib/bundle2.json"


class Refused(Exception):
    """exit 2: an input is missing or stale; nothing written."""


class BundleError(Exception):
    """exit 3: an extraction, model or harness error; nothing written."""


def render(obj) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def file_sha(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


class Ctx:
    """The sidecar, the configuration and the output paths."""

    def __init__(self, root: Path, sidecar: str):
        self.root = Path(root)
        self.side_rel = sidecar
        p = self.root / sidecar
        try:
            self.side = json.loads(p.read_text(encoding="utf-8"))
            self.cfg = json.loads((self.root / "config" / "holon.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise Refused(f"{p}: {e}") from e
        self.side_sha = file_sha(p)
        self.out = self.side.get("outputs") or {}

    def path(self, key: str) -> Path:
        if key not in self.out:
            raise Refused(f"sidecar outputs has no {key}")
        return self.root / self.out[key]

    def rel(self, p: Path) -> str:
        return Path(p).resolve().relative_to(self.root.resolve()).as_posix()

    def members(self) -> list[dict]:
        return list(self.side.get("members") or [])

    def extracted_only(self) -> list[dict]:
        return list(self.side.get("extracted_only") or [])

    def source(self) -> str:
        repo = ((self.cfg.get("extract") or {}).get("sources") or {}).get(self.side["target"]["repo"])
        if not repo or not Path(repo).is_dir():
            raise Refused(f"config extract.sources has no checkout of {self.side['target']['repo']}")
        return repo


class Writer:
    """Collects outputs, then writes them all (or, with check, compares them all): nothing is written on an error."""

    def __init__(self, check: bool):
        self.check = check
        self.files: dict = {}

    def put(self, path: Path, data: bytes) -> None:
        self.files[Path(path)] = data

    def finish(self, label: str) -> int:
        if self.check:
            bad = [p for p, d in sorted(self.files.items()) if not p.is_file() or p.read_bytes() != d]
            for p in bad:
                print(f"holon bundle2 {label}: {p} differs from a fresh run", file=sys.stderr)
            if not bad:
                print(f"holon bundle2 {label}: {len(self.files)} files up to date")
            return 1 if bad else 0
        for p, d in sorted(self.files.items()):
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.is_file() and p.read_bytes() == d:
                continue
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_bytes(d)
            os.replace(tmp, p)
        print(f"holon bundle2 {label}: wrote {len(self.files)} files")
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon bundle2", description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["extract", "deploy", "model", "corpus", "refine", "acquire"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sidecar", default=SIDECAR)
    ap.add_argument("--root")
    ap.add_argument("--work", help="scratch directory for forge projects (default: a temporary directory)")
    ap.add_argument("--jobs", type=int, default=4)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        ctx = Ctx(root, a.sidecar)
        if a.command == "extract":
            from . import extract
            return extract.run(ctx, a.check)
        if a.command == "model":
            from . import modelx
            return modelx.run(ctx, a.check)
        if a.command == "acquire":
            from . import acquire
            return acquire.run(ctx, a.check)
        from . import harness
        return {"corpus": harness.run_corpus, "deploy": harness.run_deploy,
                "refine": harness.run_refine}[a.command](ctx, a.check, a)
    except Refused as e:
        print(f"holon bundle2 {a.command}: refused: {e}", file=sys.stderr)
        return 2
    except BundleError as e:
        print(f"holon bundle2 {a.command}: error: {e}", file=sys.stderr)
        return 3
