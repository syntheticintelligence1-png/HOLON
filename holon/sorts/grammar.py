"""Sort grammar (whitepaper §7.1).

  sigma ::= Mach(w) | Time | Dur^± | Idx[k] | Cnt[k]^± | Prin[role] | Amt[asset] | Dig[kind] | Ver | Bool
          | sigma_1 + sigma_2 (untagged union) | <fields> (record) | List<sigma>
Text form: Mach(256)  Time  Dur  Dur-  Idx[batch]  Cnt[msg]  Cnt[msg]-  Prin[submitter]  Amt[eth]  Dig[root]  Ver
Bool  Null (the literal-0 member of a union)  A+B  List<A>.  A width suffix @w (e.g. Cnt[msg]@16) is the
realization width of the register (§7.6); it is carried separately from the sort.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, order=True)
class Sort:
    kind: str                 # Mach Time Dur Idx Cnt Prin Amt Dig Ver Bool Null Union List Record
    arg: str = ""             # family / role / asset / kind; Mach: width as str
    signed: bool = False      # Dur^± / Cnt^± (a difference that may be negative)
    members: tuple = field(default_factory=tuple)   # Union members (sorted, deduplicated) / List element / Record fields

    def __str__(self) -> str:
        return pretty(self)

    @property
    def is_quantity(self) -> bool:
        return self.kind in ("Time", "Dur", "Idx", "Cnt", "Amt", "Mach")

    def unsigned(self) -> "Sort":
        return Sort(self.kind, self.arg, False, self.members)

    def with_signed(self) -> "Sort":
        return Sort(self.kind, self.arg, True, self.members)


MACH = Sort("Mach", "256")
TIME = Sort("Time")
DUR = Sort("Dur")
SDUR = Sort("Dur", signed=True)
VER = Sort("Ver")
BOOL = Sort("Bool")
NULL = Sort("Null")


def mach(w: int = 256) -> Sort:
    return Sort("Mach", str(w))


def idx(k: str) -> Sort:
    return Sort("Idx", k)


def cnt(k: str, signed: bool = False) -> Sort:
    return Sort("Cnt", k, signed)


def prin(role: str) -> Sort:
    return Sort("Prin", role)


def amt(asset: str) -> Sort:
    return Sort("Amt", asset)


def dig(kind: str) -> Sort:
    return Sort("Dig", kind)


def lst(elem: Sort) -> Sort:
    return Sort("List", members=(elem,))


def record(fields: dict) -> Sort:
    return Sort("Record", members=tuple(sorted(fields.items())))


def union(*ss: Sort) -> Sort:
    """Untagged union (§7.4): flattened, deduplicated, canonically ordered; a singleton collapses."""
    mem: set = set()
    for s in ss:
        if s.kind == "Union":
            mem.update(s.members)
        else:
            mem.add(s)
    if len(mem) == 1:
        return next(iter(mem))
    return Sort("Union", members=tuple(sorted(mem)))


def members(s: Sort) -> tuple:
    return s.members if s.kind == "Union" else (s,)


def pretty(s: Sort) -> str:
    if s.kind == "Mach":
        return f"Mach({s.arg})"
    if s.kind in ("Time", "Ver", "Bool", "Null"):
        return s.kind
    if s.kind == "Dur":
        return "Dur-" if s.signed else "Dur"
    if s.kind in ("Idx", "Cnt", "Prin", "Amt", "Dig"):
        return f"{s.kind}[{s.arg}]" + ("-" if s.signed else "")
    if s.kind == "Union":
        return "+".join(pretty(m) for m in s.members)
    if s.kind == "List":
        return f"List<{pretty(s.members[0])}>"
    if s.kind == "Record":
        return "<" + ", ".join(f"{k}: {pretty(v)}" for k, v in s.members) + ">"
    raise ValueError(s.kind)


def parse(text: str) -> Sort:
    """Parse the text form (no record literals)."""
    t = text.strip()
    if "+" in t and not t.startswith("List<"):
        return union(*(parse(p) for p in t.split("+")))
    if t.startswith("List<") and t.endswith(">"):
        return lst(parse(t[5:-1]))
    if t.startswith("Mach(") and t.endswith(")"):
        return mach(int(t[5:-1]))
    if t in ("Time", "Ver", "Bool", "Null"):
        return Sort(t)
    if t in ("Dur", "Dur-"):
        return Sort("Dur", signed=t.endswith("-"))
    for k in ("Idx", "Cnt", "Prin", "Amt", "Dig"):
        if t.startswith(k + "[") and (t.endswith("]") or t.endswith("]-")):
            signed = t.endswith("-")
            inner = t[len(k) + 1:-2 if signed else -1]
            if k in ("Prin", "Amt", "Dig") and signed:
                raise ValueError(f"{k} has no signed form: {text}")
            return Sort(k, inner, signed)
    raise ValueError(f"cannot parse sort {text!r}")


def parse_seed(text: str) -> tuple[Sort, int | None]:
    """`Cnt[msg]@16` -> (Cnt[msg], 16); the width is the realization width of the register."""
    if "@" in text:
        s, w = text.rsplit("@", 1)
        return parse(s), int(w)
    return parse(text), None
