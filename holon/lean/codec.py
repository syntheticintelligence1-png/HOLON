"""Codec facts (holon-facts/0.1) -> Lean 4 model.

A term-for-term mirror of holon.gen.model. The Lean compiler caps constructor
fields at 256, so the header record is emitted in chunks: `Hdr` has one field
per chunk `pc0 : HC0, pc1 : HC1, ...`, each `HCj` holding at most CHUNK cell
fields. Cell accesses are paths `h.pc<j>.<name>`; `get_<name>` reassembles the
byte list. Everything else mirrors holon.gen.model: the same put/zeros/slice
memory ops, the same `<fn>_at` version dispatch, the same `_fields`/`_sel`
decoder shape. Reduction behaviour is preserved: `{h with pc0 := {h.pc0 with
f := v}}` projections reduce without any `match`, so pinned headers evaluate
under `rfl`.
"""
from __future__ import annotations

from .. import facts as F
from .prelude import PRELUDE

CHUNK = 128


def cell_names(facts: dict) -> list[str]:
    return [f"{f['name']}_{k}" for f in F.header_fields(facts) for k in range(f["width"])]


def chunks(facts: dict) -> list[list[str]]:
    cells = cell_names(facts)
    return [cells[i:i + CHUNK] for i in range(0, len(cells), CHUNK)]


def cell_path(facts: dict, name: str) -> str:
    """Lean path of a cell: h.pc<j>.<name> (j = flat index // CHUNK)."""
    cells = cell_names(facts)
    i = cells.index(name)
    return f"h.pc{i // CHUNK}.{name}"


def _cell(facts: dict, c: list) -> str:
    if c[0] == "field":
        return cell_path(facts, f"{c[1]}_{c[2]}")
    if c[0] == "const":
        return str(int(c[1]))
    raise ValueError(c)


def _list(xs: list[str]) -> str:
    return "[" + ", ".join(xs) + "]"


def _version_field(facts: dict) -> str:
    names = [f["name"] for f in F.header_fields(facts)]
    if "version" not in names or F.widths(facts)["version"] != 1:
        raise ValueError("Header must have a 1-byte 'version' field")
    return "version_0"


def _rule_value(fn: str, then) -> str:
    if isinstance(then, bool):
        return "true" if then else "false"
    if set(then) == {"len_ge"}:
        k = then["len_ge"]
        return "true" if k <= 1 else f"tailLenGe t {k - 1}"
    if set(then) == {"len_eq"}:
        k = then["len_eq"]
        return "false" if k == 0 else f"tailLenEq t {k - 1}"
    raise ValueError(f"{fn}: unsupported rule result {then}")


def _first_rule(fn: str, rules: list, empty: bool, version):
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


def _put_chain(facts: dict, fn: str, f: dict, w: dict, version, init: str) -> list[str]:
    lines = [f"let m0 := {init}"]
    i = 0
    for op in f["ops"]:
        if version is not None and not F.when_ok(op.get("when"), version):
            continue
        if version is None and op.get("when"):
            raise ValueError(f"{fn}: version-conditional op in a version-independent encoder")
        cells = F.src_cells(op["src"], w)
        F.check_op_width(fn, op, len(cells))
        lines.append(f"-- {op.get('code', op['op'])}".replace("?", ""))
        lines.append(f"let m{i + 1} := put m{i} {op['offset']} {_list([_cell(facts, c) for c in cells])}")
        i += 1
    tail = f"m{i}" if version is None else f"(m{i}).take {f['length_by_version'][str(version)]}"
    return lines + [tail]


def gen_encoder(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    w = F.widths(facts)
    out = [f"-- {fn}: {f['lang']} encoder ({f['from']} -> {f['to']})"]
    if f["lang"] == "go-bytes":
        body = _put_chain(facts, fn, f, w, None, f"zeros {f['length']}")
        out += [f"def {fn} (h : Hdr) : List Nat :="] + ["  " + l for l in body]
        return out
    if f["lang"] != "solidity-evm-memory":
        raise ValueError(f"{fn}: unsupported encoder language {f['lang']}")
    versions = F.encoder_versions(f)
    size = F.evm_memory_size(f, w)
    out += [f"def {fn}_at : Nat -> Hdr -> List Nat"]
    for v in sorted(versions):
        body = _put_chain(facts, fn, f, w, v, f"List.replicate {size} {F.UNDEF}")
        out += [f"  | {v}, h =>"] + ["      " + l for l in body]
    out += ["  | _, _ => [" + str(F.UNDEF) + "]"]
    out += ["", f"def {fn} (h : Hdr) : List Nat := {fn}_at (hdr_version h) h"]
    return out


def gen_predicate(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    rules = f["rules"]
    out = [f"-- {fn}: {f.get('meaning', 'predicate')}".replace("?", "")]
    out += [f"def {fn}_at : Nat -> List Nat -> Bool"]
    k = max_version_const(rules)
    for v in range(k + 1):
        r = _first_rule(fn, rules, False, v)
        out += [f"  | {v}, t =>"]
        out += [f"      -- {r.get('code', '')}".replace("?", "").rstrip(),
                f"      {_rule_value(fn, r['then'])}"]
    tail = _first_rule(fn, rules, False, k + 1)
    out += ["  | _, t =>", f"      {_rule_value(fn, tail['then'])}"]
    empty = _first_rule(fn, rules, True, None)
    if not isinstance(empty["then"], bool):
        raise ValueError(f"{fn}: the empty-input rule must be a constant")
    out += ["", f"def {fn} : List Nat -> Bool",
            "  | [] => " + _rule_value(fn, empty["then"]),
            "  | h :: t => " + f"{fn}_at h t"]
    return out


def _when_const(when) -> int:
    return when["version_ge"] if when else 0


def gen_decoder(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    getters = f["getters"]
    k = max([_when_const(g.get("when")) for g in getters] + [0])
    out = [f"-- {fn}: {f.get('meaning', 'decoder')}".replace("?", "")]
    out += [f"def {fn}_fields_at : Nat -> List Nat -> List (List Nat)"]
    for v in range(k + 1):
        gs = [f"slice b {g['offset']} {g['width']}" for g in getters if F.when_ok(g.get("when"), v)]
        out += [f"  | {v}, b => {_list(gs)}"]
    tail = [f"slice b {g['offset']} {g['width']}" for g in getters if F.when_ok(g.get("when"), k + 1)]
    out += [f"  | _, b => {_list(tail)}"]
    out += ["", f"def {fn}_fields : List Nat -> List (List Nat)",
            "  | [] => []",
            f"  | h :: t => {fn}_fields_at h (h :: t)", "",
            f"def {fn}_sel : Bool -> List Nat -> Option (List (List Nat))",
            f"  | true, b => some ({fn}_fields b)",
            "  | false, _ => none", "",
            f"-- none unless the guard {f['guard']} accepts b",
            f"def {fn} (b : List Nat) : Option (List (List Nat)) := {fn}_sel ({f['guard']} b) b"]
    return out


def gen_projection(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    w = F.widths(facts)
    when = f.get("when", {})
    k = max([_when_const(when.get(n)) for n in f["order"]] + [0])
    out = [f"-- {fn}: {f.get('meaning', 'projection')}".replace("?", "")]
    out += [f"def {fn}_at : Nat -> Hdr -> List (List Nat)"]
    for v in range(k + 1):
        items = [_list([cell_path(facts, f"{n}_{i}") for i in range(w[n])])
                 for n in f["order"] if F.when_ok(when.get(n), v)]
        out += [f"  | {v}, h => {_list(items)}"]
    items = [_list([cell_path(facts, f"{n}_{i}") for i in range(w[n])])
             for n in f["order"] if F.when_ok(when.get(n), k + 1)]
    out += [f"  | _, h => {_list(items)}"]
    out += ["", f"def {fn} (h : Hdr) : List (List Nat) := {fn}_at (hdr_version h) h"]
    return out


GENERATORS = {"encoder": gen_encoder, "predicate": gen_predicate, "decoder": gen_decoder,
              "projection": gen_projection}


def definition_order(facts: dict) -> list[str]:
    """A def comes after everything it calls (decoders call guards)."""
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
    chs = chunks(facts)
    lines = [
        "-- GENERATED by holon.lean.codec from facts; do not edit (fix the generator instead).",
        f"-- facts_sha256: {facts_sha256}",
        f"-- target: {facts['target']['repo']} @ {facts['target']['commit']}",
        "",
        "set_option linter.unusedVariables false",
        "",
        "-- Header carrier: one Nat per byte, in declaration order. The Lean compiler",
        f"-- caps constructor fields at 256, so cells are chunked into HC0..HC{len(chs) - 1}.",
    ]
    for j, ch in enumerate(chs):
        lines += [f"structure HC{j} where",
                  "\n".join(f"  {c} : Nat" for c in ch),
                  ""]
    lines += ["structure Hdr where",
              "\n".join(f"  pc{j} : HC{j}" for j in range(len(chs))),
              "",
              PRELUDE,
              "def hdr_version (h : Hdr) : Nat := " + cell_path(facts, vf),
              ""]
    for name in w:
        cells = [_cell(facts, ["field", name, i]) for i in range(w[name])]
        lines += [f"def get_{name} (h : Hdr) : List Nat := {_list(cells)}", ""]
    for fn in definition_order(facts):
        lines += GENERATORS[facts["functions"][fn]["kind"]](facts, fn) + [""]
    return "\n".join(lines).rstrip() + "\n"
