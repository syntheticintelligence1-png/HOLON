"""I64 instrument (= I33a: intent contracts and G10), fixed at the I64 prereg (BUILD_PLAN §0.1, "instruments are
inputs").

The contract is the docstring of tests_m3/test_contracts.py, rules K1-K10. This module writes K1, K2, K5, K6 and K9 out
a second time, independently of holon/, so that the tests can decide what holon must write and what G10 must say. It
reads contract files, law files, result records and facts documents as JSON; nothing here imports holon/.

  problems(contract, root)          K1 and K9: why a contract file is not valid ([] when it is)
  content_sha256(contract)          K2: the registry's hash of a contract
  derived_law(contract, root)       K3: the law holon contracts derive must write for an intended contract
  states(milestone, root)           K5: every contract of the milestone with its state (proved and current, or why not)
  expected_marks(milestone, root)   K5: {law id: {"contract", "l_weak"}} for the records the contracts must mark
  contracts_doc(milestone, root)    K5: results/<milestone>/contracts.json as the run's last step must write it
  marks(milestone, root)            K6: the marks the records carry
  g10(milestone, root)              K6: (passed, [reasons]) as G10 must decide it
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "holon-contract/0.1"
REGISTRY_VERSION = "holon-contracts-registry/0.1"
STATUS_VERSION = "holon-contracts/0.1"
KINDS = ("intended", "volatile_view")
RULES = ("PAR", "UNDO", "NAT", "SYM", "FACT", "SORT", "DISCH", "OWN", "INTENT")
EVIDENCE = ("E1", "E2", "E3", "E4", "E5", "E6")
COMMON = {"contract_version", "id", "kind", "milestone", "rule", "facts", "maps_to", "evidence", "rationale"}
EXTRA = {"intended": {"scope", "l_weak"}, "volatile_view": {"view"}}
NOT_APPLICABLE = ("M0", "M1")


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def contracts_dir(root: Path) -> Path:
    return Path(root) / "laws" / "CONTRACTS"


def contract_files(root: Path) -> list:
    d = contracts_dir(root)
    return sorted(p for p in d.glob("*.json") if p.name != "REGISTRY.json") if d.is_dir() else []


# ---------------------------------------------------------------------------------------------------- K1, K9
def problems(c: dict, root: Path = ROOT, stem: str | None = None) -> list:
    """K1 (format) and K9 (a volatile view names a function the Go document's slice results hold)."""
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
    if not isinstance(c.get("milestone"), str) or not re.fullmatch(r"[MT][0-9]+", c.get("milestone") or ""):
        out.append("milestone")
    elif c["milestone"] in NOT_APPLICABLE:
        out.append(f"milestone {c['milestone']} (no contracts on M0 and M1; Q15)")
    if c.get("rule") not in RULES:
        out.append("rule")
    facts = c.get("facts")
    if not isinstance(facts, str) or not (Path(root) / facts).is_file():
        out.append(f"facts {facts!r} is not a file")
    if not isinstance(c.get("evidence"), list) or not c["evidence"] or any(e not in EVIDENCE for e in c["evidence"]):
        out.append("evidence")
    for k in ("maps_to", "rationale"):
        if not isinstance(c.get(k), str) or not c[k].strip():
            out.append(k)
    if kind == "intended":
        laws = (c.get("scope") or {}).get("laws") if isinstance(c.get("scope"), dict) else None
        if set(c.get("scope") or {}) != {"laws"} or not isinstance(laws, list) or not laws \
                or any(not isinstance(x, str) or not re.fullmatch(r"L[0-9]?_[A-Za-z0-9_]+", x) for x in laws):
            out.append("scope (exactly {\"laws\": [law ids]}, non-empty)")
        lw = c.get("l_weak")
        if not isinstance(lw, dict) or not {"binders", "claim"} <= set(lw):
            out.append("l_weak (an IR 0.3 statement)")
    else:
        v = c.get("view")
        if not isinstance(v, dict) or set(v) != {"facts", "function", "result"} or not isinstance(v.get("result"), int):
            out.append("view (exactly {facts, function, result})")
        else:
            p = Path(root) / v["facts"]
            try:
                doc = load(p)
                res = ((doc.get("go") or {}).get("slices") or {}).get("results") or []
                if not any(r.get("function") == v["function"] and r.get("result") == v["result"] for r in res):
                    out.append(f"view: {v['facts']} has no slice result {v['function']} #{v['result']}")
            except (OSError, ValueError):
                out.append(f"view: {v['facts']} is not a readable document")
    return out


# ---------------------------------------------------------------------------------------------------- K2, K3
def content_sha256(c: dict) -> str:
    """K2: sha256 of the contract's canonical JSON (sorted keys, no whitespace)."""
    return sha256_bytes(canonical(c))


def derived_law(c: dict, root: Path = ROOT) -> dict:
    """K3: the law holon contracts derive writes to laws/<milestone>/L_contract_<id>.json for an intended contract."""
    facts = c["facts"]
    return {"ir_version": "holon-ir/0.3", "law_id": f"L_contract_{c['id']}", "milestone": c["milestone"],
            "rule": c["rule"], "subform": "intended_weak", "rule_catalog_version": "holon-rules/0.1",
            "facts": facts, "facts_sha256": sha256_bytes((Path(root) / facts).read_bytes()),
            "statement": c["l_weak"], "maps_to": c["maps_to"], "evidence": c["evidence"],
            "notes": f"L_weak of intent contract {c['id']} (laws/CONTRACTS/{c['id']}.json), derived by holon contracts"}


# ---------------------------------------------------------------------------------------------------- K5, K6
def states(milestone: str, root: Path = ROOT) -> list:
    """K5: [{"id", "kind", "state", "scope"}] for the contracts of the milestone, by id. state: "proved" (an intended
    contract whose derived law is its l_weak, and whose law and PROVED record were made over the facts file as it is
    now), "valid" (a volatile view with no problem), or the reason it is neither. K5 also has holon check that the
    record carries the derived law's statement_hash; this module does not recompute that hash (holon.gen.refs), so it
    leaves that one check to holon."""
    root = Path(root)
    out = []
    for p in contract_files(root):
        c = load(p)
        if not isinstance(c, dict) or c.get("milestone") != milestone:
            continue
        probs = problems(c, root, p.stem)
        row = {"id": c.get("id"), "kind": c.get("kind"),
               "scope": sorted((c.get("scope") or {}).get("laws") or []) if c.get("kind") == "intended" else []}
        if probs:
            row["state"] = "invalid: " + "; ".join(probs)
        elif c["kind"] == "volatile_view":
            row["state"] = "valid"
        else:
            lid = f"L_contract_{c['id']}"
            lp, rp = root / "laws" / milestone / f"{lid}.json", root / "results" / milestone / f"{lid}.json"
            if not lp.is_file() or not rp.is_file():
                row["state"] = "not derived or not decided"
            else:
                law, rec = load(lp), load(rp)
                now = sha256_bytes((root / c["facts"]).read_bytes())
                if law.get("statement") != c["l_weak"] or law.get("facts_sha256") != now:
                    row["state"] = "stale: the derived law is not the contract's L_weak over the current facts"
                elif rec.get("status") != "PROVED":
                    row["state"] = f"not proved: {rec.get('status')}"
                elif rec.get("facts_sha256") != now:
                    row["state"] = "stale: decided over other facts"
                else:
                    row["state"] = "proved"
        out.append(row)
    return sorted(out, key=lambda r: str(r["id"]))


def refuted(milestone: str, lid: str, root: Path = ROOT) -> bool:
    rp = Path(root) / "results" / milestone / f"{lid}.json"
    return rp.is_file() and load(rp).get("status") == "REFUTED"


def expected_marks(milestone: str, root: Path = ROOT) -> dict:
    """K5: every REFUTED record of a law in the scope of a proved intended contract must be marked, naming the least id
    among the proved contracts whose scope holds it: {law id: {"contract": id, "l_weak": "L_contract_<id>"}}."""
    root = Path(root)
    out = {}
    for s in states(milestone, root):   # by id, so the first proved contract to claim a law has the least id
        if s["kind"] != "intended" or s["state"] != "proved":
            continue
        for lid in s["scope"]:
            if lid not in out and refuted(milestone, lid, root):
                out[lid] = {"contract": s["id"], "l_weak": f"L_contract_{s['id']}"}
    return dict(sorted(out.items()))


def contracts_doc(milestone: str, root: Path = ROOT):
    """K5: results/<milestone>/contracts.json as the run's last step must write it; None (no file) when the milestone
    has no contract. marked: the REFUTED laws of a proved intended contract's scope, [] for every other contract."""
    rows = states(milestone, root)
    if not rows:
        return None
    for s in rows:
        s["marked"] = (sorted(lid for lid in s["scope"] if refuted(milestone, lid, root))
                       if s["kind"] == "intended" and s["state"] == "proved" else [])
    return {"contracts_version": STATUS_VERSION, "milestone": milestone, "contracts": rows}


def marks(milestone: str, root: Path = ROOT) -> dict:
    """K6: the marks the records carry, {law id: {"filter_bin", "contract", "l_weak"}}, for every record whose
    filter_bin is intended_bounded or that has the field intended (so a half-made mark shows)."""
    rdir = Path(root) / "results" / milestone
    out = {}
    for p in sorted(rdir.glob("L*.json")) if rdir.is_dir() else []:
        r = load(p)
        if r.get("filter_bin") == "intended_bounded" or "intended" in r:
            i = r.get("intended") if isinstance(r.get("intended"), dict) else {}
            out[p.stem] = {"filter_bin": r.get("filter_bin"), "contract": i.get("contract"), "l_weak": i.get("l_weak")}
    return out


def g10(milestone: str, root: Path = ROOT) -> tuple:
    """K6: (passed, reasons) for G10 on the milestone; (None, [reason]) where G10 is not applicable."""
    root = Path(root)
    if milestone in NOT_APPLICABLE:
        return None, [f"{milestone} holds no intent contracts: they start at M2 (whitepaper 5.9, BUILD_PLAN I33; Q15)"]
    reasons = []
    reg_p = contracts_dir(root) / "REGISTRY.json"
    reg = load(reg_p).get("contracts", {}) if reg_p.is_file() else {}
    mine = [load(p) for p in contract_files(root)]
    mine = [c for c in mine if isinstance(c, dict) and c.get("milestone") == milestone]
    for c in mine:
        r = reg.get(c.get("id"))
        if r is None or r.get("sha256") != content_sha256(c):
            reasons.append(f"{c.get('id')}: not in the registry, or changed since it was registered")
    for s in states(milestone, root):
        if s["state"] not in ("proved", "valid"):
            reasons.append(f"{s['id']}: {s['state']}")
    want = {k: {"filter_bin": "intended_bounded", **v} for k, v in expected_marks(milestone, root).items()}
    have = marks(milestone, root)
    for lid in sorted(set(have) | set(want)):
        if have.get(lid) != want.get(lid):
            reasons.append(f"{lid}: the record's mark {have.get(lid)} is not the contracts' {want.get(lid)}")
    return not reasons, reasons
