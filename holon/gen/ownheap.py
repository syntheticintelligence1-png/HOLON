"""The Go heap model of an OWN carrier document, its laws and their decision (BUILD_PLAN I35; rules W9 and W10 of the
docstring of tests_m3/test_own.py; the carrier document is holon.own's).

  generate(doc, sha) -> text   gen/<M>/model/own_<stem>.bend: the heap, the carrier's modelled fields, its methods'
                               effects, the views, and per OWN law its two sides
  emit(law, doc, ...)          LAWS.bend of a law (or its counter-law)
  decide(law, cm, ...)         rule W10: a heap_disjoint proof, else a counter-law at the first witness of the bounded
                               search over traces (the sidecar's pool), else UNKNOWN naming what failed

The heap. A backing array is OBk{k, c}: its key OKey{f, g, x} (f the field's tag, 1.. in the sorted order of the
document's "modelled" fields; g the field's generation, raised by a reallocating stored append; x 0 for the field's own
backings, 1 + the state's fresh counter for the backing a transient append allocates) and its bytes. A lookup takes the
first entry whose key equals; a write prepends an entry, so a key's newest entry shadows the older ones and every
other key keeps its entries. A field is FS{g, off, len, cap} (its key is OKey{its tag, g, 0}); a view is OSl{k, off,
len, cap}. Byte writes never change a backing's length (cells past its end are not written): an in-place append writes
inside the capacity, which a backing's length is.

Effects (the append-store class, W9). A method's stores F = append(F, X) (X a byte-slice parameter or a modelled field's
bytes) are stored appends; a W3 write with no store of its field is a transient append (its result is not stored); a
view is a field (F) or a transient append's result. Each append builds its heap entry and the field's new header with
ite components, so a lookup at another field's key or at a key of another generation or fresh index passes it by
computation, and only an effect on the view's own field needs a case split (the lemmas store_same and trans_same of
the proof library). Stores into an abstracted field and into non-slice fields are not modelled (A-own-fields: every
store into an abstracted field is an append onto itself or a fresh value, checked here); other parameters than byte
slices are not modelled. Anything else is Unsupported: the laws naming the method are UNKNOWN with the reason.

Lost writes. A value-receiver method runs on a copy: its receiver's field keeps its length, and the method assigns a
fresh allocation of the length its lost-write entry states exactly when the condition of the slice result case with
the same allocation site holds (a comparison of the field's length with a constant); the law compares lengths
(A-own-len).

Nothing here names a target: every field, method and length comes from the carrier document.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import bend

ROOT = Path(__file__).resolve().parents[2]
DRIVER = ROOT / "holon" / "js" / "linked.mjs"
SEARCH = ROOT / "holon" / "js" / "ownsearch.mjs"
ALIAS = "M"
SIDECAR = "spec/{m}/lib/own.json"


class Unsupported(Exception):
    """A construct the model class does not cover (named)."""


# ====================================================================== the fixed prelude
def prelude(classes: list[int], page: int, threshold: int) -> str:
    cls = ", ".join(f"{c}n" for c in classes)
    return f'''\
def ite(-A: Data, c: Bool, a: A, b: A) -> A:
  match c:
    case True{{}}:
      a
    case False{{}}:
      b

def n_eq(a: Nat, b: Nat) -> Bool:
  match a b:
    case 0n 0n:
      True{{}}
    case 0n 1n+q:
      False{{}}
    case 1n+p 0n:
      False{{}}
    case 1n+p 1n+q:
      n_eq(p, q)

# a backing's key: the field's tag, its generation, 0 or 1 + the fresh index of a transient append's allocation
type OKey is Data:
  OKey{{f: Nat, g: Nat, x: Nat}}

type OBk is Data:
  OBk{{k: OKey, c: List<&2, U32>}}

type OSl is Data:
  OSl{{k: OKey, off: Nat, len: Nat, cap: Nat}}

type FS is Data:
  FS{{g: Nat, off: Nat, len: Nat, cap: Nat}}

def key_eq(a: OKey, b: OKey) -> Bool:
  match a b:
    case OKey{{af, ag, ax}} OKey{{bf, bg, bx}}:
      Bool.and(n_eq(af, bf), Bool.and(n_eq(ag, bg), n_eq(ax, bx)))

def h_get(h: List<&2, OBk>, +k: OKey) -> List<&2, U32>:
  match h:
    case Nil{{}}:
      Nil{{}}
    case Con{{e, t}}:
      match e:
        case OBk{{ek, ec}}:
          ite(List<&2, U32>, key_eq(ek, k), ec, h_get(t, k))

def b_len(c: List<&2, U32>) -> Nat:
  match c:
    case Nil{{}}:
      0n
    case Con{{x, t}}:
      1n+b_len(t)

def b_over(xs: List<&2, U32>, c: List<&2, U32>) -> List<&2, U32>:
  match xs c:
    case Nil{{}} _:
      c
    case Con{{x, xt}} Nil{{}}:
      Nil{{}}
    case Con{{x, xt}} Con{{y, t}}:
      Con{{x, b_over(xt, t)}}

def b_write(at: Nat, c: List<&2, U32>, xs: List<&2, U32>) -> List<&2, U32>:
  match at c:
    case 0n _:
      b_over(xs, c)
    case 1n+p Nil{{}}:
      Nil{{}}
    case 1n+p Con{{y, t}}:
      Con{{y, b_write(p, t, xs)}}

def b_drop(n: Nat, c: List<&2, U32>) -> List<&2, U32>:
  match n c:
    case 0n _:
      c
    case 1n+p Nil{{}}:
      Nil{{}}
    case 1n+p Con{{y, t}}:
      b_drop(p, t)

def b_take(n: Nat, c: List<&2, U32>) -> List<&2, U32>:
  match n c:
    case 0n _:
      Nil{{}}
    case 1n+p Nil{{}}:
      Nil{{}}
    case 1n+p Con{{y, t}}:
      Con{{y, b_take(p, t)}}

def b_zeros(n: Nat) -> List<&2, U32>:
  match n:
    case 0n:
      Nil{{}}
    case 1n+p:
      Con{{0, b_zeros(p)}}

def b_app3(a: List<&2, U32>, b: List<&2, U32>, z: Nat) -> List<&2, U32>:
  List.append(&2, U32, List.append(&2, U32, a, b), b_zeros(z))

def b_eq(a: List<&2, U32>, b: List<&2, U32>) -> Bool:
  match a b:
    case Nil{{}} Nil{{}}:
      True{{}}
    case Nil{{}} Con{{y, ys}}:
      False{{}}
    case Con{{x, xs}} Nil{{}}:
      False{{}}
    case Con{{x, xs}} Con{{y, ys}}:
      Bool.and(U32.is_eq(x, y), b_eq(xs, ys))

def is_true(b: Bool) -> Type:
  match b:
    case True{{}}:
      Unit
    case False{{}}:
      Empty

# Go's growslice for a byte slice (A-go-growth): nextslicecap, then the smallest size class at least it, else the next
# multiple of the page
def g_classes() -> List<&2, Nat>:
  [{cls}]

def g_round_in(+n: Nat, cs: List<&2, Nat>) -> Nat:
  match cs:
    case Nil{{}}:
      Nat.mul(Nat.div(Nat.add(n, {page - 1}n), {page}n), {page}n)
    case Con{{+c, rest}}:
      ite(Nat, Nat.is_le(n, c), c, g_round_in(n, rest))

# runtime/slice.go's loop `newcap += (newcap + 3*threshold) >> 2` until newcap >= newlen, as a fold whose step keeps
# c once it reaches newlen (the compiled model evaluates ite's arms eagerly: the recursion is never under an ite);
# each step adds at least 3*threshold/4, so newlen steps are enough
def g_grow(fuel: Nat, +newlen: Nat, +c: Nat) -> Nat:
  match fuel:
    case 0n:
      c
    case 1n+p:
      g_grow(p, newlen, ite(Nat, Nat.is_le(newlen, c), c, Nat.add(c, Nat.div(Nat.add(c, {3 * threshold}n), 4n))))

def g_next(+newlen: Nat, +oldcap: Nat) -> Nat:
  ite(Nat, Nat.is_lt(Nat.add(oldcap, oldcap), newlen), newlen, ite(Nat, Nat.is_lt(oldcap, {threshold}n), Nat.add(oldcap, oldcap), g_grow(newlen, newlen, oldcap)))

def growcap(+newlen: Nat, +oldcap: Nat) -> Nat:
  g_round_in(g_next(newlen, oldcap), g_classes())

# a stored append onto field t (header FS{{g, off, len, cap}}, n = len + |xs|, old its backing's bytes): the heap gains
# one entry under tag t, the field's new header; c: whether it is in place
type AR is Data:
  AR{{h: List<&2, OBk>, s: FS}}

def st_app_e(+c: Bool, +t: Nat, +g: Nat, +off: Nat, +len: Nat, +cap: Nat, +n: Nat, +old: List<&2, U32>, +xs: List<&2, U32>, h: List<&2, OBk>) -> AR:
  AR{{Con{{OBk{{OKey{{t, ite(Nat, c, g, 1n+g), 0n}}, ite(List<&2, U32>, c, b_write(Nat.add(off, len), old, xs), b_app3(b_take(len, b_drop(off, old)), xs, Nat.sub(growcap(n, cap), n)))}}, h}}, FS{{ite(Nat, c, g, 1n+g), ite(Nat, c, off, 0n), n, ite(Nat, c, cap, growcap(n, cap))}}}}

def ar_h(r: AR) -> List<&2, OBk>:
  match r:
    case AR{{h, s}}:
      h

def ar_s(r: AR) -> FS:
  match r:
    case AR{{h, s}}:
      s

# a transient append onto field t (its result is not stored): the heap entry, the result slice, the fresh counter
type TR is Data:
  TR{{h: List<&2, OBk>, v: OSl, fc: Nat}}

def tr_app_e(+c: Bool, +t: Nat, +g: Nat, +off: Nat, +len: Nat, +cap: Nat, +n: Nat, +old: List<&2, U32>, +xs: List<&2, U32>, h: List<&2, OBk>, +fc: Nat) -> TR:
  TR{{Con{{OBk{{OKey{{t, g, ite(Nat, c, 0n, 1n+fc)}}, ite(List<&2, U32>, c, b_write(Nat.add(off, len), old, xs), b_app3(b_take(len, b_drop(off, old)), xs, Nat.sub(growcap(n, cap), n)))}}, h}}, OSl{{OKey{{t, g, ite(Nat, c, 0n, 1n+fc)}}, ite(Nat, c, off, 0n), n, ite(Nat, c, cap, growcap(n, cap))}}, ite(Nat, c, fc, 1n+fc)}}

def tr_h(r: TR) -> List<&2, OBk>:
  match r:
    case TR{{h, v, fc}}:
      h

def tr_v(r: TR) -> OSl:
  match r:
    case TR{{h, v, fc}}:
      v

def tr_fc(r: TR) -> Nat:
  match r:
    case TR{{h, v, fc}}:
      fc

def fbytes(+h: List<&2, OBk>, +t: Nat, s: FS) -> List<&2, U32>:
  match s:
    case FS{{g, off, len, cap}}:
      b_take(len, b_drop(off, h_get(h, OKey{{t, g, 0n}})))

def vbytes(+h: List<&2, OBk>, v: OSl) -> List<&2, U32>:
  match v:
    case OSl{{k, off, len, cap}}:
      b_take(len, b_drop(off, h_get(h, k)))
'''


# ====================================================================== the carrier's effects
@dataclass
class Effect:
    kind: str                 # "store" | "transient"
    field: str
    src: tuple                # ("param", index) | ("field", name)


@dataclass
class Method:
    name: str
    params: list              # the byte-slice parameters' names, in order
    effects: list             # [Effect]
    view: tuple | None        # None | ("field", F) | ("append", index into effects)


@dataclass
class Carrier:
    stem: str
    fields: list              # modelled fields, sorted (tag = index + 1)
    methods: dict             # name -> Method | Unsupported
    lost: dict                # (method, field) -> {"len": N, "cond": (op, c)} | Unsupported
    init: str | None = None   # why the constructor's value is outside the model class (None: s0 is it)

    def tag(self, f: str) -> int:
        return self.fields.index(f) + 1


def _field_ref(t, recv: str):
    if isinstance(t, list) and len(t) == 3 and t[0] == "field" and t[1] == ["param", recv] and isinstance(t[2], str):
        return t[2]
    return None


def _bytes_src(t, recv: str, params: list, modelled: list):
    if isinstance(t, list) and len(t) == 2 and t[0] == "param" and t[1] in params:
        return ("param", params.index(t[1]))
    f = _field_ref(t, recv)
    if f in modelled:
        return ("field", f)
    raise Unsupported(f"an append of {json.dumps(t)[:80]} (not a byte-slice parameter or a modelled field)")


def _method(name: str, m: dict, doc: dict) -> Method:
    recv, modelled = m["receiver"], doc["modelled"]
    ps = (m.get("params") or [])[1:]
    params = [p["name"] for p in ps if p.get("type") == "[]byte"]
    effects = []
    stored = set()
    for s in m.get("stores") or []:
        f = _field_ref(s.get("target"), recv)
        v = s.get("value")
        if f is None:
            raise Unsupported(f"{name}: a store into {json.dumps(s.get('target'))[:80]}")
        if f in modelled:
            if not (isinstance(v, list) and len(v) == 3 and v[0] == "append" and _field_ref(v[1], recv) == f):
                raise Unsupported(f"{name}: the store into {f} is not an append onto {f}")
            effects.append(Effect("store", f, _bytes_src(v[2], recv, params, modelled)))
            stored.add(f)
        elif f in doc.get("abstracted") or []:
            if not (isinstance(v, list) and v[:1] == ["append"] and _field_ref(v[1], recv) == f):
                raise Unsupported(f"{name}: the store into the abstracted field {f} is not an append onto it "
                                  "(A-own-fields)")
        # other fields (scalars) are not modelled
    for w in m.get("writes") or []:
        f = w["field"]
        if f in stored or f not in modelled:
            continue
        to = w.get("to")
        if not (isinstance(to, list) and len(to) == 4 and to[:2] == ["op", "+"] and to[2] == ["len", ["field",
                ["param", recv], f]] and isinstance(to[3], list) and to[3][:1] == ["len"]):
            raise Unsupported(f"{name}: the in-place write into {f} is not an append (to {json.dumps(to)[:80]})")
        effects.append(Effect("transient", f, _bytes_src(to[3][1], recv, params, modelled)))
    view = None
    cases = [c for c in m.get("cases") or []]
    vfs = sorted({v["field"] for v in doc["views"] if v["method"] == name})
    if vfs:
        if len(vfs) != 1:
            raise Unsupported(f"{name}: views of two fields {vfs}")
        f = vfs[0]
        tr = [i for i, e in enumerate(effects) if e.kind == "transient" and e.field == f]
        if tr:
            view = ("append", tr[-1])
        elif any(c.get("backing") == ["of", ["field", ["param", recv], f]] and c.get("offset") == ["const", 0]
                 and c.get("len") == ["len", ["field", ["param", recv], f]] for c in cases):
            view = ("field", f)
        else:
            raise Unsupported(f"{name}: a view of {f} that is neither the field nor an append's result")
    return Method(name, params, effects, view)


def _lost(m: dict, x: dict):
    """{"len": N, "cond": (op, c)} of a lost write: the fresh allocation it assigns and the result case's condition."""
    v = x.get("value")
    if not (isinstance(v, list) and len(v) == 5 and v[0] == "slice" and isinstance(v[1], list) and v[1][:1] == ["alloc"]
            and v[3] == v[1][2] and isinstance(v[3], list) and v[3][:1] == ["const"]):
        raise Unsupported(f"the lost write's value {json.dumps(v)[:100]} is not a fresh allocation of a constant length")
    site, n = v[1][1], int(v[3][1])
    recv = m["receiver"]
    for c in m.get("cases") or []:
        if c.get("backing") == ["fresh", site]:
            cond = c.get("cond") or []
            if len(cond) != 1:
                raise Unsupported(f"the assignment's condition {json.dumps(cond)[:100]} is not one comparison")
            op, a, b = cond[0][0], cond[0][1], cond[0][2]
            if a != ["len", ["field", ["param", recv], x["field"]]] or not (isinstance(b, list) and b[:1] == ["const"]):
                raise Unsupported(f"the assignment's condition {json.dumps(cond)[:100]} is not the field's length "
                                  "against a constant")
            if op not in ("<=", "<", "==", ">", ">=", "!="):
                raise Unsupported(f"the comparison {op}")
            return {"len": n, "cond": (op, int(b[1]))}
    raise Unsupported(f"no slice result case allocates at {site}")


def init_problem(doc: dict) -> str | None:
    """W9's constructor: a function of D returning *T or T whose stores set no modelled field but to an empty
    allocation (["alloc", site, ["const", 0]] or ["nil"]). The frontend records stores alone (a composite literal's
    fields are no store), so a modelled field the constructor does not store is the zero value: len 0, cap 0, no
    backing, which an append treats as an empty make. None when such a constructor exists (s0 is its value)."""
    cs = doc.get("constructors") or []
    if not cs:
        return "the document has no constructor (a function of D returning *T or T)"
    why = []
    for c in cs:
        bad = []
        for st in c.get("stores") or []:
            t = st.get("target")
            if isinstance(t, list) and len(t) == 3 and t[0] == "field" and t[2] in doc["modelled"]:
                v = st.get("value")
                if not (v == ["nil"] or (isinstance(v, list) and len(v) == 3 and v[0] == "alloc"
                                         and v[2] == ["const", 0])):
                    bad.append(f"{t[2]} := {json.dumps(v)[:60]}")
        if not bad:
            return None
        why.append(f"{c['function']} stores {'; '.join(bad)}")
    return "no constructor leaves every modelled field empty: " + " / ".join(why)


def carrier(doc: dict) -> Carrier:
    methods, lost = {}, {}
    for name, m in sorted(doc["methods"].items()):
        if not m.get("pointer"):
            continue
        try:
            methods[name] = _method(name, m, doc)
        except Unsupported as e:
            methods[name] = e
    for x in doc["lost_writes"]:
        try:
            lost[(x["method"], x["field"])] = _lost(doc["methods"][x["method"]], x)
        except Unsupported as e:
            lost[(x["method"], x["field"])] = e
    return Carrier(doc["stem"], list(doc["modelled"]), methods, lost, init_problem(doc))


def bname(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


# ====================================================================== the carrier's text
def _src_text(e: Effect, cr: Carrier, args: list, hvar: str, fvars: dict) -> str:
    if e.src[0] == "param":
        return args[e.src[1]]
    return f"fbytes({hvar}, {cr.tag(e.src[1])}n, {fvars[e.src[1]]})"


def carrier_text(cr: Carrier) -> str:
    """The state, the calls, the methods' effects and views, the trace runner."""
    ok = {n: m for n, m in cr.methods.items() if isinstance(m, Method)}
    fl = cr.fields
    fdecl = ", ".join(f"f{i + 1}: FS" for i in range(len(fl)))
    out = [f"# the carrier: fields {', '.join(f'{i + 1} = {f}' for i, f in enumerate(fl))} (tags); the heap; fc the fresh "
           "counter", f"type St is Data:\n  St{{h: List<&2, OBk>, fc: Nat{', ' + fdecl if fdecl else ''}}}", ""]
    ctors = []
    for n, m in ok.items():
        fs = ", ".join(f"a{i}: List<&2, U32>" for i in range(len(m.params)))
        ctors.append(f"  C_{bname(n)}{{{fs}}}")
    out += ["type Call is Data:"] + (ctors or ["  C_none{}"]) + [""]
    fz = ", ".join("FS{0n, 0n, 0n, 0n}" for _ in fl)
    out += [f"def s0() -> St:\n  St{{Nil{{}}, 0n{', ' + fz if fz else ''}}}", ""]
    pat = f"    case St{{h, fc{''.join(f', f{i + 1}' for i in range(len(fl)))}}}:"
    out += ["def st_h(s: St) -> List<&2, OBk>:", "  match s:", pat, "      h", ""]
    for i in range(len(fl)):
        out += [f"def st_f{i + 1}(s: St) -> FS:", "  match s:", pat, f"      f{i + 1}", ""]
    fpat = ", ".join(f"+f{i + 1}" for i in range(len(fl)))
    for n, m in ok.items():
        b = bname(n)
        args = [f"a{i}" for i in range(len(m.params))]
        sig_args = "".join(f", +a{i}: List<&2, U32>" for i in range(len(m.params)))
        # one def per effect: e_<m>_<i>(st, args) -> St (a transient append keeps its result in no field)
        for i, e in enumerate(m.effects):
            t = cr.tag(e.field)
            k = fl.index(e.field) + 1
            fvars = {f: f"f{j + 1}" for j, f in enumerate(fl)}
            src = _src_text(e, cr, args, "h", fvars)
            lines = [f"def e_{b}_{i}(st: St{sig_args}) -> St:", "  match st:",
                     f"    case St{{+h, +fc{', ' + fpat if fpat else ''}}}:", f"      match f{k}:",
                     "        case FS{+g, +off, +len, +cap}:"]
            n_expr = f"Nat.add(len, b_len({src}))"
            cond = f"Nat.is_le({n_expr}, cap)"
            old = f"h_get(h, OKey{{{t}n, g, 0n}})"
            if e.kind == "store":
                r = f"st_app_e({cond}, {t}n, g, off, len, cap, {n_expr}, {old}, {src}, h)"
                fs_new = [f"ar_s({r})" if j + 1 == k else f"f{j + 1}" for j in range(len(fl))]
                lines.append(f"          St{{ar_h({r}), fc, {', '.join(fs_new)}}}")
            else:
                r = f"tr_app_e({cond}, {t}n, g, off, len, cap, {n_expr}, {old}, {src}, h, fc)"
                fs_new = [f"FS{{g, off, len, cap}}" if j + 1 == k else f"f{j + 1}" for j in range(len(fl))]
                lines.append(f"          St{{tr_h({r}), tr_fc({r}), {', '.join(fs_new)}}}")
            out += lines + [""]
        body = "st"
        for i in range(len(m.effects)):
            body = f"e_{b}_{i}({body}{''.join(', ' + a for a in args)})"
        out += [f"def do_{b}(st: St{sig_args}) -> St:", f"  {body}", ""]
        if m.view is not None:
            out += _view_text(cr, m)
    out += ["def step(c: Call, st: St) -> St:", "  match c:"]
    for n, m in ok.items():
        args = [f"a{i}" for i in range(len(m.params))]
        out += [f"    case C_{bname(n)}{{{', '.join(args)}}}:", f"      do_{bname(n)}(st{''.join(', ' + a for a in args)})"]
    if not ok:
        out += ["    case C_none{}:", "      st"]
    out += ["", "def run(p: List<&2, Call>, st: St) -> St:", "  match p:", "    case Nil{}:", "      st",
            "    case Con{c, rest}:", "      run(rest, step(c, st))", ""]
    return "\n".join(out) + "\n"


def _view_text(cr: Carrier, m: Method) -> list[str]:
    """view_<m>(st) -> VR (the view and the state after the method): a field view, or a transient append's result."""
    b = bname(m.name)
    fl = cr.fields
    fpat = ", ".join(f"+f{i + 1}" for i in range(len(fl)))
    if m.view[0] == "field":
        k = fl.index(m.view[1]) + 1
        t = cr.tag(m.view[1])
        return [f"def view_{b}(st: St) -> VR:", "  match st:", f"    case St{{h, fc{', ' + fpat if fpat else ''}}}:",
                f"      match f{k}:", "        case FS{+g, +off, +len, +cap}:",
                f"          VR{{OSl{{OKey{{{t}n, g, 0n}}, off, len, cap}}, do_{b}(St{{h, fc{''.join(f', f{i + 1}' if i + 1 != k else ', FS{g, off, len, cap}' for i in range(len(fl)))}}})}}",
                ""]
    i = m.view[1]
    e = m.effects[i]
    if any(x.src[0] == "param" for x in m.effects) or len(m.effects) != i + 1 or m.params:
        raise Unsupported(f"{m.name}: a view after parameters or later effects")
    k = fl.index(e.field) + 1
    t = cr.tag(e.field)
    fvars = {f: f"f{j + 1}" for j, f in enumerate(fl)}
    src = _src_text(e, cr, [], "h", fvars)
    pre = "st"
    for j in range(i):
        pre = f"e_{b}_{j}({pre})"
    return [f"def vw_{b}(st: St) -> VR:", "  match st:", f"    case St{{+h, +fc{', ' + fpat if fpat else ''}}}:",
            f"      match f{k}:", "        case FS{+g, +off, +len, +cap}:",
            f"          VR{{tr_v(tr_app_e(Nat.is_le(Nat.add(len, b_len({src})), cap), {t}n, g, off, len, cap, "
            f"Nat.add(len, b_len({src})), h_get(h, OKey{{{t}n, g, 0n}}), {src}, h, fc)), do_{b}(St{{h, fc"
            f"{''.join(f', f{x + 1}' if x + 1 != k else ', FS{g, off, len, cap}' for x in range(len(fl)))}}})}}",
            "", f"def view_{b}(st: St) -> VR:", f"  vw_{b}({pre})", ""]


VR_TEXT = '''# a view: the slice the method returns and the state after it
type VR is Data:
  VR{v: OSl, st: St}

def vr_pre(r: VR) -> List<&2, U32>:
  match r:
    case VR{+v, st1}:
      vbytes(st_h(st1), v)
'''


def alias_text(cr: Carrier, V: str, W: str) -> str:
    """oa_pre / oa_post of the alias law (V, W): the view's bytes after V, and after one call of W from there (the state
    after V when the call is not of W)."""
    b = f"{bname(V)}_{bname(W)}"
    mw = cr.methods[W]
    ok = {n: m for n, m in cr.methods.items() if isinstance(m, Method)}
    lines = [f"def vr_post_{b}(r: VR, w: Call) -> List<&2, U32>:", "  match r:", "    case VR{+v, st1}:", "      match w:"]
    for n, m in ok.items():
        args = [f"a{i}" for i in range(len(m.params))]
        lines.append(f"        case C_{bname(n)}{{{', '.join(args)}}}:")
        if n == W:
            lines.append(f"          vbytes(st_h(do_{bname(W)}(st1{''.join(', ' + a for a in args)})), v)")
        else:
            lines.append("          vbytes(st_h(st1), v)")
    del mw
    lines += ["", f"def oa_pre_{b}(p: List<&2, Call>, w: Call) -> List<&2, U32>:",
              f"  vr_pre(view_{bname(V)}(run(p, s0())))", "",
              f"def oa_post_{b}(p: List<&2, Call>, w: Call) -> List<&2, U32>:",
              f"  vr_post_{b}(view_{bname(V)}(run(p, s0())), w)", "",
              "# the search's predicate: both sides from one evaluation of the view",
              f"def oa_eq_go_{b}(+r: VR, w: Call) -> Bool:", f"  b_eq(vr_post_{b}(r, w), vr_pre(r))", "",
              f"def oa_eq_{b}(p: List<&2, Call>, w: Call) -> Bool:", f"  oa_eq_go_{b}(view_{bname(V)}(run(p, s0())), w)",
              ""]
    lines += live_text(cr, V, W)
    return "\n".join(lines) + "\n"


def live_route(cr: Carrier, V: str, W: str):
    """(field index k, effect) when V is a field view of F and W has one effect on F, of a byte-slice parameter: the
    shape heap_disjoint proves and whose inhabitant oa_live states; else None."""
    mv, mw = cr.methods.get(V), cr.methods.get(W)
    if not (isinstance(mv, Method) and isinstance(mw, Method)) or mv.view is None or mv.view[0] != "field" \
            or mv.effects:
        return None
    vf = mv.view[1]
    hits = [e for e in mw.effects if e.field == vf]
    if len(hits) != 1 or hits[0].src[0] != "param" or any(e.src == ("field", vf) for e in mw.effects):
        return None
    return cr.fields.index(vf) + 1, hits[0]


def live_text(cr: Carrier, V: str, W: str) -> list[str]:
    """oa_live_<V>_<W>(p, w): after p the view is not empty and w is a call of W whose write into the view's field puts
    at least one byte into the view's backing in place (past the view's end): the run a heap_disjoint proof covers."""
    r = live_route(cr, V, W)
    if r is None:
        return []
    k, e = r
    b = f"{bname(V)}_{bname(W)}"
    a = f"a{e.src[1]}"
    lines = [f"def oa_live_go_{b}(s: FS, w: Call) -> Bool:", "  match s:", "    case FS{g, off, +len, +cap}:",
             "      match w:"]
    for n, m in cr.methods.items():
        if not isinstance(m, Method):
            continue
        args = [("+" if n == W and f"a{i}" == a else "") + f"a{i}" for i in range(len(m.params))]
        lines.append(f"        case C_{bname(n)}{{{', '.join(args)}}}:")
        lines.append(f"          Bool.and(Nat.is_lt(0n, len), Bool.and(Nat.is_lt(0n, b_len({a})), "
                     f"Nat.is_le(Nat.add(len, b_len({a})), cap)))" if n == W else "          False{}")
    return lines + ["", f"def oa_live_{b}(p: List<&2, Call>, w: Call) -> Bool:",
                    f"  oa_live_go_{b}(st_f{k}(run(p, s0())), w)", ""]


_CMP = {"<=": "Nat.is_le(n, {c}n)", "<": "Nat.is_lt(n, {c}n)", "==": "n_eq(n, {c}n)", ">": "Nat.is_gt(n, {c}n)",
        ">=": "Nat.is_ge(n, {c}n)", "!=": "Bool.not(n_eq(n, {c}n))"}


def lost_text(m: str, f: str, x: dict) -> str:
    """The lost write's model: the receiver's field length n (a value receiver: it keeps it), and what m assigns."""
    b = f"{bname(m)}_{bname(f)}"
    cond = _CMP[x["cond"][0]].format(c=x["cond"][1])
    return f'''# the lost write of {m} on {f}: a copy's field takes a fresh allocation of length {x["len"]} when {x["cond"][0]} {x["cond"][1]}
type LS_{b} is Data:
  LS_{b}{{n: Nat}}

type LC_{b} is Data:
  LC_{b}{{}}

def ol_go_{b}(c: Bool, +n: Nat) -> Nat:
  match c:
    case True{{}}:
      {x["len"]}n
    case False{{}}:
      n

def ol_field_{b}(x: LS_{b}, c: LC_{b}) -> Nat:
  match x:
    case LS_{b}{{n}}:
      n

def ol_assigned_{b}(x: LS_{b}, c: LC_{b}) -> Nat:
  match x:
    case LS_{b}{{+n}}:
      ol_go_{b}({cond}, n)
'''


def generate(doc: dict, sha: str, growth: dict) -> str:
    """The carrier's model text (rule W9). A method or lost write outside the class gets a comment with its reason."""
    cr = carrier(doc)
    head = [f"# GENERATED by holon.gen.ownheap from the OWN carrier document {doc['stem']} (sha256 {sha}); do not edit.",
            "import Base", "", prelude(growth["class_to_size"], growth["page"], growth["threshold"])]
    body = [f"# s0, the constructor's value: unsupported ({cr.init})" if cr.init else
            "# s0, the constructor's value: every modelled field empty (len 0, cap 0, no backing; W9)"]
    for n, m in cr.methods.items():
        if isinstance(m, Unsupported):
            body.append(f"# {n}: unsupported ({m})")
    if cr.fields:
        try:
            body.append(carrier_text(cr))
            body.append(VR_TEXT)
            from ..rules import own as OR
            for e in OR.elements(doc):
                if e["subform"] == "alias":
                    V, W = e["basis"]["view"], e["basis"]["writer"]
                    if isinstance(cr.methods.get(V), Method) and isinstance(cr.methods.get(W), Method):
                        body.append(alias_text(cr, V, W))
        except Unsupported as e:
            body.append(f"# the carrier: unsupported ({e})")
    for (m, f), x in sorted(cr.lost.items()):
        body.append(f"# {m} {f}: unsupported ({x})" if isinstance(x, Unsupported) else lost_text(m, f, x))
    return "\n".join(head) + "\n" + "\n".join(body)


# ====================================================================== the proof library (fixed text)
LIBRARY = '''\
def l_n_eq_refl(g: Nat) -> {M.n_eq(g, g) == True{} : Bool}:
  match g:
    case 0n:
      {==}
    case 1n+p:
      l_n_eq_refl(p)

def l_n_eq_succ(g: Nat) -> {M.n_eq(1n+g, g) == False{} : Bool}:
  match g:
    case 0n:
      {==}
    case 1n+p:
      l_n_eq_succ(p)

def l_region0(n: Nat, +c: List<&2, U32>, +xs: List<&2, U32>) -> {M.b_take(n, M.b_write(n, c, xs)) == M.b_take(n, c) : List<&2, U32>}:
  match n:
    case 0n:
      {==}
    case 1n+p:
      match c:
        case Nil{}:
          {==}
        case Con{+y, +t}:
          %l_region0(p, t, xs) : {Con{y, M.b_take(p, M.b_write(p, t, xs))} == Con{y, _} : List<&2, U32>}
          {==}

def l_region(o: Nat, +n: Nat, +c: List<&2, U32>, +xs: List<&2, U32>) -> {M.b_take(n, M.b_drop(o, M.b_write(Nat.add(o, n), c, xs))) == M.b_take(n, M.b_drop(o, c)) : List<&2, U32>}:
  match o:
    case 0n:
      l_region0(n, c, xs)
    case 1n+p:
      match c:
        case Nil{}:
          {==}
        case Con{y, t}:
          l_region(p, n, t, xs)

def l_get_ne(+k1: M.OKey, +k2: M.OKey, +c: List<&2, U32>, +h: List<&2, M.OBk>, e: {M.key_eq(k1, k2) == False{} : Bool}) -> {M.h_get(Con{M.OBk{k1, c}, h}, k2) == M.h_get(h, k2) : List<&2, U32>}:
  %Equal.sym(Bool, M.key_eq(k1, k2), False{}, e) : {M.ite(List<&2, U32>, _, c, M.h_get(h, k2)) == M.h_get(h, k2) : List<&2, U32>}
  {==}

def l_get_eq(+k1: M.OKey, +k2: M.OKey, +c: List<&2, U32>, +h: List<&2, M.OBk>, e: {M.key_eq(k1, k2) == True{} : Bool}) -> {M.h_get(Con{M.OBk{k1, c}, h}, k2) == c : List<&2, U32>}:
  %Equal.sym(Bool, M.key_eq(k1, k2), True{}, e) : {M.ite(List<&2, U32>, _, c, M.h_get(h, k2)) == c : List<&2, U32>}
  {==}

def l_key_refl(+t: Nat, +g: Nat) -> {M.key_eq(M.OKey{t, g, 0n}, M.OKey{t, g, 0n}) == True{} : Bool}:
  %Equal.sym(Bool, M.n_eq(t, t), True{}, l_n_eq_refl(t)) : {Bool.and(_, Bool.and(M.n_eq(g, g), True{})) == True{} : Bool}
  %Equal.sym(Bool, M.n_eq(g, g), True{}, l_n_eq_refl(g)) : {Bool.and(True{}, Bool.and(_, True{})) == True{} : Bool}
  {==}

def l_key_gen(+t: Nat, +g: Nat) -> {M.key_eq(M.OKey{t, 1n+g, 0n}, M.OKey{t, g, 0n}) == False{} : Bool}:
  %Equal.sym(Bool, M.n_eq(t, t), True{}, l_n_eq_refl(t)) : {Bool.and(_, Bool.and(M.n_eq(1n+g, g), True{})) == False{} : Bool}
  %Equal.sym(Bool, M.n_eq(1n+g, g), False{}, l_n_eq_succ(g)) : {Bool.and(True{}, Bool.and(_, True{})) == False{} : Bool}
  {==}

def l_key_fresh(+t: Nat, +g: Nat, +fc: Nat) -> {M.key_eq(M.OKey{t, g, 1n+fc}, M.OKey{t, g, 0n}) == False{} : Bool}:
  %Equal.sym(Bool, M.n_eq(t, t), True{}, l_n_eq_refl(t)) : {Bool.and(_, Bool.and(M.n_eq(g, g), False{})) == False{} : Bool}
  %Equal.sym(Bool, M.n_eq(g, g), True{}, l_n_eq_refl(g)) : {Bool.and(True{}, Bool.and(_, False{})) == False{} : Bool}
  {==}

# a stored append onto the view's own field keeps the view's bytes: in place it writes past the view's end; else it is
# a new generation's backing
def l_store_same(c: Bool, +t: Nat, +g: Nat, +off: Nat, +len: Nat, +cap: Nat, +n: Nat, +xs: List<&2, U32>, +h: List<&2, M.OBk>) -> {M.b_take(len, M.b_drop(off, M.h_get(M.ar_h(M.st_app_e(c, t, g, off, len, cap, n, M.h_get(h, M.OKey{t, g, 0n}), xs, h)), M.OKey{t, g, 0n}))) == M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))) : List<&2, U32>}:
  match c:
    case True{}:
      %Equal.sym(List<&2, U32>, M.h_get(Con{M.OBk{M.OKey{t, g, 0n}, M.b_write(Nat.add(off, len), M.h_get(h, M.OKey{t, g, 0n}), xs)}, h}, M.OKey{t, g, 0n}), M.b_write(Nat.add(off, len), M.h_get(h, M.OKey{t, g, 0n}), xs), l_get_eq(M.OKey{t, g, 0n}, M.OKey{t, g, 0n}, M.b_write(Nat.add(off, len), M.h_get(h, M.OKey{t, g, 0n}), xs), h, l_key_refl(t, g))) : {M.b_take(len, M.b_drop(off, _)) == M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))) : List<&2, U32>}
      l_region(off, len, M.h_get(h, M.OKey{t, g, 0n}), xs)
    case False{}:
      %Equal.sym(List<&2, U32>, M.h_get(Con{M.OBk{M.OKey{t, 1n+g, 0n}, M.b_app3(M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))), xs, Nat.sub(M.growcap(n, cap), n))}, h}, M.OKey{t, g, 0n}), M.h_get(h, M.OKey{t, g, 0n}), l_get_ne(M.OKey{t, 1n+g, 0n}, M.OKey{t, g, 0n}, M.b_app3(M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))), xs, Nat.sub(M.growcap(n, cap), n)), h, l_key_gen(t, g))) : {M.b_take(len, M.b_drop(off, _)) == M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))) : List<&2, U32>}
      {==}

# a transient append onto the view's own field keeps the view's bytes: in place it writes past the view's end; else it
# is a fresh backing
def l_trans_same(c: Bool, +t: Nat, +g: Nat, +off: Nat, +len: Nat, +cap: Nat, +n: Nat, +xs: List<&2, U32>, +h: List<&2, M.OBk>, +fc: Nat) -> {M.b_take(len, M.b_drop(off, M.h_get(M.tr_h(M.tr_app_e(c, t, g, off, len, cap, n, M.h_get(h, M.OKey{t, g, 0n}), xs, h, fc)), M.OKey{t, g, 0n}))) == M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))) : List<&2, U32>}:
  match c:
    case True{}:
      %Equal.sym(List<&2, U32>, M.h_get(Con{M.OBk{M.OKey{t, g, 0n}, M.b_write(Nat.add(off, len), M.h_get(h, M.OKey{t, g, 0n}), xs)}, h}, M.OKey{t, g, 0n}), M.b_write(Nat.add(off, len), M.h_get(h, M.OKey{t, g, 0n}), xs), l_get_eq(M.OKey{t, g, 0n}, M.OKey{t, g, 0n}, M.b_write(Nat.add(off, len), M.h_get(h, M.OKey{t, g, 0n}), xs), h, l_key_refl(t, g))) : {M.b_take(len, M.b_drop(off, _)) == M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))) : List<&2, U32>}
      l_region(off, len, M.h_get(h, M.OKey{t, g, 0n}), xs)
    case False{}:
      %Equal.sym(List<&2, U32>, M.h_get(Con{M.OBk{M.OKey{t, g, 1n+fc}, M.b_app3(M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))), xs, Nat.sub(M.growcap(n, cap), n))}, h}, M.OKey{t, g, 0n}), M.h_get(h, M.OKey{t, g, 0n}), l_get_ne(M.OKey{t, g, 1n+fc}, M.OKey{t, g, 0n}, M.b_app3(M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))), xs, Nat.sub(M.growcap(n, cap), n)), h, l_key_fresh(t, g, fc))) : {M.b_take(len, M.b_drop(off, _)) == M.b_take(len, M.b_drop(off, M.h_get(h, M.OKey{t, g, 0n}))) : List<&2, U32>}
      {==}
'''


# ====================================================================== laws
@dataclass
class Emitted:
    name: str
    text: str
    lhs: str
    rhs: str
    claim_type: str
    binders: list           # [(name, Bend type)]


def law_name(law_id: str, counter: bool = False) -> str:
    return ("cl_" if counter else "") + law_id.lower()


def _own_id(law: dict) -> str:
    c = law["statement"]["claim"]
    if set(c) != {"eq"} or not isinstance(c["eq"][0], dict) or "own" not in c["eq"][0] or c["eq"][1] != {"bool": True}:
        raise Unsupported("an OWN law's claim is {own: ID, on: binders} == true")
    return c["eq"][0]["own"]


def emit(law: dict, doc: dict, model_import: str, counter: bool = False, note: str = "") -> Emitted:
    """LAWS.bend of an OWN law, or its counter-law (the exs form of BEND_PRIMER 5.4)."""
    oid = _own_id(law)
    stem, sub, m, x = oid.split(":")
    if stem != doc["stem"] or sub not in ("alias", "lost_write"):
        raise Unsupported(f"the own id {oid} is not the carrier's")
    bs = [b["name"] for b in law["statement"]["binders"]]
    if sub == "alias":
        b = f"{bname(m)}_{bname(x)}"
        binders = [(bs[0], f"List<&2, {ALIAS}.Call>"), (bs[1], f"{ALIAS}.Call")]
        lhs = f"{ALIAS}.oa_post_{b}({bs[0]}, {bs[1]})"
        rhs = f"{ALIAS}.oa_pre_{b}({bs[0]}, {bs[1]})"
        ty = "List<&2, U32>"
    else:
        b = f"{bname(m)}_{bname(x)}"
        binders = [(bs[0], f"{ALIAS}.LS_{b}"), (bs[1], f"{ALIAS}.LC_{b}")]
        lhs = f"{ALIAS}.ol_field_{b}({bs[0]}, {bs[1]})"
        rhs = f"{ALIAS}.ol_assigned_{b}({bs[0]}, {bs[1]})"
        ty = "Nat"
    name = law_name(law["law_id"], counter)
    q, pre = ("exs", "") if counter else ("for", "+")
    lines = ["# GENERATED by holon.gen.ownheap from the frozen law IR; do not edit.",
             f"# law_id: {law['law_id']}   statement_hash: {note}", "import Base", f"import {model_import} as {ALIAS}",
             "", f"law {name}:"] + [f"  {q} {pre}{n}: {t}" for n, t in binders] + \
            [f"  {{{lhs} {'!=' if counter else '=='} {rhs} : {ty}}}"]
    return Emitted(name, "\n".join(lines) + "\n", lhs, rhs, ty, binders)


HEADER = ["# GENERATED by holon.gen.ownheap; untrusted, accepted only if Bend checks it.", "import Base"]
EQ_FN = {"List<&2, U32>": "b_eq", "Nat": "n_eq"}


def counter_proof(em: Emitted, model_import: str, values: list[str]) -> str:
    """The counter-law's proof at a concrete witness: the binders' values, then the motive is_true(eq(_, lhs))."""
    lhs = em.lhs
    for (n, _t), v in zip(em.binders, values):
        lhs = re.sub(rf"(?<![\w.]){re.escape(n)}(?![\w])", lambda _m, v=v: v, lhs)
    eq = f"{ALIAS}.{EQ_FN[em.claim_type]}"
    inner = f"e => (%e : {ALIAS}.is_true({eq}(_, {lhs}))\n  Unit{{}})"
    term = inner
    for v in reversed(values):
        term = f"({v}, {term})"
    lines = HEADER + [f"import {model_import} as {ALIAS}", "import ./LAWS.bend as Laws", "",
                      "# class counter: concrete binders; the motive is Unit at the lhs and Empty at the rhs",
                      f"def Laws.{em.name}():", f"  {term}"]
    return "\n".join(lines) + "\n"


def disjoint_proof(em: Emitted, model_import: str, cr: Carrier, V: str, W: str) -> str | None:
    """heap_disjoint (W10): the alias law of a field view V of F and a writer W whose one effect on F appends a
    byte-slice parameter (live_route), as the library's store_same / trans_same at that effect, after the effects before
    it (on other fields: a lookup at the view's key passes their entries by computation). The proof is over every
    state, so it needs every method that can store into a modelled field to be in the class (an unsupported one could
    reach a state where two fields share a backing, which no state of the model represents). None when the route does
    not apply."""
    r = live_route(cr, V, W)
    if r is None or any(isinstance(m, Unsupported) for m in cr.methods.values()):
        return None
    k, e = r
    mw = cr.methods[W]
    i = mw.effects.index(e)
    if e.kind == "transient" and i:
        return None    # the fresh counter before the effect would be a later effect's: not this route
    fl = cr.fields
    t = cr.tag(fl[k - 1])
    b = f"{bname(V)}_{bname(W)}"
    args = [f"a{j}" for j in range(len(mw.params))]
    # the state W starts from (after V, which changes nothing for a field view): the fields as matched
    fields_t = [f"{ALIAS}.FS{{g{j + 1}, off{j + 1}, len{j + 1}, cap{j + 1}}}" for j in range(len(fl))]
    pre = f"{ALIAS}.St{{h, fc{''.join(', ' + x for x in fields_t)}}}"
    for j in range(i):
        pre = f"{ALIAS}.e_{bname(W)}_{j}({pre}{''.join(', ' + a for a in args)})"
    hpre = f"{ALIAS}.st_h({pre})"
    src = args[e.src[1]]
    n = f"Nat.add(len{k}, {ALIAS}.b_len({src}))"
    cond = f"Nat.is_le({n}, cap{k})"
    if e.kind == "store":
        lemma = f"l_store_same({cond}, {t}n, g{k}, off{k}, len{k}, cap{k}, {n}, {src}, {hpre})"
    else:
        lemma = f"l_trans_same({cond}, {t}n, g{k}, off{k}, len{k}, cap{k}, {n}, {src}, {hpre}, fc)"
    lines = HEADER + [f"import {model_import} as {ALIAS}", "import ./LAWS.bend as Laws", "", LIBRARY]
    lines.append(f"def main_{b}(st: {ALIAS}.St, w: {ALIAS}.Call) -> {{{ALIAS}.vr_post_{b}({ALIAS}.view_{bname(V)}(st), w) "
                 f"== {ALIAS}.vr_pre({ALIAS}.view_{bname(V)}(st)) : List<&2, U32>}}:")
    lines += ["  match st:", f"    case {ALIAS}.St{{+h, +fc{''.join(f', f{j + 1}' for j in range(len(fl)))}}}:"]
    ind = 6
    for j in range(len(fl)):
        lines += [" " * ind + f"match f{j + 1}:",
                  " " * (ind + 2) + f"case {ALIAS}.FS{{+g{j + 1}, +off{j + 1}, +len{j + 1}, +cap{j + 1}}}:"]
        ind += 4
    lines.append(" " * ind + "match w:")
    for nme, m in cr.methods.items():
        a = [f"+a{x}" for x in range(len(m.params))]
        lines.append(" " * (ind + 2) + f"case {ALIAS}.C_{bname(nme)}{{{', '.join(a)}}}:")
        lines.append(" " * (ind + 4) + (lemma if nme == W else "{==}"))
    lines += ["", f"def Laws.{em.name}(p, w):", f"  main_{b}({ALIAS}.run(p, {ALIAS}.s0()), w)"]
    return "\n".join(lines) + "\n"


def inhabitant_texts(law: dict, model_import: str, values: list[str]) -> tuple[str, str, str]:
    """(name, LAWS.bend, PROOF.bend) of a PROVED alias law's inhabitant at concrete (p, w): oa_live holds there, so the
    proof covers a run where W really writes into the view's backing (W10's checked inhabitant). Checked by Bend apart
    from the law's own pair; the record lists it among its attempts."""
    stem, sub, V, W = _own_id(law).split(":")
    b = f"{bname(V)}_{bname(W)}"
    name = "nv_" + law["law_id"].lower()
    laws = "\n".join(["# GENERATED by holon.gen.ownheap: an OWN alias law's inhabitant; do not edit.",
                      f"# law_id: {law['law_id']}", "import Base", f"import {model_import} as {ALIAS}", "",
                      f"law {name}:", f"  exs p: List<&2, {ALIAS}.Call>", f"  exs w: {ALIAS}.Call",
                      f"  {{{ALIAS}.oa_live_{b}(p, w) == True{{}} : Bool}}"]) + "\n"
    proof = "\n".join(HEADER + [f"import {model_import} as {ALIAS}", "import ./LAWS.bend as Laws", "",
                                f"def Laws.{name}():", f"  ({values[0]}, ({values[1]}, {{==}}))"]) + "\n"
    return name, laws, proof


# ====================================================================== the compiled model and the search
class CompiledModel:
    """A carrier model compiled with the pinned Bend to an ES module (cached by the text's hash)."""

    def __init__(self, source: Path, artifact: Path, doc: dict, cfg: dict | None, cr: Carrier):
        self.source, self.artifact, self.doc, self.cfg, self.carrier = source, artifact, doc, cfg, cr

    @classmethod
    def build(cls, doc: dict, sha: str, name: str, growth: dict, cfg: dict | None = None) -> "CompiledModel":
        text = generate(doc, sha, growth)
        h = hashlib.sha256(text.encode()).hexdigest()
        src = bend.build_dir(ROOT) / "own" / h[:16] / f"{name}.bend"
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
        return cls(src, art, doc, cfg, carrier(doc))

    def calls(self, exprs: list) -> list:
        """The compiled model's values of calls (holon/js/linked.mjs): untrusted, like every evaluation; Bend decides."""
        if not exprs:
            return []
        node = (self.cfg or bend.config()).get("node", "node")
        p = subprocess.run([node, f"--stack-size={max(bend.js_stack_bytes(self.cfg) // 1024, 984)}", str(DRIVER)],
                           input=json.dumps({"module": str(self.artifact), "calls": exprs}), capture_output=True,
                           text=True, timeout=1800)
        if p.returncode != 0:
            raise RuntimeError(f"node evaluation failed: {p.stderr[-2000:]}")
        return json.loads(p.stdout)["results"]

    def search(self, fn: str, W: str, search: dict, stop_on: bool) -> tuple[int | None, int]:
        """(index in candidates' order of the first candidate whose fn(p, w) is stop_on, or None; candidates tried):
        holon/js/ownsearch.mjs enumerates candidates' order on the compiled model. Untrusted: the caller re-evaluates
        the candidate it names."""
        cr = self.carrier
        ok = sorted(n for n, m in cr.methods.items() if isinstance(m, Method))
        req = {"module": str(self.artifact), "fn": fn, "stop_on": stop_on,
               "methods": [{"ctor": f"C_{bname(n)}", "nparams": len(cr.methods[n].params)} for n in ok],
               "writer": {"ctor": f"C_{bname(W)}", "nparams": len(cr.methods[W].params)},
               "max_calls": int(search["max_calls"]), "byte_lengths": [int(x) for x in search["byte_lengths"]]}
        node = (self.cfg or bend.config()).get("node", "node")
        p = subprocess.run([node, f"--stack-size={max(bend.js_stack_bytes(self.cfg) // 1024, 984)}", str(SEARCH)],
                           input=json.dumps(req), capture_output=True, text=True,
                           timeout=int(search.get("budget_s", 900)) + 60)
        if p.returncode != 0:
            raise RuntimeError(f"node search failed: {p.stderr[-2000:]}")
        r = json.loads(p.stdout)
        return r["index"], r["tried"]


def call_value(cr: Carrier, name: str, args: list[list[int]]) -> dict:
    return {"$": f"C_{bname(name)}", **{f"a{i}": list(a) for i, a in enumerate(args)}}


def call_text(name: str, args: list[list[int]]) -> str:
    def lit(a):
        return ("[" + ", ".join(str(x) for x in a) + "]") if a else "Nil{}"
    return f"{ALIAS}.C_{bname(name)}{{{', '.join(lit(a) for a in args)}}}"


def trace_text(calls: list) -> str:
    return ("[" + ", ".join(call_text(n, a) for n, a in calls) + "]") if calls else "Nil{}"


def candidates(cr: Carrier, W: str, search: dict):
    """The sidecar's bounded search (rule W10), in order: prefixes of calls of the modelled methods (lengths 0.. up to
    max_calls - 1), then W's call; each byte argument of a length from byte_lengths, argument i (0-based, in trace order)
    every byte (i + 1) mod 256."""
    ok = sorted(n for n, m in cr.methods.items() if isinstance(m, Method))
    lens = list(search["byte_lengths"])
    mw = cr.methods[W]

    def shapes(n_params):
        return list(itertools.product(lens, repeat=n_params))

    for depth in range(0, int(search["max_calls"])):
        for names in itertools.product(ok, repeat=depth):
            pools = [shapes(len(cr.methods[n].params)) for n in names] + [shapes(len(mw.params))]
            for combo in itertools.product(*pools):
                calls, idx = [], 0
                for n, ls in zip(list(names) + [W], combo):
                    args = []
                    for ln in ls:
                        args.append([(idx + 1) % 256] * ln)
                        idx += 1
                    calls.append((n, args))
                yield calls[:-1], calls[-1]


@dataclass
class Decision:
    status: str
    em: Emitted | None = None
    statement: Emitted | None = None
    check: object = None
    witness: dict | None = None
    difference: dict | None = None
    bound: str | None = None
    attempts: list = field(default_factory=list)


def decide(law: dict, cm: CompiledModel, ld: Path, pd: Path, model_import_l: str, model_import_p: str, cfg: dict,
           shash: str, write_pair, accepted, search: dict, scratch: Path | None = None) -> Decision:
    """Rule W10. Every status is Bend's: PROVED or REFUTED only through a LAWS.bend / PROOF.bend pair Bend accepts.
    scratch: a directory for the inhabitant's check (removed after)."""
    doc, cr = cm.doc, cm.carrier
    try:
        stmt = emit(law, doc, model_import_l, note=shash)
        cem = emit(law, doc, model_import_l, counter=True, note=shash)
    except Unsupported as e:
        return Decision("UNKNOWN", attempts=[{"kind": "emit", "error": f"unsupported statement form: {e}"}],
                        bound="not searched: the emitter cannot express this statement faithfully")
    stem, sub, m, x = _own_id(law).split(":")
    attempts = []
    if sub == "lost_write":
        lw = cr.lost.get((m, x))
        if not isinstance(lw, dict):
            return Decision("UNKNOWN", statement=stmt, attempts=[{"kind": "model", "error": str(lw)}],
                            bound=f"not searched: the lost write is outside the model class ({lw})")
        # the type's zero value: the field's length 0 (W10)
        b = f"{bname(m)}_{bname(x)}"
        vals = [f"{ALIAS}.LS_{b}{{0n}}", f"{ALIAS}.LC_{b}{{}}"]
        ok, rr, why = _check(ld, pd, write_pair, accepted, cem, counter_proof(cem, model_import_p, vals), cfg)
        attempts.append({"kind": "counter-law", "generator": "counter", "candidate": f"the zero value ({x} of length 0)",
                         "exit_code": rr.code, "marker": rr.marker, "seconds": rr.seconds,
                         **({} if ok else {"error": why})})
        if ok:
            return Decision("REFUTED", em=cem, statement=stmt, check=rr, witness={"x": {x: {"len": 0}}, "c": m},
                            difference={"field_len_after": 0, "assigned_len": lw["len"]}, attempts=attempts)
        _clean(ld, pd)
        return Decision("UNKNOWN", statement=stmt, attempts=attempts,
                        bound="the counter-law at the type's zero value is not accepted; no proof route")
    V, W = m, x
    bad = {n: str(cr.methods.get(n)) for n in (V, W) if not isinstance(cr.methods.get(n), Method)}
    if bad:
        return Decision("UNKNOWN", statement=stmt, attempts=[{"kind": "model", "error": f"unsupported: {bad}"}],
                        bound=f"not searched: the model class does not cover {sorted(bad)} (rule W9)")
    if cr.init is not None:
        return Decision("UNKNOWN", statement=stmt, attempts=[{"kind": "model", "error": cr.init}],
                        bound=f"not searched: the constructor's value is outside the model class ({cr.init})")
    b = f"{bname(V)}_{bname(W)}"
    proof = disjoint_proof(stmt, model_import_p, cr, V, W)
    if proof is not None:
        ok, rr, why = _check(ld, pd, write_pair, accepted, stmt, proof, cfg)
        attempts.append({"kind": "proof", "generator": "heap_disjoint", "exit_code": rr.code, "marker": rr.marker,
                         "seconds": rr.seconds, **({} if ok else {"error": why})})
        if ok:
            attempts.append(_inhabitant(law, cm, W, b, search, cfg, scratch or (pd.parent / f".nv_{law['law_id']}")))
            return Decision("PROVED", em=stmt, statement=stmt, check=rr, attempts=attempts)
    else:
        attempts.append({"kind": "proof", "generator": "heap_disjoint",
                         "error": "does not apply: the view is not a field view, or the writer does not write the "
                                  "view's field exactly once by appending a parameter past the view's end (an "
                                  "overlapping write), or a method outside the model class stores into a field"})
    index, tried = cm.search(f"oa_eq_{b}", W, search, stop_on=False)
    attempts.append({"kind": "refute", "engine": "compiled-model search", "tried": tried, "hit": index is not None,
                     "pool": {k: search[k] for k in ("max_calls", "byte_lengths")}})
    if index is None:
        _clean(ld, pd)
        return Decision("UNKNOWN", statement=stmt, attempts=attempts,
                        bound=(f"no trace of the pool refutes it ({tried} candidates: up to {search['max_calls']} calls, "
                               f"byte lengths {search['byte_lengths']}); heap_disjoint "
                               + ("failed" if proof is not None else "does not apply (an overlapping write)")))
    prefix, last = next(itertools.islice(candidates(cr, W, search), index, None))
    pv = {"val": [call_value(cr, n, a) for n, a in prefix]}
    wv = {"val": call_value(cr, *last)}
    pre, post = cm.calls([{"fn": f"oa_pre_{b}", "args": [pv, wv]}, {"fn": f"oa_post_{b}", "args": [pv, wv]}])
    if not (isinstance(pre, list) and isinstance(post, list)) or pre == post:
        raise RuntimeError(f"the search named candidate {index}, whose sides the model does not tell apart: {pre} / "
                           f"{post}")
    vals = [trace_text(prefix), call_text(*last)]
    ok, rr, why = _check(ld, pd, write_pair, accepted, cem, counter_proof(cem, model_import_p, vals), cfg)
    attempts.append({"kind": "counter-law", "generator": "counter", "candidate": index, "exit_code": rr.code,
                     "marker": rr.marker, "seconds": rr.seconds, **({} if ok else {"error": why})})
    if not ok:
        _clean(ld, pd)
        return Decision("UNKNOWN", statement=stmt, attempts=attempts, bound="the witness's counter-law was not accepted")
    wit = {"p": [{"method": n, "args": ["0x" + bytes(a).hex() for a in args]} for n, args in prefix],
           "w": {"method": last[0], "args": ["0x" + bytes(a).hex() for a in last[1]]}}
    return Decision("REFUTED", em=cem, statement=stmt, check=rr, witness=wit,
                    difference={"view_before": "0x" + bytes(pre).hex(), "view_after": "0x" + bytes(post).hex()},
                    attempts=attempts)


def _inhabitant(law: dict, cm: CompiledModel, W: str, b: str, search: dict, cfg: dict, d: Path) -> dict:
    """The attempt entry of a PROVED alias law's inhabitant: the first candidate of the pool where oa_live holds,
    stated as an existential law and checked by Bend in d (removed after)."""
    cr = cm.carrier
    out = {"kind": "inhabitant", "generator": "live"}
    index, tried = cm.search(f"oa_live_{b}", W, search, stop_on=True)
    if index is None:
        return {**out, "tried": tried, "error": "no candidate of the pool makes W write into the view's backing"}
    prefix, last = next(itertools.islice(candidates(cr, W, search), index, None))
    d = Path(d)
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    try:
        shutil.copyfile(cm.source, d / "model.bend")
        name, laws, proof = inhabitant_texts(law, "./model.bend", [trace_text(prefix), call_text(*last)])
        (d / "LAWS.bend").write_text(laws)
        (d / "PROOF.bend").write_text(proof)
        rr = bend.check(d / "PROOF.bend", cfg)
        ok = rr.ok and not bend.escape_hatches(laws + proof)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    wit = {"p": [{"method": n, "args": ["0x" + bytes(a).hex() for a in args]} for n, args in prefix],
           "w": {"method": last[0], "args": ["0x" + bytes(a).hex() for a in last[1]]}}
    return {**out, "law": name, "candidate": index, "witness": wit, "exit_code": rr.code, "marker": rr.marker,
            "seconds": rr.seconds, **({} if ok else {"error": (rr.out or "")[-600:]})}


def _clean(ld: Path, pd: Path) -> None:
    for x in {ld, pd}:
        shutil.rmtree(x, ignore_errors=True)


def _check(ld, pd, write_pair, accepted, em: Emitted, proof: str, cfg):
    _clean(ld, pd)
    pf = write_pair(ld, pd, em.text, proof)
    rr = bend.check(pf, cfg)
    ok, why = accepted(rr, pf, ld / "LAWS.bend", em, proof)
    return ok, rr, why


# ====================================================================== the ledger bundle (W11)
EQ_DEFS = ("ite", "n_eq", "b_len", "b_over", "b_write", "b_drop", "b_take", "b_zeros", "b_app3", "b_eq", "is_true",
           "AR", "ar_h", "ar_s", "TR", "tr_h", "tr_v", "tr_fc", "VR", "vr_pre", "vr_post_*", "oa_*", "Call", "run",
           "st_h", "st_f*", "LC_*", "ol_field_*")
METHOD_DEFS = ("e_*", "do_*", "vw_*", "view_*", "step", "ol_go_*", "ol_assigned_*")
TEXTS = {
    "A-go-growth": "An append of k bytes onto a byte slice of length len and capacity cap is in place when len + k <= "
                   "cap; else its new backing has the capacity Go 1.24's growslice gives (runtime/slice.go "
                   "nextslicecap, then runtime/msize.go roundupsize over runtime/sizeclasses.go's class_to_size, the "
                   "constants of the OWN sidecar), the old bytes copied and the rest zero. The growth is an oracle of "
                   "the pinned toolchain; replay compares every capacity of a witness with the real one (rule W12).",
    "A-own-fields": "The heap holds one backing per modelled field and generation and one per transient allocation: "
                    "distinct modelled fields never share a backing (every store into one is an append onto itself, "
                    "checked at generation), an abstracted field is not modelled (every store into one is an append "
                    "onto it or a fresh value), and non-slice fields and non-byte-slice parameters are not modelled. "
                    "The constructor's value has every modelled field empty: len 0, cap 0, no backing (rule W9; the "
                    "Go document records stores alone, so a composite literal's empty make is the zero value).",
    "A-own-len": "A lost write compares lengths: a value receiver's field keeps its length, and the method assigns a "
                 "fresh allocation of the lost write's constant length exactly under the condition of the slice "
                 "result case with the same allocation site (rule W9).",
}


def declared_bundle(doc: dict, rel: str, sha: str, root: Path) -> dict:
    """The ledger bundle of an OWN carrier model (holon.records; rule W11): every assumption the Go document declares
    (its "assumptions"), each introduced by the methods' definitions, and A-go-growth, A-own-fields and A-own-len.
    Every definition generate() writes is classified: by an entry, or the one no_assumption group (equality and
    structure utilities, the laws' sides and the trace runner)."""
    drel = doc["document"]
    try:
        src = json.loads((Path(root) / drel).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        src = {}
    own = {"A-go-growth": ["g_classes", "g_round_in", "g_grow", "g_next", "growcap", "st_app_e", "tr_app_e"],
           "A-own-fields": ["OKey", "OBk", "OSl", "FS", "St", "key_eq", "h_get", "fbytes", "vbytes", "s0"],
           "A-own-len": ["LS_*", "ol_go_*", "ol_assigned_*"]}
    entries, seen = [], set(own)
    for i, a in enumerate(src.get("assumptions") or []):
        if not isinstance(a, dict) or not isinstance(a.get("id"), str):
            continue
        aid = re.sub(r"[^A-Za-z0-9_-]", "-", a["id"])
        while aid in seen:
            aid += "-2"
        seen.add(aid)
        entries.append({"id": aid, "kind": "abstraction", "source": f"{drel}#/assumptions/{i}",
                        "text": a.get("text", ""), "introduced_by": list(METHOD_DEFS)})
    for k in sorted(own):
        entries.append({"id": k, "kind": "abstraction", "source": f"{rel}#/methods", "text": TEXTS[k],
                        "introduced_by": sorted(own[k])})
    return {"facts": rel, "facts_sha256": sha, "model": f"model/own_{doc['stem']}",
            "doc": "The model of an OWN carrier document (holon.gen.ownheap): the assumptions its Go document declares, "
                   "and the heap model's own (generated from the document, never hand-written).",
            "entries": entries,
            "no_assumption": [{"defs": list(EQ_DEFS), "why": "equality and structure utilities of the generator "
                                                             "prelude, the laws' two sides and the trace runner: no "
                                                             "modelling choice"}]}


def growth_of(root: Path, milestone: str) -> dict:
    return json.loads((Path(root) / SIDECAR.format(m=milestone)).read_text(encoding="utf-8"))["growth"]


def search_of(root: Path, milestone: str) -> dict:
    return json.loads((Path(root) / SIDECAR.format(m=milestone)).read_text(encoding="utf-8"))["search"]
