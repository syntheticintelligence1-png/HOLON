"""I91's instrument (fixed at the I91 prereg; written without holon/; do not edit: a wrong instrument is a Question and an
amendment line in spec/M3/amendments.jsonl).

It computes, independently of holon.oracles.compression, what the compression oracle must find:
  * the capacity C from the pinned source text (the constant's declaration, evaluated here), and K from HypZ's
    expression in the sidecar;
  * the sample inputs (zero, ramp and stream bytes) and their sha256;
  * what the real codec and blob pipeline do on the sample, through its own Go file
    tests_m3/fixtures/compression/holon_i91_instrument.go.txt, run as an external test of the probe package in a scratch
    copy of the pinned checkout's bindings and common modules (the source tree itself is never written);
  * the statuses, failures, expansion and empty-payload entries those outcomes give (rules Z3-Z7 of the docstring of
    tests_m3/test_compress.py).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "spec" / "M3" / "lib" / "compression.json"
HOLON_CONFIG = ROOT / "config" / "holon.json"
INSTRUMENT_GO = ROOT / "tests_m3" / "fixtures" / "compression" / "holon_i91_instrument.go.txt"
EXPR = re.compile(r"^(?:(\d+)|C|C([+-])(\d+)|(\d+)\*C)$")
FAIL_CAP = 10
MSG_CAP = 200


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def value(expr: str, c: int) -> int:
    """An expression of the sidecar (an integer, C, C-d, C+d, m*C) at capacity c."""
    m = EXPR.match(str(expr))
    if not m:
        raise AssertionError(f"not an expression over C: {expr!r}")
    if m.group(1) is not None:
        return int(m.group(1))
    if m.group(2) is not None:
        d = int(m.group(3))
        return c + d if m.group(2) == "+" else c - d
    if m.group(4) is not None:
        return int(m.group(4)) * c
    return c


def go_binary() -> str:
    found = shutil.which("go") or ("/usr/local/go/bin/go" if Path("/usr/local/go/bin/go").is_file() else None)
    if not found:
        raise AssertionError("no go toolchain on PATH or at /usr/local/go/bin/go (pinned: config replay.go_version)")
    want = (load_json(HOLON_CONFIG).get("replay") or {}).get("go_version")
    got = subprocess.run([found, "version"], capture_output=True, text=True, timeout=120).stdout.strip()
    if got != want:
        raise AssertionError(f"`go version` is {got!r}, pinned {want!r} (config/holon.json replay.go_version)")
    return found


def checkout(commit: str) -> Path:
    """The pinned checkout (config replay.morph), clean, at the Go document's target commit."""
    cfg = load_json(HOLON_CONFIG).get("replay") or {}
    src = Path(cfg["morph"])
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != commit:
        raise AssertionError(f"{src} is at {head!r}, not at the Go document's commit {commit}")
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise AssertionError(f"{src} has local changes:\n{dirty[:2000]}")
    return src


def capacity_from_source(src: Path) -> int:
    """C as both blob packages declare it (`const MaxBlobBytesSize = a * b`), evaluated here; they must agree."""
    vals = set()
    for rel in ("common/blob/payload.go", "common/batch/blob.go"):
        text = (src / rel).read_text(encoding="utf-8")
        m = re.search(r"(?m)^const\s+MaxBlobBytesSize\s*=\s*([0-9]+(?:\s*\*\s*[0-9]+)*)\s*$", text)
        if not m:
            raise AssertionError(f"{rel}: no MaxBlobBytesSize declaration")
        v = 1
        for part in m.group(1).split("*"):
            v *= int(part.strip())
        vals.add(v)
    if len(vals) != 1:
        raise AssertionError(f"the two blob packages declare different capacities: {sorted(vals)}")
    return vals.pop()


def x_bytes(kind: str, n: int, seed: str) -> bytes:
    if kind == "zero":
        return bytes(n)
    if kind == "ramp":
        return bytes(i % 256 for i in range(n))
    if kind == "stream":
        out = bytearray()
        j = 0
        while len(out) < n:
            out += hashlib.sha256(seed.encode("utf-8") + j.to_bytes(4, "big")).digest()
            j += 1
        return bytes(out[:n])
    raise AssertionError(f"unknown kind {kind!r}")


def cb(n: int, bound: dict) -> int:
    small = bound["small"]
    return n + (n >> bound["shift"]) + ((small - n) >> bound["small_shift"] if n < small else 0)


def resolved_sample(sidecar: dict, c: int) -> dict:
    s = sidecar["sample"]
    e = s["expansion"]
    lim = value(e["limit"], c)
    return {"seed": s["seed"], "kinds": list(s["kinds"]), "lengths": [value(x, c) for x in s["lengths"]],
            "paddings": [value(x, c) for x in s["paddings"]], "beyond": [value(x, c) for x in s["beyond"]],
            "exp_kind": e["kind"], "exp_lo": lim - int(e["window"]) + 1, "exp_hi": lim}


_RUNS: dict = {}


def run_instrument() -> dict:
    """{"source_capacity": C from the source text, "sample": the resolved sample, "out": the Go file's output}."""
    if "run" in _RUNS:
        return _RUNS["run"]
    sidecar = load_json(SIDECAR)
    doc = load_json(ROOT / sidecar["document"])
    src = checkout(doc["target"]["commit"])
    c = capacity_from_source(src)
    sample = resolved_sample(sidecar, c)
    go = go_binary()
    ws = Path(tempfile.mkdtemp(prefix="holon-i91-go-"))
    try:
        ign = shutil.ignore_patterns(".git", "node_modules", ".env", ".env.*", "bunfig.toml")
        for d in ("bindings", "common"):
            shutil.copytree(src / d, ws / d, symlinks=True, ignore=ign)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
        shutil.copy(INSTRUMENT_GO, ws / "common" / "blob" / "holon_i91_instrument_test.go")
        (ws / "in.json").write_text(json.dumps(sample))
        env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS")}
        env.update({"GOTOOLCHAIN": "local", "HOLON_I91_IN": str(ws / "in.json"), "HOLON_I91_OUT": str(ws / "out.json")})
        p = subprocess.run([go, "test", "./blob", "-run", "^TestHolonI91Instrument$", "-count=1", "-v"],
                           cwd=ws / "common", env=env, capture_output=True, text=True, timeout=3000)
        if p.returncode != 0 or not (ws / "out.json").exists():
            raise AssertionError(f"I91 Go instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        out = load_json(ws / "out.json")
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    _RUNS["run"] = {"source_capacity": c, "sample": sample, "out": out}
    return _RUNS["run"]


def expected(sidecar: dict, run: dict) -> dict:
    """What rules Z3-Z7 give from the instrument's outcomes: capacity, points (the outcome fields), hypotheses (status,
    points, decodes, failures, max_excess), expansion and empty."""
    out, sample = run["out"], run["sample"]
    c = out["capacity"]
    k_max = value(sidecar["hypotheses"]["HypZ"]["K"], c)
    bound = sidecar["hypotheses"]["HypZ_len"]["bound"]
    points, zfail, lfail = [], [], []
    decodes = 0
    max_excess = None
    for p in out["points"]:
        x = x_bytes(p["kind"], p["n"], sample["seed"])
        q = {"kind": p["kind"], "n": p["n"], "x_sha256": hashlib.sha256(x).hexdigest(),
             "go_x_sha256": p["x_sha256"], "enc_error": p.get("enc_error"), "enc_len": p.get("enc_len"),
             "enc_sha256": p.get("enc_sha256"), "blobs": p.get("blobs"), "padded_len": p.get("padded_len"),
             "padded_is_c_then_zeros": p.get("padded_is_c_then_zeros"), "pipeline": p.get("pipeline"),
             "paddings": p.get("paddings"), "beyond": p.get("beyond")}
        q["padding"] = (p["padded_len"] - p["enc_len"]) if p.get("padded_len") is not None else None
        points.append(q)
        if p.get("enc_error") is not None:
            zfail.append({"kind": p["kind"], "n": p["n"], "k": "enc", "got": "error: " + p["enc_error"][:MSG_CAP]})
            lfail.append({"kind": p["kind"], "n": p["n"], "enc_len": None, "bound": cb(p["n"], bound)})
            continue
        checks = [("pipeline", p["pipeline"])] + [(int(k), v) for k, v in sorted(p["paddings"].items(),
                                                                                 key=lambda kv: int(kv[0]))]
        for k, v in checks:
            decodes += 1
            if v != "ok":
                zfail.append({"kind": p["kind"], "n": p["n"], "k": k, "got": v})
        excess = p["enc_len"] - p["n"]
        max_excess = excess if max_excess is None else max(max_excess, excess)
        if p["enc_len"] > cb(p["n"], bound):
            lfail.append({"kind": p["kind"], "n": p["n"], "enc_len": p["enc_len"], "bound": cb(p["n"], bound)})
    lens = {int(n): ln for n, ln in out["expansion"]["lens"]}
    lo, hi = sample["exp_lo"], sample["exp_hi"]
    over = sorted(n for n, ln in lens.items() if ln > hi)
    expansion = {"kind": sample["exp_kind"], "limit": hi, "window": [lo, hi], "enc_len_at_limit": lens[hi],
                 "overhead": lens[hi] - hi,
                 "exceeding": {"count": len(over), "min": over[0] if over else None,
                               "interval": bool(over) and over == list(range(over[0], hi + 1))}}
    return {"capacity": {"C": c, "K": k_max}, "source_capacity": run["source_capacity"], "points": points,
            "HypZ": {"status": "checked" if not zfail else "mismatch", "points": len(points), "decodes": decodes,
                     "failures": zfail[:FAIL_CAP]},
            "HypZ_len": {"status": "checked" if not lfail else "mismatch", "points": len(points),
                         "max_excess": max_excess, "failures": lfail[:FAIL_CAP]},
            "expansion": expansion, "empty": out["empty"], "sample": sample}
