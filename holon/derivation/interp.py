"""Rule G1: an interpreter of the consumer section's SSA (go/ssa as ssadump prints it), with Go's semantics for every op
it evaluates and Go's runtime panics with their runtime texts; anything else is Unsupported, never guessed.

  Interp(section, environment, answers).run(batch_json) -> {"status", "error", "panic", "info", "site", "reason"}

environment is the sidecar's extract.environment (kinds and result shapes of the boundary functions); answers holds the
real library's answers to oracle calls ({function: {sha256 of the argument: answer}}). An oracle call whose answer is
missing raises NeedAnswer(function, argument); the driver asks the oracle and runs the case again.

One documented approximation: append's growth gives the new backing array exactly the new length as its capacity (Go
rounds the capacity up to its allocation size classes); cap() of a grown slice is unsupported, and the only other way to
observe the difference, two slices sharing a grown backing array past one's length, is not detected.
"""
from __future__ import annotations

import hashlib

from . import natives as N
from .values import (AObj, Box, Fn, GoPanic, Iface, Native, Ptr, SObj, Slice, Types, Unsupported, assign, build,
                     copy_value, deref, dump, eq, wrap)

SUPPORTED_OPS = frozenset({"Alloc", "BinOp", "UnOp", "Field", "FieldAddr", "Index", "IndexAddr", "Slice", "Store",
                           "Call", "Convert", "ChangeType", "MakeInterface", "ChangeInterface", "TypeAssert", "Extract",
                           "Phi", "If", "Jump", "Return", "Panic", "MakeSlice", "MakeClosure"})
MAX_STEPS = 60_000_000
MAX_ALLOC = 1 << 28


class NeedAnswer(Exception):
    def __init__(self, fid: str, arg: bytes):
        super().__init__(fid)
        self.fid, self.arg = fid, arg


def arg_key(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Func:
    __slots__ = ("fid", "blocks", "types", "params", "free")

    def __init__(self, fid: str, raw: dict):
        self.fid = fid
        self.blocks = {b["index"]: b for b in raw["blocks"]}
        self.params = raw.get("params") or []
        self.free = raw.get("freevars") or []
        self.types = {}
        for b in raw["blocks"]:
            for ins in b["instrs"]:
                if ins.get("name"):
                    self.types[ins["name"]] = ins.get("type") or ""


class Interp:
    def __init__(self, section: dict, environment: dict, answers: dict):
        self.ty = Types(section["types"])
        self.raw = section["functions"]
        self.funcs: dict = {}
        self.kinds = {e["function"]: e["kind"] for e in section["environment"]}
        self.declared = environment or {}
        self.answers = answers
        self.ginit = {g["global"]: g for g in section["globals"]}
        self.globals: dict = {}
        self.entry = section["entry"]
        self.steps = 0
        self.pos = ""
        self.grown: list = []     # backing arrays made by append's growth (their capacity is approximate)

    # ------------------------------------------------------------------ entry
    def run(self, batch_json) -> dict:
        f = self.func(self.entry)
        if len(f.params) != 2:
            raise Unsupported("the entry is not a method with one parameter")
        rtype = self.ty.pointee(f.params[0]["type"])
        recv = Ptr(self.ty.zero(rtype)) if self.ty.is_aggregate(rtype) else Ptr(Box(self.ty.zero(rtype)))
        out = {"status": None, "error": None, "panic": None, "info": None, "site": None, "reason": None}
        try:
            batch = build(self.ty, f.params[1]["type"], batch_json)
            ret, site = self.call_fn(self.entry, [recv, batch], [], top=True)
            out["site"] = site
            if ret is None:
                out["status"] = "ok"
            else:
                out["status"], out["error"] = "error", N.error_text(ret)
        except GoPanic as p:
            out["status"], out["panic"], out["site"] = "panic", p.text, self.pos
        except Unsupported as u:
            return {"status": "unsupported", "error": None, "panic": None, "info": None, "site": None,
                    "reason": str(u)}
        except RecursionError:
            return {"status": "unsupported", "error": None, "panic": None, "info": None, "site": None,
                    "reason": "call depth"}
        try:
            out["info"] = dump(self.ty, rtype, deref(recv), N.error_text)
        except Unsupported as u:
            return {"status": "unsupported", "error": None, "panic": None, "info": None, "site": None,
                    "reason": f"dump: {u}"}
        return out

    def func(self, fid: str) -> Func:
        f = self.funcs.get(fid)
        if f is None:
            f = self.funcs[fid] = Func(fid, self.raw[fid])
        return f

    # ------------------------------------------------------------------ operands
    def const(self, c: dict):
        k = c.get("kind")
        if k == "int":
            return int(c["value"])
        if k == "bool":
            return c["value"] == "true"
        if k == "string":
            return c["value"]
        if k == "nil":
            return None
        if k == "zero":
            return self.ty.zero(c["type"])
        raise Unsupported(f"a constant of kind {k}")

    def global_ptr(self, g: str) -> Ptr:
        p = self.globals.get(g)
        if p is None:
            e = self.ginit.get(g)
            if e is None or e["kind"] == "unaccounted":
                raise Unsupported(f"global {g}")
            if e["kind"] == "native":
                if g not in N.GLOBALS:
                    raise Unsupported(f"native global {g}")
                v = N.GLOBALS[g]()
            else:
                v = self.term(e["value"])
            p = self.globals[g] = Ptr(Box(v))
        return p

    def term(self, t):
        """A package initializer's value term (the frontend's go.globals): an errors.New of a string, a constant."""
        if isinstance(t, list) and t and t[0] == "call" and len(t) == 3 and t[1] == "errors.New" \
                and len(t[2]) == 1 and isinstance(t[2][0], list) and t[2][0][:1] == ["str"]:
            return N.error_value(t[2][0][1])
        if isinstance(t, list) and len(t) == 2 and t[0] in ("const", "str"):
            return t[1]
        raise Unsupported(f"a global's value term {str(t)[:80]}")

    def val(self, o, env, args, free):
        if o is None:
            return None
        if "v" in o:
            try:
                return env[o["v"]]
            except KeyError:
                raise Unsupported(f"value {o['v']} used before its definition")
        if "param" in o:
            return args[o["param"]]
        if "free" in o:
            return free[o["free"]]
        if "const" in o:
            return self.const(o["const"])
        if "global" in o:
            return self.global_ptr(o["global"])
        if "func" in o:
            return Fn(o["func"], [])
        raise Unsupported(f"operand {o}")

    def type_of(self, o, f: Func) -> str:
        if "v" in o:
            return f.types.get(o["v"], "")
        if "param" in o:
            return f.params[o["param"]]["type"]
        if "free" in o:
            return f.free[o["free"]]["type"]
        if "const" in o:
            return o["const"]["type"]
        raise Unsupported(f"the type of operand {o}")

    # ------------------------------------------------------------------ memory
    def load(self, p):
        if p is None:
            raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
        if not isinstance(p, Ptr):
            raise Unsupported("a load through a non-pointer")
        return copy_value(deref(p))

    def store(self, p, v) -> None:
        if p is None:
            raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
        o, i = p.o, p.i
        if i is None:
            if isinstance(o, Box):
                o.v = v
            else:
                assign(o, v)
        elif isinstance(o, SObj):
            o.f[i] = v
        elif isinstance(o, AObj):
            o.e[i] = v
        else:
            raise Unsupported("a store into a non-aggregate")

    def elem_ptr(self, arr: AObj, k: int) -> Ptr:
        if self.ty.is_aggregate(arr.t):
            return Ptr(arr.e[k])
        return Ptr(arr, k)

    # ------------------------------------------------------------------ calls
    def call_fn(self, fid: str, args: list, free: list, top: bool = False, rtype: str = ""):
        if fid not in self.raw:
            return self.env_call(fid, args, rtype), None
        f = self.func(fid)
        env: dict = {}
        b = f.blocks[0]
        prev = None
        while True:
            instrs = b["instrs"]
            k = 0
            if prev is not None:
                pend = []
                preds = b["preds"]
                while k < len(instrs) and instrs[k]["op"] == "Phi":
                    ins = instrs[k]
                    pend.append((ins["name"], self.val(ins["operands"][preds.index(prev)], env, args, free)))
                    k += 1
                for n, v in pend:
                    env[n] = v
            nxt = None
            for ins in instrs[k:]:
                self.steps += 1
                if self.steps > MAX_STEPS:
                    raise Unsupported(f"more than {MAX_STEPS} steps")
                op = ins["op"]
                self.pos = ins.get("pos") or self.pos
                if op == "If":
                    c = self.val(ins["operands"][0], env, args, free)
                    nxt = b["succs"][0 if c else 1]
                    break
                if op == "Jump":
                    nxt = b["succs"][0]
                    break
                if op == "Return":
                    rs = [self.val(o, env, args, free) for o in ins["operands"]]
                    ret = None if not rs else (rs[0] if len(rs) == 1 else tuple(rs))
                    return ret, (ins.get("pos") or None) if top else None
                if op == "Panic":
                    x = self.val(ins["operands"][0], env, args, free)
                    raise GoPanic(self.panic_text(x))
                if op == "Phi":
                    raise Unsupported("a phi after a non-phi instruction")
                h = OPS.get(op)
                if h is None:
                    raise Unsupported(f"op {op}")
                v = h(self, ins, env, args, free, f)
                if ins.get("name"):
                    env[ins["name"]] = v
            if nxt is None:
                raise Unsupported(f"block {b['index']} of {fid} falls off its end")
            prev = b["index"]
            b = f.blocks[nxt]

    def panic_text(self, x) -> str:
        if isinstance(x, Iface):
            if isinstance(x.v, Native) and x.v.kind == "err":
                return x.v.v
            if isinstance(x.v, str):
                return x.v
        raise Unsupported("a panic value of no known text")

    def env_call(self, fid: str, args: list, rtype: str = ""):
        kind = self.kinds.get(fid)
        if kind == "native":
            fn = N.FUNCS.get(fid)
            if fn is None:
                raise Unsupported(f"native {fid}")
            return fn(self, args)
        if kind == "slice_len":
            s = args[0]
            return 0 if s is None else s.n
        if kind == "encoding":
            p = args[0]
            if not (isinstance(p, Ptr) and isinstance(p.o, Native) and p.o.kind == "element"):
                raise Unsupported(f"{fid} on a value the oracle did not make")
            return (N.new_bytes(p.o.v), None)
        if kind == "oracle":
            return self.oracle(fid, args, rtype)
        raise Unsupported(f"callee {fid} ({kind})")

    def oracle(self, fid: str, args: list, rtype: str = ""):
        shape = (self.declared.get(fid) or {}).get("results")
        if len(args) != 1:
            raise Unsupported(f"oracle {fid} with {len(args)} arguments")
        arg = N.slice_bytes(args[0])
        a = (self.answers.get(fid) or {}).get(arg_key(arg))
        if a is None:
            raise NeedAnswer(fid, arg)
        if "panic" in a:
            raise GoPanic(a["panic"])
        if "error" in a:
            return (None, N.error_value(a["error"]))
        rt = self.ty.entry(rtype) if rtype else {}
        first = (rt.get("elems") or [None])[0] if rt.get("kind") == "tuple" else None
        if first is None or self.ty.kind(first) != "slice":
            raise Unsupported(f"oracle {fid}: its first result is not a slice")
        el = self.ty.entry(first)["elem"]
        if shape == "bytes":
            if a["nil"]:
                return (None, None)
            b = bytes.fromhex(a["bytes"][2:])
            return (Slice(AObj(el, bytearray(b)), 0, len(b), len(b)), None)
        if shape == "encodings":
            if a["nil"]:
                return (None, None)
            items = [Ptr(Native("element", bytes.fromhex(h[2:]))) for h in a["items"]]
            return (Slice(AObj(el, items), 0, len(items), len(items)), None)
        raise Unsupported(f"oracle {fid}: result shape {shape}")


# ---------------------------------------------------------------------------------------------- ops
def _bounds_index(i: int, n: int):
    if i < 0:
        raise GoPanic(f"runtime error: index out of range [{i}]")
    if i >= n:
        raise GoPanic(f"runtime error: index out of range [{i}] with length {n}")


def op_alloc(it, ins, env, args, free, f):
    t = it.ty.pointee(ins["type"])
    if t == "math/big.Int":
        return Ptr(Native("big", 0))
    if it.ty.is_aggregate(t):
        return Ptr(it.ty.zero(t))
    return Ptr(Box(it.ty.zero(t)))


def _div(x: int, y: int) -> int:
    q = abs(x) // abs(y)
    return q if (x >= 0) == (y >= 0) else -q


def op_binop(it, ins, env, args, free, f):
    o = ins["binop"]
    x = it.val(ins["operands"][0], env, args, free)
    y = it.val(ins["operands"][1], env, args, free)
    if o == "==":
        return eq(x, y)
    if o == "!=":
        return not eq(x, y)
    if o in ("<", "<=", ">", ">="):
        if not (isinstance(x, (int, str)) and type(x) is type(y)) or isinstance(x, bool):
            raise Unsupported(f"ordering of {type(x).__name__}")
        return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[o]
    t = ins.get("type") or ""
    if isinstance(x, str) and o == "+":
        return x + y
    if not (isinstance(x, int) and isinstance(y, int)) or isinstance(x, bool):
        raise Unsupported(f"binop {o} on {type(x).__name__}")
    info = it.ty.int_info(t)
    if o == "+":
        return wrap(x + y, info)
    if o == "-":
        return wrap(x - y, info)
    if o == "*":
        return wrap(x * y, info)
    if o in ("/", "%"):
        if y == 0:
            raise GoPanic("runtime error: integer divide by zero")
        q = _div(x, y)
        return wrap(q if o == "/" else x - q * y, info)
    if o == "&":
        return wrap(x & y, info)
    if o == "|":
        return wrap(x | y, info)
    if o == "^":
        return wrap(x ^ y, info)
    if o == "&^":
        return wrap(x & ~y, info)
    if o in ("<<", ">>"):
        if y < 0:
            raise GoPanic("runtime error: negative shift amount")
        if info is None:
            raise Unsupported("a shift of an untyped value")
        if y >= info[0]:
            return 0 if (o == "<<" or x >= 0) else -1
        return wrap(x << y, info) if o == "<<" else wrap(x >> y, info)
    raise Unsupported(f"binop {o}")


def op_unop(it, ins, env, args, free, f):
    o = ins["unop"]
    x = it.val(ins["operands"][0], env, args, free)
    if o == "*":
        return it.load(x)
    if o == "!":
        return not x
    info = it.ty.int_info(ins.get("type") or "")
    if o == "-":
        return wrap(-x, info)
    if o == "^":
        return wrap(~x, info)
    raise Unsupported(f"unop {o}")


def op_field(it, ins, env, args, free, f):
    x = it.val(ins["operands"][0], env, args, free)
    if not isinstance(x, SObj):
        raise Unsupported("Field of a non-struct")
    return x.f[ins["field"]]


def _struct_obj(p):
    if p is None:
        raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
    o = deref(p)
    if not isinstance(o, SObj):
        raise Unsupported("FieldAddr of a pointer to a non-struct")
    return o


def op_fieldaddr(it, ins, env, args, free, f):
    o = _struct_obj(it.val(ins["operands"][0], env, args, free))
    k = ins["field"]
    ft = it.ty.field_types(o.t)[k]
    if it.ty.is_aggregate(ft):
        return Ptr(o.f[k])
    return Ptr(o, k)


def op_index(it, ins, env, args, free, f):
    x = it.val(ins["operands"][0], env, args, free)
    i = it.val(ins["operands"][1], env, args, free)
    if isinstance(x, AObj):
        _bounds_index(i, len(x.e))
        return copy_value(x.e[i])
    if isinstance(x, str):
        b = x.encode("utf-8", "surrogateescape")
        _bounds_index(i, len(b))
        return b[i]
    raise Unsupported("Index of a non-array")


def op_indexaddr(it, ins, env, args, free, f):
    x = it.val(ins["operands"][0], env, args, free)
    i = it.val(ins["operands"][1], env, args, free)
    if x is None:
        tx = it.type_of(ins["operands"][0], f)
        if it.ty.kind(tx) == "slice":
            _bounds_index(i, 0)
        raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
    if isinstance(x, Slice):
        _bounds_index(i, x.n)
        return it.elem_ptr(x.arr, x.off + i)
    if isinstance(x, Ptr):
        arr = deref(x)
        if not isinstance(arr, AObj):
            raise Unsupported("IndexAddr of a pointer to a non-array")
        _bounds_index(i, len(arr.e))
        return it.elem_ptr(arr, i)
    raise Unsupported("IndexAddr of a non-slice")


def _neg(v):
    return v is not None and v < 0


def op_slice(it, ins, env, args, free, f):
    ops = ins["operands"]
    x = it.val(ops[0], env, args, free)
    lo = it.val(ops[1], env, args, free) if ops[1] is not None else None
    hi = it.val(ops[2], env, args, free) if ops[2] is not None else None
    mx = it.val(ops[3], env, args, free) if len(ops) > 3 and ops[3] is not None else None
    tx = it.type_of(ops[0], f)
    kind = it.ty.kind(tx)
    is_str = kind == "basic"
    if kind == "slice":
        n, cap = (0, 0) if x is None else (x.n, x.cap)
        if x is not None and any(x.arr is g for g in it.grown) and (
                (hi is not None and hi > cap) or (mx is not None and mx > cap)):
            raise Unsupported("a reslice past the capacity of a grown slice (Go's capacity is larger)")
        acap = "capacity"
    elif kind == "pointer":
        if x is None:
            raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
        arr = deref(x)
        n = cap = len(arr.e)
        acap = "length"
    elif is_str:
        b = x.encode("utf-8", "surrogateescape")
        n = cap = len(b)
        acap = "length"
    else:
        raise Unsupported(f"Slice of {tx}")
    i = 0 if lo is None else lo
    j = n if hi is None else hi
    if mx is not None:
        k = mx
        if _neg(k):
            raise GoPanic(f"runtime error: slice bounds out of range [::{k}]")
        if k > cap:
            raise GoPanic(f"runtime error: slice bounds out of range [::{k}] with {acap} {cap}")
        if _neg(j):
            raise GoPanic(f"runtime error: slice bounds out of range [:{j}:]")
        if j > k:
            raise GoPanic(f"runtime error: slice bounds out of range [:{j}:{k}]")
        if _neg(i):
            raise GoPanic(f"runtime error: slice bounds out of range [{i}::]")
        if i > j:
            raise GoPanic(f"runtime error: slice bounds out of range [{i}:{j}:]")
    else:
        k = cap
        if hi is not None:
            if _neg(j):
                raise GoPanic(f"runtime error: slice bounds out of range [:{j}]")
            if j > cap:
                raise GoPanic(f"runtime error: slice bounds out of range [:{j}] with {acap} {cap}")
        if _neg(i):
            raise GoPanic(f"runtime error: slice bounds out of range [{i}:]")
        if i > j:
            raise GoPanic(f"runtime error: slice bounds out of range [{i}:{j}]")
    if is_str:
        return b[i:j].decode("utf-8", "surrogateescape")
    if kind == "slice":
        if x is None:
            return None
        return Slice(x.arr, x.off + i, j - i, k - i)
    return Slice(arr, i, j - i, k - i)


def op_store(it, ins, env, args, free, f):
    it.store(it.val(ins["operands"][0], env, args, free), it.val(ins["operands"][1], env, args, free))
    return None


def op_convert(it, ins, env, args, free, f):
    o = ins["operands"][0]
    x = it.val(o, env, args, free)
    src, dst = it.type_of(o, f), ins.get("type") or ""
    di = it.ty.int_info(dst)
    if isinstance(x, int) and not isinstance(x, bool) and di is not None:
        return wrap(x, di)
    sk, dk = it.ty.kind(src), it.ty.kind(dst)
    if sk == "basic" and dk == "slice" and isinstance(x, str) and it.ty.is_byte(it.ty.entry(dst)["elem"]):
        b = x.encode("utf-8", "surrogateescape")
        return Slice(AObj(it.ty.entry(dst)["elem"], bytearray(b)), 0, len(b), len(b))
    if sk == "slice" and dk == "basic" and it.ty.entry(dst).get("string"):
        return N.slice_bytes(x).decode("utf-8", "surrogateescape")
    raise Unsupported(f"Convert {src} -> {dst}")


def op_changetype(it, ins, env, args, free, f):
    return it.val(ins["operands"][0], env, args, free)


def op_makeinterface(it, ins, env, args, free, f):
    o = ins["operands"][0]
    return Iface(it.type_of(o, f), it.val(o, env, args, free))


def op_typeassert(it, ins, env, args, free, f):
    x = it.val(ins["operands"][0], env, args, free)
    a = ins["asserted"]
    if it.ty.is_interface(a):
        raise Unsupported(f"a type assertion to the interface {a}")
    ok = isinstance(x, Iface) and x.t == a
    if ins.get("commaok"):
        return (x.v if ok else it.ty.zero(a), ok)
    if not ok:
        raise Unsupported(f"a failing type assertion to {a}")
    return x.v


def op_extract(it, ins, env, args, free, f):
    t = it.val(ins["operands"][0], env, args, free)
    return t[ins["index"]]


def op_makeslice(it, ins, env, args, free, f):
    n = it.val(ins["operands"][0], env, args, free)
    c = it.val(ins["operands"][1], env, args, free)
    el = it.ty.entry(ins["type"])["elem"]
    if n < 0:
        raise GoPanic("runtime error: makeslice: len out of range")
    if c < n:
        raise GoPanic("runtime error: makeslice: cap out of range")
    if c > MAX_ALLOC:
        raise Unsupported(f"makeslice of {c} elements")
    if it.ty.is_byte(el):
        return Slice(AObj(el, bytearray(c)), 0, n, c)
    return Slice(AObj(el, [it.ty.zero(el) for _ in range(c)]), 0, n, c)


def op_makeclosure(it, ins, env, args, free, f):
    return Fn(ins["fn"], [it.val(o, env, args, free) for o in ins["operands"][1:]])


def _append(it, ins, s, extra):
    if extra is None:
        items = []
    elif isinstance(extra, Slice):
        items = list(extra.items())
    elif isinstance(extra, str):
        items = list(extra.encode("utf-8", "surrogateescape"))
    else:
        raise Unsupported("append's second argument")
    if not items:
        return s
    old = 0 if s is None else s.n
    cap = 0 if s is None else s.cap
    need = old + len(items)
    if s is not None and need <= cap:
        s.arr.e[s.off + old:s.off + need] = (bytearray(items) if isinstance(s.arr.e, bytearray)
                                             else [copy_value(x) for x in items])
        return Slice(s.arr, s.off, need, cap)
    el = it.ty.entry(ins["type"])["elem"]
    olds = [] if s is None else list(s.items())
    if it.ty.is_byte(el):
        arr = AObj(el, bytearray(bytes(olds) + bytes(items)))
    else:
        arr = AObj(el, [copy_value(x) for x in olds] + [copy_value(x) for x in items])
    it.grown.append(arr)
    return Slice(arr, 0, need, need)


def op_call(it, ins, env, args, free, f):
    c = ins["call"]
    mode = c["mode"]
    a = [it.val(o, env, args, free) for o in c.get("args") or []]
    if mode == "static":
        ret, _ = it.call_fn(c["callee"], a, [], rtype=ins.get("type") or "")
        return ret
    if mode == "builtin":
        name = c["callee"]
        if name == "len":
            x = a[0]
            if x is None:
                return 0
            if isinstance(x, Slice):
                return x.n
            if isinstance(x, str):
                return len(x.encode("utf-8", "surrogateescape"))
            if isinstance(x, AObj):
                return len(x.e)
            if isinstance(x, Ptr) and isinstance(deref(x), AObj):
                return len(deref(x).e)
            raise Unsupported("len of this value")
        if name == "cap":
            x = a[0]
            if x is None:
                return 0
            if isinstance(x, Slice):
                if any(x.arr is g for g in it.grown):
                    raise Unsupported("cap of a grown slice")
                return x.cap
            raise Unsupported("cap of this value")
        if name == "append":
            return _append(it, ins, a[0], a[1] if len(a) > 1 else None)
        if name == "copy":
            dst, src = a
            if dst is None:
                return 0
            sitems = (list(src.encode("utf-8", "surrogateescape")) if isinstance(src, str)
                      else ([] if src is None else list(src.items())))
            n = min(dst.n, len(sitems))
            if n:
                if isinstance(dst.arr.e, bytearray):
                    dst.arr.e[dst.off:dst.off + n] = bytearray(sitems[:n])
                else:
                    dst.arr.e[dst.off:dst.off + n] = [copy_value(x) for x in sitems[:n]]
            return n
        if name in ("min", "max"):
            return (min if name == "min" else max)(a)
        if name == "ssa:wrapnilchk":
            if a[0] is None:
                raise Unsupported("a nil receiver of a method wrapper")
            return a[0]
        raise Unsupported(f"builtin {name}")
    if mode == "dynamic":
        fv = it.val(c["value"], env, args, free)
        if not isinstance(fv, Fn) or fv.fid not in it.raw:
            raise Unsupported("a dynamic call of no known function")
        ret, _ = it.call_fn(fv.fid, a, fv.binds)
        return ret
    raise Unsupported(f"a call of mode {mode}")


OPS = {"Alloc": op_alloc, "BinOp": op_binop, "UnOp": op_unop, "Field": op_field, "FieldAddr": op_fieldaddr,
       "Index": op_index, "IndexAddr": op_indexaddr, "Slice": op_slice, "Store": op_store, "Call": op_call,
       "Convert": op_convert, "ChangeType": op_changetype, "MakeInterface": op_makeinterface,
       "ChangeInterface": op_changetype, "TypeAssert": op_typeassert, "Extract": op_extract,
       "MakeSlice": op_makeslice, "MakeClosure": op_makeclosure}
