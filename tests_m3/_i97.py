"""I97's instrument (the contract is the docstring of tests_m3/test_bendtt_i97.py). It imports nothing from holon/ or
tools/; it runs `python -m holon` and `bend` only as subprocesses.

    SIX                the six decided REFUTED records of round 3's F-M3-13 (audit round 3, a7_g7_six.json at ea2118c7).
    forge(tree)        round 3's tamper (a7_forge.py at ea2118c7), applied to a copy of a tree: every decided M3 record
                       whose bendtt entry is not "checked" is made to claim it (kernels[bendtt].result checked,
                       independence_class I1-shared, kernel.verdict checked, checker.bendtt exit 0 and ALL PROOFS
                       CHECK). Returns the forged law ids, sorted.
    gate(tree, checks) -> (exit code, {check: (passed, detail)}): `python -m holon gate --milestone M3 --checks <checks>
                       --root <tree> --report <tmp>` in that tree.
    bend_pair(dir)     -> (bend2 accepts, BendTT accepts) for dir/PROOF.bend: `bend PROOF.bend` and `bend PROOF.bend
                       --verdict`, each judged by its ALL PROOFS CHECK line and exit code.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "docs/iterations/I97"
REGISTRY = "spec/M3/lib/bendtt_constructs.json"
SIX = ("L_par_gobr_BatchData_EstimateCompressedSizeWithNewPayload_p0_p3",
       "L_par_gobr_BatchData_WillExceedCompressedSizeLimit_p4_p7",
       "L_sym_sentinel_inv_L1MessageQueueWithGasPriceOracle_messageEnqueueTime_getFirstUnfinalizedMessageEnqueueTime",
       "L_sym_tau_L1CrossDomainMessenger_replayMessage",
       "L_sym_tau_L1MessageQueueWithGasPriceOracle_getFirstUnfinalizedMessageEnqueueTime",
       "L_sym_tau_L1MessageQueueWithGasPriceOracle_getMessageEnqueueTimestamp")


def _env() -> dict:
    home = os.path.expanduser("~")
    return {**os.environ, "BEND_NO_TELEMETRY": "1",
            "PATH": f"{home}/.holon/bin:{home}/.elan/bin:" + os.environ.get("PATH", "")}


def forge(tree) -> list[str]:
    changed = []
    for f in sorted((Path(tree) / "results" / "M3").glob("L*.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        ks = {k["name"]: k for k in r.get("kernels") or []}
        bt = ks.get("bendtt")
        if r.get("status") in ("PROVED", "REFUTED") and bt is not None and bt.get("result") != "checked":
            bt["result"] = "checked"
            bt.pop("reason", None)
            r["independence_class"] = "I1-shared"
            if isinstance(r.get("kernel"), dict):
                r["kernel"]["verdict"] = "checked"
            c = (r.get("checker") or {}).get("bendtt")
            if isinstance(c, dict):
                c["exit_code"] = 0
                c["output_tail"] = "ALL PROOFS CHECK\n"
            for a in r.get("attempts") or []:
                c = (a.get("checker") or {}).get("bendtt") if isinstance(a.get("checker"), dict) else None
                if isinstance(c, dict):
                    c["exit_code"] = 0
                    c["output_tail"] = "ALL PROOFS CHECK\n"
            f.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            changed.append(f.stem)
    return sorted(changed)


def gate(tree, checks: str, timeout: int = 7200) -> tuple[int, dict]:
    tree = Path(tree)
    with tempfile.TemporaryDirectory() as tmp:
        rep = Path(tmp) / "gate_report.json"
        env = {**_env(), "PYTHONPATH": str(tree) + os.pathsep + os.environ.get("PYTHONPATH", "")}
        p = subprocess.run([sys.executable, "-m", "holon", "gate", "--milestone", "M3", "--checks", checks, "--root",
                            str(tree), "--report", str(rep)], cwd=tree, env=env, capture_output=True, text=True,
                           timeout=timeout)
        got = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
    return p.returncode, {k: (v.get("passed"), v.get("detail")) for k, v in (got.get("checks") or {}).items()}


def bend_pair(d) -> tuple[bool, bool]:
    d = Path(d)
    out = []
    for extra in ([], ["--verdict"]):
        p = subprocess.run(["bend", "PROOF.bend", *extra], cwd=d, env=_env(), capture_output=True, text=True,
                           timeout=1800)
        out.append(p.returncode == 0 and "ALL PROOFS CHECK" in (p.stdout + p.stderr))
    return out[0], out[1]
