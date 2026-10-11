"""Result records v2 (whitepaper §8.6) and the model-assumption ledger (§8.5, Def 4.7).

A v2 record keeps every §8.6 item in its own field, next to the frozen v1 fields:

  status, statement_hash (law hash), model_sha256 (model hash), premises, scope_v2,
  kernels, independence_class, refinement_refs, replay (witness replay status), coverage

plus the cone of the law, its model_assumptions, the generator hash and the fields later
iterations fill (non_vacuity: I3, witness_provenance and filter_bin: I4, refinement_refs:
I16, coverage: I19). A pending field holds "pending:I<n>", never a made-up value.

The cone of a law is the set of generated model definitions its frozen statement reaches:
the `M.<name>` references of the emitted statement (a type for a constructor), closed
over references between definitions. model_assumptions are the spec/ledger entries whose
introducing definitions meet the cone. A facts bundle the ledger does not know is an
error: a record never silently carries no assumptions.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = Path("spec") / "ledger" / "assumptions.json"
RECORD_VERSION = "holon-record/0.2"

# Generators whose source determines the emitted Bend (bound into each record).
GENERATORS = {
    "holon-ir/0.1": ["holon/gen/model.py", "holon/gen/laws.py", "holon/gen/proofs.py"],
    "holon-ir/0.2": ["holon/gen/machine.py", "holon/gen/mlaws.py", "holon/gen/mproofs.py"],
}

_TOP = re.compile(r"^(def|type)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUAL = re.compile(r"(?<![\w.])M\.([A-Za-z_][A-Za-z0-9_]*)")
_COMMENT = re.compile(r"#[^\n]*")


class LedgerError(Exception):
    pass


# ---------------------------------------------------------------- cone of influence
def model_defs(model_text: str) -> dict[str, str]:
    """Top-level def/type name -> its text, comments removed."""
    text = _COMMENT.sub("", model_text)
    ms = list(_TOP.finditer(text))
    return {m.group(2): text[m.start():(ms[i + 1].start() if i + 1 < len(ms) else len(text))]
            for i, m in enumerate(ms)}


def _ctor_owner(defs: dict[str, str]) -> dict[str, str]:
    own = {}
    for name, body in defs.items():
        if body.startswith("type "):
            for line in body.splitlines()[1:]:
                m = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{", line)
                if m:
                    own[m.group(1)] = name
    return own


def _resolve(tok: str, defs: dict, own: dict) -> str | None:
    if tok in defs:
        return tok
    return own.get(tok)


def def_graph(defs: dict[str, str]) -> dict[str, set[str]]:
    own = _ctor_owner(defs)
    g = {}
    for name, body in defs.items():
        out = set()
        for tok in _IDENT.findall(body):
            r = _resolve(tok, defs, own)
            if r and r != name:
                out.add(r)
        g[name] = out
    return g


def roots(statement_text: str, defs: dict[str, str]) -> set[str]:
    own = _ctor_owner(defs)
    return {r for tok in _QUAL.findall(_COMMENT.sub("", statement_text)) if (r := _resolve(tok, defs, own))}


def cone(statement_text: str, model_text: str) -> list[str]:
    defs = model_defs(model_text)
    g = def_graph(defs)
    seen: set[str] = set()
    todo = sorted(roots(statement_text, defs))
    while todo:
        d = todo.pop()
        if d not in seen:
            seen.add(d)
            todo.extend(sorted(g[d] - seen))
    return sorted(seen)


def ir_roots_text(law: dict) -> str:
    """Fallback roots when the emitter cannot express a statement: every model name the IR uses."""
    names: set[str] = set()

    def walk(t):
        if isinstance(t, dict):
            for k in ("call", "fn", "obsv"):
                if isinstance(t.get(k), str):
                    names.add(t[k])
            if isinstance(t.get("mig"), str):
                names.add("mig_" + t["mig"])
            for k in ("run", "step", "obs", "s0"):
                if k in t:
                    names.add(k)
            for v in t.values():
                walk(v)
        elif isinstance(t, list):
            for v in t:
                walk(v)
    walk(law["statement"])
    return " ".join(f"M.{n}" for n in sorted(names))


# ---------------------------------------------------------------- ledger
@lru_cache(maxsize=None)
def _ledger(path: str) -> dict:
    return json.loads(Path(path).read_text())


def load_ledger(root: Path | str = ROOT) -> dict:
    return _ledger(str(Path(root) / LEDGER))


def bundle(facts_sha256: str, root: Path | str = ROOT) -> dict:
    for b in load_ledger(root)["bundles"]:
        if b["facts_sha256"] == facts_sha256:
            return b
    raise LedgerError(f"no ledger bundle for facts {facts_sha256}: add the bundle's model assumptions to {LEDGER} "
                      "before building records over it")


def resolve_bundle(facts_sha256: str, base_facts: str | None, root: Path | str = ROOT) -> tuple[dict, str]:
    """The ledger bundle for a record: an exact facts match, or else, for a run over facts derived
    from a registered file (the planted mutations of --no-registry runs), the bundle of that
    registered file, flagged "derived" in the record. Committed records must match exactly (the
    v2 schema accepts only "exact", so G9 rejects anything else). No match at all is an error."""
    try:
        return bundle(facts_sha256, root), "exact"
    except LedgerError:
        same = [b for b in load_ledger(root)["bundles"] if base_facts and b["facts"] == base_facts]
        if len(same) != 1:
            raise
        return same[0], "derived"


def _meets(entry: dict, cone_set: set[str]) -> bool:
    return any(p == "*" or any(fnmatch.fnmatchcase(d, p) for d in cone_set) for p in entry["introduced_by"])


def model_assumptions(facts_sha256: str, cone_set: set[str], root: Path | str = ROOT) -> list[str]:
    b = bundle(facts_sha256, root)
    return sorted(e["id"] for e in b["entries"] if _meets(e, set(cone_set)))


def unclassified(facts_sha256: str, model_text: str, root: Path | str = ROOT) -> list[str]:
    """Model definitions the ledger classifies neither by an entry nor by exactly one no_assumption group."""
    b = bundle(facts_sha256, root)
    bad = []
    for d in model_defs(model_text):
        by_entry = any(p != "*" and fnmatch.fnmatchcase(d, p) for e in b["entries"] for p in e["introduced_by"])
        groups = sum(1 for g in b["no_assumption"] if any(fnmatch.fnmatchcase(d, p) for p in g["defs"]))
        if not by_entry and groups != 1:
            bad.append(d)
    return bad


# ---------------------------------------------------------------- v2 fields
def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def generator_sha256(ir_version: str, root: Path | str = ROOT) -> str:
    h = hashlib.sha256()
    for rel in GENERATORS[ir_version]:
        h.update(rel.encode() + b"\0" + (Path(root) / rel).read_bytes() + b"\0")
    return h.hexdigest()


def _mentions(obj, key: str) -> bool:
    if isinstance(obj, dict):
        return key in obj or any(_mentions(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_mentions(v, key) for v in obj)
    return False


def scope_v2(law: dict, rec: dict) -> dict:
    st = law["statement"]
    binders = st.get("binders", [])
    if any(b["type"] == "State" for b in binders):
        at = "any"
    elif _mentions(st, "s0"):
        at = "s0"
    else:
        at = None
    if rec["status"] == "UNKNOWN":
        return {"kind": "bounded", "horizon": rec.get("bound"), "at_state": at}
    return {"kind": "unbounded", "horizon": None, "at_state": at}


def kernels(rec: dict) -> list[dict]:
    ver = rec["kernel"]["version"]
    checked = rec["status"] in ("PROVED", "REFUTED")
    out = [{"name": "bend2", "version": ver, "role": "primary", "result": "checked" if checked else "not_run"}]
    v = rec["kernel"].get("verdict", "not_run")
    if checked and v != "not_run":
        out.append({"name": "bendtt", "version": ver, "role": "second", "result": v, "shares_frontend_with": "bend2",
                    "note": "BendTT (--verdict) re-checks bend2's elaboration of the same file: it shares the front end, "
                            "so agreement is not independent evidence (class I1-shared, not I2)"})
    return out


def independence_class(rec: dict) -> str:
    if rec["status"] not in ("PROVED", "REFUTED"):
        return "none"
    return "I1-shared" if rec["kernel"].get("verdict") == "checked" else "I1"


def v2_fields(law: dict, rec: dict, statement_text: str, model_path: Path, base_facts: str | None,
              root: Path | str = ROOT) -> dict:
    """The v2 fields of a finished record (status, kernel, bound and replay already set).

    base_facts is the registered facts file (repo-relative) the run's facts stand for."""
    model_text = Path(model_path).read_text()
    c = cone(statement_text, model_text)
    refuted = rec["status"] == "REFUTED"
    b, match = resolve_bundle(rec["facts_sha256"], base_facts, root)
    return {
        "record_version": RECORD_VERSION,
        "model_sha256": sha256_file(model_path),
        "generator_sha256": generator_sha256(law["ir_version"], root),
        "cone": c,
        "ledger_match": match,
        "model_assumptions": sorted(e["id"] for e in b["entries"] if _meets(e, set(c))),
        "scope_v2": scope_v2(law, rec),
        "kernels": kernels(rec),
        "independence_class": independence_class(rec),
        "refinement_refs": "pending:I16",
        "coverage": "pending:I19",
        "non_vacuity": "pending:I3",
        "witness_provenance": "pending:I4" if refuted else None,
        "filter_bin": "pending:I4" if refuted else None,
    }
