"""Early adequacy signal for S1 (facts only, no law pipeline).

For each mutant in spec/M2/mutants.json (Rollup.sol, R01-R20): fresh git
worktree at the pinned commit, sha256-verify the target file, apply the single
line mutation, compile with solc, run the extractor, and report
identical / differs (which actions/fields) / compile_fail vs the baseline
extracted facts. Deterministic: sorted iteration, no timestamps.

Usage: python -m holon.frontends.solidity.adequacy [R01 R02 ...]
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from . import astload, extract as extract_mod
from .sexpr import normalize

REPO = Path(__file__).resolve().parents[3]
MUTANTS = REPO / "spec" / "M2" / "mutants.json"
BASELINE = REPO / "spec" / "M2" / "extracted" / "morph_rollup.json"


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def apply_mutation(root: Path, m: dict):
    """Replace line m['line'] of m['file'] after asserting the original text."""
    fp = root / m["file"]
    lines = fp.read_text().splitlines(keepends=True)
    idx = m["line"] - 1
    orig = lines[idx].rstrip("\n")
    assert orig.strip() == m["original"], (
        f"{m['id']}: line {m['line']} is {orig.strip()!r}, expected {m['original']!r}")
    indent = orig[: len(orig) - len(orig.lstrip())]
    nl = "\n" if lines[idx].endswith("\n") else ""
    lines[idx] = indent + m["replacement"] + nl
    fp.write_text("".join(lines))


def _fv(e, out):
    """Free variable-ish leaves of an sexpr, for diff reporting."""
    if isinstance(e, str):
        out.add(e)
    elif isinstance(e, list):
        for x in e[1:]:
            _fv(x, out)
    elif isinstance(e, dict):
        for v in e.values():
            _fv(v, out)


def diff_actions(base: dict, ext: dict):
    """Which actions/fields differ canonically between two facts docs."""
    out = []
    ba = {a["name"]: a for a in base.get("actions", [])}
    ea = {a["name"]: a for a in ext.get("actions", [])}
    for name in sorted(set(ba) | set(ea)):
        if name not in ba:
            out.append(f"{name}:+action")
            continue
        if name not in ea:
            out.append(f"{name}:-action")
            continue
        hg = [g.get("require", g.get("expr")) for g in ba[name].get("guards", [])]
        eg = [g.get("require", g.get("expr")) for g in ea[name].get("guards", [])]
        if [repr(normalize(g)) for g in hg] != [repr(normalize(g)) for g in eg]:
            out.append(f"{name}:guards")
        he, ee = ba[name].get("effects", {}), ea[name].get("effects", {})
        for f in sorted(set(he) | set(ee)):
            if repr(normalize(he.get(f))) != repr(normalize(ee.get(f))):
                out.append(f"{name}:effects.{f}")
    bd, ed = base.get("defs", {}), ext.get("defs", {})
    for k in sorted(set(bd) | set(ed)):
        if repr(normalize((bd.get(k) or {}).get("body"))) != repr(normalize((ed.get(k) or {}).get("body"))):
            out.append(f"defs.{k}")
    return out


def run_mutant(spec, morph_git: str, commit: str, m: dict, work_root: str):
    """One mutant: worktree -> sha check -> apply -> compile -> extract -> diff."""
    mid = m["id"]
    wt = Path(work_root) / mid
    subprocess.run(["git", "-C", morph_git, "worktree", "add", "--detach",
                    str(wt), commit], check=True, capture_output=True)
    try:
        # solc needs the package deps the worktree doesn't have: borrow them
        base = spec.get("base_path", "contracts")
        for dep in ("node_modules", "lib"):
            src_dir = Path(morph_git) / base / dep
            dst_dir = wt / base / dep
            if src_dir.exists() and not dst_dir.exists():
                dst_dir.symlink_to(src_dir)
        target = wt / m["file"]
        want = MUTANTS_JSON["target"]["file_sha256"][m["file"]]
        got = sha256_file(target)
        if got != want:
            return {"id": mid, "status": "sha_mismatch", "detail": got[:16]}
        apply_mutation(wt, m)
        try:
            world = astload.run_solc(spec, str(wt))
        except Exception as e:
            return {"id": mid, "status": "compile_fail",
                    "detail": str(e).split("\n")[0][:160]}
        baseline = json.loads(BASELINE.read_text())
        try:
            ext, _cov = extract_mod.extract(world, spec, None, None)
        except Exception as e:
            return {"id": mid, "status": "extract_fail",
                    "detail": str(e).split(chr(10))[0][:160]}
        d = diff_actions(baseline, ext)
        return {"id": mid, "status": "identical" if not d else "differs",
                "detail": ";".join(d)}
    finally:
        subprocess.run(["git", "-C", morph_git, "worktree", "remove", "--force",
                        str(wt)], capture_output=True)


def main(ids=None):
    global MUTANTS_JSON
    MUTANTS_JSON = json.loads(MUTANTS.read_text())
    spec = extract_mod.load_spec()
    morph_git = os.path.expanduser(
        os.environ.get(spec["morph_root_env"], spec["morph_root_default"]))
    commit = MUTANTS_JSON["target"]["commit"]
    mutants = [m for m in MUTANTS_JSON["mutants"]
               if m["file"].endswith(".sol") and (not ids or m["id"] in ids)]
    work_root = tempfile.mkdtemp(prefix="holon-adeq-")
    results = []
    for m in mutants:
        r = run_mutant(spec, morph_git, commit, m, work_root)
        results.append(r)
        print(json.dumps(r, sort_keys=True), flush=True)
    return results


MUTANTS_JSON = None

if __name__ == "__main__":
    main(sys.argv[1:] or None)
