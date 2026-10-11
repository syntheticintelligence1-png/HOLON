"""Fact sets (holon-facts/0.1): loading, hashing, and the types of fact functions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

# Byte values are modelled as U32 in Bend. A value outside 0..255 marks an undefined
# result: unwritten EVM memory, or a revert (whitepaper §8.3: definedness is explicit).
UNDEF = 57005  # 0xDEAD

# fact function kind -> (input type, output type) in the law IR's type vocabulary
KIND_TYPES = {
    "encoder": ("Header", "Bytes"),
    "predicate": ("Bytes", "Bool"),
    "decoder": ("Bytes", "MaybeFields"),
    "projection": ("Header", "Fields"),
}
OP_WIDTH = {"mstore": 32, "mstore8": 1, "set_byte": 1, "put_uint64_be": 8}


def load(path) -> dict:
    return json.loads(Path(path).read_text())


def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def header_fields(facts: dict) -> list[dict]:
    return facts["types"]["Header"]["fields"]


def widths(facts: dict) -> dict[str, int]:
    return {f["name"]: f["width"] for f in header_fields(facts)}


def fn_types(facts: dict, fn: str) -> tuple[str, str]:
    return KIND_TYPES[facts["functions"][fn]["kind"]]


def when_ok(when: dict | None, version: int) -> bool:
    if not when:
        return True
    if set(when) == {"version_ge"}:
        return version >= when["version_ge"]
    if set(when) == {"version_in"}:
        return version in when["version_in"]
    raise ValueError(f"unsupported when-condition {when}")


def src_cells(src: list, w: dict[str, int]) -> list[list]:
    """Symbolic cells written by one op: ["field", name, k] | ["const", v]."""
    cells: list[list] = []
    for item in src:
        if "field" in item:
            cells.extend(["field", item["field"], k] for k in range(w[item["field"]]))
        elif "zeros" in item:
            cells.extend(["const", 0] for _ in range(item["zeros"]))
        elif "const" in item:
            cells.append(["const", item["const"]])
        else:
            raise ValueError(f"unsupported op source {item}")
    return cells


def check_op_width(fn: str, op: dict, n: int) -> None:
    want = OP_WIDTH.get(op["op"])
    if op["op"] not in OP_WIDTH and op["op"] != "copy":
        raise ValueError(f"{fn}: unsupported op {op['op']}")
    if want is not None and n != want:
        raise ValueError(f"{fn}: {op['op']} at {op['offset']} writes {n} bytes, expected {want}")


def encoder_versions(f: dict) -> list[int]:
    """Versions at which a Solidity encoder is defined (its domain guard)."""
    return list(range(f["domain"]["version_le"] + 1))


def evm_memory_size(f: dict, w: dict[str, int]) -> int:
    length = max(int(v) for v in f["length_by_version"].values())
    end = max(op["offset"] + len(src_cells(op["src"], w)) for op in f["ops"])
    return max(length, end)
