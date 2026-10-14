"""Deciding the laws of a linked codec component (BUILD_PLAN I24; whitepaper §8.3, §8.4 PAR rows, §10.2; the contract is
rule X9 of the docstring of tests_m3/test_derive_par.py; the layer itself is holon.diagram.linked).

The component model gen/<M>/model/<role>.bend, generated from the linked codec document alone:

  * one record type R_<carrier> per record carrier, one U32 per byte in field order (a field's bytes F_0 .. F_<w-1>,
    a Go field path's "." written "__"), and a getter get_<carrier>__<field> per field;
  * byte strings are List<&2, U32>;
  * an encoder is its layout (rule X5): a layout without a tag field is a constant list over the record's bytes; a
    layout family keyed by a one-byte tag field dispatches on that field's value (holon.gen.model's convention), a
    version without a layout and an unwritten cell the sentinel 57005 (0xDEAD, never a byte);
  * a decoder is Maybe: Some of the bytes it reads when one of its ok paths holds on the input's length and tag byte,
    else None; a predicate, and a loader's domain predicate ok_<loader>, is that Bool (a loader is Some of its input);
    an encoder's domain conditions are recorded in the document and not modelled (assumption A-codec-domain).

Laws (holon-ir/0.3 codec terms): premises on record fields by pinning (a field equal to constant bytes, or, through
correspondence premises, to another binder's field: one equivalence class per field, its representative the first
member in binder order, all members the class's constant when it has one), any other premise as a hypothesis binder.
A law over records only is proved by opening every record and {==} (M0's class); a counter-law at a concrete witness
refutes it, the witness found by evaluating the compiled model over fixed fills (premises applied) and satisfying
every atom, over record fields only, of the ok conditions of the encoders it names (so the real code reaches its
store). A law over the linked byte carrier is refuted only at probes: lengths and tag bytes from every integer
constant k of the two sides' ok conditions (k - 1, k, k + 1 and 0), the first difference by (length, tag); under a
tag premise of version v only tag byte v and length >= 1. No probe distinguishing the sides leaves it UNKNOWN, its
bound naming the probes: a byte-string law has no proof route here (gap G6). Every status is Bend's: PROVED and
REFUTED only through a file Bend accepts.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import bend

ALIAS = "M"
UNDEF = 57005
BYTES = "List<&2, U32>"
MAYBE_BYTES = "Maybe<&2, List<&2, U32>>"
ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "holon" / "js" / "linked.mjs"
SEED = 20261013
RANDOM_FILLS = 8
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PRELUDE_DEFS = ("byte_at", "slice", "sel_bytes", "eq_bytes", "eq_maybe_bytes", "eq_bool", "is_true")
KEYWORDS = {"match", "case", "def", "type", "law", "for", "exs", "import", "as", "is", "Data", "Type", "Nat", "Bool",
            "U32", "List", "Maybe", "Some", "None", "True", "False", "Con", "Nil", "Unit", "Empty"}


class Unsupported(Exception):
    """A document or statement form this generator cannot express faithfully (the law stays UNKNOWN)."""


# ====================================================================== names
def mangle(f: str) -> str:
    out = f.replace(".", "__")
    if not IDENT.match(out):
        raise Unsupported(f"field {f!r} gives no identifier")
    return out


def rec_type(cid: str) -> str:
    return f"R_{cid}"


def cell_var(f: str, k: int) -> str:
    return f"{mangle(f)}_{k}"


def getter(cid: str, f: str) -> str:
    return f"get_{cid}__{mangle(f)}"


def records(doc: dict) -> dict[str, list[dict]]:
    return {cid: c["fields"] for cid, c in doc["carriers"].items() if c["kind"] == "record"}


def cells_of(doc: dict, cid: str) -> list[tuple[str, int, str]]:
    return [(f["name"], k, cell_var(f["name"], k)) for f in records(doc)[cid] for k in range(f["width"])]


def fn_type(doc: dict, name: str) -> tuple[str, str] | None:
    """(argument type, result type) of a component function named in a law: an encoder takes its record; a decoder
    and a loader take the linked byte carrier into Maybe bytes; a predicate and a loader's domain predicate ok_<L>
    into Bool. Types: a record carrier id, "Bytes", "MaybeBytes", "Bool"."""
    fs = doc["functions"]
    if name in fs:
        f = fs[name]
        if f["kind"] == "encoder":
            return f["from"], "Bytes"
        if f["kind"] in ("decoder", "loader"):
            return "Bytes", "MaybeBytes"
        if f["kind"] == "predicate":
            return "Bytes", "Bool"
    if name.startswith("ok_") and (fs.get(name[3:]) or {}).get("kind") == "loader":
        return "Bytes", "Bool"
    return None


def binder_type(doc: dict, t: str) -> str:
    if t == doc["linked_carrier"]:
        return "Bytes"
    if t in records(doc):
        return t
    raise Unsupported(f"binder type {t} is neither a record carrier nor the linked carrier")


def bend_type(t: str, alias: str = ALIAS) -> str:
    if t == "Bytes":
        return BYTES
    if t == "MaybeBytes":
        return MAYBE_BYTES
    if t == "Bool":
        return "Bool"
    return f"{alias}.{rec_type(t)}"


def _list(xs: list[str]) -> str:
    return "[" + ", ".join(xs) + "]" if xs else "Nil{}"


# ====================================================================== conditions -> Bend
def _go_term(t, b: str):
    if isinstance(t, list) and len(t) == 2 and t[0] == "len" and t[1][0] == "param":
        return "Nat", f"List.length(&2, U32, {b})"
    if isinstance(t, list) and len(t) == 3 and t[0] == "index" and t[1][0] == "param" and t[2][0] == "const":
        return "U32", f"byte_at({b}, {int(t[2][1])}n)"
    if isinstance(t, list) and len(t) == 2 and t[0] == "const" and isinstance(t[1], int) and not isinstance(t[1], bool):
        return "Int", int(t[1])
    raise Unsupported(f"condition term {t}")


def _sol_term(t, b: str):
    if isinstance(t, list) and len(t) == 2 and t[0] == "len":
        return "Nat", f"List.length(&2, U32, {b})"
    if isinstance(t, list) and len(t) == 3 and t[0] == "byte" and isinstance(t[2], int):
        return "U32", f"byte_at({b}, {int(t[2])}n)"
    if isinstance(t, int) and not isinstance(t, bool):
        return "Int", int(t)
    raise Unsupported(f"condition term {t}")


CMP = {"==": "is_eq", "!=": "is_ne", "<": "is_lt", "<=": "is_le", ">": "is_gt", ">=": "is_ge"}


def _cmp(op: str, a, b) -> str:
    (ta, xa), (tb, xb) = a, b
    if ta == "Int" and tb == "Int":
        return "True{}" if {"==": xa == xb, "!=": xa != xb, "<": xa < xb, "<=": xa <= xb, ">": xa > xb,
                            ">=": xa >= xb}[op] else "False{}"
    ty = ta if ta != "Int" else tb
    if ta not in ("Int", ty) or tb not in ("Int", ty):
        raise Unsupported(f"a comparison of {ta} with {tb}")
    lit = (lambda x: f"{x}n") if ty == "Nat" else (lambda x: str(x))
    xa = lit(xa) if ta == "Int" else xa
    xb = lit(xb) if tb == "Int" else xb
    if ty == "Nat":
        if op == "!=":
            return f"Bool.not(Nat.is_eq({xa}, {xb}))"
        return f"Nat.{CMP[op]}({xa}, {xb})"
    return f"U32.{CMP[op]}({xa}, {xb})"


def _and(xs: list[str]) -> str:
    if not xs:
        return "True{}"
    out = xs[-1]
    for x in reversed(xs[:-1]):
        out = f"Bool.and({x}, {out})"
    return out


def _or(xs: list[str]) -> str:
    if not xs:
        return "False{}"
    out = xs[-1]
    for x in reversed(xs[:-1]):
        out = f"Bool.or({x}, {out})"
    return out


def go_condition(paths: list[list], b: str = "b") -> str:
    """A Go decoder's or predicate's ok paths (each a list of atoms over its parameter's length and index) as one Bool."""
    out = []
    for cond in paths:
        atoms = []
        for a in cond:
            if not (isinstance(a, list) and len(a) == 3 and a[0] in CMP):
                raise Unsupported(f"condition atom {a}")
            atoms.append(_cmp(a[0], _go_term(a[1], b), _go_term(a[2], b)))
        out.append(_and(atoms))
    return _or(out)


def _sol_bool(e, b: str) -> str:
    if isinstance(e, bool):
        return "True{}" if e else "False{}"
    if not isinstance(e, list) or not e:
        raise Unsupported(f"condition {e}")
    if e[0] == "!" and len(e) == 2:
        return f"Bool.not({_sol_bool(e[1], b)})"
    if e[0] == "&&":
        return _and([_sol_bool(x, b) for x in e[1:]])
    if e[0] == "||":
        return _or([_sol_bool(x, b) for x in e[1:]])
    if e[0] in CMP and len(e) == 3:
        return _cmp(e[0], _sol_term(e[1], b), _sol_term(e[2], b))
    raise Unsupported(f"condition {e}")


def sol_condition(paths: list[list], b: str = "b") -> str:
    """A Solidity loader's ok paths (each a list of I17 DSL atoms over its input's length and bytes) as one Bool."""
    return _or([_and([_sol_bool(a, b) for a in cond]) for cond in paths])


# ====================================================================== the model
PRELUDE = '''\
# byte_at(b, n): byte n of b, or the sentinel 57005 past its end (never a byte, so it equals no constant)
def byte_at(b: List<&2, U32>, n: Nat) -> U32:
  match b n:
    case Nil{} _:
      57005
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      byte_at(t, p)

# slice(b, off, w) = b[off:off+w]
def slice(+b: List<&2, U32>, off: Nat, w: Nat) -> List<&2, U32>:
  List.take(&2, U32, List.drop(&2, U32, b, off), w)

def sel_bytes(c: Bool, x: List<&2, U32>) -> Maybe<&2, List<&2, U32>>:
  match c:
    case True{}:
      Some{x}
    case False{}:
      None{}

# Equality functions used by counter-laws. They are not trusted: a counter-law whose sides are actually equal is
# rejected whatever these compute (BEND_PRIMER 5.4).
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

def eq_maybe_bytes(a: Maybe<&2, List<&2, U32>>, b: Maybe<&2, List<&2, U32>>) -> Bool:
  match a b:
    case None{} None{}:
      True{}
    case None{} Some{y}:
      False{}
    case Some{x} None{}:
      False{}
    case Some{x} Some{y}:
      eq_bytes(x, y)

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


def _pattern(doc: dict, cid: str, prefix: str = "", reuse: bool = True, alias: str | None = None) -> str:
    pre = "+" if reuse else ""
    t = rec_type(cid) if alias is None else f"{alias}.{rec_type(cid)}"
    return t + "{" + ", ".join(pre + prefix + v for _, _, v in cells_of(doc, cid)) + "}"


def _layout_list(lay: list[list], prefix: str = "") -> str:
    out = []
    for c in lay:
        if c[0] == "field":
            out.append(prefix + cell_var(c[1], c[2]))
        elif c[0] == "const":
            out.append(str(int(c[1])))
        else:
            out.append(str(UNDEF))
    return _list(out)


def tag_field(f: dict, doc: dict) -> str | None:
    """The one-byte record field an encoder's layouts carry at the tag index, when every layout has it there."""
    tag = doc["tag_index"]
    fields = {x["name"]: x["width"] for x in records(doc).get(f["from"], [])}
    names = set()
    for lay in f["layouts"].values():
        c = lay[tag] if tag < len(lay) else ["unknown"]
        if c[0] != "field" or c[2] != 0 or fields.get(c[1]) != 1:
            return None
        names.add(c[1])
    return names.pop() if len(names) == 1 else None


def _nat_cases(k: int) -> list[tuple[str, int | None]]:
    return [(f"{i}n", i) for i in range(k + 1)] + [(f"{k + 1}n+p", None)]


def _gen_encoder(doc: dict, name: str, f: dict) -> list[str]:
    cid = f["from"]
    pat = _pattern(doc, cid)
    out = [f"# {name}: encoder of {f['source']} ({f['lang']}), {cid} -> bytes; versions {f['versions']}"]
    if len(f["layouts"]) == 1:
        lay = next(iter(f["layouts"].values()))
        return out + [f"def {name}(h: {rec_type(cid)}) -> {BYTES}:", "  match h:", f"    case {pat}:",
                      f"      {_layout_list(lay)}"]
    tf = tag_field(f, doc)
    if tf is None or any(not k.isdigit() for k in f["layouts"]):
        raise Unsupported(f"{name}: several layouts not keyed by a one-byte tag field")
    vs = sorted(int(k) for k in f["layouts"])
    out += [f"def {name}_at(n: Nat, h: {rec_type(cid)}) -> {BYTES}:", "  match n:"]
    for patn, v in _nat_cases(max(vs)):
        out.append(f"    case {patn}:")
        if v is not None and str(v) in f["layouts"]:
            out += ["      match h:", f"        case {pat}:", f"          {_layout_list(f['layouts'][str(v)])}"]
        else:
            out.append(f"      [{UNDEF}]")
    out += ["", f"def {name}_tag(h: {rec_type(cid)}) -> U32:", "  match h:", f"    case {_pattern(doc, cid, reuse=False)}:",
            f"      {cell_var(tf, 0)}", "",
            f"def {name}(+h: {rec_type(cid)}) -> {BYTES}:", f"  {name}_at(U32.to_nat({name}_tag(h)), h)"]
    return out


def model_names(doc: dict) -> dict[str, str]:
    """Every top-level name the model defines -> what defines it (names must be distinct)."""
    out: dict[str, str] = {}

    def add(n: str, what: str) -> None:
        if not IDENT.match(n) or n in KEYWORDS:
            raise Unsupported(f"{what}: {n!r} is no usable name")
        if n in out:
            raise Unsupported(f"{what} and {out[n]} both define {n}")
        out[n] = what
    for n in PRELUDE_DEFS:
        add(n, "the prelude")
    for cid, fs in records(doc).items():
        add(rec_type(cid), f"record {cid}")
        for fl in fs:
            add(getter(cid, fl["name"]), f"record {cid}")
    for name, f in doc["functions"].items():
        add(name, f"function {name}")
        if f["kind"] == "encoder" and len(f["layouts"]) > 1:
            add(f"{name}_at", f"function {name}")
            add(f"{name}_tag", f"function {name}")
        if f["kind"] == "decoder":
            add(f"{name}_ok", f"function {name}")
        if f["kind"] == "loader":
            add(f"ok_{name}", f"function {name}")
    return out


def generate(doc: dict, sha: str) -> str:
    """The component model (module docstring), a pure function of the linked codec document."""
    model_names(doc)
    lines = ["# GENERATED by holon.gen.linked from a linked codec document; do not edit (fix the generator instead).",
             f"# facts_sha256: {sha}", f"# component: {doc['component']} (linked carrier {doc['linked_carrier']}, "
             f"tag byte {doc['tag_index']})", "import Base", ""]
    for cid in records(doc):
        lines += [f"# record carrier {cid}: one U32 per byte, in field order",
                  f"type {rec_type(cid)} is Data:", "  " + rec_type(cid) + "{" +
                  ", ".join(f"{v}: U32" for _, _, v in cells_of(doc, cid)) + "}", ""]
    lines += [PRELUDE]
    for cid, fs in records(doc).items():
        for fl in fs:
            lines += [f"def {getter(cid, fl['name'])}(h: {rec_type(cid)}) -> {BYTES}:", "  match h:",
                      f"    case {_pattern(doc, cid)}:",
                      f"      {_list([cell_var(fl['name'], k) for k in range(fl['width'])])}", ""]
    for name, f in doc["functions"].items():
        kind = f["kind"]
        if kind == "encoder":
            lines += _gen_encoder(doc, name, f) + [""]
        elif kind == "decoder":
            rd = f["read"]
            lines += [f"# {name}: decoder {f['source']}, reads bytes {rd['offset']}..{rd['offset'] + rd['width'] - 1}; "
                      "Some iff an ok path holds on the length and the tag byte",
                      f"def {name}_ok(+b: {BYTES}) -> Bool:", f"  {go_condition(f['ok'])}", "",
                      f"def {name}(+b: {BYTES}) -> {MAYBE_BYTES}:",
                      f"  sel_bytes({name}_ok(b), slice(b, {rd['offset']}n, {rd['width']}n))", ""]
        elif kind == "predicate":
            lines += [f"# {name}: predicate {f['source']}: an ok path holds on the length and the tag byte",
                      f"def {name}(+b: {BYTES}) -> Bool:", f"  {go_condition(f['ok'])}", ""]
        elif kind == "loader":
            lines += [f"# {name}: loader {f['source']}; ok_{name} is its domain predicate",
                      f"def ok_{name}(+b: {BYTES}) -> Bool:", f"  {sol_condition(f['ok'])}", "",
                      f"def {name}(+b: {BYTES}) -> {MAYBE_BYTES}:", f"  sel_bytes(ok_{name}(b), b)", ""]
        else:
            raise Unsupported(f"{name}: kind {kind}")
    return "\n".join(lines).rstrip() + "\n"


class CompiledModel:
    """A component model compiled with the pinned Bend to an ES module (cached by the text's hash)."""

    def __init__(self, source: Path, artifact: Path, doc: dict, cfg: dict | None):
        self.source, self.artifact, self.doc, self.cfg = source, artifact, doc, cfg

    @classmethod
    def build(cls, doc: dict, sha: str, name: str, cfg: dict | None = None) -> "CompiledModel":
        text = generate(doc, sha)
        h = hashlib.sha256(text.encode()).hexdigest()
        src = bend.build_dir(ROOT) / "linked" / h[:16] / f"{name}.bend"
        src.parent.mkdir(parents=True, exist_ok=True)
        if not src.exists() or src.read_text() != text:
            src.write_text(text)
        art = src.with_suffix(".mjs")
        stamp = src.with_suffix(".src.sha256")
        if not (art.exists() and stamp.exists() and stamp.read_text() == h):
            r = bend.run([src.name, "-o", art.name], cwd=src.parent, cfg=cfg)
            if r.code != 0 or not art.exists():
                raise RuntimeError(f"bend failed to compile {src}: {r.out[:2000]}")
            stamp.write_text(h)
        return cls(src, art, doc, cfg)

    def calls(self, exprs: list) -> list:
        if not exprs:
            return []
        node = (self.cfg or bend.config()).get("node", "node")
        p = subprocess.run([node, str(DRIVER)], input=json.dumps({"module": str(self.artifact), "calls": exprs}),
                           capture_output=True, text=True, timeout=1800)
        if p.returncode != 0:
            raise RuntimeError(f"node evaluation failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)["results"]


# ====================================================================== statements
@dataclass
class Emitted:
    name: str
    text: str
    binders: list            # [(name, type)]: type a record carrier id or "Bytes"
    pins: dict               # binder -> {cell var: ("const", int) | ("cell", binder, cell var)}
    deps: dict               # binder -> [earlier binders its pin reads]
    hyps: list               # [(lhs, rhs, type)] Bend texts of the premises that are no pin
    lhs: str
    rhs: str
    claim_type: str
    classes: list = field(default_factory=list)   # the premise equivalence classes, for witnesses


class _Ctx:
    def __init__(self, doc: dict, law: dict):
        self.doc = doc
        st = law["statement"]
        if any(b.get("q", "forall") != "forall" for b in st.get("binders", [])):
            raise Unsupported("a component law is universal")
        self.binders = [(b["name"], binder_type(doc, b["type"])) for b in st.get("binders", [])]
        self.types = dict(self.binders)
        if len(self.types) != len(self.binders):
            raise Unsupported("two binders of one name")


def _hexbytes(s: str) -> list[int]:
    if not (isinstance(s, str) and s.startswith("0x") and len(s) % 2 == 0):
        raise Unsupported(f"bytes literal {s!r}")
    return list(bytes.fromhex(s[2:]))


def _field_width(doc: dict, cid: str, f: str) -> int:
    for x in records(doc).get(cid, []):
        if x["name"] == f:
            return x["width"]
    raise Unsupported(f"{cid} has no field {f}")


def premise_classes(doc: dict, law: dict, ctx: _Ctx) -> tuple[list[dict], list[dict]]:
    """The field premises as equivalence classes {"members": [(binder, field)], "const": bytes | None}, in binder and
    field order; and the premises that are no field equation."""
    order = {}
    for i, (n, t) in enumerate(ctx.binders):
        if t != "Bytes":
            for j, fl in enumerate(records(doc)[t]):
                order[(n, fl["name"])] = (i, j)
    parent: dict = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x
    consts: dict = {}
    other = []

    def slot(t):
        if (isinstance(t, dict) and set(t) == {"field", "of"} and isinstance(t["of"], dict) and set(t["of"]) == {"var"}
                and ctx.types.get(t["of"]["var"]) not in (None, "Bytes")):
            key = (t["of"]["var"], t["field"])
            _field_width(doc, ctx.types[key[0]], key[1])
            return key
        return None
    for p in law["statement"].get("assume", []):
        if set(p) != {"eq"}:
            raise Unsupported(f"premise form {sorted(p)}")
        a, b = p["eq"]
        sa, sb = slot(a), slot(b)
        if sa and sb:
            if _field_width(doc, ctx.types[sa[0]], sa[1]) != _field_width(doc, ctx.types[sb[0]], sb[1]):
                raise Unsupported(f"a correspondence of fields of two widths: {p}")
            ra, rb = find(sa), find(sb)
            if ra != rb:
                parent[max(ra, rb, key=lambda x: order[x])] = min(ra, rb, key=lambda x: order[x])
        elif (sa and isinstance(b, dict) and set(b) == {"bytes"}) or (sb and isinstance(a, dict) and set(a) == {"bytes"}):
            s, c = (sa, b) if sa else (sb, a)
            val = _hexbytes(c["bytes"])
            if len(val) != _field_width(doc, ctx.types[s[0]], s[1]):
                raise Unsupported(f"a pin of {len(val)} bytes on a field of another width: {p}")
            find(s)
            consts.setdefault(s, []).append(val)
        else:
            other.append(p)
    classes: dict = {}
    for x in list(parent):
        classes.setdefault(find(x), []).append(x)
    out = []
    for rep, members in classes.items():
        members.sort(key=lambda x: order[x])
        vals = {tuple(v) for m in members for v in consts.get(m, [])}
        if len(vals) > 1:
            raise Unsupported(f"contradictory premises on {members}: a vacuous law")
        out.append({"members": members, "const": list(vals.pop()) if vals else None})
    out.sort(key=lambda c: order[c["members"][0]])
    return [c for c in out if len(c["members"]) > 1 or c["const"] is not None], other


def _pins(doc: dict, ctx: _Ctx, classes: list[dict]) -> tuple[dict, dict]:
    """binder -> {cell var: replacement}, binder -> [earlier binders read]."""
    pins: dict = {}
    deps: dict = {}
    for c in classes:
        rep = c["members"][0]
        w = _field_width(doc, ctx.types[rep[0]], rep[1])
        for m in c["members"]:
            if c["const"] is None and m == rep:
                continue
            for k in range(w):
                tv = cell_var(m[1], k)
                if c["const"] is not None:
                    pins.setdefault(m[0], {})[tv] = ("const", c["const"][k])
                else:
                    pins.setdefault(m[0], {})[tv] = ("cell", rep[0], cell_var(rep[1], k))
                    if rep[0] != m[0]:
                        deps.setdefault(m[0], [])
                        if rep[0] not in deps[m[0]]:
                            deps[m[0]].append(rep[0])
    for b in deps:
        deps[b].sort(key=lambda x: [n for n, _ in ctx.binders].index(x))
    return pins, deps


def _pin_def(doc: dict, ctx: _Ctx, b: str, pins: dict, deps: list[str]) -> list[str]:
    cid = ctx.types[b]
    params = [f"{b}: {ALIAS}.{rec_type(cid)}"] + [f"+{d}: {ALIAS}.{rec_type(ctx.types[d])}" for d in deps]
    lines = [f"# the premises on {b}, by pinning", f"def pin_{b}({', '.join(params)}) -> {ALIAS}.{rec_type(cid)}:",
             f"  match {b}:", f"    case {_pattern(doc, cid, prefix=b + '_', alias=ALIAS)}:"]
    ind = 6
    for d in deps:
        lines += [" " * ind + f"match {d}:", " " * (ind + 2) + f"case {_pattern(doc, ctx.types[d], prefix=d + '_', alias=ALIAS)}:"]
        ind += 4
    vals = []
    for _, _, v in cells_of(doc, cid):
        r = pins.get(v)
        if r is None:
            vals.append(f"{b}_{v}")
        elif r[0] == "const":
            vals.append(str(int(r[1])))
        else:
            vals.append(f"{r[1]}_{r[2]}")
    lines.append(" " * ind + f"{ALIAS}.{rec_type(cid)}{{" + ", ".join(vals) + "}")
    return lines


def _term(doc: dict, t, env: dict, types: dict) -> tuple[str, str]:
    if not isinstance(t, dict):
        raise Unsupported(f"term {t}")
    if set(t) == {"var"}:
        return env[t["var"]], types[t["var"]]
    if set(t) == {"bytes"}:
        return _list([str(x) for x in _hexbytes(t["bytes"])]), "Bytes"
    if set(t) == {"bool"}:
        return ("True{}" if t["bool"] else "False{}"), "Bool"
    if set(t) == {"field", "of"}:
        x, tx = _term(doc, t["of"], env, types)
        if tx in ("Bytes", "MaybeBytes", "Bool"):
            raise Unsupported(f"a field of a {tx} term")
        _field_width(doc, tx, t["field"])
        return f"{ALIAS}.{getter(tx, t['field'])}({x})", "Bytes"
    if set(t) == {"call", "args"}:
        sig = fn_type(doc, t["call"])
        if sig is None or len(t["args"]) != 1:
            raise Unsupported(f"call of {t['call']}")
        x, tx = _term(doc, t["args"][0], env, types)
        if tx != sig[0]:
            raise Unsupported(f"ill-typed call {t['call']}({tx})")
        return f"{ALIAS}.{t['call']}({x})", sig[1]
    if set(t) == {"some"}:
        x, tx = _term(doc, t["some"], env, types)
        if tx != "Bytes":
            raise Unsupported("Some of a non-bytes term")
        return f"{{Some{{{x}}} : {MAYBE_BYTES}}}", "MaybeBytes"
    raise Unsupported(f"term {t}")


def law_name(law_id: str, counter: bool = False) -> str:
    return ("cl_" if counter else "") + law_id.lower()


def emit(law: dict, doc: dict, model_import: str, counter: bool = False, note: str = "") -> Emitted:
    """LAWS.bend of a component law (premises by pinning, the rest as hypothesis binders), or its counter-law."""
    ctx = _Ctx(doc, law)
    classes, other = premise_classes(doc, law, ctx)
    pins, deps = _pins(doc, ctx, classes)
    env = {n: (f"pin_{n}({', '.join([n] + deps.get(n, []))})" if n in pins else n) for n, _ in ctx.binders}
    hyps = []
    for p in other:
        (a, ta), (b, tb) = (_term(doc, x, env, ctx.types) for x in p["eq"])
        if ta != tb:
            raise Unsupported(f"premise sides of two types: {p}")
        hyps.append((a, b, ta))
    c = law["statement"]["claim"]
    if set(c) != {"eq"}:
        raise Unsupported("a component law states one equation")
    (lhs, tl), (rhs, tr) = (_term(doc, x, env, ctx.types) for x in c["eq"])
    if tl != tr:
        raise Unsupported(f"claim sides of two types: {tl} / {tr}")
    name = law_name(law["law_id"], counter)
    lines = ["# GENERATED by holon.gen.linked from the frozen law IR; do not edit.",
             f"# law_id: {law['law_id']}   statement_hash: {note}", "import Base", f"import {model_import} as {ALIAS}", ""]
    for n, _ in ctx.binders:
        if n in pins:
            lines += _pin_def(doc, ctx, n, pins[n], deps.get(n, [])) + [""]
    q = "exs" if counter else "for"
    lines.append(f"law {name}:")
    for n, t in ctx.binders:
        lines.append(f"  {q} {'' if counter else '+'}{n}: {bend_type(t)}")
    for i, (a, b, t) in enumerate(hyps):
        lines.append(f"  {q} h{i}: {{{a} == {b} : {bend_type(t)}}}")
    lines.append(f"  {{{lhs} {'!=' if counter else '=='} {rhs} : {bend_type(tl)}}}")
    return Emitted(name, "\n".join(lines) + "\n", ctx.binders, pins, deps, hyps, lhs, rhs, tl, classes)


def statement_text(law: dict, doc: dict, model_import: str, note: str = "") -> str:
    return emit(law, doc, model_import, note=note).text


# ====================================================================== proofs and counter-laws
HEADER = ["# GENERATED by holon.gen.linked; untrusted, accepted only if Bend checks it.", "import Base"]


def _imports(model_import: str) -> list[str]:
    return HEADER + [f"import {model_import} as {ALIAS}", "import ./LAWS.bend as Laws", ""]


def open_refl(em: Emitted, doc: dict, model_import: str) -> str | None:
    """Open every record binder, then reflexivity (M0's class): decides layout equalities over symbolic fields."""
    if em.hyps or any(t == "Bytes" for _, t in em.binders):
        return None
    lines = [f"# class open_refl: open {len(em.binders)} record binder(s), then reflexivity",
             f"def Laws.{em.name}({', '.join(n for n, _ in em.binders)}):"]
    ind = 2
    for n, t in em.binders:
        lines += [" " * ind + f"match {n}:", " " * (ind + 2) + f"case {_pattern(doc, t, prefix=n + '_', reuse=False, alias=ALIAS)}:"]
        ind += 4
    lines.append(" " * ind + "{==}")
    return "\n".join(_imports(model_import) + lines) + "\n"


def literal(doc: dict, t: str, v) -> str:
    """The Bend literal of a witness value: a record {field: "0x.."} or bytes "0x..", in the proof module."""
    if t == "Bytes":
        return _list([str(x) for x in _hexbytes(v)])
    cells = []
    for f in records(doc)[t]:
        bs = _hexbytes(v[f["name"]])
        if len(bs) != f["width"]:
            raise ValueError(f"witness field {f['name']} has {len(bs)} bytes, expected {f['width']}")
        cells += [str(x) for x in bs]
    return f"{ALIAS}.{rec_type(t)}{{" + ", ".join(cells) + "}"


def _at(em: Emitted, side: str, lits: dict) -> str:
    out = side
    for n, _ in em.binders:
        if n in em.pins:
            call = f"pin_{n}({', '.join([n] + em.deps.get(n, []))})"
            args = ", ".join(lits[x] for x in [n] + em.deps.get(n, []))
            out = out.replace(call, f"Laws.pin_{n}({args})")
    for n, _ in em.binders:
        out = re.sub(rf"(?<![\w.]){re.escape(n)}(?![\w])", lambda _m, n=n: lits[n], out)
    return out


EQ_FN = {"Bytes": "eq_bytes", "MaybeBytes": "eq_maybe_bytes", "Bool": "eq_bool"}


def counter(em: Emitted, doc: dict, model_import: str, witness: dict) -> str:
    """The counter-law's proof at a concrete witness (BEND_PRIMER §5.4): the witness, each premise by computation,
    then the sides separated by the model's (untrusted) equality function."""
    lits = {n: literal(doc, t, witness[n]) for n, t in em.binders}
    at_lhs = _at(em, em.lhs, lits)
    eq = f"{ALIAS}.{EQ_FN[em.claim_type]}"
    parts = [lits[n] for n, _ in em.binders] + ["{==}"] * len(em.hyps)
    tup = f"e => (%e : {ALIAS}.is_true({eq}(_, {at_lhs}))\n  Unit{{}})"
    for p in reversed(parts):
        tup = f"({p}, {tup})"
    lines = ["# class counter: concrete witness; premises by computation; the motive is Unit at the lhs and Empty at "
             "the rhs", f"def Laws.{em.name}():", f"  {tup}"]
    return "\n".join(_imports(model_import) + lines) + "\n"


# ====================================================================== witnesses and evaluation
def _rec_value(doc: dict, t: str, v: dict) -> dict:
    out = {"$": rec_type(t)}
    for f in records(doc)[t]:
        bs = _hexbytes(v[f["name"]])
        for k in range(f["width"]):
            out[cell_var(f["name"], k)] = bs[k]
    return out


def js_term(doc: dict, t, wit: dict, types: dict):
    """An IR term at a witness, as a linked.mjs expression."""
    if set(t) == {"var"}:
        v, ty = wit[t["var"]], types[t["var"]]
        return {"val": _hexbytes(v)} if ty == "Bytes" else {"val": _rec_value(doc, ty, v)}
    if set(t) == {"bytes"}:
        return {"val": _hexbytes(t["bytes"])}
    if set(t) == {"bool"}:
        return {"val": bool(t["bool"])}
    if set(t) == {"field", "of"}:
        return {"fn": getter(types[t["of"]["var"]], t["field"]), "args": [js_term(doc, t["of"], wit, types)]}
    if set(t) == {"call", "args"}:
        return {"fn": t["call"], "args": [js_term(doc, a, wit, types) for a in t["args"]]}
    if set(t) == {"some"}:
        return {"some": js_term(doc, t["some"], wit, types)}
    raise Unsupported(f"term {t}")


def _calls_in(t) -> list:
    out = []
    if isinstance(t, dict):
        if isinstance(t.get("call"), str):
            out.append(t)
        for v in t.values():
            out += _calls_in(v)
    elif isinstance(t, list):
        for v in t:
            out += _calls_in(v)
    return out


def canon_value(v):
    """A model value in canonical JSON: bytes "0x..", Some -> the value, None -> null, Bool as is."""
    if isinstance(v, list):
        if any(not (isinstance(x, int) and 0 <= x <= 255) for x in v):
            raise ValueError("undefined")
        return "0x" + bytes(v).hex()
    if isinstance(v, dict) and "$some" in v:
        return {"some": canon_value(v["$some"])}
    if isinstance(v, dict) and "error" in v:
        raise ValueError(v["error"])
    return v


def apply_classes(doc: dict, types: dict, classes: list[dict], raw: dict) -> dict:
    """A raw assignment with every premise class applied (constants, then each member equal to its representative)."""
    out = {n: (dict(v) if isinstance(v, dict) else v) for n, v in raw.items()}
    for c in classes:
        rep = c["members"][0]
        val = "0x" + bytes(c["const"]).hex() if c["const"] is not None else out[rep[0]][rep[1]]
        for b, f in c["members"]:
            out[b][f] = val
    return out


def _int(v: str) -> int:
    return int(v, 16) if v != "0x" else 0


def encoder_reaches(doc: dict, law: dict, wit: dict, types: dict) -> bool:
    """X9: at the witness, every atom over record fields only of the ok condition of every Solidity encoder the law
    names holds at the witness's version (the ok path whose version set holds the encoded record's tag field)."""
    from ..diagram.linked import eval_sol
    for call in _calls_in(law["statement"]):
        f = doc["functions"].get(call["call"])
        if not f or f["kind"] != "encoder" or not f.get("ok"):
            continue
        arg = call["args"][0]
        if set(arg) != {"var"}:
            continue
        rec = wit[arg["var"]]
        cid = types[arg["var"]]
        names = {x["name"] for x in records(doc)[cid]}
        env = {n: _int(rec[n]) for n in names}
        ok = False
        for cond in f["ok"]:
            vals = [eval_sol(a, env) for a in cond]
            if all(v is None or v != 0 for v in vals) and all(_only_fields(a, names) for a in cond):
                ok = True
                break
        if not ok:
            return False
    return True


def _only_fields(e, names: set) -> bool:
    """Whether a Solidity condition atom mentions record fields only (no input length or byte, no other name)."""
    if isinstance(e, str):
        return e in names
    if isinstance(e, list) and e:
        if e[0] in ("len", "byte"):
            return False
        return all(_only_fields(x, names) for x in e[1:])
    return True


def fills(doc: dict, binders: list) -> list[tuple[str, dict]]:
    """Deterministic raw assignments of the record binders (labelled): ones, counting, 0xff, zeros, one field 0xff,
    and fixed-seed random fills."""
    recs = [(n, t) for n, t in binders if t != "Bytes"]
    total = [(n, f["name"], f["width"]) for n, t in recs for f in records(doc)[t]]

    def build(fill) -> dict:
        out: dict = {n: {} for n, _ in recs}
        i = 0
        for n, fname, w in total:
            out[n][fname] = "0x" + bytes(fill(n, fname, i + k) for k in range(w)).hex()
            i += w
        return out
    out = [("ones", build(lambda n, f, i: 1)), ("counting", build(lambda n, f, i: (i % 255) + 1)),
           ("0xff", build(lambda n, f, i: 0xFF)), ("zeros", build(lambda n, f, i: 0))]
    for n, fname, _ in total:
        out.append((f"only {n}.{fname}=0xff", build(lambda b, f, i, n=n, fname=fname: 0xFF if (b, f) == (n, fname) else 1)))
    rng = random.Random(SEED)
    for r in range(RANDOM_FILLS):
        cells = {(n, f, k): rng.randrange(256) for n, f, w in total for k in range(w)}
        offs, i = {}, 0
        for n, f, w in total:
            offs[(n, f)] = i
            i += w
        out.append((f"random#{r}", build(lambda b, f, i, c=cells, o=offs: c[(b, f, i - o[(b, f)])])))
    return out


def _consts(e, out: set) -> set:
    if isinstance(e, list):
        for x in e:
            _consts(x, out)
    elif isinstance(e, int) and not isinstance(e, bool):
        out.add(e)
    return out


def probe_constants(doc: dict, names: list[str]) -> list[int]:
    ks: set = set()
    fs = doc["functions"]
    for n in names:
        f = fs.get(n)
        if f is None and n.startswith("ok_"):
            f = fs.get(n[3:])
        for cond in (f or {}).get("ok") or []:
            _consts(cond, ks)
    return sorted(ks)


def probes(ks: list[int]) -> list[tuple[int, int]]:
    """(length, tag byte) probes: k - 1, k, k + 1 (those >= 0) and 0 for every constant k, as lengths; those below 256
    as tag bytes; length 0 only with tag 0; sorted by (length, tag)."""
    vals = sorted({0} | {x for k in ks for x in (k - 1, k, k + 1) if x >= 0})
    tags = [v for v in vals if v < 256]
    return [(n, t) for n in vals for t in tags if n > 0 or t == 0]


def probe_bytes(n: int, t: int) -> str:
    """The probe byte string of length n and tag byte t: the tag byte, then distinct nonzero filler bytes."""
    if n == 0:
        return "0x"
    return "0x" + bytes([t] + [((i * 37) % 255) + 1 for i in range(1, n)]).hex()


def tag_premise_version(doc: dict, law: dict) -> int | None:
    """X8c: the version a law's tag premise fixes (its tag decoder reads the one byte v), else None."""
    tag = doc["tag_index"]
    for p in law["statement"].get("assume", []):
        a, b = p.get("eq", [None, None])
        if (isinstance(a, dict) and set(a) == {"call", "args"} and isinstance(b, dict) and set(b) == {"some"}
                and isinstance(b["some"], dict) and set(b["some"]) == {"bytes"}):
            f = doc["functions"].get(a["call"]) or {}
            rd = f.get("read") or {}
            bs = _hexbytes(b["some"]["bytes"])
            if f.get("kind") == "decoder" and (rd.get("offset"), rd.get("width")) == (tag, 1) and len(bs) == 1:
                return bs[0]
    return None


def evaluate(cm: CompiledModel, law: dict, types: dict, wits: list[dict]) -> list[dict]:
    """For each witness: the premises' and the claim's sides on the compiled model, and every call inside them,
    decoded: {"premises": [(l, r)], "claim": (l, r), "subcalls": [v]}; a value an error made undefined is None."""
    st = law["statement"]
    doc = cm.doc
    exprs, plan = [], []
    for w in wits:
        start = len(exprs)
        for p in st.get("assume", []):
            exprs += [js_term(doc, x, w, types) for x in p["eq"]]
        exprs += [js_term(doc, x, w, types) for x in st["claim"]["eq"]]
        subs = [c for x in st["claim"]["eq"] for c in _calls_in(x)]
        exprs += [js_term(doc, c, w, types) for c in subs]
        plan.append((start, len(st.get("assume", [])), len(subs)))
    vals = cm.calls(exprs)
    out = []
    for start, np_, ns in plan:
        v = vals[start:start + 2 * np_ + 2 + ns]
        out.append({"premises": [(v[2 * i], v[2 * i + 1]) for i in range(np_)], "claim": (v[2 * np_], v[2 * np_ + 1]),
                    "subcalls": v[2 * np_ + 2:]})
    return out


def _defined(v) -> bool:
    try:
        canon_value(v)
        return True
    except (ValueError, TypeError):
        return False


def _same(a, b) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# ====================================================================== deciding one law
@dataclass
class Decision:
    status: str
    em: Emitted | None = None          # the LAWS.bend checked (statement or counter-law)
    statement: Emitted | None = None   # the frozen statement as emitted
    check: object = None
    witness: dict | None = None
    difference: dict | None = None
    bound: str | None = None
    attempts: list = field(default_factory=list)


def _first(out: str, n: int = 14) -> str:
    return "\n".join(out.strip().splitlines()[:n])


def decide(law: dict, cm: CompiledModel, ld: Path, pd: Path, model_import_l: str, model_import_p: str, cfg: dict,
           note: str, write_pair, accepted) -> Decision:
    """Rule X9 for one component law: the proof class over records, else the counter-law at a witness of the compiled
    model (fills for record laws, probes for byte-string laws), else UNKNOWN with its bound. write_pair and accepted
    are holon.mpipeline's (prover separation, I10; the acceptance point, F-M2-07)."""
    doc = cm.doc
    d = Decision("UNKNOWN")
    try:
        em = emit(law, doc, model_import_l, note=note)
    except Unsupported as e:
        d.attempts.append({"kind": "emit", "error": f"unsupported statement form: {e}"})
        d.bound = "not searched: the emitter cannot express this statement faithfully"
        return d
    d.statement = em
    types = dict(em.binders)
    byte_law = any(t == "Bytes" for _, t in em.binders)
    text = open_refl(em, doc, model_import_p)
    if text is None:
        d.attempts.append({"kind": "proof", "generator": "open_refl", "error": (
            "does not apply: a law over unbounded byte strings has no proof route here (gap G6)" if byte_law else
            "does not apply: the statement has a premise that is no field pin")})
    else:
        pf = write_pair(ld, pd, em.text, text)
        rr = bend.check(pf, cfg)
        ok, why = accepted(rr, pf, ld / "LAWS.bend", em, text)
        d.attempts.append({"kind": "proof", "generator": "open_refl", "exit_code": rr.code, "marker": rr.marker,
                           "seconds": rr.seconds, **({} if ok else {"error": why})})
        if ok:
            d.status, d.em, d.check = "PROVED", em, rr
            return d
    if byte_law:
        found, bound, tried = _probe_search(cm, law, types)
    else:
        found, bound, tried = _fill_search(cm, law, types, em)
    d.attempts.append({"kind": "refute", "engine": "compiled-model probes" if byte_law else "compiled-model fills",
                       "bound": bound, "tried": tried, "hit": found is not None})
    d.bound = bound
    if found is None:
        return d
    wit, diff = found
    em2 = emit(law, doc, model_import_l, counter=True, note=note)
    try:
        text = counter(em2, doc, model_import_p, wit)
    except (ValueError, KeyError) as e:
        d.attempts.append({"kind": "counter-law", "generator": "counter", "error": f"inexpressible: {e}"})
        return d
    for x in {ld, pd}:
        shutil.rmtree(x, ignore_errors=True)
    pf = write_pair(ld, pd, em2.text, text)
    rr = bend.check(pf, cfg)
    ok, why = accepted(rr, pf, ld / "LAWS.bend", em2, text)
    d.attempts.append({"kind": "counter-law", "generator": "counter", "exit_code": rr.code, "marker": rr.marker,
                       "seconds": rr.seconds, **({} if ok else {"error": why})})
    if ok:
        d.status, d.em, d.check, d.witness, d.difference = "REFUTED", em2, rr, wit, diff
    return d


def _fill_search(cm: CompiledModel, law: dict, types: dict, em: Emitted):
    doc = cm.doc
    cands = []
    for label, raw in fills(doc, em.binders):
        w = apply_classes(doc, types, em.classes, raw)
        if not encoder_reaches(doc, law, w, types):
            continue
        cands.append((label, w))
    bound = (f"record fills (ones, counting, 0xff, zeros, one field 0xff, {RANDOM_FILLS} random with seed {SEED}), the "
             "premises applied, kept when the named encoders' ok atoms over record fields hold "
             f"({len(cands)} candidates)")
    if not cands:
        return None, bound, 0
    res = evaluate(cm, law, types, [w for _, w in cands])
    for (label, w), r in zip(cands, res):
        if not all(_defined(v) for v in r["subcalls"] + list(r["claim"])):
            continue
        if not all(_same(a, b) for a, b in r["premises"]):
            continue
        lv, rv = r["claim"]
        if not _same(lv, rv):
            return (w, {"lhs": canon_value(lv), "rhs": canon_value(rv)}), bound + f"; hit: {label}", len(cands)
    return None, bound, len(cands)


def _probe_search(cm: CompiledModel, law: dict, types: dict):
    doc = cm.doc
    names = sorted({c["call"] for c in _calls_in(law["statement"]["claim"])})
    ks = probe_constants(doc, names)
    ps = probes(ks)
    v = tag_premise_version(doc, law)
    if v is not None:
        ps = [(n, v) for n in sorted({n for n, _ in ps}) if n > 0]
    var = [n for n, t in types.items() if t == "Bytes"]
    if len(var) != 1 or len(types) != 1:
        return None, "not searched: a byte-string law over one byte-string binder only", 0
    lens = sorted({n for n, _ in ps})
    tags = sorted({t for _, t in ps})
    bound = (f"probes (length, tag byte) from the integer constants {ks} of the ok conditions of {names}: lengths "
             f"{lens} x tag bytes {tags}" + (f" (the tag premise: tag byte {v}, length >= 1)" if v is not None else
                                             " (length 0 with tag 0 only)")
             + f", {len(ps)} probes, filler bytes ((i * 37) mod 255) + 1; no probe distinguishes the two sides, and a "
             "law over unbounded byte strings has no proof route here (gap G6)")
    wits = [{var[0]: probe_bytes(n, t)} for n, t in ps]
    res = evaluate(cm, law, types, wits) if wits else []
    for (n, t), w, r in zip(ps, wits, res):
        if not all(_same(a, b) for a, b in r["premises"]):
            continue
        lv, rv = r["claim"]
        if not (_defined(lv) and _defined(rv)):
            continue
        if not _same(lv, rv):
            return (w, {"lhs": canon_value(lv), "rhs": canon_value(rv)}), \
                bound.split("; no probe")[0] + f"; first difference at length {n}, tag byte {t}", len(ps)
    return None, bound, len(ps)


# ====================================================================== non-vacuity (G11V)
def _getter_props(em: Emitted, doc: dict, law: dict) -> list[str]:
    ctx_types = dict(em.binders)
    out = []
    for p in law["statement"].get("assume", []):
        (a, ta), (b, tb) = (_term(doc, x, {n: n for n, _ in em.binders}, ctx_types) for x in p["eq"])
        out.append(f"{{{a} == {b} : {bend_type(ta)}}}")
    return out


def inhabitant_texts(law: dict, doc: dict, model_stem: str, witness: dict) -> tuple[str, str, str]:
    """(law name, LAWS.bend, PROOF.bend) of a component law's non-vacuity inhabitant: its binders made existential
    and its premises, through the getters and calls, as the claim, at the witness (zeros elsewhere)."""
    em = emit(law, doc, f"../../model/{model_stem}.bend")
    name = "nv_" + law["law_id"].lower()
    imp = f"../../model/{model_stem}.bend"
    props = _getter_props(em, doc, law)
    lines = [f"# GENERATED by holon.gen.linked: non-vacuity inhabitant of {law['law_id']}.", "import Base",
             f"import {imp} as {ALIAS}", "", f"law {name}:"]
    lines += [f"  exs {n}: {bend_type(t)}" for n, t in em.binders]
    lines += [f"  exs c{i}: {p}" for i, p in enumerate(props[:-1])] + [f"  {props[-1]}"]
    parts = [literal(doc, t, witness[n]) for n, t in em.binders] + ["{==}"] * len(props)
    tup = parts[-1]
    for p in reversed(parts[:-1]):
        tup = f"({p}, {tup})"
    proof = "\n".join(["# GENERATED by holon.gen.linked; accepted only if Bend checks it.", "import Base",
                       f"import {imp} as {ALIAS}", "import ./LAWS.bend as Laws", "",
                       "# class evaluate: the premises' witness, then every premise by computation",
                       f"def Laws.{name}():", f"  {tup}"]) + "\n"
    return name, "\n".join(lines) + "\n", proof


def inhabitant_witness(law: dict, doc: dict) -> dict:
    """Zeros everywhere, the premise classes applied."""
    em = emit(law, doc, "../../model/x.bend")
    raw = dict(fills(doc, em.binders))["zeros"]
    return apply_classes(doc, dict(em.binders), em.classes, raw)


# ====================================================================== the model's ledger bundle
def _slug(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9-]+", "-", s).strip("-")
    return out or "assumption"


def declared_bundle(doc: dict, rel: str, sha: str, root: Path) -> dict:
    """The ledger bundle of a component model (holon.records): every assumption the two documents declare
    (their "assumptions"), each introduced by the definitions generated from that document's functions and records,
    and the layer's own A-codec-domain (rule X5: encoders' domains are not modelled), introduced by the encoders."""
    names = model_names(doc)
    by_doc: dict[str, list[str]] = {}
    for name, f in doc["functions"].items():
        defs = [n for n, what in names.items() if what == f"function {name}"]
        by_doc.setdefault(f["document"], []).extend(defs)
    for cid, c in doc["carriers"].items():
        if c["kind"] == "record":
            by_doc.setdefault(c["document"], []).extend(n for n, what in names.items() if what == f"record {cid}")
    entries, seen = [], set()
    for drel in doc["documents"]:
        try:
            src = json.loads((Path(root) / drel).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            src = {}
        for i, a in enumerate(src.get("assumptions") or []):
            if not isinstance(a, dict) or not isinstance(a.get("id"), str):
                continue
            aid = _slug(a["id"])
            while aid in seen:
                aid += "-2"
            seen.add(aid)
            entries.append({"id": aid, "kind": "abstraction", "source": f"{drel}#/assumptions/{i}",
                            "text": a.get("text", ""), "introduced_by": sorted(set(by_doc.get(drel, [])))})
    encs = sorted(n for name, f in doc["functions"].items() if f["kind"] == "encoder"
                  for n, what in names.items() if what == f"function {name}")
    entries.append({"id": "A-codec-domain", "kind": "abstraction", "source": f"{rel}#/functions",
                    "text": "An encoder's value at a version is its layout there; the other atoms of its ok conditions "
                            "(input checks, a cache path that returns a stored value) are its domain, recorded in the "
                            "linked codec document and not modelled (rule X5).",
                    "introduced_by": encs})
    return {"facts": rel, "facts_sha256": sha, "model": f"model/{doc['component']}",
            "doc": "The component model of a linked codec document (holon.gen.linked): the assumptions its two extracted "
                   "documents declare, and the linked codec layer's own (generated from the document, never hand-written).",
            "entries": entries,
            "no_assumption": [{"defs": list(PRELUDE_DEFS), "why": "byte-list and equality utilities of the generator "
                                                                  "prelude; no modelling choice"}]}
