"""holon extract go_machines: Go state machines as transitions documents (I105; M6 generality).

  python -m holon extract go_machines [--root DIR] --config CFG [--src DIR] --out-dir DIR

The Go codec frontend (holon.frontends.go, unchanged) extracts functions and codecs. This frontend reads the same
holon-go-frontend/0.3 config and the same SSA dump (holon/frontends/go/ssadump, built and run by the codec frontend's own
helpers) and writes, for every machine of every document of the config, one holon-facts/0.3 transitions document in the
Solidity frontend's IR (holon.frontends.solidity.transitions: extraction.kind "transitions", the same sections, the same
term language), so the typed pipeline (holon sorts, types, model, disch, derive) reads it unchanged. Output:
DIR/<stem>.<Type>.extracted.json. Nothing here names a target: the config is the only vocabulary.

Machines. A machine is a named struct type declared in a document package with at least one exported method declared
there (value or pointer receiver). Its state is its fields, one family per field, at slot = field index, offset 0 (an
abstract layout: the families are independent cells; the Go zero value of each field is the model's zero storage). A
field on which an action calls Get/Has/Set/Delete over []byte keys, directly or on a value an opaque call derives from
it (a store handle held in a field), is a KV family: a mapping from the key bytes to the value bytes (Get reads it, Has compares
the read with the empty value, Set and Delete write it, Iterator and ReverseIterator read it opaquely; A-kv). Its actions are its exported
methods; static calls of functions of the document's packages are inlined to the config's inline_depth (no recursion).

The walk. Each action is walked path by path over its SSA form (depth first, the true successor first), with a symbolic
store: the receiver pointer and its field addresses, the receiver's copy (a value receiver), local allocations, and the
state values read so far. Terms are the Solidity IR's (["param", n], ["storage", f], ["map", m, k], ["store", base,
path, v], operators, ["?", c, a, b], ["call", fn, args...], ["unknown", span, what]); Go's fixed-width arithmetic is
rendered exactly (["trunc", N, t] for uintN, ["sext", N, t] for intN, the signed comparisons and divisions for intN);
string equality compares ["keccak256", ...] of both sides, concatenation is ["abi.encodePacked", a, b].
  * A path that returns a non-nil error, or panics (a panic instruction, an integer division by a zero divisor), before
    it writes anything is a guard: kind "revert", expr ["!", K] (K the path's condition, n-ary "&&"), reason the error's
    text or name. An error or panic path that has written keeps its writes (Go does not roll back): it is a path like
    the others.
  * Every other path contributes its writes, in path order, each with cond K: a store through the receiver pointer or a
    local alias of a field address; a map update of a map read from a field (a value receiver's copy shares its maps);
    KV Set (value) and Delete (0).
  * Soundness: a write the walk cannot resolve is never dropped; the families it may reach are havocked: written at the
    path's end with ["unknown", <span>, "havoc"], and every later read of them in the path is a fresh unknown. That
    covers a store through a pointer read from the state (every family), a whole-receiver store, a store below a
    field (into a struct, array or slice element of the state), and an opaque call (outside the document's packages,
    dynamic, interface, or past inline_depth) or goroutine or defer handed a pointer to the state, a state map, a KV
    store or a closure over them (the families they reach; the receiver pointer reaches every family). A loop (a block
    of a cycle) is not iterated: every family a store, map update, KV write or call inside the loop may reach is
    havocked, the loop's values are unknown, and the walk continues at each exit; debt kind "loop". Goroutines,
    channel operations and select are debt (kinds "goroutine", "channel"); a path count above max_paths havocs every
    family and drops the guards (debt "path_limit"), which only adds behaviours.
  Guards that are dropped, and havoc, only add behaviours: a law over the document can become UNKNOWN or REFUTED with a
  failing replay, never PROVED for a behaviour the code does not have.

The document. The Solidity transitions document's keys (spec/schemas/facts_0_3.schema.json, branch go_transitions):
contract "<package path>.<Type>", constants {}, storage [families], inherited_storage [], actions, assumptions; the
extraction {method, frontend "go", kind "transitions", frontend_version FRONTEND_VERSION, config {path, sha256}, tool
{go, x_tools, ssadump_sha256}, inputs [{unit, sha256}]}; and two keys of its own: "debt" [{action, kind, src, what}]
(sorted) and "info", what the model reads from the frontend in place of a compiler (holon.machine.toolchain_info): the
families' layout in the storage-layout vocabulary (types t_bool, t_uint<N>, t_int<N>, t_string_storage,
t_bytes_storage, t_mapping(<k>,<v>); any other field type is the opaque word t_bytes32) and each action's inputs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from ..go.ssaload import DumpError, Func, Program, span_of

GX = importlib.import_module("holon.frontends.go.extract")   # the codec frontend's helpers (its __init__ re-exports a function named extract)

FRONTEND_VERSION = "holon-go-machines/0.1"
FACTS_VERSION = "holon-facts/0.3"
INFO_VERSION = "holon-extracted-info/0.2"
KV_METHODS = ("Delete", "Get", "Has", "Set")
KV_READERS = ("Iterator", "ReverseIterator")
WORD = 1 << 256

ASSUMPTIONS = {
    "A-env": "Environment terms (the state before the action, the results of opaque calls) are free: every value of "
             "them is possible. The result of an opaque call is a function of its function and arguments.",
    "A-implicit": "Implicit Go panics other than an integer division by zero (nil dereference, index out of range, a "
                  "nil map write, a failed type assertion) are not modelled as guards.",
    "A-loop": "A loop is not iterated: every family it may write is havocked and its values are unknown after it.",
    "A-reach": "Every path that returns a non-nil error or panics before writing is a guard reach.",
    "A-reentrancy": "An opaque call writes only state reachable from its arguments (and its receiver): a state "
                    "pointer, map, KV store or closure handed to it havocs the families it reaches; a call through an "
                    "interface held in the state does not write this machine's state otherwise.",
}
KV_ASSUMPTION = ("A-kv", "A KV store maps key bytes to value bytes; Get of an absent key is the empty value, Has(k) is "
                 "Get(k) != empty (a stored value is never empty), Delete writes the empty value. A KV call's error result is free; a Set or Delete that returns an error "
                 "is modelled as having written.")


class Refused(Exception):
    """An input is refused (exit 2): nothing written."""


class ExtractionError(Exception):
    """The extraction failed (exit 3): nothing written."""


# ------------------------------------------------------------------------------------------------ symbolic values
class Ptr:
    """A pointer: kind "recv" (the receiver), "fam" (family f, accessor path), "local" (object oid, field path),
    "unk" (anything; read from the state or from an opaque result)."""
    __slots__ = ("kind", "a", "path")

    def __init__(self, kind, a=None, path=()):
        self.kind, self.a, self.path = kind, a, tuple(path)


class MapRef:
    __slots__ = ("fam",)

    def __init__(self, fam):
        self.fam = fam


class KVRef:
    __slots__ = ("fam",)

    def __init__(self, fam):
        self.fam = fam


class Local:
    """A local object (an allocation, a made map or slice): writes to it are not state writes."""
    __slots__ = ("oid",)

    def __init__(self, oid):
        self.oid = oid


class RecvVal:
    """The receiver's value (a value receiver): its fields read the state before the action."""
    __slots__ = ()


class StructV:
    __slots__ = ("fields",)

    def __init__(self, fields):
        self.fields = dict(fields)


class Tup:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = list(items)


class Clo:
    __slots__ = ("fid", "binds")

    def __init__(self, fid, binds):
        self.fid, self.binds = fid, list(binds)


class NonNilErr:
    """An error value that is non-nil by the language's library semantics: the result of errors.New or fmt.Errorf, or
    a package variable of type error that a package initializer assigns from one of them (and nothing else)."""
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


NONNIL_CALLS = ("errors.New", "fmt.Errorf")


def nonnil_error_globals(prog: Program) -> dict:
    """{global id: reason} of every package variable of type error whose only stores, in package initializers, are of
    a value that errors.New or fmt.Errorf returns."""
    good, bad = {}, set()
    for fn in prog.funcs.values():
        for ins in fn.instrs:
            if ins.op != "Store" or not ins.operands or "global" not in (ins.operands[0] or {}):
                continue
            g = ins.operands[0]["global"]
            v = ins.operands[1] if len(ins.operands) > 1 else None
            d = fn.defs.get(v["v"]) if v and "v" in v else None
            c = d.call if d is not None and d.op == "Call" else None
            if fn.name == "init" and c and c.get("mode") == "static" and c.get("callee") in NONNIL_CALLS:
                arg = c.get("args")[0] if c.get("args") else None
                good[g] = (arg.get("const") or {}).get("value") if arg and "const" in arg else None
            else:
                bad.add(g)
    return {g: r for g, r in good.items() if g not in bad and (prog.globals.get(g) or {}).get("type") == "*error"}


class PathLimit(Exception):
    pass


def hexs(s: str) -> str:
    return s.encode("utf-8", "surrogateescape").hex()


def conj(atoms: list):
    xs = [a for a in atoms if a != 1]
    if any(a == 0 for a in xs):
        return 0
    if not xs:
        return 1
    return xs[0] if len(xs) == 1 else ["&&", *xs]


def neg(t):
    if t in (0, 1):
        return 1 - t
    if isinstance(t, list) and t[:1] == ["!"]:
        return t[1]
    return ["!", t]


# ------------------------------------------------------------------------------------------------ type helpers
class TypeView:
    def __init__(self, prog: Program):
        self.prog = prog
        self.T = prog.types

    def basic(self, k: str) -> dict:
        e = self.T.entry(self.T.under(k))
        return e if e.get("kind") == "basic" else {}

    def int_info(self, k: str):
        return self.T.int_info(k)

    def struct_fields(self, k: str) -> list:
        """Fields of a struct type, or of the struct a pointer type points to."""
        u = self.T.entry(self.T.under(k))
        if u.get("kind") == "pointer":
            u = self.T.entry(self.T.under(u.get("elem", "")))
        return list(u.get("fields") or []) if u.get("kind") == "struct" else []

    def is_kv_iface(self, k: str) -> bool:
        u = self.T.entry(self.T.under(k))
        return u.get("kind") == "interface" and set(KV_METHODS) <= set(u.get("methods") or [])

    def tid(self, k: str, out: dict) -> str:
        """The storage-layout type id of a Go type (module docstring), registered in out."""
        T = self.T
        kind = T.kind(k)
        if T.is_bool(k):
            tid, e = "t_bool", {"encoding": "inplace", "label": "bool", "numberOfBytes": "1"}
        elif T.is_integer(k) and T.int_info(k):
            bits, uns = T.int_info(k)
            n = f"{'uint' if uns else 'int'}{bits}"
            tid, e = f"t_{n}", {"encoding": "inplace", "label": n, "numberOfBytes": str(bits // 8)}
        elif T.is_string(k):
            tid, e = "t_string_storage", {"encoding": "bytes", "label": "string", "numberOfBytes": "32"}
        elif T.is_byte_slice(k):
            tid, e = "t_bytes_storage", {"encoding": "bytes", "label": "bytes", "numberOfBytes": "32"}
        elif kind == "map":
            u = T.entry(T.under(k))
            kt, vt = self.key_tid(u.get("key", ""), out), self.tid(u.get("elem", ""), out)
            tid = f"t_mapping({kt},{vt})"
            e = {"encoding": "mapping", "key": kt, "value": vt, "numberOfBytes": "32",
                 "label": f"mapping({out[kt]['label']} => {out[vt]['label']})"}
        else:
            tid, e = "t_bytes32", {"encoding": "inplace", "label": "bytes32", "numberOfBytes": "32"}
        out.setdefault(tid, e)
        return tid

    def key_tid(self, k: str, out: dict) -> str:
        if self.T.is_string(k):
            out.setdefault("t_string_memory_ptr", {"encoding": "bytes", "label": "string", "numberOfBytes": "32"})
            return "t_string_memory_ptr"
        if self.T.is_byte_slice(k):
            out.setdefault("t_bytes_memory_ptr", {"encoding": "bytes", "label": "bytes", "numberOfBytes": "32"})
            return "t_bytes_memory_ptr"
        return self.tid(k, out)

    def abi(self, k: str) -> dict:
        """The ABI shape of a parameter's Go type (opaque word when it has none)."""
        T = self.T
        if T.is_bool(k):
            return {"type": "bool"}
        if T.is_integer(k) and T.int_info(k):
            bits, uns = T.int_info(k)
            return {"type": f"{'uint' if uns else 'int'}{bits}"}
        if T.is_string(k):
            return {"type": "string"}
        if T.is_byte_slice(k):
            return {"type": "bytes"}
        fs = self.struct_fields(k)
        if fs and (T.kind(k) == "struct" or T.kind(k) == "pointer"):
            comps = []
            for f in fs:
                a = self.abi_scalar(f["type"])
                comps.append(dict(a, name=f["name"]))
            return {"type": "tuple", "components": comps}
        return {"type": "uint256"}

    def abi_scalar(self, k: str) -> dict:
        a = self.abi(k) if not self.struct_fields(k) else {"type": "uint256"}
        return a if a["type"] != "tuple" else {"type": "uint256"}

    def width(self, k: str):
        T = self.T
        if T.is_bool(k):
            return 8
        if T.is_integer(k) and T.int_info(k):
            return T.int_info(k)[0]
        return None


# ------------------------------------------------------------------------------------------------ the walk
class PState:
    __slots__ = ("frames", "atoms", "mem", "over", "taint", "writes", "debt", "nobj", "loopvals")

    def __init__(self):
        self.frames, self.atoms, self.mem, self.over = [], [], {}, {}
        self.taint, self.writes, self.debt, self.nobj = set(), [], [], 0
        self.loopvals = set()

    def fork(self) -> "PState":
        s = PState()
        s.frames = [f.copy() for f in self.frames]
        s.atoms = list(self.atoms)
        s.mem = {k: (dict(v) if isinstance(v, dict) else v) for k, v in self.mem.items()}
        s.over = dict(self.over)
        s.taint = set(self.taint)
        s.writes = list(self.writes)
        s.debt = list(self.debt)
        s.nobj = self.nobj
        return s


class Frame:
    __slots__ = ("fn", "regs", "params", "free", "block", "pred", "idx", "ret_to", "stack")

    def __init__(self, fn: Func, params, free, ret_to=None, stack=()):
        self.fn, self.params, self.free = fn, list(params), list(free)
        self.regs, self.block, self.pred, self.idx, self.ret_to = {}, 0, -1, 0, ret_to
        self.stack = tuple(stack)

    def copy(self) -> "Frame":
        f = Frame(self.fn, self.params, self.free, self.ret_to, self.stack)
        f.regs, f.block, f.pred, f.idx = dict(self.regs), self.block, self.pred, self.idx
        return f


class End:
    def __init__(self, st: PState, kind: str, src: str, rets, reason):
        self.st, self.kind, self.src, self.rets, self.reason = st, kind, src, rets, reason
        self.err = None


class Walker:
    def __init__(self, prog: Program, tv: TypeView, pkset: set, machine: str, fields: list, kv: set, limits: dict):
        self.prog, self.tv, self.pkset = prog, tv, pkset
        self.machine, self.fields, self.kv = machine, fields, kv
        self.fnames = [f["name"] for f in fields]
        self.ftypes = {f["name"]: f["type"] for f in fields}
        self.max_paths = int(limits.get("max_paths", 512))
        self.inline_depth = int(limits.get("inline_depth", 4))
        self.ends: list[End] = []
        self.npaths = 0
        self.members: dict = {}
        self.nonnil = nonnil_error_globals(prog) if not hasattr(prog, "_nonnil") else prog._nonnil
        prog._nonnil = self.nonnil

    # ---------------------------------------------------------------- values
    def unknown(self, ins_or_pos, what: str):
        pos = ins_or_pos if isinstance(ins_or_pos, str) else (ins_or_pos.pos or ins_or_pos.fn.pos)
        return ["unknown", span_of(pos) or "?", what]

    def operand(self, fr: Frame, o, st: PState):
        if o is None:
            return 0
        if "v" in o:
            return fr.regs.get(o["v"], ["unknown", "?", o["v"]])
        if "param" in o:
            return fr.params[o["param"]]
        if "free" in o:
            return fr.free[o["free"]]
        if "const" in o:
            return self.const(o["const"])
        if "global" in o:
            return Ptr("unk")
        if "func" in o:
            return Clo(o["func"], [])
        return ["unknown", "?", "operand"]

    def const(self, c: dict):
        k, v, t = c.get("kind"), c.get("value"), c.get("type", "")
        if k == "bool":
            return 1 if v == "true" else 0
        if k == "int":
            n = int(v)
            return n % WORD
        if k == "string":
            return ["str", hexs(v)]
        if k in ("nil", "zero"):
            return 0
        return ["unknown", "?", f"const:{k}"]

    def term(self, v, pos="?"):
        """A value as a term (non-term values are opaque)."""
        if isinstance(v, (int, list)):
            return v
        if isinstance(v, Tup):
            return ["tuple", *[self.term(x, pos) for x in v.items]]
        return ["unknown", span_of(pos) or "?", type(v).__name__.lower()]

    # ---------------------------------------------------------------- state
    def fam_read(self, st: PState, f: str, pos: str):
        """The current value of family f."""
        if f in st.taint:
            return ["unknown", span_of(pos) or "?", "havoc"]
        if f in self.kv:
            return KVRef(f)
        ft = self.ftypes[f]
        if self.tv.T.kind(ft) == "map":
            return MapRef(f)
        if self.tv.T.kind(ft) == "pointer" or self.tv.T.kind(ft) == "slice" and not self.tv.T.is_byte_slice(ft):
            return Ptr("unk")
        return st.over.get(f, ["storage", f])

    def fam_term(self, st: PState, f: str):
        return st.over.get(f, ["storage", f])

    def write(self, st: PState, ins, f: str, path: list, v, stack) -> None:
        val = self.term(v, ins.pos)
        st.writes.append((span_of(ins.pos) or ins.fn.span(), list(stack), f, path, val))
        if path:
            st.over[f] = ["store", self.fam_term(st, f), path, val]
        else:
            st.over[f] = val

    def taint(self, st: PState, fams) -> None:
        for f in fams:
            st.taint.add(f)

    def reach(self, v, st: PState, seen=None) -> set:
        """The families a value lets an opaque callee write."""
        seen = set() if seen is None else seen
        if id(v) in seen:
            return set()
        seen.add(id(v))
        if isinstance(v, Ptr):
            if v.kind in ("recv", "unk"):
                return set(self.fnames)
            if v.kind == "fam":
                return {v.a}
            if v.kind == "local":
                obj = st.mem.get(v.a)
                out = set()
                if isinstance(obj, dict):
                    for x in obj.values():
                        out |= self.reach(x, st, seen)
                elif obj is not None:
                    out |= self.reach(obj, st, seen)
                return out
        if isinstance(v, (MapRef, KVRef)):
            return {v.fam}
        if isinstance(v, RecvVal):
            return {f for f in self.fnames if f in self.kv or self.tv.T.kind(self.ftypes[f]) in ("map", "pointer", "slice")}
        if isinstance(v, StructV):
            out = set()
            for x in v.fields.values():
                out |= self.reach(x, st, seen)
            return out
        if isinstance(v, Tup):
            out = set()
            for x in v.items:
                out |= self.reach(x, st, seen)
            return out
        if isinstance(v, Clo):
            out = set()
            for x in v.binds:
                out |= self.reach(x, st, seen)
            return out
        if isinstance(v, Local):
            obj = st.mem.get(v.oid)
            return self.reach(obj, st, seen) if obj is not None and not isinstance(obj, Local) else set()
        return set()

    def load(self, st: PState, p, ins):
        if isinstance(p, Ptr):
            if p.kind == "fam":
                if p.path:
                    return ["unknown", span_of(ins.pos) or "?", "member"] if p.a not in st.taint else \
                        ["unknown", span_of(ins.pos) or "?", "havoc"]
                return self.fam_read(st, p.a, ins.pos)
            if p.kind == "local":
                obj = st.mem.get(p.a)
                if isinstance(obj, dict):
                    if not p.path:
                        return StructV(obj)
                    x = obj.get(p.path[0], 0)
                    return x if len(p.path) == 1 else ["unknown", span_of(ins.pos) or "?", "member"]
                if isinstance(obj, RecvVal):
                    if not p.path:
                        return obj
                    f = self.fnames[p.path[0]] if isinstance(p.path[0], int) and p.path[0] < len(self.fnames) else None
                    if f is None:
                        return ["unknown", span_of(ins.pos) or "?", "member"]
                    v = self.fam_read(st, f, ins.pos)
                    return v if isinstance(v, (MapRef, KVRef, Ptr)) or f in st.taint else ["storage", f]
                if p.path:
                    return ["unknown", span_of(ins.pos) or "?", "member"]
                return obj if obj is not None else 0
            if p.kind == "recv":
                return RecvVal()
        return ["unknown", span_of(ins.pos) or "?", "load"]

    def store(self, st: PState, p, v, ins, stack) -> None:
        if isinstance(p, Ptr):
            if p.kind == "fam":
                if p.path:
                    self.taint(st, {p.a})
                    return
                ft = self.ftypes[p.a]
                if p.a in self.kv or self.tv.T.kind(ft) in ("map", "pointer", "slice", "struct", "interface") \
                        and not self.tv.T.is_byte_slice(ft):
                    self.taint(st, {p.a})
                    return
                self.write(st, ins, p.a, [], v, stack)
                return
            if p.kind == "local":
                obj = st.mem.get(p.a)
                if not p.path:
                    if isinstance(v, StructV):
                        st.mem[p.a] = dict(v.fields)
                    else:
                        st.mem[p.a] = v
                    return
                if isinstance(obj, RecvVal):
                    # a field of the receiver's copy: materialize the copy's fields from the state
                    obj = {i: self.load(st, Ptr("local", p.a, (i,)), ins) for i in range(len(self.fnames))}
                if not isinstance(obj, dict):
                    obj = {}
                obj = dict(obj)
                if len(p.path) == 1:
                    obj[p.path[0]] = v
                st.mem[p.a] = obj
                return
            if p.kind in ("recv", "unk"):
                self.taint(st, set(self.fnames))
                return
        self.taint(st, set(self.fnames))

    def field_addr(self, st: PState, base, i: int, ins):
        if isinstance(base, Ptr):
            if base.kind == "recv":
                return Ptr("fam", self.fnames[i]) if i < len(self.fnames) else Ptr("unk")
            if base.kind == "fam":
                return Ptr("fam", base.a, base.path + (("member", ins.get("fieldname") or str(i)),))
            if base.kind == "local":
                obj = st.mem.get(base.a)
                if base.path:
                    return Ptr("local", base.a, base.path + (i,))
                return Ptr("local", base.a, (i,))
            return Ptr("unk")
        return Ptr("unk")

    def field(self, st: PState, base, i: int, ins):
        if isinstance(base, RecvVal):
            f = self.fnames[i] if i < len(self.fnames) else None
            if f is None:
                return ["unknown", span_of(ins.pos) or "?", "member"]
            v = self.fam_read(st, f, ins.pos)
            return v if isinstance(v, (MapRef, KVRef, Ptr)) or f in st.taint else ["storage", f]
        if isinstance(base, StructV):
            return base.fields.get(i, 0)
        if isinstance(base, list) and base[:1] == ["param"]:
            return ["member", base, ins.get("fieldname") or str(i)]
        return ["unknown", span_of(ins.pos) or "?", "member"]

    # ---------------------------------------------------------------- arithmetic
    def binop(self, op: str, a, b, ins):
        typ_l = self.operand_type(ins, 0)
        ta, tb = self.term(a, ins.pos), self.term(b, ins.pos)
        T = self.tv.T
        info = T.int_info(typ_l) if typ_l else None
        signed = bool(info and not info[1])
        if T.is_string(typ_l) or T.is_byte_slice(typ_l):
            if op == "+":
                return ["abi.encodePacked", ta, tb]
            if op in ("==", "!="):
                return [op, ["keccak256", ta], ["keccak256", tb]]
            return ["unknown", span_of(ins.pos) or "?", f"string{op}"]
        cmp = {"==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">="}
        if op in cmp:
            o = cmp[op]
            if signed and o in ("<", "<=", ">", ">="):
                o = "s" + o
            return [o, ta, tb]
        if T.is_bool(typ_l) and op in ("&", "|", "^"):
            return [op, ta, tb]
        if not info:
            return ["unknown", span_of(ins.pos) or "?", f"op{op}"]
        bits = info[0]
        arith = {"+": "+", "-": "-", "*": "*", "<<": "<<", "&": "&", "|": "|", "^": "^"}
        if op in arith:
            t = [arith[op], ta, tb] if op != "<<" else ["<<", ta, tb]
            return ["sext", bits, t] if signed else (["trunc", bits, t] if op in ("+", "-", "*", "<<") else t)
        if op == ">>":
            return ["sar", ta, tb] if signed else [">>", ta, tb]
        if op == "&^":
            return ["&", ta, ["~", tb]] if signed else ["trunc", bits, ["&", ta, ["~", tb]]]
        if op in ("/", "%"):
            o = ("sdiv" if op == "/" else "smod") if signed else op
            t = [o, ta, tb]
            return ["sext", bits, t] if signed and op == "/" else t
        return ["unknown", span_of(ins.pos) or "?", f"op{op}"]

    def operand_type(self, ins, k: int) -> str:
        o = ins.operands[k] if k < len(ins.operands) else None
        if not o:
            return ""
        if "v" in o:
            d = ins.fn.defs.get(o["v"])
            return d.type if d else ""
        if "param" in o:
            return ins.fn.params[o["param"]][1]
        if "free" in o:
            return ins.fn.freevars[o["free"]][1]
        if "const" in o:
            return o["const"].get("type", "")
        return ""

    def convert(self, v, src: str, dst: str, ins):
        T = self.tv.T
        t = self.term(v, ins.pos)
        if (T.is_string(src) or T.is_byte_slice(src)) and (T.is_string(dst) or T.is_byte_slice(dst)):
            return t
        si, di = T.int_info(src), T.int_info(dst)
        if si and di:
            sb, su = si
            db, du = di
            if du:
                return t if (su and db >= sb) else ["trunc", db, t]
            return t if (not su and db >= sb) else ["sext", db, t]
        return ["unknown", span_of(ins.pos) or "?", "convert"]

    # ---------------------------------------------------------------- the walk proper
    def run(self, fn: Func) -> list[End]:
        st = PState()
        params = []
        for i, (pn, pt) in enumerate(fn.params):
            if i == 0 and fn.method:
                params.append(Ptr("recv") if self.tv.T.is_pointer(pt) else RecvVal())
            else:
                params.append(["param", pn])
        st.frames = [Frame(fn, params, [])]
        work = [st]
        while work:
            s = work.pop()
            for nxt in self.step(s):
                if isinstance(nxt, End):
                    self.npaths += 1
                    if self.npaths > self.max_paths:
                        raise PathLimit()
                    self.ends.append(nxt)
                else:
                    work.append(nxt)
        return self.ends

    def loop_blocks(self, fn: Func) -> dict:
        """header -> the blocks of its natural loop."""
        out: dict = {}
        for (tail, head) in fn.back_edges():
            body = {head, tail}
            stack = [tail]
            while stack:
                x = stack.pop()
                if x == head:
                    continue
                for p in fn.blocks[x].preds:
                    if p not in body:
                        body.add(p)
                        stack.append(p)
            out.setdefault(head, set()).update(body)
        return out

    def enter(self, st: PState, fr: Frame, b: int, pred: int) -> list:
        """Enter block b from pred: a loop header is summarised."""
        fn = fr.fn
        loops = self._loops.setdefault(fn.id, self.loop_blocks(fn))
        if b in loops and not (pred in loops[b]):
            return self.summarize_loop(st, fr, b, loops[b])
        fr.block, fr.pred, fr.idx = b, pred, 0
        return [st]

    def summarize_loop(self, st: PState, fr: Frame, head: int, body: set) -> list:
        fn = fr.fn
        hit = set()
        for bi in sorted(body):
            for ins in fn.blocks[bi].instrs:
                hit |= self.static_reach(fr, ins, st, depth=0)
        self.taint(st, hit)
        pos = fn.blocks[head].instrs[0].pos if fn.blocks[head].instrs else fn.pos
        st.debt.append({"kind": "loop", "src": span_of(pos) or fn.span(), "what": "loop not iterated; havocked: "
                        + ",".join(sorted(hit))})
        for bi in sorted(body):
            for ins in fn.blocks[bi].instrs:
                if ins.name:
                    fr.regs[ins.name] = ["unknown", span_of(ins.pos or pos) or "?", "loop"]
        outs = []
        exits = sorted({(bi, s) for bi in body for s in fn.blocks[bi].succs if s not in body})
        for k, (bi, s) in enumerate(exits):
            ns = st.fork() if k < len(exits) - 1 else st
            nf = ns.frames[-1]
            nf.block, nf.pred, nf.idx = s, bi, 0
            outs.append(ns)
        return outs

    def static_reach(self, fr: Frame, ins, st: PState, depth: int) -> set:
        """Families an instruction inside a summarised loop may write (statically; unresolved: every family)."""
        op = ins.op
        if op in ("Store", "MapUpdate"):
            return self.addr_root(fr, ins.operands[0], st)
        if op in ("Call", "Go", "Defer"):
            c = ins.call or {}
            if c.get("mode") == "invoke" and c.get("method") in KV_METHODS:
                r = self.addr_root(fr, c.get("value"), st)
                if r and c.get("method") in ("Set", "Delete"):
                    return r
            if c.get("mode") == "builtin":
                return set()
            out = set()
            for a in ([c.get("value")] if c.get("mode") == "invoke" else []) + list(c.get("args") or []):
                out |= self.addr_root(fr, a, st, loose=True)
            callee = c.get("callee")
            if c.get("mode") == "static" and callee in self.prog.funcs and self.prog.funcs[callee].package in self.pkset \
                    and depth < self.inline_depth:
                g = self.prog.funcs[callee]
                if any(self.addr_root(fr, a, st, loose=True) for a in c.get("args") or []):
                    return set(self.fnames)
                return out
            return out
        if op in ("Send", "Select"):
            return set(self.fnames)
        return set()

    def addr_root(self, fr: Frame, o, st: PState, loose=False, seen=None) -> set:
        """The families an operand's value reaches, by its definition chain (statically). A definition met again (a
        cycle of phis through a loop) adds nothing new. loose: an operand handed to a call, where a scalar reaches
        nothing; strict (a store's or map update's address): an unresolved address reaches every family."""
        seen = set() if seen is None else seen
        if not o:
            return set()
        if "param" in o:
            v = fr.params[o["param"]] if o["param"] < len(fr.params) else None
            return self.reach(v, st) if v is not None else set()
        if "free" in o:
            v = fr.free[o["free"]] if o["free"] < len(fr.free) else None
            return self.reach(v, st) if v is not None else set()
        if "global" in o:
            return set(self.fnames) if not loose else set()
        if "v" not in o:
            return set()
        name = o["v"]
        if name in seen:
            return set()
        seen.add(name)
        if name in fr.regs and not isinstance(fr.regs[name], (list, int)) and fr.regs[name] is not None:
            return self.reach(fr.regs[name], st)
        d = fr.fn.defs.get(name)
        if d is None:
            return set(self.fnames)
        if d.op in ("FieldAddr", "Field"):
            base = d.operands[0]
            r = self.addr_root(fr, base, st, loose, seen)
            if self._is_recv(fr, base, st):
                i = d.get("field")
                return {self.fnames[i]} if i is not None and i < len(self.fnames) else set(self.fnames)
            return r
        if d.op in ("UnOp", "IndexAddr", "Index", "Lookup", "Slice", "ChangeType", "MakeInterface", "ChangeInterface",
                    "Convert", "Phi", "Extract", "TypeAssert"):
            out = set()
            for oo in (d.operands if d.op == "Phi" else d.operands[:1]):
                out |= self.addr_root(fr, oo, st, loose, seen)
            return out
        if d.op in ("Alloc", "MakeMap", "MakeSlice", "MakeChan", "BinOp", "Const"):
            return set()
        if loose and not self._ref_type(d.type):
            return set()
        return set(self.fnames)

    def _ref_type(self, t: str) -> bool:
        """A type whose values can reach memory (pointers, maps, slices, channels, functions, interfaces, structs and
        tuples holding them)."""
        T = self.tv.T
        if not t:
            return True
        if T.is_tuple(t):
            return any(self._ref_type(x) for x in T.tuple_elems(t))
        k = T.kind(t)
        if k == "basic":
            return False
        if k == "struct":
            return any(self._ref_type(f["type"]) for f in self.tv.struct_fields(t))
        if k == "array":
            return self._ref_type(T.elem(t))
        return True

    def sval(self, fr: Frame, o, st: PState, depth=0):
        """The value an operand holds, by its definition chain (statically; None when not resolved)."""
        if not o or depth > 16:
            return None
        if "param" in o:
            return fr.params[o["param"]] if o["param"] < len(fr.params) else None
        if "free" in o:
            return fr.free[o["free"]] if o["free"] < len(fr.free) else None
        if "v" in o:
            if o["v"] in fr.regs:
                return fr.regs[o["v"]]
            d = fr.fn.defs.get(o["v"])
            if d is not None and d.op == "UnOp" and d.get("unop") == "*":
                p = self.sval(fr, d.operands[0], st, depth + 1)
                if isinstance(p, Ptr) and p.kind == "local" and not p.path:
                    return st.mem.get(p.a)
            if d is not None and d.op in ("ChangeType", "MakeInterface"):
                return self.sval(fr, d.operands[0], st, depth + 1)
        return None

    def _is_recv(self, fr: Frame, o, st: PState) -> bool:
        v = self.sval(fr, o, st)
        return isinstance(v, RecvVal) or (isinstance(v, Ptr) and v.kind == "recv")

    def step(self, st: PState) -> list:
        fr = st.frames[-1]
        fn = fr.fn
        blk = fn.blocks[fr.block]
        while fr.idx < len(blk.instrs):
            ins = blk.instrs[fr.idx]
            fr.idx += 1
            r = self.exec(st, fr, ins)
            if r is not None:
                return r
        return [self.end(st, "panic", fn.span(), None, "fallthrough")]

    def end(self, st: PState, kind, src, rets, reason) -> End:
        return End(st, kind, src, rets, reason)

    def exec(self, st: PState, fr: Frame, ins):
        op = ins.op
        ops = ins.operands
        val = lambda k: self.operand(fr, ops[k], st)  # noqa: E731
        stack = fr.stack
        if op == "Phi":
            edges = ins.get("edges") or []
            k = edges.index(fr.pred) if fr.pred in edges else -1
            fr.regs[ins.name] = val(k) if k >= 0 else ["unknown", span_of(ins.pos) or "?", "phi"]
            return None
        if op == "Alloc":
            st.nobj += 1
            oid = (len(st.frames), fr.fn.id, ins.name, st.nobj)
            st.mem[oid] = {}
            fr.regs[ins.name] = Ptr("local", oid)
            return None
        if op == "Store":
            p, v = val(0), val(1)
            self.store(st, p, v, ins, stack)
            return None
        if op == "UnOp":
            u = ins.get("unop")
            x = val(0)
            if u == "*":
                g = (ops[0] or {}).get("global") if ops else None
                if g is not None and g in self.nonnil:
                    fr.regs[ins.name] = NonNilErr(self.nonnil[g] or g.rsplit(".", 1)[-1])
                else:
                    fr.regs[ins.name] = self.load(st, x, ins)
            elif u == "<-":
                st.debt.append({"kind": "channel", "src": span_of(ins.pos) or fr.fn.span(), "what": "receive"})
                fr.regs[ins.name] = ["unknown", span_of(ins.pos) or "?", "recv"]
            elif u == "!":
                fr.regs[ins.name] = neg(self.term(x, ins.pos))
            elif u == "-":
                info = self.tv.T.int_info(ins.type)
                t = self.term(x, ins.pos)
                fr.regs[ins.name] = (["trunc", info[0], ["neg", t]] if info[1] else ["sext", info[0], ["neg", t]]) \
                    if info else ["unknown", span_of(ins.pos) or "?", "neg"]
            elif u == "^":
                info = self.tv.T.int_info(ins.type)
                t = self.term(x, ins.pos)
                fr.regs[ins.name] = (["trunc", info[0], ["~", t]] if info[1] else ["~", t]) if info else \
                    ["unknown", span_of(ins.pos) or "?", "not"]
            else:
                fr.regs[ins.name] = ["unknown", span_of(ins.pos) or "?", f"unop{u}"]
            return None
        if op == "BinOp":
            o = ins.get("binop")
            a, b = val(0), val(1)
            if o in ("/", "%"):
                tb = self.term(b, ins.pos)
                if not (isinstance(tb, int) and tb != 0) and self.tv.T.int_info(self.operand_type(ins, 0)):
                    if tb == 0:
                        return [self.end(st, "panic", span_of(ins.pos), None, "division by zero")]
                    zs = st.fork()
                    zs.atoms.append(["==", tb, 0])
                    st.atoms.append(["!=", tb, 0])
                    fr.regs[ins.name] = self.binop(o, a, b, ins)
                    return [self.end(zs, "panic", span_of(ins.pos), None, "division by zero"), st]
            fr.regs[ins.name] = self.binop(o, a, b, ins)
            return None
        if op == "FieldAddr":
            fr.regs[ins.name] = self.field_addr(st, val(0), ins.get("field"), ins)
            return None
        if op == "Field":
            fr.regs[ins.name] = self.field(st, val(0), ins.get("field"), ins)
            return None
        if op in ("ChangeType", "MakeInterface", "ChangeInterface", "SliceToArrayPointer"):
            fr.regs[ins.name] = val(0)
            return None
        if op == "Convert":
            fr.regs[ins.name] = self.convert(val(0), self.operand_type(ins, 0), ins.type, ins)
            return None
        if op == "Extract":
            t = val(0)
            i = ins.get("index")
            if isinstance(t, Tup) and i < len(t.items):
                fr.regs[ins.name] = t.items[i]
            elif isinstance(t, list) and t[:1] == ["call"]:
                fr.regs[ins.name] = ["at", i, t]
            else:
                fr.regs[ins.name] = ["unknown", span_of(ins.pos) or "?", "extract"]
            return None
        if op == "Lookup":
            m, k = val(0), val(1)
            if isinstance(m, MapRef):
                v = ["map", self.fam_term(st, m.fam), self.term(k, ins.pos)]
            elif self.tv.T.is_string(self.operand_type(ins, 0)):
                v = ["unknown", span_of(ins.pos) or "?", "index"]
            else:
                v = ["unknown", span_of(ins.pos) or "?", "lookup"]
            fr.regs[ins.name] = Tup([v, ["unknown", span_of(ins.pos) or "?", "ok"]]) if ins.get("commaok") else v
            return None
        if op == "MapUpdate":
            m, k, v = val(0), val(1), val(2)
            if isinstance(m, MapRef):
                self.write(st, ins, m.fam, [["map", self.term(k, ins.pos)]], v, stack)
            elif isinstance(m, Local):
                pass
            else:
                self.taint(st, {f for f in self.fnames if self.tv.T.kind(self.ftypes[f]) == "map"})
            return None
        if op in ("MakeMap", "MakeSlice", "MakeChan"):
            st.nobj += 1
            fr.regs[ins.name] = Local(("mk", st.nobj))
            return None
        if op == "MakeClosure":
            fr.regs[ins.name] = Clo(ins.get("fn"), [val(k) for k in range(1, len(ops))])
            return None
        if op in ("IndexAddr",):
            base = val(0)
            if isinstance(base, Ptr) and base.kind == "fam":
                fr.regs[ins.name] = Ptr("fam", base.a, base.path + (("index", 0),))
            elif isinstance(base, Ptr) and base.kind == "unk":
                fr.regs[ins.name] = Ptr("unk")
            elif isinstance(base, Ptr) and base.kind == "local":
                fr.regs[ins.name] = Ptr("local", base.a, base.path + ("idx",))
            elif isinstance(base, Local):
                fr.regs[ins.name] = Ptr("local", base.oid, ("idx",))
            else:
                fr.regs[ins.name] = Ptr("unk")
            return None
        if op in ("Index", "Slice", "TypeAssert", "Next", "Range", "Select"):
            if op == "Select":
                st.debt.append({"kind": "channel", "src": span_of(ins.pos) or fr.fn.span(), "what": "select"})
                self.taint(st, set().union(*[self.reach(val(k), st) for k in range(len(ops))]) if ops else set())
            if op == "Slice" and isinstance(val(0), (Ptr, Local)):
                fr.regs[ins.name] = val(0)
                return None
            x = ["unknown", span_of(ins.pos) or "?", op.lower()]
            fr.regs[ins.name] = Tup([x, ["unknown", span_of(ins.pos) or "?", "ok"]]) if \
                (op == "TypeAssert" and ins.get("commaok")) or op == "Next" else x
            return None
        if op == "Send":
            st.debt.append({"kind": "channel", "src": span_of(ins.pos) or fr.fn.span(), "what": "send"})
            self.taint(st, self.reach(val(1), st) if len(ops) > 1 else set())
            return None
        if op in ("Call", "Go", "Defer"):
            return self.call(st, fr, ins)
        if op == "RunDefers" or op == "DebugRef":
            return None
        if op == "Jump":
            return self.enter(st, fr, fr.fn.blocks[fr.block].succs[0], fr.block)
        if op == "If":
            c = self.term(val(0), ins.pos)
            succ = fr.fn.blocks[fr.block].succs
            if c in (0, 1) or isinstance(c, int):
                return self.enter(st, fr, succ[0] if c else succ[1], fr.block)
            e = st.fork()
            st.atoms.append(c)
            e.atoms.append(neg(c))
            out = self.enter(e, e.frames[-1], succ[1], fr.block) + self.enter(st, fr, succ[0], fr.block)
            return out
        if op == "Return":
            rets = [val(k) for k in range(len(ops))]
            if len(st.frames) > 1:
                st.frames.pop()
                caller = st.frames[-1]
                ret_to = fr.ret_to
                if ret_to:
                    caller.regs[ret_to] = rets[0] if len(rets) == 1 else Tup(rets)
                return [st]
            return [self.finish(st, fr, ins, rets)]
        if op == "Panic":
            if any(f.fn.recover >= 0 for f in st.frames):
                # a deferred recover may stop the panic: the path may return normally (its results unknown)
                st.debt.append({"kind": "defer", "src": span_of(ins.pos) or fr.fn.span(),
                                "what": "panic under a deferred recover: not a guard"})
                return [self.end(st, "ok", span_of(ins.pos) or fr.fn.span(), None, None)]
            return [self.end(st, "panic", span_of(ins.pos) or fr.fn.span(), None, self.reason_of(val(0)))]
        fr.regs[ins.name] = ["unknown", span_of(ins.pos) or "?", op.lower()] if ins.name else None
        return None

    def reason_of(self, v):
        if isinstance(v, NonNilErr):
            return v.name
        if isinstance(v, list) and v[:1] == ["str"]:
            try:
                return bytes.fromhex(v[1]).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return None
        if isinstance(v, list) and v[:1] == ["call"] and len(v) > 2 and isinstance(v[2], list) and v[2][:1] == ["str"]:
            return self.reason_of(v[2])
        if isinstance(v, list) and v[:1] == ["global"]:
            return v[1]
        return None

    def finish(self, st: PState, fr: Frame, ins, rets) -> End:
        res = fr.fn.results
        err = None
        for k, t in enumerate(res):
            if t == "error":
                v = rets[k] if k < len(rets) else 0
                err = v
        vals = [r for t, r in zip(res, rets) if t != "error"]
        src = span_of(ins.pos) or fr.fn.span()
        if err is None or err == 0:
            return self.end(st, "ok", src, vals, None)
        if self.definitely_error(err):
            return self.end(st, "error", src, vals, self.reason_of(err))
        # an error that may be nil: the path fails when it is not (a free value), else it succeeds
        e = self.end(st, "maybe", src, vals, self.reason_of(err))
        e.err = self.term(err, ins.pos)
        return e

    def definitely_error(self, v) -> bool:
        if isinstance(v, NonNilErr):
            return True
        return isinstance(v, list) and v[:1] == ["call"] and len(v) > 1 and v[1] in NONNIL_CALLS

    def call(self, st: PState, fr: Frame, ins):
        c = ins.call or {}
        mode = c.get("mode")
        args = [self.operand(fr, a, st) for a in c.get("args") or []]
        pos = ins.pos or c.get("pos") or ""
        if ins.op in ("Go", "Defer"):
            # not walked: the families the callee's body may write (statically, as for a loop), or, for a callee
            # without a body in the document's packages, every family its arguments and closure reach, are havocked
            v = self.operand(fr, c.get("value"), st) if c.get("value") else None
            g = self.prog.funcs.get(c.get("callee")) if mode == "static" and c.get("callee") else None
            binds = v.binds if isinstance(v, Clo) else []
            if g is not None and g.has_body and g.package in self.pkset:
                gf = Frame(g, args, binds)
                hit = set()
                for gi in g.instrs:
                    hit |= self.static_reach(gf, gi, st, depth=1)
            else:
                hit = set()
                for a in args + ([v] if v is not None else []):
                    hit |= self.reach(a, st)
            self.taint(st, hit)
            if ins.op == "Go":
                st.debt.append({"kind": "goroutine", "src": span_of(pos) or fr.fn.span(),
                                "what": "go statement; havocked: " + ",".join(sorted(hit))})
            elif hit:
                st.debt.append({"kind": "defer", "src": span_of(pos) or fr.fn.span(),
                                "what": "deferred call; havocked: " + ",".join(sorted(hit))})
            return None
        if mode == "builtin":
            b = c.get("callee")
            if b == "len" and args:
                r = ["len", self.term(args[0], pos)]
            elif b == "append" and len(args) == 2 and self.tv.T.is_byte_slice(ins.type):
                r = ["abi.encodePacked", self.term(args[0], pos), self.term(args[1], pos)]
            elif b in ("print", "println"):
                r = None
            else:
                hit = set()
                if b in ("copy", "clear", "delete", "append"):
                    for a in args[:1]:
                        hit |= self.reach(a, st)
                    if b == "delete" and len(args) == 2 and isinstance(args[0], MapRef):
                        self.write(st, ins, args[0].fam, [["map", self.term(args[1], pos)]], 0, fr.stack)
                        hit = set()
                self.taint(st, hit)
                r = ["unknown", span_of(pos) or "?", b or "builtin"]
            if ins.name:
                fr.regs[ins.name] = r
            return None
        recv = self.operand(fr, c.get("value"), st) if mode == "invoke" else None
        if mode == "invoke" and isinstance(recv, KVRef) and c.get("method") in KV_METHODS and args:
            m, f = c["method"], recv.fam
            k = self.term(args[0], pos)
            cur = self.fam_term(st, f)
            if m == "Get":
                r = ["map", cur, k]
            elif m == "Has":
                r = ["!=", ["map", cur, k], 0]
            elif m == "Set":
                self.write(st, ins, f, [["map", k]], args[1] if len(args) > 1 else 0, fr.stack)
                r = None
            else:
                self.write(st, ins, f, [["map", k]], 0, fr.stack)
                r = None
            if self.tv.T.is_tuple(ins.type):
                # (value, error) or a lone error: the error is free (a read that fails adds behaviours; a write that
                # returns an error is modelled as written: A-kv)
                err = ["unknown", span_of(pos) or "?", "kv-error"]
                n = len(self.tv.T.tuple_elems(ins.type))
                r = Tup(([r] if r is not None else []) + [err] * (n - (1 if r is not None else 0)))
            elif ins.type == "error":
                r = ["unknown", span_of(pos) or "?", "kv-error"]
            self._ret(fr, ins, r)
            return None
        if mode == "invoke" and isinstance(recv, KVRef) and c.get("method") in KV_READERS:
            # the KV interface's iterators read the store: an opaque value, no write
            name = f"{_otype(fr.fn, c.get('value'))}.{c.get('method')}"
            sig = self.tv.T.entry(c.get("signature") or "")
            self.member(name, ["*"] + list(sig.get("params") or []), list(sig.get("results") or []))
            r = ["call", name, ["unknown", span_of(pos) or "?", "kv-handle"], *[self.term(a, pos) for a in args]]
            self._ret(fr, ins, Tup([["at", i, r] for i in range(len(self.tv.T.tuple_elems(ins.type)))])
                      if self.tv.T.is_tuple(ins.type) else ["unknown", span_of(pos) or "?", "iterator"])
            return None
        callee = c.get("callee") if mode == "static" else None
        clo = self.operand(fr, c.get("value"), st) if mode in ("static", "dynamic") else None
        binds = clo.binds if isinstance(clo, Clo) else []
        if callee and callee in self.prog.funcs:
            g = self.prog.funcs[callee]
            if g.package in self.pkset and g.has_body and len(st.frames) <= self.inline_depth \
                    and all(f.fn.id != g.id for f in st.frames):
                nf = Frame(g, args, binds, ret_to=ins.name or None, stack=fr.stack + (span_of(pos),))
                st.frames.append(nf)
                return self.enter(st, nf, 0, -1)
        # opaque
        hit = set()
        for a in args + ([recv] if recv is not None else []) + binds:
            hit |= self.reach(a, st)
        if isinstance(clo, Clo):
            hit |= self.reach(clo, st)
        if mode == "dynamic" and not isinstance(clo, Clo):
            for a in args:
                hit |= self.reach(a, st)
        self.taint(st, hit)
        sig = self.tv.T.entry(c.get("signature") or "")
        if mode == "invoke":
            name = f"{_otype(fr.fn, c.get('value'))}.{c.get('method')}"
            r = ["call", name, self.term(recv, pos) if not isinstance(recv, KVRef) else
                 ["unknown", span_of(pos) or "?", "kv-handle"], *[self.term(a, pos) for a in args]]
            self.member(name, ["*"] + list(sig.get("params") or []), list(sig.get("results") or []))
        else:
            name = callee or f"dynamic.{c.get('signature')}"
            r = ["call", name, *[self.term(a, pos) for a in args]]
            self.member(name, list(sig.get("params") or []), list(sig.get("results") or []))
        res = self.tv.T.tuple_elems(ins.type) if self.tv.T.is_tuple(ins.type) else None
        # a value that an opaque call derives from a KV family or a state field handle (a store handle held in a field)
        kvsrc = [x.fam for x in ([recv] + args) if isinstance(x, KVRef)]
        if res:
            out = Tup([["at", i, r] for i in range(len(res))])
        elif kvsrc:
            out = KVRef(kvsrc[0])
        else:
            out = r
        if ins.name and self.tv.is_kv_iface(ins.type):
            f = _root_field(fr.fn, {"v": ins.name}, self.fnames, self.machine, self.tv, 0)
            if f in self.kv:
                out = KVRef(f)
        self._ret(fr, ins, out)
        return None

    def member(self, name: str, params: list, results: list) -> None:
        """The ABI signature of a function a call term names (info.members; the model encodes a call's arguments with
        it): a receiver ("*") and every parameter and result as its scalar ABI shape (an opaque word when it has none);
        the selector is the first four bytes of keccak256 of the name."""
        from ...keccak import keccak256
        ins = [dict({"type": "uint256"} if t == "*" else self.tv.abi_scalar(t), name=f"a{i}") for i, t in enumerate(params)]
        outs = [dict(self.tv.abi_scalar(t), name="") for t in results]
        self.members[name] = {"name": name, "kind": "function", "visibility": "external", "mutability": "nonpayable",
                              "selector": "0x" + keccak256(name.encode("utf-8"))[:4].hex(), "inputs": ins,
                              "outputs": outs}

    def _ret(self, fr: Frame, ins, r):
        if ins.name:
            fr.regs[ins.name] = r

    _loops: dict = {}


# ------------------------------------------------------------------------------------------------ machines
def machines_of(prog: Program, pkset: set) -> list:
    """[(type id, [method Func])] sorted: named struct types of the packages with exported methods declared there."""
    T = prog.types
    out = {}
    for fid, fn in prog.funcs.items():
        if not fn.method or fn.package not in pkset or fn.synthetic or fn.parent or not fn.has_body:
            continue
        if not fn.name[:1].isupper() or not fn.params:
            continue
        rt = fn.params[0][1]
        base = T.pointer_elem(rt) or rt
        e = T.entry(base)
        if e.get("kind") != "named" or e.get("pkg") not in pkset:
            continue
        if T.kind(base) != "struct":
            continue
        out.setdefault(base, []).append(fn)
    return [(k, sorted(v, key=lambda f: f.name)) for k, v in sorted(out.items())]


def kv_fields(prog: Program, tv: TypeView, typ: str, methods: list, fnames: list, pkset: set) -> set:
    """Fields an action uses as a KV store (module docstring), found by the definition chains of KV invokes."""
    out = set()
    seen = set()
    todo = list(methods)
    while todo:
        fn = todo.pop()
        if fn.id in seen:
            continue
        seen.add(fn.id)
        for ins in fn.instrs:
            c = ins.call
            if not c:
                continue
            if c.get("mode") == "static" and c.get("callee") in prog.funcs and \
                    prog.funcs[c["callee"]].package in pkset:
                todo.append(prog.funcs[c["callee"]])
            if c.get("mode") != "invoke" or c.get("method") not in KV_METHODS:
                continue
            sig = tv.T.entry(c.get("signature") or "")
            ps = sig.get("params") or []
            if not ps or not tv.T.is_byte_slice(ps[0]):
                continue
            f = _root_field(fn, c.get("value"), fnames, typ, tv, 0)
            if f:
                out.add(f)
    return out


def _root_field(fn: Func, o, fnames, typ, tv, depth):
    if not o or depth > 16 or "v" not in o:
        return None
    d = fn.defs.get(o["v"])
    if d is None:
        return None
    if d.op in ("Field", "FieldAddr"):
        bt = _otype(fn, d.operands[0])
        b = tv.T.pointer_elem(bt) or bt
        if b == typ:
            i = d.get("field")
            return fnames[i] if i is not None and i < len(fnames) else None
        return _root_field(fn, d.operands[0], fnames, typ, tv, depth + 1)
    if d.op in ("UnOp", "ChangeType", "MakeInterface", "ChangeInterface"):
        return _root_field(fn, d.operands[0], fnames, typ, tv, depth + 1)
    if d.op == "Call" and d.call:
        cc = d.call
        for a in ([cc.get("value")] if cc.get("mode") == "invoke" else []) + list(cc.get("args") or []):
            r = _root_field(fn, a, fnames, typ, tv, depth + 1)
            if r:
                return r
    return None


def _otype(fn: Func, o) -> str:
    if not o:
        return ""
    if "v" in o:
        d = fn.defs.get(o["v"])
        return d.type if d else ""
    if "param" in o:
        return fn.params[o["param"]][1]
    return ""


def action_record(w: Walker, fn: Func, ends: list, limit: bool, tv: TypeView, ret_types: list) -> tuple[dict, list]:
    """The action's transitions record from its finished paths (module docstring), and its debt."""
    seq = 0
    guards: dict = {}
    writes = []
    debt = []
    ok_paths = []
    order = []
    for e in ends:
        K = conj(e.st.atoms)
        for d in e.st.debt:
            debt.append(d)
        if limit:
            continue
        if e.kind in ("error", "panic", "maybe") and not e.st.writes and not e.st.taint:
            # a maybe-error path fails only where its error is not nil (a free value), and succeeds otherwise
            x = neg(K) if e.kind != "maybe" else (["==", e.err, 0] if K == 1 else ["||", neg(K), ["==", e.err, 0]])
            g = guards.setdefault(e.src, {"src": e.src, "kind": "revert", "reason": e.reason, "expr": x,
                                          "reaches": []})
            g["reaches"].append({"seq": seq, "stack": [], "expr": x})
            order.append(["guard", e.src, len(g["reaches"]) - 1])
            seq += 1
            if e.kind != "maybe":
                continue
        ok_paths.append((K, e))
        for (src, stack, f, path, val) in e.st.writes:
            writes.append({"seq": seq, "src": src, "stack": stack, "family": f, "path": path, "value": val, "cond": K})
            seq += 1
        for f in sorted(e.st.taint):
            writes.append({"seq": seq, "src": e.src, "stack": [], "family": f, "path": [],
                           "value": ["unknown", e.src, "havoc"], "cond": K})
            seq += 1
    if limit:
        debt.append({"kind": "path_limit", "src": fn.span(), "what": f"more than {w.max_paths} paths: every family "
                     "havocked, no guard"})
        for f in w.fnames:
            writes.append({"seq": seq, "src": fn.span(), "stack": [], "family": f, "path": [],
                           "value": ["unknown", fn.span(), "havoc"], "cond": 1})
            seq += 1
    post = {}
    fams = sorted({x["family"] for x in writes})
    for f in fams:
        acc = ["storage", f]
        for K, e in reversed(ok_paths):
            fin = ["unknown", e.src, "havoc"] if f in e.st.taint else e.st.over.get(f, ["storage", f])
            acc = fin if K == 1 else ["?", K, fin, acc]
        if limit:
            acc = ["unknown", fn.span(), "havoc"]
        post[f] = acc
    rets = None
    if ok_paths and not limit and ret_types:
        acc = None
        for K, e in reversed(ok_paths):
            vs = [w.term(v, e.src) for v in (e.rets or [])]
            v = vs[0] if len(vs) == 1 else (["tuple", *vs] if vs else None)
            if v is None:
                acc = None
                break
            acc = v if acc is None or K == 1 else ["?", K, v, acc]
        rets = acc
    effects = sorted({(x["src"], x["family"]) for x in writes})
    params = []
    for (pn, pt) in fn.params[1:]:
        p = {"name": pn, "type": tv.abi(pt)["type"], "width": tv.width(pt), "location": "default"}
        params.append(p)
    rec = {
        "name": fn.name, "selector": None, "src": fn.span(), "modifiers": [], "principal": None,
        "guards": [guards[k] for k in guards], "effects": [{"family": f, "src": s} for s, f in effects],
        "cost": {"terms": []}, "edges": [], "declared_in": fn.params[0][1].lstrip("*").rsplit("/", 1)[-1],
        "params": params, "returns": rets, "payable": False,
        "mutability": "nonpayable" if writes else "view",
        "checks": [], "panics": [], "calls": [], "writes": writes, "mstores": [], "events": [], "loops": [],
        "post": post, "order": order,
    }
    dd = sorted({json.dumps(dict(d, action=fn.name), sort_keys=True) for d in debt})
    return rec, [json.loads(x) for x in dd]


def machine_document(prog: Program, tv: TypeView, cfg: dict, prov: dict, typ: str, methods: list, pkset: set) -> dict:
    fields = tv.struct_fields(typ)
    fnames = [f["name"] for f in fields]
    kv = kv_fields(prog, tv, typ, methods, fnames, pkset)
    types: dict = {}
    storage, layout = [], []
    short = typ.rsplit("/", 1)[-1]
    for i, f in enumerate(fields):
        if f["name"] in kv:
            kt = tv.key_tid("[]byte", types)
            vt = tv.tid("[]byte", types)
            tid = f"t_mapping({kt},{vt})"
            types.setdefault(tid, {"encoding": "mapping", "key": kt, "value": vt, "numberOfBytes": "32",
                                   "label": "mapping(bytes => bytes)"})
        else:
            tid = tv.tid(f["type"], types)
        t = types[tid]
        fam = {"name": f["name"], "slot": i, "offset": 0,
               "kind": "mapping" if t["encoding"] == "mapping" else "scalar", "value": t["label"]}
        if t["encoding"] == "mapping":
            fam["key"] = types[t["key"]]["label"]
            fam["value"] = types[t["value"]]["label"]
        storage.append(fam)
        layout.append({"label": f["name"], "slot": str(i), "offset": 0, "type": tid, "contract": short})
    actions, debt, functions, members = [], [], {}, {}
    for fn in methods:
        w = Walker(prog, tv, pkset, typ, fields, kv, cfg["limits"])
        w._loops = {}
        limit = False
        try:
            ends = w.run(fn)
        except PathLimit:
            ends, limit = w.ends, True
        rec, d = action_record(w, fn, ends, limit, tv, [t for t in fn.results if t != "error"])
        for k, v in w.members.items():
            members[k] = [v]
        actions.append(rec)
        debt.extend(d)
        functions[fn.name] = {"name": fn.name, "kind": "function", "visibility": "external",
                              "mutability": rec["mutability"], "selector": None,
                              "inputs": [dict(tv.abi(pt), name=pn) for pn, pt in fn.params[1:]],
                              "outputs": [dict(tv.abi(t), name="") for t in fn.results if t != "error"],
                              "declared_in": short}
    if ((cfg.get("machines") or {}).get("nil_maps")) == "unknown":
        # I108 (Q60), under the config's opt-in: a Go map field is nil until it is made (a struct's zero value, or a
        # constructor that leaves it nil), and a write into a nil map panics. Without a constructor rule the frontend
        # cannot tell which state made it, so every element write into a map field (a KV store is not a Go map) is
        # nil_map debt, and the typed model refuses the document (holon.sorts.model3): every law over it is UNKNOWN.
        gomaps = {f["name"] for f in fields if f["name"] not in kv
                  and types[next(x["type"] for x in layout if x["label"] == f["name"])]["encoding"] == "mapping"}
        for rec in actions:
            for w in rec["writes"]:
                if w["family"] in gomaps and w.get("path") and isinstance(w["path"][0], list) \
                        and w["path"][0][:1] == ["map"]:
                    debt.append({"action": rec["name"], "kind": "nil_map", "src": w["src"],
                                 "what": f"a write into the map field {w['family']}, which may be nil (Q60: a nil-map "
                                         "write panics; no constructor rule)"})
        debt = [json.loads(x) for x in sorted({json.dumps(d, sort_keys=True) for d in debt})]
    sels: dict = {}
    for k, (v,) in sorted(members.items()):
        if sels.setdefault(v["selector"], k) != k:
            raise ExtractionError(f"{typ}: calls {sels[v['selector']]} and {k} share the selector {v['selector']}")
    assumptions = [{"id": k, "text": v} for k, v in sorted(ASSUMPTIONS.items())]
    if kv:
        assumptions.append({"id": KV_ASSUMPTION[0], "text": KV_ASSUMPTION[1]})
        assumptions.sort(key=lambda a: a["id"])
    info = {"info_version": INFO_VERSION, "contract": short, "unit": prov["unit"], "linearization": [short],
            "layout": {"storage": layout, "types": dict(sorted(types.items()))},
            "functions": dict(sorted(functions.items())), "members": dict(sorted(members.items())), "errors": {}, "events": {},
            "immutables": {}}
    return {
        "facts_version": FACTS_VERSION,
        "target": {"repo": cfg["target"]["repo"], "commit": cfg["target"]["commit"], "scope": f"go machine {typ}"},
        "extraction": {"method": "extracted", "frontend": "go", "kind": "transitions",
                       "frontend_version": FRONTEND_VERSION, "config": prov["config"], "tool": prov["tool"],
                       "inputs": prov["inputs"]},
        "contract": typ, "constants": {}, "storage": storage, "inherited_storage": [],
        "actions": sorted(actions, key=lambda a: a["name"]), "assumptions": assumptions,
        "debt": sorted(debt, key=lambda d: (d["action"], d["kind"], d["src"], d["what"])),
        "info": info,
    }


def extract(config_path, src=None, root=None) -> dict:
    """{file name: document} for every machine of every document of the config."""
    root = Path(root).resolve() if root else GX.REPO_ROOT
    config_path = Path(config_path)
    try:
        cfg = GX.load_config(config_path)
    except GX.Refused as e:
        raise Refused(str(e))
    src = Path(src) if src else GX.resolve_src(cfg, root)
    if not src.is_dir():
        raise Refused(f"source tree {src} is missing")
    try:
        go, go_ver = GX.check_go(root)
        digest = GX.ssadump_digest()
        xt = GX.x_tools_version()
        binary = GX.build_ssadump(go, digest)
    except GX.Refused as e:
        raise Refused(str(e))
    patterns = sorted({p for pk in cfg["documents"].values() for p in pk})
    ws_parent = Path(tempfile.mkdtemp(prefix="holon-gom-ws-"))
    try:
        ws = ws_parent / "src"
        ws.mkdir()
        GX.make_workspace(src, ws)
        try:
            dump = GX.run_ssadump(binary, ws.resolve(), patterns)
            prog = Program(dump)
        except (DumpError, GX.Refused) as e:
            raise Refused(str(e))
        missing = [p for p in patterns if p not in prog.packages]
        if missing:
            raise Refused(f"packages did not load: {missing}")
        hashes = {}
        for pk in prog.packages.values():
            for f in pk["files"]:
                if f.startswith("<outside>/"):
                    raise Refused(f"package {pk['path']}: compiled file {f} lies outside the source tree")
                hashes[f] = GX._sha(ws / f)
    finally:
        shutil.rmtree(ws_parent, ignore_errors=True)
    cfg_sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
    tv = TypeView(prog)
    out = {}
    for stem, pks in sorted(cfg["documents"].items()):
        pkset = set(pks)
        files = sorted(f for p in sorted(pkset) for f in prog.packages[p]["files"])
        prov = {"config": {"path": GX.rel_to(config_path, root), "sha256": cfg_sha},
                "tool": {"go": go_ver, "x_tools": xt, "ssadump_sha256": digest},
                "inputs": [{"unit": f, "sha256": hashes[f]} for f in files], "unit": files[0] if files else ""}
        for typ, methods in machines_of(prog, pkset):
            doc = machine_document(prog, tv, cfg, prov, typ, methods, pkset)
            _validate(doc, root)
            name = f"{stem}.{typ.rsplit('/', 1)[-1].split('.', 1)[-1]}.extracted.json"
            if name in out:
                raise Refused(f"two machines write {name}")
            out[name] = doc
    return out


def _validate(doc: dict, root: Path) -> None:
    """The document validates against spec/schemas/facts_0_3.schema.json (branch go_transitions) when the root holds
    it; a document that does not is an extraction error (exit 3), nothing written."""
    from ...schema import errors
    p = Path(root) / "spec" / "schemas" / "facts_0_3.schema.json"
    if not p.exists():
        return
    errs = errors(doc, json.loads(p.read_text(encoding="utf-8")))
    if errs:
        raise ExtractionError(f"{doc['contract']}: the document does not validate against "
                              "spec/schemas/facts_0_3.schema.json: " + "; ".join(errs[:5]))


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    ap = argparse.ArgumentParser(prog="holon extract go_machines")
    ap.add_argument("--root")
    ap.add_argument("--config", required=True)
    ap.add_argument("--src")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else GX.REPO_ROOT
    try:
        docs = extract(Path(a.config), a.src, root)
    except Refused as e:
        print(f"holon extract go_machines: refused: {e}", file=sys.stderr)
        return 2
    except ExtractionError as e:
        print(f"holon extract go_machines: extraction failed: {e}", file=sys.stderr)
        return 3
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in sorted(docs):
        (out / name).write_text(render(docs[name]), encoding="utf-8")
    print(f"holon extract go_machines: wrote {len(docs)} machine document(s) to {out}")
    return 0
