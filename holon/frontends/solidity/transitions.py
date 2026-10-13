"""Transitions of one contract: storage families, guards, effects, cost terms, principal predicates, hash and commit
edges, and the coverage of every statement (I19; whitepaper §10.1 Solidity, §9.3 G8). The contract is the docstring of
tests_m2/test_extract_transitions.py (document) and tests_m2/test_coverage.py (coverage); I17's compile (W1), spans
(W2) and terms (W4) are reused from holon.frontends.solidity.{compile, ast}.

Inputs: the compiler's AST and storage layout and the source bytes, through a sidecar with "transitions":
{"contract", "commit_interfaces"}. Nothing here reads a fact document, a law or a result, and no name of a target
appears here: the contract and the commit interfaces come from the sidecar.

The walk. Every external or public FunctionDefinition the contract declares itself is an action. Its walk is a
structured symbolic execution of the body, depth first:
  * modifiers are inlined in order (a modifier's `_` walks the next modifier, then the body); internal, private,
    public and library-internal calls with a body are inlined (virtual calls dispatched against the contract's
    linearization), arguments evaluated left to right and bound by value (storage pointers by reference);
  * both branches of an if are walked (then before else) under the branch condition; a condition that folds to a
    constant walks only its branch; after the if, locals, storage and memory that differ are merged into conditional
    terms ["?", c, a, b]; a branch that always reverts contributes nothing to the merge; a branch that may leave by
    return, break or continue puts the condition under which control goes on into the context of what follows;
  * a loop is walked twice: a dry run, recording nothing, finds what its body changes; then the locals it changes
    become ["phi", <loop span>, <name>] (a pointer keeps its region with a phi offset), every storage family it writes
    becomes ["phi", <loop span>, ["storage", <family>]], every memory region it writes gets a ["loop", <span>] entry,
    and the body is walked once more under the loop condition, recording; after the loop the same phi values hold;
  * inline assembly is walked with I17's Yul subset (W7) plus sload, blobhash, YulIf and a few environment builtins;
    YulForLoop, YulSwitch, Yul functions and other builtins are not represented (debt "unsupported", the variables
    they assign havocked to ["unknown", <span>, <name>]).
The walk keeps a context: the conditions of the enclosing branches and loops (across inlined calls).

Terms (JSON arrays; ints are constants mod 2^256, folded with EVM semantics as in I17 W4):
  ["param", name]           an entry parameter          ["caller"]                 msg.sender, _msgSender(), caller()
  ["storage", name]         a state variable before the transaction (also the base of mapping/array/struct reads)
  ["map", base, key]        a mapping read              ["index", base, i]         an array or bytes element
  ["member", base, name]    a struct member             ["len", x]                 .length
  ["byte", x, k]            byte k of input bytes x     ["word", x, k]             the 32 bytes at offset k of the memory
                                                                                   copy of input bytes x (calldatacopy)
  ["call", "<I>.<f>", args...]   the result of an external call of function f declared in I (the receiver is not an
                            argument); low-level calls: ["call", "address.<call|staticcall|delegatecall|send|transfer>",
                            receiver, args...] (["value", v] last when it carries value); ["at", k, t] a component
  ["env", "<global>.<member>"]  block, msg (but sender) and tx members, gasleft; ["this"]; ["code", a]; ["balance", a]
  ["immutable", name]       ["blobhash", i]  ["blockhash", i]  ["sload", slot]  ["str", hex]
  ["keccak256", b] / ["sha256", b]   a hash of b: input bytes, an abi encoding ["abi.encode"|..., args...], or
                            ["slice", mem, offset, length] of a memory region
  ["mem", write...]         a memory region's writes in order: ["mstore", off, v], ["mstore8", off, v],
                            ["calldatacopy", off, x, from, n], ["loop", span], ["unknown", span]
  ["mload", mem, off]       a memory read not resolved to a write; ["ptr", stack, off] a pointer into the region
                            allocated (mload(0x40)) at that call stack
  ["store", base, [accessor...], v]   storage base after writing v at the path (["map", k], ["index", i],
                            ["member", n]); a later read of the same path is v, of a disjoint path the base's value
  ["?", c, a, b]            a conditional (merges and the conditional operator)
  ["phi", span, name]       a value at the head of the loop at span; ["unknown", span, name] a havocked value
  ["struct", name, [[member, v], ...]]  ["tuple", ...]
  [op, a, b] / ["!", a]     operators: I17's DSL ops (== != < <= > >= ! && || + - * / % & | ^ << >>), plus "trunc",
                            "~", "neg", "**"; context conjunctions are n-ary "&&".

Per action (document "actions", sorted by name):
  guards     every require, assert and revert reached (Solidity revert, revert E(...), Yul revert/invalid), one entry
             per span (the first reach of a depth-first walk: modifiers in order, then the body; then before else).
             kind "modifier" when reached inside a modifier's own code (including the calls it makes), else "require"
             (require, assert) or "revert". reason: the string literal, the custom error's name, else null. expr: the
             condition that must hold for the walk to pass the guard: a require's condition c, or
             ["||", ["!", K], c] under the context K; a revert's ["!", K] (0 when unconditional). Guards are checked
             in order; the transaction reverts at the first one whose expr is false (implicit reverts excepted).
  principal  the first of the action's modifiers whose own code reaches a require whose condition mentions
             ["caller"]; its predicate is that condition.
  effects    every storage write reached ({family, src}: the written state variable and the span of the assignment,
             ++/--, or delete), deduplicated, sorted by (src, family).
  cost       one term per Solidity loop reached whose body writes no storage: {loop: its span, iters}. iters comes
             from the loop header: for (i = a; i op N; i++ / i-- / i += k / i -= k / i = i +- k) with op one of
             < <= != (> >= != counting down), i not assigned in the body and N not changed by the loop; a while
             (v op N) whose body's only assignment of the local v is one such top-level step, counted the same way
             from v's value before the loop; otherwise ["unknown", span, "iterations"]. A count that may be
             negative is guarded (["?", ["<", a, N], ..., 0]); a loop with a break counts its header bound.
  edges      HASH: keccak256 (Solidity or Yul) and sha256 calls; COMMIT: blobhash (Solidity or Yul) and external calls
             of functions declared in an interface the sidecar's commit_interfaces names. {kind, fn, src}, first
             reach order, deduplicated.

Coverage (coverage_document): the statements are every Solidity Statement node inside the bodies of the actions and
of every function and modifier they reach (the bodies themselves excluded). A statement is extracted when the walk
used it for a guard, an effect, a cost term, an edge or a principal, when it is control flow (block, if, return,
break, continue, `_`) or an inlined call, or when it is local computation (a local's declaration or assignment,
memory writes) whose local is read by some walked statement or is a return variable. Debt entries ({src, kind,
detail}): external_call (an external call that is not a COMMIT edge), value_transfer (a call with value, send,
transfer), loop_storage_write (a loop whose body writes storage; detail: the families), unsupported (a statement or
Yul construct the walk does not represent, with its node type: an event emission, a YulForLoop, try, ...; the
statements nested in an unsupported statement count as that debt). A statement neither extracted nor debt, including
one the walk never reached (dead code), is unaccounted.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .. import ExtractionError, FACTS_VERSION
from .ast import Index, MASK, conversion_bits, fold as _fold, literal_value, type_string
from . import storage as STORAGE

TRANSITIONS_VERSION = "holon-frontend-solidity/0.2"
MAX_CALL_DEPTH = 24

STATEMENTS = frozenset({"Block", "UncheckedBlock", "PlaceholderStatement", "IfStatement", "TryStatement",
                        "WhileStatement", "DoWhileStatement", "ForStatement", "Continue", "Break", "Return", "Throw",
                        "EmitStatement", "RevertStatement", "VariableDeclarationStatement", "ExpressionStatement",
                        "InlineAssembly"})
LOOPS = frozenset({"ForStatement", "WhileStatement", "DoWhileStatement"})
EXTRACTED_TAGS = frozenset({"guard", "principal", "effect", "cost", "edge", "control", "inlined"})
LOW_LEVEL = ("call", "delegatecall", "staticcall", "send", "transfer")
YUL_PURE = {"add": "+", "sub": "-", "mul": "*", "div": "/", "mod": "%", "and": "&", "or": "|", "xor": "^",
            "eq": "==", "lt": "<", "gt": ">", "exp": "**"}
YUL_ENV = {"timestamp": ("env", "block.timestamp"), "number": ("env", "block.number"),
           "chainid": ("env", "block.chainid"), "callvalue": ("env", "msg.value"), "gas": ("env", "gasleft"),
           "origin": ("env", "tx.origin"), "gasprice": ("env", "tx.gasprice"), "coinbase": ("env", "block.coinbase"),
           "basefee": ("env", "block.basefee"), "blobbasefee": ("env", "block.blobbasefee"),
           "prevrandao": ("env", "block.prevrandao"), "calldatasize": ("env", "msg.data.length"),
           "caller": ("caller",), "address": ("this",)}

ASSUMPTIONS = {
    "A-env": ("Environment terms (storage before the transaction, block, msg and tx members, blobhash, results of "
              "external calls, sload) are free: every value of them is possible."),
    "A-implicit": ("Implicit reverts (checked arithmetic, array bounds, ABI decoding, failing external calls) are not "
                   "guards: only explicit require, assert and revert (and Yul revert/invalid) are."),
    "A-loop": ("A loop body is walked once at a generic iteration: what it changes is a phi term of the loop "
               "(locals, storage families, memory regions), a guard inside it holds at every iteration, and its cost "
               "term counts the header's bound."),
    "A-reentrancy": ("External calls do not change this contract's storage (no reentrancy): a storage read after an "
                     "external call is the value this contract last wrote, or the value before the transaction."),
    "A-span": ("One guard per span: a require or revert reached again (a second inlined call of the same function) "
               "keeps the expression of its first reach."),
}


# ------------------------------------------------------------------------------------------------ terms
def fold(op: str, *args):
    """I17's folding (W4), distributed over conditionals of pointers so that pointer arithmetic stays resolvable."""
    for i, a in enumerate(args):
        if is_ite(a) and has_ptr(a):
            return ite(a[1], fold(op, *(args[:i] + (a[2],) + args[i + 1:])),
                       fold(op, *(args[:i] + (a[3],) + args[i + 1:])))
    if op in ("+", "-") and len(args) == 2:
        a, b = args
        if is_ptr(a) and not is_ptr(b):
            return ("ptr", a[1], _fold(op, a[2], b))
        if op == "+" and is_ptr(b) and not is_ptr(a):
            return ("ptr", b[1], _fold("+", b[2], a))
        if op == "-" and is_ptr(a) and is_ptr(b) and a[1] == b[1]:
            return _fold("-", a[2], b[2])
        if b == 0 and not isinstance(a, int):   # x + 0 = x - 0 = x
            return a
        if op == "+" and a == 0 and not isinstance(b, int):
            return b
    return _fold(op, *args)


def is_ptr(t) -> bool:
    return isinstance(t, tuple) and len(t) == 3 and t[0] == "ptr"


def is_ite(t) -> bool:
    return isinstance(t, tuple) and len(t) == 4 and t[0] == "?"


def has_ptr(t) -> bool:
    if is_ptr(t):
        return True
    return is_ite(t) and (has_ptr(t[2]) or has_ptr(t[3]))


def ite(c, a, b):
    if a == b:
        return a
    if isinstance(c, int):
        return a if c else b
    return ("?", c, a, b)


def neg(c):
    if isinstance(c, int):
        return int(not c)
    if isinstance(c, tuple) and len(c) == 2 and c[0] == "!":
        return c[1]
    return ("!", c)


def conj(items) -> object:
    xs = []
    for x in items:
        if isinstance(x, int):
            if not x:
                return 0
            continue
        xs.append(x)
    if not xs:
        return 1
    return xs[0] if len(xs) == 1 else ("&&",) + tuple(xs)


def disj2(a, b):
    if a == 1 or b == 1:
        return 1
    if a == 0:
        return b
    if b == 0:
        return a
    return ("||", a, b)


def branch_falls(c, f1, f2):
    """The condition under which control goes on after `if (c) S1 else S2`, given S1's and S2's."""
    if f1 == f2:
        return f1
    if f1 == 1 and f2 == 0:
        return c
    if f1 == 0 and f2 == 1:
        return neg(c)
    if f2 == 1:
        return disj2(neg(c), f1)
    if f1 == 1:
        return disj2(c, f2)
    if f1 == 0:
        return conj([neg(c), f2])
    if f2 == 0:
        return conj([c, f1])
    return ("||", conj([c, f1]), conj([neg(c), f2]))


def mentions_caller(t) -> bool:
    if t == ("caller",):
        return True
    return isinstance(t, tuple) and any(mentions_caller(x) for x in t[1:])


@dataclass(frozen=True)
class Ref:
    """A storage location: a state variable and an access path of ("map", key), ("index", i), ("member", name)."""
    fam: str
    path: tuple = ()


def render(t):
    """A term as JSON (lists, ints, strings)."""
    if isinstance(t, bool):
        return int(t)
    if isinstance(t, int) or t is None or isinstance(t, str):
        return t
    if isinstance(t, Ref):
        return ["ref", t.fam, [render(list(a)) for a in t.path]]
    if isinstance(t, list):
        return [render(x) for x in t]
    if isinstance(t, tuple):
        h = t[0] if t else "tuple"
        if h == "store":
            return ["store", render(t[1]), [[a[0], render(a[1])] for a in t[2]], render(t[3])]
        if h == "ptr":
            return ["ptr", list(t[1][1]), render(t[2])]
        if h == "struct":
            return ["struct", t[1], [[m, render(v)] for m, v in zip(t[2], t[3])]]
        return [h] + [render(x) for x in t[1:]]
    raise ExtractionError(f"a value the document cannot hold: {t!r:.200}")


def _key(x) -> str:
    return json.dumps(x, sort_keys=True)


# ------------------------------------------------------------------------------------------------ frames and state
@dataclass
class Frame:
    fn: dict
    name: str
    vars: dict = field(default_factory=dict)
    zone: str = "body"                      # "modifier" inside a modifier's own code (and what it calls)
    mod_index: int | None = None            # the action modifier whose code this is (principal detection)
    is_action: bool = False
    returns: list = field(default_factory=list)   # [(local condition, value, storage, memory)]
    ctx_base: int = 0
    result: object = None
    placeholder: object = None
    yul: list = field(default_factory=list)
    asm: dict | None = None


@dataclass
class Snap:
    vars: dict
    yul: list
    storage: dict
    memory: dict


class Collector:
    """What the walks of every action of one contract record for coverage (shared by the actions)."""

    def __init__(self):
        self.tags: dict[int, set] = {}
        self.defs: dict[int, set] = {}
        self.reads: set = set()
        self.debt: dict = {}                # (src, kind, detail) -> None, first record order
        self.reached: dict[int, dict] = {}  # function / modifier id -> node
        self.covered_by_debt: set = set()


# ------------------------------------------------------------------------------------------------ the walk
class Walk:
    """The walk of one action (see the module docstring)."""

    def __init__(self, index: Index, contract: dict, action: dict, coll: Collector, commit: list[str]):
        self.ix = index
        self.contract = contract
        self.action = action
        self.coll = coll
        self.commit = set(commit)
        self.frames: list[Frame] = []
        self.calls: list[str] = []
        self.ctx: list = []
        self.storage: dict = {}
        self.memory: dict = {}
        self.exit: str | None = None
        self.recording = True
        self.stmts: list[int] = []
        self.regions = 0
        self.guards: dict = {}
        self.effects: dict = {}
        self.cost: dict = {}
        self.edges: dict = {}
        self.principal: dict = {}
        self.written: list[str] = []

    # -- bookkeeping
    @property
    def frame(self) -> Frame:
        return self.frames[-1]

    def span(self, node: dict) -> str:
        return self.ix.span(node["src"])

    def tag(self, t: str, defs=()) -> None:
        if not self.recording or not self.stmts or self.stmts[-1] is None:
            return
        sid = self.stmts[-1]
        self.coll.tags.setdefault(sid, set()).add(t)
        if defs:
            self.coll.defs.setdefault(sid, set()).update(defs)

    def read_decl(self, decl) -> None:
        if self.recording:
            self.coll.reads.add(decl)

    def debt(self, kind: str, detail: str, node: dict) -> None:
        if not self.recording:
            return
        self.coll.debt.setdefault((self.span(node), kind, detail), None)
        self.tag("debt")

    def edge(self, kind: str, fn: str, node: dict) -> None:
        if not self.recording:
            return
        self.edges.setdefault((kind, fn, self.span(node)), None)
        self.tag("edge")

    def reach(self, fn: dict) -> None:
        if self.recording:
            self.coll.reached.setdefault(fn["id"], fn)

    def snapshot(self) -> Snap:
        f = self.frame
        return Snap(dict(f.vars), [dict(s) for s in f.yul], dict(self.storage), dict(self.memory))

    def restore(self, s: Snap) -> None:
        f = self.frame
        f.vars = dict(s.vars)
        f.yul = [dict(x) for x in s.yul]
        self.storage = dict(s.storage)
        self.memory = dict(s.memory)

    def merge(self, c, a: Snap, b: Snap, keys: Snap) -> None:
        """The state after a two-way branch on c whose branches ended in a and b (keys: the state before it)."""
        f = self.frame
        f.vars = {k: ite(c, a.vars.get(k, v), b.vars.get(k, v)) for k, v in keys.vars.items()}
        f.yul = []
        for i, scope in enumerate(keys.yul):
            sa = a.yul[i] if i < len(a.yul) else {}
            sb = b.yul[i] if i < len(b.yul) else {}
            f.yul.append({k: ite(c, sa.get(k, v), sb.get(k, v)) for k, v in scope.items()})
        self.storage = merge_storage(c, a.storage, b.storage)
        self.memory = merge_memory(c, a.memory, b.memory)

    # -- the action
    def run(self) -> dict:
        fn = self.action
        f = Frame(fn=fn, name=self.ix.fn_name(fn), is_action=True)
        for p in fn["parameters"]["parameters"]:
            f.vars[p["id"]] = ("param", p["name"])
        for p in fn["returnParameters"]["parameters"]:
            f.vars[p["id"]] = 0
        self.reach(fn)
        self.chain_function(fn, f)
        return self.result()

    def result(self) -> dict:
        mods = [m["modifierName"]["name"] for m in self.action.get("modifiers") or []
                if m.get("kind", "modifierInvocation") == "modifierInvocation"]
        principal = None
        if self.principal:
            i = min(self.principal)
            principal = {"modifier": mods[i], "predicate": render(self.principal[i])}
        effects = sorted(({"family": fam, "src": src} for fam, src in self.effects), key=lambda e: (e["src"],
                                                                                                    e["family"]))
        sel = self.action.get("functionSelector")
        return {
            "name": self.action.get("name") or self.action.get("kind"),
            "selector": ("0x" + sel) if sel else None,
            "src": self.span(self.action),
            "modifiers": mods,
            "principal": principal,
            "guards": list(self.guards.values()),
            "effects": effects,
            "cost": {"terms": [{"loop": span, "iters": render(it)} for span, it in self.cost.items()]},
            "edges": [{"kind": k, "fn": fn, "src": src} for (k, fn, src) in self.edges],
        }

    def chain_function(self, fn: dict, f: Frame):
        """Walk fn's modifiers and body in the frame f (pushed here); returns fn's result."""
        mods = [m for m in fn.get("modifiers") or [] if m.get("kind", "modifierInvocation") == "modifierInvocation"]
        self.frames.append(f)
        try:
            self._chain(fn, f, mods, 0)
        finally:
            self.frames.pop()
        return f.result

    def _chain(self, fn: dict, f: Frame, mods: list, i: int) -> None:
        if i == len(mods):
            f.returns = []
            f.ctx_base = len(self.ctx)
            falls = self.block(fn["body"])
            f.result = self.finish(f, falls)
            return
        m = mods[i]
        mdef = self._modifier(m)
        if mdef is None or not mdef.get("body"):
            self.stmts.append(m["id"])
            try:
                self.debt("unsupported", "ModifierInvocation", m)
            finally:
                self.stmts.pop()
            self._chain(fn, f, mods, i + 1)
            return
        args = [self.ev(a) for a in m.get("arguments") or []]
        mf = Frame(fn=mdef, name=self.ix.fn_name(mdef), zone="modifier",
                   mod_index=(i if f.is_action else f.mod_index))
        for p, v in zip(mdef["parameters"]["parameters"], args):
            mf.vars[p["id"]] = self.bind(p, v)
        mf.placeholder = (fn, f, mods, i + 1)
        self.reach(mdef)
        self.frames.append(mf)
        try:
            mf.returns = []
            mf.ctx_base = len(self.ctx)
            falls = self.block(mdef["body"])
            self.finish(mf, falls)
        finally:
            self.frames.pop()

    def _modifier(self, m: dict) -> dict | None:
        d = self.ix.nodes.get(m["modifierName"].get("referencedDeclaration"))
        if d is None or d.get("nodeType") != "ModifierDefinition":
            return None
        if d.get("virtual") or d.get("overrides"):
            for cid in self.contract.get("linearizedBaseContracts", []):
                for x in (self.ix.nodes.get(cid) or {}).get("nodes", []):
                    if x.get("nodeType") == "ModifierDefinition" and x.get("name") == d["name"] and x.get("body"):
                        return x
        return d

    def placeholder(self) -> None:
        fn, f, mods, j = self.frame.placeholder
        self.frames.append(f)
        try:
            self._chain(fn, f, mods, j)
        finally:
            self.frames.pop()

    def finish(self, f: Frame, falls):
        """The end of a body: merge its returns and its fall-through into the state; the body's value."""
        entries = list(f.returns)
        if self.exit is None:
            rets = f.fn.get("returnParameters", {}).get("parameters", []) if f.fn.get("nodeType") == \
                "FunctionDefinition" else []
            vals = [f.vars.get(p["id"], 0) for p in rets]
            v = None if not vals else (vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals))
            entries.append((falls, v, dict(self.storage), dict(self.memory)))
        f.returns = []
        if not entries:
            self.exit = "revert"
            return None
        self.exit = None
        _, v, st, mem = entries[-1]
        for c, vi, sti, memi in reversed(entries[:-1]):
            v = ite_value(c, vi, v)
            st = merge_storage(c, sti, st)
            mem = merge_memory(c, memi, mem)
        self.storage, self.memory = st, mem
        return v

    # -- statements
    def block(self, n: dict):
        base = len(self.ctx)
        falls = 1
        try:
            for s in n.get("statements") or []:
                if self.exit:
                    break
                f = self.stmt(s)
                if self.exit:
                    break
                if f != 1:
                    self.ctx.append(f)
                    falls = conj([falls, f])
        finally:
            del self.ctx[base:]
        return falls

    def stmt(self, n: dict):
        self.stmts.append(n["id"])
        try:
            return self._stmt(n)
        finally:
            self.stmts.pop()

    def _stmt(self, n: dict):
        nt = n["nodeType"]
        if nt in ("Block", "UncheckedBlock"):
            self.tag("control")
            return self.block(n)
        if nt == "ExpressionStatement":
            self.ev(n["expression"])
            return 1
        if nt == "VariableDeclarationStatement":
            self.var_decl(n)
            return 1
        if nt == "IfStatement":
            self.tag("control")
            return self.if_stmt(n)
        if nt == "Return":
            self.tag("control")
            return self.ret(n)
        if nt in ("Break", "Continue"):
            self.tag("control")
            self.exit = "break" if nt == "Break" else "continue"
            return 0
        if nt == "PlaceholderStatement":
            self.tag("control")
            if self.frame.placeholder is None:
                self.debt("unsupported", nt, n)
                return 1
            self.placeholder()
            return 1
        if nt == "EmitStatement":   # not represented: debt; what its arguments compute counts as feeding it
            self.debt("unsupported", nt, n)
            call = n["eventCall"]
            self.stmts.append(None)
            try:
                for a in call.get("arguments") or []:
                    self.val(self.ev(a))
            finally:
                self.stmts.pop()
            return 1
        if nt == "RevertStatement":
            call = n["errorCall"]
            for a in call.get("arguments") or []:
                self.val(self.ev(a))
            name = call["expression"].get("name") or call["expression"].get("memberName")
            self.guard("revert", n, None, name)
            self.exit = "revert"
            return 1
        if nt == "InlineAssembly":
            self.assembly(n)
            return 1
        if nt in LOOPS:
            return self.loop(n)
        self.unsupported(n, nt)
        return 1

    def unsupported(self, n: dict, what: str) -> None:
        """A statement the walk does not represent: debt; the locals it may assign are havocked; the statements
        nested in it count as that debt; every memory region gets an ["unknown", span] entry."""
        self.debt("unsupported", what, n)
        self.havoc_memory(n)
        if self.recording:
            stack = [n]
            while stack:
                x = stack.pop()
                if isinstance(x, dict):
                    if x is not n and x.get("nodeType") in STATEMENTS and isinstance(x.get("id"), int):
                        self.coll.covered_by_debt.add(x["id"])
                    stack.extend(v for k, v in x.items() if k != "AST" and isinstance(v, (dict, list)))
                elif isinstance(x, list):
                    stack.extend(x)
        self.havoc(n)

    def havoc_memory(self, n: dict) -> None:
        span = self.span(n)
        for r in list(self.memory):
            self.memory[r] = mem_append(self.memory[r], ("unknown", span))

    def havoc(self, n: dict) -> None:
        span = self.span(n)
        stack = [n]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                nt = x.get("nodeType")
                if nt == "Assignment":
                    for d in _lvalue_decls(x.get("leftHandSide")):
                        self._havoc_decl(d, span)
                elif nt == "UnaryOperation" and x.get("operator") in ("++", "--", "delete"):
                    for d in _lvalue_decls(x.get("subExpression")):
                        self._havoc_decl(d, span)
                elif nt == "YulAssignment":
                    for v in x.get("variableNames", []):
                        self._havoc_yul(v, span)
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(x)

    def _havoc_decl(self, d, span: str) -> None:
        if d in self.frame.vars:
            node = self.ix.nodes.get(d) or {}
            self.frame.vars[d] = ("unknown", span, node.get("name", ""))

    def _havoc_yul(self, ident: dict, span: str) -> None:
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                scope[name] = ("unknown", span, name)
                return
        ref = _external_ref(self.frame.asm, ident)
        if ref is not None:
            self._havoc_decl(ref["declaration"], span)

    def var_decl(self, n: dict) -> None:
        decls = n.get("declarations") or []
        ids = [d["id"] for d in decls if d is not None]
        self.tag("local", ids)
        if n.get("initialValue") is None:
            for d in decls:
                if d is not None:
                    self.frame.vars[d["id"]] = 0
            return
        v = self.ev(n["initialValue"])
        if len(decls) == 1:
            if decls[0] is not None:
                self.frame.vars[decls[0]["id"]] = self.bind(decls[0], v)
            return
        for d, x in zip(decls, components(v, len(decls))):
            if d is not None:
                self.frame.vars[d["id"]] = self.bind(d, x)

    def bind(self, decl: dict, v):
        """A value bound to a parameter or local: storage pointers keep their location, anything else its value."""
        if isinstance(v, Ref) and decl.get("storageLocation") == "storage":
            return v
        return self.val(v)

    def if_stmt(self, n: dict):
        c = self.val(self.ev(n["condition"]))
        if isinstance(c, int):
            if c:
                return self.stmt(n["trueBody"])
            return self.stmt(n["falseBody"]) if n.get("falseBody") is not None else 1
        before = self.snapshot()
        self.ctx.append(c)
        try:
            f1 = self.stmt(n["trueBody"])
        finally:
            self.ctx.pop()
        e1, s1 = self.exit, self.snapshot()
        self.exit = None
        self.restore(before)
        f2 = 1
        if n.get("falseBody") is not None:
            self.ctx.append(neg(c))
            try:
                f2 = self.stmt(n["falseBody"])
            finally:
                self.ctx.pop()
        e2, s2 = self.exit, self.snapshot()
        self.exit = None
        if e1 and e2:
            self.restore(s2)
            self.exit = "revert" if e1 == e2 == "revert" else ("return" if "return" in (e1, e2) else
                                                                (e1 if e1 != "revert" else e2))
            return 0
        if e1:
            self.restore(s2)
        elif e2:
            self.restore(s1)
        else:
            self.merge(c, s1, s2, before)
        g1 = 1 if e1 == "revert" else (0 if e1 else f1)
        g2 = 1 if e2 == "revert" else (0 if e2 else f2)
        return branch_falls(c, g1, g2)

    def ret(self, n: dict):
        f = self.frame
        v = None
        if n.get("expression") is not None:
            v = self.ev(n["expression"])
            rets = f.fn.get("returnParameters", {}).get("parameters", []) if f.fn.get("nodeType") == \
                "FunctionDefinition" else []
            if len(rets) == 1:
                v = self.bind(rets[0], v)
            elif isinstance(v, tuple) and v[:1] == ("tuple",):
                v = ("tuple",) + tuple(self.bind(p, x) for p, x in zip(rets, v[1:]))
            else:
                v = self.val(v)
        else:
            rets = f.fn.get("returnParameters", {}).get("parameters", []) if f.fn.get("nodeType") == \
                "FunctionDefinition" else []
            vals = [f.vars.get(p["id"], 0) for p in rets]
            v = None if not vals else (vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals))
        f.returns.append((conj(self.ctx[f.ctx_base:]), v, dict(self.storage), dict(self.memory)))
        self.exit = "return"
        return 0

    # -- guards
    def guard(self, kind: str, node: dict, cond, reason) -> None:
        if not self.recording:
            return
        self.tag("guard")
        span = self.span(node)
        f = self.frame
        if span not in self.guards:
            k = conj(self.ctx)
            if kind == "revert":
                expr = neg(k)
            else:
                expr = cond if k == 1 else disj2(neg(k), cond)
            self.guards[span] = {"src": span, "kind": "modifier" if f.zone == "modifier" else kind,
                                 "reason": reason, "expr": render(expr)}
        if kind == "require" and f.zone == "modifier" and f.mod_index is not None and mentions_caller(cond):
            if f.mod_index not in self.principal:
                self.principal[f.mod_index] = cond
            self.tag("principal")

    # -- loops
    def loop(self, n: dict):
        span = self.span(n)
        nt = n["nodeType"]
        if nt == "ForStatement" and n.get("initializationExpression") is not None:
            self.stmt(n["initializationExpression"])
            if self.exit:
                return 1
        bound = self.loop_bound(n, span)
        before = self.snapshot()
        nret, nwritten = len(self.frame.returns), len(self.written)
        rec, exit0 = self.recording, self.exit
        self.recording = False
        try:
            self.loop_body(n)
        finally:
            after = self.snapshot()
            self.recording, self.exit = rec, exit0
            self.restore(before)
            del self.frame.returns[nret:]
            fams = sorted(set(self.written[nwritten:]))
            del self.written[nwritten:]
        changed = [k for k, v in before.vars.items() if after.vars.get(k) != v]
        regions = sorted((r for r in after.memory if r in before.memory and after.memory[r] != before.memory[r]),
                         key=lambda r: r[0])
        for k in changed:
            self.frame.vars[k] = phi(before.vars[k], span, (self.ix.nodes.get(k) or {}).get("name", str(k)))
        for i, scope in enumerate(before.yul):
            for name, v in scope.items():
                if i < len(after.yul) and after.yul[i].get(name) != v:
                    self.frame.yul[i][name] = phi(v, span, name)
        for fam in fams:
            self.storage[fam] = ("phi", span, ("storage", fam))
        for r in regions:
            self.memory[r] = mem_append(self.memory[r], ("loop", span))
        if fams:
            self.debt("loop_storage_write", ", ".join(fams), n)
        else:
            self.tag("cost")
            if self.recording:
                self.cost.setdefault(span, bound if bound is not None else ("unknown", span, "iterations"))
        phis = self.snapshot()
        try:
            self.loop_body(n)
        finally:
            self.exit = None
            self.restore(phis)
        return 1

    def loop_body(self, n: dict) -> None:
        nt = n["nodeType"]
        base = len(self.ctx)
        try:
            if nt == "DoWhileStatement":
                f = self.stmt(n["body"])
                if self.exit in ("break", "continue"):
                    self.exit = None
                if not self.exit:
                    if f != 1:
                        self.ctx.append(f)
                    self.val(self.ev(n["condition"]))
                return
            c = self.val(self.ev(n["condition"])) if n.get("condition") is not None else 1
            if not isinstance(c, int):
                self.ctx.append(c)
            elif not c:
                return
            f = self.stmt(n["body"])
            if self.exit in ("break", "continue"):
                self.exit = None
            if nt == "ForStatement" and n.get("loopExpression") is not None and not self.exit:
                if f != 1:
                    self.ctx.append(f)
                self.stmt(n["loopExpression"])
                if self.exit in ("break", "continue"):
                    self.exit = None
        finally:
            del self.ctx[base:]

    def loop_bound(self, n: dict, span: str):
        """The iteration count of a loop from its header (module docstring), or None."""
        nt = n["nodeType"]
        body = n.get("body") or {}
        rec = self.recording
        self.recording = False
        try:
            if nt == "ForStatement":
                return self._for_bound(n, body)
            if nt == "WhileStatement":
                return self._while_bound(n, body)
            return None
        finally:
            self.recording = rec

    def _for_bound(self, n: dict, body: dict):
        init = n.get("initializationExpression") or {}
        ivar = None
        if init.get("nodeType") == "VariableDeclarationStatement" and len(init.get("declarations") or []) == 1 \
                and init.get("initialValue") is not None and init["declarations"][0] is not None:
            ivar = init["declarations"][0]["id"]
        elif init.get("nodeType") == "ExpressionStatement":
            e = init["expression"]
            if e.get("nodeType") == "Assignment" and e.get("operator") == "=" and \
                    e["leftHandSide"].get("nodeType") == "Identifier":
                ivar = e["leftHandSide"].get("referencedDeclaration")
        if ivar is None or ivar not in self.frame.vars:
            return None
        a = self.frame.vars[ivar]
        cond = n.get("condition") or {}
        if cond.get("nodeType") != "BinaryOperation":
            return None
        op, lhs, rhs = cond["operator"], cond["leftExpression"], cond["rightExpression"]
        if _is_ident(lhs, ivar) and not _mentions_decl(rhs, ivar):
            bound_node = rhs
        elif _is_ident(rhs, ivar) and not _mentions_decl(lhs, ivar):
            bound_node, op = lhs, {"<": ">", "<=": ">=", ">": "<", ">=": "<="}.get(op, op)
        else:
            return None
        step = _step(n.get("loopExpression"), ivar)
        if step is None or _assigns(body, ivar) or self._changed_in(n, bound_node):
            return None
        bound = self.val(self.ev(bound_node))
        return count(op, a, bound, step)

    def _while_bound(self, n: dict, body: dict):
        """while (v op E) whose body's only assignment of the local v is one top-level step (v++, v--, v += k,
        v -= k, v = v +- k): counted like the for loop from v's value before the loop."""
        cond = n.get("condition") or {}
        if cond.get("nodeType") != "BinaryOperation":
            return None
        op, lhs, rhs = cond["operator"], cond["leftExpression"], cond["rightExpression"]
        flip = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        if lhs.get("nodeType") == "Identifier" and lhs.get("referencedDeclaration") in self.frame.vars \
                and not _mentions_decl(rhs, lhs.get("referencedDeclaration")):
            d, bound_node = lhs["referencedDeclaration"], rhs
        elif rhs.get("nodeType") == "Identifier" and rhs.get("referencedDeclaration") in self.frame.vars \
                and not _mentions_decl(lhs, rhs.get("referencedDeclaration")):
            d, bound_node, op = rhs["referencedDeclaration"], lhs, flip.get(op, op)
        else:
            return None
        stmts = body.get("statements") if body.get("nodeType") in ("Block", "UncheckedBlock") else [body]
        steps = [(s, _step(s, d)) for s in stmts or [] if s.get("nodeType") == "ExpressionStatement"]
        steps = [(s, k) for s, k in steps if k is not None]
        if len(steps) != 1 or _assigns(body, d, skip=steps[0][0]["expression"]["id"]) \
                or self._changed_in(n, bound_node):
            return None
        bound = self.val(self.ev(bound_node))
        return count(op, self.frame.vars[d], bound, steps[0][1])

    def _changed_in(self, loop: dict, expr: dict) -> bool:
        """Whether the loop may change something expr reads: a local it assigns, or a state variable it names."""
        decls = _identifiers(expr)
        for d in decls:
            node = self.ix.nodes.get(d) or {}
            if node.get("stateVariable") and not node.get("constant"):
                if _writes_state(loop, self.ix, node.get("name")):
                    return True
            elif _assigns(loop, d):
                return True
        return False

    # -- expressions
    def val(self, v):
        """The value of an evaluation result: a storage location is read."""
        if isinstance(v, Ref):
            return self.read(v)
        return v

    def read(self, r: Ref):
        base = self.storage.get(r.fam, ("storage", r.fam))
        return resolve(base, r.path)

    def write(self, r: Ref, v, node: dict) -> None:
        v = self.val(v)
        cur = self.storage.get(r.fam, ("storage", r.fam))
        if not r.path:
            new = ("store", ("storage", r.fam), (), v)
        else:
            if isinstance(cur, tuple) and cur[:1] == ("store",) and cur[2] == r.path:
                cur = cur[1]
            new = ("store", cur, r.path, v)
        self.storage[r.fam] = new
        self.written.append(r.fam)    # every write, recorded or not (a loop's dry run reads it)
        if self.recording:
            self.effects.setdefault((r.fam, self.span(node)), None)
            self.tag("effect")

    def ev(self, n: dict):
        nt = n["nodeType"]
        if nt == "Literal":
            return literal_value(n)
        if nt == "Identifier":
            return self.identifier(n)
        if nt == "MemberAccess":
            return self.member(n)
        if nt == "IndexAccess":
            return self.index_access(n)
        if nt == "IndexRangeAccess":
            base = self.val(self.ev(n["baseExpression"]))
            lo = self.val(self.ev(n["startExpression"])) if n.get("startExpression") else 0
            hi = self.val(self.ev(n["endExpression"])) if n.get("endExpression") else ("len", base)
            return ("range", base, lo, hi)
        if nt == "BinaryOperation":
            a = self.val(self.ev(n["leftExpression"]))
            b = self.val(self.ev(n["rightExpression"]))
            return fold(n["operator"], a, b)
        if nt == "UnaryOperation":
            return self.unary(n)
        if nt == "Conditional":
            c = self.val(self.ev(n["condition"]))
            if isinstance(c, int):
                return self.val(self.ev(n["trueExpression"] if c else n["falseExpression"]))
            self.ctx.append(c)
            try:
                a = self.val(self.ev(n["trueExpression"]))
            finally:
                self.ctx.pop()
            self.ctx.append(neg(c))
            try:
                b = self.val(self.ev(n["falseExpression"]))
            finally:
                self.ctx.pop()
            return ite(c, a, b)
        if nt == "TupleExpression":
            if n.get("isInlineArray"):
                return ("array",) + tuple(self.val(self.ev(c)) for c in n.get("components") or [])
            comps = n.get("components") or []
            vals = [self.ev(c) if c is not None else None for c in comps]
            return vals[0] if len(vals) == 1 else ("tuple",) + tuple(vals)
        if nt == "FunctionCall":
            return self.call(n)
        if nt == "Assignment":
            return self.assign(n)
        if nt == "ElementaryTypeNameExpression":
            return ("type", type_string(n))
        self.unsupported_expr(n, nt)
        return ("unknown", self.span(n), nt)

    def unsupported_expr(self, n: dict, what: str) -> None:
        self.debt("unsupported", what, n)
        self.havoc(n)

    def identifier(self, n: dict):
        ref = n.get("referencedDeclaration")
        name = n.get("name")
        if ref in self.frame.vars:
            self.read_decl(ref)
            return self.frame.vars[ref]
        if ref is None or ref < 0:
            if name in ("msg", "block", "tx", "abi", "this", "super", "bytes", "string"):
                return ("this",) if name == "this" else ("global", name)
            if name == "now":
                return ("env", "block.timestamp")
            return ("global", name)
        d = self.ix.nodes.get(ref)
        if d is None:
            return ("unknown", self.span(n), name)
        nt = d.get("nodeType")
        if nt == "VariableDeclaration":
            if d.get("constant"):
                v = fold_constant(self.ix, d)
                return v if v is not None else ("constant", name)
            if d.get("stateVariable"):
                if d.get("mutability") == "immutable":
                    return ("immutable", name)
                return Ref(name)
            return ("unknown", self.span(n), name)
        return ("decl", ref)

    def member(self, n: dict):
        ref = n.get("referencedDeclaration")
        d = self.ix.nodes.get(ref) if isinstance(ref, int) and ref >= 0 else None
        name = n["memberName"]
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("constant"):
            v = fold_constant(self.ix, d)
            return v if v is not None else ("constant", d.get("name"))
        if d is not None and d.get("nodeType") == "EnumValue":
            enum = self.ix.nodes.get(d.get("scope")) or {}
            members = [m.get("id") for m in enum.get("members", [])]
            return members.index(d["id"]) if d["id"] in members else ("enum", name)
        if d is not None and d.get("nodeType") in ("FunctionDefinition", "EventDefinition", "ErrorDefinition"):
            return ("decl", ref)
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("stateVariable"):
            return ("immutable", d["name"]) if d.get("mutability") == "immutable" else Ref(d["name"])
        base_node = n["expression"]
        if base_node.get("nodeType") == "FunctionCall" and (base_node.get("expression") or {}).get("name") == "type":
            return self._meta_member(base_node, name)
        base = self.ev(base_node)
        if isinstance(base, tuple) and base[:1] == ("global",):
            g = base[1]
            if g == "msg" and name == "sender":
                return ("caller",)
            if g in ("msg", "block", "tx"):
                return ("env", f"{g}.{name}")
            return ("global", f"{g}.{name}")
        if isinstance(base, Ref):
            if name == "length":
                return ("len", self.read(base))
            return Ref(base.fam, base.path + (("member", name),))
        if isinstance(base, tuple) and base[:1] == ("struct",):
            members, values = base[2], base[3]
            return values[members.index(name)] if name in members else ("member", base, name)
        bts = type_string(base_node)
        if name == "length":
            return ("len", base)
        if bts in ("address", "address payable") or bts.startswith("contract "):
            if name == "code":
                return ("code", base)
            if name == "balance":
                return ("balance", base)
            if name == "codehash":
                return ("codehash", base)
        return ("member", base, name)

    def _meta_member(self, call: dict, name: str):
        args = call.get("arguments") or []
        ts = type_string(args[0]) if args else ""
        m = re.fullmatch(r"type\((u?int)(\d*)\)", ts)
        if m:
            b = int(m.group(2) or 256)
            if m.group(1) == "uint":
                return {"max": (1 << b) - 1, "min": 0}.get(name, ("type", ts, name))
            return {"max": (1 << (b - 1)) - 1, "min": (-(1 << (b - 1))) & MASK}.get(name, ("type", ts, name))
        return ("type", ts, name)

    def index_access(self, n: dict):
        base = self.ev(n["baseExpression"])
        idx = self.val(self.ev(n["indexExpression"])) if n.get("indexExpression") is not None else None
        bts = type_string(n["baseExpression"])
        if isinstance(base, Ref):
            return Ref(base.fam, base.path + ((("map" if bts.startswith("mapping") else "index"), idx),))
        if (bts == "bytes" or bts.startswith("bytes ")) and isinstance(idx, int):
            return ("byte", base, idx)
        return ("index", base, idx)

    def unary(self, n: dict):
        op = n["operator"]
        sub = n["subExpression"]
        if op in ("++", "--"):
            target = self.ev(sub)
            old = self.val(target)
            new = fold("+" if op == "++" else "-", old, 1)
            self.store(sub, target, new, n)
            return new if n.get("prefix") else old
        if op == "delete":
            target = self.ev(sub)
            self.store(sub, target, 0, n)
            return ("tuple",)
        a = self.val(self.ev(sub))
        return fold({"-": "neg"}.get(op, op), a)

    def assign(self, n: dict):
        op = n.get("operator", "=")
        v = self.val(self.ev(n["rightHandSide"]))
        lhs = n["leftHandSide"]
        if lhs.get("nodeType") == "TupleExpression":
            comps = lhs.get("components") or []
            for c, x in zip(comps, components(v, len(comps))):
                if c is not None:
                    self.store(c, self.ev(c), x, n)
            return v
        target = self.ev(lhs)
        if op != "=":
            v = fold(op[:-1], self.val(target), v)
        self.store(lhs, target, v, n)
        return v

    def store(self, lhs: dict, target, v, node: dict) -> None:
        if isinstance(target, Ref):
            self.write(target, v, node)
            return
        if lhs.get("nodeType") == "Identifier":
            ref = lhs.get("referencedDeclaration")
            if ref in self.frame.vars or _is_local(self.ix, ref):
                d = self.ix.nodes.get(ref) or {}
                self.frame.vars[ref] = self.bind(d, v)
                self.tag("local", [ref])
                return
        if lhs.get("nodeType") in ("IndexAccess", "MemberAccess"):
            root = _root_decl(lhs)
            if root in self.frame.vars:   # a write into a memory struct or array held by a local
                self.frame.vars[root] = ("update", self.frame.vars[root], self.val(target) if not isinstance(
                    target, Ref) else target, self.val(v))
                self.tag("local", [root])
                return
        self.unsupported_expr(node, "Assignment")

    # -- calls
    def call(self, n: dict):
        kind = n.get("kind")
        args = n.get("arguments") or []
        callee = n["expression"]
        opts = {}
        if callee.get("nodeType") == "FunctionCallOptions":
            for name, o in zip(callee.get("names") or [], callee.get("options") or []):
                opts[name] = self.val(self.ev(o))
            callee = callee["expression"]
        if kind == "typeConversion":
            if len(args) != 1:
                self.unsupported_expr(n, "FunctionCall")
                return ("unknown", self.span(n), "conversion")
            v = self.val(self.ev(args[0]))
            return convert(v, type_string(args[0]), type_string(n))
        if kind == "structConstructorCall":
            vals = tuple(self.val(self.ev(a)) for a in args)
            sd = self.ix.nodes.get(callee.get("referencedDeclaration")) or {}
            members = [m.get("name") for m in sd.get("members", [])]
            names = n.get("names") or []
            if names:
                by = dict(zip(names, vals))
                vals = tuple(by.get(m, 0) for m in members)
            return ("struct", sd.get("name", ""), tuple(members), vals)
        if callee.get("nodeType") == "Identifier" and (callee.get("referencedDeclaration") or 0) < 0:
            return self.builtin(callee.get("name"), n, args)
        if callee.get("nodeType") == "MemberAccess":
            base_node = callee["expression"]
            if base_node.get("nodeType") == "Identifier" and (base_node.get("referencedDeclaration") or 0) < 0 \
                    and base_node.get("name") in ("abi", "bytes", "string"):
                vals = [self.val(self.ev(a)) for a in args]
                return (f"{base_node['name']}.{callee['memberName']}",) + tuple(vals)
        target = self.ix.nodes.get(callee.get("referencedDeclaration")) if callee.get("nodeType") in (
            "Identifier", "MemberAccess") else None
        cts = type_string(callee)
        low = callee.get("nodeType") == "MemberAccess" and callee.get("memberName") in LOW_LEVEL and target is None
        if " external" in cts or low:
            return self.external(n, callee, target, args, opts, low)
        if callee.get("nodeType") == "MemberAccess" and target is None and callee.get("memberName") in ("push", "pop"):
            base = self.ev(callee["expression"])
            vals = [self.val(self.ev(a)) for a in args]
            if isinstance(base, Ref):
                self.write(base, (callee["memberName"], self.read(base)) + tuple(vals), n)
                return ("tuple",)
        if target is None or target.get("nodeType") != "FunctionDefinition":
            for a in args:
                self.val(self.ev(a))
            self.unsupported_expr(n, "FunctionCall")
            return results(n, ("unknown", self.span(n), "call"))
        target = self.dispatch(target, callee)
        arg_nodes = list(args)
        if callee.get("nodeType") == "MemberAccess" and len(arg_nodes) + 1 == len(target["parameters"]["parameters"]) \
                and not type_string(callee["expression"]).startswith("type("):
            arg_nodes = [callee["expression"]] + arg_nodes   # a bound library call x.f(y)
        if not target.get("body") or not target.get("implemented", True) \
                or len(self.calls) + 1 > MAX_CALL_DEPTH or any(f.fn["id"] == target["id"] for f in self.frames):
            for a in arg_nodes:
                self.val(self.ev(a))
            self.unsupported_expr(n, "FunctionCall")
            return results(n, ("unknown", self.span(n), target.get("name", "call")))
        return self.inline(target, arg_nodes, n)

    def dispatch(self, target: dict, callee: dict) -> dict:
        """Virtual dispatch of a plain internal call against the contract's linearization."""
        if callee.get("nodeType") != "Identifier" or not target.get("virtual") and not target.get("overrides"):
            return target
        sig = [type_string(p) for p in target["parameters"]["parameters"]]
        for cid in self.contract.get("linearizedBaseContracts", []):
            for x in (self.ix.nodes.get(cid) or {}).get("nodes", []):
                if x.get("nodeType") == "FunctionDefinition" and x.get("name") == target.get("name") \
                        and [type_string(p) for p in x["parameters"]["parameters"]] == sig and x.get("body"):
                    return x
        return target

    def inline(self, target: dict, arg_nodes: list, call_node: dict):
        caller = self.frame
        vals = [self.ev(a) for a in arg_nodes]
        self.tag("inlined")
        f = Frame(fn=target, name=self.ix.fn_name(target), zone=caller.zone, mod_index=caller.mod_index)
        for p, v in zip(target["parameters"]["parameters"], vals):
            f.vars[p["id"]] = self.bind(p, v)
        for p in target["returnParameters"]["parameters"]:
            f.vars[p["id"]] = 0
        self.reach(target)
        self.calls.append(self.span(call_node))
        try:
            v = self.chain_function(target, f)
        finally:
            self.calls.pop()
        if v is None:
            return ("tuple",)
        return v

    def external(self, n: dict, callee: dict, target: dict | None, args: list, opts: dict, low: bool):
        recv = self.val(self.ev(callee["expression"])) if callee.get("nodeType") == "MemberAccess" else None
        vals = [self.val(self.ev(a)) for a in args]
        member = callee.get("memberName") or callee.get("name") or "call"
        if low:
            fname = f"address.{member}"
            term = ("call", fname, recv) + tuple(vals) + ((("value", opts["value"]),) if "value" in opts else ())
        else:
            owner = self.ix.contract_of(target) if target is not None else None
            if owner is not None:
                iface = owner["name"]
            else:
                iface = re.sub(r"^(contract|interface) ", "", type_string(callee.get("expression") or {})) or "?"
            fname = f"{iface}.{target['name'] if target is not None else member}"
            term = ("call", fname) + tuple(vals)
        if not low and iface in self.commit:
            self.edge("COMMIT", fname, n)
        else:
            self.debt("external_call", fname, n)
        if "value" in opts or (low and member in ("send", "transfer")):
            self.debt("value_transfer", fname, n)
        return results(n, term)

    def builtin(self, name: str, n: dict, args: list):
        if name in ("require", "assert"):
            c = self.val(self.ev(args[0]))
            reason = None
            if name == "require" and len(args) > 1:
                a = args[1]
                if a.get("nodeType") == "Literal" and a.get("kind") in ("string", "unicodeString"):
                    reason = a.get("value") or ""
                else:
                    self.val(self.ev(a))
                    if a.get("nodeType") == "FunctionCall":   # require(c, E(...)): the custom error's name
                        reason = (a.get("expression") or {}).get("name")
            self.guard("require", n, c, reason)
            if c == 0:
                self.exit = "revert"
            return ("tuple",)
        if name == "revert":
            reason = None
            if args and args[0].get("nodeType") == "Literal" and args[0].get("kind") in ("string", "unicodeString"):
                reason = args[0].get("value") or ""
            self.guard("revert", n, None, reason)
            self.exit = "revert"
            return ("tuple",)
        vals = [self.val(self.ev(a)) for a in args]
        if name in ("keccak256", "sha256"):
            self.edge("HASH", name, n)
            return (name,) + tuple(vals)
        if name == "blobhash":
            self.edge("COMMIT", "blobhash", n)
            return ("blobhash",) + tuple(vals)
        if name in ("blockhash", "ripemd160", "ecrecover"):
            return (name,) + tuple(vals)
        if name == "gasleft":
            return ("env", "gasleft")
        if name in ("addmod", "mulmod") and len(vals) == 3:
            inner = fold("+" if name == "addmod" else "*", vals[0], vals[1])
            return fold("%", inner, vals[2])
        self.unsupported_expr(n, name or "FunctionCall")
        return results(n, ("unknown", self.span(n), name or "call"))

    # -- inline assembly
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
                if self.exit:
                    break
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
                vals = [v] if len(names) == 1 else [("unknown", self.span(s), x) for x in names]
            for name, v in zip(names, vals):
                self.frame.yul[-1][name] = v
        elif nt == "YulAssignment":
            v = self.yul_expr(s["value"])
            targets = s.get("variableNames", [])
            vals = [v] if len(targets) == 1 else [("unknown", self.span(s), t["name"]) for t in targets]
            for t, x in zip(targets, vals):
                self.yul_set(t, x)
        elif nt == "YulExpressionStatement":
            self.yul_expr(s["expression"])
        elif nt == "YulIf":
            c = self.yul_expr(s["condition"])
            c = c if isinstance(c, int) or _is_boolean(c) else fold("!=", c, 0)
            if isinstance(c, int):
                if c:
                    self.yul_block(s["body"])
                return
            before = self.snapshot()
            self.ctx.append(c)
            try:
                self.yul_block(s["body"])
            finally:
                self.ctx.pop()
            e1, s1 = self.exit, self.snapshot()
            self.exit = None
            self.restore(before)
            if not e1:
                self.merge(c, s1, before, before)
        else:
            self.debt("unsupported", nt, s)
            self.havoc(s)
            self.havoc_memory(s)

    def yul_set(self, ident: dict, v) -> None:
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                scope[name] = v
                return
        ref = _external_ref(self.frame.asm, ident)
        if ref is not None:
            self.frame.vars[ref["declaration"]] = v
            self.tag("local", [ref["declaration"]])
            return
        self.frame.yul[-1][name] = v

    def yul_get(self, ident: dict):
        name = ident["name"]
        for scope in reversed(self.frame.yul):
            if name in scope:
                return scope[name]
        ref = _external_ref(self.frame.asm, ident)
        if ref is None:
            return ("unknown", self.span(ident), name)
        decl = ref["declaration"]
        suffix = ref.get("suffix")
        d = self.ix.nodes.get(decl) or {}
        if suffix == "slot" or ref.get("isSlot"):
            return ("slot", d.get("name", ""))
        if decl in self.frame.vars:
            self.read_decl(decl)
            v = self.val(self.frame.vars[decl])
        elif d.get("constant"):
            v = fold_constant(self.ix, d)
            v = v if v is not None else ("constant", d.get("name"))
        else:
            v = ("unknown", self.span(ident), name)
        if suffix == "offset" or (ref.get("isOffset") and suffix != "slot"):
            return ("cdoff", v)
        if suffix == "length":
            return ("len", v)
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
            self.debt("unsupported", nt, e)
            return ("unknown", self.span(e), nt)
        name = e["functionName"]["name"]
        args = e.get("arguments") or []
        known = name in YUL_PURE or name in YUL_ENV or name in ("shl", "shr", "iszero", "not", "mload", "mstore",
                                                                 "mstore8", "calldatacopy", "keccak256", "sload",
                                                                 "blobhash", "revert", "invalid", "extcodesize",
                                                                 "calldataload", "balance", "selfbalance")
        if not known:
            self.debt("unsupported", name, e)
            self.havoc(e)
            return ("unknown", self.span(e), name)
        vals = [None] * len(args)
        for i in range(len(args) - 1, -1, -1):   # Yul evaluates arguments right to left
            vals[i] = self.yul_expr(args[i])
        if name in YUL_ENV:
            return YUL_ENV[name]
        if name in YUL_PURE:
            return fold(YUL_PURE[name], vals[0], vals[1])
        if name == "shl":
            return fold("<<", vals[1], vals[0])
        if name == "shr":
            return fold(">>", vals[1], vals[0])
        if name == "iszero":
            return fold("==", vals[0], 0)
        if name == "not":
            return fold("not", vals[0])
        if name == "sload":
            return ("sload", vals[0])
        if name == "blobhash":
            self.edge("COMMIT", "blobhash", e)
            return ("blobhash", vals[0])
        if name == "extcodesize":
            return ("len", ("code", vals[0]))
        if name == "balance":
            return ("balance", vals[0])
        if name == "selfbalance":
            return ("balance", ("this",))
        if name == "calldataload":
            return ("calldataload", vals[0])
        if name in ("revert", "invalid"):
            self.guard("revert", e, None, None)
            self.exit = "revert"
            return ("tuple",)
        return self.yul_memory(name, vals, e)

    def yul_memory(self, name: str, vals: list, e: dict):
        p = vals[0]
        if name == "mload":
            if p == 0x40:
                self.regions += 1
                rid = (self.regions, tuple(self.calls) + (self.span(e),))
                self.memory[rid] = ("mem",)
                return ("ptr", rid, 0)
            return self.mload(p, e)
        if name == "keccak256":
            self.edge("HASH", "keccak256", e)
            return self.hash_mem(p, vals[1], e)
        if name == "mstore" and p == 0x40:
            return ("tuple",)
        if name == "calldatacopy":
            src, n = vals[1], vals[2]
            x, k = None, None
            if isinstance(src, tuple) and src[:1] == ("cdoff",):
                x, k = src[1], 0
            elif isinstance(src, tuple) and src[:1] == ("+",) and len(src) == 3:
                a, b = src[1], src[2]
                if isinstance(a, tuple) and a[:1] == ("cdoff",):
                    x, k = a[1], b
                elif isinstance(b, tuple) and b[:1] == ("cdoff",):
                    x, k = b[1], a
            w = (lambda off: ("calldatacopy", off, x, k, n)) if x is not None else \
                (lambda off: ("calldatacopy", off, ("calldata", src), 0, n))
        else:
            v = vals[1]
            w = (lambda off: (name, off, v))
        self.mem_write(p, w, e)
        self.tag("local")
        self.tag("memory")
        return ("tuple",)

    def mem_write(self, p, w, e: dict, cond=None) -> None:
        if is_ite(p):
            self.mem_write(p[2], w, e, p[1] if cond is None else conj([cond, p[1]]))
            self.mem_write(p[3], w, e, neg(p[1]) if cond is None else conj([cond, neg(p[1])]))
            return
        if is_ptr(p) and p[1] in self.memory:
            cur = self.memory[p[1]]
            new = mem_append(cur, w(p[2]))
            self.memory[p[1]] = new if cond is None else ite(cond, new, cur)
            return
        self.debt("unsupported", f"{e['functionName']['name']} at an unresolved address", e)
        for r in list(self.memory):
            self.memory[r] = mem_append(self.memory[r], ("unknown", self.span(e)))

    def mload(self, p, e: dict):
        if is_ite(p):
            return ite(p[1], self.mload(p[2], e), self.mload(p[3], e))
        if is_ptr(p) and p[1] in self.memory:
            return resolve_word(self.memory[p[1]], p[2])
        return ("mload", ("unknown", self.span(e), "memory"), p)

    def hash_mem(self, p, n, e: dict):
        if is_ite(p):
            return ite(p[1], self.hash_mem(p[2], n, e), self.hash_mem(p[3], n, e))
        if is_ptr(p) and p[1] in self.memory:
            return ("keccak256", resolve_bytes(self.memory[p[1]], p[2], n))
        return ("keccak256", ("slice", ("unknown", self.span(e), "memory"), p, n))


# ------------------------------------------------------------------------------------------------ helpers
def phi(v, span: str, name: str):
    if is_ptr(v):
        return ("ptr", v[1], ("phi", span, name))
    if isinstance(v, Ref):
        return v
    return ("phi", span, name)


def ite_value(c, a, b):
    if isinstance(a, tuple) and isinstance(b, tuple) and a[:1] == b[:1] == ("tuple",) and len(a) == len(b):
        return ("tuple",) + tuple(ite(c, x, y) for x, y in zip(a[1:], b[1:]))
    return ite(c, a, b)


def merge_storage(c, a: dict, b: dict) -> dict:
    out = {}
    for f in sorted(set(a) | set(b)):
        p = ("storage", f)
        v = ite(c, a.get(f, p), b.get(f, p))
        if v != p:
            out[f] = v
    return out


def merge_memory(c, a: dict, b: dict) -> dict:
    out = {}
    for r in sorted(set(a) | set(b), key=lambda r: r[0]):
        if r in a and r in b:
            out[r] = ite(c, a[r], b[r])
        else:
            out[r] = a[r] if r in a else b[r]
    return out


def mem_append(content, w):
    if is_ite(content):
        return ("?", content[1], mem_append(content[2], w), mem_append(content[3], w))
    return content + (w,)


def resolve_word(content, off):
    """mload at offset off of a region: the value of an mstore exactly there, the word of a calldatacopy covering it,
    else ["mload", content, off]."""
    if is_ite(content):
        return ite(content[1], resolve_word(content[2], off), resolve_word(content[3], off))
    if isinstance(off, int):
        for w in reversed(content[1:]):
            kind = w[0]
            if kind in ("mstore", "mstore8"):
                wo = w[1]
                if not isinstance(wo, int):
                    break
                width = 32 if kind == "mstore" else 1
                if wo + width <= off or off + 32 <= wo:
                    continue
                if kind == "mstore" and wo == off:
                    return w[2]
                break
            if kind == "calldatacopy":
                wo, x, frm, n = w[1], w[2], w[3], w[4]
                if not isinstance(wo, int):
                    break
                if isinstance(n, int) and (off + 32 <= wo or wo + n <= off):
                    continue
                if off >= wo and (not isinstance(n, int) or off + 32 <= wo + n):
                    return ("word", x, fold("+", off - wo, frm))
                break
            break
    return ("mload", content, off)


def resolve_bytes(content, off, n):
    """The bytes keccak256(off, n) hashes: the input itself when the region is exactly its copy, else a slice."""
    if is_ite(content):
        return ite(content[1], resolve_bytes(content[2], off, n), resolve_bytes(content[3], off, n))
    ws = content[1:]
    if off == 0 and len(ws) == 1 and ws[0][0] == "calldatacopy" and ws[0][1] == 0 and ws[0][3] == 0 and ws[0][4] == n:
        return ws[0][2]
    return ("slice", content, off, n)


def resolve(base, path: tuple):
    """A storage read of path in base (a family's value: ["storage", f], a store chain, a phi or a conditional)."""
    if is_ite(base):
        return ite(base[1], resolve(base[2], path), resolve(base[3], path))
    if isinstance(base, tuple) and base[:1] == ("store",):
        _, b, wpath, v = base
        rel = _compare(wpath, path)
        if rel == "same":
            return v
        if rel == "prefix":
            return project(v, path[len(wpath):])
        if rel == "disjoint":
            return resolve(b, path)
    return apply_path(base, path)


def _compare(wpath: tuple, path: tuple) -> str:
    for a, b in zip(wpath, path):
        if a == b:
            continue
        if a[0] == "member" and b[0] == "member":
            return "disjoint"
        if a[0] == b[0] and isinstance(a[1], int) and isinstance(b[1], int):
            return "disjoint"
        return "unknown"
    if len(wpath) == len(path):
        return "same"
    return "prefix" if len(wpath) < len(path) else "unknown"


def project(v, rest: tuple):
    for a in rest:
        if v == 0:
            return 0
        if a[0] == "member" and isinstance(v, tuple) and v[:1] == ("struct",) and a[1] in v[2]:
            v = v[3][v[2].index(a[1])]
        else:
            v = apply_path(v, (a,))
    return v


def apply_path(base, path: tuple):
    t = base
    for kind, x in path:
        t = (kind, t, x)
    return t


def components(v, k: int) -> list:
    if isinstance(v, tuple) and v[:1] == ("tuple",) and len(v) - 1 == k:
        return list(v[1:])
    if k == 1:
        return [v]
    return [("at", i, v) for i in range(k)]


def results(n: dict, term):
    """The value of a call: its term, or its components when it returns a tuple."""
    ts = type_string(n)
    if ts.startswith("tuple("):
        k = _tuple_arity(ts)
        if k == 0:
            return ("tuple",)
        if k > 1:
            return ("tuple",) + tuple(("at", i, term) for i in range(k))
    return term


def convert(v, src_ts: str, dst_ts: str):
    """W4: a conversion of a constant folds; to the same or a larger size it is the identity on terms; a narrowing
    conversion is ["trunc", bits, t]."""
    if isinstance(v, int) or (isinstance(v, tuple) and v[:1] == ("str",)):
        return convert_const(v, dst_ts)
    if dst_ts in ("address", "address payable") and v == ("this",):
        return v
    sb, db = conversion_bits(src_ts), conversion_bits(dst_ts)
    if sb is not None and db is not None and db < sb:
        return ("trunc", db, v)
    return v


def convert_const(a, dst_ts: str):
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


def fold_constant(index: Index, decl: dict, seen=()):
    """The folded value of a constant VariableDeclaration (W4; also keccak256 of a literal), or None."""
    if decl["id"] in seen or decl.get("value") is None:
        return None
    v = _const_expr(index, decl["value"], seen + (decl["id"],))
    if isinstance(v, int) or (isinstance(v, tuple) and v[:1] == ("str",)):
        return v
    return None


def _const_expr(index: Index, n: dict, seen):
    nt = n.get("nodeType")
    if nt == "Literal":
        return literal_value(n)
    if nt in ("Identifier", "MemberAccess"):
        d = index.nodes.get(n.get("referencedDeclaration"))
        if d is not None and d.get("nodeType") == "VariableDeclaration" and d.get("constant"):
            return fold_constant(index, d, seen)
        return None
    if nt == "BinaryOperation":
        a, b = _const_expr(index, n["leftExpression"], seen), _const_expr(index, n["rightExpression"], seen)
        return _fold(n["operator"], a, b) if isinstance(a, int) and isinstance(b, int) else None
    if nt == "UnaryOperation" and n.get("operator") in ("-", "~", "!"):
        a = _const_expr(index, n["subExpression"], seen)
        return _fold({"-": "neg"}.get(n["operator"], n["operator"]), a) if isinstance(a, int) else None
    if nt == "FunctionCall" and n.get("kind") == "typeConversion" and len(n.get("arguments") or []) == 1:
        a = _const_expr(index, n["arguments"][0], seen)
        return convert_const(a, type_string(n)) if a is not None else None
    if nt == "FunctionCall" and (n.get("expression") or {}).get("name") == "keccak256" \
            and (n["expression"].get("referencedDeclaration") or 0) < 0 and len(n.get("arguments") or []) == 1:
        a = _const_expr(index, n["arguments"][0], seen)
        if isinstance(a, tuple) and a[:1] == ("str",):
            from ...keccak import keccak256
            return int.from_bytes(keccak256(bytes.fromhex(a[1])), "big")
        return None
    if nt == "TupleExpression" and len(n.get("components") or []) == 1 and not n.get("isInlineArray"):
        return _const_expr(index, n["components"][0], seen)
    return None


def count(op: str, a, n, step: int):
    """Iterations of `for (i = a; i op n; i += step)` (step < 0: i -= |step|)."""
    def sub(x, y):
        return x if y == 0 else fold("-", x, y)

    def div(x, k):
        return x if k == 1 else fold("/", x, k)

    if step > 0:
        s = step
        if op == "<":
            body = div(sub(n, a) if s == 1 else fold("+", sub(n, a), s - 1), s)
            return body if a == 0 else ite(fold("<", a, n), body, 0)
        if op == "<=":
            body = fold("+", div(sub(n, a), s), 1)
            return body if a == 0 else ite(fold("<=", a, n), body, 0)
        if op == "!=" and s == 1:
            return sub(n, a)
        return None
    s = -step
    if op == ">":
        body = div(sub(a, n) if s == 1 else fold("+", sub(a, n), s - 1), s)
        return body if n == 0 else ite(fold(">", a, n), body, 0)
    if op == ">=":
        return ite(fold(">=", a, n), fold("+", div(sub(a, n), s), 1), 0)
    if op == "!=" and s == 1:
        return sub(a, n)
    return None


def _step(e: dict | None, ivar):
    if e is None:
        return None
    x = e.get("expression") if e.get("nodeType") == "ExpressionStatement" else e
    if x is None:
        return None
    if x.get("nodeType") == "UnaryOperation" and x.get("operator") in ("++", "--") and _is_ident(x["subExpression"], ivar):
        return 1 if x["operator"] == "++" else -1
    if x.get("nodeType") == "Assignment" and _is_ident(x["leftHandSide"], ivar):
        k = _lit(x["rightHandSide"])
        if x.get("operator") in ("+=", "-=") and isinstance(k, int) and k > 0:
            return k if x["operator"] == "+=" else -k
        r = x["rightHandSide"]
        if x.get("operator") == "=" and r.get("nodeType") == "BinaryOperation" and r["operator"] in ("+", "-") \
                and _is_ident(r["leftExpression"], ivar) and isinstance(_lit(r["rightExpression"]), int):
            k = _lit(r["rightExpression"])
            return k if r["operator"] == "+" else -k
    return None


def _lit(n: dict):
    if n.get("nodeType") == "Literal" and n.get("kind") == "number":
        v = literal_value(n)
        return v if isinstance(v, int) else None
    return None


def _is_ident(n: dict, decl) -> bool:
    return n.get("nodeType") == "Identifier" and n.get("referencedDeclaration") == decl


def _mentions_decl(n, decl) -> bool:
    return decl in _identifiers(n)


def _identifiers(n) -> list:
    out, stack = [], [n]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("nodeType") in ("Identifier", "MemberAccess") and isinstance(x.get("referencedDeclaration"), int):
                out.append(x["referencedDeclaration"])
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return out


def _assigns(n, decl, skip=None) -> bool:
    stack = [n]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("id") != skip:
                nt = x.get("nodeType")
                if nt == "Assignment" and decl in _lvalue_decls(x.get("leftHandSide")):
                    return True
                if nt == "UnaryOperation" and x.get("operator") in ("++", "--", "delete") \
                        and decl in _lvalue_decls(x.get("subExpression")):
                    return True
                if nt == "YulAssignment":
                    pass
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return False


def _writes_state(n, index: Index, name: str) -> bool:
    """Whether the loop's own statements syntactically write the state variable `name` (an approximation the bound
    check uses: a write inside a called function is not seen; the dry run catches what the walk writes)."""
    stack = [n]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            nt = x.get("nodeType")
            lv = x.get("leftHandSide") if nt == "Assignment" else (
                x.get("subExpression") if nt == "UnaryOperation" and x.get("operator") in ("++", "--", "delete")
                else None)
            if lv is not None:
                r = _root_decl(lv)
                d = index.nodes.get(r) or {}
                if d.get("stateVariable") and d.get("name") == name:
                    return True
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return False


def _root_decl(n: dict):
    x = n
    while x.get("nodeType") in ("IndexAccess", "MemberAccess", "IndexRangeAccess"):
        x = x.get("baseExpression") or x.get("expression") or {}
    return x.get("referencedDeclaration") if x.get("nodeType") == "Identifier" else None


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


def _is_local(index: Index, ref) -> bool:
    d = index.nodes.get(ref) if isinstance(ref, int) else None
    return d is not None and d.get("nodeType") == "VariableDeclaration" and not d.get("stateVariable")


def _is_boolean(t) -> bool:
    return isinstance(t, tuple) and t[:1] and t[0] in ("==", "!=", "<", "<=", ">", ">=", "!", "&&", "||")


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


# ------------------------------------------------------------------------------------------------ the contract
def find_contract(index: Index, name: str) -> dict:
    cs = index.contracts_named(name)
    if len(cs) != 1:
        raise ExtractionError(f"contract {name} found {len(cs)} times")
    return cs[0]


def actions_of(contract: dict) -> list[dict]:
    """Every external or public FunctionDefinition with a body the contract declares itself (not a constructor)."""
    out = []
    for n in contract.get("nodes") or []:
        if n.get("nodeType") == "FunctionDefinition" and n.get("visibility") in ("external", "public") \
                and n.get("kind") in ("function", "receive", "fallback") and n.get("body") is not None:
            out.append(n)
    return sorted(out, key=lambda n: (n.get("name") or n.get("kind"), n["id"]))


def walk_contract(compiled, side: dict):
    """(index, contract, actions, collector): every action walked."""
    index = Index(compiled)
    tr = side["transitions"]
    contract = find_contract(index, tr["contract"])
    coll = Collector()
    acts = []
    for fn in actions_of(contract):
        acts.append(Walk(index, contract, fn, coll, tr.get("commit_interfaces") or []).run())
    names = [a["name"] for a in acts]
    if len(set(names)) != len(names):
        dup = sorted({x for x in names if names.count(x) > 1})
        raise ExtractionError(f"contract {tr['contract']}: overloaded actions {dup} (one entry per name)")
    return index, contract, acts, coll


def build(compiled, side: dict, sidecar_rel: str, sidecar_sha256: str) -> dict:
    """The transitions document of a sidecar with "transitions"."""
    import hashlib
    index, contract, acts, _ = walk_contract(compiled, side)
    return {
        "facts_version": FACTS_VERSION,
        "target": dict(side["target"]),
        "extraction": {
            "method": "extracted",
            "frontend": "solidity",
            "kind": "transitions",
            "frontend_version": TRANSITIONS_VERSION,
            "sidecar": {"path": sidecar_rel, "sha256": sidecar_sha256},
            "toolchain": {"solc": {"version": compiled.version, "sha256": compiled.solc_sha256}},
            "settings": compiled.settings,
            "inputs": [{"unit": u, "sha256": hashlib.sha256(compiled.units[u]).hexdigest()}
                       for u in sorted(compiled.units)],
        },
        "contract": contract["name"],
        "constants": STORAGE.constants(contract, lambda d: fold_constant(index, d)),
        "storage": STORAGE.families(compiled, index, contract),
        "actions": acts,
        "assumptions": [{"id": k, "text": v} for k, v in sorted(ASSUMPTIONS.items())],
    }


def statements_of(body: dict) -> list[dict]:
    """The Solidity Statement nodes inside a body (the body itself excluded; Yul is not entered)."""
    out, stack = [], [body]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x is not body and x.get("nodeType") in STATEMENTS and isinstance(x.get("id"), int):
                out.append(x)
            stack.extend(v for k, v in x.items() if k != "AST" and isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return out


def coverage_document(compiled, side: dict) -> dict:
    """{statements, extracted, debt, unaccounted} of the sidecar's contract (module docstring)."""
    index, contract, acts, coll = walk_contract(compiled, side)
    stmts: dict[int, dict] = {}
    returns: set = set()
    for fid in sorted(coll.reached):
        fn = coll.reached[fid]
        for s in statements_of(fn["body"]):
            stmts[s["id"]] = s
        for p in (fn.get("returnParameters") or {}).get("parameters", []):
            returns.add(p["id"])
    extracted, unaccounted = 0, []
    for sid in sorted(stmts):
        tags = coll.tags.get(sid, set())
        feeding = "local" in tags and ("memory" in tags or any(d in coll.reads or d in returns
                                                                for d in coll.defs.get(sid, ())))
        if tags & EXTRACTED_TAGS or feeding:
            extracted += 1
        elif "debt" in tags or sid in coll.covered_by_debt:
            continue
        else:
            s = stmts[sid]
            unaccounted.append({"src": index.span(s["src"]), "node": s["nodeType"]})
    debt = [{"src": src, "kind": kind, "detail": detail} for (src, kind, detail) in coll.debt]
    return {
        "statements": len(stmts),
        "extracted": extracted,
        "debt": sorted(debt, key=lambda d: (d["src"], d["kind"], d["detail"])),
        "unaccounted": sorted(unaccounted, key=lambda d: (d["src"], d["node"])),
    }
