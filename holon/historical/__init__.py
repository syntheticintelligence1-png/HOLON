"""Historical on-chain acquisition and replay on real inputs (I59, the I23a track; I23, the M2 exit evaluation; human
answer Q5 in docs/HUMAN_ANSWERS.md: on-chain replay is make or break). The frozen instruments are
spec/M2/lib/historical.json (I59) and spec/M2/lib/historical_exit.json (I23); the contracts are the docstrings of
tests_m2/test_historical.py and tests_m2/test_historical_exit.py.

    python -m holon historical fetch       [--milestone M2] [--from N] [--to M] [--index PATH] [--snapshot DIR]
    python -m holon historical replay      [--milestone M2] [--index PATH] [--out PATH]
    python -m holon historical fetch-state [--milestone M2] [--snapshot DIR] [--out PATH] [--offline]
    python -m holon historical codec       [--milestone M2]
    python -m holon historical trans       [--milestone M2]
    python -m holon historical laws        [--milestone M2]
    python -m holon historical smoke       [--milestone M2]
    python -m holon historical exit        [--milestone M2] [--check]

Modules:
    net         HTTP: per-host pacing, retries with backoff, JSON-RPC; hosts only in outputs, secrets scrubbed
    store       the content-addressed snapshot outside the repo and the resumable fetch state
    fetch       logs, transactions, blobs, receipts; the index
    abi         the pinned ABI of the commit functions, and the selectors of every signature in the pinned
                checkout's history of the interface (to name a function, never to decode it)
    checks      header_checks: the per-header checks on the frozen M0 model, without the chain
    replay      the replay, the Go decoder run and the disagreements
    context     what the I23 commands read (the instrument, I59's index and snapshot)
    stepper     real transactions through the extracted model, observed, never changed
    supplement  fetch-state: the supplementary acquisition (state, calls, headers, code)
    trans       the transitions window through the extracted model; pinned the deployed code against the pinned build
    codec       the header carrier's edges on every real parent header
    laws        the per-law table of historical evidence
    smoke       the synthetic smoke fixtures (never counted)
    exit        the M2 exit report
"""
from __future__ import annotations

import sys

from .checks import header_checks  # noqa: F401

COMMANDS = {"fetch": "fetch", "replay": "replay", "fetch-state": "supplement", "codec": "codec", "trans": "trans",
            "laws": "laws", "smoke": "smoke", "exit": "exit_report"}


def main(argv=None) -> int:
    import importlib
    argv = list(sys.argv[1:] if argv is None else argv)
    mod = COMMANDS.get(argv[0]) if argv else None
    if mod is None:
        print("usage: python -m holon historical " + "|".join(COMMANDS) + " [options]", file=sys.stderr)
        return 2
    return importlib.import_module(f"{__name__}.{mod}").main(argv[1:])
