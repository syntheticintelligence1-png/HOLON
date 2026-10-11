"""Grammar- and sort-boundary fuzzing of the compiled model (§10.5, engine row 3).

Seeded and deterministic: a grammar over the binder sorts, not an ad-hoc list.

  * Header: the version cell ranges over sort boundaries — every version
    constant the facts mention, ±1, plus the byte extremes; every other field
    takes a fill pattern (zeros, ones, 0x01, 0x80, counting, per-field hot
    bytes, seeded randoms). Premises are applied by pinning, exactly as
    `refute.candidates` does.
  * Bytes: version byte × boundary lengths (every length constant ±1, small
    lengths, and one past the top constant) × fill patterns.
  * A mutation tier: seeded single-cell mutations of the grammar candidates.

Candidates respect the same input domain as the original refuter: each one is
filtered by `refute.in_domain` (the restored M0 `_in_domain`), so nothing is
tried that takes a called function outside its stated domain. Evaluation is
identical to `refute.search`: the same term jobs on the same compiled Bend
model, with every intermediate subterm required to be defined.
"""
from __future__ import annotations

import random

from .. import facts as F
from .. import refute
from ..gen import laws as LG
from ..model_eval import ModelError, value_in, value_out

SEED = 20261011
RANDOM_HEADERS = 96
RANDOM_FILLS = 2
MUTATE_CELLS = 2            # mutated cells per mutation tier round


# ---------------------------------------------------------------- candidate grammar
def boundary_versions(facts: dict) -> list[int]:
    vs = refute.version_constants(facts)
    out = {0, 255}
    for k in vs:
        out.update(x for x in (k - 1, k, k + 1) if 0 <= x <= 255)
    return sorted(out)


def boundary_lengths(facts: dict) -> list[int]:
    ks = refute.length_constants(facts)
    out = {0, 1, 2}
    for k in ks:
        out.update(x for x in (k - 1, k, k + 1) if x >= 0)
    out.add(max(ks, default=0) + 2)
    return sorted(out)


def header_candidates(law: dict, facts: dict, pins: dict, rng: random.Random):
    w = F.widths(facts)
    pats = [("zeros", lambda n, k: 0), ("ones", lambda n, k: 0xFF), ("0x01", lambda n, k: 1),
            ("0x80", lambda n, k: 0x80),
            ("counting", lambda n, k: (sum(w[m] for m in list(w)[:list(w).index(n)]) + k + 1) % 256)]
    for f in w:
        pats.append((f"first {f}=0xff", lambda n, k, f=f: 0xFF if n == f and k == 0 else 0))
        pats.append((f"last {f}=0xff", lambda n, k, f=f: 0xFF if n == f and k == w[f] - 1 else 0))
    for i in range(RANDOM_HEADERS):
        cells = {(n, k): rng.randrange(256) for n, width in w.items() for k in range(width)}
        pats.append((f"random#{i}", lambda n, k, c=cells: c[(n, k)]))
    b = law["statement"]["forall"][0]
    versions = [None] if "version" in pins.get(b["name"], {}) else boundary_versions(facts)
    for name, fill in pats:
        for v in versions:
            h = {n: "0x" + bytes(fill(n, k) for k in range(width)).hex() for n, width in w.items()}
            if v is not None:
                h["version"] = "0x" + bytes([v]).hex()
            for fld, val in pins.get(b["name"], {}).items():
                h[fld] = "0x" + bytes(val).hex()
            yield f"{name}" + ("" if v is None else f", version={v}"), h


def bytes_candidates(law: dict, facts: dict, rng: random.Random):
    versions = boundary_versions(facts)
    lens = boundary_lengths(facts)
    yield "empty", "0x"
    for v in versions:
        for n in lens:
            if n == 0:
                continue
            fills = [("zeros", bytes(n - 1)), ("ones", b"\xff" * (n - 1)),
                     ("counting", bytes((k + 1) % 256 for k in range(n - 1)))]
            fills += [(f"random#{i}", bytes(rng.randrange(256) for _ in range(n - 1)))
                      for i in range(RANDOM_FILLS)]
            for fname, rest in fills:
                yield f"version={v}, len={n}, {fname}", "0x" + (bytes([v]) + rest).hex()


def _mutate(label: str, cand, binders: list, rng: random.Random, facts: dict,
            pins: dict):
    """One grammar-mutation step: flip MUTATE_CELLS cells of a base candidate.

    Premise-pinned cells are never touched: a mutation there would leave the
    law's input domain, and the kernel's pinned evaluation would (correctly)
    reject the candidate."""
    mut = dict(cand)
    for b in binders:
        if b["type"] == "Header":
            w = F.widths(facts)
            free = [n for n in w if n not in pins.get(b["name"], {})]
            h = {n: bytearray(bytes.fromhex(mut[b["name"]][n][2:])) for n in w}
            for _ in range(MUTATE_CELLS):
                n = rng.choice(free)
                h[n][rng.randrange(w[n])] = rng.randrange(256)
            mut[b["name"]] = {n: "0x" + bytes(v).hex() for n, v in h.items()}
        else:
            bs = bytearray(bytes.fromhex(mut[b["name"]][2:]))
            if not bs:
                continue
            for _ in range(MUTATE_CELLS):
                bs[rng.randrange(len(bs))] = rng.randrange(256)
            mut[b["name"]] = "0x" + bytes(bs).hex()
    return f"mut({label})", mut


def candidates(law: dict, facts: dict, pins: dict, seed: int = SEED):
    """(label, binder-env) pairs in the law's input domain, deterministic."""
    rng = random.Random(seed)
    binders = law["statement"].get("forall")
    if binders is None:
        raise LG.Unsupported("statement has no forall binders (not the codec ir/0.1 form)")
    if len(binders) != 1:
        raise LG.Unsupported("grammar fuzzer handles one binder in the codec fragment")
    b = binders[0]
    if b["type"] == "Header":
        gen = header_candidates(law, facts, pins, rng)
    elif b["type"] == "Bytes":
        gen = bytes_candidates(law, facts, rng)
    else:
        raise LG.Unsupported(b["type"])
    base = [(label, {b["name"]: v}) for label, v in gen]
    base += list(_mutations(list(base), binders, rng, facts, pins))
    for label, env in base:
        if refute.in_domain(law, facts, env, pins):
            yield label, env


def _mutations(base: list, binders: list, rng: random.Random, facts: dict, pins: dict):
    for label, env in base:
        yield _mutate(label, env, binders, rng, facts, pins)


def describe_space(law: dict, facts: dict) -> str:
    b = law["statement"].get("forall", [{}])[0]
    if b["type"] == "Header":
        pats = 5 + 2 * len(F.widths(facts))
        return (f"Header grammar: {pats} fills + {RANDOM_HEADERS} random + mutation tier "
                f"({MUTATE_CELLS} cells), versions at {boundary_versions(facts)}, seed {SEED}")
    return (f"Bytes grammar: empty + versions {boundary_versions(facts)} x lengths "
            f"{boundary_lengths(facts)} x (zeros, ones, counting, {RANDOM_FILLS} random) + "
            f"mutation tier, seed {SEED}")


# ---------------------------------------------------------------- search (same eval discipline as refute.search)
def search(law: dict, facts: dict, model, batch: int = 256, seed: int = SEED) -> refute.Search:
    pins = LG.collect_pins(law, facts)
    types, terms, res_t, sub_t = refute._jobs_terms(law, facts)
    out = refute.Search(bound=describe_space(law, facts))
    cands = list(candidates(law, facts, pins, seed))
    for i in range(0, len(cands), batch):
        chunk = cands[i:i + batch]
        jobs = [{"terms": terms, "env": {v: value_in(types[v], x[v], facts) for v in types}} for _, x in chunk]
        for (label, env), vals in zip(chunk, model.run_jobs(jobs)):
            out.tried += 1
            try:
                lj, rj = refute._decode(vals, res_t, sub_t)
            except (ValueError, ModelError):
                out.undefined += 1
                continue
            if lj != rj:
                out.witness, out.difference = env, {"lhs": lj, "rhs": rj}
                out.notes.append(f"hit: {label}")
                return out
    return out
