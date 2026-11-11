"""Parallel per-law work with a deterministic merge (I47; whitepaper L20, "parallel checking").

`python -m holon run --milestone M --jobs N` (N > 1) decides the laws of a state-machine milestone in N worker
processes (concurrent.futures.ProcessPoolExecutor). Each worker runs the sequential pipeline itself (`holon run
--laws <shard>`, holon.mpipeline.run_m1, unchanged) in a fresh interpreter, into a shard directory beside the final one;
this module then merges the shards into the directories the sequential run writes, so that the merged tree is the
sequential run's under G1's normalization (every JSON key named "seconds" removed; every other byte equal):

  * laws that the pipeline decides together stay in one shard: a law and its frozen negation (negation_of / negation:
    the ∃-law's record links its negation's), and every law with a hypothesis premise (holon-splits/0.1 pairs them:
    holon.gen.oracles.splits reads their statuses and their oracle sidecars from one run);
  * the shards' paths in what they wrote (the pipeline records repo-relative or absolute paths, holon.mpipeline.relpath)
    are rewritten to the final directories' (a shard directory's name, <final>.shard-<i>, occurs nowhere else);
  * gen/<M>/model and gen/<M>/core are written by every shard and must be byte-identical across shards (else the merge
    fails); every other generated file belongs to exactly one shard;
  * summary.json is the union of the shards' (each law in one shard), deps.json the union of their dependents
    (holon.bindings.dependents is a union over laws), splits.json the shard's that holds every hypothesis law (or, when
    no law has one, any shard's: they are equal).

The pipeline itself is not edited (its bytes are in every committed record's generator_sha256). Milestones M0 (its
pipeline decides all laws in one call) and the typed milestones (holon.sorts.run3) are refused with --jobs > 1.
Deterministic: shard assignment, merge order and output bytes depend on the law ids only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def groups(laws: list[dict]) -> list[list[str]]:
    """Law ids in groups that must be decided in one run, sorted (each group sorted, groups by first id)."""
    from .gen import oracles as O
    parent = {l["law_id"]: l["law_id"] for l in laws}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        if a in parent and b in parent:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    hyp = sorted(l["law_id"] for l in laws if O.hyp_names(l))
    for x in hyp[1:]:
        union(hyp[0], x)
    for l in laws:
        for k in ("negation_of", "negation"):
            if isinstance(l.get(k), str):
                union(l["law_id"], l[k])
    out: dict[str, list[str]] = {}
    for lid in sorted(parent):
        out.setdefault(find(lid), []).append(lid)
    return sorted(out.values(), key=lambda g: g[0])


def shards(gs: list[list[str]], jobs: int) -> list[list[str]]:
    """Greedy balance by law count (largest group first, ties by first id), each shard's ids sorted; empty shards
    dropped."""
    bins: list[list[str]] = [[] for _ in range(max(1, jobs))]
    for g in sorted(gs, key=lambda g: (-len(g), g[0])):
        i = min(range(len(bins)), key=lambda k: (len(bins[k]), k))
        bins[i] += g
    return [sorted(b) for b in bins if b]


def _worker(job: tuple) -> tuple[int, int, str]:
    """Run one shard: `python -m holon run ... --laws <ids> --out <out> --gen-dir <gen>` in a fresh interpreter."""
    i, argv, ids, out, gen, build, cwd = job
    env = dict(os.environ)
    env["HOLON_BUILD_DIR"] = build
    env.pop("HOLON_TRACE", None)
    cmd = [sys.executable, "-m", "holon", *argv, "--laws", ",".join(ids), "--out", out, "--gen-dir", gen]
    p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    return i, p.returncode, (p.stdout + p.stderr)


def _strip(argv: list[str], names: tuple[str, ...]) -> tuple[list[str], dict]:
    out, vals, i = [], {}, 0
    while i < len(argv):
        x = argv[i]
        hit = next((n for n in names if x == n or x.startswith(n + "=")), None)
        if hit is None:
            out.append(x)
            i += 1
        elif x == hit:
            vals[hit] = argv[i + 1] if i + 1 < len(argv) else None
            i += 2
        else:
            vals[hit] = x.split("=", 1)[1]
            i += 1
    return out, vals


def _relstr(p: Path) -> str:
    from .mpipeline import relpath
    return relpath(p)


def _copy_rewrite(src: Path, dst: Path, subs: list[tuple[bytes, bytes]], seen: dict[str, bytes]) -> list[str]:
    """Copy every file under src to dst with subs applied to its bytes; a file another shard already wrote must be
    byte-identical (problems otherwise)."""
    probs = []
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src).as_posix()
        b = f.read_bytes()
        for a, z in subs:
            b = b.replace(a, z)
        if rel in seen:
            if seen[rel] != b:
                probs.append(f"{rel}: shards wrote different bytes")
            continue
        seen[rel] = b
        t = dst / rel
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_bytes(b)
    return probs


def run(argv: list[str]) -> int:
    """`holon run --milestone M --jobs N [...]`; argv starts with "run"."""
    from . import ir
    from .bindings import dump
    from .mpipeline import clean_gen
    rest, vals = _strip(argv[1:], ("--jobs", "--out", "--gen-dir", "--laws"))
    jobs = int(vals.get("--jobs") or 1)
    m = None
    for i, x in enumerate(rest):
        if x == "--milestone" and i + 1 < len(rest):
            m = rest[i + 1]
        elif x.startswith("--milestone="):
            m = x.split("=", 1)[1]
    if m is None:
        print("holon run --jobs: --milestone is required", file=sys.stderr)
        return 2
    from .sorts.typed_sidecar import typed
    if typed(m) and m.startswith("M"):
        print(f"holon run --jobs: {m} is a typed milestone (holon.sorts.run3); run it without --jobs", file=sys.stderr)
        return 2
    if m == "M0":
        print("holon run --jobs: M0's pipeline decides its laws in one call; run it without --jobs", file=sys.stderr)
        return 2
    out = Path(vals.get("--out") or ROOT / "results" / m).resolve()
    gen = Path(vals.get("--gen-dir") or ROOT / "gen" / m).resolve()
    laws = ir.load_laws_any(m, ROOT)
    only = [x.strip() for x in (vals.get("--laws") or "").split(",") if x.strip()] or None
    if only is not None:
        laws = [l for l in laws if l["law_id"] in set(only)]
    parts = shards(groups(laws), jobs)
    work = Path(tempfile.mkdtemp(prefix="holon-par-"))
    sdirs = []
    try:
        jobs_ = []
        for i, ids in enumerate(parts):
            so, sg = out.parent / f"{out.name}.shard-{i}", gen.parent / f"{gen.name}.shard-{i}"
            for d in (so, sg):
                shutil.rmtree(d, ignore_errors=True)
            sdirs += [so, sg]
            jobs_.append((i, ["run", *rest], ids, str(so), str(sg), str(work / f"build-{i}"), str(Path.cwd())))
        with ProcessPoolExecutor(max_workers=max(1, min(jobs, len(jobs_)))) as ex:
            res = sorted(ex.map(_worker, jobs_))
        for i, code, text in res:
            print(f"holon run --jobs: shard {i} ({len(parts[i])} laws) exit {code}")
            if code != 0:
                print(text[-4000:], file=sys.stderr)
                return code
        # merge
        if only is None:
            clean_gen(gen)
        else:
            clean_gen(gen, only)
        out.mkdir(parents=True, exist_ok=True)
        seen: dict[str, bytes] = {}
        probs: list[str] = []
        summary, flat, by_model, splits = {}, {}, {}, []
        for i, _ids in enumerate(parts):
            so, sg = out.parent / f"{out.name}.shard-{i}", gen.parent / f"{gen.name}.shard-{i}"
            subs = [(_relstr(sg).encode(), _relstr(gen).encode()), (_relstr(so).encode(), _relstr(out).encode()),
                    (str(sg).encode(), str(gen).encode()), (str(so).encode(), str(out).encode())]
            probs += _copy_rewrite(sg, gen, subs, seen)
            for f in sorted(so.iterdir()):
                b = f.read_bytes()
                for a, z in subs:
                    b = b.replace(a, z)
                if f.name == "summary.json":
                    summary.update(json.loads(b))
                elif f.name == "deps.json":
                    d = json.loads(b)
                    for k, ls in d.get("dependents", {}).items():
                        flat.setdefault(k, set()).update(ls)
                    for mdl, ds in d.get("dependents_by_model", {}).items():
                        for k, ls in ds.items():
                            by_model.setdefault(mdl, {}).setdefault(k, set()).update(ls)
                elif f.name == "splits.json":
                    splits.append((i, b))
                elif f.is_file():
                    if (out / f.name).exists() and f.name in seen:
                        probs.append(f"{f.name}: written by two shards")
                    seen[f.name] = b
                    (out / f.name).write_bytes(b)
        if probs:
            print("holon run --jobs: the shards do not merge: " + "; ".join(probs[:10]), file=sys.stderr)
            return 1
        (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        (out / "deps.json").write_text(dump({"milestone": m,
                                             "dependents": {k: sorted(v) for k, v in sorted(flat.items())},
                                             "dependents_by_model": {mdl: {k: sorted(v) for k, v in sorted(ds.items())}
                                                                     for mdl, ds in sorted(by_model.items())}}))
        if splits:
            from .gen import oracles as O
            hyp = {l["law_id"] for l in laws if O.hyp_names(l)}
            pick = next((b for i, b in splits if hyp and hyp <= set(parts[i])), None)
            if pick is None:
                if hyp or len({b for _, b in splits}) != 1:
                    print("holon run --jobs: splits.json cannot be merged", file=sys.stderr)
                    return 1
                pick = splits[0][1]
            (out / "splits.json").write_bytes(pick)
        print(f"holon run --jobs {jobs}: {len(summary)} laws in {len(parts)} shards merged into {_relstr(out)}")
        return 0
    finally:
        for d in sdirs:
            shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
