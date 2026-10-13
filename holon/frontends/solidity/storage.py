"""Storage families and constants of one contract (I19; contract: the docstring of tests_m2/test_extract_transitions.py).

Storage comes from the compiler, never from counting: solc's "storageLayout" output (holon.frontends.solidity.compile,
selected for transitions sidecars) gives every state variable's slot and offset and every type's encoding, label and
size. A family is a state variable the contract declares itself (its FunctionDefinition's siblings in the
ContractDefinition, not an inherited one), in declaration order:

  {"name", "slot", "offset", "kind": "scalar" | "mapping" | "array",
   "key": "<type>"          (mappings: the key type's label)
   "keys": ["<type>", ...]  (nested mappings only, mapping(a => mapping(b => c)): every key's label, outermost first;
                             value, width and fields then describe the innermost value c)
   "value": "<type>"        (the label of the variable's type; of a mapping's value type; of an array's element type)
   "width": bits            (when that value type is elementary: 8 * the compiler's numberOfBytes)
   "length": n              (fixed-size arrays: the declared length; dynamic arrays have none)
   "fields": [{"name", "type", "width", "slot", "offset"}]
                            (when that value type is a struct: its members in order; width as above, null for a member
                             that is not elementary; slot and offset relative to the struct's first slot, from the
                             compiler's layout of the struct type)}

inherited (I19 follow-up A19-10): the layout entries of the state variables the contract inherits (every entry of the
compiler's storageLayout of the contract whose astId the contract does not declare itself), in (slot, offset) order,
with the same shape plus "declared_in": the name of the contract whose AST declares the variable (read from the AST,
never from the layout's "contract" field, which names the derived contract). Entries that share a name are told apart
by declared_in and slot.

Constants and immutables are not storage (the compiler's layout leaves them out). The contract's own constants
(VariableDeclaration with constant true) are listed separately by `constants`, their values folded from the AST:
bytesN and address as "0x" + big-endian hex of the type's size, string and bytes literals as "0x" + their bytes,
integers and booleans as decimal strings (a negative intN in decimal with its sign); null when the initial value does
not fold (holon.frontends.solidity.transitions.fold_constant).
"""
from __future__ import annotations

import re

from .. import ExtractionError


def _layout(compiled, index, contract: dict) -> dict:
    unit = index.file_ids.get(int(contract["src"].split(":")[2]))
    lay = compiled.layouts.get((unit, contract["name"]))
    if lay is None:
        raise ExtractionError(f"contract {contract['name']}: the compiler gave no storageLayout for {unit}")
    return lay


def _elementary(t: dict) -> bool:
    return t.get("encoding") == "inplace" and "members" not in t and "base" not in t \
        and not str(t.get("label", "")).startswith("struct ")


def _bits(t: dict) -> int:
    return 8 * int(t["numberOfBytes"])


def _fields(types: dict, t: dict) -> list[dict]:
    out = []
    for m in t.get("members") or []:
        mt = types[m["type"]]
        out.append({"name": m["label"], "type": mt["label"], "width": _bits(mt) if _elementary(mt) else None,
                    "slot": int(m["slot"]), "offset": int(m["offset"])})
    return out


def _value(types: dict, tid: str, entry: dict) -> None:
    t = types[tid]
    entry["value"] = t["label"]
    if _elementary(t):
        entry["width"] = _bits(t)
    elif "members" in t:
        entry["fields"] = _fields(types, t)


def _length(t: dict):
    m = re.search(r"\[(\d+)\]$", str(t.get("label", "")))
    return int(m.group(1)) if m and t.get("encoding") != "dynamic_array" else None


def describe(types: dict, tid: str, entry: dict) -> dict:
    """Kind, key(s), value, width, length and fields of a state variable of type tid (solc storageLayout type id)."""
    t = types[tid]
    enc = t.get("encoding")
    if enc == "mapping":
        entry["kind"] = "mapping"
        entry["key"] = types[t["key"]]["label"]
        keys, vt = [entry["key"]], t["value"]
        while types[vt].get("encoding") == "mapping":
            keys.append(types[types[vt]["key"]]["label"])
            vt = types[vt]["value"]
        if len(keys) > 1:
            entry["keys"] = keys
        _value(types, vt, entry)
    elif "base" in t and (enc == "dynamic_array" or str(t.get("label", "")).endswith("]")):
        entry["kind"] = "array"
        n = _length(t)
        if n is not None:
            entry["length"] = n
        _value(types, t["base"], entry)
    else:
        entry["kind"] = "scalar"
        _value(types, tid, entry)
    return entry


def families(compiled, index, contract: dict) -> list[dict]:
    """The storage families of `contract`: its own state variables in declaration order, slots from the compiler."""
    lay = _layout(compiled, index, contract)
    types = lay.get("types") or {}
    by_id = {s["astId"]: s for s in lay.get("storage") or []}
    out = []
    for n in contract.get("nodes") or []:
        if n.get("nodeType") != "VariableDeclaration" or not n.get("stateVariable"):
            continue
        if n.get("constant") or n.get("mutability") in ("constant", "immutable"):
            continue
        s = by_id.get(n["id"])
        if s is None:
            raise ExtractionError(f"state variable {contract['name']}.{n.get('name')}: not in the compiler's "
                                  "storage layout")
        entry = {"name": s["label"], "slot": int(s["slot"]), "offset": int(s["offset"])}
        out.append(describe(types, s["type"], entry))
    return out


def inherited(compiled, index, contract: dict) -> list[dict]:
    """The inherited storage of `contract` (module docstring): the layout entries it does not declare, in (slot,
    offset) order, each with declared_in from the AST."""
    lay = _layout(compiled, index, contract)
    types = lay.get("types") or {}
    own = {n["id"] for n in contract.get("nodes") or [] if n.get("nodeType") == "VariableDeclaration"}
    out = []
    for s in lay.get("storage") or []:
        if s["astId"] in own:
            continue
        decl = index.nodes.get(s["astId"]) or {}
        owner = index.nodes.get(decl.get("scope")) or {}
        if owner.get("nodeType") != "ContractDefinition":
            raise ExtractionError(f"inherited state variable {s['label']}: its declaring contract is not in the AST")
        entry = {"name": s["label"], "slot": int(s["slot"]), "offset": int(s["offset"])}
        describe(types, s["type"], entry)
        entry["declared_in"] = owner["name"]
        out.append(entry)
    return sorted(out, key=lambda e: (e["slot"], e["offset"]))


def render_constant(value, type_string: str):
    """A folded constant as the document writes it (see the module docstring); None stays None."""
    if value is None:
        return None
    if isinstance(value, tuple) and value[:1] == ("str",):
        return "0x" + value[1]
    if not isinstance(value, int):
        return None
    ts = type_string.strip()
    m = re.fullmatch(r"bytes(\d+)", ts)
    if m:
        return "0x" + format(value, "0{}x".format(2 * int(m.group(1))))
    if ts in ("address", "address payable") or ts.startswith("contract "):
        return "0x" + format(value, "040x")
    m = re.fullmatch(r"int(\d*)", ts)
    if m:
        bits = int(m.group(1) or 256)
        v = value & ((1 << bits) - 1)
        return str(v - (1 << bits) if v >> (bits - 1) else v)
    return str(value)


def constants(contract: dict, fold) -> dict:
    """{name: value} of the contract's own constants; fold(decl) folds a constant declaration (None: no fold)."""
    out = {}
    for n in contract.get("nodes") or []:
        if n.get("nodeType") == "VariableDeclaration" and n.get("constant"):
            ts = ((n.get("typeDescriptions") or {}).get("typeString")) or ""
            out[n["name"]] = render_constant(fold(n), ts)
    return out
