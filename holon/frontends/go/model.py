"""Resolve the gossa dump into per-function expression trees and op streams.

The dump is a normalized SSA value graph: every instruction has an id, an
op, operand value ids and a block id; blocks carry successors tagged
then/else/next.  ``Fn`` wraps one dumped function; ``expr(fn, vid)`` maps a
value id to a hashable expression tree used by the reducers.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Expr forms (tuples):
#   ("const", value, gotype)
#   ("param", name, index)
#   ("global", name)
#   ("alloc", vid)                       heap/local slot, self-identified
#   ("call", fnid, [args])
#   ("builtin", name, [args])
#   ("fieldaddr", e, name) ("field", e, name)
#   ("indexaddr", e, idx_expr) ("index", e, idx_expr)
#   ("load", e)                          unop *  (may alias -> store later)
#   ("slice", e, lo_expr, hi_expr, mx_expr)
#   ("binop", op, a, b) ("unop", op, a)
#   ("cast", to_type, e)                 convert/changetype/changeiface
#   ("extract", e, i)
#   ("phi", [e, ...])
#   ("makeslice", len_e, cap_e)
#   ("value", vid)                       opaque / unresolved


@dataclass
class Fn:
    d: dict
    instrs: dict = field(init=False)
    blocks: dict = field(init=False)
    _expr_cache: dict = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.instrs = {i["id"]: i for i in self.d["instrs"]}
        self.blocks = {b["id"]: b for b in self.d["blocks"]}

    @property
    def id(self):
        return self.d["id"]

    @property
    def name(self):
        return self.d["name"]

    @property
    def file(self):
        return self.d["file"]

    @property
    def line(self):
        return self.d["line"]

    @property
    def recv(self):
        return self.d.get("recv")

    def instr(self, vid):
        return self.instrs.get(vid)


class Dump:
    def __init__(self, d: dict):
        self.format = d["dump_version"]
        self.module = ""
        self.consts = d.get("consts", [])
        self.funcs = {f["id"]: Fn(f) for f in d["functions"]}
        self.by_short = {}
        for f in self.funcs.values():
            key = short_name(f.d)
            self.by_short.setdefault(key, []).append(f)


def short_name(fd: dict) -> str:
    """`...batch.BatchHeaderV0).Bytes` -> `BatchHeaderV0.Bytes`."""
    fid = fd["id"]
    fid = fid.rsplit("/", 1)[-1]
    fid = fid.split(")", 1)[-1] if ")" in fid else fid
    if fid.startswith(".("):
        fid = fid[2:-1] + ")" + fd["id"].rsplit(")", 1)[-1]
    name = fd["name"]
    recv = fd.get("recv")
    if recv:
        t = recv["type"].rsplit("/", 1)[-1].lstrip("*")
        return f"{t}.{name}"
    return name


def expr(fn: Fn, vid: int):
    if vid is None or vid < 0:
        return ("nil",)
    cached = fn._expr_cache.get(vid)
    if cached is not None:
        return cached
    ins = fn.instr(vid)
    if ins is None:
        return ("value", vid)
    fn._expr_cache[vid] = ("cycle", vid)  # breaks phi/loop recursion
    out = _expr_instr(fn, ins)
    fn._expr_cache[vid] = out
    return out


def _expr_instr(fn: Fn, ins: dict):
    op = ins["op"]
    args = ins.get("args") or []
    ea = [expr(fn, a) for a in args]
    if op == "param":
        return ("param", ins.get("name", ""), ins.get("index", ins["id"]))
    if op == "freevar":
        return ("freevar", ins.get("name", ""))
    if op == "const":
        return ("const", ins.get("value"), ins.get("type", ""), ins.get("name", ""))
    if op == "global":
        return ("global", ins.get("name", ""))
    if op == "alloc":
        return ("alloc", ins["id"])
    if op == "call":
        f = ins.get("fn", "")
        if f.startswith("builtin."):
            return ("builtin", f.split(".", 1)[1], tuple(ea))
        return ("call", f, tuple(ea))
    if op == "fnref":
        return ("fnref", ins.get("fn", ""))
    if op == "builtin":
        return ("builtin", ins.get("name", ""), tuple(ea))
    if op == "fieldaddr":
        return ("fieldaddr", ea[0], ins.get("name", ""))
    if op == "field":
        return ("field", ea[0], ins.get("name", ""))
    if op == "indexaddr":
        return ("indexaddr", ea[0], ea[1] if len(ea) > 1 else ("nil",))
    if op == "index":
        return ("index", ea[0], ea[1] if len(ea) > 1 else ("nil",))
    if op == "slice":
        return ("slice", ea[0], ea[1], ea[2], ea[3])
    if op == "unop":
        return ("load" if ins.get("name") == "*" else "unop:" + str(ins.get("name")), ea[0])
    if op == "binop":
        return ("binop", ins.get("name", ""), ea[0], ea[1])
    if op in ("convert", "changetype", "changeiface", "typeassert", "makeiface"):
        return ("cast", ins.get("type", ""), ea[0])
    if op == "extract":
        return ("extract", ea[0], ins.get("index", 0))
    if op == "phi":
        return ("phi", tuple(expr(fn, pr[1]) for pr in ins.get("edges", [])))
    if op == "lookup":
        return ("lookup", ea[0], ea[1] if len(ea) > 1 else ("nil",))
    if op == "makeslice":
        return ("makeslice", ea[0] if ea else ("nil",), ea[1] if len(ea) > 1 else ("nil",))
    return ("value", ins["id"])


def const_val(e):
    if e and e[0] == "const":
        return e[1]
    return None


def is_nil_const(e):
    return e and e[0] == "const" and e[3] == "nil"


def strip_casts(e):
    while e and e[0] == "cast":
        e = e[2]
    return e


def strip_loads(e):
    while e and e[0] == "load":
        e = e[1]
    return e


def expr_text(e, depth=0):
    """Stable one-line rendering for conditions/debt records."""
    if e is None or depth > 8:
        return "?"
    t = e[0]
    if t == "const":
        return repr(e[1]) if e[1] is not None else (e[3] or "nil")
    if t == "param":
        return e[1] or f"arg{e[2]}"
    if t == "global":
        return e[1]
    if t == "alloc":
        return f"alloc{e[1]}"
    if t in ("call", "builtin"):
        fnname = e[1].rsplit("/", 1)[-1]
        return f"{fnname}(" + ", ".join(expr_text(a, depth + 1) for a in e[2]) + ")"
    if t in ("field", "fieldaddr"):
        return f"{expr_text(e[1], depth + 1)}.{e[2]}"
    if t in ("index", "indexaddr"):
        return f"{expr_text(e[1], depth + 1)}[{expr_text(e[2], depth + 1)}]"
    if t == "slice":
        lo, hi = e[2], e[3]
        s = expr_text(e[1], depth + 1)
        l = "" if lo[0] == "nil" else expr_text(lo, depth + 1)
        h = "" if hi[0] == "nil" else expr_text(hi, depth + 1)
        return f"{s}[{l}:{h}]"
    if t == "binop":
        return f"{expr_text(e[2], depth + 1)} {e[1]} {expr_text(e[3], depth + 1)}"
    if t == "load":
        return "*" + expr_text(e[1], depth + 1)
    if t == "cast":
        return expr_text(e[2], depth)
    if t == "extract":
        return f"{expr_text(e[1], depth + 1)}.{e[2]}"
    if t == "phi":
        return "phi(" + "|".join(expr_text(a, depth + 1) for a in e[1]) + ")"
    if t == "makeslice":
        return "makeslice"
    if t == "nil":
        return "nil"
    if t == "fnref":
        return e[1].rsplit("/", 1)[-1]
    return f"{t}#{e[1] if len(e) > 1 else ''}"


# ---------- CFG walk ----------

# A seq tree is a list of nodes:
#   ("instr", instr-dict)             one effectful or value instruction, in order
#   ("branch", cond_expr, then_seq, else_seq)
#   ("term", terminator-instr|None)   return/panic/unreachable
#   ("backedge", block_id)
_WALK_CAP = 6000


def walk_seq(fn):
    """Deterministic DFS expansion of the CFG into a seq tree."""
    budget = [_WALK_CAP]
    overflow = []

    def walk(bid, stack):
        if budget[0] <= 0:
            if not overflow:
                overflow.append(bid)
            return [("overflow", bid)]
        budget[0] -= 1
        if bid in stack:
            return [("backedge", bid)]
        b = fn.blocks.get(bid)
        if b is None:
            return [("overflow", bid)]
        stack = stack | {bid}
        ids = list(b["instrs"])
        term = None
        if ids:
            last = fn.instr(ids[-1])
            if last and last["op"] in ("if", "jump", "return", "panic"):
                term = last
                ids = ids[:-1]
        nodes = [("instr", fn.instr(i)) for i in ids]
        succs = b.get("succs") or []
        if term and term["op"] == "if":
            cond = expr(fn, term.get("cond"))
            tb = next((e["to"] for e in succs if e["tag"] == "then"), None)
            eb = next((e["to"] for e in succs if e["tag"] == "else"), None)
            then = walk(tb, stack) if tb is not None else [("term", None)]
            els = walk(eb, stack) if eb is not None else [("term", None)]
            nodes.append(("branch", cond, then, els))
        elif term and term["op"] == "jump":
            if succs:
                nodes.extend(walk(succs[0]["to"], stack))
            else:
                nodes.append(("term", None))
        elif term:
            nodes.append(("term", term))
        else:
            nodes.append(("term", None))
        return nodes

    if not fn.blocks:
        return [], False
    out = walk(0, set())
    return out, not overflow


def seq_leaves(seq, conds=()):
    """Yield (conds, term-instr-or-None) for every leaf of a seq tree."""
    for node in seq:
        k = node[0]
        if k == "branch":
            c = node[1]
            yield from seq_leaves(node[2], conds + (c,))
            yield from seq_leaves(node[3], conds + (("not", c),))
        elif k == "term":
            yield conds, node[1]


def seq_instrs(fn, seq, _seen=None):
    """Yield (instr, in_loop) once per instr id, first path occurrence."""
    if _seen is None:
        _seen = set()
    for node in seq:
        k = node[0]
        if k == "instr":
            if node[1]["id"] in _seen:
                continue
            _seen.add(node[1]["id"])
            b = fn.blocks.get(node[1].get("block"), {})
            yield node[1], bool(b.get("loop"))
        elif k == "branch":
            yield from seq_instrs(fn, node[2], _seen)
            yield from seq_instrs(fn, node[3], _seen)
