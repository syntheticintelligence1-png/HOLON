"""Symbolic byte layout of an encoder (M0_SPEC section 5, prompts/P1).

Cells: ["field", name, k] | ["const", v] | ["unknown"] (dirty EVM memory).
"""
from __future__ import annotations

from .facts import when_ok, widths

_OP_WIDTH = {"mstore": 32, "mstore8": 1, "set_byte": 1, "put_uint64_be": 8}


def layout(facts: dict, fn: str, version: int) -> list[list]:
    f = facts["functions"][fn]
    w = widths(facts)
    if f["lang"] == "solidity-evm-memory":
        length = f["length_by_version"][str(version)]
        mem_size = max(length, max(op["offset"] + _OP_WIDTH[op["op"]] for op in f["ops"]))
        mem = [["unknown"] for _ in range(mem_size)]
    elif f["lang"] == "go-bytes":
        length = f["length"]
        mem = [["const", 0] for _ in range(length)]
    else:
        raise ValueError(f["lang"])
    for op in f["ops"]:
        if not when_ok(op.get("when"), version):
            continue
        cells = []
        for item in op["src"]:
            if "field" in item:
                cells.extend(["field", item["field"], k] for k in range(w[item["field"]]))
            elif "zeros" in item:
                cells.extend(["const", 0] for _ in range(item["zeros"]))
            else:
                cells.append(["const", item["const"]])
        o = op["offset"]
        mem[o:o + len(cells)] = cells
    return [list(c) for c in mem[:length]]
