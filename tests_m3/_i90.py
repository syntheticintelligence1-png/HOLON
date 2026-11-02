"""The I90 prereg instrument (fixed at the prereg; independent of holon/: nothing here imports it).

What it computes, each from its own reading of the inputs:
  * run_instrument(probes): what the real morph-l2/common/batch.BatchData.Append leaves in its l1TxNum, l1TxHashes
    and blockNum fields after a sequence of calls, from the Go instrument
    tests_m3/fixtures/go_counts/holon_i90_instrument.go.txt run on a scratch copy of the pinned morph checkout;
  * expected_channels(sidecar, document, config): the count components rule C1 of tests_m3/test_go_counts.py defines,
    from the sidecar spec/M3/lib/go_counts.json, the Go document it names and that document's extraction config (the
    primitives' widths): each component's carrier id, count carrier and channels;
  * expected_laws(component): the laws and duplicates rule C3 gives over such a component with PAR's producers as I24
    wrote them (P3 over two channels of one function, P8's cycle elements over the two-carrier multigraph), as law
    ids and statements;
  * channel_value(channel, n) and witness(channels): the count a channel records after one call on a parameter of
    length n from the receiver's zero value (rule C4's semantics, written out again: an item channel n, a wrap channel
    of width w n mod 2^w), and the smallest length at which two channels differ.
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
FIX = ROOT / "tests_m3" / "fixtures" / "go_counts"
INSTRUMENT = FIX / "holon_i90_instrument.go.txt"
HOLON_CONFIG = ROOT / "config" / "holon.json"
SIDECAR = ROOT / "spec" / "M3" / "lib" / "go_counts.json"
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GO_METHOD = re.compile(r"\((\*?)(.*)\)\.([^.()]+)")
WRAP_WIDTHS = {"uint8": 8, "uint16": 16, "uint32": 32}
ITEM_KINDS = ("array_bytes", "to_array")

# The probe set (fixed at the prereg): no call; one call with 0, 1, 65535, 65536, 65537 and 131072 hashes from
# NewBatchData(); one call with 65536 hashes from the zero value new(BatchData); 65536 hashes split across two calls
# (32768 each) and across 64 calls of 1024 (block-sized counts); 65535 calls of one hash each (the block count's
# last value before its own wrap).
PROBES = ([{"fresh": "new", "calls": []}]
          + [{"fresh": "new", "calls": [n]} for n in (0, 1, 65535, 65536, 65537, 131072)]
          + [{"fresh": "zero", "calls": [65536]},
             {"fresh": "new", "calls": [32768, 32768]},
             {"fresh": "new", "calls": [1024] * 64},
             {"fresh": "new", "calls": [1] * 65535}])


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


def morph_checkout(commit: str) -> Path:
    """The pinned morph checkout (config replay.morph), clean, at the Go document's target commit."""
    cfg = load_json(HOLON_CONFIG).get("replay") or {}
    if not cfg.get("morph"):
        raise AssertionError("config/holon.json replay.morph is not pinned")
    morph = Path(cfg["morph"])
    if not (morph / "common" / "batch").is_dir():
        raise AssertionError(f"pinned morph checkout {morph} is missing common/batch")
    head = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != commit:
        raise AssertionError(f"{morph} is at {head!r}, not at the Go document's commit {commit}")
    dirty = subprocess.run(["git", "-C", str(morph), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise AssertionError(f"{morph} has local changes:\n{dirty[:2000]}")
    return morph


_RUNS: dict = {}


def run_instrument(commit: str, probes: list | None = None) -> list[dict]:
    """[outcome per probe] on the probes (default PROBES), cached per probe list."""
    probes = PROBES if probes is None else probes
    key = json.dumps(probes)
    if key in _RUNS:
        return _RUNS[key]
    go = go_binary()
    morph = morph_checkout(commit)
    ws = Path(tempfile.mkdtemp(prefix="holon-i90-go-"))
    try:
        ign = shutil.ignore_patterns(".git", "node_modules", ".env", ".env.*", "bunfig.toml")
        for d in ("bindings", "common"):
            shutil.copytree(morph / d, ws / d, symlinks=True, ignore=ign)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
        shutil.copy(INSTRUMENT, ws / "common" / "batch" / "holon_i90_instrument_test.go")
        (ws / "in.json").write_text(json.dumps({"probes": probes}))
        env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS")}
        env.update({"GOTOOLCHAIN": "local", "HOLON_I90_IN": str(ws / "in.json"), "HOLON_I90_OUT": str(ws / "out.json")})
        p = subprocess.run([go, "test", "./batch", "-run", "^TestHolonI90Instrument$", "-count=1", "-v"],
                           cwd=ws / "common", env=env, capture_output=True, text=True, timeout=1500)
        if p.returncode != 0 or not (ws / "out.json").exists():
            raise AssertionError(f"I90 Go instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        out = load_json(ws / "out.json")["outcomes"]
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    if len(out) != len(probes):
        raise AssertionError(f"I90 Go instrument: {len(out)} outcomes for {len(probes)} probes")
    _RUNS[key] = out
    return out


# ------------------------------------------------------------------ the expected components (C1)
def go_name(fid: str) -> str:
    """I67's model name: "<pkg>_<F>" for "<path>/<pkg>.F", "<pkg>_<T>_<M>" for "(*<path>/<pkg>.T).M"."""
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


def type_word(t: str) -> str:
    """A Go type as an identifier: every leading "[]" as Slice and "*" as Ptr, then the last name segment with its
    first letter upper-cased (I67's result-carrier words)."""
    word = ""
    while t.startswith(("[]", "*")):
        word += "Slice" if t.startswith("[]") else "Ptr"
        t = t[2:] if t.startswith("[]") else t[1:]
    last = t.rsplit(".", 1)[-1].rsplit("/", 1)[-1]
    out = word + last[:1].upper() + last[1:]
    if not NAME.match(out):
        raise AssertionError(f"{t}: carrier id {out!r} is not an identifier")
    return out


def _mentions_rangeindex(t) -> bool:
    if isinstance(t, list):
        if len(t) == 3 and t[0] == "var" and t[2] == "rangeindex":
            return True
        return any(_mentions_rangeindex(x) for x in t)
    return False


def channel_of(store: dict, recv: str, param: str, loops: list, prims: dict):
    """(kind, width, field) of one store fact that is a count channel of param, else None."""
    tgt, val = store.get("target"), store.get("value")
    if not (isinstance(tgt, list) and len(tgt) == 3 and tgt[0] == "field" and tgt[1] == ["param", recv]
            and isinstance(tgt[2], str)):
        return None
    f = tgt[2]
    me = ["field", ["param", recv], f]
    if (isinstance(val, list) and len(val) == 4 and val[0] == "op" and val[1] == "+" and val[2] == me
            and isinstance(val[3], list) and len(val[3]) == 3 and val[3][0] == "convert"
            and val[3][1] in WRAP_WIDTHS and val[3][2] == ["len", ["param", param]]):
        return "wrap", WRAP_WIDTHS[val[3][1]], f
    if isinstance(val, list) and len(val) == 3 and val[0] == "append" and val[1] == me:
        x = val[2]
        if not (isinstance(x, list) and len(x) == 3 and x[0] == "call" and isinstance(x[2], list) and len(x[2]) == 1):
            return None
        prim = prims.get(x[1]) or {}
        k = prim.get("width")
        if prim.get("kind") not in ITEM_KINDS or not isinstance(k, int) or isinstance(k, bool) or k < 1:
            return None
        arg = x[2][0]
        if not (isinstance(arg, list) and len(arg) == 3 and arg[0] == "index" and arg[1] == ["param", param]
                and _mentions_rangeindex(arg[2])):
            return None
        ranges = [lp for lp in loops if lp.get("kind") == "range"]
        if len(ranges) != 1:
            return None
        lp = ranges[0]
        if (lp.get("limit"), lp.get("init"), lp.get("step"), lp.get("exits")) != (["len", ["param", param]],
                                                                                  ["const", 0], 1, []):
            return None
        return "item", k, f
    return None


def expected_channels(sidecar: dict, document: dict, config: dict) -> dict:
    """{component: {"carrier": id, "type", "count": "Len_<id>", "channels": {name: entry}}} by rule C1."""
    fns = document["go"]["functions"]
    stores = document["go"]["slices"]["stores"]
    loops = document["go"]["loops"]
    prims = config.get("primitives") or {}
    out = {}
    for comp, c in sorted(sidecar["components"].items()):
        chans = {}
        for fid, f in sorted(fns.items()):
            m = GO_METHOD.fullmatch(fid)
            ps = f.get("params") or []
            hits = [p["name"] for p in ps if p.get("type") == c["carrier"]]
            if not m or m.group(1) != "*" or not ps or not hits:
                continue
            if len(hits) > 1:
                raise AssertionError(f"{fid}: two parameters of the carrier's type")
            recv, param = ps[0]["name"], hits[0]
            mine = [lp for lp in loops if lp.get("function") == fid]
            for s in stores:
                if s.get("function") != fid:
                    continue
                ch = channel_of(s, recv, param, mine, prims)
                if ch is None:
                    continue
                kind, width, field = ch
                name = f"{go_name(fid)}_{field}"
                if name in chans:
                    raise AssertionError(f"two channels named {name}")
                chans[name] = {"source": fid, "param": param, "receiver": recv, "field": field, "kind": kind,
                               "width": width, "site": s.get("site")}
        cid = type_word(c["carrier"])
        out[comp] = {"carrier": cid, "type": c["carrier"], "count": f"Len_{cid}", "channels": dict(sorted(chans.items()))}
    return out


# ------------------------------------------------------------------ the expected laws (C3)
def _st(car: str, lhs: str, rhs: str) -> dict:
    return {"binders": [{"q": "forall", "name": "x", "type": car}], "assume": [],
            "claim": {"eq": [{"call": lhs, "args": [{"var": "x"}]}, {"call": rhs, "args": [{"var": "x"}]}]},
            "scope": {"kind": "unbounded"}}


def expected_laws(comp: dict) -> tuple[dict, dict]:
    """({law id: statement}, {cycle candidate id: kept id}) of rule C3 over one component: P3 gives one law per pair of
    channels p < q (by name) of one function; P8's spanning tree over the two carriers takes the first channel by name
    (the root is the count carrier, the smaller id) and every other channel e is a non-tree edge whose cycle states
    [e(x), t(x)] with t the tree channel: a duplicate of P3's law when e and t cite one function, else a law
    L_par_cy_<e>. No other producer gives anything (no atom, no interface carrier, no version)."""
    car, ch = comp["carrier"], comp["channels"]
    names = sorted(ch)
    laws, canon = {}, {}
    for i, p in enumerate(names):
        for q in names[i + 1:]:
            if ch[p]["source"] == ch[q]["source"]:
                lid = f"L_par_br_{p}_{q}"
                laws[lid] = _st(car, p, q)
                canon[frozenset((p, q))] = lid
    dups = {}
    if names:
        t = names[0]
        for e in names[1:]:
            cid = f"L_par_cy_{e}"
            key = frozenset((e, t))
            if key in canon:
                dups[cid] = canon[key]
            else:
                laws[cid] = _st(car, e, t)
                canon[key] = cid
    return dict(sorted(laws.items())), dups


# ------------------------------------------------------------------ the model's semantics (C4)
def channel_value(channel: dict, n: int) -> int:
    """The count a channel records after one call on a parameter of length n, from the receiver's zero value."""
    if channel["kind"] == "item":
        return n
    if channel["kind"] == "wrap":
        return n % (1 << channel["width"])
    raise AssertionError(f"unknown channel kind {channel['kind']!r}")


def candidates(channels: list[dict]) -> list[int]:
    """Rule C5's candidates for a law over these channels: 2^w per distinct wrap width w, ascending, then 0."""
    return sorted({1 << c["width"] for c in channels if c["kind"] == "wrap"}) + [0]


def witness(channels: list[dict]) -> int | None:
    """The first candidate at which the channels' values are not all equal, else None."""
    for n in candidates(channels):
        if len({channel_value(c, n) for c in channels}) > 1:
            return n
    return None
