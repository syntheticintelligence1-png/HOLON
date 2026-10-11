"""QF_UFBV encoding of a codec law's negation (whitepaper §10.5, engine row 1).

The encoding mirrors `holon/gen/model.py` exactly, so the query asks z3 the
same question the Bend model answers:

  * a byte is a 16-bit bit-vector; a value outside 0..255 (57005 = 0xDEAD)
    marks an undefined result, matching the model's U32 convention;
  * a `List<&2, U32>` is a (cells, length) pair: a fixed-capacity list of
    byte expressions plus a 16-bit length; cells past `length` are don't-care
    and are masked out of every comparison;
  * `Fields` is a (items, count) pair of byte-lists; `MaybeFields` adds a
    `present` flag;
  * version dispatch becomes a z3 `If` chain over the version byte, the same
    0n..Kn, (K+1)n+p split the generator emits;
  * a `Bytes` binder is a length variable bounded by `cap` (recorded in every
    result — a bound, never silently extended); a `Header` binder is one byte
    variable per record cell, which is the binder's whole (finite) domain;
  * premises are applied as constraints (`collect_pins`), and the query also
    asserts `refute.in_domain`'s rule: a `Header` binder may not carry a
    version above a called encoder's `domain.version_le` — outside it the
    call reverts and the input is not a witness.

Only bit-vector equality/order, ITE and fresh constants are used: pure
QF_UFBV. The solver is z3; its name and version go into every record.
"""
from __future__ import annotations

import z3
from dataclasses import dataclass, field

from .. import facts as F
from .. import refute
from ..gen import laws as LG
from ..gen import model as G

BV16 = 16                     # cell width: 0..255 defined, 57005 undefined
UNDEF = F.UNDEF               # 0xDEAD, the model's undefined marker
SEED = 20261011               # smt.random_seed, fixed for determinism
TIMEOUT_MS = 60_000


def solver_info() -> dict:
    return {"name": "z3", "version": z3.get_version_string(), "logic": "QF_UFBV"}


def _c(v: int):
    return z3.BitVecVal(v, BV16)


def _ule(a, b):
    b = b if z3.is_expr(b) else _c(b)
    return z3.ULE(a, b)



@dataclass
class BL:                     # List<&2, U32>: capacity cells + a length
    cells: list
    length: object            # z3 expr or int

    def len_e(self):
        return self.length if z3.is_expr(self.length) else _c(self.length)


@dataclass
class FIELDS:                 # List of byte-lists
    items: list               # of BL
    count: object             # z3 expr or int

    def count_e(self):
        return self.count if z3.is_expr(self.count) else _c(self.count)


@dataclass
class MAYBE:
    present: object           # z3 Bool
    fields: FIELDS


@dataclass
class Binder:
    name: str
    type: str                 # "Header" | "Bytes"
    value: object             # dict cell->expr (Header) or BL (Bytes)
    length_var: object = None


@dataclass
class Query:
    solver: object
    binders: list             # of Binder
    cap: int                  # Bytes length bound used
    negation: object          # the asserted disequality
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- list ops (mirroring the generated model)
def lit(bs: list[int]) -> BL:
    return BL([_c(x) for x in bs], len(bs))


def zeros(n: int) -> BL:
    return lit([0] * n)


def replicate(v: int, n: int) -> BL:
    return lit([v] * n)


def put(mem: BL, off: int, bs: list) -> BL:
    """put(mem, off, bs): writes bs at off, keeps mem's length (writes past the end drop)."""
    cells = list(mem.cells)
    for i, c in enumerate(bs):
        if off + i < len(cells):
            cells[off + i] = c
    return BL(cells, mem.length)


def take(b: BL, n: int) -> BL:
    cells = b.cells[:n]
    return BL(cells, z3.If(_ule(b.len_e(), n), b.len_e(), _c(n)))


def drop(b: BL, n: int) -> BL:
    cells = b.cells[n:]
    return BL(cells, z3.If(z3.UGE(b.len_e(), n), b.len_e() - n, _c(0)))


def slice_(b: BL, off: int, w: int) -> BL:
    return take(drop(b, off), w)


def _pad(cells: list, n: int):
    return cells + [_c(0)] * max(0, n - len(cells))


def eq_blist(a: BL, b: BL):
    n = max(len(a.cells), len(b.cells))
    ca, cb = _pad(a.cells, n), _pad(b.cells, n)
    # compare exactly the live cells: i < length (cells past the length are don't-care)
    return z3.And(a.len_e() == b.len_e(),
                  *[z3.Implies(z3.ULT(_c(i), a.len_e()), ca[i] == cb[i]) for i in range(n)])


def eq_fields(a: FIELDS, b: FIELDS):
    n = max(len(a.items), len(b.items))
    dummy = BL([_c(0)], 1)
    ia = a.items + [dummy] * max(0, n - len(a.items))
    ib = b.items + [dummy] * max(0, n - len(b.items))
    return z3.And(a.count_e() == b.count_e(),
                  *[z3.Implies(z3.ULT(_c(i), a.count_e()), eq_blist(ia[i], ib[i])) for i in range(n)])


def eq_maybe(a: MAYBE, b: MAYBE):
    return z3.And(a.present == b.present, z3.Implies(a.present, eq_fields(a.fields, b.fields)))


def eq_value(kind: str, a, b):
    if kind == "bool":
        return a == b
    if kind == "blist":
        return eq_blist(a, b)
    if kind == "fields":
        return eq_fields(a, b)
    if kind == "maybe":
        return eq_maybe(a, b)
    raise LG.Unsupported(f"equality over {kind}")


# ---------------------------------------------------------------- rule values (mirroring gen.model._rule_value)
def _first_rule(fn: str, rules: list, empty: bool, version: int | None) -> dict:
    for r in rules:
        c = r["if"]
        if c == "otherwise":
            return r
        if c == "empty":
            if empty:
                return r
            continue
        if not empty and set(c) == {"version_in"} and version in c["version_in"]:
            return r
        if set(c) != {"version_in"}:
            raise LG.Unsupported(f"{fn}: unsupported rule condition {c}")
    raise LG.Unsupported(f"{fn}: rules are not exhaustive")


def _rule_val(fn: str, then, length) -> object:
    """Bool value of a predicate rule at byte-string length `length` (= len(t)+1)."""
    if isinstance(then, bool):
        return then
    if set(then) == {"len_ge"}:
        k = then["len_ge"]
        return True if k <= 1 else z3.UGE(length, k)
    if set(then) == {"len_eq"}:
        k = then["len_eq"]
        return False if k == 0 else length == k
    raise LG.Unsupported(f"{fn}: unsupported rule result {then}")


# ---------------------------------------------------------------- fact functions
def _field_cells(hdr: dict, facts: dict, name: str) -> list:
    return [hdr[f"{name}_{k}"] for k in range(F.widths(facts)[name])]


def _src_cells(src: list, hdr: dict, facts: dict) -> list:
    out = []
    for item in src:
        if "field" in item:
            out.extend(_field_cells(hdr, facts, item["field"]))
        elif "zeros" in item:
            out.extend([_c(0)] * item["zeros"])
        elif "const" in item:
            out.append(_c(item["const"]))
        else:
            raise LG.Unsupported(f"unsupported op source {item}")
    return out


def call_fn(fn: str, arg, facts: dict):
    f = facts["functions"].get(fn)
    if f is None:
        raise LG.Unsupported(f"unknown function {fn}")
    kind = f["kind"]
    if kind == "encoder":
        return enc_encoder(fn, f, arg, facts)
    if kind == "predicate":
        return enc_predicate(fn, f, arg, facts)
    if kind == "decoder":
        return enc_decoder(fn, f, arg, facts)
    if kind == "projection":
        return enc_projection(fn, f, arg, facts)
    raise LG.Unsupported(f"function kind {kind}")


def enc_encoder(fn: str, f: dict, hdr: dict, facts: dict) -> BL:
    if not isinstance(hdr, dict):
        raise LG.Unsupported(f"{fn}: encoder argument is not a Header binder")
    w = F.widths(facts)
    if f["lang"] == "go-bytes":
        mem = zeros(f["length"])
        for op in f["ops"]:
            if op.get("when"):
                raise LG.Unsupported(f"{fn}: version-conditional op in a version-independent encoder")
            cells = _src_cells(op["src"], hdr, facts)
            F.check_op_width(fn, op, len(cells))
            mem = put(mem, op["offset"], cells)
        return mem
    if f["lang"] != "solidity-evm-memory":
        raise LG.Unsupported(f"{fn}: unsupported encoder language {f['lang']}")
    versions = F.encoder_versions(f)
    size = F.evm_memory_size(f, w)
    per_v = {}
    for v in versions:
        mem = replicate(UNDEF, size)
        for op in f["ops"]:
            if not F.when_ok(op.get("when"), v):
                continue
            cells = _src_cells(op["src"], hdr, facts)
            F.check_op_width(fn, op, len(cells))
            mem = put(mem, op["offset"], cells)
        per_v[v] = take(mem, f["length_by_version"][str(v)])
    v0 = hdr["version_0"]
    maxlen = max(len(per_v[v].cells) for v in versions)
    # fold Ifs over the version byte; outside the domain the call reverts: [UNDEF]
    cells = [_c(UNDEF)] * maxlen
    length = _c(1)
    for v in reversed(versions):
        body = _pad(per_v[v].cells, maxlen)
        cells = [z3.If(v0 == v, body[i], cells[i]) for i in range(maxlen)]
        length = z3.If(v0 == v, per_v[v].len_e(), length)
    return BL(cells, length)


def enc_predicate(fn: str, f: dict, b: BL, _facts: dict):
    if not isinstance(b, BL):
        raise LG.Unsupported(f"{fn}: predicate argument is not a Bytes term")
    rules = f["rules"]
    empty = _first_rule(fn, rules, True, None)
    if not isinstance(empty["then"], bool):
        raise LG.Unsupported(f"{fn}: the empty-input rule must be a constant")
    if not b.cells:                      # a statically empty input: only the empty rule
        return empty["then"]
    k = G.max_version_const(rules)
    tail = _rule_val(fn, _first_rule(fn, rules, False, k + 1)["then"], b.len_e())
    val = tail
    for v in reversed(range(k + 1)):
        r = _first_rule(fn, rules, False, v)
        val = z3.If(b.cells[0] == v, _rule_val(fn, r["then"], b.len_e()), val)
    return z3.If(b.len_e() == 0, empty["then"], val)


def _dispatch(v0, per_v: dict, k: int):
    """If chain over the version byte: exact cases 0..k, tail = per_v[k + 1]."""
    def e(x):
        return x if z3.is_expr(x) else _c(int(x))
    val = e(per_v[k + 1])
    for v in reversed(range(k + 1)):
        val = z3.If(v0 == v, e(per_v[v]), val)
    return val


def enc_decoder(fn: str, f: dict, b: BL, facts: dict) -> MAYBE:
    if not isinstance(b, BL):
        raise LG.Unsupported(f"{fn}: decoder argument is not a Bytes term")
    getters = f["getters"]
    k = max([g.get("when", {}).get("version_ge", 0) for g in getters] + [0])
    guard = f.get("guard")
    if guard is None:
        raise LG.Unsupported(f"{fn}: decoder without a guard")
    if not b.cells:                      # statically empty: fields are Nil{}
        return MAYBE(call_fn(guard, b, facts), FIELDS([], 0))
    per_items, per_count = {}, {}
    for v in range(k + 2):
        gs = [g for g in getters if F.when_ok(g.get("when"), v)]
        per_items[v] = [slice_(b, g["offset"], g["width"]) for g in gs]
        per_count[v] = len(gs)
    n = max(per_count.values())
    dummy = BL([_c(0)], 1)
    b0 = b.cells[0]
    items = []
    for i in range(n):
        per = {v: (per_items[v][i] if i < len(per_items[v]) else dummy) for v in per_items}
        maxw = max(len(per[v].cells) for v in per)
        items.append(BL([_dispatch(b0, {v: _pad(per[v].cells, maxw)[j] for v in per}, k)
                         for j in range(maxw)],
                        _dispatch(b0, {v: per[v].len_e() for v in per}, k)))
    count = _dispatch(b0, per_count, k)
    # `dec_fields(b)`: the model returns Nil{} on an empty input.
    count = z3.If(b.len_e() == 0, _c(0), count)
    present = call_fn(guard, b, facts)
    return MAYBE(present, FIELDS(items, count))


def enc_projection(fn: str, f: dict, hdr: dict, facts: dict) -> FIELDS:
    if not isinstance(hdr, dict):
        raise LG.Unsupported(f"{fn}: projection argument is not a Header binder")
    w = F.widths(facts)
    when = f.get("when", {})
    k = max([when.get(n, {}).get("version_ge", 0) for n in f["order"]] + [0])
    per_items, per_count = {}, {}
    for v in range(k + 2):
        names = [n for n in f["order"] if F.when_ok(when.get(n), v)]
        per_items[v] = [BL(_field_cells(hdr, facts, n), w[n]) for n in names]
        per_count[v] = len(names)
    n = max(per_count.values())
    dummy = BL([_c(0)], 1)
    v0 = hdr["version_0"]
    items = []
    for i in range(n):
        per = {v: (per_items[v][i] if i < len(per_items[v]) else dummy) for v in per_items}
        maxw = max(len(per[v].cells) for v in per)
        items.append(BL([_dispatch(v0, {v: _pad(per[v].cells, maxw)[j] for v in per}, k)
                         for j in range(maxw)],
                        _dispatch(v0, {v: per[v].len_e() for v in per}, k)))
    return FIELDS(items, _dispatch(v0, per_count, k))


# ---------------------------------------------------------------- terms and binders
def enc_term(t: dict, env: dict, types: dict, facts: dict):
    """(kind, value): kind in hdr | blist | bool | fields | maybe."""
    if "var" in t:
        v = env[t["var"]]
        return ("hdr", v) if types[t["var"]] == "Header" else ("blist", v)
    if "bytes" in t:
        return "blist", lit(LG.hexbytes(t["bytes"]))
    if "field" in t:
        k, of = enc_term(t["of"], env, types, facts)
        if k != "hdr":
            raise LG.Unsupported(f"field projection off a non-Header term {t}")
        return "blist", BL(_field_cells(of, facts, t["field"]), F.widths(facts)[t["field"]])
    if "call" in t:
        fn = t["call"]
        f = facts["functions"].get(fn)
        if f is None:
            raise LG.Unsupported(f"unknown function {fn}")
        if len(t["args"]) != 1:
            raise LG.Unsupported(f"{fn}: {len(t['args'])}-ary call")
        _, arg = enc_term(t["args"][0], env, types, facts)
        arg_t, res_t = F.fn_types(facts, fn)
        val = call_fn(fn, arg, facts)
        return {"Bytes": "blist", "Bool": "bool", "Fields": "fields", "MaybeFields": "maybe"}[res_t], val
    if "some" in t:
        k, inner = enc_term(t["some"], env, types, facts)
        if k != "fields":
            raise LG.Unsupported(f"Some over a non-Fields term {t}")
        return "maybe", MAYBE(True, inner)
    raise LG.Unsupported(f"term {t}")


def byte_cap(law: dict, facts: dict) -> int:
    """Length bound for Bytes binders: one past every constant the claim can reach."""
    ks = set()

    def walk(t):
        if "call" in t:
            f = facts["functions"].get(t["call"], {})
            for r in f.get("rules", []):
                if isinstance(r["then"], dict):
                    ks.update(int(v) for v in r["then"].values())
            if "length" in f:
                ks.add(int(f["length"]))
            ks.update(int(v) for v in f.get("length_by_version", {}).values())
            for g in f.get("getters", []):
                ks.add(g["offset"] + g["width"])
            if f.get("guard") and f["guard"] in facts["functions"]:
                walk({"call": f["guard"], "args": []})
            for a in t["args"]:
                walk(a)

    a, b = law["statement"]["claim"]["eq"]
    walk(a)
    walk(b)
    return max(ks, default=0) + 2


def encode(law: dict, facts: dict, cap: int | None = None) -> Query:
    """The solver query for the law's negation, or LG.Unsupported."""
    if "forall" not in law["statement"]:
        raise LG.Unsupported("statement has no forall binders (not the codec ir/0.1 form)")
    types = LG.binder_types(law)                 # raises Unsupported on a foreign binder
    pins = LG.collect_pins(law, facts)           # raises Unsupported on a foreign premise
    claim = law["statement"]["claim"]
    if set(claim) != {"eq"}:
        raise LG.Unsupported("only eq claims exist in the codec fragment")
    a, b = claim["eq"]
    ta, tb = LG.type_of(a, types, facts), LG.type_of(b, types, facts)
    if ta != tb:
        raise LG.Unsupported(f"claim sides have different types {ta} / {tb}")
    cap = cap if cap is not None else byte_cap(law, facts)

    s = z3.Solver()
    s.set("random_seed", SEED)
    s.set("timeout", TIMEOUT_MS)
    env, binders = {}, []
    for bnd in law["statement"]["forall"]:
        name, ty = bnd["name"], bnd["type"]
        if ty == "Header":
            cells = {}
            for f_ in F.header_fields(facts):
                for k in range(f_["width"]):
                    x = z3.BitVec(f"{name}.{f_['name']}_{k}", BV16)
                    s.add(_ule(x, 255))
                    cells[f"{f_['name']}_{k}"] = x
            env[name] = cells
            binders.append(Binder(name, ty, cells))
        elif ty == "Bytes":
            n = z3.BitVec(f"{name}.len", BV16)
            s.add(_ule(n, cap))
            cells = [z3.BitVec(f"{name}.{k}", BV16) for k in range(cap)]
            for x in cells:
                s.add(_ule(x, 255))
            env[name] = BL(cells, n)
            binders.append(Binder(name, ty, env[name], n))
        else:
            raise LG.Unsupported(f"binder type {ty}")
    for var, fields in pins.items():            # premises, exactly as pinning does
        for fname, val in fields.items():
            for k, x in enumerate(val):
                s.add(env[var][f"{fname}_{k}"] == x)
    for var, vmax in refute.called_domains(law, facts):  # the _in_domain restriction
        if var in env and isinstance(env[var], dict) and "version" in pins.get(var, {}):
            continue
        if var in env and isinstance(env[var], dict):
            s.add(_ule(env[var]["version_0"], vmax))
    ka, va = enc_term(a, env, types, facts)
    kb, vb = enc_term(b, env, types, facts)
    kind = {"Bytes": "blist", "Bool": "bool", "Fields": "fields", "MaybeFields": "maybe"}.get(ta)
    if kind is None or ka != kind or kb != kind:
        raise LG.Unsupported(f"claim type {ta}")
    neg = z3.Not(eq_value(kind, va, vb))
    s.add(neg)
    return Query(s, binders, cap, neg)


def extract(model: z3.ModelRef, q: Query, facts: dict) -> dict:
    """Canonical-JSON witness (the shape refute/PG.literal expect)."""
    env = {}
    for bnd in q.binders:
        if bnd.type == "Header":
            h = {}
            for f_ in F.header_fields(facts):
                n, w_ = f_["name"], f_["width"]
                h[n] = "0x" + bytes(model.eval(bnd.value[f"{n}_{k}"]).as_long()
                                    for k in range(w_)).hex()
            env[bnd.name] = h
        else:
            n = model.eval(bnd.length_var).as_long()
            env[bnd.name] = "0x" + bytes(model.eval(c).as_long() for c in bnd.value.cells[:n]).hex()
    return env
