"""Trusted reference interpreter for HOLON M0 facts.

This file is part of the frozen test oracle. It is deliberately small and
independent of the implementation under test: it interprets facts/*.json
directly in Python. Agents must not import it from holon/ (a test enforces this).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

UNKNOWN = None  # an unwritten (dirty) memory byte


class DomainError(Exception):
    """The function is not defined on this input (e.g. Solidity version guard)."""


def load_facts(path) -> dict:
    return json.loads(Path(path).read_text())


def facts_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def header_fields(facts: dict) -> list[dict]:
    return facts["types"]["Header"]["fields"]


def widths(facts: dict) -> dict[str, int]:
    return {f["name"]: f["width"] for f in header_fields(facts)}


def _when_ok(when, version: int) -> bool:
    if not when:
        return True
    if "version_ge" in when:
        return version >= when["version_ge"]
    raise ValueError(f"unknown when-condition {when}")


def _src_bytes(src: list, h: dict, w: dict) -> list:
    out: list = []
    for item in src:
        if "field" in item:
            val = h[item["field"]]
            assert len(val) == w[item["field"]], (item, len(val))
            out.extend(val)
        elif "zeros" in item:
            out.extend([0] * item["zeros"])
        elif "const" in item:
            out.append(item["const"])
        else:
            raise ValueError(item)
    return out


_OP_WIDTH = {"mstore": 32, "mstore8": 1, "set_byte": 1, "put_uint64_be": 8}


def encode(facts: dict, fn: str, h: dict) -> bytes:
    """h: field name -> bytes (exact width). Returns the encoded header bytes."""
    f = facts["functions"][fn]
    w = widths(facts)
    version = h["version"][0]
    if f["lang"] == "solidity-evm-memory":
        if version > f["domain"]["version_le"]:
            raise DomainError(f"{fn}: version {version} > {f['domain']['version_le']}")
        length = f["length_by_version"][str(version)]
        mem: list = [UNKNOWN] * max(length, max(op["offset"] + _OP_WIDTH[op["op"]] for op in f["ops"]))
    elif f["lang"] == "go-bytes":
        length = f["length"]
        mem = [0] * length
    else:
        raise ValueError(f["lang"])
    for op in f["ops"]:
        if not _when_ok(op.get("when"), version):
            continue
        data = _src_bytes(op["src"], h, w)
        if op["op"] in _OP_WIDTH:
            assert len(data) == _OP_WIDTH[op["op"]], (fn, op, len(data))
        elif op["op"] == "copy":
            pass  # Go copy(dst[o:], src): copies len(src) bytes (all fit in M0)
        else:
            raise ValueError(op["op"])
        o = op["offset"]
        if f["lang"] == "go-bytes":
            assert o + len(data) <= length, (fn, op)  # PutUint64 would panic otherwise
        mem[o:o + len(data)] = data
    out = mem[:length]
    if any(b is UNKNOWN for b in out):
        raise DomainError(f"{fn}: output contains unwritten bytes")
    return bytes(out)


def predicate(facts: dict, fn: str, b: bytes) -> bool:
    f = facts["functions"][fn]
    for rule in f["rules"]:
        cond, then = rule["if"], rule["then"]
        if cond == "empty":
            if len(b) == 0:
                return bool(then)
            continue
        if cond == "otherwise":
            return bool(then)
        if b[0] in cond["version_in"]:
            if isinstance(then, bool):
                return then
            if "len_ge" in then:
                return len(b) >= then["len_ge"]
            if "len_eq" in then:
                return len(b) == then["len_eq"]
            raise ValueError(then)
    raise ValueError(f"{fn}: rules not exhaustive")


def decode(facts: dict, fn: str, b: bytes):
    """Returns None (decode fails) or ('some', [bytes, ...])."""
    f = facts["functions"][fn]
    if not predicate(facts, f["guard"], b):
        return None
    version = b[0]
    out = []
    for g in f["getters"]:
        if not _when_ok(g.get("when"), version):
            continue
        out.append(bytes(b[g["offset"]:g["offset"] + g["width"]]))
    return ("some", out)


def view(facts: dict, h: dict) -> list[bytes]:
    f = facts["functions"]["view"]
    version = h["version"][0]
    return [bytes(h[n]) for n in f["order"] if _when_ok(f["when"].get(n), version)]


def call(facts: dict, fn: str, args: list):
    kind = facts["functions"][fn]["kind"]
    if kind == "encoder":
        return encode(facts, fn, args[0])
    if kind == "predicate":
        return predicate(facts, fn, args[0])
    if kind == "decoder":
        return decode(facts, fn, args[0])
    if kind == "projection":
        return view(facts, args[0])
    raise ValueError(kind)


# ---------------------------------------------------------------- layouts
def layout(facts: dict, fn: str, version: int) -> list[list]:
    """Symbolic layout of an encoder at a fixed version.

    Cells: ["field", name, k] | ["const", value] | ["unknown"].
    The version byte, when written from the field, is ["field", "version", 0].
    """
    f = facts["functions"][fn]
    w = widths(facts)
    if f["lang"] == "solidity-evm-memory":
        length = f["length_by_version"][str(version)]
        mem = [["unknown"] for _ in range(max(length, max(op["offset"] + _OP_WIDTH[op["op"]] for op in f["ops"])))]
    else:
        length = f["length"]
        mem = [["const", 0] for _ in range(length)]
    for op in f["ops"]:
        if not _when_ok(op.get("when"), version):
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


# ---------------------------------------------------------------- values
def hexb(b: bytes) -> str:
    return "0x" + bytes(b).hex()


def unhex(s: str) -> bytes:
    assert s.startswith("0x"), s
    return bytes.fromhex(s[2:])


def header_from_json(facts: dict, obj: dict) -> dict:
    w = widths(facts)
    h = {k: unhex(v) for k, v in obj.items()}
    assert set(h) == set(w), (sorted(set(w) ^ set(h)))
    for k, v in h.items():
        assert len(v) == w[k], (k, len(v), w[k])
    return h


def header_to_json(h: dict) -> dict:
    return {k: hexb(v) for k, v in h.items()}


def value_to_json(v):
    """Canonical JSON form of model outputs (shared by tests and implementation)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (bytes, bytearray)):
        return hexb(v)
    if v is None:
        return None
    if isinstance(v, tuple) and v[0] == "some":
        return [hexb(x) for x in v[1]]
    if isinstance(v, list):
        return [hexb(x) for x in v]
    raise TypeError(type(v))
