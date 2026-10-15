"""Lean model, statements and proofs of a holon-linked codec document (I43 rule L1, kind linked; rules L2-L4).

The model reads the codec document itself, never holon.gen.linked (rule L1), and agrees with the Bend component
model holon.gen.linked compiles from the same document on every byte-valued record:

  * the frozen abbrev Cell := Option (BitVec 8) and Bytes := List Cell, and a structure R_<carrier> per record
    carrier, one BitVec 8 per byte in field order (byte k of field F is f_<F with . written __>_<k>), verbatim and
    without deriving;
  * an encoder c_<f> is its layout, a list literal over the record's bytes (a field cell some h.f_<F>_<k>, a constant
    cell some 0x.., any other cell none); an encoder with several layouts dispatches on the value of its one-byte tag
    field (the cell every layout holds at the document's tag index), and a version without a layout is [none] (Bend's
    one-cell [57005]);
  * a decoder c_<f> is sel (c_ok_<f> b) (slice b <offset> <width>), its ok condition c_ok_<f> the disjunction of its
    ok paths over the input's length and bytes; a predicate c_<f> is that condition itself; a loader c_<f> is
    sel (c_ok_<f> b) b with its domain condition c_ok_<f>;
  * conditions are Bool terms (Nat.beq, Nat.ble, Nat.blt, !, &&, ||) over List.length b and byte_at b k, which reads
    an undefined cell or a position past the end as 57005, so the orderings agree with Bend's U32 cells (reading
    LP-G1). Every definition is structurally recursive or not recursive at all, so decide and rfl evaluate it.

Statements (rule L3, kind linked): binders in IR order as (v_<name> : Model.R_<carrier>) or (v_<name> : Model.Bytes);
premises as hypotheses; a field as the list of its cells, a byte constant as a list of some 0x..; a call as
Model.c_<function> (Model.c_ok_<loader> for a loader's condition); claim eq/neq as =/≠ and a conjunction as ∧. A
PROVED law is `theorem <law id> : ∀ .., <premises> → <claim>`; a REFUTED law is `theorem <law id>_counter : ∃ ..,
<premises> ∧ <negated claim>` and `theorem <law id>_refuted : ¬ (<statement>)`.

Classes: open_refl (a law over records: without premises, rfl after the binders; with premises over record fields
and byte constants, every record opened into its cell variables, each premise split into its cell equations and
substituted, then rfl) and counter_decide (a REFUTED law at the record's witness: the witness values as noncomputable
definitions, the counter-law by decide, the refutation from it).
"""
from __future__ import annotations

import re

from .lean_common import COUNTER_CLASS, Model, Theorem, Unsupported, ident

UNDEF = 57005          # Bend's undefined cell (0xDEAD, never a byte): a Lean none, which byte_at reads as this number
BYTES = "Bytes"        # the IR type of a byte string: a field's cells, a byte constant, a decoder's input
U32_LIMIT = 1 << 32
CMP = ("==", "!=", "<", "<=", ">", ">=")
HEX = re.compile(r"0x(?:[0-9a-fA-F]{2})*")
PER_LINE = 8           # cells per line in the list literals of the model and of a witness

# the helpers every linked model declares after the frozen types (no name from a document has these prefixes)
PRELUDE = (
    "def cell_nat : Cell → Nat\n"
    f"  | none => {UNDEF}\n"
    "  | some x => x.toNat",
    "def byte_at : Bytes → Nat → Nat\n"
    f"  | [], _ => {UNDEF}\n"
    "  | c :: _, 0 => cell_nat c\n"
    "  | _ :: t, n + 1 => byte_at t n",
    "def slice (b : Bytes) (off w : Nat) : Bytes :=\n"
    "  List.take w (List.drop off b)",
    "def sel : Bool → Bytes → Option Bytes\n"
    "  | true, x => some x\n"
    "  | false, _ => none",
)


# ====================================================================================== the document
def _records(codec: dict) -> dict[str, list[dict]]:
    return {cid: c.get("fields") or [] for cid, c in codec["carriers"].items() if c.get("kind") == "record"}


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _cell(field: str, k: int) -> str:
    """The Lean field of byte k of record field `field` (a Go field path's . written __)."""
    return f"{ident('f_', field.replace('.', '__'))}_{int(k)}"


def _record_type(cid: str) -> str:
    return ident("R_", cid)


def _fn(name: str) -> str:
    return ident("c_", name)


def _ok(name: str) -> str:
    return ident("c_ok_", name)


def _byte(v) -> str:
    if not _is_int(v) or not 0 <= v <= 255:
        raise Unsupported(f"a byte constant {v!r} outside 0..255 (a Lean cell is a BitVec 8)")
    return f"0x{v:02x}"


def _hex_bytes(h) -> list[int]:
    if not isinstance(h, str) or not HEX.fullmatch(h):
        raise Unsupported(f"bytes {str(h)[:40]!r}")
    return list(bytes.fromhex(h[2:]))


def _list(cells: list[str], indent: str) -> str:
    """A list literal, PER_LINE cells per line, its continuation lines at `indent`."""
    if not cells:
        return "[]"
    rows = [", ".join(cells[i:i + PER_LINE]) for i in range(0, len(cells), PER_LINE)]
    return "[" + (",\n" + indent + " ").join(rows) + "]"


# ====================================================================================== conditions
def _param(t) -> bool:
    return isinstance(t, list) and t[:1] == ["param"]


def _go_term(t) -> tuple[str, object]:
    """A Go condition term: the input's length (Nat), its byte k (a U32 cell in Bend), or an integer constant."""
    if isinstance(t, list) and len(t) == 2 and t[0] == "len" and _param(t[1]):
        return "Nat", "(List.length b)"
    if isinstance(t, list) and len(t) == 3 and t[0] == "index" and _param(t[1]) and isinstance(t[2], list) \
            and len(t[2]) == 2 and t[2][0] == "const" and _is_int(t[2][1]) and t[2][1] >= 0:
        return "U32", f"(byte_at b {t[2][1]})"
    if isinstance(t, list) and len(t) == 2 and t[0] == "const" and _is_int(t[1]):
        return "Int", t[1]
    raise Unsupported(f"condition term {str(t)[:80]}")


def _sol_term(t) -> tuple[str, object]:
    """A Solidity loader's condition term: the input's length, its byte k, or an integer constant."""
    if isinstance(t, list) and len(t) == 2 and t[0] == "len":
        return "Nat", "(List.length b)"
    if isinstance(t, list) and len(t) == 3 and t[0] == "byte" and _is_int(t[2]) and t[2] >= 0:
        return "U32", f"(byte_at b {t[2]})"
    if _is_int(t):
        return "Int", t
    raise Unsupported(f"condition term {str(t)[:80]}")


def _cmp(op: str, a: tuple[str, object], b: tuple[str, object]) -> str:
    """One comparison as a Bool term. Bend compares a length as a Nat and a byte as a U32 (an undefined byte is
    57005); both are Nat here, which agrees with Bend on every constant a U32 holds."""
    (ta, xa), (tb, xb) = a, b
    if ta == "Int" and tb == "Int":
        return "true" if {"==": xa == xb, "!=": xa != xb, "<": xa < xb, "<=": xa <= xb, ">": xa > xb,
                          ">=": xa >= xb}[op] else "false"
    ty = ta if ta != "Int" else tb
    if ta not in ("Int", ty) or tb not in ("Int", ty):
        raise Unsupported(f"a comparison of {ta} with {tb}")
    for t, x in ((ta, xa), (tb, xb)):
        if t == "Int" and (x < 0 or (ty == "U32" and x >= U32_LIMIT)):
            raise Unsupported(f"the constant {x} in a {ty} comparison")
    lhs, rhs = str(xa), str(xb)
    return {"==": f"(Nat.beq {lhs} {rhs})", "!=": f"(!(Nat.beq {lhs} {rhs}))", "<": f"(Nat.blt {lhs} {rhs})",
            "<=": f"(Nat.ble {lhs} {rhs})", ">": f"(Nat.blt {rhs} {lhs})", ">=": f"(Nat.ble {rhs} {lhs})"}[op]


def _and(xs: list[str]) -> str:
    if not xs:
        return "true"
    return xs[0] if len(xs) == 1 else "(" + " && ".join(xs) + ")"


def _or(xs: list[str], sep: str = " || ") -> str:
    if not xs:
        return "false"
    return xs[0] if len(xs) == 1 else "(" + sep.join(xs) + ")"


def _go_condition(paths) -> str:
    """A Go decoder's or predicate's ok paths (lists of comparisons over the input's length and bytes) as one Bool."""
    if not isinstance(paths, list):
        raise Unsupported("a function without ok paths")
    out = []
    for cond in paths:
        atoms = []
        for a in cond:
            if not (isinstance(a, list) and len(a) == 3 and a[0] in CMP):
                raise Unsupported(f"condition atom {str(a)[:80]}")
            atoms.append(_cmp(a[0], _go_term(a[1]), _go_term(a[2])))
        out.append(_and(atoms))
    return _or(out, " ||\n    ")


def _sol_bool(e) -> str:
    if isinstance(e, bool):
        return "true" if e else "false"
    if not isinstance(e, list) or not e:
        raise Unsupported(f"condition {str(e)[:80]}")
    if e[0] == "!" and len(e) == 2:
        return f"(!{_sol_bool(e[1])})"
    if e[0] == "&&":
        return _and([_sol_bool(x) for x in e[1:]])
    if e[0] == "||":
        return _or([_sol_bool(x) for x in e[1:]])
    if e[0] in CMP and len(e) == 3:
        return _cmp(e[0], _sol_term(e[1]), _sol_term(e[2]))
    raise Unsupported(f"condition {str(e)[:80]}")


def _sol_condition(paths) -> str:
    """A Solidity loader's ok paths (lists of conditions over its input's length and bytes) as one Bool."""
    if not isinstance(paths, list):
        raise Unsupported("a loader without ok paths")
    return _or([_and([_sol_bool(a) for a in cond]) for cond in paths], " ||\n    ")


# ====================================================================================== the model
def _tag_field(codec: dict, f: dict) -> str | None:
    """The one-byte record field an encoder's layouts all carry at the document's tag index (byte 0 of it)."""
    tag = codec.get("tag_index")
    widths = {x["name"]: x["width"] for x in _records(codec).get(f["from"], [])}
    names = set()
    for lay in f["layouts"].values():
        c = lay[tag] if _is_int(tag) and 0 <= tag < len(lay) else ["unknown"]
        if c[0] != "field" or len(c) != 3 or c[2] != 0 or widths.get(c[1]) != 1:
            return None
        names.add(c[1])
    return names.pop() if len(names) == 1 else None


def _layout(codec: dict, cid: str, lay, indent: str) -> str:
    widths = {x["name"]: x["width"] for x in _records(codec)[cid]}
    if not isinstance(lay, list):
        raise Unsupported("a layout that is no list of cells")
    cells = []
    for c in lay:
        if isinstance(c, list) and c[:1] == ["field"]:
            if len(c) != 3 or c[1] not in widths or not _is_int(c[2]) or not 0 <= c[2] < widths[c[1]]:
                raise Unsupported(f"layout cell {str(c)[:80]} of {cid}")
            cells.append(f"some h.{_cell(c[1], c[2])}")
        elif isinstance(c, list) and c[:1] == ["const"] and len(c) == 2:
            cells.append(f"some {_byte(c[1])}")
        else:
            cells.append("none")
    return _list(cells, indent)


def _encoder(codec: dict, name: str, f: dict) -> str:
    cid = f.get("from")
    if cid not in _records(codec):
        raise Unsupported(f"encoder {name} from {cid!r}, no record carrier")
    lays = f.get("layouts") or {}
    head = f"def {_fn(name)} (h : {_record_type(cid)}) : Bytes :=\n"
    if len(lays) == 1:
        return head + "  " + _layout(codec, cid, next(iter(lays.values())), "  ")
    tf = _tag_field(codec, f) if lays else None
    if tf is None or any(not k.isdigit() for k in lays):
        raise Unsupported(f"encoder {name}: several layouts not keyed by a one-byte tag field")
    top = max(int(k) for k in lays)
    alts = [f"  | {v} =>\n    {_layout(codec, cid, lays[str(v)], '    ')}" for v in range(top + 1) if str(v) in lays]
    return head + f"  match h.{_cell(tf, 0)}.toNat with\n" + "\n".join(alts) + "\n  | _ => [none]"


def _functions(codec: dict) -> list[str]:
    out = []
    for name, f in codec["functions"].items():
        kind = f.get("kind")
        if kind == "encoder":
            out.append(_encoder(codec, name, f))
        elif kind == "decoder":
            rd = f.get("read") or {}
            off, w = rd.get("offset"), rd.get("width")
            if not (_is_int(off) and _is_int(w) and off >= 0 and w >= 0):
                raise Unsupported(f"decoder {name} reads {rd!r}")
            out.append(f"def {_ok(name)} (b : Bytes) : Bool :=\n  {_go_condition(f.get('ok'))}")
            out.append(f"def {_fn(name)} (b : Bytes) : Option Bytes :=\n  sel ({_ok(name)} b) (slice b {off} {w})")
        elif kind == "predicate":
            out.append(f"def {_fn(name)} (b : Bytes) : Bool :=\n  {_go_condition(f.get('ok'))}")
        elif kind == "loader":
            out.append(f"def {_ok(name)} (b : Bytes) : Bool :=\n  {_sol_condition(f.get('ok'))}")
            out.append(f"def {_fn(name)} (b : Bytes) : Option Bytes :=\n  sel ({_ok(name)} b) b")
        else:
            raise Unsupported(f"linked function {name} of kind {kind!r}")
    return out


def _types(codec: dict) -> list[str]:
    """The frozen types (rule L2), verbatim."""
    out = ["abbrev Cell : Type := Option (BitVec 8)", "abbrev Bytes : Type := List Cell"]
    for cid, fields in _records(codec).items():
        cells = [f"  {_cell(x['name'], k)} : BitVec 8" for x in fields for k in range(x["width"])]
        out.append(f"structure {_record_type(cid)} where\n" + "\n".join(cells))
    return out


_DECL = re.compile(r"(?:def|abbrev|structure) ([A-Za-z_][A-Za-z0-9_]*)")


def model(codec: dict, stem: str) -> Model:
    """The Lean model of a linked codec document (models/<stem>.lean)."""
    if not codec.get("linked_version"):
        raise Unsupported("not a linked codec document")
    decls = _types(codec) + list(PRELUDE) + _functions(codec)
    names = [_DECL.match(d).group(1) for d in decls]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        raise Unsupported(f"the model would declare {', '.join(dup)} twice")
    return Model(stem=stem, decls=tuple(decls))


# ====================================================================================== statements (rule L3)
def _strip(s: str) -> str:
    """Drop one pair of outer parentheses enclosing a whole application (never a type ascription `(x : T)`)."""
    if not (s.startswith("(") and s.endswith(")")):
        return s
    depth = 0
    for i, ch in enumerate(s):
        depth += ch in "([{"
        depth -= ch in ")]}"
        if depth == 0 and i < len(s) - 1:
            return s
        if depth == 1 and s.startswith(" : ", i):
            return s
    return s[1:-1]


def _quant(q: str, bs: list, inner: str) -> str:
    if not bs:
        return inner
    return f"{q} " + " ".join(f"({name} : {ty})" for _, name, ty in bs) + ", " + inner


class _Render:
    """Rule L3 for the linked kind: IR terms and propositions as Lean text over the model (names Model.<name>)."""

    def __init__(self, codec: dict):
        self.records = _records(codec)
        self.fns = codec["functions"]
        self.carrier = codec.get("linked_carrier")

    def ty(self, t: str) -> tuple[str, str]:
        """A binder type: (Lean type, IR type)."""
        if t == self.carrier:
            return "Model.Bytes", BYTES
        if t in self.records:
            return f"Model.{_record_type(t)}", t
        raise Unsupported(f"binder type {t}")

    def term(self, t, env: dict) -> tuple[str, str]:
        if not isinstance(t, dict):
            raise Unsupported(f"term {t!r}")
        if "var" in t:
            v = env.get(t["var"])
            if v is None:
                raise Unsupported(f"unbound {t['var']}")
            return v
        if set(t) == {"field", "of"}:
            v, vt = self.term(t["of"], env)
            fld = next((x for x in self.records.get(vt, []) if x["name"] == t["field"]), None)
            if fld is None:
                raise Unsupported(f"field {t['field']} of {vt}")
            cells = ", ".join(f"some {v}.{_cell(fld['name'], k)}" for k in range(fld["width"]))
            return f"([{cells}] : Model.Bytes)", BYTES
        if set(t) == {"bytes"}:
            cells = ", ".join(f"some {_byte(x)}" for x in _hex_bytes(t["bytes"]))
            return f"([{cells}] : Model.Bytes)", BYTES
        if set(t) == {"some"}:
            x, xt = self.term(t["some"], env)
            return f"(some {x})", f"Maybe<{xt}>"
        if set(t) == {"call", "args"}:
            n = t["call"]
            loaders = {f"ok_{m}" for m, f in self.fns.items() if f.get("kind") == "loader"}
            res = {"encoder": BYTES, "decoder": f"Maybe<{BYTES}>", "predicate": "Bool", "loader": f"Maybe<{BYTES}>"}
            if n in self.fns and self.fns[n].get("kind") in res:
                k = self.fns[n]["kind"]
                arg_t, out_t = (self.fns[n].get("from") if k == "encoder" else BYTES), res[k]
            elif n in loaders:
                arg_t, out_t = BYTES, "Bool"
            else:
                raise Unsupported(f"call {n}")
            if not isinstance(t["args"], list) or len(t["args"]) != 1:
                raise Unsupported(f"call {n} arity")
            return f"(Model.{_fn(n)} {self.expect(t['args'][0], arg_t, env)})", out_t
        raise Unsupported(f"term {sorted(t)}")

    def expect(self, t, want: str, env: dict) -> str:
        x, xt = self.term(t, env)
        if xt != want:
            raise Unsupported(f"a {xt} where {want} is expected")
        return x

    def prop(self, p, env: dict, negate: bool = False) -> str:
        if isinstance(p, dict) and (set(p) == {"eq"} or set(p) == {"neq"}):
            op = "eq" if "eq" in p else "neq"
            if not isinstance(p[op], list) or len(p[op]) != 2:
                raise Unsupported(f"{op} of other than two terms")
            (x, xt), (y, yt) = self.term(p[op][0], env), self.term(p[op][1], env)
            if xt != yt:
                raise Unsupported(f"{op} of {xt} and {yt}")
            rel = "=" if (op == "eq") != negate else "≠"
            return f"{_strip(x)} {rel} {_strip(y)}"
        raise Unsupported(f"premise or claim {sorted(p) if isinstance(p, dict) else p!r}")

    def claim(self, c, env: dict, negate: bool = False) -> str:
        if isinstance(c, dict) and set(c) == {"all"}:
            body = " ∧ ".join(self.prop(p, env) for p in c["all"])
            return f"¬ ({body})" if negate else body
        return self.prop(c, env, negate)

    def binders(self, st: dict) -> tuple[list[tuple[str, str, str]], dict]:
        """[(quantifier, Lean name, Lean type)] in IR order, and {IR name: (Lean name, IR type)}."""
        bs = st.get("binders") or []
        if any(b.get("q") not in ("forall", "exists") for b in bs):
            raise Unsupported("binder quantifier")
        if len({b["q"] for b in bs}) > 1:
            raise Unsupported("mixed quantifiers")
        env, out = {}, []
        for b in bs:
            name = ident("v_", b["name"])
            lean_t, ir_t = self.ty(b["type"])
            env[b["name"]] = (name, ir_t)
            out.append((b["q"], name, lean_t))
        return out, env

    def body(self, law: dict, counter: bool = False, flip: bool = False) -> str:
        st = law["statement"]
        sc = (st.get("scope") or {"kind": "unbounded"}).get("kind", "unbounded")
        if sc != "unbounded":
            raise Unsupported(f"scope {sc}")
        bs, env = self.binders(st)
        prem = [self.prop(p, env) for p in st.get("assume") or []]
        q = bs[0][0] if bs else "forall"
        if q == "exists":
            if counter:
                raise Unsupported("the counter-law of an existential law")
            return _quant("∃", bs, " ∧ ".join(prem + [self.claim(st["claim"], env)]))
        if counter:
            return _quant("∃", bs, " ∧ ".join(prem + [self.claim(st["claim"], env, negate=not flip)]))
        return _quant("∀", bs, " → ".join(prem + [self.claim(st["claim"], env)]))


def statements(law: dict, status: str, codec: dict, flip: bool = False) -> list[tuple[str, str]]:
    """[(theorem name, statement text)], as lean_mlaws.statements for the linked kind: the law's theorem (PROVED), or
    its counter-law and refutation (REFUTED). flip=True renders a REFUTED law's counter-law with its claim's relation
    flipped (G7's flip canary: the counter-law's proof then decides a false proposition)."""
    lid = ident("", law["law_id"])
    r = _Render(codec)
    if status == "PROVED":
        return [(lid, f"theorem {lid} : {r.body(law)}")]
    if status == "REFUTED":
        return [(f"{lid}_counter", f"theorem {lid}_counter : {r.body(law, counter=True, flip=flip)}"),
                (f"{lid}_refuted", f"theorem {lid}_refuted : ¬ ({r.body(law)})")]
    raise Unsupported(f"a {status} law has no Lean statement")


def swap_canary(law: dict, codec: dict) -> str | None:
    """G7's perturb text for a round trip without premise whose right side is some <field of width 2 or more>: the
    law's statement with the first two cells of the right side swapped; None for any other law."""
    st = law.get("statement") or {}
    bs = st.get("binders") or []
    if law.get("subform") != "round_trip" or st.get("assume") or len(bs) != 1:
        return None
    claim = st.get("claim") or {}
    if set(claim) != {"eq"} or not isinstance(claim["eq"], list) or len(claim["eq"]) != 2:
        return None
    lhs, rhs = claim["eq"]
    var = {"var": bs[0]["name"]}
    if not (isinstance(rhs, dict) and set(rhs) == {"some"} and isinstance(rhs["some"], dict)
            and set(rhs["some"]) == {"field", "of"} and rhs["some"]["of"] == var):
        return None
    inner = lhs.get("args") if isinstance(lhs, dict) and set(lhs) == {"call", "args"} else None
    if not (isinstance(inner, list) and len(inner) == 1 and isinstance(inner[0], dict)
            and set(inner[0]) == {"call", "args"} and inner[0]["args"] == [var]):
        return None
    fld = next((x for x in _records(codec).get(bs[0]["type"], []) if x["name"] == rhs["some"]["field"]), None)
    if fld is None or fld["width"] < 2:
        return None
    v = ident("v_", bs[0]["name"])
    cells = [f"some {v}.{_cell(fld['name'], k)}" for k in range(fld["width"])]
    orig, swapped = ", ".join(cells), ", ".join([cells[1], cells[0]] + cells[2:])
    text = statements(law, "PROVED", codec)[0][1]
    if text.count(orig) != 1:
        return None
    return text.replace(orig, swapped)


# ====================================================================================== proofs
def _field_ref(t, types: dict) -> tuple[str, str, int] | None:
    """(binder, field, width) of a term {"field": F, "of": {"var": x}} over a record binder x, else None."""
    if not (isinstance(t, dict) and set(t) == {"field", "of"} and isinstance(t["of"], dict)
            and set(t["of"]) == {"var"}):
        return None
    x = t["of"]["var"]
    fld = next((f for f in types.get(x, []) if f["name"] == t["field"]), None)
    return (x, fld["name"], fld["width"]) if fld else None


def _premise_widths(prem: list, types: dict) -> list[int]:
    """The width of each premise, an equation between a record binder's field and another binder's field or a byte
    constant of the same width. Each one becomes as many cell equations between the opened records' variables and
    bytes, substituted in order; that is possible exactly when no equation joins two cells already equal (a class of
    equal cells holding at most one constant), checked here as a union-find over the cells. Unsupported otherwise."""
    parent: dict = {}

    def root(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    widths = []
    for p in prem:
        if not (isinstance(p, dict) and set(p) == {"eq"} and isinstance(p["eq"], list) and len(p["eq"]) == 2):
            raise Unsupported("open_refl with a premise that is no equation")
        sides = []
        for t in p["eq"]:
            f = _field_ref(t, types)
            if f is not None:
                sides.append([("cell", f[0], f[1], k) for k in range(f[2])])
            elif isinstance(t, dict) and set(t) == {"bytes"}:
                sides.append([("byte", x) for x in _hex_bytes(t["bytes"])])
            else:
                raise Unsupported("open_refl with a premise over a term that is no field or byte constant")
        if len(sides[0]) != len(sides[1]) or not sides[0]:
            raise Unsupported("open_refl with a premise between byte strings of different widths")
        for x, y in zip(*sides):
            rx, ry = root(x), root(y)
            if rx == ry or (rx[0] == "byte" and ry[0] == "byte"):
                raise Unsupported("open_refl with premises that equate two cells already equal or two constants")
            if rx[0] == "byte":
                rx, ry = ry, rx
            parent[rx] = ry          # a class's root is its constant when it has one
        widths.append(len(sides[0]))
    return widths


def _open_refl(law: dict, codec: dict, statement: str) -> Theorem:
    """A law over records proved by computation (Bend's open_refl: open every record, then {==}). Without premises:
    rfl after the binders. With premises (a field equal to another binder's field or to a byte constant): every
    record opened into its cell variables, each premise split into its cell equations and substituted, then rfl. The
    last step is rfl either way, so a perturbed claim is rejected for a semantic reason (a type mismatch, or the
    sides not definitionally equal)."""
    st = law["statement"]
    records = _records(codec)
    bs = st.get("binders") or []
    if any(b.get("q") != "forall" for b in bs):
        raise Unsupported("open_refl over a law that is not universal")
    if any(b.get("type") not in records for b in bs):
        raise Unsupported("open_refl over a byte-string binder (no record to open)")
    if set(st.get("claim") or {}) != {"eq"}:
        raise Unsupported("open_refl for a claim that is no equation")
    names = [ident("v_", b["name"]) for b in bs]
    prem = st.get("assume") or []
    lid = law["law_id"]
    if not prem:
        return Theorem(name=lid, statement=statement, proof=(f"fun {' '.join('_' for _ in names)} => rfl" if names
                                                             else "rfl"))
    widths = _premise_widths(prem, {b["name"]: records[b["type"]] for b in bs})
    hyps = [f"p{i}" for i in range(len(prem))]
    body = [f"  intro {' '.join(names + hyps)}"]
    for i, (b, v) in enumerate(zip(bs, names)):
        n = sum(f["width"] for f in records[b["type"]])
        body.append(f"  obtain ⟨{', '.join(f'x{i}_{j}' for j in range(n))}⟩ := {v}")
    body.append(f"  simp only [List.cons.injEq, Option.some.injEq, and_true] at {' '.join(hyps)}")
    for h, w in zip(hyps, widths):
        body.append(f"  obtain {'rfl' if w == 1 else '⟨' + ', '.join(['rfl'] * w) + '⟩'} := {h}")
    body.append("  rfl")
    return Theorem(name=lid, statement=statement, proof="by\n" + "\n".join(body))


def _witness_def(name: str, ty: str, codec: dict, value) -> str:
    """A binder's witness value (a record: field -> hex bytes; a byte string: hex) as a noncomputable definition."""
    records = _records(codec)
    if ty in records:
        if not isinstance(value, dict) or set(value) != {f["name"] for f in records[ty]}:
            raise Unsupported(f"a witness record of {ty} without exactly its fields")
        cells = []
        for f in records[ty]:
            bs = _hex_bytes(value[f["name"]])
            if len(bs) != f["width"]:
                raise Unsupported(f"a witness field {f['name']} of {len(bs)} bytes, not {f['width']}")
            cells += [f"{_cell(f['name'], k)} := {_byte(x)}" for k, x in enumerate(bs)]
        rows = [", ".join(cells[i:i + PER_LINE]) for i in range(0, len(cells), PER_LINE)]
        return f"noncomputable def {name} : Model.{_record_type(ty)} :=\n  {{ " + ",\n    ".join(rows) + " }"
    if ty == codec.get("linked_carrier"):
        cells = [f"some {_byte(x)}" for x in _hex_bytes(value)]
        return f"noncomputable def {name} : Model.Bytes :=\n  " + _list(cells, "  ")
    raise Unsupported(f"a witness of type {ty}")


def _counter(law: dict, record: dict, codec: dict, texts: dict) -> tuple[Theorem, ...]:
    """A REFUTED law at the record's witness: the witness values as noncomputable definitions, the counter-law by
    decide (its premises and negated claim evaluated there), the refutation by applying the law to it."""
    lid = law["law_id"]
    st = law["statement"]
    bs = st.get("binders") or []
    if any(b.get("q") != "forall" for b in bs):
        raise Unsupported("the counter-law of a law that is not universal")
    w = record.get("witness")
    if bs and (not isinstance(w, dict) or any(b["name"] not in w for b in bs)):
        raise Unsupported("a REFUTED record without a witness value for every binder")
    wnames = [ident(f"{lid}_w_", b["name"]) for b in bs]
    defs = tuple(_witness_def(n, b["type"], codec, w[b["name"]]) for n, b in zip(wnames, bs))
    proof = ("⟨" + ", ".join(wnames + ["by decide"]) + "⟩") if bs else "by decide"
    counter = Theorem(name=f"{lid}_counter", statement=texts[f"{lid}_counter"], proof=proof, before=defs)
    names = [ident("v_", b["name"]) for b in bs]
    hyps = [f"q{i}" for i in range(len(st.get("assume") or []))]
    pattern = ", ".join(names + hyps + ["hne"])
    applied = " ".join(["H"] + names + hyps)
    claim = st.get("claim") or {}
    last = f"({applied}) hne" if isinstance(claim, dict) and set(claim) == {"neq"} else f"hne ({applied})"
    refuted = Theorem(name=f"{lid}_refuted", statement=texts[f"{lid}_refuted"],
                      proof=f"by\n  intro H\n  obtain ⟨{pattern}⟩ := {lid}_counter\n  exact {last}")
    return counter, refuted


def theorems(cls: str, law: dict, status: str, record: dict, codec: dict,
             stmts: list[tuple[str, str]]) -> tuple[Theorem, ...]:
    """The theorems of a linked law file: cls is open_refl (PROVED) or counter_decide (REFUTED)."""
    texts = dict(stmts)
    lid = ident("", law["law_id"])
    if cls == "open_refl" and status == "PROVED" and lid in texts:
        return (_open_refl(law, codec, texts[lid]),)
    if cls == COUNTER_CLASS and status == "REFUTED" and {f"{lid}_counter", f"{lid}_refuted"} <= set(texts):
        return _counter(law, record, codec, texts)
    raise Unsupported(f"no linked Lean class {cls} for a {status} law")
