"""A migration's slash sites linked with the registries each version names (the contract: the docstring of
tests_m3/test_cutover_slash.py).

  python -m holon cutover acquire|model|corpus|refine [--milestone M3] [--root DIR] [--check]

A milestone's sidecar (spec/<M>/lib/cutover_slash.json) names the versioned document, the bundle it extends (I69's
sidecar and outputs), the registry linked at each end of the migration, the acquisition (the explorer record, the
compile-match criterion, the labels), the planted corpus and the outputs. This package is generic: every contract,
function, address and slot it uses comes from the sidecars, the documents or the compiler's output. It is imported by
no generator closure.

Modules: acquire (A1-A3), build (creation codes from the members' commits), harness (L2: the forge harness and its
deployment), machine (L1: the linked versioned machine), corpus (L3), refine (L4, M2), model (M1).

Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input); 3 a build,
model or harness error. Outputs are canonical JSON (sorted keys, indent 1, a final newline), byte-identical across runs.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from ..bundle import BundleError, Refused, render, sha256_bytes, sha256_file, write_or_check  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = "spec/{m}/lib/cutover_slash.json"


@dataclass
class Ctx:
    root: Path
    milestone: str
    side_rel: str
    side: dict
    cfg: dict = field(default_factory=dict)
    _bundle: object = None
    _versions: object = None

    def path(self, rel: str) -> Path:
        return self.root / rel

    def out(self, key: str) -> str:
        return self.side["outputs"][key]

    def load(self, rel: str):
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def ref(self, rel: str) -> dict:
        return {"path": rel, "sha256": sha256_file(self.root / rel)}

    def bundle(self):
        """The bundle context this one extends (its sidecar is the inputs' bundle_sidecar)."""
        if self._bundle is None:
            from ..bundle import context
            self._bundle = context(self.root, self.milestone)
            if self._bundle.side_rel != self.side["inputs"]["bundle_sidecar"]:
                raise Refused(f"the bundle sidecar is {self._bundle.side_rel}, the inputs name "
                              f"{self.side['inputs']['bundle_sidecar']}")
        return self._bundle

    def versioned(self) -> dict:
        return self.load(self.side["inputs"]["versioned"])

    def versions(self):
        """The versioned machine's context (holon.versions), for its implementations' builds."""
        if self._versions is None:
            from ..versions import Ctx as VCtx
            self._versions = VCtx(self.root)
        return self._versions


def context(root: Path, milestone: str) -> Ctx:
    root = Path(root).resolve()
    rel = SIDECAR.format(m=milestone)
    p = root / rel
    if not p.is_file():
        raise Refused(f"{rel} is missing")
    side = json.loads(p.read_text(encoding="utf-8"))
    cfg = json.loads((root / "config" / "holon.json").read_text(encoding="utf-8"))
    return Ctx(root=root, milestone=milestone, side_rel=rel, side=side, cfg=cfg)


STEPS = ("acquire", "model", "corpus", "refine")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon cutover", description="a migration's slash sites, linked")
    ap.add_argument("step", choices=STEPS)
    ap.add_argument("--milestone", default="M3")
    ap.add_argument("--root")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT

    def log(s):
        print(f"holon cutover {a.step}: {s}", file=sys.stderr)
    from ..frontends import ExtractionError, Refused as FRefused
    try:
        ctx = context(root, a.milestone)
        if a.step == "acquire":
            from . import acquire
            return write_or_check(ctx, acquire.build(ctx, log), a.check, log=log)
        if a.step == "model":
            from . import model
            return write_or_check(ctx, model.build(ctx, log), a.check, log=log)
        if a.step == "corpus":
            from . import corpus
            return write_or_check(ctx, corpus.build(ctx, log), a.check, log=log)
        from . import refine
        return write_or_check(ctx, refine.run(ctx, log), a.check, log=log)
    except (Refused, FRefused) as e:
        log(f"refused: {e}")
        return 2
    except (BundleError, ExtractionError) as e:
        log(f"error: {e}")
        return 3
