"""The rules registry and `python -m holon derive` (BUILD_PLAN I15, §2.3; whitepaper §9.4: a statement is a function of
the diagram, the rule-catalog version and the generator version). The contract is the docstring of
tests_m2/test_sort_sites.py.

  python -m holon derive --milestone M [--root DIR] [--out DIR] [--obstructions PATH] [--facts PATH ...]
                         [--assignment PATH] [--against DIR --diff PATH]
                         [--catalog VERSION] [--codec PATH ...]   (I24: rule PAR; tests_m3/test_derive_par.py)
                         [--sidecar PATH]                         (I30: typed SORT; tests_m3/test_sort_types.py)

CATALOG maps rule -> subform -> producer (a module with produce(ctx) -> [(law, DERIVATION entry)]). derive() runs
every producer over the milestone's fact documents (holon.diagram.fact_documents, or --facts) and the frozen sort
assignment, and writes, deterministically (CATALOGS holds the later catalog versions; compute_catalog derives with
them):

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
# Catalog versions (I24, I30):
#   holon-rules/1.0  M2's catalog (I15's SORT/site, I20's SORT/width), and every test milestone's below T30.
#   holon-rules/1.1  I24's: rule PAR, one producer per sub-form (holon.rules.par), run in par.SUBFORMS order; M3's
#                    catalog before I30, and a test milestone's through derive's --catalog.
#   holon-rules/1.2  I30's: the rules of holon-rules/1.1 unchanged (the same producer objects), plus SORT's typed
#                    subforms realize, as_member and reinterpret (holon.rules.sort; whitepaper §7.8); M3 and later, and
#                    test milestones T<n> with n >= 30. M2 keeps I15's SORT/site and I20's SORT/width.
from . import par as _par  # noqa: E402
PAR_CATALOG_VERSION = "holon-rules/1.1"
TYPED_CATALOG_VERSION = "holon-rules/1.2"
CATALOGS = {RULE_CATALOG_VERSION: CATALOG, PAR_CATALOG_VERSION: {"PAR": dict(_par.PRODUCERS)}}
CATALOGS[TYPED_CATALOG_VERSION] = {**{r: subs for r, subs in CATALOGS[PAR_CATALOG_VERSION].items()},
                                   "SORT": dict(_sort.PRODUCERS)}
#   holon-rules/1.3  I27's: the rules of holon-rules/1.2 unchanged (the same producer objects: I24's PAR, I30's SORT),
#                    plus rule UNDO's subforms pair and residue (holon.rules.undo; whitepaper §5.2); M3 and later. A
#                    test milestone keeps its catalog and takes this one through derive's --catalog.
from . import undo as _undo  # noqa: E402
UNDO_CATALOG_VERSION = "holon-rules/1.3"
CATALOGS[UNDO_CATALOG_VERSION] = {**{r: dict(subs) for r, subs in CATALOGS[TYPED_CATALOG_VERSION].items()},
                                  "UNDO": dict(_undo.PRODUCERS)}


def catalog_version(milestone: str) -> str:
    """The rule-catalog version a milestone derives with: holon-rules/1.3 for M3 and later (I27); holon-rules/1.2 for
    the typed test milestones (T<n> with n >= 30; holon.sorts.typed_sidecar.typed); holon-rules/1.0 for M0-M2 and every
    other test milestone. A test milestone's catalog may be replaced with `--catalog`."""
    if not _typed(milestone):
        return RULE_CATALOG_VERSION
    return UNDO_CATALOG_VERSION if target_milestone(milestone) else TYPED_CATALOG_VERSION


def target_milestone(milestone: str) -> bool:
    import re
    return re.fullmatch(r"M\d+", milestone or "") is not None


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


def _typed_part(milestone: str, root: Path, cv: str, facts: list[str] | None = None, assignment: str | None = None,
                sidecar: str | None = None, undo_sidecar: str | None = None) -> dict:
    """derive's typed part (I30), for a typed milestone (M3+, T30+): the sidecar's transitions documents (or --facts),
    the frozen assignment gen/<M>/sorts/assignment.json (read, never written: Thm 6.18) and every producer of catalog
    `cv` that takes the typed context (every rule but PAR, whose engine is _par_part). No hand-written fact document, no
    I13 output and no target library is read (Q19). Returns the laws, their DERIVATION entries, the inputs read, the
    assignment, the documents' sha256 and the obstructions document."""
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
        paths = [_typed_fact_path(f, root) for f in facts]
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
        if not _transitions(d.facts):
            raise ValueError(f"{d.rel}: a typed milestone derives over holon-facts/0.3 transitions documents")
        if d.model not in (A.get("models") or {}):
            raise Refused(f"the assignment {inputs.rel(ap)} has no model {d.model}")
    catalog = CATALOGS[cv]
    ctx = Context(milestone, root, [], A, set())
    ctx.rule_catalog_version = cv
    ctx.typed_documents = docs
    ctx.sidecar = sc
    ctx.undo_sidecar = undo_sidecar     # I27: rule UNDO's sidecar (default spec/<M>/lib/undo.json)
    ctx.inputs = inputs
    pairs = []
    try:
        for rule in _typed_rules(catalog):
            for sub in sorted(catalog[rule]):
                pairs += catalog[rule][sub].produce(ctx)
    except (_sort.SortRuleError, _undo.UndoError) as e:
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
    # the obstructions document lists what the typed part read (the sidecar, its seeds, the assignment, the documents)
    obs = {"document": "obstructions", "derive_version": DERIVE_VERSION, "milestone": milestone,
           "inputs": inputs.listing(), "sorts_sha256": A.get("sorts_sha256"),
           "obstructions": sorted(obstructions, key=lambda o: o["id"])}
    return {"laws": laws, "entries": entries, "inputs": inputs, "assignment": A,
            "shas": {d.rel: d.sha256 for d in docs}, "obstructions": obs}


def _typed_rules(catalog: dict) -> list[str]:
    """The rules of a catalog after holon-rules/1.0 whose producers take the typed context (produce(ctx), I30): every
    rule but PAR, whose sub-forms run per document in rule P11's order (holon.rules.par.derive_document)."""
    return sorted(r for r in catalog if r != "PAR")


def _transitions(doc) -> bool:
    return isinstance(doc, dict) and doc.get("facts_version") == "holon-facts/0.3" and \
        (doc.get("extraction") or {}).get("kind") == "transitions"


def _typed_fact_path(f: str, root: Path) -> Path:
    """A --facts document of the typed part: relative to --root when it exists there, else to the working directory;
    inside --root."""
    p = Path(f)
    p = (p if p.is_absolute() else (root / p if (root / p).exists() else Path.cwd() / p)).resolve()
    try:
        p.relative_to(root)
    except ValueError:
        raise ValueError(f"--facts {f}: not inside the root {root} (inputs are read from --root only)") from None
    return p


def _is_transitions_file(f: str, root: Path) -> bool:
    try:
        return _transitions(json.loads(_typed_fact_path(f, root).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return False


def compute(milestone: str, root: Path, facts: list[str] | None = None, assignment: str | None = None,
            sidecar: str | None = None, catalog: str | None = None, codecs: list[str] | None = None,
            undo_sidecar: str | None = None) -> dict:
    """Everything derive writes, as documents (nothing is written here), with the milestone's catalog or `catalog`:
    holon-rules/1.0 here (I15's SORT/site, I20's SORT/width); a later catalog in compute_catalog (I24's PAR, I30's
    typed SORT, or both)."""
    cv = catalog or catalog_version(milestone)
    if cv not in CATALOGS:
        raise ValueError(f"unknown catalog {cv!r} (known: {sorted(CATALOGS)})")
    if CATALOGS[cv] is not CATALOG:
        return compute_catalog(milestone, root, cv, facts, codecs, assignment, sidecar, undo_sidecar)
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


# ====================================================================== rule PAR (I24)
def _json_text(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8")
    except OSError:
        return None


def _committed_par_inputs(milestone: str, root: Path, inputs: Inputs):
    """M3 on: the linked codec documents, their diagrams and the evidence set, each byte for byte what holon codecs,
    diagram and evidence write now (else Refused: a stale input). Returns ([(path, diagram)], evidence, uncovered)."""
    from ..diagram import DiagramError, linked_diagrams
    from ..diagram import evidence as EV
    from ..diagram import linked as L
    ad_rel, link_rel = L.default_sidecars(milestone)
    try:
        fresh = L.render_all(root, milestone, ad_rel, link_rel)
    except L.SidecarError as e:
        raise Refused(f"the linked codec layer cannot be rebuilt: {e}") from e
    except L.LinkedError as e:
        raise DeriveError(str(e)) from e
    have = {p.name: p.read_text(encoding="utf-8") for p in L.committed_codecs(milestone, root)}
    if have != fresh:
        raise Refused(f"gen/{milestone}/codec is stale: it is not what `holon codecs --milestone {milestone}` writes now")
    try:
        dtexts = linked_diagrams(milestone, root)
    except DiagramError as e:
        raise Refused(f"the component diagrams cannot be rebuilt: {e}") from e
    for model, text in dtexts.items():
        if _json_text(root / "gen" / milestone / "diagram" / f"{model}.json") != text:
            raise Refused(f"gen/{milestone}/diagram/{model}.json is stale: it is not what `holon diagram --milestone "
                          f"{milestone}` writes now")
    ev_p = root / "gen" / milestone / "evidence.json"
    try:
        etext = EV.render(EV.build_milestone(milestone, root))
    except (EV.EvidenceError, DiagramError) as e:
        raise Refused(f"the evidence set cannot be rebuilt: {e}") from e
    if _json_text(ev_p) != etext:
        raise Refused(f"gen/{milestone}/evidence.json is stale: it is not what `holon evidence --milestone "
                      f"{milestone}` writes now")
    ev = inputs.json(ev_p)
    inputs.read(root / ad_rel)
    inputs.read(root / link_rel)
    inputs.read(root / "spec" / "M2" / "lib" / "evidence_lexical.json")
    for rel in json.loads((root / ad_rel).read_text(encoding="utf-8")).get("documents") or []:
        inputs.read(root / rel)
    comps = []
    for p in L.committed_codecs(milestone, root):
        dg = inputs.json(root / "gen" / milestone / "diagram" / p.name)
        comps.append((p, dg))
    try:
        unc = L.uncovered(root, ad_rel, link_rel)
    except L.SidecarError as e:
        raise Refused(str(e)) from e
    return comps, ev, unc


def _sidecars_of(doc: dict, root: Path) -> tuple[str | None, str | None]:
    """The adoption and link sidecars a linked codec document lists among its inputs."""
    ad = ln = None
    for i in doc.get("inputs") or []:
        try:
            d = json.loads((root / i["path"]).read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if isinstance(d, dict) and "derive_extracted_version" in d:
            ad = i["path"]
        elif isinstance(d, dict) and isinstance(d.get("roles"), dict):
            ln = i["path"]
    return ad, ln


def _given_par_inputs(milestone: str, root: Path, inputs: Inputs, paths: list[Path], codecs: list[Path],
                      assignment: dict | None):
    """A test milestone's --facts and --codec documents: their diagrams and the evidence set built in memory. Returns
    ([(path, diagram)] of the fact documents, [(path, diagram)] of the codec documents, evidence, uncovered)."""
    from ..diagram import DiagramError
    from ..diagram import evidence as EV
    from ..diagram import linked as L
    from ..diagram.build import build as build_diagram
    fdocs, cdocs = [], []
    for p in paths:
        inputs.read(p)
        try:
            fdocs.append((p, build_diagram(p, root).to_json()))
        except DiagramError as e:
            raise DeriveError(f"{inputs.rel(p)}: no diagram: {e}") from e
    unc_src = set()
    for p in codecs:
        raw = inputs.read(p)
        doc = json.loads(raw.decode("utf-8"))
        if not L.is_linked(doc):
            raise ValueError(f"--codec {inputs.rel(p)}: not a linked codec document ({L.LINKED_VERSION})")
        try:
            dg = L.diagram(doc, inputs.rel(p), sha256_bytes(raw))
        except L.LinkedError as e:
            raise DeriveError(str(e)) from e
        cdocs.append((p, dg))
        ad, ln = _sidecars_of(doc, root)
        if ad and ln:
            unc_src.add((ad, ln))
    if assignment is None:
        assignment = {"models": {}, "sites": [], "sorts_sha256": None}
    try:
        ev = EV.build(paths, root, diagrams={d["model"]: d for _, d in fdocs}, assignment=assignment,
                      milestone=milestone, components=cdocs, adopted=False)
    except EV.EvidenceError as e:
        raise Refused(f"the evidence set cannot be built: {e}") from e
    unc = []
    for ad, ln in sorted(unc_src):
        inputs.read(root / ad)
        inputs.read(root / ln)
        unc += L.uncovered(root, ad, ln)
    return fdocs, cdocs, ev, sorted({json.dumps(u, sort_keys=True): u for u in unc}.values(),
                                    key=lambda u: (u["document"], u["function"] or ""))


def _earlier_laws(milestone: str, root: Path, inputs: Inputs) -> list[tuple[str, dict]]:
    """P11: the laws a derivation is linked against: laws/M<j> for j < k (a test milestone: every laws/M<j>)."""
    import re
    m = re.fullmatch(r"M(\d+)", milestone)
    out = []
    for d in sorted((root / "laws").glob("M*")):
        mm = re.fullmatch(r"M(\d+)", d.name)
        if not mm or not d.is_dir() or (m and int(mm.group(1)) >= int(m.group(1))):
            continue
        for p in sorted(d.glob("L*.json")):
            out.append((d.name, inputs.json(p)))
    return out


def _par_part(milestone: str, root: Path, cv: str, inputs: Inputs, facts: list[str] | None = None,
              codecs: list[str] | None = None, assignment: str | None = None) -> dict:
    """derive's PAR part (I24: rules P0-P12, X8) over the --facts and --codec documents, or, with neither, a target
    milestone's committed linked codec layer. Returns the laws, their DERIVATION entries, the PAR keys of DERIVATION
    (links, evidence_sha256, cycle_rank, par_basis, uncovered), the --facts assignment and the documents' sha256."""
    from ..gen import refs as R
    cat = CATALOGS[cv]
    given = bool(facts) or bool(codecs)
    A = None
    if given:
        paths = _documents(milestone, root, facts) if facts else []
        cpaths = _documents(milestone, root, codecs) if codecs else []
        if paths:
            if not assignment:
                raise ValueError("--facts documents need --assignment (their sorts: evidence level E5)")
            ap = Path(assignment)
            A = inputs.json(ap if ap.is_absolute() else Path.cwd() / ap)
            docs_ = [Document(p, inputs, milestone, root) for p in paths]
            bad = _stale(A, docs_)
            if bad:
                raise Refused(f"the assignment is stale: it does not list " + "; ".join(bad))
        fdocs, cdocs, ev, unc = _given_par_inputs(milestone, root, inputs, paths, cpaths, A)
        comps = cdocs
    else:
        if not target_milestone(milestone):
            raise ValueError(f"{milestone}: a test milestone derives PAR from --facts and --codec documents")
        comps, ev, unc = _committed_par_inputs(milestone, root, inputs)
        fdocs = []
    documents = []
    for p, dg in fdocs + comps:
        d = Document(p, inputs, milestone, root)
        documents.append((d, dg))
    models = [dg["model"] for _, dg in documents]
    if len(set(models)) != len(models):
        raise ValueError(f"two documents give one model: {sorted(models)}")
    laws, entries, basis, cycle_rank = {}, [], [], {}
    for d, dg in sorted(documents, key=lambda x: x[1]["model"]):
        pd = _par.ParDoc(rel=d.rel, facts=d.facts, diagram=dg,
                         atoms=[a for a in ev["atoms"] if a["model"] == dg["model"]],
                         oracle_binders=list(d.params), lib_builtins=dict(d.builtins))
        try:
            acc = _par.derive_document(pd, cat["PAR"])
        except _par.ParError as e:
            raise DeriveError(f"{d.rel}: {e}") from e
        for lid, x in acc.laws.items():
            if lid in laws:
                raise DeriveError(f"two basis elements map to one law id: {lid}")
            law = {"ir_version": IR_VERSION, "law_id": lid, "milestone": milestone, "rule": "PAR",
                   "subform": x["subform"], "rule_catalog_version": cv, "facts": d.rel, "facts_sha256": d.sha256,
                   "notes": x["notes"], "statement": x["statement"]}
            laws[lid] = law
            entries.append({"law_id": lid, "rule": "PAR", "subform": x["subform"], "facts": d.rel,
                            "basis": x["basis"], "entry_points": x["entry_points"],
                            "statement_hash": R.law_hash(law, d.facts, oracles=d.orc, root=root)})
        basis += acc.basis
        cycle_rank[dg["model"]] = {k: acc.cycle[k] for k in ("E", "V", "kappa", "rank", "tree", "non_tree")}
    links = []
    canon_new = {lid: _par.canonical_json(_par.canonical(law)) for lid, law in laws.items()}
    for om, old in _earlier_laws(milestone, root, inputs):
        co = _par.canonical_json(_par.canonical(old))
        for lid, cn in canon_new.items():
            if cn == co:
                nb = [b["name"] for b in laws[lid]["statement"].get("binders", [])]
                ob = [b["name"] for b in (old["statement"].get("binders") or old["statement"].get("forall") or [])]
                links.append({"old": old["law_id"], "old_milestone": om, "new": lid, "new_milestone": milestone,
                              "basis": "alpha-equivalent", "binder_map": dict(zip(nb, ob))})
    links.sort(key=lambda x: (x["old_milestone"], x["old"], x["new"]))
    entries.sort(key=lambda e: e["law_id"])
    basis.sort(key=_par.basis_sort_key)
    return {"laws": laws, "entries": entries, "links": links, "assignment": A,
            "shas": {d.rel: d.sha256 for d, _ in documents},
            "keys": {"evidence_sha256": ev["evidence_sha256"], "cycle_rank": dict(sorted(cycle_rank.items())),
                     "par_basis": basis, "uncovered": unc}}


def compute_catalog(milestone: str, root: Path, cv: str, facts: list[str] | None = None,
                    codecs: list[str] | None = None, assignment: str | None = None, sidecar: str | None = None,
                    undo_sidecar: str | None = None) -> dict:
    """Everything derive writes for a catalog after holon-rules/1.0, as documents (nothing is written): rule PAR (I24)
    and the rules that take the typed context (I30's SORT realize, as_member and reinterpret), each over its own
    documents, in one DERIVATION and one REGISTRY.

    Documents. With neither --facts nor --codec, PAR takes a target milestone's committed linked codec layer (a test
    milestone's PAR needs given documents, so with typed rules beside it PAR derives nothing there, and alone it is
    refused) and the typed rules take the typed sidecar's transitions documents. Otherwise each takes only the given
    documents that are its own: PAR the --codec documents and the --facts documents that are not holon-facts/0.3
    transitions documents; the typed rules the --facts transitions documents. A catalog without PAR gives every --facts
    document to its typed rules, one without typed rules every --facts document to PAR.

    DERIVATION: the I15 keys over both parts ("inputs" every file either part read, "laws" every entry sorted by law_id,
    "sorts_sha256" the typed part's assignment, else the PAR --facts assignment's, else null, "links" rule P11's),
    plus PAR's "evidence_sha256", "cycle_rank", "par_basis" and "uncovered" when PAR derived. REGISTRY as I15's, with
    "evidence_sha256" the evidence set PAR built (without PAR: gen/<M>/evidence.json's when it exists). The obstructions
    document is the typed part's (none without it: a catalog without SORT writes no obstructions file)."""
    cat = CATALOGS[cv]
    has_par, typed_rules = "PAR" in cat, _typed_rules(cat)
    given = bool(facts) or bool(codecs)
    pfacts, tfacts = [], []
    for f in facts or []:
        if typed_rules and (not has_par or _is_transitions_file(f, root)):
            tfacts.append(f)
        else:
            pfacts.append(f)
    inputs = Inputs(root)
    par = typed = None
    if has_par and (pfacts or codecs or (not given and (target_milestone(milestone) or not typed_rules))):
        par = _par_part(milestone, root, cv, inputs, pfacts, codecs, assignment)
    if typed_rules and (tfacts or not given):
        typed = _typed_part(milestone, root, cv, tfacts, assignment, sidecar, undo_sidecar)
        inputs.files.update(typed["inputs"].files)
    laws, entries, shas = {}, [], {}
    for part in (par, typed):
        if part is None:
            continue
        for lid, law in part["laws"].items():
            if lid in laws:
                raise DeriveError(f"two basis elements map to one law id: {lid}")
            laws[lid] = law
        entries += part["entries"]
        shas.update(part["shas"])
    entries.sort(key=lambda e: e["law_id"])
    if typed is not None:
        sorts_sha = typed["assignment"].get("sorts_sha256")
    elif par is not None and par["assignment"] is not None:
        sorts_sha = par["assignment"].get("sorts_sha256")
    else:
        sorts_sha = None
    # links (rule P11, F-M2-23): PAR's; the typed rules derive from coercion sites, so they give none
    derivation = {"document": "derivation", "derive_version": DERIVE_VERSION, "milestone": milestone,
                  "rule_catalog_version": cv, "sorts_sha256": sorts_sha, "inputs": inputs.listing(), "laws": entries,
                  "links": par["links"] if par is not None else []}
    if par is not None:
        derivation.update(par["keys"])
    dtext = dumps(derivation)
    named = sorted({law["facts"] for law in laws.values()})
    registry = {"milestone": milestone, "ir_version": IR_VERSION, "rule_catalog_version": cv,
                "facts": named[0] if named else None, "facts_sha256": shas[named[0]] if named else None,
                "facts_files": {r: shas[r] for r in named},
                "statements": {e["law_id"]: e["statement_hash"] for e in entries},
                "sorts_sha256": sorts_sha, "derivation_sha256": sha256_bytes(dtext.encode("utf-8"))}
    if par is not None:
        registry["evidence_sha256"] = par["keys"]["evidence_sha256"]
    else:
        ev = root / "gen" / milestone / "evidence.json"
        if ev.exists():   # the milestone's evidence set: its identity is copied, never recomputed here
            registry["evidence_sha256"] = json.loads(ev.read_text(encoding="utf-8")).get("evidence_sha256")
    return {"laws": laws, "derivation": derivation, "derivation_text": dtext, "registry": registry,
            "obstructions": typed["obstructions"] if typed is not None else None}


def diff(base: dict, new: dict) -> dict:
    """The derive diff of `new` against `base` (two DERIVATION documents)."""
    b = {e["law_id"]: e for e in base.get("laws", [])}
    n = {e["law_id"]: e for e in new.get("laws", [])}
    out = []
    for lid in sorted(set(b) | set(n)):
        x, y = b.get(lid), n.get(lid)
        eb = set(x.get("entry_points") or []) if x else set()
        en = set(y.get("entry_points") or []) if y else set()
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
           diff_path: str | None = None, log=print, catalog: str | None = None, codecs: list[str] | None = None,
           sidecar: str | None = None, undo_sidecar: str | None = None) -> int:
    root_p = Path(root).resolve() if root else ROOT
    cv = catalog or catalog_version(milestone)
    if cv not in CATALOGS:
        print(f"holon derive: unknown catalog {cv!r} (known: {sorted(CATALOGS)})", file=sys.stderr)
        return 1
    if catalog and target_milestone(milestone) and catalog != catalog_version(milestone):
        print(f"holon derive: refused: {milestone} derives with {catalog_version(milestone)}; --catalog {catalog} "
              "replaces the catalog of a test milestone only", file=sys.stderr)
        return 1
    if codecs and "PAR" not in CATALOGS[cv]:
        print(f"holon derive: --codec documents are derived by rule PAR, which catalog {cv} does not hold",
              file=sys.stderr)
        return 1
    try:
        res = compute(milestone, root_p, facts, assignment, sidecar, catalog=cv, codecs=codecs,
                      undo_sidecar=undo_sidecar)
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
    if res["obstructions"] is not None:   # no obstructions file without a SORT derivation (I24), else the typed part's
        obs_p.parent.mkdir(parents=True, exist_ok=True)
        obs_p.write_text(dumps(res["obstructions"]), encoding="utf-8")
    if against and diff_path:
        d = diff(base, res["derivation"])
        Path(diff_path).parent.mkdir(parents=True, exist_ok=True)
        Path(diff_path).write_text(dumps(d), encoding="utf-8")
    n_obs = len(res["obstructions"]["obstructions"]) if res["obstructions"] is not None else 0
    log(f"holon derive: {len(res['laws'])} laws, {n_obs} obstructions -> {laws_dir}")
    for e in res["derivation"]["laws"]:
        log(f"  {e['law_id']:58s} {', '.join(e.get('entry_points') or [])}")
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
    ap.add_argument("--catalog", help="a rule-catalog version of CATALOGS replacing a test milestone's catalog (I24)")
    ap.add_argument("--codec", action="append", help="a linked codec document to derive from (test milestones; I24)")
    ap.add_argument("--sidecar", help="the typed-sorts sidecar of an M3+ or T30+ milestone (default "
                                      "spec/<M>/lib/sort_types.json)")
    ap.add_argument("--undo-sidecar", help="rule UNDO's sidecar (default spec/<M>/lib/undo.json; I27)")
    a = ap.parse_args(argv)
    if bool(a.against) != bool(a.diff):
        ap.error("--against and --diff go together")
    return derive(a.milestone, a.root, a.out, a.obstructions, a.facts, a.assignment, a.against, a.diff,
                  catalog=a.catalog, codecs=a.codec, sidecar=a.sidecar, undo_sidecar=a.undo_sidecar)
