"""Historical on-chain acquisition and the first per-edge replay on real inputs (I59, the I23a track; human answer
Q5 in docs/HUMAN_ANSWERS.md: on-chain replay is make or break). The frozen instrument is
spec/M2/lib/historical.json; the contract is the docstring of tests_m2/test_historical.py.

    python -m holon historical fetch  [--milestone M2] [--from N] [--to M] [--index PATH] [--snapshot DIR]
    python -m holon historical replay [--milestone M2] [--index PATH] [--out PATH]

Modules:
    net      HTTP: per-host pacing, retries with backoff, JSON-RPC; hosts only in outputs, secrets scrubbed
    store    the content-addressed snapshot outside the repo and the resumable fetch state
    fetch    logs, transactions, blobs, receipts; the index
    abi      the pinned ABI of the commit functions, and the selectors of every signature in the pinned
             checkout's history of IRollup.sol (to name a function, never to decode it)
    checks   header_checks: the per-header checks on the frozen M0 model, without the chain
    replay   the replay, the Go decoder run and the disagreements
"""
from __future__ import annotations

import sys

from .checks import header_checks  # noqa: F401


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["fetch"]:
        from . import fetch
        return fetch.main(argv[1:])
    if argv[:1] == ["replay"]:
        from . import replay
        return replay.main(argv[1:])
    print("usage: python -m holon historical fetch|replay [options]", file=sys.stderr)
    return 2
