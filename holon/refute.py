"""Deterministic bounded witness search on the compiled model (prompts/P3).

Candidates are evaluated on the compiled Bend model through model_eval,
never on the test oracle. Premise pins are applied to every candidate.
"""
from __future__ import annotations

import random

from . import model_eval
from .emit import pins_of
from .facts import widths

SEARCH_SEED = 0xCA7E
N_RANDOM_HEADERS = 256
N_RANDOM_BYTES = 64
BYTES_VERSIONS = (0, 1, 2, 3, 255)
BYTES_LENGTHS = (0, 1, 2, 248, 249, 250, 256, 257, 258)

BATCH = 200


def _apply_pins_header(facts: dict, pins: dict, h: dict) -> dict:
    h = dict(h)
    for field, hexs in pins.items():
        h[field] = bytes.fromhex(hexs[2:])
    return h


def header_candidates(facts: dict, pins: dict):
    w = widths(facts)
    seen = set()

    def emit(h):
        h = _apply_pins_header(facts, pins, h)
        key = tuple(h[k] for k in sorted(h))
        if key not in seen:
            seen.add(key)
            return h
        return None

    bases = [{k: bytes(v) for k, v in w.items()},
             {k: b"\xff" * v for k, v in w.items()}]
    for b in bases:
        h = emit(b)
        if h:
            yield h
    for fname, wd in w.items():
        for val in (b"\x01" * wd, b"\xff" * wd, bytes([wd]) + b"\x00" * (wd - 1)):
            h = emit({**{k: bytes(v) for k, v in w.items()}, fname: val})
            if h:
                yield h
    rng = random.Random(SEARCH_SEED)
    for _ in range(N_RANDOM_HEADERS):
        h = emit({k: bytes(rng.randrange(256) for _ in range(v)) for k, v in w.items()})
        if h:
            yield h


def bytes_candidates():
    yield b""
    for v in BYTES_VERSIONS:
        for n in BYTES_LENGTHS:
            if n < 1:
                continue
            yield bytes([v]) + bytes(n - 1)
    rng = random.Random(SEARCH_SEED)
    for _ in range(N_RANDOM_BYTES):
        n = rng.choice(BYTES_LENGTHS[1:])
        yield bytes(rng.randrange(256) for _ in range(n))


def _header_json(h: dict) -> dict:
    return {k: "0x" + v.hex() for k, v in h.items()}


def _called_domains(law: dict, facts: dict) -> list:
    """(binder, version_le) for each Header arg of a domain-restricted call in the claim."""

    def walk(t):
        if "call" in t:
            f = facts["functions"].get(t["call"], {})
            dom = f.get("domain", {})
            if "version_le" in dom:
                for a in t["args"]:
                    if "var" in a:
                        yield a["var"], int(dom["version_le"])
            for a in t["args"]:
                yield from walk(a)

    return list(set(x for side in law["statement"]["claim"]["eq"] for x in walk(side)))


def _in_domain(law: dict, facts: dict, witness: dict, pins_map: dict) -> bool:
    """Skip candidates that take a called function outside its stated domain."""
    for var, vmax in _called_domains(law, facts):
        if var not in witness:
            continue
        pins = pins_map.get(var, {})
        if "version" in pins:
            v = bytes.fromhex(pins["version"][2:])[0]
        elif isinstance(witness[var], dict) and "version" in witness[var]:
            v = bytes.fromhex(witness[var]["version"][2:])[0]
        else:
            continue
        if v > vmax:
            return False
    return True


def find_witness(law: dict, facts: dict, facts_path=None, root=None):
    """Return {"witness": {binder: canonical}, "lhs": .., "rhs": ..} or None."""
    pins_map = pins_of(law)
    st = law["statement"]
    binder = st["forall"][0]
    bname, btype = binder["name"], binder["type"]
    if btype == "Header":
        pins = pins_map.get(bname, {})
        cands = (_header_json(h) for h in header_candidates(facts, pins))
    elif btype == "Bytes":
        cands = ("0x" + b.hex() for b in bytes_candidates())
    else:
        return None
    batch = []
    total = 0
    for c in cands:
        w = {bname: c}
        if not _in_domain(law, facts, w, pins_map):
            continue
        batch.append(w)
        total += 1
        if len(batch) >= BATCH:
            hit = _eval_batch(law, batch, facts_path, root)
            if hit:
                return hit
            batch = []
    if batch:
        return _eval_batch(law, batch, facts_path, root)
    return None


def _eval_batch(law, batch, facts_path, root):
    for w, res in zip(batch, model_eval.eval_claim(law, batch, facts_path, root)):
        if res["eq"] is False:
            return {"witness": w, "lhs": res["lhs"], "rhs": res["rhs"],
                    "n_candidates": len(batch)}
    return None


def bound_description(law: dict, facts: dict) -> str:
    b = law["statement"]["forall"][0]
    if b["type"] == "Header":
        return (f"headers: all-zero, all-0xff, single-field variants, "
                f"{N_RANDOM_HEADERS} seeded-random (seed {SEARCH_SEED}), premise pins applied")
    return (f"bytes: empty, versions {list(BYTES_VERSIONS)} x lengths "
            f"{list(BYTES_LENGTHS)} zero-filled, {N_RANDOM_BYTES} seeded-random "
            f"(seed {SEARCH_SEED})")
