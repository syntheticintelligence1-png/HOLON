"""I68's instrument, fixed at the prereg (do not edit: a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl). Structural storage keys (Q21's answer, docs/HUMAN_ANSWERS.md), written out a second time
independently of holon/: the real slot of a structural key by solc's storage layout rules, the classification of a
deployment's captured slots, and the keys check. Standard library and the test suite's own Keccak
(tests_m2/_keccak.py) only; deterministic.

Keys (rule S2 of tests_m3/test_structural_keys.py). A structural key is (b, o, path): b the family's literal base slot
(the compiler's layout), o the slot offset inside the top-level variable, path a tuple of hashed steps ("m", k, o2):
the mapping key word k (cleaned as solc hashes it) and the slot offset o2 inside the value. Its real slot is
s = b + o, then for each step s = keccak256(pad32(k) ++ pad32(s)) + o2, all mod 2**256 (solc's rule for a mapping
value at a key of an elementary type, then the member or element offset).

Classification (rule S5). A captured slot of the deployment is literal when it is a slot of a top-level variable
(a scalar family's slot, or a slot of a fixed-length array family), structural when it is keccak256(k ++ b) + o2 for
a recorded 64-byte preimage k ++ b whose b is a mapping family's base slot and 0 <= o2 < the value type's slot
count, and raw otherwise (an EIP-1967 style slot computed by code).

Keys check (rule S7). Over a set of structural keys and raw slots: no raw or literal slot equals the real slot of a
structural key, and no two different structural keys share a real slot.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASK = (1 << 256) - 1


def _keccak(b: bytes) -> bytes:
    from tests_m2._keccak import keccak256
    return keccak256(b)


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def pad32(x: int) -> bytes:
    return (x & MASK).to_bytes(32, "big")


def real_slot(b: int, o: int, path: tuple = ()) -> int:
    """The real slot of the structural key (b, o, path)."""
    s = (b + o) & MASK
    for step in path:
        tag, k, o2 = step
        if tag != "m":
            raise ValueError(f"step {step!r}: only mapping steps are structural keys at I68")
        s = (int.from_bytes(_keccak(pad32(k) + pad32(s)), "big") + o2) & MASK
    return s


def families(doc: dict) -> list[dict]:
    return [s for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []) if isinstance(s, dict)]


def literal_slots(doc: dict) -> dict[int, list[str]]:
    """{slot: [variable names]} of the slots of top-level variables (scalars and fixed-length arrays)."""
    out: dict[int, list[str]] = {}
    for f in families(doc):
        if f["kind"] == "scalar":
            out.setdefault(f["slot"], []).append(f["name"])
        elif f["kind"] == "array" and f.get("length"):
            for i in range(int(f["length"])):
                out.setdefault(f["slot"] + i, []).append(f"{f['name']}[{i}]")
    return out


def value_slots(f: dict) -> int:
    """The slot count of a mapping family's value: 1 for an elementary value, 1 + the largest member slot for a
    struct."""
    ms = f.get("fields") or []
    return 1 + max((int(m.get("slot") or 0) for m in ms), default=0)


def classify(init: dict, doc: dict) -> dict:
    """{"literal": {slot: names}, "structural": {slot: (family, key, o2)}, "raw": [slot]} of the captured storage."""
    lit = literal_slots(doc)
    maps = {f["slot"]: f for f in families(doc) if f["kind"] == "mapping"}
    pre = {}
    for p in init.get("preimages") or []:
        bs = bytes.fromhex(p[2:])
        if len(bs) == 64:
            pre[int.from_bytes(_keccak(bs), "big")] = bs
    out = {"literal": {}, "structural": {}, "raw": []}
    for k in sorted(init.get("storage") or {}, key=lambda x: int(x, 16)):
        s = int(k, 16)
        if s in lit:
            out["literal"][s] = lit[s]
            continue
        hit = None
        for h, bs in pre.items():
            base = int.from_bytes(bs[32:], "big")
            o2 = (s - h) & MASK
            if base in maps and o2 < value_slots(maps[base]):
                hit = (maps[base]["name"], int.from_bytes(bs[:32], "big"), o2)
                break
        if hit is not None:
            out["structural"][s] = hit
        else:
            out["raw"].append(s)
    return out


def keys_check(structural: list[tuple], raw: list[int], literal: list[int]) -> list[str]:
    """Rule S7's problems: a raw or literal slot equal to a structural key's real slot, or two different structural
    keys with one real slot. structural: [(b, o, path)]."""
    probs = []
    img: dict[int, tuple] = {}
    for key in sorted(set(structural), key=repr):
        s = real_slot(*key)
        if s in img and img[s] != key:
            probs.append(f"structural keys {img[s]!r} and {key!r} share the real slot {s:#x}")
        img.setdefault(s, key)
    for s in sorted(set(raw)):
        if s in img:
            probs.append(f"raw slot {s:#x} is the real slot of the structural key {img[s]!r}")
    for s in sorted(set(literal)):
        if s in img:
            probs.append(f"literal slot {s:#x} is the real slot of the structural key {img[s]!r}")
    return probs
