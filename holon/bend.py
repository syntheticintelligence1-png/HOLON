"""The pinned Bend 2 checker: configuration, invocation and environment safety.

Bend's verdicts are final (AGENTS.md rule 6), so everything here is about running the
*right* checker in a *clean* environment and reading its output strictly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK_OK = "ALL PROOFS CHECK"
MARK_FAIL = "SOME PROOFS FAIL"
# Bun reads bunfig.toml and .env, .env.local and .env.<NODE_ENV>[.local] from its working directory (I97, F-M3-14): a
# preload there runs inside the checker, and a variable there (BENDTT) reaches it. bunfig.toml and every name that
# starts with ".env" are refused (AGENTS.md rule 8, as holon/consumers.py reads it)
UNSAFE_ENV_FILES = ("bunfig.toml", ".env*")


def unsafe_env_name(name: str) -> bool:
    return name == "bunfig.toml" or name.startswith(".env")


def build_dir(root: Path | None = None) -> Path:
    """Where compiled models are cached. The gate sets HOLON_BUILD_DIR to a fresh directory so a
    regeneration (G1) or re-check never reuses a cache copied along with the tree."""
    env = os.environ.get("HOLON_BUILD_DIR")
    return Path(env) if env else Path(root or ROOT) / "build"


def config(root: Path | None = None) -> dict:
    root = Path(root or ROOT)
    p = root / "config" / "holon.json"
    if not p.exists():
        p = root / "config" / "holon.example.json"
    return json.loads(p.read_text())


def bend_cmd(cfg: dict | None = None) -> list[str]:
    env = os.environ.get("HOLON_BEND_CMD")
    if env:
        return shlex.split(env)
    return list((cfg or config())["bend"]["cmd"])


# I97 (F-M3-14): the checker's environment is an allowlist. Of the caller's environment only these names reach bun, and
# through it bend2, the Lean build of the kernel and the kernel itself. Everything else never does: BENDTT, BUN_OPTIONS
# and every BUN_* (extra flags such as --preload), NODE_* (NODE_ENV picks a .env.<NODE_ENV> file), BEND_LIB, BEND_HUB
# and BEND_ORIGIN (where bend2 resolves packages and its version check), CC, LD_*, and the rest
ENV_ALLOW = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE")


class EnvRefused(RuntimeError):
    """An environment or a working directory the checker must not run in (I97, F-M3-14). The message names why. It is
    never a verdict, and what it names is never silently used."""


_KERNEL_PATHS: dict = {}


def pinned_kernel_path(cfg: dict | None = None) -> Path | None:
    """The pinned toolchain's --verdict kernel: verdict_kernel_path of the resolved checkout (resolve_checker, the
    checkout fingerprint() hashes), or None when the checker cannot be resolved. Memoized by $HOME and the stat of
    the two source files the path is derived from."""
    try:
        _bun, checkout = resolve_checker(cfg)
        srcs = (checkout / "bend2" / "safe.ts", checkout / "bend2" / "bendtt.lean")
        key = (os.path.expanduser("~"),) + tuple((str(f), f.stat().st_mtime_ns, f.stat().st_size) for f in srcs)
        if key not in _KERNEL_PATHS:
            _KERNEL_PATHS[key] = verdict_kernel_path(checkout)
        return _KERNEL_PATHS[key]
    except (FingerprintError, OSError):
        return None


def checker_env(cfg: dict | None = None) -> dict:
    """The environment of every checker run (run, run_budgeted, fingerprint's `bun --version`, the classifier's kernel
    run): ENV_ALLOW from the caller's environment, then what HOLON sets itself.
      - PATH gains ~/.elan/bin: `--verdict` builds the BendTT kernel with Lean. Appended, never prepended: nothing in
        ~/.elan/bin may shadow a command (the checker itself always runs by absolute path, see checker_cmd).
      - BEND_NO_TELEMETRY=1: main.ts skips its daily version check (a network GET).
      - BUN_JSC_maxPerThreadStackUsage from the registered config (F38): the stack, so a deep or large file gets a
        verdict instead of "the machine stack overflowed" (the launcher raises the checker's RLIMIT_STACK to match, see
        _spawn_argv). No other JavaScriptCore option reaches the checker.
      - BENDTT = the pinned toolchain's kernel (pinned_kernel_path), once it is built. Until then bend2 builds it at that
        same path (safe.ts kernel_bin). A BENDTT inherited from the caller is never passed on: one that names another
        path raises EnvRefused, so an override is never silently used. GENV refuses any inherited BENDTT."""
    src = os.environ
    env = {k: src[k] for k in ENV_ALLOW if src.get(k)}
    elan = Path.home() / ".elan" / "bin"
    if elan.is_dir():
        env["PATH"] = os.pathsep.join(x for x in (env.get("PATH", ""), str(elan)) if x)
    env["BEND_NO_TELEMETRY"] = "1"
    env["BUN_JSC_maxPerThreadStackUsage"] = str(js_stack_bytes(cfg))
    kp = pinned_kernel_path(cfg)
    got = src.get("BENDTT")
    if got and (kp is None or os.path.realpath(got) != os.path.realpath(kp)):
        raise EnvRefused(f"BENDTT is set to {got!r}, not the pinned toolchain's --verdict kernel "
                         f"{str(kp) if kp is not None else '(unresolved)'}: an inherited kernel override is refused, "
                         "never used (unset BENDTT)")
    if kp is not None and kp.is_file():
        env["BENDTT"] = str(kp)
    return env


def _env(cfg: dict | None = None) -> dict:
    return checker_env(cfg)


def refuse_unsafe_cwd(cwd=None) -> None:
    """Raise EnvRefused when the working directory a checker run would get (cwd, else this process's) holds a name bun
    reads there (unsafe_env_name). Bun reads them from its working directory only, not from the file's directory or
    from a parent (I97's probe of bun 1.4.2)."""
    d = Path(cwd) if cwd is not None else Path.cwd()
    bad = sorted(p.name for p in d.iterdir() if unsafe_env_name(p.name))
    if bad:
        raise EnvRefused(f"the checker's working directory {d} holds {', '.join(bad)}, which bun would read: the run "
                         "is refused (AGENTS.md rule 8; I97, F-M3-14)")


# ------------------------------------------------------------------ checker fingerprint (I3, §8.8)
class FingerprintError(RuntimeError):
    """The bend command cannot be resolved to a bun + bend2/main.ts checkout, so it cannot be pinned."""


def _which(name: str) -> str | None:
    found = shutil.which(name)
    if found is None and os.sep in name and Path(name).is_file():
        found = name
    return os.path.realpath(found) if found else None


def _is_text_script(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return False
    return head.startswith(b"#!") and b"\0" not in head


def _parse_wrapper(path: str) -> tuple[str, str]:
    """(bun, main.ts) from a wrapper whose only command is `exec <bun> <.../bend2/main.ts> "$@"`.

    Strict on purpose: any other command in the wrapper (an export, a preload flag, a second
    exec) could change what runs, so it is refused rather than fingerprinted."""
    lines = [ln.strip() for ln in Path(path).read_text().splitlines()[1:]]
    lines = [ln for ln in lines if ln and not ln.startswith("#")]
    if len(lines) != 1:
        raise FingerprintError(f"{path}: expected a wrapper whose only command is "
                               f"`exec <bun> <checkout>/bend2/main.ts \"$@\"`, found {len(lines)} commands")
    try:
        toks = shlex.split(lines[0])
    except ValueError as e:
        raise FingerprintError(f"{path}: cannot parse {lines[0]!r}: {e}") from None
    if len(toks) != 4 or toks[0] != "exec" or toks[3] != "$@":
        raise FingerprintError(f"{path}: expected `exec <bun> <checkout>/bend2/main.ts \"$@\"`, found {lines[0]!r}")
    return toks[1], toks[2]


def _checkout_of(main_ts: str, origin: str) -> Path:
    m = Path(os.path.realpath(main_ts))
    if m.name != "main.ts" or m.parent.name != "bend2" or not m.is_file():
        raise FingerprintError(f"{origin}: {main_ts!r} is not an existing <checkout>/bend2/main.ts")
    return m.parent.parent


def resolve_checker(cfg: dict | None = None) -> tuple[str, Path]:
    """(bun binary, checkout root) of the checker `bend_cmd(cfg)` actually runs (HOLON_BEND_CMD included).

    Accepted forms: a wrapper script (followed through symlinks) whose only command is
    `exec <bun> <checkout>/bend2/main.ts "$@"`, or a command `[<bun>, <checkout>/bend2/main.ts]`.
    Anything else (an installer binary, a fake script, extra arguments) raises FingerprintError."""
    cmd = bend_cmd(cfg)
    if not cmd:
        raise FingerprintError("the bend command is empty")
    exe = _which(cmd[0])
    if exe is None:
        raise FingerprintError(f"bend command not found: {cmd[0]!r}")
    if _is_text_script(exe):
        if len(cmd) != 1:
            raise FingerprintError(f"extra arguments after the wrapper {cmd[0]!r} are not pinned: {cmd[1:]}")
        bun, main_ts = _parse_wrapper(exe)
        origin = exe
    elif len(cmd) == 2:
        bun, main_ts, origin = cmd[0], cmd[1], " ".join(cmd)
    else:
        raise FingerprintError(f"{' '.join(cmd)!r} resolves to {exe}, which is neither a bun wrapper over "
                               "<checkout>/bend2/main.ts nor `<bun> <checkout>/bend2/main.ts`")
    checkout = _checkout_of(main_ts, origin)
    bun_path = _which(bun)
    if bun_path is None or not os.access(bun_path, os.X_OK):
        raise FingerprintError(f"{origin}: bun {bun!r} not found or not executable")
    return bun_path, checkout


def checker_cmd(cfg: dict | None = None) -> list[str]:
    """The exact argv prefix every Bend run executes: [bun, <checkout>/bend2/main.ts], both absolute
    and realpath-resolved by resolve_checker (the wrapper itself is not executed: its one allowed
    command is exactly this). fingerprint() hashes this same pair, so PATH cannot substitute another
    checker between GENV and a check."""
    bun_path, checkout = resolve_checker(cfg)
    return [bun_path, str(checkout / "bend2" / "main.ts")]


FINGERPRINT_SOURCES = ("bend2/**/*.ts", "bend2/**/*.lean", "bend2/**/*.bend")


def sources_sha256(checkout: Path) -> str:
    """sha256 over (relative path, NUL, bytes, NUL) of every .ts, .lean and .bend file under bend2/
    (the checker, its proven kernel and its Base library), sorted by path."""
    checkout = Path(checkout)
    files = sorted({f for pat in FINGERPRINT_SOURCES for f in checkout.glob(pat) if f.is_file()},
                   key=lambda f: f.relative_to(checkout).as_posix())
    h = hashlib.sha256()
    for f in files:
        h.update(f.relative_to(checkout).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(cfg: dict | None = None) -> dict:
    """The identity of the checker run() executes (checker_cmd): checkout HEAD, its sources, the bun
    version and the bun executable's bytes.

    `fingerprint` = "sha256:" + sha256 of the canonical JSON of {head, sources_sha256, bun, bun_sha256};
    it is pinned as config bend.pinned_fingerprint. Deterministic: no timestamps, no absolute paths
    hashed. Also returned, unhashed: `checkout`, `bun_path` and `command` (the argv prefix run()
    executes, which GENV compares with what a run actually executed). A checkout that is not a git
    repository gets head "unknown" (and so will not match a pin). The --verdict kernel binary is
    pinned separately (verdict_kernel_path, bend.pinned_kernel_sha256)."""
    cfg = cfg or config()
    bun_path, checkout = resolve_checker(cfg)
    try:
        g = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True,
                           timeout=60)
        head = g.stdout.strip() if g.returncode == 0 and re.fullmatch(r"[0-9a-f]{40,64}", g.stdout.strip()) \
            else "unknown"
    except (OSError, subprocess.SubprocessError):
        head = "unknown"
    try:
        b = subprocess.run([bun_path, "--version"], capture_output=True, text=True, env=_env(cfg), timeout=60,
                           cwd=str(checkout))
    except (OSError, subprocess.SubprocessError) as e:
        raise FingerprintError(f"cannot run {bun_path} --version: {e}") from None
    bun_v = b.stdout.strip()
    if b.returncode != 0 or not bun_v:
        raise FingerprintError(f"{bun_path} --version failed: {(b.stdout + b.stderr)[:300]!r}")
    core = {"head": head, "sources_sha256": sources_sha256(checkout), "bun": bun_v,
            "bun_sha256": file_sha256(bun_path)}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
    return {"checkout": str(checkout), "bun_path": bun_path, "command": [bun_path, str(checkout / "bend2" / "main.ts")],
            **core, "fingerprint": "sha256:" + digest}


# bend2/safe.ts kernel_bin(): with $BENDTT unset, --verdict runs the kernel built from bendtt.lean and cached at
# ~/.bend/bendtt/<sha256(LEAN_VERSION "\0" bendtt.lean)[:16]>/bendtt. GENV refuses an inherited $BENDTT, and
# checker_env passes exactly this path once the kernel is built (I97, F-M3-14).
# These are the source lines that derivation is read from; if they change, the path is unknown.
_KERNEL_HASH_SRC = ('const hash = crypto.createHash("sha256").update(LEAN_VERSION).update("\\0").update(text)'
                    '.digest("hex").slice(0, 16);')
_KERNEL_DIR_SRC = 'const dir = path.join(os.homedir(), ".bend", "bendtt", hash);'


def verdict_kernel_path(checkout: Path) -> Path:
    """Where the checkout's bend2 caches the BendTT kernel binary that `--verdict` executes.

    Mirrors safe.ts kernel_bin() (its derivation lines are matched verbatim, else FingerprintError):
    os.homedir() is $HOME (as for Node), the source is bend2/bendtt.lean."""
    checkout = Path(checkout)
    safe = (checkout / "bend2" / "safe.ts").read_text()
    m = re.search(r'^const LEAN_VERSION = "([^"]+)";', safe, re.M)
    if not m or _KERNEL_HASH_SRC not in safe or _KERNEL_DIR_SRC not in safe:
        raise FingerprintError("bend2/safe.ts no longer derives the kernel cache path as holon/bend.py mirrors it; "
                               "the --verdict kernel cannot be located")
    text = (checkout / "bend2" / "bendtt.lean").read_bytes().decode("utf-8", errors="replace")
    h = hashlib.sha256(m.group(1).encode() + b"\0" + text.encode()).hexdigest()[:16]
    return Path(os.path.expanduser("~")) / ".bend" / "bendtt" / h / "bendtt"


def global_bunfig() -> list[str]:
    """Global Bun config files that exist: $XDG_CONFIG_HOME/.bunfig.toml and $HOME/.bunfig.toml.

    Bun reads the first of these that applies; both are refused whenever present (a preload in
    either runs code inside the checker). Read from os.environ at call time."""
    out = []
    for var in ("XDG_CONFIG_HOME", "HOME"):
        d = os.environ.get(var)
        if d:
            p = Path(d) / ".bunfig.toml"
            if p.exists() and str(p) not in out:
                out.append(str(p))
    return out


@dataclass
class Run:
    code: int | None
    out: str
    seconds: float
    argv: list = field(default_factory=list)  # exactly what was executed

    @property
    def first_line(self) -> str:
        lines = self.out.strip().splitlines()
        return lines[0].strip() if lines else ""

    @property
    def ok(self) -> bool:
        return self.code == 0 and self.first_line == MARK_OK

    @property
    def marker(self) -> str:
        if self.first_line in (MARK_OK, MARK_FAIL):
            return self.first_line
        return MARK_FAIL if self.code not in (0, None) else "not_run"


def js_stack_bytes(cfg: dict | None = None) -> int:
    """The checker's JavaScript stack in bytes (config/holon.json bend.js_stack_mb, F38)."""
    return int((cfg or config())["bend"].get("js_stack_mb", 1024)) * 1024 * 1024


# F38 review M2: RLIMIT_STACK is raised in the checker's process only, never in this one, whose other children (z3,
# solc, the frontends) keep the environment they were registered with. A launcher run by this interpreter in isolated
# mode (-I -S: no PYTHON* variable, no site, no current directory on sys.path) sets the soft limit and execs the checker
# with the same argv. Not a preexec_fn: checks run from threads (holon.gen.eqsearch), where it can deadlock.
_STACK_LAUNCHER = ("import os, resource, sys\n"
                   "n = int(sys.argv[1])\n"
                   "soft, hard = resource.getrlimit(resource.RLIMIT_STACK)\n"
                   "resource.setrlimit(resource.RLIMIT_STACK, (n if hard == resource.RLIM_INFINITY else min(n, hard), hard))\n"
                   "os.execv(sys.argv[2], sys.argv[2:])\n")


def stack_limits(cfg: dict | None = None) -> dict:
    """The checker's stack (F38): {"js_bytes", "rlimit_soft", "rlimit_hard"}. js_bytes is the JavaScript stack it is
    given (BUN_JSC_maxPerThreadStackUsage); rlimit_soft the RLIMIT_STACK its process runs with, js_bytes within the
    hard limit it inherits (rlimit_hard, None when unlimited), whatever this process's own soft limit is."""
    import resource
    n = js_stack_bytes(cfg)
    _soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
    unlimited = hard == resource.RLIM_INFINITY
    return {"js_bytes": n, "rlimit_soft": n if unlimited else min(n, hard), "rlimit_hard": None if unlimited else hard}


def _spawn_argv(cmd: list[str], cfg: dict | None = None) -> list[str]:
    """What run() executes for the checker command cmd: the stack launcher, which execs exactly cmd."""
    if not sys.executable:
        raise FileNotFoundError("cannot launch the bend checker: this interpreter's path is unknown (sys.executable)")
    return [sys.executable, "-I", "-S", "-c", _STACK_LAUNCHER, str(js_stack_bytes(cfg)), *cmd]


def run(args: list, cwd=None, timeout: int | None = None, cfg: dict | None = None) -> Run:
    """Run the resolved checker (checker_cmd: absolute bun + main.ts, the pair fingerprint() hashes)."""
    cfg = cfg or config()
    try:
        prefix = checker_cmd(cfg)
    except FingerprintError as e:
        raise FileNotFoundError(f"cannot resolve the bend checker: {e} (see tools/install_bend.sh)") from None
    cmd = prefix + [str(a) for a in args]
    env = checker_env(cfg)
    refuse_unsafe_cwd(cwd)
    t0 = time.monotonic()
    # its own process group, so a timeout stops everything the checker started (BendTT's Lean kernel is a child
    # of bun), not only bun (F35 review m4: the bound must bound the resources too)
    p = subprocess.Popen(_spawn_argv(cmd, cfg), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         env=env, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout or int(cfg["bend"].get("timeout_s", 180)))
        return Run(p.returncode, out + err, round(time.monotonic() - t0, 3), cmd)
    except subprocess.TimeoutExpired:
        _kill_group(p)
        out, _err = p.communicate()
        return Run(None, (out or "") + "\n[timeout]", round(time.monotonic() - t0, 3), cmd)
    except BaseException:
        _kill_group(p)
        raise


def _kill_group(p: subprocess.Popen) -> None:
    import os
    import signal
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        p.kill()


def parse_version(r: Run) -> str:
    m = re.search(r"bend (\d+\.\d+\.\d+)", r.out)
    if r.code != 0 or not m:
        raise RuntimeError(f"cannot read bend version: {r.out[:300]}")
    return m.group(1)


def version(cfg: dict | None = None) -> str:
    return parse_version(run(["version"], cfg=cfg))


def _in_clean_dir(proof_file: Path, extra: list, cfg: dict | None, timeout: int | None) -> Run:
    """I97 (F-M3-14): a check runs in a fresh empty working directory, the file by its absolute path (bend2 resolves
    its imports relative to the file, and prints no path in its verdict), so nothing beside the file configures bun."""
    proof_file = Path(proof_file).resolve()
    with tempfile.TemporaryDirectory(prefix="holon-bend-") as d:
        return run([str(proof_file), *extra], cwd=d, cfg=cfg, timeout=timeout)


def check(proof_file: Path, cfg: dict | None = None, timeout: int | None = None) -> Run:
    """Check a PROOF.bend (Bend resolves its imports relative to it), in a fresh empty working directory. timeout:
    seconds (default bend.timeout_s)."""
    return _in_clean_dir(proof_file, [], cfg, timeout)


def verdict_available() -> bool:
    """--verdict can run: the pinned kernel is built, or Lean is on the PATH to build it. An inherited BENDTT does not
    count (checker_env refuses one that names another kernel)."""
    env = _env()
    if env.get("BENDTT"):
        return True
    return shutil.which("lean", path=env["PATH"]) is not None


def verdict_enabled(cfg: dict | None = None) -> bool:
    v = (cfg or config())["bend"].get("verdict", "auto")
    return verdict_available() if v == "auto" else bool(v)


def check_verdict(proof_file: Path, cfg: dict | None = None, timeout: int | None = None) -> Run:
    """Second kernel (whitepaper §8.8): BendTT, whose soundness is proved in Lean. Runs through run(),
    so the same resolved checker, in a fresh empty working directory; the kernel binary it executes is the pinned
    toolchain's (checker_env passes it as BENDTT once built; GENV pins its sha256, bend.pinned_kernel_sha256)."""
    return _in_clean_dir(proof_file, ["--verdict"], cfg, timeout or 1800)


def equivalence_timeout(cfg: dict | None = None) -> int:
    """Q34: the bound, in seconds, of the final whole-proof check of an equivalence proof and of G2's re-check of a
    committed one, in each kernel (config equivalence.timeout_s, 900). Nothing else uses it."""
    return int((cfg or config()).get("equivalence", {}).get("timeout_s", 900))


def timed_out(r: Run) -> bool:
    return r.code is None and r.out.endswith("[timeout]")


def crashed(r: Run) -> bool:
    """A checker crash (bend2's nondeterministic 'the machine stack overflowed'): no verdict either way (Q34)."""
    return (not r.ok) and "stack overflow" in r.out.lower() and "Location:" not in r.out


def check_equivalence(proof_file: Path, cfg: dict | None = None, verdict: bool = False, tries: int | None = None) -> tuple:
    """(Run, crash log) of the final check of an equivalence proof in bend2 (verdict=False) or BendTT (--verdict),
    bounded by equivalence_timeout. A crash is never a verdict: it is retried, up to `tries` runs in all (default
    config equivalence.crash_tries), and each
    crash is logged ({kernel, seconds, message}). The last run is returned: a crash or a timeout there is UNKNOWN to
    the caller, never acceptance."""
    t = equivalence_timeout(cfg)
    if tries is None:
        tries = int((cfg or config()).get("equivalence", {}).get("crash_tries", 5))
    log = []
    for _ in range(max(1, tries)):
        r = check_verdict(proof_file, cfg, timeout=t) if verdict else check(proof_file, cfg, timeout=t)
        if not crashed(r):
            return r, log
        log.append({"kernel": "BendTT" if verdict else "bend", "seconds": r.seconds,
                    "message": "\n".join(ln for ln in r.out.splitlines() if ln.strip())[:300]})
    return r, log


def unsafe_env_files(root: Path) -> list[str]:
    """Every bunfig.toml and every name that starts with ".env" under root, at any depth outside .git (GENV; I97,
    F-M3-14): bun reads them from its working directory, where a preload patches the checker and a variable (BENDTT)
    redirects it. Relative to root, sorted."""
    root = Path(root)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if unsafe_env_name(p.name) and ".git" not in p.relative_to(root).parts)


# Escape hatches (BEND_PRIMER §3.2), scanned textually in addition to the checker's verdict.
ESCAPE_PATTERNS = {
    "unsafe": re.compile(r"@unsafe"),
    "unsafe_sugar": re.compile(r"^\s*def\s+[\w.]+\?\s*\(", re.M),
    "hole": re.compile(r"\?[A-Za-z_][\w]*"),
    "foreign_import": re.compile(r"^\s*import\s+\"", re.M),
}


def escape_hatches(src: str) -> list[str]:
    """Strict on purpose: comments are scanned too, so generators never write '?' anywhere."""
    return sorted(k for k, rx in ESCAPE_PATTERNS.items() if rx.search(src))


# `law` is a Bend keyword (bend2/bend.ts: a top-level `law Name :`); between tokens Bend skips whitespace and
# `#` comments, newlines included, so the name and the colon may sit on different lines (audit F-M2-21). Moved here
# from holon.gate (I41): G3's scan of gen/<m>/proofs/ (holon.gate.laws_in_proofs) and the prover intake's
# declares_law check (holon.intake) are one rule.
LAW_DECL = re.compile(r"(?<![\w.])law\s+[A-Za-z0-9_.]+\s*:")


def strip_comments(text: str) -> str:
    """Bend source with every `#` comment removed (to the end of its line), string and char literals kept whole,
    the way Bend's parse_skip treats them; line breaks are kept."""
    out = []
    for line in text.splitlines(keepends=True):
        i, cut, in_str = 0, None, False
        while i < len(line):
            ch = line[i]
            if in_str:
                if ch == "\\":
                    i += 2
                    continue
                if ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "'" and i + 2 < len(line) and line[i + 2] == "'":
                i += 3
                continue
            elif ch == "#":
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut] + ("\n" if line.endswith("\n") else ""))
    return "".join(out)


def declares_law(text: str) -> bool:
    """Whether Bend source declares a law, comments removed as Bend removes them (G3's rule for proof files)."""
    return LAW_DECL.search(strip_comments(text)) is not None


def run_budgeted(args: list, cwd, budget_s: float, cfg: dict | None = None) -> Run:
    """run() under a hard wall-clock budget (the prover intake, I41): the checker runs in its own process group,
    and the whole group is killed when the budget runs out, so nothing it spawned outlives the check. A run killed
    at the budget is Run(code=None, out ending in "[timeout]"), with the seconds it ran."""
    import signal
    cfg = cfg or config()
    try:
        prefix = checker_cmd(cfg)
    except FingerprintError as e:
        raise FileNotFoundError(f"cannot resolve the bend checker: {e} (see tools/install_bend.sh)") from None
    cmd = prefix + [str(a) for a in args]
    env = checker_env(cfg)
    refuse_unsafe_cwd(cwd)
    t0 = time.monotonic()
    p = subprocess.Popen(_spawn_argv(cmd, cfg), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         env=env, start_new_session=True)
    try:
        out, _ = p.communicate(timeout=budget_s)
        return Run(p.returncode, out or "", round(time.monotonic() - t0, 3), cmd)
    except subprocess.TimeoutExpired:
        secs = round(time.monotonic() - t0, 3)
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            p.kill()
        out, _ = p.communicate()
        return Run(None, (out or "") + "\n[timeout]", secs, cmd)


# ================================================================== I97: classifying a BendTT rejection (F-M3-13)
# A rejection by BendTT (--verdict) of a file bend2 accepts is a cross-kernel disagreement (the lead's ruling on
# F-M3-13), unless the kernel itself says it cannot decide the file: the emitted translation (`bend F -o F.bendtt`)
# names a definition outside the kernel's scope, or the kernel binary stops with "In <def>: out of fuel" (the
# evaluation exceeds its pinned budget, bend2/bendtt.lean FUEL). bend2's --verdict reports either as the generic
# mismatch text, so the classifier reads the kernel's own message. A construct counts only when the registry
# (spec/<M>/lib/bendtt_constructs.json) declares it with a minimized repro that bend2 accepts and BendTT rejects.
# Nothing here names a target.
CONSTRUCTS_REL = "spec/{m}/lib/bendtt_constructs.json"
_FUEL = re.compile(r"(?m)^In ([^\s:]+):\s*\n\s*out of fuel\s*$")


def constructs(root: Path | str | None = None, milestone: str = "M3") -> list[dict]:
    p = Path(root or Path(__file__).resolve().parents[1]) / CONSTRUCTS_REL.format(m=milestone)
    if not p.is_file():
        return []
    return list(json.loads(p.read_text(encoding="utf-8")).get("constructs") or [])


def kernel_message(proof_file: Path, cfg: dict | None = None, timeout: int = 1800) -> tuple[list[str], int | None, str]:
    """(out-of-scope lines, kernel exit code, kernel output) of a file bend2 accepts: its BendTT translation in a fresh
    directory, then the pinned kernel binary on it, with the stack bend2's own kernel_check gives it."""
    proof_file = Path(proof_file).resolve()
    cfg = cfg or config()
    tmp = Path(tempfile.mkdtemp(prefix="holon-bendtt-"))
    try:
        out = tmp / "in.bendtt"
        e = run([str(proof_file), "-o", str(out)], cwd=tmp, cfg=cfg, timeout=timeout)
        oos = [ln[2:].strip() for ln in (e.out or "").splitlines() if ln.startswith("- ")]
        kp = pinned_kernel_path(cfg)
        if not out.is_file() or kp is None or not kp.is_file():
            return oos, None, (e.out or "")[-800:]
        k = subprocess.run([str(kp), str(out)], capture_output=True, text=True, timeout=timeout, cwd=str(tmp),
                           env={**checker_env(cfg), "LEAN_STACK_SIZE_KB": "4194304"})
        return oos, k.returncode, (k.stdout + k.stderr)[-800:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def construct_of(proof_file: Path, cfg: dict | None = None) -> dict | None:
    """The kernel's own reason for not checking a file: {"kind": "out_of_scope", "detail"} or {"kind": "kernel_fuel",
    "def"}, or None when the kernel checks it or rejects it for another reason."""
    oos, code, msg = kernel_message(proof_file, cfg)
    if oos:
        return {"kind": "out_of_scope", "detail": oos[0]}
    if code not in (None, 0):
        m = _FUEL.search(msg.replace("\r", ""))
        if m:
            return {"kind": "kernel_fuel", "def": m.group(1)}
    return None


def classify_rejection(proof_file: Path, cfg: dict | None = None, root: Path | str | None = None,
                       milestone: str = "M3", verdict: "Run | None" = None) -> dict | None:
    """None when BendTT accepts the file; {"class": "unsupported", "construct", "def", "repro"} when the kernel's own
    reason is a registered construct; {"class": "disagreement", "detail"} otherwise. verdict: a check_verdict result
    of the same file already in hand."""
    v = verdict if verdict is not None else check_verdict(proof_file, cfg)
    if v.ok:
        return None
    got = construct_of(proof_file, cfg)
    reg = {c["kind"]: c for c in constructs(root, milestone)}
    if got and got["kind"] in reg:
        c = reg[got["kind"]]
        return {"class": "unsupported", "construct": c["name"], "def": got.get("def") or got.get("detail"),
                "repro": c["repro"]}
    return {"class": "disagreement", "detail": (v.out or "")[-300:].strip()}


def unsupported_reason(c: dict) -> str:
    """The bendtt reason a record carries for an unsupported rejection (holon.records.kernels, G7): "<construct>:
    <repro>". The definition the kernel stopped in is the record's checker.bendtt.construct.def."""
    return f"{c['construct']}: {c['repro']}"
