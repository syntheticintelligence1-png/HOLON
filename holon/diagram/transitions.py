"""E2 over an adopted holon-facts/0.3 transitions document (I72; rules Z1-Z4 of tests_m3/test_e2_transitions.py).

holon.diagram.evidence covers each transitions document a milestone adopts with a model of anchors only (I20). This
module reads such a document's own terms, so that the model gets I14's level E2 ("written via p, read via q") without
a diagram. holon.diagram.evidence.transitions_atoms turns its pairs into atoms.

Accesses (Z1). An access is (family, path); a path is a tuple of segments ("map", k) and ("member", name), k the
integer key of a literal map key and None for any other key.
  - A write record (a dict with "family", "path" and "value", at any depth of an action: top-level writes and loop
    bodies alike) writes its family at its path.
  - A state term of family f is ["storage", f], ["carried", L, s] or ["exit", L, s] (the family inside or after loop
    L) and ["store", s, P, v] (the family after a write at P), s a state term of f.
  - A maximal chain of map and member selections over a state term of f reads f at the chain's path; the base's own
    store paths and values are walked, and the map keys are walked as values.
  - A state term of a scalar family that no selection takes reads that family whole (the path ()).
  - A threading position of family f holds f's state and is no read of it: the value of post[f] (the post-state the
    document restates from the writes), and the "entry" and "value" of a loop record's carried, next, at_break and
    exit entries whose name is ["storage", f]. There a state term of f is no read, a ["?", c, a, b] walks c as a value
    and a and b as threading positions, and anything else is walked as a value.
  - A raw ["sload", n] or ["sstore", n, v] at a literal slot n that no family declares (no scalar's slot, no fixed
    array's slots, no mapping's base slot) accesses no family; one at a slot a family declares, or at a slot that is
    not a literal, is a construct the rule does not map.
  - A state term of a non-scalar family that is neither a selection's base nor in a threading position, an accessed
    family two declarations share, and a path segment other than map and member are constructs the rule does not map.

Overlap (Z2). Two paths overlap unless some position of the shorter one separates them: two members of different
names, or two literal map keys that differ. A symbolic key overlaps every key, as an index term does in E2 over a
diagram (holon.diagram.evidence.overlap); a shorter path covers what lies below it.

Pairs (Z3). For actions p and q (p == q included) and a family f that p writes and q reads, a pair when some write path
of p on f overlaps some read path of q on f: (p, q, f, the rendered write paths that overlap a read, the rendered read
paths that overlap a write), each sorted, rendered "*" for the whole family, "[*]" for a symbolic key, "[<k>]" for a
literal one and ".<name>" for a member.

Pure Python and standard library; deterministic (sorted iteration).
"""
from __future__ import annotations

WHOLE = "*"
_SELECT = ("map", "member")
_WRAP = ("carried", "exit")
_THREADS = ("carried", "next", "at_break", "exit")
_RAW = ("sload", "sstore")


class TransitionsError(ValueError):
    """A construct the E2 rule over transitions documents does not map."""


def _seg(tag: str, x):
    if tag == "map":
        return ("map", x if isinstance(x, int) and not isinstance(x, bool) else None)
    if tag == "member" and isinstance(x, str):
        return ("member", x)
    raise TransitionsError(f"a path segment {[tag, x]!r}")


def state_family(t):
    """The family of a state term, else None."""
    if isinstance(t, list) and len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
        return t[1]
    if isinstance(t, list) and len(t) == 3 and t[0] in _WRAP and isinstance(t[1], str):
        return state_family(t[2])
    if isinstance(t, list) and len(t) == 4 and t[0] == "store" and isinstance(t[2], list):
        return state_family(t[1])
    return None


def _chain(t):
    """(family, path, base, keys) of a chain of map and member selections over a state term, else None."""
    if isinstance(t, list) and len(t) == 3 and t[0] in _SELECT:
        keys = [t[2]] if t[0] == "map" else []
        f = state_family(t[1])
        if f is not None:
            return f, (_seg(t[0], t[2]),), t[1], keys
        c = _chain(t[1])
        if c is not None:
            return c[0], c[1] + (_seg(t[0], t[2]),), c[2], c[3] + keys
    return None


class _Reads:
    def __init__(self, kinds: dict[str, str], slots: set[int]):
        self.kinds, self.slots, self.out = kinds, slots, set()

    def value(self, t) -> None:
        if isinstance(t, list) and t:
            if t[0] in _RAW and len(t) >= 2 and isinstance(t[0], str):
                n = t[1]
                if not isinstance(n, int) or isinstance(n, bool) or n in self.slots:
                    raise TransitionsError(f"a raw {t[0]} at {n!r}: a slot a family declares, or not a literal")
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
                    raise TransitionsError(f"a whole {self.kinds.get(f)} family {f!r} read as a value")
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
        if isinstance(t, list) and len(t) == 3 and t[0] in _WRAP and state_family(t) == fam:
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


def families(doc: dict) -> tuple[dict[str, str], set[str], set[int]]:
    """({family: kind}, the names two declarations share, the slots the families declare)."""
    entries = [s for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []) if isinstance(s, dict)]
    names = [s.get("name") for s in entries]
    slots = set()
    for s in entries:
        if isinstance(s.get("slot"), int):
            n = int(s.get("length") or 1) if s.get("kind") == "array" else 1
            slots.update(range(s["slot"], s["slot"] + n))
    return ({s["name"]: s.get("kind") for s in entries if isinstance(s.get("name"), str)},
            {n for n in names if names.count(n) > 1}, slots)


def reads(action: dict, kinds: dict[str, str], slots: set[int]) -> set:
    """The reads of one action: {(family, path)}."""
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
                    if kk in _THREADS and isinstance(vv, list):
                        for e in vv:
                            f = _thread_name(e.get("name")) if isinstance(e, dict) else None
                            for slot in ("entry", "value"):
                                if isinstance(e, dict) and slot in e:
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
    """The writes of one action: {(family, path)} from every write record at any depth."""
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
    return "".join(f"[{'*' if x is None else x}]" if t == "map" else f".{x}" for t, x in path) or WHOLE


def e2_pairs(doc: dict) -> list[tuple]:
    """(p, q, family, writes, reads) of every E2 relation of a transitions document (Z3), sorted."""
    kinds, shared, slots = families(doc)
    acts = sorted((a for a in doc.get("actions") or [] if isinstance(a, dict) and isinstance(a.get("name"), str)),
                  key=lambda a: a["name"])
    try:
        W = {a["name"]: writes(a) for a in acts}
        R = {a["name"]: reads(a, kinds, slots) for a in acts}
    except (KeyError, TypeError, IndexError, AttributeError) as e:
        raise TransitionsError(f"{type(e).__name__}: {e}") from e
    out = []
    for p in acts:
        for q in acts:
            for f in sorted({g for g, _ in W[p["name"]]} & {g for g, _ in R[q["name"]]}):
                if f in shared:
                    raise TransitionsError(f"the family {f!r}, declared twice, is accessed")
                pw = [w for g, w in W[p["name"]] if g == f]
                qr = [r for g, r in R[q["name"]] if g == f]
                ws = sorted({render(w) for w in pw if any(overlap(w, r) for r in qr)})
                if ws:
                    rs = sorted({render(r) for r in qr if any(overlap(w, r) for w in pw)})
                    out.append((p["name"], q["name"], f, ws, rs))
    return out
