"""python -m holon eval <command> (I48): each command lives in its own module, imported on use."""
from __future__ import annotations

import importlib
import sys

from .common import Refused

USAGE = """usage: python -m holon eval <command> [options]

  index      --system ID --out FILE                          mechanical index items for one collector (rule C2)
  candidates --from DIR [--check]                            assemble spec/eval/candidates.json from collector files
  verify     [--root DIR] [--cache DIR]                      re-derive every candidate's git facts (rule C3)
  select     [--root DIR] [--check]                          round-robin selection (rule C4)
  label      --role a|b|adjudicator --model NAME [--root DIR]   run one labeller over the corpus (rule C5)
  agree      [--root DIR] [--check]                          labels, final labels and agreement (rules C5-C6)
  rename     --root DIR --files F [F ...] --seed S --out DIR2 --map MAP   (rules N0-N3)
  unrename   --root DIR2 --map MAP --out DIR3
  renaming   [--root DIR] [--cache DIR] [--check]            gen/eval/renaming/<entry>.json (rule N3)
  controls   [--root DIR] [--check]                          the unsolved controls (rules K1-K2)
"""

COMMANDS = {
    "index": ("holon.eval.index", "cli_index"),
    "candidates": ("holon.eval.candidates", "cli_candidates"),
    "verify": ("holon.eval.verify", "cli_verify"),
    "select": ("holon.eval.select", "cli_select"),
    "label": ("holon.eval.label", "cli_label"),
    "agree": ("holon.eval.agree", "cli_agree"),
    "rename": ("holon.eval.rename", "cli_rename"),
    "unrename": ("holon.eval.rename", "cli_unrename"),
    "renaming": ("holon.eval.renaming", "cli_renaming"),
    "controls": ("holon.eval.controls", "cli_controls"),
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        sys.stderr.write(USAGE)
        return 2
    module, fn = COMMANDS[argv[0]]
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError as e:
        if e.name != module:
            raise
        print(f"holon eval {argv[0]}: {module} is not built yet", file=sys.stderr)
        return 2
    try:
        return int(getattr(mod, fn)(argv[1:]) or 0)
    except Refused as e:
        print(f"holon eval {argv[0]}: refused: {e}", file=sys.stderr)
        return 2
