"""Model generator: facts -> executable, provable Bend model (whitepaper §8.3).

One Bend type per carrier, one Bend def per fact function. The output is a pure
function of the facts document, byte-identical across runs (AGENTS.md rule 7).

Conventions of the generated model:
  * A byte is a U32. A k-byte header field is k record fields `<name>_0 .. <name>_{k-1}`.
  * A value outside 0..255 (57005 = 0xDEAD) marks an undefined result: unwritten
    EVM memory, or a revert. Definedness is therefore visible in the output.
  * Behaviour that depends on the version byte dispatches on `U32.to_nat(v)` through a
    helper `<fn>_at(n: Nat, ..)` whose cases are 0n .. Kn plus a tail (K+1)n+p, where K
    is the largest version constant the function mentions. Proof generators rely on
    this shape (holon/gen/proofs.py: `version_split`).
"""
from __future__ import annotations

from .. import facts as F

BYTES = "List<&2, U32>"
FIELDS = "List<&2, List<&2, U32>>"
MAYBE_FIELDS = "Maybe<&2, List<&2, List<&2, U32>>>"
BEND_TYPE = {"Bytes": BYTES, "Bool": "Bool", "Fields": FIELDS, "MaybeFields": MAYBE_FIELDS, "Header": "Hdr"}
EQ_FN = {"Bytes": "eq_bytes", "Bool": "eq_bool", "Fields": "eq_fields", "MaybeFields": "eq_maybe_fields"}

PRELUDE = '''\
# overlay(mem, bs): replace the prefix of mem with bs, keeping the length of mem.
def overlay(mem: List<&2, U32>, bs: List<&2, U32>) -> List<&2, U32>:
  match mem bs:
    case Nil{} _:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Con{h, t} Con{b, r}:
      Con{b, overlay(t, r)}

# put(mem, off, bs): write bs at byte offset off (EVM mstore/mstore8, Go copy/PutUint64).
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

# slice(b, off, w) = b[off:off+w]
def slice(+b: List<&2, U32>, off: Nat, w: Nat) -> List<&2, U32>:
  List.take(&2, U32, List.drop(&2, U32, b, off), w)

# Length tests on the tail t of a non-empty byte string b = h:t (len(b) = 1 + len(t)).
def tail_len_ge(t: List<&2, U32>, k: Nat) -> Bool:
  Nat.is_ge(List.length(&2, U32, t), k)

def tail_len_eq(t: List<&2, U32>, k: Nat) -> Bool:
  Nat.is_eq(List.length(&2, U32, t), k)

# Equality functions used by counter-laws. They are not trusted: a counter-law whose
# sides are actually equal is rejected whatever these compute (BEND_PRIMER 5.4).
def eq_bytes(xs: List<&2, U32>, ys: List<&2, U32>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(U32.is_eq(x, y), eq_bytes(xt, yt))

def eq_fields(xs: List<&2, List<&2, U32>>, ys: List<&2, List<&2, U32>>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{x, xt} Con{y, yt}:
      Bool.and(eq_bytes(x, y), eq_fields(xt, yt))

def eq_maybe_fields(a: Maybe<&2, List<&2, List<&2, U32>>>, b: Maybe<&2, List<&2, List<&2, U32>>>) -> Bool:
  match a b:
    case None{} None{}:
      True{}
    case None{} Some{y}:
      False{}
    case Some{x} None{}:
      False{}
    case Some{x} Some{y}:
      eq_fields(x, y)

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


def nat_cases(k: int) -> list[tuple[str, int]]:
    """Exhaustive Nat patterns 0n..kn, (k+1)n+p, each with a representative value."""
    return [(f"{i}n", i) for i in range(k + 1)] + [(f"{k + 1}n+p", k + 1)]


def cell_names(facts: dict) -> list[str]:
    return [f"{f['name']}_{k}" for f in F.header_fields(facts) for k in range(f["width"])]


def hdr_pattern(facts: dict, reuse: bool = True) -> str:
    pre = "+" if reuse else ""
    return "Hdr{" + ", ".join(pre + c for c in cell_names(facts)) + "}"


def _cell(c: list) -> str:
    if c[0] == "field":
        return f"{c[1]}_{c[2]}"
    if c[0] == "const":
        return str(int(c[1]))
    raise ValueError(c)


def _list(xs: list[str]) -> str:
    return "[" + ", ".join(xs) + "]" if xs else "Nil{}"


def _indent(lines: list[str], n: int) -> list[str]:
    return [" " * n + l for l in lines]


def _version_field(facts: dict) -> str:
    names = [f["name"] for f in F.header_fields(facts)]
    if "version" not in names or F.widths(facts)["version"] != 1:
        raise ValueError("Header must have a 1-byte 'version' field")
    return "version_0"


# ---------------------------------------------------------------- encoders
def _put_chain(fn: str, f: dict, w: dict, version: int | None, init: str) -> list[str]:
    lines = [f"m0 = {init}"]
    i = 0
    for op in f["ops"]:
        if version is not None and not F.when_ok(op.get("when"), version):
            continue
        if version is None and op.get("when"):
            raise ValueError(f"{fn}: version-conditional op in a version-independent encoder")
        cells = F.src_cells(op["src"], w)
        # a fixed-width op writes exactly its width: slice a src field that is
        # wider, pad a narrower one with UNDEF (extracted layouts may disagree
        # with the op width under mutation)
        want = F.OP_WIDTH.get(op["op"])
        if want is not None:
            cells = (cells + [["const", F.UNDEF]] * want)[:want]
        F.check_op_width(fn, op, len(cells))
        lines.append(f"# {op.get('code', op['op'])}".replace("?", ""))
        lines.append(f"m{i + 1} = put(m{i}, {op['offset']}n, {_list([_cell(c) for c in cells])})")
        i += 1
    return lines + [f"m{i}"] if version is None else lines + [f"List.take(&2, U32, m{i}, {f['length_by_version'][str(version)]}n)"]


def gen_encoder(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    w = F.widths(facts)
    out = [f"# {fn}: {f['lang']} encoder ({f['from']} -> {f['to']})"]
    if f["lang"] == "go-bytes":
        body = _put_chain(fn, f, w, None, f"zeros({f['length']}n)")
        out += [f"def {fn}(h: Hdr) -> {BYTES}:", "  match h:", f"    case {hdr_pattern(facts)}:"]
        out += _indent(body, 6)
        return out
    if f["lang"] != "solidity-evm-memory":
        raise ValueError(f"{fn}: unsupported encoder language {f['lang']}")
    versions = F.encoder_versions(f)
    size = F.evm_memory_size(f, w)
    out += [f"def {fn}_at(n: Nat, h: Hdr) -> {BYTES}:", "  match n:"]
    for pat, v in nat_cases(max(versions)):
        out.append(f"    case {pat}:")
        if v in versions:
            body = _put_chain(fn, f, w, v, f"List.replicate(U32, {size}n, {F.UNDEF})")
            out += ["      match h:", f"        case {hdr_pattern(facts)}:"] + _indent(body, 10)
        else:
            out.append(f"      [{F.UNDEF}]")  # outside the domain guard: the call reverts
    out += ["", f"def {fn}(+h: Hdr) -> {BYTES}:", f"  {fn}_at(hdr_version(h), h)"]
    return out


# ---------------------------------------------------------------- predicates
def _rule_value(fn: str, then) -> str:
    if isinstance(then, bool):
        return "True{}" if then else "False{}"
    if set(then) == {"len_ge"}:
        k = then["len_ge"]
        return "True{}" if k <= 1 else f"tail_len_ge(t, {k - 1}n)"
    if set(then) == {"len_eq"}:
        k = then["len_eq"]
        return "False{}" if k == 0 else f"tail_len_eq(t, {k - 1}n)"
    raise ValueError(f"{fn}: unsupported rule result {then}")


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
            raise ValueError(f"{fn}: unsupported rule condition {c}")
    raise ValueError(f"{fn}: rules are not exhaustive")


def max_version_const(rules: list) -> int:
    ks = [v for r in rules if isinstance(r["if"], dict) for v in r["if"].get("version_in", [])]
    return max(ks, default=0)


def gen_predicate(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    rules = f["rules"]
    out = [f"# {fn}: {f.get('meaning', 'predicate')}".replace("?", "")]
    out += [f"def {fn}_at(n: Nat, t: {BYTES}) -> Bool:", "  match n:"]
    for pat, v in nat_cases(max_version_const(rules)):
        r = _first_rule(fn, rules, False, v)
        out += [f"    case {pat}:", f"      # {r.get('code', '')}".replace("?", "").rstrip(),
                f"      {_rule_value(fn, r['then'])}"]
    empty = _first_rule(fn, rules, True, None)
    if not isinstance(empty["then"], bool):
        raise ValueError(f"{fn}: the empty-input rule must be a constant")
    out += ["", f"def {fn}(b: {BYTES}) -> Bool:", "  match b:", "    case Nil{}:",
            f"      {_rule_value(fn, empty['then'])}", "    case Con{h, t}:",
            f"      {fn}_at(U32.to_nat(h), t)"]
    return out


# ---------------------------------------------------------------- decoders, projections
def _when_const(when: dict | None) -> int:
    if not when:
        return 0
    if "version_ge" in when:
        return when["version_ge"]
    return max(when["version_in"])


def gen_decoder(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    getters = f["getters"]
    k = max([_when_const(g.get("when")) for g in getters] + [0])
    out = [f"# {fn}: {f.get('meaning', 'decoder')}".replace("?", "")]
    out += [f"def {fn}_fields_at(n: Nat, +b: {BYTES}) -> {FIELDS}:", "  match n:"]
    for pat, v in nat_cases(k):
        gs = [f"slice(b, {g['offset']}n, {g['width']}n)" for g in getters if F.when_ok(g.get("when"), v)]
        out += [f"    case {pat}:", f"      {_list(gs)}"]
    out += ["", f"def {fn}_fields(b: {BYTES}) -> {FIELDS}:", "  match b:", "    case Nil{}:", "      Nil{}",
            "    case Con{+h, +t}:", f"      {fn}_fields_at(U32.to_nat(h), Con{{h, t}})", "",
            f"def {fn}_sel(c: Bool, b: {BYTES}) -> {MAYBE_FIELDS}:", "  match c:", "    case True{}:",
            f"      Some{{{fn}_fields(b)}}", "    case False{}:", "      None{}", "",
            f"# None unless the guard {f['guard']} accepts b",
            f"def {fn}(+b: {BYTES}) -> {MAYBE_FIELDS}:", f"  {fn}_sel({f['guard']}(b), b)"]
    return out


def gen_projection(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    w = F.widths(facts)
    when = f.get("when", {})
    k = max([_when_const(when.get(n)) for n in f["order"]] + [0])
    out = [f"# {fn}: {f.get('meaning', 'projection')}".replace("?", "")]
    out += [f"def {fn}_at(n: Nat, h: Hdr) -> {FIELDS}:", "  match n:"]
    for pat, v in nat_cases(k):
        items = [_list([f"{n}_{i}" for i in range(w[n])]) for n in f["order"] if F.when_ok(when.get(n), v)]
        out += [f"    case {pat}:", "      match h:", f"        case {hdr_pattern(facts)}:",
                f"          {_list(items)}"]
    out += ["", f"def {fn}(+h: Hdr) -> {FIELDS}:", f"  {fn}_at(hdr_version(h), h)"]
    return out


GENERATORS = {"encoder": gen_encoder, "predicate": gen_predicate, "decoder": gen_decoder,
              "projection": gen_projection}


# ---------------------------------------------------------------- the module
def definition_order(facts: dict) -> list[str]:
    """Bend resolves names top-down: a def comes after everything it calls (decoders call guards)."""
    fns = facts["functions"]
    for fn, f in fns.items():
        if f["kind"] not in GENERATORS:
            raise ValueError(f"{fn}: unsupported function kind {f['kind']}")
    deps = {fn: ([f["guard"]] if f["kind"] == "decoder" else []) for fn, f in fns.items()}
    out: list[str] = []

    def visit(fn: str, stack: tuple = ()) -> None:
        if fn in out:
            return
        if fn in stack or fn not in fns:
            raise ValueError(f"bad dependency on {fn} via {stack}")
        for d in deps[fn]:
            visit(d, stack + (fn,))
        out.append(fn)

    for fn in sorted(fns):
        visit(fn)
    return out


def generate(facts: dict, facts_sha256: str) -> str:
    vf = _version_field(facts)
    w = F.widths(facts)
    lines = [
        "# GENERATED by holon.gen.model from facts; do not edit (fix the generator instead).",
        f"# facts_sha256: {facts_sha256}",
        f"# target: {facts['target']['repo']} @ {facts['target']['commit']}",
        "import Base", "",
        "# Header carrier: one U32 per byte, in declaration order.",
        "type Hdr is Data:",
        "  Hdr{" + ", ".join(f"{c}: U32" for c in cell_names(facts)) + "}", "",
        PRELUDE,
        "def hdr_version(h: Hdr) -> Nat:", "  match h:", f"    case {hdr_pattern(facts, reuse=False)}:",
        f"      U32.to_nat({vf})", "",
    ]
    for name in w:  # field getters, for IR terms {"field": name, "of": ..}
        lines += [f"def get_{name}(h: Hdr) -> {BYTES}:", "  match h:", f"    case {hdr_pattern(facts)}:",
                  f"      {_list([f'{name}_{i}' for i in range(w[name])])}", ""]
    for fn in definition_order(facts):
        lines += GENERATORS[facts["functions"][fn]["kind"]](facts, fn) + [""]
    return "\n".join(lines).rstrip() + "\n"
