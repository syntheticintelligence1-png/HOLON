"""facts/*.json -> Bend source of the model (M0_SPEC section 4, prompts/P2).

Generated defs share the facts function names: encoders, predicates, the
decoder and the projection. One U32 per byte; dirty EVM memory is 57005.
"""
from __future__ import annotations

from .facts import header_fields, when_ok

BYTE_LIST = "List<&2, U32>"
FIELDS = "List<&2, List<&2, U32>>"
MAYBE_FIELDS = "Maybe<&2, List<&2, List<&2, U32>>>"

_OP_WIDTH = {"mstore": 32, "mstore8": 1, "set_byte": 1, "put_uint64_be": 8}

_TO_BEND = {"Bytes": BYTE_LIST, "Bool": "Bool", "Fields": FIELDS, "Maybe<Fields>": MAYBE_FIELDS}


def field_names(facts: dict) -> list[str]:
    return [f"{f['name']}_{k}" for f in header_fields(facts) for k in range(f["width"])]


def _hdr_pat(names, plus=True):
    p = "+" if plus else ""
    return "Hdr{" + ", ".join(p + n for n in names) + "}"


def _src_list(item, w):
    out = []
    if "field" in item:
        out.extend(f"{item['field']}_{k}" for k in range(w[item["field"]]))
    elif "zeros" in item:
        out.extend("0" for _ in range(item["zeros"]))
    else:
        out.append(str(item["const"]))
    return out


def _emit_encoder(lines, facts, name, f):
    a = lines.append
    names = field_names(facts)
    w = {x["name"]: x["width"] for x in header_fields(facts)}
    if f["lang"] == "go-bytes":
        mem = [f"zeros({f['length']}n)"]
        a(f"def {name}(+h: Hdr) -> {BYTE_LIST}:")
        a(f"  match h:")
        a(f"    case {_hdr_pat(names)}:")
        _emit_ops(a, f, f["ops"], None, mem)
        return
    if f["lang"] != "solidity-evm-memory":
        raise ValueError(f["lang"])
    # EVM: dispatch on version to per-version bodies.
    lbv = {int(k): v for k, v in f["length_by_version"].items()}
    mem_size = max(list(lbv.values()) + [op["offset"] + _OP_WIDTH[op["op"]] for op in f["ops"]])
    groups = {}  # (ops tuple, length) -> [versions]
    for v in sorted(lbv):
        ops = tuple(i for i, op in enumerate(f["ops"]) if when_ok(op.get("when"), v))
        groups.setdefault((ops, lbv[v]), []).append(v)
    bodies = {}  # version -> body def name
    for gi, ((ops, length), vs) in enumerate(sorted(groups.items(), key=lambda kv: kv[1][0])):
        bname = f"{name}_b{'_'.join(str(v) for v in vs)}"
        for v in vs:
            bodies[v] = bname
    vmax = max(lbv)
    for (ops, length), vs in sorted(groups.items(), key=lambda kv: kv[1][0]):
        bname = bodies[vs[0]]
        a(f"def {bname}(+h: Hdr) -> {BYTE_LIST}:")
        a(f"  match h:")
        a(f"    case {_hdr_pat(names)}:")
        mem = [f"List.replicate(U32, {mem_size}n, 57005)"]
        _emit_ops(a, f, [f["ops"][i] for i in ops], length, mem)
        a("")
    a(f"def {name}_at(v: Nat, +h: Hdr) -> {BYTE_LIST}:")
    a(f"  match v:")
    for v in range(vmax + 1):
        target = bodies.get(v)
        a(f"    case {v}n:")
        a(f"      {target}(h)" if target else "      Nil{}")
    a(f"    case {vmax + 1}n+p:")
    a(f"      Nil{{}}")
    a("")
    a(f"def {name}(+h: Hdr) -> {BYTE_LIST}:")
    a(f"  match h:")
    a(f"    case {_hdr_pat(names)}:")
    a(f"      {name}_at(U32.to_nat(version_0), h)")
    return


def _emit_ops(a, f, ops, take_len, mem):
    """Emit m0/m1/.. put chain; last line returns the output list."""
    indent = "      "
    a(f"{indent}m0 = {mem[0]}")
    for i, op in enumerate(ops):
        src = []
        for item in op["src"]:
            src.extend(_src_list(item, {x["name"]: x["width"] for x in _cur_fields}))
        a(f"{indent}m{i + 1} = put(m{i}, {op['offset']}n, [{', '.join(src)}])")
    last = f"m{len(ops)}"
    if take_len is None:
        a(f"{indent}{last}")
    else:
        a(f"{indent}List.take(&2, U32, {last}, {take_len}n)")


_cur_fields = []


def _emit_predicate(lines, facts, name, f):
    a = lines.append
    rules = f["rules"]
    empty_then = False
    otherwise = False
    vmap = {}
    vmax = -1
    for rule in rules:
        cond, then = rule["if"], rule["then"]
        if cond == "empty":
            empty_then = bool(then)
        elif cond == "otherwise":
            otherwise = then
        else:
            for v in cond["version_in"]:
                vmax = max(vmax, v)
                if v not in vmap:
                    vmap[v] = then

    def then_expr(then):
        if isinstance(then, bool):
            return "True{}" if then else "False{}"
        if "len_ge" in then:
            return f"Nat.is_ge(n, {then['len_ge']}n)"
        if "len_eq" in then:
            return f"Nat.is_eq(n, {then['len_eq']}n)"
        raise ValueError(then)

    a(f"def {name}_v(v: Nat, n: Nat) -> Bool:")
    a(f"  match v:")
    for v in range(vmax + 1):
        a(f"    case {v}n:")
        a(f"      {then_expr(vmap[v]) if v in vmap else then_expr(otherwise)}")
    a(f"    case {vmax + 1}n+p:")
    a(f"      {then_expr(otherwise)}")
    a("")
    a(f"def {name}(+b: {BYTE_LIST}) -> Bool:")
    a(f"  match b:")
    a(f"    case Nil{{}}:")
    a(f"      {'True{}' if empty_then else 'False{}'}")
    a(f"    case Con{{+h0, +t}}:")
    a(f"      {name}_v(U32.to_nat(h0), 1n+List.length(&2, U32, t))")
    a("")


def _emit_decoder(lines, facts, name, f):
    a = lines.append
    guard = f["guard"]
    getters = f["getters"]
    thresholds = sorted({g["when"]["version_ge"] for g in getters if g.get("when")})
    k = max(thresholds) if thresholds else 0
    a(f"def {name}_fields(v: Nat, +b: {BYTE_LIST}) -> {FIELDS}:")
    a(f"  match v:")
    for v in range(k + 1):
        a(f"    case {v}n:")
        a(f"      {_getter_list(getters, v)}")
    if k:
        a(f"    case {k + 1}n+p:")
        a(f"      {_getter_list(getters, k + 1)}")
    else:
        a(f"    case 1n+p:")
        a(f"      {_getter_list(getters, 1)}")
    a("")
    a(f"def {name}_h(vh: {BYTE_LIST}, +b: {BYTE_LIST}) -> {MAYBE_FIELDS}:")
    a(f"  match vh:")
    a(f"    case Nil{{}}:")
    a(f"      None{{}}")
    a(f"    case Con{{+v0, +t}}:")
    a(f"      Some{{{name}_fields(U32.to_nat(v0), b)}}")
    a("")
    a(f"def {name}_g(g: Bool, +b: {BYTE_LIST}) -> {MAYBE_FIELDS}:")
    a(f"  match g:")
    a(f"    case True{{}}:")
    a(f"      {name}_h(List.take(&2, U32, b, 1n), b)")
    a(f"    case False{{}}:")
    a(f"      None{{}}")
    a("")
    a(f"def {name}(+b: {BYTE_LIST}) -> {MAYBE_FIELDS}:")
    a(f"  {name}_g({guard}(b), b)")
    a("")


def _getter_list(getters, version):
    parts = []
    for g in getters:
        if not when_ok(g.get("when"), version):
            continue
        parts.append(f"List.take(&2, U32, List.drop(&2, U32, b, {g['offset']}n), {g['width']}n)")
    return "[" + ", ".join(parts) + "]"


def _emit_projection(lines, facts, name, f):
    a = lines.append
    names = field_names(facts)
    w = {x["name"]: x["width"] for x in header_fields(facts)}
    thresholds = sorted({c["version_ge"] for c in f.get("when", {}).values() if "version_ge" in c})
    k = max(thresholds) if thresholds else 0
    sets = {}
    for v in list(range(k + 1)) + [k + 1]:
        inc = tuple(n for n in f["order"] if when_ok(f.get("when", {}).get(n), v))
        sets.setdefault(inc, []).append(v)
    body_for = {}
    for gi, (inc, vs) in enumerate(sorted(sets.items(), key=lambda kv: kv[1][0])):
        bname = f"{name}_b{gi}"
        for v in vs:
            body_for[v] = (bname, inc)
    for inc, vs in sorted(sets.items(), key=lambda kv: kv[1][0]):
        bname = body_for[vs[0]][0]
        a(f"def {bname}(+h: Hdr) -> {FIELDS}:")
        a(f"  match h:")
        a(f"    case {_hdr_pat(names)}:")
        fl = []
        for n in inc:
            fl.append("[" + ", ".join(f"{n}_{j}" for j in range(w[n])) + "]")
        a(f"      [{', '.join(fl)}]")
        a("")
    last = max(body_for)
    a(f"def {name}_at(v: Nat, +h: Hdr) -> {FIELDS}:")
    a(f"  match v:")
    for v in range(last + 1):
        bname, inc = body_for[v]
        a(f"    case {v}n:")
        a(f"      {bname}(h)")
    a(f"    case {last + 1}n+p:")
    a(f"      {body_for[last][0]}(h)")
    a("")
    a(f"def {name}(+h: Hdr) -> {FIELDS}:")
    a(f"  match h:")
    a(f"    case {_hdr_pat(names)}:")
    a(f"      {name}_at(U32.to_nat(version_0), h)")
    a("")


PRELUDE = '''import Base

def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  match mem bs:
    case Nil{} _:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Con{h, t} Con{b, r}:
      Con{b, overlay(t, r)}

def put(mem: List<&2, U32>, off: Nat, bs: List<&2, U32>) -> List<&2, U32>:
  match mem off:
    case Nil{} _:
      Nil{}
    case Con{h, t} 0n:
      overlay(Con{h, t}, bs)
    case Con{h, t} 1n+p:
      Con{h, put(t, p, bs)}

def zeros(n: Nat) -> List<&2, U32>:
  match n:
    case 0n:
      Nil{}
    case 1n+p:
      Con{0, zeros(p)}

def bytes_eq(xs: List<&2, U32>, ys: List<&2, U32>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(U32.is_eq(x, y), bytes_eq(xt, yt))

def bool_eq(a: Bool, b: Bool) -> Bool:
  match a b:
    case True{} True{}:
      True{}
    case True{} False{}:
      False{}
    case False{} True{}:
      False{}
    case False{} False{}:
      True{}

def fields_eq(xs: List<&2, List<&2, U32>>, ys: List<&2, List<&2, U32>>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(bytes_eq(x, y), fields_eq(xt, yt))

def maybe_fields_eq(xs: Maybe<&2, List<&2, List<&2, U32>>>, ys: Maybe<&2, List<&2, List<&2, U32>>>) -> Bool:
  match xs ys:
    case Some{+a} Some{+b}:
      fields_eq(a, b)
    case None{} None{}:
      True{}
    case _ _:
      False{}

def is_true(b: Bool) -> Type:
  match b:
    case True{}:
      Unit
    case False{}:
      Empty
'''


def bend_model(facts: dict) -> str:
    """Return the deterministic Bend source of the model for these facts."""
    global _cur_fields
    _cur_fields = header_fields(facts)
    lines = [PRELUDE, ""]
    names = field_names(facts)
    lines.append("type Hdr is Data:")
    lines.append("  Hdr{" + ", ".join(f"{n}: U32" for n in names) + "}")
    lines.append("")
    order = [n for n, f in facts["functions"].items() if f.get("kind") != "decoder"]
    order += [n for n, f in facts["functions"].items() if f.get("kind") == "decoder"]
    for name in order:
        f = facts["functions"][name]
        kind = f["kind"]
        if kind == "encoder":
            _emit_encoder(lines, facts, name, f)
        elif kind == "predicate":
            _emit_predicate(lines, facts, name, f)
        elif kind == "decoder":
            _emit_decoder(lines, facts, name, f)
        elif kind == "projection":
            _emit_projection(lines, facts, name, f)
        else:
            raise ValueError(kind)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
