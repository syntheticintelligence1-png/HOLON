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

K5 also has holon check that a proved contract's record carries its derived law's statement_hash. This module does not
recompute that hash (holon.gen.refs), so g10 and states leave that one check to holon. It validates an l_weak against
spec/schemas/law_ir_0_3.schema.json with the frozen test oracle's validator (tests/reference/mini_schema.py), which
holon may not import.
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
NA_WHY = ("{m} holds no intent contracts: they start at M2 (BUILD_PLAN §2 invariant 10 and §4 I33; whitepaper 5.9; "
          "Q15 is still open)")


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> bytes:
    """K2: UTF-8, sorted keys, separators (",", ":"), ensure_ascii False."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def contracts_dir(root: Path) -> Path:
    return Path(root) / "laws" / "CONTRACTS"


def contract_files(root: Path) -> list:
    d = contracts_dir(root)
    return sorted(p for p in d.glob("*.json") if p.name != "REGISTRY.json") if d.is_dir() else []


def contract_docs(root: Path) -> list:
    """[(path, document)] for every contract file; the document is None when the file is not JSON."""
    out = []
    for p in contract_files(root):
        try:
            out.append((p, load(p)))
        except (OSError, ValueError):
            out.append((p, None))
    return out


def milestone_of(c) -> str | None:
    """The milestone a contract file belongs to for G10: its milestone field when that names a milestone G10 applies
    to (M<n> or T<n>, not M0 or M1), else None."""
    m = c.get("milestone") if isinstance(c, dict) else None
    return m if isinstance(m, str) and re.fullmatch(r"[MT][0-9]+", m) and m not in NOT_APPLICABLE else None


def repo_path(x) -> bool:
    """K1: a repository path: relative, without '..'."""
    return isinstance(x, str) and bool(x) and not Path(x).is_absolute() and ".." not in Path(x).parts


def l_weak_law(lw) -> dict:
    """K1: the law K3 would derive from an l_weak, with neutral values in every other field, so that a schema error
    can only be the statement's."""
    return {"ir_version": "holon-ir/0.3", "law_id": "L_contract_C_check", "milestone": "T0", "rule": "INTENT",
            "subform": "intended_weak", "rule_catalog_version": "holon-rules/0.1", "facts": "facts.json",
            "facts_sha256": "0" * 64, "statement": lw, "maps_to": "check", "evidence": ["E1"], "notes": "check"}


def scope_of(c) -> list:
    """K5: the sorted law ids of an intended contract's scope ([] for a view, or a scope that is not a list of ids)."""
    s = c.get("scope") if isinstance(c, dict) and c.get("kind") == "intended" else None
    laws = s.get("laws") if isinstance(s, dict) else None
    return sorted(x for x in laws if isinstance(x, str)) if isinstance(laws, list) else []


# ---------------------------------------------------------------------------------------------------- K1, K9
def problems(c, root: Path = ROOT, stem: str | None = None) -> list:
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
        s = c.get("scope")
        laws = s.get("laws") if isinstance(s, dict) else None
        if not isinstance(s, dict) or list(s) != ["laws"] or not isinstance(laws, list) or not laws \
                or any(not isinstance(x, str) or not re.fullmatch(r"L[0-9]?_[A-Za-z0-9_]+", x) for x in laws):
            out.append("scope (exactly {\"laws\": [law ids]}, non-empty)")
        lw = c.get("l_weak")
        if not isinstance(lw, dict) or not {"binders", "claim"} <= set(lw):
            out.append("l_weak (an IR 0.3 statement)")
        else:
            from tests.reference import mini_schema
            if mini_schema.errors(l_weak_law(lw), load(ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json")):
                out.append("l_weak (an IR 0.3 statement)")
    else:
        v = c.get("view")
        if not isinstance(v, dict) or set(v) != {"facts", "function", "result"} or type(v.get("result")) is not int \
                or not repo_path(v.get("facts")) or not isinstance(v.get("function"), str):
            out.append("view (exactly {facts, function, result}, result an integer)")
        else:
            try:
                doc = load(Path(root) / v["facts"])
                res = ((doc.get("go") or {}).get("slices") or {}).get("results") or []
                if not any(isinstance(r, dict) and r.get("function") == v["function"] and type(r.get("result")) is int
                           and r.get("result") == v["result"] for r in res):
                    out.append(f"view: {v['facts']} has no slice result {v['function']} #{v['result']}")
            except (OSError, ValueError, AttributeError):
                out.append(f"view: {v['facts']} is not a readable document")
    return out


# ---------------------------------------------------------------------------------------------------- K2, K3
def content_sha256(c: dict) -> str:
    """K2: sha256 of the contract's canonical JSON."""
    return sha256_bytes(canonical(c))


def derived_law(c: dict, root: Path = ROOT) -> dict:
    """K3: the law holon contracts derive writes to laws/<milestone>/L_contract_<id>.json for an intended contract."""
    facts = c["facts"]
    return {"ir_version": "holon-ir/0.3", "law_id": f"L_contract_{c['id']}", "milestone": c["milestone"],
            "rule": c["rule"], "subform": "intended_weak", "rule_catalog_version": "holon-rules/0.1",
            "facts": facts, "facts_sha256": sha256_bytes((Path(root) / facts).read_bytes()),
            "statement": c["l_weak"], "maps_to": c["maps_to"], "evidence": c["evidence"],
            "notes": f"L_weak of intent contract {c['id']} (laws/CONTRACTS/{c['id']}.json), derived by holon contracts"}


# ---------------------------------------------------------------------------------------------------- K5
def states(milestone: str, root: Path = ROOT) -> list:
    """K5: [{"id", "kind", "scope", "state"}] for the contracts of the milestone, by id. state: "proved" (an intended
    contract whose derived law is its l_weak, and whose law and PROVED record were made over the facts file as it is
    now), "valid" (a volatile view with no problem), or "invalid: ...", "not derived or not decided", "stale: ...",
    "not proved: <status>"."""
    root = Path(root)
    out = []
    for p, c in contract_docs(root):
        if milestone_of(c) != milestone:
            continue
        probs = problems(c, root, p.stem)
        row = {"id": c.get("id"), "kind": c.get("kind"), "scope": scope_of(c)}
        if probs:
            row["state"] = "invalid: " + "; ".join(probs)
        elif c["kind"] == "volatile_view":
            row["state"] = "valid"
        else:
            row["state"] = intended_state(c, milestone, root)
        out.append(row)
    return sorted(out, key=lambda r: str(r["id"]))


def intended_state(c: dict, milestone: str, root: Path) -> str:
    lid = f"L_contract_{c['id']}"
    lp, rp = root / "laws" / milestone / f"{lid}.json", root / "results" / milestone / f"{lid}.json"
    if not lp.is_file() or not rp.is_file():
        return "not derived or not decided"
    try:
        law, rec = load(lp), load(rp)
    except ValueError:
        return "not derived or not decided"
    now = sha256_bytes((root / c["facts"]).read_bytes())
    if not isinstance(law, dict) or law.get("statement") != c["l_weak"] or law.get("facts_sha256") != now:
        return "stale: the derived law is not the contract's L_weak over the current facts"
    if not isinstance(rec, dict) or rec.get("status") != "PROVED":
        return f"not proved: {rec.get('status') if isinstance(rec, dict) else None}"
    if rec.get("facts_sha256") != now:
        return "stale: decided over other facts"
    return "proved"


def refuted(milestone: str, lid: str, root: Path = ROOT) -> bool:
    rp = Path(root) / "results" / milestone / f"{lid}.json"
    try:
        r = load(rp) if rp.is_file() else None
    except ValueError:
        return False
    return isinstance(r, dict) and r.get("status") == "REFUTED"


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
    has no contract. marked: under every proved intended contract, each REFUTED law of its scope (so a law in several
    scopes is listed under each, while its record names only the least id); [] for every other contract."""
    rows = states(milestone, root)
    if not rows:
        return None
    for s in rows:
        s["marked"] = (sorted(lid for lid in s["scope"] if refuted(milestone, lid, root))
                       if s["kind"] == "intended" and s["state"] == "proved" else [])
    return {"contracts_version": STATUS_VERSION, "milestone": milestone, "contracts": rows}


# ---------------------------------------------------------------------------------------------------- K6
def marks(milestone: str, root: Path = ROOT) -> dict:
    """K6: the marks the records carry, {law id: {"filter_bin", "contract", "l_weak"}}, for every record whose
    filter_bin is intended_bounded or that has the field intended (so a half-made mark shows)."""
    rdir = Path(root) / "results" / milestone
    out = {}
    for p in sorted(rdir.glob("L*.json")) if rdir.is_dir() else []:
        try:
            r = load(p)
        except ValueError:
            continue
        if isinstance(r, dict) and (r.get("filter_bin") == "intended_bounded" or "intended" in r):
            i = r.get("intended") if isinstance(r.get("intended"), dict) else {}
            out[p.stem] = {"filter_bin": r.get("filter_bin"), "contract": i.get("contract"), "l_weak": i.get("l_weak")}
    return out


def g10(milestone: str, root: Path = ROOT) -> tuple:
    """K6: (passed, reasons) for G10 on the milestone; (None, [reason]) where G10 is not applicable."""
    root = Path(root)
    if milestone in NOT_APPLICABLE:
        return None, [NA_WHY.format(m=milestone)]
    reasons = []
    docs = contract_docs(root)
    reg_p = contracts_dir(root) / "REGISTRY.json"
    reg = {}
    if reg_p.is_file():
        try:
            doc = load(reg_p)
        except ValueError:
            doc = None
        if not isinstance(doc, dict) or doc.get("registry_version") != REGISTRY_VERSION \
                or not isinstance(doc.get("contracts"), dict):
            reasons.append(f"REGISTRY.json: not a {REGISTRY_VERSION} document")
        else:
            reg = doc["contracts"]
    for p, c in docs:   # a file G10 cannot attribute to a milestone it applies to fails it everywhere it applies
        if milestone_of(c) is None:
            reasons.append(f"{p.name}: belongs to no milestone G10 applies to ({'; '.join(problems(c, root, p.stem))})")
    for cid, r in sorted(reg.items()):   # so does a registry entry that is not one, or names no such milestone
        if not isinstance(r, dict) or set(r) != {"milestone", "kind", "sha256"} \
                or not all(isinstance(r[k], str) for k in ("milestone", "kind", "sha256")):
            reasons.append(f"REGISTRY.json: the entry {cid} is not {{milestone, kind, sha256}}")
        elif milestone_of(r) is None:
            reasons.append(f"REGISTRY.json: the entry {cid} is for {r['milestone']}, a milestone G10 never runs on")
    mine = {c["id"]: c for p, c in docs if milestone_of(c) == milestone and isinstance(c.get("id"), str)}
    for cid, c in sorted(mine.items()):
        r = reg.get(cid)
        if not isinstance(r, dict) or r.get("sha256") != content_sha256(c) or r.get("milestone") != c.get("milestone") \
                or r.get("kind") != c.get("kind"):
            reasons.append(f"{cid}: not in the registry, or changed since it was registered")
    for cid, r in sorted(reg.items()):
        if isinstance(r, dict) and r.get("milestone") == milestone and cid not in mine:
            reasons.append(f"{cid}: registered for {milestone}, but laws/CONTRACTS/{cid}.json is not one of its "
                           "contracts")
    for s in states(milestone, root):
        if s["state"] not in ("proved", "valid"):
            reasons.append(f"{s['id']}: {s['state']}")
    rdir = root / "results" / milestone
    for p in sorted(rdir.glob("L*.json")) if rdir.is_dir() else []:
        try:
            r = load(p)
        except ValueError:
            r = None
        if not isinstance(r, dict):
            reasons.append(f"{p.stem}: the record is not a JSON object")
    want = {k: {"filter_bin": "intended_bounded", **v} for k, v in expected_marks(milestone, root).items()}
    have = marks(milestone, root)
    for lid in sorted(set(have) | set(want)):
        if have.get(lid) != want.get(lid):
            reasons.append(f"{lid}: the record's mark {have.get(lid)} is not the contracts' {want.get(lid)}")
    return not reasons, reasons
