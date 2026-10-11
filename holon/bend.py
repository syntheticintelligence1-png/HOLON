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
from dataclasses import dataclass
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
    if elan.is_dir():  # `--verdict` builds the BendTT kernel with Lean
        env["PATH"] = str(elan) + os.pathsep + env.get("PATH", "")
    env["BEND_NO_TELEMETRY"] = "1"  # main.ts skips its daily version check (a network GET)
    # bun reads BUN_OPTIONS as extra command-line flags (e.g. --preload ./x.ts, which would run code
    # inside the checker): the checker never inherits it
    for k in [k for k in env if k == "BUN_OPTIONS" or k.startswith("BUN_CONFIG_")]:
        env.pop(k)
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


def fingerprint(cfg: dict | None = None) -> dict:
    """The identity of the checker the gate runs: checkout HEAD, its sources and the bun version.

    `fingerprint` = "sha256:" + sha256 of the canonical JSON of {head, sources_sha256, bun}; it is
    pinned as config bend.pinned_fingerprint. Deterministic: no timestamps, no absolute paths hashed.
    A checkout that is not a git repository gets head "unknown" (and so will not match a pin)."""
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
    core = {"head": head, "sources_sha256": sources_sha256(checkout), "bun": bun_v}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
    return {"checkout": str(checkout), "bun_path": bun_path, **core, "fingerprint": "sha256:" + digest}


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
    cfg = cfg or config()
    cmd = bend_cmd(cfg) + [str(a) for a in args]
    if shutil.which(cmd[0]) is None and not Path(cmd[0]).exists():
        raise FileNotFoundError(f"bend command not found: {cmd[0]!r} (see tools/install_bend.sh)")
    t0 = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=_env(),
                           timeout=timeout or int(cfg["bend"].get("timeout_s", 180)))
        return Run(p.returncode, p.stdout + p.stderr, round(time.monotonic() - t0, 3))
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        return Run(None, out + "\n[timeout]", round(time.monotonic() - t0, 3))


def version(cfg: dict | None = None) -> str:
    r = run(["version"], cfg=cfg)
    m = re.search(r"bend (\d+\.\d+\.\d+)", r.out)
    if r.code != 0 or not m:
        raise RuntimeError(f"cannot read bend version: {r.out[:300]}")
    return m.group(1)


def check(proof_file: Path, cfg: dict | None = None) -> Run:
    """Check a PROOF.bend in its own directory (Bend resolves imports relative to it)."""
    proof_file = Path(proof_file)
    return run([proof_file.name], cwd=proof_file.parent, cfg=cfg)


def verdict_available() -> bool:
    if os.environ.get("BENDTT"):
        return True
    return shutil.which("lean", path=_env()["PATH"]) is not None


def verdict_enabled(cfg: dict | None = None) -> bool:
    v = (cfg or config())["bend"].get("verdict", "auto")
    return verdict_available() if v == "auto" else bool(v)


def check_verdict(proof_file: Path, cfg: dict | None = None) -> Run:
    """Second kernel (whitepaper §8.8): BendTT, whose soundness is proved in Lean."""
    proof_file = Path(proof_file)
    return run([proof_file.name, "--verdict"], cwd=proof_file.parent, cfg=cfg, timeout=1800)


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
