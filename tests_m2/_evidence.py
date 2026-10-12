"""Shared helpers for the I14 evidence tests (tests_m2/test_evidence*.py).

The contract these helpers read is stated in full in the docstring of tests_m2/test_evidence.py. Nothing here
imports holon/ at module level: the CLI runs as a subprocess, and the code under test is imported lazily inside
the functions that need it, so a missing module fails the test that uses it (red), never the import of a test
module. The sha256 of the evidence document, the E6 tokenizer and the E1 getter recovery are recomputed here
independently of holon (instruments fixed at the I14 prereg).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json, run_holon

OUT = ROOT / "gen" / "M2" / "evidence.json"
SCHEMA = ROOT / "spec" / "schemas" / "evidence.schema.json"
RECORD_SCHEMA = ROOT / "spec" / "schemas" / "result_record_v2.schema.json"
LEXICAL = ROOT / "spec" / "M2" / "lib" / "evidence_lexical.json"
ASSIGNMENT = ROOT / "gen" / "M2" / "sorts" / "assignment.json"
DIAGRAMS = ROOT / "gen" / "M2" / "diagram"
FIXTURES = ROOT / "tests_m2" / "fixtures" / "evidence"
EXPECTED = FIXTURES / "expected.json"
OVERRIDES = Path("config") / "evidence_overrides.json"
EVIDENCE_VERSION = "holon-evidence/0.1"
LEVELS = ("E1", "E2", "E3", "E4", "E5", "E6")
STRENGTH = {"E1": "strong", "E2": "strong", "E3": "strong", "E4": "strong", "E5": "medium", "E6": "weak"}
DOCS = {"morph_header": "facts/morph_header.json",
        "morph_rollup": "spec/M1/facts/morph_rollup.json",
        "morph_batchdata": "spec/M1/facts/morph_batchdata.json"}
HEADER, ROLLUP, BATCHDATA = "morph_header", "morph_rollup", "morph_batchdata"
ENDPOINT_KINDS = ("CODEC", "TRANS", "MIG", "CONS")
ID_RE = re.compile(r"^(?P<model>[A-Za-z0-9_]+):(?P<level>E[1-6]):(?P<p>[^:]+):(?P<q>[^:]+):(?P<h>[0-9a-f]{8})$")


class Run:
    """One `python -m holon evidence ... --out PATH` invocation and the file it wrote."""

    def __init__(self, args: list[str], cwd: Path = ROOT, out: Path | None = None):
        self.tmp = None
        if out is None:
            self.tmp = Path(tempfile.mkdtemp(prefix="holon-evidence-"))
            out = self.tmp / "evidence.json"
        self.out = Path(out)
        p = run_holon(["evidence", *args, "--out", str(self.out)], cwd=cwd)
        self.code = p.returncode
        self.log = f"exit {p.returncode}\n--- stdout\n{p.stdout[-3000:]}\n--- stderr\n{p.stderr[-3000:]}"
        self.text = self.out.read_text(encoding="utf-8") if self.out.exists() else None
        self.doc = json.loads(self.text) if self.text is not None else None

    def need(self) -> dict:
        if self.doc is None:
            raise AssertionError(f"holon evidence wrote no {self.out.name}\n{self.log}")
        return self.doc

    def cleanup(self) -> None:
        if self.tmp is not None:
            shutil.rmtree(self.tmp, ignore_errors=True)


# ------------------------------------------------------------------ document helpers
def canonical_sha256(obj) -> str:
    """sha256 of the canonical JSON text: sorted keys, separators (",", ":"), UTF-8, no ASCII escaping."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def without(doc: dict, *keys: str) -> dict:
    return {k: v for k, v in doc.items() if k not in keys}


def atoms(doc: dict, level: str | None = None, model: str | None = None) -> list[dict]:
    return [a for a in doc["atoms"] if (level is None or a["level"] == level) and (model is None or a["model"] == model)]


def find(doc: dict, level: str, p: str, q: str, model: str | None = None) -> list[dict]:
    return [a for a in atoms(doc, level, model) if a["p"] == p and a["q"] == q]


def touches(a: dict, edge: str) -> bool:
    return edge in (a["p"], a["q"])


def project(a: dict) -> tuple:
    """What a fixture expectation pins for one atom: model, level, endpoints, the whole via, src."""
    return (a["model"], a["level"], a["p"], a["q"], json.dumps(a["via"], sort_keys=True), a.get("src"))


def project_unresolved(u: dict) -> tuple:
    return (u["model"], u["p"], u["q"], u["carrier"], tuple(u["imprecise"]))


def diagram(model: str) -> dict:
    return load_json(DIAGRAMS / f"{model}.json")


def edges(model: str) -> dict[str, dict]:
    return {e["id"]: e for e in diagram(model)["edges"]}


def facts(model: str) -> dict:
    return load_json(ROOT / DOCS[model])


def action(model: str, name: str) -> dict:
    return next(a for a in facts(model)["actions"] if a["name"] == name)


def at_where(model: str, edge: str, where: str):
    """The facts expression an atom's via.where names: guards[i].require | guards[i].expr | effects.<f> | body."""
    f = facts(model)
    if edge.startswith("LOAD.obs."):
        assert where == "body", where
        return f["observers"][edge[len("LOAD.obs."):]]["body"]
    kind, name = edge.split(".", 1)
    owner = next(a for a in f["actions"] if a["name"] == name) if kind == "TRANS" else f["migrations"][name]
    m = re.fullmatch(r"guards\[(\d+)\]\.(require|expr)", where)
    if m:
        return owner["guards"][int(m.group(1))][m.group(2)]
    m = re.fullmatch(r"effects\.(.+)", where)
    if m:
        return owner["effects"][m.group(1)]
    raise AssertionError(f"unknown position {where!r}")


def subterms(e):
    """Every list node of a DSL expression (pre-order)."""
    if isinstance(e, list) and e:
        yield e
        kids = e[1:]
        if e[0] == "mk":
            kids = list(e[2].values())
        elif e[0] == "with":
            kids = [e[2], *e[3].values()]
        for k in kids:
            yield from subterms(k)


def has_node(e, op: str, left, right) -> bool:
    return any(n[0] == op and len(n) == 3 and n[1] == left and n[2] == right for n in subterms(e))


# ------------------------------------------------------------------ independent instruments
def tokens(text: str, lexical: dict) -> list[str]:
    """The documented E6 tokenizer of spec/M2/lib/evidence_lexical.json, re-implemented (before stopwords)."""
    out = []
    for ident in re.findall(lexical["tokenize"]["identifier"], text):
        for part in ident.split("_"):
            if not part:
                continue
            for t in re.split(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", part):
                t = t.lower()
                if len(t) >= lexical["tokenize"]["min_length"]:
                    out.append(t)
    return out


def edge_tokens(edge: dict, lexical: dict) -> set[str]:
    if edge["kind"] == "CODEC":
        names = [s["fn"] for s in edge.get("source", []) if "fn" in s]
    elif edge["kind"] == "TRANS":
        names = [edge["component"]]
    else:
        return set()
    stop = set(lexical["stopwords"])
    return {t for n in names for t in tokens(n, lexical) if t not in stop}


def versions(label) -> list[int]:
    if label is None:
        return []
    out = []
    for part in str(label).split(","):
        if ".." in part:
            lo, hi = part.split("..")
            out += list(range(int(lo), int(hi) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def recovered(facts_doc: dict, encoder: str, decoder: str, version: int) -> tuple[list[str], list[str]]:
    """Getter recovery (§10.2) recomputed from the frozen layout algebra holon.layout.layout (an M0 tool that
    predates I14): (recovered getters, active getters not recovered), each in getter order."""
    lay = holon_module("holon.layout").layout(facts_doc, encoder, version)
    when_ok = holon_module("holon.facts").when_ok
    rec, rest = [], []
    for g in facts_doc["functions"][decoder]["getters"]:
        if not when_ok(g.get("when"), version):
            continue
        ok = g["offset"] + g["width"] <= len(lay) and all(
            lay[g["offset"] + k] == ["field", g["name"], k] for k in range(g["width"]))
        (rec if ok else rest).append(g["name"])
    return rec, rest


def target_names() -> set[str]:
    """Every name the fact documents and their libraries give, derived (never hand-listed; audit F-M2-14): of the
    0.2 documents the actions, their inputs and lets, the state fields, the record types and their fields, the
    definitions, observers, migrations and params; of the 0.1 document the functions, the types and the Header
    fields; and every library builtin."""
    names: set[str] = set()
    for m in (ROLLUP, BATCHDATA):
        f = facts(m)
        names |= set(f.get("observers", {})) | set(f.get("defs", {})) | set(f.get("migrations", {}))
        names |= set(f.get("params", {}) if isinstance(f.get("params"), dict) else [])
        names |= {s[0] for s in f.get("state", [])}
        for t, ty in (f.get("types") or {}).items():
            names.add(t)
            for fld in (ty.get("fields", []) if isinstance(ty, dict) else []):
                names.add(fld[0] if isinstance(fld, list) else fld.get("name"))
        for a in f["actions"]:
            names.add(a["name"])
            names |= {x for x, *_ in a.get("inputs", [])}
            names |= {g["let"] for g in a.get("guards", []) if "let" in g}
    for lib in sorted((ROOT / "spec").glob("**/*.lib.json")):
        names |= set(load_json(lib).get("builtins", {}))
    h = facts(HEADER)
    names |= set(h["functions"]) | set(h.get("types", {})) | {fld["name"] for fld in h["types"]["Header"]["fields"]}
    return {n for n in names if isinstance(n, str) and n}


def morph_identifiers() -> set[str]:
    """Target names the generic evidence pass must not hold anywhere, docstrings included: the compound names of
    target_names() (5+ characters with an underscore or an uppercase letter after the first). A plain word such as
    `append`, or a capitalized one such as `Header` at the start of a sentence, is not compound (quoted, it is caught
    by quoted_target_names), and `version` is the facts-0.1 DSL's own record field (version_le, version_ge,
    version_in), which rule E1 and L4 read generically."""
    return {n for n in target_names() if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}


# generic words a generic pass may quote although some fact document also uses them as a name (record and IR keys)
GENERIC_WORDS = {"status", "value", "count", "next", "len", "append", "view", "off", "cap", "ctx", "proof"}


def quoted_target_names(contract: str) -> set[str]:
    """Target names (3+ characters) the generic pass must never hold as a string literal ("win", "lfi", "csr", ...;
    I13's rule for holon/sorts): target_names() minus the contract's own vocabulary (every identifier quoted in the
    contract docstring), the generic builtins of holon.diagram.access and GENERIC_WORDS."""
    allowed = set(re.findall(r'"([A-Za-z_][A-Za-z0-9_]*)"', contract)) | GENERIC_WORDS
    allowed |= set(getattr(holon_module("holon.diagram.access"), "GENERIC_ROLES", {}))
    return {n for n in target_names() if len(n) >= 3} - allowed


# ------------------------------------------------------------------ fixture
def fixture() -> dict:
    return load_json(EXPECTED)


def fixture_law(entry: dict) -> dict:
    """A fixture law with facts_sha256 filled from the fixture file (LF_uncovered keeps its planted mismatch)."""
    law = json.loads(json.dumps(entry["law"]))
    if law["law_id"] != "LF_uncovered":
        law["facts_sha256"] = hashlib.sha256((ROOT / law["facts"]).read_bytes()).hexdigest()
    return law


def fixture_doc() -> dict:
    """The evidence document of the two fixture fact documents: diagrams built by holon.diagram.build (I11),
    the planted assignment of expected.json, read through holon.diagram.evidence.build (the code under test)."""
    fx = fixture()
    build_diagram = holon_module("holon.diagram").build
    E = holon_module("holon.diagram.evidence")
    paths = [ROOT / rel for _, rel in sorted(fx["facts"].items())]
    diagrams = {p.stem: build_diagram(p, ROOT).to_json() for p in paths}
    return E.build(paths, ROOT, diagrams=diagrams, assignment=fx["assignment"])


def gevid(milestone: str, root: Path = ROOT) -> dict:
    return holon_module("holon.diagram.evidence").gevid(milestone, root)


def light_copy() -> Path:
    """A throwaway copy of what GEVID reads (fact documents, spec, laws, results, config, gen/M2), for in-process
    holon.diagram.evidence.gevid(milestone, copy) runs that must not touch the working tree."""
    dst = Path(tempfile.mkdtemp(prefix="holon-i14-")) / "repo"
    for rel in ("facts", "spec", "laws", "results", "config", "gen/M2"):
        src = ROOT / rel
        if src.exists():
            shutil.copytree(src, dst / rel, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return dst


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_gate(repo: Path, milestone: str, checks: str = "GEVID"):
    report = repo / f"gate_report_i14_{milestone}.json"
    p = run_holon(["gate", "--milestone", milestone, "--root", str(repo), "--report", str(report), "--checks", checks],
                  cwd=repo)
    return p, (load_json(report) if report.exists() else None)
