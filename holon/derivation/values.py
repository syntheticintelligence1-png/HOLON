"""Go values and memory for the consumer model (rule G1), over the consumer section's type table.

Values held by SSA registers:
  int, bool, str          integers (normalized to their type's width), booleans, strings
  None                    a nil pointer, slice, map, function or interface
  Ptr(o, i)               a pointer: to a Box's value (i None), to a whole struct or array object (i None), or to the
                          i-th field or element of one whose type is not an aggregate
  Slice(arr, off, n, cap) a slice over an array object
  SObj / AObj             a struct or array value; in memory the same classes are the mutable objects a pointer reaches
  Iface(t, v)             a non-nil interface value: dynamic type key t, value v
  Fn(fid, binds)          a function value
  tuple                   a call's results
Memory objects are mutable; values are never mutated after they are made (every load and store copies aggregates), so a
value may be shared freely.
"""
from __future__ import annotations


class Unsupported(Exception):
    """A construct the model does not evaluate: the step is unsupported, never guessed."""


class GoPanic(Exception):
    """A Go panic: text is what fmt.Sprint(recover()) prints."""

    def __init__(self, text: str):
        super().__init__(text)
        self.text = text


class Box:
    __slots__ = ("v",)

    def __init__(self, v):
        self.v = v


class SObj:
    __slots__ = ("t", "f")

    def __init__(self, t: str, f: list):
        self.t, self.f = t, f


class AObj:
    __slots__ = ("t", "e")

    def __init__(self, t: str, e):
        self.t, self.e = t, e        # t: the element type key; e: list, or bytearray for byte elements


class Ptr:
    __slots__ = ("o", "i")

    def __init__(self, o, i=None):
        self.o, self.i = o, i

    def __eq__(self, other):
        return isinstance(other, Ptr) and self.o is other.o and self.i == other.i

    def __hash__(self):
        return hash((id(self.o), self.i))


class Slice:
    __slots__ = ("arr", "off", "n", "cap")

    def __init__(self, arr: AObj, off: int, n: int, cap: int):
        self.arr, self.off, self.n, self.cap = arr, off, n, cap

    def items(self):
        return self.arr.e[self.off:self.off + self.n]


class Iface:
    __slots__ = ("t", "v")

    def __init__(self, t: str, v):
        self.t, self.v = t, v

    def __eq__(self, other):
        return isinstance(other, Iface) and self.t == other.t and eq(self.v, other.v)

    def __hash__(self):
        return hash(self.t)


class Fn:
    __slots__ = ("fid", "binds")

    def __init__(self, fid: str, binds: list):
        self.fid, self.binds = fid, binds


class Native:
    """An object of a standard-library or environment type the natives implement (a big integer, a byte reader, an
    error value, a byte order, an element the environment decoded)."""
    __slots__ = ("kind", "v")

    def __init__(self, kind: str, v):
        self.kind, self.v = kind, v


def eq(a, b) -> bool:
    """Go's == on comparable values."""
    if a is None or b is None:
        return a is b
    if isinstance(a, Ptr) or isinstance(b, Ptr):
        return isinstance(a, Ptr) and isinstance(b, Ptr) and a == b
    if isinstance(a, Iface) or isinstance(b, Iface):
        return isinstance(a, Iface) and isinstance(b, Iface) and a.t == b.t and eq(a.v, b.v)
    if isinstance(a, Native) or isinstance(b, Native):
        return a is b
    if isinstance(a, SObj) and isinstance(b, SObj):
        return len(a.f) == len(b.f) and all(eq(x, y) for x, y in zip(a.f, b.f))
    if isinstance(a, AObj) and isinstance(b, AObj):
        return len(a.e) == len(b.e) and all(eq(x, y) for x, y in zip(a.e, b.e))
    if isinstance(a, (Slice, Fn)) or isinstance(b, (Slice, Fn)):
        raise Unsupported("== on a slice or function value other than nil")
    return a == b


class Types:
    """The consumer section's type table (ssadump's: kind, name, underlying, elem, key, len, fields, elems, size,
    unsigned, ...)."""

    def __init__(self, table: dict):
        self.t = table

    def get(self, k: str) -> dict:
        e = self.t.get(k)
        if e is None:
            raise Unsupported(f"type {k} is not in the type table")
        return e

    def under(self, k: str) -> str:
        seen = 0
        while True:
            e = self.get(k)
            if e.get("kind") == "alias" and e.get("underlying") == k:
                return k          # the universe alias any: ssadump keys interface{} by its printed name, "any"
            if e.get("kind") in ("named", "alias") and e.get("underlying"):
                k = e["underlying"]
                seen += 1
                if seen > 64:
                    raise Unsupported(f"type {k}: underlying chain too long")
                continue
            return k

    def kind(self, k: str) -> str:
        return self.entry(k).get("kind")

    def entry(self, k: str) -> dict:
        u = self.under(k)
        e = self.get(u)
        if e.get("kind") == "alias" and e.get("underlying") == u:
            return {"kind": "interface", "name": u}
        return e

    def is_byte(self, k: str) -> bool:
        e = self.entry(k)
        return e.get("kind") == "basic" and e.get("integer") and e.get("unsigned") and e.get("size") == 1

    def is_aggregate(self, k: str) -> bool:
        return k == "math/big.Int" or self.kind(k) in ("struct", "array")

    def int_info(self, k: str):
        """(bits, unsigned) of an integer type; None for an untyped or non-integer one."""
        e = self.entry(k)
        if e.get("kind") != "basic" or not e.get("integer") or e.get("untyped"):
            return None
        return 8 * int(e["size"]), bool(e.get("unsigned"))

    def is_interface(self, k: str) -> bool:
        return self.kind(k) == "interface"

    def pointee(self, k: str) -> str:
        e = self.entry(k)
        if e.get("kind") != "pointer":
            raise Unsupported(f"type {k} is not a pointer")
        return e["elem"]

    def zero(self, k: str):
        if k == "math/big.Int":
            return Native("big", 0)
        e = self.entry(k)
        kind = e.get("kind")
        if kind == "basic":
            if e.get("boolean"):
                return False
            if e.get("string"):
                return ""
            if e.get("integer"):
                return 0
            raise Unsupported(f"zero of basic type {k}")
        if kind in ("pointer", "slice", "map", "chan", "signature", "interface"):
            return None
        if kind == "struct":
            return SObj(k, [self.zero(f["type"]) for f in e.get("fields") or []])
        if kind == "array":
            n = int(e["len"])
            if self.is_byte(e["elem"]):
                return AObj(e["elem"], bytearray(n))
            return AObj(e["elem"], [self.zero(e["elem"]) for _ in range(n)])
        raise Unsupported(f"zero of type {k} ({kind})")

    def field_names(self, k: str) -> list:
        return [f["name"] for f in self.entry(k).get("fields") or []]

    def field_types(self, k: str) -> list:
        return [f["type"] for f in self.entry(k).get("fields") or []]


def wrap(v: int, info) -> int:
    if info is None:
        return v
    bits, unsigned = info
    v &= (1 << bits) - 1
    if not unsigned and v >> (bits - 1):
        v -= 1 << bits
    return v


def copy_value(v):
    """A value's copy (aggregates are copied deeply; everything else is immutable or a reference)."""
    if isinstance(v, SObj):
        return SObj(v.t, [copy_value(x) for x in v.f])
    if isinstance(v, AObj):
        if isinstance(v.e, bytearray):
            return AObj(v.t, bytearray(v.e))
        return AObj(v.t, [copy_value(x) for x in v.e])
    if isinstance(v, Native) and v.kind == "big":
        return Native("big", v.v)
    return v


def assign(dst, v) -> None:
    """Store aggregate value v into memory object dst in place (pointers into dst keep seeing it)."""
    if isinstance(dst, SObj) and isinstance(v, SObj):
        for k, x in enumerate(v.f):
            cur = dst.f[k]
            if isinstance(cur, (SObj, AObj)) or (isinstance(cur, Native) and cur.kind == "big"):
                assign(cur, x)
            else:
                dst.f[k] = x
        return
    if isinstance(dst, AObj) and isinstance(v, AObj):
        if isinstance(dst.e, bytearray):
            dst.e[:] = v.e
            return
        for k, x in enumerate(v.e):
            cur = dst.e[k]
            if isinstance(cur, (SObj, AObj)) or (isinstance(cur, Native) and cur.kind == "big"):
                assign(cur, x)
            else:
                dst.e[k] = x
        return
    if isinstance(dst, Native) and dst.kind == "big" and isinstance(v, Native) and v.kind == "big":
        dst.v = v.v
        return
    raise Unsupported(f"store of {type(v).__name__} into {type(dst).__name__}")


# ---------------------------------------------------------------------------------------------- building and dumping
def build(ty: Types, k: str, j):
    """A value of type k from its JSON form (rule J2 and the corpus): structs by Go field name (absent fields zero),
    byte arrays and slices as "0x" hex (null a nil slice), other arrays and slices as lists, integers as numbers."""
    e = ty.entry(k)
    kind = e.get("kind")
    if kind == "struct":
        if j is None:
            return ty.zero(k)
        if not isinstance(j, dict):
            raise Unsupported(f"a {k} needs an object")
        names = ty.field_names(k)
        bad = [n for n in j if n not in names]
        if bad:
            raise Unsupported(f"{k} has no fields {bad}")
        return SObj(k, [build(ty, ft, j.get(n)) if n in j else ty.zero(ft)
                        for n, ft in zip(names, ty.field_types(k))])
    if kind == "basic":
        if e.get("integer"):
            if not isinstance(j, int) or isinstance(j, bool):
                raise Unsupported(f"a {k} needs an integer")
            info = ty.int_info(k)
            if wrap(j, info) != j:
                raise Unsupported(f"{j} does not fit {k}")
            return j
        if e.get("boolean"):
            return bool(j)
        if e.get("string"):
            return str(j)
        raise Unsupported(f"build of {k}")
    if kind == "array":
        n = int(e["len"])
        if ty.is_byte(e["elem"]):
            b = _hex(j)
            if len(b) != n:
                raise Unsupported(f"a {k} needs {n} bytes, got {len(b)}")
            return AObj(e["elem"], bytearray(b))
        if not isinstance(j, list) or len(j) != n:
            raise Unsupported(f"a {k} needs a list of {n}")
        return AObj(e["elem"], [build(ty, e["elem"], x) for x in j])
    if kind == "slice":
        if j is None:
            return None
        if ty.is_byte(e["elem"]):
            b = _hex(j)
            return Slice(AObj(e["elem"], bytearray(b)), 0, len(b), len(b))
        if not isinstance(j, list):
            raise Unsupported(f"a {k} needs a list")
        return Slice(AObj(e["elem"], [build(ty, e["elem"], x) for x in j]), 0, len(j), len(j))
    if kind == "pointer" and j is None:
        return None
    raise Unsupported(f"build of {k} ({kind}) from {str(j)[:40]}")


def _hex(j) -> bytes:
    if not isinstance(j, str) or not j.startswith("0x"):
        raise Unsupported(f"expected 0x hex, got {str(j)[:40]}")
    return bytes.fromhex(j[2:])


def dump(ty: Types, k: str, v, err_text):
    """Rule G5: the JSON form of value v of type k."""
    if k == "math/big.Int":
        return {"big": str(v.v)}
    e = ty.entry(k)
    kind = e.get("kind")
    if kind == "basic":
        return v
    if kind == "struct":
        return {n: dump(ty, ft, x, err_text) for n, ft, x in zip(ty.field_names(k), ty.field_types(k), v.f)}
    if kind == "array":
        if ty.is_byte(e["elem"]):
            return "0x" + bytes(v.e).hex()
        return [dump(ty, e["elem"], x, err_text) for x in v.e]
    if kind == "slice":
        if v is None:
            return None
        if ty.is_byte(e["elem"]):
            return "0x" + bytes(v.items()).hex()
        return [dump(ty, e["elem"], x, err_text) for x in v.items()]
    if kind == "pointer":
        if v is None:
            return None
        el = e["elem"]
        if el == "math/big.Int":
            target = v.o if v.i is None else _at(v)
            return {"big": str(target.v)}
        return dump(ty, el, deref(v), err_text)
    if kind == "interface":
        if v is None:
            return None
        return {"error": err_text(v)}
    raise Unsupported(f"dump of {k} ({kind})")


def _at(p: Ptr):
    o = p.o
    if isinstance(o, SObj):
        return o.f[p.i]
    if isinstance(o, AObj):
        return o.e[p.i]
    raise Unsupported("a pointer into a non-aggregate")


def deref(p: Ptr):
    """The value a pointer reaches (aggregates as the memory object itself: callers copy)."""
    if p.i is None:
        return p.o.v if isinstance(p.o, Box) else p.o
    return _at(p)
