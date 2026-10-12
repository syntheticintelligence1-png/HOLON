"""I15: SORT II, per-site SORT laws and the rules registry, the first generated M2 laws (whitepaper §5.6, §7.2,
§7.3, §7.8, Thm 6.18 localization, App. E SORT basis, §9.4; BUILD_PLAN I15). This docstring is the contract that
tests_m2/test_sort_sites.py (builder A: registry, derive, sites, instrumented model, obstructions) and
tests_m2/test_sort_site_outcomes.py (builder B: proofs, refutation, replay, records, gate) read.
tests_m2/_i15.py and tests_m2/fixtures/sort_sites/ are instruments fixed at the prereg.

Inputs (frozen before this iteration): the I13 fact documents of milestone M2 (holon.diagram.fact_documents("M2"):
facts/morph_header.json, spec/M1/facts/morph_rollup.json, spec/M1/facts/morph_batchdata.json), the frozen I13
assignment gen/M2/sorts/assignment.json (its "sites" and "provenance"), and spec/M2/lib/sort_sites.json (the I15
sidecar, frozen in the I15 prereg commit: the revert reasons that mean a checked-arithmetic failure). For a milestone
M, derive and holon.gen.refs read spec/<M>/lib/sort_sites.json when it exists, else spec/M2/lib/sort_sites.json (so a
test milestone such as T15 uses M2's).

CLI
  python -m holon derive --milestone M [--root DIR] [--out DIR] [--obstructions PATH] [--facts PATH ...]
                         [--assignment PATH] [--against DIR --diff PATH]
    Derives the laws of every rule in the registry (I15: SORT, subform site) from the milestone's fact documents
    (or the documents --facts names, as `holon sorts` does) and the frozen sort assignment (default
    <root>/gen/<M>/sorts/assignment.json, or --assignment). Inputs are read from --root only, except --assignment and
    --against, which may lie outside it (an input read from outside --root is listed in "inputs" as
    "<outside>/<file name>"). It refuses, with exit 2
    and nothing written, an assignment whose "inputs" do not list every fact document it derives from with that
    document's current sha256 (a stale assignment: Thm 6.18's freezing condition). Default outputs: the laws
    directory <root>/laws/<M>/ (one <law_id>.json per law, REGISTRY.json, DERIVATION.json; a stale L*.json there is
    removed) and <root>/gen/<M>/sorts/obstructions.json. --out DIR writes the laws directory to DIR instead, and the
    obstructions to DIR/obstructions.json unless --obstructions PATH. --against DIR --diff PATH also writes the
    derive diff of this derivation against the one in DIR (a laws directory holding DERIVATION.json; DIR may lie
    outside --root) to PATH.
    Exit 0 on success; 3 when a site cannot be instrumented (it is named; no silent drop). Every file is
    deterministic: json.dumps(obj, indent=2, sort_keys=True) + "\\n", no timestamps, no absolute paths; two runs
    are byte-identical, and the default run reproduces the committed laws/M2/ and obstructions.json byte for byte
    (BUILD_PLAN §2.3: `holon derive` reproduces laws/<M>/).
  python -m holon run --milestone M2 [--laws ID,ID] [...the existing flags]
    as for any M2+ milestone, plus: --laws decides only those laws (the registry is still checked whole).
  python -m holon replay --milestone M2, python -m holon bind --milestone M2, python -m holon gate --milestone M2:
    builder B (tests_m2/test_sort_site_outcomes.py).

Rules registry (holon/rules/__init__.py)
  RULE_CATALOG_VERSION == "holon-rules/1.0" (rule_catalog_version 1, in the IR 0.3 form ^holon-rules/N.N$);
  CATALOG: {rule: {subform: producer}}, here {"SORT": {"site": holon.sorts.sites}}; derive(milestone, root, ...)
  runs every producer. A law id is a deterministic function of (rule, subform, basis element) (BUILD_PLAN §2.3).

Laws (holon-ir/0.3, laws/M2/<law_id>.json), one per I13 site of a holon-facts/0.2 document whose realized_in is "Nat"
(every site of assignment.json "sites" today: whatever its sort or obligation; F-M2-27, "every subtraction is a site")
  {"ir_version": "holon-ir/0.3", "law_id": law_id(site id), "milestone": "M2", "rule": "SORT", "subform": "site",
   "rule_catalog_version": "holon-rules/1.0", "facts": the site's fact document (repo-relative),
   "facts_sha256": its sha256, "notes": str,
   "statement": {"binders": [{"q": "forall", "name": "s", "type": "Reach"}, {"q": "forall", "name": "a", "type": "Act"},
                             then one {"q": "forall", "name": p, "type": "Fn<A,B>"} per oracle parameter p that the M2
                             model of the document threads (Machine.threaded, sidecar order; none without a sidecar)],
                 "assume": [],
                 "claim": {"eq": [{"site": <I13 site id>, "on": {"var": "a"}, "from": {"var": "s"}}, {"bool": true}]},
                 "scope": {"kind": "unbounded"}}}
  No "evidence" key (GEVID reads a missing key as the empty set: the obligation comes from the rule and the frozen
  assignment, and its provenance is DERIVATION.json) and no "predicted" key (a generator does not predict; the
  predictions are in spec/M2/predictions.json). law_id(site id): tests_m2/_i15.py::law_id, e.g.
  "morph_rollup:contracts/contracts/l1/rollup/Rollup.sol:363:1fc7f88a" -> "L_sort_site_rollup_363_1fc7f88a",
  "morph_rollup:morph_rollup:lci:356891e4" -> "L_sort_site_def_lci_356891e4"; holon.sorts.sites.law_id is the same
  function. Two sites mapping to one id is a derive error.
  The site term {"site": ID, "on": A, "from": S} (new in IR 0.3, additive: spec/schemas/law_ir_0_3.schema.json gains
  it, holon.ir.render_term renders it `site_ok[ID](A, S)`) is the Bool "every hit of site ID while action A is
  evaluated from state S has minuend >= subtrahend" (nonneg). With the binders above the law reads ∀s ∈ Reach, ∀a.
  at_site(a, s, ℓ) → nonneg(d_ℓ): the plan's ∀p. at_site(p, s0, ℓ) → nonneg(d_ℓ) with p = (a trace to s) ++ [a].
  It is kernel-neutral (it names a site by its span-derived id, not a Bend function) and hashed: the statement hash
  (holon.gen.refs.law_hash(law, facts)) covers the statement, rule_catalog_version, the transition function (the
  `step` ref, whatever the refs closure computes for it) and the ref "site:<ID>": the sha256 of the canonical JSON of
  {"template": "holon.sorts.sites/site_ok", "template_version": 1, "basis": {"site_id", "model", "span", "expr"},
   "hits": the site's hits as in DERIVATION.json}, computed from the facts and the sidecar (so G2 needs no derive
  output). Changing the sidecar's realization_check_reasons changes the hash of every law with a realization check.

Hit points (the rules fixed at the prereg; tests_m2/_i15.py::hit_points writes R8 and R9 out)
  R7 Law ids: as above.
  R8 Action sites. For each occurrence (action a, where) of a site, the hit is at the occurrence (the guard or let
     guards[i], or the effect effects.<field>), kind "occurrence", unless a require g of a that comes before the
     occurrence (any require of a, for an effect occurrence) is a realization check of the site: g's span (the
     leading "<path>:<line>[-<line>]" of its src) equals the site's span, and the text of g's reason in the facts'
     reasons table is in spec/M2/lib/sort_sites.json realization_check_reasons. Then the hit is at the first such g,
     kind "realization_check", evaluated just before g's require: g is the facts' model of the real code's own check
     of this subtraction (Solidity's checked arithmetic, Panic 0x11), so a human-modelled check never discharges the
     obligation it models ("whether or not a human modelled a require"). Any other require before the hit is an
     ordinary guard: the hit is evaluated only when it holds.
  R9 Definition sites (occurrences "defs.<d>.body"). The site is hit at every evaluation of d's body: at every call
     of d made while an action's guards and effects are evaluated, directly or through non-ghost definitions. Its
     entry points are those actions (F-M2-28); its hits are {"action", "at": a guard or effect whose expression
     calls a definition whose evaluation reaches d, "kind": "call", "via": [f] + ([d] if f != d)}, one per (action,
     at), where f is the first such call in a pre-order, left-to-right walk of the expression. A ghost definition
     ("ghost": true) is not instrumented and a call of it contributes no hit (its arguments are still evaluated).
     Observers and migrations are not actions: they are never instrumented.
  R10 Evaluation order. A hit counts only where the real code evaluates the subtraction: guards in order up to the
     first failing require; effects only when every require holds; inside an expression ["?", c, x, y] evaluates x
     only when c holds and y only when it fails, ["&&", x, y, ..] evaluates y only when x holds, ["||", x, y, ..]
     evaluates y only when x fails, a call of a definition evaluates its body with the arguments bound (its own
     conditionals likewise), and any other node evaluates every operand. At a realization-check hit, the path
     condition of the occurrence inside its own expression (the conditions of the enclosing ?, && and || on the way to
     the subtraction) is evaluated at g; a free variable of it, or of the minuend or subtrahend, that is not bound at g
     is a derive error (exit 3).
  R11 Coherence obstructions (§7.3 "a guard κ ⇒ ρ must read a sort written by the action family that ρ constrains";
     §7.8; R6 of tests_m2/test_sorts_morph.py made them I15's). For each require ["||", d1, .., dk] of action a with a
     disjunct ["!", κ], take ρ = the other disjunct (their disjunction when several); when ρ mentions an input of a,
     every state register that κ reads, through a's lets (recursively; definition calls read their arguments), whose
     variable has a writer-provenance entry in the frozen assignment that does not list a among its writers, is
     incoherent. One obstruction per (a, the require, at), at = the guard or let whose expression reads the register
     directly; tests_m2/_i15.py::expected_obstructions writes this out.

DERIVATION.json (laws/M2/)
  {"document": "derivation", "derive_version": "holon-derive/0.1", "milestone": "M2",
   "rule_catalog_version": "holon-rules/1.0", "sorts_sha256": the assignment's,
   "inputs": [{"path": repo-relative, "sha256"}] (every file read, sorted by path: the fact documents, their target
             libraries, gen/M2/sorts/assignment.json, spec/M2/lib/sort_sites.json),
   "laws": [{"law_id", "rule": "SORT", "subform": "site", "facts": path,
             "basis": {"kind": "site", "site_id", "model", "span", "expr"},
             "sort", "obligation", "realized_in": copied from the I13 site,
             "entry_points": [actions, sorted], "hits": [{"action", "at", "kind", "via" (kind call only)}] sorted by
             (action, at), "statement_hash": the law's}]  sorted by law_id}
  There is no field saying whether a site is a real subtraction of the code or a model coordinate (a window offset):
  that needs the Solidity frontend (I17-I19); spec/M2/predictions.json says it per site, from reading the source.

REGISTRY.json (laws/M2/)
  {"milestone": "M2", "ir_version": "holon-ir/0.3", "rule_catalog_version": "holon-rules/1.0",
   "facts": the fact document of the laws (the lexicographically first one a law names),
   "facts_sha256": its sha256, "facts_files": {path: sha256} of every fact document a law names,
   "statements": {law_id: statement hash}, "sorts_sha256": equal to gen/M2/sorts/assignment.json's (I13 contract),
   "derivation_sha256": sha256 of DERIVATION.json's bytes,
   "evidence_sha256": present iff <root>/gen/M2/evidence.json exists (I14), equal to that file's "evidence_sha256"}
  The registry is derive's output: `holon run` never writes it.

obstructions.json (gen/M2/sorts/obstructions.json)
  {"document": "obstructions", "derive_version": "holon-derive/0.1", "milestone": "M2", "inputs": [as DERIVATION],
   "sorts_sha256", "obstructions": [{"id": "coherence:<model>:<action>:<guard>:<at>", "kind": "coherence", "model",
     "action", "guard": "guards[i]" (the κ ⇒ ρ require), "guard_span", "kappa": DSL, "rho": DSL,
     "at": "guards[j]", "span": the span of the entry at `at` (its src's leading span, else the action's),
     "via": [definitions called at `at` that receive an incoherent register, sorted],
     "registers": [{"var", "sort", "label", "writers"}] sorted by var,
     "constrains": [inputs of the action that ρ mentions, sorted]}] sorted by id}
  Coherence obstructions are typing obstructions (Thm 6.18: localized to a site), not laws.

derive diff (--against DIR --diff PATH)
  {"document": "derive_diff", "derive_version": "holon-derive/0.1",
   "laws": [{"law_id", "change": "added" | "removed" | "statement" | "unchanged",
             "entry_points": {"lost": [sorted], "gained": [sorted]},
             "statement_hash": {"base": h | null, "new": h | null}}] sorted by law_id, one per id in either derivation}
  "statement" when both hold the id with different statement hashes; entry points are DERIVATION's.

The instrumented M2 model (holon.sorts.sites.instrumented_model(facts_path, derivation, root=None) -> str; `holon run
--milestone M2` writes it to gen/M2/model/<model>.bend)
  The text is the model holon builds for an M2 run of that document (Reach included; oracle tables as that run
  threads them), then the line GHOST_MARKER (tests_m2/_i15.py), then the ghost section, generated from the
  derivation: for each SORT-site law of the document, `def site_<x>(a: HAct, s: HSt[, the threaded tables]) -> Bool`
  with x = law_id[len("L_sort_site_"):], the site term of R8-R10 (true when the action does not reach a hit), and
  `def hit_<x>(a: HAct, s: HSt[, the threaded tables]) -> Bool`, true iff evaluating a from s reaches at least one hit
  of the site under R8-R10 (the requires before it hold, and so does the occurrence's path condition), whatever the
  obligation says there: the at_site premise of the plan's form ∀p. at_site(p, s0, ℓ) → nonneg(d_ℓ), which the site
  term folds in, so that non-vacuity can be stated (tests_m2/test_sort_site_outcomes.py); plus any helpers they need. Bend definitions only see definitions above them, so nothing of the model can read the ghost
  section: no definition before the marker names one defined after it, and the text before the marker is exactly the
  model holon generates for that run without sites (for a model that threads no oracle table: the M1 model
  gen/M1/model/<model>.bend followed by REACH_BLOCK). The ghost section adds no state field: a hit at a revert is
  not lost, since nothing is logged in the state. The emitted law (holon.gen.mlaws) applies M.site_<x>(a, s, ..).

Honesty (construction checks; I13's rules carried over, AGENTS rules 2 and 4)
  - Derive reads spans (the leading span of a src), the facts' reasons table, the sidecar and the frozen assignment;
    never a "site" or "note" annotation, a doc, or the facts' own spelling of names. On a copy mutated with I13's
    honesty mutations (tests_m2/test_sorts_honesty.py: strip, rename), the diagram and sorts regenerated each time,
    stripping changes no law, basis, entry point, hit or obstruction (statement and input hashes aside), and renaming
    renames them and changes nothing else (keyed by span and expression: a law id hashes the expression as written).
  - Nothing under holon/ names a site: no "<file>.sol:<line>" span, no SORT-site law id, no site hash of the frozen
    assignment. holon/rules/*.py, holon/sorts/sites.py and holon/sorts/check.py name no target identifier (derived from
    the fact documents and libraries, tests_m2/_i15.py::target_names; compound names anywhere, any 3+ character name
    when quoted) and no revert-reason text ("panic"): R8's only vocabulary is spec/M2/lib/sort_sites.json.

Coordination (I14, built in parallel): I15 creates laws/M2/ (I14 never writes there); whenever gen/M2/evidence.json
exists the registry's evidence_sha256 equals its "evidence_sha256" (re-run derive after the merge); generated laws
carry no "evidence" (I14's GEVID reads a missing key as the empty set, and names a site law's actions through its
anchors.sites, from the frozen assignment). The v2 record schema gains, additively, I15's "site" and "witnesses" (builder B) and I14's
evidence fields.
"""
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests_m2 import _i15 as H
from tests_m2._m2 import ROOT, SCHEMAS2, copy_repo, holon_module, load_json, run_holon, validate, write_json
from tests_m2.test_sorts_honesty import (LEAF_RN, ROLLUP as ROLLUP_PATH, dump, fact_paths, rename_identifiers,
                                         strip_hints, strip_state_docs)

DOCS = ("facts/morph_header.json", "spec/M1/facts/morph_batchdata.json", "spec/M1/facts/morph_rollup.json")
ROLLUP_REL = "spec/M1/facts/morph_rollup.json"
TOY_REL = "tests_m2/fixtures/sort_sites/toy_sites.json"
IR03 = SCHEMAS2 / "law_ir_0_3.schema.json"
LAW_FILES = re.compile(r"^L[0-9]?_[A-Za-z0-9_]+\.json$")
SITE_363 = "morph_rollup:contracts/contracts/l1/rollup/Rollup.sol:363:1fc7f88a"
SITE_636 = "morph_rollup:contracts/contracts/l1/rollup/Rollup.sol:636:e68daf06"
LAW_363 = "L_sort_site_rollup_363_1fc7f88a"
LAW_636 = "L_sort_site_rollup_636_e68daf06"
LAW_MUT2_NEW = "L_sort_site_rollup_360_364_1fc7f88a"
COMMITS = ("commitBatch", "commitBatchWithProof", "commitState")


def assignment() -> dict:
    return load_json(H.ASSIGNMENT)


def facts_of(rel: str, root: Path = ROOT) -> dict:
    return load_json(root / rel)


def file_sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class Derive:
    """One `python -m holon derive ...` run into a scratch directory, and what it wrote."""

    def __init__(self, args: list[str], cwd: Path = ROOT):
        self.tmp = Path(tempfile.mkdtemp(prefix="holon-derive-"))
        self.laws = self.tmp / "laws"
        self.obs = self.tmp / "obstructions.json"
        p = run_holon(["derive", *args, "--out", str(self.laws), "--obstructions", str(self.obs)], cwd=cwd)
        self.code = p.returncode
        self.log = f"exit {p.returncode}\n--- stdout\n{p.stdout[-3000:]}\n--- stderr\n{p.stderr[-3000:]}"

    def files(self) -> dict[str, bytes]:
        out = {f.name: f.read_bytes() for f in sorted(self.laws.glob("*")) if f.is_file()} if self.laws.is_dir() else {}
        if self.obs.exists():
            out["<obstructions>"] = self.obs.read_bytes()
        return out

    def doc(self, name: str) -> dict:
        p = self.obs if name == "obstructions" else self.laws / f"{name}.json"
        if not p.exists():
            raise AssertionError(f"holon derive wrote no {p.name}\n{self.log}")
        return load_json(p)

    def law_docs(self) -> dict[str, dict]:
        return {p.stem: load_json(p) for p in sorted(self.laws.glob("*.json")) if LAW_FILES.match(p.name)}

    def cleanup(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)


class _Shared(unittest.TestCase):
    d: Derive = None

    @classmethod
    def setUpClass(cls):
        if _Shared.d is None:
            _Shared.d = Derive(["--milestone", "M2"])

    @property
    def r(self) -> Derive:
        return _Shared.d

    def derivation_entry(self, lid: str) -> dict:
        e = next((x for x in self.r.doc("DERIVATION")["laws"] if x["law_id"] == lid), None)
        self.assertIsNotNone(e, f"DERIVATION.json has no entry for {lid}")
        return e


# ---------------------------------------------------------------------------------------------- construction
class TestDeriveContract(_Shared):
    def test_cli_writes_laws_registry_derivation_and_obstructions(self):
        self.assertEqual(self.r.code, 0, self.r.log)
        names = set(self.r.files())
        for f in ("REGISTRY.json", "DERIVATION.json", "<obstructions>"):
            self.assertIn(f, names, self.r.log)
        self.assertTrue(self.r.law_docs(), "no law written")

    def test_two_runs_are_byte_identical_and_match_the_committed_files(self):
        """Exit (construction check): derive is byte-identical across two runs and reproduces the committed laws/M2/
        and gen/M2/sorts/obstructions.json byte for byte."""
        self.assertEqual(self.r.code, 0, self.r.log)
        again = Derive(["--milestone", "M2"])
        try:
            self.assertEqual(again.code, 0, again.log)
            self.assertEqual(self.r.files(), again.files(), "two derive runs differ")
            committed = {f.name: f.read_bytes() for f in sorted(H.LAWS2.glob("*")) if f.is_file()}
            mine = {k: v for k, v in self.r.files().items() if k != "<obstructions>"}
            self.assertEqual(sorted(committed), sorted(mine), "laws/M2 holds exactly derive's files")
            for k in mine:
                with self.subTest(file=k):
                    self.assertEqual(committed[k], mine[k], f"committed laws/M2/{k} is stale")
            self.assertTrue(H.OBSTRUCTIONS.exists(), "gen/M2/sorts/obstructions.json is not committed")
            self.assertEqual(H.OBSTRUCTIONS.read_bytes(), self.r.files()["<obstructions>"])
            for k, b in mine.items():
                self.assertEqual(b, (json.dumps(json.loads(b), indent=2, sort_keys=True) + "\n").encode(),
                                 f"{k}: not in the canonical file form")
        finally:
            again.cleanup()

    def test_one_law_per_site(self):
        sites = [s for s in assignment()["sites"] if s["realized_in"] == "Nat"]
        laws = self.r.law_docs()
        self.assertEqual(sorted(laws), sorted(H.law_id(s["id"]) for s in sites))
        self.assertEqual(len(laws), len(sites), "one law per site, no two sites share an id")
        rules = holon_module("holon.rules")
        sites_mod = holon_module("holon.sorts.sites")
        self.assertEqual(rules.RULE_CATALOG_VERSION, H.RULE_CATALOG_VERSION)
        self.assertIn("site", rules.CATALOG.get("SORT", {}))
        for s in sites:
            with self.subTest(site=s["id"]):
                self.assertEqual(sites_mod.law_id(s["id"]), H.law_id(s["id"]))

    def test_law_ir(self):
        self.assertTrue(IR03.exists())
        A = assignment()
        facts_path = {m: mo["facts"] for m, mo in A["models"].items()}
        laws = self.r.law_docs()
        self.assertTrue(laws, self.r.log)
        for lid, law in laws.items():
            with self.subTest(law=lid):
                self.assertEqual(validate(law, IR03), [])
                e = self.derivation_entry(lid)
                site = next(s for s in A["sites"] if s["id"] == e["basis"]["site_id"])
                self.assertEqual(law["ir_version"], "holon-ir/0.3")
                self.assertEqual((law["milestone"], law["rule"], law["subform"], law["rule_catalog_version"]),
                                 ("M2", "SORT", "site", H.RULE_CATALOG_VERSION))
                self.assertEqual(law["facts"], facts_path[site["model"]])
                self.assertEqual(law["facts_sha256"], file_sha(ROOT / law["facts"]))
                self.assertNotIn("evidence", law, "a generated law carries no evidence metadata")
                self.assertNotIn("predicted", law, "a generator does not predict")
                st = law["statement"]
                self.assertEqual(st["binders"][:2], [{"q": "forall", "name": "s", "type": "Reach"},
                                                     {"q": "forall", "name": "a", "type": "Act"}])
                for b in st["binders"][2:]:
                    self.assertEqual(b["q"], "forall")
                    self.assertTrue(b["type"].startswith("Fn<"), b)
                self.assertEqual(st.get("assume", []), [])
                self.assertEqual(st["claim"], {"eq": [{"site": site["id"], "on": {"var": "a"}, "from": {"var": "s"}},
                                                      {"bool": True}]})
                self.assertEqual(st["scope"], {"kind": "unbounded"})

    def test_registry(self):
        reg = self.r.doc("REGISTRY")
        laws = self.r.law_docs()
        dv = self.r.doc("DERIVATION")
        A = assignment()
        self.assertEqual((reg["milestone"], reg["ir_version"], reg["rule_catalog_version"]),
                         ("M2", "holon-ir/0.3", H.RULE_CATALOG_VERSION))
        self.assertEqual(reg["sorts_sha256"], A["sorts_sha256"], "the registry carries the frozen assignment's hash")
        self.assertEqual(sorted(reg["statements"]), sorted(laws))
        named = sorted({l["facts"] for l in laws.values()})
        self.assertEqual(reg["facts_files"], {p: file_sha(ROOT / p) for p in named})
        self.assertEqual(reg["facts"], named[0])
        self.assertEqual(reg["facts_sha256"], file_sha(ROOT / named[0]))
        self.assertEqual(reg["derivation_sha256"], hashlib.sha256((self.r.laws / "DERIVATION.json").read_bytes()).hexdigest())
        ev = ROOT / "gen" / "M2" / "evidence.json"
        if ev.exists():   # I14's frozen evidence set, merged later: its identity is copied, never recomputed here
            self.assertEqual(reg.get("evidence_sha256"), load_json(ev).get("evidence_sha256"))
        else:
            self.assertNotIn("evidence_sha256", reg)
        refs = holon_module("holon.gen.refs")
        by_id = {e["law_id"]: e for e in dv["laws"]}
        for lid, law in laws.items():
            with self.subTest(law=lid):
                h = refs.law_hash(law, facts_of(law["facts"]))
                self.assertRegex(h, r"^sha256:[0-9a-f]{64}$")
                self.assertEqual(reg["statements"][lid], h)
                self.assertEqual(by_id[lid]["statement_hash"], h)

    def test_derivation_follows_the_rules(self):
        """R8-R10 (construction): every law's basis, entry points and hits are those tests_m2/_i15.py computes from the
        facts and the frozen assignment; sort, obligation and realized_in are copied from the I13 site."""
        dv = self.r.doc("DERIVATION")
        A = assignment()
        self.assertEqual((dv["document"], dv["derive_version"], dv["milestone"], dv["rule_catalog_version"]),
                         ("derivation", H.DERIVE_VERSION, "M2", H.RULE_CATALOG_VERSION))
        self.assertEqual(dv["sorts_sha256"], A["sorts_sha256"])
        paths = [i["path"] for i in dv["inputs"]]
        self.assertEqual(paths, sorted(paths))
        for p in list(DOCS) + ["gen/M2/sorts/assignment.json", "spec/M2/lib/sort_sites.json"]:
            self.assertIn(p, paths)
        for i in dv["inputs"]:
            self.assertEqual(i["sha256"], file_sha(ROOT / i["path"]), i["path"])
        self.assertEqual([e["law_id"] for e in dv["laws"]], sorted(e["law_id"] for e in dv["laws"]))
        models = {m: load_json(ROOT / mo["facts"]) for m, mo in A["models"].items()}
        for e in dv["laws"]:
            with self.subTest(law=e["law_id"]):
                site = next(s for s in A["sites"] if s["id"] == e["basis"]["site_id"])
                f = models[site["model"]]
                self.assertEqual(e["law_id"], H.law_id(site["id"]))
                self.assertEqual((e["rule"], e["subform"]), ("SORT", "site"))
                self.assertEqual(e["basis"], {"kind": "site", "site_id": site["id"], "model": site["model"],
                                              "span": site["span"], "expr": site["expr"]})
                for k in ("sort", "obligation", "realized_in"):
                    self.assertEqual(e[k], site[k], k)
                want = H.hit_points(f, site)
                self.assertEqual([{k: h[k] for k in ("action", "at", "kind")} for h in e["hits"]], want)
                self.assertEqual(e["entry_points"], sorted({h["action"] for h in want}))
                for h in e["hits"]:
                    if h["kind"] == "call":
                        self.assertEqual(h["via"][-1], e["basis"]["span"].split(":")[-1], "via ends with the def")

    def test_derive_refuses_a_stale_assignment(self):
        """Thm 6.18's freezing condition: an assignment computed from other facts is refused, exit 2, nothing written
        (in a copy where derive first succeeds, so that the exit status is derive's own refusal)."""
        repo = copy_repo()
        try:
            ok = repo.parent / "ok"
            q0 = run_holon(["derive", "--milestone", "M2", "--out", str(ok), "--obstructions", str(ok / "o.json")], cwd=repo)
            self.assertEqual(q0.returncode, 0, q0.stdout[-1500:] + q0.stderr[-1500:])
            p = repo / ROLLUP_REL
            f = load_json(p)
            f["abstractions"] = list(f["abstractions"]) + ["(I15 test edit: the assignment no longer lists this file's hash)"]
            write_json(p, f)
            out = repo.parent / "out"
            q = run_holon(["derive", "--milestone", "M2", "--out", str(out), "--obstructions", str(out / "o.json")], cwd=repo)
            self.assertEqual(q.returncode, 2, q.stdout[-1500:] + q.stderr[-1500:])
            self.assertNotIn("usage:", q.stderr, "the CLI rejected the arguments: not a refusal of the assignment")
            self.assertFalse(out.exists() and any(out.iterdir()), "a refused derive writes nothing")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_site_spec_is_hashed(self):
        """The statement hash covers the site's hit points: with the sidecar's realization reasons emptied (in a copy),
        the :363 law's hits become occurrences and its hash changes; a law without a realization check keeps its hash."""
        repo = copy_repo()
        try:
            sc = repo / "spec" / "M2" / "lib" / "sort_sites.json"
            doc = load_json(sc)
            doc["realization_check_reasons"] = []
            write_json(sc, doc)
            out = repo.parent / "out"
            q = run_holon(["derive", "--milestone", "M2", "--out", str(out), "--obstructions", str(out / "o.json")], cwd=repo)
            self.assertEqual(q.returncode, 0, q.stdout[-1500:] + q.stderr[-1500:])
            new = {e["law_id"]: e for e in load_json(out / "DERIVATION.json")["laws"]}
            base = {e["law_id"]: e for e in self.r.doc("DERIVATION")["laws"]}
            self.assertEqual({h["kind"] for h in new[LAW_363]["hits"]}, {"occurrence"})
            self.assertNotEqual(new[LAW_363]["statement_hash"], base[LAW_363]["statement_hash"])
            for lid, e in base.items():
                if all(h["kind"] != "realization_check" for h in e["hits"]):
                    self.assertEqual(new[lid]["statement_hash"], e["statement_hash"], lid)
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


class TestObstructions(_Shared):
    def test_obstructions_follow_rule_r11(self):
        """R11 (construction): the obstructions are exactly those tests_m2/_i15.py computes, with the contract's fields."""
        doc = self.r.doc("obstructions")
        A = assignment()
        self.assertEqual((doc["document"], doc["derive_version"], doc["milestone"], doc["sorts_sha256"]),
                         ("obstructions", H.DERIVE_VERSION, "M2", A["sorts_sha256"]))
        want = []
        for m, mo in sorted(A["models"].items()):
            f = load_json(ROOT / mo["facts"])
            if f.get("facts_version") != "holon-facts/0.2":
                continue
            want += [dict(x, model=m) for x in H.expected_obstructions(f, A, m)]
        got = [{"model": o["model"], "action": o["action"], "guard": o["guard"], "at": o["at"],
                "registers": [r["var"] for r in o["registers"]]} for o in doc["obstructions"]]
        key = lambda o: (o["model"], o["action"], o["guard"], o["at"])
        self.assertEqual(sorted(got, key=key), sorted(want, key=key))
        self.assertEqual([o["id"] for o in doc["obstructions"]], sorted(o["id"] for o in doc["obstructions"]))
        for o in doc["obstructions"]:
            with self.subTest(obstruction=o["id"]):
                self.assertEqual(o["id"], f"coherence:{o['model']}:{o['action']}:{o['guard']}:{o['at']}")
                self.assertEqual(o["kind"], "coherence")
                prov = A["models"][o["model"]]["provenance"]
                for r in o["registers"]:
                    self.assertEqual(r["sort"], A["models"][o["model"]]["assignment"][r["var"]])
                    self.assertEqual((r["label"], r["writers"]), (prov[r["var"]]["label"], prov[r["var"]]["writers"]))
                    self.assertNotIn(o["action"], r["writers"])


class TestToyDerivation(unittest.TestCase):
    """Construction checks on the toy fixture (tests_m2/fixtures/sort_sites/toy_sites.json, milestone T15): every rule
    on a machine small enough to read by hand. Its I13 assignment is computed by `holon sorts` (I13's code)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="holon-toy-sites-"))
        p = run_holon(["sorts", "--facts", TOY_REL, "--out", str(cls.tmp / "sorts")])
        cls.sorts_log = p.stdout[-2000:] + p.stderr[-2000:]
        cls.d = Derive(["--milestone", "T15", "--facts", TOY_REL, "--assignment", str(cls.tmp / "sorts" / "assignment.json")])

    @classmethod
    def tearDownClass(cls):
        cls.d.cleanup()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_toy_laws_hits_and_obstruction(self):
        self.assertEqual(self.d.code, 0, self.sorts_log + self.d.log)
        dv = {e["law_id"]: e for e in self.d.doc("DERIVATION")["laws"]}
        want = {"L_sort_site_toy_12_b4cd5068": [("revertTo", "guards[2]", "occurrence")],
                "L_sort_site_toy_34_b2fa4afd": [("commit", "guards[2]", "realization_check")],
                "L_sort_site_toy_52_e68daf06": [("finalize", "guards[1]", "realization_check")],
                "L_sort_site_toy_56_58_e68daf06": [("finalize", "effects.last", "occurrence")],
                "L_sort_site_toy_56_58_7f392a5d": [("finalize", "effects.len", "occurrence")],
                "L_sort_site_def_after_aca797ff": [("commit", "guards[4]", "call")],
                "L_sort_site_def_lci_ed147249": [("commit", "guards[4]", "call"), ("finalize", "guards[0]", "call")]}
        self.assertEqual(sorted(dv), sorted(want))
        for lid, hits in want.items():
            with self.subTest(law=lid):
                self.assertEqual([(h["action"], h["at"], h["kind"]) for h in dv[lid]["hits"]], hits)
        self.assertEqual(dv["L_sort_site_def_lci_ed147249"]["hits"][0]["via"], ["after", "lci"])
        obs = self.d.doc("obstructions")["obstructions"]
        self.assertEqual([(o["action"], o["guard"], o["at"], [r["var"] for r in o["registers"]], o["via"]) for o in obs],
                         [("commit", "guards[1]", "guards[0]", ["qpend"], ["first"])])
        laws = self.d.law_docs()
        self.assertTrue(all(l["milestone"] == "T15" and l["facts"] == TOY_REL for l in laws.values()))

    def test_toy_instrumented_model_checks_and_leaves_the_model_alone(self):
        """The ghost section of the toy model: one site_<x> per law, after GHOST_MARKER; the text before it is the model
        holon generates without sites; nothing before the marker names a ghost definition; Bend checks the file."""
        sites = holon_module("holon.sorts.sites")
        machine = holon_module("holon.gen.machine")
        facts = ROOT / TOY_REL
        text = sites.instrumented_model(facts, self.d.doc("DERIVATION"))
        self.assertEqual(text.count(H.GHOST_MARKER), 1)
        head, ghost = text.split(H.GHOST_MARKER)
        plain = machine.Machine(load_json(facts), facts, m2plus=True).generate(file_sha(facts), reach=True)
        self.assertEqual(head.rstrip("\n"), plain.rstrip("\n"), "the model above the ghost section is unchanged")
        defined = set(re.findall(r"^def\s+(\w+)\(", ghost, re.M))
        for lid in self.d.law_docs():
            self.assertIn("site_" + lid[len("L_sort_site_"):], defined)
            self.assertIn("hit_" + lid[len("L_sort_site_"):], defined, "the at_site predicate of the law")
        for name in defined:
            self.assertIsNone(re.search(rf"(?<![\w.]){re.escape(name)}\(", head), f"{name} is named above the marker")
        work = self.tmp / "model"
        work.mkdir(exist_ok=True)
        (work / "toy_sites.bend").write_text(text)
        from tests._util import run_bend
        code, out = run_bend(["toy_sites.bend"], cwd=work)
        self.assertEqual(code, 0, out[-2000:])
        self.assertIn("ALL PROOFS CHECK", out)


class TestInstrumentedMorphModel(_Shared):
    def test_ghost_section_follows_the_m2_model_unchanged(self):
        """Construction: the rollup's instrumented model = the M2 model (= the M1 model and the Reach block when no
        oracle table is threaded) + the ghost section, which nothing above it can read; Bend checks it."""
        sites = holon_module("holon.sorts.sites")
        machine = holon_module("holon.gen.machine")
        facts = ROOT / ROLLUP_REL
        text = sites.instrumented_model(facts, self.r.doc("DERIVATION"))
        self.assertEqual(text.count(H.GHOST_MARKER), 1)
        head, ghost = text.split(H.GHOST_MARKER)
        if "type Reach<-s: HSt> is Type:" in head:   # no oracle table threaded: compare with the frozen M1 model
            m1 = (ROOT / "gen" / "M1" / "model" / "morph_rollup.bend").read_text()
            self.assertTrue(head.startswith(m1.rstrip("\n")), "the M1 model is the prefix of the M2 model")
            self.assertEqual(head[len(m1.rstrip("\n")):].strip(), H.REACH_BLOCK.strip())
        defined = set(re.findall(r"^def\s+(\w+)\(", ghost, re.M))
        laws = [l for l in self.r.law_docs().values() if l["facts"] == ROLLUP_REL]
        self.assertTrue(laws)
        for l in laws:
            self.assertIn("site_" + l["law_id"][len("L_sort_site_"):], defined)
            self.assertIn("hit_" + l["law_id"][len("L_sort_site_"):], defined, "the at_site predicate of the law")
        for name in defined:
            self.assertIsNone(re.search(rf"(?<![\w.]){re.escape(name)}\(", head), f"{name} is named above the marker")
        self.assertNotIn("type HSt", ghost, "the ghost section adds no state")
        work = Path(tempfile.mkdtemp(prefix="holon-i15-model-"))
        try:
            (work / "morph_rollup.bend").write_text(text)
            from tests._util import run_bend
            code, out = run_bend(["morph_rollup.bend"], cwd=work)
            self.assertEqual(code, 0, out[-2000:])
            self.assertIn("ALL PROOFS CHECK", out)
        finally:
            shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- honesty (construction)
INVERSE_RN = {v: k for k, v in LEAF_RN.items()}
_RENAMED = re.compile(r"\b(" + "|".join(sorted(map(re.escape, INVERSE_RN), key=len, reverse=True)) + r")\b")


def unrename(obj):
    """obj with every identifier I13's rename introduced mapped back (on its JSON text: the zz_ names are unique)."""
    return json.loads(_RENAMED.sub(lambda m: INVERSE_RN[m.group(1)], json.dumps(obj, sort_keys=True)))


def derivation_view(dv: dict, back: bool = False) -> dict:
    """DERIVATION laws keyed by (span, expression as written), each with what derive decided for it."""
    out = {}
    for e in dv["laws"]:
        b = unrename(e["basis"]) if back else e["basis"]
        out[(b["span"], json.dumps(b["expr"], sort_keys=True))] = {
            k: (unrename(e[k]) if back else e[k]) for k in ("entry_points", "hits", "sort", "obligation", "realized_in")}
    return out


class TestDeriveHonesty(unittest.TestCase):
    """Derive reads no hand annotation and does not key on the facts' spelling of names (contract: Honesty). One copy,
    I13's mutations (tests_m2/test_sorts_honesty.py); each time `holon diagram`, `holon sorts --out` and `holon derive
    --assignment` run in the copy."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        try:
            cls._run_all()
        except BaseException:
            shutil.rmtree(cls.repo.parent, ignore_errors=True)
            raise

    @classmethod
    def _run_all(cls):
        repo = cls.repo
        orig = {p: json.loads(p.read_text(encoding="utf-8")) for p in fact_paths(repo)}
        rollup = repo / ROLLUP_PATH

        def strip_all():
            for p, f in orig.items():
                dump(p, strip_state_docs(strip_hints(f)))

        def rename_all():
            dump(rollup, rename_identifiers(orig[rollup]))

        cls.runs = {}
        for name, mutate in (("baseline", None), ("strip", strip_all), ("rename", rename_all)):
            for p, f in orig.items():
                dump(p, f)
            if mutate:
                mutate()
            sorts, out, obs = repo / f"sorts_{name}", repo / f"laws_{name}", repo / f"obstructions_{name}.json"
            logs, ok = [], True
            for args in (["diagram", "--milestone", "M2", "--root", str(repo)],
                         ["sorts", "--milestone", "M2", "--root", str(repo), "--out", str(sorts)],
                         ["derive", "--milestone", "M2", "--root", str(repo), "--assignment", str(sorts / "assignment.json"),
                          "--out", str(out), "--obstructions", str(obs)]):
                q = run_holon(args, cwd=repo)
                logs.append(f"$ holon {args[0]} ({name}): exit {q.returncode}\n{q.stdout[-1500:]}{q.stderr[-1500:]}")
                if q.returncode != 0:
                    ok = False
                    break
            docs = {}
            if ok and (out / "DERIVATION.json").exists() and obs.exists():
                docs = {"derivation": load_json(out / "DERIVATION.json"), "obstructions": load_json(obs),
                        "laws": {f.stem: load_json(f) for f in sorted(out.glob("L*.json"))}}
            cls.runs[name] = (ok, "\n".join(logs), docs)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def ran(self, name: str) -> dict:
        ok, log, docs = self.runs[name]
        self.assertTrue(ok, log)
        self.assertTrue(docs, f"{name}: holon derive wrote no DERIVATION.json or obstructions.json\n{log}")
        return docs

    def test_stripping_hand_hints_changes_no_law_hit_or_obstruction(self):
        """strip (the :363 guards' "site" annotations, every "note", docs stating sorts or sites): the same laws, bases,
        entry points, hits and obstructions; statements equal apart from facts_sha256."""
        base, strip = self.ran("baseline"), self.ran("strip")
        self.assertTrue(base["derivation"]["laws"], "the baseline derives laws")
        self.assertEqual(derivation_view(strip["derivation"]), derivation_view(base["derivation"]))
        self.assertEqual(sorted(strip["laws"]), sorted(base["laws"]))
        for lid, law in base["laws"].items():
            with self.subTest(law=lid):
                self.assertEqual({k: v for k, v in strip["laws"][lid].items() if k != "facts_sha256"},
                                 {k: v for k, v in law.items() if k != "facts_sha256"})
        self.assertEqual(strip["obstructions"]["obstructions"], base["obstructions"]["obstructions"])

    def test_renaming_fact_identifiers_renames_the_derivation_and_nothing_else(self):
        """rename: the derivation keyed by span and expression is the baseline's under the renaming, and so are the
        obstructions (their registers and constrained inputs renamed back)."""
        base, rn = self.ran("baseline"), self.ran("rename")
        self.assertTrue(any("zz_" in json.dumps(e["basis"]["expr"]) for e in rn["derivation"]["laws"]),
                        "the renaming reached a site expression")
        self.assertEqual(derivation_view(rn["derivation"], back=True), derivation_view(base["derivation"]))
        strip_id = lambda o: {k: v for k, v in o.items() if k != "id"}  # noqa: E731
        # registers are listed sorted by var (contract), an order the renaming changes: re-sorted once named back
        by_var = lambda o: dict(o, registers=sorted(o["registers"], key=lambda r: r["var"]))  # noqa: E731
        self.assertEqual(sorted(json.dumps(by_var(unrename(strip_id(o))), sort_keys=True) for o in rn["obstructions"]["obstructions"]),
                         sorted(json.dumps(by_var(strip_id(o)), sort_keys=True) for o in base["obstructions"]["obstructions"]))


class TestGenericCode(unittest.TestCase):
    """No special-casing (AGENTS rule 2; contract: Honesty)."""

    def test_nothing_under_holon_names_a_site_span_or_site_law(self):
        hashes = sorted({s["id"].rsplit(":", 1)[1] for s in assignment()["sites"]})
        self.assertTrue(hashes)
        pat = re.compile(r"\.sol:\d|L_sort_site_\w*[0-9a-f]{8}|\b(" + "|".join(hashes) + r")\b")
        files = [f for f in sorted((ROOT / "holon").rglob("*")) if f.suffix in (".py", ".mjs", ".js")
                 and "__pycache__" not in f.parts and "node_modules" not in f.parts]
        self.assertTrue(files)
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                m = pat.search(f.read_text(encoding="utf-8", errors="replace"))
                self.assertIsNone(m, m and m.group(0))

    def test_the_rule_code_names_no_target_and_no_reason_text(self):
        files = sorted((ROOT / "holon" / "rules").glob("*.py")) + [ROOT / "holon" / "sorts" / "sites.py",
                                                                    ROOT / "holon" / "sorts" / "check.py"]
        compound, quoted = H.compound_target_names(), H.quoted_target_names()
        for f in files:
            with self.subTest(file=str(f.relative_to(ROOT))):
                self.assertTrue(f.exists(), f"{f.relative_to(ROOT)} is missing")
                text = f.read_text(encoding="utf-8")
                self.assertEqual(sorted(n for n in compound
                                        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text)), [])
                self.assertEqual(sorted(n for n in quoted if re.search(rf"[\"']{re.escape(n)}[\"']", text)), [])
                self.assertNotRegex(text, r"(?i)panic", "R8 reads the realization reasons from the sidecar only")


# ---------------------------------------------------------------------------------------------- predictions
class TestPredictedDerivation(_Shared):
    def test_363_is_one_law_reached_from_the_three_commits_at_their_realization_checks(self):
        """I15-P3 (derivation half): the :363 site yields ONE law, L_sort_site_rollup_363_1fc7f88a, whose entry points
        are commitBatch, commitBatchWithProof and commitState, each hit at its realization check (the facts' require
        !inch || t <= W + cstart, reason panic:0x11, span :363): guards[23], guards[27] and guards[22]."""
        laws = self.r.law_docs()
        self.assertEqual([l for l, d in laws.items() if d["statement"]["claim"]["eq"][0]["site"] == SITE_363], [LAW_363])
        e = self.derivation_entry(LAW_363)
        self.assertEqual(e["entry_points"], list(COMMITS))
        self.assertEqual([(h["action"], h["at"], h["kind"]) for h in e["hits"]],
                         [("commitBatch", "guards[23]", "realization_check"),
                          ("commitBatchWithProof", "guards[27]", "realization_check"),
                          ("commitState", "guards[22]", "realization_check")])

    def test_636_is_hit_before_its_realization_check(self):
        """I15-P4 (derivation half): the :636 site's require idx >= 1 (reason panic:0x11, span :636) is the facts' model of
        the real code's checked _batchIndex - 1, so the hit is at finalizeBatch guards[8], before it."""
        e = self.derivation_entry(LAW_636)
        self.assertEqual([(h["action"], h["at"], h["kind"]) for h in e["hits"]],
                         [("finalizeBatch", "guards[8]", "realization_check")])

    def test_coherence_obstructions_at_the_enq_first_call_sites(self):
        """I15-P6: the coherence obstructions of the M2 facts are exactly three, one at each enq_first call site of the
        delay guard !(ef + D < t) || n > 0: commitBatch guards[5], commitState guards[10] and commitBatchWithProof
        guards[4] (the require is guards[6], guards[11] and guards[6]); each passes qlen (Idx[queue]_wcf8ad7dc, writers
        {sendMessage}) and qpend (Idx[queue]_fin, writers {finalizeBatch}) into enq_first, while ρ (n > 0) constrains the
        commit family, which writes Entry.tot (Idx[queue]_inc). Nowhere else (the :363 require's ρ reads no input;
        setPause's reads only Bool registers)."""
        doc = self.r.doc("obstructions")
        got = [(o["model"], o["action"], o["guard"], o["at"], o["via"], [r["var"] for r in o["registers"]])
               for o in doc["obstructions"]]
        self.assertEqual(sorted(got), sorted([
            ("morph_rollup", "commitBatch", "guards[6]", "guards[5]", ["enq_first"], ["qlen", "qpend"]),
            ("morph_rollup", "commitBatchWithProof", "guards[6]", "guards[4]", ["enq_first"], ["qlen", "qpend"]),
            ("morph_rollup", "commitState", "guards[11]", "guards[10]", ["enq_first"], ["qlen", "qpend"])]))
        for o in doc["obstructions"]:
            self.assertEqual(o["constrains"], ["n"])
            self.assertEqual({r["var"]: r["sort"] for r in o["registers"]},
                             {"qlen": "Idx[queue]_wcf8ad7dc", "qpend": "Idx[queue]_fin"})


class TestMut2Derivation(unittest.TestCase):
    """MUT2 (spec/M1/mutations.json MUT2_cwp_no_underflow_check: /actions/2/guards/27/require := true), in a copy: the
    copy's sorts are regenerated by `holon sorts`, then `holon derive --against <ROOT>/laws/M2 --diff`."""

    @classmethod
    def setUpClass(cls):
        cls.repo = copy_repo()
        mut = next(m for m in load_json(H.MUTATIONS)["mutations"] if m["id"].startswith("MUT2"))
        p = cls.repo / ROLLUP_REL
        f = load_json(p)
        node, *path = mut["edit"]["pointer"].strip("/").split("/")
        cur = f[node]
        for k in path[:-1]:
            cur = cur[int(k)] if isinstance(cur, list) else cur[k]
        cur[path[-1]] = mut["edit"]["value"]
        write_json(p, f)
        a = run_holon(["sorts", "--milestone", "M2"], cwd=cls.repo)
        cls.diff_path = cls.repo.parent / "derive_diff.json"
        b = run_holon(["derive", "--milestone", "M2", "--against", str(ROOT / "laws" / "M2"), "--diff", str(cls.diff_path)],
                      cwd=cls.repo)
        cls.log = "\n".join(x.stdout[-1500:] + x.stderr[-1500:] for x in (a, b))
        cls.codes = (a.returncode, b.returncode)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo.parent, ignore_errors=True)

    def test_derive_diff_lists_commit_batch_with_proof_as_no_longer_reaching_363(self):
        """I15-P5 (derive half): under MUT2 the :363 law is still generated (same id) with entry points commitBatch and
        commitState; the derive diff lists commitBatchWithProof as lost from it, and a new law
        L_sort_site_rollup_360_364_1fc7f88a (the unchecked subtraction of commitBatchWithProof, span :360-364, hit at
        its occurrence) is added with that single entry point."""
        self.assertEqual(self.codes, (0, 0), self.log)
        d = load_json(self.diff_path)
        self.assertEqual((d["document"], d["derive_version"]), ("derive_diff", H.DERIVE_VERSION))
        by = {x["law_id"]: x for x in d["laws"]}
        self.assertEqual([x["law_id"] for x in d["laws"]], sorted(by))
        self.assertIn(LAW_363, by)
        self.assertIn(by[LAW_363]["change"], ("statement", "unchanged"))
        self.assertEqual(by[LAW_363]["entry_points"], {"lost": ["commitBatchWithProof"], "gained": []})
        self.assertEqual(by.get(LAW_MUT2_NEW, {}).get("change"), "added", sorted(by))
        self.assertEqual(by[LAW_MUT2_NEW]["entry_points"], {"lost": [], "gained": ["commitBatchWithProof"]})
        dv = {e["law_id"]: e for e in load_json(self.repo / "laws" / "M2" / "DERIVATION.json")["laws"]}
        self.assertEqual(dv[LAW_363]["entry_points"], ["commitBatch", "commitState"])
        self.assertEqual([(h["action"], h["at"], h["kind"]) for h in dv[LAW_MUT2_NEW]["hits"]],
                         [("commitBatchWithProof", "guards[28]", "occurrence")])


def tearDownModule():
    if _Shared.d is not None:
        _Shared.d.cleanup()
        _Shared.d = None


if __name__ == "__main__":
    unittest.main()
