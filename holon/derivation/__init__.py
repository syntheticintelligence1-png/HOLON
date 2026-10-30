"""holon derivation: a Go consumer extracted as SSA beside the frontend's document, evaluated by an interpreter, joined
with the adopted Solidity commit into an evaluator-level product machine, and refined against the real Go code
(BUILD_PLAN row I85 = I39a; whitepaper §5.1 consumer and cycle, §5.5, §8.7, §10.1 Go; the contract is the docstring of
tests_m3/test_derivation_extraction.py).

  python -m holon derivation extract|corpus|product|refine [--check] [--sidecar PATH] [--root DIR]

  extract  the Go frontend's document of the sidecar's stem (its own config, unchanged) plus the "consumer" section: the
           SSA of the consumer's closure, its environment, globals, types and coverage            holon.derivation.extract
  corpus   the sidecar's corpus made concrete: raw payloads compressed by the real library, packed for blobs
                                                                                                  holon.derivation.corpus
  product  the product machine's traces: the Solidity commit (holon.extracted_eval), the committed header as the next
           parent, the derived batch of each committed batch                                     holon.derivation.product
  refine   every corpus and product case on the consumer model and on the real code (the generated Go replay)
                                                                                                  holon.derivation.refine

The interpreter (holon.derivation.interp) and its standard-library natives (holon.derivation.natives) are the consumer
model; holon.derivation.goside generates the Go test that is both the replay and the environment's oracle. Everything
specific to a target comes from the sidecar (default spec/M3/lib/derivation.json), the documents it names and the
ssadump output. Exit codes: 0 written (or --check reproduced), 1 --check differs, 2 refused (nothing written), 3 an
extraction, product or replay error (nothing written). Outputs are canonical JSON (sorted keys, indent 1, a final
newline). This package is imported by no generator closure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = "spec/M3/lib/derivation.json"
OUT_GEN = "gen/M3/derivation"
OUT_RES = "results/M3/derivation"
OUT_REPLAY = "replay/M3/derivation"


class Refused(Exception):
    """exit 2: an input is missing or stale; nothing written."""


class DerivationError(Exception):
    """exit 3: an extraction, product or replay error; nothing written."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def load(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{p}: {e}")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(root: Path, rel: str) -> dict:
    return {"path": rel, "sha256": sha256_file(root / rel)}


def sidecar(root: Path, rel: str = SIDECAR) -> dict:
    side = load(root / rel)
    if side.get("derivation_version") != "holon-derivation/0.1":
        raise Refused(f"{rel}: derivation_version must be holon-derivation/0.1")
    for k in ("target", "extract", "product", "corpus"):
        if not isinstance(side.get(k), dict):
            raise Refused(f"{rel}: no {k} section")
    return side


def write_or_check(root: Path, outputs: dict, check: bool) -> int:
    """Write {rel: text}, or compare with the committed files: 0 same / written, 1 differs."""
    if check:
        bad = [rel for rel, text in sorted(outputs.items())
               if not (root / rel).is_file() or (root / rel).read_text(encoding="utf-8") != text]
        for rel in bad:
            print(f"holon derivation: {rel} differs", file=sys.stderr)
        return 1 if bad else 0
    for rel, text in sorted(outputs.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"holon derivation: wrote {rel}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon derivation")
    ap.add_argument("command", choices=("extract", "corpus", "product", "refine"))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sidecar", default=SIDECAR)
    ap.add_argument("--root")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        side = sidecar(root, a.sidecar)
        if a.command == "extract":
            from . import extract
            outputs = extract.run(root, side, a.sidecar)
        elif a.command == "corpus":
            from . import corpus
            outputs = corpus.run(root, side, a.sidecar)
        elif a.command == "product":
            from . import product
            outputs = product.run(root, side, a.sidecar)
        else:
            from . import refine
            outputs = refine.run(root, side, a.sidecar, check=a.check)
    except Refused as e:
        print(f"holon derivation {a.command}: refused: {e}", file=sys.stderr)
        return 2
    except DerivationError as e:
        print(f"holon derivation {a.command}: error: {e}", file=sys.stderr)
        return 3
    return write_or_check(root, outputs, a.check)
