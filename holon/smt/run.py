"""The pinned z3 (spec/M3/lib/refute.json "solver"; config/holon.json "z3"; Q16): checked by sha256 before every run,
random_seed 0, one thread, z3's deterministic rlimit per query (never a wall-clock timeout).

  pin_check(solver) -> None | reason      the binary's and the library's sha256 and the version line
  Session(solver).check(text) -> "sat" | "unsat" | "unknown"
  Session.values([terms]) -> {term: int}  values of a sat query's terms (bit-vectors as ints, Bools as 0/1)
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path


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
    return None


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


class Session:
    """One interactive z3 process for one query: check, then read values."""

    def __init__(self, solver: dict):
        self.solver = solver
        self.p = None

    def check(self, text: str) -> str:
        self.p = subprocess.Popen([self.solver["binary"], "-in", "-smt2", "parallel.enable=false"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                  bufsize=1)
        self.p.stdin.write(text)
        self.p.stdin.write('(echo "@@done")\n')
        self.p.stdin.flush()
        lines = []
        while True:
            line = self.p.stdout.readline()
            if not line:
                break
            if line.strip() == "@@done":
                break
            lines.append(line.strip())
        res = [x for x in lines if x in ("sat", "unsat", "unknown")]
        errs = [x for x in lines if x.startswith("(error")]
        if errs:
            self.close()
            raise RuntimeError(f"z3: {errs[0][:400]}")
        return res[-1] if res else "unknown"

    def values(self, terms: list[str], chunk: int = 256) -> dict[str, int]:
        out = {}
        for i in range(0, len(terms), chunk):
            part = terms[i:i + chunk]
            self.p.stdin.write("(get-value (" + " ".join(part) + "))\n(echo \"@@done\")\n")
            self.p.stdin.flush()
            buf = []
            while True:
                line = self.p.stdout.readline()
                if not line or line.strip() == "@@done":
                    break
                buf.append(line)
            text = "".join(buf).strip()
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
        self.p.stdin.write("(get-info :reason-unknown)\n(echo \"@@done\")\n")
        self.p.stdin.flush()
        buf = []
        while True:
            line = self.p.stdout.readline()
            if not line or line.strip() == "@@done":
                break
            buf.append(line.strip())
        return " ".join(buf)

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
            self.p = None
