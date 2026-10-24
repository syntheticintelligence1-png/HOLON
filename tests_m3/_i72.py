"""I72's instrument, fixed at the prereg (do not edit: a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl). Rules Z1-Z3 of the docstring of tests_m3/test_e2_transitions.py, written out a second time
independently of holon/: the read and write accesses of an adopted holon-facts/0.3 transitions document's actions,
the overlap of two access paths, and the E2 atoms of the document's model. Standard library only; deterministic.

Accesses (Z1). An access is (family, path); a path is a tuple of segments ("map", k) and ("member", name), k the
integer key of a literal map key and None for any other key. A write record (a dict with "family", "path", "value",
at any depth of the action: top-level writes and loop bodies alike) writes its family at its path. Reads are found by
walking every section of the action:
  - a state term of family f is ["storage", f], ["carried", L, s] or ["exit", L, s] (the family's value inside or
    after loop L) and ["store", s, P, v] (the family after a write at P), s a state term of f;
  - a selection is ["map", x, k] or ["member", x, name]; a maximal chain of selections whose innermost base is a
    state term of f reads f at the chain's path (the base's own store paths and values are walked; the keys are
    walked as values);
  - a state term of a scalar family that no selection takes reads that family whole (the path ());
  - a threading position of family f holds f's state, not a read of it: the value of post[f] (the post-state the
    document restates from the writes), and the "entry" and "value" of a loop record's carried, next, at_break and
    exit entries whose name is ["storage", f]. In a threading position a state term of f is no read, a ["?", c, a, b]
    walks c as a value and a and b as threading positions, and anything else is walked as a value.
A state term of a non-scalar family that is neither a selection's base nor in a threading position is a construct
the rule does not map (Unmapped). A raw ["sload", n] (or ["sstore", n, v]) at a literal slot n that no family declares
(no scalar's slot, no fixed array's slots, no mapping's base slot) is no access of any family (the EIP-1967 slots);
one at a slot a family declares, or at a slot that is not a literal, is a construct the rule does not map.

Overlap (Z2). Two paths overlap when, segment by segment over the shorter one, no position separates them: two
members of different names do, two literal map keys that differ do, and nothing else does (a symbolic key overlaps
every key; a shorter path covers what lies below it).

Atoms (Z3). For actions p and q (p == q included, as I14's E2 pairs every endpoint with every endpoint) and a family
f that p writes and q reads: an atom when some write path of p on f overlaps some read path of q on f, with via
{"carrier": f as the model's anchors name it, "writes": the rendered write paths that overlap a read, "reads": the
rendered read paths that overlap a write}, both sorted. Rendering: "*" for (), "[*]" for a symbolic key, "[<k>]"
for a literal one, ".<name>" for a member, concatenated. The id is <model>:E2:<p>:<q>:<the first 8 hex digits of the
sha256 of the canonical JSON of via>, p and q the edges TRANS.<action>, src null.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRAP = ("carried", "exit")
THREAD_LISTS = ("carried", "next", "at_break", "exit")


class Unmapped(ValueError):
    """A construct rule Z1 does not map."""


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_sha256(obj) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def adopted(gm: str, root: Path = ROOT) -> list[tuple[str, dict]]:
    """(repo path, document) of every transitions document spec/<gm>/lib/derive_extracted.json adopts, sorted."""
    side = root / "spec" / gm / "lib" / "derive_extracted.json"
    if not side.exists():
        return []
    out = []
    for rel in sorted(load(side).get("documents") or []):
        d = load(root / rel)
        if d.get("facts_version") == "holon-facts/0.3" and (d.get("extraction") or {}).get("kind") == "transitions":
            out.append((rel, d))
    return out


def model_name(rel: str) -> str:
    return rel.rsplit("/", 1)[-1][:-len(".json")]


def families(doc: dict) -> tuple[dict[str, str], set[str]]:
    """({family name: kind}, the names two entries declare)."""
    entries = [s for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []) if isinstance(s, dict)]
    names = [s.get("name") for s in entries]
    return {s["name"]: s["kind"] for s in entries}, {n for n in names if names.count(n) > 1}


# ------------------------------------------------------------------------------------------------ Z1 accesses
def _seg(tag: str, x):
    if tag == "map":
        return ("map", x if isinstance(x, int) and not isinstance(x, bool) else None)
    if tag == "member" and isinstance(x, str):
        return ("member", x)
    raise Unmapped(f"path segment {[tag, x]!r}")


def state_family(t):
    if isinstance(t, list) and len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
        return t[1]
    if isinstance(t, list) and len(t) == 3 and t[0] in WRAP and isinstance(t[1], str):
        return state_family(t[2])
    if isinstance(t, list) and len(t) == 4 and t[0] == "store" and isinstance(t[2], list):
        return state_family(t[1])
    return None


def _chain(t):
    """(family, path, base, keys) of a selection chain over a state term, else None."""
    if isinstance(t, list) and len(t) == 3 and t[0] in ("map", "member"):
        key = [t[2]] if t[0] == "map" else []
        f = state_family(t[1])
        if f is not None:
            return f, (_seg(t[0], t[2]),), t[1], key
        c = _chain(t[1])
        if c is not None:
            return c[0], c[1] + (_seg(t[0], t[2]),), c[2], c[3] + key
    return None


class _Reads:
    def __init__(self, kinds: dict[str, str], slots: set[int] | None = None):
        self.kinds = kinds
        self.slots = slots or set()
        self.out: set = set()

    def value(self, t) -> None:
        if isinstance(t, list) and t:
            if t[0] in ("sload", "sstore") and len(t) >= 2 and isinstance(t[0], str):
                n = t[1]
                if not isinstance(n, int) or isinstance(n, bool) or n in self.slots:
                    raise Unmapped(f"a raw {t[0]} at {n!r}: a slot a family declares, or not a literal")
                for x in t[2:]:
                    self.value(x)
                return
            c = _chain(t)
            if c is not None:
                self.out.add((c[0], c[1]))
                self.thread(c[2], c[0])
                for k in c[3]:
                    self.value(k)
                return
            f = state_family(t)
            if f is not None:
                if self.kinds.get(f) != "scalar":
                    raise Unmapped(f"a whole {self.kinds.get(f)} family {f!r} read as a value")
                self.out.add((f, ()))
                self.thread(t, f)
                return
            for x in t:
                self.value(x)
        elif isinstance(t, dict):
            for k in sorted(t):
                self.value(t[k])

    def thread(self, t, fam: str) -> None:
        if isinstance(t, list) and len(t) == 2 and t[0] == "storage" and t[1] == fam:
            return
        if isinstance(t, list) and len(t) == 3 and t[0] in WRAP and state_family(t) == fam:
            self.thread(t[2], fam)
            return
        if isinstance(t, list) and len(t) == 4 and t[0] == "store" and state_family(t) == fam:
            self.thread(t[1], fam)
            for s in t[2]:
                if isinstance(s, list) and len(s) == 2 and s[0] == "map":
                    self.value(s[1])
            self.value(t[3])
            return
        if isinstance(t, list) and len(t) == 4 and t[0] == "?":
            self.value(t[1])
            self.thread(t[2], fam)
            self.thread(t[3], fam)
            return
        self.value(t)


def _thread_name(n):
    return n[1] if isinstance(n, list) and len(n) == 2 and n[0] == "storage" and isinstance(n[1], str) else None


def family_slots(doc: dict) -> set[int]:
    """The slots the document's families declare: each scalar's slot, each fixed array's slots, each mapping's base."""
    out = set()
    for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []):
        if not isinstance(s, dict) or not isinstance(s.get("slot"), int):
            continue
        n = int(s.get("length") or 1) if s.get("kind") == "array" else 1
        out.update(range(s["slot"], s["slot"] + n))
    return out


def reads(action: dict, kinds: dict[str, str], slots: set[int] | None = None) -> set:
    """Rule Z1's reads of one action: {(family, path)}."""
    r = _Reads(kinds, slots)
    for k in sorted(action):
        v = action[k]
        if k == "post" and isinstance(v, dict):
            for f in sorted(v):
                r.thread(v[f], f)
        elif k == "loops" and isinstance(v, list):
            for loop in v:
                for kk in sorted(loop):
                    vv = loop[kk]
                    if kk in THREAD_LISTS and isinstance(vv, list):
                        for e in vv:
                            f = _thread_name(e.get("name"))
                            for slot in ("entry", "value"):
                                if slot in e:
                                    if f is not None:
                                        r.thread(e[slot], f)
                                    else:
                                        r.value(e[slot])
                    else:
                        r.value(vv)
        else:
            r.value(v)
    return r.out


def writes(action: dict) -> set:
    """Rule Z1's writes of one action: {(family, path)} from every write record at any depth."""
    out: set = set()

    def walk(t):
        if isinstance(t, dict):
            if isinstance(t.get("family"), str) and "path" in t and "value" in t:
                out.add((t["family"], tuple(_seg(s[0], s[1]) for s in t["path"])))
            for k in sorted(t):
                walk(t[k])
        elif isinstance(t, list):
            for x in t:
                walk(x)
    walk(action)
    return out


# ------------------------------------------------------------------------------------------------ Z2, Z3
def overlap(p: tuple, q: tuple) -> bool:
    for a, b in zip(p, q):
        if a[0] != b[0]:
            continue
        if a[0] == "member" and a[1] != b[1]:
            return False
        if a[0] == "map" and a[1] is not None and b[1] is not None and a[1] != b[1]:
            return False
    return True


def render(path: tuple) -> str:
    return "".join(("[" + ("*" if x is None else str(x)) + "]") if t == "map" else "." + x for t, x in path) or "*"


def e2_atoms(model: str, doc: dict) -> list[dict]:
    """Rule Z3's atoms of one adopted transitions document, sorted by id."""
    kinds, dups = families(doc)
    acts = sorted((a for a in doc.get("actions") or [] if isinstance(a, dict) and isinstance(a.get("name"), str)),
                  key=lambda a: a["name"])
    slots = family_slots(doc)
    W = {a["name"]: writes(a) for a in acts}
    R = {a["name"]: reads(a, kinds, slots) for a in acts}
    atoms = []
    for p in acts:
        for q in acts:
            for f in sorted({g for g, _ in W[p["name"]]} & {g for g, _ in R[q["name"]]}):
                if f in dups:
                    raise Unmapped(f"family {f!r} is declared twice and accessed")
                pw = [w for g, w in W[p["name"]] if g == f]
                qr = [r for g, r in R[q["name"]] if g == f]
                ws = sorted({render(w) for w in pw if any(overlap(w, r) for r in qr)})
                if not ws:
                    continue
                rs = sorted({render(r) for r in qr if any(overlap(w, r) for w in pw)})
                via = {"carrier": f, "writes": ws, "reads": rs}
                pe, qe = f"TRANS.{p['name']}", f"TRANS.{q['name']}"
                atoms.append({"id": f"{model}:E2:{pe}:{qe}:{canonical_sha256(via)[:8]}", "model": model,
                              "level": "E2", "p": pe, "q": qe, "via": via, "src": None})
    return sorted(atoms, key=lambda a: a["id"])


def expected(gm: str, root: Path = ROOT) -> dict[str, list[dict]]:
    """{model: rule Z3's atoms} for every transitions document the milestone gm adopts."""
    return {model_name(rel): e2_atoms(model_name(rel), d) for rel, d in adopted(gm, root)}


def strip(a: dict) -> tuple:
    """An atom's projection the checks compare: (p, q, carrier, writes, reads)."""
    return (a["p"], a["q"], a["via"]["carrier"], tuple(a["via"]["writes"]), tuple(a["via"]["reads"]))
