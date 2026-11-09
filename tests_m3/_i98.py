"""I98's instrument (the contract is the docstring of tests_m3/test_g6_i98.py). It imports nothing from holon/ or
tools/; it runs `python -m holon` only as a subprocess.

    TWO                 the two REFUTED records G6 refuses at the key's base (I97's head 5b1fe820), with the clause
                        that refuses each there.
    PLANTED             {law: report}: one REFUTED record of each of two G6 families, with a passed replay at the base,
                        and the family replay report that binds it.
    plant(tree)         on a copy of a tree: removes each PLANTED law's entry from its report, so no G6 clause can bind
                        it. Returns the planted law ids, sorted.
    gate(tree, checks)  -> (exit code, {check: (passed, detail)}): `python -m holon gate --milestone M3 --checks <checks>
                        --root <tree> --report <tmp>` in that tree.
    final_filter(tree)  -> exit code of `python -m holon refute --milestone M3 --only filter` in that tree.
    status(tree, law)   -> the status of results/M3/<law>.json in that tree, and its bound (None when it has none).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "docs/iterations/I98"
TWO = {"L_sort_tag_rollup_279_e01ea84a": "commitState: not replayed",
       "L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter": "replay failed"}
PLANTED = {"L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash": "replay/M3/fact/report.json",
           "L_sort_realize_rollup_363_4a64383b": "replay/M3/sorts/report.json"}


def _env(tree) -> dict:
    home = os.path.expanduser("~")
    return {**os.environ, "BEND_NO_TELEMETRY": "1",
            "PATH": f"{home}/.holon/bin:{home}/.elan/bin:" + os.environ.get("PATH", ""),
            "PYTHONPATH": str(tree) + os.pathsep + os.environ.get("PYTHONPATH", "")}


def plant(tree) -> list[str]:
    tree = Path(tree)
    done = []
    for law, rel in sorted(PLANTED.items()):
        p = tree / rel
        doc = json.loads(p.read_text(encoding="utf-8"))
        if law in (doc.get("laws") or {}):
            del doc["laws"][law]
            p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            done.append(law)
    return sorted(done)


def gate(tree, checks: str, timeout: int = 7200) -> tuple[int, dict]:
    tree = Path(tree)
    with tempfile.TemporaryDirectory() as tmp:
        rep = Path(tmp) / "gate_report.json"
        p = subprocess.run([sys.executable, "-m", "holon", "gate", "--milestone", "M3", "--checks", checks, "--root",
                            str(tree), "--report", str(rep)], cwd=tree, env=_env(tree), capture_output=True,
                           text=True, timeout=timeout)
        got = json.loads(rep.read_text(encoding="utf-8")) if rep.is_file() else {}
    return p.returncode, {k: (v.get("passed"), v.get("detail")) for k, v in (got.get("checks") or {}).items()}


def final_filter(tree, timeout: int = 7200) -> int:
    tree = Path(tree)
    p = subprocess.run([sys.executable, "-m", "holon", "refute", "--milestone", "M3", "--only", "filter"], cwd=tree,
                       env=_env(tree), capture_output=True, text=True, timeout=timeout)
    return p.returncode


def status(tree, law: str) -> tuple[str | None, str | None]:
    p = Path(tree) / "results" / "M3" / f"{law}.json"
    if not p.is_file():
        return None, None
    r = json.loads(p.read_text(encoding="utf-8"))
    return r.get("status"), r.get("bound") if isinstance(r.get("bound"), str) else None
