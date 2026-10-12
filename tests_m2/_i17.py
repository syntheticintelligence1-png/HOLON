"""I17 helpers: the instruments fixed at the I17 prereg (BUILD_PLAN §0.1, "instruments are inputs").

Nothing here imports holon/. The contract these helpers read is the docstring of
tests_m2/test_extract_solidity_layout.py. The tests use them to decide what an extracted holon-facts/0.3 document says,
independently of the code that wrote it:

- `Extract(args)` runs `python -m holon extract ...` into a scratch file and keeps what it wrote;
- `ev(expr, env)` evaluates the condition and length DSL (rule J5 of the contract);
- `op_cells`, `path_layout` expand an ok path's ops into the layout algebra's cells (whitepaper §10.2:
  ["field", name, k] | ["const", byte] | ["input", name, k] | ["unknown"]), later writes overriding earlier ones;
- `active_ok_paths`, `layout_at`, `reverts_at` decide, for an encoder edge and one value v of a selector field (the
  version byte of the M0 header), which paths are active, by evaluating the conjuncts that mention only the selector and
  checking that every other conjunct is a single-field comparison with a constant satisfiable inside the field's width;
- `loader_outcome(edge, input, b0, L)` decides the one path of a loader edge that holds for a byte string of length L
  whose first byte is b0;
- `frozen_layout(v)` and `frozen_ok_sol(b)` read the FROZEN M0 facts through the frozen reference interpreter
  (tests/reference/ref_model.py), never through holon;
- `target_vocabulary()` derives, from the pinned checkout and the frozen facts, the names generic frontend code must not
  hold; `opened_during(args)` runs the extract CLI under a Python audit hook and returns every file it opened and every
  process it started;
- `mutated_source(morph)` builds a scratch copy of the pinned contracts with four line-preserving mutations (a store
  offset, a library length constant, the version bound, a store formal's name), for the "the extraction follows the
  code" check of tests_m2/test_extract_solidity_honesty.py;
- `go_envelope_example()` is a placeholder document in the shape I18's contract fixes, for the shared-envelope check.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.reference import ref_model
from tests_m2._m2 import ROOT, load_json, run_holon

FACTS_VERSION = "holon-facts/0.3"
FRONTEND_VERSION = "holon-frontend-solidity/0.1"
SIDECAR_REL = "spec/M2/lib/extract_solidity.json"
SIDECAR = ROOT / SIDECAR_REL
OUTPUT_REL = "spec/M2/facts/morph_header.extracted.json"
OUTPUT = ROOT / OUTPUT_REL
SCHEMA = ROOT / "spec" / "schemas" / "facts_0_3.schema.json"
FROZEN = ROOT / "facts" / "morph_header.json"
FIX = ROOT / "tests_m2" / "fixtures" / "extract_solidity"
TOY = FIX / "toy"
TOY_SIDECAR = TOY / "extract_solidity.json"
TOY_ENV_SIDECAR = TOY / "extract_env.json"
TOY_EXPECTED = TOY / "expected.json"
ROLLUP = "contracts/contracts/l1/rollup/Rollup.sol"
V0 = "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol"
V1 = "contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol"
CODEC_SOURCES = (ROLLUP, V0, V1, "contracts/contracts/l1/rollup/IRollup.sol",
                 "contracts/contracts/l1/rollup/IL1MessageQueue.sol")
WORD = 2 ** 256
SPAN = re.compile(r"^(?P<unit>[^\s:]+):(?P<lo>[1-9][0-9]*)(?:-(?P<hi>[1-9][0-9]*))?$")
CMP = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b,
       "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
ARITH = {"+": lambda a, b: (a + b) % WORD, "-": lambda a, b: (a - b) % WORD, "*": lambda a, b: (a * b) % WORD,
         "/": lambda a, b: a // b if b else 0, "%": lambda a, b: a % b if b else 0,
         "&": lambda a, b: a & b, "|": lambda a, b: a | b, "^": lambda a, b: a ^ b,
         "<<": lambda a, b: (a << b) % WORD if b < 256 else 0, ">>": lambda a, b: a >> b if b < 256 else 0}


# ------------------------------------------------------------------ running the CLI
class Extract:
    """One `python -m holon extract ...` run into a scratch file (--out), and what it wrote."""

    def __init__(self, args: list[str], cwd: Path = ROOT, out: Path | None = None):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-i17-"))
        self.out = out or (self.tmp / "out.extracted.json")
        p = run_holon(["extract", *args, "--out", str(self.out)], cwd=cwd)
        self.code = p.returncode
        self.stdout, self.stderr = p.stdout, p.stderr
        self.log = f"exit {p.returncode}\n--- stdout\n{p.stdout[-3000:]}\n--- stderr\n{p.stderr[-3000:]}"

    def bytes(self) -> bytes:
        if not self.out.exists():
            raise AssertionError(f"holon extract wrote nothing to {self.out}\n{self.log}")
        return self.out.read_bytes()

    def doc(self) -> dict:
        return json.loads(self.bytes())

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


def morph_args() -> list[str]:
    return ["solidity", "--milestone", "M2"]


def toy_args(sidecar: Path = TOY_SIDECAR) -> list[str]:
    return ["solidity", "--sidecar", str(sidecar), "--source", str(TOY)]


# ------------------------------------------------------------------ the DSL (rule J5)
def truth(x) -> bool:
    return bool(x) if isinstance(x, bool) else x != 0


def atoms(e) -> set:
    """Field names (str), ("len", input) and ("byte", input, k) atoms of an expression."""
    if isinstance(e, bool):
        raise AssertionError(f"a boolean literal is not a DSL expression: {e!r}")
    if isinstance(e, int):
        return set()
    if isinstance(e, str):
        return {e}
    if not isinstance(e, list) or not e or not isinstance(e[0], str):
        raise AssertionError(f"not a DSL expression: {e!r}")
    if e[0] == "len":
        return {("len", e[1])}
    if e[0] == "byte":
        return {("byte", e[1], e[2])}
    out = set()
    for a in e[1:]:
        out |= atoms(a)
    return out


def ev(e, env: dict):
    """Value of a DSL expression; env maps field names and ("len", x) / ("byte", x, k) atoms to integers. A missing
    atom raises KeyError."""
    if isinstance(e, bool):
        raise AssertionError(f"a boolean literal is not a DSL expression: {e!r}")
    if isinstance(e, int):
        return e
    if isinstance(e, str):
        return env[e]
    op, *args = e
    if op == "len":
        return env[("len", args[0])]
    if op == "byte":
        return env[("byte", args[0], args[1])]
    if op == "!":
        return not truth(ev(args[0], env))
    if op == "&&":
        return all(truth(ev(a, env)) for a in args)
    if op == "||":
        return any(truth(ev(a, env)) for a in args)
    if op in CMP:
        return CMP[op](ev(args[0], env), ev(args[1], env))
    if op in ARITH:
        return ARITH[op](ev(args[0], env), ev(args[1], env))
    raise AssertionError(f"unknown DSL operator {op!r} in {e!r}")


def holds(cond: list, env: dict) -> bool:
    """A conjunct list, evaluated left to right, stopping at the first false conjunct."""
    for c in cond:
        if not truth(ev(c, env)):
            return False
    return True


# ------------------------------------------------------------------ layouts (whitepaper §10.2)
def item_cells(item: dict, env: dict) -> list[list]:
    if "field" in item:
        return [["field", item["field"], item["from"] + k] for k in range(item["len"])]
    if "zeros" in item:
        return [["const", 0] for _ in range(item["zeros"])]
    if "const" in item:
        if not 0 <= item["const"] <= 255:
            raise AssertionError(f"a const item is one byte: {item}")
        return [["const", item["const"]]]
    if "input" in item:
        n = ev(item["len"], env)
        return [["input", item["input"], item["from"] + k] for k in range(n)]
    raise AssertionError(f"unknown src item {item}")


def op_cells(op: dict, env: dict | None = None) -> list[list]:
    env = env or {}
    cells = [c for it in op["src"] for c in item_cells(it, env)]
    width = ev(op["width"], env)
    if len(cells) != width:
        raise AssertionError(f"op at {op['offset']} has width {width} but its src holds {len(cells)} bytes: {op}")
    want = {"mstore": 32, "mstore8": 1}.get(op["op"])
    if want is not None and width != want:
        raise AssertionError(f"{op['op']} writes {want} bytes, not {width}")
    return cells


def path_layout(path: dict, env: dict | None = None) -> list[list]:
    """The cells of an ok path: an all-unknown buffer (memory_init dirty), the ops applied in order, cut to length."""
    env = env or {}
    length = ev(path["length"], env)
    writes = [(op["offset"], op_cells(op, env)) for op in path["ops"]]
    size = max([length] + [o + len(c) for o, c in writes])
    buf: list[list] = [["unknown"] for _ in range(size)]
    for o, c in writes:
        buf[o:o + len(c)] = [list(x) for x in c]
    return buf[:length]


def expand_runs(runs: list) -> list[list]:
    """[kind, name, from, count] runs (expected.json) -> cells."""
    out = []
    for kind, name, frm, n in runs:
        if kind == "field":
            out += [["field", name, frm + k] for k in range(n)]
        elif kind == "const":
            out += [["const", name] for _ in range(n)]
        elif kind == "unknown":
            out += [["unknown"] for _ in range(n)]
        else:
            raise AssertionError(kind)
    return out


def field_widths(doc: dict, record: str) -> dict[str, int]:
    return {f["name"]: f["width"] for f in doc["types"][record]["fields"]}


def _single_field_satisfiable(c, widths: dict[str, int], selector: str) -> bool:
    """c is ["op", f, k], ["op", k, f] or ["!", one of those], with f a field other than the selector and k an integer;
    True iff some value of f in [0, 2^(8 width)) satisfies it."""
    neg = isinstance(c, list) and c[:1] == ["!"]
    inner = c[1] if neg else c
    if not (isinstance(inner, list) and len(inner) == 3 and inner[0] in CMP):
        raise AssertionError(f"conjunct {c!r} is not a single-field comparison with a constant")
    _, a, b = inner
    f, k = (a, b) if isinstance(a, str) else (b, a)
    if not (isinstance(f, str) and isinstance(k, int) and not isinstance(k, bool)) or f == selector:
        raise AssertionError(f"conjunct {c!r} is not a single-field comparison with a constant")
    hi = 2 ** (8 * widths[f]) - 1
    for v in sorted(x for x in {0, 1, hi - 1, hi, k - 1, k, k + 1} if 0 <= x <= hi):
        r = truth(ev(inner, {f: v}))
        if (not r) if neg else r:
            return True
    return False


def active(path: dict, widths: dict[str, int], selector: str, v: int) -> bool:
    for c in path["cond"]:
        a = atoms(c)
        if a <= {selector}:
            if not truth(ev(c, {selector: v})):
                return False
        elif not _single_field_satisfiable(c, widths, selector):
            return False
    return True


def active_ok_paths(edge: dict, widths: dict[str, int], selector: str, v: int) -> list[dict]:
    return [p for p in edge["paths"] if p["outcome"] == "ok" and active(p, widths, selector, v)]


def reverts_at(edge: dict, selector: str, v: int) -> list[dict]:
    """Revert paths whose every conjunct mentions only the selector and holds at v (they fail for every input with
    that selector value)."""
    out = []
    for p in edge["paths"]:
        if p["outcome"] == "revert" and all(atoms(c) <= {selector} for c in p["cond"]) \
                and holds(p["cond"], {selector: v}):
            out.append(p)
    return out


def layout_at(edge: dict, widths: dict[str, int], selector: str, v: int):
    """None when no ok path is active at v, else the one layout of the active ok paths (several active paths must
    agree, else the layout is not a function of the selector and this fails)."""
    oks = active_ok_paths(edge, widths, selector, v)
    if not oks:
        return None
    lays = [path_layout(p) for p in oks]
    if any(x != lays[0] for x in lays[1:]):
        raise AssertionError(f"{len(oks)} ok paths are active at {selector} = {v} with different layouts")
    return lays[0]


def loader_outcome(edge: dict, inp: str, b0: int, length: int) -> dict:
    env = {("len", inp): length}
    if length > 0:
        env[("byte", inp, 0)] = b0
    hits = [p for p in edge["paths"] if holds(p["cond"], env)]
    if len(hits) != 1:
        raise AssertionError(f"{len(hits)} paths hold for first byte {b0}, length {length}: "
                             + json.dumps([p.get("reason", "ok") for p in hits]))
    return hits[0]


def fields_env(doc_fields: dict, values: dict) -> dict:
    return {k: v for k, v in values.items() if k in doc_fields}


# ------------------------------------------------------------------ the frozen M0 facts (through the frozen oracle)
def frozen() -> dict:
    return load_json(FROZEN)


def frozen_layout(v: int) -> list[list]:
    return [list(c) for c in ref_model.layout(frozen(), "enc_sol", v)]


def frozen_ok_sol(b: bytes) -> bool:
    return ref_model.predicate(frozen(), "ok_sol", b)


def frozen_encodes(header: dict) -> bool:
    """Whether the frozen enc_sol is defined on a header (field -> bytes): False on its DomainError."""
    try:
        ref_model.encode(frozen(), "enc_sol", header)
        return True
    except ref_model.DomainError:
        return False


def m0_witness(law: str) -> dict:
    """The REFUTED M0 witness header of a law, field -> int."""
    rec = load_json(ROOT / "results" / "M0" / f"{law}.json")
    return {k: int(v, 16) for k, v in rec["witness"]["h"].items()}


# ------------------------------------------------------------------ honesty instruments
def morph_vocabulary(morph: Path) -> set[str]:
    """Names the pinned target declares in the codec sources (contracts, libraries, interfaces, structs, functions,
    events, modifiers, typed declarations), plus the frozen header facts' functions and Header fields."""
    names: set[str] = set()
    decl = re.compile(r"\b(?:contract|library|interface|struct|function|event|modifier|error)\s+([A-Za-z_]\w*)")
    typed = re.compile(r"\b(?:u?int\d*|bytes\d*|address|bool|string|[A-Z]\w*)(?:\s*\[\s*\])?"
                       r"(?:\s+(?:calldata|memory|storage|internal|public|private|external|constant|immutable|payable))*"
                       r"\s+(_?[A-Za-z]\w*)\s*[;=,)]")
    for rel in CODEC_SOURCES:
        text = (morph / rel).read_text(encoding="utf-8")
        text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
        names |= set(decl.findall(text)) | set(typed.findall(text))
    f = frozen()
    names |= set(f["functions"]) | {x["name"] for x in f["types"]["Header"]["fields"]}
    return names


def distinctive(name: str) -> bool:
    """A name generic code cannot hold by accident: at least 5 characters after leading underscores, with an
    underscore or an uppercase letter after the first character (batchPtr, BatchHeaderCodecV0, enc_sol)."""
    core = name.lstrip("_")
    return len(core) >= 5 and ("_" in core or any(ch.isupper() for ch in core[1:]))


def target_vocabulary(morph: Path) -> set[str]:
    out = set()
    for n in morph_vocabulary(morph):
        if distinctive(n):
            out |= {n, n.lstrip("_")}
    return {n for n in out if distinctive(n)}


def revert_messages(morph: Path) -> set[str]:
    msgs = set()
    for rel in (ROLLUP, V0, V1):
        msgs |= set(re.findall(r"(?:require\([^;]*?,|revert\()\s*\"([^\"]+)\"", (morph / rel).read_text(encoding="utf-8")))
    return msgs


HOOK = r'''
import json, os, sys
LOG = []
def _hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        LOG.append(["open", os.fsdecode(args[0]), args[1] if isinstance(args[1], str) else str(args[1])])
    elif event == "subprocess.Popen":
        LOG.append(["exec", [os.fsdecode(a) for a in (args[1] if isinstance(args[1], (list, tuple)) else [args[1]])]])
sys.addaudithook(_hook)
code = 1
try:
    from holon.__main__ import main
    code = main(json.loads(os.environ["HOLON_I17_ARGS"]))
finally:
    _out = os.environ["HOLON_I17_LOG"]
    LOG.append(["exit", code])
    with open(_out, "w") as fh:
        fh.write(json.dumps(LOG))
sys.exit(code if isinstance(code, int) else 1)
'''


def opened_during(args: list[str], cwd: Path = ROOT) -> tuple[int, list, list]:
    """Run `holon <args>` in-process under an audit hook (cwd as the import root). Returns (exit code, opened paths
    [(realpath, mode)], started processes [argv])."""
    tmp = Path(tempfile.mkdtemp(prefix="holon-i17-hook-"))
    try:
        log = tmp / "log.json"
        env = dict(os.environ, HOLON_I17_ARGS=json.dumps(args), HOLON_I17_LOG=str(log))
        env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
        p = subprocess.run([sys.executable, "-c", HOOK], cwd=cwd, env=env, capture_output=True, text=True, timeout=1800)
        if not log.exists():
            raise AssertionError(f"the hooked run wrote no log: exit {p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}")
        entries = json.loads(log.read_text())
        code = next((e[1] for e in entries if e[0] == "exit"), p.returncode)

        def real(x: str) -> str:
            return os.path.realpath(x if os.path.isabs(x) else os.path.join(str(cwd), x))
        opened = [(real(e[1]), e[2]) for e in entries if e[0] == "open"]
        opened = [(x, m) for x, m in opened if not x.startswith(os.path.realpath(tmp))]
        execs = [e[1] for e in entries if e[0] == "exec"]
        return code, opened, execs
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def canonical_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode()


# ------------------------------------------------------------------ mutation instrument (a scratch copy of the codec)
# Line-preserving edits of the pinned sources (so every span stays valid), each anchor occurring exactly once:
# a store offset moved, a library length constant changed, the version bound changed, a store formal renamed.
MUTATION_EDITS = (
    (V0, "mstore(add(batchPtr, 57), _blobVersionedHash)", "mstore(add(batchPtr, 58), _blobVersionedHash)"),
    (V0, "uint256 internal constant BATCH_HEADER_LENGTH = 249;", "uint256 internal constant BATCH_HEADER_LENGTH = 250;"),
    (ROLLUP, 'require(batchDataInput.version <= 2, "invalid version");',
     'require(batchDataInput.version <= 3, "invalid version");'),
)
MUTATION_RENAME = (V0, "_withdrawRootHash", "_exitRootHash")   # every occurrence in that file (a whole word)


def mutated_source(morph: Path) -> tuple[Path, Path]:
    """(scratch dir, source root): a copy of <morph>/contracts/contracts (unit names unchanged) with MUTATION_EDITS and
    MUTATION_RENAME applied, and next to it a copy of the frozen sidecar with target.commit null (no checkout check)."""
    tmp = Path(tempfile.mkdtemp(prefix="holon-i17-mut-"))
    src = tmp / "src"
    shutil.copytree(morph / "contracts" / "contracts", src / "contracts" / "contracts", symlinks=False,
                    ignore=shutil.ignore_patterns(".git", "node_modules", ".env", ".env.*", "bunfig.toml"))
    for rel, old, new in MUTATION_EDITS:
        p = src / rel
        text = p.read_text(encoding="utf-8")
        if text.count(old) != 1:
            raise AssertionError(f"{rel}: the mutation anchor {old!r} occurs {text.count(old)} times")
        p.write_text(text.replace(old, new), encoding="utf-8")
    rel, old, new = MUTATION_RENAME
    p = src / rel
    text = p.read_text(encoding="utf-8")
    renamed = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, text)
    if renamed == text:
        raise AssertionError(f"{rel}: {old} does not occur")
    p.write_text(renamed, encoding="utf-8")
    side = load_json(SIDECAR)
    side["target"]["commit"] = None
    (tmp / "extract_solidity.json").write_text(json.dumps(side, indent=2) + "\n", encoding="utf-8")
    return tmp, src


def replace_exact(x, old, new):
    """x with every subtree equal to old replaced by new."""
    if x == old and type(x) is type(old):
        return json.loads(json.dumps(new))
    if isinstance(x, list):
        return [replace_exact(v, old, new) for v in x]
    if isinstance(x, dict):
        return {k: replace_exact(v, old, new) for k, v in x.items()}
    return x


def replace_int(x, old: int, new: int):
    if isinstance(x, bool):
        return x
    if isinstance(x, int):
        return new if x == old else x
    if isinstance(x, list):
        return [replace_int(v, old, new) for v in x]
    return x


def go_envelope_example() -> dict:
    """A minimal document in the shape I18's contract fixes for the Go frontend (tests_m2/test_extract_go.py:
    envelope, extraction provenance, assumptions, and the "go" section with its seven keys), used to check that the
    shared holon-facts/0.3 schema admits it. Its values are placeholders, not facts about any target."""
    z = "0" * 64
    return {"facts_version": FACTS_VERSION,
            "target": {"repo": "example/repo", "commit": "0123456789abcdef0123456789abcdef01234567",
                       "scope": "go packages: example/repo/pkg"},
            "extraction": {"method": "extracted", "frontend": "go", "frontend_version": "holon-go/0.1",
                           "tool": {"go": "go1.24.7", "x_tools": "v0.36.0", "ssadump_sha256": z},
                           "config": {"path": "spec/M2/lib/go_frontend.json", "sha256": z},
                           "inputs": [{"path": "pkg/a.go", "sha256": z}]},
            "assumptions": [{"id": "go-append-growth", "text": "placeholder"}],
            "go": {"packages": [{"path": "example/repo/pkg", "dir": "pkg", "files": ["pkg/a.go"]}],
                   "functions": {}, "codecs": {}, "slices": {}, "calls": {}, "loops": [], "coverage": {}}}
