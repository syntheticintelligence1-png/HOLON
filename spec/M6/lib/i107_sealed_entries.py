"""I107 prereg instrument: the sealed targets' entries file, by the scope rules G1-G4 of spec/M6/lib/i107_protocol.json.

Written before the reveal of spec/heldout2/target.json; it names no target. It reads the revealed target.json (schema
holon-heldout2-target/0.1, spec/M6/lib/I106_draw.py) and, per target, the file list of a clone at the pin's commit
(`git ls-tree -r --name-only <commit>`), and writes the entries file holon eval holon reads as its corpus.

  python3 spec/M6/lib/i107_sealed_entries.py --target spec/heldout2/target.json --clones DIR \
      --out results/eval/generality/sealed/entries.json

DIR/<target id> is a clone of the target's repo holding the pin's commit (fetched only as target.json pins it).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# G1: a path is out of scope when any directory component, lowercased, is one of these, or starts with "."
EXCLUDED_DIRS = frozenset({
    "test", "tests", "testing", "t", "mock", "mocks", "script", "scripts", "lib", "node_modules", "certora",
    "echidna", "fuzz", "fuzzing", "invariant", "invariants", "harness", "harnesses", "example", "examples",
    "deprecated", "audit", "audits", "broadcast", "out", "cache", "artifacts", "typechain", "typechain-types",
    "build", "dist", "coverage", "forge-std", "vendor", "simulation", "simulations", "spec", "specs", "formal",
})
# G1: a file is out of scope when its name ends with one of these, or starts with "Mock" or "Test"
EXCLUDED_SUFFIXES = (".t.sol", ".s.sol", "Mock.sol", "Test.sol", "Harness.sol", "Echidna.sol")
EXCLUDED_PREFIXES = ("Mock", "Test")


def in_scope(path: str) -> bool:
    """G1: a tracked .sol file outside test, mock, script and dependency trees."""
    if not path.endswith(".sol"):
        return False
    parts = path.split("/")
    for d in parts[:-1]:
        if d.lower() in EXCLUDED_DIRS or d.startswith("."):
            return False
    name = parts[-1]
    return not (name.endswith(EXCLUDED_SUFFIXES) or name.startswith(EXCLUDED_PREFIXES))


def tracked(clone: Path, commit: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(clone), "ls-tree", "-r", "--name-only", commit], check=True,
                         capture_output=True, text=True).stdout
    return sorted(x for x in out.splitlines() if x)


def entries(target: dict, clones: Path) -> dict:
    rows = []
    for i, t in enumerate(target["targets"], 1):                        # G2: target.json order, ids s1, s2
        commit = t["pin"]["commit"]
        files = [f for f in tracked(clones / t["id"], commit) if in_scope(f)]   # G1, sorted
        rows.append({"id": f"s{i}", "system": t["id"], "repo": t["repo"], "prefix_commit": commit,
                     "fix_commit": commit, "label": None, "files": files,
                     "pin": t["pin"], "kind": "sealed",
                     "description": "I106 sealed target (G2): no label, no fix; prefix_commit = fix_commit = the pin"})
    return {"doc": "I107 (run b): the sealed targets' entries, written by spec/M6/lib/i107_sealed_entries.py from "
                   "spec/heldout2/target.json by rules G1-G4 of spec/M6/lib/i107_protocol.json. Not a corpus: "
                   "no entry has a label or a fix.",
            "entries": rows, "schema": "holon-i107-sealed-entries/0.1"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--clones", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    doc = entries(json.loads(Path(a.target).read_text()), Path(a.clones))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    for e in doc["entries"]:
        print(f"{e['id']} {e['system']}: {len(e['files'])} in-scope files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
