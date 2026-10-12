"""R9 restatements (lead-authored, preregistered before any run).
R9 made the MVRV model revert on calls to address 0, which is faithful to the pinned contract
(native control ctrlC_uninit_updateVerifier). Nine closed router laws then flipped to REFUTED,
because their traces start from s0 without `initialize` (rollup == 0). Those laws stay as they are,
REFUTED and triaged "setup-order artefact". This file states the property each one was written for
on an initialised router: the same statement with `initialize(who=1 owner, r=5)` prepended to every
trace rooted at s0 (`run` from s0, or runs_ok(trace, s0)). Predictions are the originals' (unchanged intent, deployed MVRV is initialised).
    python3 spec/M3/laws_src/r9_init_laws.py  ->  laws/M3_router/L_init_*.json
"""
import copy, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ["L_cov_rt_vap_registered", "L_rt_finalized_start", "L_rt_latest", "L_rt_latest2", "L_rt_legacy",
       "L_rt_same_start_replaces", "L_setup_rt_latest", "L_setup_rt_legacy", "L_setup_rt_same_start_replaces"]
INIT = {"act": "initialize", "args": {"who": {"nat": 1}, "r": {"nat": 5}}}


def prefix(x, n):
    if isinstance(x, dict):
        if x.get("from") == {"s0": {}} and isinstance(x.get("run"), dict) and "trace" in x["run"]:
            x["run"]["trace"] = [copy.deepcopy(INIT)] + x["run"]["trace"]
            n[0] += 1
        a = x.get("args")
        if x.get("fn") == "runs_ok" and isinstance(a, list) and len(a) == 2 and a[1] == {"s0": {}} and "trace" in a[0]:
            a[0]["trace"] = [copy.deepcopy(INIT)] + a[0]["trace"]
            n[0] += 1
        for v in x.values():
            prefix(v, n)
    elif isinstance(x, list):
        for v in x:
            prefix(v, n)


def main():
    d = ROOT / "laws" / "M3_router"
    for lid in SRC:
        old = json.loads((d / f"{lid}.json").read_text())
        new = copy.deepcopy(old)
        n = [0]
        prefix(new["statement"], n)
        assert n[0] >= 1, lid
        new["law_id"] = "L_init_" + lid[2:]
        new["notes"] = f"R9 restatement of {lid} on an initialised router ({n[0]} s0 trace(s) prefixed with initialize); {old.get('notes', '')}"
        (d / f"{new['law_id']}.json").write_text(json.dumps(new, indent=1, sort_keys=True) + "\n")
        print(new["law_id"], new["predicted"], n[0])


if __name__ == "__main__":
    main()
