"""I99's instrument (the contract is the docstring of tests_m3/test_g9_i99.py). It imports nothing from holon/ or
tools/; it runs `python -m holon` only as a subprocess.

    THIRTEEN              the 13 M3 records audit M3/5 F-M3-19 names: premises [] while their laws assume clauses,
                          {law: the number of its assume clauses}.
    PLANTED_EMPTY         a PROVED M3 record whose law has 12 assume clauses (the finding's own scratch case), judged by
                          holon/gate.py's G9 over M3's other laws.
    PLANTED_MISSING       a PROVED M3 record whose law has 4 assume clauses, judged by the contract laws' G9.
    copy(tree, dst)       a copy of a tree without .git, cache, build and node_modules; returns the copy's root.
    plant_empty(tree)     sets PLANTED_EMPTY's premises to []; returns the law id.
    plant_missing(tree)   drops the last of PLANTED_MISSING's premises; returns the law id.
    clauses(tree, m, law) the number of assume clauses of laws/<m>/<law>.json in that tree.
    gate(tree, m, checks) -> (exit code, {check: (passed, detail)}): `python -m holon gate --milestone <m> --checks
                          <checks> --root <tree> --report <tmp>` in that tree.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "docs/iterations/I99"
SKIP = {".git", "cache", "build", "node_modules"}
THIRTEEN = {
    "L_contract_C_o12_m3": 4,
    "L_par_push_L1CrossDomainMessenger_proveAndRelayMessage_154": 2,
    "L_sort_cons_L1CrossDomainMessenger_receive": 1,
    "L_sort_cons_L1CrossDomainMessenger_replayMessage": 1,
    "L_sort_cons_L1CrossDomainMessenger_sendMessage_5f7b1577": 1,
    "L_sort_cons_L1CrossDomainMessenger_sendMessage_b2267a7b": 1,
    "L_sort_cons_Rollup_challengeState": 1,
    "L_sort_cons_Rollup_commitBatch": 1,
    "L_sort_cons_Rollup_receive": 1,
    "L_sort_cons_Submitter_stake": 1,
    "L_sort_payer_L1CrossDomainMessenger_replayMessage_201": 1,
    "L_sort_payer_L1CrossDomainMessenger_sendMessage_5f7b1577_291": 1,
    "L_sort_payer_L1CrossDomainMessenger_sendMessage_b2267a7b_291": 1,
}
PLANTED_EMPTY = "L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned"
PLANTED_MISSING = "L_contract_C_o12_m3"


def _env(tree) -> dict:
    home = os.path.expanduser("~")
    return {**os.environ, "BEND_NO_TELEMETRY": "1",
            "PATH": f"{home}/.holon/bin:{home}/.elan/bin:" + os.environ.get("PATH", ""),
            "PYTHONPATH": str(tree) + os.pathsep + os.environ.get("PYTHONPATH", "")}


def copy(tree, dst) -> Path:
    tree, dst = Path(tree), Path(dst)
    shutil.copytree(tree, dst, ignore=lambda d, names: [n for n in names if Path(d) == tree and n in SKIP])
    return dst


def _edit(tree, law: str, fn) -> str:
    p = Path(tree) / "results" / "M3" / f"{law}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["premises"] = fn(list(rec.get("premises") or []))
    p.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return law


def plant_empty(tree) -> str:
    return _edit(tree, PLANTED_EMPTY, lambda pr: [])


def plant_missing(tree) -> str:
    return _edit(tree, PLANTED_MISSING, lambda pr: pr[:-1])


def clauses(tree, m: str, law: str) -> int:
    d = json.loads((Path(tree) / "laws" / m / f"{law}.json").read_text(encoding="utf-8"))
    return len((d.get("statement") or {}).get("assume") or [])


def gate(tree, m: str, checks: str, timeout: int = 7200) -> tuple[int, dict]:
    tree = Path(tree)
    with tempfile.TemporaryDirectory() as tmp:
        rep = Path(tmp) / "gate_report.json"
        p = subprocess.run([sys.executable, "-m", "holon", "gate", "--milestone", m, "--checks", checks, "--root",
                            str(tree), "--report", str(rep)], cwd=tree, env=_env(tree), capture_output=True,
                           text=True, timeout=timeout)
        got = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
    return p.returncode, {k: (v.get("passed"), v.get("detail")) for k, v in (got.get("checks") or {}).items()}
