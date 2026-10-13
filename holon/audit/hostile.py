"""Auditor A2 of audit round M2/2 (I21): hostile input at every interface carrier, through public entry points
(whitepaper §9.5 A2, Def 4.1 and §8.3 R^ext, §9.6 finding filter). The contract is the docstring of
tests_m2/test_audit_extraction.py; the instrument is the frozen sidecar spec/M2/lib/audit_round2.json.

    python -m holon audit hostile --milestone M2 --round 2 [--surface S ...] [--checkout PATH] [--snapshot DIR]
                                  [--out FILE] [--target COMMIT] [--work DIR] [--jobs N] [--check]

(--checkout is the pinned source checkout, config/holon.json replay; the replay configuration's own key for it is
accepted as an alias, so the contract's spelling works too.)

What it does. The round audits one commit of the project branch, its target commit: that commit's tree is
materialized in a scratch directory (git archive; Git LFS objects are smudged) and every repository input is read
from there. The real code runs in scratch copies of the pinned checkout (nothing is ever written to it), with the
harness sources of audit/rounds/M2/round2/harness/ copied in. The model side is only the extracted documents of the
target tree (spec/M2/facts/*.extracted.json, whose path conditions are evaluated here term by term) and the compiled
models (holon.model_eval for the frozen header facts; holon.mpipeline's compiled machine for the batch-data facts;
I20's extracted rollup model through holon.replay_fragments). tests/reference/ is never read (AGENTS rule 5).
Nothing here names the target: names come from the sidecar, the documents, the compiled artifacts and the harnesses.

Surfaces (sidecar "surfaces"; the sidecar's corpora are minimums):
  sol_loader     the header corpus through every non-dominated call site of the sidecar's loader, each by its public
                 function, from a state where every check before the call site passes (the Solidity harness builds
                 the states and calls); plus the sidecar's malformed ABI encodings of the header argument
  sol_encoder    the encoder corpus through the sidecar's entry points, every other field, the state and blobs valid
  go_header      the header corpus through every exported method of the sidecar's Go packages, by name
  go_encoders    the sidecar's encoders, one field varied at a time from the zero struct (fields and widths from the
                 document's encoder layout), the cache field in {nil, 1 byte, the encoder's own length}
  rollup_act     every action I20's extracted model compiles, one parameter varied at a time from a succeeding base
                 call, from the post-genesis state and from a corpus state where the base call succeeds
  batchdata_act  the sidecar's constructor, every sequence of at most 3 appends (block contexts {0,1,58,59,60,61,120}
                 bytes, payloads {0,1,4096} bytes, {0,1,2} L1 hashes), then each method once; each on a nil receiver
  go_consumer    the derivation's two entry points on the header corpus inside a commit's calldata under each of the
                 sidecar's selectors, and on the real calldata and blobs of every commit of I59's replay (the
                 snapshot, every object checked against its sha256 in the target tree's historical index)

Output: audit/rounds/M2/round2/a2.json (canonical JSON, json.dumps(indent=2, sort_keys=True) + newline; no
timestamps). --check reads target_commit from the committed file, reruns everything from that commit's tree, and
exits 0 iff the result equals the committed file byte for byte.

Classification. Every mismatch gets a class (unexplained, implicit, debt, assumption), decided mechanically from the
documents by the classify_* functions below, never from a prediction. An unexplained mismatch, and a panic at a safe
or unexplained site, carries the id of the audit/M2_findings.jsonl line of this round whose "a2_keys" lists its key
(its id, or its group); none until the auditor has filed it.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = Path("audit") / "rounds" / "M2" / "round2" / "harness"
OUT = Path("audit") / "rounds" / "M2" / "round2" / "a2.json"
SIDECAR = Path("spec") / "M2" / "lib" / "audit_round2.json"
FINDINGS = Path("audit") / "M2_findings.jsonl"
INDEX = Path("results") / "M2" / "historical" / "index.json"
REPLAY = Path("results") / "M2" / "historical" / "replay.json"
ROUND = "M2/round2"
# the round's surfaces, in the sidecar's order (its "surfaces" keys)
SURFACES = tuple(json.loads((ROOT / SIDECAR).read_text())["surfaces"]) if (ROOT / SIDECAR).is_file() else ()
ZERO_ADDR = "0x" + "00" * 20
FRESH = "0x" + "00" * 18 + "dead"
BD_CTX_LENGTHS = (0, 1, 58, 59, 60, 61, 120)    # the contract's batchdata_act corpus, in its order
BD_PAYLOAD_LENGTHS = (0, 1, 4096)
BD_HASHES = (0, 1, 2)
BD_DEPTH = 3
ERROR_STRING = "08c379a0"
PANIC = "4e487b71"


class HostileError(RuntimeError):
    pass


def canonical(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_json(obj) -> str:
    return sha256_hex(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode())


def hx(b: bytes) -> str:
    return "0x" + bytes(b).hex()


def unhex(s: str) -> bytes:
    if not isinstance(s, str) or not s.startswith("0x"):
        raise HostileError(f"not a 0x string: {str(s)[:40]}")
    return bytes.fromhex(s[2:])


def log(msg: str) -> None:
    print(f"hostile: {msg}", file=sys.stderr, flush=True)


def run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 14400) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), env={**os.environ, **(env or {})}, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def keccak(b: bytes) -> str:
    from ..keccak import keccak256
    return hx(keccak256(bytes(b)))


# ---------------------------------------------------------------- the target commit's tree
def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise HostileError(f"git {' '.join(args)} failed: {p.stderr.strip()[-400:]}")
    return p.stdout


def resolve_commit(c: str) -> str:
    sha = git("rev-parse", "--verify", f"{c}^{{commit}}").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise HostileError(f"cannot resolve {c!r} to a commit")
    return sha


def materialize(commit: str, dest: Path) -> Path:
    """The commit's tree in dest (git archive; Git LFS objects are smudged by archive's working-tree filters). A file
    that is still an LFS pointer fails: the instrument never reads a pointer as data."""
    shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True)
    tar = dest.parent / (dest.name + ".tar")
    p = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", "-o", str(tar), commit],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise HostileError(f"git archive {commit} failed: {p.stderr[-400:]}")
    p = subprocess.run(["tar", "-xf", str(tar), "-C", str(dest)], capture_output=True, text=True)
    tar.unlink(missing_ok=True)
    if p.returncode != 0:
        raise HostileError(f"untar failed: {p.stderr[-400:]}")
    for f in dest.rglob("*.json"):
        if f.stat().st_size < 1024 and f.read_bytes().startswith(b"version https://git-lfs"):
            raise HostileError(f"{f.relative_to(dest)} is a Git LFS pointer in the archive of {commit}: git lfs pull")
    return dest


def load(tree: Path, rel: str):
    return json.loads((Path(tree) / rel).read_text())


# ---------------------------------------------------------------- corpora (sidecar)
def _span(fb) -> list[int]:
    return list(range(fb["from"], fb["to"] + 1)) if isinstance(fb, dict) else list(fb)


def header_inputs(spec: dict, seed: int) -> list[bytes]:
    """The empty string (when the spec says so), then b0 ascending, then L in the order of lengths: b0 followed by the
    first L-1 bytes of sha256("I21:<seed>:<b0>:<L>:0") || sha256("I21:<seed>:<b0>:<L>:1") || ..."""
    out = [b""] if spec["empty"] else []
    for b0 in _span(spec["first_bytes"]):
        for n in spec["lengths"]:
            body, k = b"", 0
            while len(body) < n - 1:
                body += hashlib.sha256(f"I21:{seed}:{b0}:{n}:{k}".encode()).digest()
                k += 1
            out.append(bytes([b0]) + body[:n - 1])
    return out


def encoder_inputs(spec: dict) -> list[tuple[int, bytes, bytes]]:
    """(version, first root, second root) in the sidecar's order; roots "0", R1 and R2 per the sidecar's rules."""
    root = {"0": bytes(32)}
    for k in ("R1", "R2"):
        m = re.fullmatch(r'sha256\("([^"]*)"\)', spec[k])
        if not m:
            raise HostileError(f"encoder corpus: cannot read {k} = {spec[k]!r}")
        root[k] = hashlib.sha256(m.group(1).encode()).digest()
    return [(v, root[a], root[b]) for v in _span(spec["versions"]) for a, b in spec["roots"]]


def digest(inputs: list[bytes]) -> str:
    return sha256_hex(b"".join(len(x).to_bytes(4, "big") + x for x in inputs))


def encoder_bytes(e: tuple[int, bytes, bytes]) -> bytes:
    return bytes([e[0]]) + e[1] + e[2]


def chain_bytes(seed: int, tag: str, n: int) -> bytes:
    body, k = b"", 0
    while len(body) < n:
        body += hashlib.sha256(f"I21:{seed}:{tag}:{n}:{k}".encode()).digest()
        k += 1
    return body[:n]


# ---------------------------------------------------------------- the findings ledger (this round's lines)
def round_findings(root: Path = ROOT) -> dict[str, str]:
    """{a2 key: finding id} from this round's ledger lines ("a2_keys")."""
    p = Path(root) / FINDINGS
    out: dict[str, str] = {}
    if not p.exists():
        return out
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        f = json.loads(line)
        if f.get("round") != ROUND:
            continue
        for k in f.get("a2_keys") or []:
            out.setdefault(k, f["id"])
    return out


# ---------------------------------------------------------------- term evaluation
class Opaque(Exception):
    """A term the evaluator cannot compute from the inputs (an opaque call's result, an allocation, content it was
    not given, ...)."""


class Blob:
    """A byte string known by its length only (a receiver field the harness reports by reflection)."""

    def __init__(self, n: int):
        self.n = int(n)

    def __len__(self):
        return self.n

    def __getitem__(self, k):
        if isinstance(k, slice):
            lo, hi, _ = k.indices(self.n)
            return Blob(max(0, hi - lo))
        raise Opaque("the content of a byte string known by its length only")


class Ptr:
    """A non-nil pointer whose target the harness does not report."""


def sol_eval(t, env: dict):
    """A term of the Solidity frontend's codec documents (loader and encoder conditions) on concrete inputs."""
    if isinstance(t, bool) or isinstance(t, int):
        return t
    if isinstance(t, str):
        if t not in env:
            raise Opaque(f"unbound {t}")
        return env[t]
    if not isinstance(t, list) or not t:
        raise Opaque(f"term {t!r}")
    h = t[0]
    if h == "len":
        return len(sol_eval(t[1], env))
    if h == "byte":
        b = sol_eval(t[1], env)
        i = sol_eval(t[2], env)
        if i >= len(b):
            raise Opaque("byte out of range")
        return b[i]
    if h == "!":
        return not sol_eval(t[1], env)
    if h == "&&":
        return all(sol_eval(x, env) for x in t[1:])
    if h == "||":
        return any(sol_eval(x, env) for x in t[1:])
    a = [sol_eval(x, env) for x in t[1:]]
    ops = {"==": lambda x, y: x == y, "!=": lambda x, y: x != y, "<": lambda x, y: x < y, "<=": lambda x, y: x <= y,
           ">": lambda x, y: x > y, ">=": lambda x, y: x >= y, "+": lambda x, y: x + y, "-": lambda x, y: x - y,
           "*": lambda x, y: x * y}
    if h in ops and len(a) == 2:
        return ops[h](*a)
    raise Opaque(f"operator {h}")


def sol_vars(t, acc: list) -> list:
    """The variable names a Solidity document term reads, in order of first appearance."""
    if isinstance(t, str):
        if t not in acc:
            acc.append(t)
    elif isinstance(t, list) and t:
        # a term is [operator, operands..]; a list whose head is no operator is a list of terms (a path's conds)
        for x in (t[1:] if isinstance(t[0], str) else t):
            sol_vars(x, acc)
    return acc


def select_paths(paths: list[dict], holds) -> tuple[list[int], bool]:
    """(indices of the paths whose conditions all hold, whether some path could not be decided)."""
    hit, undecided = [], False
    for k, p in enumerate(paths):
        ok = True
        try:
            for c in p.get("cond") or []:
                if not holds(c):
                    ok = False
                    break
        except Opaque:
            undecided = True
            continue
        if ok:
            hit.append(k)
    return hit, undecided


NIL = None


def _cmp_eq(x, y) -> bool:
    if isinstance(x, (Blob, Ptr)) or isinstance(y, (Blob, Ptr)):
        if x is NIL or y is NIL:
            return False
        raise Opaque("equality of content not given")
    return x == y


def go_eval(t, env: dict):
    """A term of the Go frontend's documents on concrete inputs: params are bytes, Blobs, ints, dicts (structs), Ptr or
    None (nil). Calls, results, globals, allocations and zero values are opaque."""
    if not isinstance(t, list) or not t:
        raise Opaque(f"term {t!r}")
    h = t[0]
    if h == "param":
        if t[1] not in env:
            raise Opaque(f"unbound param {t[1]}")
        return env[t[1]]
    if h == "const":
        return t[1]
    if h == "nil":
        return NIL
    if h == "true":            # ["true"] is the constant; ["true", x] says x evaluates to true
        return True if len(t) == 1 else bool(go_eval(t[1], env))
    if h == "false":
        return False if len(t) == 1 else not go_eval(t[1], env)
    if h == "str":
        return t[1]
    if h == "len":
        v = go_eval(t[1], env)
        if v is NIL:
            return 0
        if isinstance(v, Ptr):
            raise Opaque("len of a pointer target")
        return len(v)
    if h == "index":
        v = go_eval(t[1], env)
        i = go_eval(t[2], env)
        if v is NIL or not (0 <= i < len(v)):
            raise Opaque("index out of range in a condition")
        return v[i]
    if h == "field":
        v = go_eval(t[1], env)
        if not isinstance(v, dict) or t[2] not in v:
            raise Opaque(f"field {t[2]}")
        return v[t[2]]
    if h == "slice":
        v = go_eval(t[1], env)
        v = b"" if v is NIL else v
        lo = 0 if t[2] is None else go_eval(t[2], env)
        hi = len(v) if t[3] is None else go_eval(t[3], env)
        if not (0 <= lo <= hi <= len(v)):
            raise Opaque("slice out of range in a condition")
        return v[lo:hi]
    if h == "append":
        parts = [go_eval(x, env) for x in t[1:]]
        if any(isinstance(p, Blob) for p in parts):
            return Blob(sum(len(p) for p in parts if p is not NIL))
        out = b""
        for p in parts:
            if p is NIL:
                continue
            if isinstance(p, list):
                out += b"".join(bytes(x) for x in p)
            else:
                out += bytes(p)
        return out
    if h == "op":
        o = t[1]
        a = [go_eval(x, env) for x in t[2:]]
        fn = {"+": lambda x, y: x + y, "-": lambda x, y: x - y, "*": lambda x, y: x * y,
              "/": lambda x, y: x // y, "%": lambda x, y: x % y, "&": lambda x, y: x & y, "|": lambda x, y: x | y,
              "^": lambda x, y: x ^ y, "<<": lambda x, y: x << y, ">>": lambda x, y: x >> y}.get(o)
        if fn is None or len(a) != 2 or not all(isinstance(x, int) for x in a):
            raise Opaque(f"op {o}")
        return fn(*a)
    if h in ("==", "!="):
        x, y = go_eval(t[1], env), go_eval(t[2], env)
        e = _cmp_eq(x, y)
        return e if h == "==" else not e
    if h in ("<", "<=", ">", ">="):
        x, y = go_eval(t[1], env), go_eval(t[2], env)
        if not (isinstance(x, int) and isinstance(y, int)):
            raise Opaque("ordered comparison of non-integers")
        return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[h]
    if h == "!":
        return not go_eval(t[1], env)
    if h in ("&&", "||"):
        vals = [go_eval(x, env) for x in t[1:]]
        return all(vals) if h == "&&" else any(vals)
    raise Opaque(f"{h} is opaque")


def go_holds(env: dict):
    return lambda c: bool(go_eval(c, env))


def go_expected(fn: dict, env: dict) -> tuple[str, int | None, str]:
    """(expected label, the path index, its panic site) of a Go function on concrete inputs, from its extracted paths:
    ok | error | panic | none (no path holds) | many | undecided (a condition needs a term the evaluator cannot
    compute from the inputs) | nopaths (the document records no path set)."""
    paths = fn.get("paths")
    if not paths:
        return "nopaths", None, ""
    hit, undecided = select_paths(paths, go_holds(env))
    if not hit:
        return ("undecided" if undecided else "none"), None, ""
    if len(hit) > 1:
        return "many", None, ""
    p = paths[hit[0]]
    if p.get("end") == "panic":
        return "panic", hit[0], p.get("site") or ""
    return ("error" if p.get("error") == "nonnil" else "ok"), hit[0], ""


def decoder_value(reads: list[dict], b: bytes) -> str | None:
    """The value a document's codecs.decoders entry says a decoder returns on b, as big-endian bytes."""
    out = b""
    for r in reads:
        off, w = r["offset"], r["width"]
        if off + w > len(b):
            return None
        out += b[off:off + w]
    return hx(out)


# ---------------------------------------------------------------- the frozen M0 model (compiled; holon.model_eval)
class Frozen:
    """The frozen codec facts of the target tree, compiled with the pinned Bend and run in node."""

    def __init__(self, path: Path, rel: str):
        from .. import facts as F
        from ..model_eval import CompiledModel
        self.rel = rel
        self.model = CompiledModel.build(path)
        self.facts = self.model.facts
        self.F = F
        self.widths = F.widths(self.facts)
        self.memo: dict = {}

    def run(self, fn: str, inputs: list) -> list:
        """The function on every input. A Bytes result is "0x.." when every cell is a byte, {"undefined": True} when it
        is the model's UNDEF sentinel (a one-cell list whose cell is no byte: audit M2/1 F-M2-36), else {"cells": [..]}
        (a defined result holding unknown memory cells)."""
        from ..model_eval import ModelError, value_in, value_out
        key = (fn, sha_json(inputs))
        if key in self.memo:
            return self.memo[key]
        arg_t, res_t = self.F.fn_types(self.facts, fn)
        out = []
        for i in range(0, len(inputs), 2000):
            chunk = inputs[i:i + 2000]
            jobs = [{"terms": [{"call": fn, "args": [{"var": "x"}]}], "env": {"x": value_in(arg_t, x, self.facts)}}
                    for x in chunk]
            for (v,) in self.model.run_jobs(jobs, timeout=3600):
                if isinstance(v, dict) and "error" in v:
                    raise HostileError(f"frozen {fn}: {v['error']}")
                if res_t == "Bytes":
                    if len(v) == 1 and not 0 <= v[0] <= 255:
                        out.append({"undefined": True})
                    elif all(0 <= x <= 255 for x in v):
                        out.append(hx(bytes(v)))
                    else:
                        out.append({"cells": list(v)})
                    continue
                try:
                    out.append(value_out(res_t, v))
                except ModelError as e:
                    raise HostileError(f"frozen {fn}: {e}")
        self.memo[key] = out
        return out

    def header(self, **fields) -> dict:
        """A Header of the frozen facts: every field zero but the given ones (bytes or ints, right-aligned)."""
        h = {}
        for name, w in self.widths.items():
            v = fields.get(name, b"")
            if isinstance(v, int):
                v = v.to_bytes(w, "big")
            if len(v) > w:
                raise HostileError(f"{name}: {len(v)} bytes for width {w}")
            h[name] = hx(bytes(w - len(v)) + v)
        return h


def frozen_label(v) -> str:
    """A frozen predicate, encoder or decoder value as an expectation: ok (true or defined) or rejected."""
    if v is False or v is None or (isinstance(v, dict) and v.get("undefined")):
        return "rejected"
    return "ok"


# ---------------------------------------------------------------- records
class Surface:
    """One surface's record (a2.json surfaces.<name>)."""

    def __init__(self, name: str, carrier: str, models: list[str]):
        self.name, self.carrier, self.models = name, carrier, list(models)
        self.entry_points: list[dict] = []
        self.inputs = 0
        self.abi_rejected = 0
        self.outcomes: dict[str, int] = {}
        self.paths = None
        self.mismatches: dict[str, dict] = {}
        self.panics: dict[tuple, dict] = {}
        self.extra: dict = {}
        self.labels_by_action: dict[str, set] = {}   # rollup_act: the outcome labels per action (mutant choice)

    def entry(self, name: str, site: str | None = None, dominated_by=None) -> dict:
        for e in self.entry_points:
            if e["name"] == name and e["site"] == site:
                return e
        e = {"name": name, "site": site, "inputs": 0, "dominated_by": dominated_by}
        self.entry_points.append(e)
        return e

    def outcome(self, label: str, n: int = 1, entry: str | None = None) -> None:
        self.outcomes[label] = self.outcomes.get(label, 0) + n
        if entry is not None:
            d = self.extra_outcomes.setdefault(entry, {})
            d[label] = d.get(label, 0) + n

    @property
    def extra_outcomes(self) -> dict:
        """Outcome counts per entry point (not part of the record; codec_labels reads them)."""
        if not hasattr(self, "_per_entry"):
            self._per_entry = {}
        return self._per_entry

    def mismatch(self, model: str, entry: str, inp, expected: str, real: str, cls: str, explained_by, why: str,
                 group: str | None = None, **extra) -> dict:
        mid = "M-" + sha_json([self.name, model, entry, inp])[:16]
        m = {"id": mid, "model": model, "entry": entry, "input": inp, "expected": expected, "real": real,
             "class": cls, "explained_by": explained_by, "why": why, "finding": None,
             "group": group or f"{self.name}|{model}|{entry}|{expected}|{real}", **extra}
        self.mismatches.setdefault(mid, m)
        return m

    def panic(self, function: str, site: str, status: str, witness, explained_by=None, why: str | None = None) -> dict:
        key = (function, site)
        p = self.panics.get(key)
        if p is None:
            p = {"function": function, "site": site, "site_status": status, "witness": witness,
                 "explained_by": explained_by, "finding": None, "count": 0, "why": why}
            self.panics[key] = p
        p["count"] += 1
        return p

    def record(self, findings: dict[str, str]) -> dict:
        ms = []
        for m in sorted(self.mismatches.values(), key=lambda x: x["id"]):
            if m["class"] == "unexplained":
                m["finding"] = findings.get(m["id"]) or findings.get(m["group"])
            ms.append(m)
        ps = []
        for p in sorted(self.panics.values(), key=lambda x: (x["function"], x["site"])):
            if p["site_status"] == "safe" or (p["site_status"] == "unrecorded" and p["explained_by"] is None):
                p["finding"] = findings.get(f"panic|{self.name}|{p['function']}|{p['site']}")
            ps.append(p)
        out = {"carrier": self.carrier, "models": sorted(self.models),
               "entry_points": sorted(self.entry_points, key=lambda e: (e["name"], e["site"] or "")),
               "inputs": self.inputs, "abi_rejected": self.abi_rejected,
               "outcomes": dict(sorted(self.outcomes.items())), "paths": self.paths, "mismatches": ms,
               "panics": ps}
        out.update(self.extra)
        return out

    def keys(self) -> set:
        return set(self.mismatches) | {f"panic|{f}|{s}" for f, s in self.panics
                                       if self.panics[(f, s)]["site_status"] == "safe"}


# ---------------------------------------------------------------- the run's context
class Ctx:
    """Everything one run reads: the target tree, the sidecar, the pinned checkout, toolchain and snapshot."""

    def __init__(self, tree: Path, work: Path, checkout: Path, snapshot: Path | None, commit: str, jobs: int = 2):
        self.tree, self.work, self.checkout, self.snapshot, self.commit = tree, work, checkout, snapshot, commit
        self.jobs = jobs
        self.side = load(tree, str(SIDECAR))
        self.seed = self.side["seed"]
        self.header = header_inputs(self.side["header_corpus"], self.seed)
        self.act_header = header_inputs(self.side["act_header_corpus"], self.seed)
        self.encoder = encoder_inputs(self.side["encoder_corpus"])
        self.cache: dict = {}
        self._lazy: dict = {}
        sl = self.side["surfaces"]["sol_loader"]["models"]
        self.loader_doc, self.loader_fn = next(m.split("#") for m in sl if m.startswith("spec/"))
        self.frozen_rel, self.frozen_pred = next(m.split("#") for m in sl if not m.startswith("spec/"))
        se = self.side["surfaces"]["sol_encoder"]["models"]
        self.encoder_doc, self.encoder_fn = next(m.split("#") for m in se if m.startswith("spec/"))
        self.frozen_encoder = next(m.split("#")[1] for m in se if not m.startswith("spec/"))

    def lazy(self, key: str, make):
        if key not in self._lazy:
            self._lazy[key] = make()
        return self._lazy[key]

    @property
    def frozen(self) -> "Frozen":
        return self.lazy("frozen", lambda: Frozen(self.tree / self.frozen_rel, self.frozen_rel))

    @property
    def sites(self) -> "GoSites":
        return self.lazy("sites", lambda: GoSites(self.tree))

    @property
    def go(self) -> "GoWorkspace":
        return self.lazy("go", lambda: GoWorkspace(self.checkout, self.work, self.go_packages()))

    @property
    def tc(self) -> dict:
        def make():
            from ..replay import toolchain
            return toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False), self.tree)
        return self.lazy("tc", make)

    def go_packages(self) -> list[str]:
        sc = self.side["surfaces"]
        pk = list(sc["go_header"]["packages"])
        pk.append(sc["batchdata_act"]["constructor"].rsplit(".", 1)[0])
        for k in sc["go_consumer"]["entry_points"]:
            pk.append(go_receiver(k)[0])
        return sorted(set(pk))

    def harness(self, rel: str) -> Path:
        return ROOT / HARNESS / rel


# ---------------------------------------------------------------- Go: names, the scratch workspace and the harnesses
def go_receiver(key: str) -> tuple[str, str | None, str]:
    """(package, receiver type or None, function) of a document's function key: "(*pkg.T).m", "(pkg.T).m", "pkg.f"."""
    m = re.fullmatch(r"\(\*?(.+)\.(\w+)\)\.(\w+)", key)
    if m:
        return m.group(1), m.group(2), m.group(3)
    pkg, f = key.rsplit(".", 1)
    return pkg, None, f


def method_keys(functions: dict, pkg: str, methods: list[str]) -> dict[str, str]:
    """{method: function key} for methods of one receiver type of pkg: the type every listed method has."""
    types: dict[str, dict] = {}
    for k in functions:
        p, t, f = go_receiver(k)
        if p == pkg and t is not None and f in methods:
            types.setdefault(t, {})[f] = k
    full = [t for t, ms in types.items() if set(ms) == set(methods)]
    if len(full) != 1:
        raise HostileError(f"{pkg}: no single receiver type has the methods {methods} (candidates {sorted(full)})")
    return types[full[0]]


class GoWorkspace:
    """A scratch copy of the pinned checkout's Go modules that the tested packages need (from its go.work and the
    modules' go.mod files), with a go.work, offline (GOPROXY=off)."""

    def __init__(self, checkout: Path, work: Path, packages: list[str]):
        self.ws = work / "go"
        shutil.rmtree(self.ws, ignore_errors=True)
        self.ws.mkdir(parents=True)
        uses = re.findall(r"^\s*\./(\S+)\s*$", (checkout / "go.work").read_text(), re.M)
        self.modules: dict[str, str] = {}
        reqs: dict[str, set] = {}
        for d in uses:
            gm = checkout / d / "go.mod"
            if not gm.exists():
                continue
            text = gm.read_text()
            m = re.search(r"^module\s+(\S+)", text, re.M)
            if m:
                self.modules[m.group(1)] = d
                reqs[m.group(1)] = set(re.findall(r"^\s*(?:require\s+)?(\S+)\s+v\S+", text, re.M))
        need: set = set()
        todo = [self.module_of(p)[0] for p in packages]
        quoted = re.compile(r'"([A-Za-z0-9_.\-/]+)"')
        while todo:
            mp = todo.pop()
            if mp in need:
                continue
            need.add(mp)
            todo += [r for r in reqs.get(mp, ()) if r in self.modules]
            # workspace modules resolve through go.work, not go.mod: follow the module's own Go imports
            for f in (checkout / self.modules[mp]).rglob("*.go"):
                for q in quoted.findall(f.read_text(errors="replace")):
                    for m in self.modules:
                        if (q == m or q.startswith(m + "/")) and m not in need:
                            todo.append(m)
        dirs = sorted(self.modules[m] for m in need)
        for d in dirs:
            shutil.copytree(checkout / d, self.ws / d, symlinks=True)
        (self.ws / "go.work").write_text("go 1.24.0\n\nuse (\n" + "".join(f"\t./{d}\n" for d in dirs) + ")\n")
        self.env = {"GOPROXY": "off", "GOFLAGS": "", "GOTOOLCHAIN": "local", "GOWORK": str(self.ws / "go.work")}

    def module_of(self, pkg: str) -> tuple[str, str, str]:
        """(module path, module dir, package dir inside the module) of a package path."""
        best = max((m for m in self.modules if pkg == m or pkg.startswith(m + "/")), key=len, default=None)
        if best is None:
            raise HostileError(f"no module of the checkout's go.work holds {pkg}")
        return best, self.modules[best], pkg[len(best):].lstrip("/") or "."

    def test(self, pkg: str, harness: Path, test: str, inp: dict, tag: str) -> list:
        """Copy the harness into the package's directory, run its test, and return its output lines (JSON arrays)."""
        _, mdir, sub = self.module_of(pkg)
        dst = self.ws / mdir / sub / harness.name
        shutil.copy(harness, dst)
        fin, fout = self.ws / f"{tag}.in.json", self.ws / f"{tag}.out.jsonl"
        fin.write_text(json.dumps(inp))
        fout.unlink(missing_ok=True)
        code, out = run(["go", "test", f"./{sub}", "-run", f"^{test}$", "-count=1", "-timeout", "0"],
                        self.ws / mdir, {**self.env, "HOLON_HOSTILE_IN": str(fin), "HOLON_HOSTILE_OUT": str(fout)})
        dst.unlink(missing_ok=True)
        if code != 0 or not fout.exists():
            raise HostileError(f"Go harness {harness.name} failed (exit {code}): {out[-3000:]}")
        lines = [json.loads(x) for x in fout.read_text().splitlines() if x.strip()]
        fin.unlink(missing_ok=True)
        fout.unlink(missing_ok=True)
        if not lines or lines[-1][0] != "DONE":
            raise HostileError(f"Go harness {harness.name} did not finish")
        return lines

    def rel(self, path: str) -> str:
        p = str(path)
        base = str(self.ws) + os.sep
        return p[len(base):] if p.startswith(base) else p


class GoSites:
    """The target tree's Go documents: every partiality site (id -> status; (file, line, kind) -> ids) and function."""

    def __init__(self, tree: Path, docs: dict | None = None):
        self.docs = docs if docs is not None else {
            p.relative_to(tree).as_posix(): json.loads(p.read_text())
            for p in sorted((tree / "spec" / "M2" / "facts").glob("*.go.extracted.json"))}
        self.status: dict[str, str] = {}
        self.by_line: dict[tuple, list[str]] = {}
        self.where: dict[str, str] = {}
        for rel, doc in sorted(self.docs.items()):
            for k, v in doc["go"]["functions"].items():
                self.where.setdefault(k, rel)
                for st in v.get("sites") or []:
                    self.status[st["id"]] = st["status"]
                    m = re.fullmatch(r"(.+):(\d+):(\d+):(\w+)", st["id"])
                    if m:
                        self.by_line.setdefault((m.group(1), int(m.group(2)), m.group(4)), []).append(st["id"])

    def resolve(self, file: str, line: int, kind: str) -> tuple[str, str]:
        """(site id, status) of a panic at file:line of that kind: the document's site when a site of the kind is
        recorded on that line (the lowest column when several are), else file:line, unrecorded."""
        ids = sorted(set(self.by_line.get((file, line, kind), [])), key=lambda s: int(s.split(":")[-2]))
        if ids:
            return ids[0], self.status[ids[0]]
        return f"{file}:{line}", "unrecorded"

    def function(self, key: str) -> dict:
        rel = self.where.get(key)
        if rel is None:
            raise HostileError(f"no Go function {key} in the documents")
        return self.docs[rel]["go"]["functions"][key]

    def doc_of(self, key: str) -> str:
        return self.where[key]

    def functions(self, rel: str) -> dict:
        return self.docs[rel]["go"]["functions"]

    def decoders(self, rel: str) -> dict[str, list]:
        return {d["function"]: d["reads"] for d in self.docs[rel]["go"]["codecs"].get("decoders") or []}

    def encoders(self, rel: str) -> dict[str, list]:
        out: dict[str, list] = {}
        for e in self.docs[rel]["go"]["codecs"].get("encoders") or []:
            out.setdefault(e["function"], []).append(e)
        return out

    def assumption_ids(self, rel: str) -> set:
        return {a["id"] for a in self.docs[rel].get("assumptions") or []}


def go_label(tok: str) -> str:
    """A harness token as an outcome label: ok, error or panic."""
    if tok.startswith("o"):
        return "ok"
    if tok.startswith("e:"):
        return "error"
    if tok.startswith("p:"):
        return "panic"
    raise HostileError(f"harness token {tok[:60]!r}")


def go_panic(tok: str, ws: GoWorkspace) -> tuple[str, int, str, str]:
    m = re.fullmatch(r"p:(.*?):(\d+):(\w+):(.*)", tok, re.S)
    if not m:
        raise HostileError(f"panic token {tok[:80]!r}")
    return ws.rel(m.group(1)), int(m.group(2)), m.group(3), m.group(4)


def record_go_panic(ctx: Ctx, s: Surface, function: str, tok: str, witness, sites: GoSites | None = None
                    ) -> tuple[str, str, str]:
    """Record a Go panic on the surface; returns (site, status, kind)."""
    sites = sites or ctx.sites
    file, line, kind, msg = go_panic(tok, ctx.go)
    site, status = sites.resolve(file, line, kind)
    expl, why = None, None
    if status == "unrecorded" and kind == "nil":
        expl = "go-nil-deref-not-modelled"
        why = (f"a nil pointer dereference ({msg[:80]}); the Go documents state that nil pointer dereferences are not "
               "partiality sites")
    elif status == "open":
        why = f"decides the open site {site}: reachable ({msg[:80]})"
    elif status == "safe":
        why = f"a panic at {site}, a site the document marks safe ({msg[:80]})"
    else:
        why = f"a panic at {site}, where no document records a site ({msg[:80]})"
    s.panic(function, site, status, witness, expl, why)
    return site, status, kind


# ---------------------------------------------------------------- the Go harness runs (real side; cached per run)
def _go_kind(ty: str) -> str:
    if ty == "[]byte":
        return "bytes"
    if ty.startswith("[]"):
        return "hashes"           # the only other slice parameters here: 32-byte hashes (L1 transaction hashes)
    if ty in ("int", "int64", "uint64", "uint", "int32", "uint32"):
        return "int"
    raise HostileError(f"no hostile values for a parameter of type {ty}")


def go_args(params: list[dict], byte_values: list[bytes], hashes: list[bytes], number: int = 0) -> tuple[list, dict]:
    """(JSON arguments for the harness, the same values for the document's terms) of a method's parameters (receiver
    excluded): the k-th []byte parameter gets byte_values[k], a slice of hashes gets hashes, an integer gets number."""
    js, env, bi = [], {}, 0
    for p in params:
        k = _go_kind(p["type"])
        if k == "bytes":
            v = byte_values[bi]
            bi += 1
            js.append(hx(v))
            env[p["name"]] = v
        elif k == "hashes":
            js.append([hx(h) for h in hashes])
            env[p["name"]] = list(hashes)
        else:
            js.append(number)
            env[p["name"]] = number
    return js, env


class BatchDataSpec:
    """The batchdata_act corpus: the constructor's package, the methods' document keys, the append arguments of
    every corpus combination (by the append method's parameters), and each method's single call."""

    def __init__(self, ctx: Ctx):
        sc = ctx.side["surfaces"]["batchdata_act"]
        self.constructor = sc["constructor"]
        self.pkg = self.constructor.rsplit(".", 1)[0]
        doc = next(m for m in sc["models"] if m.startswith("spec/M2/"))
        self.doc = doc
        fs = ctx.sites.functions(doc)
        self.methods = list(sc["methods"])
        self.keys = method_keys(fs, self.pkg, self.methods)
        abstract = load(ctx.tree, next(m for m in sc["models"] if not m.startswith("spec/M2/")))
        names = {a["name"].lower(): a["name"] for a in abstract["actions"]}
        self.append_method = next(m for m in self.methods if m.lower() in names and
                                  _go_kind_ok(fs[self.keys[m]]["params"][1:]) and
                                  len(next(a for a in abstract["actions"] if a["name"].lower() == m.lower())["inputs"]) > 0)
        seed = ctx.seed
        self.combos = []
        for bl in BD_CTX_LENGTHS:
            for pl in BD_PAYLOAD_LENGTHS:
                for nh in BD_HASHES:
                    self.combos.append((chain_bytes(seed, "bctx", bl), chain_bytes(seed, "payload", pl),
                                        [hashlib.sha256(f"I21:{seed}:l1hash:{j}".encode()).digest()
                                         for j in range(nh)]))
        ap = fs[self.keys[self.append_method]]["params"][1:]
        self.append_js = [go_args(ap, [c[0], c[1]], c[2])[0] for c in self.combos]
        self.append_env = [go_args(ap, [c[0], c[1]], c[2])[1] for c in self.combos]
        b60, b1 = chain_bytes(seed, "call:bctx", 60), chain_bytes(seed, "call:payload", 1)
        h1 = [hashlib.sha256(f"I21:{seed}:call:l1hash".encode()).digest()]
        self.call_js, self.call_env = {}, {}
        for m in self.methods:
            js, env = go_args(fs[self.keys[m]]["params"][1:], [b60, b1], h1)
            self.call_js[m], self.call_env[m] = js, env
        self.sequences = [s for d in range(BD_DEPTH + 1) for s in itertools.product(range(len(self.combos)), repeat=d)]


def _go_kind_ok(params: list[dict]) -> bool:
    try:
        return all(_go_kind(p["type"]) for p in params)
    except HostileError:
        return False


def encoder_spec(fn: dict, encs: list[dict]) -> tuple[list[tuple], str | None]:
    """([(field path, width)], cache field) of an encoder: the fields its layout cells read (width: the highest byte
    index + 1) and the field its paths' conditions measure (the cache)."""
    widths: dict[tuple, int] = {}

    def fpath(t):
        if isinstance(t, list) and t and t[0] == "field":
            return fpath(t[1]) + (t[2],)
        if isinstance(t, list) and t and t[0] == "param":
            return ()
        raise HostileError(f"encoder cell term {t}")
    for e in encs:
        for c in e["cells"]:
            if c[0] == "byte":
                p = fpath(c[1])
                widths[p] = max(widths.get(p, 0), c[2] + 1)
    cache = None
    for p in fn.get("paths") or []:
        for c in p.get("cond") or []:
            for side in c[1:]:
                if isinstance(side, list) and side[:1] == ["len"] and side[1][:1] == ["field"]:
                    cache = fpath(side[1])
    return sorted(widths.items()), cache


def set_field(struct: dict, path: tuple, v) -> None:
    for p in path[:-1]:
        struct = struct.setdefault(p, {})
    struct[path[-1]] = v


def encoder_inputs_go(ctx: Ctx) -> list[dict]:
    """go_encoders inputs: for every entry point, the zero struct, then one field at a time (a field of 8 bytes in
    {0, 1, 2^64 - 1}, of 32 bytes in {0x00..00, 0xff..ff}, else {0, 1, max}), then the cache in {nil, 1 byte, the
    encoder's own length}."""
    sc = ctx.side["surfaces"]["go_encoders"]
    out, seen = [], set()
    for key in sc["entry_points"]:
        rel = ctx.sites.doc_of(key)
        fn = ctx.sites.function(key)
        encs = ctx.sites.encoders(rel).get(key, [])
        fields, cache = encoder_spec(fn, encs)
        length = max(e["length"] for e in encs)
        zero = {p: bytes(w) for p, w in fields}
        variants = [({}, None)]
        for p, w in fields:
            vals = [bytes(w), b"\xff" * w] if w == 32 else [bytes(w), (1).to_bytes(w, "big"), b"\xff" * w]
            for v in vals:
                variants.append(({p: v}, None))
        for enc in (None, b"\x01", bytes((i * 7 + 1) % 256 for i in range(length))):
            variants.append(({}, enc))
        for fv, enc in variants:
            vals = {**zero, **fv}
            item = {"key": key, "fields": {p[-1]: hx(v) for p, v in vals.items()},
                    "encoded": None if enc is None else hx(enc)}
            k = json.dumps(item, sort_keys=True)
            if k in seen:
                continue
            seen.add(k)
            struct: dict = {}
            for p, v in vals.items():
                set_field(struct, p, v)
            if cache is not None:
                set_field(struct, cache, enc)
            item["_struct"] = struct
            out.append(item)
    return out


def run_go_batch(ctx: Ctx) -> dict:
    """The in-package harness of the batch-data constructor's package: go_header's methods of that package (and
    validate), go_encoders, batchdata_act."""
    if "go_batch" in ctx.cache:
        return ctx.cache["go_batch"]
    sc = ctx.side["surfaces"]
    bd = BatchDataSpec(ctx)
    methods = sc["go_header"]["packages"][bd.pkg]["methods"]
    encs = encoder_inputs_go(ctx)
    inp = {"headers": [hx(h) for h in ctx.header], "methods": methods,
           "encoders": [{"type": go_receiver(e["key"])[1], "fields": e["fields"], "encoded": e["encoded"]} for e in encs],
           "sequences": {"append": bd.append_js, "depth": BD_DEPTH, "methods": bd.methods, "call": bd.call_js}}
    log(f"go: {bd.pkg} harness ({len(ctx.header)} headers x {len(methods)} methods, {len(encs)} encoder inputs, "
        f"{len(bd.sequences)} append sequences x {len(bd.methods)} methods)")
    lines = ctx.go.test(bd.pkg, ctx.harness("go/holon_hostile_batch_test.go"), "TestHolonHostileBatch", inp, "batch")
    res = {"bd": bd, "encoders": encs, "H": {}, "V": {}, "E": {}, "B": [], "N": {}, "F": None}
    for ln in lines:
        if ln[0] == "F":
            res["F"] = (ln[1], ln[2])
        elif ln[0] == "H":
            res["H"][(ln[1], ln[2])] = ln[3]
        elif ln[0] == "V":
            res["V"][ln[1]] = ln[2]
        elif ln[0] == "E":
            res["E"][ln[1]] = ln[2]
        elif ln[0] == "B":
            res["B"].append(ln)
        elif ln[0] == "N":
            res["N"][ln[1]] = ln[2]
    if len(res["B"]) != len(bd.sequences):
        raise HostileError(f"batch data: {len(res['B'])} sequences ran, {len(bd.sequences)} expected")
    ctx.cache["go_batch"] = res
    return res


def run_go_other_headers(ctx: Ctx, pkg: str) -> dict:
    """go_header's methods of a package other than the batch-data one (an external-package harness by name)."""
    key = f"go_hdr:{pkg}"
    if key in ctx.cache:
        return ctx.cache[key]
    methods = ctx.side["surfaces"]["go_header"]["packages"][pkg]["methods"]
    log(f"go: {pkg} harness ({len(ctx.header)} headers x {len(methods)} methods)")
    lines = ctx.go.test(pkg, ctx.harness("go/holon_hostile_types_test.go"), "TestHolonHostileTypes",
                        {"headers": [hx(h) for h in ctx.header], "methods": methods}, "types")
    res = {(ln[1], ln[2]): ln[3] for ln in lines if ln[0] == "H"}
    ctx.cache[key] = res
    return res


# ---------------------------------------------------------------- surface go_header
def surface_go_header(ctx: Ctx, docs: dict | None = None) -> Surface:
    sc = ctx.side["surfaces"]["go_header"]
    sites = GoSites(ctx.tree, docs) if docs is not None else ctx.sites
    s = Surface("go_header", sc["carrier"], sc["models"])
    batch = run_go_batch(ctx)
    bpkg = batch["bd"].pkg
    s.inputs = len(ctx.header)
    covered, total = set(), 0
    for pkg, v in sorted(sc["packages"].items()):
        rel = v["document"]
        keys = method_keys(sites.functions(rel), pkg, v["methods"])
        real = batch["H"] if pkg == bpkg else run_go_other_headers(ctx, pkg)
        decs = sites.decoders(rel)
        for m in v["methods"]:
            key = keys[m]
            fn = sites.function(key)
            total += len(fn.get("paths") or [])
            e = s.entry(key)
            for i, h in enumerate(ctx.header):
                tok = real[(i, m)]
                lab = go_label(tok)
                e["inputs"] += 1
                s.outcome(lab, entry=key)
                exp, k, _ = go_expected(fn, {go_param(fn): h})
                if k is not None:
                    covered.add((key, k))
                inp = hx(h)
                if lab == "panic":
                    site, status, kind = record_go_panic(ctx, s, key, tok, [{"call": key, "args": [inp]}], sites)
                    if status == "safe":
                        s.mismatch(rel, key, inp, exp, f"panic:{site}", "unexplained", None,
                                   f"the method panicked at {site}, a site the document marks safe")
                        continue
                if exp in ("none", "many", "undecided", "nopaths"):
                    s.mismatch(rel, key, inp, exp, lab, "unexplained", None,
                               f"the input satisfies {exp} of the method's extracted paths")
                    continue
                if exp != lab:
                    s.mismatch(rel, key, inp, exp, lab, "unexplained", None,
                               "the real outcome differs from the outcome of the extracted path the input selects")
                    continue
                if lab == "ok" and key in decs:
                    want = decoder_value(decs[key], h)
                    got = tok[2:] if tok.startswith("o:") else None
                    if want != got:
                        s.mismatch(rel, key, inp, f"ok:{want}", f"ok:{got}", "unexplained", None,
                                   "the decoded value differs from the document's codecs.decoders reads",
                                   group=f"go_header|{rel}|{key}|value")
    s.paths = {"covered": len(covered), "total": total}
    frozen_ok_go_dec_go(ctx, s, batch, bpkg, sites)
    return s


def go_param(fn: dict) -> str:
    """The name of a method's receiver (its first parameter)."""
    return fn["params"][0]["name"]


def frozen_ok_go_dec_go(ctx: Ctx, s: Surface, batch: dict, pkg: str, sites: GoSites) -> None:
    """validate against the frozen ok_go, and the getters against the frozen dec_go, as the I16 binding reads dec_go
    (None when validate fails, else the getters' values in the facts' order, a getter that errors after validate
    passed being absent)."""
    fz = ctx.frozen
    hexes = [hx(h) for h in ctx.header]
    preds = [m.split("#")[1] for m in ctx.side["surfaces"]["go_header"]["models"] if "#" in m]
    binding = load(ctx.tree, "replay/M2/implementations.json")["edges"]
    ok_fn = next(p for p in preds if binding.get(p, {}).get("op") == "validate")
    dec_fn = next(p for p in preds if binding.get(p, {}).get("op") == "decode")
    okv = fz.run(ok_fn, hexes)
    decv = fz.run(dec_fn, hexes)
    getters = binding[dec_fn]["getters"]
    gdefs = fz.facts["functions"][dec_fn]["getters"]
    pk = ctx.side["surfaces"]["go_header"]["packages"][pkg]
    mkeys = method_keys(sites.functions(pk["document"]), pkg, pk["methods"])
    vkey = f"({pkg}.{go_receiver(next(iter(mkeys.values())))[1]}).validate"
    for i, h in enumerate(ctx.header):
        vt = batch["V"][i]
        if go_label(vt) == "panic":
            raise HostileError(f"validate panicked on header {i}: {vt[:200]}")
        real_some = go_label(vt) == "ok"
        exp = frozen_label(okv[i])
        if exp != ("ok" if real_some else "rejected"):
            s.mismatch(f"{fz.rel}#{ok_fn}", vkey, hexes[i], exp, "ok" if real_some else "rejected", "unexplained",
                       None, f"validate disagrees with the frozen {ok_fn} on the compiled M0 model")
        d = decv[i]
        if (d is not None) != real_some:
            s.mismatch(f"{fz.rel}#{dec_fn}", vkey, hexes[i], "ok" if d is not None else "rejected",
                       "ok" if real_some else "rejected", "unexplained", None,
                       f"the decoder's definedness (validate, then the getters) differs from the frozen {dec_fn}")
            continue
        if d is None:
            continue
        gets = [g for g in gdefs if not g.get("when") or _when(g["when"], h)]
        vals = dict(zip([g["name"] for g in gets], d))
        for g in gdefs:
            m = getters[g["name"]]
            key = mkeys[m]
            tok = batch["H"][(i, m)]
            real_l = "ok" if go_label(tok) == "ok" else "rejected"
            exp_l, exp_v = ("ok", vals[g["name"]]) if g["name"] in vals else ("rejected", None)
            if exp_l != real_l:
                s.mismatch(f"{fz.rel}#{dec_fn}", key, hexes[i], exp_l, real_l, "unexplained", None,
                           f"after validate passed, the getter for {g['name']} disagrees with the frozen {dec_fn}")
            elif exp_l == "ok" and tok[2:] != exp_v:
                s.mismatch(f"{fz.rel}#{dec_fn}", key, hexes[i], f"ok:{exp_v}", f"ok:{tok[2:]}", "unexplained", None,
                           f"the getter for {g['name']} returns another value than the frozen {dec_fn}",
                           group=f"go_header|{dec_fn}|{key}|value")


def _when(w: dict, b: bytes) -> bool:
    """A frozen getter's `when` on the header's version byte (version_ge / version_le / version_in)."""
    if not b:
        return False
    v = b[0]
    if "version_ge" in w:
        return v >= w["version_ge"]
    if "version_le" in w:
        return v <= w["version_le"]
    if "version_in" in w:
        return v in w["version_in"]
    raise HostileError(f"unknown when {w}")


# ---------------------------------------------------------------- surface go_encoders
def encoder_cells(entry: dict, env: dict) -> bytes | None:
    out = bytearray()
    for c in entry["cells"]:
        if c[0] == "const":
            out.append(c[1])
        elif c[0] == "byte":
            v = go_eval(c[1], env)
            out.append(bytes(v)[c[2]])
        else:
            return None
    return bytes(out)


def surface_go_encoders(ctx: Ctx, docs: dict | None = None) -> Surface:
    sc = ctx.side["surfaces"]["go_encoders"]
    sites = GoSites(ctx.tree, docs) if docs is not None else ctx.sites
    s = Surface("go_encoders", sc["carrier"], sc["models"])
    batch = run_go_batch(ctx)
    items = batch["encoders"]
    fz = ctx.frozen
    binding = load(ctx.tree, "replay/M2/implementations.json")["edges"]
    frozen_fns = [m.split("#")[1] for m in sc["models"] if "#" in m]
    edge_of = {}
    for key in sc["entry_points"]:
        _, t, m = go_receiver(key)
        edge_of[key] = next(f for f in frozen_fns if binding.get(f, {}).get("op") == f"{t}.{m}")
    fin = {f: [] for f in frozen_fns}
    for it in items:
        f = edge_of[it["key"]]
        go2f = {g: n for n, g in binding[f]["fields"].items()}
        fin[f].append(fz.header(**{go2f[g]: unhex(v) for g, v in it["fields"].items() if g in go2f}))
    fout = {f: fz.run(f, fin[f]) for f in frozen_fns}
    pos = {f: 0 for f in frozen_fns}
    covered, total = set(), 0
    for key in sc["entry_points"]:
        total += len(sites.function(key).get("paths") or [])
    for i, it in enumerate(items):
        key = it["key"]
        rel = sites.doc_of(key)
        fn = sites.function(key)
        e = s.entry(key)
        e["inputs"] += 1
        s.inputs += 1
        tok = batch["E"][i]
        lab = "panic" if str(tok).startswith("p:") else "ok"
        s.outcome(lab, entry=key)
        inp = {"fields": it["fields"], "cache": it["encoded"]}
        env = {go_param(fn): it["_struct"]}
        exp, k, _ = go_expected(fn, env)
        if k is not None:
            covered.add((key, k))
        if lab == "panic":
            site, status, _ = record_go_panic(ctx, s, key, tok, [{"call": key, "args": [inp]}], sites)
            s.mismatch(rel, key, inp, exp, f"panic:{site}", "unexplained", None,
                       f"the encoder panicked at {site} ({status})")
        elif exp != "ok":
            s.mismatch(rel, key, inp, exp, lab, "unexplained", None,
                       "the real outcome differs from the outcome of the extracted path the input selects")
        else:
            want = None
            for en in sites.encoders(rel).get(key, []):
                hit, _ = select_paths([{"cond": c} for c in en["conds"]], go_holds(env))
                if hit:
                    want = encoder_cells(en, env)
                    break
            if want is None and k is not None:
                try:
                    v = go_eval(fn["paths"][k]["returns"][0], env)
                    want = b"" if v is None else bytes(v)
                except Opaque:
                    want = None
            if want is None:
                s.mismatch(f"{rel}#codecs.encoders", key, inp, "undecided", "ok", "unexplained", None,
                           "neither the encoder layout nor the path's returned term gives the bytes")
            elif hx(want) != tok:
                s.mismatch(f"{rel}#codecs.encoders", key, inp, f"ok:{hx(want)}", f"ok:{tok}", "unexplained", None,
                           "the encoded bytes differ from the document's encoder layout or returned cache")
        f = edge_of[key]
        fo = fout[f][pos[f]]
        pos[f] += 1
        real_f = "ok" if lab == "ok" else "rejected"
        if frozen_label(fo) != real_f:
            s.mismatch(f"{fz.rel}#{f}", key, inp, frozen_label(fo), real_f, "unexplained", None,
                       "the encoder's definedness differs from the frozen encoder's on the compiled M0 model")
    s.paths = {"covered": len(covered), "total": total}
    return s


# ---------------------------------------------------------------- surface batchdata_act
def _calls_in(t, acc: list) -> list:
    if isinstance(t, list) and t:
        if t[0] == "call" and len(t) >= 2 and isinstance(t[1], str):
            acc.append(t)
        for x in (t[1:] if isinstance(t[0], str) else t):
            _calls_in(x, acc)
    elif isinstance(t, dict):
        for v in t.values():
            _calls_in(v, acc)
    return acc


class BatchModel:
    """The batch-data facts compiled (holon.mpipeline.CompiledMachine) and the names its walk needs, derived from the
    facts: the state fields of slice type (a type with len and cap) that name a receiver field in their description
    ("<Type>.<field>"), the append and view actions (the actions whose names are the Go methods'), the field the view
    action's effects set, the reader of a slice (a call of (heap field, slice field)) and the size-class table the
    append builtin is given (a List<Nat> state field among its call's arguments: the model's stated scope)."""

    def __init__(self, ctx: Ctx, bd: BatchDataSpec, real_fields: list[str]):
        from ..mpipeline import CompiledMachine
        sc = ctx.side["surfaces"]["batchdata_act"]
        self.rel = next(m for m in sc["models"] if not m.startswith("spec/M2/"))
        facts = load(ctx.tree, self.rel)
        self.cm = CompiledMachine.build(ctx.tree / self.rel)
        slice_types = {t for t, d in facts["types"].items() if {"len", "cap"} <= {f[0] for f in d.get("fields", [])}}
        state = {s[0]: s for s in facts["state"]}
        self.slices = {}
        for name, ty, doc in facts["state"]:
            if ty in slice_types:
                tail = doc.rsplit(".", 1)[-1] if "." in doc else None
                if tail in real_fields:
                    self.slices[name] = tail
        acts = {a["name"].lower(): a for a in facts["actions"]}
        self.append = acts[bd.append_method.lower()]
        self.view_action = next(acts[m.lower()] for m in bd.methods if m.lower() in acts and not acts[m.lower()]["inputs"])
        self.view_method = next(m for m in bd.methods if m.lower() == self.view_action["name"].lower())
        self.view = next(k for k, v in self.view_action["effects"].items() if state.get(k, [None, None])[1] in slice_types)
        reads = [c for c in _calls_in([facts.get("observers"), facts.get("defs"), [a.get("effects") for a in facts["actions"]]], [])
                 if len(c) == 4 and c[3] in state and state[c[3]][1] in slice_types and c[2] in state]
        if not reads:
            raise HostileError("the batch-data facts have no reader of a slice")
        f, self.heap = reads[0][1], reads[0][2]
        self.read = ("d_" if f in (facts.get("defs") or {}) else "b_") + f
        lists = {n for n, s in state.items() if s[1] == "List<Nat>"}
        tables = [a for c in _calls_in(self.append["guards"], []) for a in c[2:] if a in lists]
        if not tables:
            raise HostileError("the append action's builtin is given no size-class table")
        self.bound = max(facts["initial"][tables[0]])
        self.n_inputs = len(self.append["inputs"])


def run_bd_model(ctx: Ctx, bd: BatchDataSpec, real_fields: list[str]) -> tuple[BatchModel, list]:
    if "bd_model" in ctx.cache:
        return ctx.cache["bd_model"]
    bm = BatchModel(ctx, bd, real_fields)
    # the append action's inputs are the Go append's byte-string arguments, in order (the hashes are not modelled)
    args = [[list(v) for v in [x for x in c[:2]][:bm.n_inputs]] for c in bd.combos]
    req = {"module": str(bm.cm.artifact), "append": args, "depth": BD_DEPTH, "appendStep": f"step_{bm.append['name']}",
           "viewStep": f"step_{bm.view_action['name']}", "slices": sorted(bm.slices), "view": bm.view,
           "read": bm.read, "heap": bm.heap, "bound": bm.bound}
    log(f"batch-data model: walking {len(bd.sequences)} sequences on {bm.rel} (bound {bm.bound} bytes)")
    p = subprocess.run(["node", str(ctx.harness("js/batchdata_walk.mjs"))], input=json.dumps(req),
                       capture_output=True, text=True, timeout=14400)
    if p.returncode != 0:
        raise HostileError(f"batch-data model walk failed: {p.stderr[-2000:]}")
    rows = [json.loads(x) for x in p.stdout.splitlines() if x.strip()]
    if len(rows) != len(bd.sequences):
        raise HostileError(f"batch-data model walk: {len(rows)} rows for {len(bd.sequences)} sequences")
    ctx.cache["bd_model"] = (bm, rows)
    return bm, rows


def _receiver(names: list[str], dump: list | None):
    """The harness's reflection of a receiver as the document's terms read it (slices by length only)."""
    if dump is None:
        return NIL
    out = {}
    for k, v in zip(names, dump):
        if isinstance(v, list):
            out[k] = Blob(v[0])
        elif v == "nil":
            out[k] = NIL
        elif v == "ptr":
            out[k] = Ptr()
        else:
            out[k] = v
    return out


def surface_batchdata_act(ctx: Ctx, docs: dict | None = None) -> Surface:
    sc = ctx.side["surfaces"]["batchdata_act"]
    sites = GoSites(ctx.tree, docs) if docs is not None else ctx.sites
    s = Surface("batchdata_act", sc["carrier"], sc["models"])
    batch = run_go_batch(ctx)
    bd = batch["bd"]
    rows = batch["B"]
    fnames, initial = batch["F"]
    real_fields = list(fnames)
    fidx = {n: i for i, n in enumerate(fnames)}
    bm, mrows = run_bd_model(ctx, bd, real_fields)
    fs = sites.functions(bd.doc)
    keys = bd.keys
    cons = s.entry(bd.constructor)
    s.inputs = len(bd.sequences)
    expect_cache: dict = {}
    covered, total = set(), sum(len(fs[keys[m]].get("paths") or []) for m in bd.methods)
    compared = outside = 0

    def witness(seq, m, nil=False):
        w = [] if nil else [{"call": bd.constructor, "args": []}] + [
            {"call": keys[bd.append_method], "args": bd.append_js[k]} for k in seq]
        call = {"call": keys[m], "args": bd.call_js[m]}
        if nil:
            call["receiver"] = None
        return w + [call]

    def judge(m, tok, env, seq, inp, nil=False):
        key = keys[m]
        fn = fs[key]
        ck = (m, json.dumps({k: (len(v) if isinstance(v, Blob) else ("ptr" if isinstance(v, Ptr) else v))
                             for k, v in (env[go_param(fn)] or {}).items()} if env[go_param(fn)] is not NIL else None,
                            sort_keys=True))
        if ck not in expect_cache:
            expect_cache[ck] = go_expected(fn, env)
        exp, k, psite = expect_cache[ck]
        if k is not None:
            covered.add((key, k))
        lab = go_label(tok)
        s.entry(key)["inputs"] += 1
        s.outcome(lab)
        rel = sites.doc_of(key)
        if lab == "panic":
            site, status, kind = record_go_panic(ctx, s, key, tok, witness(seq, m, nil), sites)
            if exp == "panic":
                if site != psite:
                    s.mismatch(rel, key, inp, f"panic:{psite}", f"panic:{site}", "unexplained", None,
                               "the method panicked at another site than its extracted path's")
            elif status == "safe":
                s.mismatch(rel, key, inp, exp, f"panic:{site}", "unexplained", None,
                           f"the method panicked at {site}, a site the document marks safe")
            elif status == "unrecorded" and kind == "nil":
                s.mismatch(rel, key, inp, exp, f"panic:{site}", "assumption", "go-nil-deref-not-modelled",
                           "a nil pointer dereference, which the document's go-nil-deref-not-modelled assumption leaves "
                           "out of its partiality", group=f"batchdata_act|{rel}|{key}|nil")
            elif status == "unrecorded":
                s.mismatch(rel, key, inp, exp, f"panic:{site}", "unexplained", None,
                           f"the method panicked at {site}, where the document records no site")
            elif exp in ("ok", "error"):
                s.mismatch(rel, key, inp, exp, f"panic:{site}", "unexplained", None,
                           f"the extracted path returns, but the method panicked at the open site {site}")
        else:
            if exp == "panic":
                s.mismatch(rel, key, inp, f"panic:{psite}", lab, "unexplained", None,
                           "the extracted path panics, but the method returned")
            elif exp in ("ok", "error") and exp != lab:
                s.mismatch(rel, key, inp, exp, lab, "unexplained", None,
                           "the real outcome differs from the outcome of the extracted path the input selects")
            elif exp in ("none", "many"):
                s.mismatch(rel, key, inp, exp, lab, "unexplained", None,
                           f"the input satisfies {exp} of the method's extracted paths")

    for row, mrow in zip(rows, mrows):
        k = row[1]
        seq = bd.sequences[k]
        after, view, toks = row[2], row[3], row[4]
        cons["inputs"] += 1
        recv = _receiver(fnames, after[-1] if after else initial)
        for m, tok in zip(bd.methods, toks):
            env = {go_param(fs[keys[m]]): recv, **bd.call_env[m]}
            judge(m, tok, env, seq, {"sequence": list(seq), "method": m})
        # the batch-data model (append, the view action) on the same sequence, where it states it applies
        if not mrow[1]:
            outside += 1
            continue
        compared += 1
        inp = {"sequence": list(seq)}
        for i, (mafter, rafter) in enumerate(zip(mrow[2], after)):
            for (field, (ml, mc)) in zip(sorted(bm.slices), mafter):
                rl, rc = rafter[fidx[bm.slices[field]]]
                if (ml, mc) != (rl, rc):
                    s.mismatch(bm.rel, f"{bd.constructor}+{bd.append_method}*{len(seq)}", inp,
                               f"{field}[{i}]=len {ml} cap {mc}", f"len {rl} cap {rc}", "unexplained",
                               None, "the model's slice after an append differs from the real field",
                               group=f"batchdata_act|{bm.rel}|{field}")
        if isinstance(view[0], str):
            s.mismatch(bm.rel, keys[bm.view_method], inp, "ok", view[0][:80], "unexplained", None,
                       "the view method panicked where the model returns")
        elif list(view) != list(mrow[3]):
            s.mismatch(bm.rel, keys[bm.view_method], inp, f"len {mrow[3][0]} cap {mrow[3][1]} sha {mrow[3][2][:16]}",
                       f"len {view[0]} cap {view[1]} sha {view[2][:16]}", "unexplained", None,
                       "the returned slice differs from the model's view (length, capacity or contents)",
                       group=f"batchdata_act|{bm.rel}|view")
    for m in bd.methods:
        env = {go_param(fs[keys[m]]): NIL, **bd.call_env[m]}
        judge(m, batch["N"][m], env, (), {"receiver": None, "method": m}, nil=True)
    s.paths = {"covered": len(covered), "total": total}
    s.extra["model_scope"] = {bm.rel: {"compared": compared, "outside": outside, "bound_bytes": bm.bound,
                                       "why": "sequences whose slices exceed the largest entry of the size-class table "
                                              "the model's append is given are outside the model's stated scope (its "
                                              "abstractions): they are compared with the Go document only"}}
    return s


# ---------------------------------------------------------------- the Solidity harness (sol_loader, sol_encoder)
def sol_label(ok: bool, ret: str, reasons: list[str]) -> str:
    """An outcome label: ok (the call returned, or reverted with revert data that is none of the compared edge's
    reasons), revert:<reason> (an Error(string) reason of the edge), panic:<code>, empty."""
    if ok:
        return "ok"
    b = unhex(ret)
    if not b:
        return "empty"
    if len(b) == 36 and b[:4].hex() == PANIC:
        return "panic:0x%02x" % int.from_bytes(b[4:], "big")
    if b[:4].hex() == ERROR_STRING:
        from .. import evm_abi as A
        try:
            r = A.decode_args([{"type": "string", "name": "r"}], b[4:])["r"]
        except A.AbiError:
            return "ok"
        return f"revert:{r}" if r in reasons else "ok"
    return "ok"


def sol_project(ctx: Ctx, tag: str = "sol") -> Path:
    """A scratch Foundry project of the pinned checkout's contracts (the I20 binding's project) with the binding's
    harness files of the target tree and this round's Solidity harness."""
    key = f"solproj:{tag}"
    if key in ctx.cache:
        return ctx.cache[key]
    from ..replay_fragments import forge_build, harness_project
    binding = load(ctx.tree, "replay/M2/fragments.json")
    proj = harness_project(binding, ctx.work / tag, ctx.tree, ctx.checkout, ctx.tc)
    for f in sorted((ROOT / HARNESS / "solidity").glob("*.sol")):
        shutil.copy(f, proj / "test" / f.name)
    log(f"forge build ({proj})")
    forge_build(proj, ctx.tc)
    ctx.cache[key] = proj
    return proj


def sol_items_encode(items: list[tuple]) -> list[str]:
    from .. import evm_abi as A
    t = [{"type": "uint8"}, {"type": "string"}, {"type": "uint256"}, {"type": "bytes"}]
    return ["0x" + A.encode_args(t, [k, e, ln, hx(p)]).hex() for k, e, ln, p in items]


def run_solidity(ctx: Ctx, extra_loader: list[bytes]) -> dict:
    """Every Solidity item through the harness, once: sol_loader's headers at every call site and its malformed
    encodings, sol_encoder's inputs and malformed encodings, and extra headers (go_consumer's rejected real parents)
    at the call site of the commit function the consumer's selectors name."""
    if "sol" in ctx.cache:
        return ctx.cache["sol"]
    sl = ctx.side["surfaces"]["sol_loader"]
    se = ctx.side["surfaces"]["sol_encoder"]
    kinds = len(ctx.side["abi_malformed"])
    items, tags = [], []
    for cs in sl["call_sites"]:
        for i, h in enumerate(ctx.header):
            items.append((1, cs["entry"], cs["line"], h))
            tags.append(("loader", cs["entry"], cs["line"], i))
        for how in range(kinds):
            items.append((3, cs["entry"], cs["line"], how.to_bytes(32, "big")))   # abi.encode(uint8 how)
            tags.append(("loader_abi", cs["entry"], cs["line"], how))
    for ep in se["entry_points"]:
        for i, (v, a, b) in enumerate(ctx.encoder):
            from .. import evm_abi as A
            items.append((2, ep, 0, A.encode_args([{"type": "uint8"}, {"type": "bytes32"}, {"type": "bytes32"}],
                                                  [v, hx(a), hx(b)])))
            tags.append(("encoder", ep, None, i))
        for how in range(kinds):
            items.append((4, ep, 0, how.to_bytes(32, "big")))
            tags.append(("encoder_abi", ep, None, how))
    commit_fn = consumer_commit_function(ctx)
    cs_commit = next(cs for cs in sl["call_sites"] if cs["entry"] == commit_fn)
    for i, h in enumerate(extra_loader):
        items.append((1, cs_commit["entry"], cs_commit["line"], h))
        tags.append(("extra", cs_commit["entry"], cs_commit["line"], i))
    from ..fragments_corpus import binding_init
    binding = load(ctx.tree, "replay/M2/fragments.json")
    init = binding_init(binding, ctx.tree)
    r1 = ctx.encoder[-1][1]          # the corpus's nonzero roots: the genesis post state root and a valid post root
    r2 = ctx.encoder[-1][2]
    from .. import evm_abi as A
    first = A.encode_args([{"type": "uint256"}] * 4 + [{"type": "bytes32"}] * 2, init[:4] + [hx(r1), hx(r2)])
    proj = sol_project(ctx)
    fin, fout = proj / "holon_hostile_in.txt", proj / "holon_hostile_out.txt"
    fin.write_text("\n".join(["0x" + first.hex()] + sol_items_encode(items) + ["0x"]) + "\n")
    fout.unlink(missing_ok=True)
    log(f"forge: {len(items)} Solidity items")
    code, out = run(["nice", "-n", "10", ctx.tc["forge"], "test", "--match-contract", "^HolonHostileTest$",
                     "--match-test", "^test_hostile\\(\\)$", "--offline", "--use", ctx.tc["solc"]], proj,
                    {"HOLON_HOSTILE_IN": fin.name, "HOLON_HOSTILE_OUT": fout.name})
    lines = fout.read_text().splitlines() if fout.exists() else []
    if code != 0 or not lines or lines[-1] != f"done {len(items)}":
        raise HostileError(f"Solidity harness failed (exit {code}, {len(lines)} lines for {len(items)} items): "
                           f"{out[-3000:]}")
    res: list = [None] * len(items)   # the harness runs the items one state at a time: lines carry the item index
    for ln in lines[:-1]:
        k, ok, ret = ln.split(" ")
        if res[int(k)] is not None:
            raise HostileError(f"Solidity harness: item {k} reported twice")
        res[int(k)] = (ok == "1", ret.lower())
    if any(r is None for r in res):
        raise HostileError("Solidity harness: an item has no outcome")
    fin.unlink(missing_ok=True)
    fout.unlink(missing_ok=True)
    ctx.cache["sol"] = {"tags": tags, "res": res}
    return ctx.cache["sol"]


def consumer_commit_function(ctx: Ctx) -> str:
    """The commit function the consumer's selectors name (every signature of the sidecar's consumer ABIs)."""
    names = {v["signature"].split("(")[0] for v in ctx.side["surfaces"]["go_consumer"]["abis"].values()}
    if len(names) != 1:
        raise HostileError(f"the consumer's selectors name several functions: {sorted(names)}")
    return names.pop()


def surface_sol_loader(ctx: Ctx, doc: dict | None = None) -> Surface:
    sl = ctx.side["surfaces"]["sol_loader"]
    s = Surface("sol_loader", sl["carrier"], sl["models"])
    sol = ctx.cache["sol"]
    d = doc if doc is not None else load(ctx.tree, ctx.loader_doc)
    fn = d["functions"][ctx.loader_fn]
    var = sol_vars([p.get("cond") for p in fn["paths"]], [])
    if len(var) != 1:
        raise HostileError(f"{ctx.loader_fn}: conditions read {var}, one input expected")
    unit = sl["unit"]
    reasons = sl["reasons"]
    hexes = [hx(h) for h in ctx.header]
    okv = ctx.frozen.run(ctx.frozen_pred, hexes)
    expected = []
    covered = set()
    for h in ctx.header:
        hit, und = select_paths(fn["paths"], lambda c, h=h: bool(sol_eval(c, {var[0]: h})))
        if len(hit) == 1:
            p = fn["paths"][hit[0]]
            covered.add(hit[0])
            expected.append("ok" if p["outcome"] == "ok" else f"revert:{p.get('reason')}")
        else:
            expected.append("none" if not hit else "many")
    s.inputs = len(ctx.header)
    for d_ in sl["dominated"]:
        s.entry(d_["entry"], f"{unit}:{d_['line']}", sorted(f"{unit}:{x}" for x in d_["by"]))
    for tag, (ok, ret) in zip(sol["tags"], sol["res"]):
        kind, ep, line, i = tag
        if kind not in ("loader", "loader_abi"):
            continue
        site = f"{unit}:{line}"
        e = s.entry(ep, site)
        if kind == "loader_abi":
            s.abi_rejected += 1
            lab = sol_label(ok, ret, reasons)
            if lab != "empty":
                s.mismatch("abi", ep, {"malformed": ctx.side["abi_malformed"][i], "site": site}, "empty", lab,
                           "unexplained", None, "a malformed ABI encoding did anything but revert with empty data")
            continue
        e["inputs"] += 1
        lab = sol_label(ok, ret, reasons)
        s.outcome(lab, entry=ep)
        inp = hexes[i]
        if lab.startswith("panic:"):
            s.panic(ep, site, "unrecorded", [{"call": ep, "args": [inp]}], None,
                    "a Solidity Panic at the compared call (its source line is not located)")
        if expected[i] != lab:
            s.mismatch(f"{ctx.loader_doc}#{ctx.loader_fn}", ep, {"header": inp, "site": site}, expected[i], lab,
                       "unexplained", None, "the real call disagrees with the extracted loader path the header selects")
        fl = frozen_label(okv[i])
        rl = "ok" if lab == "ok" else "rejected"
        if fl != rl:
            s.mismatch(f"{ctx.frozen_rel}#{ctx.frozen_pred}", ep, {"header": inp, "site": site}, fl, rl,
                       "unexplained", None, f"the real call disagrees with the frozen {ctx.frozen_pred}")
    s.paths = {"covered": len(covered), "total": len(fn["paths"])}
    return s


def surface_sol_encoder(ctx: Ctx, doc: dict | None = None) -> Surface:
    se = ctx.side["surfaces"]["sol_encoder"]
    s = Surface("sol_encoder", se["carrier"], se["models"])
    sol = ctx.cache["sol"]
    d = doc if doc is not None else load(ctx.tree, ctx.encoder_doc)
    fn = d["functions"][ctx.encoder_fn]
    names = sol_vars([p.get("cond") for p in fn["paths"]], [])
    if len(names) != 3:
        raise HostileError(f"{ctx.encoder_fn}: conditions read {names}; the encoder corpus has three components")
    reasons = se["reasons"]
    fz = ctx.frozen
    # the corpus's components are (version, prev root, post root), the order the paths read them in; their widths in
    # the frozen Header confirm it (a 1-byte version, two 32-byte roots)
    if [fz.widths.get(n) for n in names] != [1, 32, 32]:
        raise HostileError(f"{ctx.encoder_fn}: {names} are not a 1-byte version and two 32-byte roots in the frozen "
                           f"Header ({[fz.widths.get(n) for n in names]})")
    fin = [fz.header(**{names[0]: v, names[1]: a, names[2]: b}) for v, a, b in ctx.encoder]
    fout = fz.run(ctx.frozen_encoder, fin)
    covered = set()
    expected = []
    for v, a, b in ctx.encoder:
        env = {names[0]: v, names[1]: int.from_bytes(a, "big"), names[2]: int.from_bytes(b, "big")}
        hit, _ = select_paths(fn["paths"], lambda c, env=env: bool(sol_eval(c, env)))
        if len(hit) == 1:
            covered.add(hit[0])
            p = fn["paths"][hit[0]]
            expected.append("ok" if p["outcome"] == "ok" else f"revert:{p.get('reason')}")
        else:
            expected.append("none" if not hit else "many")
    s.inputs = len(ctx.encoder)
    for tag, (ok, ret) in zip(sol["tags"], sol["res"]):
        kind, ep, _, i = tag
        if kind not in ("encoder", "encoder_abi"):
            continue
        e = s.entry(ep)
        lab = sol_label(ok, ret, reasons)
        if kind == "encoder_abi":
            s.abi_rejected += 1
            if lab != "empty":
                s.mismatch("abi", ep, {"malformed": ctx.side["abi_malformed"][i]}, "empty", lab, "unexplained", None,
                           "a malformed ABI encoding did anything but revert with empty data")
            continue
        e["inputs"] += 1
        s.outcome(lab, entry=ep)
        v, a, b = ctx.encoder[i]
        inp = {names[0]: v, names[1]: hx(a), names[2]: hx(b)}
        if lab.startswith("panic:"):
            s.panic(ep, se["unit"], "unrecorded", [{"call": ep, "args": [inp]}], None,
                    "a Solidity Panic in the commit path (its source line is not located)")
        if expected[i] != lab:
            s.mismatch(f"{ctx.encoder_doc}#{ctx.encoder_fn}", ep, inp, expected[i], lab, "unexplained", None,
                       "the real commit path disagrees with the extracted encoder path the input selects")
        fl = frozen_label(fout[i])
        rl = "ok" if lab == "ok" else "rejected"
        if fl != rl:
            why = ("the frozen encoder is defined (it builds a header) where the real commit path reverts"
                   if fl == "ok" else "the frozen encoder is undefined where the real commit path goes past")
            s.mismatch(f"{ctx.frozen_rel}#{ctx.frozen_encoder}", ep, inp, fl, lab, "unexplained", None, why,
                       group=f"sol_encoder|{ctx.frozen_rel}#{ctx.frozen_encoder}|{fl}|{lab}")
    s.paths = {"covered": len(covered), "total": len(fn["paths"])}
    return s


# ---------------------------------------------------------------- surface go_consumer
def step_prefixes(ctx: Ctx) -> dict[str, str]:
    """{label: message prefix} of ParseBatch's header steps: the string literal the error branch after each step's
    call site formats, up to its first verb (read from the scratch copy of the pinned checkout)."""
    out = {}
    for label, site in ctx.side["surfaces"]["go_consumer"]["header_steps"].items():
        m = re.fullmatch(r"(.+):(\d+):(\d+)", site)
        path = ctx.checkout / m.group(1)
        lines = path.read_text().splitlines()
        ln = int(m.group(2))
        for text in lines[ln - 1:ln + 4]:
            q = re.search(r'Errorf\("([^"%]*)', text)
            if q:
                out[label] = q.group(1)
                break
        if label not in out:
            raise HostileError(f"no error message after the header step at {site}")
    return out


def parse_label(tok: str | None, prefixes: dict[str, str]) -> str | None:
    if tok is None:
        return None
    if tok == "o":
        return "ok"
    if tok.startswith("p:"):
        return "panic"
    for label, pre in sorted(prefixes.items()):
        if tok[2:].startswith(pre):
            return label
    return "error:other"


def consumer_real(ctx: Ctx) -> list[dict]:
    """The commits of the target tree's replay (I59) with their calldata and blobs named by the index's sha256."""
    replay = load(ctx.tree, str(REPLAY))
    index = load(ctx.tree, str(INDEX))
    tx_sha, blob_sha = {}, {}
    for it in index["items"]:
        if it.get("status") != "ok":
            continue
        if it["kind"] == "tx":
            tx_sha[it["tx"]] = it["sha256"]
        elif it["kind"] == "blob":
            blob_sha[(it["tx"], it["versioned_hash"])] = it["sha256"]
    out = []
    for c in replay["commits"]:
        par = c.get("parent") or c.get("legacy_parent") or {}
        try:
            out.append({"key": c["batch_index"], "tx": tx_sha[c["tx"]],
                        "blobs": [blob_sha[(c["tx"], vh)] for vh in c["tx_blob_versioned_hashes"]],
                        "parent_keccak": par.get("keccak")})
        except KeyError as e:
            raise HostileError(f"commit {c['batch_index']}: no index item {e}")
    return out


def run_consumer(ctx: Ctx) -> dict:
    if "consumer" in ctx.cache:
        return ctx.cache["consumer"]
    gc = ctx.side["surfaces"]["go_consumer"]
    real = consumer_real(ctx)
    from ..historical.store import resolve_snapshot
    snap = resolve_snapshot(str(ctx.snapshot) if ctx.snapshot else None)
    if not (snap / "objects").is_dir():
        raise HostileError(f"the I59 snapshot is missing: {snap}")
    sels = sorted(gc["abis"])
    pkg = go_receiver(gc["entry_points"][0])[0]
    log(f"go: {pkg} consumer harness ({len(sels)} selectors x {len(ctx.header)} headers, {len(real)} real commits)")
    lines = ctx.go.test(pkg, ctx.harness("go/holon_hostile_consumer_test.go"), "TestHolonHostileConsumer",
                        {"selectors": sels, "headers": [hx(h) for h in ctx.header], "snapshot": str(snap),
                         "real": [{"key": r["key"], "tx": r["tx"], "blobs": r["blobs"]} for r in real]}, "consumer")
    res = {"sels": sels, "real": real, "h": {}, "r": {}}
    for ln in lines:
        if ln[0] == "h":
            res["h"][(ln[1], ln[2])] = ln[3:]
        elif ln[0] == "r":
            res["r"][ln[1]] = ln[2:]
    if len(res["r"]) != len(real) or len(res["h"]) != len(sels) * len(ctx.header):
        raise HostileError("the consumer harness skipped inputs")
    ctx.cache["consumer"] = res
    return res


def consumer_expect(ctx: Ctx, sites: GoSites, header: bytes, okgo) -> tuple[str, str]:
    """(expected header step from the extracted header methods' paths, from the frozen ok_go): error:header_index,
    error:header_total or past."""
    gc = ctx.side["surfaces"]["go_consumer"]
    steps = sorted(gc["header_steps"].items(), key=lambda kv: [int(x) for x in kv[1].rsplit(":", 2)[1:]])
    exp = "past"
    for (label, _), key in zip(steps, gc["header_methods"]):
        fn = sites.function(key)
        e, _, _ = go_expected(fn, {go_param(fn): header})
        if e == "error":
            exp = label
            break
        if e != "ok":
            exp = f"{label}?{e}"
            break
    fro = "past" if frozen_label(okgo) == "ok" else steps[0][0]
    return exp, fro


def surface_go_consumer(ctx: Ctx, docs: dict | None = None) -> Surface:
    gc = ctx.side["surfaces"]["go_consumer"]
    sites = GoSites(ctx.tree, docs) if docs is not None else ctx.sites
    s = Surface("go_consumer", gc["carrier"], gc["models"])
    res = run_consumer(ctx)
    prefixes = step_prefixes(ctx)
    unpack_key, parse_key = gc["entry_points"]
    callers = gc.get("callers") or {}
    eu = s.entry(unpack_key, callers.get(unpack_key, "").split(" ")[0] or None)
    ep = s.entry(parse_key, callers.get(parse_key, "").split(" ")[0] or None)
    udoc = sites.doc_of(unpack_key)
    frozen_model = next(m for m in gc["models"] if "#" in m)
    okfn = frozen_model.split("#")[1]
    hexes = [hx(h) for h in ctx.header]
    okgo = ctx.frozen.run(okfn, hexes)
    hdr_doc = sites.doc_of(gc["header_methods"][0])

    def judge(tag: str, key, header: bytes | None, toks: list, okv, witness_args):
        ut, pk, pt, ph = toks
        ul = go_label(ut)
        eu["inputs"] += 1
        s.outcome(ul)
        inp = {"input": tag, "key": key}
        if ul == "panic":
            site, status, _ = record_go_panic(ctx, s, unpack_key, ut, [{"call": unpack_key, "args": witness_args}],
                                              sites)
            s.mismatch(udoc, unpack_key, inp, "ok", f"panic:{site}", "unexplained", None,
                       f"UnPackData panicked at {site} ({status})")
            return None
        # UnPackData's extracted paths read opaque calls (the ABIs' method ids, Unpack's result), so they decide only
        # the panic sites; the contract's expectation is a nil error with the parent header unchanged
        if ul != "ok":
            s.mismatch(udoc, unpack_key, inp, "ok", ul, "unexplained", None,
                       "UnPackData returned an error on a well-formed commit calldata")
            return None
        if header is not None and pk != keccak(header):
            s.mismatch(udoc, unpack_key, inp, "ok:unchanged", "ok:changed", "unexplained", None,
                       "the unpacked parentBatchHeader differs from the header the calldata carries")
        pl = parse_label(pt, prefixes)
        ep["inputs"] += 1
        s.outcome(pl)
        hb = header if header is not None else (unhex(ph) if ph else None)
        if pl == "panic":
            site, status, _ = record_go_panic(ctx, s, parse_key, pt, [{"call": unpack_key, "args": witness_args},
                                                                       {"call": parse_key, "args": ["<unpacked>"]}],
                                              sites)
        if hb is None:
            return pl
        exp, fro = consumer_expect(ctx, sites, hb, okv)
        real_step = pl if pl in prefixes else "past"
        if exp != real_step:
            s.mismatch(hdr_doc, parse_key, {**inp, "header": hx(hb)}, exp, pl, "unexplained", None,
                       "ParseBatch's header step disagrees with the extracted header methods' paths")
        if fro != real_step:
            s.mismatch(frozen_model, parse_key, {**inp, "header": hx(hb)}, fro, pl, "unexplained", None,
                       f"ParseBatch's header step disagrees with the frozen {okfn}")
        return pl

    for (si, hi), toks in sorted(res["h"].items()):
        judge("hostile", [res["sels"][si], hi], ctx.header[hi], toks, okgo[hi], [res["sels"][si], hexes[hi]])
    # the real commits (I59): parent headers through the frozen ok_go in one batch
    real = res["real"]
    parents = []
    for r in real:
        ph = res["r"][r["key"]][4]
        parents.append(ph if ph else "0x")
    okreal = ctx.frozen.run(okfn, parents)
    by_sel: dict = {}
    unpack: dict = {}
    parse: dict = {}
    rejected: dict = {}
    mism_keccak = []
    for r, okv in zip(real, okreal):
        sel, ut, pk, pt, ph = res["r"][r["key"]]
        by_sel[sel] = by_sel.get(sel, 0) + 1
        ul = go_label(ut)
        unpack[ul] = unpack.get(ul, 0) + 1
        if ul == "ok" and pk != r["parent_keccak"]:
            mism_keccak.append(r["key"])
        pl = judge("real", r["key"], None, res["r"][r["key"]][1:], okv, [f"<calldata of batch {r['key']}>"])
        if pl is not None:
            parse[pl] = parse.get(pl, 0) + 1
            if pl != "ok":
                rejected.setdefault(pl, []).append(r["key"])
    s.inputs = len(ctx.header) * len(res["sels"]) + len(real)
    rej = {k: sorted(v) for k, v in sorted(rejected.items())}
    s.extra["real_inputs"] = {"commits": len(real), "by_selector": dict(sorted(by_sel.items())),
                              "unpack": dict(sorted(unpack.items())), "parent_keccak_mismatches": sorted(mism_keccak),
                              "parse": dict(sorted(parse.items())), "rejected": rej, "solidity_on_rejected": {}}
    return s


def consumer_rejected_parents(ctx: Ctx, s: Surface) -> list[bytes]:
    """The parent headers of the real commits ParseBatch rejected at its first header step, in batch-index order."""
    res = run_consumer(ctx)
    first = sorted(ctx.side["surfaces"]["go_consumer"]["header_steps"].items(),
                   key=lambda kv: [int(x) for x in kv[1].rsplit(":", 2)[1:]])[0][0]
    keys = s.extra["real_inputs"]["rejected"].get(first, [])
    return [unhex(res["r"][k][4]) for k in keys]


# ---------------------------------------------------------------- surface rollup_act (I20's refinement harness)
def leaf_values(ty: str, header: bool, act_header: list[bytes]) -> list:
    """The hostile values of one ABI leaf (the contract's rollup_act corpus)."""
    m = re.fullmatch(r"uint(\d*)", ty)
    if m:
        w = int(m.group(1) or 256)
        return [0, 1, (1 << w) - 2, (1 << w) - 1]
    m = re.fullmatch(r"int(\d*)", ty)
    if m:
        w = int(m.group(1) or 256)
        return [0, 1, -1, -(1 << (w - 1)), (1 << (w - 1)) - 1]
    m = re.fullmatch(r"bytes(\d+)", ty)
    if m:
        n = int(m.group(1))
        return ["0x" + "00" * n, "0x" + "00" * (n - 1) + "01", "0x" + "ff" * n]
    if ty == "bool":
        return [False, True]
    if ty == "address":
        return [ZERO_ADDR, FRESH]
    if ty == "bytes":
        return [hx(h) for h in act_header] if header else ["0x", "0x01"]
    if ty == "string":
        return ["", "x"]
    return []


def _param_paths(t, acc: set) -> set:
    """The parameter paths a document term reads: ("p",) for ["param", p], ("p", "f") for its member f."""
    if isinstance(t, list) and t:
        if t[0] == "param" and len(t) == 2 and isinstance(t[1], str):
            acc.add((t[1],))
            return acc
        if t[0] == "member" and len(t) == 3 and isinstance(t[1], list) and t[1][:1] == ["param"]:
            acc.add((t[1][1], t[2]))
            return acc
        for x in t[1:]:
            _param_paths(x, acc)
    return acc


def header_params(view, action: str, reasons: list[str]) -> set:
    """The parameter paths of an action that its document passes to the header loader: those its reaches with a
    loader reason (the sidecar's sol_loader reasons) read."""
    out: set = set()
    for r in view.reaches.get(action, []):
        if r.reason in reasons:
            _param_paths(r.expr, out)
    return out


class ActTarget:
    """I20's refinement harness on the real contract (holon.replay_fragments), the extracted model and the corpus."""

    def __init__(self, ctx: Ctx):
        from .. import fragments_corpus as FC
        from .. import replay_fragments as RF
        self.RF, self.FC = RF, FC
        self.binding = load(ctx.tree, "replay/M2/fragments.json")
        self.doc_rel = self.binding["facts"]
        self.doc_path = ctx.tree / self.doc_rel
        self.doc = json.loads(self.doc_path.read_text())
        self.proj = RF.harness_project(self.binding, ctx.work / "rollup", ctx.tree, ctx.checkout, ctx.tc)
        log(f"forge build ({self.proj})")
        RF.forge_build(self.proj, ctx.tc)
        self.tgt = RF.Target.build(self.proj, self.binding, self.doc)
        self.view = self.tgt.view
        self.slots = self.view.dump_slots()
        self.init = FC.binding_init(self.binding, ctx.tree)
        self.load, self.step_fn = RF.load_evaluator(None, ctx.tree)
        self.model = self.model_of(self.doc_path, ctx)
        self.base, self.counts = FC.base_traces(self.binding, ctx.tree, FC.M1_SIZE, ["m1", "witness"],
                                                {f["name"]: f for f in self.tgt.fns.values()})
        log(f"rollup: translation run of {len(self.base)} base traces")
        self.runs = RF.run_harness(self.proj, ctx.tc, self.binding, self.base, self.slots, self.init, RF.MAX_STEPS,
                                   ctx.jobs, tag="i21-translation")
        self.search = FC.Search(self.view, self.tgt, self.runs, self.slots)

    def model_of(self, path: Path, ctx: Ctx):
        src = self.binding.get("source")
        return self.load(str(path), str(ctx.tree / src)) if src else self.load(str(path))


def rollup_bases(ctx: Ctx, R: ActTarget) -> dict:
    """{action: (Base, how)}: the first corpus call of the action that succeeded, else the first ABI-built call
    (synthesized at the corpus's spots, with every corpus caller) that succeeds in a probe run, else the first one."""
    S = R.search
    out = {}
    probes: dict = {}
    cands: dict = {}
    for a in sorted(R.view.actions):
        ok = [b for b in S.bases.get(a, []) if b.ok]
        if ok:
            out[a] = (ok[0], "corpus")
            continue
        syn = S.synthesized(a)
        if not syn:
            out[a] = (None, "none")
            continue
        cands[a] = syn
        for k, b in enumerate(syn):
            st = S._fork(b, b.args, b.env, {"source": "i21-probe", "action": a, "cand": k})
            if st is not None:
                probes.setdefault((b.tid, b.pos), []).append(st)
    if probes:
        log(f"rollup: probe run for {len(cands)} actions the corpus never succeeds in")
        traces = R.FC.insert_forks(R.base, probes)
        runs = R.RF.run_harness(R.proj, ctx.tc, R.binding, traces, R.slots, R.init, R.RF.MAX_STEPS, ctx.jobs,
                                tag="i21-probe")
        okc: dict = {}
        for tr in runs:
            steps = {str(i): st for i, st in enumerate(tr.steps)}
            for e in tr.execs:
                st = steps.get(e.id)
                if st is None or not st.fork:
                    continue
                for m in [st.meta] + list(st.meta.get("also") or []):
                    if m.get("source") == "i21-probe":
                        okc.setdefault(m["action"], {})[m["cand"]] = e.ok
        for a, syn in cands.items():
            good = [k for k in sorted(okc.get(a, {})) if okc[a][k]]
            out[a] = (syn[good[0]], "synthesized") if good else (syn[0], "synthesized, none succeeds")
    return out


def rollup_variations(ctx: Ctx, R: ActTarget, a: str, b) -> list[tuple[str, dict, dict]]:
    """(description, args, env) of every hostile call of an action from its base call: one ABI leaf at a time, the
    caller (a satisfying and a failing caller of the action's principal predicate, and address(0)), msg.value."""
    from .. import evm_abi as abi
    S = R.search
    fn = b.fn
    reasons = ctx.side["surfaces"]["sol_loader"]["reasons"]
    hdr = header_params(R.view, a, reasons)
    out = []
    for i in fn["inputs"]:
        for path, lt in abi.leaves(i, (i["name"],)):
            is_hdr = tuple(path) in hdr
            for v in leaf_values(lt["type"], is_hdr, ctx.act_header):
                out.append((f"{'.'.join(map(str, path))}={v if not isinstance(v, str) or len(v) < 20 else v[:18] + '..'}",
                            abi.set_path(b.args, tuple(path), v), b.env))
    pred = (R.view.actions[a].get("principal") or {}).get("predicate")
    callers = sorted(S.callers | {FRESH})
    sat = fail = None
    if pred is not None:
        for c in callers:
            r = S.evaluator(b, b.args, {**b.env, "caller": c}).ev(pred)
            if r == 1 and sat is None:
                sat = c
            if r == 0 and fail is None:
                fail = c
    else:
        sat = b.env["caller"]
    for who, c in (("satisfying", sat), ("failing", fail), ("zero", ZERO_ADDR)):
        if c is not None:
            out.append((f"caller={who}", b.args, {**b.env, "caller": c}))
    for v in (0, 1):
        out.append((f"msg.value={v}", b.args, {**b.env, "msg.value": v}))
    return out


def run_rollup(ctx: Ctx) -> dict:
    if "rollup" in ctx.cache:
        return ctx.cache["rollup"]
    R = ActTarget(ctx)
    bases = rollup_bases(ctx, R)
    S = R.search
    post = S.positions[0][:2]
    forks: dict = {}
    nvar = 0
    for a, (b, how) in sorted(bases.items()):
        if b is None:
            continue
        for desc, args, env in rollup_variations(ctx, R, a, b):
            for at, pos in (("base", (b.tid, b.pos)), ("post-genesis", post)):
                if at == "post-genesis" and pos == (b.tid, b.pos):
                    continue
                st = S._fork(b, args, env, {"source": "i21-hostile", "action": a, "param": desc, "at": at})
                if st is not None:
                    forks.setdefault(pos, []).append(st)
                    nvar += 1
    log(f"rollup: hostile run, {nvar} fork steps")
    traces = R.FC.insert_forks(R.base, forks)
    runs = R.RF.run_harness(R.proj, ctx.tc, R.binding, traces, R.slots, R.init, R.RF.MAX_STEPS, ctx.jobs,
                            tag="i21-hostile")
    out = {"R": R, "bases": bases, "runs": runs}
    ctx.cache["rollup"] = out
    return out


def rollup_label(c) -> str:
    if c.real["status"] == "ok":
        return "ok"
    from ..replay_fragments import revert_key
    k = revert_key(c.real["revert"])
    if k[0] == "error":
        return f"revert:{k[1]}"
    if k[0] == "panic":
        return "panic:0x%02x" % k[1]
    if k[0] == "custom":
        return f"custom:{k[1]}"
    return "empty" if k[1] in ("0x", "") else "raw"


def classify_rollup(c, R: ActTarget, coverage: dict) -> tuple[str, str | None, str, str | None]:
    """(class, explained_by, why, exemption) of a disagreement between the extracted model and the real contract."""
    from ..replay_fragments import revert_key
    m, r = c.model, c.real
    if m["status"] not in ("ok", "revert"):
        return "unexplained", None, f"the model answered {m['status']} ({m.get('reason', '')[:120]})", None
    rk = revert_key(r["revert"]) if r["status"] == "revert" else None
    implicit = rk is not None and (rk == ["raw", "0x"] or rk[0] == "panic")
    if implicit and m.get("guard") is None:
        # an empty revert or a Panic where the model records no check: A-implicit's exemptions only
        if rk[0] == "panic" and rk[1] == 0x41:
            return ("implicit", "A-implicit", "a Panic 0x41 (allocating a decoded dynamic value) is exempt from the "
                    "document's checks", "abi_dynamic_calldata")
        return "unexplained", None, ("the real contract reverted with an empty revert or a Panic where the "
                                     "document records no check, outside A-implicit's exemptions"), None
    # a disagreement inside a statement the coverage lists as debt (the action's source span holds the debt's)
    action_src = R.view.actions[c.action].get("src") or ""
    for d in coverage.get(R.doc_rel, []):
        if _span_holds(action_src, d["src"]) and ("storage" in c.diff or "events" in c.diff) \
                and d["kind"] in ("loop_storage_write", "external_call", "value_transfer"):
            return "debt", d["src"], f"the differing observable lies in a {d['kind']} the coverage lists as debt " \
                                     f"({d['detail']})", None
    return "unexplained", None, f"the model and the real contract differ on {', '.join(c.diff)}", None


def _span_holds(outer: str, inner: str) -> bool:
    """Whether the source span inner (file:line or file:a-b) lies inside outer."""
    mo = re.fullmatch(r"(.+):(\d+)(?:-(\d+))?", outer or "")
    mi = re.fullmatch(r"(.+):(\d+)(?:-(\d+))?", inner or "")
    if not mo or not mi or mo.group(1) != mi.group(1):
        return False
    a, b = int(mo.group(2)), int(mo.group(3) or mo.group(2))
    c, d = int(mi.group(2)), int(mi.group(3) or mi.group(2))
    return a <= c and d <= b


def surface_rollup_act(ctx: Ctx, model=None) -> Surface:
    sc = ctx.side["surfaces"]["rollup_act"]
    s = Surface("rollup_act", sc["carrier"], sc["models"])
    rr = run_rollup(ctx)
    R = rr["R"]
    cov = {d["document"]: d["debt"] for d in load(ctx.tree, "gen/M2/coverage.json")["documents"]}
    compared, _ = R.RF.compare_runs(rr["runs"], R.tgt, R.slots, model or R.model, R.step_fn)
    for a in sorted(R.view.actions):
        b, how = rr["bases"][a]
        s.entry(a)   # every action the model compiles is an entry point, with 0 inputs until one runs
        s.extra.setdefault("bases", {})[a] = {"how": how, "ok": None if b is None else b.ok}
    model_rel = next(m for m in sc["models"] if m.endswith(".bend"))
    for c in compared:
        metas = [c.meta] + list(c.meta.get("also") or [])
        hs = [m for m in metas if m.get("source") == "i21-hostile"]
        if not hs:
            continue
        lab = rollup_label(c)
        s.labels_by_action.setdefault(c.action, set()).add(lab)   # for the planted mutant (not written out)
        for m in hs:
            s.entry(c.action)["inputs"] += 1
            s.inputs += 1
            s.outcome(lab)
        inp = {"param": hs[0]["param"], "at": hs[0]["at"], "input_sha256": c.input_sha}
        if lab.startswith("panic:"):
            g = c.model.get("guard")
            span = g.split("#")[1] if isinstance(g, str) and g.count("#") >= 2 else None
            same = c.model["status"] == "revert" and R.RF.revert_key(c.model["revert"]) == R.RF.revert_key(c.real["revert"])
            s.panic(c.action, span if (same and span) else "unknown", "open" if same and span else "unrecorded",
                    [{"tx": {"action": c.action, "param": hs[0]["param"], "at": hs[0]["at"], "input_sha256": c.input_sha}}],
                    None, "a Panic the document records as a check" if same else "a Panic the model does not give")
        if not c.diff:
            continue
        cls, expl, why, ex = classify_rollup(c, R, cov)
        extra = {"exemption": ex} if cls == "implicit" else {}
        s.mismatch(model_rel, c.action, inp, R.RF.outcome_text(c).split(": ", 1)[-1].split(", real ")[0],
                   lab, cls, expl, why, group=f"rollup_act|{c.action}|{','.join(c.diff)}|{cls}", **extra)
    return s


# ---------------------------------------------------------------- codec labels, target findings
def codec_labels(ctx: Ctx, surfaces: dict[str, Surface]) -> dict:
    """Every CODEC edge of the header carrier's diagram: its partial flag there, and whether the real code rejects
    some input of the edge's surface (the surface whose models name the edge's frozen function; for a surface of
    several encoders, the entry points the I16 binding binds to the edge)."""
    doc = ctx.side["surfaces"]["sol_loader"]["carrier"].split(":")[0]
    diag = load(ctx.tree, f"gen/M2/diagram/{doc}.json")
    binding = load(ctx.tree, "replay/M2/implementations.json")["edges"]
    out = {}
    for e in sorted((e for e in diag["edges"] if e["kind"] == "CODEC"), key=lambda e: e["id"]):
        fn = e["id"].split(".", 1)[1]
        name = next(n for n, s in sorted(surfaces.items()) if f"{ctx.frozen_rel}#{fn}" in s.models)
        s = surfaces[name]
        op = (binding.get(fn) or {}).get("op", "")
        entries = [k for k in s.extra_outcomes if "." in op and k.endswith(f".{op.split('.')[0]}).{op.split('.')[1]}")]
        pool = [s.extra_outcomes[k] for k in entries] if entries else [s.outcomes]
        rejects = any(lab != "ok" and n > 0 for d in pool for lab, n in d.items())
        out[e["id"]] = {"surface": name, "diagram_partial": bool(e["partial"]), "real_partial": rejects}
    return out


def frozen_law(ctx: Ctx, preds: set) -> str | None:
    """The M0 law whose claim equates calls of the two frozen predicates (e.g. the domain law of the two loaders)."""
    for p in sorted((ctx.tree / "laws" / "M0").glob("L_*.json")):
        law = json.loads(p.read_text())
        eq = (law.get("statement") or {}).get("claim", {}).get("eq")
        if isinstance(eq, list) and len(eq) == 2 and all(isinstance(x, dict) and "call" in x for x in eq):
            if {x["call"] for x in eq} == preds:
                return law["law_id"]
    return None


def target_findings(ctx: Ctx, surfaces: dict[str, Surface]) -> list[dict]:
    """Results about the target, binned by the finding filter (whitepaper §9.6)."""
    out = []
    gc = surfaces.get("go_consumer")
    ok_go = next(m.split("#")[1] for m in ctx.side["surfaces"]["go_consumer"]["models"] if "#" in m)
    law = frozen_law(ctx, {ctx.frozen_pred, ok_go})
    if gc is not None:
        ri = gc.extra["real_inputs"]
        unpack_key, parse_key = ctx.side["surfaces"]["go_consumer"]["entry_points"]
        first = sorted(ctx.side["surfaces"]["go_consumer"]["header_steps"].items(),
                       key=lambda kv: [int(x) for x in kv[1].rsplit(":", 2)[1:]])[0]
        res = run_consumer(ctx)
        note_path = ROOT / HARNESS / "consumer_reachability.json"
        notes = json.loads(note_path.read_text())["labels"] if note_path.is_file() else {}
        for label, keys in sorted(ri["rejected"].items()):
            sha = sha256_hex(",".join(map(str, keys)).encode())
            sol = ri["solidity_on_rejected"] if label == first[0] else {}
            accepted = label == first[0] and sol == {"ok": len(keys)}
            msgs = sorted({str(res["r"][k][3])[2:300] for k in keys})
            t = {"surface": "go_consumer", "entry_points": [unpack_key, parse_key], "inputs": len(keys),
                 "batch_indices_sha256": sha, "go": label, "go_errors": msgs, "first_batch_index": keys[0],
                 "last_batch_index": keys[-1], "batch_indices": keys if len(keys) <= 32 else None}
            if accepted:
                t.update({"bin": "finding", "law": law, "solidity": "ok",
                          "why": (f"{len(keys)} real mainnet commits (batches {keys[0]}..{keys[-1]}) carry a parent "
                                  f"header that the chain accepted and that the pinned Solidity loader accepts "
                                  f"through the public commit function, while the pinned node's derivation rejects it "
                                  f"at its first header step ({first[1]}, {label}); the frozen {ctx.frozen_pred} and "
                                  f"{ok_go} say the same of every one, so it realizes {law}. A node whose derivation "
                                  f"range holds these commits stops at the first of them (reachability)")})
            else:
                t.update({"bin": "finding", "law": None, "solidity": None,
                          "why": (f"{len(keys)} real mainnet commits, accepted by the chain, pass the header steps of "
                                  f"the pinned node's ParseBatch and are rejected by a later step ({label}: "
                                  f"{msgs[0] if msgs else ''}); a node whose derivation range holds them stops at the "
                                  f"first of them (reachability)")})
            if label in notes:
                t["reachability"] = notes[label]
            out.append(t)
    # hostile headers one side's loader accepts and the other side's decoder rejects
    sl, gh = surfaces.get("sol_loader"), surfaces.get("go_header")
    if sl is not None and gh is not None:
        okv = ctx.frozen.run(ctx.frozen_pred, [hx(h) for h in ctx.header])
        okg = ctx.frozen.run(ok_go, [hx(h) for h in ctx.header])
        n = sum(1 for a, b in zip(okv, okg) if a is True and b is False)
        if n:
            commit_fn = consumer_commit_function(ctx)
            out.append({"surface": "sol_loader", "bin": "known_limitation", "law": law,
                        "entry_points": [commit_fn, f"({ctx.side['surfaces']['go_consumer']['header_methods'][0].split('(')[1]}"],
                        "inputs": n, "batch_indices_sha256": None, "solidity": "ok", "go": "error",
                        "why": (f"{n} hostile headers pass the Solidity loader of every public entry point and fail "
                                f"the Go decoders (the real sides agree with {ctx.frozen_pred} and {ok_go}); with the "
                                f"pinned code no public entry point commits such a header, so on hostile inputs alone "
                                f"this is a known limitation (the real commits of go_consumer show it on mainnet)")})
    for k, t in enumerate(out, 1):
        t["id"] = f"T{k}"
    return out


# ---------------------------------------------------------------- planted partiality mutants (attack A9)
def _bump_const(t, pred, done: list):
    """A copy of term t with the first integer constant k for which pred(k) holds replaced by k + 1 (Go documents
    write ["const", k], Solidity documents a bare int)."""
    if done[0] is not None:
        return t
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "const" and isinstance(t[1], int) and pred(t[1]):
            done[0] = t[1]
            return ["const", t[1] + 1]
        return [_bump_const(x, pred, done) for x in t]
    if isinstance(t, int) and not isinstance(t, bool) and pred(t):
        done[0] = t
        return t + 1
    return t


def _bump_all(t, k: int):
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "const" and t[1] == k:
            return ["const", k + 1]
        return [_bump_all(x, k) for x in t]
    if isinstance(t, int) and not isinstance(t, bool) and t == k:
        return k + 1
    return t


def mutate_paths(fn: dict, pred) -> str | None:
    """Mutate a function's path conditions in place: the first constant pred selects, everywhere in the paths."""
    done = [None]
    for p in fn.get("paths") or []:
        _bump_const(p.get("cond"), pred, done)
        if done[0] is not None:
            break
    if done[0] is None:
        return None
    k = done[0]
    for p in fn.get("paths") or []:
        p["cond"] = _bump_all(p.get("cond"), k)
    return f"{k} -> {k + 1}"


def run_mutants(ctx: Ctx, surfaces: dict[str, Surface]) -> list[dict]:
    """One planted partiality mutant per surface: a scratch copy of a compared document or model with one length
    constant, condition, guard or site status changed; detected iff the rerun reports a mismatch the unmutated run
    did not. The real side is not rerun (its outcomes are the unmutated run's); mutants are never written to disk in
    the repository."""
    out = []

    def record(name, mutation, new):
        base = surfaces[name].keys()
        added = sorted(new.keys() - base)
        out.append({"surface": name, "mutation": mutation, "detected": bool(added), "mismatches": len(added)})

    # sol_loader: the loader's first length constant
    d = copy.deepcopy(load(ctx.tree, ctx.loader_doc))
    m = mutate_paths(d["functions"][ctx.loader_fn], lambda k: k >= 2)
    record("sol_loader", f"{ctx.loader_doc}#{ctx.loader_fn}: the first length constant of its conditions {m}",
           surface_sol_loader(ctx, d))
    # sol_encoder: the encoder's first comparison constant
    d = copy.deepcopy(load(ctx.tree, ctx.encoder_doc))
    m = mutate_paths(d["functions"][ctx.encoder_fn], lambda k: k >= 1)
    record("sol_encoder", f"{ctx.encoder_doc}#{ctx.encoder_fn}: its first comparison constant {m}",
           surface_sol_encoder(ctx, d))
    # go_header and go_consumer: the first header method's length constant (in the consumer's first header method)
    key = ctx.side["surfaces"]["go_consumer"]["header_methods"][0]
    rel = ctx.sites.doc_of(key)
    docs = copy.deepcopy(ctx.sites.docs)
    m = mutate_paths(docs[rel]["go"]["functions"][key], lambda k: k >= 2)
    record("go_header", f"{rel}#{key}: its first length constant {m}", surface_go_header(ctx, docs))
    record("go_consumer", f"{rel}#{key}: its first length constant {m}", surface_go_consumer(ctx, docs))
    # go_encoders: the cache comparison of the first encoder (its paths and its layout's conditions)
    key = ctx.side["surfaces"]["go_encoders"]["entry_points"][0]
    rel = ctx.sites.doc_of(key)
    docs = copy.deepcopy(ctx.sites.docs)
    fn = docs[rel]["go"]["functions"][key]
    m = mutate_paths(fn, lambda k: k == 0)
    for e in docs[rel]["go"]["codecs"]["encoders"]:
        if e["function"] == key:
            e["conds"] = _bump_all(e["conds"], 0)
    record("go_encoders", f"{rel}#{key}: the cache length constant of its conditions {m}",
           surface_go_encoders(ctx, docs))
    # batchdata_act: the status of the first open site the run decided, made safe
    decided = sorted(p["site"] for p in surfaces["batchdata_act"].panics.values() if p["site_status"] == "open")
    docs = copy.deepcopy(ctx.sites.docs)
    if decided:
        for d in docs.values():
            for f in d["go"]["functions"].values():
                for st in f.get("sites") or []:
                    if st["id"] == decided[0]:
                        st["status"] = "safe"
        record("batchdata_act", f"the site {decided[0]}: status open -> safe", surface_batchdata_act(ctx, docs))
    else:
        out.append({"surface": "batchdata_act", "mutation": "no open site was decided: nothing to plant",
                    "detected": False, "mismatches": 0})
    # rollup_act: a guard condition changed: the first require (in the sidecar's modelled-action order, then guard
    # order) whose revert reason a hostile input of that action met on the real contract, negated (its expression
    # and every reach's), so the inputs that reached it are judged differently by the mutant
    if "rollup_act" in surfaces:
        R = ctx.cache["rollup"]["R"]
        doc = copy.deepcopy(R.doc)
        seen = surfaces["rollup_act"].labels_by_action
        what = None
        for an in ctx.side["surfaces"]["rollup_act"]["modelled_actions"]:
            a = next(x for x in doc["actions"] if x["name"] == an)
            met = {lab.split(":", 1)[1] for lab in seen.get(an, ()) if lab.startswith("revert:")}
            for g in a.get("guards") or []:
                if g.get("reason") in met:
                    g["expr"] = ["!", g["expr"]]
                    for r in g.get("reaches") or []:
                        r["expr"] = ["!", r["expr"]]
                    what = f"{an}: the require at {g.get('src')} ({g['reason']!r}) negated"
                    break
            if what:
                break
        p = ctx.work / "mutants" / Path(R.doc_rel).name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc))
        record("rollup_act", f"{R.doc_rel}#{what}", surface_rollup_act(ctx, R.model_of(p, ctx)))
    return out


# ---------------------------------------------------------------- the round's A2 record
def build(ctx: Ctx, only: list[str] | None = None) -> dict:
    want = set(only or SURFACES)
    surfaces: dict[str, Surface] = {}
    if want & {"go_header", "sol_loader"}:
        surfaces["go_header"] = surface_go_header(ctx)
    if "go_encoders" in want:
        surfaces["go_encoders"] = surface_go_encoders(ctx)
    if "batchdata_act" in want:
        surfaces["batchdata_act"] = surface_batchdata_act(ctx)
    parents: list[bytes] = []
    if want & {"go_consumer"}:
        surfaces["go_consumer"] = surface_go_consumer(ctx)
        parents = consumer_rejected_parents(ctx, surfaces["go_consumer"])
    if want & {"sol_loader", "sol_encoder", "go_consumer"}:
        sol = run_solidity(ctx, parents)
        reasons = ctx.side["surfaces"]["sol_loader"]["reasons"]
        if "go_consumer" in surfaces:
            labs: dict = {}
            for tag, (ok, ret) in zip(sol["tags"], sol["res"]):
                if tag[0] == "extra":
                    lab = sol_label(ok, ret, reasons)
                    labs[lab] = labs.get(lab, 0) + 1
            surfaces["go_consumer"].extra["real_inputs"]["solidity_on_rejected"] = dict(sorted(labs.items()))
        if "sol_loader" in want:
            surfaces["sol_loader"] = surface_sol_loader(ctx)
        if "sol_encoder" in want:
            surfaces["sol_encoder"] = surface_sol_encoder(ctx)
    if "rollup_act" in want:
        surfaces["rollup_act"] = surface_rollup_act(ctx)
    surfaces = {k: v for k, v in surfaces.items() if k in want}
    findings = round_findings(ROOT)
    a2 = {"round": ctx.side["round"], "milestone": ctx.side["milestone"], "target_commit": ctx.commit,
          "seed": ctx.seed,
          "corpora": {"header": digest(ctx.header), "act_header": digest(ctx.act_header),
                      "encoder": digest([encoder_bytes(e) for e in ctx.encoder])},
          "surfaces": {n: s.record(findings) for n, s in sorted(surfaces.items())},
          "codec_labels": codec_labels(ctx, surfaces) if {"sol_encoder", "go_header", "go_encoders"} <= set(surfaces)
          else {},
          "target_findings": target_findings(ctx, surfaces)}
    a2["mutants"] = run_mutants(ctx, surfaces) if set(SURFACES) <= set(surfaces) else []
    from ..replay import PIN_KEYS
    a2["toolchain"] = {k: ctx.tc[k] for k in (*PIN_KEYS, "go_version")}
    a2["checkout_commit"] = git_checkout_head(ctx.checkout)
    return a2


def git_checkout_head(checkout: Path) -> str:
    p = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip()


# ---------------------------------------------------------------- the CLI
def checkout_flags() -> list[str]:
    """--checkout, and the replay configuration's own key for the pinned checkout as an alias."""
    from ..replay import replay_config
    cfg = replay_config(ROOT)
    path = None
    try:
        from ..replay import morph_path as _checkout_path   # noqa: N813 (the adapter's name for it)
        path = str(_checkout_path(argparse.Namespace(), ROOT))
    except Exception:  # noqa: BLE001
        pass
    alias = sorted(k for k, v in cfg.items() if isinstance(v, str) and k.isalpha() and path and
                   str(Path(v).resolve()) == path)
    return ["--checkout"] + [f"--{a}" for a in alias]


def default_checkout() -> Path:
    from ..replay import morph_path as _checkout_path   # noqa: N813
    return Path(_checkout_path(argparse.Namespace(), ROOT))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon audit hostile", description=__doc__.split("\n\n")[0])
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--surface", action="append", choices=SURFACES)
    ap.add_argument(*checkout_flags(), dest="checkout", help="the pinned source checkout (default: config replay)")
    ap.add_argument("--snapshot", help="the I59 snapshot (default: HOLON_HISTORICAL_DIR or ~/.holon/historical)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--target", help="the audited commit (default: the target_commit of the committed output)")
    ap.add_argument("--work", help="scratch directory (default: a fresh temporary directory)")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--check", action="store_true", help="rebuild from the committed file's target commit and "
                                                         "compare byte for byte")
    a = ap.parse_args(argv)
    side_round = (a.milestone, a.round)
    if side_round != ("M2", 2):
        print("hostile: only audit round M2/2 has an instrument (spec/M2/lib/audit_round2.json)", file=sys.stderr)
        return 2
    out = Path(a.out)
    out = out if out.is_absolute() else ROOT / out
    target = a.target
    if a.check or not target:
        if not out.exists():
            print(f"hostile: {out} does not exist: pass --target", file=sys.stderr)
            return 2
        target = json.loads(out.read_text())["target_commit"]
    work = Path(a.work).resolve() if a.work else Path(tempfile.mkdtemp(prefix="holon-i21-hostile-"))
    os.environ["HOLON_BUILD_DIR"] = str(work / "build")
    try:
        commit = resolve_commit(target)
        tree = materialize(commit, work / "tree")
        ctx = Ctx(tree, work, Path(a.checkout).resolve() if a.checkout else default_checkout(),
                  Path(a.snapshot) if a.snapshot else None, commit, a.jobs)
        from ..replay import check_checkout
        check_checkout(ctx.checkout, load(tree, ctx.loader_doc)["target"]["commit"])
        a2 = build(ctx, a.surface)
    except HostileError as e:
        print(f"hostile: {e}", file=sys.stderr)
        return 2
    text = canonical(a2)
    if a.check:
        same = out.read_text() == text
        print(f"hostile --check: {'identical' if same else 'DIFFERS from'} {out.relative_to(ROOT)} "
              f"(target {commit[:12]})")
        if not same:
            (work / "a2.rebuilt.json").write_text(text)
            print(f"hostile --check: the rebuilt record is {work / 'a2.rebuilt.json'}")
        else:
            shutil.rmtree(work, ignore_errors=True)
        return 0 if same else 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"hostile: wrote {out} (target {commit[:12]}; surfaces {', '.join(sorted(a2['surfaces']))})")
    if not a.work:
        shutil.rmtree(work, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
