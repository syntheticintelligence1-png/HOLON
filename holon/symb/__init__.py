"""SYM over Bundle I (I92 = I34b; contract tests_m3/test_sym_bundle.py, rules K1-K12): a member's other version, its
migration map, the members' nominal sorts, and the laws over the members and their links.

    python -m holon symb legacy --milestone M3 [--check]     K1, K3: the sidecar's legacy member at its commit, its
                                                              model, and eta (gen/M3/symb/legacy/, eta_enq.json)
    python -m holon symb sorts --milestone M3 [--check]      K2: the members' nominal sorts (gen/M3/symb/sorts.json)
    python -m holon symb sections --milestone M3 [--check]   K5: the members' raw sections (gen/M3/symb/sections/),
                                                              the versioned member and the link (versioned/, link/)
    python -m holon symb replay --milestone M3 [--check]     K7: every witness run on the real code
                                                              (replay/M3/symb/<law>.json, holon.symb.replay)
    python -m holon symb contrast --milestone M3 [--check]   P6's contrast: each sentinel invariant's search with the
                                                              member at the head only (results/M3/symb/head_only.json)

The sidecar is spec/<M>/lib/sym_bundle.json; the members' documents and extraction specs are I69's bundle sidecar's
(spec/<M>/lib/bundle.json, holon.bundle). Nothing here names a target: members, versions and registers come from the
two sidecars and the documents.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SYMB_VERSION = "holon-symb/0.1"
STEPS = ("legacy", "sorts", "sections", "replay", "contrast")


class SymbError(Exception):
    pass


@dataclass
class Ctx:
    root: Path
    milestone: str
    side_rel: str
    side: dict
    bundle: object      # holon.bundle.Ctx

    def out(self, *parts: str) -> str:
        return "/".join([f"gen/{self.milestone}/symb", *parts])


def context(root: Path, milestone: str) -> Ctx:
    from .. import bundle
    root = Path(root).resolve()
    rel = f"spec/{milestone}/lib/sym_bundle.json"
    p = root / rel
    if not p.is_file():
        raise SymbError(f"{rel} is missing")
    return Ctx(root=root, milestone=milestone, side_rel=rel, side=json.loads(p.read_text(encoding="utf-8")),
               bundle=bundle.context(root, milestone))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon symb", description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=STEPS)
    ap.add_argument("--milestone", default="M3")
    ap.add_argument("--root", default=".")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)

    def log(msg):
        print(f"holon symb {a.step}: {msg}", flush=True)
    try:
        ctx = context(Path(a.root), a.milestone)
        if a.step == "legacy":
            from . import legacy
            return legacy.main(ctx, a.check, log)
        if a.step == "sorts":
            from . import sorts
            return sorts.main(ctx, a.check, log)
        if a.step == "sections":
            from . import sections
            return sections.main(ctx, a.check, log)
        if a.step == "replay":
            from . import replay
            return replay.main(ctx, a.check, log)
        if a.step == "contrast":
            from ..bundle import render, write_or_check
            from .lawrun import Decider, head_only
            d = Decider(ctx.root, ctx.milestone, ctx.root / "results" / ctx.milestone, ctx.root / "gen" / ctx.milestone,
                        log=log)
            try:
                doc = head_only(d)
            finally:
                d.close()
            for lid, v in doc.items():
                log(f"{lid}: {v['status']} ({v['bound']})")
            return write_or_check(ctx.bundle, {f"results/{ctx.milestone}/symb/head_only.json": render(doc)}, a.check,
                                  log=log)
    except SymbError as e:
        print(f"holon symb {a.step}: refused: {e}", file=sys.stderr)
        return 2
    return 2
