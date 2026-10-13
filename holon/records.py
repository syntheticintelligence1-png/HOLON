"""Result records v2 (whitepaper §8.6) and the model-assumption ledger (§8.5, Def 4.7).

A v2 record keeps every §8.6 item in its own field, next to the frozen v1 fields:

  status, statement_hash (law hash), model_sha256 (model hash), premises, scope_v2,
  kernels, independence_class, refinement_refs, replay (witness replay status), coverage

kernels lists bend2 (primary), BendTT (second; shares bend2's front end, so I1-shared) and, since I9, for
holon-ir/0.1 laws, lean4 (second-independent: own emitters holon/gen/lean_*.py, Lean's elaborator and
kernel). independence_class is I2 exactly when lean4 checked the same verdict: holon.lean.kernel_entry
accepts the committed gen/<m>/lean/report.json only for the exact text emitted for this law, facts, status
and witness, and G7 re-checks it from scratch.

plus the cone of the law, its model_assumptions, the generator hash and the fields later
iterations fill: non_vacuity (I3), witness_provenance / filter_bin (I4, from the replay
report through holon.filter), refinement_refs (I16, refinement_refs below) and coverage (I19, coverage_field:
null unless the law's facts document is an extracted one) are filled. A pending field holds "pending:I<n>", never a
made-up value; no field is pending since I19.

refinement_refs (Def 4.7, §8.6 "the refinement records of the edges used") is the sorted list of
  * "results/M2/refinement/<edge>.json" for every per-edge refinement record (holon.refinement) of the
    law's milestone and facts whose edge is in the law's cone;
  * "replay/<m>/report.json#/refinement/per_action/<a>" for every action a of the milestone's trace
    corpus (holon.mreplay) whose step definition step_<a> (holon/gen/machine.py) is in the cone.

The cone of a law is the set of generated model definitions its frozen statement reaches:
the `M.<name>` references of the emitted statement (a type for a constructor), closed
over references between definitions. The references are textual tokens, so a local
variable spelled like a definition adds a spurious edge: the cone over-approximates,
which can only add assumptions, never hide one. Since I2 it is cross-checked against the
checker's own BendTT dependency graph (holon/bindings.py): for all 24 laws the two agree on
the model's own definitions (tests_m2/test_bindings.py, prediction I2-P4).

model_assumptions are the spec/ledger entries whose introducing definitions meet the cone.
Which bundle applies (resolve_bundle):
  * exact: the facts sha256 has a ledger bundle; the only match the v2 schema accepts;
  * derived: a run over facts derived from a registered file (the planted mutations of
    `holon run --no-registry --facts ...`, which the frozen tests/test_31 requires to
    succeed) uses that file's bundle, flagged in the record, and only if every definition
    in the cone is still classified by it; otherwise LedgerError;
  * anything else (no registered base, or a base the ledger does not know): LedgerError.
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

# Entry modules of the generators whose source determines the emitted Bend. generator_sha256
# hashes these and every holon module they import, transitively (generator_files).
GENERATORS = {
    "holon-ir/0.1": ["holon/gen/model.py", "holon/gen/laws.py", "holon/gen/proofs.py"],
    "holon-ir/0.2": ["holon/gen/machine.py", "holon/gen/mlaws.py", "holon/gen/mproofs.py"],
    "holon-ir/0.3": ["holon/gen/machine.py", "holon/gen/mlaws.py", "holon/gen/mproofs.py", "holon/gen/refs.py",
                     "holon/gen/core.py"],
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
    st = law["statement"]
    # types the emitters print: binder types, and the types of term kinds
    types01 = {"Header": "Hdr"}
    types02 = {"State": "HSt", "Trace": "HAct", "Act": "HAct"}
    for b in st.get("forall", []):
        if b["type"] in types01:
            names.add(types01[b["type"]])
    for b in st.get("binders", []):
        if b["type"] in types02:
            names.add(types02[b["type"]])

    def kinds(t):
        if isinstance(t, dict):
            if "field" in t:
                names.update({"Hdr", f"get_{t['field']}"})
            if "proj" in t:
                names.add("HSt")
            if "act" in t:
                names.add("HAct")
            if "obs" in t:
                names.add("HObs")
            for v in t.values():
                kinds(v)
        elif isinstance(t, list):
            for v in t:
                kinds(v)
    kinds(st)
    return " ".join(f"M.{n}" for n in sorted(names))


# ---------------------------------------------------------------- ledger
@lru_cache(maxsize=None)
def _ledger(path: str) -> dict:
    return json.loads(Path(path).read_text())


def load_ledger(root: Path | str = ROOT) -> dict:
    return _ledger(str(Path(root) / LEDGER))


def all_bundles(root: Path | str = ROOT, facts_path: Path | str | None = None, milestone: str | None = None) -> list[dict]:
    """The ledger's bundles, the "bundles" of every milestone ledger spec/M<n>/ledger.json (a document first
    modelled at that milestone, I20: the extracted model's), plus the bundles of a sidecar ledger.json next to a
    facts file (a fixture or a target outside spec/ may carry its own ledger; I6). With a milestone, a bundle extended
    by spec/<milestone>/ledger.json (milestone_extensions) carries the extension's no_assumption groups too."""
    out = list(load_ledger(root)["bundles"])
    for p in sorted(Path(root).glob("spec/M*/ledger.json")):   # the bundles a milestone registers (I20: a document
        out += list(json.loads(p.read_text(encoding="utf-8")).get("bundles") or [])   # first modelled there)
    if facts_path is not None:
        side = (Path(root) / facts_path).parent / "ledger.json"
        if side.exists():
            out += json.loads(side.read_text(encoding="utf-8"))["bundles"]
        out += _linked_bundles(Path(root), facts_path)
    exts = milestone_extensions(root, milestone) if milestone else []
    for i, b in enumerate(out):
        for x in exts:
            if x.get("facts") == b.get("facts") and x.get("facts_sha256") == b.get("facts_sha256"):
                out[i] = b = {**b, "no_assumption": list(b["no_assumption"]) + list(x.get("no_assumption") or [])}
    return out


def _linked_bundles(root: Path, facts_path) -> list[dict]:
    """I24: the bundle of a linked codec document (holon.diagram.linked), generated from it by
    holon.gen.linked.declared_bundle: the assumptions its two extracted documents declare, each introduced by the
    definitions generated from that document, and the layer's own A-codec-domain. Never hand-written: the document is
    itself generated (holon codecs), so its bundle follows it byte for byte."""
    p = Path(root) / facts_path
    if p.suffix != ".json" or not p.is_file():
        return []
    try:
        raw = p.read_bytes()
        doc = json.loads(raw)
    except (OSError, ValueError):
        return []
    from .diagram.linked import is_linked
    if not is_linked(doc):
        return []
    from .gen.linked import Unsupported, declared_bundle
    rel = p.resolve().relative_to(Path(root).resolve()).as_posix() if p.resolve().is_relative_to(Path(root).resolve()) \
        else str(facts_path)
    try:
        return [declared_bundle(doc, rel, hashlib.sha256(raw).hexdigest(), Path(root))]
    except Unsupported:
        return []


def milestone_extensions(root: Path | str, milestone: str) -> list[dict]:
    """spec/<milestone>/ledger.json "extends": per facts bundle, the no_assumption groups of the definitions that
    milestone's model generator adds to the bundle's model (I15: the M2 model's Reach, oracle tables and permission
    predicates). The base ledger is unchanged, so what reads it (the diagrams) is unchanged."""
    p = Path(root) / "spec" / milestone / "ledger.json"
    return list(json.loads(p.read_text(encoding="utf-8")).get("extends") or []) if p.exists() else []


def bundle(facts_sha256: str, root: Path | str = ROOT, facts_path: Path | str | None = None,
           milestone: str | None = None) -> dict:
    for b in all_bundles(root, facts_path, milestone):
        if b["facts_sha256"] == facts_sha256:
            return b
    raise LedgerError(f"no ledger bundle for facts {facts_sha256}: add the bundle's model assumptions to {LEDGER} "
                      "before building records over it")


def resolve_bundle(facts_sha256: str, base_facts: str | None, root: Path | str = ROOT,
                   model_text: str | None = None, cone_set: set[str] | None = None,
                   milestone: str | None = None) -> tuple[dict, str]:
    """(bundle, "exact" | "derived"); see the module docstring. LedgerError when neither applies. milestone: the run's
    milestone, whose ledger extension classifies what its model adds (milestone_extensions)."""
    try:
        return bundle(facts_sha256, root, base_facts), "exact"
    except LedgerError:
        same = [b for b in all_bundles(root, base_facts, milestone) if base_facts and b["facts"] == base_facts]
        if len(same) != 1:
            raise LedgerError(f"no ledger bundle for facts {facts_sha256} and no registered base bundle "
                              f"({base_facts!r}): add its model assumptions to {LEDGER}") from None
        b = same[0]
        if model_text is not None:
            loose = sorted(set(unclassified(b["facts_sha256"], model_text, root, base_facts, milestone))
                           & set(cone_set or ()))
            if loose:
                raise LedgerError(f"derived facts for {base_facts}: definitions {loose} in the cone are not "
                                  f"classified by its ledger bundle, so its assumptions may not apply")
        return b, "derived"


def _meets(entry: dict, cone_set: set[str]) -> bool:
    return any(p == "*" or any(fnmatch.fnmatchcase(d, p) for d in cone_set) for p in entry["introduced_by"])


def model_assumptions(facts_sha256: str, cone_set: set[str], root: Path | str = ROOT,
                      facts_path: Path | str | None = None) -> list[str]:
    b = bundle(facts_sha256, root, facts_path)
    return sorted(e["id"] for e in b["entries"] if _meets(e, set(cone_set)))


def unclassified(facts_sha256: str, model_text: str, root: Path | str = ROOT,
                 facts_path: Path | str | None = None, milestone: str | None = None) -> list[str]:
    """Model definitions the ledger classifies neither by an entry nor by exactly one no_assumption group. The ghost
    section of an instrumented model (I15, after GHOST_MARKER) is not the model: its definitions only evaluate the
    model's own terms (no state, nothing above the marker names them), so they carry no assumption to classify."""
    from .sorts.sites import GHOST_MARKER
    b = bundle(facts_sha256, root, facts_path, milestone)
    bad = []
    for d in model_defs(model_text.split(GHOST_MARKER, 1)[0]):
        by_entry = any(p != "*" and fnmatch.fnmatchcase(d, p) for e in b["entries"] for p in e["introduced_by"])
        groups = sum(1 for g in b["no_assumption"] if any(fnmatch.fnmatchcase(d, p) for p in g["defs"]))
        if not by_entry and groups != 1:
            bad.append(d)
    return bad


# ---------------------------------------------------------------- v2 fields
def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _holon_imports(rel: str, root: Path) -> set[str]:
    """Repo-relative paths of the holon modules a module imports (relative and absolute forms)."""
    import ast
    path = root / rel
    pkg = Path(rel).parent.parts
    out = set()
    for n in ast.walk(ast.parse(path.read_text())):
        mods = []
        if isinstance(n, ast.ImportFrom):
            if n.level:
                base = list(pkg[:len(pkg) - (n.level - 1)])
            elif (n.module or "").split(".")[0] == "holon":
                base = []
            else:
                continue
            parts = base + ((n.module or "").split(".") if n.module else [])
            mods.append(parts)
            mods += [parts + [a.name] for a in n.names]  # `from . import facts`
        elif isinstance(n, ast.Import):
            mods += [a.name.split(".") for a in n.names if a.name.split(".")[0] == "holon"]
        for parts in mods:
            for cand in (Path(*parts).with_suffix(".py"), Path(*parts) / "__init__.py"):
                if parts and (root / cand).is_file():
                    out.add(cand.as_posix())
    return out


def generator_files(ir_version: str, root: Path | str = ROOT) -> list[str]:
    """The generator modules, transitively, plus (for state machines, since I6) the target libraries
    and search hints the generators read as input (holon.gen.targetlib), and (for holon-ir/0.3, since I12)
    the oracle sidecars (holon.gen.oracles)."""
    root = Path(root)
    seen, todo = set(), list(GENERATORS[ir_version])
    while todo:
        rel = todo.pop()
        if rel not in seen:
            seen.add(rel)
            todo.extend(sorted(_holon_imports(rel, root) - seen))
    if ir_version in ("holon-ir/0.2", "holon-ir/0.3"):
        for pat in ("spec/lib/*.lib.json", "spec/*/lib/*.lib.json", "spec/*/policy_hints.mjs"):
            seen |= {p.relative_to(root).as_posix() for p in root.glob(pat)}
    if ir_version == "holon-ir/0.3":   # oracle sidecars shape the M2+ models (I12); M0 and M1 never read one
        seen |= {p.relative_to(root).as_posix() for p in root.glob("spec/*/lib/oracles.json")}
    return sorted(seen)


def generator_sha256(ir_version: str, root: Path | str = ROOT) -> str:
    h = hashlib.sha256()
    for rel in generator_files(ir_version, root):
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


def kernels(rec: dict, lean_entry: dict | None = None) -> list[dict]:
    """bend2 (primary), BendTT (second, shares bend2's front end) and, for the laws the Lean emitters cover,
    lean4 (second-independent: its own emitters, elaborator and kernel; holon.lean.kernel_entry)."""
    ver = rec["kernel"]["version"]
    checked = rec["status"] in ("PROVED", "REFUTED")
    out = [{"name": "bend2", "version": ver, "role": "primary", "result": "checked" if checked else "not_run"}]
    v = rec["kernel"].get("verdict", "not_run")
    if checked and v != "not_run":
        out.append({"name": "bendtt", "version": ver, "role": "second", "result": v, "shares_frontend_with": "bend2",
                    "note": "BendTT (--verdict) re-checks bend2's elaboration of the same file: it shares the front end, "
                            "so agreement is not independent evidence (class I1-shared, not I2)"})
    if lean_entry is not None:
        out.append(dict(lean_entry))
    return out


def independence_class(rec: dict, lean_entry: dict | None = None) -> str:
    """I2 only when an independent kernel (lean4) re-checked the same verdict; BendTT alone is I1-shared."""
    if rec["status"] not in ("PROVED", "REFUTED"):
        return "none"
    if lean_entry is not None and lean_entry.get("result") == "checked":
        return "I2"
    return "I1-shared" if rec["kernel"].get("verdict") == "checked" else "I1"


STEP_PREFIX = "step_"  # holon/gen/machine.py names the step definition of action <a> step_<a>


def refinement_refs(law: dict, cone_set: set[str], root: Path | str = ROOT) -> list[str]:
    """The refinement records of the edges the law's cone uses (see the module docstring)."""
    root, m, out = Path(root), law["milestone"], set()
    for f in sorted((root / "results" / "M2" / "refinement").glob("*.json")):
        try:
            r = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if (isinstance(r, dict) and r.get("milestone") == m and r.get("facts_sha256") == law["facts_sha256"]
                and r.get("edge") in cone_set):
            out.add(f"results/M2/refinement/{f.name}")
    rep = root / "replay" / m / "report.json"
    try:
        pa = (json.loads(rep.read_text()).get("refinement") or {}).get("per_action") if rep.exists() else None
    except (OSError, ValueError):
        pa = None
    for a in sorted(pa or {}):
        if STEP_PREFIX + a in cone_set:
            out.add(f"replay/{m}/report.json#/refinement/per_action/{a}")
    return sorted(out)


def v2_fields(law: dict, rec: dict, statement_text: str, model_path: Path, base_facts: str | None,
              compiled_path: Path | None, root: Path | str = ROOT, lean_entry: dict | None = None,
              ledger_required: bool = True) -> dict:
    """The v2 fields of a finished record (status, kernel, bound and replay already set).

    base_facts is the registered facts file (repo-relative) the run's facts stand for;
    compiled_path is the compiled model the refuter executed; lean_entry is the record's lean4 kernel
    entry (holon.lean.kernel_entry; None where the Lean emitters do not apply). ledger_required=False (test
    milestones only, holon.mpipeline.test_milestone: fixtures that are no target) records a document without a ledger
    bundle as ledger_match "none" with no model assumptions, which the v2 schema never accepts; otherwise LedgerError."""
    model_text = Path(model_path).read_text()
    c = cone(statement_text, model_text)
    refuted = rec["status"] == "REFUTED"
    try:
        b, match = resolve_bundle(rec["facts_sha256"], base_facts, root, model_text, set(c), law.get("milestone"))
    except LedgerError:
        if ledger_required:
            raise
        b, match = None, "none"
    wp, fb = None, None
    if refuted:  # provisional finding filter (I4), from the committed replay report
        from .filter import record_fields
        from .replay import load_report, witness_sha256
        wp, fb = record_fields(load_report(law["milestone"], Path(root)), law["law_id"], rec.get("witness"),
                               witness_sha256)
    return {
        "record_version": RECORD_VERSION,
        "model_sha256": sha256_file(model_path),
        "compiled_sha256": sha256_file(compiled_path) if compiled_path else None,
        "generator_sha256": generator_sha256(law["ir_version"], root),
        "cone": c,
        "ledger_match": match,
        "model_assumptions": model_assumptions(b["facts_sha256"], set(c), root, base_facts) if b else [],
        "scope_v2": scope_v2(law, rec),
        "kernels": kernels(rec, lean_entry),
        "independence_class": independence_class(rec, lean_entry),
        "refinement_refs": refinement_refs(law, set(c), root),
        "coverage": coverage_field(law, root),
        "non_vacuity": None,  # set by the pipeline from holon.inhabit (I3)
        "witness_provenance": wp,
        "filter_bin": fb,
        **evidence_fields(law, rec, root),
    }


def coverage_field(law: dict, root: Path | str = ROOT) -> dict | None:
    """I19 (§8.6 coverage; holon.coverage): {"document", "debt", "unaccounted"} for an M2+ law whose facts document is
    an extracted document (*.extracted.json), the numbers of debt entries and unaccounted statements of that document
    in the committed report gen/<milestone>/coverage.json; null for every other law (hand-written facts: M0, M1 and,
    until I20 adopts an extracted document, M2). A law over an extracted document that the report does not list is an
    error: run `python -m holon coverage` first."""
    facts = law.get("facts")
    if law.get("milestone") in ("M0", "M1") or not isinstance(facts, str) or not facts.endswith(".extracted.json"):
        return None
    rp = Path(root) / "gen" / law["milestone"] / "coverage.json"
    rep = json.loads(rp.read_text()) if rp.exists() else {"documents": []}
    for d in rep.get("documents", []):
        if d.get("document") == facts:
            return {"document": facts, "debt": len(d["debt"]), "unaccounted": len(d["unaccounted"])}
    raise ValueError(f"{law.get('law_id')}: its facts document {facts} has no entry in "
                     f"gen/{law['milestone']}/coverage.json (python -m holon coverage --milestone {law['milestone']})")


def evidence_fields(law: dict, rec: dict, root: Path | str = ROOT) -> dict:
    """I14: evidence_levels, evidence_triage and evidence_override, from the committed evidence set
    (gen/M2/evidence.json for M0-M2) and config/evidence_overrides.json (holon.diagram.evidence.record_fields).
    The frozen v1 `triage` is never touched. A law the set does not cover (planted mutations, toy targets) gets
    null levels and the computed triage; nothing fails here, GEVID reports what is wrong."""
    from .diagram.evidence import record_fields
    return record_fields(law, rec.get("status"), root)
