"""Structural storage keys (I68, the Q21 fix; rules S2, S3, S5 and S7 of tests_m3/test_structural_keys.py).

A structural key is (b, o, path): b the family's base slot (the compiler's layout), o the slot offset inside the
top-level variable, path a tuple of hashed steps ("m", k, o2), each the mapping key word k (cleaned as solc hashes
it) and the slot offset o2 inside the value. The model states a key as SK{W{b}, o, [SP_m{k, o2}, ..]} (holon.sorts.
prelude3.PRELUDE_SK) and never computes a real slot. This module maps keys to real slots with the real keccak256, which
only R5, the replays, the deployment conversion and the search's heuristics do:

  real_slot(b, o, path)      s = b + o, then for each step s = keccak256(pad32(k) ++ pad32(s)) + o2, mod 2**256
  layout(doc)                the document's literal slots and mapping bases (with each value's slot count)
  s0_entries(init, doc)      the deployment's captured slots as keys: a slot of a top-level variable is its literal key
                             (b = the variable's slot, o = the offset inside it), a slot keccak256(k ++ b) + o2 of a
                             recorded 64-byte preimage k ++ b whose b is a mapping family's base (o2 below the value's
                             slot count) is (b, 0, (("m", k, o2),)), and any other slot stays raw: (r, 0, ())
  s0_text(entries)           the model's s0 over those keys; s0_keys(model_text) reads them back, real_state(entries)
                             gives the {real slot: value} they denote (the capture exactly, rule S5)
  sk_code(b, o, path)        the Bend term of a key with literal parts
  keys_document(..)          gen/<M>/sorts/keys.json (rule S7): raw, literal and structural keys with their real slots,
                             and every collision (a raw or literal slot equal to a structural image, two structural keys
                             with one image): a finding, never an assumption

Standard library and holon.keccak only; deterministic (sorted iteration). Nothing here names a target.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..keccak import keccak256

MASK = (1 << 256) - 1


class KeysError(ValueError):
    """A key or a model text this module cannot read."""


def _pad32(x: int) -> bytes:
    return (int(x) & MASK).to_bytes(32, "big")


def real_slot(b: int, o: int, path=()) -> int:
    """The real slot of the structural key (b, o, path)."""
    s = (int(b) + int(o)) & MASK
    for step in path:
        tag, k, o2 = step
        if tag != "m":
            raise KeysError(f"step {step!r}: only mapping steps are structural keys")
        s = (int.from_bytes(keccak256(_pad32(k) + _pad32(s)), "big") + int(o2)) & MASK
    return s


def norm_key(key) -> tuple:
    """(b, o, path) with ints and a tuple path of ("m", k, o2) triples."""
    b, o, path = key
    return int(b), int(o), tuple(("m", int(k), int(o2)) for _t, k, o2 in path)


# ------------------------------------------------------------------------------------------------ the layout
def families(doc: dict) -> list[dict]:
    return [s for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []) if isinstance(s, dict)]


def value_slots(fam: dict) -> int:
    """The slot count of a mapping family's value: 1 for an elementary value, 1 + the largest member slot for a
    struct."""
    ms = fam.get("fields") or []
    return 1 + max((int(m.get("slot") or 0) for m in ms), default=0)


def layout(doc: dict) -> tuple[dict, dict]:
    """({literal slot: (base, offset)}, {mapping base slot: value slot count}) of a document's storage layout: every
    slot of a scalar or of a fixed-length array of a top-level variable, and every mapping family's base."""
    lits: dict = {}
    maps: dict = {}
    for f in families(doc):
        kind, slot = f.get("kind"), f.get("slot")
        if not isinstance(slot, int):
            continue
        if kind == "scalar":
            lits.setdefault(slot, (slot, 0))
            for m in f.get("fields") or []:            # a top-level struct: each member slot keyed (base, member slot)
                if int(m.get("slot") or 0):
                    lits.setdefault(slot + int(m["slot"]), (slot, int(m["slot"])))
        elif kind == "array" and f.get("length"):
            for i in range(int(f["length"])):
                lits.setdefault(slot + i, (slot, i))
        elif kind == "mapping":
            maps[slot] = max(maps.get(slot, 0), value_slots(f))
    return lits, maps


# ------------------------------------------------------------------------------------------------ the deployment (S5)
def s0_entries(init: dict, doc: dict) -> list[tuple]:
    """[((b, o, path), value, kind)] of the deployment's non-zero captured slots, kind literal, structural or raw,
    sorted by key."""
    lits, maps = layout(doc)
    images: dict = {}
    for p in init.get("preimages") or []:
        bs = bytes.fromhex(p[2:] if p.startswith("0x") else p)
        if len(bs) != 64:
            continue
        base = int.from_bytes(bs[32:], "big")
        if base in maps:
            images[int.from_bytes(keccak256(bs), "big")] = (base, int.from_bytes(bs[:32], "big"))
    out = []
    for k, v in (init.get("storage") or {}).items():
        s, val = int(k, 16) if isinstance(k, str) else int(k), int(v, 16) if isinstance(v, str) else int(v)
        if not val:
            continue
        if s in lits:
            b, o = lits[s]
            out.append(((b, o, ()), val, "literal"))
            continue
        hit = None
        for h, (base, key) in sorted(images.items()):
            o2 = (s - h) & MASK
            if o2 < maps[base]:
                hit = ((base, 0, (("m", key, o2),)), val, "structural")
                break
        out.append(hit if hit is not None else ((s, 0, ()), val, "raw"))
    out.sort(key=lambda e: (e[0][0], e[0][1], e[0][2]))
    image = real_state([(k, v) for k, v, _ in out])
    want = {int(k, 16) if isinstance(k, str) else int(k): int(v, 16) if isinstance(v, str) else int(v)
            for k, v in (init.get("storage") or {}).items()}
    if image != {s: v for s, v in want.items() if v}:
        raise KeysError("the structural s0's real image is not the captured storage")
    return out


def real_state(entries) -> dict:
    """{real slot: value} of [(key, value)] (later entries of one real slot win, as none should exist)."""
    out = {}
    for e in entries:
        key, val = e[0], e[1]
        if int(val):
            out[real_slot(*norm_key(key))] = int(val)
    return out


# ------------------------------------------------------------------------------------------------ Bend text
def wlit(x: int) -> str:
    x = int(x) & MASK
    return "W{" + ", ".join(str((x >> (32 * i)) & 0xFFFFFFFF) for i in range(8)) + "}"


def wterm(x: int) -> str:
    """A literal word: w0() for zero (the offset word of a key is always present), else W{..}."""
    return "w0()" if not int(x) & MASK else wlit(x)


def sk_code(b: int, o: int, path=()) -> str:
    """The Bend term of a key whose parts are literals."""
    steps = ", ".join(f"SP_m{{{wlit(k)}, {wterm(o2)}}}" for _t, k, o2 in path)
    return f"SK{{{wlit(b)}, {wterm(o)}, {('[' + steps + ']') if steps else 'Nil{}'}}}"


def s0_text(entries) -> str:
    items = [f"KV{{{sk_code(*key)}, {wlit(val)}}}" for key, val, *_ in entries if int(val)]
    return "def s0() -> HSt:\n  HSt{" + ("[" + ", ".join(items) + "]" if items else "Nil{}") + "}\n"


_W = r"(?:W\{\s*(\d+(?:\s*,\s*\d+){7})\s*\}|w0\(\))"
_STEP = re.compile(r"SP_m\{\s*" + _W + r"\s*,\s*" + _W + r"\s*\}")
_KV = re.compile(r"KV\{SK\{\s*" + _W + r"\s*,\s*" + _W + r"\s*,\s*(Nil\{\}|\[(?:[^\[\]]*)\])\s*\}\s*,\s*" + _W + r"\s*\}")


def _word(limbs: str | None) -> int:
    if limbs is None:
        return 0
    xs = [int(x) for x in limbs.split(",")]
    return sum(x << (32 * i) for i, x in enumerate(xs))


def s0_keys(model_text: str) -> list[tuple]:
    """[((b, o, path), value)] of a structural model's s0 definition."""
    m = re.search(r"(?ms)^def s0\(\) -> HSt:\n  HSt\{(.*?)\}\n(?=\S|\Z)", model_text)
    if m is None:
        raise KeysError("the model has no structural s0")
    body = m.group(1)
    if body.strip() == "Nil{}":
        return []
    out = []
    for kv in _KV.finditer(body):
        b, o, path, v = _word(kv.group(1)), _word(kv.group(2)), kv.group(3), _word(kv.group(4))
        steps = tuple(("m", _word(s.group(1)), _word(s.group(2))) for s in _STEP.finditer(path)) \
            if path != "Nil{}" else ()
        out.append(((b, o, steps), v))
    if body.count("KV{") != len(out):
        raise KeysError("an s0 entry is not a literal structural key")
    return out


# ------------------------------------------------------------------------------------------------ the keys check (S7)
def collisions(structural, raw, literal) -> list[str]:
    """Rule S7's findings: a raw or literal slot equal to a structural key's real slot, or two different structural
    keys with one real slot. structural: [(b, o, path)] with a non-empty path."""
    out = []
    img: dict = {}
    for key in sorted({norm_key(k) for k in structural}):
        s = real_slot(*key)
        if s in img and img[s] != key:
            out.append(f"structural keys {img[s]!r} and {key!r} share the real slot {hex(s)}")
        img.setdefault(s, key)
    for s in sorted({int(x) for x in raw}):
        if s in img:
            out.append(f"raw slot {hex(s)} is the real slot of the structural key {img[s]!r}")
    for s in sorted({int(x) for x in literal}):
        if s in img:
            out.append(f"literal slot {hex(s)} is the real slot of the structural key {img[s]!r}")
    return out


def keys_document(milestone: str, keys: dict, sources: list) -> dict:
    """gen/<M>/sorts/keys.json from {"raw": set, "literal": set, "structural": set of (b, o, path)} gathered over the
    sources (deployment, r5, witnesses, inhabitants): every number a 0x-prefixed hex string, sorted."""
    st = sorted({norm_key(k) for k in keys.get("structural") or ()})
    raw = sorted({int(x) for x in keys.get("raw") or ()})
    lit = sorted({int(x) for x in keys.get("literal") or ()})
    return {"document": "structural_keys", "milestone": milestone,
            "raw": [hex(s) for s in raw], "literal": [hex(s) for s in lit],
            "structural": [{"b": hex(b), "o": hex(o), "p": [{"k": hex(k), "o": hex(o2)} for _t, k, o2 in p],
                            "real": hex(real_slot(b, o, p))} for b, o, p in st],
            "collisions": collisions(st, raw, lit), "sources": sorted(set(sources))}


def split_key(key) -> tuple[str, tuple]:
    """("structural", key) for a key with a path; ("literal" or "raw", slot) otherwise, judged by the layout's
    literal slots (keys_from_json's callers pass them)."""
    b, o, p = norm_key(key)
    return ("structural", (b, o, p)) if p else ("flat", (b, o, p))


def key_of_json(v) -> tuple:
    """(b, o, path) of an evaluator JSON value of an SK ({"$r": "SK", "f": {"b", "o", "p"}}, words as 0x-strings)."""
    if not (isinstance(v, dict) and v.get("$r") == "SK"):
        raise KeysError(f"not a structural key: {str(v)[:120]}")
    f = v["f"]

    def w(x):
        return int(x, 16) if isinstance(x, str) else int(x.get("$w", "0x0"), 16)
    steps = []
    for s in f.get("p") or []:
        if not (isinstance(s, dict) and s.get("$r") == "SP_m"):
            raise KeysError(f"not a mapping step: {str(s)[:120]}")
        steps.append(("m", w(s["f"]["k"]), w(s["f"]["o"])))
    return w(f["b"]), w(f["o"]), tuple(steps)


def key_json(key) -> dict:
    """The evaluator's JSON value of the key (b, o, path)."""
    b, o, p = norm_key(key)

    def word(x):
        return {"$w": "0x%064x" % (int(x) & MASK)}
    return {"$r": "SK", "f": {"b": word(b), "o": word(o),
                              "p": [{"$r": "SP_m", "f": {"k": word(k), "o": word(o2)}} for _t, k, o2 in p]}}


def write_json(path: Path, doc: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
