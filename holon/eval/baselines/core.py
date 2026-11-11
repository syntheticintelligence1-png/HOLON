"""The shared machinery of the I52 baselines (spec/M4/lib/I52_baselines.json): targets and scopes, checkouts, the
equal-budget runner, findings normalisation, location matching and the result files.

Raw per-target outcomes live outside the repository under ~/.holon/eval/baselines/raw/<system>/<baseline>/<target>.json
(findings and unit timings, as the runner produced them); `assemble` turns them, with the match adjudications, into
results/eval/<system>/<baseline>.json (the findings schema) and <baseline>.timing.json.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path, PurePosixPath

from .. import common, gitfacts

ROOT = common.ROOT
LIB = common.LIB
PROTOCOL_PATH = LIB / "I52_baselines.json"
ANCHORS_PATH = LIB / "I52_morph_anchors.json"
SCHEMA_PATH = LIB / "I52_findings.schema.json"
REVIEW_PROMPT = LIB / "I52_review_prompt.md"
MATCH_PROMPT = LIB / "I52_match_prompt.md"
CORPUS = common.EVAL / "corpus.json"
RESULTS = ROOT / "results" / "eval"
HOME = common.HOME / "baselines"
RAW = HOME / "raw"
WORK = HOME / "work"
TOOLS = Path.home() / ".holon" / "tools"
PY = TOOLS / "baselines-py" / "bin"
BASELINES = ("slither", "echidna", "medusa", "hevm", "halmos", "go_fuzz", "two_cycle", "spec_mining", "agent_review")
SOLIDITY = ("slither", "echidna", "medusa", "hevm", "halmos")
GO = ("go_fuzz", "two_cycle")
WINDOW = 10
MAX_SPAN = 150
SCHEMA = "holon-baseline-findings/0.1"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def protocol() -> dict:
    return load(PROTOCOL_PATH)


def protocol_sha256() -> str:
    return common.sha256_file(PROTOCOL_PATH)


def anchors() -> dict:
    return load(ANCHORS_PATH)["obstructions"]


def entries() -> list[dict]:
    return load(CORPUS)["entries"]


def entry(eid: str) -> dict:
    return next(e for e in entries() if e["id"] == eid)


def systems() -> tuple:
    return tuple(protocol()["systems"])


def pinned(system: str) -> bool:
    """A pinned system is one repository at one commit (the protocol's systems.<s>.repo, checked out from the
    config's replay.<s>); the others are manifests of entries (systems.<s>.manifest)."""
    return "repo" in protocol()["systems"].get(system, {})


def config() -> dict:
    return load(ROOT / "config" / "holon.json")


# ------------------------------------------------------------------------------------------------- budget
def holon_budget_path() -> Path:
    return RESULTS / "holon_budget.json"


def budget(system: str) -> dict:
    b = dict(protocol()["budget"][system])
    if "wall_s_rule" in b:
        hb = load(holon_budget_path()) if holon_budget_path().is_file() else {}
        if f"{system}_wall_s" not in hb:
            raise common.Refused(f"the {system} budget waits for its HOLON measurement (holon_budget.{system})")
        b = {"wall_s": hb[f"{system}_wall_s"], "cpus": b["cpus"], "setup_cap_s": b["setup_cap_s"]}
    return b


def rule_wall_s(h: float) -> int:
    """60 * ceil(H / 60), over H in milliseconds so float noise cannot move it."""
    return 60 * -(-int(round(h * 1000)) // 60000)


# ------------------------------------------------------------------------------------------------- targets and scope
def targets(system: str) -> list[str]:
    if pinned(system):
        return list(protocol()["systems"][system]["targets"])
    if system == "corpus":
        return [e["id"] for e in entries()]
    raise common.Refused("the held-out system is pending I49/I50; this session never reads spec/heldout/")


def labelled_files(system: str, target: str) -> list[str]:
    if pinned(system):
        return sorted({a["file"] for o in anchors().values() for a in o["anchors"]})
    return list(entry(target)["files"])


def scope_dirs(system: str, target: str) -> list[str]:
    return sorted({PurePosixPath(f).parent.as_posix() for f in labelled_files(system, target)})


def is_test(path: str) -> bool:
    return gitfacts.test_path(path, common.protocol())


def languages(system: str, target: str) -> set:
    if pinned(system):
        return {"go" if f.endswith(".go") else "solidity" for f in labelled_files(system, target)}
    return set(entry(target)["languages"])


def applicable(baseline: str, system: str, target: str) -> bool:
    langs = languages(system, target)
    if baseline in SOLIDITY:
        return "solidity" in langs
    if baseline in GO:
        return "go" in langs
    return True


def scope_files(src: Path, system: str, target: str, ext: str | None = None) -> list[str]:
    """Every non-test .go/.sol file directly inside a scope directory of the checkout src."""
    out = []
    for d in scope_dirs(system, target):
        base = src / d if d != "." else src
        if not base.is_dir():
            continue
        for p in sorted(base.iterdir()):
            if p.is_file() and p.suffix in (".go", ".sol") and (ext is None or p.suffix == ext):
                rel = p.relative_to(src).as_posix()
                if not is_test(rel):
                    out.append(rel)
    return out


# ------------------------------------------------------------------------------------------------- checkouts
_LOCK = threading.Lock()
_TARGET_LOCKS: dict = {}


def target_lock(system: str, target: str) -> threading.RLock:
    """One re-entrant lock per target: the setup steps that write into a target's shared trees (the unit projects, the
    Go harness files) run one at a time, while the baselines' bounded runs stay concurrent."""
    with _LOCK:
        return _TARGET_LOCKS.setdefault((system, target), threading.RLock())


def commit_of(system: str, target: str) -> str:
    if pinned(system):
        return load(ANCHORS_PATH)["commit"]
    return entry(target)["prefix_commit"]


def checkout(system: str, target: str) -> Path:
    """The target's source tree at its commit (created once, shared by the baselines): Morph a shared clone of the
    pinned checkout; a corpus entry a detached worktree of holon's partial clone of the manifest's URL."""
    dest = WORK / system / target / "src"
    if (dest / ".holon-ready").exists():
        return dest
    with _LOCK:
        if (dest / ".holon-ready").exists():  # made by another thread while this one waited
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(dest, ignore_errors=True)
        sha = commit_of(system, target)
        if pinned(system):
            pin = config()["replay"][system]
            common.git(dest.parent, "clone", "-q", "--shared", "--no-checkout", pin, str(dest))
            common.git(dest, "checkout", "-q", "--detach", sha)
        else:
            e = entry(target)
            d = common.repo_cache(e["repo"])
            subprocess.run(["git", "-C", str(d), "worktree", "prune"], capture_output=True)
            common.git(d, "worktree", "add", "-f", "--detach", str(dest), sha, timeout=7200)
        if common.git(dest, "rev-parse", "HEAD").strip() != sha:
            raise RuntimeError(f"{target}: checkout is not at {sha}")
        (dest / ".holon-ready").write_text(sha + "\n")
    return dest


def submodules_list(src: Path) -> list[dict]:
    """The checkout's submodules with their gitlinked commits (clone_rule); an excluded URL is refused."""
    if not (src / ".gitmodules").is_file():
        return []
    out = []
    cfg = common.git(src, "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.url$", check=False)
    for line in cfg.splitlines():
        key, url = line.split(None, 1)
        if common.excluded(url):
            raise common.Refused(f"submodule {url} is an excluded repository")
        name = key[len("submodule."):-len(".url")]
        path = common.git(src, "config", "-f", ".gitmodules", "--get", f"submodule.{name}.path").strip()
        ls = common.git(src, "ls-tree", "HEAD", "--", path, check=False).split()
        if len(ls) < 3 or ls[1] != "commit":
            continue
        out.append({"path": path, "url": url, "commit": ls[2]})
    return out


def fetch_submodules(src: Path, subs: list[dict]) -> list[dict]:
    """Fetch each submodule at its gitlinked commit (recursively for its own submodules)."""
    for s in subs:
        if (src / s["path"] / ".git").exists():
            s["fetched"] = True
            continue
        p = subprocess.run(["git", "-C", str(src), "submodule", "update", "--init", "--recursive", "--", s["path"]],
                           capture_output=True, text=True, timeout=3600, env=common.git_env())
        s["fetched"] = p.returncode == 0
        if not s["fetched"]:
            s["error"] = p.stderr.strip()[-300:]
    return subs


# ------------------------------------------------------------------------------------------------- the bounded runner
CORES = [1, 2, 3] if (os.cpu_count() or 1) >= 4 else [0]
_core_sem = threading.Semaphore(len(CORES))
_free = list(CORES)
_free_lock = threading.Lock()


class Core:
    """One CPU core held for a target's analysis (released on exit)."""

    def __enter__(self):
        _core_sem.acquire()
        with _free_lock:
            self.core = _free.pop(0)
        return self.core

    def __exit__(self, *exc):
        with _free_lock:
            _free.append(self.core)
        _core_sem.release()


def run_bounded(argv: list[str], cwd: Path, wall_s: float, core: int | None, env: dict | None = None,
                log: Path | None = None) -> dict:
    """argv pinned to one core (taskset), killed (its whole process group) at wall_s. Returns exit, wall_s, cpu_s
    (rusage of the process tree), timed_out and the output (stdout+stderr, also written to log)."""
    e = {**os.environ, "GOMAXPROCS": "1", "BEND_NO_TELEMETRY": "1", **(env or {})}
    full = (["taskset", "-c", str(core)] if core is not None else []) + argv
    log = log or Path(cwd) / ".holon-run.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    with open(log, "wb") as out:
        p = subprocess.Popen(full, cwd=str(cwd), env=e, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        timed_out, status, ru = False, None, None
        while True:
            pid, status, ru = os.wait4(p.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() - t0 > max(wall_s, 1):
                timed_out = True
                for sig, wait in ((signal.SIGTERM, 10), (signal.SIGKILL, 0)):
                    try:
                        os.killpg(p.pid, sig)
                    except ProcessLookupError:
                        pass
                    end = time.monotonic() + wait
                    while time.monotonic() < end:
                        pid, status, ru = os.wait4(p.pid, os.WNOHANG)
                        if pid:
                            break
                        time.sleep(0.2)
                    if pid:
                        break
                if not pid:
                    _, status, ru = os.wait4(p.pid, 0)
                break
            time.sleep(0.2)
        p.returncode = os.waitstatus_to_exitcode(status)
    try:  # stragglers of the group
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    wall = time.monotonic() - t0
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", log.read_bytes().decode("utf-8", errors="replace"))
    return {"exit": p.returncode, "wall_s": round(wall, 3), "cpu_s": round(ru.ru_utime + ru.ru_stime, 3),
            "timed_out": timed_out, "output": text, "argv": full}


def run_setup(argv: list[str], cwd: Path, timeout: float = 3600, env: dict | None = None) -> tuple[int, str, float]:
    t0 = time.monotonic()
    try:
        p = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **(env or {})})
        return p.returncode, (p.stdout + p.stderr), time.monotonic() - t0
    except subprocess.TimeoutExpired as ex:
        return 124, f"setup timed out after {timeout} s: {ex}", time.monotonic() - t0


class Units:
    """Sequential units over one target's wall budget: each gets the time left divided by the units left."""

    def __init__(self, wall_s: float, n: int):
        self.left, self.n, self.used = float(wall_s), max(n, 1), []

    def share(self) -> float:
        return max(self.left / self.n, 1.0)

    def done(self, name: str, wall: float, cpu: float | None, **extra) -> None:
        self.left -= wall
        self.n = max(self.n - 1, 1)
        self.used.append({"name": name, "wall_s": round(wall, 3), "cpu_s": None if cpu is None else round(cpu, 3),
                          **extra})


# ------------------------------------------------------------------------------------------------- findings
def finding(kind: str, message: str, locations: list[dict], severity: str | None = None, evidence=None) -> dict:
    f = {"kind": kind, "message": message, "locations": locations, "severity": severity}
    if evidence is not None:
        f["evidence"] = evidence
    return f


def loc(file: str, a: int, b: int | None = None, function: str | None = None) -> dict:
    return {"file": file, "lines": [int(a), int(b if b is not None else a)], "function": function}


def normalise(findings: list[dict], scope: set[str]) -> list[dict]:
    """Keep the locations in scope files (a finding with none left is dropped), dedupe, sort, number f0001.."""
    seen, out = set(), []
    for f in findings:
        locs = [l for l in f["locations"] if l["file"] in scope]
        if not locs:
            continue
        locs = sorted({json.dumps(l, sort_keys=True) for l in locs})
        g = dict(f, locations=[json.loads(x) for x in locs])
        k = json.dumps({k: g.get(k) for k in ("kind", "message", "locations", "severity")}, sort_keys=True)
        if k in seen:
            continue
        seen.add(k)
        out.append(g)
    out.sort(key=lambda g: (g["locations"][0]["file"], g["locations"][0]["lines"], g["kind"], g["message"]))
    for i, g in enumerate(out, 1):
        g["id"] = f"f{i:04d}"
    return [{k: g[k] for k in ("id", "kind", "severity", "message", "locations", *(["evidence"] if "evidence" in g else []))}
            for g in out]


# ------------------------------------------------------------------------------------------------- matching
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@", re.M)
_FIXLINES: dict = {}


def fix_lines(e: dict, path: str) -> list[int]:
    key = (e["id"], path)
    if key not in _FIXLINES:
        d = common.repo_cache(e["repo"])
        out = common.git(d, *gitfacts.DIFF_OPTIONS, "-U0", e["prefix_commit"], e["fix_commit"], "--", path,
                         text=False).decode("utf-8", errors="replace")
        lines = set()
        for m in _HUNK.finditer(out):
            a = int(m.group(1))
            n = int(m.group(2)) if m.group(2) is not None else 1
            lines.update((a, a + 1) if n == 0 else range(a, a + n))
        _FIXLINES[key] = sorted(lines)
    return _FIXLINES[key]


def _meets(span, lo, hi) -> bool:
    a, b = span
    if b - a + 1 > MAX_SPAN:
        b = a
    return a <= hi and lo <= b


def located(system: str, target: str, f: dict) -> list[str]:
    if pinned(system):
        out = []
        for oid, o in anchors().items():
            if any(l["file"] == a["file"] and _meets(l["lines"], *a["lines"]) for a in o["anchors"] for l in f["locations"]):
                out.append(oid)
        return sorted(out, key=lambda k: int(k[1:]))
    e = entry(target)
    for l in f["locations"]:
        if l["file"] in e["files"] and any(_meets(l["lines"], x - WINDOW, x + WINDOW) for x in fix_lines(e, l["file"])):
            return [target]
    return []


def label_key(k: str):
    return (k[0], int(k[1:]))


# ------------------------------------------------------------------------------------------------- raw records
def raw_path(system: str, baseline: str, target: str) -> Path:
    return RAW / system / baseline / f"{target}.json"


def write_raw(system: str, baseline: str, target: str, rec: dict) -> None:
    p = raw_path(system, baseline, target)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")


def raw(system: str, baseline: str, target: str) -> dict | None:
    p = raw_path(system, baseline, target)
    return load(p) if p.exists() else None


def tail(text: str, n: int = 1500) -> str:
    return text[-n:]


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()
