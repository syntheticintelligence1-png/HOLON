"""python -m holon intent <command> (I55, the intent lane; key I55 design):

  atomize  [--root DIR] [--out PATH] [--check]   results/M5/intent/atoms.json (holon.intent.atomize)
  compile  [--root DIR] [--check]                laws/INTENT/, results/M5/intent/compile.json, gen/M5/intent/model/
                                                 and gen/M5/intent/facts/ (holon.intent.compile)
  requests [--root DIR] [--check]                results/M5/intent/review_requests.json (holon.intent.review)
  run      [--root DIR] [--check --tmp DIR]      gen/M5/intent/<law>/ and results/M5/intent/records/ (holon.intent.run)
  metrics  [--root DIR] [--check]                results/M5/intent/{l10_inputs,l10,obstructions,sym_route_i}.json
                                                 (holon.intent.metrics)

Each command imports only its own module, so the atomizer's closure is its own (key design I1).
"""
from __future__ import annotations

import importlib
import sys

COMMANDS = {"atomize": "atomize", "compile": "compile", "requests": "review", "run": "run", "metrics": "metrics"}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    mod = importlib.import_module(f"holon.intent.{COMMANDS[argv[0]]}")
    return mod.main(argv[1:])
