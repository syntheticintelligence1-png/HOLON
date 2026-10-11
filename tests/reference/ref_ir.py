"""Trusted reference for the HOLON law IR (holon-ir/0.1): hashing and evaluation.

Frozen test oracle. See docs/M0_SPEC.md section "Law IR" for the format.
"""
from __future__ import annotations

import hashlib
import json

from . import ref_model as M

HASHED_KEYS = ("ir_version", "law_id", "rule", "facts_sha256", "statement")


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def statement_hash(law: dict) -> str:
    core = {k: law[k] for k in HASHED_KEYS}
    return "sha256:" + hashlib.sha256(canonical_json(core)).hexdigest()


def eval_term(t: dict, env: dict, facts: dict):
    if "var" in t:
        return env[t["var"]]
    if "bytes" in t:
        return M.unhex(t["bytes"])
    if "field" in t:
        return env_field(eval_term(t["of"], env, facts), t["field"])
    if "call" in t:
        return M.call(facts, t["call"], [eval_term(a, env, facts) for a in t["args"]])
    if "some" in t:
        return ("some", eval_term(t["some"], env, facts))
    raise ValueError(f"unknown term {t}")


def env_field(record: dict, name: str):
    return record[name]


def eval_prop(p: dict, env: dict, facts: dict) -> tuple[bool, object, object]:
    """Returns (holds, lhs_value, rhs_value). Only 'eq' exists in holon-ir/0.1."""
    (a, b), = [p["eq"]]
    lv, rv = eval_term(a, env, facts), eval_term(b, env, facts)
    return lv == rv, lv, rv


def check(law: dict, facts: dict, env: dict) -> dict:
    """Evaluate a law at one assignment of its binders.

    Returns {"premises": bool, "claim": bool|None, "lhs": .., "rhs": ..}.
    claim is None when premises fail or a function is undefined on the input.
    """
    st = law["statement"]
    for prem in st.get("assume", []):
        ok, _, _ = eval_prop(prem, env, facts)
        if not ok:
            return {"premises": False, "claim": None, "lhs": None, "rhs": None}
    try:
        holds, lv, rv = eval_prop(st["claim"], env, facts)
    except M.DomainError as e:
        return {"premises": True, "claim": None, "lhs": None, "rhs": None, "domain_error": str(e)}
    return {"premises": True, "claim": holds, "lhs": lv, "rhs": rv}


def env_from_witness(law: dict, facts: dict, witness: dict) -> dict:
    env = {}
    for b in law["statement"]["forall"]:
        raw = witness[b["name"]]
        if b["type"] == "Header":
            env[b["name"]] = M.header_from_json(facts, raw)
        elif b["type"] == "Bytes":
            env[b["name"]] = M.unhex(raw)
        else:
            raise ValueError(b["type"])
    return env
