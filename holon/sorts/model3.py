"""The M3 model of a transitions document (BUILD_PLAN I30; whitepaper §7.8, §8.3, Thm 6.18, Prop 6.19; the contract is
the docstring of tests_m3/test_sort_types.py, rules N1-N10, G1-G4 and the typed model section).

  python -m holon model --milestone M [--root DIR] [--sidecar PATH] [--untyped] --out DIR

writes DIR/<model>.bend and DIR/<model>.init.json for every document of the milestone's typed-sorts sidecar
(holon.sorts.typed_sidecar). The model is the document's program compiled exactly as holon.extracted_eval runs it
(the I20 evaluator of record), with what the I20 model left to its environment computed:

  words      W{l0..l7}, eight U32 limbs (holon.sorts.prelude3): Bend's checker and the BendTT kernel evaluate a
             concrete step in time polynomial in the width (N8)
  storage    the contract's raw slots (HSt), read and written at the compiler's slots and offsets with its packing;
             a mapping's slot is the keccak256 of the key and the slot, through the law's keccak256 table
  hashes     keccak256 and sha256 are parameters (List<&2, HKB> tables), one table for the whole trace (I12)
  loops      every loop record runs (structural recursion on a fuel of FUEL iterations): its checks, carried names,
             writes, events and exits; memory regions and their mloop / when writes are built byte by byte
  env        only what A-env makes free: msg, block and tx members, blob hashes, the answers of external calls
             (matched by receiver and calldata), the code and balance of addresses, the deployment's immutables
  actions    per action a: run_<a> (one evaluation: HOut{code, revert data, post-state, logs, touched slots}),
             chk_<a> (0 when every check holds, k + 1 when check k, holon.machine's order, is the first to fail),
             post_<a>, logs_<a>, step_<a> (the post-state when chk_<a> is 0, else the state), and HAct / step

The typed model (N1-N7, the default from M3 on) adds the sort section of the frozen assignment: one nominal type per
refined sort (T_<sort>{p: W}; a signed sort T_<S>{neg, p}), typed operations only where holon.sorts.grammar.affine
admits them, realize_<signed>(d) -> Maybe<unsigned> at every sign site (a checked site's realization check reverts with
Panic 0x11 on None; the real code then uses the machine value), and below GHOST_MARKER the ghost store of the generated
companions (rule G1-G3: tg of every write of a union family, at the same key, in the action's ghost step), Reach from
the deployment (R0) by RStep over any action with its arguments and environment, and per I30 law coerce_<x> and
chit_<x>. --untyped writes the same machine without the sort section (no nominal type, typed operation, coercion,
companion or ghost store) plus I15's site instrumentation of the term-size ratio site (holon termsize's baseline).

Nothing here names a target: every name comes from the document, its compiler information and the assignment.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import extracted_eval as EV
from ..machine import Check, Event, ExtractedModel, Loop, ModelError, MStore, Write, canonical
from ..machine_bend import bname, comment
from . import grammar as G
from .prelude3 import FUEL, PRELUDE, SENTINEL

GHOST_MARKER = "# ---- ghost: SORT coercions (holon.rules.sort)"
SITE_MARKER = "# ---- ghost: SORT-site instrumentation (holon.sorts.sites)"
MODEL3_VERSION = "holon-model-m3/0.1"
FUEL_CODE = 4294967295       # a step whose loop ran out of fuel (more than FUEL - 1 iterations): not a check
MASK = (1 << 256) - 1
PANIC_SEL = bytes.fromhex("4e487b71")


class GenError(ModelError):
    """A construct the M3 generator cannot compile (named; never left to the environment)."""


# ------------------------------------------------------------------------------------------------ literals
def wlit(x: int) -> str:
    x &= MASK
    return "W{" + ", ".join(str((x >> (32 * i)) & 0xFFFFFFFF) for i in range(8)) + "}"


def blit(bs) -> str:
    bs = list(bs)
    return ("[" + ", ".join(str(int(b)) for b in bs) + "]") if bs else "Nil{}"


def natlit(n: int) -> str:
    return f"{int(n)}n"


def tname(sort: str) -> str:
    return "T_" + (re.sub(r"[^A-Za-z0-9]+", "_", sort).strip("_") or "x")


def sname(sort: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", sort).strip("_")


def to_int(v) -> int:
    return EV.to_int(v)


# ------------------------------------------------------------------------------------------------ the scope
@dataclass
class LoopInfo:
    j: int
    loop: Loop
    carried: list            # [(name, label, kind)]
    exits_extra: list        # [(name, label, kind)] exit names that are not carried
    returns: int


@dataclass
class Scope:
    action: str
    x: str = "x"
    subst: dict = field(default_factory=dict)     # canonical term -> (code, kind)
    loops: dict = field(default_factory=dict)     # (span, r) -> LoopInfo
    src: object = None                            # the src of the record under compilation (error messages)


class StoragePath:
    """A storage location under compilation: the view it reads (HSt code), its family, and the accessors so far."""

    def __init__(self, view: str, family: str, accessors: list, var: str):
        self.view, self.family, self.accessors, self.var = view, family, list(accessors), var

    def extend(self, kind: str, code, ckind: str, var: str) -> "StoragePath":
        return StoragePath(self.view, self.family, self.accessors + [(kind, code, ckind)], var)


# ------------------------------------------------------------------------------------------------ the generator
class Gen:
    def __init__(self, m: ExtractedModel, *, typed: bool, sorts: dict | None = None, seeds: dict | None = None,
                 init_storage: dict | None = None, hashes: list | None = None, basis=None, site: dict | None = None,
                 binding: str | None = None):
        self.m = m
        self.typed = typed
        self.sorts = dict(sorts or {})
        self.seeds = seeds or {}
        self.init = {int(k, 16) if isinstance(k, str) else int(k): to_int(v) for k, v in (init_storage or {}).items()}
        self.hashes = list(hashes or ["keccak256"])
        self.basis = basis
        self.site = site
        self.binding = binding
        self.defs: list[str] = []
        self.names: set = set()
        self.records: dict = {}        # struct param record -> [(field, bend type, abi param)]
        self.env_fields: list = []     # (field, bend type, key)
        self.shifts: set = set()
        self.masks: set = set()
        self.ml_cache: dict = {}
        self.uid = 0
        self.types_used: dict = {}     # sort -> Bend type (typed)
        self.ops: dict = {}            # op name -> {"name", "op", "args", "result"}
        self.coercions: dict = {}      # name -> {"name", "kind", "from", "to"}
        self.checks: dict = {}         # action -> [Check] in holon.machine's order
        self.ctx_fields: dict = {}     # action -> [(field, bend type)]
        if typed:
            from .extracted import Walker
            self.seedw = Walker("_", {"actions": []}, self.seeds)
        else:
            self.seedw = None

    # ---------------------------------------------------------- bookkeeping
    def fresh(self, base: str) -> str:
        self.uid += 1
        return f"{base}_{self.uid}"

    def add(self, text: str) -> None:
        for n in re.findall(r"(?m)^(?:def|type)\s+([\w.]+)", text):
            if n in self.names:
                raise GenError(f"the generated model would define {n} twice")
            self.names.add(n)
        self.defs.append(text.rstrip("\n") + "\n")

    def env_field(self, key: str, ty: str = "W") -> str:
        f = "e_" + bname(key)
        if f not in [x[0] for x in self.env_fields]:
            self.env_fields.append((f, ty, key))
        return f

    def ge(self, key: str, sc: Scope, ty: str = "W") -> str:
        f = self.env_field(key, ty)
        return f"ge_{f}({self.gx(sc, 'en')})"

    def gx(self, sc: Scope, fld: str) -> str:
        return f"gx_{bname(sc.action)}_{fld}({sc.x})"

    # ---------------------------------------------------------- shifts and masks (on demand)
    def shr(self, k: int) -> str:
        if k >= 256:
            return None
        self.shifts.add(("r", k))
        return f"w_shr_{k}"

    def shl(self, k: int) -> str:
        if k >= 256:
            return None
        self.shifts.add(("l", k))
        return f"w_shl_{k}"

    def shift_defs(self) -> list[str]:
        out = []
        for d, k in sorted(self.shifts):
            q, r = divmod(k, 32)
            limbs = []
            for i in range(8):
                if d == "r":
                    src, nxt = i + q, i + q + 1
                    a = f"a{src}" if src < 8 else None
                    b = f"a{nxt}" if nxt < 8 else None
                    if r == 0:
                        limbs.append(a or "0")
                    else:
                        parts = []
                        if a:
                            parts.append(f"U32.shrn({a}, {r}n)")
                        if b:
                            parts.append(f"U32.shln({b}, {32 - r}n)")
                        limbs.append(parts[0] if len(parts) == 1 else (f"U32.or({parts[0]}, {parts[1]})" if parts else "0"))
                else:
                    src, prv = i - q, i - q - 1
                    a = f"a{src}" if 0 <= src < 8 else None
                    b = f"a{prv}" if 0 <= prv < 8 else None
                    if r == 0:
                        limbs.append(a or "0")
                    else:
                        parts = []
                        if a:
                            parts.append(f"U32.shln({a}, {r}n)")
                        if b:
                            parts.append(f"U32.shrn({b}, {32 - r}n)")
                        limbs.append(parts[0] if len(parts) == 1 else (f"U32.or({parts[0]}, {parts[1]})" if parts else "0"))
            pat = ", ".join(f"+a{i}" for i in range(8))
            out.append(f"def w_sh{d}_{k}(a: W) -> W:\n  match a:\n    case W{{{pat}}}:\n      W{{{', '.join(limbs)}}}\n")
        return out

    def mask(self, bits: int) -> str:
        """A W literal of the low `bits` bits."""
        return wlit((1 << bits) - 1)

    # ---------------------------------------------------------- types of the document
    def arg_type(self, p: dict) -> str:
        t = p.get("type", "")
        m = re.fullmatch(r"(.*)\[(\d*)\]", t)
        if m:
            return f"List<&2, {self.arg_type(dict(p, type=m.group(1)))}>"
        if t == "tuple":
            name = "S_" + bname(p.get("struct") or "tuple")
            if name not in self.records:
                self.records[name] = []
                self.records[name] = [(bname(c["name"]), self.arg_type(c), c) for c in p.get("components") or []]
            return name
        if t in ("bytes", "string"):
            return "List<&2, U32>"
        return "W"

    @staticmethod
    def kind_of_type(ty: str) -> str:
        if ty == "W":
            return "w"
        if ty == "List<&2, U32>":
            return "b"
        if ty.startswith("List<&2, "):
            return "l:" + ty[len("List<&2, "):-1]
        return "r:" + ty

    # ---------------------------------------------------------- sorts (typed)
    def refined(self, sort: str | None) -> bool:
        if not self.typed or sort is None:
            return False
        if sort in ("Nat (unrefined)", "Bool") or sort.startswith("Mach("):
            return False
        return True

    def T(self, sort: str) -> str:
        """The nominal type of a sort (registered)."""
        n = tname(sort)
        self.types_used[sort] = n
        s = G.parse(sort)
        if s.label:
            self.T(G.render(G.base(s)))
            self.coercions[f"erase_{sname(sort)}"] = {"name": f"erase_{sname(sort)}", "kind": "erase",
                                                      "from": sort, "to": G.render(G.base(s))}
        if s.head == "Union":
            for mm in s.members:
                self.T(G.render(mm))
        if G.is_signed(s):
            self.T(G.render(G.unsigned(s)))
        return n

    def wrap(self, raw: str, sort: str) -> tuple[str, str]:
        return f"{self.T(sort)}{{{raw}}}" if not G.is_signed(G.parse(sort)) else \
            f"{self.T(sort)}{{w_lt({raw}, w0()), {raw}}}", "t:" + sort

    def var_sort(self, var: str | None) -> str | None:
        if var is None:
            return None
        return self.sorts.get(var)

    def leaf(self, raw: str, var: str | None, term=None) -> tuple[str, str]:
        """A word leaf: typed when its variable's frozen sort is refined (or a seed gives the term one member)."""
        if self.typed:
            s = self.var_sort(var)
            if not self.refined(s) and term is not None and self.seedw is not None:
                ms = sorted({x for _i, x in self.seedw.term_seed(term) + self.seedw.digest_seed(term)})
                s = ms[0] if len(ms) == 1 else None
            if self.refined(s):
                return self.wrap(raw, s)
        return raw, "w"

    # ---------------------------------------------------------- conversions
    def to_w(self, code: str, kind: str) -> str:
        if kind == "w":
            return code
        if kind == "bool":
            return f"w_b({code})"
        if kind.startswith("t:"):
            s = kind[2:]
            if G.is_signed(G.parse(s)):
                return f"pay_{tname(s)}({code})"
            return f"pay_{tname(s)}({code})"
        if kind == "a":
            return f"b_word(a_ret({code}), 0n)"
        raise GenError(f"a {kind} value used as a word")

    def to_bool(self, code: str, kind: str) -> str:
        if kind == "bool":
            return code
        return f"w_nz({self.to_w(code, kind)})"

    def to_bytes(self, code: str, kind: str) -> str:
        if kind == "b":
            return code
        return f"b_of_w({self.to_w(code, kind)})"

    def bend_type(self, kind: str) -> str:
        if kind == "w":
            return "W"
        if kind == "bool":
            return "Bool"
        if kind == "b":
            return "List<&2, U32>"
        if kind.startswith("t:"):
            return tname(kind[2:])
        if kind.startswith("v:"):
            return "HSt"
        if kind.startswith("r:"):
            return kind[2:]
        if kind.startswith("l:"):
            return f"List<&2, {kind[2:]}>"
        if kind == "a":
            return "HAns"
        raise GenError(f"no Bend type for a {kind} value")

    # ---------------------------------------------------------- terms
    def nat(self, t, sc: Scope) -> str:
        """A term used as a count, offset or index (its low 32 bits)."""
        if isinstance(t, int) and not isinstance(t, bool):
            return natlit(t)
        c, k = self.value(t, sc)
        return f"n_of_w({self.to_w(c, k)})"

    def w(self, t, sc: Scope) -> str:
        c, k = self.value(t, sc)
        return self.to_w(c, k)

    def b(self, t, sc: Scope) -> str:
        c, k = self.value(t, sc)
        return self.to_bytes(c, k)

    def cond(self, t, sc: Scope) -> str:
        if t in (1, True):
            return "True{}"
        if t in (0, False):
            return "False{}"
        c, k = self.value(t, sc)
        return self.to_bool(c, k)

    def tx(self, t, sc: Scope):
        """(Bend code, kind) of a term (kinds: w, bool, b, t:<sort>, v:<family> (a storage view), r:<record>,
        l:<elem>, a (an external call's answer), p (a storage path under compilation: a StoragePath object))."""
        if isinstance(t, bool):
            return ("w_u(1)" if t else "w0()"), "w"
        if isinstance(t, int):
            return wlit(t), "w"
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            raise GenError(f"{sc.action}: not a term: {str(t)[:120]}")
        key = canonical(t)
        if key in sc.subst:
            return sc.subst[key]
        h = t[0]
        f = getattr(self, "t_" + _NAMES.get(h, h.replace(".", "_")), None)
        if f is None:
            raise GenError(f"{sc.action}: term {h!r} is outside the M3 generator's language: {key[:160]}")
        out = f(t, sc)
        if out[1] == "p":
            return out
        return out

    def value(self, t, sc: Scope):
        """A term's value with a storage path read (an elementary value) or kept as a view (a container)."""
        c, k = self.tx(t, sc)
        if k == "p":
            return self.read_path(c, sc)
        return c, k

    # leaves
    def t_param(self, t, sc):
        ps = {p["name"]: p for p in self.m.params(sc.action) or []}
        p = ps.get(t[1])
        if p is None:
            raise GenError(f"{sc.action}: parameter {t[1]} has no ABI type")
        ty = self.arg_type(p)
        code = f"ga_{bname(sc.action)}_{bname(t[1])}({self.gx(sc, 'ar')})"
        k = self.kind_of_type(ty)
        if k == "w":
            return self.leaf(code, f"{sc.action}.{t[1]}", t)
        return code, k

    def t_env(self, t, sc):
        return self.leaf(self.ge(t[1], sc), f"env:{t[1]}", t)

    def t_caller(self, t, sc):
        return self.leaf(self.ge("caller", sc), "env:caller", t)

    def t_this(self, t, sc):
        return self.leaf(self.ge("this", sc), "env:this", t)

    def t_immutable(self, t, sc):
        return self.ge(f"immutable.{t[1]}", sc), "w"

    def t_blobhash(self, t, sc):
        f = self.env_field("blobs", "List<&2, W>")
        return self.leaf(f"w_nth(ge_{f}({self.gx(sc, 'en')}), {self.nat(t[1], sc)})", None, t)

    def t_code(self, t, sc):
        f = self.env_field("code", "List<&2, KB>")
        return f"kb_get(ge_{f}({self.gx(sc, 'en')}), {self.w(t[1], sc)})", "b"

    def t_balance(self, t, sc):
        f = self.env_field("balance", "List<&2, KW>")
        return f"kw_get(ge_{f}({self.gx(sc, 'en')}), {self.w(t[1], sc)})", "w"

    def t_str(self, t, sc):
        return blit(bytes.fromhex(t[1] or "")), "b"

    def t_sload(self, t, sc):
        return f"sload({self.gx(sc, 'st')}, {self.w(t[1], sc)})", "w"

    def t_ptr(self, t, sc):
        return self.w(t[2], sc), "w"     # a memory pointer: its offset (never compared with storage)

    # loops' symbols
    def loop_of(self, t, sc, tag_len: int) -> LoopInfo:
        span = t[1]
        rest = t[tag_len:]
        r = rest[0] if rest and isinstance(rest[0], int) and not isinstance(rest[0], bool) else 0
        li = sc.loops.get((span, r))
        if li is None:
            raise GenError(f"{sc.action}: {t[0]} of loop {span}#{r} outside the loop's scope")
        return li

    def t_iter(self, t, sc):
        li = self.loop_of(t, sc, 2)
        return self.leaf(self.gx(sc, f"it{li.j}"), f"loop:{li.loop.src}{'#' + str(li.loop.reach) if li.loop.reach else ''}:iter")

    def t_count(self, t, sc):
        li = self.loop_of(t, sc, 2)
        return self.gx(sc, f"cn{li.j}"), "w"

    def t_carried(self, t, sc):
        li = self.loop_of(t, sc, 3)
        name = t[2]
        span = f"{li.loop.src}{'#' + str(li.loop.reach) if li.loop.reach else ''}"
        for i, (n, lab, kind) in enumerate(li.carried):
            if n == name:
                code = self.gx(sc, f"c{li.j}_{i}")
                return self.leaf(code, f"loop:{span}:{lab}") if kind == "w" else (code, kind)
        for i, (n, lab, kind) in enumerate(li.exits_extra):
            if n == name:
                code = self.gx(sc, f"x{li.j}_{i}")
                return self.leaf(code, f"loop:{span}:{lab}") if kind == "w" else (code, kind)
        raise GenError(f"{sc.action}: {t[0]} {canonical(name)} is not a name of loop {li.loop.src}")

    t_exit = t_carried

    def t_returned(self, t, sc):
        li = self.loop_of(t, sc, 3)
        return f"w_b(w_eq({self.gx(sc, f'rt{li.j}')}, {wlit(int(t[2]) + 1)}))", "w"

    # storage
    def fam_type(self, family: str) -> tuple[int, int, str]:
        f = self.m.family(family)
        return f.slot, f.offset, f.type

    def t_storage(self, t, sc):
        fam = t[1]
        self.m.family(fam)
        return StoragePath(self.gx(sc, "st"), fam, [], fam), "p"

    def path_of(self, t, sc):
        c, k = self.tx(t, sc)
        if k == "p":
            return c
        if k.startswith("v:"):
            return StoragePath(c, k[2:], [], k[2:])
        return None

    def t_map(self, t, sc):
        base = self.path_of(t[1], sc)
        if base is None:
            raise GenError(f"{sc.action}: a map access into a value that is not storage")
        kc, kk = self.value(t[2], sc)
        return base.extend("map", kc, kk, base.var), "p"

    def t_index(self, t, sc):
        c, k = self.tx(t[1], sc)
        if k == "p" or k.startswith("v:"):
            base = c if k == "p" else StoragePath(c, k[2:], [], k[2:])
            ic, ik = self.value(t[2], sc)
            return base.extend("index", ic, ik, base.var), "p"
        if k == "b":
            return f"w_u(b_at({c}, {self.nat(t[2], sc)}))", "w"
        if k.startswith("l:"):
            el = k[2:]
            if el == "W":
                return f"w_nth({c}, {self.nat(t[2], sc)})", "w"
            raise GenError(f"{sc.action}: an index into a list of {el}")
        raise GenError(f"{sc.action}: an index into a {k} value")

    def t_member(self, t, sc):
        c, k = self.tx(t[1], sc)
        if k == "p" or k.startswith("v:"):
            base = c if k == "p" else StoragePath(c, k[2:], [], k[2:])
            return base.extend("member", t[2], "name", f"{base.var}.{t[2]}"), "p"
        if k.startswith("r:"):
            rec = k[2:]
            fs = {f: (ty, p) for f, ty, p in self.records.get(rec) or []}
            fld = bname(t[2])
            if fld not in fs:
                raise GenError(f"{sc.action}: no member {t[2]} in {rec}")
            ty = fs[fld][0]
            code = f"g_{rec}_{fld}({c})"
            kk = self.kind_of_type(ty)
            if kk == "w":
                pv = _param_var(t, sc.action)
                return self.leaf(code, pv, t)
            return code, kk
        raise GenError(f"{sc.action}: member {t[2]} of a {k} value")

    def key_bytes(self, kc: str, kk: str, kt: dict) -> str:
        """The bytes a mapping key is hashed as (holon.extracted_eval.Eval.locate / word_for_key)."""
        if kt.get("encoding") == "inplace":
            v = self.to_w(kc, kk)
            n = int(kt.get("numberOfBytes", 32))
            lab = str(kt.get("label", ""))
            if not EV._BYTESN.match(lab) and n < 32 and not lab.startswith("int"):
                v = f"w_and({v}, {self.mask(8 * n)})"
            return f"b_of_w({v})"
        return self.to_bytes(kc, kk)

    def locate(self, p: StoragePath, sc: Scope) -> tuple[str, int, str, bool]:
        """(slot code, offset, type id, whether the slot is a literal) of a storage path (Eval.locate)."""
        slot, off, tid = self.fam_type(p.family)
        code, lit = wlit(slot), slot
        for kind, x, xk in p.accessors:
            t = self.m.type_of(tid)
            enc = t.get("encoding")
            if kind == "map":
                if enc != "mapping":
                    raise GenError(f"{sc.action}: {p.family}: a map access into {t.get('label')}")
                kt = self.m.type_of(t["key"])
                kb = self.key_bytes(x, xk, kt)
                code = f"h_get({self.gx(sc, 'kh')}, List.append(&2, U32, {kb}, b_of_w({code})))"
                lit = None
                off, tid = 0, t["value"]
            elif kind == "member":
                mm = next((y for y in t.get("members") or [] if y["label"] == x), None)
                if mm is None:
                    raise GenError(f"{sc.action}: {p.family}: no member {x} in {t.get('label')}")
                if lit is not None:
                    lit = (lit + int(mm["slot"])) & MASK
                    code = wlit(lit)
                elif int(mm["slot"]):
                    code = f"w_add({code}, {wlit(int(mm['slot']))})"
                off, tid = int(mm["offset"]), mm["type"]
            elif kind == "index":
                bt = self.m.type_of(t["base"]) if "base" in t else None
                if bt is None or enc == "dynamic_array" or int(bt["numberOfBytes"]) != 32:
                    raise GenError(f"{sc.action}: {p.family}: an index into {t.get('label')} (only static arrays of "
                                   "words are compiled)")
                iv = self.to_w(x, xk)
                code = f"w_add({code}, {iv})"
                lit = None
                off, tid = 0, t["base"]
        return code, off, tid, lit is not None

    def read_word(self, view: str, slot: str, off: int, tid: str) -> str:
        t = self.m.type_of(tid)
        if t.get("encoding") != "inplace" or "members" in t or "base" in t:
            raise GenError(f"a value read of a {t.get('label')} (not an elementary value)")
        n = int(t["numberOfBytes"])
        wcode = f"sload({view}, {slot})"
        if off:
            wcode = f"{self.shr(8 * off)}({wcode})"
        if n < 32:
            wcode = f"w_and({wcode}, {self.mask(8 * n)})"
            if EV._BYTESN.match(str(t.get("label", ""))):
                wcode = f"{self.shl(256 - 8 * n)}({wcode})"
        return wcode

    def read_path(self, p: StoragePath, sc: Scope):
        slot, off, tid, _lit = self.locate(p, sc)
        t = self.m.type_of(tid)
        if t.get("encoding") == "inplace" and "members" not in t and "base" not in t:
            return self.leaf(self.read_word(p.view, slot, off, tid), p.var)
        if not p.accessors:
            return p.view, "v:" + p.family
        raise GenError(f"{sc.action}: {p.family}: a read of a whole {t.get('label')}")

    def write_word(self, view: str, slot: str, off: int, tid: str, v: str) -> str:
        """sstore of value v at (slot, off) of type tid into view, with the compiler's packing."""
        t = self.m.type_of(tid)
        n = int(t["numberOfBytes"])
        if n == 32 and off == 0:
            return f"sstore({view}, {slot}, {v})"
        vv = v
        if EV._BYTESN.match(str(t.get("label", ""))) and n < 32:
            vv = f"{self.shr(256 - 8 * n)}({vv})"
        vv = f"w_and({vv}, {self.mask(8 * n)})"
        if off:
            vv = f"{self.shl(8 * off)}({vv})"
        mk = (((1 << (8 * n)) - 1) << (8 * off)) & MASK
        keep = f"w_and(sload({view}, {slot}), {wlit(MASK ^ mk)})"
        return f"sstore({view}, {slot}, w_or({keep}, {vv}))"

    def t_store(self, t, sc):
        if not t[2]:
            return self.value(t[3], sc)
        base = self.path_of(t[1], sc)
        if base is None:
            raise GenError(f"{sc.action}: a store into a value that is not storage")
        p = base
        for acc in t[2]:
            kind, x = acc[0], acc[1]
            if kind == "member":
                p = p.extend("member", x, "name", f"{p.var}.{x}")
            else:
                xc, xk = self.value(x, sc)
                p = p.extend(kind, xc, xk, p.var)
        vc, vk = ("", "z0") if t[3] in (0, False) else self.value(t[3], sc)
        view = self.write_path(p.view, p, vc, vk, sc)
        return view, "v:" + base.family

    def write_path(self, view: str, p: StoragePath, vc: str, vk: str, sc: Scope, slot_lets: dict | None = None) -> str:
        slot, off, tid, _lit = self.locate(p, sc)
        t = self.m.type_of(tid)
        if t.get("encoding") == "inplace" and "members" in t:
            # a struct value: a literal (vk "z:<json>") or 0 (delete)
            if vk == "z0":
                vals = {}
            elif vk.startswith("z:"):
                vals = json.loads(vk[2:])
            else:
                raise GenError(f"{sc.action}: a struct write of a {vk} value")
            out = view
            for mm in t["members"]:
                mslot = f"w_add({slot}, {wlit(int(mm['slot']))})" if int(mm["slot"]) else slot
                code = vals.get(mm["label"], "w0()")
                out = self.write_word(out, mslot, int(mm["offset"]), mm["type"], code)
            return out
        if vk == "z0":
            vc, vk = "w0()", "w"
        return self.write_word(view, slot, off, tid, self.to_w(vc, vk))

    def path_slots(self, p: StoragePath, vk: str, sc: Scope) -> list[str]:
        slot, off, tid, _lit = self.locate(p, sc)
        t = self.m.type_of(tid)
        if t.get("encoding") == "inplace" and "members" in t:
            return [f"w_add({slot}, {wlit(int(mm['slot']))})" if int(mm["slot"]) else slot for mm in t["members"]]
        return [slot]

    # arithmetic
    def t_add(self, t, sc):
        return self.arith("+", t, sc)

    def t_sub(self, t, sc):
        return self.arith("-", t, sc)

    def affine_operands(self, op: str, t, a, b):
        """(code, sort) of both operands of a typed + or -, or None: a literal operand carries no sort (holon.sorts.
        extracted: a fresh auxiliary), so it takes the sort of its pair that keeps the other operand's sort (an index
        plus a count, a time plus a duration), else the first its pair admits."""
        if not self.typed:
            return None
        (ac, ak), (bc, bk) = a, b
        ta = self.typed_operand(ac, ak, None, "")
        tb = self.typed_operand(bc, bk, None, "")
        if ta is not None and tb is None and _is_lit(t[2]):
            tb = self.lit_operand(op, ta[1], t[2], first=False)
        elif tb is not None and ta is None and _is_lit(t[1]):
            ta = self.lit_operand(op, tb[1], t[1], first=True)
        return (ta, tb) if ta is not None and tb is not None else None

    def lit_operand(self, op: str, other: str, lit: int, first: bool):
        base = self.base_sort(other)
        try:
            fam = G.family(G.parse(base))
        except G.SortError:
            return None
        pr = G.pair_role(fam) if fam else None
        if pr is None:
            return None
        roles = ("S",) if pr[0].startswith("S:") else ("G", "P")
        cands = []
        for r in roles:
            c = G.render(G.parse(G.family_of(pr[0], r)))
            res = G.affine(op, c, base) if first else G.affine(op, base, c)
            if res is not None:
                cands.append((res != base, c))
        if not cands:
            return None
        c = sorted(cands)[0][1]
        return f"{self.T(c)}{{{wlit(lit)}}}", c

    def arith(self, op: str, t, sc):
        (ac, ak), (bc, bk) = self.value(t[1], sc), self.value(t[2], sc)
        tt = self.affine_operands(op, t, (ac, ak), (bc, bk))
        if tt is not None:
            return self.typed_affine(op, tt[0], tt[1], sc)
        ac2, ak2 = self.unsigned_kind(ac, ak)
        bc2, bk2 = self.unsigned_kind(bc, bk)
        a, b = self.to_w(ac2, ak2), self.to_w(bc2, bk2)
        return (f"w_add({a}, {b})" if op == "+" else f"w_sub({a}, {b})"), "w"

    def unsigned_kind(self, c: str, k: str):
        """A signed typed value consumed by anything but its realization check: its machine value (R1)."""
        if k.startswith("t:") and G.is_signed(G.parse(k[2:])):
            u = G.render(G.unsigned(G.parse(k[2:])))
            return f"wrap_{tname(k[2:])}({c})", "t:" + u
        return c, k

    def typed_operand(self, c: str, k: str, term, other_kind: str):
        """(code, sort) of an operand of a typed operation: typed, or a literal adopting the other's sort."""
        if not self.typed:
            return None
        if k.startswith("t:"):
            c2, k2 = self.unsigned_kind(c, k)
            return c2, k2[2:]
        if isinstance(term, int) and not isinstance(term, bool) and other_kind.startswith("t:"):
            s = G.render(G.unsigned(G.parse(other_kind[2:])))
            return f"{self.T(s)}{{{wlit(term)}}}", s
        return None

    def base_sort(self, s: str) -> str:
        return G.render(G.base(G.parse(s)))

    def erase(self, c: str, s: str) -> tuple[str, str]:
        b = self.base_sort(s)
        if b != s:
            self.T(s)
            return f"erase_{sname(s)}({c})", b
        return c, s

    def typed_affine(self, op: str, a, b, sc):
        (ac, asort), (bc, bsort) = a, b
        ac, asort = self.erase(ac, asort)
        bc, bsort = self.erase(bc, bsort)
        r = G.affine(op, asort, bsort)
        if r is None:
            raise GenError(f"{sc.action}: {asort} {op} {bsort} is ill-sorted (no typed operation)")
        name = f"{'add' if op == '+' else 'sub'}_{sname(asort)}_{sname(bsort)}"
        self.ops[name] = {"name": name, "op": op, "args": [asort, bsort], "result": r}
        self.T(asort), self.T(bsort), self.T(r)
        return f"{name}({ac}, {bc})", "t:" + r

    def t_mul(self, t, sc):
        a, b = self.w(t[1], sc), self.w(t[2], sc)
        for x, y in ((t[1], b), (t[2], a)):
            if isinstance(x, int) and not isinstance(x, bool) and 0 < x < (1 << 32):
                if x & (x - 1) == 0:
                    return f"{self.shl(x.bit_length() - 1)}({y})", "w"
                return f"w_mul_small({y}, {x})", "w"
        return f"w_mul({a}, {b})", "w"

    def t_div(self, t, sc):
        a = self.w(t[1], sc)
        d = t[2]
        if isinstance(d, int) and not isinstance(d, bool) and 0 < d < (1 << 16):
            return f"w_div_small({a}, {d})", "w"
        return f"w_div({a}, {self.w(d, sc)})", "w"

    def t_mod(self, t, sc):
        a = self.w(t[1], sc)
        d = t[2]
        if isinstance(d, int) and not isinstance(d, bool) and 0 < d < (1 << 16):
            return f"w_mod_small({a}, {d})", "w"
        return f"w_mod({a}, {self.w(d, sc)})", "w"

    def t_and(self, t, sc):
        return f"w_and({self.w(t[1], sc)}, {self.w(t[2], sc)})", "w"

    def t_or(self, t, sc):
        return f"w_or({self.w(t[1], sc)}, {self.w(t[2], sc)})", "w"

    def t_xor(self, t, sc):
        return f"w_xor({self.w(t[1], sc)}, {self.w(t[2], sc)})", "w"

    def t_bnot(self, t, sc):
        return f"w_not({self.w(t[1], sc)})", "w"

    def t_neg(self, t, sc):
        return f"w_sub(w0(), {self.w(t[1], sc)})", "w"

    def t_shl(self, t, sc):
        if not isinstance(t[2], int):
            raise GenError(f"{sc.action}: a shift by a non-constant amount")
        fn = self.shl(int(t[2]))
        return (f"{fn}({self.w(t[1], sc)})" if fn else "w0()"), "w"

    def t_shr(self, t, sc):
        if not isinstance(t[2], int):
            raise GenError(f"{sc.action}: a shift by a non-constant amount")
        fn = self.shr(int(t[2]))
        return (f"{fn}({self.w(t[1], sc)})" if fn else "w0()"), "w"

    def t_trunc(self, t, sc):
        bits = int(t[1])
        if bits >= 256:
            return self.w(t[2], sc), "w"
        return f"w_and({self.w(t[2], sc)}, {self.mask(bits)})", "w"

    def t_fits(self, t, sc):
        n = int(t[1])
        inner = t[2]
        if not (isinstance(inner, list) and len(inner) == 3 and inner[0] in ("+", "-", "*")):
            raise GenError(f"{sc.action}: fits over {canonical(inner)[:80]}")
        op = inner[0]
        (ac, ak), (bc, bk) = self.value(inner[1], sc), self.value(inner[2], sc)
        if self.typed and op == "-" and n == 256:
            tt = self.affine_operands("-", inner, (ac, ak), (bc, bk))
            if tt is not None:
                dc, dk = self.typed_affine("-", tt[0], tt[1], sc)
                ds = dk[2:]
                if G.is_signed(G.parse(ds)):
                    u = G.render(G.unsigned(G.parse(ds)))
                    self.coercions[f"realize_{tname(ds)}"] = {"name": f"realize_{tname(ds)}", "kind": "realize",
                                                             "from": ds, "to": u}
                    return f"is_some_{tname(u)}(realize_{tname(ds)}({dc}))", "bool"
        a = self.to_w(*self.unsigned_kind(ac, ak))
        b = self.to_w(*self.unsigned_kind(bc, bk))
        if op == "+":
            ok, val = f"w_add_ok({a}, {b})", f"w_add({a}, {b})"
        elif op == "-":
            ok, val = f"w_sub_ok({a}, {b})", f"w_sub({a}, {b})"
        else:
            ok, val = f"w_mul_ok({a}, {b})", f"w_mul({a}, {b})"
        if n >= 256:
            return ok, "bool"
        return f"Bool.and({ok}, w_lt({val}, {wlit(1 << n)}))", "bool"

    # comparisons and logic
    def compare(self, op: str, t, sc):
        (ac, ak), (bc, bk) = self.value(t[1], sc), self.value(t[2], sc)
        ta = self.typed_operand(ac, ak, t[1], bk)
        tb = self.typed_operand(bc, bk, t[2], ak)
        if ta is not None and tb is not None:
            (ac2, asort), (bc2, bsort) = self.erase(*ta), self.erase(*tb)
            if asort == bsort:
                name = f"{_CMP_NAMES[op]}_{sname(asort)}_{sname(bsort)}"
                self.ops[name] = {"name": name, "op": op, "args": [asort, bsort], "result": "Bool"}
                self.T(asort)
                return f"{name}({ac2}, {bc2})", "bool"
            raise GenError(f"{sc.action}: a comparison {asort} {op} {bsort} joins two base sorts")
        a = self.to_w(*self.unsigned_kind(ac, ak))
        b = self.to_w(*self.unsigned_kind(bc, bk))
        return _RAW_CMP[op](a, b), "bool"

    def t_eq(self, t, sc):
        return self.compare("==", t, sc)

    def t_ne(self, t, sc):
        return self.compare("!=", t, sc)

    def t_lt(self, t, sc):
        if isinstance(t[2], int) and t[2] >= (1 << 32) and t[2] & (t[2] - 1) == 0:
            k = t[2].bit_length() - 1
            v = self.w(t[1], sc)
            return f"Bool.not(w_nz({self.shr(k)}({v})))", "bool"
        return self.compare("<", t, sc)

    def t_le(self, t, sc):
        return self.compare("<=", t, sc)

    def t_gt(self, t, sc):
        return self.compare(">", t, sc)

    def t_ge(self, t, sc):
        return self.compare(">=", t, sc)

    def t_land(self, t, sc):
        xs = [self.cond(x, sc) for x in t[1:]]
        if not xs:
            return "True{}", "bool"
        out = xs[-1]
        for x in reversed(xs[:-1]):
            out = f"Bool.and({x}, {out})"
        return out, "bool"

    def t_lor(self, t, sc):
        xs = [self.cond(x, sc) for x in t[1:]]
        if not xs:
            return "False{}", "bool"
        out = xs[-1]
        for x in reversed(xs[:-1]):
            out = f"Bool.or({x}, {out})"
        return out, "bool"

    def t_lnot(self, t, sc):
        return f"Bool.not({self.cond(t[1], sc)})", "bool"

    def t_ite(self, t, sc):
        c = self.cond(t[1], sc)
        (ac, ak), (bc, bk) = self.value(t[2], sc), self.value(t[3], sc)
        ac, ak = self.unsigned_kind(ac, ak)
        bc, bk = self.unsigned_kind(bc, bk)
        if ak != bk:
            if ak.startswith("t:") and bk == "w" and isinstance(t[3], int):
                bc, bk = f"{self.T(ak[2:])}{{{bc}}}", ak
            elif bk.startswith("t:") and ak == "w" and isinstance(t[2], int):
                ac, ak = f"{self.T(bk[2:])}{{{ac}}}", bk
            elif {ak, bk} <= {"w", "bool"} or (ak.startswith("t:") or bk.startswith("t:")) and \
                    {ak[:2], bk[:2]} <= {"t:", "w", "bo"}:
                ac, ak, bc, bk = self.to_w(ac, ak), "w", self.to_w(bc, bk), "w"
            elif {ak, bk} <= {"w", "b"}:
                ac, ak, bc, bk = self.to_bytes(ac, ak), "b", self.to_bytes(bc, bk), "b"
            elif ak.startswith("v:") and bk.startswith("v:"):
                pass
            else:
                raise GenError(f"{sc.action}: a conditional over {ak} and {bk}")
        return f"ite({self.bend_type(ak)}, {c}, {ac}, {bc})", ak

    # bytes, hashes, memory
    def t_len(self, t, sc):
        c, k = self.value(t[1], sc)
        if k == "b":
            return f"w_u(b_len({c}))", "w"
        if k.startswith("l:"):
            el = k[2:]
            if el == "W":
                return f"w_u(w_len({c}))", "w"
            return f"w_u(U32.from_nat(List.length(&2, {el}, {c})))", "w"
        raise GenError(f"{sc.action}: the length of a {k} value")

    def t_byte(self, t, sc):
        return f"w_u(b_at({self.b(t[1], sc)}, {self.nat(t[2], sc)}))", "w"

    def t_word(self, t, sc):
        code = f"b_word({self.b(t[1], sc)}, {self.nat(t[2], sc)})"
        pv = _param_var(t[1], sc.action)
        return self.leaf(code, f"{pv}@{t[2]}" if pv and isinstance(t[2], int) else None, t)

    def hash(self, which: str, t, sc):
        if which not in self.hashes:
            raise GenError(f"{sc.action}: {which} is not a hash parameter of the model")
        tab = self.gx(sc, "kh" if which == "keccak256" else "sh")
        fn = "h_get" if which == "keccak256" else "hs_get"
        return self.leaf(f"{fn}({tab}, {self.b(t[1], sc)})", None, t)

    def t_keccak256(self, t, sc):
        return self.hash("keccak256", t, sc)

    def t_sha256(self, t, sc):
        return self.hash("sha256", t, sc)

    def t_mem(self, t, sc):
        code = "Nil{}"
        for wr in t[1:]:
            code = self.mem_write(code, wr, sc)
        return code, "b"

    def mem_write(self, mem: str, wr, sc: Scope) -> str:
        k = wr[0] if isinstance(wr, list) and wr else None
        if k == "mstore":
            return f"m_put({self.nat(wr[1], sc)}, {mem}, b_of_w({self.w(wr[2], sc)}))"
        if k == "mstore8":
            return f"m_put({self.nat(wr[1], sc)}, {mem}, [U32.and(w_lo({self.w(wr[2], sc)}), 255)])"
        if k == "calldatacopy":
            return (f"m_put({self.nat(wr[1], sc)}, {mem}, b_take({self.nat(wr[4], sc)}, "
                    f"b_drop({self.b(wr[2], sc)}, {self.nat(wr[3], sc)}), 0))")
        if k == "when":
            return f"ite(List<&2, U32>, {self.cond(wr[1], sc)}, {self.mem_write(mem, wr[2], sc)}, {mem})"
        if k in ("loop", "unknown"):
            return f"m_havoc({mem})"
        if k == "mloop":
            return self.mloop(mem, wr, sc)
        raise GenError(f"{sc.action}: memory write {k}")

    def mloop(self, mem: str, wr, sc: Scope) -> str:
        key = (sc.action, canonical(wr), tuple(sorted(sc.subst)))
        name = self.ml_cache.get(key)
        if name is None:
            name = self.fresh(f"ml_{bname(sc.action)}")
            kvar = wr[2]
            body = wr[4] if isinstance(wr[4], list) and wr[4] and isinstance(wr[4][0], list) else [wr[4]]
            inner = Scope(sc.action, sc.x, dict(sc.subst), sc.loops)
            inner.subst[canonical(kvar)] = self.leaf("k", None)
            code = "mem"
            for b in body:
                code = self.mem_write(code, b, inner)
            xt = f"X_{bname(sc.action)}"
            self.add(f"def {name}(n: Nat, +k: W, +{sc.x}: {xt}, mem: List<&2, U32>) -> List<&2, U32>:\n"
                     f"  match n:\n    case 0n:\n      mem\n    case 1n+p:\n"
                     f"      {name}(p, w_add(k, w_u(1)), {sc.x}, {code})\n")
            self.ml_cache[key] = name
        if sc.subst:
            raise GenError(f"{sc.action}: an mloop inside an mloop")
        return f"{name}({self.nat(wr[3], sc)}, w0(), {sc.x}, {mem})"

    def t_slice(self, t, sc):
        return f"m_slice({self.b(t[1], sc)}, {self.w(t[2], sc)}, {self.w(t[3], sc)})", "b"

    def t_mload(self, t, sc):
        return f"b_word({self.b(t[1], sc)}, {self.nat(t[2], sc)})", "w"

    def t_abi_encode(self, t, sc):
        heads, tails = [], []
        for x in t[1:]:
            c, k = self.value(x, sc)
            if k == "b":
                heads.append(None)
                tails.append(c)
            else:
                heads.append(f"b_of_w({self.to_w(c, k)})")
        return self.abi_concat(heads, tails), "b"

    def abi_concat(self, heads: list, tails: list) -> str:
        """head . tail encoding: a None head is a dynamic value whose tail is the next of `tails`."""
        n = len(heads)
        parts = []
        off = f"w_u({32 * n})"
        it = iter(tails)
        tail_parts = []
        for h in heads:
            if h is None:
                tl = next(it)
                parts.append(f"b_of_w({off})")
                enc = f"abi_dyn({tl})"
                tail_parts.append(enc)
                off = f"w_add({off}, w_u(b_len({enc})))"
            else:
                parts.append(h)
        out = "Nil{}"
        for p in reversed(parts + tail_parts):
            out = f"List.append(&2, U32, {p}, {out})"
        return out

    def t_abi_encodePacked(self, t, sc):
        out = "Nil{}"
        parts = []
        for x in t[1:]:
            c, k = self.value(x, sc)
            if k == "b":
                parts.append(c)
                continue
            ty = self.term_type(x, sc)
            if ty is None:
                raise GenError(f"{sc.action}: abi.encodePacked of a word of no known type: {canonical(x)[:100]}")
            n, left = EV._packed_width(ty)
            wv = self.to_w(c, k)
            parts.append(f"b_take({n}n, b_of_w({wv}), 0)" if left else f"b_drop(b_of_w({wv}), {32 - n}n)")
        for p in reversed(parts):
            out = f"List.append(&2, U32, {p}, {out})"
        return out, "b"

    def term_type(self, t, sc) -> str | None:
        """holon.extracted_eval.Eval.term_type, statically."""
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
            return (self.m.immutable_type(t[1]) or {}).get("type")
        if h == "param":
            for p in self.m.params(sc.action) or []:
                if p.get("name") == t[1]:
                    return p.get("type")
            return None
        if h in ("storage", "map", "member", "index"):
            p = self.path_of(t, sc)
            if p is None:
                return None
            _s, _o, tid, _l = self.locate(p, sc)
            lab = str(self.m.type_of(tid).get("label", ""))
            if lab.startswith(("contract ", "address")):
                return "address"
            return "uint8" if lab.startswith("enum ") else lab
        return None

    # external calls
    def calldata(self, fn: str, args: list, sc: Scope) -> str:
        sig = self.m.call_signature(fn)
        if sig is None or not sig.get("selector"):
            raise GenError(f"{sc.action}: external function {fn} has no single ABI signature")
        ins = sig.get("inputs") or []
        if len(ins) != len(args):
            raise GenError(f"{sc.action}: {fn} takes {len(ins)} arguments, the term gives {len(args)}")
        heads, tails = [], []
        for x, p in zip(args, ins):
            c, k = self.value(x, sc)
            if EV._is_dynamic(p):
                if p.get("type") not in ("bytes", "string"):
                    raise GenError(f"{sc.action}: {fn}: a dynamic argument of type {p.get('type')}")
                heads.append(None)
                tails.append(self.to_bytes(c, k))
            else:
                if p.get("type") == "tuple":
                    raise GenError(f"{sc.action}: {fn}: a tuple argument")
                heads.append(f"b_of_w({self.to_w(c, k)})")
        sel = bytes.fromhex(sig["selector"][2:])
        return f"List.append(&2, U32, {blit(sel)}, {self.abi_concat(heads, tails)})"

    def answer(self, fn: str, receiver, args: list, sc: Scope) -> str:
        cf = self.env_field("calls", "List<&2, HCall>")
        calls = f"ge_{cf}({self.gx(sc, 'en')})"
        if fn.startswith("address."):
            if not args and receiver is None:
                raise GenError(f"{sc.action}: {fn} without a receiver")
            to = self.w(receiver if receiver is not None else args[0], sc)
            rest = args if receiver is not None else args[1:]
            data = self.b(rest[0], sc) if rest else "Nil{}"
            return f"c_find({calls}, {to}, True{{}}, {data})"
        data = self.calldata(fn, args, sc)
        if receiver is not None:
            return f"c_find({calls}, {self.w(receiver, sc)}, True{{}}, {data})"
        return f"c_find({calls}, w0(), False{{}}, {data})"

    @staticmethod
    def split_value(args: list):
        """The call's arguments without its ["value", v] annotation."""
        return [a for a in args if not (isinstance(a, list) and a[:1] == ["value"])]

    def t_call(self, t, sc):
        fn = t[1]
        args = self.split_value(t[2:])
        if fn.startswith("address."):
            return self.answer(fn, None, args, sc), "a"
        ans = self.answer(fn, None, args, sc)
        sig = self.m.call_signature(fn) or {}
        outs = sig.get("outputs") or []
        if len(outs) == 1 and not EV._is_dynamic(outs[0]):
            return self.leaf(f"b_word(a_ret({ans}), 0n)", f"call:{fn}", t)
        return ans, "a"

    def t_callok(self, t, sc):
        fn = t[1]
        receiver = t[2]
        args = self.split_value(t[3:])
        return f"a_ok({self.answer(fn, receiver, args, sc)})", "bool"

    def t_at(self, t, sc):
        c, k = self.tx(t[2], sc)
        if k != "a":
            raise GenError(f"{sc.action}: a component of a value that is not a call answer")
        i = int(t[1])
        inner = t[2]
        if isinstance(inner, list) and inner[:1] == ["call"] and str(inner[1]).startswith("address."):
            if i == 0:
                return f"w_b(a_ok({c}))", "w"
            return f"a_ret({c})", "b"
        return f"b_word(a_ret({c}), {32 * i}n)", "w"

    def t_value(self, t, sc):
        raise GenError(f"{sc.action}: a call value outside a call")

    def t_struct(self, t, sc):
        vals = {}
        for mname, v in t[2]:
            vals[mname] = self.w(v, sc)
        return "z:" + json.dumps(vals, sort_keys=True), "z"

    def t_unknown(self, t, sc):
        raise GenError(f"{sc.action}: an unknown term {canonical(t)[:100]} (its value is no environment member)")


def _is_lit(t) -> bool:
    return isinstance(t, int) and not isinstance(t, bool)


def _param_var(t, action: str) -> str | None:
    if not isinstance(t, list) or not t:
        return None
    if t[0] == "param" and isinstance(t[1], str):
        return f"{action}.{t[1]}"
    if t[0] == "member" and len(t) >= 3:
        b = _param_var(t[1], action)
        return f"{b}.{t[2]}" if b else None
    return None


_NAMES = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod", "&": "and", "|": "or", "^": "xor",
          "~": "bnot", "not": "bnot", "<<": "shl", ">>": "shr", "==": "eq", "!=": "ne", "<": "lt", "<=": "le",
          ">": "gt", ">=": "ge", "&&": "land", "||": "lor", "!": "lnot", "?": "ite", "abi.encode": "abi_encode",
          "abi.encodePacked": "abi_encodePacked"}
_CMP_NAMES = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
_RAW_CMP = {"==": lambda a, b: f"w_eq({a}, {b})", "!=": lambda a, b: f"Bool.not(w_eq({a}, {b}))",
            "<": lambda a, b: f"w_lt({a}, {b})", "<=": lambda a, b: f"w_le({a}, {b})",
            ">": lambda a, b: f"w_gt({a}, {b})", ">=": lambda a, b: f"w_ge({a}, {b})"}


# ================================================================================================ the machine
CALL_CODE = 4294967294       # a step whose external call term reverted (its revert data bubbled; no check of the document)
TOP_CODE = 4026531840        # codes from here up are not checks (call reverts, fuel)

_COMMON = '''\
def lg_rev(xs: List<&2, HLog>, +acc: List<&2, HLog>) -> List<&2, HLog>:
  match xs:
    case Nil{}:
      acc
    case Con{h, t}:
      lg_rev(t, Con{h, acc})

def hs_get(+xs: List<&2, HKB>, +k: List<&2, U32>) -> W:
  h_get(xs, k)

def kt_id(+xs: List<&2, HKB>) -> List<&2, HKB>:
  xs

def st_after(+o: HOut, +st: HSt) -> HSt:
  ite(HSt, u_nz(o_code(o)), st, o_post(o))

def b_zeros(n: Nat) -> List<&2, U32>:
  match n:
    case 0n:
      Nil{}
    case 1n+p:
      Con{0, b_zeros(p)}

def abi_dyn(+bs: List<&2, U32>) -> List<&2, U32>:
  List.append(&2, U32, b_of_w(w_u(b_len(bs))), List.append(&2, U32, bs, b_zeros(U32.to_nat(U32.and(U32.sub(32, U32.and(b_len(bs), 31)), 31)))))

def abi_words(xs: List<&2, W>) -> List<&2, U32>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{h, t}:
      List.append(&2, U32, b_of_w(h), abi_words(t))

def abi_wlist(+xs: List<&2, W>) -> List<&2, U32>:
  List.append(&2, U32, b_of_w(w_u(w_len(xs))), abi_words(xs))

def eq_bool(a: Bool, b: Bool) -> Bool:
  match a b:
    case True{} True{}:
      True{}
    case False{} False{}:
      True{}
    case True{} False{}:
      False{}
    case False{} True{}:
      False{}

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty
'''


def _getters(prefix: str, rec: str, fs: list) -> list[str]:
    out = []
    names = [f for f, _ in fs]
    for f, ty in fs:
        pat = ", ".join(names)
        out.append(f"def {prefix}{f}(e: {rec}) -> {ty}:\n  match e:\n    case {rec}{{{pat}}}:\n      {f}\n")
    return out


def _setters(prefix: str, rec: str, fs: list) -> list[str]:
    out = []
    names = [f for f, _ in fs]
    for f, ty in fs:
        pat = ", ".join(n if n != f else "_" for n in names)
        vals = ", ".join(n if n != f else "v" for n in names)
        out.append(f"def {prefix}{f}(e: {rec}, +v: {ty}) -> {rec}:\n  match e:\n    case {rec}{{{pat}}}:\n"
                   f"      {rec}{{{vals}}}\n")
    return out


def _record(rec: str, fs: list) -> str:
    return f"type {rec} is Data:\n  {rec}{{{', '.join(f'{f}: {ty}' for f, ty in fs)}}}\n"


def _default(ty: str) -> str:
    if ty == "W":
        return "w0()"
    if ty == "U32":
        return "0"
    if ty == "Nat":
        return "0n"
    if ty == "Bool":
        return "False{}"
    if ty == "HSt":
        return "st"
    if ty == "HAns":
        return "HAns{False{}, False{}, Nil{}}"
    if ty.startswith("List<"):
        return "Nil{}"
    raise GenError(f"no default value of {ty}")


def _calls_in(t, pc: list, out: list) -> None:
    """The call terms a term evaluates (holon.extracted_eval: "?", && and || evaluate lazily), in evaluation order, each
    with the conditions under which it is evaluated: [(term, [(cond, polarity)])]."""
    if not isinstance(t, list) or not t or not isinstance(t[0], str):
        if isinstance(t, list):
            for x in t:
                _calls_in(x, pc, out)
        return
    h = t[0]
    if h == "mloop":
        return      # a memory loop's calls run once per iteration under its own variable: its loop record's call
        # records check them (a call term outside its iteration has no meaning)
    if h == "?" and len(t) == 4:
        _calls_in(t[1], pc, out)
        _calls_in(t[2], pc + [(t[1], True)], out)
        _calls_in(t[3], pc + [(t[1], False)], out)
        return
    if h in ("&&", "||"):
        acc = list(pc)
        for x in t[1:]:
            _calls_in(x, acc, out)
            acc = acc + [(x, h == "&&")]
        return
    for x in t[1:]:
        _calls_in(x, pc, out)
    if h == "call" and not str(t[1]).startswith("address."):
        key = canonical([t, pc])
        if key not in [canonical([a, b]) for a, b in out]:
            out.append((t, pc))


def _callok_terms(t, out: list) -> None:
    if isinstance(t, list):
        if t and t[0] == "callok":
            out.append(t)
        for x in t:
            _callok_terms(x, out)


class Machine(Gen):
    """The whole model: per-action programs (above the ghost marker), the sort section (typed), the ghost section or
    the site instrumentation (untyped)."""

    def __init__(self, m: ExtractedModel, **kw):
        super().__init__(m, **kw)
        self.action_defs: dict = {}
        self.action_ctx: dict = {}
        self.cidx: dict = {}
        self.nstmt = 0
        self.nloop = 0
        self.loops_of: dict = {}

    def cidx_of(self, a: str, cid: str) -> int:
        for i, c in enumerate(self.checks[a]):
            if c.id == cid:
                return i
        raise GenError(f"{a}: no check {cid}")

    # ---------------------------------------------------------- context records
    def xt(self, a: str) -> str:
        return f"X_{bname(a)}"

    def ctx(self, a: str, fld: str, ty: str) -> str:
        fs = self.ctx_fields.setdefault(a, [])
        if fld not in [f for f, _ in fs]:
            fs.append((fld, ty))
        return fld

    def sx(self, sc: Scope, fld: str, x: str, v: str) -> str:
        return f"sx_{bname(sc.action)}_{fld}({x}, {v})"

    def field_type(self, kind: str) -> str:
        if kind in ("w", "bool") or kind.startswith("t:"):
            return "W"
        return self.bend_type(kind)

    @staticmethod
    def store_kind(kind: str) -> str:
        return "w" if kind in ("w", "bool") or kind.startswith("t:") else kind

    def store_value(self, code: str, kind: str, want: str) -> str:
        if want == "w":
            return self.to_w(code, kind)
        if want == "b":
            return self.to_bytes(code, kind)
        if want != kind:
            raise GenError(f"a loop name of kind {want} takes a {kind} value")
        return code

    # ---------------------------------------------------------- actions
    def compile_action(self, a: str) -> None:
        ba = bname(a)
        X = self.xt(a)
        prog = self.m.program(a)
        self.checks[a] = prog.checks()
        self.cidx = {c.id: i for i, c in enumerate(self.checks[a])}
        self.defs = []
        self.ctx_fields[a] = []
        for f, ty in (("st", "HSt"), ("ov", "HSt"), ("ar", f"AR_{ba}"), ("en", "HEnv")):
            self.ctx(a, f, ty)
        for h in self.hashes:
            self.ctx(a, "kh" if h == "keccak256" else "sh", "List<&2, HKB>")
        for f, ty in (("cd", "U32"), ("rv", "List<&2, U32>"), ("lg", "List<&2, HLog>"), ("tw", "List<&2, W>")):
            self.ctx(a, f, ty)
        sc = Scope(a)
        self.nstmt = 0
        self.register_loops(prog.steps, sc)
        end = f"sz_{ba}"
        first = self.chain(prog.steps, sc, end)
        body = self.defs
        fs = self.ctx_fields[a]
        hs = ", ".join(f"+{'kh' if h == 'keccak256' else 'sh'}: List<&2, HKB>" for h in self.hashes)
        hv = ", ".join("kh" if h == "keccak256" else "sh" for h in self.hashes)
        sig = f"+st: HSt, +ar: AR_{ba}, +en: HEnv{', ' + hs if hs else ''}"
        args = f"st, ar, en{', ' + hv if hv else ''}"
        head = [_record(X, fs)] + _getters(f"gx_{ba}_", X, fs) + _setters(f"sx_{ba}_", X, fs)
        head.append(f"def xf_{ba}(+x: {X}, +c: U32, +r: List<&2, U32>) -> {X}:\n  sx_{ba}_cd(sx_{ba}_rv(x, r), c)\n")
        head.append(f"def {end}(+x: {X}) -> {X}:\n  x\n")
        init = []
        for f, ty in fs:
            init.append({"st": "st", "ov": "st", "ar": "ar", "en": "en", "kh": "kh", "sh": "sh"}.get(f) or _default(ty))
        tail = [f"def x0_{ba}({sig}) -> {X}:\n  {X}{{{', '.join(init)}}}\n",
                f"# the context after the action's program ran (holon.extracted_eval's order)\n"
                f"def xr_{ba}({sig}) -> {X}:\n  {first}(x0_{ba}({args}))\n",
                f"def xo_{ba}(+x: {X}) -> HOut:\n  HOut{{gx_{ba}_cd(x), gx_{ba}_rv(x), gx_{ba}_ov(x), "
                f"lg_rev(gx_{ba}_lg(x), Nil{{}}), gx_{ba}_tw(x)}}\n",
                f"def run_{ba}({sig}) -> HOut:\n  xo_{ba}(xr_{ba}({args}))\n",
                f"# 0 when every check of {a} holds, k + 1 when check k (holon.machine's order) is the first to fail\n"
                f"def chk_{ba}({sig}) -> U32:\n  o_code(run_{ba}({args}))\n",
                f"def post_{ba}({sig}) -> HSt:\n  o_post(run_{ba}({args}))\n",
                f"def logs_{ba}({sig}) -> List<&2, HLog>:\n  o_logs(run_{ba}({args}))\n",
                f"def step_{ba}({sig}) -> HSt:\n  st_after(run_{ba}({args}), st)\n"]
        self.action_defs[a] = head + body + tail
        self.defs = []

    def chain(self, steps, sc: Scope, nxt: str) -> str:
        for s in reversed(list(steps)):
            nxt = self.statement(s, sc, nxt)
        return nxt

    # ---------------------------------------------------------- loops: registration (forward)
    def register_loops(self, steps, sc: Scope) -> None:
        for s in steps:
            if not isinstance(s, Loop):
                continue
            self.nloop += 1
            j = self.nloop
            a = sc.action
            li = LoopInfo(j, s, [], [], len(s.returns))
            sc.src = s.src
            for n, e, _v in s.carried:
                c, k = self.value(e, sc)
                k = self.store_kind(k)
                li.carried.append((n, _lab(n), k))
            sc.loops[(s.src, s.reach)] = li
            for i, (n, lab, k) in enumerate(li.carried):
                self.ctx(a, f"c{j}_{i}", self.field_type(k))
            for f, ty in ((f"it{j}", "W"), (f"cn{j}", "W"), (f"rt{j}", "W"), (f"ld{j}", "Nat")):
                self.ctx(a, f, ty)
            self.register_loops(s.body, sc)
            names = [canonical(n) for n, _l, _k in li.carried]
            for n, e in s.exits:
                if canonical(n) in names:
                    continue
                c, k = self.value(e, sc)
                li.exits_extra.append((n, _lab(n), self.store_kind(k)))
                names.append(canonical(n))
            for m, (_cnd, v) in enumerate(s.returns):
                c, k = self.value(v, sc)
                li.exits_extra.append((["return", m], f"return{m}", self.store_kind(k)))
            for i, (n, lab, k) in enumerate(li.exits_extra):
                self.ctx(a, f"x{j}_{i}", self.field_type(k))
            self.loops_of[(a, s.seq)] = li

    # ---------------------------------------------------------- statements (reverse)
    def statement(self, s, sc: Scope, nxt: str) -> str:
        if isinstance(s, MStore):
            return nxt                    # memory is not observable; terms carry the regions they read
        a = sc.action
        ba = bname(a)
        X = self.xt(a)
        self.nstmt += 1
        i = self.nstmt
        sc.src = s.src
        try:
            pc = [] if getattr(s, "cond", 1) in (1, True) else [(s.cond, True)]
            if isinstance(s, Check):
                body = self.st_check(s, sc, nxt, i)
                terms = [(s.expr, [])]
            elif isinstance(s, Write):
                body = self.st_write(s, sc, nxt, i)
                terms = [(s.cond, []), ([x[1] for x in s.path], pc), (s.value, pc)]
            elif isinstance(s, Event):
                body = self.st_event(s, sc, nxt, i)
                terms = [(s.cond, []), (list(s.topics), pc), (list(s.args), pc)]
            elif isinstance(s, Loop):
                body = self.st_loop(s, sc, nxt, i)
                terms = [(s.cond, []), ([e for _n, e, _v in s.carried], pc)]
            else:
                raise GenError(f"{a}: a program record of kind {type(s).__name__}")
        except GenError as e:
            msg = str(e)
            if s.src and str(s.src) not in msg:
                msg = f"{msg} (at {s.src})"
            raise GenError(msg) from None
        body = self.call_guards(terms, sc, body, i)
        name = f"s_{ba}_{i}"
        self.add(f"# {comment(f'{type(s).__name__.lower()} {s.src}')}\ndef {name}(+x: {X}) -> {X}:\n  {body}\n")
        return name

    def call_guards(self, terms: list, sc: Scope, body: str, i: int) -> str:
        """A call term whose answer is a revert reverts the step with that data (holon.extracted_eval CallReverted),
        when the evaluation reaches it."""
        calls: list = []
        for t, pc in terms:
            _calls_in(t, list(pc), calls)
        if not calls:
            return body
        a = sc.action
        ba = bname(a)
        X = self.xt(a)
        for n in range(len(calls) - 1, -1, -1):
            t, pc = calls[n]
            ans = self.answer(t[1], None, self.split_value(t[2:]), sc)
            name = f"cq_{ba}_{i}_{n}"
            self.add(f"def {name}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n"
                     f"      xf_{ba}(x, {CALL_CODE}, a_ret({ans}))\n    case False{{}}:\n      {body}\n")
            cond = f"Bool.not(a_ok({ans}))"
            for ct, pol in reversed(pc):
                cc = self.cond(ct, sc)
                cond = f"Bool.and({cc if pol else f'Bool.not({cc})'}, {cond})"
            body = f"{name}({cond}, x)"
        return body

    def st_check(self, c: Check, sc: Scope, nxt: str, i: int) -> str:
        ba = bname(sc.action)
        X = self.xt(sc.action)
        k = self.cidx[c.id]
        cond = self.cond(c.expr, sc)
        rv = self.revert_code(c, sc)
        kn = f"k_{ba}_{i}"
        self.add(f"# {comment(c.id)}\ndef {kn}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n"
                 f"      {nxt}(x)\n    case False{{}}:\n      xf_{ba}(x, {k + 1}, {rv})\n")
        return f"{kn}({cond}, x)"

    def revert_code(self, c: Check, sc: Scope) -> str:
        if c.kind == "panic" or c.code is not None:
            return blit(EV.panic(to_int(c.code)))
        if c.kind in ("call", "uncaught"):
            oks: list = []
            _callok_terms(c.expr, oks)
            code = "Nil{}"
            for t in oks:
                ans = self.answer(t[1], t[2], self.split_value(t[3:]), sc)
                code = f"ite(List<&2, U32>, a_ok({ans}), {code}, a_ret({ans}))"
            return code
        if c.kind in ("callvalue", "calldatasize", "abi", "slice"):
            return "Nil{}"
        err = c.error if isinstance(c.error, dict) else None
        if err is None:
            return "Nil{}"
        sel = err.get("selector")
        if not (isinstance(sel, str) and re.fullmatch(r"0x[0-9a-fA-F]{8}", sel)):
            raise GenError(f"check {c.id}: its error has no selector")
        head = blit(bytes.fromhex(sel[2:]))
        ps = EV.signature_types(err.get("signature") or "")
        args = c.args if isinstance(c.args, list) else []
        if not ps or len(args) != len(ps):
            return head
        return f"List.append(&2, U32, {head}, {self.abi_values(list(zip(args, ps)), sc)})"

    def abi_values(self, pairs: list, sc: Scope) -> str:
        heads, tails = [], []
        for t, p in pairs:
            ty = p.get("type", "")
            if ty in ("bytes", "string"):
                heads.append(None)
                tails.append(self.b(t, sc))
            elif re.fullmatch(r"(u?int\d*|address|bool|bytes\d+)", ty):
                heads.append(f"b_of_w({self.w(t, sc)})")
            elif re.fullmatch(r"(u?int\d*|address|bool|bytes\d+)\[\]", ty):
                c, k = self.value(t, sc)
                if k != "l:W":
                    raise GenError(f"{sc.action}: an ABI {ty} of a {k} value")
                heads.append(None)
                tails.append(("w", c))
            else:
                raise GenError(f"{sc.action}: ABI encoding of a {ty}")
        n = len(heads)
        parts = []
        off = f"w_u({32 * n})"
        it = iter(tails)
        tail_parts = []
        for h in heads:
            if h is None:
                tl = next(it)
                enc = f"abi_wlist({tl[1]})" if isinstance(tl, tuple) else f"abi_dyn({tl})"
                parts.append(f"b_of_w({off})")
                tail_parts.append(enc)
                off = f"w_add({off}, w_u(b_len({enc})))"
            else:
                parts.append(h)
        out = "Nil{}"
        for p in reversed(parts + tail_parts):
            out = f"List.append(&2, U32, {p}, {out})" if out != "Nil{}" else p
        return out

    # writes
    def st_write(self, w: Write, sc: Scope, nxt: str, i: int) -> str:
        a = sc.action
        ba = bname(a)
        X = self.xt(a)
        wn = f"wr_{ba}_{i}"
        lines = self.write_body(w, sc)
        self.add(f"def {wn}(+x: {X}) -> {X}:\n" + "\n".join(lines) + "\n")
        if w.cond in (1, True):
            return f"{nxt}({wn}(x))"
        cn = f"wc_{ba}_{i}"
        self.add(f"def {cn}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      {nxt}({wn}(x))\n"
                 f"    case False{{}}:\n      {nxt}(x)\n")
        return f"{cn}({self.cond(w.cond, sc)}, x)"

    def write_body(self, w: Write, sc: Scope) -> list[str]:
        fam = w.family
        self.m.family(fam)
        p = StoragePath("o0", fam, [], fam)
        for acc in w.path:
            kind, key = acc[0], acc[1]
            if kind == "member":
                p = p.extend("member", key, "name", f"{p.var}.{key}")
            else:
                kc, kk = self.value(key, sc)
                p = p.extend(kind, kc, kk, p.var)
        slot, off, tid, _lit = self.locate(p, sc)
        t = self.m.type_of(tid)
        lines = [f"  +o0 = {self.gx(sc, 'ov')}", f"  +k = {{{slot} : W}}"]
        slots: list = []
        if t.get("encoding") == "inplace" and "members" in t:
            vals = self.struct_value(w.value, sc, lines)
            cur = "o0"
            n = 0
            for mm in t["members"]:
                mt = self.m.type_of(mm["type"])
                if mt.get("encoding") != "inplace" or "members" in mt or "base" in mt:
                    if vals.get(mm["label"], "w0()") != "w0()":
                        raise GenError(f"{sc.action}: a write of member {mm['label']} ({mt.get('label')}) of {fam}")
                    continue
                ms = "k" if not int(mm["slot"]) else f"w_add(k, {wlit(int(mm['slot']))})"
                n += 1
                lines.append(f"  +o{n} = {{{self.write_word(cur, ms, int(mm['offset']), mm['type'], vals.get(mm['label'], 'w0()'))} : HSt}}")
                cur = f"o{n}"
                if ms not in slots:
                    slots.append(ms)
        elif t.get("encoding") == "inplace" and "base" not in t:
            vc, vk = self.value(w.value, sc)
            lines.append(f"  +v = {{{self.to_w(vc, vk)} : W}}")
            lines.append(f"  +o1 = {{{self.write_word('o0', 'k', off, tid, 'v')} : HSt}}")
            cur = "o1"
            slots = ["k"]
        else:
            raise GenError(f"{sc.action}: a write of a whole {t.get('label')} ({fam})")
        tw = self.gx(sc, "tw")
        for s_ in reversed(slots):
            tw = f"Con{{{s_}, {tw}}}"
        lines.append(f"  {self.sx(sc, 'tw', self.sx(sc, 'ov', 'x', cur), tw)}")
        return lines

    def struct_value(self, t, sc: Scope, lines: list) -> dict:
        if t in (0, False):
            return {}
        c, k = self.tx(t, sc)
        if k == "z":
            return json.loads(c[2:])
        if k == "p":
            slot, off, tid, _l = self.locate(c, sc)
            st = self.m.type_of(tid)
            if "members" not in st:
                raise GenError(f"{sc.action}: a struct write of a {st.get('label')} read")
            lines.append(f"  +q = {{{slot} : W}}")
            out = {}
            for mm in st["members"]:
                mt = self.m.type_of(mm["type"])
                if mt.get("encoding") != "inplace" or "members" in mt or "base" in mt:
                    continue
                ms = "q" if not int(mm["slot"]) else f"w_add(q, {wlit(int(mm['slot']))})"
                out[mm["label"]] = self.read_word(c.view, ms, int(mm["offset"]), mm["type"])
            return out
        raise GenError(f"{sc.action}: a struct write of a {k} value")

    # events
    def st_event(self, ev: Event, sc: Scope, nxt: str, i: int) -> str:
        a = sc.action
        ba = bname(a)
        X = self.xt(a)
        if not ev.signature:
            raise GenError(f"{a}: event {ev.event}: the document gives no signature")
        ps = EV.signature_types(ev.signature)
        if len(ev.args) != len(ps) or len(ev.indexed) != len(ps):
            raise GenError(f"{a}: event {ev.event}: {len(ev.args)} arguments for {len(ps)} parameters")
        topics = []
        if not ev.anonymous:
            if not isinstance(ev.topic0, str):
                raise GenError(f"{a}: event {ev.event}: no topic0")
            topics.append(wlit(to_int(ev.topic0)))
        if len(ev.topics) != sum(1 for x in ev.indexed if x):
            raise GenError(f"{a}: event {ev.event}: topic terms and indexed arguments differ")
        topics += [self.w(t, sc) for t in ev.topics]
        data = self.abi_values([(x, p) for x, p, ix in zip(ev.args, ps, ev.indexed) if not ix], sc)
        tl = ("[" + ", ".join(topics) + "]") if topics else "Nil{}"
        en = f"ev_{ba}_{i}"
        lgc = self.gx(sc, "lg")
        new = "Con{HLog{" + tl + ", " + data + "}, " + lgc + "}"
        self.add(f"def {en}(+x: {X}) -> {X}:\n  {self.sx(sc, 'lg', 'x', new)}\n")
        if ev.cond in (1, True):
            return f"{nxt}({en}(x))"
        cn = f"ec_{ba}_{i}"
        self.add(f"def {cn}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      {nxt}({en}(x))\n"
                 f"    case False{{}}:\n      {nxt}(x)\n")
        return f"{cn}({self.cond(ev.cond, sc)}, x)"

    # loops
    def set_fields(self, sc: Scope, x: str, pairs: list) -> str:
        out = x
        for f, v in pairs:
            out = self.sx(sc, f, out, v)
        return out

    def st_loop(self, lp: Loop, sc: Scope, nxt: str, i: int) -> str:
        a = sc.action
        ba = bname(a)
        X = self.xt(a)
        li = self.loops_of[(a, lp.seq)]
        j = li.j
        p = f"{ba}_{j}"
        # the iteration's body, then its decisions (helpers before their users: Bend reads definitions in order)
        lets, sets = [], []
        for k_, (n, e) in enumerate(lp.next):
            idx = next((q for q, (cn_, _l, _k) in enumerate(li.carried) if canonical(cn_) == canonical(n)), None)
            if idx is None:
                raise GenError(f"{a}: loop {lp.src}: next value of {canonical(n)}, which is not carried")
            c, kk = self.value(e, sc)
            lets.append(f"  +n{k_} = {{{self.store_value(c, kk, li.carried[idx][2])} : {self.field_type(li.carried[idx][2])}}}")
            sets.append((f"c{j}_{idx}", f"n{k_}"))
        sets.append((f"it{j}", f"w_add({self.gx(sc, f'it{j}')}, w_u(1))"))
        sets.append((f"ld{j}", "1n"))
        self.add(f"def ln_{p}(+x: {X}) -> {X}:\n" + "\n".join(lets + [f"  {self.set_fields(sc, 'x', sets)}"]) + "\n")
        # break: the at_break values, the count
        lets, sets = [], []
        for k_, (n, e) in enumerate(lp.at_break):
            idx = next((q for q, (cn_, _l, _k) in enumerate(li.carried) if canonical(cn_) == canonical(n)), None)
            if idx is None:
                continue
            c, kk = self.value(e, sc)
            lets.append(f"  +b{k_} = {{{self.store_value(c, kk, li.carried[idx][2])} : {self.field_type(li.carried[idx][2])}}}")
            sets.append((f"c{j}_{idx}", f"b{k_}"))
        sets += [(f"cn{j}", self.gx(sc, f"it{j}")), (f"ld{j}", "3n")]
        self.add(f"def lbk_{p}(+x: {X}) -> {X}:\n" + "\n".join(lets + [f"  {self.set_fields(sc, 'x', sets)}"]) + "\n")
        self.add(f"def lk_{p}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      lbk_{p}(x)\n"
                 f"    case False{{}}:\n      ln_{p}(x)\n")
        nxt_dec = f"lk_{p}({self.cond(lp.brk, sc)}, x)" if lp.brk not in (0, False) else f"ln_{p}(x)"
        # return paths, last first
        for m in range(len(lp.returns) - 1, -1, -1):
            cnd, val = lp.returns[m]
            xi = next(q for q, (n, _l, _k) in enumerate(li.exits_extra) if n == ["return", m])
            c, kk = self.value(val, sc)
            sets = [(f"x{j}_{xi}", "r"), (f"rt{j}", f"w_u({m + 1})"), (f"cn{j}", self.gx(sc, f"it{j}")),
                    (f"ld{j}", "3n")]
            self.add(f"def lrr_{p}_{m}(+x: {X}) -> {X}:\n  +r = {{{self.store_value(c, kk, li.exits_extra[xi][2])} : {self.field_type(li.exits_extra[xi][2])}}}\n"
                     f"  {self.set_fields(sc, 'x', sets)}\n")
            self.add(f"def lr_{p}_{m}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      lrr_{p}_{m}(x)\n"
                     f"    case False{{}}:\n      {nxt_dec}\n")
            nxt_dec = f"lr_{p}_{m}({self.cond(cnd, sc)}, x)"
        self.add(f"def lc_{p}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      {self.sx(sc, f'ld{j}', 'x', '2n')}\n"
                 f"    case False{{}}:\n      {nxt_dec}\n")
        self.add(f"def lb_{p}(+x: {X}) -> {X}:\n  lc_{p}(u_nz({self.gx(sc, 'cd')}), x)\n")
        body_first = self.chain(lp.body, sc, f"lb_{p}")
        # the normal exit (the head failed): the count, the exit values of the names that are not carried
        lets, sets = [], []
        for k_, (n, e) in enumerate(lp.exits):
            xi = next((q for q, (nn, _l, _k) in enumerate(li.exits_extra) if canonical(nn) == canonical(n)), None)
            if xi is None:
                continue
            c, kk = self.value(e, sc)
            lets.append(f"  +e{k_} = {{{self.store_value(c, kk, li.exits_extra[xi][2])} : {self.field_type(li.exits_extra[xi][2])}}}")
            sets.append((f"x{j}_{xi}", f"e{k_}"))
        sets += [(f"cn{j}", self.gx(sc, f"it{j}")), (f"ld{j}", "0n")]
        self.add(f"def lx_{p}(+x: {X}) -> {X}:\n" + "\n".join(lets + [f"  {self.set_fields(sc, 'x', sets)}"]) + "\n")
        self.add(f"def lh_{p}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      {body_first}(x)\n"
                 f"    case False{{}}:\n      lx_{p}(x)\n")
        self.add(f"def li_{p}(+x: {X}) -> {X}:\n  lh_{p}({self.cond(lp.head, sc)}, x)\n")
        self.add(f"def lpz_{p}(d: Nat, +x: {X}) -> {X}:\n  match d:\n    case 0n:\n      x\n    case 1n+q:\n"
                 f"      match q:\n        case 0n:\n          xf_{ba}(x, {FUEL_CODE}, Nil{{}})\n"
                 f"        case 1n+s:\n          x\n")
        self.add(f"# {comment(f'loop {lp.src}: fuel f; d 0 exited (head false), 1 iterate, 2 a check failed, 3 exited (break or return)')}\n"
                 f"def lp_{p}(f: Nat, d: Nat, +x: {X}) -> {X}:\n  match f:\n    case 0n:\n      lpz_{p}(d, x)\n"
                 f"    case 1n+r:\n      match d:\n        case 0n:\n          x\n        case 1n+q:\n"
                 f"          match q:\n            case 0n:\n              +y = li_{p}(x)\n"
                 f"              lp_{p}(r, {self.gx(Scope(a, 'y'), f'ld{j}')}, y)\n            case 1n+s:\n              x\n")
        # the start: the carried names' entry values (evaluated before the loop), iteration 0
        lets, sets = [], []
        for idx, (n, e, _v) in enumerate(lp.carried):
            c, kk = self.value(e, sc)
            lets.append(f"  +v{idx} = {{{self.store_value(c, kk, li.carried[idx][2])} : {self.field_type(li.carried[idx][2])}}}")
            sets.append((f"c{j}_{idx}", f"v{idx}"))
        sets += [(f"it{j}", "w0()"), (f"cn{j}", "w0()"), (f"rt{j}", "w0()"), (f"ld{j}", "1n")]
        self.add(f"def ls_{p}(+x: {X}) -> {X}:\n" + "\n".join(lets + [f"  {self.set_fields(sc, 'x', sets)}"]) + "\n")
        self.add(f"def la_{ba}_{i}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      x\n"
                 f"    case False{{}}:\n      {nxt}(x)\n")
        run = f"la_{ba}_{i}(u_nz({self.gx(Scope(a, 'y'), 'cd')}), y)"
        self.add(f"def lg_{ba}_{i}(+x: {X}) -> {X}:\n  +y = lp_{p}(U32.to_nat({FUEL}), 1n, ls_{p}(x))\n  {run}\n")
        if lp.cond in (1, True):
            return f"lg_{ba}_{i}(x)"
        self.add(f"def lq_{ba}_{i}(c: Bool, +x: {X}) -> {X}:\n  match c:\n    case True{{}}:\n      lg_{ba}_{i}(x)\n"
                 f"    case False{{}}:\n      {nxt}(x)\n")
        return f"lq_{ba}_{i}({self.cond(lp.cond, sc)}, x)"


def _lab(n) -> str:
    if isinstance(n, list) and len(n) == 2 and n[0] == "storage":
        return f"storage.{n[1]}"
    return n if isinstance(n, str) else canonical(n)


# ================================================================================================ the sort section
def n1_sorts(sorts: dict, sites: list) -> list[str]:
    """N1: every family and parameter sort other than Nat (unrefined), Bool and Mach(w), every sign site's sort, every
    union member (the variables of E2 that are families, family members and parameters)."""
    out = set()
    for v, s in sorts.items():
        if v.startswith(("env:", "call:", "loop:", "$")):
            continue
        if s in ("Nat (unrefined)", "Bool") or str(s).startswith("Mach("):
            continue
        out.add(s)
    for s in sites:
        if s.get("obligation") == "sign":
            out.add(s["sort"])
    for s in list(out):
        p = G.parse(s)
        if p.head == "Union":
            out |= {G.render(m) for m in p.members}
    return sorted(out)


class Model3(Machine):
    def typed_section(self) -> list[str]:
        out = []
        sorts = sorted(self.types_used)
        for s in sorts:
            n = tname(s)
            if G.is_signed(G.parse(s)):
                out.append(f"type {n} is Data:\n  {n}{{ng: Bool, p: W}}\n")
                out.append(f"def pay_{n}(v: {n}) -> W:\n  match v:\n    case {n}{{ng, p}}:\n      p\n")
            else:
                out.append(f"type {n} is Data:\n  {n}{{p: W}}\n")
                out.append(f"def pay_{n}(v: {n}) -> W:\n  match v:\n    case {n}{{p}}:\n      p\n")
            out.append(f"def is_some_{n}(m: Maybe<&2, {n}>) -> Bool:\n  match m:\n    case None{{}}:\n      False{{}}\n"
                       f"    case Some{{v}}:\n      True{{}}\n")
        for s in sorts:
            ps = G.parse(s)
            n = tname(s)
            if ps.label:
                b = self.base_sort(s)
                out.append(f"# erase: the labelled sort {s} as its base {b} (total)\n"
                           f"def erase_{sname(s)}(+v: {n}) -> {tname(b)}:\n  {tname(b)}{{pay_{n}(v)}}\n")
            if G.is_signed(ps):
                u = G.render(G.unsigned(ps))
                tu = tname(u)
                out.append(f"def wrap_{n}(+v: {n}) -> {tu}:\n  {tu}{{pay_{n}(v)}}\n")
                out.append(f"def rzg_{n}(c: Bool, +p: W) -> Maybe<&2, {tu}>:\n  match c:\n    case True{{}}:\n"
                           f"      None{{}}\n    case False{{}}:\n      Some{{{tu}{{p}}}}\n")
                out.append(f"# realize (N3): None iff the signed value is negative\n"
                           f"def realize_{n}(v: {n}) -> Maybe<&2, {tu}>:\n  match v:\n    case {n}{{ng, p}}:\n"
                           f"      rzg_{n}(ng, p)\n")
        for name, o in sorted(self.ops.items()):
            a, b = o["args"]
            ta, tb, tr = tname(a), tname(b), tname(o["result"])
            pa, pb = f"pay_{ta}(a)", f"pay_{tb}(b)"
            if o["op"] in ("+", "-"):
                fn = "w_add" if o["op"] == "+" else "w_sub"
                if G.is_signed(G.parse(o["result"])):
                    if o["op"] != "-":
                        raise GenError(f"a typed {a} + {b} with a signed result")
                    body = f"{tr}{{w_lt({pa}, {pb}), {fn}({pa}, {pb})}}"
                else:
                    body = f"{tr}{{{fn}({pa}, {pb})}}"
                out.append(f"def {name}(+a: {ta}, +b: {tb}) -> {tr}:\n  {body}\n")
            else:
                out.append(f"def {name}(+a: {ta}, +b: {tb}) -> Bool:\n  {_RAW_CMP[o['op']](pa, pb)}\n")
        return out


# ================================================================================================ the ghost section
def _branch_cond(v, R) -> list | None:
    """The conditions under which a write's value is its branch R ([(cond, polarity)]), or None."""
    if v == R:
        return []
    if isinstance(v, list) and len(v) == 4 and v[0] == "?":
        for pol, br in ((True, v[2]), (False, v[3])):
            r = _branch_cond(br, R)
            if r is not None:
                return [(v[1], pol)] + r
    return None


class Ghost:
    """Below GHOST_MARKER: the generated companions (G1-G3), the augmented state, Reach, and the coercions of every I30
    law of the document (coerce_<x>, chit_<x>)."""

    def __init__(self, mm: Model3, basis):
        self.mm = mm
        self.b = basis
        self.out: list = []
        self.regs = sorted(basis.unions)
        self.members = sorted({G.render(x) for f in self.regs for x in G.parse(mm.sorts[f]).members})

    def comp(self, f: str) -> str:
        return "gc_" + bname(f)

    def comp_type(self, f: str) -> tuple[str, bool]:
        fam = f.partition(".")[0]
        t = self.mm.m.type_of(self.mm.m.family(fam).type)
        return ("List<&2, GKT>", True) if t.get("encoding") == "mapping" else ("Tag", False)

    def tag_code(self, tt, sc: Scope, g: str) -> str:
        from ..rules.sort import BOTTOM
        if tt == BOTTOM or tt is None:
            return "TG_bot{}"
        if isinstance(tt, list) and tt and tt[0] == "sort":
            if tt[1] not in self.members:
                return "TG_bot{}"
            return f"TG_{sname(tt[1])}{{}}"
        if isinstance(tt, list) and len(tt) == 4 and tt[0] == "?":
            return f"ite(Tag, {self.mm.cond(tt[1], sc)}, {self.tag_code(tt[2], sc, g)}, {self.tag_code(tt[3], sc, g)})"
        from .extracted import TAG_HEAD
        if isinstance(tt, list) and tt and tt[0] == TAG_HEAD:
            f, key = tt[1], tt[2]
            _ty, keyed = self.comp_type(f)
            if keyed:
                if key is None:
                    raise GenError(f"the companion of {f} read without a key")
                return f"gk_get(gh_get_{bname(f)}({g}), {self.mm.w(key, sc)})"
            return f"gh_get_{bname(f)}({g})"
        raise GenError(f"a tag term {canonical(tt)[:100]}")

    def effects(self, a: str) -> list:
        """(write, register, key term) of every write of a union register in a's program (G3)."""
        out = []
        for s in self.mm.m.program(a).records(Write):
            regs = [r for r in self.regs if r.partition(".")[0] == s.family]
            if not regs:
                continue
            for r in regs:
                mem = r.partition(".")[2]
                path = list(s.path)
                if mem:
                    if not path or path[-1][0] != "member" or path[-1][1] != mem:
                        if any(p[0] == "member" for p in path):
                            continue
                        raise GenError(f"{a}: a write of the whole struct of union member {r} ({s.src})")
                    path = path[:-1]
                if s.entry.get("loop") is not None:
                    raise GenError(f"{a}: a write of union register {r} inside a loop ({s.src}): its ghost effect is "
                                   "not compiled")
                if len(path) > 1 or (path and path[0][0] != "map"):
                    raise GenError(f"{a}: a write of union register {r} at a nested path ({s.src})")
                out.append((s, r, path[0][1] if path else None))
        return out

    def section(self, acts: list, elements: list) -> list[str]:
        mm, out = self.mm, []
        hs = ", ".join(f"+{'kh' if h == 'keccak256' else 'sh'}: List<&2, HKB>" for h in mm.hashes)
        hv = ", ".join("kh" if h == "keccak256" else "sh" for h in mm.hashes)
        out.append("type Tag is Data:\n  TG_bot{}\n" + "".join(f"  TG_{sname(m)}{{}}\n" for m in self.members))
        cases = []
        cons = ["TG_bot"] + [f"TG_{sname(m)}" for m in self.members]
        for x in cons:
            for y in cons:
                cases.append(f"    case {x}{{}} {y}{{}}:\n      {'True' if x == y else 'False'}{{}}\n")
        out.append("def tg_eq(a: Tag, b: Tag) -> Bool:\n  match a b:\n" + "".join(cases))
        out.append("type GKT is Data:\n  GKT{k: W, t: Tag}\n")
        out.append("def gk_get(+xs: List<&2, GKT>, +k: W) -> Tag:\n  match xs:\n    case Nil{}:\n      TG_bot{}\n"
                   "    case Con{+h, +t}:\n      match h:\n        case GKT{+hk, +ht}:\n"
                   "          ite(Tag, w_eq(hk, k), ht, gk_get(t, k))\n")
        out.append("def gk_set(+xs: List<&2, GKT>, +k: W, +v: Tag) -> List<&2, GKT>:\n  match xs:\n    case Nil{}:\n"
                   "      [GKT{k, v}]\n    case Con{+h, +t}:\n      match h:\n        case GKT{+hk, +ht}:\n"
                   "          ite(List<&2, GKT>, w_eq(hk, k), Con{GKT{k, v}, t}, Con{GKT{hk, ht}, gk_set(t, k, v)})\n")
        fs = [("st", "HSt")] + [(self.comp(f), self.comp_type(f)[0]) for f in self.regs]
        out.append("# the augmented state: the real store and the generated companion of every union register (G1)\n"
                   + _record("GSt", fs))
        out += [x.replace("def gh_get_gc_", "def gh_get_", 1) for x in _getters("gh_get_", "GSt", fs)]
        out += [x.replace("def gh_set_gc_", "def gh_set_", 1) for x in _setters("gh_set_", "GSt", fs)]
        init = ["s0()"] + ["Nil{}" if self.comp_type(f)[1] else "TG_bot{}" for f in self.regs]
        out.append(f"def gh_s0() -> GSt:\n  GSt{{{', '.join(init)}}}\n")
        # ghost steps (G3)
        for a in acts:
            ba = bname(a)
            X = mm.xt(a)
            eff = self.effects(a)
            sc = Scope(a)
            lines = []
            cur = "g"
            for n, (w, r, key) in enumerate(eff):
                tt = self.b.tagger.tg(w.value, a)
                tag = self.tag_code(tt, sc, "g")
                if self.comp_type(r)[1]:
                    newc = f"gk_set(gh_get_{bname(r)}({cur}), {mm.w(key, sc)}, {tag})"
                else:
                    newc = tag
                upd = f"gh_set_{bname(r)}({cur}, {newc})"
                cond = mm.cond(w.cond, sc) if w.cond not in (1, True) else None
                lines.append(f"  +g{n + 1} = {{{upd if cond is None else f'ite(GSt, {cond}, {upd}, {cur})'} : GSt}}")
                cur = f"g{n + 1}"
            out.append(f"def gh_eff_{ba}(+x: {X}, +g: GSt) -> GSt:\n" + "".join(l + "\n" for l in lines) + f"  {cur}\n")
            out.append(f"def gh_ok_{ba}(c: Bool, +x: {X}, +g: GSt) -> GSt:\n  match c:\n    case True{{}}:\n      g\n"
                       f"    case False{{}}:\n      gh_eff_{ba}(x, gh_set_st(g, gx_{ba}_ov(x)))\n")
            out.append(f"def gh_go_{ba}(+x: {X}, +g: GSt) -> GSt:\n  gh_ok_{ba}(u_nz(gx_{ba}_cd(x)), x, g)\n")
        cases = "".join(f"    case A_{bname(a)}{{ar, en}}:\n      gh_go_{bname(a)}(xr_{bname(a)}(gh_get_st(g), ar, en"
                        f"{', ' + hv if hv else ''}), g)\n" for a in acts)
        out.append(f"# one step of any action from an augmented state: the real step and its ghost effects\n"
                   f"def gh_step(a: HAct, +g: GSt{', ' + hs if hs else ''}) -> GSt:\n  match a:\n{cases}")
        idx = ", ".join(f"-{v}: List<&2, HKB>" for v in hv.split(", ")) if hv else ""
        ix = (hv + ", ") if hv else ""
        out.append(f"# the reachable augmented states: the deployment (R0) and one step of any action (RStep)\n"
                   f"type Reach<{idx + ', ' if idx else ''}-s: GSt> is Type:\n  R0{{e: {{s == gh_s0() : GSt}}}}\n"
                   f"  RStep{{a: HAct, p: GSt, r: Reach<{ix}p>, e: {{s == gh_step(a, p{', ' + hv if hv else ''}) : GSt}}}}\n")
        out.append(f"def run(tr: List<&2, HAct>, g: GSt{', ' + hs if hs else ''}) -> GSt:\n  match tr:\n    case Nil{{}}:\n"
                   f"      g\n    case Con{{a, rest}}:\n      run(rest, gh_step(a, g{', ' + hv if hv else ''}){', ' + hv if hv else ''})\n")
        # coercions
        made = set()
        for f in self.regs:
            u = mm.sorts[f]
            tu = tname(u)
            for m_ in G.parse(u).members:
                ms = G.render(m_)
                name = f"as_member_{sname(u)}_{sname(ms)}"
                if name in made:
                    continue
                made.add(name)
                tm = tname(ms)
                mm.coercions[name] = {"name": name, "kind": "as_member", "from": u, "to": ms}
                cs = "".join(f"    case {c}{{}}:\n      {'Some{' + tm + '{pay_' + tu + '(x)}}' if c == 'TG_' + sname(ms) else 'None{}'}\n"
                             for c in cons)
                out.append(f"# as_member (N4): Some iff the tag is {ms}\n"
                           f"def {name}(+x: {tu}, t: Tag) -> Maybe<&2, {tm}>:\n  match t:\n{cs}")
        for e in elements:
            if e["subform"] == "reinterpret":
                fr, to = e["basis"]["from"], e["basis"]["to"]
                name = f"reinterpret_{sname(fr)}_{sname(to)}"
                if name in made:
                    continue
                made.add(name)
                mm.T(fr), mm.T(to)
                mm.coercions[name] = {"name": name, "kind": "reinterpret", "from": fr, "to": to}
                tf, tt_ = tname(fr), tname(to)
                out.append(f"# reinterpret (N5): Some iff the payloads are equal\n"
                           f"def {name}(+x: {tf}, +c: {tt_}) -> Maybe<&2, {tt_}>:\n"
                           f"  ite(Maybe<&2, {tt_}>, w_eq(pay_{tf}(x), pay_{tt_}(c)), Some{{{tt_}{{pay_{tf}(x)}}}}, None{{}})\n")
        out.append(f"def rz_reached(+c: U32, +k: U32) -> Bool:\n  Bool.or(U32.is_eq(c, 0), Bool.and(U32.is_ge(c, k), "
                   f"U32.is_lt(c, {TOP_CODE})))\n")
        for e in elements:
            out += self.coerce(e, acts, hs, hv)
        return out

    def coerce(self, e: dict, acts: list, hs: str, hv: str) -> list[str]:
        from ..rules.sort import ghost_x
        mm = self.mm
        x = ghost_x(e["law_id"])
        out = []
        per: dict = {}
        for h in e["hits"]:
            per.setdefault(h["action"], []).append(h)
        bodies_c, bodies_h = {}, {}
        for a, hits in sorted(per.items()):
            ba = bname(a)
            X = mm.xt(a)
            sc = Scope(a)
            if e["subform"] == "realize":
                if all(h["kind"] == "realization_check" for h in hits):
                    ks = [mm.cidx_of(a, h["at"]) + 1 for h in hits]
                    okc = " ".join(f"Bool.and(Bool.not(U32.is_eq(c, {k})), " for k in ks) + "True{}" + ")" * len(ks)
                    hit = " ".join(f"Bool.or(rz_reached(c, {k}), " for k in ks) + "False{}" + ")" * len(ks)
                    out.append(f"def cz_{x}_{ba}(+c: U32) -> Bool:\n  {okc}\n")
                    out.append(f"def ch_{x}_{ba}(+c: U32) -> Bool:\n  {hit}\n")
                    bodies_c[a] = f"cz_{x}_{ba}(chk_{ba}(gh_get_st(g), ar, en{', ' + hv if hv else ''}))"
                    bodies_h[a] = f"ch_{x}_{ba}(chk_{ba}(gh_get_st(g), ar, en{', ' + hv if hv else ''}))"
                else:
                    # an unchecked site: its occurrences are reached when the action completes (every record runs)
                    s = e["site"]
                    d = mm.tx(s["expr"], sc)
                    if not d[1].startswith("t:") or not G.is_signed(G.parse(d[1][2:])):
                        raise GenError(f"{e['law_id']}: the site's difference is not a signed typed value")
                    ds = d[1][2:]
                    u = G.render(G.unsigned(G.parse(ds)))
                    hitc = f"Bool.not(u_nz(gx_{ba}_cd(x)))"
                    out.append(f"def cz_{x}_{ba}(+x: {X}) -> Bool:\n  Bool.or(Bool.not({hitc}), "
                               f"is_some_{tname(u)}(realize_{tname(ds)}({d[0]})))\n")
                    out.append(f"def ch_{x}_{ba}(+x: {X}) -> Bool:\n  {hitc}\n")
                    xr = f"xr_{ba}(gh_get_st(g), ar, en{', ' + hv if hv else ''})"
                    bodies_c[a], bodies_h[a] = f"cz_{x}_{ba}({xr})", f"ch_{x}_{ba}({xr})"
            elif e["subform"] == "as_member":
                b = e["basis"]
                w = e["write"]
                R = b["read"]
                f = e["family"]
                bc = _branch_cond(w["value"], R)
                if bc is None:
                    raise GenError(f"{e['law_id']}: the read is not a branch of the copy write")
                if w.get("loop") is not None:
                    raise GenError(f"{e['law_id']}: a copy write inside a loop")
                conds = [f"Bool.not(u_nz(gx_{ba}_cd(x)))"]
                if w.get("cond", 1) not in (1, True):
                    conds.append(mm.cond(w["cond"], sc))
                for ct, pol in bc:
                    cc = mm.cond(ct, sc)
                    conds.append(cc if pol else f"Bool.not({cc})")
                hitc = conds[-1]
                for c_ in reversed(conds[:-1]):
                    hitc = f"Bool.and({c_}, {hitc})"
                rv, rk = mm.value(R, sc)
                u = mm.sorts[f]
                tu = tname(u)
                if rk != "t:" + u:
                    rv = f"{tu}{{{mm.to_w(rv, rk)}}}"
                tag_r = self.tag_code(self.b.tagger.tg(R, a), sc, "g")
                member = self.tag_code(e["coercion"]["member_fn"], sc, "g")
                cases = "    case TG_bot{}:\n      False{}\n"
                for m_ in G.parse(u).members:
                    ms = G.render(m_)
                    cases += (f"    case TG_{sname(ms)}{{}}:\n      is_some_{tname(ms)}(as_member_{sname(u)}_{sname(ms)}"
                              f"(r, t))\n")
                out.append(f"def cm_{x}_{ba}(m: Tag, +r: {tu}, +t: Tag) -> Bool:\n  match m:\n{cases}")
                out.append(f"def cz_{x}_{ba}(+x: {X}, +g: GSt) -> Bool:\n  Bool.or(Bool.not({hitc}), "
                           f"cm_{x}_{ba}({member}, {rv}, {tag_r}))\n")
                out.append(f"def ch_{x}_{ba}(+x: {X}, +g: GSt) -> Bool:\n  {hitc}\n")
                xr = f"xr_{ba}(gh_get_st(g), ar, en{', ' + hv if hv else ''})"
                bodies_c[a], bodies_h[a] = f"cz_{x}_{ba}({xr}, g)", f"ch_{x}_{ba}({xr}, g)"
            else:   # reinterpret
                b = e["basis"]
                fr, to = b["from"], b["to"]
                reg = mm.value(["storage", b["register"]], sc)
                cur = mm.value(b["cursor"][a], sc)
                regc = reg[0] if reg[1] == "t:" + fr else f"{tname(fr)}{{{mm.to_w(*reg)}}}"
                curc = cur[0] if cur[1] == "t:" + to else f"{tname(to)}{{{mm.to_w(*cur)}}}"
                hitc = f"Bool.not(u_nz(gx_{ba}_cd(x)))"
                out.append(f"def cz_{x}_{ba}(+x: {X}) -> Bool:\n  Bool.or(Bool.not({hitc}), is_some_{tname(to)}"
                           f"(reinterpret_{sname(fr)}_{sname(to)}({regc}, {curc})))\n")
                out.append(f"def ch_{x}_{ba}(+x: {X}) -> Bool:\n  {hitc}\n")
                xr = f"xr_{ba}(gh_get_st(g), ar, en{', ' + hv if hv else ''})"
                bodies_c[a], bodies_h[a] = f"cz_{x}_{ba}({xr})", f"ch_{x}_{ba}({xr})"
        for kind, bodies, other in (("coerce", bodies_c, "True{}"), ("chit", bodies_h, "False{}")):
            cases = ""
            for a in acts:
                ba = bname(a)
                if a in bodies:
                    cases += f"    case A_{ba}{{ar, en}}:\n      {bodies[a]}\n"
                else:
                    cases += f"    case A_{ba}{{_, _}}:\n      {other}\n"
            doc = ("every hit of coercion " + e["coercion_id"] + " while the action runs from the state is Some (true "
                   "where the step reaches no hit)") if kind == "coerce" else \
                  ("the step reaches a hit of coercion " + e["coercion_id"])
            out.append(f"# {comment(doc)}\ndef {kind}_{x}(a: HAct, +g: GSt{', ' + hs if hs else ''}) -> Bool:\n"
                       f"  match a:\n{cases}")
        return out


# ================================================================================================ the untyped site form
def site_section(mm: Machine, acts: list, sites: list) -> list[str]:
    """I15's site form (holon.sorts.sites: the site's minuend >= subtrahend at every hit) of the given sites over the
    untyped machine: site_<x>(a, s, kh..) and hit_<x>(a, s, kh..), x from I15's law id rule."""
    from .sites import ghost_x as site_x, law_id as site_law_id
    out = []
    hs = ", ".join(f"+{'kh' if h == 'keccak256' else 'sh'}: List<&2, HKB>" for h in mm.hashes)
    hv = ", ".join("kh" if h == "keccak256" else "sh" for h in mm.hashes)
    real = None
    if sites:
        out.append(f"def rz_reached(+c: U32, +k: U32) -> Bool:\n  Bool.or(U32.is_eq(c, 0), Bool.and(U32.is_ge(c, k), "
                   f"U32.is_lt(c, {TOP_CODE})))\n")
    for s in sites:
        x = site_x(site_law_id(s["id"]))
        hits: dict = {}
        if not s.get("checked"):
            raise GenError(f"site {s['id']}: an unchecked site has no site form over the untyped machine")
        from . import extracted as XX
        real = real or XX.realization_checks(mm.m.doc)
        for a in s["entry_points"]:
            p = real.get((a, XX.ckey(s["expr"])))
            if p is None:
                continue
            for i, c in enumerate(mm.checks[a]):
                if c.section == "panics" and c.seq == p.get("seq"):
                    hits.setdefault(a, []).append(i + 1)
        cs, ch = "", ""
        for a in acts:
            ba = bname(a)
            ks = hits.get(a)
            if not ks:
                cs += f"    case A_{ba}{{_, _}}:\n      True{{}}\n"
                ch += f"    case A_{ba}{{_, _}}:\n      False{{}}\n"
                continue
            okc = " ".join(f"Bool.and(Bool.not(U32.is_eq(c, {k})), " for k in ks) + "True{}" + ")" * len(ks)
            hit = " ".join(f"Bool.or(rz_reached(c, {k}), " for k in ks) + "False{}" + ")" * len(ks)
            out.append(f"def gs_{x}_{ba}(+c: U32) -> Bool:\n  {okc}\n")
            out.append(f"def gh_{x}_{ba}(+c: U32) -> Bool:\n  {hit}\n")
            call = f"chk_{ba}(s, ar, en{', ' + hv if hv else ''})"
            cs += f"    case A_{ba}{{ar, en}}:\n      gs_{x}_{ba}({call})\n"
            ch += f"    case A_{ba}{{ar, en}}:\n      gh_{x}_{ba}({call})\n"
        out.append(f"# {comment('nonneg of ' + s['id'] + ': the minuend is at least the subtrahend at every hit')}\n"
                   f"def site_{x}(a: HAct, +s: HSt{', ' + hs if hs else ''}) -> Bool:\n  match a:\n{cs}")
        out.append(f"def hit_{x}(a: HAct, +s: HSt{', ' + hs if hs else ''}) -> Bool:\n  match a:\n{ch}")
    return out


# ================================================================================================ the model
def _env_record(mm: Machine) -> list[str]:
    fs = sorted({(f, ty) for f, ty, _k in mm.env_fields})
    keys = {f: k for f, _ty, k in mm.env_fields}
    if not fs:
        fs = [("e_none", "W")]
    doc = "".join(f"# HEnv.{f}: {keys[f]}\n" for f, _ty in fs if f in keys)
    return [doc + _record("HEnv", fs)] + _getters("ge_", "HEnv", fs)


def _arg_records(mm: Machine, acts: list) -> list[str]:
    out = []
    for a in acts:
        for p in mm.m.params(a) or []:
            mm.arg_type(p)
    for rec, fs in mm.records.items():     # struct parameters (in the order the ABI introduced them)
        ff = [(f, ty) for f, ty, _p in fs]
        out.append(_record(rec, ff))
        out += _getters(f"g_{rec}_", rec, ff)
    for a in acts:
        ba = bname(a)
        fs = [(bname(p["name"]), mm.arg_type(p)) for p in mm.m.params(a) or []]
        out.append(_record(f"AR_{ba}", fs) if fs else f"type AR_{ba} is Data:\n  AR_{ba}{{}}\n")
        out += _getters(f"ga_{ba}_", f"AR_{ba}", fs)
    return out


def s0_text(init: dict) -> str:
    items = [f"KW{{{wlit(k)}, {wlit(v)}}}" for k, v in sorted(init.items()) if v]
    return "def s0() -> HSt:\n  HSt{" + ("[" + ", ".join(items) + "]" if items else "Nil{}") + "}\n"


def build_text(m: ExtractedModel, *, typed: bool, sorts: dict, seeds: dict, init: dict, hashes: list, basis,
               site_rows: list, header: list[str]) -> tuple[str, Model3]:
    mm = Model3(m, typed=typed, sorts=sorts, seeds=seeds, init_storage=init, hashes=hashes)
    acts = sorted(a for a in m.actions if m.params(a) is not None)
    for a in acts:
        mm.compile_action(a)
    elements = basis.elements() if (typed and basis is not None) else []
    if typed:
        for s in n1_sorts(sorts, basis.sites if basis is not None else []):
            mm.T(s)
    ghost = []
    if typed:
        gh = Ghost(mm, basis)
        ghost = gh.section(acts, elements)       # (registers coercions and types before the sort section is written)
    parts = ["\n".join(header) + "\nimport Base\n", PRELUDE, _COMMON]
    parts += mm.shift_defs()
    if typed:
        parts += mm.typed_section()
    parts += _env_record(mm)
    parts += _arg_records(mm, acts)
    for a in acts:
        parts += mm.action_defs[a]
    hs = ", ".join(f"+{'kh' if h == 'keccak256' else 'sh'}: List<&2, HKB>" for h in hashes)
    hv = ", ".join("kh" if h == "keccak256" else "sh" for h in hashes)
    parts.append("# an action with its arguments and its environment (A-env: free per step)\ntype HAct is Data:\n"
                 + "".join(f"  A_{bname(a)}{{ar: AR_{bname(a)}, en: HEnv}}\n" for a in acts))
    parts.append(f"def step(a: HAct, +s: HSt{', ' + hs if hs else ''}) -> HSt:\n  match a:\n"
                 + "".join(f"    case A_{bname(a)}{{ar, en}}:\n      step_{bname(a)}(s, ar, en{', ' + hv if hv else ''})\n"
                           for a in acts))
    parts.append("# the initial state: the target's storage after the deployment of the binding (zero without one)\n"
                 + s0_text(init))
    if typed:
        parts.append(GHOST_MARKER + "\n")
        parts += ghost
    else:
        idx = ", ".join(f"-{v}: List<&2, HKB>" for v in hv.split(", ")) if hv else ""
        ix = (hv + ", ") if hv else ""
        parts.append(f"def run(tr: List<&2, HAct>, s: HSt{', ' + hs if hs else ''}) -> HSt:\n  match tr:\n"
                     f"    case Nil{{}}:\n      s\n    case Con{{a, rest}}:\n"
                     f"      run(rest, step(a, s{', ' + hv if hv else ''}){', ' + hv if hv else ''})\n")
        parts.append(f"# the reachable states: the deployment (R0) and one step of any action (RStep)\n"
                     f"type Reach<{idx + ', ' if idx else ''}-s: HSt> is Type:\n  R0{{e: {{s == s0() : HSt}}}}\n"
                     f"  RStep{{a: HAct, p: HSt, r: Reach<{ix}p>, e: {{s == step(a, p{', ' + hv if hv else ''}) : HSt}}}}\n")
        if site_rows:
            parts.append(SITE_MARKER + "\n")
            parts += site_section(mm, acts, site_rows)
    text = "\n".join(p.rstrip("\n") + "\n" for p in parts if p)
    return text, mm


# ================================================================================================ generate, CLI
def model_name(doc_rel: str) -> str:
    return Path(doc_rel).name[:-len(".json")] if doc_rel.endswith(".json") else Path(doc_rel).stem


def load_doc_model(root: Path, doc_rel: str, source: str | None):
    from ..machine import load_extracted
    return load_extracted(Path(root) / doc_rel, Path(root), source=(Path(root) / source) if source else None)


def ratio_sites(milestone: str, root: Path, assignment: dict, model: str) -> list:
    """The sites of the milestone's term-size sidecar (its ratio site) of this model: the untyped baseline's I15 site
    form (holon termsize)."""
    p = Path(root) / "spec" / milestone / "lib" / "term_size.json"
    if not p.is_file():
        return []
    sid = json.loads(p.read_text(encoding="utf-8")).get("ratio_site")
    return [s for s in assignment.get("sites") or [] if s.get("id") == sid and s.get("model") == model]


def generate(milestone: str, root: Path, doc_rel: str, *, typed: bool = True, sidecar: str | None = None,
             init: dict | None = None, assignment: dict | None = None) -> tuple[str, "Model3"]:
    """The typed (or untyped) model text of one document of a typed milestone, and its generator (types, ops,
    coercions)."""
    from ..rules.sort import DocBasis, hash_functions
    from .typed_sidecar import load as load_sidecar
    root = Path(root)
    sc = load_sidecar(milestone, root, sidecar)
    m = load_doc_model(root, doc_rel, sc.source(doc_rel))
    doc = m.doc
    model = model_name(doc_rel)
    if assignment is None:
        ap = root / "gen" / milestone / "sorts" / "assignment.json"
        if not ap.is_file():
            raise GenError(f"{ap.relative_to(root)} is missing: run `holon sorts --milestone {milestone}` first")
        assignment = json.loads(ap.read_text(encoding="utf-8"))
    mo = (assignment.get("models") or {}).get(model)
    if mo is None:
        raise GenError(f"the assignment has no model {model}")
    seeds = json.loads(sc.seeds.read_text(encoding="utf-8"))
    basis = DocBasis(doc_rel, doc, model, assignment, seeds)
    init = init or {"storage": {}}
    storage = {int(k, 16) if isinstance(k, str) else int(k): to_int(v) for k, v in (init.get("storage") or {}).items()}
    hashes = hash_functions(doc) or ["keccak256"]
    sha = hashlib.sha256((root / doc_rel).read_bytes()).hexdigest()
    kind = "typed: the sort section and the ghost section" if typed else "untyped: the sort section off"
    start = f"the deployment of {init.get('binding')}" if init.get("binding") else "the zero storage"
    header = [f"# GENERATED by holon.sorts.model3 from {doc_rel}; do not edit (fix the generator instead).",
              f"# facts_sha256: {sha}",
              f"# model_version: {MODEL3_VERSION} ({kind})",
              f"# assignment sorts_sha256: {assignment.get('sorts_sha256')}",
              f"# initial state: {start} ({len([v for v in storage.values() if v])} non-zero slots)",
              "# chk_<action>(st, ar, en, kh..): 0 when every check holds, k + 1 when check k is the first that fails;",
              f"#   {CALL_CODE} when an external call term reverted, {FUEL_CODE} when a loop ran past its fuel;",
              "# post_<action>, logs_<action>: its post-state and logs; step_<action>: the post-state when chk is 0, "
              "else st."]
    sites = [] if typed else ratio_sites(milestone, root, assignment, model)
    text, mm = build_text(m, typed=typed, sorts=mo.get("assignment") or {}, seeds=seeds, init=storage, hashes=hashes,
                          basis=basis, site_rows=sites, header=header)
    mm.basis = basis
    mm.n1 = n1_sorts(mo.get("assignment") or {}, basis.sites)
    mm.hashes = hashes
    return text, mm


def documents_of(milestone: str, root: Path, sidecar: str | None, facts: list | None = None) -> list[str]:
    from .typed_sidecar import load as load_sidecar, rel_of
    root = Path(root)
    if facts:
        return [rel_of((root / f) if not Path(f).is_absolute() else Path(f), root) for f in facts]
    sc = load_sidecar(milestone, root, sidecar)
    return [rel_of(p, root) for p in sc.documents]


def init_of(milestone: str, root: Path, sidecar: str | None, doc_rel: str) -> dict:
    """The model's initial state: the deployment of the sidecar's binding (holon.sorts.deploy3), else zero."""
    from .typed_sidecar import load as load_sidecar
    sc = load_sidecar(milestone, root, sidecar)
    if not sc.binding:
        return {"binding": None, "storage": {}, "preimages": []}
    from . import deploy3
    return deploy3.deployment(Path(root), sc.binding, doc_rel)


def importable(name: str) -> str:
    """The file name Bend can import a model under: the pinned checker's import paths are plain names (letters,
    digits, _ and -), so a model named after its document (morph_rollup.extracted) is written as
    morph_rollup_extracted.bend, and <name>.bend is a symbolic link to it (one file, two names)."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) + ".bend"


def write_model_file(out: Path, name: str, text: str) -> Path:
    """Write the model under its importable name and link <name>.bend to it; returns the <name>.bend path."""
    import os
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    plain = out / importable(name)
    if not plain.is_file() or plain.read_text(encoding="utf-8") != text:
        plain.write_text(text, encoding="utf-8")
    link = out / f"{name}.bend"
    if link.name != plain.name:
        if link.is_symlink() and os.readlink(link) == plain.name:
            return link
        if link.exists() or link.is_symlink():
            link.unlink()
        os.symlink(plain.name, link)
    return link


def write_models(milestone: str, root: Path, out: Path, *, typed: bool = True, sidecar: str | None = None,
                 facts: list | None = None) -> list[Path]:
    root = Path(root)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for rel in documents_of(milestone, root, sidecar, facts):
        init = init_of(milestone, root, sidecar, rel)
        text, _mm = generate(milestone, root, rel, typed=typed, sidecar=sidecar, init=init)
        name = model_name(rel)
        p = write_model_file(out, name, text)
        (out / f"{name}.init.json").write_text(json.dumps(init, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                                               encoding="utf-8")
        written.append(p)
    return written


def main(argv=None) -> int:
    import argparse
    import sys
    ap = argparse.ArgumentParser(prog="holon model", description="the M3 model of a typed milestone's documents")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root")
    ap.add_argument("--sidecar")
    ap.add_argument("--facts", action="append")
    ap.add_argument("--untyped", action="store_true")
    ap.add_argument("--out", required=True)
    ap.add_argument("--check", action="store_true", help="run Bend on each written model")
    a = ap.parse_args(argv)
    from .. import machine as _m
    root = Path(a.root).resolve() if a.root else _m.ROOT
    out = Path(a.out)
    out = out if out.is_absolute() else Path.cwd() / out
    try:
        ps = write_models(a.milestone, root, out, typed=not a.untyped, sidecar=a.sidecar, facts=a.facts)
    except (GenError, ModelError, OSError, ValueError) as e:
        print(f"holon model: {e}", file=sys.stderr)
        return 2 if isinstance(e, GenError) else 1
    for p in ps:
        print(f"wrote {p}")
    if a.check:
        from .. import bend
        for p in ps:
            r = bend.check(p)
            print(f"{p.name}: {r.first_line}")
            if not r.ok:
                return 1
    return 0
