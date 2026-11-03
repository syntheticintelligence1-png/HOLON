"""Layout facts as solver queries (whitepaper §10.2; I40 E-LAY): one query per function of an extracted codec document
(holon-facts/0.3 "functions": an encoder from a record's fields to bytes, a loader from bytes), written from the
document's paths alone.

Each path's condition is a term over the function's inputs (a record's fields as words of their value width, or a byte
string as an array with a length of at most byte_length_max); an ok path's ops write its output array (mstore8, mstore,
calldatacopy: each op's src pieces are field bytes, zeros or input bytes) and fix its length. The query defines every
path's condition and output and asserts that the paths do NOT partition the input space (no path holds, or two do):
unsat is the layout fact "exactly one path applies to every input", sat a counterexample. Ground, QF_AUFBV.
"""
from __future__ import annotations

from . import encode as E
from .encode import ARR, band, bnot, bor, eq, ite, lit


def _term(t, env: dict) -> str:
    """A path-condition term as a Bool or a 256-bit word (env: input name -> word, or (array, length))."""
    if isinstance(t, bool):
        return "true" if t else "false"
    if isinstance(t, int):
        return lit(t)
    if isinstance(t, str):
        v = env[t]
        if isinstance(v, tuple):
            raise ValueError(f"byte string {t} used as a word")
        return v
    h = t[0]
    if h == "!":
        return bnot(_bool(t[1], env))
    if h == "&&":
        return band(*[_bool(x, env) for x in t[1:]])
    if h == "||":
        return bor(*[_bool(x, env) for x in t[1:]])
    if h == "len":
        return env[t[1]][1]
    if h == "byte":
        arr = env[t[1]][0]
        return f"((_ zero_extend 248) (select {arr} {_term(t[2], env)}))"
    a, b = _term(t[1], env), _term(t[2], env)
    ops = {"==": f"(= {a} {b})", "!=": f"(not (= {a} {b}))", "<": f"(bvult {a} {b})", "<=": f"(bvule {a} {b})",
           ">": f"(bvugt {a} {b})", ">=": f"(bvuge {a} {b})", "+": f"(bvadd {a} {b})", "-": f"(bvsub {a} {b})"}
    if h not in ops:
        raise ValueError(f"layout term {h}")
    return ops[h]


def _bool(t, env: dict) -> str:
    x = _term(t, env)
    if x in ("true", "false") or x.startswith(("(=", "(not", "(bvult", "(bvule", "(bvugt", "(bvuge", "(and", "(or")):
        return x
    return f"(not (= {x} {lit(0)}))"


def query(doc: dict, fn: str, rlimit: int, byte_length_max: int) -> E.Query:
    f = doc["functions"][fn]
    q = E.Query(rlimit)
    env = {}
    src = doc["types"].get(f["from"]) or {}
    widths = {}
    if src.get("kind") == "record":
        for fl in src["fields"]:
            w = q.const(f"f_{fl['name']}")
            q.add(f"(bvult {w} {lit(1 << int(fl['value_bits']))})" if int(fl["value_bits"]) < 256 else "true")
            env[fl["name"]] = w
            widths[fl["name"]] = int(fl["width"])
    else:
        names = sorted({x for p in f["paths"] for x in _names(p.get("cond"))} | {"input"})
        for n in names:
            arr, ln = q.const(f"b_{n}", ARR), q.const(f"n_{n}")
            q.add(f"(bvule {ln} {lit(byte_length_max)})")
            env[n] = (arr, ln)
    conds = []
    for j, p in enumerate(f["paths"]):
        c = q.define(band(*[_bool(x, env) for x in p.get("cond") or []]), "Bool", f"path{j}")
        conds.append(c)
        if p.get("outcome") == "ok":
            a = f"((as const {ARR}) {lit(0, 8)})"
            for op in p.get("ops") or []:
                a = _op(op, a, env, widths)
                a = q.define(a, ARR, f"out{j}")
            q.define(a, ARR, f"out{j}")
    one = bor(*[band(conds[i], *[bnot(conds[k]) for k in range(len(conds)) if k != i]) for i in range(len(conds))])
    q.add(bnot(one))
    q.notes = [f"layout of {fn} ({f.get('kind')} {f.get('from')} -> {f.get('to')}): {len(f['paths'])} paths; "
               "unsat: exactly one path applies to every input"]
    return q


def _names(t) -> set:
    out = set()
    if isinstance(t, list):
        if t[:1] in (["len"], ["byte"]) and len(t) > 1 and isinstance(t[1], str):
            out.add(t[1])
        for x in t:
            out |= _names(x)
    return out


def _op(op: dict, a: str, env: dict, widths: dict) -> str:
    off = op["offset"]
    pos = 0
    for piece in op.get("src") or []:
        if "zeros" in piece:
            for i in range(int(piece["zeros"])):
                a = f"(store {a} {lit(off + pos + i)} {lit(0, 8)})"
            pos += int(piece["zeros"])
        elif "field" in piece:
            w = env[piece["field"]]
            nb = widths.get(piece["field"], 32)
            for i in range(int(piece["len"])):
                k = int(piece["from"]) + i              # byte k of the field's nb-byte big-endian form
                hi = 8 * (nb - k) - 1
                a = f"(store {a} {lit(off + pos + i)} ((_ extract {hi} {hi - 7}) {w}))"
            pos += int(piece["len"])
        elif "input" in piece:
            arr, ln = env[piece["input"]]
            del ln
            for i in range(64):           # the copied prefix the layout's fields read (the header's fixed part)
                a = f"(store {a} {lit(off + i)} (select {arr} {lit(int(piece.get('from', 0)) + i)}))"
            pos += 64
    return a
