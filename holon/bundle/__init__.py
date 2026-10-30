"""A bundle of linked contracts (the bundle contract: the docstring of tests_m3/test_bundle_extraction.py).

  python -m holon bundle extract|model|corpus|refine|history|fetch|timeline [--milestone M3] [--root DIR] [--check]
  python -m holon bundle laws|replay-laws|bmc [--milestone M3] [--root DIR] [--check]   (I86: the bundle's laws)

A milestone's bundle sidecar (spec/<M>/lib/bundle.json) names the members (one adopted transitions document, the
others extracted from their sources), the wiring a deployment sets (which storage or immutable variable of a member
holds another member's address), the deployment, the corpus, the observables, the acquisition (a registry's pinned
tags, proxies, a window, hosts) and the output paths. This package is generic: every contract, function, address, slot
and host it uses comes from the sidecar, the documents or the compiler's output. It is imported by no generator
closure (holon.records.generator_files, GEN3, GEN_FACT, GEN_UNDO, GEN_DISCH, GEN_PROFILE).

Modules: extract (E1-E5: generated sidecars, documents, the declaration, links by rule L2), model (M3: member models),
corpus (C3), machine (L1-L8: the linked machine over holon.extracted_eval's programs), harness (C1-C2: the forge
harness), refine (C5-C6, M4), acquire (A1-A6: history, fetch, timeline).

Exit codes: 0 written (or --check reproduced); 1 --check differs; 2 refused (a missing or stale input, a missing git
object), nothing written; 3 an extraction, model, harness or fetch error, nothing written. Outputs are canonical JSON
(sorted keys, indent 1, a final newline) but receipts (compact canonical bytes) and code files; byte-identical across
runs; no timestamps and no absolute paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_VERSION = "holon-bundle/0.1"


class Refused(Exception):
    """An input is refused (exit 2): nothing written."""


class BundleError(Exception):
    """An extraction, model, harness or fetch error (exit 3): nothing written."""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(Path(p).read_bytes())


def render(doc) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


@dataclass
class Ctx:
    root: Path
    milestone: str
    side_rel: str
    side: dict
    cfg: dict = field(default_factory=dict)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def out(self, key: str) -> str:
        return self.side["outputs"][key]

    def load(self, rel: str):
        return json.loads((self.root / rel).read_text(encoding="utf-8"))

    def ref(self, rel: str) -> dict:
        return {"path": rel, "sha256": sha256_file(self.root / rel)}

    def members(self) -> list:
        return list(self.side["members"])

    def all_members(self) -> list:
        return list(self.side["members"]) + list(self.side.get("extracted_only") or [])

    def member(self, name: str) -> dict:
        for m in self.all_members():
            if m["name"] == name:
                return m
        raise Refused(f"no member {name} in {self.side_rel}")

    def document_rel(self, m: dict) -> str:
        return m["document"] if m.get("adopted") else f"{self.out('documents')}/{m['name']}.json"

    def commit_of(self, m: dict) -> str:
        if m.get("adopted"):
            return self.load(m["document"])["target"]["commit"]
        return m["commit"]

    def source_repo(self) -> str:
        repo = ((self.cfg.get("extract") or {}).get("sources") or {}).get(self.side["target"]["repo"])
        if not repo or not Path(repo).is_dir():
            raise Refused(f"config/holon.json extract.sources has no checkout of {self.side['target']['repo']}")
        return repo


def context(root: Path, milestone: str) -> Ctx:
    root = Path(root).resolve()
    rel = f"spec/{milestone}/lib/bundle.json"
    p = root / rel
    if not p.is_file():
        raise Refused(f"{rel} is missing")
    side = json.loads(p.read_text(encoding="utf-8"))
    cfg = json.loads((root / "config" / "holon.json").read_text(encoding="utf-8"))
    return Ctx(root=root, milestone=milestone, side_rel=rel, side=side, cfg=cfg)


def write_or_check(ctx: Ctx, files: dict, check: bool, owned: list | None = None, log=print) -> int:
    """Write {relative path: bytes} (or, with check, compare them with the committed files). `owned` lists directories
    whose other files are stale: --check reports them, a write removes them. Returns the exit code."""
    stale = []
    for d in owned or []:
        base = ctx.path(d)
        if base.is_dir():
            for p in sorted(base.rglob("*")):
                rel = p.relative_to(ctx.root).as_posix()
                if p.is_file() and rel not in files:
                    stale.append(rel)
    if check:
        bad = [rel for rel, data in sorted(files.items())
               if not ctx.path(rel).is_file() or ctx.path(rel).read_bytes() != data]
        for rel in bad + stale:
            log(f"differs: {rel}")
        log(f"{len(files)} files checked: {'up to date' if not bad and not stale else 'differ'}")
        return 0 if not bad and not stale else 1
    for rel in stale:
        ctx.path(rel).unlink()
    for rel, data in sorted(files.items()):
        p = ctx.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not (p.is_file() and p.read_bytes() == data):
            tmp = p.with_name(p.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, p)
    log(f"wrote {len(files)} files")
    return 0


STEPS = ("extract", "model", "corpus", "refine", "history", "fetch", "timeline", "laws", "replay-laws", "bmc")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon bundle", description="a bundle of linked contracts (bundle)")
    ap.add_argument("step", choices=STEPS)
    ap.add_argument("--milestone", default="M3")
    ap.add_argument("--root")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--jobs", type=int, default=0)
    ap.add_argument("--cached-only", action="store_true",
                    help="bmc: no search; the document from the cached searches (a target without one is not run)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT

    def log(s):
        print(f"holon bundle {a.step}: {s}", file=sys.stderr)
    from ..frontends import ExtractionError, Refused as FRefused
    try:
        ctx = context(root, a.milestone)
        if a.step == "extract":
            from . import extract
            return extract.main(ctx, a.check, log)
        if a.step == "model":
            from . import model
            return model.main(ctx, a.check, log)
        if a.step == "corpus":
            from . import corpus
            return corpus.main(ctx, a.check, log)
        if a.step == "refine":
            from . import refine
            return refine.main(ctx, a.check, log, jobs=a.jobs)
        if a.step == "laws":             # I86: the laws' analysis, claims modules and the adopted member's law model
            from . import laws
            return laws.main(ctx, a.check, log)
        if a.step == "replay-laws":      # I86: the witnesses of the bundle's laws on the real bundle
            from . import replay_laws
            return replay_laws.main(ctx, a.check, log, jobs=a.jobs)
        if a.step == "bmc":              # I86: Q28's BMC over the linked queue (rules Q1-Q5)
            from . import linkbmc_out
            return linkbmc_out.main(ctx, a.check, log, jobs=a.jobs, cached_only=a.cached_only)
        from . import acquire
        return getattr(acquire, f"main_{a.step}")(ctx, a.check, log)
    except (Refused, FRefused) as e:
        log(f"refused: {e}")
        return 2
    except (BundleError, ExtractionError) as e:
        log(f"error: {e}")
        return 3
