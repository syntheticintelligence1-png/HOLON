"""Layout algebra (whitepaper §10.2, Appendix C).

A layout maps each output byte of an encoder to ["field", name, k], ["const", v] or
["unknown"] (dirty EVM memory). Writes are applied in program order, so later writes
override earlier ones; equality of two layouts is decidable in O(length).

Getter recovery (§10.2, "Getters recover a field iff its positions map to it in order"; rule E1 of
the evidence calculus, BUILD_PLAN I14): `recovers(layout, getter)` and, for one encoder, decoder and
version, `evidence(...)`.
"""
from __future__ import annotations

from . import facts as F


def layout(facts: dict, fn: str, version: int) -> list[list]:
    f = facts["functions"][fn]
    w = F.widths(facts)
    if f["lang"] == "solidity-evm-memory":
        length = f["length_by_version"][str(version)]
        mem: list[list] = [["unknown"] for _ in range(F.evm_memory_size(f, w))]
    elif f["lang"] == "go-bytes":
        length = f["length"]
        mem = [["const", 0] for _ in range(length)]
    else:
        raise ValueError(f"{fn}: unsupported encoder language {f['lang']}")
    for op in f["ops"]:
        if not F.when_ok(op.get("when"), version):
            continue
        cells = F.src_cells(op["src"], w)
        F.check_op_width(fn, op, len(cells))
        o = op["offset"]
        if o + len(cells) > len(mem):
            raise ValueError(f"{fn}: write at {o}+{len(cells)} exceeds buffer of {len(mem)}")
        mem[o:o + len(cells)] = [list(c) for c in cells]
    return [list(c) for c in mem[:length]]


def diff(a: list[list], b: list[list]) -> list[int]:
    """Positions where two layouts differ (including a length mismatch)."""
    out = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    out += list(range(min(len(a), len(b)), max(len(a), len(b))))
    return out


def recovers(layout: list[list], getter: dict) -> bool:
    """Whether a getter (a decoder's {"name", "offset", "width"}) recovers its field from a layout: every
    position offset + k, k < width, exists and maps to ["field", name, k]. A constant, an unknown byte,
    another field's byte, a byte of the field out of order, or a position past the end breaks it."""
    o, w, name = getter["offset"], getter["width"], getter["name"]
    return o + w <= len(layout) and all(list(layout[o + k]) == ["field", name, k] for k in range(w))


def evidence(facts: dict, encoder: str, decoder: str, version: int) -> dict:
    """Rule E1 for one encoder, one decoder (facts function names) and one version: the decoder's getters
    active at that version (their "when" holds) split, in getter order, into those that recover their field
    from the encoder's layout and those that do not."""
    lay = layout(facts, encoder, version)
    rec, rest = [], []
    for g in facts["functions"][decoder]["getters"]:
        if not F.when_ok(g.get("when"), version):
            continue
        (rec if recovers(lay, g) else rest).append(g["name"])
    return {"fields": rec, "not_recovered": rest}
