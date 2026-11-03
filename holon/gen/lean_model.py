"""Lean 4 model emitter: facts (holon-facts/0.1) -> Lean definitions for the second kernel (I9).

Written independently of the Bend model generator (holon/gen/model.py): it imports neither that
module nor holon.facts or holon.layout, and reads the facts JSON itself. The two generators share only
the facts document (the common mode BUILD_PLAN I9 names). The emitted Lean is a pure function of the
facts, byte-identical across runs (AGENTS.md rule 7).

Semantics of the emitted model (namespace `Model`):
  * `Cell := Option (BitVec 8)`. `some b` is the byte b; `none` is an undefined cell: unwritten
    (dirty) EVM memory, or the result of a revert. Definedness is part of every value, so an
    undefined byte in an encoder output is visible to every equality.
  * `Bytes := List Cell`, `Fields := List Bytes`; a decoder returns `Option Fields`.
  * `Hdr` is a structure with one `BitVec 8` field per header byte: a k-byte header field f is the
    fields `f_0 .. f_{k-1}`, in the facts' declaration order. `Hdr.get_f h` is f as Bytes.
  * Encoders are the facts' write sequence, executed in program order by `put` on an initial
    memory (`some 0` cells for `memory_init: zeros`, `none` cells for `memory_init: dirty`). An
    op with a `when` condition runs only when the version byte satisfies it. A Solidity encoder
    returns `revert` (one undefined cell) outside its domain guard and otherwise takes the
    version's length from `length_by_version`.
  * Predicates follow the facts' rules in order, first match wins (`empty`, `version_in`,
    `otherwise`; results `len_ge`, `len_eq` or a constant).
  * The decoder is `some (getters)` when its guard accepts the input, else `none`; a getter is the
    slice b[offset : offset + width], present when its `when` condition holds for b's version byte.
  * The projection lists the header fields in its `order`, each present when its `when` holds.
"""
from __future__ import annotations

import json
from pathlib import Path

NS = "Model"
UNSUPPORTED = "unsupported by the Lean model emitter"
OP_BYTES = {"mstore": 32, "mstore8": 1, "set_byte": 1, "put_uint64_be": 8}


class LeanUnsupported(ValueError):
    """The facts use a form this emitter cannot express faithfully."""


# ---------------------------------------------------------------- reading the facts (own code)
def load_facts(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def header_layout(facts: dict) -> list[tuple[str, int]]:
    """[(field, width)] of the Header record, in declaration order."""
    hdr = facts["types"]["Header"]
    if hdr.get("kind") != "record":
        raise LeanUnsupported(f"Header kind {hdr.get('kind')!r}: {UNSUPPORTED}")
    out = []
    for f in hdr["fields"]:
        w = int(f["width"])
        if w < 1 or not f["name"].isidentifier():
            raise LeanUnsupported(f"Header field {f!r}: {UNSUPPORTED}")
        out.append((f["name"], w))
    return out


def byte_names(facts: dict) -> list[str]:
    return [f"{n}_{k}" for n, w in header_layout(facts) for k in range(w)]


def version_field(facts: dict) -> str:
    w = dict(header_layout(facts))
    if w.get("version") != 1:
        raise LeanUnsupported("the Header needs a 1-byte `version` field (version-dependent behaviour)")
    return "version_0"


def op_cells(src: list, widths: dict[str, int]) -> list[str]:
    """Lean cells written by one op, in order: header bytes `some h.f_k`, constants `some c`."""
    cells: list[str] = []
    for item in src:
        if set(item) == {"field"}:
            f = item["field"]
            if f not in widths:
                raise LeanUnsupported(f"unknown field {f!r}")
            cells += [f"some h.{f}_{k}" for k in range(widths[f])]
        elif set(item) == {"zeros"}:
            cells += ["some 0"] * int(item["zeros"])
        elif set(item) == {"const"}:
            c = int(item["const"])
            if not 0 <= c <= 255:
                raise LeanUnsupported(f"constant byte {c} out of range")
            cells.append(f"some {c}")
        else:
            raise LeanUnsupported(f"op source {item!r}: {UNSUPPORTED}")
    return cells


def version_cond(when: dict | None, v: str) -> str | None:
    """Lean Bool condition on the version number `v` for a facts `when`, or None if unconditional."""
    if not when:
        return None
    if set(when) == {"version_ge"}:
        return f"decide ({v} ≥ {int(when['version_ge'])})"
    raise LeanUnsupported(f"when-condition {when!r}: {UNSUPPORTED}")


def lean_comment(s: str) -> str:
    """Facts text for a Lean comment: one line, and never a comment delimiter (`/-`, `-/`)."""
    return " ".join(str(s).split()).replace("/-", "/ -").replace("-/", "- /")


# ---------------------------------------------------------------- prelude
PRELUDE = f'''\
namespace {NS}

/-- A cell: `some b` is the byte b, `none` an undefined cell (unwritten EVM memory, or a revert). -/
abbrev Cell := Option (BitVec 8)
abbrev Bytes := List Cell
abbrev Fields := List Bytes

/-- `overlay m bs`: m with its prefix replaced by bs; the length of m is kept. -/
def overlay : Bytes → Bytes → Bytes
  | [], _ => []
  | m, [] => m
  | _ :: t, b :: r => b :: overlay t r

/-- `put m off bs`: write bs into m at offset off (mstore, mstore8, Go copy and PutUint64). -/
def put : Bytes → Nat → Bytes → Bytes
  | [], _, _ => []
  | m, 0, bs => overlay m bs
  | c :: t, n + 1, bs => c :: put t n bs

/-- `slice b off w` = b[off : off + w]. -/
def slice (b : Bytes) (off w : Nat) : Bytes := (b.drop off).take w

/-- The result of a reverting call: one undefined cell, unequal to every defined encoding. -/
def revert : Bytes := [none]

/-- The version number of a byte string: its first cell, if that cell is defined. -/
def verOf : Bytes → Option Nat
  | some x :: _ => some x.toNat
  | _ => none

/-- Does the byte string's version byte satisfy p? (false for an empty or undefined first cell) -/
def verIs (b : Bytes) (p : Nat → Bool) : Bool :=
  match verOf b with
  | some v => p v
  | none => false
'''


# ---------------------------------------------------------------- per function kind
def emit_header(facts: dict) -> list[str]:
    lay = header_layout(facts)
    out = ["/-- The header carrier: one byte per field, in declaration order. -/", "structure Hdr where"]
    out += [f"  {c} : BitVec 8" for c in byte_names(facts)]
    out.append("")
    for n, w in lay:
        cells = ", ".join(f"some h.{n}_{k}" for k in range(w))
        out += [f"/-- Header field `{n}` ({w} bytes). -/",
                f"def Hdr.get_{n} (h : Hdr) : Bytes := [{cells}]", ""]
    return out


def emit_encoder(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    widths = dict(header_layout(facts))
    lang = f["lang"]
    ops = f["ops"]
    for op in ops:
        if op["op"] not in OP_BYTES and op["op"] != "copy":
            raise LeanUnsupported(f"{fn}: op {op['op']!r}: {UNSUPPORTED}")
    src = "; ".join(f"{s['file']} {s['fn']}" for s in f.get("source", []))
    out = [f"/-- `{fn}`: {lang} encoder (Header → Bytes). {lean_comment(src)} -/"]
    if lang == "go-bytes":
        if f.get("memory_init") != "zeros":
            raise LeanUnsupported(f"{fn}: go-bytes memory_init {f.get('memory_init')!r}")
        size = int(f["length"])
        init = f"List.replicate {size} (some 0)"
        if any(op.get("when") for op in ops):
            raise LeanUnsupported(f"{fn}: version-conditional op in a fixed-length encoder")
        body = [f"let m : Bytes := {init}"] + _writes(fn, ops, widths, size, None) + ["m"]
        out += [f"def {fn} (h : Hdr) : Bytes :="] + ["  " + l for l in body]
        return out
    if lang != "solidity-evm-memory":
        raise LeanUnsupported(f"{fn}: encoder language {lang!r}")
    if f.get("memory_init") != "dirty":
        raise LeanUnsupported(f"{fn}: solidity memory_init {f.get('memory_init')!r}")
    vf = version_field(facts)
    lens = {int(k): int(v) for k, v in f["length_by_version"].items()}
    vmax = int(f["domain"]["version_le"])
    if sorted(lens) != list(range(vmax + 1)):
        raise LeanUnsupported(f"{fn}: length_by_version must cover exactly versions 0..{vmax}")
    ends = [op["offset"] + len(op_cells(op["src"], widths)) for op in ops]
    size = max([max(lens.values())] + ends)
    len_expr = " else ".join(f"if v = {k} then {lens[k]}" for k in sorted(lens)) + " else 0"
    body = [f"let m : Bytes := List.replicate {size} none"] + _writes(fn, ops, widths, size, "v")
    body.append(f"List.take ({len_expr}) m")
    out += [f"def {fn} (h : Hdr) : Bytes :=", f"  let v := h.{vf}.toNat",
            f"  -- {lean_comment(f['domain'].get('code', 'domain guard'))}",
            f"  if v ≤ {vmax} then"]
    out += ["    " + l for l in body]
    out += ["  else revert"]
    return out


def _writes(fn: str, ops: list, widths: dict, size: int, v: str | None) -> list[str]:
    lines = []
    for op in ops:
        cells = op_cells(op["src"], widths)
        want = OP_BYTES.get(op["op"])
        if want is not None and len(cells) != want:
            raise LeanUnsupported(f"{fn}: {op['op']} at {op['offset']} writes {len(cells)} bytes, not {want}")
        off = int(op["offset"])
        if off + len(cells) > size:
            raise LeanUnsupported(f"{fn}: write at {off}+{len(cells)} exceeds the buffer of {size}")
        lines.append(f"-- {lean_comment(op.get('code', op['op']))}")
        write = f"put m {off} [{', '.join(cells)}]"
        cond = version_cond(op.get("when"), v) if v else None
        if op.get("when") and not v:
            raise LeanUnsupported(f"{fn}: conditional op without a version")
        lines.append(f"let m : Bytes := if {cond} then {write} else m" if cond else f"let m : Bytes := {write}")
    return lines


def _rule_cond(fn: str, cond) -> str:
    if cond == "empty":
        return "b.isEmpty"
    if cond == "otherwise":
        return "true"
    if isinstance(cond, dict) and set(cond) == {"version_in"}:
        vs = [int(x) for x in cond["version_in"]]
        if not vs:
            raise LeanUnsupported(f"{fn}: empty version_in")
        return "verIs b (fun v => " + " || ".join(f"v == {x}" for x in vs) + ")"
    raise LeanUnsupported(f"{fn}: rule condition {cond!r}: {UNSUPPORTED}")


def _rule_value(fn: str, then) -> str:
    if isinstance(then, bool):
        return "true" if then else "false"
    if isinstance(then, dict) and set(then) == {"len_ge"}:
        return f"decide (b.length ≥ {int(then['len_ge'])})"
    if isinstance(then, dict) and set(then) == {"len_eq"}:
        return f"decide (b.length = {int(then['len_eq'])})"
    raise LeanUnsupported(f"{fn}: rule result {then!r}: {UNSUPPORTED}")


def emit_predicate(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    rules = f["rules"]
    if not rules or rules[-1]["if"] != "otherwise":
        raise LeanUnsupported(f"{fn}: the rules must end with `otherwise` (exhaustive)")
    if any(r["if"] == "otherwise" for r in rules[:-1]):
        raise LeanUnsupported(f"{fn}: unreachable rules after `otherwise`")
    out = [f"/-- `{fn}`: {lean_comment(f.get('meaning', 'predicate'))}. Rules in order, first match wins. -/",
           f"def {fn} (b : Bytes) : Bool :="]
    for i, r in enumerate(rules):
        out.append(f"  -- {lean_comment(r.get('code', ''))}")
        val = _rule_value(fn, r["then"])
        if r["if"] == "otherwise":
            out.append(f"  {val}" if i == 0 else f"  else {val}")
        else:
            out.append(f"  {'if' if i == 0 else 'else if'} {_rule_cond(fn, r['if'])} then {val}")
    return out


def _segments(items: list[tuple[str, str | None]]) -> str:
    """Concatenate [(lean term, condition or None)] into one list expression, keeping the order."""
    parts, run = [], []
    for t, cond in items:
        if cond is None:
            run.append(t)
            continue
        if run:
            parts.append("[" + ", ".join(run) + "]")
            run = []
        parts.append(f"(if {cond} then [{t}] else [])")
    if run or not parts:
        parts.append("[" + ", ".join(run) + "]")
    return " ++ ".join(parts)


def emit_decoder(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    guard = f["guard"]
    if facts["functions"].get(guard, {}).get("kind") != "predicate":
        raise LeanUnsupported(f"{fn}: guard {guard!r} is not a predicate")
    items = []
    for g in f["getters"]:
        when = g.get("when")
        cond = None
        if when:
            if set(when) != {"version_ge"}:
                raise LeanUnsupported(f"{fn}: getter condition {when!r}")
            cond = f"verIs b (fun v => decide (v ≥ {int(when['version_ge'])}))"
        items.append((f"slice b {int(g['offset'])} {int(g['width'])}", cond))
    return [f"/-- `{fn}` getters: {lean_comment(f.get('meaning', 'decoder'))}. -/",
            f"def {fn}_fields (b : Bytes) : Fields :=", f"  {_segments(items)}", "",
            f"/-- `{fn}`: `none` unless the guard `{guard}` accepts b. -/",
            f"def {fn} (b : Bytes) : Option Fields :=", f"  if {guard} b then some ({fn}_fields b) else none"]


def emit_projection(facts: dict, fn: str) -> list[str]:
    f = facts["functions"][fn]
    widths = dict(header_layout(facts))
    vf = version_field(facts)
    when = f.get("when", {})
    items = []
    for n in f["order"]:
        if n not in widths:
            raise LeanUnsupported(f"{fn}: unknown field {n!r}")
        items.append((f"h.get_{n}", version_cond(when.get(n), f"h.{vf}.toNat")))
    return [f"/-- `{fn}`: {lean_comment(f.get('meaning', 'projection'))}. -/",
            f"def {fn} (h : Hdr) : Fields :=", f"  {_segments(items)}"]


EMITTERS = {"encoder": emit_encoder, "predicate": emit_predicate, "decoder": emit_decoder,
            "projection": emit_projection}


def order(facts: dict) -> list[str]:
    """Lean needs a definition before its use: guards before the decoders that call them."""
    fns = facts["functions"]
    for fn, f in fns.items():
        if f["kind"] not in EMITTERS:
            raise LeanUnsupported(f"{fn}: function kind {f['kind']!r}: {UNSUPPORTED}")
        if not fn.isidentifier():
            raise LeanUnsupported(f"function name {fn!r}")
    first = sorted(fn for fn, f in fns.items() if f["kind"] != "decoder")
    return first + sorted(fn for fn, f in fns.items() if f["kind"] == "decoder")


def emit_model(facts: dict, facts_sha256: str) -> str:
    """The `Model` namespace for these facts (no imports: Lean core only)."""
    version_field(facts)
    t = facts.get("target", {})
    lines = [f"-- model: GENERATED by holon.gen.lean_model from facts sha256 {facts_sha256}",
             f"-- target: {lean_comment(t.get('repo', '?'))} @ {lean_comment(t.get('commit', '?'))}",
             PRELUDE.rstrip(), ""]
    lines += emit_header(facts)
    for fn in order(facts):
        lines += EMITTERS[facts["functions"][fn]["kind"]](facts, fn) + [""]
    lines.append(f"end {NS}")
    return "\n".join(lines) + "\n"
