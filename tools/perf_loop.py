#!/usr/bin/env python3
"""The performance loop with veto (whitepaper §9.2(7); I47).

    python tools/perf_loop.py (--target NAME | --milestone M) --candidate DIR [--min-gain X] [--jobs N] [--apply]

A proposer changes generators, proof strategies or model encodings to cut check time. A candidate is a directory of
files that replace (or add) repo files at the same relative paths. The loop:

1. builds two fresh trees, the baseline (the working tree as it is) and the candidate (the same with DIR overlaid);
2. runs the check in each and times it:
   --target NAME   `holon target run --target NAME` (the target's run.out and run.gen are its outputs);
   --milestone M   `holon gate --milestone M --root <tree>` (G1 regenerates every output and compares it with the
                   committed one; G4's canaries, G5's from-scratch checks, G6's replay and every other check run);
3. vetoes the candidate unless every output is the baseline's under G1's normalization (JSON keys named "seconds"
   removed, every other byte equal: so every law, proof and counter-law is unchanged) and, for a milestone, the gate
   passes with the baseline's verdict per check;
4. keeps a surviving candidate only when it is at least --min-gain (default 0.05) faster than the baseline, else
   reports "no_gain".

The working tree changes only with --apply and only for "kept": the candidate's files are then copied into it. One JSON
object is printed: verdict (kept, no_gain, vetoed), failed (what vetoed it), baseline_s, candidate_s, gain, files.
The budget the loop serves is the per-file check budget, config bend.budget_s_per_file (bend-ssz used two minutes);
the gate's G5 enforces it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", "node_modules", "build"}


def _strip_seconds(x):
    if isinstance(x, dict):
        return {k: _strip_seconds(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_strip_seconds(v) for v in x]
    return x


def normalized(d: Path) -> dict[str, str]:
    out = {}
    if not d.is_dir():
        return out
    for f in sorted(d.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        b = f.read_bytes()
        if f.suffix == ".json":
            try:
                b = json.dumps(_strip_seconds(json.loads(b)), sort_keys=True, separators=(",", ":")).encode()
            except ValueError:
                pass
        out[f.relative_to(d).as_posix()] = hashlib.sha256(b).hexdigest()
    return out


def tree(dst: Path, parts: list[str] | None) -> Path:
    def ignore(_d, names):
        return [n for n in names if n in SKIP or n.endswith(".pyc")]
    dst.mkdir(parents=True)
    for p in sorted(ROOT.iterdir()) if parts is None else [ROOT / x for x in parts]:
        if p.name in SKIP or not p.exists():
            continue
        rel = p.relative_to(ROOT)
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        if p.is_dir():
            shutil.copytree(p, dst / rel, ignore=ignore, symlinks=True)
        else:
            shutil.copy2(p, dst / rel)
    return dst


def overlay(dst: Path, cand: Path) -> list[str]:
    files = []
    for f in sorted(cand.rglob("*")):
        if f.is_file():
            rel = f.relative_to(cand).as_posix()
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, dst / rel)
            files.append(rel)
    return files


def holon(args: list[str], cwd: Path) -> tuple[subprocess.CompletedProcess, float]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(cwd)
    env["BEND_NO_TELEMETRY"] = "1"
    t0 = time.monotonic()
    p = subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, env=env, capture_output=True, text=True)
    return p, time.monotonic() - t0


def measure(kind: str, name: str, t: Path, jobs: int) -> dict:
    if kind == "target":
        spec = json.loads((t / "targets" / name / "target.json").read_text())
        p, s = holon(["target", "run", "--target", name] + (["--jobs", str(jobs)] if jobs > 1 else []), t)
        outs = {k: normalized(t / spec["run"][k]) for k in ("out", "gen")}
        return {"code": p.returncode, "seconds": s, "outputs": outs, "log": (p.stdout + p.stderr)[-2000:]}
    rep = t.parent / "gate.json"
    p, s = holon(["gate", "--milestone", name, "--root", str(t), "--report", str(rep)]
                 + (["--jobs", str(jobs)] if jobs > 1 else []), t)
    r = json.loads(rep.read_text()) if rep.is_file() else {}
    return {"code": p.returncode, "seconds": s, "verdicts": {g: c["passed"] for g, c in (r.get("checks") or {}).items()},
            "passed": bool(r.get("passed")), "log": p.stdout[-2000:]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--target")
    g.add_argument("--milestone")
    ap.add_argument("--candidate", required=True)
    ap.add_argument("--min-gain", type=float, default=0.05)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    kind, name = ("target", a.target) if a.target else ("milestone", a.milestone)
    cand = Path(a.candidate).resolve()
    if not cand.is_dir():
        ap.error(f"{cand} is not a directory")
    # a target's run needs only these; a gate needs the whole tree
    if kind == "target":   # what a target's run reads (holon.target_run: holon/, config/, targets/, its spec inputs)
        sys.path.insert(0, str(ROOT))
        from holon.target_run import spec_inputs
        parts = ["holon", "config", "targets", "results/targets", "gen/targets"] + spec_inputs(ROOT)
    else:
        parts = None
    work = Path(tempfile.mkdtemp(prefix="holon-perf-"))
    try:
        base = measure(kind, name, tree(work / "base" / "root", parts), a.jobs)
        ct = tree(work / "cand" / "root", parts)
        files = overlay(ct, cand)
        new = measure(kind, name, ct, a.jobs)
        failed = []
        if base["code"] != 0:
            failed.append(f"the baseline itself fails (exit {base['code']}): {base['log'][-300:]}")
        if new["code"] != 0:
            failed.append(f"the candidate's check exits {new['code']}")
        if kind == "target":
            for k in ("out", "gen"):
                x, y = base["outputs"][k], new["outputs"][k]
                diff = sorted(f for f in set(x) | set(y) if x.get(f) != y.get(f))
                if diff:
                    failed.append(f"run.{k} differs from the baseline: {diff[:10]}")
        else:
            if not new["passed"]:
                failed.append("the gate fails: " + ", ".join(sorted(gc for gc, ok in new["verdicts"].items() if not ok)))
            if new["verdicts"] != base["verdicts"]:
                failed.append("a check's verdict differs from the baseline's")
        gain = (base["seconds"] - new["seconds"]) / base["seconds"] if base["seconds"] > 0 else 0.0
        verdict = "vetoed" if failed else ("kept" if gain >= a.min_gain else "no_gain")
        if verdict == "kept" and a.apply:
            overlay(ROOT, cand)
        print(json.dumps({"verdict": verdict, "failed": failed, "baseline_s": round(base["seconds"], 3),
                          "candidate_s": round(new["seconds"], 3), "gain": round(gain, 4), "files": files,
                          "applied": verdict == "kept" and a.apply, "check": kind, "name": name}, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
