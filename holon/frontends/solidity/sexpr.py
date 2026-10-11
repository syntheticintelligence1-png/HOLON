"""Shared helpers for the holon-facts/0.2 expression DSL and normalization.

Facts expressions (consumed by holon/gen/machine.py `ex`):
  scalars: int / bool / string(var or param)
  [op, a, b ...]: + - * / < <= > >= == !=  (Nat), && || ! (Bool), ? (ite),
  call <name-or-list> <args...>, get <rec> <field>, mk <T> {f:e}, with <T> <rec> {f:e},
  list <elems...>

`normalize` + `simplify` give a canonical form used BOTH to pretty-extract
expressions and by the differ (tests_m2) to compare hand vs extracted terms.
The normalizations are semantics-preserving rewrites only.
"""

# ---------------------------------------------------------------- helpers

def C(name, *args):
    return ["call", name, *args]

def get(rec, field):
    return ["get", rec, field]

def ite(c, a, b):
    return ["?", c, a, b]

def AND(*xs):
    xs = [x for x in xs if x is not True]
    if not xs:
        return True
    if len(xs) == 1:
        return xs[0]
    return ["&&", *xs]

def OR(*xs):
    xs = [x for x in xs if x is not False]
    if not xs:
        return False
    if len(xs) == 1:
        return xs[0]
    return ["||", *xs]

def NOT(x):
    return ["!", x]

def eq(a, b):
    return ["==", a, b]

def neq(a, b):
    return ["!=", a, b]

def is_var(e):
    return isinstance(e, str)

def is_call(e, name=None):
    return isinstance(e, list) and len(e) >= 1 and e[0] == "call" and (name is None or e[1] == name)

def call_name(e):
    return e[1] if is_call(e) else None

def call_args(e):
    return e[2:] if is_call(e) else []

# ---------------------------------------------------------------- simplifier
# Small, semantics-preserving rewrite system run on emitted terms.

def simplify(e):
    if not isinstance(e, list):
        return e
    if e and e[0] in ("call", "get"):
        return e  # calls/gets: simplify args? keep shallow for determinism
    op = e[0]
    if op == "!":
        x = simplify(e[1])
        return _neg(x)
    if op == "&&":
        xs = [simplify(x) for x in e[1:]]
        return _and(xs)
    if op == "||":
        xs = [simplify(x) for x in e[1:]]
        return _or(xs)
    if op == "?":
        c, a, b = simplify(e[1]), simplify(e[2]), simplify(e[3])
        if a is True and b is False:
            return c
        if a is False and b is True:
            return _neg(c)
        if a == b:
            return a
        if a is True:
            return _or([c, b])
        if a is False:
            return _and([_neg(c), b])
        if b is True:
            return _or([_neg(c), a])
        if b is False:
            return _and([c, a])
        return ["?", c, a, b]
    return [op, *[simplify(x) for x in e[1:]]]


def _flat(op, xs):
    out = []
    for x in xs:
        if isinstance(x, list) and x and x[0] == op:
            out.extend(x[1:])
        else:
            out.append(x)
    return out


def _and(xs):
    xs = _flat("&&", xs)
    xs = [x for x in xs if x is not True]
    if any(x is False for x in xs):
        return False
    # a && (!a || b) -> a && b   (complement absorption inside disjuncts)
    conj = {repr(x): x for x in xs}
    out = []
    for x in xs:
        if isinstance(x, list) and x and x[0] == "||":
            parts = [p for p in x[1:] if not (isinstance(p, list) and p and p[0] == "!" and repr(p[1]) in conj)]
            if len(parts) < len(x[1:]):
                x = _or(parts) if parts else False
                if x is True:
                    continue
        out.append(x)
    xs = _flat("&&", out)
    xs = [x for x in xs if x is not True]
    if not xs:
        return True
    if len(xs) == 1:
        return xs[0]
    return ["&&", *xs]


def _or(xs):
    xs = _flat("||", xs)
    xs = [x for x in xs if x is not False]
    if any(x is True for x in xs):
        return True
    disj = {repr(x): x for x in xs}
    out = []
    for x in xs:
        if isinstance(x, list) and x and x[0] == "&&":
            parts = [p for p in x[1:] if not (isinstance(p, list) and p and p[0] == "!" and repr(p[1]) in disj)]
            if len(parts) < len(x[1:]):
                x = _and(parts) if parts else True
                if x is False:
                    continue
        out.append(x)
    xs = _flat("||", out)
    xs = [x for x in xs if x is not False]
    if not xs:
        return False
    if len(xs) == 1:
        return xs[0]
    return ["||", *xs]


def _neg(x):
    if isinstance(x, bool):
        return not x
    if isinstance(x, list) and x:
        op = x[0]
        if op == "!":
            return x[1]
        if op == "&&":
            return _or([_neg(a) for a in x[1:]])
        if op == "||":
            return _and([_neg(a) for a in x[1:]])
        if op == "!=":
            return ["==", x[1], x[2]]
        if op == "==":
            return ["!=", x[1], x[2]]
        if op == "<":
            return [">=", x[1], x[2]]
        if op == ">=":
            return ["<", x[1], x[2]]
        if op == ">":
            return ["<=", x[1], x[2]]
        if op == "<=":
            return [">", x[1], x[2]]
    return ["!", x]


# ---------------------------------------------------------------- normalizer
# Canonical form for comparison: commutative operand sort, flat &&/||, negation pushed in.

def _key(e):
    return repr(e)

def normalize(e):
    if not isinstance(e, list) or not e:
        return e
    op = e[0]
    if op == "!":
        r = _neg(normalize(e[1]))
        if isinstance(r, list) and r and r[0] == "!":
            return r
        return normalize(r) if isinstance(r, list) else r
    if op in ("&&", "||"):
        xs = _flat(op, [normalize(x) for x in e[1:]])
        xs = sorted(xs, key=_key)
        return [op, *xs] if len(xs) > 1 else (xs[0] if xs else (True if op == "&&" else False))
    if op in ("==", "!="):
        a, b = normalize(e[1]), normalize(e[2])
        if _key(b) < _key(a):
            a, b = b, a
        return [op, a, b]
    if op in ("<", "<=", ">", ">="):
        a, b = normalize(e[1]), normalize(e[2])
        # canonical: strict/weak lower-bound forms only; < and <= flip to > and >=
        if op == "<":
            return [">", b, a]
        if op == "<=":
            return [">=", b, a]
        return [op, a, b]
    if op == "get" and len(e) == 3 and e[2] is None:
        return normalize(e[1])
    if op == "?":
        return ["?", normalize(e[1]), normalize(e[2]), normalize(e[3])]
    return [normalize(x) for x in e]
