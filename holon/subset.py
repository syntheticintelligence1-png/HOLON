"""A run with --laws keeps what it does not own (F-M3-42, audit M3/9; I101; the contract is the docstring of
tests_m3/test_audit_fixes_i101.py, S4).

`holon run --milestone M --laws ID,..` decides only the listed laws. The pipeline's own clean step (holon.mpipeline
clean_gen) still empties gen/<M>/model and gen/<M>/core, and its writer replaces results/<M>/summary.json and deps.json
with the listed laws' entries. So a subset run left committed models of the other laws missing, while committed law and
proof files still import them, and cut the milestone's summary and dependency index down to the subset.

The pipeline's bytes are in every committed record's generator_sha256 (holon.records.generator_files), so it is not
edited here. holon/__main__.py's cli (the `python -m holon` command line) wraps a run with --laws in keep(), as I47's
holon/parallel.py wraps the pipeline from outside it:
  - before the run, it reads every file under the run's gen/<M>/model and gen/<M>/core, and the run's summary.json and
    deps.json (the --gen-dir and --out of the run, else gen/<M>/ and results/<M>/);
  - after the run, it writes back each of those files that is now missing, and nothing the run wrote. It merges
    summary.json: the earlier entries, with the run's entries replacing those of the same laws. It merges deps.json:
    the earlier dependents with the listed laws taken out, then the run's dependents of those laws put in, in
    holon.bindings.dump's format.
A run without --laws never enters keep(). Deterministic: sorted iteration, no clock. No generator closure imports this
module. Nothing here names a law or a target.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

KEPT = ("model", "core")
MERGED = ("summary.json", "deps.json")


def _arg(argv: list, flag: str) -> str | None:
    for i, x in enumerate(argv):
        if x == flag and i + 1 < len(argv):
            return argv[i + 1]
        if x.startswith(flag + "="):
            return x[len(flag) + 1:]
    return None


def is_subset(argv: list) -> bool:
    """A `run` that names its laws (--laws) and a milestone."""
    return argv[:1] == ["run"] and _arg(argv, "--laws") is not None and _arg(argv, "--milestone") is not None


def dirs(argv: list, root: Path) -> tuple[Path, Path]:
    """(the run's gen dir, its out dir): --gen-dir and --out, else gen/<M>/ and results/<M>/ of the root."""
    m = _arg(argv, "--milestone")
    gen, out = _arg(argv, "--gen-dir"), _arg(argv, "--out")
    return (Path(gen) if gen else Path(root) / "gen" / m), (Path(out) if out else Path(root) / "results" / m)


def snapshot(gen: Path, out: Path) -> dict:
    files = {}
    for x in KEPT:
        d = Path(gen) / x
        if d.is_dir():
            for p in sorted(d.rglob("*")):
                if p.is_file():
                    files[p.relative_to(gen).as_posix()] = p.read_bytes()
    merged = {f: ((Path(out) / f).read_bytes() if (Path(out) / f).is_file() else None) for f in MERGED}
    return {"files": files, "merged": merged}


def merge_deps(old: dict, new: dict, laws: set) -> dict:
    """old's dependents with the laws taken out, then new's put in; empty entries dropped, everything sorted."""
    def flat(o: dict, n: dict) -> dict:
        out: dict = {}
        for d, ls in (o or {}).items():
            keep = sorted(set(ls) - laws)
            if keep:
                out[d] = keep
        for d, ls in (n or {}).items():
            out[d] = sorted(set(out.get(d, [])) | set(ls))
        return {d: out[d] for d in sorted(out) if out[d]}
    by_model: dict = {}
    for mdl in sorted(set(old.get("dependents_by_model") or {}) | set(new.get("dependents_by_model") or {})):
        ds = flat((old.get("dependents_by_model") or {}).get(mdl), (new.get("dependents_by_model") or {}).get(mdl))
        if ds:
            by_model[mdl] = ds
    return {"milestone": new.get("milestone") or old.get("milestone"),
            "dependents": flat(old.get("dependents"), new.get("dependents")), "dependents_by_model": by_model}


def restore(gen: Path, out: Path, snap: dict, laws: list) -> list[str]:
    """Write back what the run removed and does not own; merge summary.json and deps.json. The paths written back."""
    from . import bindings
    back = []
    for rel, data in sorted(snap["files"].items()):
        p = Path(gen) / rel
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            back.append(rel)
    old_s, old_d = snap["merged"]["summary.json"], snap["merged"]["deps.json"]
    sp, dp = Path(out) / "summary.json", Path(out) / "deps.json"
    if old_s is not None and sp.is_file() and sp.read_bytes() != old_s:   # the run rewrote it
        merged = {**json.loads(old_s), **json.loads(sp.read_text())}
        sp.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    if old_d is not None and dp.is_file() and dp.read_bytes() != old_d:
        dp.write_text(bindings.dump(merge_deps(json.loads(old_d), json.loads(dp.read_text()), set(laws))))
    return back


@contextlib.contextmanager
def keep(argv: list, root: Path):
    """Around a run with --laws: what it does not own is there after it, as before it."""
    gen, out = dirs(argv, root)
    laws = [x for x in (_arg(argv, "--laws") or "").split(",") if x]
    snap = snapshot(gen, out)
    try:
        yield
    finally:
        back = restore(gen, out, snap, laws)
        if back:
            print(f"holon run: --laws: kept {len(back)} file(s) of {gen.as_posix()} the run does not own")
