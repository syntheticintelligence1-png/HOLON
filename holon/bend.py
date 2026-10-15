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
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK_OK = "ALL PROOFS CHECK"
MARK_FAIL = "SOME PROOFS FAIL"
UNSAFE_ENV_FILES = ("bunfig.toml", ".env")


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


def _env() -> dict:
    env = dict(os.environ)
    elan = Path.home() / ".elan" / "bin"
    if elan.is_dir():
        # `--verdict` builds the BendTT kernel with Lean. Appended, never prepended: nothing in
        # ~/.elan/bin may shadow a command (the checker itself always runs by absolute path, see
        # checker_cmd)
        env["PATH"] = os.pathsep.join(x for x in (env.get("PATH", ""), str(elan)) if x)
    env["BEND_NO_TELEMETRY"] = "1"  # main.ts skips its daily version check (a network GET)
    # bun reads BUN_OPTIONS as extra command-line flags (e.g. --preload ./x.ts, which would run code
    # inside the checker): the checker never inherits it
    for k in [k for k in env if k == "BUN_OPTIONS" or k.startswith("BUN_CONFIG_")]:
        env.pop(k)
    # bend2/bend.ts resolves package imports through BEND_LIB / BEND_HUB: never let the environment
    # redirect them (HOLON's files import only Base and relative paths)
    for k in ("BEND_LIB", "BEND_HUB"):
        env.pop(k, None)
    return env


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
        b = subprocess.run([bun_path, "--version"], capture_output=True, text=True, env=_env(), timeout=60,
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


# bend2/safe.ts kernel_bin(): with $BENDTT unset (GENV refuses it), --verdict runs the kernel built
# from bendtt.lean and cached at ~/.bend/bendtt/<sha256(LEAN_VERSION "\0" bendtt.lean)[:16]>/bendtt.
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


def run(args: list, cwd=None, timeout: int | None = None, cfg: dict | None = None) -> Run:
    """Run the resolved checker (checker_cmd: absolute bun + main.ts, the pair fingerprint() hashes)."""
    cfg = cfg or config()
    try:
        prefix = checker_cmd(cfg)
    except FingerprintError as e:
        raise FileNotFoundError(f"cannot resolve the bend checker: {e} (see tools/install_bend.sh)") from None
    cmd = prefix + [str(a) for a in args]
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=_env(),
                           timeout=timeout or int(cfg["bend"].get("timeout_s", 180)))
        return Run(p.returncode, p.stdout + p.stderr, round(time.monotonic() - t0, 3), cmd)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return Run(None, out + "\n[timeout]", round(time.monotonic() - t0, 3), cmd)


def parse_version(r: Run) -> str:
    m = re.search(r"bend (\d+\.\d+\.\d+)", r.out)
    if r.code != 0 or not m:
        raise RuntimeError(f"cannot read bend version: {r.out[:300]}")
    return m.group(1)


def version(cfg: dict | None = None) -> str:
    return parse_version(run(["version"], cfg=cfg))


def check(proof_file: Path, cfg: dict | None = None, timeout: int | None = None) -> Run:
    """Check a PROOF.bend in its own directory (Bend resolves imports relative to it). timeout: seconds (default
    bend.timeout_s)."""
    proof_file = Path(proof_file)
    return run([proof_file.name], cwd=proof_file.parent, cfg=cfg, timeout=timeout)


def verdict_available() -> bool:
    if os.environ.get("BENDTT"):
        return True
    return shutil.which("lean", path=_env()["PATH"]) is not None


def verdict_enabled(cfg: dict | None = None) -> bool:
    v = (cfg or config())["bend"].get("verdict", "auto")
    return verdict_available() if v == "auto" else bool(v)


def check_verdict(proof_file: Path, cfg: dict | None = None, timeout: int | None = None) -> Run:
    """Second kernel (whitepaper §8.8): BendTT, whose soundness is proved in Lean. Runs through run(),
    so the same resolved checker; the kernel binary it executes is pinned by GENV
    (verdict_kernel_path, bend.pinned_kernel_sha256)."""
    proof_file = Path(proof_file)
    return run([proof_file.name, "--verdict"], cwd=proof_file.parent, cfg=cfg, timeout=timeout or 1800)


def equivalence_timeout(cfg: dict | None = None) -> int:
    """Q34: the bound, in seconds, of the final whole-proof check of an equivalence proof and of G2's re-check of a
    committed one, in each kernel (config equivalence.timeout_s, 900). Nothing else uses it."""
    return int((cfg or config()).get("equivalence", {}).get("timeout_s", 900))


def timed_out(r: Run) -> bool:
    return r.code is None and r.out.endswith("[timeout]")


def crashed(r: Run) -> bool:
    """A checker crash (bend2's nondeterministic 'the machine stack overflowed'): no verdict either way (Q34)."""
    return (not r.ok) and "stack overflow" in r.out.lower() and "Location:" not in r.out


def check_equivalence(proof_file: Path, cfg: dict | None = None, verdict: bool = False, tries: int = 3) -> tuple:
    """(Run, crash log) of the final check of an equivalence proof in bend2 (verdict=False) or BendTT (--verdict),
    bounded by equivalence_timeout. A crash is never a verdict: it is retried, up to `tries` runs in all, and each
    crash is logged ({kernel, seconds, message}). The last run is returned: a crash or a timeout there is UNKNOWN to
    the caller, never acceptance."""
    t = equivalence_timeout(cfg)
    log = []
    for _ in range(max(1, tries)):
        r = check_verdict(proof_file, cfg, timeout=t) if verdict else check(proof_file, cfg, timeout=t)
        if not crashed(r):
            return r, log
        log.append({"kernel": "BendTT" if verdict else "bend", "seconds": r.seconds,
                    "message": "\n".join(ln for ln in r.out.splitlines() if ln.strip())[:300]})
    return r, log


def unsafe_env_files(root: Path) -> list[str]:
    """Bun reads bunfig.toml/.env from the working directory; a preload there patches the checker."""
    root = Path(root)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.name in UNSAFE_ENV_FILES and ".git" not in p.relative_to(root).parts)


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
    t0 = time.monotonic()
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=_env(),
                         start_new_session=True)
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
