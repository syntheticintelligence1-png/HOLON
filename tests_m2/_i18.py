"""I18 helpers: the instruments fixed at the I18 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m2/test_extract_go.py. Nothing here imports holon/ at module level: the CLI
runs as a subprocess and holon modules are imported lazily, so a missing module fails the test that needs it (red),
never the import of a test module. What decides a prediction is computed here, independently of the code under test:

- the frozen layouts, ok_go and the getter expectations are read from facts/morph_header.json directly (no holon);
- `outcome` evaluates an extracted path set on a concrete probe (a byte string of a given len, cap and byte 0);
- `run_go_instrument` runs tests_m2/fixtures/go_frontend/holon_i18_instrument.go.txt on the real morph
  common/batch at the pinned commit (a scratch copy; the checkout is never touched);
- `audit_violations` judges the file, directory and process events an audit hook recorded during a run;
- `grammar_problems` checks the term, atom, cell and ordering rules of the contract.
A missing toolchain, checkout or output is a failure with a message, never a skip.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NamedTuple

from tests._util import config
from tests_m2._m2 import ROOT, holon_module, load_json, validate  # noqa: F401  (holon_module re-exported)

CONFIG = ROOT / "spec" / "M2" / "lib" / "go_frontend.json"
FACTS_DIR = ROOT / "spec" / "M2" / "facts"
GO_SCHEMA = ROOT / "spec" / "schemas" / "facts_0_3_go.schema.json"
SHARED_SCHEMA = ROOT / "spec" / "schemas" / "facts_0_3.schema.json"
FROZEN = ROOT / "facts" / "morph_header.json"
FIX = ROOT / "tests_m2" / "fixtures" / "go_frontend"
TOY = FIX / "toy"
TOY_CONFIG = FIX / "toy_config.json"
INSTRUMENT = FIX / "holon_i18_instrument.go.txt"
FRONTEND = ROOT / "holon" / "frontends" / "go"
SSADUMP = FRONTEND / "ssadump"
GO_VERSION = "go1.24.7"
X_TOOLS = "v0.36.0"
SSADUMP_VERSION = "holon-ssadump/0.1"
# go.sum lines verified at the prereg (`go get golang.org/x/tools@v0.36.0` + `go mod tidy` through the proxy into a
# scratch GOMODCACHE, checked against sum.golang.org). The two x/tools lines are required; no other line is allowed.
GO_SUM_REQUIRED = (
    "golang.org/x/tools v0.36.0 h1:kWS0uv/zsvHEle1LbV5LE8QujrxB3wfQyxHfhOk0Qkg=",
    "golang.org/x/tools v0.36.0/go.mod h1:WBDiHKJK8YgLHlcQPYQzNCkUxUypCaa5ZegCVutKm+s=",
)
GO_SUM_ALLOWED = GO_SUM_REQUIRED + (
    "github.com/google/go-cmp v0.6.0 h1:ofyhxvXcZhMsU5ulbFiLKl/XBFqE1GSq7atu8tAmTRI=",
    "github.com/google/go-cmp v0.6.0/go.mod h1:17dUlkBOakJ0+DkrSSNjCkIjxS6bF9zb3elmeNGIjoY=",
    "golang.org/x/mod v0.27.0 h1:kb+q2PyFnEADO2IEF935ehFUXlWiNjJWtRNgBLSfbxQ=",
    "golang.org/x/mod v0.27.0/go.mod h1:rWI627Fq0DEoudcK+MBkNkCe0EetEaDSwJJkCcjpazc=",
    "golang.org/x/sync v0.16.0 h1:ycBJEhp9p4vXvUZNszeOq0kGTPghopOL8q0fq3vstxw=",
    "golang.org/x/sync v0.16.0/go.mod h1:1dzgHSNfp02xaA81J2MS99Qcpr2w7fw1gpm99rleRqA=",
)
GENERIC_ASSUMPTIONS = ("go-append-growth", "go-errors-nonnil", "go-nil-deref-not-modelled", "go-opaque-calls")
O4_WORDS = [0, 3967, 3968, 4095]
PROBE_VERSIONS = (0, 1, 2, 3, 255)
CAP_EXTRA = 16
NODE_TYPES_METHODS = ("validate", "Bytes", "Hash", "Version", "BatchIndex", "L1MessagePopped", "TotalL1MessagePopped",
                      "DataHash", "BlobVersionedHash", "BlobHashesHash", "PrevStateRoot", "PostStateRoot",
                      "WithdrawalRoot", "SequencerSetVerifyHash", "ParentBatchHash", "LastBlockNumber")
SPAN_RE = re.compile(r"^[^:\s]+\.go:\d+(:\d+)?$")
SITE_ID_RE = re.compile(r"^[^:\s]+\.go:\d+:\d+:(index|slice|prim|convert|panic|assert)(#\d+)?$")
OPS = {"==", "!=", "<", "<=", ">", ">="}
BINOPS = {"+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "&^"}


# ------------------------------------------------------------------ basics
def sha256_file(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ssadump_sha256() -> str:
    """sha256(main.go + go.mod + go.sum), the contract's extraction.tool.ssadump_sha256 and cache key."""
    h = hashlib.sha256()
    for name in ("main.go", "go.mod", "go.sum"):
        p = SSADUMP / name
        if not p.is_file():
            raise AssertionError(f"{p.relative_to(ROOT)} is missing")
        h.update(p.read_bytes())
    return h.hexdigest()


def has_build_constraint(p: Path) -> bool:
    head = Path(p).read_text(encoding="utf-8", errors="replace").split("\npackage ", 1)[0]
    return bool(re.search(r"^//go:build |^// \+build ", head, re.M))


def go_binary() -> str:
    found = shutil.which("go") or ("/usr/local/go/bin/go" if Path("/usr/local/go/bin/go").is_file() else None)
    if not found:
        raise AssertionError("no go toolchain on PATH or at /usr/local/go/bin/go (pinned: config replay.go_version)")
    return found


def check_go_version() -> str:
    go = go_binary()
    want = (config().get("replay") or {}).get("go_version")
    got = subprocess.run([go, "version"], capture_output=True, text=True, timeout=120).stdout.strip()
    if got != want:
        raise AssertionError(f"`go version` is {got!r}, pinned {want!r} (config/holon.json replay.go_version)")
    return go


def morph_checkout() -> Path:
    """The pinned morph checkout (config replay.morph) at the sidecar's target commit, clean."""
    cfg = config().get("replay") or {}
    if not cfg.get("morph"):
        raise AssertionError("config/holon.json replay.morph is not pinned")
    morph = Path(cfg["morph"])
    if not (morph / "common" / "batch").is_dir():
        raise AssertionError(f"pinned morph checkout {morph} is missing common/batch")
    head = subprocess.run(["git", "-C", str(morph), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    want = load_json(CONFIG)["target"]["commit"]
    if head != want:
        raise AssertionError(f"{morph} is at {head!r}, not at the sidecar's commit {want}")
    dirty = subprocess.run(["git", "-C", str(morph), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise AssertionError(f"{morph} has local changes:\n{dirty[:2000]}")
    return morph


def copy_go_tree(src: Path, dst: Path) -> Path:
    """A scratch copy of a Go source tree as the contract's workspace rule copies it (go.work, go.work.sum and its
    `use` directories; else the whole tree), skipping .git, node_modules, .env* and bunfig.toml."""
    ign = shutil.ignore_patterns(".git", "node_modules", ".env", ".env.*", "bunfig.toml")
    dst.mkdir(parents=True, exist_ok=True)
    work = src / "go.work"
    if not work.is_file():
        shutil.copytree(src, dst, symlinks=True, ignore=ign, dirs_exist_ok=True)
        return dst
    text = work.read_text()
    uses = re.findall(r"^\s*(\./[^\s)]+|\.)\s*$", text.split("use", 1)[1], re.M) if "use" in text else []
    for u in uses:
        rel = u[2:] if u.startswith("./") else ""
        shutil.copytree(src / rel, dst / rel, symlinks=True, ignore=ign, dirs_exist_ok=True)
    for f in ("go.work", "go.work.sum"):
        if (src / f).is_file():
            shutil.copy(src / f, dst / f)
    return dst


# ------------------------------------------------------------------ runs
AUDIT_WRAPPER = r'''
import json, os, sys
log, args = sys.argv[1], sys.argv[2:]
events = []
def _p(x):
    try:
        return os.path.realpath(os.fsdecode(x))
    except Exception:
        return None
def hook(ev, a):
    if ev == "open" and a and isinstance(a[0], (str, bytes, os.PathLike)):
        events.append(["open", _p(a[0])])
    elif ev in ("os.listdir", "os.scandir"):
        events.append(["list", _p(a[0] if a and a[0] is not None else ".")])
    elif ev == "subprocess.Popen":
        exe, argv, cwd = a[0], a[1], a[2]
        events.append(["exec", json.dumps([os.fsdecode(exe) if exe else None,
                                           [os.fsdecode(x) for x in (argv or [])],
                                           _p(cwd) if cwd else _p(os.getcwd())])])
sys.addaudithook(hook)
from holon.__main__ import main
try:
    rc = main(args)
except SystemExit as e:
    rc = e.code if isinstance(e.code, int) else 2
snapshot = list(events)
with open(log, "w") as f:
    json.dump({"rc": rc, "events": snapshot}, f)
sys.exit(rc or 0)
'''


class Run:
    """One `python -m holon extract go ... --out-dir DIR` invocation and the documents it wrote."""

    def __init__(self, args: list[str], audit: bool = False, timeout: int = 1800):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i18-"))
        self.out = self.tmp / "out"
        self.out.mkdir()
        full = ["extract", "go", *args, "--out-dir", str(self.out)]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        self.events: list = []
        if audit:
            log = self.tmp / "audit.json"
            cwd = self.tmp / "cwd"
            cwd.mkdir()
            p = subprocess.run([sys.executable, "-c", AUDIT_WRAPPER, str(log), *full], cwd=cwd, env=env,
                               capture_output=True, text=True, timeout=timeout)
            if log.exists():
                self.events = [tuple(e) for e in json.loads(log.read_text())["events"]]
        else:
            p = subprocess.run([sys.executable, "-m", "holon", *full], cwd=ROOT, env=env, capture_output=True,
                               text=True, timeout=timeout)
        self.code = p.returncode
        self.log = f"exit {p.returncode}\n--- stdout\n{p.stdout[-3000:]}\n--- stderr\n{p.stderr[-3000:]}"
        self.texts = {f.name[:-len(".go.extracted.json")]: f.read_text(encoding="utf-8")
                      for f in sorted(self.out.glob("*.go.extracted.json"))}
        self.docs = {k: json.loads(v) for k, v in self.texts.items()}

    @classmethod
    def morph(cls, audit: bool = False, src: Path | None = None) -> "Run":
        check_go_version()
        if src is None:
            morph_checkout()
        return cls(["--milestone", "M2", "--root", str(ROOT)] + (["--src", str(src)] if src else []), audit=audit)

    @classmethod
    def toy(cls) -> "Run":
        check_go_version()
        return cls(["--root", str(ROOT), "--config", str(TOY_CONFIG)])

    def need(self) -> dict:
        if self.code != 0 or not self.docs:
            raise AssertionError(f"holon extract go wrote no documents\n{self.log}")
        return self.docs

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


ALLOWED_READ = ("holon/", "spec/M2/lib/go_frontend.json", "config/holon.json", "spec/schemas/")


def audit_violations(events) -> list[str]:
    """Events under the repository root outside the allowlist (opening, listing, or naming in a subprocess's
    arguments or working directory). Listing the root itself is the import machinery and is allowed."""
    root = str(ROOT.resolve())

    def rel(p):
        if not p:
            return None
        p = os.path.realpath(p)
        if p == root:
            return ""
        return p[len(root) + 1:] if p.startswith(root + os.sep) else None

    def ok(r: str) -> bool:
        return any(r == a.rstrip("/") or r.startswith(a) for a in ALLOWED_READ)

    out = []
    for kind, payload in events:
        if kind in ("open", "list"):
            r = rel(payload)
            if r is None or (kind == "list" and r == ""):
                continue
            if not ok(r):
                out.append(f"{kind} {r}")
        elif kind == "exec":
            exe, argv, cwd = json.loads(payload)
            rc = rel(cwd)
            if rc is not None and rc != "holon/frontends/go/ssadump":
                out.append(f"exec in {rc or '.'}: {argv[:4]}")
            for a in [exe, *argv]:
                if a and os.path.isabs(a):
                    r = rel(a)
                    if r is not None and not r.startswith("holon/frontends/go/"):
                        out.append(f"exec argument {r}: {argv[:4]}")
    return sorted(set(out))


# ------------------------------------------------------------------ document access
def function(docs: dict, fid: str) -> dict:
    hits = [d["go"]["functions"][fid] for d in docs.values() if fid in d["go"]["functions"]]
    if len(hits) != 1:
        raise AssertionError(f"{fid}: found in {len(hits)} documents")
    return hits[0]


def section(docs: dict, *keys: str) -> list:
    out = []
    for stem in sorted(docs):
        x = docs[stem]["go"]
        for k in keys:
            x = x[k]
        out.extend(x)
    return out


def result_entry(docs: dict, fid: str, i: int) -> dict:
    hits = [r for r in section(docs, "slices", "results") if r["function"] == fid and r["result"] == i]
    if len(hits) != 1:
        raise AssertionError(f"{fid} result {i}: {len(hits)} entries")
    return hits[0]


def reads(docs: dict, fid: str, via: bool = False) -> list:
    hits = [d for d in section(docs, "codecs", "decoders") if d["function"] == fid]
    if len(hits) != 1:
        raise AssertionError(f"{fid}: {len(hits)} decoder entries")
    return [(r["offset"], r["width"], r["via"]) if via else (r["offset"], r["width"]) for r in hits[0]["reads"]]


def field_chain(term, recv: str):
    """["field", ["field", ["param", recv], a], b] -> [a, b]; None when not rooted at that parameter."""
    names = []
    while isinstance(term, list) and term and term[0] == "field":
        names.append(term[2])
        term = term[1]
    if term != ["param", recv]:
        return None
    return list(reversed(names))


def cell_callee(c, k: int):
    if isinstance(c, list) and len(c) == 3 and c[0] == "byte" and c[2] == k and c[1][0] == "call":
        return c[1][1]
    return None


def rename_param(t, a: str, b: str):
    if isinstance(t, list):
        if t == ["param", a]:
            return ["param", b]
        return [rename_param(x, a, b) for x in t]
    return t


def blank_spans(x):
    if isinstance(x, str):
        return "<span>" if SPAN_RE.match(x) or SITE_ID_RE.match(x) else x
    if isinstance(x, list):
        return [blank_spans(y) for y in x]
    if isinstance(x, dict):
        return {k: blank_spans(v) for k, v in x.items()}
    return x


def normalize_package(obj, pkg: str, to: str):
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False).replace(pkg + ".", to + ".")
    return blank_spans(json.loads(text))


def backing_label(b) -> str:
    """The last field name of an ["of", T] backing whose T is a field chain, else its JSON."""
    if isinstance(b, list) and len(b) == 2 and b[0] == "of" and isinstance(b[1], list) and b[1][:1] == ["field"]:
        return b[1][2]
    return json.dumps(b)


def use_kinds(uses: list) -> list:
    return sorted({(u["kind"], u.get("callee"), u.get("index")) for u in uses}, key=lambda t: json.dumps(t))


def primitives_named(go: dict, prims: dict) -> set:
    found = set()

    def walk(x):
        if isinstance(x, str):
            if x in prims:
                found.add(x)
        elif isinstance(x, list):
            for y in x:
                walk(y)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    walk(go)
    return found


# ------------------------------------------------------------------ frozen facts (read directly, no holon)
def frozen_facts() -> dict:
    return load_json(FROZEN)


def go_leaf_map(facts: dict) -> dict:
    """Go field name (first token of a header field's frozen "go" text) -> frozen field name."""
    out = {}
    for f in facts["types"]["Header"]["fields"]:
        tok = (f.get("go") or "").split()
        if tok and re.fullmatch(r"[A-Z]\w*", tok[0]):
            out[tok[0]] = f["name"]
    return out


def frozen_layout(facts: dict, fn: str, version: int) -> list:
    """The frozen Go encoder layout: zero memory of the facts' length, then each op in order."""
    f = facts["functions"][fn]
    width = {x["name"]: x["width"] for x in facts["types"]["Header"]["fields"]}
    mem = [["const", 0] for _ in range(f["length"])]
    for op in f["ops"]:
        w = op.get("when")
        if w and version < w["version_ge"]:
            continue
        cells = []
        for s in op["src"]:
            if "field" in s:
                cells += [["field", s["field"], k] for k in range(width[s["field"]])]
            elif "zeros" in s:
                cells += [["const", 0] for _ in range(s["zeros"])]
            else:
                cells.append(["const", s["const"]])
        mem[op["offset"]:op["offset"] + len(cells)] = cells
    return mem


def to_frozen_cells(cells: list, recv: str, facts: dict) -> list:
    leaf = go_leaf_map(facts)
    out = []
    for c in cells:
        if c[0] == "byte":
            chain = field_chain(c[1], recv)
            out.append(["field", leaf.get(chain[-1], "?" + chain[-1]), c[2]] if chain else ["?", c])
        else:
            out.append(c)
    return out


def getter_method(g: dict) -> str:
    m = re.match(r"^(\w+)\(\)", g["code"])
    if not m:
        raise AssertionError(f"frozen getter {g['name']}: code {g['code']!r} names no method")
    return m.group(1)


class Probe(NamedTuple):
    n: int
    cap: int
    b0: int


def frozen_ok(facts: dict, p: Probe) -> bool:
    """facts/morph_header.json ok_go on a probe (its rules in order)."""
    for r in facts["functions"]["ok_go"]["rules"]:
        c = r["if"]
        if c == "empty":
            if p.n == 0:
                return r["then"]
            continue
        if c == "otherwise":
            return r["then"]
        if p.b0 in c["version_in"]:
            t = r["then"]
            return p.n == t["len_eq"] if "len_eq" in t else p.n >= t["len_ge"]
    return False


def frozen_decoder_expectations(facts: dict) -> dict:
    """method -> predicate(probe) for the nil-error outcome, per I18-P2: validate and Hash: ok_go; the method the
    frozen ok_go 'empty' rule's code names (Version): length >= 1; every other frozen getter's method: ok_go and its
    frozen "when"."""
    rules = facts["functions"]["ok_go"]["rules"]
    empty = next(r for r in rules if r["if"] == "empty")
    empty_method = re.match(r"^(\w+)\(\)", empty["code"]).group(1)
    out = {"validate": lambda p: frozen_ok(facts, p), "Hash": lambda p: frozen_ok(facts, p)}
    for g in facts["functions"]["dec_go"]["getters"]:
        m = getter_method(g)
        if m == empty_method:
            out[m] = lambda p: p.n >= 1
        else:
            w = g.get("when")
            out[m] = (lambda w: lambda p: frozen_ok(facts, p) and (not w or p.b0 >= w["version_ge"]))(w)
    return out


def probes(facts: dict) -> list:
    """Every getter offset and offset + width of the frozen dec_go and every ok_go length, each -1, 0, +1, plus
    0, 1, 2; byte 0 in PROBE_VERSIONS; cap len and len + CAP_EXTRA. Length 0 has one probe per cap."""
    cs = set()
    for g in facts["functions"]["dec_go"]["getters"]:
        cs |= {g["offset"], g["offset"] + g["width"]}
    for r in facts["functions"]["ok_go"]["rules"]:
        if isinstance(r["then"], dict):
            cs |= {v for k, v in r["then"].items() if k in ("len_eq", "len_ge")}
    lengths = sorted({0, 1, 2} | {c + d for c in cs if c > 0 for d in (-1, 0, 1)})
    out = []
    for n in lengths:
        for cap in (n, n + CAP_EXTRA):
            for v in (PROBE_VERSIONS if n > 0 else (0,)):
                out.append(Probe(n, cap, v))
    return out


# ------------------------------------------------------------------ path evaluation
class Unevaluable(AssertionError):
    pass


_UNSIGNED = {"uint8": 8, "byte": 8, "uint16": 16, "uint32": 32, "uint64": 64, "uint": 64, "uintptr": 64}


def eval_term(t, env: dict):
    tag = t[0]
    if tag == "const":
        return t[1]
    if tag == "bool":
        return t[1]
    if tag == "nil":
        return None
    if tag == "param":
        if t[1] not in env:
            raise Unevaluable(f"no value for {t}")
        return env[t[1]]
    if tag in ("len", "cap"):
        x = eval_term(t[1], env)
        if not isinstance(x, Probe):
            raise Unevaluable(f"{tag} of {t[1]}")
        return x.n if tag == "len" else x.cap
    if tag == "index":
        x, i = eval_term(t[1], env), eval_term(t[2], env)
        if not isinstance(x, Probe) or not isinstance(i, int):
            raise Unevaluable(f"index {t}")
        if not 0 <= i < x.n:
            raise Unevaluable(f"a path condition reads byte {i} of a {x.n}-byte probe: {t}")
        return x.b0 if i == 0 else 0
    if tag == "op":
        a, b = eval_term(t[2], env), eval_term(t[3], env)
        if not isinstance(a, int) or not isinstance(b, int):
            raise Unevaluable(f"op {t}")
        return {"+": a + b, "-": a - b, "*": a * b, "/": int(a / b) if b else 0, "%": a % b if b else 0,
                "&": a & b, "|": a | b, "^": a ^ b, "<<": a << b, ">>": a >> b, "&^": a & ~b}[t[1]]
    if tag == "convert":
        x = eval_term(t[2], env)
        bits = _UNSIGNED.get(t[1])
        return x % (1 << bits) if bits and isinstance(x, int) else x
    raise Unevaluable(f"term {t}")


def eval_atom(a, env: dict) -> bool:
    if a[0] in ("true", "false"):
        v = eval_term(a[1], env)
        return bool(v) if a[0] == "true" else not v
    x, y = eval_term(a[1], env), eval_term(a[2], env)
    if a[0] in ("==", "!="):
        return (x == y) == (a[0] == "==")
    return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[a[0]]


def holds(path: dict, env: dict) -> bool:
    for a in path["cond"]:
        if not eval_atom(a, env):
            return False
    return True


def outcome(f: dict, p: Probe, param: str | None = None) -> str:
    """"ok" | "err" | "panic": the end of the one extracted path of f that holds on the probe bound to f's byte-slice
    parameter (the first parameter unless named)."""
    if f.get("paths") is None:
        raise AssertionError(f"no paths ({f.get('paths_reason')})")
    name = param or f["params"][0]["name"]
    hit = [x for x in f["paths"] if holds(x, {name: p})]
    if len(hit) != 1:
        raise AssertionError(f"{len(hit)} paths hold on {p}")
    x = hit[0]
    if x["end"] == "panic":
        return "panic"
    if x["error"] in (None, "nil"):
        return "ok"
    if x["error"] == "nonnil":
        return "err"
    raise AssertionError(f"error classification {x['error']!r} on {p}")


# ------------------------------------------------------------------ loops
def _var_star(t):
    if isinstance(t, list):
        if t and t[0] == "var":
            return ["var", "*", t[2]]
        return [_var_star(x) for x in t]
    return t


def loop_shape(l: dict, f: dict | None = None) -> tuple:
    return (l["span"], l["kind"], l["iv"], _var_star(l["init"]), l["step"], l["cmp"], _var_star(l["limit"]),
            _var_star(l["fuel"]), l["exits"])


_CB, _BLOB, _DER = "morph-l2/common/batch", "morph-l2/common/blob", "morph-l2/node/derivation"
_BC = ["op", "/", ["op", "-", ["op", "+", ["len", ["param", "blobBytes"]], ["const", 126976]], ["const", 1]],
       ["const", 126976]]
_FIRST = ["field", ["param", "batchInfo"], "firstBlockNumber"]
_LAST = ["field", ["param", "batchInfo"], "lastBlockNumber"]


def _range(span, x, exits):
    return (span, "range", None, ["const", 0], 1, "<", ["len", x], ["len", x], exits)


def _counted(span, iv, limit, exits, init=None, cmp="<", fuel=None):
    init = ["const", 0] if init is None else init
    return (span, "counted", iv, init, 1, cmp, limit, limit if fuel is None else fuel, exits)


EXPECTED_LOOPS = {
    f"(*{_CB}.BatchData).Append": [_range("common/batch/batch_data.go:38", ["param", "l1TxHashes"], [])],
    f"(*{_CB}.BatchData).DataHash": [_counted("common/batch/batch_data.go:74", "i",
                                              ["convert", "int", ["field", ["param", "cks"], "blockNum"]], [])],
    f"{_CB}.MakeBlobCanonical": [_counted("common/batch/blob.go:33", "i", ["const", 4096], ["break"])],
    f"{_CB}.RetrieveBlobBytes": [_counted("common/batch/blob.go:47", "i", ["const", 4096], ["return"])],
    f"{_CB}.MakeBlobTxSidecar": [_counted("common/batch/blob.go:89", "i", _BC, ["return"])],
    f"{_CB}.DecodeTxsFromBytes": [("common/batch/blob.go:120", "unbounded", None, None, None, None, None, None,
                                   ["return"])],
    f"{_CB}.ParsingTxs": [_range("common/batch/batch_cache.go:1755", ["param", "transactions"], ["return"])],
    f"{_CB}.aggregateBlobHashes": [_range("common/batch/batch_cache.go:1791", ["param", "hashes"], [])],
    f"{_BLOB}.MakeBlobCanonical": [_counted("common/blob/payload.go:31", "i", ["const", 4096], ["break"])],
    f"{_BLOB}.RetrieveBlobBytes": [_counted("common/blob/payload.go:45", "i", ["const", 4096], ["return"])],
    f"{_BLOB}.MakeBlobTxSidecar": [_counted("common/blob/payload.go:87", "i", _BC, ["return"])],
    f"(*{_DER}.BatchInfo).ParseBatch": [
        _range("node/derivation/batch_info.go:114", ["field", ["field", ["param", "batch"], "Sidecar"], "Blobs"],
               ["return"]),
        _counted("node/derivation/batch_info.go:209", "i", ["convert", "int", ["var", "*", "blockCount"]], ["return"])],
    f"(*{_DER}.Derivation).rebuildBlob": [
        _counted("node/derivation/verify_local.go:159", "n", _LAST, ["return"], init=_FIRST, cmp="<=",
                 fuel=["op", "+", ["op", "-", _LAST, _FIRST], ["const", 1]])],
}


# ------------------------------------------------------------------ grammar
_TERM_TAGS = {"const", "bool", "str", "nil", "zero", "param", "global", "field", "len", "cap", "index", "slice", "op",
              "unop", "convert", "iface", "call", "result", "append", "alloc", "var", "unknown"}


def term_problems(t, where: str) -> list[str]:
    bad = []

    def chk(x, w):
        if not isinstance(x, list) or not x or x[0] not in _TERM_TAGS:
            bad.append(f"{w}: not a term: {str(x)[:80]}")
            return
        tag, a = x[0], x[1:]
        shape = {"const": lambda: len(a) == 1 and isinstance(a[0], int) and not isinstance(a[0], bool),
                 "bool": lambda: len(a) == 1 and isinstance(a[0], bool),
                 "str": lambda: len(a) == 1 and isinstance(a[0], str),
                 "nil": lambda: not a,
                 "zero": lambda: len(a) == 1 and isinstance(a[0], str),
                 "param": lambda: len(a) == 1 and isinstance(a[0], str),
                 "global": lambda: len(a) == 1 and isinstance(a[0], str),
                 "field": lambda: len(a) == 2 and isinstance(a[1], str),
                 "len": lambda: len(a) == 1, "cap": lambda: len(a) == 1, "index": lambda: len(a) == 2,
                 "slice": lambda: len(a) == 4,
                 "op": lambda: len(a) == 3 and a[0] in BINOPS,
                 "unop": lambda: len(a) == 2 and a[0] in ("-", "^", "!"),
                 "convert": lambda: len(a) == 2 and isinstance(a[0], str),
                 "iface": lambda: len(a) == 2 and isinstance(a[0], str),
                 "call": lambda: len(a) == 2 and isinstance(a[0], str) and isinstance(a[1], list),
                 "result": lambda: len(a) == 2 and isinstance(a[1], int),
                 "append": lambda: len(a) == 2,
                 "alloc": lambda: len(a) == 2 and isinstance(a[0], str) and SPAN_RE.match(a[0]) is not None,
                 "var": lambda: len(a) == 2 and isinstance(a[0], str) and (a[1] is None or isinstance(a[1], str)),
                 "unknown": lambda: len(a) == 1 and isinstance(a[0], str)}[tag]
        if not shape():
            bad.append(f"{w}: malformed {tag} term: {str(x)[:120]}")
            return
        subs = {"field": [a[0]], "len": [a[0]], "cap": [a[0]], "index": a, "slice": [y for y in a if y is not None],
                "op": a[1:], "unop": a[1:], "convert": a[1:], "iface": a[1:], "call": a[1], "result": a[:1],
                "append": a, "alloc": [a[1]] if a[1] is not None else []}.get(tag, [])
        for y in subs:
            chk(y, w)
    chk(t, where)
    return bad


def atom_problems(a, where: str) -> list[str]:
    if isinstance(a, list) and len(a) == 3 and a[0] in OPS:
        return term_problems(a[1], where) + term_problems(a[2], where)
    if isinstance(a, list) and len(a) == 2 and a[0] in ("true", "false"):
        return term_problems(a[1], where)
    return [f"{where}: not an atom: {str(a)[:80]}"]


def cell_problems(c, where: str) -> list[str]:
    if c == ["unknown"]:
        return []
    if isinstance(c, list) and len(c) == 2 and c[0] == "const" and isinstance(c[1], int) and 0 <= c[1] <= 255:
        return []
    if isinstance(c, list) and len(c) == 3 and c[0] in ("byte", "byte_le") and isinstance(c[2], int):
        return term_problems(c[1], where)
    return [f"{where}: not a cell: {str(c)[:80]}"]


def _sorted_by(xs: list, key, where: str) -> list[str]:
    ks = [key(x) for x in xs]
    return [] if ks == sorted(ks) else [f"{where}: not sorted"]


def grammar_problems(doc: dict) -> list[str]:
    g = doc["go"]
    bad: list[str] = []
    for fid, f in g["functions"].items():
        for p in f["paths"] or []:
            for a in p["cond"]:
                bad += atom_problems(a, f"{fid} cond")
            for t in p["returns"] or []:
                bad += term_problems(t, f"{fid} returns")
            if p["end"] not in ("return", "panic") or p["error"] not in (None, "nil", "nonnil", "unknown"):
                bad.append(f"{fid}: bad path end/error")
        ids = [s["id"] for s in f["sites"]]
        if ids != sorted(set(ids)):
            bad.append(f"{fid}: site ids not sorted and unique")
        for s in f["sites"]:
            if not SITE_ID_RE.match(s["id"]) or s["status"] not in ("safe", "open"):
                bad.append(f"{fid}: bad site {s['id']}")
            for a in s["bound"] or []:
                bad += atom_problems(a, f"{fid} site {s['id']}")
    c = g["codecs"]
    for e in c["encoders"]:
        if len(e["cells"]) != e["length"]:
            bad.append(f"{e['function']}: {len(e['cells'])} cells for length {e['length']}")
        for x in e["cells"]:
            bad += cell_problems(x, e["function"])
        if e["exact"] != all(x != ["unknown"] for x in e["cells"]):
            bad.append(f"{e['function']}: exact flag")
    bad += _sorted_by(c["encoders"], lambda e: (e["function"], e["length"], json.dumps(e["cells"])), "encoders")
    for k in ("decoders", "predicates"):
        bad += _sorted_by(c[k], lambda e: e["function"], k)
    for k in ("matches", "absences"):
        bad += _sorted_by(c[k], lambda e: (e["predicate"], e["index"], e["value"], e["length"]), k)
    bad += _sorted_by(c["patches"], lambda e: (e["function"], e["site"]), "patches")
    s = g["slices"]
    bad += _sorted_by(s["results"], lambda e: (e["function"], e["result"]), "results")
    for k in ("writes", "stores", "lost_writes"):
        bad += _sorted_by(s[k], lambda e: (e["function"], e["site"]), k)
    for r in s["results"]:
        for case in r["cases"]:
            for a in case["cond"]:
                bad += atom_problems(a, f"{r['function']} case")
            if case["backing"][0] not in ("fresh", "of", "none", "unknown"):
                bad.append(f"{r['function']}: backing {case['backing'][:1]}")
    k = g["calls"]
    bad += _sorted_by(k["edges"], lambda e: (e["caller"], e["site"], e["callee"]), "edges")
    bad += _sorted_by(k["flows"], lambda e: (e["producer"], e["caller"], e["site"]), "flows")
    for e in k["edges"]:
        if e["kind"] not in ("call", "go", "defer") or e["callee_kind"] not in ("analyzed", "external", "primitive",
                                                                                "dynamic"):
            bad.append(f"edge {e['caller']} -> {e['callee']}")
    bad += _sorted_by(g["loops"], lambda e: (e["function"], e["span"]), "loops")
    for l in g["loops"]:
        if l["kind"] not in ("counted", "range", "unbounded") or not SPAN_RE.match(l["span"]):
            bad.append(f"loop {l['function']} {l['span']}")
    bad += _sorted_by(g["coverage"]["debt"], lambda e: (e["function"], e["kind"], e["where"]), "debt")
    return bad


# ------------------------------------------------------------------ the independent Go instrument
def run_go_instrument(probe_list: list, words: list) -> dict:
    """Real outcomes from the prereg instrument on a scratch copy of morph bindings + common at the pinned commit."""
    go = check_go_version()
    morph = morph_checkout()
    ws = Path(tempfile.mkdtemp(prefix="holon-i18-go-"))
    try:
        ign = shutil.ignore_patterns(".git", "node_modules", ".env", ".env.*", "bunfig.toml")
        for d in ("bindings", "common"):
            shutil.copytree(morph / d, ws / d, symlinks=True, ignore=ign)
        (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
        shutil.copy(INSTRUMENT, ws / "common" / "batch" / "holon_i18_instrument_test.go")
        (ws / "in.json").write_text(json.dumps({"probes": [list(p) for p in probe_list], "words": words}))
        env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS")}
        env.update({"GOTOOLCHAIN": "local", "HOLON_I18_IN": str(ws / "in.json"), "HOLON_I18_OUT": str(ws / "out.json")})
        p = subprocess.run([go, "test", "./batch", "-run", "^TestHolonI18Instrument$", "-count=1", "-v"],
                           cwd=ws / "common", env=env, capture_output=True, text=True, timeout=1500)
        if p.returncode != 0 or not (ws / "out.json").exists():
            raise AssertionError(f"I18 Go instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        return json.loads((ws / "out.json").read_text())
    finally:
        shutil.rmtree(ws, ignore_errors=True)


# ------------------------------------------------------------------ honesty vocabulary
MORPH_WORDS = re.compile(
    r"\b(BatchHeader\w*|BatchData|TxsPayload\w*|EncodedBytes|RetrieveBlobBytes|MakeBlobCanonical|MakeBlobTxSidecar|"
    r"ParseBatch|BatchInfo|BatchCache|GenesisBatchHeader|blockContexts|txsPayload|kzg4844|BytesToHash|"
    r"Keccak256Hash|CompressMorphDABatch|WrappedBlock|morph|Morph|commitBatch|Rollup|genesis)\b")
MAGIC_NUMBERS = re.compile(r"(?<![\w.])(249|257|3967|3968|4095|4096|126976|131072)(?![\w.])")
SPAN_TEXT = re.compile(r"\w+\.(go|sol):\d+")


def config_vocabulary(cfg: dict) -> set[str]:
    """Every target name the sidecar holds: repo, document stems, import paths, primitive names."""
    words = {cfg["target"]["repo"]}
    for stem, pk in cfg["documents"].items():
        words.add(stem)
        words.update(pk)
    for name in cfg["primitives"]:
        words.add(name)
        words.add(name.rsplit(".", 1)[-1])
    return {w for w in words if len(w) > 5}


def frontend_sources() -> list[Path]:
    return sorted(p for p in FRONTEND.rglob("*") if p.is_file() and p.suffix in (".py", ".go")
                  and "__pycache__" not in p.parts)
