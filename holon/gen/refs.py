"""Statement refs for holon-ir/0.3 (whitepaper §8.9, §9.4; BUILD_PLAN I7).

A 0.3 statement hash covers the definitions the statement names, each by the content hash of its
source in the fact document, never the whole facts bundle: an extraction change outside a law's refs
leaves its hash unchanged.

  obsv NAME           facts["observers"][NAME]
  mig NAME            facts["migrations"][NAME]
  act NAME, is_NAME   the action NAME
  CONSUMER (fn)       facts["consumers"][CONSUMER]
  builtin (fn)        its entry in holon.gen.mlaws.BUILTINS, under the rule catalog
  s0                  the state declaration and the initial state
  step                run, step, obs and the model functions over traces (runs_ok, last_ok, no_code,
                      perm, cost, elapsed): the state declaration, initial state, params, types, defs
                      and every action (the transition function reads them all)
  hyp H (premise)     hyp:H, the entry of the oracle sidecar whose hypothesis is H, restricted to
                      {parameter, hypothesis} (I12; holon.gen.oracles.Oracles.hyp_ref): editing a hypothesis
                      restales exactly the laws that name it; an instance, a doc, a ledger citation or a
                      not_in_scope entry changes no hash. Without a sidecar the ref is the hash of null.
"""
from __future__ import annotations

import hashlib

from .. import ir

_TRACE_FNS = {"runs_ok", "last_ok", "no_code", "perm", "cost", "elapsed"}


def _h(obj) -> str:
    return "sha256:" + hashlib.sha256(ir.canonical_json(obj)).hexdigest()


def _names(t, out: set) -> None:
    if isinstance(t, dict):
        if isinstance(t.get("obsv"), str):
            out.add(("obsv", t["obsv"]))
        if isinstance(t.get("mig"), str):
            out.add(("mig", t["mig"]))
        if isinstance(t.get("act"), str):
            out.add(("act", t["act"]))
        if isinstance(t.get("fn"), str) and "args" in t:
            out.add(("fn", t["fn"]))
        for k in ("run", "step", "obs"):
            if k in t:
                out.add(("step", "step"))
        if "s0" in t:
            out.add(("s0", "s0"))
        if isinstance(t.get("hyp"), dict) and isinstance(t["hyp"].get("name"), str):
            out.add(("hyp", t["hyp"]["name"]))
        for v in t.values():
            _names(v, out)
    elif isinstance(t, list):
        for v in t:
            _names(v, out)


def refs(law: dict, facts: dict, oracles=None) -> dict:
    """{definition name: content hash} for every model definition the statement names; `oracles` is the parsed
    sidecar (holon.gen.oracles.Oracles or its JSON document) that hyp premises refer to."""
    from .mlaws import BUILTINS
    names: set = set()
    _names(law["statement"], names)
    acts = {a["name"]: a for a in facts.get("actions", [])}
    step_src = {k: facts.get(k) for k in ("state", "initial", "params", "types", "defs", "actions")}
    out = {}
    orc = _oracles(oracles)
    for kind, n in sorted(names):
        if kind == "hyp":
            out["hyp:" + n] = orc.hyp_ref(n) if orc is not None else _h(None)
        elif kind == "obsv":
            out[n] = _h(facts.get("observers", {}).get(n))
        elif kind == "mig":
            out["mig_" + n] = _h(facts.get("migrations", {}).get(n))
        elif kind == "act":
            out["A_" + n] = _h(acts.get(n))
        elif kind == "s0":
            out["s0"] = _h({"state": facts.get("state"), "initial": facts.get("initial")})
        elif kind == "step":
            out["step"] = _h(step_src)
        elif n in BUILTINS:
            out[n] = _h({"builtin": n, "bend": BUILTINS[n][0], "rule_catalog_version": law.get("rule_catalog_version")})
        elif n.startswith("is_") and n[3:] in acts:
            out["A_" + n[3:]] = _h(acts[n[3:]])
        elif n in facts.get("consumers", {}):
            out[n] = _h(facts["consumers"][n])
        elif n in _TRACE_FNS:
            out["step"] = _h(step_src)
        else:
            out[n] = _h(None)   # a name the facts do not define: hashed as absent, so defining it changes the hash
    return out


def _oracles(oracles):
    if oracles is None or hasattr(oracles, "hyp_ref"):
        return oracles
    from .oracles import Oracles
    return Oracles(oracles)


def law_hash(law: dict, facts: dict | None, oracles=None) -> str:
    """The law's statement hash: 0.1/0.2 over the hashed keys; 0.3 with its refs into `facts` and, for hyp
    premises, into the oracle sidecar `oracles` (I12)."""
    if law.get("ir_version") == "holon-ir/0.3":
        return ir.statement_hash(law, refs=refs(law, facts or {}, oracles))
    return ir.statement_hash(law)
