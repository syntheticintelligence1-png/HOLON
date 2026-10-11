"""Deterministic refutation search on the compiled model (whitepaper §9.2 loop 4, §10.5).

Candidates come from sort-boundary values and a fixed-seed sampler; claims are evaluated
by the compiled Bend model (holon.model_eval), never by a Python re-implementation.
A hit is only a *candidate* witness: status changes only when Bend accepts the counter-law
built from it (Thm 6.17).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import facts as F
from .gen import laws as LG
from .model_eval import CompiledModel, ModelError, value_in, value_out

SEED = 20261010
RANDOM_HEADERS = 48
RANDOM_FILLS = 1


@dataclass
class Search:
    witness: dict | None = None          # binder -> canonical JSON (premises applied)
    difference: dict | None = None       # {"lhs": .., "rhs": ..}
    tried: int = 0
    undefined: int = 0
    bound: str = ""
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------- candidate spaces
def version_constants(facts: dict) -> list[int]:
    ks = {0}
    for f in facts["functions"].values():
        for r in f.get("rules", []):
            if isinstance(r["if"], dict):
                ks.update(r["if"].get("version_in", []))
        if "domain" in f:
            ks.add(f["domain"]["version_le"])
        for w in [o.get("when") for o in f.get("ops", [])] + [g.get("when") for g in f.get("getters", [])] \
                + list(f.get("when", {}).values()):
            if w:
                ks.add(w["version_ge"])
    return sorted(ks)


def length_constants(facts: dict) -> list[int]:
    ks = set()
    for f in facts["functions"].values():
        for r in f.get("rules", []):
            if isinstance(r["then"], dict):
                ks.update(r["then"].values())
        if "length" in f:
            ks.add(f["length"])
        ks.update(f.get("length_by_version", {}).values())
    return sorted(ks)


def _header(w: dict, fill) -> dict:
    return {n: "0x" + bytes(fill(n, k) for k in range(width)).hex() for n, width in w.items()}


def header_candidates(facts: dict, pins: dict, rng: random.Random):
    w = F.widths(facts)
    versions = [None] if "version" in pins else sorted(set(version_constants(facts)) | {max(version_constants(facts)) + 1})
    pats = [("zeros", lambda n, k: 0), ("ones", lambda n, k: 0xFF), ("0x01", lambda n, k: 1)]
    for f in w:
        pats.append((f"only {f}=0xff", lambda n, k, f=f: 0xFF if n == f else 0))
    pats.append(("counting", lambda n, k: (sum(w[m] for m in list(w)[:list(w).index(n)]) + k + 1) % 256))
    for i in range(RANDOM_HEADERS):
        cells = {(n, k): rng.randrange(256) for n, width in w.items() for k in range(width)}
        pats.append((f"random#{i}", lambda n, k, c=cells: c[(n, k)]))
    for name, fill in pats:
        for v in versions:
            h = _header(w, fill)
            if v is not None:
                h["version"] = "0x" + bytes([v]).hex()
            for fld, val in pins.items():
                h[fld] = "0x" + bytes(val).hex()
            yield f"{name}" + ("" if v is None else f", version={v}"), h


def bytes_candidates(facts: dict, rng: random.Random):
    vs = version_constants(facts)
    versions = sorted(set(vs) | {max(vs) + 1, 255})
    lens = {0, 1, 2}
    for k in length_constants(facts):
        lens.update({k - 1, k, k + 1})
    lens = sorted(x for x in lens if x >= 0)
    yield "empty", "0x"
    for v in versions:
        for n in lens:
            if n == 0:
                continue
            fills = [("zeros", bytes(n - 1)), ("ones", b"\xff" * (n - 1))]
            fills += [(f"random#{i}", bytes(rng.randrange(256) for _ in range(n - 1))) for i in range(RANDOM_FILLS)]
            for fname, rest in fills:
                yield f"version={v}, len={n}, {fname}", "0x" + (bytes([v]) + rest).hex()


def candidates(law: dict, facts: dict, pins: dict):
    rng = random.Random(SEED)
    binders = law["statement"]["forall"]
    if len(binders) != 1:
        raise LG.Unsupported("refuter handles one binder in M0")
    b = binders[0]
    if b["type"] == "Header":
        for label, h in header_candidates(facts, pins.get(b["name"], {}), rng):
            yield label, {b["name"]: h}
    elif b["type"] == "Bytes":
        for label, x in bytes_candidates(facts, rng):
            yield label, {b["name"]: x}
    else:
        raise LG.Unsupported(b["type"])


def describe_space(law: dict, facts: dict) -> str:
    b = law["statement"]["forall"][0]
    if b["type"] == "Header":
        return (f"Header: {3 + len(F.widths(facts)) + 1} structured fills + {RANDOM_HEADERS} random (seed {SEED}), "
                f"premises pinned; unpinned version over {version_constants(facts)}+1")
    return (f"Bytes: empty + versions {sorted(set(version_constants(facts)) | {max(version_constants(facts)) + 1, 255})} "
            f"x lengths around {length_constants(facts)} x (zeros, ones, {RANDOM_FILLS} random; seed {SEED})")


# ---------------------------------------------------------------- search
def subterms(t: dict):
    """Every call/field subterm strictly inside t. A witness needs each to be defined:
    an undefined intermediate (a revert, unwritten memory) is not an execution."""
    for k in ("args",):
        for a in t.get(k, []):
            if "call" in a or "field" in a:
                yield a
            yield from subterms(a)
    for k in ("some", "of"):
        if k in t:
            if "call" in t[k] or "field" in t[k]:
                yield t[k]
            yield from subterms(t[k])


def _jobs_terms(law: dict, facts: dict):
    types = LG.binder_types(law)
    a, b = law["statement"]["claim"]["eq"]
    subs = [x for side in (a, b) for x in subterms(side)]
    sub_t = [LG.type_of(x, types, facts) for x in subs]
    return types, [a, b] + subs, LG.type_of(a, types, facts), sub_t


def _decode(vals: list, res_t: str, sub_t: list):
    lv, rv, *sv = vals
    for v, t in zip(sv, sub_t):
        value_out(t, v)  # raises on an undefined intermediate
    return value_out(res_t, lv), value_out(res_t, rv)


def search(law: dict, facts: dict, model: CompiledModel, batch: int = 256) -> Search:
    pins = LG.collect_pins(law, facts)
    types, terms, res_t, sub_t = _jobs_terms(law, facts)
    out = Search(bound=describe_space(law, facts))
    cands = list(candidates(law, facts, pins))
    for i in range(0, len(cands), batch):
        chunk = cands[i:i + batch]
        jobs = [{"terms": terms, "env": {v: value_in(types[v], x[v], facts) for v in types}} for _, x in chunk]
        for (label, env), vals in zip(chunk, model.run_jobs(jobs)):
            out.tried += 1
            try:
                lj, rj = _decode(vals, res_t, sub_t)
            except (ValueError, ModelError):
                out.undefined += 1  # a side is undefined here (revert / unwritten memory): not a witness
                continue
            if lj != rj:
                out.witness, out.difference = env, {"lhs": lj, "rhs": rj}
                out.notes.append(f"hit: {label}")
                return out
    return out


def evaluate(law: dict, facts: dict, model: CompiledModel, env: dict):
    """(lhs, rhs) of a law's claim at one assignment, on the compiled model; None if undefined."""
    types, terms, res_t, sub_t = _jobs_terms(law, facts)
    vals, = model.run_jobs([{"terms": terms, "env": {v: value_in(types[v], env[v], facts) for v in types}}])
    try:
        return _decode(vals, res_t, sub_t)
    except (ValueError, ModelError):
        return None
