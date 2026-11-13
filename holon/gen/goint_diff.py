"""The differential check of holon.gen.goint against the pinned Go toolchain (BUILD_PLAN row I117; HUMAN_ANSWERS Q90 (2)).

cases() lists the edge cases (fixed, sorted, no randomness): for every integer type, every binary op over the type's
edge values (0, 1, 2, 7, -1, -2, -7, the minimum and maximum and their neighbours, fit to the type), every shift by the
counts 0, 1, 7, 8, 15, 16, 31, 32, 33, 63, 64, 65, 200 (of uint) and -1, -64 (of int, the negative-count panic), every
unary op, every conversion between two integer types and every comparison. go_program() writes them as a Go program
whose operands are variables (never constants folded by the compiler); run_go() runs it with a given go binary and
reads one line per case: the value, or "panic: <message>". reference() is the module's own reference; model_text()
the Bend harness over the model's definitions (a function per op and type), evaluated by node through the compiled
module (holon/js/linked.mjs) and, for a sample, checked by Bend itself as laws (check_text()).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import goint as GI

TYPES = ("int8", "int16", "int32", "int64", "int", "uint8", "uint16", "uint32", "uint64", "uint", "uintptr")
COUNTS_U = (0, 1, 7, 8, 15, 16, 31, 32, 33, 63, 64, 65, 200)
COUNTS_S = (-1, -64, 3)
NONSHIFT = ("+", "-", "*", "/", "%", "&", "|", "^", "&^")
OPNAME = {"+": "add", "-": "sub", "*": "mul", "/": "quo", "%": "rem", "&": "and", "|": "or", "^": "xor", "&^": "andnot",
          "<<": "shl", ">>": "shr", "==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}


def edges(t: str) -> list[int]:
    bits, signed = GI.itype(t)
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    vs = {0, 1, 2, 7, -1, -2, -7, lo, lo + 1, hi, hi - 1, 100, -100}
    return sorted({GI.fit(v, t) for v in vs})


def cases() -> list[dict]:
    out = []
    for t in TYPES:
        vs = edges(t)
        for o in NONSHIFT:
            for a in vs:
                for b in vs:
                    out.append({"k": "bin", "op": o, "t": t, "a": a, "b": b})
        for o in ("<<", ">>"):
            for a in vs:
                for c in COUNTS_U:
                    out.append({"k": "shift", "op": o, "t": t, "a": a, "b": c, "ct": "uint"})
                for c in COUNTS_S:
                    out.append({"k": "shift", "op": o, "t": t, "a": a, "b": c, "ct": "int"})
        for o in ("-", "^"):
            for a in vs:
                out.append({"k": "un", "op": o, "t": t, "a": a})
        for o in GI.CMPS:
            for a in vs:
                for b in vs:
                    out.append({"k": "cmp", "op": o, "t": t, "a": a, "b": b})
        for u in TYPES:
            for a in vs:
                out.append({"k": "conv", "t": t, "u": u, "a": a})
    return out


def reference(c: dict) -> str:
    """The reference's answer as the Go program prints it."""
    try:
        if c["k"] == "bin":
            return str(GI.binop(c["op"], c["t"], c["a"], c["b"]))
        if c["k"] == "shift":
            return str(GI.binop(c["op"], c["t"], c["a"], c["b"], c["ct"]))
        if c["k"] == "un":
            return str(GI.unop(c["op"], c["t"], c["a"]))
        if c["k"] == "cmp":
            return "true" if GI.compare(c["op"], c["t"], c["a"], c["b"]) else "false"
        if c["k"] == "conv":
            return str(GI.fit(c["a"], c["u"]))
    except GI.Panic:
        return "panic"
    raise ValueError(c)


def _fname(c: dict) -> str:
    if c["k"] in ("bin", "cmp"):
        return f"{c['k']}_{OPNAME[c['op']]}_{c['t']}"
    if c["k"] == "shift":
        return f"shift_{OPNAME[c['op']]}_{c['t']}_{c['ct']}"
    if c["k"] == "un":
        return f"un_{'neg' if c['op'] == '-' else 'not'}_{c['t']}"
    return f"conv_{c['t']}_{c['u']}"


def go_program(cs: list[dict]) -> str:
    """A Go program printing one line per case. Operands are function parameters (go:noinline), so nothing folds."""
    fns, seen, calls = [], set(), []
    for c in cs:
        f = _fname(c)
        if f not in seen:
            seen.add(f)
            t = c["t"]
            if c["k"] == "bin":
                body = f"func {f}(a, b {t}) {t} {{ return a {c['op']} b }}"
            elif c["k"] == "cmp":
                body = f"func {f}(a, b {t}) bool {{ return a {c['op']} b }}"
            elif c["k"] == "shift":
                body = f"func {f}(a {t}, s {c['ct']}) {t} {{ return a {c['op']} s }}"
            elif c["k"] == "un":
                body = f"func {f}(a {t}) {t} {{ return {c['op']}a }}"
            else:
                body = f"func {f}(a {t}) {c['u']} {{ return {c['u']}(a) }}"
            fns.append("//go:noinline\n" + body)
        args = [f"{c['t']}({c['a']})"]
        if c["k"] in ("bin", "cmp"):
            args.append(f"{c['t']}({c['b']})")
        elif c["k"] == "shift":
            args.append(f"{c['ct']}({c['b']})")
        calls.append(f"\tshow(func() any {{ return {f}({', '.join(_lit(a) for a in args)}) }})")
    return "\n".join([
        "// GENERATED by holon.gen.goint_diff (I117's differential check); do not edit.",
        "package main", "", 'import "fmt"', "",
        "func show(f func() any) {",
        "\tdefer func() {", "\t\tif r := recover(); r != nil {", '\t\t\tfmt.Println("panic")', "\t\t}", "\t}()",
        "\tfmt.Println(f())", "}", "", *fns, "", "func main() {", *calls, "}", ""])


def _lit(a: str) -> str:
    """A conversion of a constant that is out of the type's range would not compile: go through a variable of int64 or
    uint64 bits (the reference fits it the same way: every value here is already in range)."""
    return a


def run_go(go: str, cs: list[dict], work: Path) -> list[str]:
    work.mkdir(parents=True, exist_ok=True)
    (work / "go.mod").write_text("module holon/i117diff\n\ngo 1.24\n")
    (work / "main.go").write_text(go_program(cs))
    p = subprocess.run([go, "run", "."], cwd=work, capture_output=True, text=True, timeout=1800,
                       env={**__import__("os").environ, "GOFLAGS": "-mod=mod", "GOTOOLCHAIN": "local"})
    if p.returncode != 0:
        raise RuntimeError(f"go run failed: {p.stderr[-3000:]}")
    return p.stdout.splitlines()


# ---------------------------------------------------------------------- the model's harness
HARNESS_HEAD = '''
type GR is Data:
  GV{hi: U32, lo: U32}
  GP{}

def gw_low.con(h: Bool, r: U32) -> U32:
  match h:
    case True{}:
      U32.add(U32.mul(r, 2), 1)
    case False{}:
      U32.mul(r, 2)

def gw_low(n: Nat, k: Nat, w: Word(n)) -> U32:
  match n:
    case 0n:
      0
    case 1n+p:
      match k:
        case 0n:
          0
        case 1n+kp:
          match w:
            case WCon{h, t}:
              gw_low.con(h, gw_low(p, kp, t))

def gw_out(+w: Word(64n)) -> GR:
  GV{gw_low(64n, 32n, gw_shrn(32n, w)), gw_low(64n, 32n, w)}

def gw_guard(p: Bool, +w: Word(64n)) -> GR:
  match p:
    case True{}:
      GP{}
    case False{}:
      gw_out(w)
'''


def _w(name: str) -> str:
    return f"gw_k({name}h, {name}l)"


def model_fn(c: dict) -> str:
    """The harness function of a case's op and type over the model's definitions (holon.gen.goint's texts)."""
    f, t = _fname(c), c["t"]
    a, b = _w("a"), _w("b")
    if c["k"] == "bin":
        e = GI.binop_text(c["op"], t, a, b)
        res = f"gw_guard(gw_div_panics({b}), {e})" if c["op"] in ("/", "%") else f"gw_out({e})"
        return f"def {f}(ah: U32, al: U32, +bh: U32, +bl: U32) -> GR:\n  {res}\n"
    if c["k"] == "shift":
        s = GI.bool_lit(GI.itype(c["ct"])[1])
        e = GI.binop_text(c["op"], t, a, b)
        return f"def {f}(ah: U32, al: U32, +bh: U32, +bl: U32) -> GR:\n  gw_guard(gw_shift_panics({s}, {b}), {e})\n"
    if c["k"] == "un":
        return f"def {f}(ah: U32, al: U32) -> GR:\n  gw_out({GI.unop_text(c['op'], t, a)})\n"
    if c["k"] == "cmp":
        return f"def {f}(+ah: U32, +al: U32, +bh: U32, +bl: U32) -> Bool:\n  {GI.compare_text(c['op'], t, a, b)}\n"
    return f"def {f}(ah: U32, al: U32) -> GR:\n  gw_out({GI.convert_text(c['u'], a)})\n"


def model_text(cs: list[dict]) -> str:
    fns, seen = [], set()
    for c in cs:
        if _fname(c) not in seen:
            seen.add(_fname(c))
            fns.append(model_fn(c))
    return "\n".join(["# GENERATED by holon.gen.goint_diff (I117's differential check); do not edit.", "import Base", "",
                      GI.PRELUDE, HARNESS_HEAD, *fns])


def _pair(v: int) -> list[int]:
    w = GI.w64(v)
    return [w >> 32, w & 0xffffffff]


def model_call(c: dict) -> dict:
    args = _pair(c["a"]) + (_pair(c["b"]) if c["k"] in ("bin", "cmp", "shift") else [])
    return {"fn": _fname(c), "args": [{"val": x} for x in args]}


def model_answer(c: dict, r) -> str:
    """A harness result as the Go program prints it (the value read in the result type's signedness)."""
    if isinstance(r, bool):
        return "true" if r else "false"
    if isinstance(r, dict) and r.get("$") == "GP":
        return "panic"
    if isinstance(r, dict) and r.get("$") == "GV":
        t = c["u"] if c["k"] == "conv" else c["t"]
        return str(GI.fit((r["hi"] << 32) | r["lo"], t if GI.itype(t)[0] == 64 else ("int64" if GI.itype(t)[1]
                                                                                       else "uint64")))
    return f"error: {json.dumps(r)[:200]}"


def check_text(cs: list[dict], expected: list[str]) -> str:
    """Bend laws, one per case (no panic, no Bool), that the model's value at the case is the expected one: checked
    by Bend's own evaluation (each proof is {==})."""
    lines = ["# GENERATED by holon.gen.goint_diff (I117's differential check, the checker's own evaluation).",
             "import Base", "", GI.PRELUDE]
    for i, (c, e) in enumerate(zip(cs, expected)):
        a, b = GI.const_text(c["a"]), GI.const_text(c.get("b", 0))
        if c["k"] in ("bin", "shift"):
            x = GI.binop_text(c["op"], c["t"], a, b)
        elif c["k"] == "un":
            x = GI.unop_text(c["op"], c["t"], a)
        elif c["k"] == "conv":
            x = GI.convert_text(c["u"], a)
        else:
            x = GI.compare_text(c["op"], c["t"], a, b)
            lines += [f"law d{i}:", f"  {{{x} == {'True{}' if e == 'true' else 'False{}'} : Bool}}", "",
                      f"def d{i}():", "  {==}", ""]
            continue
        lines += [f"law d{i}:", f"  {{{x} == {GI.const_text(int(e))} : Word(64n)}}", "", f"def d{i}():", "  {==}", ""]
    return "\n".join(lines) + "\n"
