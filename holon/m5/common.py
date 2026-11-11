"""Shared measure helpers (definitions.common): proportions with Wilson intervals, labels, threshold verdicts."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIN_N = 5
CHECKED = "ALL PROOFS CHECK"
Z = 1.96


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def proportion(k: int, n: int) -> dict:
    if not n:
        return {"numerator": k, "denominator": n, "value": None, "wilson95": None}
    p = k / n
    denom = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / denom
    return {"numerator": k, "denominator": n, "value": round(p, 6),
            "wilson95": [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]}


def size_label(n: int) -> str:
    if n <= 0:
        return "not_measured"
    return "insufficient_n" if n < MIN_N else "measured"


def verdict(value, op: str, target, lab: str) -> str:
    """meets/misses for a measured measure; its label otherwise (never meets)."""
    if lab != "measured":
        return lab
    if op == ">=":
        ok = value >= target
    elif op == ">":
        ok = value > target
    elif op == "==":
        ok = value == target
    else:
        raise ValueError(op)
    return "meets" if ok else "misses"


def overall(thresholds: dict) -> str:
    vals = list(thresholds.values())
    if vals and set(vals) == {"meets"}:
        return "meets"
    if "misses" in vals:
        return "misses"
    return "not_judged"


def checked(evidence) -> bool:
    """common.outcome_vocabulary: the checker accepted a file in which the law is present."""
    return isinstance(evidence, dict) and evidence.get("marker") == CHECKED and evidence.get("law_present") is True


def git_blobs(cwd: Path, commit: str, paths: list[str]) -> dict:
    """{path: bytes or None} at a commit, read-only (`git cat-file --batch`)."""
    if not paths:
        return {}
    req = "".join(f"{commit}:{p}\n" for p in paths).encode()
    raw = subprocess.run(["git", "cat-file", "--batch"], cwd=cwd, input=req, capture_output=True, check=True).stdout
    out, pos = {}, 0
    for p in paths:
        end = raw.index(b"\n", pos)
        header = raw[pos:end].split()
        if header[-1] == b"missing":
            out[p] = None
            pos = end + 1
            continue
        n = int(header[2])
        out[p] = raw[end + 1:end + 1 + n]
        pos = end + 1 + n + 1
    return out


def git_list(cwd: Path, commit: str, prefix: str) -> list[str]:
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit, "--", prefix], cwd=cwd, capture_output=True,
                       check=True, text=True)
    return sorted(x for x in r.stdout.splitlines() if x)
