"""Rule G2: the Go standard-library functions and globals the consumer model evaluates natively, with their Go semantics
(the Go 1.24 standard library). A function or global not in these tables is not native; a verb, flag or argument kind a
function here does not implement is Unsupported, never guessed.

FUNCS maps a go/ssa function id to fn(it, args) -> result (one value, or a tuple for several results); GLOBALS maps a
global's id to a constructor of its value; BUILTINS is the set of builtins the interpreter implements.
"""
from __future__ import annotations

from .values import GoPanic, Iface, Native, Ptr, Slice, Unsupported, deref

ERRSTR = "*errors.errorString"
BUILTINS = frozenset({"len", "cap", "append", "copy", "min", "max", "ssa:wrapnilchk"})


def error_value(text: str, t: str = ERRSTR) -> Iface:
    return Iface(t, Native("err", text))


def error_text(e) -> str:
    if isinstance(e, Iface) and isinstance(e.v, Native) and e.v.kind == "err":
        return e.v.v
    raise Unsupported(f"the text of an error of dynamic type {getattr(e, 't', type(e).__name__)}")


def slice_bytes(s) -> bytes:
    if s is None:
        return b""
    if not isinstance(s, Slice):
        raise Unsupported("a byte slice was expected")
    return bytes(s.items())


def new_bytes(b: bytes, nil_if_empty: bool = False):
    from .values import AObj
    if nil_if_empty and not b:
        return None
    return Slice(AObj("byte", bytearray(b)), 0, len(b), len(b))


# ---------------------------------------------------------------------------------------------- fmt
def _int_type(it, t: str) -> bool:
    try:
        return it.ty.int_info(t) is not None
    except Unsupported:
        return False


def _fmt_one(it, verb: str, a) -> str:
    if a is None:
        return "<nil>" if verb in "vs" else f"%!{verb}(<nil>)"
    if not isinstance(a, Iface):
        raise Unsupported("a formatted argument that is not an interface value")
    t, v = a.t, a.v
    if isinstance(v, Native) and v.kind == "err":
        if verb in "vs":
            return v.v
        raise Unsupported(f"verb %{verb} on an error")
    if _int_type(it, t):
        if verb in "vd":
            return str(v)
        if verb == "x":
            return format(v, "x") if v >= 0 else "-" + format(-v, "x")
        raise Unsupported(f"verb %{verb} on {t}")
    if t == "*math/big.Int":
        if v is None:
            return "<nil>"
        if verb in "vd":
            return str(deref(v).v if isinstance(deref(v), Native) else v.o.v)
        raise Unsupported(f"verb %{verb} on {t}")
    kind = it.ty.kind(t)
    e = it.ty.entry(t)
    if kind == "basic" and e.get("string") and verb in "vs":
        return v
    if kind == "basic" and e.get("boolean") and verb == "v":
        return "true" if v else "false"
    raise Unsupported(f"verb %{verb} on {t}")


def sprintf(it, fmt: str, args: list) -> str:
    out, i, ai, n = [], 0, 0, len(fmt)
    while i < n:
        c = fmt[i]
        if c != "%":
            out.append(c)
            i += 1
            continue
        i += 1
        if i >= n:
            out.append("%!(NOVERB)")
            break
        if fmt[i] == "%":
            out.append("%")
            i += 1
            continue
        verb = fmt[i]
        if verb not in "vdxs":
            raise Unsupported(f"fmt verb or flag {verb!r}")
        i += 1
        if ai >= len(args):
            out.append(f"%!{verb}(MISSING)")
            continue
        out.append(_fmt_one(it, verb, args[ai]))
        ai += 1
    if ai < len(args):
        raise Unsupported("extra fmt arguments")
    return "".join(out)


def fmt_Errorf(it, args):
    fmt, a = args
    if "%w" in fmt:
        raise Unsupported("fmt.Errorf with %w")
    vals = [] if a is None else list(a.items())
    return error_value(sprintf(it, fmt, vals))


def errors_New(it, args):
    return error_value(args[0])


# ---------------------------------------------------------------------------------------------- bytes
def bytes_NewReader(it, args):
    return Ptr(Native("reader", [slice_bytes(args[0]), 0]))


def bytes_Reader_Len(it, args):
    r = _reader(args[0])
    return len(r.v[0]) - r.v[1]


def _reader(p):
    if isinstance(p, Iface):
        p = p.v
    if p is None:
        raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
    o = p.o if isinstance(p, Ptr) else None
    if not (isinstance(o, Native) and o.kind == "reader"):
        raise Unsupported("a byte reader was expected")
    return o


# ---------------------------------------------------------------------------------------------- encoding/binary
EOF = None
UNEXPECTED_EOF = None


def _eof():
    global EOF
    if EOF is None:
        EOF = error_value("EOF")
    return EOF


def _unexpected_eof():
    global UNEXPECTED_EOF
    if UNEXPECTED_EOF is None:
        UNEXPECTED_EOF = error_value("unexpected EOF")
    return UNEXPECTED_EOF


def _order(o) -> str:
    v = o.v if isinstance(o, Iface) else o
    if isinstance(v, Native) and v.kind in ("bigEndian", "littleEndian"):
        return "big" if v.kind == "bigEndian" else "little"
    raise Unsupported("a byte order that is not encoding/binary's")


def binary_Read(it, args):
    """binary.Read(r, order, data): the fixed-size fast path of Go 1.24 (io.ReadFull, then decode into data)."""
    r, order, data = args
    rd = _reader(r)
    bo = _order(order)
    if not isinstance(data, Iface):
        raise Unsupported("binary.Read's data is not an interface value")
    t, p = data.t, data.v
    if not t.startswith("*"):
        raise Unsupported(f"binary.Read into {t}")
    el = t[1:]
    if p is None:
        raise Unsupported("binary.Read into a nil pointer")
    info = it.ty.int_info(el) if it.ty.kind(el) == "basic" else None
    if info is not None:
        n = info[0] // 8
    elif it.ty.kind(el) == "slice" and it.ty.is_byte(it.ty.entry(el)["elem"]):
        cur = deref(p)
        n = 0 if cur is None else cur.n
    else:
        raise Unsupported(f"binary.Read into {t}")
    if n == 0:
        raise Unsupported("binary.Read of zero bytes")
    buf, pos = rd.v
    rest = len(buf) - pos
    if rest == 0:
        return _eof()
    if rest < n:
        rd.v[1] = len(buf)
        return _unexpected_eof()
    chunk = buf[pos:pos + n]
    rd.v[1] = pos + n
    if info is not None:
        it.store(p, int.from_bytes(chunk, bo, signed=not info[1]))
    else:
        cur = deref(p)
        cur.arr.e[cur.off:cur.off + n] = chunk
    return None


def _need(b: bytes, k: int):
    if len(b) <= k:
        raise GoPanic(f"runtime error: index out of range [{k}] with length {len(b)}")


def _uint(width: int, order: str):
    def f(it, args):
        b = slice_bytes(args[1])
        _need(b, width - 1)
        return int.from_bytes(b[:width], order)
    return f


# ---------------------------------------------------------------------------------------------- math/big
def _big(p):
    if p is None:
        raise GoPanic("runtime error: invalid memory address or nil pointer dereference")
    o = p.o if isinstance(p, Ptr) else None
    if not (isinstance(o, Native) and o.kind == "big"):
        raise Unsupported("a *big.Int was expected")
    return o


def big_NewInt(it, args):
    return Ptr(Native("big", args[0]))


def big_SetBytes(it, args):
    z, buf = args
    _big(z).v = int.from_bytes(slice_bytes(buf), "big")
    return z


def big_Cmp(it, args):
    x, y = _big(args[0]).v, _big(args[1]).v
    return (x > y) - (x < y)


def big_Sign(it, args):
    x = _big(args[0]).v
    return (x > 0) - (x < 0)


FUNCS = {
    "fmt.Errorf": fmt_Errorf,
    "errors.New": errors_New,
    "bytes.NewReader": bytes_NewReader,
    "(*bytes.Reader).Len": bytes_Reader_Len,
    "encoding/binary.Read": binary_Read,
    "(encoding/binary.bigEndian).Uint16": _uint(2, "big"),
    "(encoding/binary.bigEndian).Uint32": _uint(4, "big"),
    "(encoding/binary.bigEndian).Uint64": _uint(8, "big"),
    "(encoding/binary.littleEndian).Uint16": _uint(2, "little"),
    "(encoding/binary.littleEndian).Uint32": _uint(4, "little"),
    "(encoding/binary.littleEndian).Uint64": _uint(8, "little"),
    "math/big.NewInt": big_NewInt,
    "(*math/big.Int).SetBytes": big_SetBytes,
    "(*math/big.Int).Cmp": big_Cmp,
    "(*math/big.Int).Sign": big_Sign,
}

GLOBALS = {
    "encoding/binary.BigEndian": lambda: Native("bigEndian", None),
    "encoding/binary.LittleEndian": lambda: Native("littleEndian", None),
    "io.EOF": _eof,
    "io.ErrUnexpectedEOF": _unexpected_eof,
}
