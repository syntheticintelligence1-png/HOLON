"""The corpus of the extracted model's refinement (I20-B; tests_m2/test_extracted_refinement.py clauses 2 and 7-9).

Sources, in this order (holon.replay_fragments runs them):
  m1        the I16/M1 refinement corpus: holon.mreplay.random_corpus on the M1 model of the binding's abstract facts,
            with the M1 replay's seed and size (20261011, 300 traces), written as abstract rows; the harness turns each
            row into a concrete call exactly as the M1 trace harness does;
  witness   every REFUTED per-entry witness of a SORT-site law (results/<M>, I15) over the binding's abstract facts:
            its prefix run then its action, as `holon replay --milestone M2` runs it (the :363 Panic 0x11 witnesses);
  seed      a binding's own concrete traces ("corpus": a toy's planted calls), in place of abstract ones;
  boundary  fork steps: the first successful call of each action in the translation run (the first run of the base
            traces), with one ABI leaf replaced by a value at a boundary of its type or of a width of the document's
            sorts (0, 1, 2^w - 1, 2^w, max uint), and a bytes leaf cut or padded to the lengths the action's checks
            compare it with; and the same call poked (vm.store, before the call) with a dirty byte (2 and 255) at
            every bool storage location its reaches read (Evaluator.reads on the call's state): the document models
            the compiler's raw reads of a bool's byte, so a byte other than 0 and 1 is a boundary of its storage;
  target    fork steps built for one reach each (Search.target): a base call of the translation run, or a call built
            from the ABI for an action the corpus never calls, mutated on the atoms of the reach's term (its parameters,
            their bytes and words, the caller, msg.value, the clock, the blob hashes; a dirty calldata word for an ABI
            range check; the call's calldata cut to the lengths a calldatasize check compares, the selector kept)
            and kept when the term evaluator here (Evaluator) finds every earlier reach of the action
            holding and that one false. A reach the search cannot violate gets a mechanical reason (counts, atoms and
            what the targeting steps did on both sides).
Every value comes from the documents (the extracted document, the binding and its abstract facts, the I15 records),
the compiled ABI and the corpus's own translation run, never from tests/reference. Deterministic: sorted iteration,
fixed seeds, first-found order.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from . import evm_abi as abi
from .replay_fragments import Step, model_call, track

ROOT = Path(__file__).resolve().parents[1]
M1_SEED = 20261011       # holon.mreplay.main_replay_m1's refinement corpus rule
M1_SIZE = 300
PER_REACH = 2            # targeting steps kept per reach
SUFFIX_PER_REACH = 2     # suffix traces per reach the single-step search cannot reach
MAX_BASES = 48           # base calls tried per reach
FRESH = "0x" + "00" * 18 + "dead"   # a caller no corpus step uses
DIRTY_BOOL = (2, 255)    # the bytes a bool's storage location is poked with (the boundary corpus)
CMP = ("==", "!=", "<", "<=", ">", ">=")
MASK = (1 << 256) - 1


def binding_init(binding: dict, root: Path = ROOT) -> list[int]:
    """holonDeploy's parameters: a list in the binding, or {"facts", "keys"} read from the facts' initial state
    ("a.0" indexes a list)."""
    init = binding.get("init", [])
    if isinstance(init, list):
        return [int(x) for x in init]
    facts = json.loads((root / init["facts"]).read_text())
    out = []
    for k in init["keys"]:
        v = facts.get("initial", {})
        for part in k.split("."):
            v = v[int(part)] if isinstance(v, list) else v[part]
        out.append(int(v))
    return out


def abstract_facts(binding: dict, root: Path = ROOT) -> dict | None:
    a = binding.get("abstract")
    if not a:
        return None
    from . import facts as F
    return F.load(root / a["facts"])


def rows(trace: list[dict], facts: dict, source: str, label: str) -> list[Step]:
    from .mreplay import encode_step
    return [Step("abstract", row=encode_step(a, facts), meta={"source": source, "label": label}, abstract=dict(a))
            for a in trace]


def m1_traces(binding: dict, root: Path = ROOT, n: int = M1_SIZE, seed: int = M1_SEED) -> list[list[dict]]:
    """The M1 refinement corpus (holon.mreplay.random_corpus on the M1 model of the binding's abstract facts)."""
    from .mpipeline import CompiledMachine
    from .mreplay import random_corpus
    a = binding.get("abstract")
    if not a or n <= 0:
        return []
    cm = CompiledMachine.build(root / a["facts"])
    return random_corpus(cm, n, seed=seed)


def witness_traces(binding: dict, root: Path = ROOT, milestone: str = "M2") -> list[tuple[str, list[dict]]]:
    """(label, trace) of every REFUTED per-entry witness of a SORT-site law whose document is the binding's abstract
    facts, in (law, entry) order."""
    from .ir import LAW_GLOB, record_files
    from .mpipeline import site_law
    a = binding.get("abstract")
    if not a:
        return []
    laws = {p.stem: json.loads(p.read_text()) for p in (root / "laws" / milestone).glob(LAW_GLOB)}
    out = []
    for p in record_files(root / "results" / milestone):
        r = json.loads(p.read_text())
        lid = r.get("law_id")
        if r.get("status") != "REFUTED" or site_law(laws.get(lid, {})) is None or laws[lid].get("facts") != a["facts"]:
            continue
        for e in sorted(r.get("witnesses") or {}):
            w = r["witnesses"][e]
            if w.get("status") == "REFUTED" and w.get("witness"):
                out.append((f"{lid}/{e}", list(w["witness"]["s"]["run"]) + [dict(w["witness"]["a"])]))
    return sorted(out, key=lambda x: x[0])


def seed_traces(binding: dict, fns_by_name: dict) -> list[list[Step]]:
    """A binding's concrete traces: {"corpus": {"traces": [[{"fn", "args", "caller", "value"?, "timestamp"?,
    "blobs"?}, ...], ...]}}, encoded with the compiled ABI."""
    out = []
    for i, tr in enumerate((binding.get("corpus") or {}).get("traces") or []):
        steps = []
        for j, c in enumerate(tr):
            fn = fns_by_name.get(c["fn"])
            if fn is None:
                raise ValueError(f"binding corpus trace {i} step {j}: no function {c['fn']!r} in the compiled ABI")
            steps.append(Step("call", caller=c["caller"].lower(), value=int(c.get("value", 0)),
                              timestamp=int(c.get("timestamp", 0)), blobs=list(c.get("blobs") or []),
                              data=abi.encode_call(fn, c.get("args") or {}), meta={"source": "seed", "label": f"seed/{i}"}))
        out.append(steps)
    return out


def base_traces(binding: dict, root: Path, n: int, sources, fns_by_name: dict | None = None) -> tuple[list, dict]:
    """(traces, counts): the m1, witness and seed traces as steps."""
    out, counts = [], {}
    facts = abstract_facts(binding, root)
    if facts is not None and "m1" in sources:
        ts = [rows(t, facts, "m1", f"m1/{i}") for i, t in enumerate(m1_traces(binding, root, n))]
        out += ts
        counts["m1"] = len(ts)
    if facts is not None and "witness" in sources:
        ts = [rows(t, facts, "witness", lab) for lab, t in witness_traces(binding, root)]
        out += ts
        counts["witness"] = len(ts)
    if binding.get("corpus"):
        ts = seed_traces(binding, fns_by_name or {})
        out += ts
        counts["seed"] = len(ts)
    return out, counts


# ---------------------------------------------------------------- the term evaluator (corpus construction only)
class _Unknown:
    __slots__ = ()

    def __repr__(self):
        return "U"


U = _Unknown()


class Ref:
    """A storage location: slot, compiled type id, byte offset."""
    __slots__ = ("slot", "type", "offset")

    def __init__(self, slot: int, type_: str, offset: int = 0):
        self.slot, self.type, self.offset = slot, type_, offset


def _int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _truth(v):
    if not _int(v):
        return U
    return bool(v)


def abi_to_term(t: dict, v):
    """An ABI value as the evaluator's value: ints for value types (bytesN left-aligned in the word), bytes for bytes
    and string, dicts and lists for tuples and arrays; a raw int (dirty calldata) stays an int."""
    ty = t["type"]
    arr = abi._array(ty)
    if arr is not None:
        return [abi_to_term(abi._elem(t, arr[0]), x) for x in v]
    if ty == "tuple":
        return {c["name"]: abi_to_term(c, v[c["name"]]) for c in t.get("components") or []}
    if _int(v):
        return v & MASK
    if ty == "bytes":
        return bytes.fromhex(v[2:])
    if ty == "string":
        return v.encode()
    if ty == "address":
        return int(v, 16)
    if ty.startswith("bytes"):
        b = bytes.fromhex(v[2:])
        return int.from_bytes(b + bytes(32 - len(b)), "big")
    if ty == "bool":
        return int(bool(v))
    return int(v) % (1 << 256)


OPS2 = {"+": lambda a, b: (a + b) & MASK, "-": lambda a, b: (a - b) & MASK, "*": lambda a, b: (a * b) & MASK,
        "/": lambda a, b: a // b if b else 0, "%": lambda a, b: a % b if b else 0,
        "**": lambda a, b: pow(a, b, 1 << 256), "&": lambda a, b: a & b, "|": lambda a, b: a | b,
        "^": lambda a, b: a ^ b, "<<": lambda a, b: (a << b) & MASK if b < 256 else 0,
        ">>": lambda a, b: a >> b if b < 256 else 0, "==": lambda a, b: int(a == b), "!=": lambda a, b: int(a != b),
        "<": lambda a, b: int(a < b), "<=": lambda a, b: int(a <= b), ">": lambda a, b: int(a > b),
        ">=": lambda a, b: int(a >= b)}


def _signed(v: int) -> int:
    return v - (1 << 256) if v >> 255 else v


class Evaluator:
    """Evaluates the document's terms (holon/frontends/solidity/transitions.py, plus the planned "fits", "sfits" and
    "callok" of the I19 follow-up) on one concrete step: the tracked storage (through the compiled layout, inherited
    storage included), the decoded arguments and the environment. Three-valued: a term it cannot decide (a loop's phi
    or carried value, a havocked value, memory, an external call answer it does not know, ...) is U. It decides which
    corpus candidates to keep; it never decides a comparison (the model's evaluator does)."""

    def __init__(self, layout, state: dict, fn: dict | None, args: dict, env: dict, answers=None):
        self.layout, self.state, self.env = layout, state, env
        self.args = {}
        for i in (fn or {}).get("inputs") or []:
            if i.get("name") in args:
                self.args[i["name"]] = abi_to_term(i, args[i["name"]])
        self.answers = answers   # (name, [arg ints]) -> int | U, for the calls the step did not make
        self.reads: list | None = None   # when a list: (slot, offset) of every bool storage location loaded
        self.heads = {"?": self._cond, "!": self._lnot, "&&": self._and, "||": self._or, "~": self._bnot,
                      "not": self._bnot, "neg": self._neg, "trunc": self._trunc, "param": self._param,
                      "caller": self._caller, "this": self._this, "storage": self._storage, "sload": self._sload,
                      "map": self._map_t, "member": self._member_t, "len": self._len, "byte": self._byte,
                      "index": self._index, "word": self._word, "env": self._env, "blobhash": self._blobhash,
                      "call": self._call_t, "callok": self._callok, "keccak256": self._keccak, "sha256": self._sha,
                      "str": self._str, "fits": self._fits, "sfits": self._sfits}

    # storage
    def _load(self, ref: Ref):
        t = self.layout.type_of(ref.type)
        if t.get("encoding") != "inplace" or t.get("members") or ref.type.startswith("t_array"):
            return ref
        n = int(t.get("numberOfBytes", "32"))
        if self.reads is not None and t.get("label") == "bool":
            self.reads.append((ref.slot, ref.offset))
        w = self.state.get(ref.slot, 0)
        return (w >> (8 * ref.offset)) & ((1 << (8 * n)) - 1)

    def _map(self, base: Ref, key):
        t = self.layout.type_of(base.type)
        kt, vt = t.get("key", ""), t.get("value", "")
        if isinstance(key, bytes) and kt.startswith(("t_bytes_", "t_string")):
            h = abi.keccak256(key + base.slot.to_bytes(32, "big"))
        elif _int(key):
            h = abi.keccak256((key & MASK).to_bytes(32, "big") + base.slot.to_bytes(32, "big"))
        else:
            return U
        return self._load(Ref(int.from_bytes(h, "big"), vt, 0))

    def _member(self, base, name):
        if isinstance(base, dict):
            return base.get(name, U)
        if isinstance(base, Ref):
            for m in self.layout.type_of(base.type).get("members") or []:
                if m["label"] == name:
                    return self._load(Ref(base.slot + int(m["slot"]), m["type"], int(m["offset"])))
        return U

    def _call(self, name: str, args: list, want_ok: bool = False):
        for c in self.env.get("calls") or []:
            if c.get("fn") != name or c.get("args") is None:
                continue
            got = [int(x, 16) if isinstance(x, str) and x.startswith("0x") else int(x)
                   for x in (c.get("args") or {}).values()]
            if got != args:
                continue
            if want_ok:
                return int(bool(c.get("ok")))
            if not c.get("ok"):
                continue
            ret = c.get("ret") or "0x"
            return int(ret[2:66], 16) if len(ret) >= 66 else U
        if want_ok:
            return U
        return self.answers(name, args) if self.answers else U

    def ev(self, t):
        if isinstance(t, bool):
            return int(t)
        if _int(t):
            return t & MASK
        if isinstance(t, str) and t.isdigit():
            return int(t) & MASK
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            return U
        f = self.heads.get(t[0])
        if f is not None:
            return f(t)
        if t[0] in OPS2 and len(t) == 3:
            a, b = self.ev(t[1]), self.ev(t[2])
            return OPS2[t[0]](a, b) if _int(a) and _int(b) else U
        return U

    def _param(self, t):
        return self.args.get(t[1], U)

    def _caller(self, t):
        c = self.env.get("caller")
        return int(c, 16) if isinstance(c, str) else U

    def _this(self, t):
        c = self.env.get("this")
        return int(c, 16) if isinstance(c, str) else U

    def _storage(self, t):
        v = self.layout.vars.get(t[1])
        return U if v is None else self._load(Ref(v["slot"], v["type"], v["offset"]))

    def _sload(self, t):
        s = self.ev(t[1])
        return self.state.get(s, 0) if _int(s) else U

    def _map_t(self, t):
        base, key = self.ev(t[1]), self.ev(t[2])
        return self._map(base, key) if isinstance(base, Ref) and key is not U else U

    def _member_t(self, t):
        return self._member(self.ev(t[1]), t[2])

    def _len(self, t):
        x = self.ev(t[1])
        if isinstance(x, (bytes, list)):
            return len(x)
        if isinstance(x, Ref) and self.layout.type_of(x.type).get("encoding") == "dynamic_array":
            return self.state.get(x.slot, 0)
        return U

    def _byte(self, t):
        x, k = self.ev(t[1]), self.ev(t[2])
        return x[k] if isinstance(x, bytes) and _int(k) and k < len(x) else U

    def _index(self, t):
        x, k = self.ev(t[1]), self.ev(t[2])
        if isinstance(x, (bytes, list)) and _int(k):
            return x[k] if k < len(x) else U
        if isinstance(x, Ref) and _int(k):
            ty = self.layout.type_of(x.type)
            if ty.get("encoding") == "dynamic_array" and int(self.layout.type_of(ty.get("base", "")).get(
                    "numberOfBytes", "0")) == 32:
                start = int.from_bytes(abi.keccak256(x.slot.to_bytes(32, "big")), "big")
                return self._load(Ref((start + k) & MASK, ty["base"], 0))
        return U

    def _word(self, t):
        x, k = self.ev(t[1]), self.ev(t[2])
        if isinstance(x, bytes) and _int(k):
            b = x[k:k + 32]
            return int.from_bytes(b + bytes(32 - len(b)), "big")
        return U

    def _env(self, t):
        v = self.env.get(t[1])
        if isinstance(v, str) and v.startswith("0x"):
            return int(v, 16)
        return v if _int(v) else U

    def _blobhash(self, t):
        i = self.ev(t[1])
        bl = self.env.get("blobhash") or []
        if not _int(i):
            return U
        return int(bl[i], 16) if i < len(bl) else 0

    def _call_args(self, t):
        if not isinstance(t[1], str) or t[1].startswith("address."):
            return None
        args = [self.ev(a) for a in t[2:]]
        return args if all(_int(a) for a in args) else None

    def _call_t(self, t):
        args = self._call_args(t)
        return U if args is None else self._call(t[1], args)

    def _callok(self, t):
        # ["callok", fn, receiver, args...]: the receiver is not among the recorded call's arguments
        args = self._call_args([t[0], t[1]] + list(t[3:])) if len(t) >= 3 else None
        return U if args is None else self._call(t[1], args, want_ok=True)

    def _bytes_of(self, t):
        if isinstance(t, list) and t and t[0] == "abi.encode":
            vals = [self.ev(a) for a in t[1:]]
            if not all(_int(v) for v in vals):
                return U
            return b"".join((v & MASK).to_bytes(32, "big") for v in vals)
        x = self.ev(t)
        return x if isinstance(x, bytes) else U

    def _keccak(self, t):
        b = self._bytes_of(t[1])
        return U if b is U else int.from_bytes(abi.keccak256(b), "big")

    def _sha(self, t):
        b = self._bytes_of(t[1])
        return U if b is U else int.from_bytes(hashlib.sha256(b).digest(), "big")

    def _str(self, t):
        s = str(t[1])
        try:
            return bytes.fromhex(s[2:] if s.startswith("0x") else s)
        except ValueError:
            return U

    def _exact(self, t, signed: bool):
        """The exact (unbounded) value of [op, a, b] for op in + - * ** (operands as words, or signed)."""
        if not (isinstance(t, list) and len(t) == 3 and t[0] in ("+", "-", "*", "**")):
            v = self.ev(t)
            return (_signed(v) if signed else v) if _int(v) else U
        a, b = self.ev(t[1]), self.ev(t[2])
        if not (_int(a) and _int(b)):
            return U
        if signed:
            a, b = _signed(a), _signed(b)
        if t[0] == "+":
            return a + b
        if t[0] == "-":
            return a - b
        if t[0] == "*":
            return a * b
        if b > 512 and abs(a) > 1:
            return 1 << 600 if a > 0 or b % 2 == 0 else -(1 << 600)
        return a ** b if b >= 0 else U

    def _fits(self, t):
        n = self.ev(t[1])
        v = self._exact(t[2], False)
        return U if not _int(n) or not _int(v) else int(0 <= v < (1 << n))

    def _sfits(self, t):
        n = self.ev(t[1])
        v = self._exact(t[2], True)
        return U if not _int(n) or not _int(v) or n < 1 else int(-(1 << (n - 1)) <= v < (1 << (n - 1)))

    def _cond(self, t):
        c = _truth(self.ev(t[1]))
        return U if c is U else self.ev(t[2] if c else t[3])

    def _lnot(self, t):
        c = _truth(self.ev(t[1]))
        return U if c is U else int(not c)

    def _and(self, t):
        unk = False
        for x in t[1:]:
            c = _truth(self.ev(x))
            if c is U:
                unk = True
            elif not c:
                return 0
        return U if unk else 1

    def _or(self, t):
        unk = False
        for x in t[1:]:
            c = _truth(self.ev(x))
            if c is U:
                unk = True
            elif c:
                return 1
        return U if unk else 0

    def _bnot(self, t):
        x = self.ev(t[1])
        return (~x) & MASK if _int(x) else U

    def _neg(self, t):
        x = self.ev(t[1])
        return (-x) & MASK if _int(x) else U

    def _trunc(self, t):
        x = self.ev(t[2])
        return x & ((1 << int(t[1])) - 1) if _int(x) else U


def first_failing(reaches: list, ev: Evaluator) -> tuple[int | None, bool]:
    """(index of the first reach whose expr is false, decided): (None, True) when every reach holds; decided is False
    when an earlier reach is undetermined."""
    decided = True
    for i, r in enumerate(reaches):
        c = _truth(ev.ev(r.expr)) if r.expr is not None else U
        if c is U:
            decided = False
        elif not c:
            return i, decided
    return None, decided


# ---------------------------------------------------------------- bases: calls of the translation run
@dataclass
class Base:
    tid: int
    pos: int                  # the step's index in its trace: a fork placed there starts from the same state
    action: str
    fn: dict
    args: dict
    env: dict
    state: dict
    ok: bool | None           # the real outcome (None: a call built from the ABI, never run)
    first: int | None = None
    decided: bool = False


def _abi_value(t: dict, v: int):
    """An int as the ABI value of an elementary type, or None when the type cannot hold it."""
    ty = t["type"]
    if ty.startswith("uint"):
        bits = int(ty[4:] or 256)
        return v if 0 <= v < 1 << bits else None
    if ty.startswith("int"):
        bits = int(ty[3:] or 256)
        return v if -(1 << (bits - 1)) <= v < 1 << (bits - 1) else None
    if ty == "address":
        return "0x%040x" % v if 0 <= v < 1 << 160 else None
    if ty == "bool":
        return bool(v) if v in (0, 1) else None
    if ty.startswith("bytes") and ty != "bytes":
        n = int(ty[5:])
        if not 0 <= v < 1 << 256:
            return None
        b = v.to_bytes(32, "big")
        return "0x" + b[:n].hex() if not any(b[n:]) else None
    return None


def _bits(ty: str) -> int:
    if ty == "address":
        return 160
    if ty == "bool":
        return 1
    if ty.startswith("uint"):
        return int(ty[4:] or 256)
    if ty.startswith("int"):
        return int(ty[3:] or 256)
    if ty.startswith("bytes") and ty != "bytes":
        return 8 * int(ty[5:])
    return 256


def _default(t: dict):
    ty = t["type"]
    arr = abi._array(ty)
    if arr is not None:
        return [] if arr[1] is None else [_default(abi._elem(t, arr[0])) for _ in range(arr[1])]
    if ty == "tuple":
        return {c["name"]: _default(c) for c in t.get("components") or []}
    if ty in ("bytes", "string"):
        return "0x" if ty == "bytes" else ""
    return _abi_value(t, 0)


def _pseudo_comparisons(t) -> list:
    """Comparisons equivalent to the implicit-check terms of the planned format: ["fits", N, ["-", x, y]] holds iff
    x >= y; ["fits", N, ["+", x, y]] iff x < 2^N - y."""
    if not (isinstance(t, list) and len(t) == 3 and t[0] in ("fits", "sfits") and isinstance(t[2], list)
            and len(t[2]) == 3 and isinstance(t[1], int)):
        return []
    op, x, y = t[2]
    if op == "-":
        return [[">=", x, y]]
    if op == "+":
        return [["<", x, ["-", 1 << t[1], y]], ["<", y, ["-", 1 << t[1], x]]]
    return []


class Search:
    """Builds the boundary and targeting fork steps from the translation run (see the module docstring)."""

    def __init__(self, view, tgt, runs: list, slots: list, step_fn=None):
        self.view, self.tgt, self.runs = view, tgt, runs
        self.fn_of = {}
        for sel, fn in tgt.fns.items():
            a = view.action_of(sel)
            if a is not None:
                self.fn_of[a] = fn
        self.bases: dict[str, list[Base]] = {}
        self.positions: list[tuple[int, int, dict, dict]] = []   # (tid, pos, state, env) of every kept step
        self.answers_tab: dict = {}
        self.callers: set = set()
        self.blobs: set = set()
        self.seeds: dict = {}            # (leaf name, type) -> values seen in the corpus
        self.harness = runs[0].harness if runs else FRESH
        for tr in runs:
            for e, before, _after in track(tr, slots):
                if e.id == "d" or e.fork:
                    continue
                pos = int(e.id)
                env0 = {"caller": e.caller, "this": tr.target, "msg.value": 0, "block.timestamp": e.timestamp,
                        "block.number": e.number, **e.env, "blobhash": [], "calls": []}
                self.positions.append((tr.tid, pos, before, env0))
                if e.caller:
                    self.callers.add(e.caller)
                self.blobs.update(e.blobs)
                mc = model_call(tgt, e, before, tr.target, tr.code, tr.impl_code)
                if mc is None:
                    continue
                action, _state, args, env = mc
                for c in env["calls"]:
                    if c["fn"] and c["ok"] and c["args"] is not None:
                        key = (c["fn"], tuple(int(x, 16) if isinstance(x, str) and x.startswith("0x") else int(x)
                                              for x in c["args"].values()))
                        self.answers_tab.setdefault(key, set()).add(c["ret"])
                fn = self.fn_of[action]
                for i in fn["inputs"]:
                    for path, lt in abi.leaves(i, (i["name"],)):
                        self.seeds.setdefault((path[-1], lt["type"]), []).append(abi.get_path(args, path))
                self.bases.setdefault(action, []).append(Base(tr.tid, pos, action, fn, args, env, before, e.ok))
        self.callers.add(self.harness)
        self.callers.add(FRESH)
        for k in self.seeds:
            seen, out = set(), []
            for v in self.seeds[k]:
                j = json.dumps(v, sort_keys=True)
                if j not in seen:
                    seen.add(j)
                    out.append(v)
            self.seeds[k] = out
        for a, bs in self.bases.items():
            seq = self.view.reaches.get(a, [])
            for b in bs:
                b.first, b.decided = first_failing(seq, self.evaluator(b, b.args, b.env))

    def answers(self, name: str, args: list):
        rets = self.answers_tab.get((name, tuple(args)))
        if rets and len(rets) == 1:
            r = next(iter(rets))
            return int(r[2:66], 16) if len(r) >= 66 else U
        return U

    def evaluator(self, b: Base, args: dict, env: dict) -> Evaluator:
        return Evaluator(self.tgt.layout, b.state, b.fn, args, env, self.answers)

    @staticmethod
    def with_length(b: Base, args: dict, env: dict, raw: str | None) -> dict:
        """env with msg.data.length the length of the calldata the candidate sends (raw, else the call encoded from
        args): a synthesized base, or a mutation that changes a dynamic argument, sends other calldata than the
        base's."""
        if raw is not None:
            data = raw
        else:
            try:
                data = abi.encode_call(b.fn, args)
            except abi.AbiError:
                return env
        return {**env, "msg.data.length": (len(data) - 2) // 2}

    # ------------------------------------------------------------ synthesized bases (actions the corpus never calls)
    def synthesized(self, action: str) -> list[Base]:
        fn = self.fn_of.get(action)
        if fn is None:
            return []
        args = {}
        for i in fn["inputs"]:
            v = _default(i)
            for path, lt in abi.leaves(i, (i["name"],)):
                seeds = self.seeds.get((path[-1], lt["type"])) or []
                if seeds:
                    v = abi.set_path(v, path[1:], seeds[0]) if len(path) > 1 else seeds[0]
            args[i["name"]] = v
        out = []
        for tid, pos, state, env0 in self.spots():
            for who in sorted(self.callers):
                out.append(Base(tid, pos, action, fn, args, {**env0, "caller": who}, state, None))
        return out

    def spots(self) -> list:
        """States to start synthesized calls from: right after the first deployment, and the state before the first
        kept call of each action in the corpus."""
        out, seen = [], set()
        if self.positions:
            out.append(self.positions[0])
            seen.add(self.positions[0][:2])
        for a in sorted(self.bases):
            b = self.bases[a][0]
            if (b.tid, b.pos) not in seen:
                seen.add((b.tid, b.pos))
                out.append(next(p for p in self.positions if p[:2] == (b.tid, b.pos)))
        return out

    # ------------------------------------------------------------ term atoms and comparisons
    @staticmethod
    def _terms(t, acc):
        if isinstance(t, list) and t:
            if isinstance(t[0], str):
                acc.append(t)
                rest = t[1:]
            else:
                rest = t
            for x in rest:
                Search._terms(x, acc)

    def _param_path(self, t):
        """The ABI path of a parameter term (param, member of it, constant index of it), else None."""
        if isinstance(t, list) and t:
            if t[0] == "param":
                return (t[1],)
            if t[0] == "member":
                p = self._param_path(t[1])
                return p + (t[2],) if p else None
            if t[0] == "index" and isinstance(t[2], int):
                p = self._param_path(t[1])
                return p + (t[2],) if p else None
        return None

    def comparisons(self, expr) -> list:
        acc: list = []
        self._terms(expr, acc)
        out = [t for t in acc if t and t[0] in CMP and len(t) == 3]
        for t in acc:
            out += _pseudo_comparisons(t)
        return out

    @staticmethod
    def constants(expr) -> list[int]:
        out = set()

        def walk(t):
            if isinstance(t, bool):
                return
            if isinstance(t, int):
                out.add(t)
            elif isinstance(t, list) and t:
                for x in t[1:]:
                    walk(x)
        walk(expr)
        return sorted(out)

    # ------------------------------------------------------------ mutations
    def mutations(self, b: Base, r, seq) -> list[tuple[str, dict, dict, str | None]]:
        """(label, args, env, raw calldata or None) candidates from base b, each changing one atom of r's term (values
        from the comparisons of the action's reaches evaluated on b, the constants of the term and the boundaries of
        the leaf's type); for an ABI range check, a dirty word of its parameter."""
        expr = r.expr
        ev = self.evaluator(b, b.args, b.env)
        out: list = []
        acc: list = []
        self._terms(expr, acc)
        all_cmp = [c for g in seq for c in self.comparisons(g.expr)]
        consts = self.constants(expr)

        def other_values(pred) -> list[int]:
            vals = []
            for c in all_cmp:
                for side, oth in ((c[1], c[2]), (c[2], c[1])):
                    if pred(side):
                        v = ev.ev(oth)
                        if _int(v):
                            vals += [v - 1, v, v + 1]
            return vals

        def with_leaf(path, value):
            return {**b.args, path[0]: abi.set_path(b.args[path[0]], path[1:], value)} if len(path) > 1 \
                else {**b.args, path[0]: value}

        seen_paths = set()
        for t in acc:
            path = self._param_path(t)
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            lt = abi.leaf_type(b.fn["inputs"], path)
            if lt is None:
                continue
            if lt["type"] in ("bytes", "string"):
                out += [(lab, a, e, None) for lab, a, e in self._bytes_mutations(b, path, lt, seq, ev, with_leaf)]
                continue
            if abi._array(lt["type"]) or lt["type"] == "tuple":
                continue
            bits = _bits(lt["type"])
            vals = other_values(lambda s, p=path: self._param_path(s) == p)
            vals += [c + d for c in consts for d in (-1, 0, 1)] + [0, 1, (1 << bits) - 1, (1 << bits) - 2]
            if lt["type"] == "address":   # the addresses the corpus uses (callers, the harness)
                vals += [int(a, 16) for a in sorted(self.callers)]
            for v in _uniq(vals):
                av = _abi_value(lt, v)
                if av is not None and av != abi.get_path(b.args, path):
                    out.append((f"{'.'.join(map(str, path))}={v}", with_leaf(path, av), b.env, None))
            if r.kind == "abi":
                for w in abi.dirty_words(lt["type"]):
                    data = abi.dirty_call(b.fn, b.args, path, w)
                    if data is not None:
                        out.append((f"dirty {'.'.join(map(str, path))}={hex(w)}", with_leaf(path, w), b.env, data))
        heads = {t[0] for t in acc if t}
        if "caller" in heads:
            for who in sorted(self.callers):
                if who != b.env.get("caller"):
                    out.append((f"caller={who}", b.args, {**b.env, "caller": who}, None))
        envs = {t[1] for t in acc if t and t[0] == "env" and len(t) > 1}
        if "msg.data.length" in envs:   # a calldatasize check: the same call cut short (selector kept)
            try:
                full = abi.encode_call(b.fn, b.args)
            except abi.AbiError:
                full = None
            nfull = (len(full) - 2) // 2 if full else 0
            for v in _uniq(other_values(lambda s: s == ["env", "msg.data.length"]) + [4]):
                if full and 4 <= v < nfull:
                    out.append((f"calldata length={v}", b.args, {**b.env, "msg.data.length": v}, full[:2 + 2 * v]))
        if "msg.value" in envs:
            for v in _uniq(other_values(lambda s: s == ["env", "msg.value"]) + [0, 1]):
                if v >= 0 and v != b.env.get("msg.value"):
                    out.append((f"msg.value={v}", b.args, {**b.env, "msg.value": v}, None))
        if "block.timestamp" in envs:
            ts = b.env.get("block.timestamp") or 0
            for v in _uniq(other_values(lambda s: s == ["env", "block.timestamp"]) + [ts + 1_000_000]):
                if v > 0 and v != ts:
                    out.append((f"timestamp={v}", b.args, {**b.env, "block.timestamp": v}, None))
        if "blobhash" in heads:
            zs = sorted(self.blobs)
            opts = [[], ["0x" + "00" * 32]] + [[z] for z in zs[:2]] + ([[zs[0], zs[-1]]] if zs else [])
            for bl in opts:
                if bl != b.env.get("blobhash"):
                    out.append((f"blobs={len(bl)}", b.args, {**b.env, "blobhash": bl}, None))
        return out

    def _bytes_mutations(self, b, path, lt, seq, ev, with_leaf) -> list:
        cur = abi.get_path(b.args, path)
        raw = bytes.fromhex(cur[2:]) if lt["type"] == "bytes" else cur.encode()
        out = []
        lens, bytes_at, words = set(), {}, {}
        for g in seq:
            for c in self.comparisons(g.expr):
                for side, oth in ((c[1], c[2]), (c[2], c[1])):
                    if not isinstance(side, list):
                        continue
                    if side[:1] == ["len"] and self._param_path(side[1]) == path and isinstance(oth, int):
                        lens.update({oth - 1, oth, oth + 1})
                    if side[:1] == ["byte"] and self._param_path(side[1]) == path and isinstance(side[2], int):
                        if isinstance(oth, int):
                            bytes_at.setdefault(side[2], set()).update({oth, oth + 1})
                    w = _word_of(side, self._param_path, path)
                    if w is not None:
                        v = ev.ev(oth)
                        if _int(v):
                            words.setdefault(w, set()).update({v - 1, v, v + 1, v + 2})
        acc: list = []
        for g in seq:
            self._terms(g.expr, acc)
        for t in acc:   # a word used as a key: try the indices the action compares it with
            w = _word_of(t, self._param_path, path)
            if w is not None:
                words.setdefault(w, set())
        hashed = any(t[:1] == ["keccak256"] and self._param_path(t[1]) == path for t in acc)

        def enc(bs: bytes):
            return "0x" + bs.hex() if lt["type"] == "bytes" else bs.decode("utf-8", errors="replace")

        name = ".".join(map(str, path))
        for n in sorted(x for x in lens | {0, 1} if x >= 0):
            if n != len(raw):
                out.append((f"len({name})={n}", with_leaf(path, enc(raw[:n] + bytes(max(0, n - len(raw))))), b.env))
        for k in sorted(bytes_at):
            for v in sorted(bytes_at[k] | {0, 255}):
                if 0 <= v < 256 and k < len(raw) and raw[k] != v:
                    out.append((f"{name}[{k}]={v}", with_leaf(path, enc(raw[:k] + bytes([v]) + raw[k + 1:])), b.env))
        for (k, shift), vals in sorted(words.items()):
            nbytes = (256 - shift) // 8
            for v in sorted(vals | {0, 1}):
                if nbytes <= 0 or not 0 <= v < 1 << (8 * nbytes) or k + nbytes > len(raw):
                    continue
                nb = raw[:k] + v.to_bytes(nbytes, "big") + raw[k + nbytes:]
                if nb != raw:
                    out.append((f"word({name},{k})>>{shift}={v}", with_leaf(path, enc(nb)), b.env))
        if hashed and raw:
            nb = raw[:-1] + bytes([raw[-1] ^ 1])
            out.append((f"flip({name})", with_leaf(path, enc(nb)), b.env))
        return out

    # ------------------------------------------------------------ targeting
    def target(self) -> tuple[dict, dict]:
        """({(tid, pos): [Step]} fork steps, {reach id: search log}) for every reach of the document: a candidate is
        kept when every earlier reach of its action (in evaluation order) holds and the reach is false."""
        forks: dict = {}
        log: dict = {}
        for action in sorted(self.view.reaches):
            seq = self.view.reaches[action]
            if not seq:
                continue
            bases = self.bases.get(action) or self.synthesized(action)
            for b in bases:
                b.first, b.decided = first_failing(seq, self.evaluator(b, b.args, b.env))
            for k, r in enumerate(seq):
                log[r.id] = self._target_one(r, k, seq, bases, forks)
        return forks, log

    def _hit(self, k, seq, ev) -> str:
        """"hit" when the candidate violates reach k with every earlier one holding, else "earlier:<i>", "held" or
        "undecided"."""
        f, dec = first_failing(seq[:k + 1], ev)
        if f == k and dec:
            return "hit"
        if f is not None and f < k and dec:
            return f"earlier:{f}"
        if f is None and dec:
            return "held"
        return "undecided"

    def _target_one(self, r, k, seq, bases, forks) -> dict:
        st = {"bases": len(bases), "candidates": 0, "earlier": {}, "held": 0, "undecided": 0, "kept": [],
              "covered": None, "index": k, "atoms": sorted(self.atoms(r.expr)), "possible": []}
        if r.expr is None:
            st["why"] = "no condition term"
            return st
        if r.expr is True or (isinstance(r.expr, int) and r.expr % (1 << 256) != 0):
            st["why"] = "a non-zero constant condition (its negation is unsatisfiable)"
            return st
        for b in bases:
            if b.ok is not None and self._hit(k, seq, self.evaluator(b, b.args, b.env)) == "hit":
                st["covered"] = [b.tid, b.pos]
                return st
        kept, possible = 0, []
        order = [b for b in bases if b.first is None or b.first >= k]
        order += [b for b in bases if b not in order]
        for b in order[:MAX_BASES]:
            cands = ([("as built", b.args, b.env, None)] if b.ok is None else []) + self.mutations(b, r, seq)
            for label, args, env, raw in cands:
                env = self.with_length(b, args, env, raw)
                st["candidates"] += 1
                ev = self.evaluator(b, args, env)
                h = self._hit(k, seq, ev)
                if h == "hit":
                    step = self._fork(b, args, env, {"source": "target", "targets": r.id, "base": [b.tid, b.pos],
                                                     "mutation": label}, raw)
                    if step is not None:
                        forks.setdefault((b.tid, b.pos), []).append(step)
                        st["kept"].append([b.tid, b.pos, label])
                        kept += 1
                        break
                elif h.startswith("earlier:"):
                    i = int(h.split(":")[1])
                    st["earlier"][i] = st["earlier"].get(i, 0) + 1
                elif h == "undecided":
                    st["undecided"] += 1
                    if len(possible) < PER_REACH and first_failing(seq[:k], ev) == (None, True):
                        possible.append((b, args, env, label, raw))
                else:
                    st["held"] += 1
            if kept >= PER_REACH:
                break
        if not kept:   # the evaluator cannot decide the reach: run the candidates on which only it is undecided
            for b, args, env, label, raw in possible:
                step = self._fork(b, args, env, {"source": "target", "targets": r.id, "base": [b.tid, b.pos],
                                                 "mutation": label, "undecided": True}, raw)
                if step is not None:
                    forks.setdefault((b.tid, b.pos), []).append(step)
                    st["possible"].append([b.tid, b.pos, label])
        st["earlier"] = {str(i): n for i, n in sorted(st["earlier"].items())}
        return st

    # ------------------------------------------------------------ suffix traces (two-step paths)
    def writers(self) -> dict[str, list[str]]:
        """family -> the actions whose effects (or planned writes) write it, sorted."""
        out: dict = {}
        for a in sorted(self.view.actions):
            act = self.view.actions[a]
            fams = {e.get("family") for e in act.get("effects") or [] if isinstance(e, dict)}
            fams |= {w.get("family") for w in act.get("writes") or [] if isinstance(w, dict)}
            for f in fams:
                if isinstance(f, str):
                    out.setdefault(f, []).append(a)
        return out

    @staticmethod
    def families(expr) -> set[str]:
        acc: list = []
        Search._terms(expr, acc)
        return {t[1] for t in acc if t[0] == "storage" and len(t) > 1 and isinstance(t[1], str)}

    def suffixes(self, log: dict, base: list[list[Step]]) -> list[list[Step]]:
        """New traces for the reaches the single-step search could not reach or violate: a corpus trace up to a
        successful call of an action that writes a family the reach (or the earlier reach that failed first) reads,
        that call, then a call of the reach's action built from one of its base calls. Up to SUFFIX_PER_REACH per
        reach, each in its own trace (nothing runs after it)."""
        writers = self.writers()
        out: list = []
        for action in sorted(self.view.reaches):
            seq = self.view.reaches[action]
            ab = [b for b in self.bases.get(action) or [] if b.ok is not None]
            if not ab:
                continue
            for k, r in enumerate(seq):
                st = log.get(r.id)
                if st is None or st.get("covered") or st["kept"] or st.get("why"):
                    continue
                fams = self.families(r.expr)
                for i in st["earlier"]:
                    fams |= self.families(seq[int(i)].expr)
                done = []
                ws = sorted({w for f in sorted(fams) for w in writers.get(f, [])})
                st["suffix_writers"] = ws
                for w in ws:
                    for wb in [b for b in self.bases.get(w) or [] if b.ok][:SUFFIX_PER_REACH]:
                        if len(done) >= SUFFIX_PER_REACH:
                            break
                        same = [b for b in ab if b.tid == wb.tid and b.pos > wb.pos]
                        tgt_b = same[0] if same else next((b for b in ab if b.first is None or b.first >= k), ab[0])
                        step = self._fork(tgt_b, tgt_b.args, tgt_b.env, {"source": "target", "targets": r.id,
                                                                          "suffix": [wb.tid, wb.pos, w],
                                                                          "base": [tgt_b.tid, tgt_b.pos]})
                        if step is None:
                            continue
                        step.fork = False
                        step.timestamp = 0
                        prefix = [_copy_step(s, {"source": "target-prefix", "for": r.id})
                                  for s in base[wb.tid][:wb.pos + 1]]
                        out.append(prefix + [step])
                        done.append([wb.tid, wb.pos, w])
                st["suffix"] = done
        return out

    def atoms(self, expr) -> set[str]:
        """The atoms of a term, by kind: param paths, caller, env members, blob hashes, external calls, storage."""
        acc: list = []
        self._terms(expr, acc)
        out = set()
        for t in acc:
            p = self._param_path(t)
            if p:
                out.add("param " + ".".join(map(str, p)))
            elif t[0] in ("caller", "blobhash", "this"):
                out.add(t[0])
            elif t[0] in ("env", "storage", "call", "callok", "immutable") and len(t) > 1 and isinstance(t[1], str):
                out.add(f"{t[0]} {t[1]}")
            elif t[0] in ("unknown", "carried", "exit", "count", "iter", "returned", "mem", "mload"):
                out.add(t[0])
        return out

    def _fork(self, b: Base, args: dict, env: dict, meta: dict, raw: str | None = None) -> Step | None:
        if raw is not None:
            data = raw
        else:
            try:
                data = abi.encode_call(b.fn, args)
            except abi.AbiError:
                return None
        ts = env.get("block.timestamp")
        return Step("call", fork=True, caller=env["caller"], value=int(env.get("msg.value") or 0),
                    timestamp=ts if ts != b.env.get("block.timestamp") else 0, blobs=list(env.get("blobhash") or []),
                    data=data, meta=meta)

    def search_reason(self, reach_id: str, log: dict) -> str:
        """Why the search built no step that violates the reach on the term evaluator (mechanical: counts and atoms,
        never prose about the code)."""
        st = log.get(reach_id)
        if st is None:
            return "no search ran for this reach"
        if st.get("why"):
            return f"the document gives it {st['why']}: the corpus cannot target it"
        parts = [f"stated bound: {st['bases']} base calls of the translation run, {st['candidates']} candidates "
                 f"(single-atom mutations of {', '.join(st['atoms']) or 'no atom'})"]
        if st["earlier"]:
            parts.append("an earlier reach fails first on " + ", ".join(
                f"{n} (reach {i})" for i, n in sorted(st["earlier"].items(), key=lambda kv: int(kv[0]))))
        if st["held"]:
            parts.append(f"it holds on {st['held']}")
        if st["undecided"]:
            parts.append(f"{st['undecided']} undecided by the term evaluator ({len(st['possible'])} of them run)")
        if not st["candidates"]:
            mut = [a for a in st["atoms"] if a.split(" ")[0] in ("param", "caller", "env", "blobhash")]
            parts.append("no atom the corpus changes" if not mut else "no candidate")
        if "suffix_writers" in st and not st.get("suffix"):
            parts.append("no successful corpus call of an action writing its storage atoms"
                         + (f" ({', '.join(st['suffix_writers'])})" if st["suffix_writers"] else " (no writer)"))
        return "; ".join(parts)

    # ------------------------------------------------------------ boundary
    def boundary(self, widths: set[int]) -> dict:
        """{(tid, pos): [Step]}: the first successful call of each action with one ABI leaf at a boundary value."""
        forks: dict = {}
        for action in sorted(self.bases):
            b = next((x for x in self.bases[action] if x.ok), self.bases[action][0])
            for i in b.fn["inputs"]:
                for path, lt in abi.leaves(i, (i["name"],)):
                    cur = abi.get_path(b.args, path)
                    for label, val in _boundary_values(lt, cur, widths, self._lens(action, path)):
                        args = {**b.args, path[0]: abi.set_path(b.args[path[0]], path[1:], val)} if len(path) > 1 \
                            else {**b.args, path[0]: val}
                        st = self._fork(b, args, b.env, {"source": "boundary", "leaf": ".".join(map(str, path)),
                                                         "value": label})
                        if st is not None:
                            forks.setdefault((b.tid, b.pos), []).append(st)
            for st in self.dirty_bools(b):
                forks.setdefault((b.tid, b.pos), []).append(st)
        return forks

    def dirty_bools(self, b: Base) -> list[Step]:
        """The call b again, poked with each DIRTY_BOOL byte at each bool storage location its reaches read (in
        reach order, the other bytes of the slot kept)."""
        ev = self.evaluator(b, b.args, b.env)
        ev.reads = []
        for r in self.view.reaches.get(b.action, []):
            if r.expr is not None:
                ev.ev(r.expr)
        out, seen = [], set()
        for slot, off in ev.reads:
            if (slot, off) in seen:
                continue
            seen.add((slot, off))
            w = b.state.get(slot, 0)
            for v in DIRTY_BOOL:
                st = self._fork(b, b.args, b.env, {"source": "boundary", "leaf": f"storage:{hex(slot)}+{off}",
                                                   "value": hex(v)})
                if st is not None:
                    st.pokes = [(slot, (w & ~(0xFF << (8 * off)) & MASK) | (v << (8 * off)))]
                    out.append(st)
        return out

    def _lens(self, action: str, path: tuple) -> set[int]:
        out = set()
        for g in self.view.reaches.get(action, []):
            for c in self.comparisons(g.expr):
                for side, oth in ((c[1], c[2]), (c[2], c[1])):
                    if isinstance(side, list) and side[:1] == ["len"] and self._param_path(side[1]) == path \
                            and isinstance(oth, int):
                        out.update({oth - 1, oth, oth + 1})
        return {x for x in out if x >= 0}


def reason_function(search: Search | None, log: dict, outcome_text):
    """reason_of(reach, steps that targeted it) for holon.replay_fragments.guard_coverage: what the targeting steps
    did on both sides when some ran, else why the search built none (Search.search_reason)."""
    def reason_of(r, steps) -> str:
        if r.expr is True or (isinstance(r.expr, int) and not isinstance(r.expr, bool) and r.expr % (1 << 256) != 0):
            return ("its condition in the document is a non-zero constant: its negation is unsatisfiable, so no input "
                    "reverts there (the reach cannot revert)")
        if steps:
            shown = "; ".join(outcome_text(c) for c in steps[:3])
            more = f" (and {len(steps) - 3} more)" if len(steps) > 3 else ""
            return (f"{len(steps)} corpus steps targeted it, none ending there on the model with the real contract "
                    f"reverting with the same revert key: {shown}{more}")
        st = log.get(r.id) or {}
        if st.get("covered"):
            return (f"the term evaluator finds it the first false reach of the corpus step at trace {st['covered'][0]} "
                    f"step {st['covered'][1]}, but no step ended there on the model with the real contract reverting "
                    "with the same revert key")
        return search.search_reason(r.id, log) if search is not None else "no targeting search ran"
    return reason_of


def _copy_step(s: Step, meta: dict) -> Step:
    return Step(s.kind, fork=s.fork, row=list(s.row), caller=s.caller, value=s.value, timestamp=s.timestamp,
                blobs=list(s.blobs), to=s.to, data=s.data, meta=dict(meta), pokes=list(s.pokes))


def _word_of(t, param_path, path):
    """(offset, shift) when t is ["word", P, k] or [">>", ["word", P, k], s] with P the parameter path, else None."""
    if not isinstance(t, list) or not t:
        return None
    if t[0] == "word" and len(t) == 3 and param_path(t[1]) == path and isinstance(t[2], int):
        return (t[2], 0)
    if t[0] == ">>" and len(t) == 3 and isinstance(t[1], list) and t[1][:1] == ["word"] and isinstance(t[2], int) \
            and len(t[1]) == 3 and param_path(t[1][1]) == path and isinstance(t[1][2], int):
        return (t[1][2], t[2])
    return None


def _uniq(xs):
    out, seen = [], set()
    for x in xs:
        if _int(x) and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _boundary_values(lt: dict, cur, widths: set[int], lens: set[int]) -> list:
    ty = lt["type"]
    if ty in ("bytes", "string"):
        raw = bytes.fromhex(cur[2:]) if ty == "bytes" else cur.encode()
        out = []
        for n in sorted(lens | {0, 1}):
            if n != len(raw):
                nb = raw[:n] + bytes(max(0, n - len(raw)))
                out.append((f"len={n}", "0x" + nb.hex() if ty == "bytes" else nb.decode("utf-8", errors="replace")))
        return out
    if abi._array(ty) or ty == "tuple":
        return []
    if ty == "bool":
        return [(str(not cur), not cur)]
    bits = _bits(ty)
    vals = [0, 1, (1 << bits) - 1]
    for w in sorted(widths | {bits}):
        if w <= bits:
            vals += [(1 << w) - 1, 1 << w]
    vals.append(MASK)
    out = []
    for v in _uniq(vals):
        av = _abi_value(lt, v)
        if av is not None and av != cur:
            out.append((hex(v), av))
    return out


def insert_forks(traces: list[list[Step]], *fork_maps: dict) -> list[list[Step]]:
    """The traces with every fork step placed before the step at its position (forks at one position in map order,
    then insertion order; an identical call at the same position runs once, its metas merged)."""
    at: dict = {}
    for fm in fork_maps:
        for key in sorted(fm):
            for st in fm[key]:
                lst = at.setdefault(key, [])
                dup = next((x for x in lst if x.key() == st.key()), None)
                if dup is not None:
                    dup.meta.setdefault("also", []).append(st.meta)
                else:
                    lst.append(st)
    out = []
    for tid, steps in enumerate(traces):
        new = []
        for pos, s in enumerate(steps):
            new += at.get((tid, pos), [])
            new.append(s)
        new += at.get((tid, len(steps)), [])
        out.append(new)
    return out
