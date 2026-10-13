#!/usr/bin/env python3
"""Fetch the on-chain history HOLON replays, for the human to run where RPC is allowed (BUILD_PLAN I23; Q5).

Runs, in order, from the repository root:
  1. python -m holon historical fetch        I59's acquisition: the Rollup's logs of the five topics, their
                                              transactions and receipts, every blob (index: results/M2/historical/
                                              index.json; snapshot outside the repo, ~/.holon/historical)
  2. python -m holon historical fetch-state  I23's supplement: block headers, the proxy's storage at the trans
                                              window's blocks, eth_call answers (and their stability checks), the
                                              implementation's code, the proxy's logs of other topics
                                              (results/M2/historical/supplement.json)
Both resume from the snapshot's state and never refetch what it holds. Historical state needs an archive endpoint:
set ETH_RPC_URL (a keyed archive RPC) in the environment, never on the command line; ETHERSCAN_API_KEY adds the
explorer's logs to step 1. No secret is printed. Without network, tools/historical_bigquery.sql is the BigQuery
alternative for step 1's logs and transactions.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="tools/fetch_historical.py",
        description="Run `holon historical fetch` (I59: logs, transactions, receipts, blobs) and then "
                    "`holon historical fetch-state` (I23: headers, storage, calls, code) for the human, where RPC is "
                    "allowed. Both resume and never refetch what the snapshot holds.")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--snapshot", help="the snapshot directory (default ~/.holon/historical or HOLON_HISTORICAL_DIR)")
    ap.add_argument("--skip-fetch", action="store_true", help="run only fetch-state (the I59 index exists)")
    ap.add_argument("--offline", action="store_true", help="rewrite both indexes from the snapshot state, no network")
    a = ap.parse_args(argv)
    extra = (["--snapshot", a.snapshot] if a.snapshot else []) + (["--offline"] if a.offline else [])
    steps = [] if a.skip_fetch else [["fetch", "--milestone", a.milestone] + extra]
    steps.append(["fetch-state", "--milestone", a.milestone] + extra)
    for s in steps:
        print(f"$ python -m holon historical {' '.join(s)}", flush=True)
        rc = subprocess.run([sys.executable, "-m", "holon", "historical", *s], cwd=ROOT).returncode
        if rc not in (0, 1):
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
