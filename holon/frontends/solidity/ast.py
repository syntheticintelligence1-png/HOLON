"""The AST index, spans, terms and the symbolic walker of the Solidity frontend (rules W2-W10, N1, D1 of the I17
contract: the docstring of tests_m2/test_extract_solidity_layout.py).

Input: solc's compact JSON AST of every unit (holon.frontends.solidity.compile). Nothing here reads a fact document.

Terms (hashable, compared structurally):
  int                                    a constant, mod 2^256
  ("param", name)                        an entry parameter (W3)
  ("member", base, name)                 a member of an input struct
  ("len", base) / ("byte", base, k)      .length / constant index of input bytes
  ("index", base, i)                     any other index of an input array or bytes
  ("cdoff", base)                        x.offset in Yul: the calldata offset of x
  ("ptr", region, offset)                a pointer into a region allocated by mload(0x40) (W5)
  ("env", uid)                           a fresh environment term (storage, block/msg/tx, blobhash, external call
                                         results, mload of memory, keccak256 values, havoc); uid is unique per walk
  (op, a, b) / ("!", a)                  an operator of the condition DSL (J5) on terms
  ("trunc", bits, t), ("~", t), ("not", t), ("neg", t), ("**", a, b), ("struct", name, members, values)
                                         operators outside the DSL (a condition holding one is not expressible)
Field values (N1) are Field(name, term, value_type) and Shl(k, field) (= shl(8k, field)); every use other than an
identity conversion, argument passing and a write strips them to their underlying term.

The walk explores one path per run. A run follows a script of branch choices and takes the first choice at every new
fork, recording the alternatives; the driver (Walker.walk) runs the scripts depth first, so paths come in walk order
(J3): then-branch before else-branch, a require's revert path before its continuation. Fresh terms and regions are
named by (the choices so far, a counter), so two paths share exactly the terms of their common prefix.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

from .. import ExtractionError

WORD = 1 << 256
MASK = WORD - 1

DSL_OPS = frozenset({"==", "!=", "<", "<=", ">", ">=", "!", "&&", "||", "+", "-", "*", "/", "%", "&", "|", "^",
                     "<<", ">>"})
CMP_OPS = ("==", "!=", "<", "<=", ">", ">=")
NON_DSL_OPS = frozenset({"trunc", "~", "not", "neg", "**"})
LEAVES = frozenset({"param", "member", "len", "byte", "index", "cdoff", "ptr", "env", "struct", "str"})
INPUT_HEADS = ("param", "member", "index", "byte")

YUL_PURE = {"add", "sub", "mul", "div", "mod", "and", "or", "xor", "not", "shl", "shr", "iszero", "eq", "lt", "gt"}
YUL_MEMORY = {"mload", "mstore", "mstore8", "calldatacopy", "keccak256"}
LOOP_NODES = {"ForStatement", "WhileStatement", "DoWhileStatement", "YulForLoop"}


# ------------------------------------------------------------------------------------------------ index and spans
class Index:
    """Every node of every unit by id, the source unit of every solc file id, and line tables for spans (W2)."""

    def __init__(self, compiled):
        self.asts = compiled.asts
        self.units = compiled.units
        self.file_ids = compiled.file_ids
        self.nodes: dict[int, dict] = {}
        self._lines = {u: [0] + [i + 1 for i, b in enumerate(data) if b == 0x0A] for u, data in compiled.units.items()}
        for unit in sorted(self.asts):
            self._collect(self.asts[unit])

    def _collect(self, n) -> None:
        stack = [n]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                if isinstance(x.get("id"), int) and "nodeType" in x:
                    self.nodes[x["id"]] = x
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)

    def span(self, src: str) -> str:
        """"<unit>:<line>" or "<unit>:<lo>-<hi>" of a solc src "start:length:file" (W2)."""
        start, length, fid = (int(x) for x in src.split(":"))
        unit = self.file_ids.get(fid)
        if unit is None:
            raise ExtractionError(f"src {src} names no source unit")
        lines = self._lines[unit]
        lo = bisect.bisect_right(lines, start)
        hi = bisect.bisect_right(lines, start + max(length, 1) - 1)
        return f"{unit}:{lo}" if lo == hi else f"{unit}:{lo}-{hi}"

    def contract_of(self, fn: dict) -> dict | None:
        c = self.nodes.get(fn.get("scope"))
        return c if c is not None and c.get("nodeType") == "ContractDefinition" else None

    def fn_name(self, fn: dict) -> str:
        c = self.contract_of(fn)
        if c is not None:
            return f"{c['name']}.{fn['name']}"
        unit = self.file_ids.get(int(fn["src"].split(":")[2]), "file")
        stem = re.sub(r"[^A-Za-z0-9_]", "_", unit.rsplit("/", 1)[-1].rsplit(".", 1)[0])
        return f"{stem}.{fn['name']}"

    def contracts_named(self, name: str) -> list[dict]:
        out = []
        for unit in sorted(self.asts):
            for n in self.asts[unit].get("nodes", []):
                if n.get("nodeType") == "ContractDefinition" and n.get("name") == name:
                    out.append(n)
        return out


def type_string(n: dict | None) -> str:
    return ((n or {}).get("typeDescriptions") or {}).get("typeString") or ""


def bits_of(ts: str) -> int | None:
    """Bit size of an elementary type string (uintN, intN: N; bytesN: 8N; address: 160; bool: 8), else None."""
    ts = ts.strip()
    m = re.fullmatch(r"(u?int)(\d*)", ts)
    if m:
        return int(m.group(2) or 256)
    m = re.fullmatch(r"bytes(\d+)", ts)
    if m:
        return 8 * int(m.group(1))
    if ts in ("address", "address payable"):
        return 160
    if ts == "bool":
        return 8
    return None


def conversion_bits(ts: str) -> int | None:
    """Bit size for conversions: elementary types, plus contract types (addresses) and enums."""
    b = bits_of(ts)
    if b is not None:
        return b
    if ts.startswith("contract ") or ts.startswith("interface "):
        return 160
    if ts.startswith("enum "):
        return 8
    return None


# ------------------------------------------------------------------------------------------------ values
@dataclass(frozen=True)
class Field:
    """A field value (N1): the value bound to the formal `name` (leading underscores removed)."""
    name: str
    term: object
    value_type: str | None


@dataclass(frozen=True)
class Shl:
    """shl(8k, field), 1 <= k <= 31, kept as a field write shape until it is used for anything but a write."""
    k: int
    field: Field


def strip(v):
    """The underlying term of a value (N1): everywhere but writes, identity conversions and argument passing."""
    if isinstance(v, Field):
        return v.term
    if isinstance(v, Shl):
        return ("<<", v.field.term, 8 * v.k)
    if isinstance(v, tuple) and v and v[0] == "tuple":
        return ("tuple",) + tuple(strip(x) for x in v[1:])
    return v


def is_ptr(t) -> bool:
    return isinstance(t, tuple) and len(t) == 3 and t[0] == "ptr"


def _truth(x: int) -> bool:
    return x != 0


def fold(op: str, *args):
    """An operator on terms (W4): constants folded with EVM semantics, pointers moved by constants (W5)."""
    if all(isinstance(a, int) for a in args):
        a = args[0]
        b = args[1] if len(args) > 1 else None
        if op == "+":
            return (a + b) & MASK
        if op == "-":
            return (a - b) & MASK
        if op == "*":
            return (a * b) & MASK
        if op == "/":
            return a // b if b else 0
        if op == "%":
            return a % b if b else 0
        if op == "**":
            return pow(a, b, WORD)
        if op == "&":
            return a & b
        if op == "|":
            return a | b
        if op == "^":
            return a ^ b
        if op == "<<":
            return (a << b) & MASK if b < 256 else 0
        if op == ">>":
            return a >> b if b < 256 else 0
        if op == "==":
            return int(a == b)
        if op == "!=":
            return int(a != b)
        if op == "<":
            return int(a < b)
        if op == "<=":
            return int(a <= b)
        if op == ">":
            return int(a > b)
        if op == ">=":
            return int(a >= b)
        if op == "&&":
            return int(_truth(a) and _truth(b))
        if op == "||":
            return int(_truth(a) or _truth(b))
        if op == "!":
            return int(not _truth(a))
        if op in ("~", "not"):
            return (~a) & MASK
        if op == "neg":
            return (-a) & MASK
    if op in ("+", "-") and len(args) == 2:
        a, b = args
        if is_ptr(a) and isinstance(b, int):
            return ("ptr", a[1], (a[2] + b) if op == "+" else (a[2] - b))
        if op == "+" and is_ptr(b) and isinstance(a, int):
            return ("ptr", b[1], b[2] + a)
        if op == "-" and is_ptr(a) and is_ptr(b) and a[1] == b[1]:
            return (a[2] - b[2]) & MASK
    return (op,) + tuple(args)


def literal_value(n: dict):
    """A Solidity Literal as a term (W4): numbers (with subdenominations), booleans; strings as ("str", hex)."""
    kind = n.get("kind")
    if kind == "bool":
        return 1 if n.get("value") == "true" else 0
    if kind == "number":
        text = (n.get("value") or "0").replace("_", "")
        if text.lower().startswith("0x"):
            v = int(text, 16)
        elif "e" in text.lower() or "." in text:
            from decimal import Decimal
            v = int(Decimal(text))
        else:
            v = int(text)
        mult = {"wei": 1, "gwei": 10 ** 9, "ether": 10 ** 18, "seconds": 1, "minutes": 60, "hours": 3600,
                "days": 86400, "weeks": 604800}.get(n.get("subdenomination") or "", 1)
        return (v * mult) & MASK
    return ("str", n.get("hexValue") or "")


# ------------------------------------------------------------------------------------------------ control flow
class _Return(Exception):
    def __init__(self, value):
        super().__init__()
        self.value = value


class _End(Exception):
    """The path ends: outcome "revert" or "ok"."""

    def __init__(self, outcome: str, **info):
        super().__init__()
        self.outcome = outcome
        self.info = info


@dataclass
class Frame:
    fn: dict
    name: str
    vars: dict = field(default_factory=dict)
    vtypes: dict = field(default_factory=dict)      # formal decl id -> value type of its outermost argument (N2)
    is_entry: bool = False
    yul: list = field(default_factory=list)         # Yul scopes of the inline assembly being walked
    asm: dict | None = None                         # the InlineAssembly node being walked


@dataclass
class PathResult:
    outcome: str                                    # ok | revert | other
    cond: list
    failing: int | None = None                      # revert: index of the failing conjunct in cond
    reason: str = ""
    src: str = ""
    length: object = None                           # ok: the sink's length term
    ops: list = field(default_factory=list)         # ok: raw store-sequence writes (dicts)
    seq_debt: list = field(default_factory=list)    # ok: debt entries inside the store sequence
    debt: list = field(default_factory=list)        # every debt entry of the path
    sinks: list = field(default_factory=list)       # stacks (tuples) of every keccak256 evaluation
    functions: set = field(default_factory=set)
    sink_ptr: object = None


# ------------------------------------------------------------------------------------------------ one run
class Run:
    """One path of a walk, following `script` at its forks."""

    def __init__(self, walker: "Walker", script: list[int]):
        self.w = walker
        self.ix = walker.index
        self.script = script
        self.decisions: list[int] = []
        self.new_forks: list[int] = []              # positions (in decisions) of forks beyond the script
        self.counter = 0
        self.seq = 0
        self.cond: list = []
        self.frames: list[Frame] = []
        self.calls: list[str] = []                  # spans of the FunctionCall nodes inlined so far (W2)
        self.call_ids: list[int] = []
        self.writes: list[dict] = []
        self.regions: dict = {}
        self.debts: list[tuple[int, dict]] = []
        self.ext_calls: list[tuple[int, dict]] = []
        self.sinks: list[tuple] = []
        self.functions: set = set()

    # -- naming and bookkeeping
    def fresh(self):
        self.counter += 1
        return ("env", (tuple(self.decisions), self.counter))

    def tick(self) -> int:
        self.seq += 1
        return self.seq

    @property
    def frame(self) -> Frame:
        return self.frames[-1]

    def stack_of(self, node: dict) -> list[str]:
        return self.calls + [self.ix.span(node["src"])]

    def fork(self) -> int:
        pos = len(self.decisions)
        if pos < len(self.script):
            choice = self.script[pos]
        else:
            choice = 0
            self.new_forks.append(pos)
        self.decisions.append(choice)
        return choice

    def debt(self, kind: str, construct: str, node: dict, havoc=None) -> None:
        """D1: record a debt entry and havoc what the construct may assign (regions become unknown)."""
        entry = {"kind": kind, "construct": construct, "src": self.ix.span(node["src"]),
                 "fn": self.frame.name, "stack": self.stack_of(node)}
        self.debts.append((self.tick(), entry))
        if havoc is not None:
            self._havoc(havoc)

    def _havoc(self, node) -> None:
        sol, yul = set(), set()
        asm_refs = {}
        stack = [(node, self.frame.asm)]
        while stack:
            x, asm = stack.pop()
            if isinstance(x, dict):
                nt = x.get("nodeType")
                if nt == "InlineAssembly":
                    asm = x
                if nt == "Assignment":
                    sol |= _lvalue_decls(x.get("leftHandSide"))
                elif nt == "UnaryOperation" and x.get("operator") in ("++", "--", "delete"):
                    sol |= _lvalue_decls(x.get("subExpression"))
                elif nt == "YulAssignment":
                    for v in x.get("variableNames", []):
                        ref = _external_ref(asm, v)
                        if ref is not None:
                            sol.add(ref["declaration"])
                            asm_refs[ref["declaration"]] = ref
                        else:
                            yul.add(v["name"])
                for k, v in x.items():
                    if isinstance(v, (dict, list)):
                        stack.append((v, asm))
            elif isinstance(x, list):
                stack.extend((v, asm) for v in x)
        for d in sorted(sol):
            if d in self.frame.vars:
                self.frame.vars[d] = self.fresh()
        for name in sorted(yul):
            for scope in reversed(self.frame.yul):
                if name in scope:
                    scope[name] = self.fresh()
                    break

    # -- the run
    def execute(self) -> PathResult:
        entry = self.w.entry
        f = Frame(fn=entry, name=self.ix.fn_name(entry), is_entry=True)
        for p in entry["parameters"]["parameters"]:
            f.vars[p["id"]] = ("param", p["name"])
        for p in entry["returnParameters"]["parameters"]:
            f.vars[p["id"]] = 0
        self.frames.append(f)
        self.functions.add(f.name)
        try:
            self._modifiers(entry)
            try:
                self.block(entry["body"])
            except _Return:
                pass
        except _End as e:
            return self._finish(e)
        return PathResult(outcome="other", cond=list(self.cond), debt=self._debt_entries(), sinks=list(self.sinks),
                          functions=set(self.functions))

    def _debt_entries(self) -> list[dict]:
        return [d for _, d in self.debts]

    def _finish(self, e: _End) -> PathResult:
        r = PathResult(outcome=e.outcome, cond=list(self.cond), sinks=list(self.sinks), functions=set(self.functions))
        if e.outcome == "revert":
            r.failing, r.reason, r.src = e.info["failing"], e.info["reason"], e.info["src"]
        else:
            r.length, r.ops, r.seq_debt, r.sink_ptr = e.info["length"], e.info["ops"], e.info["seq_debt"], e.info["ptr"]
        r.debt = self._debt_entries()
        return r

    # -- branching (W9)
    def decide(self, c):
        """W9: True / False when the condition is decided on this path, else None (the path forks). Decided: it folds
        to a constant, it or its negation is a conjunct, or adding it makes the path infeasible (False). Adding its
        negation making the path infeasible decides it True, so no infeasible branch is ever walked."""
        if isinstance(c, int):
            return _truth(c)
        if c in self.cond:
            return True
        if ("!", c) in self.cond:
            return False
        if isinstance(c, tuple) and c[0] == "!" and c[1] in self.cond:
            return False
        if infeasible(self.cond + [c]):
            return False
        if infeasible(self.cond + [("!", c)]):
            return True
        return None

    def require(self, c, reason: str, node: dict) -> None:
        d = self.decide(c)
        if d is True:
            return
        if d is None and self.fork() == 1:
            self.cond.append(c)
            return
        if d is None:
            self.cond.append(("!", c))
        self.revert(reason, node)

    def revert(self, reason: str, node: dict) -> None:
        failing = len(self.cond) - 1 if self.cond else None
        raise _End("revert", failing=failing, reason=reason, src=self.ix.span(node["src"]))

    # -- statements (W6)
    def block(self, n: dict) -> None:
        for s in n.get("statements") or []:
            self.stmt(s)

    def stmt(self, n: dict) -> None:
        nt = n["nodeType"]
        if nt in ("Block", "UncheckedBlock"):
            self.block(n)
        elif nt == "ExpressionStatement":
            self.expr(n["expression"])
        elif nt == "VariableDeclarationStatement":
            self.var_decl(n)
        elif nt == "IfStatement":
            c = strip(self.expr(n["condition"]))
            d = self.decide(c)
            if d is None:
                if self.fork() == 0:
                    self.cond.append(c)
                    d = True
                else:
                    self.cond.append(("!", c))
                    d = False
            if d:
                self.stmt(n["trueBody"])
            elif n.get("falseBody") is not None:
                self.stmt(n["falseBody"])
        elif nt == "Return":
            value = self.expr(n["expression"]) if n.get("expression") is not None else None
            raise _Return(value)
        elif nt == "InlineAssembly":
            self.assembly(n)
        elif nt == "EmitStatement":
            pass
        elif nt in LOOP_NODES:
            self.debt("loop", nt, n, havoc=n)
        else:
            self.debt("construct", nt, n, havoc=n)

    def var_decl(self, n: dict) -> None:
        decls = n.get("declarations") or []
        if n.get("initialValue") is None:
            for d in decls:
                if d is not None:
                    self.frame.vars[d["id"]] = 0
            return
        v = self.expr(n["initialValue"])
        if len(decls) == 1:
            if decls[0] is not None:
                self.frame.vars[decls[0]["id"]] = _bindable(v)
            return
        vals = _components(v, len(decls))
        for d, x in zip(decls, vals):
            if d is not None:
                self.frame.vars[d["id"]] = _bindable(x)

    # -- expressions
    def expr(self, n: dict):
        nt = n["nodeType"]
        if nt == "Literal":
            return literal_value(n)
        if nt == "Identifier":
            return self.identifier(n)
        if nt == "MemberAccess":
            return self.member(n)
        if nt == "IndexAccess":
            return self.index_access(n)
        if nt == "BinaryOperation":
            a = strip(self.expr(n["leftExpression"]))
            b = strip(self.expr(n["rightExpression"]))
            return fold(n["operator"], a, b)
        if nt == "UnaryOperation":
            return self.unary(n)
        if nt == "TupleExpression":
            if n.get("isInlineArray"):
                self.debt("construct", nt, n, havoc=n)
                return self.fresh()
            comps = n.get("components") or []
            vals = [self.expr(c) if c is not None else None for c in comps]
            return vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals)
        if nt == "FunctionCall":
            return self.call(n)
        if nt == "Assignment":
            return self.assign(n)
        if nt == "ElementaryTypeNameExpression":
            return ("type", type_string(n))
        self.debt("construct", nt, n, havoc=n)
        return self.fresh()

    def constant(self, decl: dict, seen=()):
        """The folded value of a constant VariableDeclaration (W4), or None when it does not fold."""
        if decl["id"] in seen or decl.get("value") is None:
            return None
        v = self._const_expr(decl["value"], seen + (decl["id"],))
        return v if isinstance(v, int) else None

    def _const_expr(self, n: dict, seen):
        nt = n.get("nodeType")
        if nt == "Literal":
            return literal_value(n)
        if nt in ("Identifier", "MemberAccess"):
            d = self.ix.nodes.get(n.get("referencedDeclaration"))
            if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("constant"):
                return self.constant(d, seen)
            return None
        if nt == "BinaryOperation":
            a, b = self._const_expr(n["leftExpression"], seen), self._const_expr(n["rightExpression"], seen)
            return fold(n["operator"], a, b) if isinstance(a, int) and isinstance(b, int) else None
        if nt == "UnaryOperation" and n.get("operator") in ("-", "~", "!"):
            a = self._const_expr(n["subExpression"], seen)
            return fold({"-": "neg"}.get(n["operator"], n["operator"]), a) if isinstance(a, int) else None
        if nt == "FunctionCall" and n.get("kind") == "typeConversion" and len(n.get("arguments") or []) == 1:
            a = self._const_expr(n["arguments"][0], seen)
            if not isinstance(a, int):
                return None
            return self._convert_const(a, type_string(n["arguments"][0]), type_string(n))
        if nt == "TupleExpression" and len(n.get("components") or []) == 1 and not n.get("isInlineArray"):
            return self._const_expr(n["components"][0], seen)
        return None

    @staticmethod
    def _convert_const(a, src_ts: str, dst_ts: str):
        if isinstance(a, tuple) and a[:1] == ("str",):
            m = re.fullmatch(r"bytes(\d+)", dst_ts)
            if m:
                raw = bytes.fromhex(a[1])[:32].ljust(32, b"\0")
                return int.from_bytes(raw, "big")
            return a
        db = conversion_bits(dst_ts)
        if isinstance(a, int) and db is not None and db < 256:
            return a & ((1 << db) - 1)
        return a

    def identifier(self, n: dict):
        ref = n.get("referencedDeclaration")
        name = n.get("name")
        if ref in self.frame.vars:   # locals, parameters and return variables of the function being walked
            return self.frame.vars[ref]
        if ref is None or ref < 0:
            return ("global", name)
        d = self.ix.nodes.get(ref)
        if d is None:
            return self.fresh()
        nt = d.get("nodeType")
        if nt == "VariableDeclaration":
            if d.get("constant"):
                v = self.constant(d)
                return v if v is not None else self.fresh()
            return self.fresh()   # state variables (storage, immutables) and locals out of scope: environment (W4)
        return ("decl", ref)

    def member(self, n: dict):
        ref = n.get("referencedDeclaration")
        d = self.ix.nodes.get(ref) if isinstance(ref, int) and ref >= 0 else None
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("constant"):
            v = self.constant(d)
            return v if v is not None else self.fresh()
        if d is not None and d.get("nodeType") == "EnumValue":
            enum = self.ix.nodes.get(d.get("scope")) or {}
            members = [m.get("id") for m in enum.get("members", [])]
            return members.index(d["id"]) if d["id"] in members else self.fresh()
        if d is not None and d.get("nodeType") in ("FunctionDefinition", "EventDefinition", "ErrorDefinition"):
            return ("decl", ref)
        base_node = n["expression"]
        if base_node.get("nodeType") == "FunctionCall" and base_node.get("expression", {}).get("name") == "type":
            return self._meta_member(base_node, n["memberName"])
        base = strip(self.expr(base_node))
        name = n["memberName"]
        if isinstance(base, tuple) and base[:1] == ("global",):
            return self.fresh()   # block / msg / tx members (W4)
        if isinstance(base, tuple) and base[:1] == ("struct",):
            members, values = base[2], base[3]
            return values[members.index(name)] if name in members else self.fresh()
        if isinstance(base, tuple) and base[:1] and base[0] in INPUT_HEADS:
            if name == "length":
                return ("len", base)
            return ("member", base, name)
        return self.fresh()

    def _meta_member(self, call: dict, name: str):
        args = call.get("arguments") or []
        ts = type_string(args[0]) if args else ""
        m = re.fullmatch(r"type\((u?int)(\d*)\)", ts)
        if m:
            b = int(m.group(2) or 256)
            if m.group(1) == "uint":
                return {"max": (1 << b) - 1, "min": 0}.get(name, self.fresh())
            return {"max": (1 << (b - 1)) - 1, "min": (-(1 << (b - 1))) & MASK}.get(name, self.fresh())
        return self.fresh()

    def index_access(self, n: dict):
        base = strip(self.expr(n["baseExpression"]))
        idx = strip(self.expr(n["indexExpression"])) if n.get("indexExpression") is not None else None
        if isinstance(base, tuple) and base[:1] and base[0] in INPUT_HEADS:
            bts = type_string(n["baseExpression"])
            dynamic_bytes = bts == "bytes" or bts.startswith("bytes ")
            if dynamic_bytes and isinstance(idx, int):
                return ("byte", base, idx)
            return ("index", base, idx)
        return self.fresh()   # storage mappings and arrays, memory: environment (W4)

    def unary(self, n: dict):
        op = n["operator"]
        sub = n["subExpression"]
        if op in ("++", "--"):
            old = strip(self.expr(sub))
            new = fold("+" if op == "++" else "-", old, 1)
            self.store(sub, new, n)
            return new if n.get("prefix") else old
        if op == "delete":
            self.store(sub, 0, n)
            return 0
        a = strip(self.expr(sub))
        return fold({"-": "neg"}.get(op, op), a)

    # -- assignment
    def assign(self, n: dict):
        v = self.expr(n["rightHandSide"])
        op = n.get("operator", "=")
        if op != "=":
            old = strip(self.expr(n["leftHandSide"]))
            v = fold(op[:-1], old, strip(v))
        self.store(n["leftHandSide"], v, n)
        return v

    def store(self, lhs: dict, v, node: dict) -> None:
        nt = lhs.get("nodeType")
        if nt == "TupleExpression":
            comps = lhs.get("components") or []
            for c, x in zip(comps, _components(v, len(comps))):
                if c is not None:
                    self.store(c, x, node)
            return
        if nt == "Identifier":
            ref = lhs.get("referencedDeclaration")
            if ref in self.frame.vars or self._is_local(ref):
                self.frame.vars[ref] = _bindable(v)
            return   # a state variable: storage, nothing written (W6)
        if nt in ("IndexAccess", "MemberAccess", "IndexRangeAccess") and self._is_storage(lhs):
            return
        self.debt("construct", "Assignment", node, havoc=None)

    def _is_local(self, ref) -> bool:
        d = self.ix.nodes.get(ref) if isinstance(ref, int) else None
        return d is not None and d.get("nodeType") == "VariableDeclaration" and not d.get("stateVariable")

    def _is_storage(self, lhs: dict) -> bool:
        x = lhs
        while x.get("nodeType") in ("IndexAccess", "MemberAccess", "IndexRangeAccess"):
            x = x.get("baseExpression") or x.get("expression") or {}
        if x.get("nodeType") != "Identifier":
            return False
        d = self.ix.nodes.get(x.get("referencedDeclaration")) or {}
        return bool(d.get("stateVariable")) or d.get("storageLocation") == "storage"

    # -- calls (W8)
    def call(self, n: dict):
        kind = n.get("kind")
        args = n.get("arguments") or []
        callee = n["expression"]
        if kind == "typeConversion":
            if len(args) != 1:
                self.debt("construct", "FunctionCall", n, havoc=n)
                return self.fresh()
            v = self.expr(args[0])
            return self.convert(v, type_string(args[0]), type_string(n))
        if kind == "structConstructorCall":
            vals = tuple(strip(self.expr(a)) for a in args)
            sd = self.ix.nodes.get(callee.get("referencedDeclaration")) or {}
            names = tuple(n.get("names") or [m.get("name") for m in sd.get("members", [])])
            return ("struct", sd.get("name", ""), names, vals)
        if callee.get("nodeType") == "Identifier" and (callee.get("referencedDeclaration") or 0) < 0:
            return self.builtin(callee.get("name"), n, args)
        target = self.ix.nodes.get(callee.get("referencedDeclaration")) if callee.get("nodeType") in (
            "Identifier", "MemberAccess") else None
        cts = type_string(callee)
        external = " external" in cts or (callee.get("nodeType") == "MemberAccess" and callee.get("memberName") in (
            "call", "delegatecall", "staticcall", "send", "transfer") and target is None)
        if external:
            if callee.get("nodeType") == "MemberAccess":
                self.expr(callee["expression"])
            for a in args:
                self.expr(a)
            self.ext_calls.append((self.tick(), {"src": self.ix.span(n["src"]), "fn": self.frame.name,
                                                 "stack": self.stack_of(n)}))
            return self._results(n)
        if target is None or target.get("nodeType") != "FunctionDefinition":
            self.debt("construct", "FunctionCall", n, havoc=n)
            return self._results(n)
        target = self._dispatch(target, callee)
        arg_nodes = list(args)
        if callee.get("nodeType") == "MemberAccess" and len(arg_nodes) + 1 == len(target["parameters"]["parameters"]) \
                and not type_string(callee["expression"]).startswith("type("):
            arg_nodes = [callee["expression"]] + arg_nodes   # a bound library call x.f(y)
        if not target.get("body") or not target.get("implemented", True):
            for a in arg_nodes:
                self.expr(a)
            self.debt("call", "FunctionCall", n, havoc=None)
            return self._results(n)
        if len(self.calls) + 1 > self.w.max_depth or target["id"] in [f.fn["id"] for f in self.frames]:
            for a in arg_nodes:
                self.expr(a)
            self.debt("call", "FunctionCall", n, havoc=None)
            return self._results(n)
        return self.inline(target, arg_nodes, n)

    def _dispatch(self, target: dict, callee: dict) -> dict:
        """Virtual dispatch of a plain internal call against the entry contract's linearization."""
        if callee.get("nodeType") != "Identifier" or not target.get("virtual") and not target.get("overrides"):
            return target
        entry_c = self.ix.contract_of(self.w.entry)
        if entry_c is None:
            return target
        sig = [type_string(p) for p in target["parameters"]["parameters"]]
        for cid in entry_c.get("linearizedBaseContracts", []):
            c = self.ix.nodes.get(cid) or {}
            for x in c.get("nodes", []):
                if x.get("nodeType") == "FunctionDefinition" and x.get("name") == target.get("name") \
                        and [type_string(p) for p in x["parameters"]["parameters"]] == sig and x.get("body"):
                    return x
        return target

    def _results(self, n: dict):
        ts = type_string(n)
        if ts.startswith("tuple("):
            k = _tuple_arity(ts)
            if k == 0:
                return ("tuple",)
            if k > 1:
                return ("tuple",) + tuple(self.fresh() for _ in range(k))
        return self.fresh()

    def inline(self, target: dict, arg_nodes: list, call_node: dict):
        caller = self.frame
        vals = [self.expr(a) for a in arg_nodes]
        f = Frame(fn=target, name=self.ix.fn_name(target))
        for p, a, v in zip(target["parameters"]["parameters"], arg_nodes, vals):
            f.vars[p["id"]] = self.bind_formal(p, a, v, caller)
            vt = self._value_type(a, caller)
            f.vtypes[p["id"]] = vt
        for p in target["returnParameters"]["parameters"]:
            f.vars[p["id"]] = 0
        self.calls.append(self.ix.span(call_node["src"]))
        self.frames.append(f)
        self.functions.add(f.name)
        try:
            self._modifiers(target)
            try:
                self.block(target["body"])
                value = None
            except _Return as r:
                value = r.value
        finally:
            self.frames.pop()
            self.calls.pop()
        rets = target["returnParameters"]["parameters"]
        if value is None:
            out = [f.vars[p["id"]] for p in rets]
        else:
            out = list(_components(value, len(rets))) if len(rets) != 1 else [value]
        out = [strip(x) for x in out]
        if not out:
            return ("tuple",)
        return out[0] if len(out) == 1 else ("tuple",) + tuple(out)

    def _modifiers(self, fn: dict) -> None:
        for m in fn.get("modifiers") or []:
            if m.get("kind", "modifierInvocation") == "modifierInvocation":
                self.debt("construct", "ModifierInvocation", m, havoc=None)

    def _value_type(self, arg: dict, caller: Frame):
        """N2: the typeString at the outermost call of the chain that binds the formal."""
        if arg.get("nodeType") == "Identifier" and not caller.is_entry:
            ref = arg.get("referencedDeclaration")
            if ref in caller.vtypes:
                return caller.vtypes[ref]
        ts = type_string(arg)
        return ts or None

    def bind_formal(self, p: dict, arg: dict, v, caller: Frame):
        """N1: the value of a formal: a constant stays a constant, a pointer a pointer, anything else is the formal's
        field value (named after the formal without leading underscores; the innermost formal wins)."""
        u = strip(v)
        if isinstance(u, int) or is_ptr(u) or (isinstance(u, tuple) and u[:1] in (("tuple",), ("global",),
                                                                                    ("decl",), ("type",))):
            return u
        name = (p.get("name") or "").lstrip("_")
        if not name:
            return u
        return Field(name, u, self._value_type(arg, caller))

    def convert(self, v, src_ts: str, dst_ts: str):
        """W4: a conversion of a constant folds; to the same or a larger size (or an unsized type) it is the identity
        on terms (a field value stays one); a narrowing conversion is ["trunc", bits, t]."""
        u = strip(v)
        if isinstance(u, int) or (isinstance(u, tuple) and u[:1] == ("str",)):
            return self._convert_const(u, src_ts, dst_ts)
        sb, db = conversion_bits(src_ts), conversion_bits(dst_ts)
        if sb is not None and db is not None and db < sb:
            return ("trunc", db, u)
        return v

    def builtin(self, name: str, n: dict, args: list):
        if name == "require":
            c = strip(self.expr(args[0]))
            reason = ""
            if len(args) > 1:
                a = args[1]
                if a.get("nodeType") == "Literal" and a.get("kind") in ("string", "unicodeString"):
                    reason = a.get("value") or ""
            self.require(c, reason, n)
            return ("tuple",)
        if name == "revert":
            reason = ""
            if args and args[0].get("nodeType") == "Literal" and args[0].get("kind") in ("string", "unicodeString"):
                reason = args[0].get("value") or ""
            self.revert(reason, n)
        if name == "blobhash":
            for a in args:
                self.expr(a)
            return self.fresh()
        for a in args:
            self.expr(a)
        self.debt("construct", "FunctionCall", n, havoc=None)
        return self._results(n)

    # -- inline assembly (W7)
    def assembly(self, n: dict) -> None:
        f = self.frame
        saved = (f.asm, f.yul)
        f.asm, f.yul = n, []
        try:
            self.yul_block(n["AST"])
        finally:
            f.asm, f.yul = saved

    def yul_block(self, b: dict) -> None:
        self.frame.yul.append({})
        try:
            for s in b.get("statements") or []:
                self.yul_stmt(s)
        finally:
            self.frame.yul.pop()

    def yul_stmt(self, s: dict) -> None:
        nt = s["nodeType"]
        if nt == "YulBlock":
            self.yul_block(s)
        elif nt == "YulVariableDeclaration":
            names = [v["name"] for v in s.get("variables", [])]
            if s.get("value") is None:
                vals = [0] * len(names)
            else:
                v = self.yul_expr(s["value"])
                vals = [v] if len(names) == 1 else [self.fresh() for _ in names]
            for name, v in zip(names, vals):
                self.frame.yul[-1][name] = v
        elif nt == "YulAssignment":
            v = self.yul_expr(s["value"])
            targets = s.get("variableNames", [])
            vals = [v] if len(targets) == 1 else [self.fresh() for _ in targets]
            for t, x in zip(targets, vals):
                self.yul_set(t, x)
        elif nt == "YulExpressionStatement":
            self.yul_expr(s["expression"])
        elif nt in LOOP_NODES:
            self.debt("loop", nt, s, havoc=s)
        else:
            self.debt("construct", nt, s, havoc=s)

    def yul_set(self, ident: dict, v) -> None:
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                scope[name] = v
                return
        ref = _external_ref(self.frame.asm, ident)
        if ref is not None:
            self.frame.vars[ref["declaration"]] = _bindable(v)
            return
        self.frame.yul[-1][name] = v

    def yul_get(self, ident: dict):
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                return scope[name]
        ref = _external_ref(self.frame.asm, ident)
        if ref is None:
            return self.fresh()
        decl = ref["declaration"]
        if decl in self.frame.vars:
            v = self.frame.vars[decl]
        else:
            d = self.ix.nodes.get(decl) or {}
            v = self.constant(d) if d.get("constant") else None
            if v is None:
                v = self.fresh()
        suffix = ref.get("suffix")
        if suffix == "offset" or ref.get("isOffset") and suffix != "slot":
            return ("cdoff", strip(v))
        if suffix == "length":
            return ("len", strip(v))
        if suffix == "slot" or ref.get("isSlot"):
            return self.fresh()
        return v

    def yul_expr(self, e: dict):
        nt = e["nodeType"]
        if nt == "YulLiteral":
            if e.get("kind") == "bool":
                return 1 if e.get("value") == "true" else 0
            if e.get("kind") == "number":
                return int(e["value"], 0) & MASK
            raw = bytes.fromhex(e["hexValue"]) if e.get("hexValue") else (e.get("value") or "").encode()
            return int.from_bytes(raw[:32].ljust(32, b"\0"), "big")
        if nt == "YulIdentifier":
            return self.yul_get(e)
        if nt != "YulFunctionCall":
            self.debt("construct", nt, e, havoc=e)
            return self.fresh()
        name = e["functionName"]["name"]
        if name not in YUL_PURE and name not in YUL_MEMORY:
            # builtins outside W7 and user-defined Yul functions: debt; their arguments are not evaluated
            self.debt("construct", name, e, havoc=e)
            return self.fresh()
        args = e.get("arguments") or []
        vals = [None] * len(args)
        for i in range(len(args) - 1, -1, -1):   # Yul evaluates arguments right to left
            vals[i] = self.yul_expr(args[i])
        if name in YUL_PURE:
            return self.yul_pure(name, vals)
        return self.yul_memory(name, vals, e)

    def yul_pure(self, name: str, vals: list):
        if name == "shl":
            s, v = strip(vals[0]), vals[1]
            if isinstance(v, Field) and isinstance(s, int) and s % 8 == 0 and 8 <= s <= 248:
                return Shl(s // 8, v)
            return fold("<<", strip(v), s)
        u = [strip(v) for v in vals]
        if name == "shr":
            return fold(">>", u[1], u[0])
        if name == "iszero":
            return fold("==", u[0], 0)
        if name == "not":
            return fold("not", u[0])
        op = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%", "and": "&", "or": "|", "xor": "^",
              "eq": "==", "lt": "<", "gt": ">"}[name]
        return fold(op, u[0], u[1])

    def yul_memory(self, name: str, vals: list, e: dict):
        u0 = strip(vals[0])
        if name == "mload":
            if u0 == 0x40:
                rid = ("region", tuple(self.decisions), self.counter + 1)
                self.counter += 1
                self.regions[rid] = self.tick()
                return ("ptr", rid, 0)
            return self.fresh()   # mload of a region: an opaque term (W5)
        if name == "keccak256":
            return self.sink(u0, strip(vals[1]), e)
        if name == "mstore" and u0 == 0x40:
            return ("tuple",)     # the free-pointer update writes no cell
        if not is_ptr(u0):
            self.debt("address", name, e, havoc=None)
            return ("tuple",)
        w = {"seq": self.tick(), "region": u0[1], "offset": u0[2], "op": name, "fn": self.frame.name,
             "src": self.ix.span(e["src"]), "stack": self.stack_of(e)}
        if name == "calldatacopy":
            w["source"], w["n"] = strip(vals[1]), strip(vals[2])
        else:
            w["value"] = vals[1]
        self.writes.append(w)
        return ("tuple",)

    # -- sinks (W10, W11)
    def sink(self, p, n, e: dict):
        stack = tuple(self.stack_of(e))
        self.sinks.append(stack)
        self.tick()
        if list(stack) != self.w.sink:
            return self.fresh()
        if not is_ptr(p):
            raise ExtractionError(f"edge {self.w.edge_name}: the selected sink's address is not a region pointer (J4)")
        rid = p[1]
        created = self.regions[rid]
        ops, extra = [], []
        for w in self.writes:
            if w["region"] != rid or w["seq"] <= created:
                continue
            op = write_op(w, p[2])
            if op is None:
                extra.append((w["seq"], {"kind": "value", "construct": w["op"], "src": w["src"], "fn": w["fn"],
                                         "stack": w["stack"]}))
            else:
                ops.append(op)
        for s, c in self.ext_calls:
            if s > created:
                extra.append((s, {"kind": "call", "construct": "FunctionCall", "src": c["src"], "fn": c["fn"],
                                  "stack": c["stack"]}))
        self.debts.extend(extra)
        self.debts.sort(key=lambda x: x[0])
        seq_debt = [d for s, d in self.debts if s > created]
        raise _End("ok", length=n, ops=ops, seq_debt=seq_debt, ptr=p)


def write_op(w: dict, base: int) -> dict | None:
    """A raw store-sequence op (W11, N1): offsets relative to the sink pointer, the written shape, field cells.
    None: the write is not expressible (debt "value")."""
    off = w["offset"] - base
    origin = {"fn": w["fn"], "src": w["src"], "stack": w["stack"]}
    if w["op"] == "calldatacopy":
        s = w["source"]
        base_t, k = None, None
        if isinstance(s, tuple) and s[:1] == ("cdoff",):
            base_t, k = s[1], 0
        elif isinstance(s, tuple) and s[:1] == ("+",) and len(s) == 3:
            a, b = s[1], s[2]
            if isinstance(a, tuple) and a[:1] == ("cdoff",) and isinstance(b, int):
                base_t, k = a[1], b
            elif isinstance(b, tuple) and b[:1] == ("cdoff",) and isinstance(a, int):
                base_t, k = b[1], a
        if base_t is None:
            return None
        return {"op": "calldatacopy", "offset": off, "input": base_t, "from": k, "n": w["n"], "origin": origin,
                "fields": []}
    v = w["value"]
    if w["op"] == "mstore":
        if isinstance(v, Field):
            return {"op": "mstore", "offset": off, "items": [("field", v.name, 0, 32)], "origin": origin,
                    "fields": [(v.name, 32, v.term, v.value_type)]}
        if isinstance(v, Shl):
            f = v.field
            return {"op": "mstore", "offset": off, "items": [("field", f.name, 0, 32 - v.k), ("zeros", v.k)],
                    "origin": origin, "fields": [(f.name, 32 - v.k, f.term, f.value_type)]}
        if isinstance(v, int):
            return {"op": "mstore", "offset": off, "items": const_items(v.to_bytes(32, "big")), "origin": origin,
                    "fields": []}
        return None
    if isinstance(v, Field):
        return {"op": "mstore8", "offset": off, "items": [("field", v.name, 0, 1)], "origin": origin,
                "fields": [(v.name, 1, v.term, v.value_type)]}
    if isinstance(v, int):
        return {"op": "mstore8", "offset": off, "items": const_items(bytes([v & 0xFF])), "origin": origin,
                "fields": []}
    return None


def const_items(data: bytes) -> list:
    """Canonical items of constant bytes: a run of zero bytes is one ("zeros", n), a non-zero byte one ("const", b)."""
    out = []
    for b in data:
        if b == 0 and out and out[-1][0] == "zeros":
            out[-1] = ("zeros", out[-1][1] + 1)
        elif b == 0:
            out.append(("zeros", 1))
        else:
            out.append(("const", b))
    return out


# ------------------------------------------------------------------------------------------------ helpers
def _components(v, k: int) -> list:
    if isinstance(v, tuple) and v[:1] == ("tuple",) and len(v) - 1 == k:
        return list(v[1:])
    if k == 1:
        return [v]
    raise ExtractionError(f"a tuple of {k} values was expected, got {v!r:.200}")


def _bindable(v):
    """What a local or a Yul-assigned Solidity variable holds: the underlying term (N1), pointers kept."""
    return strip(v)


def _lvalue_decls(n) -> set:
    out = set()
    if not isinstance(n, dict):
        return out
    if n.get("nodeType") == "Identifier" and isinstance(n.get("referencedDeclaration"), int):
        out.add(n["referencedDeclaration"])
    elif n.get("nodeType") == "TupleExpression":
        for c in n.get("components") or []:
            out |= _lvalue_decls(c)
    return out


def _external_ref(asm: dict | None, ident: dict):
    if asm is None:
        return None
    for r in asm.get("externalReferences") or []:
        if r.get("src") == ident.get("src"):
            return r
    return None


def _tuple_arity(ts: str) -> int:
    inner = ts[len("tuple("):-1]
    if not inner.strip():
        return 0
    depth, k = 0, 1
    for ch in inner:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        elif ch == "," and depth == 0:
            k += 1
    return k


def _cmp_constraint(c):
    """(atom term, op, k) for a comparison of one non-constant term with an integer (negations folded in), else None."""
    neg = False
    if isinstance(c, tuple) and c[:1] == ("!",):
        neg, c = True, c[1]
    if not (isinstance(c, tuple) and len(c) == 3 and c[0] in CMP_OPS):
        return None
    op, a, b = c
    if isinstance(a, int) and not isinstance(b, int):
        a, b = b, a
        op = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}.get(op, op)
    if isinstance(a, int) or not isinstance(b, int):
        return None
    if neg:
        op = {"==": "!=", "!=": "==", "<": ">=", "<=": ">", ">": "<=", ">=": "<"}[op]
    return a, op, b


def infeasible(cond: list) -> bool:
    """W9: a conjunct and its negation, a constant-false conjunct, or comparisons of one atom term with integer
    constants admitting no integer in [0, 2^256)."""
    seen = set()
    per: dict = {}
    for c in cond:
        if isinstance(c, int):
            if not _truth(c):
                return True
            continue
        seen.add(c)
        x = _cmp_constraint(c)
        if x is not None:
            per.setdefault(x[0], []).append((x[1], x[2]))
    for c in seen:
        if ("!", c) in seen:
            return True
    for cons in per.values():
        lo, hi, eqs, neqs = 0, MASK, set(), set()
        for op, k in cons:
            if op == "==":
                eqs.add(k)
            elif op == "!=":
                neqs.add(k)
            elif op == "<":
                hi = min(hi, k - 1)
            elif op == "<=":
                hi = min(hi, k)
            elif op == ">":
                lo = max(lo, k + 1)
            elif op == ">=":
                lo = max(lo, k)
        if eqs:
            if len(eqs) > 1:
                return True
            e = next(iter(eqs))
            if not (lo <= e <= hi) or e in neqs:
                return True
            continue
        if hi < lo:
            return True
        if hi - lo + 1 <= len({x for x in neqs if lo <= x <= hi}):
            return True
    return False


# ------------------------------------------------------------------------------------------------ the walk
class Walker:
    """All paths of one edge's walk (W8-W12), in walk order."""

    def __init__(self, index: Index, edge_name: str, spec: dict, entry: dict, max_paths: int, max_depth: int):
        self.index = index
        self.edge_name = edge_name
        self.spec = spec
        self.entry = entry
        self.sink = list(spec["sink"])
        self.max_paths = max_paths
        self.max_depth = max_depth

    def walk(self) -> list[PathResult]:
        out: list[PathResult] = []
        pending: list[list[int]] = [[]]
        while pending:
            script = pending.pop()
            run = Run(self, script)
            res = run.execute()
            out.append(res)
            if len(out) > self.max_paths:
                raise ExtractionError(f"edge {self.edge_name}: more than {self.max_paths} paths in one walk (W12)")
            for pos in run.new_forks:
                pending.append(run.decisions[:pos] + [1])
        return out
