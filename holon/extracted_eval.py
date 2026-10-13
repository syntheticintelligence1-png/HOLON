"""The executable step of the extracted model (I20; the A/B interface between the model and the refinement harness;
whitepaper §8.7, Def 4.7). The contract is the docstring of tests_m2/test_extracted_refinement.py, clause 7.

  step(model, state, action, args, env) -> {"status": "ok" | "revert" | "unsupported",
                                            "revert": "0x.." | None, "writes": {"0x<slot>": "0x<word>"},
                                            "events": [{"topics": ["0x.."], "data": "0x.."}],
                                            "guard": "<action>#<span>#<k>" | None, ...}

  model  holon.machine.load_extracted(doc): the document's programs (holon.machine.Program), its storage layout
         (inherited storage included) and its ABI.
  state  raw storage before the step: {"0x<slot>": "0x<word>"} (or ints); a missing slot is 0.
  args   the action's arguments by parameter name (holon.evm_abi values: ints, bools, 0x-hex for addresses, bytesN and
         bytes, str for strings, dicts for structs, lists for arrays); normalized by the action's ABI types (a raw int
         for a dirty calldata leaf stays that word: the decoder's "abi" check rejects it).
  env    "caller", "this", "msg.value", "msg.data.length", "block.<member>", "tx.<member>", "gasleft" (ints or 0x-hex);
         "blobhash": [word, ...] (BLOBHASH(i) is 0 past the list);
         "calls": [{"fn": "<Interface>.<function>" | null, "to", "data", "args": {name: value} | null, "ok", "ret"}]
                  the external calls the real code made, with their answers (a call term is answered by the entry with
                  its function and arguments; two different answers for one call are unsupported);
         "unknown": {"<span>": {"<name>": value}}   values of ["unknown", span, name] terms;
         "immutable", "code", "balance", "blockhash": {key: value} for those terms (immutable by name, code and balance
                  by address).

The result. "status" ok or revert, "revert" the raw revert data, "writes" every slot a write of the step touches with
its new word (packing kept), "events" the logs in order, "guard" the id of the check that reverted (None on ok, and on a
revert that no check of the document decides, such as a call term whose answer is a revert outside any call check).
Extras: "revert_prefix": true when only the leading bytes of the revert data are determined (an error whose arguments
the document does not record: its 4-byte selector), "reason" for an unsupported step.

Semantics. Terms are the language of holon.frontends.solidity.transitions (I17 W4 plus the I19 follow-up) with exact
256-bit EVM semantics: + - * ** wrap mod 2^256, / and % give 0 for a zero divisor (the Yul semantics; Solidity's checked
division is an implicit check, a panic record), shifts of 256 bits or more give 0, comparisons are unsigned, && || !
test non-zero, "trunc" keeps the low bits, "~" and "neg" are bitwise and two's complement; ["?", c, a, b], && and ||
evaluate lazily, as the code does. ["fits", N, [op, a, b]] (the exact, non-modular result of op lies in [0, 2^N)),
["sfits", N, ..] (in [-2^(N-1), 2^(N-1)), operands two's complement N-bit), ["callok", fn, receiver, args..] (the
external call succeeds); a loop's symbols ["iter", loop], ["carried", loop, name], ["count", loop], ["exit", loop,
name], ["returned", loop, j] are bound by running the loop record (Eval.loop); ["mloop", loop, ["iter", loop], count,
[write..]] repeats its writes for iter < count and ["when", c, write] writes when c holds. Storage reads ["storage", f]
(and their ["map"], ["member"], ["index"] paths) read the pre-state at the compiler's slots (mapping slots
keccak256(key . slot), struct members at their slot and offset, packed values masked as the compiler reads them: a bool
is its raw byte, bytesN left-aligned); ["store", base, path, v] reads v at path and the base elsewhere. Memory regions
["mem", writes...] are byte arrays built from their writes; a byte no write determines is unknown and reading it is
unsupported (never zero: memory may be dirty). abi.encodePacked takes each word's width from its type: a parameter's ABI
type, a family's or member's storage type, an immutable's declared type, 32 bytes for a hash or a calldata word, 20 for
an address; a word of no known type is unsupported.

The step runs the action's program (holon.machine.ExtractedModel.program) in seq order: a check whose condition is 0
reverts with the revert data the document records (holon.extracted_eval.revert_data); a write applies its value at its
path when its condition holds; an event is encoded from its signature, topic0 and topic terms; a loop record runs its
body per iteration (at most MAX_ITERATIONS) when its condition holds. Writes, events and checks are over the pre-state:
the document states every term over the storage before the transaction (store chains for what the action wrote).

Unsupported, never a guess: a term whose value is not determined by the arguments, the pre-state and env (an unknown
term without its env value, an external call with no answer, an unknown memory byte, an index past an input's length
whose implicit revert the document does not place, a packed word of no known width): status "unsupported" with
"reason". The refinement harness counts it as a status disagreement.
"""
from __future__ import annotations

import hashlib
import json
import re

from .keccak import keccak256 as _keccak

WORD = 1 << 256
MASK = WORD - 1
ERROR_STRING = bytes.fromhex("08c379a0")
PANIC = bytes.fromhex("4e487b71")
MAX_MEM = 1 << 22          # a memory offset beyond this is not a memory address the code can use
MAX_ITERATIONS = 4096      # a loop that runs longer is unsupported (the bound is stated in the reason)
SUBST_HEADS = {"carried", "exit", "count", "iter", "returned"}


class Unsupported(Exception):
    """A value the arguments, the pre-state and env do not determine."""


_MISSING = object()


class Poison:
    """A loop name whose value the step does not determine (e.g. a memory pointer): reading it is unsupported, carrying
    it is not (a pointer only placed memory writes, which are not observable)."""

    def __init__(self, reason: str):
        self.reason = reason


class CallReverted(Exception):
    """An external call whose answer is a revert: the step reverts with its data (bubbling)."""

    def __init__(self, data: bytes, fn: str):
        super().__init__(fn)
        self.data, self.fn = data, fn


class Reverted(Exception):
    """A check of the program failed."""

    def __init__(self, check, data: bytes, prefix: bool = False):
        super().__init__(check.id)
        self.check, self.data, self.prefix = check, data, prefix


def keccak(b: bytes) -> int:
    return int.from_bytes(_keccak(bytes(b)), "big")


def h32(v: int) -> str:
    return "0x%064x" % (v & MASK)


def hexb(b: bytes) -> str:
    return "0x" + bytes(b).hex()


def canonical(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------------------------------------ values
def to_int(v) -> int:
    """A word from an input value: int, bool, or 0x-hex (big-endian, right-aligned)."""
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v & MASK
    if isinstance(v, str):
        s = v.strip().lower()
        if s.startswith("0x"):
            return int(s[2:] or "0", 16) & MASK
        if re.fullmatch(r"-?\d+", s):
            return int(s) & MASK
    if isinstance(v, (bytes, bytearray)) and len(v) <= 32:
        return int.from_bytes(bytes(v), "big")
    raise Unsupported(f"not a word: {str(v)[:80]}")


def to_bytes(v) -> bytes:
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    if isinstance(v, str):
        s = v.strip()
        if s.lower().startswith("0x"):
            try:
                return bytes.fromhex(s[2:])
            except ValueError:
                pass
        return s.encode("utf-8")
    if isinstance(v, list) and all(isinstance(x, int) and 0 <= x < 256 for x in v):
        return bytes(v)
    raise Unsupported(f"not bytes: {str(v)[:80]}")


_UINT = re.compile(r"^u?int(\d*)$")
_BYTESN = re.compile(r"^bytes(\d+)$")


def norm(v, p: dict | None):
    """An ABI value as the evaluator holds it: words as ints (bytesN left-aligned), bytes and strings as bytes,
    tuples as dicts by member name, arrays as lists. p: the ABI parameter ({type, components}); None: untyped."""
    if p is None:
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v & MASK
        if isinstance(v, dict):
            return {k: norm(x, None) for k, x in v.items()}
        if isinstance(v, list):
            return [norm(x, None) for x in v]
        if isinstance(v, str) and v.lower().startswith("0x") and len(v) in (42, 66):
            return to_int(v)        # an address or a word (untyped: right-aligned)
        if isinstance(v, str):
            return to_bytes(v)
        return v
    t = p.get("type", "")
    m = re.fullmatch(r"(.*)\[(\d*)\]", t)
    if m:
        inner = dict(p, type=m.group(1))
        if not isinstance(v, list):
            raise Unsupported(f"argument of type {t} is not a list")
        return [norm(x, inner) for x in v]
    if t == "tuple":
        comps = p.get("components") or []
        if isinstance(v, dict):
            return {c["name"]: norm(v.get(c["name"]), c) for c in comps}
        if isinstance(v, list) and len(v) == len(comps):
            return {c["name"]: norm(x, c) for c, x in zip(comps, v)}
        raise Unsupported(f"argument of type tuple is neither a dict nor a list of {len(comps)}")
    if t == "string":
        return v.encode("utf-8") if isinstance(v, str) and not v.lower().startswith("0x") else to_bytes(v)
    if t == "bytes":
        return to_bytes(v)
    mb = _BYTESN.match(t)
    if mb:
        if isinstance(v, str) and v.lower().startswith("0x"):
            raw = bytes.fromhex(v[2:])
            return int.from_bytes(raw[:32].ljust(32, b"\0"), "big")
        if isinstance(v, (bytes, bytearray)):
            return int.from_bytes(bytes(v)[:32].ljust(32, b"\0"), "big")
        return to_int(v)          # an int is taken as the EVM word (left-aligned) itself
    if t == "bool":
        # True/False as 1/0; a raw word (dirty calldata) stays that word: the decoder's "abi" check rejects it
        return int(v) if isinstance(v, bool) else to_int(v)
    if v is None:
        raise Unsupported(f"missing value of type {t}")
    mi = _UINT.match(t)
    if mi and t.startswith("int") and isinstance(v, int) and v < 0:
        return v & MASK            # a negative intN is its two's complement word
    return to_int(v)


# ------------------------------------------------------------------------------------------------ ABI encoding
def parse_types(text: str) -> list[dict]:
    """The parameter list of a canonical signature's argument part, e.g. "uint256,(bytes,uint8)[]", as ABI
    parameters."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    if cur:
        out.append(cur)
    res = []
    for i, t in enumerate(out):
        t = t.strip()
        if t.startswith("("):
            close, d = 0, 0
            for j, ch in enumerate(t):
                d += ch == "("
                d -= ch == ")"
                if d == 0:
                    close = j
                    break
            comps = parse_types(t[1:close])
            for k, c in enumerate(comps):
                c["name"] = f"_{k}"
            res.append({"type": "tuple" + t[close + 1:], "components": comps, "name": f"_{i}"})
        else:
            res.append({"type": t, "name": f"_{i}"})
    return res


def signature_types(sig: str) -> list[dict]:
    m = re.fullmatch(r"[^()]*\((.*)\)", str(sig or ""))
    if not m:
        raise Unsupported(f"not a signature: {sig!r}")
    return parse_types(m.group(1)) if m.group(1) else []


def _is_dynamic(p: dict) -> bool:
    t = p.get("type", "")
    if t in ("bytes", "string") or t.endswith("[]"):
        return True
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        return _is_dynamic(dict(p, type=m.group(1)))
    if t == "tuple":
        return any(_is_dynamic(c) for c in p.get("components") or [])
    return False


def _word_of(v, p: dict) -> bytes:
    t = p.get("type", "")
    x = v if isinstance(v, int) else to_int(v)
    m = _UINT.match(t)
    if m and t.startswith("int"):
        bits = int(m.group(1) or 256)
        x &= (1 << bits) - 1
        if x >> (bits - 1):
            x = (x - (1 << bits)) & MASK
    return (x & MASK).to_bytes(32, "big")


def abi_encode(values: list, params: list[dict]) -> bytes:
    """Standard ABI encoding (head/tail) of values by their parameters."""
    heads, tails = [], []
    size = 32 * sum(_static_words(p) for p in params)
    for v, p in zip(values, params):
        if _is_dynamic(p):
            heads.append(None)
            tails.append(_encode_one(v, p))
        else:
            heads.append(_encode_one(v, p))
            tails.append(b"")
    out, off = b"", size
    for h, t in zip(heads, tails):
        if h is None:
            out += off.to_bytes(32, "big")
            off += len(t)
        else:
            out += h
    return out + b"".join(tails)


def _static_words(p: dict) -> int:
    if _is_dynamic(p):
        return 1
    t = p.get("type", "")
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        return int(m.group(2)) * _static_words(dict(p, type=m.group(1)))
    if t == "tuple":
        return sum(_static_words(c) for c in p.get("components") or [])
    return 1


def _encode_one(v, p: dict) -> bytes:
    t = p.get("type", "")
    if t in ("bytes", "string"):
        b = to_bytes(v)
        return len(b).to_bytes(32, "big") + b + b"\0" * ((32 - len(b) % 32) % 32)
    m = re.fullmatch(r"(.*)\[(\d*)\]", t)
    if m:
        inner = dict(p, type=m.group(1))
        xs = list(v)
        body = abi_encode(xs, [inner] * len(xs))
        return (len(xs).to_bytes(32, "big") + body) if m.group(2) == "" else body
    if t == "tuple":
        comps = p.get("components") or []
        xs = [v[c["name"]] for c in comps] if isinstance(v, dict) else list(v)
        return abi_encode(xs, comps)
    return _word_of(v, p)


def abi_decode(data: bytes, params: list[dict]) -> list:
    """Decode ABI data by parameters (static words, bytes, strings, arrays, tuples)."""
    out, pos = [], 0
    for p in params:
        if _is_dynamic(p):
            off = int.from_bytes(data[pos:pos + 32], "big")
            out.append(_decode_at(data, off, p))
            pos += 32
        else:
            v, used = _decode_static(data, pos, p)
            out.append(v)
            pos += used
    return out


def _decode_static(data: bytes, pos: int, p: dict):
    t = p.get("type", "")
    m = re.fullmatch(r"(.*)\[(\d+)\]", t)
    if m:
        inner = dict(p, type=m.group(1))
        xs = []
        for _ in range(int(m.group(2))):
            v, u = _decode_static(data, pos, inner)
            xs.append(v)
            pos += u
        return xs, 32 * _static_words(p)
    if t == "tuple":
        d = {}
        for c in p.get("components") or []:
            v, u = _decode_static(data, pos, c)
            d[c["name"]] = v
            pos += u
        return d, 32 * _static_words(p)
    w = data[pos:pos + 32]
    if len(w) < 32:
        raise Unsupported("ABI data too short")
    return int.from_bytes(w, "big"), 32      # every static value type is its word (bytesN left-aligned)


def _decode_at(data: bytes, off: int, p: dict):
    t = p.get("type", "")
    if t in ("bytes", "string"):
        n = int.from_bytes(data[off:off + 32], "big")
        return bytes(data[off + 32:off + 32 + n])
    m = re.fullmatch(r"(.*)\[(\d*)\]", t)
    if m:
        inner = dict(p, type=m.group(1))
        if m.group(2) == "":
            n = int.from_bytes(data[off:off + 32], "big")
            return abi_decode(data[off + 32:], [inner] * n)
        return abi_decode(data[off:], [inner] * int(m.group(2)))
    if t == "tuple":
        comps = p.get("components") or []
        return dict(zip([c["name"] for c in comps], abi_decode(data[off:], comps)))
    raise Unsupported(f"cannot decode {t}")


def error_string(reason: str) -> bytes:
    return ERROR_STRING + abi_encode([reason.encode("utf-8")], [{"type": "string"}])


def panic(code: int) -> bytes:
    return PANIC + int(code).to_bytes(32, "big")


# ------------------------------------------------------------------------------------------------ storage and memory
class SRef:
    """A storage location (a family and an access path of evaluated accessors) with the writes a store chain made
    before the read (overlays, latest first)."""

    def __init__(self, fam: str, path: tuple = (), overlays: tuple = ()):
        self.fam, self.path, self.overlays = fam, tuple(path), tuple(overlays)

    def extend(self, kind: str, x) -> "SRef":
        return SRef(self.fam, self.path + ((kind, x),), self.overlays)


class Mem:
    """A memory region: bytes and which of them a write determined."""

    def __init__(self):
        self.data = bytearray()
        self.known = bytearray()

    def _grow(self, n: int) -> None:
        if n > MAX_MEM:
            raise Unsupported(f"memory offset {n} beyond any region the code can address")
        if len(self.data) < n:
            self.data.extend(b"\0" * (n - len(self.data)))
            self.known.extend(b"\0" * (n - len(self.known)))

    def write(self, off: int, b: bytes) -> None:
        self._grow(off + len(b))
        self.data[off:off + len(b)] = b
        self.known[off:off + len(b)] = b"\1" * len(b)

    def havoc(self) -> None:
        self.known = bytearray(len(self.known))

    def read(self, off: int, n: int) -> bytes:
        if n == 0:
            return b""
        if off + n > MAX_MEM:
            raise Unsupported(f"memory read at {off} beyond any region the code can address")
        if off + n > len(self.known) or not all(self.known[off:off + n]):
            raise Unsupported(f"memory bytes {off}..{off + n - 1} are not determined by the region's writes")
        return bytes(self.data[off:off + n])


def _within(src: str, span: str) -> bool:
    """src ("unit:lo[-hi]") lies within span (same unit, line range contained)."""
    def parse(s):
        u, _, r = str(s).rpartition(":")
        lo, _, hi = r.partition("-")
        if not lo.isdigit():
            return None
        return u, int(lo), int(hi or lo)
    a, b = parse(src), parse(span)
    return bool(a and b and a[0] == b[0] and b[1] <= a[1] and a[2] <= b[2])


# ------------------------------------------------------------------------------------------------ the evaluator
class Eval:
    def __init__(self, model, state: dict, action: str, args: dict, env: dict):
        self.m = model
        self.state = {to_int(k): to_int(v) for k, v in (state or {}).items()}
        self.action = action
        self.env = env or {}
        params = model.params(action) if hasattr(model, "params") else None
        if params is not None:
            self.args = {p["name"]: norm(args.get(p["name"]), p) for p in params if p["name"] in (args or {})}
        else:
            self.args = {k: norm(v, None) for k, v in (args or {}).items()}
        self.subst: dict = {}          # canonical term -> value: carried / exit / count / mloop iteration variables
        self.subst_heads = set(SUBST_HEADS)
        self.failed_call: bytes | None = None
        self.overlay: dict = {}        # slot -> word written by the step so far
        self.touched: list = []        # slots written, first-write order
        self.events: list = []

    # ---------------------------------------------------------- env
    def envval(self, key: str):
        if key in self.env and self.env[key] is not None:
            return to_int(self.env[key])
        raise Unsupported(f"environment term {key} has no value in env")

    # ---------------------------------------------------------- storage
    def load(self, ref: SRef):
        """The value at a storage location: an int for an elementary value, a dict for a struct."""
        for wpath, val in ref.overlays:
            n = min(len(wpath), len(ref.path))
            if wpath[:n] != ref.path[:n]:
                continue
            if len(wpath) == len(ref.path):
                return val
            if len(wpath) < len(ref.path):
                return self.project(val, ref.path[len(wpath):], ref)
            raise Unsupported(f"a read of {ref.fam} over a store to a deeper path (a partly written aggregate)")
        slot, off, tid = self.locate(ref)
        return self.load_at(slot, off, tid)

    def project(self, val, rest: tuple, ref: SRef):
        for kind, x in rest:
            if isinstance(val, int) and val == 0:
                return 0
            if kind == "member" and isinstance(val, dict) and x in val:
                val = val[x]
            else:
                raise Unsupported(f"a read of {ref.fam} through a stored aggregate value")
        return val

    def load_at(self, slot: int, off: int, tid: str):
        t = self.m.type_of(tid)
        if t.get("encoding") == "inplace" and "members" in t:
            return {mm["label"]: self.load_at(slot + int(mm["slot"]), int(mm["offset"]), mm["type"])
                    for mm in t["members"]}
        if t.get("encoding") != "inplace" or "base" in t:
            raise Unsupported(f"a value read of a {t.get('label')} (not an elementary value)")
        n = int(t["numberOfBytes"])
        w = self.state.get(slot, 0)
        v = (w >> (8 * off)) & ((1 << (8 * n)) - 1)
        if _BYTESN.match(str(t.get("label", ""))) and n < 32:
            v <<= 256 - 8 * n
        return v

    def locate(self, ref: SRef) -> tuple[int, int, str]:
        """(slot, offset, type id) of a storage location, by the compiler's layout."""
        f = self.m.family(ref.fam)
        slot, off, tid = f.slot, f.offset, f.type
        for kind, x in ref.path:
            t = self.m.type_of(tid)
            enc = t.get("encoding")
            if kind == "map":
                if enc != "mapping":
                    raise Unsupported(f"{ref.fam}: a map access into {t.get('label')}")
                kt = self.m.type_of(t["key"])
                if kt.get("encoding") == "inplace":
                    kw = self.word_for_key(x, kt)
                    slot = keccak(kw.to_bytes(32, "big") + slot.to_bytes(32, "big"))
                else:
                    slot = keccak(to_bytes(x) + slot.to_bytes(32, "big"))
                off, tid = 0, t["value"]
            elif kind == "member":
                mm = next((m for m in t.get("members") or [] if m["label"] == x), None)
                if mm is None:
                    raise Unsupported(f"{ref.fam}: no member {x} in {t.get('label')}")
                slot, off, tid = slot + int(mm["slot"]), int(mm["offset"]), mm["type"]
            elif kind == "index":
                bt = self.m.type_of(t["base"]) if "base" in t else None
                if bt is None:
                    raise Unsupported(f"{ref.fam}: an index into {t.get('label')}")
                size = int(bt["numberOfBytes"])
                i = to_int(x)
                if enc == "dynamic_array":
                    n = self.state.get(slot, 0)
                    if i >= n:
                        raise Unsupported(f"{ref.fam}: index {i} past the array's length {n} (an implicit revert "
                                          "the document does not place)")
                    base = keccak(slot.to_bytes(32, "big"))
                else:
                    m = re.search(r"\[(\d+)\]$", str(t.get("label", "")))
                    if m and i >= int(m.group(1)):
                        raise Unsupported(f"{ref.fam}: index {i} past a static array's length")
                    base = slot
                if size <= 16:
                    per = 32 // size
                    slot, off = base + i // per, (i % per) * size
                else:
                    slot, off = base + i * ((size + 31) // 32), 0
                tid = t["base"]
            else:
                raise Unsupported(f"{ref.fam}: accessor {kind}")
            slot &= MASK
        return slot, off, tid

    @staticmethod
    def word_for_key(x, kt: dict) -> int:
        v = to_int(x)
        n = int(kt.get("numberOfBytes", 32))
        lab = str(kt.get("label", ""))
        if _BYTESN.match(lab):
            return v                       # left-aligned already
        if n < 32 and not lab.startswith("int"):
            v &= (1 << (8 * n)) - 1
        return v

    def as_int(self, v) -> int:
        if isinstance(v, bool):
            return int(v)
        if isinstance(v, int):
            return v
        if isinstance(v, SRef):
            x = self.load(v)
            if isinstance(x, dict):
                raise Unsupported(f"{v.fam}: a struct used as a word")
            return x
        if isinstance(v, (bytes, bytearray)) and len(v) <= 32:
            return int.from_bytes(bytes(v), "big")
        raise Unsupported(f"not a word: {type(v).__name__}")

    def as_bytes(self, v) -> bytes:
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, int):
            return v.to_bytes(32, "big")
        raise Unsupported(f"not bytes: {type(v).__name__}")

    def value(self, v):
        """A value with storage references resolved (struct reads become dicts)."""
        return self.load(v) if isinstance(v, SRef) else v

    # ---------------------------------------------------------- terms
    def ev(self, t):
        if isinstance(t, bool):
            return int(t)
        if isinstance(t, int):
            return t & MASK
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            raise Unsupported(f"not a term: {str(t)[:80]}")
        h = t[0]
        if h in self.subst_heads:
            k = canonical(t)
            if k in self.subst:
                v = self.subst[k]
                if isinstance(v, Poison):
                    raise Unsupported(v.reason)
                return v
            if h in SUBST_HEADS:
                raise Unsupported(f"{h} term {canonical(t)[:120]} outside the loop that defines it")
        f = getattr(self, "t_" + _NAMES.get(h, h.replace(".", "_")), None)
        if f is not None:
            return f(t)
        if h in _BIN:
            return self.binop(h, t)
        raise Unsupported(f"term {h} is outside the evaluator's language")

    def iv(self, t) -> int:
        return self.as_int(self.ev(t))

    def truth(self, t) -> bool:
        return self.iv(t) != 0

    # leaves
    def t_param(self, t):
        n = t[1]
        if n in self.args:
            return self.args[n]
        raise Unsupported(f"argument {n} is missing")

    def t_caller(self, t):
        return self.envval("caller")

    def t_this(self, t):
        return self.envval("this")

    def t_env(self, t):
        return self.envval(t[1])

    def t_storage(self, t):
        f = self.m.family(t[1])
        tt = self.m.type_of(f.type)
        ref = SRef(t[1])
        if tt.get("encoding") == "inplace" and "members" not in tt and "base" not in tt:
            return self.load(ref)
        return ref

    def t_sload(self, t):
        return self.state.get(self.iv(t[1]), 0)

    def t_str(self, t):
        return bytes.fromhex(t[1] or "")

    def t_immutable(self, t):
        return to_int(self._table("immutable", t[1]))

    def t_blockhash(self, t):
        return to_int(self._table("blockhash", str(self.iv(t[1]))))

    def t_balance(self, t):
        return to_int(self._table("balance", _addr(self.iv(t[1]))))

    def t_code(self, t):
        return to_bytes(self._table("code", _addr(self.iv(t[1]))))

    def _table(self, name: str, key: str):
        """env[name][key] (an address key as 0x + 40 lowercase hex digits)."""
        tab = self.env.get(name) or {}
        if key in tab:
            v = tab[key]
            return v if isinstance(v, (bytes, bytearray, str)) else to_int(v)
        raise Unsupported(f"{name}[{key}] has no value in env")

    def t_blobhash(self, t):
        i = self.iv(t[1])
        bl = self.env.get("blobhash")
        if bl is None:
            raise Unsupported("blobhash has no value in env")
        return to_int(bl[i]) if i < len(bl) else 0

    def t_unknown(self, t):
        span, name = t[1], t[2]
        tab = (self.env.get("unknown") or {}).get(span) or {}
        key = name if isinstance(name, str) else canonical(name)
        if key in tab:
            v = tab[key]
            return norm(v, None) if not isinstance(v, (bytes, bytearray)) else bytes(v)
        raise Unsupported(f"unknown term {span} {key}: env gives no value")

    # inputs
    def t_member(self, t):
        b = self.ev(t[1])
        n = t[2]
        if isinstance(b, SRef):
            r = b.extend("member", n)
            tt = self.m.type_of(self.locate(r)[2])
            return self.load(r) if tt.get("encoding") == "inplace" and "base" not in tt else r
        if isinstance(b, dict):
            if n in b:
                return b[n]
            raise Unsupported(f"no member {n}")
        if isinstance(b, int) and b == 0:
            return 0
        raise Unsupported(f"member {n} of a {type(b).__name__}")

    def t_map(self, t):
        b = self.ev(t[1])
        k = self.ev(t[2])
        if not isinstance(b, SRef):
            raise Unsupported("a map access into a value that is not storage")
        r = b.extend("map", self.as_int(k) if not isinstance(k, (bytes, bytearray)) else bytes(k))
        tt = self.m.type_of(self.locate(r)[2])
        if tt.get("encoding") == "inplace" and "members" not in tt and "base" not in tt:
            return self.load(r)
        return r

    def t_index(self, t):
        b = self.ev(t[1])
        i = self.iv(t[2])
        if isinstance(b, SRef):
            r = b.extend("index", i)
            tt = self.m.type_of(self.locate(r)[2])
            if tt.get("encoding") == "inplace" and "members" not in tt and "base" not in tt:
                return self.load(r)
            return r
        if isinstance(b, (bytes, bytearray)):
            if i >= len(b):
                raise Unsupported(f"byte index {i} past the input's length {len(b)} (an implicit revert the "
                                  "document does not place)")
            return b[i]
        if isinstance(b, list):
            if i >= len(b):
                raise Unsupported(f"index {i} past the input's length {len(b)} (an implicit revert the document "
                                  "does not place)")
            return b[i]
        raise Unsupported(f"an index into a {type(b).__name__}")

    def t_len(self, t):
        x = self.ev(t[1])
        if isinstance(x, (bytes, bytearray, list)):
            return len(x)
        if isinstance(x, SRef):
            slot, _off, tid = self.locate(x)
            tt = self.m.type_of(tid)
            if tt.get("encoding") == "dynamic_array":
                return self.state.get(slot, 0)
            raise Unsupported(f"length of a storage {tt.get('label')}")
        raise Unsupported(f"length of a {type(x).__name__}")

    def t_byte(self, t):
        x = self.as_bytes(self.ev(t[1]))
        k = self.iv(t[2])
        if k >= len(x):
            raise Unsupported(f"byte {k} past the input's length {len(x)} (an implicit revert the document does not "
                              "place)")
        return x[k]

    def t_word(self, t):
        x = self.as_bytes(self.ev(t[1]))
        k = self.iv(t[2])
        if k > MAX_MEM:
            raise Unsupported(f"word at offset {k}")
        return int.from_bytes(x[k:k + 32].ljust(32, b"\0"), "big")

    def t_cdoff(self, t):
        raise Unsupported("the calldata offset of an input depends on its ABI encoding position")

    def t_calldata(self, t):
        raise Unsupported("raw calldata is not an argument")

    def t_struct(self, t):
        return {m: self.value(self.ev(v)) for m, v in t[2]}

    def t_tuple(self, t):
        return [self.ev(x) for x in t[1:]]

    def t_at(self, t):
        v = self.ev(t[2])
        k = t[1] if isinstance(t[1], int) else self.iv(t[1])
        if isinstance(v, (list, tuple)) and k < len(v):
            return v[k]
        raise Unsupported(f"component {k} of a {type(v).__name__}")

    def t_value(self, t):
        return ("value", self.iv(t[1]))

    # conditionals and logic (lazy)
    def t_ite(self, t):
        return self.ev(t[2]) if self.truth(t[1]) else self.ev(t[3])

    def t_and(self, t):
        for x in t[1:]:
            if not self.truth(x):
                return 0
        return 1

    def t_or(self, t):
        for x in t[1:]:
            if self.truth(x):
                return 1
        return 0

    def t_not(self, t):
        return int(not self.truth(t[1]))

    def t_bnot(self, t):
        return (~self.iv(t[1])) & MASK

    def t_neg(self, t):
        return (-self.iv(t[1])) & MASK

    def t_trunc(self, t):
        bits = t[1] if isinstance(t[1], int) else self.iv(t[1])
        return self.iv(t[2]) & ((1 << bits) - 1)

    def t_addmod(self, t):
        a, b, n = self.iv(t[1]), self.iv(t[2]), self.iv(t[3])
        return (a + b) % n if n else 0

    def t_mulmod(self, t):
        a, b, n = self.iv(t[1]), self.iv(t[2]), self.iv(t[3])
        return (a * b) % n if n else 0

    def binop(self, op: str, t):
        if len(t) != 3:
            raise Unsupported(f"operator {op} with {len(t) - 1} operands")
        a, b = self.iv(t[1]), self.iv(t[2])
        return _BIN[op](a, b)

    # implicit checks (I19 follow-up A19-02)
    def exact(self, t, signed_bits: int | None = None) -> int:
        """The exact (non-modular) value of [op, a, b] over operand words (two's complement when signed_bits)."""
        if not (isinstance(t, list) and len(t) == 3 and t[0] in ("+", "-", "*", "**")):
            if isinstance(t, list) and len(t) == 2 and t[0] == "neg":
                x = self.iv(t[1])
                return -_signed(x, signed_bits) if signed_bits else -x
            raise Unsupported(f"fits over {canonical(t)[:80]}: not an arithmetic operation")
        a, b = self.iv(t[1]), self.iv(t[2])
        if signed_bits:
            a, b = _signed(a, signed_bits), _signed(b, signed_bits)
        op = t[0]
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b > 4096 and abs(a) > 1:
            return 1 << 4097          # far beyond any width: the exact power is not needed
        return a ** b

    def t_fits(self, t):
        n = t[1] if isinstance(t[1], int) else self.iv(t[1])
        v = self.exact(t[2])
        return int(0 <= v < (1 << n))

    def t_sfits(self, t):
        n = t[1] if isinstance(t[1], int) else self.iv(t[1])
        v = self.exact(t[2], n)
        return int(-(1 << (n - 1)) <= v < (1 << (n - 1)))

    # hashes and encodings
    def t_keccak256(self, t):
        return keccak(self.hash_input(t[1]))

    def t_sha256(self, t):
        return int.from_bytes(hashlib.sha256(self.hash_input(t[1])).digest(), "big")

    def hash_input(self, x) -> bytes:
        v = self.ev(x)
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, int):
            return v.to_bytes(32, "big")
        if isinstance(v, SRef):
            return self.as_int(v).to_bytes(32, "big")
        raise Unsupported(f"hash of a {type(v).__name__}")

    def t_abi_encode(self, t):
        out = b""
        heads, tails = [], []
        vals = [self.ev(x) for x in t[1:]]
        for v in vals:
            if isinstance(v, (bytes, bytearray)):
                heads.append(None)
                b = bytes(v)
                tails.append(len(b).to_bytes(32, "big") + b + b"\0" * ((32 - len(b) % 32) % 32))
            elif isinstance(v, int) or isinstance(v, SRef):
                heads.append(self.as_int(v).to_bytes(32, "big"))
                tails.append(b"")
            else:
                raise Unsupported("abi.encode of an aggregate without its type")
        off = 32 * len(vals)
        for hd, tl in zip(heads, tails):
            if hd is None:
                out += off.to_bytes(32, "big")
                off += len(tl)
            else:
                out += hd
        return out + b"".join(tails)

    def t_abi_encodePacked(self, t):
        """Packed encoding: bytes and strings as they are, a word in its type's width (module docstring)."""
        out = b""
        for x in t[1:]:
            v = self.value(self.ev(x))
            if isinstance(v, (bytes, bytearray)):
                out += bytes(v)
                continue
            ty = self.term_type(x)
            if ty is None:
                raise Unsupported(f"abi.encodePacked of a word of no known type: {canonical(x)[:120]}")
            n, left = _packed_width(ty)
            w = self.as_int(v).to_bytes(32, "big")
            out += w[:n] if left else w[32 - n:]
        return out

    def term_type(self, t) -> str | None:
        """The Solidity type name of a word term where its source fixes it (a parameter, an immutable or constant, a
        storage value, an environment member, a hash or a calldata word), else None."""
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return None
        h = t[0]
        if h in ("word", "keccak256", "sha256", "blobhash", "blockhash"):
            return "bytes32"
        if h in ("caller", "this"):
            return "address"
        if h == "env":
            return "address" if t[1] in ("block.coinbase", "tx.origin") else "uint256"
        if h == "immutable":
            ty = self.m.immutable_type(t[1]) if hasattr(self.m, "immutable_type") else None
            return (ty or {}).get("type")
        if h == "param":
            for p in (self.m.params(self.action) if hasattr(self.m, "params") else None) or []:
                if p.get("name") == t[1]:
                    return p.get("type")
            return None
        if h in ("storage", "map", "member", "index"):
            try:
                ref = self._ref_of(t)
                lab = str(self.m.type_of(self.locate(ref)[2]).get("label", ""))
            except (Unsupported, KeyError):
                return None
            if lab.startswith(("contract ", "address")):
                return "address"
            return "uint8" if lab.startswith("enum ") else lab
        return None

    def _ref_of(self, t) -> SRef:
        """The storage location a storage read term names."""
        h = t[0]
        if h == "storage":
            return SRef(t[1])
        b = self.ev(t[1])
        if not isinstance(b, SRef):
            raise Unsupported("not a storage location")
        if h == "member":
            return b.extend("member", t[2])
        k = self.ev(t[2])
        if h == "map":
            return b.extend("map", self.as_int(k) if not isinstance(k, (bytes, bytearray)) else bytes(k))
        return b.extend("index", self.as_int(k))

    def t_mem(self, t):
        m = Mem()
        for w in t[1:]:
            self.mem_write(m, w)
        return m

    def mem_write(self, m: Mem, w) -> None:
        k = w[0] if isinstance(w, list) and w else None
        if k == "mstore":
            m.write(self.iv(w[1]), self.iv(w[2]).to_bytes(32, "big"))
        elif k == "mstore8":
            m.write(self.iv(w[1]), bytes([self.iv(w[2]) & 0xFF]))
        elif k == "calldatacopy":
            off, src, frm, n = self.iv(w[1]), self.ev(w[2]), self.iv(w[3]), self.iv(w[4])
            b = self.as_bytes(src)
            if n > MAX_MEM:
                raise Unsupported(f"calldatacopy of {n} bytes")
            m.write(off, b[frm:frm + n].ljust(n, b"\0"))
        elif k == "mloop":            # ["mloop", loop, ["iter", loop], count, [write...]]
            kvar, n = w[2], self.iv(w[3])
            if n > MAX_ITERATIONS:
                raise Unsupported(f"memory loop {w[1]}: {n} iterations (more than {MAX_ITERATIONS})")
            key = canonical(kvar)
            if isinstance(kvar, list) and kvar and isinstance(kvar[0], str):
                self.subst_heads.add(kvar[0])
            body = w[4] if isinstance(w[4], list) and w[4] and isinstance(w[4][0], list) else [w[4]]
            saved = self.subst.get(key, _MISSING)
            try:
                for j in range(n):
                    self.subst[key] = j
                    for x in body:
                        self.mem_write(m, x)
            finally:
                if saved is _MISSING:
                    self.subst.pop(key, None)
                else:
                    self.subst[key] = saved
        elif k == "when":             # ["when", c, write]: a write made only when c holds
            if self.truth(w[1]):
                self.mem_write(m, w[2])
        elif k in ("loop", "unknown"):
            m.havoc()
        else:
            raise Unsupported(f"memory write {k}")

    def mem_of(self, x) -> Mem:
        v = self.ev(x)
        if isinstance(v, Mem):
            return v
        raise Unsupported(f"not a memory region: {type(v).__name__}")

    def t_slice(self, t):
        m = self.mem_of(t[1])
        return m.read(self.iv(t[2]), self.iv(t[3]))

    def t_mload(self, t):
        m = self.mem_of(t[1])
        return int.from_bytes(m.read(self.iv(t[2]), 32), "big")

    def t_ptr(self, t):
        raise Unsupported("a memory pointer's address depends on the free memory pointer")

    def t_store(self, t):
        if not t[2]:                  # a store at the empty path: the whole variable's new value
            return self.value(self.ev(t[3]))
        base = self.ev(t[1])
        if not isinstance(base, SRef):
            raise Unsupported("a store into a value that is not storage")
        wpath = self.path(t[2])
        v = self.value(self.ev(t[3]))
        return SRef(base.fam, base.path, ((tuple(base.path) + tuple(wpath), v),) + base.overlays)

    def path(self, accs) -> list:
        out = []
        for acc in accs or []:
            kind, x = acc[0], acc[1]
            if kind == "member":
                out.append(("member", x))
            elif kind == "map":
                k = self.ev(x)
                out.append(("map", self.as_int(k) if not isinstance(k, (bytes, bytearray)) else bytes(k)))
            elif kind == "index":
                out.append(("index", self.iv(x)))
            else:
                raise Unsupported(f"store accessor {kind}")
        return out

    # external calls
    def t_call(self, t):
        fn = t[1]
        raw = [self.ev(x) for x in t[2:]]
        value = None
        if raw and isinstance(raw[-1], tuple) and raw[-1][:1] == ("value",):
            value = raw[-1][1]
            raw = raw[:-1]
        if fn.startswith("address."):
            return self.low_level(fn, raw, value)
        ok, data, sig = self.answer(fn, None, raw)
        if not ok:
            raise CallReverted(data, fn)
        outs = (sig or {}).get("outputs")
        if outs is None:
            if len(data) == 32:
                return int.from_bytes(data, "big")
            raise Unsupported(f"external call {fn}: its return types are unknown")
        vals = abi_decode(data, outs) if outs else []
        return vals[0] if len(vals) == 1 else vals

    def t_callok(self, t):
        fn = t[1]
        receiver = self.iv(t[2]) if t[2] is not None else None
        raw = [self.ev(x) for x in t[3:]]
        if fn.startswith("address."):
            ok = self.low_level(fn, ([receiver] if receiver is not None else []) + raw, None, status_only=True)
            return int(ok)
        ok, data, _ = self.answer(fn, receiver, raw)
        if not ok:
            self.failed_call = data
        return int(ok)

    def _calls(self) -> list:
        cs = self.env.get("calls")
        if cs is None:
            raise Unsupported("env gives no external calls")
        return cs

    def answer(self, fn: str, receiver, args: list) -> tuple[bool, bytes, dict | None]:
        """(ok, return or revert data, signature) of the external call fn(args) (to receiver when known)."""
        sig = self.m.call_signature(fn) if hasattr(self.m, "call_signature") else None
        ins = (sig or {}).get("inputs")
        mine = [self.value(a) for a in args]
        hits = []
        for c in self._calls():
            if c.get("fn") != fn:
                continue
            if receiver is not None and c.get("to") is not None:
                try:
                    if to_int(c["to"]) != receiver:
                        continue
                except Unsupported:
                    continue
            if ins is not None and len(ins) == len(mine):
                theirs = c.get("args")
                try:
                    want = [norm(a, p) if not isinstance(a, int) else a & MASK for a, p in zip(mine, ins)]
                    if isinstance(theirs, dict):
                        if [norm(theirs.get(p["name"]), p) for p in ins] != want:
                            continue
                    elif c.get("data"):
                        if to_bytes(c["data"])[4:] != abi_encode(want, ins):
                            continue
                except Unsupported:
                    continue
            elif mine:
                raise Unsupported(f"external call {fn}: its signature is unknown, its arguments cannot be matched")
            hits.append(c)
        answers = {(bool(c.get("ok")), (c.get("ret") or "0x").lower()) for c in hits}
        if not answers:
            raise Unsupported(f"external call {fn}: env gives no answer for these arguments")
        if len(answers) > 1:
            raise Unsupported(f"external call {fn}: env gives several answers for these arguments")
        ok, ret = answers.pop()
        return ok, to_bytes(ret), sig

    def low_level(self, fn: str, args: list, value, status_only: bool = False):
        kind = fn.split(".", 1)[1]
        if not args:
            raise Unsupported(f"{fn} without a receiver")
        to = self.as_int(args[0])
        data = self.as_bytes(args[1]) if len(args) > 1 else b""
        hits = []
        for c in self._calls():
            try:
                if to_int(c.get("to")) != to:
                    continue
                if to_bytes(c.get("data") or "0x") != data:
                    continue
            except Unsupported:
                continue
            if c.get("fn") not in (None, fn) and not str(c.get("fn") or "").startswith("address."):
                continue
            hits.append(c)
        answers = {(bool(c.get("ok")), (c.get("ret") or "0x").lower()) for c in hits}
        if len(answers) != 1:
            raise Unsupported(f"{fn} to {to:#x}: env gives {'no' if not answers else 'several'} answers")
        ok, ret = answers.pop()
        if status_only:
            if not ok:
                self.failed_call = to_bytes(ret)
            return ok
        if kind == "transfer":
            if not ok:
                raise CallReverted(b"", fn)
            return []
        if kind == "send":
            return int(ok)
        return [int(ok), to_bytes(ret)]

    # ---------------------------------------------------------- the program
    def run(self, steps) -> None:
        from .machine import Check, Event, Loop, MStore, Write
        for s in steps:
            if isinstance(s, Check):
                self.failed_call = None
                if not self.truth(s.expr):
                    data, prefix = revert_data(self.m, s, self)
                    raise Reverted(s, data, prefix)
            elif isinstance(s, Write):
                if self.truth(s.cond):
                    self.write(s)
            elif isinstance(s, Event):
                if self.truth(s.cond):
                    self.events.append(self.event(s))
            elif isinstance(s, Loop):
                if self.truth(s.cond):
                    self.loop(s)
            elif isinstance(s, MStore):
                continue          # memory is not observable; terms carry the regions they read

    def loop(self, lp) -> None:
        """A loop record (A19-04), run concretely: the carried names start at their entry values; each iteration k
        binds ["iter", loop] to k and ["carried", loop, name] to the names' values, stops when its head fails, runs its
        body (the records made in the generic iteration), then stops when a return path's condition or its break holds
        (the names take their at_break values), else steps the names to their next values. Afterwards ["count", loop]
        is the number of iterations completed, ["exit", loop, name] the names' values (the document's exit values,
        evaluated with the count and the last values bound), ["returned", loop, j] whether return path j was taken and
        ["exit", loop, ["return", j]] its value. The loop's terms carry its reach index r as a last element when r > 0
        (holon.machine.Loop.sym)."""
        vals = {canonical(n): (n, self._name_value(e)) for n, e, _v in lp.carried}
        k = 0
        taken = None
        broke = False
        while True:
            if k > MAX_ITERATIONS:
                raise Unsupported(f"loop {lp.src}: more than {MAX_ITERATIONS} iterations")
            bound = self._bind(lp, vals, k)
            nxt = None
            try:
                if not self.truth(lp.head):
                    break
                self.run(lp.body)
                for j, (cond, value) in enumerate(lp.returns):
                    if self.truth(cond):
                        taken = (j, self.value(self.ev(value)))
                        break
                if taken is not None:
                    break
                if self.truth(lp.brk):
                    vals.update({canonical(n): (n, self._name_value(e)) for n, e in lp.at_break})
                    broke = True
                    break
                nxt = {canonical(n): (n, self._name_value(e)) for n, e in lp.next}
            finally:
                for key in bound:
                    self.subst.pop(key, None)
            vals.update(nxt)
            k += 1
        self.subst[canonical(lp.sym("count"))] = k
        for j in range(len(lp.returns)):
            self.subst[canonical(lp.sym("returned", j))] = int(taken is not None and taken[0] == j)
        if taken is not None:
            self.subst[canonical(lp.sym("exit", ["return", taken[0]]))] = taken[1]
        # the exit values: the names' values where the loop left off (iteration k, before its head or at its break)
        bound = self._bind(lp, vals, k)
        try:
            exits = {canonical(n): (n, vals[canonical(n)][1]) for n, _e in lp.exits if canonical(n) in vals}
            for n, e in lp.exits:
                if canonical(n) not in exits and not (broke or taken is not None):
                    exits[canonical(n)] = (n, self._name_value(e))
        finally:
            for key in bound:
                self.subst.pop(key, None)
        for key, (n, v) in sorted(vals.items()):
            self.subst[canonical(lp.sym("exit", n))] = v
        for key, (n, v) in sorted(exits.items()):
            self.subst[canonical(lp.sym("exit", n))] = v

    def _name_value(self, t):
        """A loop name's value, or a Poison when the step does not determine it (read later, it is unsupported)."""
        try:
            return self.ev(t)
        except Unsupported as x:
            return Poison(str(x))

    def _bind(self, lp, vals: dict, k: int) -> list:
        keys = [canonical(lp.sym("iter"))]
        self.subst[keys[0]] = k
        for _key, (n, v) in vals.items():
            key = canonical(lp.sym("carried", n))
            self.subst[key] = v
            keys.append(key)
        return keys

    def write(self, w) -> None:
        path = tuple(self.path(w.path))
        val = self.value(self.ev(w.value))
        slot, off, tid = self.locate(SRef(w.family, path))
        self._write_at(slot, off, tid, val)

    def _write_at(self, slot: int, off: int, tid: str, value) -> None:
        t = self.m.type_of(tid)
        if t.get("encoding") == "inplace" and "members" in t:
            for mm in t["members"]:
                v = value.get(mm["label"], 0) if isinstance(value, dict) else (0 if value == 0 else None)
                if v is None:
                    raise Unsupported(f"a struct write of a {type(value).__name__}")
                self._write_at(slot + int(mm["slot"]), int(mm["offset"]), mm["type"], v)
            return
        if t.get("encoding") != "inplace" or "base" in t:
            raise Unsupported(f"a write of a whole {t.get('label')}")
        n = int(t["numberOfBytes"])
        v = self.as_int(value)
        if _BYTESN.match(str(t.get("label", ""))) and n < 32:
            v >>= 256 - 8 * n
        mask = ((1 << (8 * n)) - 1) << (8 * off)
        old = self.overlay.get(slot, self.state.get(slot, 0))
        self.overlay[slot] = (old & ~mask & MASK) | ((v << (8 * off)) & mask)
        if slot not in self.touched:
            self.touched.append(slot)

    def event(self, ev) -> dict:
        """The log of an emit record (A19-09): topic0 (none for an anonymous event), then the document's topic terms
        of the indexed arguments (V19-04), and as data the ABI encoding of the other arguments by the signature's
        types."""
        if not ev.signature:
            raise Unsupported(f"event {ev.event}: the document gives no signature")
        ps = signature_types(ev.signature)
        if len(ev.args) != len(ps) or len(ev.indexed) != len(ps):
            raise Unsupported(f"event {ev.event}: {len(ev.args)} arguments and {len(ev.indexed)} indexed flags for "
                              f"{len(ps)} parameters")
        topics = []
        if not ev.anonymous:
            if not isinstance(ev.topic0, str):
                raise Unsupported(f"event {ev.event}: no topic0")
            topics.append(to_int(ev.topic0))
        if len(ev.topics) != sum(1 for x in ev.indexed if x):
            raise Unsupported(f"event {ev.event}: {len(ev.topics)} topic terms for {sum(map(bool, ev.indexed))} "
                              "indexed arguments")
        topics += [self.iv(t) for t in ev.topics]
        data_vals, data_ps = [], []
        for x, p, ix in zip(ev.args, ps, ev.indexed):
            if not ix:
                data_vals.append(self.value(self.ev(x)))
                data_ps.append(p)
        return {"topics": [h32(x) for x in topics], "data": hexb(abi_encode(data_vals, data_ps))}


def _packed_width(ty: str) -> tuple[int, bool]:
    """(bytes, left-aligned) of an elementary type in abi.encodePacked."""
    ty = ty.strip()
    if ty in ("address", "address payable") or ty.startswith("contract "):
        return 20, False
    if ty == "bool":
        return 1, False
    m = _BYTESN.match(ty)
    if m:
        return int(m.group(1)), True
    m = _UINT.match(ty)
    if m:
        return int(m.group(1) or 256) // 8, False
    raise Unsupported(f"abi.encodePacked of a {ty}")


def _signed(x: int, bits: int) -> int:
    x &= (1 << bits) - 1
    return x - (1 << bits) if x >> (bits - 1) else x


def _addr(v: int) -> str:
    return "0x" + ("%064x" % (v & MASK))[-40:]


def _shl(a, b):
    return (a << b) & MASK if b < 256 else 0


def _shr(a, b):
    return a >> b if b < 256 else 0


_BIN = {
    "+": lambda a, b: (a + b) & MASK, "-": lambda a, b: (a - b) & MASK, "*": lambda a, b: (a * b) & MASK,
    "/": lambda a, b: a // b if b else 0, "%": lambda a, b: a % b if b else 0, "**": lambda a, b: pow(a, b, WORD),
    "&": lambda a, b: a & b, "|": lambda a, b: a | b, "^": lambda a, b: a ^ b, "<<": _shl, ">>": _shr,
    "==": lambda a, b: int(a == b), "!=": lambda a, b: int(a != b), "<": lambda a, b: int(a < b),
    "<=": lambda a, b: int(a <= b), ">": lambda a, b: int(a > b), ">=": lambda a, b: int(a >= b),
}
_NAMES = {"?": "ite", "&&": "and", "||": "or", "!": "not", "~": "bnot", "not": "bnot", "neg": "neg",
          "trunc": "trunc", "abi.encode": "abi_encode", "abi.encodePacked": "abi_encodePacked"}


# ------------------------------------------------------------------------------------------------ revert data
def revert_data(m, c, e: Eval | None = None) -> tuple[bytes, bool]:
    """(revert data, whether only its prefix is determined) of a failing check (module docstring), as the document
    records it: a panic record's or an assert reach's code gives Panic(code); a failing external call (and an uncaught
    try call) bubbles the call's revert data; the dispatcher's and the decoder's checks (callvalue, calldatasize, abi,
    slice) revert with empty data; a guard with "error" {selector, signature} reverts with the selector followed by the
    ABI encoding of its reach's args by the signature's types (Error(string) for a reason); a guard without one reverts
    with empty data."""
    if c.kind == "panic" or c.code is not None:
        return panic(to_int(c.code)), False
    if c.kind in ("call", "uncaught"):
        if e is not None and e.failed_call is not None:
            return e.failed_call, False
        raise Unsupported(f"check {c.id}: the external call's failure has no revert data in env")
    if c.kind in ("callvalue", "calldatasize", "abi", "slice"):
        return b"", False
    err = c.error if isinstance(c.error, dict) else None
    if err is None:
        return b"", False
    sel = err.get("selector")
    if not (isinstance(sel, str) and re.fullmatch(r"0x[0-9a-fA-F]{8}", sel)):
        raise Unsupported(f"check {c.id}: its error has no selector")
    head = bytes.fromhex(sel[2:])
    ps = signature_types(err.get("signature") or "")
    args = c.args if isinstance(c.args, list) else []
    if not ps:
        return head, False
    if e is None or len(args) != len(ps):
        return head, True
    vals = [e.value(e.ev(x)) for x in args]
    return head + abi_encode(vals, ps), False


# ------------------------------------------------------------------------------------------------ the step
def _result(status, revert=None, w=None, evs=None, guard=None, **extra) -> dict:
    out = {"status": status, "revert": revert, "writes": w or {}, "events": evs or [], "guard": guard}
    out.update(extra)
    return out


def step(model, state, action: str, args: dict, env: dict) -> dict:
    """One transition of the extracted model (module docstring)."""
    if action not in model.actions:
        return _result("unsupported", reason=f"no action {action} in the document")
    prog = model.program(action)
    e = Eval(model, state, action, args or {}, env or {})
    try:
        e.run(prog.steps)
    except Reverted as x:
        out = _result("revert", hexb(x.data), guard=x.check.id)
        if x.prefix:
            out["revert_prefix"] = True
        return out
    except CallReverted as x:
        return _result("revert", hexb(x.data), guard=None, reason=f"external call {x.fn} reverted (bubbled)")
    except Unsupported as x:
        return _result("unsupported", reason=f"{action}: {x}")
    except (ArithmeticError, RecursionError) as x:
        return _result("unsupported", reason=f"{action}: {type(x).__name__}: {x}")
    wd = {h32(k): h32(e.overlay[k]) for k in sorted(e.touched)}
    return _result("ok", None, wd, e.events, None)
