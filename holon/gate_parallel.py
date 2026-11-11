"""`holon gate --jobs N` (I47; whitepaper L20, "parallel checking"): the gate's checks in N worker processes.

The checks are the sequential gate's, run by the same methods of holon.gate.Gate, each in a worker process
(concurrent.futures.ProcessPoolExecutor) that builds its own Gate over the same root, passes GENV again, and gets its
own fresh build directory (nothing compiled is shared or reused). They are grouped so that no check reads state another
check of a different group writes:

  G1 | G8 | G5 then G3 (G3 reads the checker outputs G5 collects) | G11 G11V G6 G9 G10 GREF GEVID | G7 | G4

G2's statement-change log scan (holon.statement_diff.scan, the check's dominant cost) is split by line kind with the
scan's own `kinds` argument: every line is checked exactly once, by the same code, with the whole file as its context
(the committed history, the origins of each line, the id of each line), in the worker of its kind's partition. Lines of
different kinds cannot share an id (a line's id is the sha256 of its content, kind included), so no duplicate escapes. A
log holding any line that is not a JSON object with a string kind is scanned whole in one worker. The partitions'
results are merged in line order and the rest of G2 (the registry, the statement-change tie, the negations, the
bindings) runs in the parent on the merged scan. Verdicts, canaries and timings are those of the sequential gate; the
G2 detail lists the partitions' notes.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

GROUPS = [["G1"], ["G8"], ["G5", "G3"], ["G11", "G11V", "G6", "G9", "G10", "GREF", "GEVID"], ["G7"], ["G4"]]
# the expected cost order (the M1 gate at I47's base: G2 151 s, G1 75, G7 23, G4 21, G5 4), longest submitted first
COST = {"G1": 75, "G7": 23, "G4": 21, "G5": 4, "G11V": 3}
NICE = 5   # the check workers' niceness; the scan workers keep the gate's own


def _fresh_build() -> str:
    d = tempfile.mkdtemp(prefix="holon-gate-build-")
    os.environ["HOLON_BUILD_DIR"] = d
    return d


def _check_task(job: tuple) -> dict:
    m, root, steps, g1_jobs = job
    from .gate import Gate, _res
    try:   # the statement-log scan is the gate's longest path: the other checks yield the CPU to it (scheduling only)
        os.nice(NICE)
    except OSError:
        pass
    build = _fresh_build()
    try:
        g = Gate(m, Path(root))
        g.g1_jobs = g1_jobs
        g.genv()
        if not g.checks.get("GENV", {}).get("passed"):
            return {"checks": {s: _res(False, g.genv_skip) for s in steps}, "canaries": [], "timings": None}
        names = {"G2": g.g2, "G1": g.g1, "G8": g.g8, "G5": g.g5, "G3": g.g3, "G11": g.g11, "G11V": g.g11v, "G6": g.g6,
                 "G9": g.g9, "G10": g.g10, "GREF": g.gref, "GEVID": g.gevid, "G7": g.g7, "G4": g.g4}
        if "G3" in steps and "G5" not in steps:
            g.recheck_outputs()
        for s in steps:
            try:
                names[s]()
            except Exception as e:  # noqa: BLE001  (a crash is a failed check, as in the sequential gate)
                g.checks[s] = _res(False, f"error: {type(e).__name__}: {e}")
        return {"checks": {s: g.checks[s] for s in steps}, "canaries": g.canaries if "G4" in steps else [],
                "timings": g.timings}
    finally:
        shutil.rmtree(build, ignore_errors=True)


def _scan_task(job: tuple) -> dict:
    m, root, kinds = job
    from . import statement_diff as SD
    build = _fresh_build()
    try:
        return SD.scan(Path(root) / SD.LOG, Path(root), kinds=set(kinds) if kinds is not None else None, milestone=m)
    finally:
        shutil.rmtree(build, ignore_errors=True)


def kind_partitions(log: Path, n: int) -> list[list[str]] | None:
    """The log's kinds in at most n partitions, balanced by line count (greedy, largest first; ties by name), or None
    when some line is not a JSON object with a string kind (then the scan runs whole)."""
    counts: dict[str, int] = {}
    if not log.is_file():
        return None
    for raw in log.read_bytes().splitlines():
        if not raw.strip():
            continue
        try:
            e = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(e, dict) or not isinstance(e.get("kind"), str):
            return None
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    if not counts:
        return None
    bins: list[tuple[int, list[str]]] = [(0, []) for _ in range(max(1, min(n, len(counts))))]
    for k in sorted(counts, key=lambda k: (-counts[k], k)):
        i = min(range(len(bins)), key=lambda j: (bins[j][0], j))
        bins[i] = (bins[i][0] + counts[k], bins[i][1] + [k])
    return [sorted(b) for _, b in bins if b]


def _line_of(p: str) -> int:
    x = re.match(r"line (\d+):", p)
    return int(x.group(1)) if x else -1


def merge_scans(parts: list[dict]) -> dict:
    """The partitions' scans as one: entries and problems in line order (problems not about a line first, once each),
    the per-line lists merged, the notes joined (the common head once, then each partition's own suffixes)."""
    out = {"problems": [], "entries": [], "git": any(p.get("git") for p in parts), "note": ""}
    seen = set()
    probs = []
    for p in parts:
        for x in p.get("problems", []):
            if x not in seen:
                seen.add(x)
                probs.append(x)
    out["problems"] = sorted(probs, key=lambda x: (_line_of(x), probs.index(x)))
    out["entries"] = sorted((e for p in parts for e in p.get("entries", [])), key=lambda e: e["line"])
    for key in ("unchecked", "stored", "elsewhere"):
        vals = sorted({n for p in parts for n in p.get(key, [])})
        if vals:
            out[key] = vals
    crashes = [c for p in parts for c in p.get("crashes", [])]
    if crashes:
        out["crashes"] = crashes
    notes = [p.get("note", "") for p in parts]
    head = notes[0].split("; ")[0] if notes else ""
    tails = []
    for n in notes:
        for seg in n.split("; ")[1:]:
            if seg not in tails:
                tails.append(seg)
    out["note"] = "; ".join([head] + tails) + (f" (scanned in {len(parts)} partitions by line kind, I47)"
                                              if len(parts) > 1 else "")
    return out


def run_checks(gate, order: list[str]) -> None:
    """Run the checks of `order` (after GENV, which the caller ran) for gate, in gate.jobs workers; fill gate.checks,
    gate.canaries and gate.timings as the sequential loop does."""
    from . import statement_diff as SD
    from .gate import _res
    root, m, jobs = str(gate.root), gate.m, gate.jobs
    tasks = []   # (cost, kind, payload)
    parts = None
    if "G2" in order:
        parts = kind_partitions(gate.root / SD.LOG, max(1, jobs - 1))
        for ks in (parts or [None]):
            tasks.append((150, "scan", (m, root, ks)))
    groups = [[s for s in grp if s in order] for grp in GROUPS]
    for grp in groups:
        if grp:
            tasks.append((max(COST.get(s, 1) for s in grp), "check", (m, root, grp, 1)))
    tasks.sort(key=lambda t: -t[0])
    with ProcessPoolExecutor(max_workers=jobs) as ex:
        futs = [(kind, payload, ex.submit(_scan_task if kind == "scan" else _check_task, payload))
                for _, kind, payload in tasks]
        scans, checks = [], {}
        for kind, payload, f in futs:
            try:
                r = f.result()
            except Exception as e:  # noqa: BLE001  (a crashed worker is a failed check, never a pass)
                if kind == "scan":
                    gate.checks["G2"] = _res(False, f"error: the statement-log scan crashed: {type(e).__name__}: {e}")
                    scans = None
                else:
                    for s in payload[2]:
                        checks[s] = _res(False, f"error: worker crashed: {type(e).__name__}: {e}")
                continue
            if kind == "scan":
                if scans is not None:
                    scans.append((payload[2] or [], r))
            else:
                checks.update(r["checks"])
                if r["canaries"]:
                    gate.canaries = r["canaries"]
                if r["timings"]:
                    gate.timings = {**(gate.timings or {}), **r["timings"]}
    if "G2" in order and scans is not None:
        scans.sort(key=lambda x: x[0])
        gate._sd = merge_scans([r for _, r in scans])
        try:
            gate.g2()
        except Exception as e:  # noqa: BLE001
            gate.checks["G2"] = _res(False, f"error: {type(e).__name__}: {e}")
        finally:
            gate._sd = None
    for s in order[1:]:
        if s in checks:
            gate.checks[s] = checks[s]
