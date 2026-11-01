"""Decision traces (pipeline v2, part B): what a `holon run` read when it decided a law, so a later run can tell, without
deciding it again, that every input is unchanged.

A trace is recorded for every law whose record a `holon run` writes (results/<M>/<law>.json). It holds everything the
process had read up to that write: an over-approximation of the law's own inputs (laws decided earlier in the same
process add theirs), which is sound and needs no change in any runner. It lives beside the record, in
results/<M>/traces/<law>.json, and is applied with it from the CI run that made both. It carries:
  reads      every file of the repository the process opened for reading (Python opens, through an audit hook),
             with its sha256 at the moment it was read; the law's own record and every file the process wrote
             before reading it are outputs, not inputs
  listings   every directory it listed (os.listdir, os.scandir, glob), keyed by its sorted names
  stats      every path whose existence or kind it asked about (os.stat and os.lstat, which os.path and pathlib use),
             with the answer
  subprocs   every subprocess: its argv, the content of each argument that is a file (with the import closure of a
             .bend argument), the bytes it was given on stdin, and its binary's sha256
  code       every module of holon/ loaded in the process, by sha256
  env        the checker's fingerprint (holon.bend), the pins (config/holon.json), Python's version, the run's argv
             and the HOLON_* environment
  network    whether the process opened a socket; a trace that did is never reused

`check` re-reads a trace against the tree: valid only when every entry still holds. Reuse is an accelerator, never a
judge: a reused PROVED or REFUTED is re-checked by the gate (G5, G7, and G6 for its replay), a reused UNKNOWN makes no
claim, and a milestone's exit re-makes every record without reuse. Nothing here names a target.
"""
from __future__ import annotations

import glob as _glob
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

VERSION = 1
RECORD = re.compile(r"results/(M\d+|T\d+)/(L_[^/]+)\.json")
SKIP = re.compile(r"(^|/)(__pycache__|\.git)(/|$)|\.pyc$|^results/[^/]+/traces/")

_T: "Tracer | None" = None


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha(p: Path) -> str | None:
    try:
        return sha(p.read_bytes())
    except OSError:
        return None


def bend_closure(p: Path, root: Path, seen: dict) -> None:
    """The .bend file and, recursively, every file it imports by a relative path (Bend's imports are plain relative
    paths inside the repository, so the closure is exact), into seen: {repo path: sha256}."""
    try:
        rel = p.resolve().relative_to(root).as_posix()
    except ValueError:
        return
    if rel in seen:
        return
    seen[rel] = file_sha(p)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError:
        return
    for m in re.finditer(r"(?m)^\s*import\s+(\S+)", text):
        tok = m.group(1)
        if "/" in tok or tok.endswith(".bend"):
            q = (p.parent / tok)
            if q.suffix != ".bend":
                q = q.with_suffix(".bend") if not q.is_file() else q
            if q.is_file():
                bend_closure(q, root, seen)


class Tracer:
    def __init__(self, root: Path, argv: list[str]):
        self.root = root.resolve()
        self.argv = list(argv)
        self.reads: dict[str, str | None] = {}
        self.listings: dict[str, str] = {}
        self.stats: dict[str, str] = {}
        self.subprocs: list[dict] = []
        self.written: set[str] = set()
        self.network = False
        self.snaps: dict[str, dict] = {}      # law -> its trace at its record's last write
        self.busy = False
        self.bins: dict[str, str | None] = {}

    def rel(self, path) -> str | None:
        try:
            s = os.fspath(path)
        except TypeError:
            return None
        if isinstance(s, bytes):
            s = s.decode(errors="replace")
        p = Path(s)
        if not p.is_absolute():
            p = Path(os.getcwd()) / p
        try:
            r = Path(os.path.normpath(p)).relative_to(self.root).as_posix()
        except ValueError:
            return None
        return None if SKIP.search(r) else r

    # ------------------------------------------------------------------ events
    def on_open(self, path, mode, flags) -> None:
        r = self.rel(path)
        if r is None:
            return
        wr = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
            (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
        if wr:
            self.written.add(r)
            m = RECORD.fullmatch(r)
            if m:
                self.snaps[m.group(2)] = {"milestone": m.group(1), "path": r}
            return
        if r in self.written or r in self.reads:
            return
        p = self.root / r
        if p.is_file():
            self.reads[r] = file_sha(p)

    def on_list(self, path) -> None:
        r = self.rel(path if path not in (None, b"", "") else ".")
        if r is None or r in self.listings or r in self.written:
            return
        try:
            names = sorted(os.listdir(self.root / r))
        except OSError:
            names = None
        self.listings[r] = sha(json.dumps(names).encode())

    def on_stat(self, path) -> None:
        r = self.rel(path)
        if r is None or r in self.stats or r in self.written:
            return
        p = self.root / r
        self.stats[r] = "file" if p.is_file() else ("dir" if p.is_dir() else ("absent" if not p.exists() else "other"))

    def on_proc(self, argv, cwd, stdin: bytes | None) -> None:
        if isinstance(argv, (str, bytes)):
            argv = [argv]
        argv = [os.fsdecode(x) if isinstance(x, (bytes, os.PathLike)) else str(x) for x in argv]
        base = Path(cwd) if cwd else Path(os.getcwd())
        files: dict[str, str | None] = {}
        for x in argv[1:]:
            q = Path(x) if Path(x).is_absolute() else base / x
            if q.is_file():
                if q.suffix == ".bend":
                    bend_closure(q, self.root, files)
                else:
                    r = self.rel(q)
                    if r is not None:
                        files[r] = file_sha(q)
        exe = argv[0] if argv else ""
        if exe not in self.bins:
            w = shutil.which(exe) if exe else None
            self.bins[exe] = file_sha(Path(w)) if w else None
        self.subprocs.append({"argv": [self.rel(x) or x if "/" in x else x for x in argv], "files": files,
                              "stdin": sha(stdin) if stdin else None, "binary": self.bins[exe]})

    # ------------------------------------------------------------------ the trace of one law
    def trace_of(self, law: str, record: str) -> dict:
        code = {}
        for mod in list(sys.modules.values()):
            f = getattr(mod, "__file__", None)
            r = self.rel(f) if f else None
            if r and r.startswith("holon/") and r.endswith(".py"):
                code[r] = file_sha(self.root / r)
        return {"version": VERSION, "law": law, "record": record, "reads": dict(sorted(
                    (k, v) for k, v in self.reads.items() if k != record)),
                "listings": dict(sorted(self.listings.items())), "stats": dict(sorted(self.stats.items())),
                "subprocs": self.subprocs, "code": dict(sorted(code.items())), "env": env_of(self.root, self.argv),
                "network": self.network, "run_id": os.environ.get("GITHUB_RUN_ID")}

    def flush(self) -> int:
        n = 0
        for law, s in sorted(self.snaps.items()):
            rec = self.root / s["path"]
            if not rec.is_file():
                continue
            out = self.root / "results" / s["milestone"] / "traces" / f"{law}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(self.trace_of(law, s["path"]), indent=1, sort_keys=True) + "\n", encoding="utf-8")
            n += 1
        return n


def env_of(root: Path, argv: list[str]) -> dict:
    try:
        from . import bend
        fp = bend.fingerprint().get("fingerprint")
    except Exception:  # noqa: BLE001: no checker, no fingerprint (and no reuse across checkers)
        fp = None
    cfg = root / "config" / "holon.json"
    return {"checker": fp, "pins": file_sha(cfg) if cfg.is_file() else None,
            "python": f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]} {platform.machine()}",
            "argv": list(argv), "holon_env": {k: v for k, v in sorted(os.environ.items()) if k.startswith("HOLON_")}}


def _hook(event: str, args) -> None:
    t = _T
    if t is None or t.busy:
        return
    t.busy = True
    try:
        if event == "open":
            t.on_open(args[0], args[1] if len(args) > 1 else None, args[2] if len(args) > 2 else None)
        elif event in ("os.listdir", "os.scandir"):
            t.on_list(args[0] if args else ".")
        elif event in ("glob.glob", "glob.glob/2"):
            pat = args[0] if args else ""
            pat = os.fsdecode(pat) if isinstance(pat, (bytes, os.PathLike)) else str(pat)
            head = pat.split("*")[0].split("?")[0].split("[")[0]
            t.on_list(os.path.dirname(head) or ".")
        elif event == "socket.connect":
            t.network = True
    finally:
        t.busy = False


def install(root: Path, argv: list[str]) -> Tracer:
    """Start tracing this process (one tracer per process: audit hooks cannot be removed)."""
    global _T
    if _T is not None:
        return _T
    _T = Tracer(root, argv)
    sys.addaudithook(_hook)
    real_stat, real_lstat = os.stat, os.lstat

    def stat(path, *a, **k):
        t = _T
        if t is not None and not t.busy and not isinstance(path, int):
            t.busy = True
            try:
                t.on_stat(path)
            finally:
                t.busy = False
        return real_stat(path, *a, **k)

    def lstat(path, *a, **k):
        t = _T
        if t is not None and not t.busy and not isinstance(path, int):
            t.busy = True
            try:
                t.on_stat(path)
            finally:
                t.busy = False
        return real_lstat(path, *a, **k)
    os.stat, os.lstat = stat, lstat
    real_init, real_comm = subprocess.Popen.__init__, subprocess.Popen.communicate

    def init(self, args, *a, **k):
        self._holon_trace = (args, k.get("cwd"))
        return real_init(self, args, *a, **k)

    def communicate(self, input=None, *a, **k):  # noqa: A002 (the stdlib's name)
        t = _T
        args, cwd = getattr(self, "_holon_trace", (getattr(self, "args", []), None))
        if t is not None and not t.busy:
            t.busy = True
            try:
                t.on_proc(args, cwd, input if isinstance(input, bytes) else (input.encode() if isinstance(input, str)
                                                                              else None))
            finally:
                t.busy = False
        return real_comm(self, input, *a, **k)
    subprocess.Popen.__init__, subprocess.Popen.communicate = init, communicate
    return _T


def finish() -> int:
    return _T.flush() if _T is not None else 0


# ------------------------------------------------------------------------------------------------ validity
def check(root: Path, trace: dict) -> str | None:
    """None when every entry of the trace still holds in the tree at root, else the first entry that does not."""
    if trace.get("version") != VERSION:
        return "trace version"
    if trace.get("network"):
        return "the run read the network"
    for r, h in (trace.get("reads") or {}).items():
        if file_sha(root / r) != h:
            return f"read {r} changed"
    for r, h in (trace.get("listings") or {}).items():
        try:
            names = sorted(os.listdir(root / r))
        except OSError:
            names = None
        if sha(json.dumps(names).encode()) != h:
            return f"listing of {r or '.'} changed"
    for r, kind in (trace.get("stats") or {}).items():
        p = root / r
        now = "file" if p.is_file() else ("dir" if p.is_dir() else ("absent" if not p.exists() else "other"))
        if now != kind:
            return f"{r} is now {now}, was {kind}"
    for sp in trace.get("subprocs") or []:
        for r, h in (sp.get("files") or {}).items():
            if file_sha(root / r) != h:
                return f"subprocess input {r} changed"
    for r, h in (trace.get("code") or {}).items():
        if file_sha(root / r) != h:
            return f"code {r} changed"
    env = trace.get("env") or {}
    now = env_of(root, env.get("argv") or [])
    for k in ("checker", "pins", "python"):
        if env.get(k) != now.get(k):
            return f"environment {k} changed"
    return None


def reusable(root: Path, m: str, laws: list[str]) -> dict[str, str]:
    """{law: why not} for the laws among `laws` that cannot be reused at root; a law missing here can be: its record
    carries the registry's statement hash and its trace still holds."""
    reg = json.loads((root / "laws" / m / "REGISTRY.json").read_text())["statements"]
    out = {}
    for lid in laws:
        rec, tr = root / "results" / m / f"{lid}.json", root / "results" / m / "traces" / f"{lid}.json"
        if not rec.is_file():
            out[lid] = "no record"
        elif json.loads(rec.read_text()).get("statement_hash") != reg.get(lid):
            out[lid] = "statement changed"
        elif not tr.is_file():
            out[lid] = "no trace"
        else:
            why = check(root, json.loads(tr.read_text()))
            if why:
                out[lid] = why
    return out


def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="holon trace", description="check decision traces against the tree")
    ap.add_argument("step", choices=("check",))
    ap.add_argument("--milestone", default="M3")
    ap.add_argument("--laws", help="comma-separated law ids (default: every law of the registry)")
    a = ap.parse_args(argv)
    root = Path.cwd()
    reg = json.loads((root / "laws" / a.milestone / "REGISTRY.json").read_text())["statements"]
    laws = [x for x in (a.laws or "").split(",") if x] or sorted(reg)
    bad = reusable(root, a.milestone, laws)
    print(f"holon trace: {len(laws) - len(bad)} of {len(laws)} laws reusable")
    for lid, why in sorted(bad.items()):
        print(f"  {lid}: {why}")
    return 0
