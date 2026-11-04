"""Decision traces (pipeline v2, part B): what a `holon run` read when it decided a law, so a later run can tell, without
deciding it again, that every input is unchanged.

With HOLON_TRACE=1 (the re-make workflows set it; local runs and tests leave the process untouched), a trace is
recorded for every law whose record a `holon run` writes (results/<M>/<law>.json). It is an over-approximation of
the law's own inputs (laws decided in the same process add theirs), which is sound and needs no change in any runner.
It lives at traces/<M>/<law>.json, outside results/ (record scanners glob results/), and is applied with the record
from the CI run that made both. It carries:
  reads      every file of the repository the process opened for reading (Python opens, through an audit hook)
  records    every other law's record the process read BEFORE this law's record was last written (a verdict
             computed from them: a back-test, an attribution, a profile); a read after it (contracts.after_run, a
             summary) is not an input of this verdict
  outputs    every path the process wrote, deleted or renamed, and every directory it wrote into, are outputs: no
             entry of the trace; the trace is evaluated at the end of the run, the state committed with its records
  listings   every directory it listed (os.listdir, os.scandir, glob), keyed by its sorted names
  stats      every path whose existence or kind it asked about (os.stat and os.lstat, which os.path and pathlib use),
             with the answer (none for a path whose directory listing is recorded)
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

VERSION = 2
RECORD = re.compile(r"results/(M\d+|T\d+)/(L_[^/]+)\.json")
# never inputs: caches, and build/ (gitignored; a compiled model under build/<kind>/<sha256 of its sources>/ is derived
# from gen/<M>/model/*.bend, which a trace records itself, and a fresh checkout has none until it builds one)
SKIP = re.compile(r"(^|/)(__pycache__|\.git)(/|$)|\.pyc$|^traces/|^build/")

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
    seen[rel] = h(p)
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
    """Records which paths a process touched; their content is read when the trace is written, at the end of the run
    (the end state is what the run committed beside its records, and what a later check compares with). Every path
    the process wrote, deleted or renamed is an output, and so is every directory it wrote into: neither is an input
    of the trace."""

    def __init__(self, root: Path, argv: list[str]):
        self.root = root.resolve()
        self.argv = list(argv)
        self.reads: dict[str, None] = {}
        self.lists: dict[str, None] = {}
        self.stats: dict[str, None] = {}
        self.procs: dict[str, dict] = {}
        self.written: set[str] = set()
        self.cleared: set[str] = set()        # directories removed whole (shutil.rmtree, os.rmdir)
        self.network = False
        self.records: dict[str, tuple[str, int]] = {}   # law -> (its record's path, the event of its last write)
        self.rec_reads: dict[str, int] = {}  # another law's record -> the event of its first read
        self.n = 0                            # the event counter
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
        self.n += 1
        wr = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
            (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
        if wr:
            self.wrote(r)
        elif RECORD.fullmatch(r):
            self.rec_reads.setdefault(r, self.n)
        else:
            self.reads.setdefault(r, None)

    def wrote(self, r: str) -> None:
        self.written.add(r)
        m = RECORD.fullmatch(r)
        if m:
            self.records[m.group(2)] = (r, self.n)

    def on_remove(self, path, whole_dir: bool = False) -> None:
        r = self.rel(path)
        if r is not None:
            (self.cleared if whole_dir else self.written).add(r)

    def on_list(self, path) -> None:
        r = self.rel(path if path not in (None, b"", "") else ".")
        if r is not None:
            self.lists.setdefault(r, None)

    def on_stat(self, path) -> None:
        r = self.rel(path)
        if r is not None:
            self.stats.setdefault(r, None)

    def on_proc(self, argv, cwd, stdin: bytes | None) -> None:
        if isinstance(argv, (str, bytes)):
            argv = [argv]
        argv = [os.fsdecode(x) if isinstance(x, (bytes, os.PathLike)) else str(x) for x in argv]
        base = str(Path(cwd) if cwd else Path(os.getcwd()))
        key = json.dumps([argv, base, sha(stdin)[:16] if stdin else None])
        if key not in self.procs:
            exe = argv[0] if argv else ""
            if exe not in self.bins:
                w = shutil.which(exe) if exe else None
                self.bins[exe] = (file_sha(Path(w)) or "")[:16] if w else None
            self.procs[key] = {"argv": argv, "cwd": base, "stdin": sha(stdin)[:16] if stdin else None,
                               "binary": self.bins[exe]}

    # ------------------------------------------------------------------ the trace, at the end of the run
    def output(self, r: str) -> bool:
        if r in self.written:
            return True
        return any(r == d or r.startswith(d + "/") for d in self.cleared)

    def out_dir(self, d: str) -> bool:
        pre = "" if d in ("", ".") else d + "/"
        return self.output(d) or any(w.startswith(pre) for w in self.written) or \
            any(c.startswith(pre) for c in self.cleared)

    def snapshot(self) -> dict:
        root = self.root
        reads = {r: h(root / r) for r in self.reads if not self.output(r)}
        recs = {r: (i, h(root / r)) for r, i in self.rec_reads.items() if not self.output(r)}
        lists = {d: listing(root / d) for d in self.lists if not self.out_dir(d)}
        listed = set(self.lists)
        stats = {r: kind(root / r) for r in self.stats
                 if r not in self.reads and not self.output(r) and not self.out_dir(str(Path(r).parent))
                 and (str(Path(r).parent) if str(Path(r).parent) != "." else ".") not in listed}
        procs = []
        for sp in self.procs.values():
            files: dict[str, str | None] = {}
            for x in sp["argv"][1:]:
                q = Path(x) if Path(x).is_absolute() else Path(sp["cwd"]) / x
                if q.is_file():
                    if q.suffix == ".bend":
                        bend_closure(q, root, files)
                    else:
                        rq = self.rel(q)
                        if rq is not None:
                            files[rq] = h(q)
            files = {k: v for k, v in files.items() if not self.output(k)}
            procs.append({"argv": [self.rel(x) or x if "/" in x else x for x in sp["argv"]], "files": files,
                          "stdin": sp["stdin"], "binary": sp["binary"]})
        code = {}
        for mod in list(sys.modules.values()):
            f = getattr(mod, "__file__", None)
            r = self.rel(f) if f else None
            if r and r.startswith("holon/") and r.endswith(".py"):
                code[r] = h(root / r)
        return {"reads": dict(sorted(reads.items())), "records": dict(sorted(recs.items())),
                "listings": dict(sorted(lists.items())), "stats": dict(sorted(stats.items())),
                "subprocs": sorted(procs, key=lambda x: json.dumps(x, sort_keys=True)), "code": dict(sorted(code.items())),
                "env": env_of(root, self.argv), "network": self.network}

    def flush(self) -> int:
        if not self.records:
            return 0
        snap = self.snapshot()
        n = 0
        for law, (rec, last) in sorted(self.records.items()):
            if not (self.root / rec).is_file():
                continue
            out = self.root / "traces" / RECORD.fullmatch(rec).group(1) / f"{law}.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            # another law's record counts for this law when it was read before this law's record was last written
            # (inside the decision: a back-test, an attribution, a profile); reads after it (contracts.after_run,
            # aggregates) are not inputs of this verdict
            body = dict(snap, records={k: v for k, (i, v) in snap["records"].items() if k != rec and i < last})
            out.write_text(json.dumps({"version": VERSION, "law": law, "record": rec, "run_id":
                                       os.environ.get("GITHUB_RUN_ID"), **body}, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
            n += 1
        return n


def h(p: Path) -> str | None:
    """A file's identity in a trace: the first 64 bits of its sha256 (change detection; claims are re-checked by the
    gate, so the hash is never what makes a result true)."""
    v = file_sha(p)
    return v[:16] if v else None


def listing(p: Path) -> str:
    try:
        names = sorted(os.listdir(p))
    except OSError:
        names = None
    return sha(json.dumps(names).encode())[:16]


def kind(p: Path) -> str:
    return "file" if p.is_file() else ("dir" if p.is_dir() else ("absent" if not p.exists() else "other"))


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
        elif event in ("os.remove", "os.unlink"):
            t.on_remove(args[0])
        elif event == "os.rename":
            t.on_remove(args[0])
            t.on_remove(args[1])
        elif event in ("shutil.rmtree", "os.rmdir"):
            t.on_remove(args[0], whole_dir=True)
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
def check(root: Path, trace: dict, records: bool = True) -> str | None:
    """None when every entry of the trace still holds in the tree at root, else the first entry that does not. The
    other laws' records in a trace are those read before this law's record was last written (holon.trace.Tracer),
    so they count: a verdict computed from them (a back-test, an attribution, a profile) is stale when they change.
    records=False skips them (diagnostics only)."""
    if trace.get("version") != VERSION:
        return "trace version"
    if trace.get("network"):
        return "the run read the network"
    for part in ("reads", "records", "code") if records else ("reads", "code"):
        for r, v in (trace.get(part) or {}).items():
            if SKIP.search(r):     # an entry an older trace recorded before SKIP excluded it (build/)
                continue
            if h(root / r) != v:
                return f"{part[:-1] if part != 'code' else 'code'} {r} changed"
    for r, v in (trace.get("listings") or {}).items():
        if SKIP.search(r):
            continue
        if listing(root / r) != v:
            return f"listing of {r or '.'} changed"
    for r, v in (trace.get("stats") or {}).items():
        if SKIP.search(r):
            continue
        if kind(root / r) != v:
            return f"{r} is now {kind(root / r)}, was {v}"
    for sp in trace.get("subprocs") or []:
        for r, v in (sp.get("files") or {}).items():
            if SKIP.search(r):
                continue
            if h(root / r) != v:
                return f"subprocess input {r} changed"
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
        rec, tr = root / "results" / m / f"{lid}.json", root / "traces" / m / f"{lid}.json"
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
