"""holon.kcache: the kernels' verdict cache for G2's re-checks of committed equivalence proofs (pipeline v2, E).

G2 re-checks every committed binding_change proof in bend2 and in BendTT on every run (F31, F33, F38). Measured
locally on the lead at 6f10b773, that is 1923 of G2's 2090 s: 3 proofs, about 210 s in bend2 and 430 s in BendTT
each. A committed proof never changes (its directory is named by its sha256) and the kernels are pinned, so the same
bytes under the same checker get the same verdict. This module remembers acceptances.

Nothing in the generator closure imports this module (holon.records.generator_files), so it re-stamps no record. It
acts only on a process run under it:

    python -m holon.kcache --dir DIR -m holon gate --milestone M3 --checks G2 ...
    python -m holon.kcache --dir DIR -m unittest tests_m3.test_catalog_rederivation -v

where it wraps holon.bend.check_equivalence for that process. CI runs the two jobs that re-check M3's proofs this
way, with DIR restored from the Actions cache and saved back to it. Nothing else reads DIR.

The key is the sha256 of the canonical JSON of:
  - the kernel ("bend2" or "BendTT") and the proof file's name;
  - the proof's Bend import closure: every file it imports by a relative path, recursively, by its path relative to
    the proof's directory, with its sha256. A bare import (Base) is the checker's library, inside its fingerprint,
    and a sibling file of that name (Base.bend) joins the closure too. A relative import that names no file leaves
    the check uncached;
  - the checker: holon.bend.fingerprint() (checkout HEAD, the bend2 sources with Base and bendtt.lean, bun and its
    bytes) and, for BendTT, the sha256 of the kernel binary --verdict executes;
  - equivalence.timeout_s, and the sha256 of holon/bend.py, which runs the kernels and reads their verdicts.

Only an acceptance is stored (Run.ok: exit 0 and the first line ALL PROOFS CHECK), with the run that produced it
(GITHUB_RUN_ID, GITHUB_SHA, ...). A rejection, a timeout and a crash are never stored, so they run again every time.
An entry whose key does not recompute from its own fields, or whose output is not an acceptance, is ignored.

Trust: an entry says that the pinned kernels accepted these bytes in a CI run. Only workflow runs write the Actions
cache. A pull request's run reads its base branch's entries and writes to its own scope, so poisoning the lead's
entries takes a workflow change pushed to the lead, which the history shows. An entry is still only CI's word, so a
milestone exit re-checks without the cache (the gate run without this wrapper), and `python -m holon.kcache audit
DIR` lists every entry with the run that produced it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import runpy
import sys
import tempfile
import threading
from pathlib import Path

VERSION = 1
IMPORT = re.compile(r"(?m)^[ \t]*import[ \t]+(\S+)")
CI_VARS = ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "GITHUB_REF", "GITHUB_JOB", "GITHUB_REPOSITORY",
           "GITHUB_WORKFLOW")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _canon(x) -> bytes:
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def closure(proof: Path) -> dict:
    """{path relative to the proof's directory: sha256, or None when the file is missing} for the proof and every
    file it imports by a relative path, recursively. Bend resolves an import relative to the importing file. A bare
    name (Base) is the checker's library; a sibling file of that name joins the closure as well, so the key holds
    whichever of the two the kernel reads."""
    proof = Path(proof)
    base = proof.parent.resolve()
    seen: dict = {}
    todo = [proof.resolve()]
    while todo:
        p = todo.pop()
        rel = Path(os.path.relpath(p, base)).as_posix()
        if rel in seen:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            seen[rel] = None
            continue
        seen[rel] = _sha(data)
        for m in IMPORT.finditer(data.decode("utf-8", errors="replace")):
            tok = m.group(1).strip("\"'")
            if "/" in tok or tok.endswith(".bend"):
                q = p.parent / tok
                if q.suffix != ".bend" and not q.is_file():
                    q = q.with_suffix(".bend")
                todo.append(q.resolve())
            elif re.fullmatch(r"[A-Za-z_][\w.]*", tok) and (p.parent / f"{tok}.bend").is_file():
                todo.append((p.parent / f"{tok}.bend").resolve())
    return dict(sorted(seen.items()))


def material(proof: Path, verdict: bool, ctx: dict) -> dict:
    """What the key hashes (see the module docstring). ctx: {"fingerprint", "kernel_sha256" (BendTT only),
    "timeout_s", "bend_py"}. Raises when an import names no file: what the kernel would read is then unknown."""
    cl = closure(proof)
    missing = sorted(k for k, v in cl.items() if v is None)
    if missing:
        raise FileNotFoundError(f"an import names no file: {', '.join(missing)}")
    return {"v": VERSION, "kernel": "BendTT" if verdict else "bend2", "proof": Path(proof).name,
            "closure": cl, "fingerprint": ctx["fingerprint"],
            "kernel_sha256": ctx.get("kernel_sha256") if verdict else None,
            "timeout_s": ctx["timeout_s"], "bend_py": ctx["bend_py"]}


def key_of(mat: dict) -> str:
    return _sha(_canon(mat))


class Cache:
    """One directory of entries, DIR/<key[:2]>/<key>.json. Thread-safe (holon.gen.eqsearch checks from threads)."""

    def __init__(self, d: Path, log=None):
        self.dir = Path(d).expanduser()
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log = log if log is not None else (lambda s: print(s, file=sys.stderr, flush=True))
        self.lock = threading.Lock()
        self.stats = {"hit": 0, "miss": 0, "stored": 0, "uncached": 0}

    def _count(self, k: str) -> None:
        with self.lock:
            self.stats[k] += 1

    def path(self, key: str) -> Path:
        return self.dir / key[:2] / f"{key}.json"

    def get(self, key: str, ok) -> dict | None:
        """The entry for key, if it is well formed, recomputes to key, and records an acceptance (ok(out))."""
        p = self.path(key)
        try:
            e = json.loads(p.read_text())
        except (OSError, ValueError):
            return None
        if not isinstance(e, dict) or e.get("key") != key or not isinstance(e.get("material"), dict) \
                or key_of(e["material"]) != key or not isinstance(e.get("out"), str) or not ok(e["out"]):
            return None
        return e

    def put(self, key: str, mat: dict, out: str, seconds: float, argv: list) -> None:
        e = {"key": key, "material": mat, "out": out, "seconds": seconds, "argv": [str(a) for a in argv],
             "run": {v: os.environ.get(v) for v in CI_VARS}}
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(json.dumps(e, sort_keys=True, indent=1) + "\n")
            os.replace(tmp, p)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def entries(self) -> list[tuple[Path, dict | None]]:
        out = []
        for p in sorted(self.dir.glob("??/*.json")):
            try:
                out.append((p, json.loads(p.read_text())))
            except (OSError, ValueError):
                out.append((p, None))
        return out


def wrap(real, cache: Cache, context, accepted, make_run):
    """check_equivalence with the cache in front of real (same signature and result: (Run, crash log)).
    context(cfg, verdict) -> ctx for material(), or raises when the checker cannot be identified (then real runs,
    uncached). accepted(out) -> bool: whether an output is an acceptance. make_run(out, seconds, argv) builds the
    Run a hit returns, in real's own Run class (argv and seconds are the producing run's)."""

    def check_equivalence(proof_file, cfg=None, verdict=False, tries=None):
        proof_file = Path(proof_file)
        kname = "BendTT" if verdict else "bend2"
        try:
            ctx = context(cfg, verdict)
            mat = material(proof_file, verdict, ctx)
            key = key_of(mat) if (not verdict or mat["kernel_sha256"]) else None
        except Exception as ex:  # noqa: BLE001  (no identity, no cache: the kernel runs as without it)
            cache._count("uncached")
            cache.log(f"holon.kcache: {kname} {proof_file}: not cached ({type(ex).__name__}: {ex})")
            return real(proof_file, cfg, verdict=verdict, tries=tries)
        if key is not None:
            e = cache.get(key, accepted)
            if e is not None:
                cache._count("hit")
                run = e.get("run") or {}
                cache.log(f"holon.kcache: hit {kname} {proof_file.name} {key[:16]} (accepted in run "
                          f"{run.get('GITHUB_RUN_ID')} at {str(run.get('GITHUB_SHA'))[:7]}, {e.get('seconds')} s)")
                return make_run(e["out"], e.get("seconds", 0.0), e.get("argv") or []), []
        cache._count("miss")
        r, log = real(proof_file, cfg, verdict=verdict, tries=tries)
        if not r.ok:
            return r, log
        try:   # the identity again: a file or the kernel binary that changed during the run stores nothing
            ctx2 = context(cfg, verdict)
            mat2 = material(proof_file, verdict, ctx2)
            key2 = key_of(mat2) if (not verdict or mat2["kernel_sha256"]) else None
        except Exception:  # noqa: BLE001
            key2 = None
        if key2 is not None and key2 == (key or key2) and accepted(r.out):
            cache.put(key2, mat2, r.out, r.seconds, list(r.argv or []))
            cache._count("stored")
            cache.log(f"holon.kcache: stored {kname} {proof_file.name} {key2[:16]} ({r.seconds} s)")
        return r, log

    check_equivalence.__wrapped__ = real
    return check_equivalence


def bend_context():
    """context() for the real checker: the fingerprint once per process (it hashes the checker's sources), the
    BendTT kernel binary's sha256 each time it is asked (it may be built by the first --verdict run)."""
    from . import bend as B
    memo: dict = {}
    lock = threading.Lock()
    bend_py = _sha(Path(B.__file__).read_bytes())

    def context(cfg, verdict):
        cfg = cfg or B.config()
        cmd = tuple(B.checker_cmd(cfg))
        with lock:
            if cmd not in memo:
                memo[cmd] = B.fingerprint(cfg)
            fp = memo[cmd]
        ctx = {"fingerprint": fp["fingerprint"], "timeout_s": B.equivalence_timeout(cfg), "bend_py": bend_py}
        if verdict:
            kb = B.verdict_kernel_path(Path(fp["checkout"]))   # I97 (F-M3-14): an inherited BENDTT is never used
            ctx["kernel_sha256"] = B.file_sha256(kb) if kb.is_file() else None
        return ctx
    return context


def install(cache: Cache) -> None:
    """Wrap holon.bend.check_equivalence in this process (callers look it up on the module at call time)."""
    from . import bend as B
    if getattr(B.check_equivalence, "__wrapped__", None) is not None:
        return
    B.check_equivalence = wrap(B.check_equivalence, cache, bend_context(), lambda out: B.Run(0, out, 0.0).ok,
                               lambda out, seconds, argv: B.Run(0, out, seconds, list(argv)))


def audit(d: Path, out=print) -> int:
    """Every entry with the run that produced it; nonzero when an entry is malformed or does not recompute."""
    c = Cache(d, log=lambda s: None)
    bad = 0
    for p, e in c.entries():
        ok = isinstance(e, dict) and isinstance(e.get("material"), dict) and key_of(e["material"]) == e.get("key") \
            == p.stem
        bad += not ok
        m = (e or {}).get("material") or {}
        run = (e or {}).get("run") or {}
        out(f"{'ok ' if ok else 'BAD'} {p.stem[:16]} {m.get('kernel')} {m.get('proof')} "
              f"{','.join(f'{k}:{str(v)[:8]}' for k, v in (m.get('closure') or {}).items())} "
              f"run={run.get('GITHUB_RUN_ID')}/{run.get('GITHUB_RUN_ATTEMPT')} sha={str(run.get('GITHUB_SHA'))[:7]} "
              f"ref={run.get('GITHUB_REF')} {(e or {}).get('seconds')} s")
    out(f"holon.kcache audit: {len(c.entries())} entries, {bad} bad")
    return 1 if bad else 0


def selftest() -> int:
    """The cache's contract on a stub kernel: a miss runs and stores, a hit does not run, any closure change, kernel
    binary or checker change misses, a rejection or a timeout is never stored, a tampered entry is ignored."""
    from dataclasses import dataclass, field

    @dataclass
    class R:
        code: int | None
        out: str
        seconds: float
        argv: list = field(default_factory=list)

        @property
        def ok(self) -> bool:
            return self.code == 0 and self.out.strip().splitlines()[:1] == ["ALL PROOFS CHECK"]

    with tempfile.TemporaryDirectory(prefix="holon-kcache-selftest-") as t:
        t = Path(t)
        work = t / "w"
        work.mkdir()
        (work / "pair.bend").write_text("import Base\ndef f() -> U32:\n  0\n")
        (work / "LAWS.bend").write_text("import Base\nimport ./pair.bend as P\n")
        (work / "PROOF.bend").write_text("import Base\nimport ./pair.bend as P\nimport ./LAWS.bend as Laws\n")
        (work / "junk.txt").write_text("not imported")
        calls = []
        verdicts = {"next": R(0, "ALL PROOFS CHECK\n", 3.0, ["bun", "main.ts", "PROOF.bend"])}

        def real(proof_file, cfg=None, verdict=False, tries=None):
            calls.append((Path(proof_file).name, verdict))
            return verdicts["next"], []

        ctx = {"fingerprint": "sha256:aa", "timeout_s": 900, "bend_py": "b0", "kernel_sha256": "k1"}
        cache = Cache(t / "c", log=lambda s: None)
        mk = lambda out, seconds, argv: R(0, out, seconds, list(argv))  # noqa: E731
        f = wrap(real, cache, lambda cfg, verdict: dict(ctx), lambda out: R(0, out, 0.0).ok, mk)
        P = work / "PROOF.bend"

        def check(cond, what):
            if not cond:
                raise AssertionError(f"holon.kcache selftest: {what}")

        r, _ = f(P)
        check(r.ok and calls == [("PROOF.bend", False)], "a miss runs the kernel")
        check(cache.stats["stored"] == 1, "an acceptance is stored")
        r, _ = f(P)
        check(r.ok and len(calls) == 1 and cache.stats["hit"] == 1, "a hit does not run the kernel")
        f(P, verdict=True)
        check(len(calls) == 2, "BendTT is keyed apart from bend2")
        f(P, verdict=True)
        check(len(calls) == 2, "BendTT hits too")
        (work / "junk.txt").write_text("changed, still not imported")
        f(P)
        check(len(calls) == 2, "a file outside the import closure is not in the key")
        (work / "pair.bend").write_text("import Base\ndef f() -> U32:\n  1\n")
        f(P)
        check(len(calls) == 3, "a change in an imported file misses")
        for k, v in (("fingerprint", "sha256:bb"), ("timeout_s", 300), ("bend_py", "b1")):
            old = ctx[k]
            ctx[k] = v
            n = len(calls)
            f(P)
            check(len(calls) == n + 1, f"a change of {k} misses")
            ctx[k] = old
        ctx["kernel_sha256"] = "k2"
        n = len(calls)
        f(P, verdict=True)
        check(len(calls) == n + 1, "a change of the BendTT kernel binary misses")
        n = len(calls)
        f(P)
        check(len(calls) == n, "bend2 does not depend on the BendTT kernel binary")
        ctx["kernel_sha256"] = None
        n = len(calls)
        f(P, verdict=True)
        f(P, verdict=True)
        check(len(calls) == n + 2, "an unknown BendTT kernel binary never hits")
        ctx["kernel_sha256"] = "k2"
        (work / "LAWS.bend").write_text("import Base\nimport ./pair.bend as P\n# rejected\n")
        for bad in (R(1, "ERROR\n", 2.0), R(None, "x\n[timeout]", 900.0), R(0, "something else\n", 1.0)):
            verdicts["next"] = bad
            n, s = len(calls), cache.stats["stored"]
            r1, _ = f(P)
            r2, _ = f(P)
            check(len(calls) == n + 2 and cache.stats["stored"] == s and not r1.ok and not r2.ok,
                  f"a non-acceptance ({bad.out.strip()[:20]!r}) is never stored")
        verdicts["next"] = R(0, "ALL PROOFS CHECK\n", 3.0)
        f(P)
        key = key_of(material(P, False, ctx))
        e = json.loads(cache.path(key).read_text())
        e["material"]["closure"]["PROOF.bend"] = "0" * 64
        cache.path(key).write_text(json.dumps(e))
        n = len(calls)
        f(P)
        check(len(calls) == n + 1, "an entry whose material does not hash to its key is ignored")
        e = json.loads(cache.path(key).read_text())
        e["out"] = "NOT AN ACCEPTANCE\n"
        cache.path(key).write_text(json.dumps(e))
        n = len(calls)
        f(P)
        check(len(calls) == n + 1, "an entry whose output is not an acceptance is ignored")
        (work / "Base.bend").write_text("def shadow() -> U32:\n  7\n")
        n = len(calls)
        f(P)
        check(len(calls) == n + 1 and "Base.bend" in material(P, False, ctx)["closure"],
              "a sibling file named by a bare import joins the key")
        (work / "pair.bend").unlink()
        n, u = len(calls), cache.stats["uncached"]
        f(P)
        f(P)
        check(len(calls) == n + 2 and cache.stats["uncached"] == u + 2,
              "an import that names no file: the kernel runs, uncached")

        def boom(cfg, verdict):
            raise RuntimeError("no checker")
        (work / "pair.bend").write_text("import Base\n")
        g = wrap(real, cache, boom, lambda out: R(0, out, 0.0).ok, mk)
        n, u = len(calls), cache.stats["uncached"]
        g(P)
        check(len(calls) == n + 1 and cache.stats["uncached"] == u + 1, "no identity: the kernel runs, uncached")
        check(audit(t / "c", out=lambda s: None) == 0, "every stored entry audits")
    print("holon.kcache selftest: ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    usage = ("usage: python -m holon.kcache --dir DIR (-m MODULE | SCRIPT) [ARGS...]\n"
             "       python -m holon.kcache audit DIR\n"
             "       python -m holon.kcache selftest")
    if argv[:1] == ["selftest"]:
        return selftest()
    if argv[:1] == ["audit"] and len(argv) == 2:
        return audit(Path(argv[1]))
    if len(argv) < 3 or argv[0] != "--dir":
        print(usage, file=sys.stderr)
        return 2
    d, rest = Path(argv[1]), argv[2:]
    cache = Cache(d)
    install(cache)
    try:
        if rest[0] == "-m" and len(rest) >= 2:
            sys.argv = [rest[1], *rest[2:]]
            runpy.run_module(rest[1], run_name="__main__", alter_sys=True)
        else:
            sys.argv = list(rest)
            runpy.run_path(rest[0], run_name="__main__")
        return 0
    finally:
        s = cache.stats
        print(f"holon.kcache: {s['hit']} hit(s), {s['miss']} miss(es), {s['stored']} stored, {s['uncached']} uncached "
              f"({cache.dir})", file=sys.stderr, flush=True)


if __name__ == "__main__":
    sys.exit(main())
