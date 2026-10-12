"""Per-edge refinement corpus (whitepaper §8.7 sources 1-3; BUILD_PLAN I16).

corpus(edge) -> [{"source": "grammar" | "boundary" | "witness", "input": x}], in that order:

  grammar   GRAMMAR_SAMPLES seeded samples of the edge's input sort, drawn from the sort's grammar as the
            facts give it (below). The generator is random.Random seeded with a sha256 of (SEED, edge),
            so the corpus is the same in every process and under every PYTHONHASHSEED.
  boundary  the sort-boundary values of §8.7: 0, 1, max and max - 1 of every field, and every sentinel
            constant the facts compare against (versions, lengths), each inside the edge's domain.
  witness   every binder value of a REFUTED record of the facts' milestone whose binder sort is the
            edge's input sort, inside the edge's domain, in law order (the witnesses come from the
            records, which hold what the compiled model refuted).

Inputs are in canonical form: a Header is {field: "0x" + lowercase hex of exactly the field's width}
for every field, a Bytes value is "0x" + lowercase hex. Encoder corpora stay inside the edge's domain
(the facts' `domain`, e.g. version_le); decoders and domain predicates take every byte string, so
their corpora hold inputs inside and outside their guards.

The sort grammars, read from the facts:
  Header  a record of fixed-width byte fields. A field value is one of: zero, one, max, max - 1, a
          small value (one random low byte), k random low bytes (1 <= k < width), or width random
          bytes. The version field (the byte every version condition of the facts reads) is one of
          the facts' version constants, the first value past them, or any byte.
  Bytes   a version byte followed by a body, or the empty string. The length is one of the facts'
          length constants, one of their neighbours (+-1), a tiny length (0..3) or any length up to the
          largest constant + 16; the first byte is drawn like the version field; the body is random,
          zero or 0xff filled.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from . import facts as F

ROOT = Path(__file__).resolve().parents[1]
SEED = 20261016
GRAMMAR_SAMPLES = 2000
SOURCES = ("grammar", "boundary", "witness")
DEFAULT_FACTS = "facts/morph_header.json"


class CorpusError(ValueError):
    pass


# ---------------------------------------------------------------- facts: sentinels, domains
def version_constants(facts: dict) -> list[int]:
    """Every version constant the facts compare against (rule version_in, domain version_le, the
    version_ge conditions of ops, getters and projections)."""
    ks: set[int] = set()
    for f in facts["functions"].values():
        for r in f.get("rules", []):
            if isinstance(r.get("if"), dict):
                ks.update(r["if"].get("version_in", []))
        if isinstance(f.get("domain"), dict) and "version_le" in f["domain"]:
            ks.add(f["domain"]["version_le"])
        conds = [o.get("when") for o in f.get("ops", [])] + [g.get("when") for g in f.get("getters", [])]
        conds += list(f.get("when", {}).values()) if isinstance(f.get("when"), dict) else []
        for w in conds:
            if isinstance(w, dict) and "version_ge" in w:
                ks.add(w["version_ge"])
    return sorted(ks)


def length_constants(facts: dict) -> list[int]:
    """Every byte-length constant of the facts (rule len_eq / len_ge, encoder lengths)."""
    ks: set[int] = set()
    for f in facts["functions"].values():
        for r in f.get("rules", []):
            if isinstance(r.get("then"), dict):
                ks.update(v for k, v in r["then"].items() if k in ("len_eq", "len_ge"))
        if "length" in f:
            ks.add(f["length"])
        ks.update(f.get("length_by_version", {}).values())
    return sorted(ks)


def input_sort(facts: dict, edge: str) -> str:
    f = facts["functions"].get(edge)
    if f is None:
        raise CorpusError(f"no fact function {edge}")
    sort = f.get("from") or F.fn_types(facts, edge)[0]
    if sort not in ("Header", "Bytes"):
        raise CorpusError(f"{edge}: no grammar for input sort {sort}")
    return sort


def in_domain(facts: dict, edge: str, x) -> bool:
    """The edge's declared domain (facts `domain`); a function without one takes every input."""
    dom = facts["functions"][edge].get("domain")
    if dom is None:
        return True
    unknown = set(dom) - {"version_le", "code"}
    if unknown:
        raise CorpusError(f"{edge}: domain keys not understood: {sorted(unknown)}")
    return int(x["version"], 16) <= dom["version_le"]


def _hex(b: bytes) -> str:
    return "0x" + b.hex()


def _int(v: int, width: int) -> str:
    return _hex(v.to_bytes(width, "big"))


# ---------------------------------------------------------------- grammar samples
def _version_byte(rng: random.Random, vs: list[int]) -> int:
    r = rng.random()
    if r < 0.6:
        return rng.choice(vs)
    if r < 0.7:
        return max(vs) + 1
    return rng.randrange(256)


def _field(rng: random.Random, width: int) -> str:
    mx = (1 << (8 * width)) - 1
    r = rng.random()
    if r < 0.15:
        return _int(0, width)
    if r < 0.25:
        return _int(1, width)
    if r < 0.35:
        return _int(mx, width)
    if r < 0.40:
        return _int(mx - 1, width)
    if r < 0.50:
        return _int(rng.randrange(256), width)
    if r < 0.60 and width > 1:
        k = rng.randrange(1, width)
        return _hex(bytes(width - k) + bytes(rng.randrange(256) for _ in range(k)))
    return _hex(bytes(rng.randrange(256) for _ in range(width)))


def _header(rng: random.Random, facts: dict, vs: list[int]) -> dict:
    out = {}
    for name, width in F.widths(facts).items():
        out[name] = _int(_version_byte(rng, vs), 1) if name == "version" else _field(rng, width)
    return out


def _bytes(rng: random.Random, vs: list[int], ls: list[int]) -> str:
    r = rng.random()
    if r < 0.50:
        n = rng.choice(ls)
    elif r < 0.65:
        n = max(0, rng.choice(ls) + rng.choice((-1, 1)))
    elif r < 0.75:
        n = rng.randrange(4)
    else:
        n = rng.randrange(max(ls) + 17)
    if n == 0:
        return "0x"
    f = rng.random()
    if f < 0.70:
        body = bytes(rng.randrange(256) for _ in range(n - 1))
    elif f < 0.85:
        body = bytes(n - 1)
    else:
        body = b"\xff" * (n - 1)
    return _hex(bytes([_version_byte(rng, vs)]) + body)


def _rng(edge: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(f"holon.corpus/{SEED}/{edge}".encode()).digest()[:8], "big"))


def grammar(facts: dict, edge: str, n: int = GRAMMAR_SAMPLES) -> list:
    sort, rng = input_sort(facts, edge), _rng(edge)
    vs, ls = version_constants(facts), length_constants(facts)
    out = []
    while len(out) < n:
        x = _header(rng, facts, vs) if sort == "Header" else _bytes(rng, vs, ls)
        if sort == "Bytes" or in_domain(facts, edge, x):
            out.append(x)
    return out


# ---------------------------------------------------------------- sort-boundary values (§8.7)
def boundary(facts: dict, edge: str) -> list:
    sort, vs = input_sort(facts, edge), version_constants(facts)
    out: list = []
    if sort == "Header":
        w = F.widths(facts)
        versions = sorted({0, 1, 254, 255} | set(vs))
        for ver in versions:
            for fill in ("zero", "max"):
                h = {n: _int(0 if fill == "zero" else (1 << (8 * k)) - 1, k) for n, k in w.items()}
                h["version"] = _int(ver, 1)
                out.append(h)
            for name, width in w.items():
                if name == "version":
                    continue
                mx = (1 << (8 * width)) - 1
                for v in (0, 1, mx, mx - 1):
                    h = {n: _int(0, k) for n, k in w.items()}
                    h["version"], h[name] = _int(ver, 1), _int(v, width)
                    out.append(h)
        out = [h for h in out if in_domain(facts, edge, h)]
    else:
        ls = length_constants(facts)
        lengths = sorted({0, 1, 2} | set(ls) | {k - 1 for k in ls} | {k + 1 for k in ls})
        firsts = sorted({0, 1, 254, 255} | set(vs) | {max(vs) + 1})
        for n in lengths:
            if n == 0:
                out.append("0x")
                continue
            for b0 in firsts:
                out.append(_hex(bytes([b0]) + bytes(n - 1)))
                out.append(_hex(bytes([b0]) + b"\xff" * (n - 1)))
    return _dedupe(out)


# ---------------------------------------------------------------- witnesses
def witnesses(facts: dict, edge: str, milestone: str = "M0", root: Path = ROOT) -> list:
    from . import ir
    sort, out = input_sort(facts, edge), []
    for law in sorted(ir.load_laws_any(milestone, root), key=lambda l: l["law_id"]):
        p = Path(root) / "results" / milestone / f"{law['law_id']}.json"
        if not p.exists():
            continue
        rec = json.loads(p.read_text())
        if rec.get("status") != "REFUTED" or not isinstance(rec.get("witness"), dict):
            continue
        for b in law["statement"]["forall"]:
            if b["type"] == sort and b["name"] in rec["witness"]:
                x = rec["witness"][b["name"]]
                if (sort == "Bytes" or in_domain(facts, edge, x)) and x not in out:
                    out.append(x)
    return out


def _dedupe(xs: list) -> list:
    seen, out = set(), []
    for x in xs:
        k = json.dumps(x, sort_keys=True)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def corpus(edge: str, facts_path: str | Path | None = None, milestone: str = "M0", root: Path = ROOT) -> list[dict]:
    root = Path(root)
    facts = F.load(Path(facts_path) if facts_path else root / DEFAULT_FACTS)
    items = [{"source": "grammar", "input": x} for x in grammar(facts, edge)]
    items += [{"source": "boundary", "input": x} for x in boundary(facts, edge)]
    items += [{"source": "witness", "input": x} for x in witnesses(facts, edge, milestone, root)]
    return items


def counts(items: list[dict]) -> dict:
    return {s: sum(1 for it in items if it["source"] == s) for s in SOURCES}
