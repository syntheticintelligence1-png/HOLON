"""A small Solidity ABI codec (the contract ABI specification, strict mode), standard library only (I20).

holon.replay_fragments uses it to turn the calldata a harness ran into the A/B interface's ABI values, and to build
the calldata of the boundary and guard-targeting corpus. Types come from a compiled ABI entry ({"type", "components",
"name"}); nothing here names a target.

ABI values (the A/B interface of holon.extracted_eval.step): uintN and intN are ints, bool is a bool, address is "0x" +
40 lowercase hex digits, bytesN and bytes are "0x" + lowercase hex, string is a str, a tuple is a dict keyed by its
component names (in component order), and T[] / T[k] are lists.

decode_args is strict by default: a value whose padding is not clean (a uint64 word above 2**64 - 1, a bool other than
0 or 1, an address with high bits, a bytesN with low bytes, a bytes tail with dirty padding) or an offset outside the
data raises AbiError, as solc's calldata decoder reverts on it. With strict=False an elementary value with dirty
padding decodes to its raw word (an int), so that a model can be asked about calldata the decoder rejects (the ABI
range checks of the I19 follow-up); offsets outside the data still raise. dirty_call builds such calldata: leaf_offset
finds the word of a static leaf by encoding the arguments with two values of it.
"""
from __future__ import annotations

import re

from .keccak import keccak256

WORD = 32


class AbiError(ValueError):
    pass


def canonical_type(t: dict) -> str:
    """The type string used in signatures: tuples expanded to (..)."""
    ty = t["type"]
    if ty.startswith("tuple"):
        return "(" + ",".join(canonical_type(c) for c in t.get("components") or []) + ")" + ty[len("tuple"):]
    return ty


def signature(name: str, inputs: list[dict]) -> str:
    return f"{name}(" + ",".join(canonical_type(i) for i in inputs) + ")"


def selector(name: str, inputs: list[dict]) -> str:
    return "0x" + keccak256(signature(name, inputs).encode()).hex()[:8]


def _array(ty: str) -> tuple[str, int | None] | None:
    """('T', None) for T[], ('T', k) for T[k], None for a non-array type."""
    m = re.fullmatch(r"(.*)\[(\d*)\]", ty)
    if not m:
        return None
    return m.group(1), (int(m.group(2)) if m.group(2) else None)


def _elem(t: dict, base: str) -> dict:
    return {**t, "type": base}


def is_dynamic(t: dict) -> bool:
    ty = t["type"]
    arr = _array(ty)
    if arr is not None:
        base, k = arr
        return k is None or is_dynamic(_elem(t, base))
    if ty in ("bytes", "string"):
        return True
    if ty == "tuple":
        return any(is_dynamic(c) for c in t.get("components") or [])
    return False


def head_size(t: dict) -> int:
    if is_dynamic(t):
        return WORD
    arr = _array(t["type"])
    if arr is not None:
        base, k = arr
        return k * head_size(_elem(t, base))
    if t["type"] == "tuple":
        return sum(head_size(c) for c in t.get("components") or [])
    return WORD


def _hexb(v) -> bytes:
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if not (isinstance(v, str) and v.startswith("0x")):
        raise AbiError(f"expected 0x-hex, got {v!r}")
    return bytes.fromhex(v[2:])


def _int_bits(ty: str, prefix: str) -> int:
    n = ty[len(prefix):]
    return int(n) if n else 256


# ---------------------------------------------------------------- encode
def _enc_static_word(ty: str, v) -> bytes:
    if ty.startswith("uint"):
        bits = _int_bits(ty, "uint")
        v = int(v)
        if not 0 <= v < 1 << bits:
            raise AbiError(f"{v} out of range for {ty}")
        return v.to_bytes(WORD, "big")
    if ty.startswith("int"):
        bits = _int_bits(ty, "int")
        v = int(v)
        if not -(1 << (bits - 1)) <= v < 1 << (bits - 1):
            raise AbiError(f"{v} out of range for {ty}")
        return (v % (1 << 256)).to_bytes(WORD, "big")
    if ty == "bool":
        return (1 if v else 0).to_bytes(WORD, "big")
    if ty == "address":
        b = _hexb(v) if isinstance(v, str) else int(v).to_bytes(20, "big")
        if len(b) != 20:
            raise AbiError(f"address of {len(b)} bytes")
        return bytes(12) + b
    m = re.fullmatch(r"bytes(\d+)", ty)
    if m:
        b = _hexb(v)
        if len(b) != int(m.group(1)):
            raise AbiError(f"{ty} value of {len(b)} bytes")
        return b + bytes(WORD - len(b))
    raise AbiError(f"unsupported static type {ty}")


def encode(t: dict, v) -> bytes:
    ty = t["type"]
    arr = _array(ty)
    if arr is not None:
        base, k = arr
        items = list(v)
        if k is not None and len(items) != k:
            raise AbiError(f"{ty}: {len(items)} items")
        body = _encode_seq([_elem(t, base)] * len(items), items)
        return (len(items).to_bytes(WORD, "big") + body) if k is None else body
    if ty == "tuple":
        comps = t.get("components") or []
        vals = [v[c["name"]] for c in comps] if isinstance(v, dict) else list(v)
        return _encode_seq(comps, vals)
    if ty in ("bytes", "string"):
        b = v.encode() if ty == "string" else _hexb(v)
        pad = (-len(b)) % WORD
        return len(b).to_bytes(WORD, "big") + b + bytes(pad)
    return _enc_static_word(ty, v)


def _encode_seq(types: list[dict], vals: list) -> bytes:
    if len(types) != len(vals):
        raise AbiError(f"{len(vals)} values for {len(types)} types")
    heads, tails = [], []
    hs = sum(head_size(t) for t in types)
    off = hs
    for t, v in zip(types, vals):
        enc = encode(t, v)
        if is_dynamic(t):
            heads.append(off.to_bytes(WORD, "big"))
            tails.append(enc)
            off += len(enc)
        else:
            heads.append(enc)
    return b"".join(heads) + b"".join(tails)


def encode_args(inputs: list[dict], values: dict | list) -> bytes:
    vals = [values[i["name"]] for i in inputs] if isinstance(values, dict) else list(values)
    return _encode_seq(inputs, vals)


def encode_call(fn: dict, values: dict | list) -> str:
    return selector(fn["name"], fn["inputs"]) + encode_args(fn["inputs"], values).hex()


# ---------------------------------------------------------------- decode
def _word(data: bytes, off: int) -> int:
    if off < 0 or off + WORD > len(data):
        raise AbiError(f"read past the end at {off}")
    return int.from_bytes(data[off:off + WORD], "big")


def _dec_static_word(ty: str, w: int, strict: bool = True):
    try:
        return _dec_clean_word(ty, w)
    except AbiError:
        if strict or not _elementary(ty):
            raise
        return w


def _elementary(ty: str) -> bool:
    return bool(re.fullmatch(r"u?int\d*|bool|address|bytes\d+", ty))


def _dec_clean_word(ty: str, w: int):
    if ty.startswith("uint"):
        bits = _int_bits(ty, "uint")
        if w >> bits:
            raise AbiError(f"dirty {ty}")
        return w
    if ty.startswith("int"):
        bits = _int_bits(ty, "int")
        v = w - (1 << 256) if w >> 255 else w
        if not -(1 << (bits - 1)) <= v < 1 << (bits - 1):
            raise AbiError(f"dirty {ty}")
        return v
    if ty == "bool":
        if w > 1:
            raise AbiError("dirty bool")
        return bool(w)
    if ty == "address":
        if w >> 160:
            raise AbiError("dirty address")
        return "0x" + w.to_bytes(20, "big").hex()
    m = re.fullmatch(r"bytes(\d+)", ty)
    if m:
        n = int(m.group(1))
        b = w.to_bytes(WORD, "big")
        if any(b[n:]):
            raise AbiError(f"dirty {ty}")
        return "0x" + b[:n].hex()
    raise AbiError(f"unsupported static type {ty}")


def decode(t: dict, data: bytes, off: int, strict: bool = True):
    """The value of type t whose encoding starts at off (for a dynamic t: its tail)."""
    ty = t["type"]
    arr = _array(ty)
    if arr is not None:
        base, k = arr
        if k is None:
            n = _word(data, off)
            if n > len(data):
                raise AbiError("array length past the end")
            return _decode_seq([_elem(t, base)] * n, data, off + WORD, strict)
        return _decode_seq([_elem(t, base)] * k, data, off, strict)
    if ty == "tuple":
        comps = t.get("components") or []
        vals = _decode_seq(comps, data, off, strict)
        return {c["name"]: v for c, v in zip(comps, vals)}
    if ty in ("bytes", "string"):
        n = _word(data, off)
        if off + WORD + n > len(data):
            raise AbiError(f"{ty} past the end")
        b = data[off + WORD:off + WORD + n]
        pad = data[off + WORD + n:off + WORD + n + ((-n) % WORD)]
        if any(pad):
            raise AbiError(f"dirty {ty} padding")
        if ty == "string":
            return b.decode("utf-8", errors="surrogateescape")
        return "0x" + b.hex()
    return _dec_static_word(ty, _word(data, off), strict)


def _decode_seq(types: list[dict], data: bytes, base: int, strict: bool = True) -> list:
    out, pos = [], base
    for t in types:
        if is_dynamic(t):
            rel = _word(data, pos)
            if rel > len(data):
                raise AbiError("offset past the end")
            out.append(decode(t, data, base + rel, strict))
        else:
            out.append(decode(t, data, pos, strict))
        pos += head_size(t)
    return out


def decode_args(inputs: list[dict], data: bytes, strict: bool = True) -> dict:
    vals = _decode_seq(inputs, data, 0, strict)
    return {(i.get("name") or f"arg{k}"): v for k, (i, v) in enumerate(zip(inputs, vals))}


def decode_call(fns: dict[str, dict], calldata: str) -> tuple[dict, dict] | None:
    """(the function entry, its arguments) of calldata, or None when no function of fns has its selector.
    fns maps a selector ("0x" + 8 hex) to an ABI function entry. AbiError when the arguments do not decode."""
    b = _hexb(calldata)
    if len(b) < 4:
        return None
    fn = fns.get("0x" + b[:4].hex())
    if fn is None:
        return None
    return fn, decode_args(fn["inputs"], b[4:])


def functions(abi: list[dict]) -> dict[str, dict]:
    """selector -> ABI function entry, for every function of a compiled ABI."""
    return {selector(f["name"], f["inputs"]): f for f in abi if f.get("type") == "function"}


def leaves(t: dict, path: tuple = ()) -> list[tuple[tuple, dict]]:
    """Every elementary component of t: (path of names / indices, type entry). Dynamic arrays count as one leaf."""
    ty = t["type"]
    if ty == "tuple":
        out = []
        for c in t.get("components") or []:
            out += leaves(c, path + (c["name"],))
        return out
    arr = _array(ty)
    if arr is not None and arr[1] is not None:
        out = []
        for k in range(arr[1]):
            out += leaves(_elem(t, arr[0]), path + (k,))
        return out
    return [(path, t)]


def get_path(v, path: tuple):
    for p in path:
        v = v[p]
    return v


def set_path(v, path: tuple, x):
    """A copy of v with the component at path replaced by x."""
    if not path:
        return x
    p, rest = path[0], path[1:]
    if isinstance(v, dict):
        return {**v, p: set_path(v[p], rest, x)}
    out = list(v)
    out[p] = set_path(out[p], rest, x)
    return out


# ---------------------------------------------------------------- dirty calldata
def _two_values(ty: str):
    if ty.startswith(("uint", "int")):
        return 0, 1
    if ty == "bool":
        return False, True
    if ty == "address":
        return "0x" + "00" * 20, "0x" + "00" * 19 + "01"
    m = re.fullmatch(r"bytes(\d+)", ty)
    if m:
        n = int(m.group(1))
        return "0x" + "00" * n, "0x01" + "00" * (n - 1)
    return None


def leaf_type(inputs: list[dict], path: tuple) -> dict | None:
    """The ABI type entry of the component at path (a parameter name, then component names and indices)."""
    t = {"type": "tuple", "components": inputs}
    for p in path:
        if t["type"] == "tuple":
            t = next((c for c in t.get("components") or [] if c.get("name") == p), None)
        else:
            arr = _array(t["type"])
            t = _elem(t, arr[0]) if arr is not None and isinstance(p, int) else None
        if t is None:
            return None
    return t


def leaf_offset(inputs: list[dict], values: dict, path: tuple) -> int | None:
    """The byte offset, in encode_args(inputs, values), of the word that holds the static elementary leaf at path,
    or None when the leaf is not such a value."""
    t = leaf_type(inputs, path)
    two = _two_values(t["type"]) if t else None
    if two is None:
        return None
    a = encode_args(inputs, {**values, path[0]: set_path(values[path[0]], path[1:], two[0])})
    b = encode_args(inputs, {**values, path[0]: set_path(values[path[0]], path[1:], two[1])})
    if len(a) != len(b):
        return None
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    if not diff or diff[-1] // WORD != diff[0] // WORD:
        return None
    return diff[0] // WORD * WORD


def dirty_words(ty: str) -> list[int]:
    """Words that a strict decoder rejects for an elementary type (none for 256-bit types)."""
    if ty.startswith("uint"):
        bits = _int_bits(ty, "uint")
        return [1 << bits, (1 << 256) - 1] if bits < 256 else []
    if ty.startswith("int"):
        bits = _int_bits(ty, "int")
        return [1 << (bits - 1), 1 << bits] if bits < 256 else []
    if ty == "bool":
        return [2]
    if ty == "address":
        return [1 << 160]
    m = re.fullmatch(r"bytes(\d+)", ty)
    if m and int(m.group(1)) < 32:
        return [1]
    return []


def dirty_call(fn: dict, values: dict, path: tuple, w: int) -> str | None:
    """The calldata of fn(values) with the word of the leaf at path replaced by w, or None."""
    off = leaf_offset(fn["inputs"], values, path)
    if off is None:
        return None
    body = bytearray(encode_args(fn["inputs"], values))
    body[off:off + WORD] = w.to_bytes(WORD, "big")
    return selector(fn["name"], fn["inputs"]) + bytes(body).hex()
