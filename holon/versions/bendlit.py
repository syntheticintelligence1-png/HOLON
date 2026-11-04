"""Bend literals of the versioned model's values (holon.versions.model's layer), for the witnesses' and inhabitants'
files: words as <P>.w_of_limbs([8 limbs]) or <P>.w0(), byte strings as lists of byte literals (Nil{} when empty), states,
hash tables, environments and the steps of a trace, each by the layer's own constructors and argument builders. <P> is
the alias the file imports the layer under. An argument's leaves are its calldata decoded by the parameter types of the
function its selector names (the compiler's ABI of the version's document), in parameter order and a struct's fields in
declaration order, value types as their 32-byte word, bytes and strings as their bytes, arrays as their elements.
"""
from __future__ import annotations

import re

from . import PLACEHOLDER, VersionsError
from .machine import Machine, cd_bytes, num

MASK = (1 << 256) - 1


def limbs(n: int) -> list:
    n &= MASK
    return [(n >> (32 * i)) & 0xFFFFFFFF for i in range(8)]


class Lit:
    def __init__(self, p: str):
        self.p = p

    def word(self, n: int) -> str:
        n = int(n) & MASK
        return f"{self.p}.w0()" if n == 0 else f"{self.p}.w_of_limbs([{', '.join(str(x) for x in limbs(n))}])"

    @staticmethod
    def blist(b: bytes) -> str:
        b = bytes(b)
        return "Nil{}" if not b else "[" + ", ".join(str(x) for x in b) + "]"

    def wlist(self, ws: list) -> str:
        return "Nil{}" if not ws else "[" + ", ".join(self.word(w) for w in ws) + "]"

    def storage(self, sl: list) -> str:
        p = self.p
        items = ", ".join(f"{p}.KW{{{self.word(k)}, {self.word(v)}}}" for k, v in sl)
        return f"{p}.HSt{{{'[' + items + ']' if sl else 'Nil{}'}}}"

    def state(self, s: dict) -> str:
        return f"{self.p}.VSt{{{self.p}.VV_{s['version']}{{}}, {self.storage(s['sl'])}}}"

    def table(self, kh: dict) -> str:
        p = self.p
        items = [f"{p}.HKB{{{self.blist(bytes.fromhex(k[2:]))}, {self.word(v)}}}" for k, v in sorted(kh.items())]
        return "[" + ", ".join(items) + "]" if items else "Nil{}"

    # ---------------------------------------------------------- environments
    def venv(self, fields: list, env: dict) -> str:
        """The layer's VEnv of an environment (holon.versions.machine.Machine.env's dict), field by field."""
        p, vals = self.p, []
        for f, ty, key in fields:
            if key == "blobs":
                v = self.wlist([num(x) for x in env.get("blobhash") or []])
            elif key == "calls":
                cs = [f"{p}.HCall{{{self.word(num(c.get('to') or 0))}, {self.blist(cd_bytes(c.get('data') or '0x'))}, "
                      f"{'True' if c.get('ok') else 'False'}{{}}, {self.blist(cd_bytes(c.get('ret') or '0x'))}}}"
                      for c in env.get("calls") or []]
                v = "[" + ", ".join(cs) + "]" if cs else "Nil{}"
            elif key == "code":
                cs = [f"{p}.KB{{{self.word(k)}, {self.blist(b)}}}" for k, b in sorted((env.get("code") or {}).items())]
                v = "[" + ", ".join(cs) + "]" if cs else "Nil{}"
            elif key == "balance":
                cs = [f"{p}.KW{{{self.word(k)}, {self.word(b)}}}" for k, b in sorted((env.get("balance") or {}).items())]
                v = "[" + ", ".join(cs) + "]" if cs else "Nil{}"
            elif key.startswith("immutable."):
                v = self.word(num((env.get("immutable") or {}).get(key[len("immutable."):], 0)))
            elif ty == "W":
                v = self.word(num(env.get(key) or 0))
            else:
                raise VersionsError(f"no literal of the environment field {f} ({ty})")
            vals.append(v)
        return f"{p}.VEnv{{{', '.join(vals)}}}"

    # ---------------------------------------------------------- arguments
    def leaves(self, params: list, cd: str) -> list:
        """The argument nodes of a call: [("w", n) | ("b", bytes) | ("l", [nodes]) | ("t", [nodes])], in parameter
        order, decoded from the calldata (its selector aside) by the parameter types."""
        data = cd_bytes(cd)[4:]
        return _tuple(params, data, 0)

    def arg_literals(self, nodes: list) -> list:
        out = []
        for n in nodes:
            if n[0] == "t":
                out += self.arg_literals(n[1])
            elif n[0] == "w":
                out.append(self.word(n[1]))
            elif n[0] == "b":
                out.append(self.blist(n[1]))
            else:
                if any(x[0] != "w" for x in n[1]):
                    raise VersionsError("an array argument of non-word elements has no literal")
                out.append(self.wlist([x[1] for x in n[1]]))
        return out


_ARRAY = re.compile(r"^(.*)\[(\d*)\]$")


def _dynamic(p: dict) -> bool:
    m = _ARRAY.match(p["type"])
    if m:
        return m.group(2) == "" or _dynamic(dict(p, type=m.group(1)))
    if p["type"] == "tuple" or p.get("components"):
        return any(_dynamic(c) for c in p.get("components") or [])
    return p["type"] in ("bytes", "string")


def _size(p: dict) -> int:
    m = _ARRAY.match(p["type"])
    if m:
        return int(m.group(2)) * _size(dict(p, type=m.group(1)))
    if p["type"] == "tuple" or p.get("components"):
        return sum(_size(c) for c in p.get("components") or [])
    return 32


def _read(data: bytes, at: int, n: int) -> bytes:
    if at < 0 or at + n > len(data):
        raise VersionsError(f"calldata ends at {len(data)}: no {n} bytes at {at}")
    return data[at:at + n]


def _tuple(ps: list, data: bytes, base: int) -> list:
    out, head = [], base
    for p in ps:
        if _dynamic(p):
            out.append(_value(p, data, base + int.from_bytes(_read(data, head, 32), "big")))
            head += 32
        else:
            out.append(_value(p, data, head))
            head += _size(p)
    return out


def _value(p: dict, data: bytes, at: int):
    m = _ARRAY.match(p["type"])
    if m:
        el = dict(p, type=m.group(1))
        if m.group(2) == "":
            n = int.from_bytes(_read(data, at, 32), "big")
            if n > (len(data) - at - 32) // 32:
                raise VersionsError(f"an array of {n} elements at {at} does not fit the calldata")
            return ("l", _tuple([el] * n, data, at + 32))
        return ("l", _tuple([el] * int(m.group(2)), data, at))
    if p["type"] == "tuple" or p.get("components"):
        return ("t", _tuple(p.get("components") or [], data, at))
    if p["type"] in ("bytes", "string"):
        n = int.from_bytes(_read(data, at, 32), "big")
        return ("b", _read(data, at + 32, n))
    return ("w", int.from_bytes(_read(data, at, 32), "big"))


def py_args(params: list, nodes: list) -> dict:
    """The arguments as holon.sorts.evaluate3 takes them ({name: value}, a struct a dict by component name), from the
    same nodes as the literals: words as ints, bytes as bytes, arrays as lists."""
    def val(p, n):
        if n[0] == "t":
            return {c.get("name"): val(c, x) for c, x in zip(p.get("components") or [], n[1])}
        if n[0] == "l":
            m = _ARRAY.match(p["type"])
            el = dict(p, type=m.group(1)) if m else p
            return [val(el, x) for x in n[1]]
        return n[1]
    return {p.get("name"): val(p, n) for p, n in zip(params, nodes)}


def step_literal(lit: Lit, m: Machine, st: dict, env: dict | None) -> str:
    """x_i's body: the step's constructor applied to its arguments (the layer's builder over the leaves), then, for a call,
    its caller and environment; for a migration with a call, the call's arguments and environment."""
    from ..machine_bend import bname
    p = lit.p
    if st["kind"] == "migrate":
        sfx = "entry" if st["label"] == "entry" else st["label"].replace("->", "_")
        if not st.get("call"):
            return f"{p}.U_{sfx}{{{p}.UN_{sfx}{{}}}}"
        b, r = st["version"], st["call"]
        fn = m.function(b, r)
        args = ", ".join(lit.arg_literals(lit.leaves(fn["inputs"], st["calldata"])))
        return (f"{p}.U_{sfx}{{{p}.UK_{sfx}_{bname(r)}{{{p}.ar_{b}_{bname(r)}({args}), "
                f"{lit.venv(m.venv_fields(), env)}}}}}")
    v, a = st["version"], st["action"]
    fn = m.function(v, a)
    args = ", ".join(lit.arg_literals(lit.leaves(fn["inputs"], st["calldata"])))
    return (f"{p}.C_{v}_{bname(a)}{{{p}.ar_{v}_{bname(a)}({args}), {lit.word(num(st['caller']))}, "
            f"{lit.venv(m.venv_fields(), env)}}}")


def placeholder_state() -> dict:
    return {"version": PLACEHOLDER, "sl": []}
