"""The pinned z3 (spec/M3/lib/refute.json "solver"; config/holon.json "z3"; Q16): checked by sha256 before every run,
random_seed 0, one thread, z3's deterministic rlimit per query, counted cumulatively over the query's check-sats, and
z3's own memory_max_size (registered in config). Nothing answers by wall-clock time: the crash watchdog aborts.

z3 accounts memory_max_size in bytes as glibc's malloc reports them (malloc_usable_size), so the cap is a function of
the query alone only on the registered glibc (config/holon.json z3 "glibc"), with no malloc tunables or preloads (z3
runs with the fixed environment Z3_ENV) and with nothing else able to fail an allocation first: no address-space or
data rlimit, no strict overcommit (environment_check, part of pin_check and of every session start). An allocation
the kernel refuses in any other way ends z3 without an answer (the OOM killer): SolverCrash, nothing recorded.

  pin_check(solver) -> None | reason      the binary's and the library's sha256, the version line, environment_check
  environment_check() -> None | reason    the registered glibc; no address-space or data rlimit; no strict overcommit
  Session(solver).check(text) -> "sat" | "unsat" | "unknown"
  Session.values([terms]) -> {term: int}  values of a sat query's terms (bit-vectors as ints, Bools as 0/1)
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

# z3's whole environment: no GLIBC_TUNABLES, MALLOC_*, LD_PRELOAD or LD_LIBRARY_PATH reaches the solver (its memory
# accounting follows glibc's malloc; the binary links nothing but the system C and C++ runtimes)
Z3_ENV = {"LC_ALL": "C"}


class SolverPinError(RuntimeError):
    pass


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pin_check(solver: dict) -> str | None:
    """None when the pinned solver is installed as pinned, else the reason it is not."""
    b, lib = Path(solver["binary"]), Path(solver["library"])
    if not b.is_file():
        return f"no solver binary at {b}"
    if sha256_file(b) != solver["binary_sha256"]:
        return f"{b}: sha256 differs from the pin"
    if not lib.is_file() or sha256_file(lib) != solver["library_sha256"]:
        return f"{lib}: missing or its sha256 differs from the pin"
    try:
        v = subprocess.run([str(b), "--version"], capture_output=True, text=True, timeout=60).stdout
    except OSError as e:
        return f"{b}: {e}"
    if f"Z3 version {solver['version']}" not in v:
        return f"{b}: version line {v.strip()!r}, pinned {solver['version']}"
    return environment_check()


_ENV_CHECKED: list = []


def environment_check(root: Path | None = None) -> str | None:
    """None when this machine runs z3 as the registered memory cap assumes, else the reason it does not: the
    registered glibc (z3 accounts memory_max_size with glibc's malloc_usable_size), no address-space or data rlimit
    and no strict overcommit (either makes an allocation fail before z3's own cap, and z3 then prints the cap's
    message)."""
    import json
    import resource
    if _ENV_CHECKED and root is None:
        return _ENV_CHECKED[0]
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    z = (json.loads((root / "config" / "holon.json").read_text(encoding="utf-8")).get("z3") or {})
    why = None
    try:
        libc = os.confstr("CS_GNU_LIBC_VERSION")
    except (ValueError, OSError):
        libc = None
    if libc != z.get("glibc"):
        why = f"C library {libc!r}, registered {z.get('glibc')!r} (z3's memory accounting follows glibc's malloc)"
    for name in ("RLIMIT_AS", "RLIMIT_DATA"):
        soft, _hard = resource.getrlimit(getattr(resource, name))
        if why is None and soft != resource.RLIM_INFINITY:
            why = f"{name} is {soft} bytes: an allocation could fail before z3's registered memory_max_size"
    try:
        oc = Path("/proc/sys/vm/overcommit_memory").read_text().strip()
    except OSError as e:
        oc = f"unreadable ({e})"
    if why is None and oc not in ("0", "1"):
        why = f"vm.overcommit_memory is {oc}: an allocation could fail before z3's registered memory_max_size"
    if root == Path(__file__).resolve().parents[2]:
        _ENV_CHECKED[:] = [why]
    return why


class SolverEnvironment(RuntimeError):
    """This machine cannot run z3 as registered (environment_check): no query is run and nothing is recorded."""


_VAL = re.compile(r"\(\((.*)\)\)\s*$", re.S)


def _tokens(s: str) -> list:
    """The top-level s-expressions and atoms of s."""
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            d, j = 0, i
            while j < n:
                d += s[j] == "("
                d -= s[j] == ")"
                j += 1
                if d == 0:
                    break
            out.append(s[i:j])
            i = j
        else:
            j = i
            while j < n and not s[j].isspace() and s[j] not in "()":
                j += 1
            out.append(s[i:j])
            i = j
    return out


def parse_value(v: str) -> int:
    v = v.strip()
    if v == "true":
        return 1
    if v == "false":
        return 0
    if v.startswith("#x"):
        return int(v[2:], 16)
    if v.startswith("#b"):
        return int(v[2:], 2)
    m = re.match(r"\(_ bv(\d+) \d+\)", v)
    if m:
        return int(m.group(1))
    raise ValueError(f"unparsed solver value {v[:80]}")


class WatchdogAbort(RuntimeError):
    """The crash watchdog fired: the run is aborted, no verdict is recorded and the question is run again later."""


class SolverCrash(RuntimeError):
    """z3 ended without an answer (a crash, killed from outside, or its pipe closed): never a verdict; nothing is
    recorded."""


def registered_limits(root: Path | None = None) -> dict:
    """The registered solver limits beyond the sidecar's rlimit (config/holon.json "z3"): memory_max_size_mb, z3's own
    allocation count (deterministic for the pinned single-threaded binary; an overrun ends the query unknown), and
    watchdog_s, a crash guard that aborts the run (never a verdict); e1_rounds_max and hash_rounds_max, BMC's
    deterministic round caps for lazy E1 and hash concretization (a cap reached ends the query unknown)."""
    import json
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    z = (json.loads((root / "config" / "holon.json").read_text(encoding="utf-8")).get("z3") or {})
    return {k: z.get(k) for k in ("memory_max_size_mb", "watchdog_s", "e1_rounds_max", "hash_rounds_max")}


class Session:
    """One interactive z3 process for one query: check, then read values.

    The budget is the query's rlimit, counted CUMULATIVELY over every check-sat of the session (the incremental E1
    rounds and the hash concretization rounds included): z3's (get-info :rlimit) is the count since the process
    started, and each further check-sat gets only the remainder, so a query never spends more than its rlimit and the
    answer does not depend on load or wall-clock time. memory_mb is z3's memory_max_size (registered in config); the
    watchdog only aborts (WatchdogAbort), it never answers."""

    def __init__(self, solver: dict, rlimit: int | None = None, memory_mb: int | None = None,
                 watchdog_s: float | None = None):
        self.solver = solver
        self.rlimit = int(rlimit if rlimit is not None else solver["rlimit_per_query"])
        lim = registered_limits()
        self.memory_mb = memory_mb if memory_mb is not None else lim["memory_max_size_mb"]
        self.watchdog_s = watchdog_s if watchdog_s is not None else lim["watchdog_s"]
        self.p = None
        self.guard = None
        self.used = 0

    def _start(self):
        why = environment_check()
        if why:
            raise SolverEnvironment(f"z3 not started: {why}")
        args = [self.solver["binary"], "-in", "-smt2", "parallel.enable=false"]
        if self.memory_mb:
            args.append(f"memory_max_size={int(self.memory_mb)}")
        self.p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  text=True, bufsize=1, env=dict(Z3_ENV))

    def _crash(self, where: str):
        rc = self.p.poll() if self.p is not None else None
        self.close()
        raise SolverCrash(f"z3 ended without an answer during {where} (exit {rc}): a crash is never a verdict")

    def _write(self, text: str, where: str) -> None:
        if self.p is None:
            raise SolverCrash(f"z3 is not running ({where}): a crash is never a verdict")
        try:
            self.p.stdin.write(text)
            self.p.stdin.flush()
        except (BrokenPipeError, OSError):
            self._crash(where)

    def _read_until_done(self, where: str) -> list:
        buf = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                self._crash(where)
            if line.strip() == "@@done":
                return buf
            buf.append(line)

    def _timed(self, fn):
        import threading
        fired = []
        timer = None
        if self.watchdog_s:
            def fire(proc=self.p):
                fired.append(1)
                proc.kill()
            timer = threading.Timer(float(self.watchdog_s), fire)
            timer.start()
        try:
            out = fn()
        except (BrokenPipeError, OSError, RuntimeError):
            if fired:
                self.close()
                raise WatchdogAbort(f"the crash watchdog ({int(self.watchdog_s)} s) fired: no verdict") from None
            raise
        finally:
            if timer is not None:
                timer.cancel()
        if fired:
            raise WatchdogAbort(f"the crash watchdog ({int(self.watchdog_s)} s) fired: no verdict")
        return out

    def count(self) -> int:
        """z3's cumulative resource count of this session."""
        self._write("(get-info :rlimit)\n(echo \"@@done\")\n", "get-info :rlimit")
        buf = [x.strip() for x in self._read_until_done("get-info :rlimit")]
        m = re.search(r":rlimit\s+(\d+)", " ".join(buf))
        if not m:
            raise RuntimeError(f"z3 get-info :rlimit: {' '.join(buf)[:200]}")
        return int(m.group(1))

    def check(self, text: str) -> str:
        """sat | unsat | unknown for the query text (its header sets :rlimit, the whole budget, for this first
        check-sat)."""
        self.guard = None
        self._start()
        return self._timed(lambda: self._account(self._check(text)))

    def more(self, text: str) -> str:
        """Further declarations and assertions on the open query, then (check-sat) again (incremental), with only the
        remainder of the query's rlimit."""
        if self.guard is not None:
            return "unknown"
        rest = self.rlimit - self.used
        if rest <= 0:
            self.guard = f"rlimit {self.rlimit} spent (cumulative over the query's check-sats)"
            return "unknown"
        return self._timed(lambda: self._account(self._check(f"(set-option :rlimit {rest})\n" + text +
                                                             "(check-sat)\n")))

    def _account(self, res: str) -> str:
        if self.p is None or self.p.poll() is not None:
            return res
        self.used = self.count()
        if res == "unknown" and self.guard is None and self.used >= self.rlimit:
            self.guard = f"rlimit {self.rlimit} spent (cumulative over the query's check-sats)"
        return res

    def send(self, text: str) -> None:
        """Declarations or definitions on the open query (no check)."""
        self._write(text + '(echo "@@done")\n', "a declaration")
        for line in self._read_until_done("a declaration"):
            if line.startswith("(error"):
                raise RuntimeError(f"z3: {line.strip()[:300]}")

    def _check(self, text: str) -> str:
        try:
            self.p.stdin.write(text)
            self.p.stdin.write('(echo "@@done")\n')
            self.p.stdin.flush()
        except (BrokenPipeError, OSError):
            self._crash("a check-sat")
        lines = []
        eof = False
        while True:
            line = self.p.stdout.readline()
            if not line:
                eof = True
                break
            if line.strip() == "@@done":
                break
            lines.append(line.strip())
        res = [x for x in lines if x in ("sat", "unsat", "unknown")]
        errs = [x for x in lines if x.startswith("(error")]
        if errs and "out of memory" in errs[0]:
            # the registered cap (environment_check rules out every other way an allocation fails with this message)
            self.guard = (f"memory_max_size {self.memory_mb} MB (z3's own allocation count, registered in "
                          f"config/holon.json z3)")
            self.close()
            return "unknown"
        if eof:
            # the output ended before the session's end marker: whatever z3 printed, a crash is never a verdict
            self._crash("a check-sat")
        if errs:
            self.close()
            raise RuntimeError(f"z3: {errs[0][:400]}")
        return res[-1] if res else "unknown"

    def values(self, terms: list[str], chunk: int = 256) -> dict[str, int]:
        out = {}
        for i in range(0, len(terms), chunk):
            part = terms[i:i + chunk]
            self._write("(get-value (" + " ".join(part) + "))\n(echo \"@@done\")\n", "get-value")
            text = "".join(self._read_until_done("get-value")).strip()
            if text.startswith("(error"):
                raise RuntimeError(f"z3 get-value: {text[:300]}")
            inner = text[1:-1]
            pairs = _tokens(inner)
            if len(pairs) != len(part):
                raise RuntimeError(f"z3 get-value: {len(pairs)} values for {len(part)} terms")
            for t, pr in zip(part, pairs):
                toks = _tokens(pr[1:-1])
                out[t] = parse_value(toks[-1])
        return out

    def reason(self) -> str:
        self._write("(get-info :reason-unknown)\n(echo \"@@done\")\n", "get-info :reason-unknown")
        return " ".join(x.strip() for x in self._read_until_done("get-info :reason-unknown"))

    def close(self):
        if self.p is not None:
            try:
                self.p.stdin.close()
            except OSError:
                pass
            try:
                self.p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.p.kill()
                self.p.wait()
            if self.p.stdout is not None:
                self.p.stdout.close()
            self.p = None
