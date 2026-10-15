"""Target-agnostic Bend 2 -> Lean 4.34.0 translator for M3+ Lean verification (I43).

Translates self-contained Bend 2 modules (types, functions, laws, proofs) into
standalone Lean 4.34.0 files with zero `import` statements and zero axioms outside
`{"Quot.sound", "propext"}`.
"""
from __future__ import annotations

import re
from pathlib import Path

PREAMBLE = """set_option linter.unusedVariables false
set_option linter.defProp false
set_option maxRecDepth 100000
set_option maxHeartbeats 1000000

inductive BId (A : Sort _) (a : A) : A → Prop where
  | refl : BId A a a

inductive BSig (A : Sort _) (B : A → Prop) : Prop where
  | mk (fst : A) (snd : B fst) : BSig A B

def b_rw {A : Type _} {a b : A} (P : A → Sort _) (h : BId A a b) (x : P a) : P b :=
  match h with
  | BId.refl => x

theorem b_sym {A : Type _} {a b : A} (h : BId A a b) : BId A b a :=
  match h with
  | BId.refl => BId.refl

def b_u32_to_nat (x : UInt32) : Nat := x.toNat
def b_nat_to_u32 (n : Nat) : UInt32 := UInt32.ofNat n

def b_list_len {A : Type} : List A → Nat
  | [] => 0
  | _ :: xs => Nat.succ (b_list_len xs)

def b_list_append {A : Type} : List A → List A → List A
  | [], ys => ys
  | x :: xs, ys => x :: b_list_append xs ys

def b_list_take {A : Type} : List A → Nat → List A
  | _, 0 => []
  | [], _ => []
  | x :: xs, Nat.succ n => x :: b_list_take xs n

def b_list_drop {A : Type} : List A → Nat → List A
  | xs, 0 => xs
  | [], _ => []
  | _ :: xs, Nat.succ n => b_list_drop xs n

def Nat_add : Nat → Nat → Nat
  | 0, b => b
  | Nat.succ a, b => Nat.succ (Nat_add a b)

def Nat_sub : Nat → Nat → Nat
  | 0, _ => 0
  | a, 0 => a
  | Nat.succ a, Nat.succ b => Nat_sub a b

def Nat_is_eq : Nat → Nat → Bool
  | 0, 0 => true
  | Nat.succ a, Nat.succ b => Nat_is_eq a b
  | _, _ => false

def Nat_is_le : Nat → Nat → Bool
  | 0, _ => true
  | Nat.succ _, 0 => false
  | Nat.succ a, Nat.succ b => Nat_is_le a b

def Nat_is_lt (a b : Nat) : Bool :=
  Nat_is_le (Nat.succ a) b

def Nat_is_ge (a b : Nat) : Bool :=
  Nat_is_le b a

def Nat_is_gt (a b : Nat) : Bool :=
  Nat_is_lt b a

def Nat_mod (a b : Nat) : Nat := a % b
def Nat_div (a b : Nat) : Nat := a / b

def Bool_and : Bool → Bool → Bool
  | true, b => b
  | false, _ => false

def Bool_or : Bool → Bool → Bool
  | true, _ => true
  | false, b => b

def Bool_not : Bool → Bool
  | true => false
  | false => true

def Bool_eq : Bool → Bool → Bool
  | true, true => true
  | false, false => true
  | _, _ => false

def U32_is_eq (a b : UInt32) : Bool := Nat_is_eq a.toNat b.toNat
def U32_is_ne (a b : UInt32) : Bool := Bool_not (U32_is_eq a b)
def U32_is_le (a b : UInt32) : Bool := Nat_is_le a.toNat b.toNat
def U32_is_lt (a b : UInt32) : Bool := Nat_is_lt a.toNat b.toNat
def U32_is_ge (a b : UInt32) : Bool := Nat_is_ge a.toNat b.toNat
def U32_is_gt (a b : UInt32) : Bool := Nat_is_gt a.toNat b.toNat

inductive BPair (A : Type) (B : Type) : Type where
  | mk : A → B → BPair A B

inductive BMaybe (A : Type) : Type where
  | none : BMaybe A
  | some : A → BMaybe A
"""

LEAN_KW = {
    "end", "in", "fun", "let", "match", "with", "if", "then", "else", "do",
    "by", "have", "show", "from", "where", "structure", "inductive", "theorem",
    "def", "abbrev", "axiom", "constant", "opaque", "partial", "unsafe", "import", "open",
    "variable", "universe", "namespace", "section", "mutual", "class", "instance",
    "deriving", "macro", "syntax", "elab", "notation", "infix", "infixl", "infixr",
    "prefix", "postfix", "forall", "exists", "true", "false", "at", "mod", "div",
    "ite", "extern", "admit", "sorry",
}

_ACTIVE_STRUCT_NAMES: set[str] = set()


def safe_ident(name: str) -> str:
    name = name.lstrip("+-")
    if not name or name == "_":
        return "_"
    if "." in name:
        parts = name.split(".")
        if parts[0] in ("M", "C", "Laws"):
            name = "_".join(parts[1:]) if len(parts) > 1 else parts[0]
        else:
            name = "_".join(parts)
    if name in LEAN_KW:
        return f"v_{name}"
    return name


def split_top(s: str, sep: str = ",") -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in "([{":
            depth += 1
            cur.append(c)
            i += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
            cur.append(c)
            i += 1
        elif c == "<" and (i == 0 or s[i - 1] not in "=-"):
            j = i + 1
            d2 = 1
            ok = False
            while j < n and d2 > 0:
                if s[j] == "<":
                    d2 += 1
                elif s[j] == ">":
                    d2 -= 1
                    if d2 == 0:
                        ok = True
                        break
                elif s[j] in ";\n":
                    break
                j += 1
            if ok:
                cur.append(s[i : j + 1])
                i = j + 1
                continue
            cur.append(c)
            i += 1
        elif depth == 0 and s.startswith(sep, i):
            if sep == "->" and i > 0 and s[i - 1] == "=":
                cur.append(c)
                i += 1
                continue
            out.append("".join(cur).strip())
            cur = []
            i += len(sep)
        else:
            cur.append(c)
            i += 1
    if cur or out:
        out.append("".join(cur).strip())
    return out


def strip_outer_parens(s: str) -> str:
    s = s.strip()
    while s.startswith("(") and s.endswith(")"):
        d = 0
        ok = True
        for i, c in enumerate(s):
            if c in "([{":
                d += 1
            elif c in ")]}":
                d -= 1
            if d == 0 and i < len(s) - 1:
                ok = False
                break
        if ok:
            s = s[1:-1].strip()
        else:
            break
    return s


def translate_type(t: str) -> str:
    t = strip_outer_parens(t.strip())
    if not t:
        return "Unit"
    if t in ("Type", "Data"):
        return "Type"
    if t == "Empty":
        return "False"
    if t == "Unit":
        return "True"
    if t == "Bool":
        return "Bool"
    if t == "Nat":
        return "Nat"
    if t == "U32":
        return "UInt32"

    if t.startswith("@"):
        depth = 0
        arrow_idx = -1
        i = 0
        while i < len(t) - 1:
            if t[i] in "([{":
                depth += 1
            elif t[i] in ")]}":
                depth = max(0, depth - 1)
            elif depth == 0 and t[i : i + 2] == "->":
                arrow_idx = i
                break
            i += 1
        if arrow_idx >= 0:
            binder = t[1:arrow_idx].strip()
            rest = t[arrow_idx + 2 :].strip()
            if ":" in binder:
                bname, bty = binder.split(":", 1)
                bname = safe_ident(bname.strip())
                return f"(∀ ({bname} : {translate_type(bty)}), {translate_type(rest)})"
            return f"({translate_type(binder)} → {translate_type(rest)})"

    parts = split_top(t, "->")
    if len(parts) > 1:
        return "(" + " → ".join(translate_type(p) for p in parts) + ")"

    if t.startswith("∀"):
        return t

    if t.startswith("[") and t.endswith("]"):
        inner = t[1:-1].strip()
        if " & " in inner:
            lhs, rhs = split_top(inner, "&")
            if ":" in lhs:
                vname, vty = lhs.split(":", 1)
                vname = safe_ident(vname.strip())
                return f"(BSig {translate_type(vty)} (fun {vname} => {translate_type(rhs)}))"

    if t.startswith("{") and t.endswith("}"):
        inner = t[1:-1].strip()
        colon_idx = -1
        d = 0
        for i in range(len(inner) - 1, -1, -1):
            if inner[i] in ")]}":
                d += 1
            elif inner[i] in "([{":
                d -= 1
            elif d == 0 and inner[i] == ":":
                colon_idx = i
                break
        if colon_idx >= 0:
            eq_part = inner[:colon_idx].strip()
            ty_part = inner[colon_idx + 1 :].strip()
            if "!=" in eq_part:
                lhs, rhs = split_top(eq_part, "!=")
                return (
                    f"({translate_type(f'{{{lhs} == {rhs} : {ty_part}}}')} → False)"
                )
            lhs, rhs = split_top(eq_part, "==")
            return (
                f"(BId {translate_type(ty_part)}"
                f" ({translate_expr(lhs)}) ({translate_expr(rhs)}))"
            )

    m = re.match(r"^([A-Za-z0-9_.]+)<(.*)>$", t, re.S)
    if m:
        base = m.group(1)
        args = [
            a.strip()
            for a in split_top(m.group(2), ",")
            if not a.strip().startswith("&")
        ]
        if base == "List":
            return f"(List {translate_type(args[0])})"
        if base == "Maybe":
            return f"(BMaybe {translate_type(args[0])})"
        if base == "Pair":
            return f"(BPair {translate_type(args[0])} {translate_type(args[1])})"
        return (
            "("
            + safe_ident(base)
            + "".join(" " + translate_arg(a) for a in args)
            + ")"
        )

    if t.endswith(")"):
        return translate_expr(t)

    return safe_ident(t)


def translate_expr(e: str) -> str:
    e = strip_outer_parens(e.strip())
    if not e:
        return "()"
    if e == "{==}":
        return "BId.refl"
    if e.startswith("{") and e.endswith("}"):
        inner = e[1:-1].strip()
        colon_idx = -1
        d = 0
        for i in range(len(inner) - 1, -1, -1):
            if inner[i] in ")]}":
                d += 1
            elif inner[i] in "([{":
                d -= 1
            elif d == 0 and inner[i] == ":":
                colon_idx = i
                break
        if colon_idx >= 0:
            lhs = inner[:colon_idx].strip()
            rhs = inner[colon_idx + 1 :].strip()
            if len(split_top(lhs, "==")) == 1 and len(split_top(lhs, "!=")) == 1:
                return f"({translate_expr(lhs)} : {translate_type(rhs)})"
    if e in ("()", "Unit"):
        return "True" if e == "Unit" else "True.intro"
    if e == "Empty":
        return "False"
    if e == "[]":
        return "[]"
    if e == "True":
        return "true"
    if e == "False":
        return "false"
    if re.match(r"^\d+n$", e):
        return e[:-1]
    if re.match(r"^\d+$", e):
        return f"({e} : UInt32)"
    if re.match(r"^0x[0-9a-fA-F]+$", e):
        return f"({int(e, 16)} : UInt32)"
    m1 = re.match(r"^(\d+)n\s*\+\s*(.+)$", e)
    if m1 and len(split_top(e, "==")) == 1 and len(split_top(e, "!=")) == 1:
        k = int(m1.group(1))
        res = translate_expr(m1.group(2))
        for _ in range(k):
            res = f"(Nat.succ {res})"
        return res

    if e.startswith("%"):
        semi_idx = -1
        d = 0
        for i, c in enumerate(e):
            if c in "([{":
                d += 1
            elif c in ")]}":
                d -= 1
            elif d == 0 and c == ";":
                semi_idx = i
                break
        if semi_idx >= 0:
            header = e[1:semi_idx].strip()
            rest = e[semi_idx + 1 :].strip()
            colon_idx = -1
            d = 0
            for i, c in enumerate(header):
                if c in "([{":
                    d += 1
                elif c in ")]}":
                    d -= 1
                elif d == 0 and c == ":":
                    colon_idx = i
                    break
            ev = header[:colon_idx].strip()
            motive = header[colon_idx + 1 :].strip()
            motive_with_var = re.sub(r"\b_\b", "_rw", motive)
            motive_ty = translate_type(motive_with_var)
            return (
                f"(b_rw (fun _rw => {motive_ty})"
                f" ({translate_expr(ev)}) ({translate_expr(rest)}))"
            )

    if (
        not e.startswith(("lambda ", "λ", "use "))
        and len(split_top(e, ";")) == 1
        and len(split_top(e, "=>")) == 1
    ):
        colon_parts = split_top(e, ":")
        if len(colon_parts) == 2 and len(split_top(colon_parts[0], "==")) == 1:
            return f"({translate_expr(colon_parts[0])} : {translate_type(colon_parts[1])})"

    semi_parts = split_top(e, ";")
    if len(semi_parts) > 1 and (
        semi_parts[0].strip().startswith("use ")
        or re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*=", semi_parts[0].strip())
    ):
        first = semi_parts[0].strip()
        rest = "; ".join(semi_parts[1:]).strip()
        if first.startswith("use "):
            first = first[4:].strip()
        vname, val = first.split("=", 1)
        return (
            f"(let {safe_ident(vname.strip())} := {translate_expr(val)};"
            f" {translate_expr(rest)})"
        )

    d = 0
    for i in range(len(e) - 1):
        if e[i] in "([{":
            d += 1
        elif e[i] in ")]}":
            d -= 1
        elif d == 0 and e[i : i + 2] == "=>":
            params_s = e[:i].strip()
            body_s = e[i + 2 :].strip()
            params = [
                safe_ident(p.strip()) for p in params_s.split(",") if p.strip()
            ]
            return f"(fun {' '.join(params)} => {translate_expr(body_s)})"

    if e.startswith("lambda "):
        dot_idx = e.find(".")
        params_s = e[7:dot_idx].strip()
        body_s = e[dot_idx + 1 :].strip()
        params = [
            safe_ident(p.strip())
            for p in re.split(r"[,\s]+", params_s)
            if p.strip()
        ]
        return f"(fun {' '.join(params)} => {translate_expr(body_s)})"

    if e.startswith("λ"):
        body_idx = -1
        for sep in (".", "=>"):
            idx = e.find(sep)
            if idx >= 0 and (body_idx < 0 or idx < body_idx):
                body_idx = idx
                sep_len = len(sep)
        if body_idx >= 0:
            params_s = e[1:body_idx].strip()
            body_s = e[body_idx + sep_len :].strip()
            params = [
                safe_ident(p.strip())
                for p in re.split(r"[,\s]+", params_s)
                if p.strip()
            ]
            return f"(fun {' '.join(params)} => {translate_expr(body_s)})"

    if e.startswith("[") and e.endswith("]"):
        inner = e[1:-1].strip()
        if not inner:
            return "[]"
        parts = [p.strip() for p in split_top(inner, ",") if p.strip()]
        if (
            len(parts) == 2
            and not (
                re.match(r"^\d+n?$", parts[0]) and re.match(r"^\d+n?$", parts[1])
            )
            and not (
                parts[0].endswith("}")
                and parts[1].endswith("}")
                and "{" in parts[0]
                and "{" in parts[1]
            )
        ):
            return (
                f"(BSig.mk ({translate_expr(parts[0])})"
                f" ({translate_expr(parts[1])}))"
            )
        return "[" + ", ".join(translate_expr(p) for p in parts) + "]"

    tuple_parts = [p.strip() for p in split_top(e, ",") if p.strip()]
    if len(tuple_parts) == 2:
        return (
            f"(BSig.mk ({translate_expr(tuple_parts[0])})"
            f" ({translate_expr(tuple_parts[1])}))"
        )

    for op, lean_op in (
        ("||", "||"),
        ("&&", "&&"),
        ("==", "=="),
        ("!=", "!="),
        ("<=", "<="),
        ("<", "<"),
        ("+", "+"),
        ("-", "-"),
        ("*", "*"),
        ("%", "%"),
        ("/", "/"),
        ("&", "&&&"),
        ("|", "|||"),
        ("^", "^^^"),
        ("<<", "<<<"),
        (">>", ">>>"),
    ):
        parts = split_top(e, f" {op} ")
        if len(parts) > 1:
            return (
                "("
                + f" {lean_op} ".join(translate_expr(p) for p in parts)
                + ")"
            )

    parts = split_top(e, "<>")
    if len(parts) > 1:
        res = translate_expr(parts[-1])
        for p in reversed(parts[:-1]):
            res = f"({translate_expr(p)} :: {res})"
        return res

    if e.endswith("}"):
        b_idx = -1
        d = 0
        for i, c in enumerate(e):
            if c in "([":
                d += 1
            elif c in ")]":
                d -= 1
            elif d == 0 and c == "{":
                b_idx = i
                break
        if b_idx > 0 and re.match(r"^[A-Za-z0-9_.]+$", e[:b_idx].strip()):
            ctor = e[:b_idx].strip()
            inner = e[b_idx + 1 : -1].strip()
            args = (
                [a.strip() for a in split_top(inner, ",") if a.strip()]
                if inner
                else []
            )
            if ctor in ("1n", "Nat.succ"):
                return (
                    f"(Nat.succ {translate_expr(args[0])})"
                    if args
                    else "Nat.succ"
                )
            if ctor in ("0n", "Nat.zero"):
                return "0"
            if ctor in ("True", "M.True"):
                return "true"
            if ctor in ("False", "M.False"):
                return "false"
            if ctor in ("Unit", "Unit.new", "M.Unit"):
                return "True.intro"
            if ctor in ("List.nil", "Nil", "M.Nil"):
                return "[]"
            if ctor in ("List.cons", "Cons", "Con", "M.Cons", "M.Con"):
                return (
                    f"({translate_expr(args[-2])} :: {translate_expr(args[-1])})"
                )
            if ctor in ("Maybe.none", "M.Maybe.none", "None", "M.None"):
                return "BMaybe.none"
            if ctor in ("Maybe.some", "M.Maybe.some", "Some", "M.Some"):
                return f"(BMaybe.some {translate_expr(args[-1])})"
            if ctor in ("Pair.new", "Pair"):
                return (
                    f"(BPair.mk {translate_expr(args[-2])}"
                    f" {translate_expr(args[-1])})"
                )
            ctor_lean = safe_ident(ctor)
            if ctor_lean in _ACTIVE_STRUCT_NAMES:
                if not args:
                    return f"{ctor_lean}.mk"
                return (
                    f"({ctor_lean}.mk "
                    + " ".join(translate_expr(a) for a in args)
                    + ")"
                )
            if not args:
                return ctor_lean
            return (
                f"({ctor_lean} "
                + " ".join(translate_expr(a) for a in args)
                + ")"
            )

    if e.endswith(")"):
        p_idx = -1
        d = 0
        for i in range(len(e) - 1, -1, -1):
            if e[i] in ")]}":
                d += 1
            elif e[i] in "([{":
                d -= 1
                if d == 0:
                    p_idx = i
                    break
        if p_idx > 0:
            fn_part = e[:p_idx].strip()
            args_part = e[p_idx + 1 : -1].strip()
            if fn_part and not any(
                fn_part.endswith(op)
                for op in ("=>", ":", ";", ",", "+", "-", "*", "==", "&&", "||")
            ):
                fn_lean = translate_fn_name(fn_part)
                raw_args = (
                    [a.strip() for a in split_top(args_part, ",") if a.strip()]
                    if args_part
                    else []
                )
                filtered_args = filter_call_args(fn_part, raw_args)
                if fn_part in ("Nat.add",):
                    return (
                        f"(Nat_add {translate_expr(filtered_args[0])}"
                        f" {translate_expr(filtered_args[1])})"
                    )
                if fn_part in ("Nat.sub",):
                    return (
                        f"(Nat_sub {translate_expr(filtered_args[0])}"
                        f" {translate_expr(filtered_args[1])})"
                    )
                if fn_part in ("Nat.mul",):
                    return (
                        f"({translate_expr(filtered_args[0])} *"
                        f" {translate_expr(filtered_args[1])})"
                    )
                if fn_part in ("U32.to_nat",):
                    return f"(b_u32_to_nat {translate_expr(filtered_args[0])})"
                if fn_part in ("Nat.to_u32",):
                    return f"(b_nat_to_u32 {translate_expr(filtered_args[0])})"
                if fn_part in ("List.length",):
                    return f"(b_list_len {translate_expr(filtered_args[-1])})"
                if fn_part in ("List.append",):
                    return (
                        f"(b_list_append {translate_expr(filtered_args[-2])}"
                        f" {translate_expr(filtered_args[-1])})"
                    )
                if fn_part in ("List.take",):
                    return (
                        f"(b_list_take {translate_expr(filtered_args[-2])}"
                        f" {translate_expr(filtered_args[-1])})"
                    )
                if fn_part in ("List.drop",):
                    return (
                        f"(b_list_drop {translate_expr(filtered_args[-2])}"
                        f" {translate_expr(filtered_args[-1])})"
                    )
                if fn_part in ("Equal.sym",):
                    return f"(b_sym {translate_expr(filtered_args[-1])})"
                if fn_part in ("Empty.absurd",):
                    return f"( False.elim {translate_expr(filtered_args[0])} )"
                if not filtered_args:
                    return fn_lean
                return (
                    f"({fn_lean} "
                    + " ".join(translate_arg(a) for a in filtered_args)
                    + ")"
                )

    return safe_ident(e)


TYPE_ATOMS = {"Nat", "Bool", "U32", "Unit", "Empty", "Type", "Data"}


def is_type_arg(a: str) -> bool:
    a = strip_outer_parens(a.strip())
    if a in TYPE_ATOMS:
        return True
    if re.match(r"^(List|Maybe|Pair)<.*>$", a):
        return True
    if "->" in a and "=>" not in a:
        return True
    if a.startswith("{") and ":" in a and "==" in a:
        return True
    if a.startswith("[") and "&" in a and ":" in a:
        return True
    return False


def translate_arg(a: str) -> str:
    if is_type_arg(a):
        return translate_type(a)
    return translate_expr(a)


def translate_fn_name(fn: str) -> str:
    fn = strip_outer_parens(fn.strip())
    if re.match(r"^[A-Za-z0-9_.]+$", fn):
        if fn == "Nat.is_eq":
            return "Nat_is_eq"
        if fn == "Nat.is_le":
            return "Nat_is_le"
        if fn == "Nat.is_lt":
            return "Nat_is_lt"
        if fn == "Nat.is_ge":
            return "Nat_is_ge"
        if fn == "Nat.is_gt":
            return "Nat_is_gt"
        if fn == "Nat.mod":
            return "Nat_mod"
        if fn == "Nat.div":
            return "Nat_div"
        if fn == "Bool.and":
            return "Bool_and"
        if fn == "Bool.or":
            return "Bool_or"
        if fn == "Bool.not":
            return "Bool_not"
        if fn == "Bool.eq":
            return "Bool_eq"
        if fn == "U32.is_eq":
            return "U32_is_eq"
        if fn == "U32.is_ne":
            return "U32_is_ne"
        if fn == "U32.is_le":
            return "U32_is_le"
        if fn == "U32.is_lt":
            return "U32_is_lt"
        if fn == "U32.is_ge":
            return "U32_is_ge"
        if fn == "U32.is_gt":
            return "U32_is_gt"
        return safe_ident(fn)
    return translate_expr(fn)


def filter_call_args(fn_part: str, args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("&")]


def split_tuple_items(s: str) -> list[str]:
    comma_parts = [p.strip() for p in split_top(s, ",") if p.strip()]
    if len(comma_parts) > 1:
        return comma_parts
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    for c in s.strip():
        if c in "([{":
            depth += 1
            cur.append(c)
        elif c in ")]}":
            depth = max(0, depth - 1)
            cur.append(c)
        elif depth == 0 and c.isspace():
            if cur:
                out.append("".join(cur).strip())
                cur = []
        else:
            cur.append(c)
    if cur:
        out.append("".join(cur).strip())
    return out


def translate_pattern(pat: str, struct_names: set[str]) -> str:
    pat = pat.strip().lstrip("+-")
    if pat in ("0n", "Nat.zero"):
        return "0"
    if re.match(r"^\d+n$", pat):
        return pat[:-1]
    if pat in ("True", "true"):
        return "true"
    if pat in ("False", "false"):
        return "false"
    if pat in ("()", "Unit.new"):
        return "()"
    if pat in ("[]", "List.nil", "Nil"):
        return "[]"
    m1 = re.match(r"^(\d+)n\s*\+\s*([+\-]?[A-Za-z0-9_]+)$", pat)
    if m1:
        k = int(m1.group(1))
        res = safe_ident(m1.group(2))
        for _ in range(k):
            res = f"(Nat.succ {res})"
        return res
    if pat.endswith("}"):
        b_idx = pat.find("{")
        ctor = pat[:b_idx].strip()
        inner = pat[b_idx + 1 : -1].strip()
        fields = (
            [
                translate_pattern(f.strip(), struct_names)
                for f in split_top(inner, ",")
                if f.strip()
            ]
            if inner
            else []
        )
        if ctor in ("0n", "Nat.zero"):
            return "0"
        if ctor in ("1n", "Nat.succ"):
            return f"(Nat.succ {fields[0]})" if fields else "Nat.succ"
        if ctor in ("True", "M.True"):
            return "true"
        if ctor in ("False", "M.False"):
            return "false"
        if ctor in ("Unit", "Unit.new", "M.Unit"):
            return "()"
        if ctor in ("List.nil", "Nil", "M.Nil"):
            return "[]"
        if ctor in ("List.cons", "Cons", "Con", "M.Cons", "M.Con"):
            return f"({fields[-2]} :: {fields[-1]})"
        if ctor in ("Maybe.none", "M.Maybe.none", "None", "M.None"):
            return "BMaybe.none"
        if ctor in ("Maybe.some", "M.Maybe.some", "Some", "M.Some"):
            return f"(BMaybe.some {fields[-1]})"
        if ctor in ("Pair.new", "Pair"):
            return f"(BPair.mk {fields[-2]} {fields[-1]})"
        ctor_lean = safe_ident(ctor)
        if ctor_lean in struct_names:
            if not fields:
                return f"{ctor_lean}.mk"
            return f"({ctor_lean}.mk " + " ".join(fields) + ")"
        if not fields:
            return ctor_lean
        return f"({ctor_lean} " + " ".join(fields) + ")"
    if "<>" in pat:
        parts = split_top(pat, "<>")
        return (
            f"({translate_pattern(parts[0], struct_names)} ::"
            f" {translate_pattern(parts[1], struct_names)})"
        )
    if pat.startswith("[") and pat.endswith("]"):
        parts = split_top(pat[1:-1], ",")
        if len(parts) == 2:
            return (
                f"(BSig.mk {translate_pattern(parts[0], struct_names)}"
                f" {translate_pattern(parts[1], struct_names)})"
            )
    return safe_ident(pat)


def translate_block(lines: list[tuple[int, str]], struct_names: set[str]) -> str:
    if not lines:
        return "()"
    ind0, first = lines[0]
    first_s = first.strip()

    if (
        first_s.startswith("use ")
        or re.match(r"^[+\-]?[A-Za-z_][A-Za-z0-9_]*\s*=(?!>)", first_s)
    ) and not first_s.startswith("case "):
        stmt = first_s[4:].strip() if first_s.startswith("use ") else first_s
        if stmt.endswith(";"):
            stmt = stmt[:-1].strip()
        vname, val = stmt.split("=", 1)
        rest = translate_block(lines[1:], struct_names)
        return f"(let {safe_ident(vname.strip())} := {translate_expr(val)}; {rest})"

    if first_s.startswith("match ") and first_s.endswith(":"):
        scruts_raw = first_s[6:-1].strip()
        scruts = [translate_expr(s) for s in split_tuple_items(scruts_raw)]
        cases: list[tuple[str, list[tuple[int, str]]]] = []
        i = 1
        while i < len(lines):
            ind, l = lines[i]
            ls = l.strip()
            if ls.startswith("case "):
                colon_idx = -1
                d = 0
                for k, ch in enumerate(ls):
                    if ch in "([{":
                        d += 1
                    elif ch in ")]}":
                        d -= 1
                    elif d == 0 and ch == ":":
                        colon_idx = k
                        break
                pat_raw = ls[5:colon_idx].strip()
                rhs_inline = ls[colon_idx + 1 :].strip()
                i += 1
                sub: list[tuple[int, str]] = []
                if rhs_inline:
                    sub.append((ind + 2, rhs_inline))
                while i < len(lines) and lines[i][0] > ind:
                    sub.append(lines[i])
                    i += 1
                pats = [
                    translate_pattern(p, struct_names)
                    for p in split_tuple_items(pat_raw)
                ]
                for pk_idx in range(min(len(pats), len(scruts))):
                    if (
                        pats[pk_idx] == "_"
                        and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", scruts[pk_idx])
                    ):
                        pats[pk_idx] = scruts[pk_idx]
                cases.append((", ".join(pats), sub))
            else:
                i += 1
        if not cases:
            return f"(False.elim ({scruts[0]}))"
        arms = " | ".join(
            f"{pat} => {translate_block(sub, struct_names)}"
            for pat, sub in cases
        )
        return f"(match {', '.join(scruts)} with | {arms})"

    if len(lines) == 1:
        return translate_expr(first_s)

    if first_s.startswith("%") and ";" not in first_s:
        header = first_s[1:].strip()
        colon_idx = -1
        d = 0
        for i, c in enumerate(header):
            if c in "([{":
                d += 1
            elif c in ")]}":
                d -= 1
            elif d == 0 and c == ":":
                colon_idx = i
                break
        if colon_idx >= 0:
            ev = header[:colon_idx].strip()
            motive = header[colon_idx + 1 :].strip()
            motive_with_var = re.sub(r"\b_\b", "_rw", motive)
            motive_ty = translate_type(motive_with_var)
            rest_lean = translate_block(lines[1:], struct_names)
            return (
                f"(b_rw (fun _rw => {motive_ty})"
                f" ({translate_expr(ev)}) ({rest_lean}))"
            )

    norm_lines: list[str] = []
    for _, l in lines:
        ls = l.strip()
        if ls.lstrip("(").startswith("%") and not ls.endswith(";"):
            ls = ls + ";"
        norm_lines.append(ls)
    joined = " ".join(norm_lines)
    return translate_expr(joined)


def parse_bend_file(text: str) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i]
        s = raw.strip()
        if not s or s.startswith("#") or s.startswith("import "):
            i += 1
            continue
        if s.startswith(("type ", "law ", "def ")):
            kind = s.split()[0]
            block = [raw]
            i += 1
            while i < n:
                r2 = lines[i]
                s2 = r2.strip()
                if not s2 or s2.startswith("#"):
                    i += 1
                    continue
                if len(r2) - len(r2.lstrip()) > 0:
                    block.append(r2)
                    i += 1
                else:
                    break
            full = "\n".join(block)
            if kind == "type":
                m = re.match(r"^type\s+([A-Za-z0-9_]+)", s)
                name = m.group(1) if m else ""
            elif kind == "law":
                m = re.match(r"^law\s+([A-Za-z0-9_.]+)\s*:", s)
                name = safe_ident(m.group(1)) if m else ""
            else:
                m = re.match(r"^def\s+([A-Za-z0-9_.]+)", s)
                name = safe_ident(m.group(1)) if m else ""
            items.append((kind, name, full))
        else:
            i += 1
    return items


def translate_type_decl(raw_text: str, struct_names: set[str]) -> str:
    lines = [
        (len(l) - len(l.lstrip()), l.strip())
        for l in raw_text.splitlines()
        if l.strip()
    ]
    head = lines[0][1]
    m = re.match(
        r"^type\s+([A-Za-z0-9_]+)(?:<(.*)>|\((.*)\))?(?:\s+is\s+\w+)?\s*:",
        head,
    )
    tname = safe_ident(m.group(1))
    raw_params = m.group(2) or m.group(3)
    tparams: list[tuple[str, str]] = []
    if raw_params:
        for p in split_top(raw_params, ","):
            p = p.strip()
            if not p:
                continue
            if ":" in p:
                pn, pt = p.split(":", 1)
                tparams.append(
                    (safe_ident(pn.strip()), translate_type(pt.strip()))
                )
            else:
                tparams.append((safe_ident(p), "Type"))
    has_val_idx = any(pt != "Type" for _, pt in tparams)
    ctors: list[tuple[str, list[tuple[str, str]]]] = []
    for _, l in lines[1:]:
        cm = re.match(r"^(?:case\s+)?([A-Za-z0-9_]+)\{(.*)\}\s*$", l)
        if cm:
            cname = safe_ident(cm.group(1))
            fraw = cm.group(2).strip()
            fields: list[tuple[str, str]] = []
            if fraw:
                for f in split_top(fraw, ","):
                    fn, ft = f.split(":", 1)
                    fields.append(
                        (safe_ident(fn.strip()), translate_type(ft.strip()))
                    )
            ctors.append((cname, fields))
    res_ty = tname + "".join(f" {pn}" for pn, _ in tparams)
    if has_val_idx:
        idx_arrows = "".join(f"{pt} → " for _, pt in tparams)
        idx_binders = "".join(f" {{{pn} : {pt}}}" for pn, pt in tparams)
        c_lines = [f"inductive {tname} : {idx_arrows}Type where"]
        for cname, fields in ctors:
            f_arrows = "".join(f"({fn} : {ft}) → " for fn, ft in fields)
            c_lines.append(f"  | {cname}{idx_binders} : {f_arrows}{res_ty}")
        c_lines.append(f"open {tname}")
        return "\n".join(c_lines)
    param_str = "".join(f" ({pn} : {pt})" for pn, pt in tparams)
    if len(ctors) == 1 and ctors[0][0] == tname:
        struct_names.add(tname)
        c_lines = [f"inductive {tname}{param_str} : Type where"]
        f_arrows = "".join(f"{ft} → " for _, ft in ctors[0][1])
        c_lines.append(f"  | mk : {f_arrows}{res_ty}")
        return "\n".join(c_lines)
    c_lines = [f"inductive {tname}{param_str} : Type where"]
    for cname, fields in ctors:
        f_arrows = "".join(f"{ft} → " for _, ft in fields)
        c_lines.append(f"  | {cname} : {f_arrows}{res_ty}")
    c_lines.append(f"open {tname}")
    return "\n".join(c_lines)


def parse_law_decl(
    raw_text: str,
) -> tuple[str, list[tuple[str, str]], str, str]:
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    head = lines[0]
    m = re.match(r"^law\s+([A-Za-z0-9_.]+)\s*:\s*(.*)$", head)
    lname = safe_ident(m.group(1))
    inline_rest = m.group(2).strip()
    binders: list[tuple[str, str]] = []
    exs_binders: list[tuple[str, str]] = []
    body_lines: list[str] = []
    if inline_rest:
        body_lines.append(inline_rest)
    for l in lines[1:]:
        if l.startswith("for "):
            bm = re.match(r"^for\s+([^:]+):\s*(.*)$", l)
            bnames_raw = bm.group(1).strip()
            bty_raw = bm.group(2).strip()
            for bn in bnames_raw.split(","):
                if bn.strip():
                    binders.append((safe_ident(bn.strip()), translate_type(bty_raw)))
        elif l.startswith("exs "):
            em = re.match(r"^exs\s+([^:]+):\s*(.*)$", l)
            enames_raw = em.group(1).strip()
            ety_raw = em.group(2).strip()
            for en in enames_raw.split(","):
                if en.strip():
                    exs_binders.append((safe_ident(en.strip()), translate_type(ety_raw)))
        else:
            body_lines.append(l)
    claim_raw = " ".join(body_lines)
    claim_lean = translate_type(claim_raw)
    for en, et in reversed(exs_binders):
        claim_lean = f"(BSig {et} (fun {en} => {claim_lean}))"
    sig_parts = [f"({bn} : {bt})" for bn, bt in binders]
    sig = (" ".join(sig_parts) + " : " + claim_lean) if sig_parts else (": " + claim_lean)
    return lname, binders, claim_lean, sig


def translate_def_decl(
    raw_text: str,
    laws_map: dict[str, tuple[list[tuple[str, str]], str, str]],
    struct_names: set[str],
    emit_theorem: bool = True,
    theorem_rename: dict[str, str] | None = None,
) -> tuple[str, str]:
    lines = [
        (len(l) - len(l.lstrip()), l.rstrip())
        for l in raw_text.splitlines()
        if l.strip()
    ]
    head = lines[0][1].strip()
    m = re.match(
        r"^def\s+([A-Za-z0-9_.]+)\s*\((.*)\)\s*(?:->\s*(.+)|:\s*([A-Za-z0-9_.]+))?\s*:\s*$",
        head,
    )
    if not m:
        m = re.match(r"^def\s+([A-Za-z0-9_.]+)\s*:\s*$", head)
        raw_name = m.group(1)
        params_raw = ""
        ret_ty_raw = None
        law_ref_raw = None
    else:
        raw_name = m.group(1)
        params_raw = m.group(2).strip()
        ret_ty_raw = m.group(3).strip() if m.group(3) else None
        law_ref_raw = m.group(4).strip() if m.group(4) else None

    dname = safe_ident(raw_name)
    is_laws_def = raw_name.startswith("Laws.")
    target_law = (
        dname
        if is_laws_def and dname in laws_map
        else (safe_ident(law_ref_raw) if law_ref_raw else None)
    )
    if not target_law and dname in laws_map:
        target_law = dname

    param_list = (
        [p.strip() for p in split_top(params_raw, ",") if p.strip()]
        if params_raw
        else []
    )
    body_lean = translate_block(lines[1:], struct_names)

    if target_law and target_law in laws_map:
        binders, claim_lean, _ = laws_map[target_law]
        paired_binders: list[str] = []
        for idx, (bn, bt) in enumerate(binders):
            pname = safe_ident(param_list[idx]) if idx < len(param_list) else bn
            paired_binders.append(f"({pname} : {bt})")
        is_thm = is_laws_def and emit_theorem
        kw = "theorem" if is_thm else "def"
        out_name = (
            theorem_rename.get(dname, dname)
            if (is_thm and theorem_rename)
            else dname
        )
        if out_name != dname:
            body_lean = re.sub(rf"\b{re.escape(dname)}\b", out_name, body_lean)
        b_str = (" " + " ".join(paired_binders)) if paired_binders else ""
        return f"{kw} {out_name}{b_str} : {claim_lean} :=\n  {body_lean}", out_name

    typed_params: list[str] = []
    for p in param_list:
        if ":" in p:
            pn, pt = p.split(":", 1)
            pt_s = pt.strip()
            pt_lean = "Sort _" if pt_s in ("Type", "Data") else translate_type(pt_s)
            typed_params.append(f"({safe_ident(pn.strip())} : {pt_lean})")
        else:
            typed_params.append(f"({safe_ident(p)})")
    if ret_ty_raw:
        rt_lean = (
            "Prop"
            if ret_ty_raw.strip() in ("Type", "Data")
            else translate_type(ret_ty_raw)
        )
        ret_lean = f" : {rt_lean}"
    else:
        ret_lean = ""
    p_str = (" " + " ".join(typed_params)) if typed_params else ""
    return f"def {dname}{p_str}{ret_lean} :=\n  {body_lean}", dname


def resolve_bend_bundle(
    laws_path: Path, proof_path: Path
) -> list[tuple[Path, set[str]]]:
    root_laws = laws_path.resolve()
    root_proof = proof_path.resolve()
    visited: set[Path] = {root_laws, root_proof}
    ordered: list[Path] = []

    def visit(p: Path) -> None:
        rp = p.resolve()
        if not rp.exists():
            return
        for line in rp.read_text().splitlines():
            s = line.strip()
            if s.startswith("import ") and s != "import Base":
                m = re.match(r"^import\s+(\S+)(?:\s+as\s+\S+)?$", s)
                if m:
                    rel = m.group(1)
                    imp_path = (rp.parent / rel).resolve()
                    if imp_path.name == "PROOF.bend":
                        sib_laws = imp_path.parent / "LAWS.bend"
                        if sib_laws.exists() and sib_laws.resolve() not in visited:
                            visited.add(sib_laws.resolve())
                            visit(sib_laws.resolve())
                            ordered.append(sib_laws.resolve())
                    if imp_path not in visited and imp_path.exists():
                        visited.add(imp_path)
                        visit(imp_path)
                        ordered.append(imp_path)
                    if imp_path.name == "LAWS.bend":
                        sib_proof = imp_path.parent / "PROOF.bend"
                        if sib_proof.exists() and sib_proof.resolve() not in visited:
                            visited.add(sib_proof.resolve())
                            visit(sib_proof.resolve())
                            ordered.append(sib_proof.resolve())

    visit(root_laws)
    visit(root_proof)
    ordered.append(root_laws)
    ordered.append(root_proof)
    return [(p, set()) for p in ordered]


def translate_files(
    files_with_aliases: list[tuple[Path, set[str]]],
    prune_unused: bool = False,
    theorem_rename: dict[str, str] | None = None,
    header_comments: list[str] | None = None,
) -> tuple[str, list[str]]:
    struct_names: set[str] = set()
    laws_map: dict[str, tuple[list[tuple[str, str]], str, str]] = {}
    all_items: list[tuple[str, str, str, bool]] = []
    auto_rename: dict[str, str] = dict(theorem_rename or {})

    for f_idx, (p, _) in enumerate(files_with_aliases):
        is_root = f_idx >= len(files_with_aliases) - 2
        txt = p.read_text()
        if is_root:
            for line in txt.splitlines():
                m_lid = re.match(r"^#\s*law_id:\s*([A-Za-z0-9_]+)", line.strip())
                if m_lid:
                    lid = m_lid.group(1)
                    auto_rename.setdefault(safe_ident(lid.lower()), lid)
        for kind, name, raw_text in parse_bend_file(txt):
            all_items.append((kind, name, raw_text, is_root))

    if prune_unused:
        needed: set[str] = set()
        queue: list[str] = []
        for kind, name, raw_text, is_root in all_items:
            if is_root:
                needed.add(name)
                queue.append(raw_text)
        item_by_name: dict[str, list[tuple[str, str, str]]] = {}
        for kind, name, raw_text, _ in all_items:
            item_by_name.setdefault(name, []).append((kind, name, raw_text))
        while queue:
            txt = queue.pop()
            for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", txt):
                s_tok = safe_ident(tok)
                for candidate in (tok, s_tok):
                    if candidate in item_by_name and candidate not in needed:
                        needed.add(candidate)
                        for _, _, target_txt in item_by_name[candidate]:
                            queue.append(target_txt)
        all_items = [it for it in all_items if it[1] in needed or it[3]]

    hdr_lines = [
        "-- GENERATED by holon.lean; do not edit.",
        "-- Lean 4 core only, no imports.",
    ]
    if header_comments:
        for c in header_comments:
            hdr_lines.append(f"-- {c}")
    out_chunks = ["\n".join(hdr_lines), PREAMBLE]
    theorem_names: list[str] = []

    _ACTIVE_STRUCT_NAMES.clear()
    for kind, name, raw_text, _ in all_items:
        if kind == "type" and name != "Maybe":
            t_lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
            t_ctors = [
                re.match(r"^(?:case\s+)?([A-Za-z0-9_]+)\{", l).group(1)
                for l in t_lines[1:]
                if re.match(r"^(?:case\s+)?([A-Za-z0-9_]+)\{", l)
            ]
            if len(t_ctors) == 1 and safe_ident(t_ctors[0]) == safe_ident(name):
                _ACTIVE_STRUCT_NAMES.add(safe_ident(name))
                struct_names.add(safe_ident(name))

    for kind, name, raw_text, _ in all_items:
        if kind == "law":
            lname, binders, claim_lean, sig = parse_law_decl(raw_text)
            laws_map[lname] = (binders, claim_lean, sig)

    for kind, name, raw_text, is_root in all_items:
        if kind == "type" and name != "Maybe":
            out_chunks.append(translate_type_decl(raw_text, struct_names))
        elif kind == "def":
            decl, out_name = translate_def_decl(
                raw_text,
                laws_map,
                struct_names,
                emit_theorem=is_root,
                theorem_rename=auto_rename,
            )
            out_chunks.append(decl)
            if decl.startswith("theorem "):
                theorem_names.append(out_name)

    if theorem_names:
        out_chunks.append("\n".join(f"#print axioms {t}" for t in theorem_names))

    return "\n\n".join(out_chunks) + "\n", theorem_names
