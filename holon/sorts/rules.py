"""Affine rules (§7.2), comparison rules, union reads (§7.4), principal/amount (§7.5), width (§7.6).

combine(op, a, b) returns (result_sort, note) or raises IllSorted. Signed results (Dur-, Cnt[k]-) are
differences that may be negative: realizing one in an unsigned machine word is a `realize` obligation
(§7.8); the machine model's truncated `-` is exactly that realization.
"""
from __future__ import annotations

from .grammar import BOOL, MACH, NULL, Sort, members, union


class IllSorted(Exception):
    pass


def is_literal(s: Sort) -> bool:
    return s.kind == "Mach"


def same_base(a: Sort, b: Sort) -> bool:
    return (a.kind, a.arg) == (b.kind, b.arg)


def _add(a: Sort, b: Sort) -> Sort:
    if is_literal(a) and is_literal(b):
        return MACH
    if is_literal(a):          # a literal added to a point is a unit displacement (1 second, 1 index)
        return _add(b, a)
    if is_literal(b):
        if a.kind in ("Time", "Dur", "Idx", "Cnt", "Amt"):
            return a.unsigned() if a.kind != "Dur" or not a.signed else a
        raise IllSorted(f"{a} + literal")
    if a.kind == "Time" and b.kind == "Dur" or a.kind == "Dur" and b.kind == "Time":
        return Sort("Time")
    if a.kind == "Dur" and b.kind == "Dur":
        return Sort("Dur", signed=a.signed or b.signed)
    if a.kind == "Idx" and b.kind == "Cnt" and a.arg == b.arg or a.kind == "Cnt" and b.kind == "Idx" and a.arg == b.arg:
        return Sort("Idx", a.arg)
    if a.kind == "Cnt" and b.kind == "Cnt" and a.arg == b.arg:
        return Sort("Cnt", a.arg, a.signed or b.signed)
    if a.kind == "Amt" and b.kind == "Amt" and a.arg == b.arg:
        return a
    raise IllSorted(f"{a} + {b}")


def _sub(a: Sort, b: Sort) -> Sort:
    if is_literal(a) and is_literal(b):
        return MACH
    if is_literal(b):
        if a.kind in ("Time", "Idx"):
            return a                          # point minus a unit displacement: still a point (may underflow: obligation)
        if a.kind in ("Dur", "Cnt", "Amt"):
            return a.with_signed() if a.kind != "Amt" else a
        raise IllSorted(f"{a} - literal")
    if is_literal(a):
        raise IllSorted(f"literal - {b}")
    if a.kind == "Time" and b.kind == "Time":
        return Sort("Dur", signed=True)       # the difference of two points may be negative
    if a.kind == "Time" and b.kind == "Dur":
        return Sort("Time")
    if a.kind == "Dur" and b.kind == "Dur":
        return Sort("Dur", signed=True)
    if a.kind == "Idx" and b.kind == "Idx" and a.arg == b.arg:
        return Sort("Cnt", a.arg, True)
    if a.kind == "Idx" and b.kind == "Cnt" and a.arg == b.arg:
        return Sort("Idx", a.arg)
    if a.kind == "Cnt" and b.kind == "Cnt" and a.arg == b.arg:
        return Sort("Cnt", a.arg, True)
    if a.kind == "Amt" and b.kind == "Amt" and a.arg == b.arg:
        return a
    raise IllSorted(f"{a} - {b}")


def combine(op: str, a: Sort, b: Sort) -> Sort:
    """Arithmetic over unions distributes over members (an ill-sorted member is an obligation, not a crash)."""
    if a.kind == "Union" or b.kind == "Union":
        outs = []
        for x in members(a):
            for y in members(b):
                if x.kind == "Null" or y.kind == "Null":
                    continue
                outs.append(combine(op, x, y))
        if not outs:
            raise IllSorted(f"{a} {op} {b}")
        return union(*outs)
    if a.kind == "Null" or b.kind == "Null":
        raise IllSorted(f"{a} {op} {b}: Null in arithmetic")
    if op == "+":
        return _add(a, b)
    if op == "-":
        return _sub(a, b)
    if op == "*":
        if is_literal(a) and a.kind == "Mach":
            return b
        if is_literal(b):
            return a
        raise IllSorted(f"{a} * {b}")
    raise IllSorted(op)


def compare(op: str, a: Sort, b: Sort) -> dict | None:
    """Comparison / equality. Returns None when well-sorted, else an obligation descriptor:
       sentinel  a point sort (Time, Prin, Dig, Idx of a family with a real index 0 excepted) tested against a literal
       mismatch  two different base sorts compared."""
    if is_literal(a) and is_literal(b):
        return None
    if is_literal(a):
        return compare(op, b, a)
    if is_literal(b):
        la = {m for m in members(a) if m.kind != "Null"}
        kinds = {m.kind for m in la}
        if kinds & {"Time", "Prin", "Dig"} and op in ("==", "!=", ">", "<=") :
            # Time and Prin have no distinguished 0: `t != 0` / `t > 0` is a sentinel (SYM-tau / SYM-pi, §7.4).
            # Dig: 0 = bytes32(0) is the storage default, a sentinel too (reported, lower severity).
            return {"obligation": "sentinel", "sort": str(a), "literal_op": op}
        return None
    norm = lambda m: ("Idx" if m.kind == "Cnt" else m.kind, m.arg)   # Idx[k] and Cnt[k] compare (zero-based indices)
    ma = {norm(m) for m in members(a) if m.kind != "Null"}
    mb = {norm(m) for m in members(b) if m.kind != "Null"}
    if ma & mb:
        return None
    if {m.kind for m in members(a)} == {"Prin"} and {m.kind for m in members(b)} == {"Prin"}:
        return None                       # a role check (authorization), §7.5
    return {"obligation": "mismatch", "left": str(a), "right": str(b)}


def read_at(reg_sort: Sort, expected: Sort) -> dict | None:
    """A union-sorted register read at a member sort (§7.4, Prop 6.19): a ghost-tag obligation."""
    if reg_sort.kind != "Union":
        return None
    if any(same_base(m, expected) for m in reg_sort.members):
        others = [str(m) for m in reg_sort.members if not same_base(m, expected)]
        return {"obligation": "union_read", "sort": str(reg_sort), "expected": str(expected), "others": others}
    return None


def width_of_sum(ws: list[int | None]) -> int | None:
    """Width rule (§7.6): a sum of terms of widths w_i needs max(w_i) + (k - 1) bits in the worst case."""
    if any(w is None for w in ws):
        return None
    return max(ws) + (len(ws) - 1)


def width_obligation(expr_width: int | None, realized: int | None) -> dict | None:
    if expr_width is None or realized is None or expr_width <= realized:
        return None
    return {"obligation": "width", "needed": expr_width, "realized": realized, "bound": 2 ** realized}


def realize_obligation(s: Sort) -> dict | None:
    """A signed difference realized in an unsigned machine word (§7.8 `realize`)."""
    if s.kind in ("Dur", "Cnt") and s.signed:
        return {"obligation": "realize", "sort": str(s), "unsigned": str(s.unsigned())}
    return None


def principal_obligations(role_writes: dict) -> list[dict]:
    """§7.5: a Prin register whose writers include the literal 0 (address(0)) is Prin[role]+Null."""
    out = []
    for reg, ws in sorted(role_writes.items()):
        if any(w.kind == "Null" for w in ws) and any(w.kind == "Prin" for w in ws):
            out.append({"obligation": "null_principal", "register": reg, "writers": sorted(str(w) for w in ws)})
    return out


__all__ = ["IllSorted", "combine", "compare", "read_at", "width_of_sum", "width_obligation",
           "realize_obligation", "principal_obligations", "BOOL", "NULL"]
