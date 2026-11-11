"""`python -m holon target run --target NAME [--jobs N]` (I47): run a target through the factory.

A target whose run.kind is "machine" (targets/<name>/target.json) is a state-machine milestone in all but its location:
its laws live in run.laws, its documents under targets/<name>/, its outputs at run.out and run.gen. The pipeline reads
its laws from <root>/laws/<milestone>/ and resolves paths against the repo root its package sits in
(holon.mpipeline.ROOT), so the run happens in a scratch root that holds a copy of holon/ and config/, the target's
directory, and laws/<run.milestone>/ made from run.laws (with a registry of the facts hash, run with --no-registry as
every test milestone is). Its outputs are written at run.out and run.gen inside the scratch root and copied back to the
same repo-relative paths: every path a record holds is repo-relative, so the records are the ones a run in place would
write. The target's own files are never written. Nothing here names a target.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import targets as T

ROOT = Path(__file__).resolve().parents[1]
RUN_OUTPUTS = ("summary.json", "deps.json", "splits.json")


def _ignore(_d, names):
    return [n for n in names if n in ("__pycache__", "node_modules") or n.endswith(".pyc")]


# What a state-machine run reads under spec/ besides its laws and documents: the ledger (holon.records), the shared
# libraries, and the files the generator closures hash (holon.records.generator_files' globs), so that a record's
# generator_sha256 is the one a run in place would write. Only these are copied (spec/heldout/ is never read).
SPEC_GLOBS = ("spec/ledger/*", "spec/lib/*", "spec/schemas/*", "spec/*/lib/*.lib.json", "spec/*/policy_hints.mjs",
              "spec/*/lib/*.pointwise.json", "spec/*/lib/window_*.json", "spec/*/lib/oracles.json")


def spec_inputs(root: Path) -> list[str]:
    out = set()
    for g in SPEC_GLOBS:
        for f in root.glob(g):
            rel = f.relative_to(root)
            if f.is_file() and rel.parts[1] != "heldout":
                out.add(rel.as_posix())
    return sorted(out)


def scratch_root(t: dict, root: Path) -> Path:
    run = t["run"]
    s = Path(tempfile.mkdtemp(prefix="holon-target-")) / "root"
    s.mkdir(parents=True)
    for d in ("holon", "config"):
        shutil.copytree(root / d, s / d, ignore=_ignore)
    shutil.copytree(root / "targets" / t["name"], s / "targets" / t["name"], ignore=_ignore)
    for rel in spec_inputs(root):
        (s / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, s / rel)
    m = run["milestone"]
    ld = s / "laws" / m
    ld.mkdir(parents=True)
    facts: dict[str, str] = {}
    stmts = {}
    for p in sorted((root / run["laws"]).glob("*.json")):
        law = json.loads(p.read_text())
        if law.get("milestone") != m:
            raise T.TargetError(f"{p}: milestone {law.get('milestone')!r} is not the target's run.milestone {m!r}")
        fp = root / law["facts"]
        if not fp.is_file():
            raise T.TargetError(f"{p}: its facts {law['facts']} do not exist")
        if not (s / law["facts"]).exists():
            (s / law["facts"]).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fp, s / law["facts"])
        facts[law["facts"]] = hashlib.sha256(fp.read_bytes()).hexdigest()
        (ld / p.name).write_bytes(p.read_bytes())
        stmts[law["law_id"]] = None
    if not stmts:
        raise T.TargetError(f"target {t['name']}: no laws in {run['laws']}")
    first = sorted(facts)[0]
    reg = {"milestone": m, "facts": first, "facts_sha256": facts[first], "facts_files": dict(sorted(facts.items())),
           "statements": dict(sorted(stmts.items()))}
    (ld / "REGISTRY.json").write_text(json.dumps(reg, indent=2, sort_keys=True) + "\n")
    return s


def run_target(name: str, root: Path = ROOT, jobs: int = 1, log=print) -> int:
    t = T.load(name, root)
    run = t.get("run")
    if not run or run.get("kind") != "machine":
        raise T.TargetError(f"target {name}: run.kind is {(run or {}).get('kind')!r}; `target run` runs machine targets")
    s = scratch_root(t, root)
    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(s)
        env["HOLON_BUILD_DIR"] = str(s.parent / "build")
        env.pop("HOLON_TRACE", None)
        cmd = [sys.executable, "-m", "holon", "run", "--milestone", run["milestone"], "--no-registry",
               "--out", str(s / run["out"]), "--gen-dir", str(s / run["gen"])]
        if jobs > 1:
            cmd += ["--jobs", str(jobs)]
        p = subprocess.run(cmd, cwd=s, env=env, capture_output=True, text=True)
        log(p.stdout.rstrip())
        if p.returncode != 0:
            print(p.stderr[-4000:], file=sys.stderr)
            return p.returncode
        out, gen = root / run["out"], root / run["gen"]
        out.mkdir(parents=True, exist_ok=True)
        for f in sorted(out.glob("*.json")):   # what a run writes; drift and other reports beside it are kept
            if f.name in RUN_OUTPUTS or f.name.startswith("L"):
                f.unlink()
        for f in sorted((s / run["out"]).iterdir()):
            if f.is_file():
                shutil.copyfile(f, out / f.name)
        shutil.rmtree(gen, ignore_errors=True)
        shutil.copytree(s / run["gen"], gen)
        log(f"target {name}: {run['milestone']} written to {run['out']} and {run['gen']}")
        return 0
    finally:
        shutil.rmtree(s.parent, ignore_errors=True)


def main(argv: list[str]) -> int:
    import argparse
    if argv[:1] and argv[0] in ("extract", "coverage", "diagram", "sizes", "gate"):   # I49: extracted targets
        from . import target_extracted
        return target_extracted.main(argv[0], argv[1:])
    ap = argparse.ArgumentParser(prog="holon target")
    ap.add_argument("command", choices=["run", "list"])
    ap.add_argument("--target")
    ap.add_argument("--root")
    ap.add_argument("--jobs", type=int, default=1)
    a = ap.parse_args(argv)
    root = Path(a.root or ROOT).resolve()
    if a.command == "list":
        for n in T.names(root):
            print(n)
        return 0
    if not a.target:
        ap.error("--target is required")
    try:
        return run_target(a.target, root, a.jobs)
    except T.TargetError as e:
        print(f"holon target: {e}", file=sys.stderr)
        return 2
