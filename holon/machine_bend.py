"""The Bend text of an extracted model (I20; holon.machine.write_model; the contract is clause 1 of the docstring of
tests_m2/test_extracted_refinement.py).

Representation (all values Nat; 256-bit words reduced mod 2^256 by the w_* helpers):
  HStore   one field per storage family the model holds (holon.machine.ExtractedModel.families, inherited storage
           included): an elementary value as its Nat value, a mapping to an elementary value as a list of HKV{k, v}
           (absent keys read 0), a mapping to a struct as a list of HKS_<S>{k, v: H<S>} (absent keys read the zero
           record), plus f__slots, raw slots for ["sload", slot] terms. The model is family-level: packing and slot
           arithmetic are the evaluator's (holon.extracted_eval), which is the evaluator of record.
  HEnv     the environment: one Nat per global the terms read (caller, this, block.*, msg.value, ...), the blobhash
           list, per external function a table of answers (argument list -> [ok, results..]), keccak256 and sha256
           tables (byte list -> word), and unk: the values of the terms the generator leaves to the environment
           (unknown, phi, carried/exit/count terms of loops, and any term it does not translate: each gets an id,
           listed in the model's header);
  A_<a>    per action, its arguments (from the compiler's ABI): words as Nat, bytes and strings as byte lists, structs
           as records S<name>, arrays as lists;
  chk_<a>(st, ar, en) -> Nat
           0 when every check of the action holds, k + 1 when check k (holon.machine.ExtractedModel.reaches order) is
           the first whose condition is 0. Each check is a decision helper k_<a>_<i>(c, st, ar, en) that matches the
           condition (a parameter, BEND_PRIMER §4) and continues with the next. A loop record is one decision whose
           value the environment gives (unk: 0 when every check of its body holds at every iteration, else k + 1).
  post_<a>(st, ar, en) -> HStore   the action's writes in program order (each value over the pre-state, as the
           document states them; a conditional write under ite), when every write is top level and translatable;
  step_<a>(st, ar, en) -> HStore   post_<a> when chk_<a> is 0, else st.
Memory regions ["mem", ...] are byte lists built by m_put from their writes over unknown cells (57005, outside the byte
range, BEND_PRIMER §4); a region a loop or an unknown write touches is all unknown cells.

On concrete values chk_<a> and step_<a> agree with the evaluator (tests_m2/test_i20_model_unit.py compiles the toy
model and compares). Executing the compiled model is exact only while every value it computes stays below 2^48: the
compiled Nat of the pinned Bend (2.0.36) stops there ("a Nat past the largest immediate 2^48-1"), and a kernel
normalization unfolds Nat in unary. The w_* helpers never build 2^256 or 2^k unless a value needs it (w_lt_pow2 halves
instead), so small concrete values run; addresses past 2^48, hashes and 2^256 wrap-around do not. This is why the
evaluator of record is holon.extracted_eval; the Bend model is what Bend checks.
"""
from __future__ import annotations

import json
import re

from .machine import MACHINE_VERSION, MASK, Check, Event, ExtractedModel, Loop, ModelError, Write

BEND_PRELUDE = '''\
def ite(-A: Data, c: Bool, a: A, b: A) -> A:
  match c:
    case True{}:
      a
    case False{}:
      b

def nth_d(-A: Data, xs: List<&2, A>, i: Nat, d: A) -> A:
  match xs i:
    case Nil{} _:
      d
    case Con{h, t} 0n:
      h
    case Con{h, t} 1n+p:
      nth_d(A, t, p, d)

def w_W() -> Nat:
  Nat.pow(2n, 256n)

def w_bool(c: Bool) -> Nat:
  match c:
    case True{}:
      1n
    case False{}:
      0n

def w_truth(+x: Nat) -> Bool:
  Nat.is_ne(x, 0n)

def w_lt_pow2(k: Nat, +x: Nat) -> Bool:
  match k:
    case 0n:
      Nat.is_eq(x, 0n)
    case 1n+p:
      w_lt_pow2(p, Nat.div(x, 2n))

def w_norm_go(c: Bool, +s: Nat) -> Nat:
  match c:
    case True{}:
      s
    case False{}:
      Nat.mod(s, w_W())

def w_norm(+s: Nat) -> Nat:
  w_norm_go(w_lt_pow2(256n, s), s)

def w_add(+a: Nat, +b: Nat) -> Nat:
  w_norm(Nat.add(a, b))

def w_sub_go(c: Bool, +a: Nat, +b: Nat) -> Nat:
  match c:
    case True{}:
      Nat.sub(a, b)
    case False{}:
      Nat.sub(w_W(), Nat.sub(b, a))

def w_sub(+a: Nat, +b: Nat) -> Nat:
  w_sub_go(Nat.is_ge(w_norm(a), w_norm(b)), w_norm(a), w_norm(b))

def w_mul(+a: Nat, +b: Nat) -> Nat:
  w_norm(Nat.mul(a, b))

def w_div_go(z: Bool, +a: Nat, +b: Nat) -> Nat:
  match z:
    case True{}:
      0n
    case False{}:
      Nat.div(a, b)

def w_div(+a: Nat, +b: Nat) -> Nat:
  w_div_go(Nat.is_eq(b, 0n), a, b)

def w_rem_go(z: Bool, +a: Nat, +b: Nat) -> Nat:
  match z:
    case True{}:
      0n
    case False{}:
      Nat.mod(a, b)

def w_rem(+a: Nat, +b: Nat) -> Nat:
  w_rem_go(Nat.is_eq(b, 0n), a, b)

def w_sel(c: Bool, +a: Nat, +b: Nat) -> Nat:
  match c:
    case True{}:
      a
    case False{}:
      b

def w_exp_go(n: Nat, +a: Nat, +b: Nat, +acc: Nat) -> Nat:
  match n:
    case 0n:
      acc
    case 1n+p:
      w_exp_go(p, w_mul(a, a), Nat.div(b, 2n), w_sel(Nat.is_eq(Nat.mod(b, 2n), 1n), w_mul(acc, a), acc))

def w_exp(+a: Nat, +b: Nat) -> Nat:
  w_exp_go(256n, w_norm(a), b, 1n)

def w_band_go(n: Nat, +a: Nat, +b: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      Nat.add(Nat.mul(2n, w_band_go(p, Nat.div(a, 2n), Nat.div(b, 2n))), Nat.mul(Nat.mod(a, 2n), Nat.mod(b, 2n)))

def w_bor_go(n: Nat, +a: Nat, +b: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      Nat.add(Nat.mul(2n, w_bor_go(p, Nat.div(a, 2n), Nat.div(b, 2n))), Nat.sub(Nat.add(Nat.mod(a, 2n), Nat.mod(b, 2n)), Nat.mul(Nat.mod(a, 2n), Nat.mod(b, 2n))))

def w_bxor_go(n: Nat, +a: Nat, +b: Nat) -> Nat:
  match n:
    case 0n:
      0n
    case 1n+p:
      Nat.add(Nat.mul(2n, w_bxor_go(p, Nat.div(a, 2n), Nat.div(b, 2n))), Nat.mod(Nat.add(Nat.mod(a, 2n), Nat.mod(b, 2n)), 2n))

def w_band(+a: Nat, +b: Nat) -> Nat:
  w_band_go(256n, a, b)

def w_bor(+a: Nat, +b: Nat) -> Nat:
  w_bor_go(256n, a, b)

def w_bxor(+a: Nat, +b: Nat) -> Nat:
  w_bxor_go(256n, a, b)

def w_bnot(+a: Nat) -> Nat:
  Nat.sub(Nat.sub(w_W(), 1n), Nat.mod(a, w_W()))

def w_neg(+a: Nat) -> Nat:
  w_sub(0n, a)

def w_dbl(k: Nat, +a: Nat) -> Nat:
  match k:
    case 0n:
      a
    case 1n+p:
      w_dbl(p, w_norm(Nat.mul(a, 2n)))

def w_half(k: Nat, +a: Nat) -> Nat:
  match k:
    case 0n:
      a
    case 1n+p:
      w_half(p, Nat.div(a, 2n))

def w_shl_go(ok: Bool, +a: Nat, +k: Nat) -> Nat:
  match ok:
    case True{}:
      w_dbl(k, a)
    case False{}:
      0n

def w_shl(+a: Nat, +k: Nat) -> Nat:
  w_shl_go(Nat.is_lt(k, 256n), a, k)

def w_shr_go(ok: Bool, +a: Nat, +k: Nat) -> Nat:
  match ok:
    case True{}:
      w_half(k, a)
    case False{}:
      0n

def w_shr(+a: Nat, +k: Nat) -> Nat:
  w_shr_go(Nat.is_lt(k, 256n), a, k)

def w_trunc_go(c: Bool, +bits: Nat, +a: Nat) -> Nat:
  match c:
    case True{}:
      a
    case False{}:
      Nat.mod(a, Nat.pow(2n, bits))

def w_trunc(+bits: Nat, +a: Nat) -> Nat:
  w_trunc_go(w_lt_pow2(bits, a), bits, a)

def w_eq(+a: Nat, +b: Nat) -> Nat:
  w_bool(Nat.is_eq(a, b))

def w_ne(+a: Nat, +b: Nat) -> Nat:
  w_bool(Nat.is_ne(a, b))

def w_lt(+a: Nat, +b: Nat) -> Nat:
  w_bool(Nat.is_lt(a, b))

def w_le(+a: Nat, +b: Nat) -> Nat:
  w_bool(Nat.is_le(a, b))

def w_gt(+a: Nat, +b: Nat) -> Nat:
  w_bool(Nat.is_gt(a, b))

def w_ge(+a: Nat, +b: Nat) -> Nat:
  w_bool(Nat.is_ge(a, b))

def w_land(+a: Nat, +b: Nat) -> Nat:
  w_bool(Bool.and(w_truth(a), w_truth(b)))

def w_lor(+a: Nat, +b: Nat) -> Nat:
  w_bool(Bool.or(w_truth(a), w_truth(b)))

def w_lnot(+a: Nat) -> Nat:
  w_bool(Nat.is_eq(a, 0n))

def w_ite(+c: Nat, +a: Nat, +b: Nat) -> Nat:
  w_sel(w_truth(c), a, b)

def w_fits(+bits: Nat, +x: Nat) -> Nat:
  w_bool(w_lt_pow2(bits, x))

def w_fits_sub(+bits: Nat, +a: Nat, +b: Nat) -> Nat:
  w_land(w_ge(a, b), w_fits(bits, Nat.sub(a, b)))

def w_lit(xs: List<&2, Nat>, +acc: Nat) -> Nat:
  match xs:
    case Nil{}:
      acc
    case Con{h, t}:
      w_lit(t, Nat.add(Nat.mul(acc, 65536n), h))

def w_bytes_go(n: Nat, +x: Nat, +acc: List<&2, Nat>) -> List<&2, Nat>:
  match n:
    case 0n:
      acc
    case 1n+p:
      w_bytes_go(p, Nat.div(x, 256n), Con{Nat.mod(x, 256n), acc})

def w_bytes32(+x: Nat) -> List<&2, Nat>:
  w_bytes_go(32n, w_norm(x), Nil{})

def w_be_go(n: Nat, +xs: List<&2, Nat>, +acc: Nat) -> Nat:
  match n:
    case 0n:
      acc
    case 1n+p:
      w_be_go(p, List.drop(&2, Nat, xs, 1n), Nat.add(Nat.mul(acc, 256n), nth_d(Nat, xs, 0n, 0n)))

def w_word(+xs: List<&2, Nat>, +k: Nat) -> Nat:
  w_be_go(32n, List.drop(&2, Nat, xs, k), 0n)

def l_eq(xs: List<&2, Nat>, ys: List<&2, Nat>) -> Bool:
  match xs ys:
    case Nil{} Nil{}:
      True{}
    case Nil{} Con{h, t}:
      False{}
    case Con{h, t} Nil{}:
      False{}
    case Con{a, s} Con{b, u}:
      Bool.and(Nat.is_eq(a, b), l_eq(s, u))

def l_pad(n: Nat, xs: List<&2, Nat>) -> List<&2, Nat>:
  match n xs:
    case 0n _:
      Nil{}
    case 1n+p Nil{}:
      Con{0n, l_pad(p, Nil{})}
    case 1n+p Con{h, t}:
      Con{h, l_pad(p, t)}

def l_slice(+xs: List<&2, Nat>, +off: Nat, +n: Nat) -> List<&2, Nat>:
  l_pad(n, List.drop(&2, Nat, xs, off))

def l_enc(xs: List<&2, Nat>, +acc: Nat) -> Nat:
  match xs:
    case Nil{}:
      acc
    case Con{+h, t}:
      l_enc(t, Nat.add(Nat.div(Nat.mul(Nat.add(acc, h), Nat.add(Nat.add(acc, h), 1n)), 2n), h))

def m_overlay(mem: List<&2, Nat>, bs: List<&2, Nat>) -> List<&2, Nat>:
  match mem bs:
    case Nil{} _:
      Nil{}
    case Con{h, t} Nil{}:
      Con{h, t}
    case Con{h, t} Con{b, r}:
      Con{b, m_overlay(t, r)}

def m_put(mem: List<&2, Nat>, off: Nat, bs: List<&2, Nat>) -> List<&2, Nat>:
  match mem off:
    case Nil{} _:
      Nil{}
    case Con{h, t} 0n:
      m_overlay(Con{h, t}, bs)
    case Con{h, t} 1n+p:
      Con{h, m_put(t, p, bs)}

type HKV is Data:
  HKV{k: Nat, v: Nat}

type HLog is Data:
  HLog{t: List<&2, Nat>, d: List<&2, Nat>}

type HKB is Data:
  HKB{b: List<&2, Nat>, v: Nat}

type HKL is Data:
  HKL{b: List<&2, Nat>, v: List<&2, Nat>}

def kv_get(xs: List<&2, HKV>, +k: Nat) -> Nat:
  match xs:
    case Nil{}:
      0n
    case Con{+h, +t}:
      match h:
        case HKV{+hk, +hv}:
          ite(Nat, Nat.is_eq(hk, k), hv, kv_get(t, k))

def kv_set(xs: List<&2, HKV>, +k: Nat, +v: Nat) -> List<&2, HKV>:
  match xs:
    case Nil{}:
      [HKV{k, v}]
    case Con{+h, +t}:
      match h:
        case HKV{+hk, +hv}:
          ite(List<&2, HKV>, Nat.is_eq(hk, k), Con{HKV{k, v}, t}, Con{HKV{hk, hv}, kv_set(t, k, v)})

def kb_get(xs: List<&2, HKB>, +k: List<&2, Nat>) -> Nat:
  match xs:
    case Nil{}:
      0n
    case Con{+h, +t}:
      match h:
        case HKB{+hb, +hv}:
          ite(Nat, l_eq(hb, k), hv, kb_get(t, k))

def kl_get(xs: List<&2, HKL>, +k: List<&2, Nat>) -> List<&2, Nat>:
  match xs:
    case Nil{}:
      Nil{}
    case Con{+h, +t}:
      match h:
        case HKL{+hb, +hv}:
          ite(List<&2, Nat>, l_eq(hb, k), hv, kl_get(t, k))
'''

SENTINEL = 57005          # an unknown memory byte (outside 0..255: never equal to a real byte; BEND_PRIMER §4)
MAX_REGION = 4096         # the largest memory region expanded cell by cell
_BOPS = {"+": "w_add", "-": "w_sub", "*": "w_mul", "/": "w_div", "%": "w_rem", "**": "w_exp", "&": "w_band",
         "|": "w_bor", "^": "w_bxor", "<<": "w_shl", ">>": "w_shr", "==": "w_eq", "!=": "w_ne", "<": "w_lt",
         "<=": "w_le", ">": "w_gt", ">=": "w_ge"}


def bname(s: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_]", "_", str(s))
    return out if out and not out[0].isdigit() else "x" + out


def comment(s) -> str:
    """Text safe in a generated comment (holon.bend.escape_hatches scans comments: no ? or @ or quote)."""
    return re.sub(r"[?@\"]", "_", str(s)).replace("\n", " ")


class BendDebt(Exception):
    """A term the generator does not translate (it becomes an environment value with its own id)."""


class BendModel:
    def __init__(self, m: ExtractedModel):
        self.m = m
        self.records: dict = {}       # Bend type name -> [(field, bend type)]
        self.env_keys: list = []      # env globals, first-use order
        self.calls: list = []         # external functions, first-use order
        self.unknowns: dict = {}      # term key -> id
        self.debt: list = []          # [{id, term, why}]
        self.store_fields: list = []  # (field, bend type, family | None)
        self.fam_kind: dict = {}      # family -> ("n",) | ("kv",) | ("ks", record) | ("raw",)
        self.no_post: dict = {}       # action -> why its post-state is not compiled
        self.no_logs: dict = {}       # action -> why its logs are not compiled

    # ---------------------------------------------------------------- types
    def struct_record(self, tid: str) -> str:
        t = self.m.type_of(tid)
        name = "H" + bname(str(t.get("label", tid)).replace("struct ", ""))
        if name not in self.records:
            fs = []
            for mm in t.get("members") or []:
                mt = self.m.type_of(mm["type"])
                if mt.get("encoding") != "inplace" or "members" in mt or "base" in mt:
                    raise ModelError(f"struct {t.get('label')}: member {mm['label']} is not elementary (not compiled)")
                fs.append((bname(mm["label"]), "Nat"))
            self.records[name] = fs
        return name

    def families(self) -> None:
        for name, f in sorted(self.m.families.items(), key=lambda kv: (kv[1].slot, kv[1].offset, kv[0])):
            t = self.m.type_of(f.type)
            fld = "f_" + bname(name)
            if t.get("encoding") == "inplace" and "members" not in t and "base" not in t:
                self.fam_kind[name] = ("n",)
                self.store_fields.append((fld, "Nat", name))
            elif t.get("encoding") == "mapping":
                vt = self.m.type_of(t["value"])
                if vt.get("encoding") == "inplace" and "members" not in vt and "base" not in vt:
                    self.fam_kind[name] = ("kv",)
                    self.store_fields.append((fld, "List<&2, HKV>", name))
                elif vt.get("encoding") == "inplace" and "members" in vt:
                    try:
                        rec = self.struct_record(t["value"])
                    except ModelError:
                        self.fam_kind[name] = ("raw",)
                        continue
                    self.fam_kind[name] = ("ks", rec)
                    self.store_fields.append((fld, f"List<&2, HKS_{rec}>", name))
                else:
                    self.fam_kind[name] = ("raw",)
            else:
                self.fam_kind[name] = ("raw",)
        self.store_fields.append(("f__slots", "List<&2, HKV>", None))

    def arg_type(self, p: dict) -> str:
        t = p.get("type", "")
        m = re.fullmatch(r"(.*)\[(\d*)\]", t)
        if m:
            return f"List<&2, {self.arg_type(dict(p, type=m.group(1)))}>"
        if t == "tuple":
            name = "S" + bname(p.get("struct") or "tuple")
            if name not in self.records:
                self.records[name] = []
                self.records[name] = [(bname(c["name"]), self.arg_type(c)) for c in p.get("components") or []]
            return name
        if t in ("bytes", "string"):
            return "List<&2, Nat>"
        return "Nat"

    @staticmethod
    def kind_of_type(ty: str) -> str:
        if ty == "Nat":
            return "n"
        if ty == "List<&2, Nat>":
            return "b"
        if ty.startswith("List<&2, "):
            return "l:" + ty[len("List<&2, "):-1]
        return "r:" + ty

    def fam_type(self, fam: str) -> str:
        for _fld, ty, f in self.store_fields:
            if f == fam:
                return ty
        raise BendDebt(f"family {fam}")

    # ---------------------------------------------------------------- terms
    def lit(self, c: int) -> str:
        c &= MASK
        if c < (1 << 32):
            return f"{c}n"
        limbs = []
        while c:
            limbs.append(c & 0xFFFF)
            c >>= 16
        return "w_lit([" + ", ".join(f"{x}n" for x in reversed(limbs)) + "], 0n)"

    def unknown(self, key: str, why: str) -> tuple[str, str]:
        if key not in self.unknowns:
            self.unknowns[key] = len(self.unknowns)
            self.debt.append({"id": self.unknowns[key], "term": key, "why": why})
        return f"kv_get(ge_unk(en), {self.unknowns[key]}n)", "n"

    def env_key(self, key: str) -> str:
        if key not in self.env_keys:
            self.env_keys.append(key)
        return f"ge_e_{bname(key)}(en)"

    def nat(self, t, a: str) -> str:
        code, kind = self.bx(t, a)
        if kind == "n":
            return code
        if kind == "c":
            return f"nth_d(Nat, {code}, 1n, 0n)"
        return self.unknown(_key(t), f"a {kind} value used as a word")[0]

    def byts(self, t, a: str) -> str:
        code, kind = self.bx(t, a)
        if kind == "b":
            return code
        if kind == "n":
            return f"w_bytes32({code})"
        raise BendDebt(f"a {kind} value used as bytes")

    def bx(self, t, a: str) -> tuple[str, str]:
        try:
            return self._bx(t, a)
        except BendDebt as e:
            return self.unknown(_key(t), str(e))

    def call_key(self, args, a: str) -> str:
        out = []
        for x in args:
            c, k = self.bx(x, a)
            if k == "n":
                out.append(c)
            elif k == "b":
                out.append(f"l_enc({c}, 0n)")
            else:
                raise BendDebt(f"a call argument of kind {k}")
        return f"[{', '.join(out)}]" if out else "Nil{}"

    def call_table(self, fn: str) -> str:
        if fn not in self.calls:
            self.calls.append(fn)
        return f"ge_c{self.calls.index(fn)}(en)"

    def _bx(self, t, a: str) -> tuple[str, str]:
        if isinstance(t, bool):
            return ("1n" if t else "0n"), "n"
        if isinstance(t, int):
            return self.lit(t), "n"
        if not isinstance(t, list) or not t or not isinstance(t[0], str):
            raise BendDebt("not a term")
        h = t[0]
        if h in ("<", ">=") and len(t) == 3 and _pow2(t[2]):   # a range check: no 2^k is built (module docstring)
            c = f"w_bool(w_lt_pow2({_pow2(t[2])}n, {self.nat(t[1], a)}))"
            return (c if h == "<" else f"w_lnot({c})"), "n"
        if h in _BOPS and len(t) == 3:
            return f"{_BOPS[h]}({self.nat(t[1], a)}, {self.nat(t[2], a)})", "n"
        if h in ("&&", "||"):
            f = "w_land" if h == "&&" else "w_lor"
            xs = [self.nat(x, a) for x in t[1:]]
            if not xs:
                return ("1n" if h == "&&" else "0n"), "n"
            out = xs[-1]
            for x in reversed(xs[:-1]):
                out = f"{f}({x}, {out})"
            return out, "n"
        if h == "!":
            return f"w_lnot({self.nat(t[1], a)})", "n"
        if h in ("~", "not"):
            return f"w_bnot({self.nat(t[1], a)})", "n"
        if h == "neg":
            return f"w_neg({self.nat(t[1], a)})", "n"
        if h == "trunc":
            return f"w_trunc({self.nat(t[1], a)}, {self.nat(t[2], a)})", "n"
        if h == "fits" and isinstance(t[1], int) and isinstance(t[2], list) and len(t[2]) == 3:
            op, x, y = t[2]
            bits = self.lit(t[1])
            if op == "+":
                return f"w_fits({bits}, Nat.add({self.nat(x, a)}, {self.nat(y, a)}))", "n"
            if op == "*":
                return f"w_fits({bits}, Nat.mul({self.nat(x, a)}, {self.nat(y, a)}))", "n"
            if op == "-":
                return f"w_fits_sub({bits}, {self.nat(x, a)}, {self.nat(y, a)})", "n"
            raise BendDebt(f"fits over {op}")
        if h == "?":
            ca, ka = self.bx(t[2], a)
            cb, kb = self.bx(t[3], a)
            c = self.nat(t[1], a)
            if ka == kb == "n":
                return f"w_ite({c}, {ca}, {cb})", "n"
            if {ka, kb} <= {"n", "b"}:
                return f"ite(List<&2, Nat>, w_truth({c}), {self.byts(t[2], a)}, {self.byts(t[3], a)})", "b"
            if ka == kb and ka.startswith("f:"):
                return f"ite({self.fam_type(ka[2:])}, w_truth({c}), {ca}, {cb})", ka
            if ka == kb and ka.startswith("r:"):
                return f"ite({ka[2:]}, w_truth({c}), {ca}, {cb})", ka
            raise BendDebt(f"a conditional over {ka} and {kb}")
        if h == "param":
            ps = {p["name"]: p for p in self.m.params(a) or []}
            p = ps.get(t[1])
            if p is None:
                raise BendDebt(f"parameter {t[1]} has no ABI type")
            return f"ga_{bname(a)}_{bname(t[1])}(ar)", self.kind_of_type(self.arg_type(p))
        if h == "member":
            base, kb = self.bx(t[1], a)
            if kb.startswith("r:"):
                rec = kb[2:]
                fs = dict(self.records.get(rec) or [])
                fld = bname(t[2])
                if fld not in fs:
                    raise BendDebt(f"no member {t[2]} in {rec}")
                return f"g_{rec}_{fld}({base})", self.kind_of_type(fs[fld])
            raise BendDebt(f"a member of a {kb} value")
        if h == "storage":
            k = self.fam_kind.get(t[1], ("raw",))
            if k[0] == "raw":
                raise BendDebt(f"family {t[1]} is not compiled")
            return f"gs_{bname(t[1])}(st)", ("n" if k[0] == "n" else "f:" + t[1])
        if h == "store":
            return self.store(t, a)
        if h == "map":
            base, kb = self.bx(t[1], a)
            if not kb.startswith("f:"):
                raise BendDebt("a map access into a value that is not a family")
            fam = kb[2:]
            k = self.fam_kind[fam]
            key = self.nat(t[2], a)
            if k[0] == "kv":
                return f"kv_get({base}, {key})", "n"
            if k[0] == "ks":
                return f"ks_get_{k[1]}({base}, {key})", "r:" + k[1]
            raise BendDebt(f"a map access into family {fam}")
        if h == "caller":
            return self.env_key("caller"), "n"
        if h == "this":
            return self.env_key("this"), "n"
        if h == "env":
            return self.env_key(t[1]), "n"
        if h == "blobhash":
            return f"nth_d(Nat, ge_blobs(en), {self.nat(t[1], a)}, 0n)", "n"
        if h == "call":
            fn = t[1]
            if fn.startswith("address."):
                raise BendDebt("a low-level call")
            return f"kl_get({self.call_table(fn)}, {self.call_key(t[2:], a)})", "c"
        if h == "callok":
            fn = t[1]
            if fn.startswith("address."):
                raise BendDebt("a low-level call")
            return f"nth_d(Nat, kl_get({self.call_table(fn)}, {self.call_key(t[3:], a)}), 0n, 0n)", "n"
        if h == "at":
            c, k = self.bx(t[2], a)
            if k != "c":
                raise BendDebt("a component of a value that is not a call result")
            idx = self.lit(t[1] + 1) if isinstance(t[1], int) else f"Nat.add({self.nat(t[1], a)}, 1n)"
            return f"nth_d(Nat, {c}, {idx}, 0n)", "n"
        if h in ("keccak256", "sha256"):
            tab = "ge_kec(en)" if h == "keccak256" else "ge_sha(en)"
            return f"kb_get({tab}, {self.byts(t[1], a)})", "n"
        if h == "len":
            c, k = self.bx(t[1], a)
            if k == "b":
                return f"List.length(&2, Nat, {c})", "n"
            if k.startswith("l:"):
                return f"List.length(&2, {k[2:]}, {c})", "n"
            raise BendDebt(f"the length of a {k} value")
        if h == "byte":
            return f"nth_d(Nat, {self.byts(t[1], a)}, {self.nat(t[2], a)}, 0n)", "n"
        if h == "word":
            return f"w_word({self.byts(t[1], a)}, {self.nat(t[2], a)})", "n"
        if h == "index":
            c, k = self.bx(t[1], a)
            if k in ("b", "l:Nat"):
                return f"nth_d(Nat, {c}, {self.nat(t[2], a)}, 0n)", "n"
            raise BendDebt(f"an index into a {k} value")
        if h == "str":
            bs = bytes.fromhex(t[1] or "")
            return ("[" + ", ".join(f"{b}n" for b in bs) + "]") if bs else "Nil{}", "b"
        if h == "mem":
            return self.mem(t, a), "b"
        if h == "slice":
            return f"l_slice({self.byts(t[1], a)}, {self.nat(t[2], a)}, {self.nat(t[3], a)})", "b"
        if h == "mload":
            return f"w_word({self.byts(t[1], a)}, {self.nat(t[2], a)})", "n"
        if h == "abi.encode":
            parts = []
            for x in t[1:]:
                c, k = self.bx(x, a)
                if k != "n":
                    raise BendDebt("abi.encode of a dynamic value")
                parts.append(f"w_bytes32({c})")
            out = "Nil{}"
            for p in reversed(parts):
                out = f"List.append(&2, Nat, {p}, {out})"
            return out, "b"
        if h == "sload":
            return f"kv_get(gs__slots(st), {self.nat(t[1], a)})", "n"
        if h in ("unknown", "phi", "carried", "exit", "count", "sfits"):
            return self.unknown(_key(t), f"an environment value ({h})")
        raise BendDebt(f"term {h}")

    def store(self, t, a: str) -> tuple[str, str]:
        base, kb = self.bx(t[1], a)
        path = t[2]
        if not kb.startswith("f:"):
            raise BendDebt("a store into a value that is not a family")
        fam = kb[2:]
        k = self.fam_kind[fam]
        if k[0] == "kv" and len(path) == 1 and path[0][0] == "map":
            return f"kv_set({base}, {self.nat(path[0][1], a)}, {self.nat(t[3], a)})", kb
        if k[0] == "ks" and len(path) == 2 and path[0][0] == "map" and path[1][0] == "member":
            fld = bname(path[1][1])
            return f"ks_setm_{k[1]}_{fld}({base}, {self.nat(path[0][1], a)}, {self.nat(t[3], a)})", kb
        if k[0] == "ks" and len(path) == 1 and path[0][0] == "map":
            return f"ks_set_{k[1]}({base}, {self.nat(path[0][1], a)}, {self.record(k[1], t[3], a)})", kb
        raise BendDebt(f"a store into family {fam} at {len(path)} accessors")

    def record(self, rec: str, v, a: str) -> str:
        """A struct value (["struct", name, [[member, v]..]], or 0 for a deleted one) as a record."""
        fs = self.records[rec]
        if v == 0:
            return f"{rec}{{" + ", ".join("0n" for _ in fs) + "}"
        if isinstance(v, list) and v and v[0] == "struct":
            got = {bname(mn): mv for mn, mv in v[2]}
            return f"{rec}{{" + ", ".join(self.nat(got[f], a) if f in got else "0n" for f, _ in fs) + "}"
        raise BendDebt("a struct value that is not a struct literal")

    def mem(self, t, a: str) -> str:
        size = 0
        for w in t[1:]:
            if isinstance(w, list) and w and w[0] in ("mstore", "mstore8", "calldatacopy"):
                off = w[1]
                if not isinstance(off, int):
                    raise BendDebt("a memory write at a symbolic offset")
                n = 32 if w[0] == "mstore" else 1 if w[0] == "mstore8" else w[4]
                if not isinstance(n, int):
                    raise BendDebt("a memory copy of a symbolic length")
                size = max(size, off + n)
            elif isinstance(w, list) and w and w[0] == "mloop":
                raise BendDebt("a memory loop")
        if size > MAX_REGION:
            raise BendDebt("a memory region larger than the generator expands")
        out = f"List.replicate(Nat, {size}n, {SENTINEL}n)"
        for w in t[1:]:
            k = w[0]
            if k == "mstore":
                out = f"m_put({out}, {w[1]}n, w_bytes32({self.nat(w[2], a)}))"
            elif k == "mstore8":
                out = f"m_put({out}, {w[1]}n, [Nat.mod({self.nat(w[2], a)}, 256n)])"
            elif k == "calldatacopy":
                out = (f"m_put({out}, {w[1]}n, l_slice({self.byts(w[2], a)}, {self.nat(w[3], a)}, "
                       f"{self.nat(w[4], a)}))")
            elif k in ("loop", "unknown"):
                out = f"List.replicate(Nat, {size}n, {SENTINEL}n)"
            else:
                raise BendDebt(f"memory write {k}")
        return out

    # ---------------------------------------------------------------- the text of one action
    def chain(self, a: str) -> list[str]:
        prog = self.m.program(a)
        order = {id(c): i for i, c in enumerate(prog.checks())}
        rec = "A_" + bname(a)
        sig = f"+st: HStore, +ar: {rec}, +en: HEnv"
        x = bname(a)
        points = []     # (comment, Bend condition: 1 holds / 0 fails | None, index-or-value)
        for s in prog.steps:
            if isinstance(s, Check):
                points.append((f"check {order[id(s)]}: {s.id} ({s.kind}: {s.reason if s.code is None else s.code})",
                               self.nat(s.expr, a), order[id(s)]))
            elif isinstance(s, Loop) and any(isinstance(c, Check) for c in _walk(s.body)):
                code, _ = self.unknown(_key(["loop", a, s.src]), "the outcome of a loop's checks (0 or k + 1)")
                points.append((f"loop {s.src}: its checks, from the environment", code, None))
        lines: list[str] = []
        n = len(points)
        for i in reversed(range(n)):
            cm, cond, idx = points[i]
            nxt = f"k_{x}_{i + 1}({points[i + 1][1]}, st, ar, en)" if i + 1 < n else "0n"
            if idx is not None:
                lines += [f"# {comment(cm)}", f"def k_{x}_{i}(c: Nat, {sig}) -> Nat:", "  match c:", "    case 0n:",
                          f"      {idx + 1}n", "    case 1n+p:", f"      {nxt}", ""]
            else:
                lines += [f"# {comment(cm)}", f"def k_{x}_{i}(c: Nat, {sig}) -> Nat:", "  match c:", "    case 0n:",
                          f"      {nxt}", "    case 1n+p:", "      Nat.add(p, 1n)", ""]
        body = f"k_{x}_0({points[0][1]}, st, ar, en)" if n else "0n"
        lines += [f"def chk_{x}({sig}) -> Nat:", f"  {body}", ""]
        return lines

    def post(self, a: str) -> list[str]:
        prog = self.m.program(a)
        rec = "A_" + bname(a)
        x = bname(a)
        sig = f"+st: HStore, +ar: {rec}, +en: HEnv"
        why = None
        nested = [s for s in prog.steps if isinstance(s, Loop) and any(isinstance(w, Write) for w in _walk(s.body))]
        if nested:
            why = f"writes inside loop records ({', '.join(str(s.src) for s in nested)})"
        lets, cur = [], "st"
        if why is None:
            try:
                for i, w in enumerate([s for s in prog.steps if isinstance(s, Write)]):
                    lets.append(f"  +s{i + 1} = {self.write(w, cur, a)}")
                    cur = f"s{i + 1}"
            except BendDebt as e:
                why = str(e)
        if why is not None:
            self.no_post[a] = why
            return [f"# post-state of {comment(a)} not compiled: {comment(why)}",
                    f"def step_{x}({sig}) -> HStore:", "  st", ""]
        return [f"def post_{x}({sig}) -> HStore:"] + lets + [f"  {cur}", "",
                f"def step_{x}({sig}) -> HStore:",
                f"  ite(HStore, Nat.is_eq(chk_{x}(st, ar, en), 0n), post_{x}(st, ar, en), st)", ""]

    def logs(self, a: str) -> list[str]:
        """logs_<a>(st, ar, en) -> List<&2, HLog>: the action's emits in program order, each when its condition holds:
        topics (topic0, then the document's topic terms of the indexed arguments) and data (the ABI encoding of the
        other arguments, static types only); not compiled when an emit sits in a loop record or is not translatable."""
        from .extracted_eval import _is_dynamic, signature_types
        prog = self.m.program(a)
        rec = "A_" + bname(a)
        x = bname(a)
        sig = f"+st: HStore, +ar: {rec}, +en: HEnv"
        why = None
        nested = [s for s in prog.steps if isinstance(s, Loop) and any(isinstance(w, Event) for w in _walk(s.body))]
        if nested:
            why = f"emits inside loop records ({', '.join(str(s.src) for s in nested)})"
        items = []
        if why is None:
            try:
                for ev in [s for s in prog.steps if isinstance(s, Event)]:
                    ps = signature_types(ev.signature) if ev.signature else None
                    if ps is None or len(ps) != len(ev.args) or len(ev.indexed) != len(ps):
                        raise BendDebt(f"emit {ev.event}: no signature for its arguments")
                    topics = ([] if ev.anonymous else [self.lit(int(str(ev.topic0), 16))]) + \
                        [self.nat(t, a) for t in ev.topics]
                    data = "Nil{}"
                    for arg, p_, ix in reversed(list(zip(ev.args, ps, ev.indexed))):
                        if ix:
                            continue
                        if _is_dynamic(p_) or p_.get("type", "").startswith("tuple"):
                            raise BendDebt(f"emit {ev.event}: a dynamic argument ({p_.get('type')})")
                        data = f"List.append(&2, Nat, w_bytes32({self.nat(arg, a)}), {data})"
                    tl = ("[" + ", ".join(topics) + "]") if topics else "Nil{}"
                    items.append((ev.cond, f"HLog{{{tl}, {data}}}"))
            except BendDebt as e:
                why = str(e)
        if why is not None:
            self.no_logs[a] = why
            return [f"# logs of {comment(a)} not compiled: {comment(why)}"]
        out = "Nil{}"
        for cond, item in reversed(items):
            out = f"Con{{{item}, {out}}}" if cond in (1, True) else \
                f"ite(List<&2, HLog>, w_truth({self.nat(cond, a)}), Con{{{item}, {out}}}, {out})"
        return [f"def logs_{x}({sig}) -> List<&2, HLog>:", f"  {out}", ""]

    def write(self, w: Write, cur: str, a: str) -> str:
        fam = w.family
        k = self.fam_kind.get(fam, ("raw",))
        if k[0] == "raw":
            raise BendDebt(f"a write of family {fam}, which is not compiled")
        f = bname(fam)
        path = w.path
        if k[0] == "n" and not path:
            new = f"ss_{f}({cur}, {self.nat(w.value, a)})"
        elif k[0] == "kv" and len(path) == 1 and path[0][0] == "map":
            new = f"ss_{f}({cur}, kv_set(gs_{f}({cur}), {self.nat(path[0][1], a)}, {self.nat(w.value, a)}))"
        elif k[0] == "ks" and len(path) == 1 and path[0][0] == "map":
            new = (f"ss_{f}({cur}, ks_set_{k[1]}(gs_{f}({cur}), {self.nat(path[0][1], a)}, "
                   f"{self.record(k[1], w.value, a)}))")
        elif k[0] == "ks" and len(path) == 2 and path[0][0] == "map" and path[1][0] == "member":
            new = (f"ss_{f}({cur}, ks_setm_{k[1]}_{bname(path[1][1])}(gs_{f}({cur}), {self.nat(path[0][1], a)}, "
                   f"{self.nat(w.value, a)}))")
        else:
            raise BendDebt(f"a write of family {fam} at path {_key(path)[:80]}")
        if w.cond in (1, True):
            return new
        return f"ite(HStore, w_truth({self.nat(w.cond, a)}), {new}, {cur})"

    @staticmethod
    def getters(prefix: str, rec: str, fs: list) -> list[str]:
        out = []
        for f, ty in fs:
            pat = ", ".join(("+" + x) if x == f else x for x, _ in fs)
            out += [f"def {prefix}{f}(e: {rec}) -> {ty}:", "  match e:", f"    case {rec}{{{pat}}}:", f"      {f}", ""]
        return out

    @staticmethod
    def setters(prefix: str, rec: str, fs: list) -> list[str]:
        out = []
        for f, ty in fs:
            pat = ", ".join(("_" if x == f else "+" + x) for x, _ in fs)
            rebuilt = ", ".join(("v" if x == f else x) for x, _ in fs)
            out += [f"def {prefix}{f}(e: {rec}, +v: {ty}) -> {rec}:", "  match e:", f"    case {rec}{{{pat}}}:",
                    f"      {rec}{{{rebuilt}}}", ""]
        return out

    def generate(self) -> str:
        m = self.m
        self.families()
        for a in sorted(m.actions):
            for p in m.params(a) or []:
                self.arg_type(p)
        chains = [self.chain(a) for a in sorted(m.actions)]
        posts = [self.post(a) for a in sorted(m.actions)]
        logs = [self.logs(a) for a in sorted(m.actions)]
        head = [f"# GENERATED by holon.machine from {comment(m.path.as_posix() if m.path else 'a document')}; do not edit "
                "(fix the generator instead).",
                f"# facts_sha256: {m.sha256}",
                f"# machine_version: {MACHINE_VERSION}",
                f"# contract: {comment(m.contract)}; families: {len(m.families)} "
                f"({sum(1 for f in m.families.values() if not f.declared)} inherited); actions: {len(m.actions)}; "
                f"checks: {len(m.all_reaches())}",
                "# chk_<action>(st, ar, en): 0 when every check holds, k + 1 when check k is the first that fails;",
                "# step_<action>(st, ar, en): the post-state when chk is 0, else st;",
                "# logs_<action>(st, ar, en): the logs the action emits when chk is 0 (topics and data, in order).",
                f"# terms left to the environment (env table unk, by id): {len(self.debt)}"]
        for d in self.debt:
            head.append(f"#   unk {d['id']}: {comment(d['why'])}: {comment(d['term'])[:200]}")
        unc = sorted(f for f, k in self.fam_kind.items() if k[0] == "raw")
        if unc:
            head.append("# families not compiled (their type is not an elementary value or a mapping of one or of a "
                        "struct of them): " + ", ".join(comment(f) for f in unc))
        for a, why in sorted(self.no_post.items()):
            head.append(f"# post-state of {comment(a)} not compiled: {comment(why)}")
        for a, why in sorted(self.no_logs.items()):
            head.append(f"# logs of {comment(a)} not compiled: {comment(why)}")
        head += ["import Base", ""]
        body = [BEND_PRELUDE]
        for name in sorted(self.records):
            fs = self.records[name]
            body += [f"type {name} is Data:", f"  {name}{{" + ", ".join(f"{f}: {ty}" for f, ty in fs) + "}", ""]
        for name in sorted(self.records):
            body += self.getters(f"g_{name}_", name, self.records[name])
        for rec in sorted({k[1] for k in self.fam_kind.values() if k[0] == "ks"}):
            fs = self.records[rec]
            zero = f"{rec}{{" + ", ".join("0n" for _ in fs) + "}"
            body += [f"type HKS_{rec} is Data:", f"  HKS_{rec}{{k: Nat, v: {rec}}}", "",
                     f"def ks_get_{rec}(xs: List<&2, HKS_{rec}>, +k: Nat) -> {rec}:", "  match xs:", "    case Nil{}:",
                     f"      {zero}", "    case Con{+h, +t}:", "      match h:", f"        case HKS_{rec}{{+hk, +hv}}:",
                     f"          ite({rec}, Nat.is_eq(hk, k), hv, ks_get_{rec}(t, k))", "",
                     f"def ks_set_{rec}(xs: List<&2, HKS_{rec}>, +k: Nat, +v: {rec}) -> List<&2, HKS_{rec}>:",
                     "  match xs:", "    case Nil{}:", f"      [HKS_{rec}{{k, v}}]",
                     "    case Con{+h, +t}:", "      match h:", f"        case HKS_{rec}{{+hk, +hv}}:",
                     f"          ite(List<&2, HKS_{rec}>, Nat.is_eq(hk, k), Con{{HKS_{rec}{{k, v}}, t}}, "
                     f"Con{{HKS_{rec}{{hk, hv}}, ks_set_{rec}(t, k, v)}})", ""]
            for f, _ty in fs:
                upd = f"{rec}{{" + ", ".join("v" if x == f else f"g_{rec}_{x}(r)" for x, _ in fs) + "}"
                body += [f"def ks_upd_{rec}_{f}(+r: {rec}, +v: Nat) -> {rec}:", f"  {upd}", "",
                         f"def ks_setm_{rec}_{f}(+xs: List<&2, HKS_{rec}>, +k: Nat, +v: Nat) -> List<&2, HKS_{rec}>:",
                         f"  ks_set_{rec}(xs, k, ks_upd_{rec}_{f}(ks_get_{rec}(xs, k), v))", ""]
        sf = [(f, ty) for f, ty, _ in self.store_fields]
        body += ["type HStore is Data:", "  HStore{" + ", ".join(f"{f}: {ty}" for f, ty in sf) + "}", ""]
        for fld, _ty, fam in self.store_fields:
            if fam is not None:
                body.append(f"# {fld}: storage {comment(fam)}")
        body += [x.replace("def gs_f_", "def gs_", 1) for x in self.getters("gs_", "HStore", sf)]
        body += [x.replace("def ss_f_", "def ss_", 1) for x in self.setters("ss_", "HStore", sf)]
        ef = [("e_" + bname(k), "Nat") for k in self.env_keys] + [("blobs", "List<&2, Nat>")] + \
             [(f"c{i}", "List<&2, HKL>") for i in range(len(self.calls))] + \
             [("kec", "List<&2, HKB>"), ("sha", "List<&2, HKB>"), ("unk", "List<&2, HKV>")]
        body += ["type HEnv is Data:", "  HEnv{" + ", ".join(f"{f}: {ty}" for f, ty in ef) + "}", ""]
        for i, fn in enumerate(self.calls):
            body.append(f"# env c{i}: the answers of {comment(fn)} (argument list -> [ok, results..])")
        body += self.getters("ge_", "HEnv", ef)
        for a in sorted(m.actions):
            rec = "A_" + bname(a)
            fs = [(bname(p["name"]), self.arg_type(p)) for p in m.params(a) or []]
            body += [f"type {rec} is Data:", f"  {rec}{{" + ", ".join(f"{f}: {ty}" for f, ty in fs) + "}", ""]
            body += self.getters(f"ga_{bname(a)}_", rec, fs)
        for c in chains:
            body += c
        for p in posts:
            body += p
        for lg in logs:
            body += lg
        text = "\n".join(head + body).rstrip("\n") + "\n"
        names = re.findall(r"(?m)^(?:type|def)\s+([\w.]+)", text)
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise ModelError(f"the generated model would define {dup} twice")
        from .bend import escape_hatches
        bad = escape_hatches(text)
        if bad:
            raise ModelError(f"the generated model would hold an escape hatch: {bad}")
        return text


def _pow2(x) -> int:
    """k when x is the constant 2^k with k >= 32 (a literal the compiled model could not build), else 0."""
    if isinstance(x, int) and not isinstance(x, bool) and x >= (1 << 32) and x & (x - 1) == 0:
        return x.bit_length() - 1
    return 0


def _walk(steps):
    for s in steps:
        yield s
        if isinstance(s, Loop):
            yield from _walk(s.body)


def _key(t) -> str:
    return json.dumps(t, sort_keys=True, separators=(",", ":"))


def bend_model(m: ExtractedModel) -> tuple[str, list]:
    """(model.bend text, the terms it leaves to the environment)."""
    g = BendModel(m)
    return g.generate(), g.debt
