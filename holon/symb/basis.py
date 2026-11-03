"""K4, K5: the members' laws, computed by holon from the members' documents and their sorts (holon.symb.sorts), the
contract's rules stated a second time on holon's side (the instrument computes them independently of holon/).

  tau        a member action touching a Time word: its guards, checks, returns, writes or calls read block.timestamp or
             a Time register's family;
  sentinel   a write of a sentinel register (a Time or Idx register compared against an integer constant in a guard, a
             check, a view's return or a write's condition) whose value is not the literal constant;
  invariant  a view whose return is a conditional on a conjunction holding R != c (R a sentinel register, c its
             constant) next to another conjunct.

Law ids: L_sym_tau_<Contract>_<action>, L_sym_sentinel_<Contract>_<path with _>_<action>_<line>,
L_sym_sentinel_inv_<Contract>_<path with _>_<view>.
"""
from __future__ import annotations

import json
import re

from . import Ctx
from .sorts import CMP, Solver, _iter, decided, register_of, written

PREFIX = "L_sym_"


def _writes_with_src(doc: dict, path: str):
    fam, _, mem = path.partition(".")
    for a in doc["actions"]:
        for w in a.get("writes") or []:
            if w.get("family") != fam:
                continue
            v = w.get("value")
            if not mem:
                if not (isinstance(v, list) and v[:1] == ["struct"]):
                    yield a["name"], w.get("src"), v
                continue
            if isinstance(v, list) and v[:1] == ["struct"] and len(v) == 3:
                for name, val in v[2]:
                    if name == mem:
                        yield a["name"], w.get("src"), val
                continue
            for x in _iter(v):
                if isinstance(x, list) and len(x) == 4 and x[0] == "update":
                    m2 = x[2] if isinstance(x[2], str) else (x[2][-1] if isinstance(x[2], list) and
                                                             x[2][:1] == ["member"] else None)
                    if m2 == mem:
                        yield a["name"], w.get("src"), x[3]


def _conjuncts(e) -> list:
    if isinstance(e, list) and e[:1] == ["&&"]:
        return [y for x in e[1:] for y in _conjuncts(x)]
    return [e]


def member_laws(ctx: Ctx, sorts: dict) -> dict:
    """{member: {"contract", "tau": [action], "sentinels": [(path, action, src, value, constant)], "readers":
    [(path, view, constant)]}} over the sidecar's members, and the law ids."""
    out = {}
    for name in sorted(ctx.side["members"]):
        spec = ctx.side["members"][name]
        doc = ctx.bundle.load(spec["document"])
        so = sorts["members"][name]
        tfam = {p.split(".")[0] for p in so["time"]}
        tau = []
        for a in doc["actions"]:
            s = json.dumps([a.get(k) for k in ("guards", "checks", "returns", "writes", "post", "calls")])
            reads = set()
            for k in ("guards", "writes", "returns", "checks", "loops", "calls", "post"):
                reads |= {x[1] for x in _iter(a.get(k)) if isinstance(x, list) and len(x) == 2 and x[0] == "storage"
                          and isinstance(x[1], str)}
            if '["env", "block.timestamp"]' in s or (reads & tfam):
                tau.append(a["name"])
        regs = set(so["time"]) | set(so["idx"])
        consts = {}
        for a in doc["actions"]:
            for e in decided(a):
                for x in _iter(e):
                    if isinstance(x, list) and len(x) == 3 and x[0] in CMP:
                        for reg, c in ((x[1], x[2]), (x[2], x[1])):
                            if isinstance(c, int) and not isinstance(c, bool):
                                p = register_of(reg)
                                if p in regs:
                                    consts.setdefault(p, set()).add(c)
        sentinels = []
        for p in sorted(consts):
            for c in sorted(consts[p]):
                for act, src, v in _writes_with_src(doc, p):
                    if v != c:
                        sentinels.append((p, act, src, v, c))
        readers = []
        for a in doc["actions"]:
            if a.get("mutability") not in ("view", "pure"):
                continue
            r = a.get("returns")
            if not (isinstance(r, list) and r[:1] == ["?"] and len(r) == 4):
                continue
            cs = _conjuncts(r[1])
            if len(cs) < 2:
                continue
            for x in cs:
                if isinstance(x, list) and len(x) == 3 and x[0] == "!=":
                    for reg, c in ((x[1], x[2]), (x[2], x[1])):
                        p = register_of(reg)
                        if p in consts and c in consts[p]:
                            readers.append((p, a["name"], c))
        uniq = {}
        for t in sentinels:
            uniq.setdefault((t[0], t[1], str(t[2]), t[4]), t)
        out[name] = {"contract": spec["contract"], "tau": sorted(set(tau)),
                     "sentinels": [uniq[k] for k in sorted(uniq)], "readers": sorted(set(readers))}
    return out


def law_ids(laws: dict) -> list:
    ids = []
    for m, v in laws.items():
        c = v["contract"]
        ids += [f"{PREFIX}tau_{c}_{a}" for a in v["tau"]]
        for p, act, src, _v, _c in v["sentinels"]:
            line = re.search(r":(\d+)(?:-\d+)?$", src or "")
            ids.append(f"{PREFIX}sentinel_{c}_{p.replace('.', '_')}_{act}_{line.group(1) if line else 'x'}")
        ids += [f"{PREFIX}sentinel_inv_{c}_{p.replace('.', '_')}_{view}" for p, view, _c in v["readers"]]
    return sorted(set(ids))
