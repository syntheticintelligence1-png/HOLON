"""holon.mutate.replay: the replay harness of I61 (instrument replay; the contract docstring's holon.mutate.replay).

A source tree's own code, run by claim at exact field values, never by law id:

  call(tree, role, arg)          one M0 role on the tree's code: {"kind": "value" | "revert" | "panic", "value",
                                 "detail", "revert_line"}
  claim(tree, law, env)          a laws/M0 statement's claim at one assignment: True, False, or None (no execution)
  trace_claim(tree, law, trace)  a trace law's claim on one witness trace: False iff a step panics at the law's site
  Harness(tree)                  the batch form behind all three: each Foundry project and the Go test binary are built
                                 once per tree, the Go binary is started once and served batches

`tree` is a source tree laid out as the checkout (the Foundry directory and the go.work modules, as
holon.mutate.common.copy_tree builds one); `sol_deps` the OpenZeppelin node_modules directory (default the config's).

The harness's shape comes from the null mutant's documents only (the committed spec/M2/facts) and from I16's binding
(replay/M2/implementations.json); everything target-facing comes, at run time, from the tree's own sources, the
documents and the harness sources under replay/M2/mutation_i61/. This module names nothing of the target.

enc_sol (instrument replay.m0). The null document's encoder edge gives the entry function, the revert paths' lines,
each store op's call line and field map, and the sink's call line. The generated Foundry harness copies from the tree's
text, in order: (i) each revert path's require whose own condition (past the conditions of the paths before it) reads
the version field alone; (ii) the statements of the innermost block of the entry function that holds every store call
and the sink's call, from its first statement up to the statement holding the sink, each store call whose op maps a
Header field given that field's witness value at the Header field's width (I16's abi; the value argument is the one the
store's own assembly writes), a store call writing zeros keeping the tree's text, and a local the copied statements use
but that is declared before the block declared with its declared type; (iii) in place of the statement holding the sink,
the return of the bytes it hashes (its length argument from its pointer argument, as I16's harness copies them). Every
occurrence of the version expression (the value argument of the version's store call) is read as the witness's version.
A marker precedes each copied statement: a revert is mapped back to the copied statement that reverted, and so to its
line in the tree's text (revert_line, when that statement is a require or a revert; a revert raised inside another
statement has none). A Panic 0x01-0x51 of enc_sol is kind "panic". ok_sol runs the tree's loader (the load_sol edge's
entry) through a subclass: true when it returns, false on any revert, a Panic included (its meaning gives every revert
that value); a loader revert's line is the line of the one require or revert in the loader's walk whose message the
revert carries. Each call runs in a fresh external call frame.

Go roles: a Go test built in the tree's own package and workspace makes I16's harness's calls with a recover per call.

Claims (instrument replay.semantics): the statement's IR is evaluated bottom-up in rounds (every call a round needs,
then each role's batch once); `view` is the specification, evaluated by the compiled frozen facts (holon.model_eval).
A panic in any role call (a Go panic, or a Solidity Panic in enc_sol, whose meaning gives a revert no value) falsifies
the claim; otherwise a role call with no value (an enc_sol revert), at the top level or nested, makes the assignment no
execution (None); otherwise the sides are compared as the M0 model compares them (canonical JSON of bytes, Maybe and
lists).

Trace laws (instrument replay.semantics): the trace runs on the tree's Rollup through holon.mreplay's M1 trace harness
(a reverted step is a no-op); each step that panics is replayed as the last step under the Foundry debugger and located
by holon.mreplay.locate_panic (the I15 M2 replay's panic_site); the claim is False iff some located site lies in the
law's basis span.

    python -m holon mutate replay --i16 [--tree DIR] [--work DIR]

runs every role of I16's binding on I16's per-edge corpus (holon.corpus, built as holon/refinement.py builds it) and
prints {edge: {"compared": n, "outputs_sha256": hex}}, the outputs digested as I16's records digest the real side.
"""
from __future__ import annotations

import argparse
import bisect
import functools
import json
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import common as C

SOL_TEMPLATE = C.HARNESS / "HolonMutateReplay.t.sol.tmpl"
SOL_TEST = Path("test") / "HolonMutateReplay.t.sol"
SOL_CONTRACT = "HolonMutateReplayTest"
SOL_MARKS = ("IMPORTS", "STRUCT", "ENC", "LOAD")
SOL_IN, SOL_OUT = "holon_i61_in.txt", "holon_i61_out.txt"
GO_HARNESS = C.HARNESS / "holon_mutate_replay_test.go"
GO_TEST = "TestHolonMutateReplay"
GO_BINARY = "holon_i61.test"
GO_PREFIX = "HOLON-I61 "
# I62: the M1 trace harness's copy with a deployment probe per trace (a trace whose deployment reverts logs every step as
# "rev deploy: <reason>": no step runs, so none panics), beside the I15 last-step harness, which imports it
TRACE_HARNESSES = (Path("replay/M2/mutation_i62/HolonTraceReplay.t.sol"), Path("replay/M2/solidity/HolonLastStep.t.sol"))
TRACE_CONTRACT = "HolonTraceReplay"
SIDECAR = Path("spec/M2/lib/extract_solidity.json")   # the Solidity frontend's frozen compiler version and settings
BINDING = Path("replay/M2/implementations.json")
M1_REGISTRY = Path("laws/M1/REGISTRY.json")
M0_LAWS = Path("laws/M0")
VERSION = "version"          # the holon-facts version byte: the Header field the facts' version conditions read
SPEC = "view"                # the specification function of the M0 statements
WITNESS = "holonH"            # the generated holonEnc's witness parameter
ENC, LOAD = 1, 2             # the Solidity harness's item ops
ERROR_SELECTOR = bytes.fromhex("08c379a0")
PANIC_SELECTOR = bytes.fromhex("4e487b71")
PANIC_LO, PANIC_HI = 0x01, 0x51
GAS_LIMIT = (1 << 63) - 1
GO_TIMEOUT_S = 1800
FORGE_TIMEOUT_S = 7200
WIDTH_TYPES = {1: "uint8", 8: "uint64", 32: "bytes32"}   # instrument replay.m0: the Header widths' Solidity types
BLOCKS = ("Block", "UncheckedBlock")
LOOPS = ("ForStatement", "WhileStatement", "DoWhileStatement")
SIMPLE_STATEMENTS = ("ExpressionStatement", "VariableDeclarationStatement", "Return", "EmitStatement",
                     "RevertStatement", "Break", "Continue", "PlaceholderStatement", "Throw")
EXPRESSIONS = ("Identifier", "MemberAccess", "IndexAccess", "IndexRangeAccess", "FunctionCall", "TupleExpression",
               "UnaryOperation", "BinaryOperation", "Conditional", "Literal", "ElementaryTypeNameExpression",
               "FunctionCallOptions", "NewExpression")


# ---------------------------------------------------------------------------------------------- inputs
def _root() -> Path:
    return C.ROOT


@functools.lru_cache(maxsize=None)
def _json(rel: str):
    return C.load_json(_root() / rel)


def binding() -> dict:
    """I16's binding (replay/M2/implementations.json)."""
    return _json(BINDING.as_posix())


def facts() -> dict:
    """The frozen facts I16's binding names (the Header type, the specification, the getters' order)."""
    return _json(binding()["facts"])


def roles() -> dict:
    """role -> its language ("solidity" | "go"), from the instrument's roles."""
    inst = C.instrument(_root())
    out = {r: lang for lang in ("solidity", "go") for r in inst["roles"][lang]}
    missing = sorted(set(out) - set(binding()["edges"]))
    if missing:
        raise C.MutateError(f"{BINDING.as_posix()} binds no implementation for the roles {missing}")
    return out


def _role_doc(role: str) -> tuple[dict, dict]:
    """(the null document's edge entry, the instrument's role entry) of a Solidity role."""
    r = C.instrument(_root())["roles"]["solidity"][role]
    doc = _json(r["document"])
    if r["edge"] not in doc["functions"]:
        raise C.MutateError(f"{r['document']} has no edge {r['edge']}")
    return doc["functions"][r["edge"]], r


def _span(s: str) -> tuple[str, int, int]:
    """'<unit>:<lo>[-<hi>]' -> (unit, lo, hi)."""
    unit, _, lines = s.rpartition(":")
    lo, _, hi = lines.partition("-")
    if not unit or not lo.isdigit() or (hi and not hi.isdigit()):
        raise C.MutateError(f"not a source span: {s!r}")
    return unit, int(lo), int(hi or lo)


def _canon(x) -> str:
    return C.compact(x)


@functools.lru_cache(maxsize=None)
def _toolchain() -> dict:
    """forge, solc and go, checked against the config's pins (replay.*_sha256, replay.go_version)."""
    rep = C.config(_root())["replay"]
    out = {}
    for k in ("forge", "solc"):
        p = rep.get(k)
        if not p or not Path(p).is_file():
            raise C.MutateError(f"{k} missing: the config's replay {k} is {p!r}")
        if C.sha256_file(p) != rep.get(f"{k}_sha256"):
            raise C.MutateError(f"{p}: its sha256 is not the config's replay {k}_sha256")
        out[k] = str(p)
    go = shutil.which("go") or "/usr/local/go/bin/go"
    v = subprocess.run([go, "version"], capture_output=True, text=True, env=_go_env(None)).stdout.strip()
    if v != rep.get("go_version"):
        raise C.MutateError(f"{go}: `go version` is {v!r}, the pin config replay.go_version is {rep.get('go_version')!r}")
    out["go"] = go
    return out


def _go_env(ws: Path | None) -> dict:
    e = C.env_tools()
    e.update(GOTOOLCHAIN="local", GOFLAGS="-mod=readonly", GOPROXY="off")
    if ws is not None:
        e["GOWORK"] = str(ws / "go.work")
    return e


def _run(cmd: list, cwd: Path, env: dict | None = None, timeout: int = FORGE_TIMEOUT_S) -> tuple[int, str]:
    e = C.env_tools()
    e.update(env or {})
    try:
        p = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as x:
        raise C.MutateError(f"{Path(cmd[0]).name} timed out after {timeout} s in {cwd.name}") from x
    return p.returncode, p.stdout + p.stderr


# ---------------------------------------------------------------------------------------------- Solidity source
def _walk(n):
    if isinstance(n, dict):
        yield n
        for v in n.values():
            yield from _walk(v)
    elif isinstance(n, list):
        for v in n:
            yield from _walk(v)


class Source:
    """The tree's Solidity units as the pinned solc reads them: the compact AST after analysis (no bytecode), with the
    frontend's own compiler run (holon.frontends.solidity.compile) and the frozen sidecar's compiler settings."""

    def __init__(self, tree: Path, units: list, sol_deps: Path):
        from ..frontends.solidity.compile import compile_sources
        sol_deps = Path(sol_deps)
        if sol_deps.name != "node_modules":
            raise C.MutateError(f"sol_deps must be a node_modules directory, not {sol_deps}")
        cfg = json.loads(json.dumps(C.config(_root())))
        cfg["replay"]["sol_deps"] = str(sol_deps.parent)
        side = {"compiler": _json(SIDECAR.as_posix())["compiler"], "target": {"commit": None},
                "sources": sorted(set(units))}
        try:
            compiled = compile_sources(cfg, side, Path(tree))
        except Exception as e:   # the frontend's Refused and ExtractionError
            raise C.MutateError(f"solc on {sorted(set(units))}: {e}") from e
        self.tree = Path(tree)
        self.asts, self.data, self.file_ids = compiled.asts, compiled.units, compiled.file_ids
        self.tree_units = sorted(u for u in self.data if (self.tree / u).is_file())
        self.nodes = {n["id"]: n for ast in self.asts.values() for n in _walk(ast) if isinstance(n.get("id"), int)}
        self._nl = {u: [i for i, b in enumerate(d) if b == 10] for u, d in self.data.items()}

    def pos(self, n: dict) -> tuple[str, int, int]:
        s, length, f = (int(x) for x in n["src"].split(":"))
        return self.file_ids[f], s, s + length

    def line(self, unit: str, off: int) -> int:
        return bisect.bisect_left(self._nl[unit], off) + 1

    def lines(self, n: dict) -> tuple[str, int, int]:
        u, s, e = self.pos(n)
        return u, self.line(u, s), self.line(u, max(s, e - 1))

    def text(self, n: dict) -> str:
        u, s, e = self.pos(n)
        return self.data[u][s:e].decode()

    def function(self, qual: str) -> dict:
        """The FunctionDefinition 'Contract.function' (exactly one)."""
        contract, _, name = qual.partition(".")
        found = [f for ast in self.asts.values() for c in ast.get("nodes", [])
                 if c.get("nodeType") == "ContractDefinition" and c.get("name") == contract
                 for f in c.get("nodes", []) if f.get("nodeType") == "FunctionDefinition" and f.get("name") == name]
        if len(found) != 1:
            raise C.MutateError(f"{qual}: {len(found)} definitions in the tree's units")
        return found[0]

    def callee(self, call: dict) -> dict | None:
        d = self.nodes.get((call.get("expression") or {}).get("referencedDeclaration"))
        return d if d is not None and d.get("nodeType") == "FunctionDefinition" else None

    def qualname(self, fn: dict) -> str:
        sc = self.nodes.get(fn.get("scope"))
        return f"{sc['name']}.{fn['name']}" if sc is not None else fn["name"]

    def statement_end(self, st: dict) -> int:
        """The end offset of a statement, its ';' included for a simple statement."""
        u, _, e = self.pos(st)
        if st["nodeType"] not in SIMPLE_STATEMENTS:
            return e
        d, i = self.data[u], e
        while i < len(d):
            if d[i:i + 1].isspace():
                i += 1
            elif d[i:i + 2] == b"//":
                i = d.index(b"\n", i) if b"\n" in d[i:] else len(d)
            elif d[i:i + 2] == b"/*":
                i = d.index(b"*/", i) + 2
            elif d[i:i + 1] == b";":
                return i + 1
            else:
                break
        raise C.MutateError(f"{u}:{self.line(u, e)}: no ';' ends the statement")


def _builtin_call(n: dict, name: str) -> bool:
    e = n.get("expression") or {}
    return (n.get("nodeType") == "FunctionCall" and e.get("nodeType") == "Identifier" and e.get("name") == name
            and isinstance(e.get("referencedDeclaration"), int) and e["referencedDeclaration"] < 0)


def _string_literal(n: dict) -> str | None:
    if n.get("nodeType") == "Literal" and n.get("kind") == "string" and isinstance(n.get("value"), str):
        return n["value"]
    return None


def _yul_param(src: Source, fn: dict, line_span: str, builtin: str, arg: int) -> list[int]:
    """The parameter indexes of `fn` that argument `arg` of the Yul builtin call `builtin` at line_span reads."""
    unit, lo, hi = _span(line_span)
    params = [p["id"] for p in fn["parameters"]["parameters"]]
    hits = []
    for asm in (n for n in _walk(fn.get("body")) if n.get("nodeType") == "InlineAssembly"):
        refs = {r["src"]: r["declaration"] for r in asm.get("externalReferences", [])}
        for y in _walk(asm.get("AST")):
            if y.get("nodeType") != "YulFunctionCall" or (y.get("functionName") or {}).get("name") != builtin:
                continue
            if src.lines(y) != (unit, lo, hi):
                continue
            if arg >= len(y.get("arguments", [])):
                continue
            used = {params.index(refs[i["src"]]) for i in _walk(y["arguments"][arg])
                    if i.get("nodeType") == "YulIdentifier" and refs.get(i.get("src")) in params}
            hits.append(sorted(used))
    if len(hits) != 1:
        raise C.MutateError(f"{src.qualname(fn)}: {len(hits)} `{builtin}` calls at {line_span}")
    return hits[0]


# ---------------------------------------------------------------------------------------------- enc_sol: the generator
@dataclass
class EncPlan:
    """The generated enc_sol harness of one tree."""
    function: str                      # holonEnc, the Solidity text that fills HOLON-ENC
    struct: str                        # HolonHeader and HOLON_MARKERS, the text that fills HOLON-STRUCT
    imports: str                       # the entry unit's import directives rebased to test/ (HOLON-IMPORTS)
    fields: list                       # [(Header field, Solidity type)] of HolonHeader, in order
    markers: list                      # marker k (1-based) -> "<unit>:<line>" of the copied statement it precedes,
                                       # None for the harness's own return of the hashed bytes
    checks: set = field(default_factory=set)     # the markers whose statement is a require or a revert
    copied: list = field(default_factory=list)   # ["<unit>:<line>"] of every copied top-level statement


def _own_conditions(paths: list, k: int) -> list:
    """The conditions of revert path k past the conditions of the paths before it."""
    seen = [_canon(c) for p in paths[:k] for c in p.get("cond", [])]

    def neg(c):
        return c[1] if isinstance(c, list) and len(c) == 2 and c[0] == "!" else ["!", c]
    return [c for c in paths[k].get("cond", []) if _canon(c) not in seen and _canon(neg(c)) not in seen]


def _reads(cond, names: set) -> set:
    """The variables a path condition reads ("other" for one that is not a Header field)."""
    out = set()
    if isinstance(cond, list):
        for x in cond[1:]:
            if isinstance(x, str):
                out.add(x if x in names else "other")
            else:
                out |= _reads(x, names)
    return out


def _store_ops(fdoc: dict) -> list:
    """The store ops of the edge's ok paths, one per call: (call span, callee, callee line, op, field or None)."""
    ops = {}
    for p in fdoc["paths"]:
        if p.get("outcome") != "ok":
            continue
        for op in p.get("ops", []):
            st = op["origin"]["stack"]
            if len(st) != 2:
                raise C.MutateError(f"store op at {op['origin']['src']}: call stack {st} is not entry -> store")
            fields = [it for it in op["src"] if "field" in it]
            if len(fields) > 1:
                raise C.MutateError(f"store op at {st[0]} maps {len(fields)} Header fields")
            item = (st[0], op["origin"]["fn"], st[1], op["op"], _canon(fields[0]) if fields else None)
            prev = ops.setdefault((st[0], op["origin"]["fn"]), item)
            if prev != item:
                raise C.MutateError(f"store call at {st[0]}: the ok paths give it different ops")
    return [(s, fn, line, op, json.loads(f) if f else None) for s, fn, line, op, f in sorted(ops.values())]


def _call_at(src: Source, calls: list, span: str, qual: str) -> dict:
    unit, lo, hi = _span(span)
    found = [c for c in calls if src.lines(c) == (unit, lo, hi) and src.callee(c) is not None
             and src.qualname(src.callee(c)) == qual]
    if len(found) != 1:
        raise C.MutateError(f"{len(found)} calls of {qual} at {span} in the tree's text")
    return found[0]


def enc_plan(src: Source) -> EncPlan:
    """The enc_sol harness of a tree (instrument replay.m0), generated from the tree's own text with the shape of the
    null mutant's document."""
    fdoc, _ = _role_doc("enc_sol")
    hdr = {f["name"]: f["width"] for f in facts()["types"]["Header"]["fields"]}
    abi = dict(binding()["edges"]["enc_sol"]["abi"])
    entry_unit = _span(fdoc["entry"]["src"])[0]
    fn = src.function(fdoc["entry"]["fn"])
    if src.pos(fn)[0] != entry_unit:
        raise C.MutateError(f"{fdoc['entry']['fn']} is not in {entry_unit}")
    body = fn["body"]
    calls = [n for n in _walk(body) if n.get("nodeType") == "FunctionCall"]
    edits = []       # (start, end, order, text) in the entry unit; order: 0 close brace, 1 open brace, 2 marker, 3 text

    # the store calls and their value arguments
    stores, bound = [], {}
    for span, qual, line, op, fld in _store_ops(fdoc):
        call = _call_at(src, calls, span, qual)
        arg = None
        if fld is not None:
            name = fld["field"]
            if name not in hdr or fld.get("from", 0) != 0 or fld.get("len", hdr[name]) != hdr[name]:
                raise C.MutateError(f"store call at {span} maps a slice of {name}, not the whole field")
            idx = _yul_param(src, src.callee(call), line, op, 1)
            if len(idx) != 1 or idx[0] >= len(call["arguments"]):
                raise C.MutateError(f"store call at {span}: its stored value reads parameters {idx}")
            arg = call["arguments"][idx[0]]
            bound[name] = arg
        stores.append((call, arg, fld["field"] if fld else None))
    if VERSION not in bound:
        raise C.MutateError("no store op maps the Header's version field")
    version_text = re.sub(r"\s+", "", src.text(bound[VERSION]))

    # the sink: its call and the bytes it hashes
    sink = fdoc["sink"]
    if len(sink["stack"]) != 2:
        raise C.MutateError(f"sink call stack {sink['stack']} is not entry -> hash")
    s_unit, s_line, _ = _span(sink["stack"][1])
    sinks = [c for c in calls if src.lines(c) == _span(sink["stack"][0]) and src.callee(c) is not None
             and src.lines(src.callee(c))[0] == s_unit
             and src.lines(src.callee(c))[1] <= s_line <= src.lines(src.callee(c))[2]]
    if len(sinks) != 1:
        raise C.MutateError(f"{len(sinks)} sink calls at {sink['stack'][0]} in the tree's text")
    sink_call = sinks[0]
    ptr_i = _yul_param(src, src.callee(sink_call), sink["stack"][1], sink["op"], 0)
    len_i = _yul_param(src, src.callee(sink_call), sink["stack"][1], sink["op"], 1)
    if len(ptr_i) != 1 or len(len_i) != 1:
        raise C.MutateError(f"the sink at {sink['stack'][1]} hashes parameters {ptr_i}, {len_i}")
    sink_params = src.callee(sink_call)["parameters"]["parameters"]
    ptr_arg, len_arg = sink_call["arguments"][ptr_i[0]], sink_call["arguments"][len_i[0]]
    ptr_type, len_type = (sink_params[ptr_i[0]]["typeDescriptions"]["typeString"],
                          sink_params[len_i[0]]["typeDescriptions"]["typeString"])
    if (ptr_type, len_type) != ("uint256", "uint256"):
        raise C.MutateError(f"the sink's pointer and length are {ptr_type}, {len_type}")

    # the innermost block holding every store call and the sink's call; the statements up to the sink's
    held = [c for c, _, _ in stores] + [sink_call]

    def holds(n, m):
        a, b = src.pos(n), src.pos(m)
        return a[0] == b[0] and a[1] <= b[1] and b[2] <= a[2]
    blocks = [b for b in _walk(body) if b.get("nodeType") in BLOCKS and all(holds(b, c) for c in held)]
    if not blocks:
        raise C.MutateError("no block of the entry function holds every store call and the sink")
    block = min(blocks, key=lambda b: src.pos(b)[2] - src.pos(b)[1])
    stmts = block["statements"]
    j = next((i for i, st in enumerate(stmts) if holds(st, sink_call)), None)
    if not j:
        raise C.MutateError("the statement holding the sink is the block's first, or none")
    copied = stmts[:j]
    for call, arg, name in stores:
        if name is not None and not any(holds(st, call) for st in copied):
            raise C.MutateError(f"the store call of {name} is not among the statements before the sink")
    b_unit, b_start, _ = src.pos(block)
    if b_unit != entry_unit:
        raise C.MutateError("the build block is not in the entry unit")

    # (i) the version-only requires
    names = set(hdr)
    requires = []
    for k, p in enumerate(fdoc["paths"]):
        if p.get("outcome") != "revert":
            continue
        own = _own_conditions(fdoc["paths"], k)
        if not own or set().union(*(_reads(c, names) for c in own)) != {VERSION}:
            continue
        unit, lo, hi = _span(p["src"])
        found = [n for n in _walk(body) if n.get("nodeType") == "ExpressionStatement"
                 and _builtin_call(n.get("expression") or {}, "require") and src.lines(n) == (unit, lo, hi)]
        if len(found) != 1:
            raise C.MutateError(f"{len(found)} requires at the revert path {p['src']} in the tree's text")
        if src.pos(found[0])[2] > b_start:
            raise C.MutateError(f"the require at {p['src']} is not before the build block")
        requires.append(found[0])

    # replacements: the store values and every occurrence of the version expression
    ranges = [(src.pos(r)[1], src.statement_end(r)) for r in requires]
    ranges.append((src.pos(copied[0])[1], src.pos(stmts[j])[1]))
    ranges += [(src.pos(ptr_arg)[1], src.pos(ptr_arg)[2]), (src.pos(len_arg)[1], src.pos(len_arg)[2])]

    def inside(n):
        u, s, e = src.pos(n)
        return u == entry_unit and any(a <= s and e <= b for a, b in ranges)
    repl = [(src.pos(arg)[1], src.pos(arg)[2], f"{WITNESS}.{name}") for _, arg, name in stores if arg is not None]
    roots = list(requires) + list(copied) + [ptr_arg, len_arg]
    for r in roots:
        for n in _walk(r):
            if n.get("nodeType") in EXPRESSIONS and inside(n) and re.sub(r"\s+", "", src.text(n)) == version_text:
                repl.append((src.pos(n)[1], src.pos(n)[2], f"{WITNESS}.{VERSION}"))
    kept = []
    for s, e, t in sorted(set(repl), key=lambda x: (x[0], -x[1])):
        if kept and s < kept[-1][1]:
            if e <= kept[-1][1]:
                continue
            raise C.MutateError("overlapping replacements in the copied statements")
        kept.append((s, e, t))
    edits += [(s, e, 3, t) for s, e, t in kept]

    # the markers: one before each copied statement, in text order
    markers, checks = [], set()

    def mark(st):
        u, a, _ = src.lines(st)
        markers.append(f"{u}:{a}")
        e = st.get("expression") or {}
        if st.get("nodeType") == "RevertStatement" or (st.get("nodeType") == "ExpressionStatement" and (
                _builtin_call(e, "require") or _builtin_call(e, "revert"))):
            checks.add(len(markers))
        edits.append((src.pos(st)[1], src.pos(st)[1], 2, f'if (holonStop == {len(markers)}) return ""; '))

    def visit_list(sts):
        for st in sts:
            mark(st)
            visit(st)

    def visit_body(st):
        if st.get("nodeType") in BLOCKS:
            visit_list(st["statements"])
            return
        edits.append((src.pos(st)[1], src.pos(st)[1], 1, "{ "))
        edits.append((src.statement_end(st), src.statement_end(st), 0, " }"))
        mark(st)
        visit(st)

    def visit(st):
        t = st.get("nodeType")
        if t in LOOPS:
            raise C.MutateError(f"a loop at {src.lines(st)[0]}:{src.lines(st)[1]}: the markers map no revert in it")
        if t in BLOCKS:
            visit_list(st["statements"])
        elif t == "IfStatement":
            visit_body(st["trueBody"])
            if st.get("falseBody"):
                visit_body(st["falseBody"])
        elif t == "TryStatement":
            for cl in st.get("clauses", []):
                visit_list(cl["block"]["statements"])
    visit_list(requires)
    visit_list(copied)

    # locals the copied statements use, declared before the block
    def replaced(s, e):
        return any(a <= s and e <= b for a, b, _ in kept)
    used = set()
    for r in roots:
        for n in _walk(r):
            if n.get("nodeType") == "Identifier" and not replaced(*src.pos(n)[1:]):
                used.add(n.get("referencedDeclaration"))
            if n.get("nodeType") == "InlineAssembly":
                used |= {x["declaration"] for x in n.get("externalReferences", [])}
    f_unit, f_start, f_end = src.pos(fn)
    params = {p["id"] for p in fn["parameters"]["parameters"]}
    decls = []
    for d in sorted((src.nodes[i] for i in used if i in src.nodes), key=lambda d: src.pos(d)[1]):
        u, s, e = src.pos(d)
        if d.get("nodeType") != "VariableDeclaration" or d.get("stateVariable") or u != f_unit:
            continue
        if not (f_start <= s and e <= b_start):
            continue
        if d["id"] in params:
            raise C.MutateError(f"the copied statements read the entry's parameter {d['name']} beyond the version "
                                "expression and the store values")
        loc = d.get("storageLocation", "default")
        if loc not in ("default", "memory"):
            raise C.MutateError(f"the local {d['name']} is a {loc} reference: it cannot be declared unassigned")
        decls.append(f"{src.text(d['typeName'])}{' memory' if loc == 'memory' else ''} {d['name']};")

    def render(a: int, b: int) -> str:
        data, out, pos = src.data[entry_unit], [], a
        mine = [x for x in edits if a <= x[0] and x[1] <= b and (x[0] < b or x[2] == 0)]
        for s, e, _, t in sorted(mine, key=lambda x: (x[0], x[2])):
            if s < pos:
                raise C.MutateError("overlapping edits in the copied statements")
            out += [data[pos:s].decode(), t]
            pos = e
        return "".join(out) + data[pos:b].decode()

    body_text = ["        " + d for d in decls]
    body_text += ["        " + render(src.pos(r)[1], src.statement_end(r)) for r in requires]
    body_text.append("        " + render(src.pos(copied[0])[1], src.pos(stmts[j])[1]).rstrip())
    markers.append(None)
    k_end = len(markers)
    body_text += [
        f'        if (holonStop == {k_end}) return "";',
        f"        uint256 holonPtr = {render(src.pos(ptr_arg)[1], src.pos(ptr_arg)[2])};",
        f"        uint256 holonLen = {render(src.pos(len_arg)[1], src.pos(len_arg)[2])};",
        "        bytes memory holonOut = new bytes(holonLen);",
        "        assembly {",
        "            for {",
        "                let holonI := 0",
        "            } lt(holonI, holonLen) {",
        "                holonI := add(holonI, 32)",
        "            } {",
        "                mstore(add(add(holonOut, 32), holonI), mload(add(holonPtr, holonI)))",
        "            }",
        "        }",
        "        return holonOut;"]
    function = ("    /// enc_sol, generated from the tree's own text (instrument replay.m0); holonStop k > 0 returns at the k-th\n"
                "    /// marker, which precedes the k-th copied statement\n"
                f"    function holonEnc(HolonHeader calldata {WITNESS}, uint256 holonStop) external returns (bytes memory) {{\n"
                + "\n".join(body_text) + "\n    }")

    # HolonHeader: the fields the store ops map, at the Header widths (I16's abi)
    fields = []
    for f in facts()["types"]["Header"]["fields"]:
        if f["name"] in bound:
            t = WIDTH_TYPES.get(f["width"])
            if t is None or abi.get(f["name"], t) != t:
                raise C.MutateError(f"Header field {f['name']} of width {f['width']}: no Solidity type agrees with "
                                    f"I16's abi ({abi.get(f['name'])})")
            fields.append((f["name"], t))
    struct = ("/// The witness values the store calls take, at the Header widths (I16's abi).\nstruct HolonHeader {\n"
              + "".join(f"    {t} {n};\n" for n, t in fields) + "}\n\n"
              + f"uint256 constant HOLON_MARKERS = {len(markers)};")

    # the entry unit's import directives, rebased to test/
    from ..mreplay import FOUNDRY_DIR
    imports = []
    for n in src.asts[entry_unit].get("nodes", []):
        if n.get("nodeType") != "ImportDirective":
            continue
        text, path = src.text(n), n["absolutePath"]
        if path in src.tree_units:
            if not path.startswith(FOUNDRY_DIR + "/"):
                raise C.MutateError(f"{path} is outside the Foundry directory")
            new = "../" + path[len(FOUNDRY_DIR) + 1:]
            for q in ('"', "'"):
                if q + n["file"] + q in text:
                    text = text.replace(q + n["file"] + q, q + new + q, 1)
                    break
            else:
                raise C.MutateError(f"cannot rebase the import of {path}")
        imports.append(text)
    copied_at = [f"{src.lines(r)[0]}:{src.lines(r)[1]}" for r in list(requires) + list(copied)]
    return EncPlan(function, struct, "\n".join(imports), fields, markers, checks, copied_at)


def load_messages(src: Source) -> dict:
    """message -> ["<unit>:<line>"] of every require and revert with a string message in the loader's walk (the
    null document's load_sol walk functions)."""
    fdoc, _ = _role_doc("ok_sol")
    out = {}
    for qual in fdoc["walk"]["functions"]:
        fn = src.function(qual)
        for n in _walk(fn.get("body")):
            msg = None
            if _builtin_call(n, "require") and len(n.get("arguments", [])) >= 2:
                msg = _string_literal(n["arguments"][1])
            elif _builtin_call(n, "revert") and len(n.get("arguments", [])) == 1:
                msg = _string_literal(n["arguments"][0])
            if msg is not None:
                u, lo, _ = src.lines(n)
                out.setdefault(msg, set()).add(f"{u}:{lo}")
    return {m: sorted(v) for m, v in out.items()}


def sol_source(src: Source, plan: EncPlan) -> str:
    """The harness of one tree: the template with its four marks filled."""
    fdoc, r = _role_doc("ok_sol")
    contract, _, loader = r["entry"].partition(".")
    src.function(r["entry"])
    t = SOL_TEMPLATE.read_text()
    if f" is {contract} {{" not in t:
        raise C.MutateError(f"{SOL_TEMPLATE.name} does not subclass {contract}, the loader's contract")
    fill = {"IMPORTS": plan.imports, "STRUCT": plan.struct, "ENC": plan.function,
            "LOAD": f"        {loader}(holonB);"}
    lines = t.split("\n")
    for m in SOL_MARKS:
        at = [i for i, x in enumerate(lines) if x.strip() == f"// HOLON-{m}"]
        if len(at) != 1:
            raise C.MutateError(f"{SOL_TEMPLATE.name}: the mark HOLON-{m} occurs {len(at)} times")
        lines[at[0]] = fill[m]
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------- revert data
def revert_reason(data: bytes) -> tuple[str, str]:
    """("panic" | "revert", detail) of a revert's data: Panic(uint256) with a code in 0x01..0x51 is a panic."""
    if len(data) == 36 and data[:4] == PANIC_SELECTOR:
        code = int.from_bytes(data[4:], "big")
        return ("panic" if PANIC_LO <= code <= PANIC_HI else "revert"), f"Panic(0x{code:02x})"
    if data[:4] == ERROR_SELECTOR and len(data) >= 68:
        off = int.from_bytes(data[4:36], "big")
        if off + 32 <= len(data) - 4:
            n = int.from_bytes(data[4 + off:36 + off], "big")
            msg = data[36 + off:36 + off + n]
            if len(msg) == n:
                return "revert", msg.decode("utf-8", "replace")
    return "revert", "0x" + data.hex() if data else "no revert data"


# ---------------------------------------------------------------------------------------------- the Go server
class _GoServer:
    """The tree's Go test binary, started once (-test.timeout=0) and served one request per line."""

    def __init__(self, binary: Path, cwd: Path, env: dict, log: Path):
        self.args, self.cwd, self.env, self.log = [str(binary), "-test.run", f"^{GO_TEST}$", "-test.count=1",
                                                   "-test.timeout=0"], cwd, env, log
        self.proc, self.q, self.n, self.pump = None, None, 0, None

    def _start(self):
        self.q = queue.Queue()
        err = open(self.log, "ab")
        self.proc = subprocess.Popen(self.args, cwd=self.cwd, env=self.env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1)
        err.close()
        self.pump = threading.Thread(target=self._pump, args=(self.proc, self.q), daemon=True)
        self.pump.start()

    @staticmethod
    def _pump(proc, q):
        for line in proc.stdout:
            if line.startswith(GO_PREFIX):
                q.put(line[len(GO_PREFIX):])
        q.put(None)

    def request(self, req: dict) -> dict:
        """One request; raises _GoDied when the process ends before it answers."""
        if self.proc is None or self.proc.poll() is not None:
            self._start()
        self.n += 1
        req = dict(req, id=self.n)
        try:
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            self.stop()
            raise _GoDied(str(e)) from e
        while True:
            try:
                line = self.q.get(timeout=GO_TIMEOUT_S)
            except queue.Empty:
                self.stop()
                raise C.MutateError(f"the Go harness gave no answer in {GO_TIMEOUT_S} s")
            if line is None:
                self.stop()
                raise _GoDied(self.log.read_text(errors="replace")[-1500:] if self.log.is_file() else "")
            resp = json.loads(line)
            if resp.get("id") == req["id"]:
                if resp.get("error"):
                    raise C.MutateError(f"Go harness: {resp['error']}")
                return resp

    def stop(self):
        if self.proc is not None:
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            if self.pump is not None:
                self.pump.join(timeout=30)
            self.proc.stdout.close()
            self.proc, self.pump = None, None


class _GoDied(Exception):
    pass


# ---------------------------------------------------------------------------------------------- the harness
class Harness:
    """The replay harness of one source tree. Builds each Foundry project and the Go test binary once, lazily; every
    result is memoized by (role, argument) (the tree is fixed). Use as a context manager, or close()."""

    def __init__(self, tree, sol_deps=None, work=None):
        self.tree = Path(tree).resolve()
        if not (self.tree / "go.work").is_file():
            raise C.MutateError(f"{self.tree} is not a source tree laid out as the checkout (no go.work)")
        self.sol_deps = Path(sol_deps).resolve() if sol_deps else C.sol_deps(_root())
        self._own = work is None
        self.work = Path(tempfile.mkdtemp(prefix="holon-i61-replay-")) if work is None else Path(work).resolve()
        self.work.mkdir(parents=True, exist_ok=True)
        self.roles = roles()
        self._cache: dict = {}
        self._src = self._plan = self._messages = None
        self._sol = self._trace = self._go = None
        self._model = None
        self._k = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._go is not None:
            self._go.stop()
            self._go = None
        if self._own:
            shutil.rmtree(self.work, ignore_errors=True)

    # ------------------------------------------------------------------ Solidity: the M0 roles' project
    def source(self) -> Source:
        if self._src is None:
            units = sorted({_span(_role_doc(r)[0]["entry"]["src"])[0] for r in ("enc_sol", "ok_sol")})
            self._src = Source(self.tree, units, self.sol_deps)
        return self._src

    def plan(self) -> EncPlan:
        if self._plan is None:
            self._plan = enc_plan(self.source())
            self._messages = load_messages(self.source())
        return self._plan

    def _project(self, name: str, units: list, files: dict) -> Path:
        """A scratch Foundry project: the given tree units (the Foundry directory's), morph's foundry.toml and
        remappings.txt, a copy of sol_deps, and the harness files {path in the project: text}."""
        from ..mreplay import FOUNDRY_DIR
        proj = self.work / name
        shutil.rmtree(proj, ignore_errors=True)
        proj.mkdir(parents=True)
        for u in units:
            if not u.startswith(FOUNDRY_DIR + "/"):
                raise C.MutateError(f"{u} is outside the Foundry directory {FOUNDRY_DIR}")
            dst = proj / u[len(FOUNDRY_DIR) + 1:]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.tree / u, dst)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy2(self.tree / FOUNDRY_DIR / f, proj / f)
        shutil.copytree(self.sol_deps, proj / "node_modules", symlinks=False, ignore=shutil.ignore_patterns(".git"))
        for rel, text in files.items():
            (proj / rel).parent.mkdir(parents=True, exist_ok=True)
            (proj / rel).write_text(text)
        tc = _toolchain()
        code, out = _run([tc["forge"], "build", "--offline", "--use", tc["solc"]], proj)
        if code != 0:
            raise C.MutateError(f"forge build of the {name} project failed (exit {code}): {out[-3000:]}")
        return proj

    def sol_project(self) -> Path:
        if self._sol is None:
            src, plan = self.source(), self.plan()
            self._sol = self._project("sol", src.tree_units, {SOL_TEST.as_posix(): sol_source(src, plan)})
        return self._sol

    def _sol_items(self, items: list) -> list:
        """Run Solidity items ("0x" + op byte + payload) through the harness: one output line each."""
        if not items:
            return []
        proj, tc = self.sol_project(), _toolchain()
        (proj / SOL_IN).write_text("\n".join(items + ["0x"]) + "\n")
        (proj / SOL_OUT).unlink(missing_ok=True)
        cmd = [tc["forge"], "test", "--match-contract", SOL_CONTRACT, "--offline", "--use", tc["solc"],
               "--gas-limit", str(GAS_LIMIT)]
        code, out = _run(cmd, proj, {"HOLON_I61_IN": SOL_IN, "HOLON_I61_OUT": SOL_OUT})
        got = (proj / SOL_OUT).read_text().splitlines() if (proj / SOL_OUT).is_file() else []
        if code != 0 or len(got) != len(items) + 1 or got[-1] != f"done {len(items)}":
            raise C.MutateError(f"the Solidity harness failed (exit {code}, {len(got)} lines for {len(items)} items): "
                                f"{out[-2000:]}")
        return got[:-1]

    def _enc_item(self, h: dict) -> str:
        if not isinstance(h, dict):
            raise C.MutateError(f"enc_sol takes a Header (field -> 0x hex), not {h!r}")
        words = []
        for name, t in self.plan().fields:
            v = h.get(name)
            b = bytes.fromhex(v[2:]) if isinstance(v, str) and v.startswith("0x") else None
            width = 32 if t == "bytes32" else int(t[4:]) // 8
            if b is None or len(b) != width:
                raise C.MutateError(f"enc_sol: Header field {name} must be {width} bytes, got {v!r}")
            words.append(b if t == "bytes32" else bytes(32 - width) + b)
        return "0x" + (bytes([ENC]) + b"".join(words)).hex()

    def _enc_result(self, line: str) -> dict:
        if line.startswith("v "):
            return {"kind": "value", "value": line[2:].strip().lower(), "detail": "", "revert_line": None}
        m = re.fullmatch(r"r (\d+) (0x[0-9a-fA-F]*)", line.strip())
        if not m:
            raise C.MutateError(f"enc_sol: the harness wrote {line[:200]!r}")
        kind, why = revert_reason(bytes.fromhex(m.group(2)[2:]))
        k = int(m.group(1))
        if kind == "panic":
            return {"kind": "panic", "value": None, "detail": why, "revert_line": None}
        plan = self.plan()
        at = plan.markers[k - 1] if 1 <= k <= len(plan.markers) else None
        where = f" in the copied statement at {at}" if at else " in the harness's return of the hashed bytes"
        return {"kind": "revert", "value": None, "detail": f"reverted: {why}{where}",
                "revert_line": at if k in plan.checks else None}

    def _load_result(self, line: str) -> dict:
        if line.strip() == "t":
            return {"kind": "value", "value": True, "detail": "", "revert_line": None}
        m = re.fullmatch(r"f (0x[0-9a-fA-F]*)", line.strip())
        if not m:
            raise C.MutateError(f"ok_sol: the harness wrote {line[:200]!r}")
        # the loader's meaning gives every revert, a Panic included, the value false (instrument replay.semantics:
        # a Solidity Panic falsifies only in a role the meaning gives no revert value)
        _, why = revert_reason(bytes.fromhex(m.group(1)[2:]))
        self.plan()
        at = self._messages.get(why, [])
        return {"kind": "value", "value": False, "detail": f"reverted: {why}",
                "revert_line": at[0] if len(at) == 1 else None}

    # ------------------------------------------------------------------ Go
    def go_server(self) -> _GoServer:
        if self._go is None:
            h = binding()["harnesses"]["go"]
            ws = self.work / "go"
            shutil.rmtree(ws, ignore_errors=True)
            C.copy_tree(self.tree, ws)
            pkg = ws / h["package"]
            if not pkg.is_dir():
                raise C.MutateError(f"the tree has no package {h['package']}")
            for f in pkg.glob("*_test.go"):
                f.unlink()
            shutil.copy2(GO_HARNESS, pkg / GO_HARNESS.name)
            mod = next((d for d in [pkg, *pkg.parents] if (d / "go.mod").is_file()), None)
            if mod is None or ws not in [mod, *mod.parents]:
                raise C.MutateError(f"no module holds {h['package']}")
            # -trimpath: the build cache is keyed independently of the scratch path, so each tree rebuilds only what
            # its sources change (the code is compiled the same; only recorded file names differ)
            code, out = _run([_toolchain()["go"], "test", "-c", "-trimpath", "-o", str(ws / GO_BINARY),
                              "./" + pkg.relative_to(mod).as_posix()], mod, _go_env(ws), timeout=GO_TIMEOUT_S)
            if code != 0 or not (ws / GO_BINARY).is_file():
                raise C.MutateError(f"the Go harness did not build (exit {code}): {out[-3000:]}")
            self._go = _GoServer(ws / GO_BINARY, pkg, _go_env(ws), ws / "harness.stderr")
        return self._go

    def _go_request(self, role: str, args: list) -> list:
        b = binding()["edges"][role]
        req = {"op": b["op"], "getters": [], "headers": [], "bytes": []}
        if b["op"] in ("decode", "validate"):
            req["bytes"] = list(args)
            if b["op"] == "decode":
                req["getters"] = [b["getters"][g["name"]] for g in facts()["functions"][role]["getters"]]
        else:
            for h in args:
                if not isinstance(h, dict) or not set(b["fields"]) <= set(h):
                    raise C.MutateError(f"{role} takes a Header with the fields {sorted(b['fields'])}, not {h!r}")
            req["headers"] = [{g: h[f] for f, g in b["fields"].items()} for h in args]
        server = self.go_server()
        try:
            res = server.request(req)["results"]
        except _GoDied:
            if len(args) == 1:   # a fatal error (not recoverable in Go) on this one input: the program died
                why = server.log.read_text(errors="replace").strip().splitlines() if server.log.is_file() else []
                return [{"kind": "panic", "value": None, "detail": "fatal: " + (why[-1] if why else "the process died"),
                         "revert_line": None}]
            return [r for a in args for r in self._go_request(role, [a])]
        if len(res) != len(args):
            raise C.MutateError(f"{role}: {len(res)} Go results for {len(args)} inputs")
        return [{"kind": r["kind"], "value": r["value"] if r["kind"] == "value" else None, "detail": r["detail"],
                 "revert_line": None} for r in res]

    # ------------------------------------------------------------------ the specification
    def _spec(self, fn: str, args: list) -> list:
        from .. import facts as F
        from ..model_eval import CompiledModel, ModelError, value_in, value_out
        if self._model is None:
            self._model = CompiledModel.build(_root() / binding()["facts"])
        fx = facts()
        arg_t, res_t = F.fn_types(fx, fn)
        jobs = [{"terms": [{"call": fn, "args": [{"var": "x"}]}], "env": {"x": value_in(arg_t, a, fx)}} for a in args]
        out = []
        for (v,) in self._model.run_jobs(jobs):
            try:
                out.append({"kind": "value", "value": value_out(res_t, v), "detail": "specification",
                            "revert_line": None})
            except (ValueError, ModelError) as e:
                raise C.MutateError(f"the specification {fn} is undefined: {e}") from e
        return out

    # ------------------------------------------------------------------ calls
    def calls_many(self, need: dict) -> dict:
        """{role: [arg, ..]} -> {role: [result, ..]}: one batch per language (the Solidity roles in one forge run)."""
        todo = {}
        for role, args in need.items():
            if role != SPEC and role not in self.roles:
                raise C.MutateError(f"unknown role {role}")
            for a in args:
                k = _canon(a)
                if (role, k) not in self._cache:
                    todo.setdefault(role, {})[k] = a
        sol = [(r, k, a) for r in sorted(todo) if self.roles.get(r) == "solidity" for k, a in sorted(todo[r].items())]
        if sol:
            items = [self._enc_item(a) if r == "enc_sol" else
                     "0x" + (bytes([LOAD]) + bytes.fromhex(_bytes_arg(r, a)[2:])).hex() for r, _, a in sol]
            lines = self._sol_items(items)
            for (r, k, _), line in zip(sol, lines):
                self._cache[(r, k)] = self._enc_result(line) if r == "enc_sol" else self._load_result(line)
        for r in sorted(todo):
            if r == SPEC or self.roles.get(r) == "go":
                ks = sorted(todo[r])
                args = [todo[r][k] for k in ks]
                if self.roles.get(r) == "go" and binding()["edges"][r]["op"] in ("decode", "validate"):
                    args = [_bytes_arg(r, a) for a in args]
                res = self._spec(r, args) if r == SPEC else self._go_request(r, args)
                for k, x in zip(ks, res):
                    self._cache[(r, k)] = x
        return {r: [dict(self._cache[(r, _canon(a))]) for a in args] for r, args in need.items()}

    def calls(self, role: str, args: list) -> list:
        """Each argument's call() result, in order."""
        return self.calls_many({role: list(args)})[role]

    # ------------------------------------------------------------------ claims
    def evaluate(self, law: dict, envs: list) -> list:
        """The claim's evaluation at each assignment: [_Eval], every role call run on the tree, round by round."""
        st = law["statement"]
        if set(st["claim"]) != {"eq"} or len(st["claim"]["eq"]) != 2:
            raise C.MutateError(f"{law.get('law_id')}: only eq claims exist in the M0 statements")
        evs = [_Eval(st["claim"]["eq"], env) for env in envs]
        while True:
            need = {}
            for ev in evs:
                ev.collect(need)
            if not need:
                break
            res = self.calls_many({r: list(m.values()) for r, m in sorted(need.items())})
            got = {(r, _canon(a)): x for r, m in need.items() for a, x in zip(m.values(), res[r])}
            for ev in evs:
                ev.apply(got)
        return evs

    def claims(self, law: dict, envs: list) -> list:
        """[{"value": True | False | None, "calls": [{"role", "arg", "result"}]}] per assignment, the calls in
        evaluation order (bottom-up, round by round, left to right)."""
        return [{"value": ev.verdict(), "calls": ev.calls} for ev in self.evaluate(law, envs)]

    # ------------------------------------------------------------------ trace laws
    def trace_project(self) -> Path:
        if self._trace is None:
            from ..mreplay import FOUNDRY_DIR
            files, units = {}, set()
            for rel in TRACE_HARNESSES:
                text = (_root() / rel).read_text()
                files[(Path("test") / rel.name).as_posix()] = text
                units |= {f"{FOUNDRY_DIR}/{m}" for m in re.findall(r'from\s+"\.\./([^"]+)"', text)}
            src = Source(self.tree, sorted(units), self.sol_deps)
            self._trace = self._project("trace", src.tree_units, files)
        return self._trace

    def _trace_outcomes(self, traces: list, mfacts: dict) -> list:
        from ..mreplay import CHUNK, LINE, encode_step
        proj, tc = self.trace_project(), _toolchain()
        init = mfacts["initial"]
        data = [init["F"], init["W"], init["D"], init["t"], init["fsr"][0], len(traces)]
        for tr in traces:
            data.append(len(tr))
            for a in tr:
                data += encode_step(a, mfacts)
        (proj / "holon_traces.json").write_text(json.dumps({"data": data}))
        cmd = [tc["forge"], "test", "--match-contract", TRACE_CONTRACT, "-vv", "--offline", "--use", tc["solc"]]
        got = {}
        for lo in range(0, len(traces), CHUNK):
            code, out = _run(cmd, proj, {"HOLON_TRACES": "holon_traces.json", "HOLON_LO": str(lo),
                                         "HOLON_HI": str(lo + CHUNK)})
            for m in LINE.finditer(out):
                got[(int(m.group(1)), int(m.group(2)))] = (m.group(3), m.group(4).strip())
            if code != 0 and not any(t >= lo for t, _ in got):
                raise C.MutateError(f"the trace harness failed (exit {code}): {out[-2000:]}")
        outs = []
        for t, tr in enumerate(traces):
            steps = [got.get((t, i)) for i in range(len(tr))]
            if any(s is None for s in steps):
                raise C.MutateError(f"the trace harness logged no outcome for some step of trace {t}")
            outs.append(steps)
        return outs

    def panic_site(self, trace: list, mfacts: dict) -> str | None:
        """The located site "<unit>:<line>" of the Panic the trace's last step raises (holon.mreplay.last_step and
        locate_panic, the I15 M2 replay), or None when no frame raised one."""
        from ..mreplay import FOUNDRY_DIR, last_step
        tc = _toolchain()
        self._k += 1
        try:
            got, panic, _ = last_step(self.trace_project(), trace, mfacts, tc["forge"], tc["solc"], self._k)
        except SystemExit as e:
            raise C.MutateError(str(e)) from e
        except ValueError as e:
            raise C.MutateError(f"the panic of a trace step cannot be located: {e}") from e
        if not str(got.get(len(trace) - 1, "")).startswith("rev panic:"):
            raise C.MutateError(f"the last step replayed alone gave {got.get(len(trace) - 1)!r}, not the panic")
        return f"{FOUNDRY_DIR}/{panic['path']}:{panic['line']}" if panic else None

    def trace_claims(self, law: dict, traces: list) -> list:
        """The law's claim on each trace: False iff some step panics at the law's site (its basis span). A law with no
        site (an M1x law over the hand abstraction) has no step that can falsify it there: it holds on every trace."""
        from ..mreplay import in_span
        try:
            span = site_span(law)
        except C.MutateError:
            return [True for _ in traces]
        mfacts = _json(_json(M1_REGISTRY.as_posix())["facts"])
        outs = self._trace_outcomes([list(t) for t in traces], mfacts) if traces else []
        res = []
        for tr, steps in zip(traces, outs):
            val = True
            for i, (kind, why) in enumerate(steps):
                if kind == "rev" and why.startswith("panic:"):
                    if in_span(span, self.panic_site(list(tr[:i + 1]), mfacts)):
                        val = False
                        break
            res.append(val)
        return res


def _bytes_arg(role: str, a) -> str:
    if not (isinstance(a, str) and re.fullmatch(r"0x(?:[0-9a-fA-F]{2})*", a)):
        raise C.MutateError(f"{role} takes 0x bytes, not {a!r}")
    return a.lower()


NONE, PANIC = object(), object()
# a role whose value is none (replay.semantics: dec_go is None when validate() errs). It is a value, compared with the
# other side like any value (none is never some(...)), unlike NONE, a call with no value, which makes no execution
NONE_VALUE = {"none": True}


class _Eval:
    """One assignment's claim, evaluated bottom-up: role calls are collected round by round and applied."""

    def __init__(self, sides: list, env: dict):
        self.sides, self.env = sides, env
        self.results = {}     # path -> call result
        self.asked = set()
        self.calls = []       # [{"role", "arg", "result"}] in evaluation order
        self._round = []

    def value(self, t: dict, path: tuple):
        """The term's value, NONE_VALUE (the role's value is none), NONE (no value), PANIC, or None when a call it
        needs has not run yet."""
        if "var" in t:
            if t["var"] not in self.env:
                raise C.MutateError(f"the assignment binds no {t['var']}")
            return self.env[t["var"]]
        if "bytes" in t:
            return t["bytes"].lower()
        if "field" in t:
            v = self.value(t["of"], path + ("of",))
            if v is NONE_VALUE:
                return NONE                  # a field of none: the model's undefined intermediate, no execution
            return v if v is None or v is NONE or v is PANIC else v[t["field"]]
        if "some" in t:
            return self.value(t["some"], path + ("some",))
        if "call" in t:
            if path in self.results:
                r = self.results[path]
                if r["kind"] == "value":
                    return NONE_VALUE if r["value"] is None else r["value"]
                return PANIC if r["kind"] == "panic" else NONE
            vals = [self.value(a, path + ("args", i)) for i, a in enumerate(t["args"])]
            if any(v is PANIC for v in vals):
                return PANIC
            if any(v is NONE or v is NONE_VALUE for v in vals):
                return NONE                  # a role never takes none as its argument: no execution
            return None
        raise C.MutateError(f"term {t} is not in the M0 IR")

    def _visit(self, t: dict, path: tuple, need: dict):
        for k in ("of", "some"):
            if k in t:
                self._visit(t[k], path + (k,), need)
        for i, a in enumerate(t.get("args", [])):
            self._visit(a, path + ("args", i), need)
        if "call" in t and path not in self.results and path not in self.asked:
            vals = [self.value(a, path + ("args", i)) for i, a in enumerate(t["args"])]
            if len(vals) == 1 and all(vals[0] is not x for x in (None, NONE, NONE_VALUE, PANIC)):
                need.setdefault(t["call"], {})[_canon(vals[0])] = vals[0]
                self.asked.add(path)
                self._round.append((path, t["call"], vals[0]))

    def collect(self, need: dict):
        self._round = []
        for i, side in enumerate(self.sides):
            self._visit(side, ("eq", i), need)

    def apply(self, got: dict):
        for path, role, arg in self._round:
            r = got[(role, _canon(arg))]
            self.results[path] = r
            self.calls.append({"role": role, "arg": arg, "result": r})
        self._round = []

    def verdict(self):
        if any(c["result"]["kind"] == "panic" for c in self.calls):
            return False
        a, b = (self.value(s, ("eq", i)) for i, s in enumerate(self.sides))
        if a is None or b is None:
            raise C.MutateError("the claim's evaluation did not finish")
        if a is NONE or b is NONE or a is PANIC or b is PANIC:
            return None
        return _canon(a) == _canon(b)


# ---------------------------------------------------------------------------------------------- the public functions
def call(tree, role: str, arg, sol_deps=None) -> dict:
    """One M0 role on the code of a source tree: {"kind", "value", "detail", "revert_line"}."""
    with Harness(tree, sol_deps) as h:
        return h.calls(role, [arg])[0]


def claim(tree, law: dict, env: dict, sol_deps=None):
    """The law's claim at one assignment on the tree's code: True, False, or None (no execution)."""
    with Harness(tree, sol_deps) as h:
        return h.claims(law, [env])[0]["value"]


def trace_claim(tree, law: dict, trace: list, sol_deps=None) -> bool:
    """A trace law's claim on one witness trace replayed on the tree's Rollup: False iff a step panics at its site."""
    with Harness(tree, sol_deps) as h:
        return h.trace_claims(law, [trace])[0]


def site_span(law: dict) -> str:
    """The law's basis span: its basis (a DERIVATION entry's) or the site its claim names ('<model>:<span>:<hash>')."""
    b = law.get("basis")
    if isinstance(b, dict) and isinstance(b.get("span"), str):
        return b["span"]
    sites = [t["site"] for t in law.get("statement", {}).get("claim", {}).get("eq", [])
             if isinstance(t, dict) and isinstance(t.get("site"), str)]
    if len(sites) != 1:
        raise C.MutateError(f"{law.get('law_id')}: no site in its claim and no basis: it is not a site law")
    _, _, rest = sites[0].partition(":")
    span, _, _ = rest.rpartition(":")
    if not span:
        raise C.MutateError(f"{law.get('law_id')}: site {sites[0]!r} names no span")
    return span


# ---------------------------------------------------------------------------------------------- the overlap check
def model_check(harness: Harness, facts_path=None, laws=None, keep: int = 10) -> dict:
    """For every laws/M0 statement and every candidate of its candidate space (holon.refute.candidates with the law's
    pins, in order), each role call's harness value against the model's value of the same term (the compiled
    facts_path, default the frozen facts): {"laws": {law: counts}, "total": counts}, counts {"candidates",
    "compared" (model defined), "equal", "different", "model_undefined", "differences": [first `keep`]}."""
    from .. import facts as F
    from .. import refute
    from ..gen import laws as LG
    from ..model_eval import CompiledModel, ModelError, value_in, value_out
    fp = Path(facts_path) if facts_path else _root() / binding()["facts"]
    fx = F.load(fp)
    model = CompiledModel.build(fp)
    if laws is None:
        laws = [C.load_json(p) for p in sorted((_root() / M0_LAWS).glob("L_*.json"))]
    out, total = {}, {"candidates": 0, "compared": 0, "equal": 0, "different": 0, "model_undefined": 0}
    for law in laws:
        pins = LG.collect_pins(law, fx)
        types = LG.binder_types(law)
        cands = list(refute.candidates(law, fx, pins))
        evs = harness.evaluate(law, [env for _, env in cands])
        paths = []

        def visit(t, path):
            for k in ("of", "some"):
                if k in t:
                    visit(t[k], path + (k,))
            for i, a in enumerate(t.get("args", [])):
                visit(a, path + ("args", i))
            if "call" in t and t["call"] != SPEC:
                paths.append((path, t))
        for i, side in enumerate(law["statement"]["claim"]["eq"]):
            visit(side, ("eq", i))
        jobs = [{"terms": [t for _, t in paths], "env": {v: value_in(types[v], env[v], fx) for v in types}}
                for _, env in cands]
        counts = {"candidates": len(cands), "compared": 0, "equal": 0, "different": 0, "model_undefined": 0,
                  "differences": []}
        for (label, env), ev, vals in zip(cands, evs, model.run_jobs(jobs)):
            for (path, t), v in zip(paths, vals):
                try:
                    mv = value_out(LG.type_of(t, types, fx), v)
                except (ValueError, ModelError):
                    counts["model_undefined"] += 1
                    continue
                counts["compared"] += 1
                r = ev.results.get(path)
                if r is not None and r["kind"] == "value" and _canon(r["value"]) == _canon(mv):
                    counts["equal"] += 1
                else:
                    counts["different"] += 1
                    if len(counts["differences"]) < keep:
                        counts["differences"].append({"candidate": label, "role": t["call"], "model": mv,
                                                      "harness": r})
        for k in total:
            total[k] += counts[k]
        out[law["law_id"]] = counts
    return {"laws": out, "total": total}


# ---------------------------------------------------------------------------------------------- CLI
def i16_digests(h: Harness) -> dict:
    """Every role of I16's binding on I16's per-edge corpus: {edge: {"compared", "outputs_sha256"}}."""
    from .. import corpus as K
    from ..refinement import sha256_json
    b = binding()
    fp = _root() / b["facts"]
    out = {}
    for edge in sorted(b["edges"]):
        inputs = [it["input"] for it in K.corpus(edge, fp, "M0", _root())]
        res = h.calls(edge, inputs)
        bad = [r for r in res if r["kind"] != "value"]
        if bad:
            print(f"replay --i16: {edge}: {len(bad)} calls gave no value, the first {bad[0]}", file=sys.stderr)
        out[edge] = {"compared": len(inputs), "outputs_sha256": sha256_json([r["value"] for r in res])}
    return out


def _pinned_clean() -> Path:
    """The pinned checkout, at the instrument's target.commit and clean in the parts a tree copies (else a refusal)."""
    src = C.checkout(_root())
    want = C.instrument(_root())["target"]["commit"]
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True)
    if head.returncode != 0 or head.stdout.strip() != want:
        raise C.MutateError(f"{src} is at {head.stdout.strip() or '?'}, not the target commit {want}")
    st = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=all", "--",
                         *C.tree_parts(src), "go.work", "go.work.sum"], capture_output=True, text=True,
                        env={**C.env_tools(), "GIT_OPTIONAL_LOCKS": "0"})
    if st.returncode != 0 or st.stdout.strip():
        raise C.MutateError(f"{src} has uncommitted changes in the parts a tree copies: {st.stdout.strip()[:300]}")
    return src


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon mutate replay",
                                 description="the I61 replay harness on I16's per-edge corpus")
    ap.add_argument("--i16", action="store_true", help="run every role of I16's binding on I16's corpus")
    ap.add_argument("--tree", help="a source tree laid out as the checkout (default: a scratch copy of the pinned one)")
    ap.add_argument("--work", help="the scratch directory for the harness's projects (default: a temporary one)")
    args = ap.parse_args(argv)
    if not args.i16:
        ap.print_usage(sys.stderr)
        return 2
    tmp = None
    try:
        if args.tree:
            tree = Path(args.tree).resolve()
        else:
            tmp = Path(tempfile.mkdtemp(prefix="holon-i61-tree-"))
            tree = C.copy_tree(_pinned_clean(), tmp / "tree")
        with Harness(tree, work=args.work) as h:
            out = i16_digests(h)
    except C.MutateError as e:
        print(f"mutate replay: {e}", file=sys.stderr)
        return 2
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0
