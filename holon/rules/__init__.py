"""The rules registry and `python -m holon derive` (BUILD_PLAN I15, §2.3; whitepaper §9.4: a statement is a function of
the diagram, the rule-catalog version and the generator version). The contract is the docstring of
tests_m2/test_sort_sites.py.

  python -m holon derive --milestone M [--root DIR] [--out DIR] [--obstructions PATH] [--facts PATH ...]
                         [--assignment PATH] [--against DIR --diff PATH]

CATALOG maps rule -> subform -> producer (a module with produce(ctx) -> [(law, DERIVATION entry)]). derive() runs
every producer over the milestone's fact documents (holon.diagram.fact_documents, or --facts) and the frozen sort
assignment, and writes, deterministically:

  <laws dir>/<law_id>.json   one holon-ir/0.3 law per basis element (a stale L*.json there is removed)
  <laws dir>/DERIVATION.json the provenance of every law (inputs, basis, hits, entry points, statement hash)
  <laws dir>/REGISTRY.json   statement hashes (holon.gen.refs.law_hash), facts hashes, sorts_sha256,
                             derivation_sha256 and, when <root>/gen/<M>/evidence.json exists, its evidence_sha256
  obstructions.json          the coherence obstructions (holon.sorts.check)
  the derive diff            with --against DIR --diff PATH: this derivation against DIR/DERIVATION.json

Exit 0 on success; 2 when the assignment is stale (its inputs do not list every fact document with its current
sha256, or its sites are not the sites the facts give: Thm 6.18's freezing condition), with nothing written; 3 when a
site cannot be derived or instrumented (named); 1 when an input is unreadable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from ..sorts import check as _check
from ..sorts import sites as _sites
from ..sorts import width as _width
from ..sorts.typed_sidecar import typed as _typed
from . import sort as _sort

ROOT = Path(__file__).resolve().parents[2]
RULE_CATALOG_VERSION = "holon-rules/1.0"
DERIVE_VERSION = "holon-derive/0.1"
IR_VERSION = "holon-ir/0.3"
# SORT-width (I20) derives nothing unless the milestone adopts extracted documents (holon.sorts.reextract), so the
# catalog entry leaves every earlier derivation byte-identical
CATALOG = {"SORT": {"site": _sites, "width": _width}}
# Catalog versions (I24, I30). holon-rules/1.0 is M2's catalog (and every test milestone's below T30). From I30 on, M3
# and later (and test milestones T<n> with n >= 30) take holon-rules/1.2: the rules of holon-rules/1.1, the M3 catalog
# before I30 (I24's PAR, when present), unchanged, plus SORT's typed subforms realize, as_member and reinterpret
# (holon.rules.sort; whitepaper §7.8). M2 keeps I15's SORT/site and I20's SORT/width.
CATALOGS = {RULE_CATALOG_VERSION: CATALOG}
TYPED_CATALOG_VERSION = "holon-rules/1.2"
CATALOGS[TYPED_CATALOG_VERSION] = {**{r: subs for r, subs in CATALOGS.get("holon-rules/1.1", {}).items()},
                                   "SORT": dict(_sort.PRODUCERS)}


def catalog_version(milestone: str) -> str:
    """The rule catalog version a milestone derives with (see CATALOGS)."""
    return TYPED_CATALOG_VERSION if _typed(milestone) else RULE_CATALOG_VERSION


class Refused(ValueError):
    """A stale assignment: exit 2, nothing written."""


class DeriveError(ValueError):
    """A site that cannot be derived or instrumented: exit 3."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class Inputs:
    """Every file derive reads: repo-relative under --root, "<outside>/<file name>" otherwise."""

    def __init__(self, root: Path):
        self.root = root
        self.files: dict[str, str] = {}

    def rel(self, p: Path) -> str:
        try:
            return Path(p).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return f"<outside>/{Path(p).name}"

    def read(self, p: Path) -> bytes:
        b = Path(p).read_bytes()
        self.files[self.rel(p)] = sha256_bytes(b)
        return b

    def json(self, p: Path):
        return json.loads(self.read(p).decode("utf-8"))

    def listing(self) -> list[dict]:
        return [{"path": k, "sha256": v} for k, v in sorted(self.files.items())]


class Document:
    """One fact document of the derivation."""

    def __init__(self, path: Path, inputs: Inputs, milestone: str, root: Path):
        from ..gen.oracles import Oracles
        from ..gen.targetlib import Library, lib_files
        self.path = path
        self.milestone = milestone
        self.rel = inputs.rel(path)
        data = inputs.read(path)
        self.sha256 = sha256_bytes(data)
        self.facts = json.loads(data.decode("utf-8"))
        self.model = path.stem
        self.params: list[tuple[str, str]] = []
        self.builtins: dict = {}
        self._machine = None
        self.orc = None
        self.lib = None
        if self.facts.get("facts_version") != "holon-facts/0.2":
            return
        libs = [inputs.json(p) for p in lib_files(path, root)]
        self.lib = Library(libs, self.facts.get("params", {}))
        self.builtins = self.lib.builtins
        self.orc = Oracles.for_milestone(milestone, path, root)
        if self.orc is not None and self.orc.path is not None:
            inputs.read(self.orc.path)
        m = self.machine()
        self.params = [(p, self.orc.param_type(p)) for p in m.threaded] if self.orc is not None else []

    def machine(self):
        """The document's machine as a run of the milestone builds it (holon.mpipeline.milestone_model: the
        milestone's oracle parameters and, after M1, permissions from the permission guards), over the target
        libraries read from --root."""
        if self._machine is None:
            from ..gen.machine import Machine
            from ..mpipeline import m2plus
            self._machine = Machine(self.facts, self.path, lib=self.lib, oracles=self.orc,
                                    m2plus=m2plus(self.milestone))
        return self._machine


class Context:
    def __init__(self, milestone: str, root: Path, documents: list[Document], assignment: dict, real: set):
        self.milestone, self.root, self.documents, self.assignment, self.real = milestone, root, documents, assignment, real
        self.rule_catalog_version = RULE_CATALOG_VERSION


def _documents(milestone: str, root: Path, facts: list[str] | None) -> list[Path]:
    if not facts:
        from ..diagram import fact_documents
        return fact_documents(milestone, root)
    out = []
    for f in facts:
        p = Path(f)
        p = (p if p.is_absolute() else Path.cwd() / p).resolve()
        try:
            p.relative_to(root)
        except ValueError:
            raise ValueError(f"--facts {f}: not inside the root {root} (inputs are read from --root only)") from None
        out.append(p)
    return out


def _stale(assignment: dict, docs: list[Document]) -> list[str]:
    listed = {i.get("path"): i.get("sha256") for i in assignment.get("inputs", []) if isinstance(i, dict)}
    bad = []
    for d in docs:
        if listed.get(d.rel) != d.sha256:
            bad.append(f"{d.rel} ({'not listed' if d.rel not in listed else 'listed with another sha256'})")
    return bad


class TypedDocument:
    """A transitions document of a typed milestone (I30): its relative path, sha256, the document and its basis."""

    def __init__(self, path: Path, inputs: Inputs, assignment: dict, seeds: dict):
        self.path = path
        self.rel = inputs.rel(path)
        data = inputs.read(path)
        self.sha256 = sha256_bytes(data)
        self.facts = json.loads(data.decode("utf-8"))
        self.model = path.stem
        self.assignment = assignment
        self.seeds = seeds
        self._basis = None

    @property
    def basis(self):
        if self._basis is None:
            self._basis = _sort.DocBasis(self.rel, self.facts, self.model, self.assignment, self.seeds)
        return self._basis


def compute_typed(milestone: str, root: Path, facts: list[str] | None = None, assignment: str | None = None,
                  sidecar: str | None = None) -> dict:
    """derive for a typed milestone (M3+, T30+; I30): the sidecar's transitions documents (or --facts), the frozen
    assignment gen/<M>/sorts/assignment.json (read, never written: Thm 6.18) and every producer of the milestone's
    catalog. No hand-written fact document, no I13 output and no target library is read (Q19)."""
    from ..gen import refs as R
    from ..sorts import extracted as X
    from ..sorts.typed_sidecar import SidecarError, load
    inputs = Inputs(root)
    try:
        sc = load(milestone, root, sidecar)
    except SidecarError as e:
        raise ValueError(str(e)) from e
    inputs.read(sc.path)
    seeds = inputs.json(sc.seeds)
    if facts:
        paths = []
        for f in facts:
            p = Path(f)
            p = (p if p.is_absolute() else (root / p if (root / p).exists() else Path.cwd() / p)).resolve()
            try:
                p.relative_to(root)
            except ValueError:
                raise ValueError(f"--facts {f}: not inside the root {root} (inputs are read from --root only)") from None
            paths.append(p)
    else:
        paths = sc.documents
    stems = [p.stem for p in paths]
    if len(set(stems)) != len(stems):
        raise ValueError(f"two documents name the same model: {sorted(stems)}")
    ap = Path(assignment) if assignment else root / "gen" / milestone / "sorts" / "assignment.json"
    if not ap.is_absolute():
        ap = Path.cwd() / ap
    A = inputs.json(ap)
    docs = [TypedDocument(p, inputs, A, seeds) for p in sorted(paths, key=lambda p: p.stem)]
    bad = _stale(A, docs)
    if bad:
        raise Refused(f"the assignment {inputs.rel(ap)} is stale: it does not list " + "; ".join(bad))
    for d in docs:
        if d.facts.get("facts_version") != "holon-facts/0.3" or (d.facts.get("extraction") or {}).get("kind") != \
                "transitions":
            raise ValueError(f"{d.rel}: a typed milestone derives over holon-facts/0.3 transitions documents")
        if d.model not in (A.get("models") or {}):
            raise Refused(f"the assignment {inputs.rel(ap)} has no model {d.model}")
    cv = catalog_version(milestone)
    catalog = CATALOGS[cv]
    ctx = Context(milestone, root, [], A, set())
    ctx.rule_catalog_version = cv
    ctx.typed_documents = docs
    ctx.sidecar = sc
    pairs = []
    try:
        for rule in sorted(catalog):
            for sub in sorted(catalog[rule]):
                pairs += catalog[rule][sub].produce(ctx)
    except _sort.SortRuleError as e:
        raise DeriveError(str(e)) from e
    ids = [law["law_id"] for law, _ in pairs]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise DeriveError(f"two basis elements map to one law id: {dup}")
    by_rel = {d.rel: d for d in docs}
    laws, entries = {}, []
    for law, entry in sorted(pairs, key=lambda p: p[0]["law_id"]):
        d = by_rel[law["facts"]]
        entry = dict(entry, statement_hash=R.law_hash(law, d.facts, root=root))
        laws[law["law_id"]] = law
        entries.append(entry)
    obstructions = []
    for d in docs:
        obstructions += X.obstructions(d.model, d.facts, A)
    listing = inputs.listing()
    derivation = {"document": "derivation", "derive_version": DERIVE_VERSION, "milestone": milestone,
                  "rule_catalog_version": cv, "sorts_sha256": A.get("sorts_sha256"),
                  "inputs": listing, "laws": entries, "links": []}
    dtext = dumps(derivation)
    named = sorted({law["facts"] for law in laws.values()})
    registry = {"milestone": milestone, "ir_version": IR_VERSION, "rule_catalog_version": cv,
                "facts": named[0] if named else None,
                "facts_sha256": by_rel[named[0]].sha256 if named else None,
                "facts_files": {r: by_rel[r].sha256 for r in named},
                "statements": {e["law_id"]: e["statement_hash"] for e in entries},
                "sorts_sha256": A.get("sorts_sha256"), "derivation_sha256": sha256_bytes(dtext.encode("utf-8"))}
    ev = root / "gen" / milestone / "evidence.json"
    if ev.exists():   # the milestone's evidence set: its identity is copied, never recomputed here
        registry["evidence_sha256"] = json.loads(ev.read_text(encoding="utf-8")).get("evidence_sha256")
    obs = {"document": "obstructions", "derive_version": DERIVE_VERSION, "milestone": milestone, "inputs": listing,
           "sorts_sha256": A.get("sorts_sha256"), "obstructions": sorted(obstructions, key=lambda o: o["id"])}
    return {"laws": laws, "derivation": derivation, "derivation_text": dtext, "registry": registry, "obstructions": obs}


def compute(milestone: str, root: Path, facts: list[str] | None = None, assignment: str | None = None,
            sidecar: str | None = None) -> dict:
    """Everything derive writes, as documents (nothing is written here)."""
    if _typed(milestone):
        return compute_typed(milestone, root, facts, assignment, sidecar)
    from ..gen import refs as R
    inputs = Inputs(root)
    paths = _documents(milestone, root, facts)
    stems = [p.stem for p in paths]
    if len(set(stems)) != len(stems):
        raise ValueError(f"two fact documents name the same model: {sorted(stems)}")
    docs = [Document(p, inputs, milestone, root) for p in sorted(paths, key=lambda p: p.stem)]
    ap = Path(assignment) if assignment else root / "gen" / milestone / "sorts" / "assignment.json"
    if not ap.is_absolute():
        ap = Path.cwd() / ap
    A = inputs.json(ap)
    bad = _stale(A, docs)
    if bad:
        raise Refused(f"the assignment {inputs.rel(ap)} is stale: it does not list " + "; ".join(bad))
    sp, _, real = _sites.load_sidecar(milestone, root)
    inputs.read(sp)
    ctx = Context(milestone, root, docs, A, real)
    pairs = []
    try:
        for rule in sorted(CATALOG):
            for sub in sorted(CATALOG[rule]):
                pairs += CATALOG[rule][sub].produce(ctx)
    except _sites.StaleSites as e:
        raise Refused(str(e)) from e
    except _sites.SiteError as e:
        raise DeriveError(str(e)) from e
    ids = [law["law_id"] for law, _ in pairs]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise DeriveError(f"two basis elements map to one law id: {dup}")
    by_rel = {d.rel: d for d in docs}
    for law, _ in pairs:   # a law over a document outside the milestone's fact documents (an adopted extraction, I20)
        if law["facts"] not in by_rel:
            by_rel[law["facts"]] = Document(root / law["facts"], inputs, milestone, root)
    from ..sorts import reextract
    sc = reextract.sidecar_path(milestone, root)
    if sc.is_file():   # an adoption of extracted documents (I20): the sidecar, its documents and the window views
        inputs.read(sc)
        for rel in (reextract.sidecar(milestone, root) or {}).get("documents") or []:
            inputs.read(root / rel)
        for p in sorted(root.glob("spec/*/lib/window_*.json")):
            inputs.read(p)
    laws, entries = {}, []
    for law, entry in sorted(pairs, key=lambda p: p[0]["law_id"]):
        d = by_rel[law["facts"]]
        entry = dict(entry, statement_hash=R.law_hash(law, d.facts, oracles=d.orc, root=root))
        laws[law["law_id"]] = law
        entries.append(entry)
    obstructions = []
    for d in docs:
        if d.facts.get("facts_version") == "holon-facts/0.2" and d.model in A.get("models", {}):
            obstructions += _check.obstructions(d.facts, A, d.model)
    listing = inputs.listing()
    # back-test links (audit F-M2-08, F-M2-23; gate G2 holon.statement_diff.check_cross_milestone): a rule that
    # re-derives an earlier milestone's law names the pair here; SORT-site laws come from sites, so there are none
    derivation = {"document": "derivation", "derive_version": DERIVE_VERSION, "milestone": milestone,
                  "rule_catalog_version": RULE_CATALOG_VERSION, "sorts_sha256": A.get("sorts_sha256"),
                  "inputs": listing, "laws": entries, "links": []}
    dtext = dumps(derivation)
    named = sorted({law["facts"] for law in laws.values()})
    registry = {"milestone": milestone, "ir_version": IR_VERSION, "rule_catalog_version": RULE_CATALOG_VERSION,
                "facts": named[0] if named else None,
                "facts_sha256": by_rel[named[0]].sha256 if named else None,
                "facts_files": {r: by_rel[r].sha256 for r in named},
                "statements": {e["law_id"]: e["statement_hash"] for e in entries},
                "sorts_sha256": A.get("sorts_sha256"), "derivation_sha256": sha256_bytes(dtext.encode("utf-8"))}
    ev = root / "gen" / milestone / "evidence.json"
    if ev.exists():   # I14's frozen evidence set: its identity is copied, never recomputed here
        registry["evidence_sha256"] = json.loads(ev.read_text(encoding="utf-8")).get("evidence_sha256")
    obs = {"document": "obstructions", "derive_version": DERIVE_VERSION, "milestone": milestone, "inputs": listing,
           "sorts_sha256": A.get("sorts_sha256"), "obstructions": sorted(obstructions, key=lambda o: o["id"])}
    return {"laws": laws, "derivation": derivation, "derivation_text": dtext, "registry": registry, "obstructions": obs}


def diff(base: dict, new: dict) -> dict:
    """The derive diff of `new` against `base` (two DERIVATION documents)."""
    b = {e["law_id"]: e for e in base.get("laws", [])}
    n = {e["law_id"]: e for e in new.get("laws", [])}
    out = []
    for lid in sorted(set(b) | set(n)):
        x, y = b.get(lid), n.get(lid)
        eb = set(x["entry_points"]) if x else set()
        en = set(y["entry_points"]) if y else set()
        if x is None:
            change = "added"
        elif y is None:
            change = "removed"
        else:
            change = "unchanged" if x.get("statement_hash") == y.get("statement_hash") else "statement"
        out.append({"law_id": lid, "change": change, "entry_points": {"lost": sorted(eb - en), "gained": sorted(en - eb)},
                    "statement_hash": {"base": x.get("statement_hash") if x else None,
                                       "new": y.get("statement_hash") if y else None}})
    return {"document": "derive_diff", "derive_version": DERIVE_VERSION, "laws": out}


def derive(milestone: str, root: str | None = None, out: str | None = None, obstructions: str | None = None,
           facts: list[str] | None = None, assignment: str | None = None, against: str | None = None,
           diff_path: str | None = None, log=print, sidecar: str | None = None) -> int:
    root_p = Path(root).resolve() if root else ROOT
    try:
        res = compute(milestone, root_p, facts, assignment, sidecar)
        base = None
        if against:
            ap = Path(against)
            base = json.loads((ap if ap.is_absolute() else Path.cwd() / ap).joinpath("DERIVATION.json").read_text(encoding="utf-8"))
    except Refused as e:
        print(f"holon derive: refused: {e}", file=sys.stderr)
        return 2
    except DeriveError as e:
        print(f"holon derive: cannot instrument: {e}", file=sys.stderr)
        return 3
    except (ValueError, KeyError, OSError) as e:
        print(f"holon derive: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    laws_dir = Path(out) if out else root_p / "laws" / milestone
    obs_p = Path(obstructions) if obstructions else (laws_dir / "obstructions.json" if out
                                                      else root_p / "gen" / milestone / "sorts" / "obstructions.json")
    laws_dir.mkdir(parents=True, exist_ok=True)
    from ..ir import LAW_GLOB
    for p in sorted(laws_dir.glob(LAW_GLOB)):
        if p.stem not in res["laws"]:
            p.unlink()
    for lid, law in sorted(res["laws"].items()):
        (laws_dir / f"{lid}.json").write_text(dumps(law), encoding="utf-8")
    (laws_dir / "DERIVATION.json").write_text(res["derivation_text"], encoding="utf-8")
    (laws_dir / "REGISTRY.json").write_text(dumps(res["registry"]), encoding="utf-8")
    obs_p.parent.mkdir(parents=True, exist_ok=True)
    obs_p.write_text(dumps(res["obstructions"]), encoding="utf-8")
    if against and diff_path:
        d = diff(base, res["derivation"])
        Path(diff_path).parent.mkdir(parents=True, exist_ok=True)
        Path(diff_path).write_text(dumps(d), encoding="utf-8")
    n_obs = len(res["obstructions"]["obstructions"])
    log(f"holon derive: {len(res['laws'])} laws, {n_obs} obstructions -> {laws_dir}")
    for e in res["derivation"]["laws"]:
        log(f"  {e['law_id']:58s} {', '.join(e['entry_points'])}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon derive")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--out", help="laws directory to write (default: <root>/laws/<milestone>)")
    ap.add_argument("--obstructions", help="obstructions file (default: <out>/obstructions.json with --out, else "
                                           "<root>/gen/<milestone>/sorts/obstructions.json)")
    ap.add_argument("--facts", action="append", help="a fact document to derive from instead of the milestone's")
    ap.add_argument("--assignment", help="the frozen sort assignment (default <root>/gen/<milestone>/sorts/assignment.json)")
    ap.add_argument("--against", help="a laws directory holding a DERIVATION.json to diff against")
    ap.add_argument("--diff", help="where to write the derive diff (with --against)")
    ap.add_argument("--sidecar", help="the typed-sorts sidecar of an M3+ or T30+ milestone (default "
                                      "spec/<M>/lib/sort_types.json)")
    a = ap.parse_args(argv)
    if bool(a.against) != bool(a.diff):
        ap.error("--against and --diff go together")
    return derive(a.milestone, a.root, a.out, a.obstructions, a.facts, a.assignment, a.against, a.diff,
                  sidecar=a.sidecar)
