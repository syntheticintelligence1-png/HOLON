"""Grammar- and sort-boundary fuzzing of a compiled model (I40 E-FUZZ; whitepaper §10.5; spec/M3/lib/refute.json
"fuzz"): a law's binders drawn from their types, boundary values first (0, 1, max, max - 1 and every literal of the
document), then uniform values from random.Random seeded with (seed, law id), one stream per law; every candidate is
evaluated on the compiled model, and one that satisfies the premises and separates the claim's sides is a candidate
witness, which counts only through its counter-law (the caller checks it with Bend and BendTT).

  linked_candidates(doc, law, n, seed, maxlen) -> [witness]   candidates for a law over a linked codec component
                                                              (records of bytes and byte strings)
  linked_fuzz(cm, law, n, seed, maxlen) -> {"tried", "found": [witness]}
"""
from __future__ import annotations

import json
import random


def _consts(x, out: set) -> set:
    if isinstance(x, list):
        if len(x) == 2 and x[0] == "const" and isinstance(x[1], int) and not isinstance(x[1], bool):
            out.add(int(x[1]))
        for y in x:
            _consts(y, out)
    elif isinstance(x, dict):
        for y in x.values():
            _consts(y, out)
    elif isinstance(x, int) and not isinstance(x, bool):
        out.add(x)
    return out


def _record(doc: dict, t: str, fill) -> dict:
    out = {}
    for f in doc["carriers"][t]["fields"]:
        w = int(f["width"])
        out[f["name"]] = "0x" + bytes(fill(w)).hex()
    return out


def linked_candidates(doc: dict, law: dict, n: int, seed: int, maxlen: int) -> list[dict]:
    """n witnesses for the law's binders, boundary values first, then the seeded stream (deterministic)."""
    binders = [(b["name"], b["type"]) for b in law["statement"]["binders"]]
    named = set()

    def calls(t):
        if isinstance(t, dict):
            if "call" in t:
                named.add(t["call"][3:] if str(t["call"]).startswith("ok_") else t["call"])
            for v in t.values():
                calls(v)
        elif isinstance(t, list):
            for v in t:
                calls(v)
    calls(law["statement"])
    # the literals of the domain conditions of the functions the law names (the document's literals that decide
    # definedness), then every other literal of those functions
    oks = [(doc["functions"].get(f) or {}).get("ok") for f in sorted(named)]
    ks = sorted({k for k in _consts(oks, set()) if 0 <= k <= maxlen})
    lengths = sorted({x for k in ks for x in (k - 1, k, k + 1) if 0 <= x <= maxlen} | {0, 1, maxlen - 1, maxlen})
    tags = sorted({x for k in ks for x in (k - 1, k, k + 1) if 0 <= x <= 255} | {0, 1, 254, 255})
    fills = [lambda w: [0] * w, lambda w: [1] * w, lambda w: [255] * w, lambda w: [254] * w]
    boundary = []
    for ln in lengths:
        for tg in tags:
            for fi in fills:
                boundary.append((ln, tg, fi))
    rng = random.Random(json.dumps([seed, law["law_id"]]))
    out = []
    i = 0
    while len(out) < n:
        w = {}
        if i < len(boundary):
            ln, tg, fi = boundary[i]
        else:
            ln, tg = rng.choice([rng.randrange(0, maxlen + 1), rng.choice(lengths)]), rng.randrange(0, 256)
            seq = [rng.randrange(0, 256) for _ in range(maxlen)]
            fi = (lambda s: (lambda m: s[:m]))(seq)
        for name, t in binders:
            if doc["carriers"].get(t, {}).get("kind") == "record":
                w[name] = _record(doc, t, fi)
            else:
                body = list(fi(ln)) if ln else []
                if body:
                    body[0] = tg
                w[name] = "0x" + bytes(body).hex()
        out.append(w)
        i += 1
    return out


def linked_fuzz(cm, law: dict, n: int, seed: int, maxlen: int, batch: int = 512) -> dict:
    """Evaluate n candidates on the compiled component model (holon.gen.linked.evaluate): the ones whose premises hold
    and whose claim's sides differ."""
    from .gen import linked as L
    types = {b["name"]: L.binder_type(cm.doc, b["type"]) for b in law["statement"]["binders"]}
    cands = linked_candidates(cm.doc, law, n, seed, maxlen)
    found = []
    for i in range(0, len(cands), batch):
        part = cands[i:i + batch]
        for w, r in zip(part, L.evaluate(cm, law, types, part)):
            if all(L._same(a, b) for a, b in r["premises"]) and not L._same(*r["claim"]):
                found.append(w)
    return {"tried": len(cands), "found": found}
