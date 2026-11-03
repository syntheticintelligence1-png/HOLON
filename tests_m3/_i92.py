"""I92 instrument (= I34b: rule SYM over Bundle I), fixed at the I92 prereg (BUILD_PLAN §0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_sym_bundle.py, rules K1-K12. This module computes K2's sorts, K4's
sentinel registers and sites and K5's law ids a second time, independently of holon/: it reads I69's member documents
(gen/M3/bundle/documents/queue.json and messenger.json) and the Rollup's facts (spec/M2/facts/morph_rollup.extracted.json)
as JSON, with I34's instrument's term helpers (tests_m3/_i34.py). Nothing here imports holon/.

  MEMBERS                        member -> (document, contract)
  time_registers(root)           K2: {member: sorted register paths whose value sort is Time}
  idx_registers(root)            K2: {member: sorted register paths whose value sort is Idx}
  idx_keys(root)                 K2: {member: sorted map families whose key domain is Idx}
  sentinel_registers(root)       K4: {member: sorted [path, constant]}
  sentinel_sites(root)           K4: {member: sorted [path, action, src]}, the non-literal writes of a sentinel register
  link_callers(root)             K3: the Rollup actions calling the queue's enqueue-time getter, sorted
  expected_law_ids(root)         K5: the law ids holon derive must write for I92, sorted
  basis(root)                    the above as one JSON object (spec/M3/lib/sym_bundle_basis.json holds it at the prereg)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from tests_m3 import _i34 as J

ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {"queue": ("gen/M3/bundle/documents/queue.json", "L1MessageQueueWithGasPriceOracle"),
           "messenger": ("gen/M3/bundle/documents/messenger.json", "L1CrossDomainMessenger")}
ROLLUP = "spec/M2/facts/morph_rollup.extracted.json"
GETTER = "getFirstUnfinalizedMessageEnqueueTime"
CALL_IFACE = {"IL1MessageQueue": "queue", "IL1MessageQueueWithGasPriceOracle": "queue"}
CMP = J.CMP


def doc(member: str, root: Path = ROOT) -> dict:
    return J.load(Path(root) / MEMBERS[member][0])


def _actions(d: dict) -> dict:
    return {a["name"]: a for a in d["actions"]}


def _register(e):
    """A register read: ["storage", F] -> F; ["map", ["storage", F], k] -> F (the map's value);
    ["member", ["map", ["storage", F], k], m] -> F.m (I34's form)."""
    r = J._register(e)
    if r:
        return r
    if isinstance(e, list) and len(e) == 3 and e[0] == "map" and isinstance(e[1], list) and e[1][:1] == ["storage"] \
            and isinstance(e[1][1], str):
        return e[1][1]
    return None


def _write_values(d: dict, path: str):
    """(action, src, value) for each write of a register path: I34's struct form, and the "update" form
    ["update", base, member, value] (a struct written back after member updates)."""
    yield from J._write_values(d, path)
    fam, _, mem = path.partition(".")
    if not mem:
        return
    for a in d["actions"]:
        for w in a.get("writes") or []:
            if w.get("family") != fam:
                continue
            for x in J._walk(w.get("value")):
                if isinstance(x, list) and len(x) == 4 and x[0] == "update" and (
                        x[2] == mem or (isinstance(x[2], list) and x[2][:1] == ["member"] and x[2][-1] == mem)):
                    yield a["name"], w.get("src"), x[3]


def _places(a: dict):
    """(where, expr) for each place a comparison decides: a guard, a check, a view's return, a write's value
    (its branch conditions)."""
    for g in a.get("guards") or []:
        yield g.get("src") or "guard", g.get("expr")
    for c in a.get("checks") or []:
        yield c.get("src") or "check", c.get("expr")
    if not J.STATE_CHANGING(a):
        yield "returns", a.get("returns")
    for w in a.get("writes") or []:
        yield w.get("src") or "write", w.get("cond")
        yield w.get("src") or "write", w.get("value")


def _calls_answer(e):
    """The callee "<iface>.<function>" of a call term ["call", "<iface>.<function>", ..], else None."""
    if isinstance(e, list) and e[:1] == ["call"] and len(e) >= 2 and isinstance(e[1], str):
        return e[1]
    return None


# ------------------------------------------------------------------------------------------------------- K2 sorts
def _sorted_terms(root: Path):
    """The fixed point of K2's rules over both members. A term is Time when it is env block.timestamp, a read of a Time
    register, or a call answer whose callee action's return term is Time; Idx when it is the length of a storage array,
    a read of an Idx register, a call answer whose callee's return term is Idx, or a trunc or an addition of a constant
    over an Idx term. A register's value sort is S when some write stores an S term in it or some comparison sets it
    against an S term; a map's key domain is Idx when some write or read indexes it with an Idx term."""
    docs = {m: doc(m, root) for m in MEMBERS}
    time = {m: set() for m in MEMBERS}
    idx = {m: set() for m in MEMBERS}
    keys = {m: set() for m in MEMBERS}

    def callee_returns(name):
        iface, _, fn = name.partition(".")
        m = CALL_IFACE.get(iface)
        if not m:
            return None, None
        return m, _actions(docs[m]).get(fn, {}).get("returns")

    def is_time(m, e, depth=0):
        if depth > 12:
            return False
        if e == ["env", "block.timestamp"]:
            return True
        r = _register(e)
        if r and r in time[m]:
            return True
        c = _calls_answer(e)
        if c:
            cm, ret = callee_returns(c)
            return bool(cm) and ret is not None and is_time(cm, ret, depth + 1)
        if isinstance(e, list) and e[:1] == ["?"] and len(e) == 4:
            return is_time(m, e[2], depth + 1) and is_time(m, e[3], depth + 1)
        return False

    def is_idx(m, e, depth=0):
        if depth > 12:
            return False
        if isinstance(e, list) and e[:1] == ["len"] and isinstance(e[1], list) and e[1][:1] == ["storage"]:
            return True
        r = _register(e)
        if r and r in idx[m]:
            return True
        c = _calls_answer(e)
        if c:
            cm, ret = callee_returns(c)
            return bool(cm) and ret is not None and is_idx(cm, ret, depth + 1)
        if isinstance(e, list) and e[:1] == ["trunc"] and len(e) == 3:
            return is_idx(m, e[2], depth + 1)
        if isinstance(e, list) and e[:1] == ["+"] and len(e) == 3:
            a, b = e[1], e[2]
            return (is_idx(m, a, depth + 1) and isinstance(b, int)) or (is_idx(m, b, depth + 1) and isinstance(a, int))
        return False

    changed = True
    while changed:
        changed = False
        for m, d in docs.items():
            regs = {s["name"]: s for s in d["storage"]}
            paths = set(regs)
            for s in d["storage"]:
                for f in s.get("fields") or []:
                    paths.add(f"{s['name']}.{f['name']}")
            for path in sorted(paths):
                for _, _, v in _write_values(d, path):
                    if path not in time[m] and is_time(m, v):
                        time[m].add(path)
                        changed = True
                    if path not in idx[m] and is_idx(m, v):
                        idx[m].add(path)
                        changed = True
            for a in d["actions"]:
                for _, e in _places(a):
                    for x in J._walk(e):
                        if isinstance(x, list) and len(x) == 3 and x[0] in CMP:
                            for reg, other in ((x[1], x[2]), (x[2], x[1])):
                                p = _register(reg)
                                if not p or isinstance(other, int):
                                    continue
                                if p not in time[m] and is_time(m, other):
                                    time[m].add(p)
                                    changed = True
                                if p not in idx[m] and is_idx(m, other):
                                    idx[m].add(p)
                                    changed = True
                for e in [a.get(k) for k in ("guards", "checks", "returns", "writes", "post")]:
                    for x in J._walk(e):
                        if isinstance(x, list) and len(x) == 3 and x[0] == "map" and isinstance(x[1], list) \
                                and x[1][:1] == ["storage"] and isinstance(x[1][1], str):
                            if x[1][1] not in keys[m] and is_idx(m, x[2]):
                                keys[m].add(x[1][1])
                                changed = True
                    for x in J._walk(e):
                        if isinstance(x, list) and len(x) == 4 and x[0] == "store" and isinstance(x[1], list) \
                                and x[1][:1] == ["storage"]:
                            for k in x[2] if isinstance(x[2], list) else []:
                                if isinstance(k, list) and k[:1] == ["map"] and len(k) == 2 and is_idx(m, k[1]) \
                                        and x[1][1] not in keys[m]:
                                    keys[m].add(x[1][1])
                                    changed = True
    return time, idx, keys


def time_registers(root: Path = ROOT) -> dict:
    return {m: sorted(v) for m, v in _sorted_terms(root)[0].items()}


def idx_registers(root: Path = ROOT) -> dict:
    return {m: sorted(v) for m, v in _sorted_terms(root)[1].items()}


def idx_keys(root: Path = ROOT) -> dict:
    return {m: sorted(v) for m, v in _sorted_terms(root)[2].items()}


# ------------------------------------------------------------------------------------------------- K4 sentinels
def sentinel_registers(root: Path = ROOT) -> dict:
    """K4: a Time or Idx register compared against an integer constant in a guard, a check, a view's return or a write's
    branch condition; {member: sorted [path, constant]}."""
    time, idx, _ = _sorted_terms(root)
    out = {}
    for m in MEMBERS:
        d = doc(m, root)
        found = set()
        for a in d["actions"]:
            for _, e in _places(a):
                for x in J._walk(e):
                    if isinstance(x, list) and len(x) == 3 and x[0] in CMP:
                        for reg, c in ((x[1], x[2]), (x[2], x[1])):
                            if isinstance(c, int) and not isinstance(c, bool):
                                p = _register(reg)
                                if p and (p in time[m] or p in idx[m]):
                                    found.add((p, c))
        out[m] = sorted([list(x) for x in found])
    return out


def sentinel_sites(root: Path = ROOT) -> dict:
    """K4: each write of a sentinel register whose value is not the literal constant; {member: sorted [path, action,
    src]}."""
    out = {}
    regs = sentinel_registers(root)
    for m in MEMBERS:
        d = doc(m, root)
        found = set()
        for path, c in regs[m]:
            for act, src, v in _write_values(d, path):
                if v != c:
                    found.add((path, act, src))
        out[m] = sorted([list(x) for x in found])
    return out


# ------------------------------------------------------------------------------------------------------ K3 link
def link_callers(root: Path = ROOT) -> list:
    """K3: the Rollup's actions that call the queue's enqueue-time getter (its facts' calls), sorted."""
    r = J.load(Path(root) / ROLLUP)
    return sorted(a["name"] for a in r["actions"] if any(GETTER in json.dumps(c) for c in a.get("calls") or []))


# ------------------------------------------------------------------------------------------------------ K5 laws
def _touches_time(m: str, a: dict, time: dict) -> bool:
    s = json.dumps([a.get(k) for k in ("guards", "checks", "returns", "writes", "post", "calls")])
    if '["env", "block.timestamp"]' in s:
        return True
    fams = {p.split(".")[0] for p in time[m]}
    if fams & J._reads(a):
        return True
    for x in J._walk([a.get(k) for k in ("guards", "checks", "returns", "writes", "post", "calls")]):
        c = _calls_answer(x)
        if c and c.split(".")[0] in CALL_IFACE and c.split(".")[1] == GETTER:
            return True
    return False


def expected_law_ids(root: Path = ROOT) -> list:
    """K5: one tau law per member action touching a Time word (L_sym_tau_<Contract>_<action>), one per Rollup caller of
    the getter over the link (L_sym_tau_link_Rollup_<action>), one sentinel law per K4 site
    (L_sym_sentinel_<Contract>_<path with _>_<action>_<line>)."""
    time, _, _ = _sorted_terms(root)
    out = []
    for m, (_, contract) in MEMBERS.items():
        for a in doc(m, root)["actions"]:
            if _touches_time(m, a, time):
                out.append(f"L_sym_tau_{contract}_{a['name']}")
    for act in link_callers(root):
        out.append(f"L_sym_tau_link_Rollup_{act}")
    for m, sites in sentinel_sites(root).items():
        contract = MEMBERS[m][1]
        for path, act, src in sites:
            line = re.search(r":(\d+)(?:-\d+)?$", src or "")
            out.append(f"L_sym_sentinel_{contract}_{path.replace('.', '_')}_{act}_{line.group(1) if line else 'x'}")
    return sorted(set(out))


def basis(root: Path = ROOT) -> dict:
    return {"time_registers": time_registers(root), "idx_registers": idx_registers(root), "idx_keys": idx_keys(root),
            "sentinel_registers": sentinel_registers(root), "sentinel_sites": sentinel_sites(root),
            "link_callers": link_callers(root), "law_ids": expected_law_ids(root)}


if __name__ == "__main__":
    print(json.dumps(basis(), indent=1, sort_keys=True))
