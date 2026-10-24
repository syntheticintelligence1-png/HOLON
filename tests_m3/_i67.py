"""The I67 prereg instrument (fixed at the prereg; independent of holon/: nothing here imports it).

What it computes, each from its own reading of the inputs:
  * run_instrument(probes): the real outcomes of morph-l2/common/batch.RetrieveBlobBytes and
    morph-l2/common/blob.RetrieveBlobBytes on probe blobs, from the Go instrument
    tests_m3/fixtures/go_loop/holon_i67_instrument.go.txt run on a scratch copy of the pinned morph checkout;
  * expected_ops(sidecar, document): the Go-op components rule Y3 of tests_m3/test_go_loop.py defines, from the
    sidecar spec/M3/lib/go_ops.json and the Go document it names (the ops, their model names, the carrier id);
  * expected_laws(component): the basis rule Y5 gives over such a component with PAR's producers as I24 wrote them
    (P4 weak over E6 pairs of one (src, tgt), P5 over the interface carrier's domains, P6 per op, P8 a duplicate),
    as law ids and statements;
  * cells_probe(cells, stride), cells_of_hex(hex) and single_cell(e): the concretization rule Y9 (cell k of a witness
    is the byte the loop body reads at iteration k, blob[stride * k]): a witness's probe, its cells, and the witness
    whose one non-zero cell is e.
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
FIX = ROOT / "tests_m3" / "fixtures" / "go_loop"
INSTRUMENT = FIX / "holon_i67_instrument.go.txt"
HOLON_CONFIG = ROOT / "config" / "holon.json"
FRONTEND_CONFIG = ROOT / "spec" / "M3" / "lib" / "go_frontend.json"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "go_ops.json"
OPS = ("common/batch", "common/blob")
CELLS = 4096          # the loop's trip count: field elements per blob
STRIDE = 32           # bytes per field element: cell k is blob[32 * k], its high-order byte
OUT_LEN = 4096 * 31   # the length of the output both clones allocate
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GO_METHOD = re.compile(r"\((\*?)(.*)\)\.([^.()]+)")

# The probe set (fixed at the prereg): the zero blob; each field element's high-order byte alone set to 1; payload
# bytes only (a byte that is no element's high-order byte); two high-order bytes, the first below the panic threshold
# the real code shows; the threshold element at the largest byte value; and every element at once.
PROBES = ([[]] + [[[STRIDE * e, 1]] for e in range(CELLS)]
          + [[[1, 7], [STRIDE * CELLS - 1, 9]], [[STRIDE * 3967, 1], [STRIDE * 3968, 1]], [[STRIDE * 3968, 255]],
             [[STRIDE * e, 1] for e in range(CELLS)]])


def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the real code
def go_binary() -> str:
    found = shutil.which("go") or ("/usr/local/go/bin/go" if Path("/usr/local/go/bin/go").is_file() else None)
    if not found:
        raise AssertionError("no go toolchain on PATH or at /usr/local/go/bin/go (pinned: config replay.go_version)")
    want = (load_json(HOLON_CONFIG).get("replay") or {}).get("go_version")
    got = subprocess.run([found, "version"], capture_output=True, text=True, timeout=120).stdout.strip()
    if got != want:
        raise AssertionError(f"`go version` is {got!r}, pinned {want!r} (config/holon.json replay.go_version)")
    return found


def morph_checkout() -> Path:
    """The pinned morph checkout (config replay.morph), clean, at the frontend config's target commit."""
    cfg = load_json(HOLON_CONFIG).get("replay") or {}
    if not cfg.get("morph"):
        raise AssertionError("config/holon.json replay.morph is not pinned")
    morph = Path(cfg["morph"])
    if not (morph / "common" / "batch").is_dir() or not (morph / "common" / "blob").is_dir():
        raise AssertionError(f"pinned morph checkout {morph} is missing common/batch or common/blob")
    head = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    want = load_json(FRONTEND_CONFIG)["target"]["commit"]
    if head != want:
        raise AssertionError(f"{morph} is at {head!r}, not at the frontend config's commit {want}")
    dirty = subprocess.run(["git", "-C", str(morph), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise AssertionError(f"{morph} has local changes:\n{dirty[:2000]}")
    return morph


_RUNS: dict = {}


def run_instrument(probes: list | None = None) -> dict:
    """{"common/batch": [outcome], "common/blob": [outcome]} on the probes (default PROBES), cached per probe list."""
    probes = PROBES if probes is None else probes
    key = json.dumps(probes)
    if key in _RUNS:
        return _RUNS[key]
    go = go_binary()
    morph = morph_checkout()
    ws = Path(tempfile.mkdtemp(prefix="holon-i67-go-"))
    try:
        ign = shutil.ignore_patterns(".git", "node_modules", ".env", ".env.*", "bunfig.toml")
        for d in ("bindings", "common"):
            shutil.copytree(morph / d, ws / d, symlinks=True, ignore=ign)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
        shutil.copy(INSTRUMENT, ws / "common" / "batch" / "holon_i67_instrument_test.go")
        (ws / "in.json").write_text(json.dumps({"probes": probes}))
        env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS")}
        env.update({"GOTOOLCHAIN": "local", "HOLON_I67_IN": str(ws / "in.json"), "HOLON_I67_OUT": str(ws / "out.json")})
        p = subprocess.run([go, "test", "./batch", "-run", "^TestHolonI67Instrument$", "-count=1", "-v"],
                           cwd=ws / "common", env=env, capture_output=True, text=True, timeout=1500)
        if p.returncode != 0 or not (ws / "out.json").exists():
            raise AssertionError(f"I67 Go instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        out = load_json(ws / "out.json")
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    if sorted(out) != sorted(OPS) or any(len(out[k]) != len(probes) for k in OPS):
        raise AssertionError(f"I67 Go instrument: malformed output {sorted(out)}")
    _RUNS[key] = out
    return out


def kind(outcome: str) -> str:
    """"ok", "err" or "panic"."""
    return outcome.split(":", 1)[0]


def outcome_class(outcome: str) -> str:
    """The model's outcome for a real one (rule Y6): ORet (nil error), OErr (non-nil error), OPanic (a panic)."""
    return {"ok": "ORet", "err": "OErr", "panic": "OPanic"}[kind(outcome)]


def index_panic(outcome: str, index: int, length: int) -> bool:
    """A Go runtime index error at that index and length."""
    return outcome == f"panic:runtime error: index out of range [{index}] with length {length}"


# ------------------------------------------------------------------ concretization (rule Y9)
def cells_probe(cells: list[int], stride: int = STRIDE) -> list[list[int]]:
    """The probe of a witness cell sequence: blob[stride * k] = cells[k] where non-zero, every other byte 0."""
    return [[stride * k, v] for k, v in enumerate(cells) if v]


def cells_of_hex(h: str) -> list[int]:
    if not isinstance(h, str) or not h.startswith("0x"):
        raise AssertionError(f"a witness cell sequence is 0x-prefixed hex, got {str(h)[:40]!r}")
    return list(bytes.fromhex(h[2:]))


def single_cell(e: int, v: int = 1, n: int = CELLS) -> list[int]:
    return [v if k == e else 0 for k in range(n)]


# ------------------------------------------------------------------ the expected component and laws (Y3, Y5)
def go_name(fid: str) -> str:
    """Rule Y3's model name: "<pkg>_<F>" for "<path>/<pkg>.F", "<pkg>_<T>_<M>" for "(*<path>/<pkg>.T).M"."""
    m = GO_METHOD.fullmatch(fid)
    if m:
        pkg_path, typ = m.group(2).rsplit(".", 1)
        name = f"{pkg_path.rsplit('/', 1)[-1]}_{typ}_{m.group(3)}"
    else:
        pkg_path, fn = fid.rsplit(".", 1)
        name = f"{pkg_path.rsplit('/', 1)[-1]}_{fn}"
    if not NAME.match(name):
        raise AssertionError(f"{fid}: model name {name!r} is not an identifier")
    return name


def carrier_id(go_type: str) -> str:
    return go_type.lstrip("*").rsplit(".", 1)[-1]


def expected_ops(sidecar: dict, document: dict) -> dict:
    """{component: {"carrier": id, "type": go type, "ops": {model name: function id}}} by rule Y3."""
    fns = document["go"]["functions"]
    out = {}
    for name, c in sorted(sidecar["components"].items()):
        ops = {}
        for fid, f in sorted(fns.items()):
            ps, rs = f.get("params") or [], f.get("results") or []
            if len(ps) == 1 and ps[0]["type"] == c["carrier"] and rs and rs[-1] == "error":
                mn = go_name(fid)
                if mn in ops:
                    raise AssertionError(f"two ops named {mn}")
                ops[mn] = fid
        out[name] = {"carrier": carrier_id(c["carrier"]), "type": c["carrier"], "ops": ops}
    return out


def expected_laws(comp: dict) -> dict:
    """{law id: statement} of rule Y5 over one component whose ops share one result tuple (as blob_ops' do): one
    totality law per op, one weak law per pair of ops (E6: two clones share name tokens), one domain-coherence law per
    pair of domains, the binder b over the carrier, no premise."""
    car, ops = comp["carrier"], sorted(comp["ops"])

    def st(lhs, rhs):
        return {"binders": [{"q": "forall", "name": "b", "type": car}], "assume": [], "claim": {"eq": [lhs, rhs]},
                "scope": {"kind": "unbounded"}}

    def call(f):
        return {"call": f, "args": [{"var": "b"}]}
    out = {}
    for i, p in enumerate(ops):
        for q in ops[i + 1:]:
            out[f"L_par_weak_{p}_{q}"] = st(call(p), call(q))
            out[f"L_par_dom_ok_{p}_ok_{q}"] = st(call(f"ok_{p}"), call(f"ok_{q}"))
    for p in ops:
        out[f"L_par_tot_{p}"] = st(call(f"ok_{p}"), {"bool": True})
    return dict(sorted(out.items()))
