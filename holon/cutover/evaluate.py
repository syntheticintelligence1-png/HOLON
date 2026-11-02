"""The linked machine's evaluator: holon.extracted_eval's evaluator of record, extended outside every generator closure
for the constructs a legacy registry's document holds, each in a method of its own, every construct the base evaluates
evaluated by the base unchanged:

- ["alloc", "<T>[] memory", n]: a memory array of n zero elements of a value type T;
- ["update", array, ["index", array, i], v] on a memory array: a copy with element i set to v;
- ["abi.decode", data, ["tuple", T..] | T]: the ABI decoding of bytes by value types and dynamic arrays of them (a
  decoding error is unsupported: the compiler's decoder revert is not a check of the document);
- ["abi.encodeCall", ["decl", id], args..]: the called function's selector and the ABI encoding of the arguments by its
  parameters, from the environment's declaration table (env "decls": {id: {"selector", "inputs"}});
- a loop's return path with no value (an early return from a function that returns nothing) yields no value;
- an external call named by an overload suffix (I69's rule E2: "<Contract>.<function>_<selector>") resolves to the
  overload with that selector;
- ["pop", array] on a loop-carried storage array value (a store chain over the variable): the value with its last
  element zeroed and its length one less, both as overlays the chain's later reads see (["len", array] reads the
  latest length overlay before the variable's stored length);
- a storage bytes or string by the compiler's encoding (a length below 32 inline: the data in the high bytes, 2 * length
  in the lowest; else 2 * length + 1 at the slot and the data from keccak256(slot) on), an assignment clearing the old
  data's words past the new.
"""
from __future__ import annotations

import copy
import re

from .. import extracted_eval as E

_VALUE_TYPE = re.compile(r"^(u?int\d*|address( payable)?|bool|bytes([1-9]|[12]\d|3[0-2]))$")


def decode_type(x) -> str:
    """An ABI type from a document's type term (["type", "type(T)"], or ["index", T, null] for T[])."""
    if isinstance(x, list) and len(x) == 2 and x[0] == "type" and isinstance(x[1], str):
        m = re.fullmatch(r"type\((.+)\)", x[1])
        if m and _VALUE_TYPE.match(m.group(1)):
            return m.group(1).replace(" payable", "")
    if isinstance(x, list) and len(x) == 3 and x[0] == "index" and x[2] is None:
        return decode_type(x[1]) + "[]"
    raise E.Unsupported(f"abi.decode to a type the evaluator does not decode: {E.canonical(x)[:80]}")


def call_signature(m, fn: str) -> dict | None:
    """The interface function a call term names: the model's unique overload, else the overload whose selector the
    name's suffix gives."""
    sig = m.call_signature(fn) if hasattr(m, "call_signature") else None
    if sig is not None:
        return sig
    mt = re.fullmatch(r"(.+)_([0-9a-f]{8})", fn)
    if not mt:
        return None
    hits = [h for h in ((m.info.get("members") or {}).get(mt.group(1)) or [])
            if (h.get("selector") or "").lower() == "0x" + mt.group(2)]
    return hits[0] if len(hits) == 1 else None


class Eval(E.Eval):
    def loop(self, lp) -> None:
        if any(v is None for _c, v in lp.returns):
            lp = copy.copy(lp)
            lp.returns = [(c, 0 if v is None else v) for c, v in lp.returns]
        return super().loop(lp)

    def answer(self, fn: str, receiver, args: list):
        hook = self.env.get("call_hook")
        if callable(hook) and not (hasattr(self.m, "call_signature") and self.m.call_signature(fn)):
            sig = call_signature(self.m, fn)
            if sig is not None:
                ok, data = hook(self, fn, receiver, [self.value(a) for a in args], sig, None)
                return ok, data, sig
        return super().answer(fn, receiver, args)

    def t_alloc(self, t):
        ty = str(t[1])
        base = ty[:-len("[] memory")].strip() if ty.endswith("[] memory") else None
        if base is None or not _VALUE_TYPE.match(base):
            raise E.Unsupported(f"an allocation of {ty}")
        n = self.iv(t[2])
        if n > (1 << 16):
            raise E.Unsupported(f"an allocation of {n} elements")
        return [0] * n

    def t_update(self, t):
        tgt = t[2]
        if isinstance(tgt, list) and len(tgt) == 3 and tgt[0] == "index":
            base = self.value(self.ev(t[1]))
            if isinstance(base, list):
                i = self.iv(tgt[2])
                if i >= len(base):
                    raise E.Unsupported(f"index {i} past the memory array's length {len(base)} (a panic the "
                                        "document does not place)")
                out = list(base)
                out[i] = self.value(self.ev(t[3]))
                return out
        return super().t_update(t)

    def t_abi_decode(self, t):
        data = self.ev(t[1])
        if not isinstance(data, (bytes, bytearray)):
            raise E.Unsupported("abi.decode of a value that is not bytes")
        spec = t[2]
        tup = isinstance(spec, list) and bool(spec) and spec[0] == "tuple"
        ps = [{"type": decode_type(x)} for x in (spec[1:] if tup else [spec])]
        try:
            vals = E.abi_decode(bytes(data), ps)
        except Exception as x:  # noqa: BLE001  (the compiler's decoder reverts on malformed data)
            raise E.Unsupported(f"abi.decode: {x}") from x
        out = [E.norm(v, p) for v, p in zip(vals, ps)]
        return out if tup else out[0]

    def t_abi_encodeCall(self, t):
        ref = t[1]
        decls = self.env.get("decls") or {}
        d = decls.get(str(ref[1])) if isinstance(ref, list) and len(ref) == 2 and ref[0] == "decl" else None
        if not d or not d.get("selector"):
            raise E.Unsupported(f"abi.encodeCall of a function with no declaration entry: {E.canonical(ref)[:80]}")
        ps = d.get("inputs") or []
        vals = [self.value(self.ev(x)) for x in t[2:]]
        if len(vals) != len(ps):
            raise E.Unsupported(f"abi.encodeCall with {len(vals)} arguments for {len(ps)} parameters")
        return bytes.fromhex(d["selector"][2:]) + E.abi_encode([E.norm(v, p) for v, p in zip(vals, ps)], ps)

    def t_pop(self, t):
        ref = self.ev(t[1])
        if not isinstance(ref, E.SRef):
            raise E.Unsupported("pop of a value that is not storage")
        n = self.array_length(ref)
        if n == 0:
            raise E.Unsupported("pop of an empty array (a panic the document does not place)")
        last = (tuple(ref.path) + (("index", n - 1),), 0)
        length = (tuple(ref.path) + (("len",),), n - 1)
        return E.SRef(ref.fam, ref.path, (length, last) + tuple(ref.overlays))

    def t_store(self, t):
        """A store of a whole variable's new value that is itself a store chain deeper than the variable (a loop-carried
        array after pop) is that chain, not a load of it (which the base cannot make)."""
        if not t[2]:
            v = self.ev(t[3])
            if isinstance(v, E.SRef) and any(len(wp) > len(v.path) for wp, _ in v.overlays):
                return v
            return self.value(v)
        return super().t_store(t)

    def t_len(self, t):
        x = self.ev(t[1])
        if isinstance(x, E.SRef):
            return self.array_length(x)
        if isinstance(x, (bytes, bytearray, list)):
            return len(x)
        raise E.Unsupported(f"length of a {type(x).__name__}")

    def array_length(self, ref) -> int:
        """A storage dynamic array's length: the latest length overlay of its store chain, else the stored length."""
        want = tuple(ref.path) + (("len",),)
        for wpath, val in ref.overlays:
            if tuple(wpath) == want:
                return val
        slot, _off, tid = self.locate(ref)
        tt = self.m.type_of(tid)
        if tt.get("encoding") == "dynamic_array":
            return self.state.get(slot, 0)
        raise E.Unsupported(f"length of a storage {tt.get('label')}")

    def load_at(self, slot: int, off: int, tid: str):
        if self.m.type_of(tid).get("encoding") == "bytes":
            return self.load_bytes(slot)
        return super().load_at(slot, off, tid)

    def _write_at(self, slot: int, off: int, tid: str, value) -> None:
        t = self.m.type_of(tid)
        if t.get("encoding") == "bytes":
            return self.write_bytes(slot, value)
        return super()._write_at(slot, off, tid, value)

    def load_bytes(self, slot: int) -> bytes:
        w = self.state.get(slot, 0)
        if w & 1 == 0:
            return w.to_bytes(32, "big")[:(w & 0xFF) // 2]
        n = (w - 1) // 2
        base = E.keccak(slot.to_bytes(32, "big"))
        return b"".join(self.state.get((base + i) & E.MASK, 0).to_bytes(32, "big")
                        for i in range((n + 31) // 32))[:n]

    def write_bytes(self, slot: int, value) -> None:
        if isinstance(value, int) and value == 0:
            b = b""
        elif isinstance(value, (bytes, bytearray)):
            b = bytes(value)
        else:
            raise E.Unsupported(f"a bytes write of a {type(value).__name__}")
        old = self.overlay.get(slot, self.state.get(slot, 0))
        old_words = (((old - 1) // 2) + 31) // 32 if old & 1 else 0
        base = E.keccak(slot.to_bytes(32, "big"))
        if len(b) < 32:
            self._put(slot, int.from_bytes(b.ljust(31, b"\0") + bytes([2 * len(b)]), "big"))
            words = 0
        else:
            self._put(slot, 2 * len(b) + 1)
            words = (len(b) + 31) // 32
            for i in range(words):
                self._put((base + i) & E.MASK, int.from_bytes(b[32 * i:32 * i + 32].ljust(32, b"\0"), "big"))
        for i in range(words, old_words):
            self._put((base + i) & E.MASK, 0)

    def _put(self, slot: int, w: int) -> None:
        self.overlay[slot] = w & E.MASK
        if slot not in self.touched:
            self.touched.append(slot)


def step(model, state, action: str, args: dict, env: dict) -> dict:
    """One transition (holon.extracted_eval.step) by this evaluator."""
    R = E._result
    if action not in model.actions:
        return R("unsupported", reason=f"no action {action} in the document")
    prog = model.program(action)
    e = Eval(model, state, action, args or {}, env or {})
    try:
        e.run(prog.steps)
    except E.Reverted as x:
        out = R("revert", E.hexb(x.data), guard=x.check.id)
        if x.prefix:
            out["revert_prefix"] = True
        return out
    except E.CallReverted as x:
        return R("revert", E.hexb(x.data), guard=None, reason=f"external call {x.fn} reverted (bubbled)")
    except E.Unsupported as x:
        return R("unsupported", reason=f"{action}: {x}")
    except (ArithmeticError, RecursionError) as x:
        return R("unsupported", reason=f"{action}: {type(x).__name__}: {x}")
    wd = {E.h32(k): E.h32(e.overlay[k]) for k in sorted(e.touched)}
    if not env.get("return_data"):
        return R("ok", None, wd, e.events, None)
    try:
        ret = E.return_data(model, e, action)
    except E.Unsupported as x:
        return R("unsupported", reason=f"{action}: return data: {x}")
    except (ArithmeticError, RecursionError) as x:
        return R("unsupported", reason=f"{action}: return data: {type(x).__name__}: {x}")
    return R("ok", None, wd, e.events, None, **{"return": E.hexb(ret)})
