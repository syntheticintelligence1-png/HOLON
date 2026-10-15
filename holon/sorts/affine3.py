"""Affine action contexts in the M3 model (A30; the evaluation shape of holon.sorts.model3's machine for the BendTT kernel).

The kernel (bend2/bendtt.lean, Term.val) normalizes every argument of a reusable (`+`, q=2) binder of a closed term
before binding it: it walks the whole value, whether it is already a normal form or not. An action's context record
X_<a> holds the step's storage, overlay, arguments, environment and hash tables, whose bytes and words are bit vectors
in the kernel, so a reusable context binder costs a walk of all of them; the I30 model bound the context reusably in
every statement, check, write, event and call guard, and those walks were about 98% of the kernel's work on a step (the
A30 diagnosis in docs/iterations/I30.md).

`affine(text)` rewrites every definition of the generated machine that takes a context `+v: X_<a>`:
  - the binder becomes affine (`v: X_<a>`), so passing the context on costs nothing;
  - each leaf block (a branch with no further match) that reads fields of v through the getters gx_<a>_<f>(v), or uses
    v more than once, opens v once (`match v: case X_<a>{..}:`) and binds each field with its exact quantity: `+` for a
    field used twice or more in the block (counting every bare use of v, which becomes the record rebuilt from its
    fields), affine for a field used once, `_` for a field the block never uses;
  - a definition whose context is used outside its leaf blocks (a let above a match) is left as it was.
The rewrite changes no value: a getter call is replaced by the field it projects and a bare use of v by the record
rebuilt from the same fields, so the compiled model computes exactly what the I30 model computed (R5 re-checks it). The
context's fields stay normal forms: they are only ever set through the setters' reusable value binder, the initial
context's reusable binders, or a rebuild from an opened context.
"""
from __future__ import annotations

import re
from collections import Counter

_DEF = re.compile(r"^def (\w+)\((.*)\) -> (.*):$")
_TYPE = re.compile(r"(?m)^type (X_\w+) is Data:\n  \1\{(.*)\}$")


def split_params(s: str) -> list[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
            continue
        depth += ch in "<({["
        depth -= ch in ">)}]"
        cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def context_records(text: str) -> dict:
    """{X_<a>: [field names]} of the context records the machine declares."""
    out = {}
    for name, body in _TYPE.findall(text):
        out[name] = [p.partition(":")[0].strip() for p in split_params(body)]
    return out


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse(lines: list, i: int, ind: int):
    items = []
    while i < len(lines) and lines[i].strip() and _indent(lines[i]) == ind:
        ln = lines[i]
        if ln.strip().startswith("match ") and ln.rstrip().endswith(":"):
            i += 1
            arms = []
            while i < len(lines) and _indent(lines[i]) == ind + 2 and lines[i].strip().startswith("case "):
                case = lines[i]
                blk, i = _parse(lines, i + 1, ind + 4)
                arms.append((case, blk))
            items.append(("match", ln, arms))
        else:
            items.append(("line", ln))
            i += 1
    return items, i


def _emit(items: list) -> list:
    out = []
    for it in items:
        if it[0] == "line":
            out.append(it[1])
        else:
            out.append(it[1])
            for case, blk in it[2]:
                out.append(case)
                out += _emit(blk)
    return out


def _shift(lines: list, n: int) -> list:
    return [" " * n + ln for ln in lines]


class _Ctx:
    def __init__(self, v: str, rec: str, fields: list):
        self.v, self.rec, self.fields = v, rec, fields
        ba = rec[len("X_"):]
        self.getter = re.compile(re.escape(f"gx_{ba}_") + r"(\w+?)\(" + re.escape(v) + r"\)")
        self.bare = re.compile(r"(?<![\w.])" + re.escape(v) + r"(?![\w])")

    def counts(self, lines: list) -> tuple[Counter, int]:
        g, b = Counter(), 0
        for ln in lines:
            fs = self.getter.findall(ln)
            g.update(f for f in fs if f in self.fields)
            b += len(self.bare.findall(self.getter.sub("", ln)))
        return g, b

    def var(self, f: str) -> str:
        return f"{self.v}_{f}"

    def leaf(self, items: list, ind: int) -> list:
        lines = [it[1] for it in items]
        g, b = self.counts(lines)
        if not g and b <= 1:
            return items
        rebuilt = f"{self.rec}{{{', '.join(self.var(f) for f in self.fields)}}}"
        pat = []
        for f in self.fields:
            n = g.get(f, 0) + b
            pat.append("_" if n == 0 else (("+" if n >= 2 else "") + self.var(f)))
        body = []
        for ln in lines:
            ln = self.getter.sub(lambda m: self.var(m.group(1)) if m.group(1) in self.fields else m.group(0), ln)
            ln = self.bare.sub(rebuilt, ln)
            body.append(ln)
        sp = " " * ind
        out = [("line", f"{sp}match {self.v}:"), ("line", f"{sp}  case {self.rec}{{{', '.join(pat)}}}:")]
        out += [("line", "    " + ln) for ln in body]
        return out

    def outside_leaves(self, items: list) -> bool:
        """Is v used in a line of a block that also holds a match, or in a match head?"""
        has_match = any(it[0] == "match" for it in items)
        for it in items:
            if it[0] == "line":
                if has_match and self.bare.search(it[1]):
                    return True
            else:
                if self.bare.search(it[1]):
                    return True
                for _case, blk in it[2]:
                    if self.outside_leaves(blk):
                        return True
        return False

    def rewrite(self, items: list, ind: int) -> list:
        if not any(it[0] == "match" for it in items):
            return self.leaf(items, ind)
        out = []
        for it in items:
            if it[0] == "line":
                out.append(it)
            else:
                out.append(("match", it[1], [(case, self.rewrite(blk, ind + 4)) for case, blk in it[2]]))
        return out


def affine_def(block: str, recs: dict) -> str:
    lines = block.split("\n")
    m = _DEF.match(lines[0])
    if not m:
        return block
    name, params, ret = m.groups()
    ps = split_params(params)
    ctx = []
    for i, p in enumerate(ps):
        q, _, ty = p.partition(":")
        q, ty = q.strip(), ty.strip()
        if q.startswith("+") and ty in recs:
            ctx.append((i, q[1:], ty))
    if not ctx:
        return block
    body = lines[1:]
    trail = []
    while body and not body[-1].strip():
        trail.append(body.pop())
    items, j = _parse(body, 0, 2)
    if j != len(body):
        return block                      # a shape this rewrite does not read: left as it was
    for i, v, ty in ctx:
        c = _Ctx(v, ty, recs[ty])
        if c.outside_leaves(items):
            continue
        items = c.rewrite(items, 2)
        ps[i] = f"{v}: {ty}"
    head = f"def {name}({', '.join(ps)}) -> {ret}:"
    return "\n".join([head] + _emit(items) + list(reversed(trail)))


def affine(text: str) -> str:
    """The model text with every context binder affine and every context read through an opened record."""
    recs = context_records(text)
    if not recs:
        return text
    out, cur = [], []

    def flush():
        if cur:
            out.append(affine_def("\n".join(cur), recs) if cur[0].startswith("def ") else "\n".join(cur))
            cur.clear()
    for ln in text.split("\n"):
        if ln.startswith("def ") or (ln and not ln.startswith(" ")):
            flush()
        cur.append(ln)
    flush()
    return "\n".join(out)
