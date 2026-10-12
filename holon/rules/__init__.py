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

ROOT = Path(__file__).resolve().parents[2]
RULE_CATALOG_VERSION = "holon-rules/1.0"
DERIVE_VERSION = "holon-derive/0.1"
IR_VERSION = "holon-ir/0.3"
CATALOG = {"SORT": {"site": _sites}}


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
        self.rel = inputs.rel(path)
        data = inputs.read(path)
        self.sha256 = sha256_bytes(data)
        self.facts = json.loads(data.decode("utf-8"))
        self.model = path.stem
        self.params: list[tuple[str, str]] = []
        self.builtins: dict = {}
        self._machine = None
        self.orc = None
        if self.facts.get("facts_version") != "holon-facts/0.2":
            return
        libs = [inputs.json(p) for p in lib_files(path, root)]
        self.builtins = Library(libs, self.facts.get("params", {})).builtins
        self.orc = Oracles.for_milestone(milestone, path, root)
        if self.orc is not None and self.orc.path is not None:
            inputs.read(self.orc.path)
        m = self.machine()
        self.params = [(p, self.orc.param_type(p)) for p in m.threaded] if self.orc is not None else []

    def machine(self):
        """The document's machine with the milestone's oracle parameters (expressions, threaded tables)."""
        if self._machine is None:
            from ..gen.machine import Machine
            self._machine = Machine(self.facts, self.path, oracles=self.orc)
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


def compute(milestone: str, root: Path, facts: list[str] | None = None, assignment: str | None = None) -> dict:
    """Everything derive writes, as documents (nothing is written here)."""
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
    derivation = {"document": "derivation", "derive_version": DERIVE_VERSION, "milestone": milestone,
                  "rule_catalog_version": RULE_CATALOG_VERSION, "sorts_sha256": A.get("sorts_sha256"),
                  "inputs": listing, "laws": entries}
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
           diff_path: str | None = None, log=print) -> int:
    root_p = Path(root).resolve() if root else ROOT
    try:
        res = compute(milestone, root_p, facts, assignment)
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
    a = ap.parse_args(argv)
    if bool(a.against) != bool(a.diff):
        ap.error("--against and --diff go together")
    return derive(a.milestone, a.root, a.out, a.obstructions, a.facts, a.assignment, a.against, a.diff)
