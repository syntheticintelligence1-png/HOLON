"""Terms of a Bend model for the equivalence prover (F32; holon.gen.eqprove).

A small, untrusted partial evaluator over Bend source: it parses the expressions of the pair module's definitions and
of Base (read from the pinned checker's `bend base`), and computes normal forms of open terms the way the kernel does
up to conversion: a call whose own match tree reduces is unfolded, a call stuck on a value that is not a constructor
stays folded. The prover uses these forms to write rewrite motives and to decide where to split; the kernel checks
every step, so a mistake here costs a failed attempt, never a wrong verdict.

Terms (immutable tuples, hashable):
  ("var", name)            a local or bound variable
  ("u32", n)               a U32 literal
  ("nat", n)               a Nat literal kn;  ("nsucc", k, t) is kn+t
  ("ctor", name, args)     a constructor with its fields in declaration order (Base or qualified model names)
  ("app", name, args)      a call of a definition (Base names like U32.add, model names qualified P.<name>)
  ("ty", text)             a type argument, kept as text (List<&2, P.KW>, U32, ...)
  ("tup", (a, b))          a pair
Target-agnostic: nothing here names a model definition.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

U32_BITS = 32
MASK32 = (1 << 32) - 1
OPS = {"+": "add", "-": "sub", "*": "mul", "/": "div", "%": "mod", ".&.": "and", ".|.": "or", ".^.": "xor",
       "<<": "shln", ">>": "shrn", "<": "is_lt", "<=": "is_le", ">": "is_gt", ">=": "is_ge"}


class TermError(Exception):
    pass


class Stuck(Exception):
    """Evaluation of a definition's body reached a match on a value that is not a constructor."""

    def __init__(self, scrut):
        super().__init__("stuck")
        self.scrut = scrut


# ------------------------------------------------------------------ constructors and helpers
def V(n):
    return ("var", n)


def A(f, *args):
    return ("app", f, tuple(args))


def C(c, *args):
    return ("ctor", c, tuple(args))


TRUE, FALSE, NIL = ("ctor", "True", ()), ("ctor", "False", ()), ("ctor", "Nil", ())


def is_ctor(t):
    return t[0] in ("ctor", "u32", "nat", "tup")


def size(t) -> int:
    if t[0] in ("app", "ctor"):
        return 1 + sum(size(a) for a in t[2])
    if t[0] == "tup":
        return 1 + sum(size(a) for a in t[1])
    if t[0] == "nsucc":
        return 1 + size(t[2])
    return 1


def subterms(t):
    yield t
    if t[0] in ("app", "ctor"):
        for a in t[2]:
            yield from subterms(a)
    elif t[0] == "tup":
        for a in t[1]:
            yield from subterms(a)
    elif t[0] == "nsucc":
        yield from subterms(t[2])


def free_vars(t, out=None) -> list:
    out = [] if out is None else out
    for s in subterms(t):
        if s[0] == "var" and s[1] not in out:
            out.append(s[1])
    return out


def replace(t, old, new):
    """Every occurrence of the subterm old replaced by new."""
    if t == old:
        return new
    if t[0] in ("app", "ctor"):
        return (t[0], t[1], tuple(replace(a, old, new) for a in t[2]))
    if t[0] == "tup":
        return ("tup", tuple(replace(a, old, new) for a in t[1]))
    if t[0] == "nsucc":
        return ("nsucc", t[1], replace(t[2], old, new))
    return t


def subst(t, env: dict):
    if t[0] == "var":
        return env.get(t[1], t)
    if t[0] in ("app", "ctor"):
        return (t[0], t[1], tuple(subst(a, env) for a in t[2]))
    if t[0] == "tup":
        return ("tup", tuple(subst(a, env) for a in t[1]))
    if t[0] == "nsucc":
        return ("nsucc", t[1], subst(t[2], env))
    return t


def word_of(n: int, width: int):
    w = ("ctor", "WNil", ())
    for i in reversed(range(width)):
        w = ("ctor", "WCon", (TRUE if (n >> i) & 1 else FALSE, w))
    return w


def const_word(w):
    """(value, width) of a Word of constant bits, or None."""
    bits = []
    while w[0] == "ctor" and w[1] == "WCon":
        b = w[2][0]
        if b == TRUE:
            bits.append(1)
        elif b == FALSE:
            bits.append(0)
        else:
            return None
        w = w[2][1]
    if w != ("ctor", "WNil", ()):
        return None
    return sum(b << i for i, b in enumerate(bits)), len(bits)


def canon(t):
    """A U32 constructor of constant bits is written as its literal."""
    if t[0] == "ctor" and t[1] == "U32" and len(t[2]) == 1:
        cw = const_word(t[2][0])
        if cw is not None and cw[1] == U32_BITS:
            return ("u32", cw[0])
    return t


# ------------------------------------------------------------------ printing
def show(t) -> str:
    k = t[0]
    if k == "var":
        return t[1]
    if k == "u32":
        return str(t[1])
    if k == "nat":
        return f"{t[1]}n"
    if k == "nsucc":
        return f"{t[1]}n+{show(t[2])}"
    if k == "ty":
        return t[1]
    if k == "tup":
        return "(" + ", ".join(show(a) for a in t[1]) + ")"
    if k == "ctor":
        return f"{t[1]}{{{', '.join(show(a) for a in t[2])}}}"
    if k == "app":
        return f"{t[1]}({', '.join(show(a) for a in t[2])})"
    raise TermError(f"cannot print {t!r}")


def show_hole(t, hole) -> str:
    """The term with every occurrence of the subterm hole written as `_` (a rewrite motive)."""
    if t == hole:
        return "_"
    k = t[0]
    if k in ("app", "ctor"):
        inner = ", ".join(show_hole(a, hole) for a in t[2])
        return f"{t[1]}({inner})" if k == "app" else f"{t[1]}{{{inner}}}"
    if k == "tup":
        return "(" + ", ".join(show_hole(a, hole) for a in t[1]) + ")"
    if k == "nsucc":
        return f"{t[1]}n+{show_hole(t[2], hole)}"
    return show(t)


def show_at(t, path: tuple, hole: str = "_") -> str:
    """The term with the subterm at path (a tuple of argument indices) written as hole."""
    if not path:
        return hole
    i, rest = path[0], path[1:]
    k = t[0]
    if k in ("app", "ctor"):
        parts = [show_at(a, rest, hole) if j == i else show(a) for j, a in enumerate(t[2])]
        return f"{t[1]}({', '.join(parts)})" if k == "app" else f"{t[1]}{{{', '.join(parts)}}}"
    if k == "tup":
        return "(" + ", ".join(show_at(a, rest, hole) if j == i else show(a) for j, a in enumerate(t[1])) + ")"
    if k == "nsucc":
        return f"{t[1]}n+{show_at(t[2], rest, hole)}"
    raise TermError("bad path")


def at(t, path):
    for i in path:
        t = t[1][i] if t[0] == "tup" else (t[2] if t[0] == "nsucc" else t[2][i])
    return t


def put(t, path, new):
    if not path:
        return new
    i, rest = path[0], path[1:]
    if t[0] == "tup":
        xs = list(t[1])
        xs[i] = put(xs[i], rest, new)
        return ("tup", tuple(xs))
    if t[0] == "nsucc":
        return ("nsucc", t[1], put(t[2], rest, new))
    xs = list(t[2])
    xs[i] = put(xs[i], rest, new)
    return (t[0], t[1], tuple(xs))


def positions(t, path=()):
    yield path, t
    if t[0] in ("app", "ctor"):
        for i, a in enumerate(t[2]):
            yield from positions(a, path + (i,))
    elif t[0] == "tup":
        for i, a in enumerate(t[1]):
            yield from positions(a, path + (i,))
    elif t[0] == "nsucc":
        yield from positions(t[2], path + (0,))


# ------------------------------------------------------------------ parsing
_TOK = re.compile(r"\s*(\d+n|\d+|\.&\.|\.\|\.|\.\^\.|<<|>>|<=|>=|=>|->|==|&\d|[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*"
                  r"|[{}()\[\],:<>+\-*/%~@])")


def tokens(s: str) -> list[str]:
    out, i = [], 0
    s = s.rstrip()
    while i < len(s):
        m = _TOK.match(s, i)
        if not m or m.end() == i:
            raise TermError(f"cannot read {s[i:i + 30]!r}")
        out.append(m.group(1))
        i = m.end()
    return out


class Parser:
    def __init__(self, text: str):
        self.t = tokens(text)
        self.i = 0

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else None

    def take(self, want=None):
        x = self.peek()
        if x is None or (want is not None and x != want):
            raise TermError(f"expected {want!r}, got {x!r}")
        self.i += 1
        return x

    def done(self):
        return self.i >= len(self.t)

    def type_text(self) -> str:
        """A type, as text, up to the next ',' ')' '}' at depth 0."""
        depth, parts = 0, []
        while not self.done():
            x = self.peek()
            if depth == 0 and x in (",", ")", "}", "]"):
                break
            if x in ("<", "(", "{", "["):
                depth += 1
            elif x in (">", ")", "}", "]"):
                depth -= 1
            parts.append(self.take())
        out = ""
        for p in parts:
            if out and (p not in (",", ">", ")", "}", "]") and not out.endswith(("<", "(", "{", "[", "&"))):
                if not (p == "<" and out[-1:].isalnum()):
                    out += " " if out[-1] in "," or p in ("->",) or out.endswith("->") else ""
            out += p
        return out.replace(",", ", ").replace(",  ", ", ")

    def expr(self):
        x = self.peek()
        if x is None:
            raise TermError("unexpected end")
        if re.fullmatch(r"\d+n", x):
            self.take()
            if self.peek() == "+" and self.peek(1) is not None:
                self.take()
                return ("nsucc", int(x[:-1]), self.expr())
            return ("nat", int(x[:-1]))
        if re.fullmatch(r"\d+", x):
            self.take()
            return ("u32", int(x) & MASK32)
        if x == "[":
            self.take()
            items = []
            while self.peek() != "]":
                items.append(self.expr())
                if self.peek() == ",":
                    self.take()
            self.take("]")
            out = NIL
            for it in reversed(items):
                out = ("ctor", "Con", (it, out))
            return out
        if x == "(":
            self.take()
            a = self.expr()
            if self.peek() == ",":
                items = [a]
                while self.peek() == ",":
                    self.take()
                    items.append(self.expr())
                self.take(")")
                return ("tup", tuple(items))
            if self.peek() in OPS:
                op = self.take()
                b = self.expr()
                self.take(":")
                ty = self.type_text()
                self.take(")")
                return ("app", f"{ty}.{OPS[op]}", (a, b))
            self.take(")")
            return a
        if x == "{":
            self.take()
            a = self.expr()
            self.take(":")
            self.type_text()
            self.take("}")
            return a
        if re.fullmatch(r"[A-Za-z_][\w.]*", x):
            self.take()
            nxt = self.peek()
            if nxt == "(":
                self.take()
                args = []
                while self.peek() != ")":
                    args.append(self.arg())
                    if self.peek() == ",":
                        self.take()
                self.take(")")
                return ("app", x, tuple(args))
            if nxt == "{":
                self.take()
                args = []
                while self.peek() != "}":
                    args.append(self.expr())
                    if self.peek() == ",":
                        self.take()
                self.take("}")
                return ("ctor", x, tuple(args))
            last = x.split(".")[-1]
            if nxt == "<" or last[:1].isupper() or x in ("Data", "Type"):
                if nxt == "<":
                    self.i -= 1
                    return ("ty", self.type_text())
                return ("ty", x)
            return ("var", x)
        if x == "&2" or x.startswith("&"):
            self.take()
            return ("ty", x)
        raise TermError(f"unexpected {x!r}")

    def arg(self):
        x = self.peek()
        if x and re.fullmatch(r"[A-Za-z_][\w.]*", x) and self.peek(1) == "<":
            return ("ty", self.type_text())
        return self.expr()


def parse(text: str):
    p = Parser(text)
    e = p.expr()
    if not p.done():
        raise TermError(f"trailing tokens in {text[:80]!r}")
    return e


def parse_pattern(text: str):
    """A case pattern: ('pvar', name) | ('pwild',) | ('pnat', k) | ('pnsucc', k, name) | ('pctor', name, [pats])."""
    s = text.strip()
    if s == "_":
        return ("pwild",)
    m = re.fullmatch(r"(\d+)n", s)
    if m:
        return ("pnat", int(m.group(1)))
    m = re.fullmatch(r"(\d+)n\+\+?([A-Za-z_]\w*)", s)
    if m:
        return ("pnsucc", int(m.group(1)), m.group(2))
    m = re.fullmatch(r"([A-Za-z_][\w.]*)\{(.*)\}", s, re.S)
    if m:
        from .equivalence import split_top
        return ("pctor", m.group(1), [parse_pattern(x) for x in split_top(m.group(2))])
    m = re.fullmatch(r"[+\-]?([a-z_][A-Za-z0-9_]*)", s)
    if m:
        return ("pvar", m.group(1))
    m = re.fullmatch(r"([A-Z][A-Za-z0-9_.]*)", s)
    if m:   # a constructor without braces is not Bend syntax; read as such only if braces were dropped
        raise TermError(f"unrecognised pattern {s!r}")
    raise TermError(f"unrecognised pattern {s!r}")


# ------------------------------------------------------------------ definitions
@dataclass
class Def:
    name: str
    params: list            # [(q, name, type text)]
    ret: str
    body: object            # a body node (see parse_def_body)
    kind: str = "def"


@dataclass
class TypeDecl:
    name: str
    params: list
    kind: str
    ctors: list             # [(ctor, [(field, type)])]


def _indent(ln):
    return len(ln) - len(ln.lstrip(" "))


def parse_def_body(lines: list[str]):
    """Body nodes: ("expr", term) | ("let", pattern, term, body) | ("match", [scrut names], [(pats, body)])."""
    lines = [ln for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        raise TermError("empty body")
    return _blk(lines, 0, len(lines), _indent(lines[0]))


def _blk(lines, i, j, ind):
    ln = lines[i].strip()
    if ln.startswith("match ") and ln.endswith(":"):
        scrut = ln[len("match "):-1].split()
        cases, k = [], i + 1
        while k < j:
            c = lines[k]
            cs = c.strip()
            if not cs.startswith("case ") or not cs.endswith(":"):
                raise TermError(f"unrecognised case line {cs[:80]!r}")
            from .equivalence import split_top
            pats = [parse_pattern(p) for p in split_top(cs[len("case "):-1], " ")]
            e = k + 1
            while e < j and _indent(lines[e]) > _indent(c):
                e += 1
            if e == k + 1:
                cases.append((pats, None))
            else:
                cases.append((pats, _blk(lines, k + 1, e, _indent(lines[k + 1]))))
            k = e
        return ("match", scrut, cases)
    m = re.match(r"^([+\-]?)([a-z_][A-Za-z0-9_]*) = (.*)$", ln)
    if m and i + 1 < j:
        return ("let", ("pvar", m.group(2)), parse(m.group(3)), _blk(lines, i + 1, j, ind))
    m = re.match(r"^\(([^()]*)\) = (.*)$", ln)
    if m and i + 1 < j:
        names = [x.strip().lstrip("+") for x in m.group(1).split(",")]
        return ("let", ("ptup", names), parse(m.group(2)), _blk(lines, i + 1, j, ind))
    m = re.match(r"^([A-Z][\w.]*\{[^{}]*\}) = (.*)$", ln)
    if m and i + 1 < j:
        return ("let", parse_pattern(m.group(1)), parse(m.group(2)), _blk(lines, i + 1, j, ind))
    if i + 1 != j:
        raise TermError(f"unrecognised statement {ln[:80]!r}")
    return ("expr", parse(ln))


def _split_params(s):
    from .equivalence import split_top
    out = []
    for p in split_top(s):
        q = p[0] if p[:1] in "+-~" else ""
        name, _, ty = p[len(q):].partition(":")
        out.append((q, name.strip(), ty.strip()))
    return out


def read_source(text: str, qualify: str | None = None) -> tuple[dict, dict]:
    """(defs, types) of a Bend source (Base's printout or a model). With qualify, every top-level name of the source
    is renamed <qualify>.<name> (constructors of its datatypes too) inside the bodies and in the tables."""
    raw = text.splitlines()
    blocks, cur = [], None
    for ln in raw:
        if ln.startswith(("def ", "type ", "law ")):
            cur = [ln]
            blocks.append(cur)
        elif ln[:1] not in (" ", "\t", "") and ln.strip():
            cur = None
        elif cur is not None:
            cur.append(ln)
    defs, types, laws = {}, {}, {}
    for blk in blocks:
        while blk and not blk[-1].strip():
            blk.pop()
        head = blk[0]
        try:
            if head.startswith("type "):
                m = re.match(r"type ([A-Za-z_][\w.]*)(<.*>)? is (\w+(?:\(\S+\))?):$", head)
                if not m:
                    continue
                params = _split_params(m.group(2)[1:-1]) if m.group(2) else []
                ctors = []
                for ln in blk[1:]:
                    s = ln.strip()
                    cm = re.match(r"([A-Za-z_]\w*)\{(.*)\}$", s)
                    if cm:
                        from .equivalence import split_top
                        ctors.append((cm.group(1), [tuple(x.strip() for x in f.split(":", 1))
                                                    for f in split_top(cm.group(2))]))
                types[m.group(1)] = TypeDecl(m.group(1), params, m.group(3), ctors)
                continue
            if head.startswith("law "):
                m = re.match(r"law ([A-Za-z_][\w.]*):$", head)
                if not m:
                    continue
                ps, ret = [], None
                for ln in blk[1:]:
                    s = ln.strip()
                    fm = re.match(r"for\s+([+\-~]?)([A-Za-z_]\w*)\s*:\s*(.*)$", s)
                    if fm:
                        ps.append((fm.group(1), fm.group(2), fm.group(3)))
                    elif s:
                        ret = (ret + " " + s) if ret else s
                laws[m.group(1)] = (ps, ret)
                continue
            i, hdr = 0, head
            while not _hdr_done(hdr):
                i += 1
                if i >= len(blk):
                    raise TermError("unterminated header")
                hdr += " " + blk[i].strip()
            m = re.match(r"def ([A-Za-z_][\w.]*)\((.*)\)\s*->\s*(.*):$", hdr)
            if m:
                params, ret = _split_params(m.group(2)), m.group(3).strip()
            else:
                m = re.match(r"def ([A-Za-z_][\w.]*)\((.*)\):$", hdr)
                if not m or m.group(1) not in laws:
                    continue
                ps, ret = laws[m.group(1)]
                names = [x.strip() for x in m.group(2).split(",") if x.strip()]
                params = [next(((q, n, t) for q, n, t in ps if n == nm), ("", nm, "")) for nm in names]
            body_lines = blk[i + 1:]
            if any("import " in ln for ln in body_lines[:2]):
                continue   # a foreign effect: never evaluated
            try:
                body = parse_def_body(body_lines)
            except TermError:
                body = None
            defs[m.group(1)] = Def(m.group(1), params, ret, body)
        except TermError:
            continue
    if qualify:
        names = set(defs) | set(types) | {c for t in types.values() for c, _ in t.ctors}
        q = lambda n: f"{qualify}.{n}" if n in names else n
        defs = {q(n): _qualify_def(d, names, qualify) for n, d in defs.items()}
        types = {q(n): TypeDecl(q(n), t.params, t.kind, [(q(c), [(f, _qualify_text(ft, names, qualify)) for f, ft in fs])
                                                          for c, fs in t.ctors]) for n, t in types.items()}
    return defs, types


def _hdr_done(h):
    depth = 0
    for ch in h.replace("->", "\x00\x01").replace("=>", "\x00\x01"):
        depth += ch in "<({["
        depth -= ch in ">)}]"
    return depth == 0 and h.rstrip().endswith(":")


_ID = re.compile(r"(?<![\w.$])([A-Za-z_][A-Za-z0-9_]*)(?![\w])")


def _qualify_text(s, names, qual):
    return _ID.sub(lambda m: f"{qual}.{m.group(1)}" if m.group(1) in names else m.group(1), s)


def qualify_term(t, names, qual, bound=frozenset()):
    k = t[0]
    if k == "var":
        return t
    if k in ("app", "ctor"):
        n = f"{qual}.{t[1]}" if t[1] in names else t[1]
        return (k, n, tuple(qualify_term(a, names, qual, bound) for a in t[2]))
    if k == "ty":
        return ("ty", _qualify_text(t[1], names, qual))
    if k == "tup":
        return ("tup", tuple(qualify_term(a, names, qual, bound) for a in t[1]))
    if k == "nsucc":
        return ("nsucc", t[1], qualify_term(t[2], names, qual, bound))
    return t


def _qualify_pat(p, names, qual):
    if p[0] == "pctor":
        n = f"{qual}.{p[1]}" if p[1] in names else p[1]
        return ("pctor", n, [_qualify_pat(x, names, qual) for x in p[2]])
    return p


def _qualify_body(b, names, qual):
    if b is None:
        return None
    if b[0] == "expr":
        return ("expr", qualify_term(b[1], names, qual))
    if b[0] == "let":
        return ("let", _qualify_pat(b[1], names, qual) if b[1][0] != "ptup" else b[1],
                qualify_term(b[2], names, qual), _qualify_body(b[3], names, qual))
    return ("match", b[1], [([_qualify_pat(p, names, qual) for p in ps], _qualify_body(c, names, qual))
                            for ps, c in b[2]])


def _qualify_def(d, names, qual):
    return Def(f"{qual}.{d.name}", [(q, n, _qualify_text(t, names, qual)) for q, n, t in d.params],
               _qualify_text(d.ret, names, qual), _qualify_body(d.body, names, qual))


# ------------------------------------------------------------------ evaluation
NATIVE = {}   # fast paths for U32 on literals (exact Base semantics, checked by the tests against bend)


def _u32n(f):
    def wrap(args):
        if all(a[0] == "u32" for a in args):
            return f(*[a[1] for a in args])
        return None
    return wrap


def _cmp(a, b):
    return ("ctor", "LT", ()) if a < b else ("ctor", "GT", ()) if a > b else ("ctor", "EQ", ())


def _b(x):
    return TRUE if x else FALSE


NATIVE.update({
    "U32.add": _u32n(lambda a, b: ("u32", (a + b) & MASK32)),
    "U32.sub": _u32n(lambda a, b: ("u32", (a - b) & MASK32)),
    "U32.mul": _u32n(lambda a, b: ("u32", (a * b) & MASK32)),
    "U32.and": _u32n(lambda a, b: ("u32", a & b)),
    "U32.or": _u32n(lambda a, b: ("u32", a | b)),
    "U32.xor": _u32n(lambda a, b: ("u32", a ^ b)),
    "U32.not": _u32n(lambda a: ("u32", ~a & MASK32)),
    "U32.inc": _u32n(lambda a: ("u32", (a + 1) & MASK32)),
    "U32.shl": _u32n(lambda a: ("u32", (a << 1) & MASK32)),
    "U32.shr": _u32n(lambda a: ("u32", a >> 1)),
    "U32.cmp": _u32n(lambda a, b: _cmp(a, b)),
    "U32.is_eq": _u32n(lambda a, b: _b(a == b)),
    "U32.is_lt": _u32n(lambda a, b: _b(a < b)),
    "U32.div": _u32n(lambda a, b: ("u32", a // b if b else 0)),
    "U32.mod": _u32n(lambda a, b: ("u32", a % b if b else a)),
})


def _native_shift(name):
    def f(args):
        a, n = args
        if a[0] == "u32" and n[0] == "nat":
            v = (a[1] << n[1]) & MASK32 if name == "U32.shln" else a[1] >> n[1]
            return ("u32", v)
        return None
    return f


NATIVE["U32.shln"] = _native_shift("U32.shln")
NATIVE["U32.shrn"] = _native_shift("U32.shrn")


class Evaluator:
    """Normal forms of open terms over the given definitions (Base and the pair module, qualified)."""

    def __init__(self, defs: dict, types: dict, native: bool = True, budget: int = 2_000_000):
        self.defs = defs
        self.types = types
        self.native = native
        self.budget = budget
        self.steps = 0
        self.ctor_type = {}
        for t in types.values():
            for c, fs in t.ctors:
                self.ctor_type[c] = (t.name, [f for f, _ in fs])
        self.memo: dict = {}

    # -- values
    def as_ctor(self, v, pat_name=None):
        """v as a constructor value when a pattern needs one (literals expanded), else None."""
        if v[0] == "ctor":
            return v
        if v[0] == "u32" and pat_name == "U32":
            return ("ctor", "U32", (word_of(v[1], U32_BITS),))
        if v[0] == "tup":
            return v
        return None

    def match_pat(self, p, v, env) -> bool:
        """Bind p against the value v into env; False when another constructor; raises Stuck when v is not a value."""
        k = p[0]
        if k == "pwild":
            return True
        if k == "pvar":
            env[p[1]] = v
            return True
        if k == "pnat":
            if v[0] == "nat":
                return v[1] == p[1]
            if v[0] == "nsucc":
                if v[1] > p[1]:
                    return False
                raise Stuck(v)
            raise Stuck(v)
        if k == "pnsucc":
            if v[0] == "nat":
                if v[1] < p[1]:
                    return False
                env[p[2]] = ("nat", v[1] - p[1])
                return True
            if v[0] == "nsucc":
                if v[1] >= p[1]:
                    rest = v[1] - p[1]
                    env[p[2]] = ("nsucc", rest, v[2]) if rest else v[2]
                    return True
                raise Stuck(v)
            raise Stuck(v)
        if k == "pctor":
            name = p[1]
            if v[0] == "tup" and name in ("Pair", ""):
                return all(self.match_pat(q, x, env) for q, x in zip(p[2], v[1]))
            cv = self.as_ctor(v, name)
            if cv is None:
                raise Stuck(v)
            if cv[1] != name:
                return False
            if len(cv[2]) != len(p[2]):
                raise TermError(f"arity of {name}")
            for q, x in zip(p[2], cv[2]):
                if not self.match_pat(q, x, env):
                    return False
            return True
        raise TermError(f"pattern {p!r}")

    def eval(self, t, env=None):
        env = env or {}
        k = t[0]
        if k == "var":
            return env.get(t[1], t)
        if k in ("u32", "nat", "ty"):
            return t
        if k == "nsucc":
            x = self.eval(t[2], env)
            if x[0] == "nat":
                return ("nat", x[1] + t[1])
            if x[0] == "nsucc":
                return ("nsucc", x[1] + t[1], x[2])
            return ("nsucc", t[1], x)
        if k == "tup":
            return ("tup", tuple(self.eval(a, env) for a in t[1]))
        if k == "ctor":
            return canon(("ctor", t[1], tuple(self.eval(a, env) for a in t[2])))
        if k == "app":
            args = tuple(self.eval(a, env) for a in t[2])
            return self.call(t[1], args)
        raise TermError(f"eval {t!r}")

    def call(self, f, args):
        key = (f, args)
        if key in self.memo:
            return self.memo[key]
        self.steps += 1
        if self.steps > self.budget:
            raise TermError("evaluation budget exhausted")
        out = None
        if self.native and f in NATIVE:
            out = NATIVE[f](args)
        if out is None:
            r = self.unfold(f, args)
            out = r if r is not None else ("app", f, args)
        self.memo[key] = out
        return out

    def unfold(self, f, args):
        """The body of f at args when its match tree reduces (None when stuck or opaque)."""
        d = self.defs.get(f)
        if d is None or d.body is None or len(d.params) != len(args):
            return None
        env = {n: a for (_, n, _), a in zip(d.params, args)}
        try:
            return self.run(d.body, env)
        except Stuck:
            return None

    def stuck_on(self, f, args):
        """The value a call is stuck on (the scrutinee of the first match that does not reduce), or None."""
        d = self.defs.get(f)
        if d is None or d.body is None or len(d.params) != len(args):
            return None
        env = {n: a for (_, n, _), a in zip(d.params, args)}
        try:
            self.run(d.body, env)
        except Stuck as s:
            return s.scrut
        return None

    def run(self, b, env):
        k = b[0]
        if k == "expr":
            return self.eval(b[1], env)
        if k == "let":
            v = self.eval(b[2], env)
            env = dict(env)
            p = b[1]
            if p[0] == "ptup":
                if v[0] != "tup":
                    raise Stuck(v)
                for n, x in zip(p[1], v[1]):
                    env[n] = x
            elif not self.match_pat(p, v, env):
                raise TermError("refutable let")
            return self.run(b[3], env)
        if k == "match":
            vals = [env.get(s, ("var", s)) for s in b[1]]
            for pats, body in b[2]:
                e2 = dict(env)
                ok = True
                for p, v in zip(pats, vals):
                    if not self.match_pat(p, v, e2):
                        ok = False
                        break
                if ok:
                    if body is None:
                        raise TermError("empty case reached")
                    return self.run(body, e2)
            raise TermError("no case matches")
        raise TermError(f"body {k}")

    def nf(self, t):
        return self.eval(t, {})
