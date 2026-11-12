"""I110 (a): where the sort pass's time goes, per document and per phase (results/M6/I110/sort_profile.json).

  python tools/i110_sort_profile.py [--base-tree DIR] [--out PATH]

Every document is sorted alone (holon.sorts.assign.run_pass over [doc], under its own run's typed sidecar with the
protocol's sort budget), with each phase timed and metered (holon.sorts.budget work units):
  walk         holon.sorts.extracted.walk
  constraints  holon.sorts.extracted.build
  number       holon.sorts.constraints.number
  conflicts    holon.sorts.assign.find_conflicts (and the System of the active set)
  sites        holon.sorts.extracted.build_sites
  unions       holon.sorts.unions.union_entries
  (assign: the rest of Model.solve)
The documents: Morph's transitions document (spec/M2/facts/morph_rollup.extracted.json, under spec/M3/lib's sidecar
settings with seeds 0.2 and the protocol's sort types version), every transitions document of the composed corpus run
(results/M6/I110/holon/<id>/facts, each under its entry's generated typed sidecar), and two planted documents generated
here (a contract of nested internal calls, depths 6 and 10, four actions; solc 0.8.24), whose whole `holon sorts` wall
clock is also taken at --base-tree (I109's head, before this key's speedups) and here, with the outputs compared.
Seconds are measurements (they vary by machine); work units and outputs are deterministic. Outside holon/: it only
calls the pass. Planted documents live in a scratch directory and are not committed (45 MB).
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
sys.path.insert(0, str(ROOT))
PROTO = ROOT / "spec" / "M6" / "lib" / "i110_run.json"
ENV = {**os.environ, "BEND_NO_TELEMETRY": "1"}


def planted_source(depth: int, actions: int) -> str:
    L = ["// SPDX-License-Identifier: UNLICENSED",
         "// I110 planted document: f_k(x) = f_{k-1}(x) + f_{k-1}(x + k), inlined, so each action's write term has",
         "// about 2^depth nodes", "pragma solidity 0.8.24;", "", "contract Deep {"]
    L += [f"    uint256 public s{i};" for i in range(actions)]
    L.append("    function f0(uint256 x) internal pure returns (uint256) { return x + 1; }")
    for k in range(1, depth + 1):
        L.append(f"    function f{k}(uint256 x) internal pure returns (uint256) {{ return f{k - 1}(x) + f{k - 1}(x + {k}); }}")
    for i in range(actions):
        L.append(f"    function a{i}(uint256 x, uint256 y) external {{ if (x > y) {{ s{i} = f{depth}(x) - s{i}; }} "
                 f"else {{ s{(i + 1) % actions} = y - x; }} }}")
    L.append("}")
    return "\n".join(L) + "\n"


def planted(tmp: Path, depth: int, actions: int) -> Path:
    d = tmp / f"deep_d{depth}_a{actions}"
    (d / "src").mkdir(parents=True)
    (d / "src" / "Deep.sol").write_text(planted_source(depth, actions))
    e = {**ENV, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for a in (["init", "-q"], ["add", "."], ["commit", "-qm", "planted"]):
        subprocess.run(["git", "-C", str(d / "src"), *a], check=True, capture_output=True, env=e)
    head = subprocess.run(["git", "-C", str(d / "src"), "rev-parse", "HEAD"], check=True, capture_output=True,
                          text=True).stdout.strip()
    side = {"sidecar_version": 1, "frontend": "solidity", "doc": "I110 planted document",
            "target": {"repo": "holon/i110", "commit": head, "scope": "contract Deep"},
            "output": "tests_m6/fixtures/i110/deep.extracted.json", "sources": ["Deep.sol"],
            "compiler": {"version": "0.8.24", "settings": {"optimizer": {"enabled": False}}},
            "transitions": {"commit_interfaces": [], "contract": "Deep", "term_budget": 4000000}}
    (d / "side.json").write_text(json.dumps(side))
    subprocess.run([sys.executable, "-m", "holon", "extract", "solidity", "--root", str(ROOT), "--sidecar",
                    str(d / "side.json"), "--source", str(d / "src"), "--out", str(d / "deep.extracted.json")],
                   cwd=ROOT, env=ENV, check=True, capture_output=True, timeout=3600)
    (d / "spec" / "M3" / "lib").mkdir(parents=True)
    shutil.copy(ROOT / "spec" / "M3" / "lib" / "sort_seeds.json", d / "spec" / "M3" / "lib" / "sort_seeds.json")
    return d


def profile_one(doc: Path, root: Path, sidecar: dict, budget: int) -> dict:
    """run_pass over [doc] with every phase timed and metered."""
    from holon.sorts import assign as A
    from holon.sorts import budget as B
    from holon.sorts import constraints as C
    from holon.sorts import extracted as X
    from holon.sorts import unions as U
    phases: dict = {}

    def timed(name, fn):
        def w(*a, **k):
            m = B._CURRENT
            u0, t0 = (m.used if m else 0), time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                p = phases.setdefault(name, {"seconds": 0.0, "work": 0})
                p["seconds"] += time.perf_counter() - t0
                p["work"] += (B._CURRENT.used if B._CURRENT else (m.used if m else 0)) - u0
        return w
    saved = [(X, "walk"), (X, "build"), (C, "number"), (A, "find_conflicts"), (X, "build_sites"),
             (U, "union_entries")]
    orig = [getattr(mod, n) for mod, n in saved]
    names = ["walk", "constraints", "number", "conflicts", "sites", "unions"]
    sc = dict(sidecar, documents=[doc.relative_to(root).as_posix()], sort_budget=budget)
    tmp = Path(tempfile.mkdtemp(prefix="holon-i110-prof-", dir=root))
    try:
        sp = tmp / "st.json"
        sp.write_text(json.dumps(sc))
        for (mod, n), nm, f in zip(saved, names, orig):
            setattr(mod, n, timed(nm, f))
        t0 = time.perf_counter()
        out = A.run_pass([doc], root, "T510", seeds_path=root / sc["seeds"], sidecar_path=sp)
        total = time.perf_counter() - t0
    finally:
        for (mod, n), f in zip(saved, orig):
            setattr(mod, n, f)
        shutil.rmtree(tmp, ignore_errors=True)
    (b,) = out["budget"]["documents"]
    return {"facts_sha256": hashlib.sha256(doc.read_bytes()).hexdigest(), "bytes": doc.stat().st_size,
            "work": b["work"], "status": b["status"], "seconds": round(total, 3),
            "phases": {k: {"seconds": round(v["seconds"], 3), "work": v["work"]} for k, v in sorted(phases.items())}}


def wall(tree: Path, d: Path, sidecar: str, out: Path) -> float:
    t0 = time.perf_counter()
    subprocess.run([sys.executable, "-m", "holon", "sorts", "--milestone", "T510", "--root", str(d), "--sidecar",
                    sidecar, "--out", str(out)], cwd=tree, env=ENV, check=True, capture_output=True, timeout=3600)
    return round(time.perf_counter() - t0, 3)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-tree", help="a checkout of the base (I109's head) for the planted wall clock")
    ap.add_argument("--out", default=str(ROOT / "results" / "M6" / "I110" / "sort_profile.json"))
    a = ap.parse_args(argv)
    proto = json.loads(PROTO.read_text())
    tier = proto["typed"]["sort_budget"]
    docs = []
    # Morph's transitions document under the protocol's typed settings (seeds 0.2)
    base_sc = {"sort_types_version": proto["typed"]["sort_types_version"], "seeds": proto["typed"]["seeds"],
               "binding": None, "search": proto["typed"]["search"], "doc": "I110 profile"}
    m = ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json"
    docs.append({"facts": m.relative_to(ROOT).as_posix(), "source": "morph", **profile_one(m, ROOT, base_sc, tier)})
    # every transitions document the composed corpus run sorted
    out_dir = ROOT / proto["out"]
    for e in sorted(out_dir.glob("c*")):
        sp = e / "sidecars" / "sort_types.json"
        if not sp.is_file():
            continue
        sc = json.loads(sp.read_text())
        for rel in sc["documents"]:
            p = ROOT / rel
            if p.is_file():
                docs.append({"facts": rel, "source": f"corpus {e.name}", **profile_one(p, ROOT, sc, tier)})
    # the planted documents
    tmp = Path(tempfile.mkdtemp(prefix="holon-i110-planted-"))
    planted_rows = []
    try:
        for depth in (6, 10):
            d = planted(tmp, depth, 4)
            p = d / "deep.extracted.json"
            sc = dict(base_sc)
            row = {"facts": f"<planted depth {depth}, 4 actions>", "source": "planted",
                   "solidity_sha256": hashlib.sha256(planted_source(depth, 4).encode()).hexdigest(),
                   **profile_one(p, d, sc, tier)}
            (d / "st0.json").write_text(json.dumps(dict(sc, documents=["deep.extracted.json"])))
            row["wall_head_s"] = wall(ROOT, d, "st0.json", d / "head")
            if a.base_tree:
                row["wall_base_s"] = wall(Path(a.base_tree), d, "st0.json", d / "base")
                same = all((d / "head" / f.name).read_bytes() == f.read_bytes() for f in sorted((d / "base").iterdir()))
                row["outputs_identical"] = same and sorted(x.name for x in (d / "base").iterdir()) == \
                    sorted(x.name for x in (d / "head").iterdir())
            docs.append(row)
            planted_rows.append(row)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    under = sum(1 for d in docs if d["work"] <= tier)
    doc = {"profile_version": "holon-i110-sort-profile/0.1", "doc": __doc__.split("\n\n")[0].strip(), "tier": tier,
           "unit": "holon.sorts.budget work units", "documents": docs,
           "summary": {"documents": len(docs), "under_tier": under, "share_under_tier": round(under / len(docs), 4),
                       "largest_work": max(d["work"] for d in docs),
                       "planted_wall_ratio": {r["facts"]: round(r["wall_head_s"] / r["wall_base_s"], 3)
                                              for r in planted_rows if r.get("wall_base_s")}}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(json.dumps(doc["summary"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
