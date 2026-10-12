"""A3 held-out mutant sampler, implementing docs/M2_A3_SPEC.md "Held-out mutant set A3".

Pool: A2's `pool()` (spec/M2/A2/sample_mutants.py — imported, not copied),
minus every (file, line) used by the 30 scored A2 mutants recorded in
replay/M2/A2/report.json. Candidates are shuffled with
random.Random(seed), seed = int(sha256("\\n".join(sorted A3 statement
hashes)), 16) mod 2**32, and given ids B001.. in shuffled order.
The campaign walks that order and keeps the first `take` mutants that compile.
Usage: sample_mutants.py <morph_dir> <registry.json> <out.json>
"""
import hashlib, importlib.util, json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _a2_sampler():
    spec = importlib.util.spec_from_file_location(
        "a2_sample_mutants", ROOT / "spec/M2/A2/sample_mutants.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    morph, reg, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    a2 = _a2_sampler()
    a2_used = {(m["file"], m["line"]) for m in
               json.loads((ROOT / "replay/M2/A2/report.json").read_text())["mutants"]}
    p = [c for c in a2.pool(morph) if (c["file"], c["line"]) not in a2_used]
    hashes = sorted(json.loads(reg.read_text())["statements"].values())
    seed = int(hashlib.sha256("\n".join(hashes).encode()).hexdigest(), 16) % 2**32
    order = list(p)
    random.Random(seed).shuffle(order)
    for i, d in enumerate(order, 1):
        d.update(id=f"B{i:03d}", equivalent=False)
    dst.write_text(json.dumps({
        "milestone": "M2-A3", "threshold": 0.8, "take": a2.TAKE,
        "registry_sha256": hashlib.sha256(reg.read_bytes()).hexdigest(), "seed": seed,
        "pool_size": len(p), "rule": "walk `order`; keep the first `take` mutants that compile",
        "order": order}, indent=1) + "\n")
    print(len(p), "candidates, seed", seed)


if __name__ == "__main__":
    main()
