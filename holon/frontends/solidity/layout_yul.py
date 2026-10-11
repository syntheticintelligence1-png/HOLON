"""Minimal parser for `solc --ir-optimized` output (M2 S2, whitepaper §10.1).

The extractor consumes Yul text only: `object` blocks with `code { ... }`
containing `function` definitions whose bodies are lists of statements. Every
statement carries the `/// @src` / `/// @ast-id` annotations solc emits, so each
extracted fact can cite the source line it came from. Nothing outside solc's own
output is trusted.

AST forms (all plain dicts, produced by `parse_yul`):

  {"lit": n}                      decimal/hex literal (or a "string")
  {"str": s}                      "literal string" (error strings)
  {"id": name}                    identifier
  {"call": name, "args": [e..]}   function-call expression
  {"let": [names], "value": e|None}
  {"assign": [names], "value": e}
  {"if": cond, "body": [stmts]}
  {"switch": cond, "cases": [(lit|None, [stmts])..]}   None = default
  {"for": init, "cond": e, "post": [stmts], "body": [stmts]}
  {"leave"|"break"|"continue"|"expr": e}
  {"fun": name, "params": [n..], "returns": [n..], "body": [stmts]}
  {"block": [stmts]}

Every statement dict may also carry "src": "file:begin:end" and "code": the
original Solidity text solc quotes in the @src annotation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------- tokenizer
_WS = re.compile(r"\s*")
_LINE_COMMENT = re.compile(r"\s*(?:///\s*@ast-id\s+(\d+)\s+@src\s+(\d+:\d+:\d+)\s+\"((?:[^\"\\]|\\.)*)\"|"
                           r"///\s*@src\s+(\d+:\d+:\d+)\s+\"((?:[^\"\\]|\\.)*)\"|"
                           r"///\s*@ast-id\s+(\d+)|"
                           r"///\s*@use-src\s+([^\n]*)|"
                           r"//[^\n]*|/\*.*?\*/)", re.S)
_TOKEN = re.compile(
    r'\s*(?:'
    r'("(?:[^"\\]|\\.)*")'                       # string literal
    r'|(0x[0-9a-fA-F]+|0|[1-9][0-9]*)'           # number
    r'|(:=|->|[{}(),:])'                         # punctuation
    r'|([A-Za-z_$][A-Za-z0-9_.$-]*)'             # identifier (incl. dots/dollars)
    r'|(.)'                                      # anything else -> error
    r')', re.S)


@dataclass
class Tok:
    kind: str           # "str" | "num" | "punct" | "id"
    text: str
    src: str | None = None     # "@src f:b:e" attached before this token
    code: str | None = None    # quoted source text
    ast_id: str | None = None


def tokenize(text: str) -> list[Tok]:
    out: list[Tok] = []
    i, n = 0, len(text)
    pend_src: tuple[str, str] | None = None
    pend_ast: str | None = None
    while i < n:
        if not text[i:].strip():
            break
        m = _LINE_COMMENT.match(text, i)
        if m:
            if m.group(1):          # combined @ast-id N @src F:S:E "text"
                pend_ast = m.group(1)
                pend_src = (m.group(2), m.group(3))
            elif m.group(4):
                pend_src = (m.group(4), m.group(5))
            elif m.group(6):
                pend_ast = m.group(6)
            i = m.end()
            continue
        t = _TOKEN.match(text, i)
        if not t:
            raise ValueError(f"Yul tokenize stuck at {i}: {text[i:i+40]!r}")
        if t.group(5) is not None:
            raise ValueError(f"Yul tokenize: unexpected {t.group(5)!r} at {i}: {text[max(0,i-40):i+10]!r}")
        if t.group(1):
            kind, val = "str", t.group(1)[1:-1]
        elif t.group(2):
            kind, val = "num", t.group(2)
        elif t.group(3):
            kind, val = "punct", t.group(3)
        else:
            kind, val = "id", t.group(4)
        tok = Tok(kind, val)
        if pend_src:
            tok.src, tok.code = pend_src
            pend_src = None
        if pend_ast:
            tok.ast_id = pend_ast
            pend_ast = None
        out.append(tok)
        i = t.end()
    return out


# ---------------------------------------------------------------- parser
class P:
    def __init__(self, toks: list[Tok]):
        self.t, self.i = toks, 0

    def peek(self, k=None, v=None) -> Tok | None:
        if self.i >= len(self.t):
            return None
        tok = self.t[self.i]
        if k is not None and tok.kind != k:
            return None
        if v is not None and tok.text != v:
            return None
        return tok

    def next(self) -> Tok:
        tok = self.t[self.i]
        self.i += 1
        return tok

    def want(self, text: str) -> Tok:
        tok = self.peek("punct", text)
        if not tok:
            got = self.t[self.i] if self.i < len(self.t) else None
            raise ValueError(f"expected {text!r}, got {got and got.text!r}")
        return self.next()

    def ident(self) -> Tok:
        tok = self.peek("id") or self.peek("num")
        if not tok:
            raise ValueError(f"expected identifier, got {self.peek() and self.peek().text!r}")
        return self.next()


def parse_expr(p: P) -> dict:
    tok = p.peek()
    if tok.kind == "num":
        p.next()
        return {"lit": int(tok.text, 0)}
    if tok.kind == "str":
        p.next()
        return {"str": tok.text}
    if tok.kind == "id":
        name = p.next().text
        if p.peek("punct", "("):
            p.want("(")
            args = []
            if not p.peek("punct", ")"):
                args.append(parse_expr(p))
                while p.peek("punct", ","):
                    p.next()
                    args.append(parse_expr(p))
            p.want(")")
            return {"call": name, "args": args}
        return {"id": name}
    raise ValueError(f"bad expression at {tok.text!r}")


def parse_stmt(p: P) -> dict:
    tok = p.next()
    meta = {}
    if tok.src:
        meta["src"] = tok.src
    if tok.code is not None:
        meta["code"] = tok.code
    if tok.ast_id:
        meta["ast_id"] = tok.ast_id
    if tok.kind == "punct" and tok.text == "{":
        body = parse_block_body(p)
        return {"block": body, **meta}
    if tok.kind != "id":
        raise ValueError(f"bad statement start {tok.text!r}")
    w = tok.text
    if w == "let":
        names = [p.ident().text]
        while p.peek("punct", ","):
            p.next()
            names.append(p.ident().text)
        val = None
        if p.peek("punct", ":="):
            p.next()
            val = parse_expr(p)
        return {"let": names, "value": val, **meta}
    if w == "function":
        name = p.ident().text
        p.want("(")
        params = []
        if not p.peek("punct", ")"):
            params.append(p.ident().text)
            while p.peek("punct", ","):
                p.next()
                params.append(p.ident().text)
        p.want(")")
        rets = []
        if p.peek("punct", "->"):
            p.next()
            rets.append(p.ident().text)
            while p.peek("punct", ","):
                p.next()
                rets.append(p.ident().text)
        p.want("{")
        body = parse_block_body(p)
        return {"fun": name, "params": params, "returns": rets, "body": body, **meta}
    if w == "if":
        cond = parse_expr(p)
        p.want("{")
        return {"if": cond, "body": parse_block_body(p), **meta}
    if w == "switch":
        cond = parse_expr(p)
        cases = []
        while True:
            if p.peek("id", "case"):
                p.next()
                lit = p.next()
                if lit.kind not in ("num", "str"):
                    raise ValueError(f"switch case literal {lit.text!r}")
                val = int(lit.text, 0) if lit.kind == "num" else lit.text
                p.want("{")
                cases.append((val, parse_block_body(p)))
            elif p.peek("id", "default"):
                p.next()
                p.want("{")
                cases.append((None, parse_block_body(p)))
            else:
                break
        return {"switch": cond, "cases": cases, **meta}
    if w == "for":
        p.want("{")
        init = parse_block_body(p)
        cond = parse_expr(p)
        p.want("{")
        post = parse_block_body(p)
        p.want("{")
        body = parse_block_body(p)
        return {"for": init, "cond": cond, "post": post, "body": body, **meta}
    if w in ("leave", "break", "continue"):
        return {w: True, **meta}
    # expression statement, possibly an assignment
    if p.peek("punct", ":="):
        p.next()
        return {"assign": [w], "value": parse_expr(p), **meta}
    if p.peek("punct", ","):          # multi-assignment: a, b := f(..)
        names = [w]
        while p.peek("punct", ","):
            p.next()
            names.append(p.ident().text)
        p.want(":=")
        return {"assign": names, "value": parse_expr(p), **meta}
    return {"expr": {"id": w} if not p.peek("punct", "(") else parse_call_tail(p, w), **meta}


def parse_call_tail(p: P, name: str) -> dict:
    p.want("(")
    args = []
    if not p.peek("punct", ")"):
        args.append(parse_expr(p))
        while p.peek("punct", ","):
            p.next()
            args.append(parse_expr(p))
    p.want(")")
    return {"call": name, "args": args}


def parse_block_body(p: P) -> list[dict]:
    out = []
    while not p.peek("punct", "}"):
        out.append(parse_stmt(p))
    p.want("}")
    return out


@dataclass
class YulUnit:
    """Parsed `--ir-optimized` output: functions plus the source-file table."""
    functions: dict = field(default_factory=dict)     # name -> fun dict
    use_src: dict = field(default_factory=dict)        # file index -> path
    objects: list = field(default_factory=list)

    def src_file(self, stmt: dict) -> str | None:
        src = stmt.get("src")
        if not src:
            return None
        return self.use_src.get(int(src.split(":", 1)[0]))


_USE_SRC = re.compile(r'@use-src\s+((?:\d+:"[^"]*"[,\s]*)+)')


def parse_yul(text: str) -> YulUnit:
    unit = YulUnit()
    for m in _USE_SRC.finditer(text):
        for idx, path in re.findall(r'(\d+):"([^"]*)"', m.group(1)):
            unit.use_src[int(idx)] = path
    toks = tokenize(text)
    p = P(toks)
    while p.i < len(toks):
        tok = p.peek()
        if tok is None:
            break
        if tok.kind == "id" and tok.text == "object":
            p.next()
            name = p.next()
            unit.objects.append(name.text.strip('"') if name.kind == "str" else name.text)
            p.want("{")
            _parse_object_body(p, unit)
        else:
            p.next()  # stray text (e.g. "Optimized IR:" headers, data blocks)
    return unit


def _parse_object_body(p: P, unit: YulUnit) -> None:
    while not p.peek("punct", "}"):
        tok = p.peek()
        if tok.kind == "id" and tok.text == "code":
            p.next()
            p.want("{")
            for s in parse_block_body(p):
                _collect_functions(s, unit)
        elif tok.kind == "id" and tok.text == "data":
            p.next()
            if p.peek("str"):
                p.next()
            if p.peek("kind") or p.peek("id"):
                p.next()
            if p.peek("str"):
                p.next()
        elif tok.kind == "id" and tok.text == "object":
            p.next()
            p.next()  # name
            p.want("{")
            _parse_object_body(p, unit)
        else:
            p.next()
    p.want("}")


def _collect_functions(stmt: dict, unit: YulUnit) -> None:
    if "fun" in stmt:
        unit.functions[stmt["fun"]] = stmt
    for key in ("body", "post"):
        for s in stmt.get(key, []) if isinstance(stmt.get(key), list) else []:
            _collect_functions(s, unit)
    for c in stmt.get("cases", []):
        for s in c[1]:
            _collect_functions(s, unit)
    for b in stmt.get("block", []):
        _collect_functions(b, unit)


# ---------------------------------------------------------------- expr helpers
def as_add_offset(e: dict, base: str) -> int | None:
    """add(base, K) or base -> constant offset, else None."""
    if e == {"id": base}:
        return 0
    if "call" in e and e["call"] == "add":
        a, b = e["args"]
        if a == {"id": base} and "lit" in b:
            return b["lit"]
        if b == {"id": base} and "lit" in a:
            return a["lit"]
    return None
