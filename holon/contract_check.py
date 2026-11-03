"""Contract-file validity (I64's K1 format and K9's volatile view), split out of holon.contracts.

holon.rules.own decides which views are volatile by asking whether a contract file is valid. That makes this check a
generator input, so it sits in the holon-ir/0.3 closure. holon.contracts (the run's last step, G10's states and marks)
must stay outside every generator closure (K5), so the check lives here and holon.contracts re-exports it unchanged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-contract/0.1"
KINDS = ("intended", "volatile_view")
RULES = ("PAR", "UNDO", "NAT", "SYM", "FACT", "SORT", "DISCH", "OWN", "INTENT")
EVIDENCE = ("E1", "E2", "E3", "E4", "E5", "E6")
COMMON = {"contract_version", "id", "kind", "milestone", "rule", "facts", "maps_to", "evidence", "rationale"}
EXTRA = {"intended": {"scope", "l_weak"}, "volatile_view": {"view"}}
NOT_APPLICABLE = ("M0", "M1")


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def repo_path(x) -> bool:
    """K1: a repository path: relative, without '..'."""
    return isinstance(x, str) and bool(x) and not Path(x).is_absolute() and ".." not in Path(x).parts


def l_weak_law(lw) -> dict:
    """K1: the law K3 would derive from an l_weak, with neutral values in every other field, so that a schema error
    can only be the statement's."""
    return {"ir_version": "holon-ir/0.3", "law_id": "L_contract_C_check", "milestone": "T0", "rule": "INTENT",
            "subform": "intended_weak", "rule_catalog_version": "holon-rules/0.1", "facts": "facts.json",
            "facts_sha256": "0" * 64, "statement": lw, "maps_to": "check", "evidence": ["E1"], "notes": "check"}


# ---------------------------------------------------------------------------------------------------- K1, K9
def problems(c, root: Path = ROOT, stem: str | None = None) -> list:
    """Why a contract file is not valid (K1 format, K9 the volatile view's function), [] when it is. The texts are
    those of tests_m3/_i64.problems, which results/<M>/contracts.json repeats."""
    out = []
    if not isinstance(c, dict):
        return ["not a JSON object"]
    kind = c.get("kind")
    if kind not in KINDS:
        return [f"kind {kind!r} is not one of {KINDS}"]
    want = COMMON | EXTRA[kind]
    if set(c) != want:
        out.append(f"fields {sorted(set(c) ^ want)} are missing or not allowed")
    if c.get("contract_version") != VERSION:
        out.append("contract_version")
    cid = c.get("id")
    pref = "C_" if kind == "intended" else "V_"
    if not isinstance(cid, str) or not re.fullmatch(r"[CV]_[A-Za-z0-9_]+", cid) or not cid.startswith(pref):
        out.append(f"id {cid!r} (an intended contract is C_..., a volatile view V_...)")
    if stem is not None and cid != stem:
        out.append(f"id {cid!r} is not the file name {stem!r}")
    m = c.get("milestone")
    if not isinstance(m, str) or not re.fullmatch(r"[MT][0-9]+", m):
        out.append("milestone")
    elif m in NOT_APPLICABLE:
        out.append(f"milestone {m} (no contracts on M0 and M1)")
    if c.get("rule") not in RULES:
        out.append("rule")
    facts = c.get("facts")
    if not repo_path(facts) or not (Path(root) / facts).is_file():
        out.append(f"facts {facts!r} is not a file at a relative repository path")
    ev = c.get("evidence")
    if not isinstance(ev, list) or not ev or any(not isinstance(e, str) or e not in EVIDENCE for e in ev):
        out.append("evidence")
    for k in ("maps_to", "rationale"):
        if not isinstance(c.get(k), str) or not c[k].strip():
            out.append(k)
    if kind == "intended":
        scope = c.get("scope")
        laws = scope.get("laws") if isinstance(scope, dict) else None
        if not isinstance(scope, dict) or list(scope) != ["laws"] or not isinstance(laws, list) or not laws \
                or any(not isinstance(x, str) or not re.fullmatch(r"L[0-9]?_[A-Za-z0-9_]+", x) for x in laws):
            out.append("scope (exactly {\"laws\": [law ids]}, non-empty)")
        lw = c.get("l_weak")
        if not isinstance(lw, dict) or not {"binders", "claim"} <= set(lw):
            out.append("l_weak (an IR 0.3 statement)")
        else:
            from .schema import errors
            if errors(l_weak_law(lw), _load(ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json")):
                out.append("l_weak (an IR 0.3 statement)")
    else:
        v = c.get("view")
        if not isinstance(v, dict) or set(v) != {"facts", "function", "result"} or type(v.get("result")) is not int \
                or not repo_path(v.get("facts")) or not isinstance(v.get("function"), str):
            out.append("view (exactly {facts, function, result}, result an integer)")
        else:
            try:
                doc = _load(Path(root) / v["facts"])
                res = ((doc.get("go") or {}).get("slices") or {}).get("results") or []
                if not any(isinstance(r, dict) and r.get("function") == v["function"]
                           and type(r.get("result")) is int and r.get("result") == v["result"] for r in res):
                    out.append(f"view: {v['facts']} has no slice result {v['function']} #{v['result']}")
            except (OSError, ValueError, AttributeError):
                out.append(f"view: {v['facts']} is not a readable document")
    return out
