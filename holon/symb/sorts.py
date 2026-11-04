"""K2: the members' nominal sorts. A register path ("family" or "family.member") takes the value sort Time or Idx, and a
map family the key domain Idx, by a fixed point over the members' documents:

  a term is Time when it is env block.timestamp, a read of a Time register, a call answer whose callee action's return
  term is Time (the callee resolved through the bundle's members by interface), or a conditional whose two values are
  Time; Idx when it is the length of a storage array, a read of an Idx register, a call answer whose callee's return is
  Idx, a trunc of an Idx term, or an Idx term plus a constant;
  a register takes a sort when some write stores a term of it there or some comparison sets it against one;
  a map family's key domain is Idx when some write or read indexes it with an Idx term.

  gen/<M>/symb/sorts.json   {"symb_version", "members": {member: {"time", "idx", "idx_keys"}}}
"""
from __future__ import annotations

from . import SYMB_VERSION, Ctx

CMP = frozenset(("==", "!=", "<", "<=", ">", ">="))


def _iter(e):
    stack = [e]
    while stack:
        x = stack.pop()
        yield x
        if isinstance(x, list):
            stack.extend(reversed(x))
        elif isinstance(x, dict):
            stack.extend(reversed(list(x.values())))


def register_of(e) -> str | None:
    """The register a read term names: a scalar family, a map family's value, or a member of a map's struct value."""
    if not isinstance(e, list) or not e:
        return None
    if e[0] == "storage" and len(e) == 2 and isinstance(e[1], str):
        return e[1]
    if e[0] == "map" and len(e) == 3 and isinstance(e[1], list) and e[1][:1] == ["storage"] and isinstance(e[1][1], str):
        return e[1][1]
    if e[0] == "member" and len(e) == 3 and isinstance(e[2], str):
        inner = register_of(e[1])
        if inner and "." not in inner and isinstance(e[1], list) and e[1][:1] == ["map"]:
            return f"{inner}.{e[2]}"
    return None


def written(doc: dict):
    """(register path, value term) for every write: a whole value, a struct literal's member, or a member an update
    term sets in a struct written back."""
    for a in doc["actions"]:
        for w in a.get("writes") or []:
            fam, v = w.get("family"), w.get("value")
            if not isinstance(fam, str):
                continue
            if isinstance(v, list) and v[:1] == ["struct"] and len(v) == 3:
                for name, val in v[2]:
                    yield f"{fam}.{name}", val
                continue
            yield fam, v
            for x in _iter(v):
                if isinstance(x, list) and len(x) == 4 and x[0] == "update":
                    mem = x[2] if isinstance(x[2], str) else (x[2][-1] if isinstance(x[2], list) and
                                                               x[2][:1] == ["member"] else None)
                    if isinstance(mem, str):
                        yield f"{fam}.{mem}", x[3]


def decided(a: dict):
    """The terms a comparison of an action can decide in: guards, checks, a view's return, writes' conditions and
    values."""
    for g in a.get("guards") or []:
        yield g.get("expr")
    for c in a.get("checks") or []:
        yield c.get("expr")
    if a.get("mutability") in ("view", "pure"):
        yield a.get("returns")
    for w in a.get("writes") or []:
        yield w.get("cond")
        yield w.get("value")


class Solver:
    def __init__(self, docs: dict, iface_member: dict):
        self.docs = docs
        self.iface = iface_member
        self.time = {m: set() for m in docs}
        self.idx = {m: set() for m in docs}
        self.keys = {m: set() for m in docs}
        self.returns = {m: {a["name"]: a.get("returns") for a in d["actions"]} for m, d in docs.items()}

    def _callee(self, name: str):
        iface, _, fn = name.partition(".")
        m = self.iface.get(iface)
        return (m, self.returns[m].get(fn)) if m in self.returns else (None, None)

    def sort(self, m: str, e, depth: int = 0) -> str | None:
        if depth > 16 or not isinstance(e, list) or not e:
            return None
        if e == ["env", "block.timestamp"]:
            return "time"
        r = register_of(e)
        if r is not None:
            return "time" if r in self.time[m] else ("idx" if r in self.idx[m] else None)
        h = e[0]
        if h == "len" and len(e) == 2 and isinstance(e[1], list) and e[1][:1] == ["storage"]:
            return "idx"
        if h == "call" and len(e) >= 2 and isinstance(e[1], str):
            cm, ret = self._callee(e[1])
            return self.sort(cm, ret, depth + 1) if cm and ret is not None else None
        if h == "?" and len(e) == 4:
            a, b = self.sort(m, e[2], depth + 1), self.sort(m, e[3], depth + 1)
            return a if a == b == "time" else None
        if h == "trunc" and len(e) == 3:
            return "idx" if self.sort(m, e[2], depth + 1) == "idx" else None
        if h == "+" and len(e) == 3:
            for t, c in ((e[1], e[2]), (e[2], e[1])):
                if isinstance(c, int) and not isinstance(c, bool) and self.sort(m, t, depth + 1) == "idx":
                    return "idx"
        return None

    def _set(self, m: str, path: str, s: str | None) -> bool:
        tab = {"time": self.time, "idx": self.idx}.get(s)
        if tab is None or path in tab[m]:
            return False
        tab[m].add(path)
        return True

    def solve(self) -> None:
        changed = True
        while changed:
            changed = False
            for m, d in self.docs.items():
                for path, v in written(d):
                    changed |= self._set(m, path, self.sort(m, v))
                for a in d["actions"]:
                    for e in decided(a):
                        for x in _iter(e):
                            if isinstance(x, list) and len(x) == 3 and x[0] in CMP:
                                for reg, other in ((x[1], x[2]), (x[2], x[1])):
                                    p = register_of(reg)
                                    if p is not None and not isinstance(other, int):
                                        changed |= self._set(m, p, self.sort(m, other))
                    for e in [a.get(k) for k in ("guards", "checks", "returns", "writes", "post")]:
                        for x in _iter(e):
                            if not isinstance(x, list) or not x:
                                continue
                            if x[0] == "map" and len(x) == 3 and isinstance(x[1], list) and x[1][:1] == ["storage"] \
                                    and isinstance(x[1][1], str) and self.sort(m, x[2]) == "idx" \
                                    and x[1][1] not in self.keys[m]:
                                self.keys[m].add(x[1][1])
                                changed = True
                            if x[0] == "store" and len(x) == 4 and isinstance(x[1], list) and x[1][:1] == ["storage"] \
                                    and isinstance(x[2], list):
                                for k in x[2]:
                                    if isinstance(k, list) and len(k) == 2 and k[0] == "map" and \
                                            self.sort(m, k[1]) == "idx" and x[1][1] not in self.keys[m]:
                                        self.keys[m].add(x[1][1])
                                        changed = True


def members_sorts(ctx: Ctx) -> dict:
    names = sorted(ctx.side["members"])
    docs = {n: ctx.bundle.load(ctx.side["members"][n]["document"]) for n in names}
    iface = {}
    for n in names:
        c = docs[n].get("contract")
        if isinstance(c, str):
            iface[c] = n
            iface[f"I{c}"] = n
    # interfaces the members' calls name (the bundle's wiring: an interface whose name is a member's contract's)
    for n in names:
        for a in docs[n]["actions"]:
            for call in a.get("calls") or []:
                fn = call.get("fn") if isinstance(call, dict) else None
                if isinstance(fn, str) and "." in fn:
                    it = fn.split(".", 1)[0]
                    for c, mn in list(iface.items()):
                        if it != c and it.startswith("I") and c.startswith(it[1:]):
                            iface.setdefault(it, mn)
    s = Solver(docs, iface)
    s.solve()
    return {"symb_version": SYMB_VERSION,
            "members": {n: {"time": sorted(s.time[n]), "idx": sorted(s.idx[n]), "idx_keys": sorted(s.keys[n])}
                        for n in names}}


def main(ctx: Ctx, check: bool, log) -> int:
    from ..bundle import render, write_or_check
    doc = members_sorts(ctx)
    for n, v in doc["members"].items():
        log(f"{n}: time {v['time']}, idx {v['idx']}, idx keys {v['idx_keys']}")
    return write_or_check(ctx.bundle, {ctx.out("sorts.json"): render(doc)}, check, log=log)
