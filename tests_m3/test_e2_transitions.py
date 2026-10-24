"""I72: E2 over the adopted holon-facts/0.3 transitions documents, in M2's and M3's evidence sets (I33's evidence key;
whitepaper Def 4.5; BUILD_PLAN I14, I20, I66 and row I72). This docstring is the contract.

Scope. I20 covered each transitions document a milestone adopts for derivation with a model of anchors only: E1-E6
are defined over facts 0.1 and 0.2 diagrams, so such a model has no atom, and a law over it that names an edge has no
evidence (levels []). I33's M3 contract (C_o12_m3) will claim E2 for a law over the adopted Rollup document
spec/M2/facts/morph_rollup.extracted.json, and GEVID (I14, enforcing from M2 on, with no exemption) fails a law whose
metadata evidence its computed levels lack. I72 computes E2, "written via p, read via q", over an adopted
transitions document, from the document's own write records and storage terms (key- and member-aware), in the two sets
that cover the document: gen/M2/evidence.json and gen/M3/evidence.json. It changes no other level, no anchor, no rule
L1-L4, no law, no fact document and no other model. The other levels over 0.3 documents (E1, E3-E6) stay uncomputed.

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i72.py (rules Z1-Z3, independently of holon/) and the fixture
tests_m3/fixtures/e2_transitions/L_probe_e2_challenge_pause.json (a probe law over the Rollup document that ranges
over reachable states, actions and traces and names challengeState and setPause by is_<action> terms; never
registered, run or proved). The probe's law evidence is computed by I66's instrument (tests_m3/_i66.law_atoms), fixed
at I66's prereg.

Z1 Accesses. An access is (family, path), a path a sequence of segments ("map", k) and ("member", name), k a literal
   integer key or "any" for every other key. A write record (a dict with "family", "path" and "value", at any depth
   of an action: top-level writes and loop bodies alike) writes its family at its path. A read is found in every
   section of the action, as tests_m3/_i72.py's docstring says in full: a maximal chain of map and member selections
   over a state term of family f (["storage", f], or ["carried", L, s], ["exit", L, s], ["store", s, P, v] over one)
   reads f at the chain's path; a state term of a scalar family that no selection takes reads it whole; a state term
   of f in a threading position of f (the value of post[f], which restates the writes, and the entry and value of a
   loop record's carried, next, at_break and exit entries named ["storage", f]) is no read, its store paths and values
   being read as values, and a ["?", c, a, b] there reads c as a value and threads a and b. A state term of a
   non-scalar family that is no selection's base and in no threading position is a construct Z1 does not map. A raw
   ["sload", n] or ["sstore", n, v] at a literal slot n that no family declares (no scalar's slot, no fixed array's
   slots, no mapping's base slot: the Rollup's two reads of the EIP-1967 admin slot) accesses no family; one at a
   slot a family declares, or at a slot that is not a literal, is a construct Z1 does not map.
Z2 Overlap. Two paths overlap unless some position of the shorter one separates them: two members of different
   names, or two literal map keys that differ. A symbolic key overlaps every key; a shorter path covers what lies
   below it.
Z3 Atoms. For actions p and q (p == q included, as I14's E2 pairs every endpoint with every endpoint) and a family f
   that p writes and q reads, an E2 atom when some write path of p on f overlaps some read path of q on f:
   {"id": "<model>:E2:TRANS.<p>:TRANS.<q>:<the first 8 hex digits of the canonical sha256 of via>", "model", "level":
   "E2", "p": "TRANS.<p>", "q": "TRANS.<q>", "via": {"carrier": f, "writes": the rendered write paths that overlap a
   read, "reads": the rendered read paths that overlap a write}, "src": null}, writes and reads sorted, rendered "*"
   for the whole family, "[*]" for a symbolic key, "[<k>]" for a literal one and ".<name>" for a member, concatenated
   (I14's _atom id scheme and its E2 via keys). The carrier is the family's name as the model's anchors name it; a
   family two declarations share is never accessed in the adopted documents, and accessing one is a construct Z1
   does not map.
Z4 Where. A module of its own, holon/diagram/transitions.py, holds the walker: transitions_atoms(model, doc) -> list
   of Z3's atoms of one adopted transitions document, sorted by id, raising holon.diagram.evidence.EvidenceError on a
   construct Z1 does not map. holon.diagram.evidence imports it (so it stays in every closure evidence.py is in) and
   re-exports transitions_atoms; evidence.py's docstring states the rule without naming an action or a family of any
   target (I14's test_the_pass_holds_no_target_name and test_the_pass_quotes_no_target_name keep holding). The
   evidence schema spec/schemas/evidence.schema.json admits the adopted model's key in an atom: its atom "model"
   pattern and the model group of its atom "id" pattern admit a dot after the first character
   (^[A-Za-z0-9_][A-Za-z0-9_.]*$; I20 keys an adopted model by its file name without ".json", morph_rollup.extracted),
   with their descriptions saying so, and no other change. build gives each adopted transitions
   document's model those atoms when it covers adopted documents (adopted on, a milestone given) for a target
   milestone (M<k>) from the committed diagrams (diagrams None): `holon evidence --milestone M2` and `--milestone M3`,
   and GEVID's regeneration. Any other build (a test milestone T24, T25, ...; diagrams passed in; no milestone;
   adopted off) gives an adopted model no atom, as before, so the in-memory and toy sets I66's key pins (I24's
   evidence_of, PAR's given inputs, codecrun's test set, par_lossy's --codec start, an M2 build given its diagrams)
   render as they did. An adopted model's anchors (transitions_anchors), its other levels (none) and its unresolved
   entries (none: the document's terms have no imprecise fallback) do not change, nor does any other model, any
   input or the sets' headers. A construct Z1 does not map makes `holon evidence` exit 1 and write nothing. The module
   docstring's "Adopted transitions documents" paragraph states the E2 rule and that E1 and E3-E6 stay uncomputed
   there.
Z5 Laws. law_evidence (L1-L4) does not change. A law over an adopted document that names an edge gets the atoms
   L1-L4 select among the model's E2 atoms; the probe, named [TRANS.challengeState, TRANS.setPause] with all 33 TRANS
   edges as context, gets levels [E2]. No committed law over an adopted document names an edge at the prereg (2 laws
   of laws/M2, 51 of laws/M3), so no committed law's computed evidence, no record's evidence fields and no GEVID row
   moves.
Z6 Regenerated, never hand-written, by this recipe (the schema change of Z4 is a build commit of its own, with the
   code):
   - holon evidence --milestone M2 and --milestone M3: gen/M2/evidence.json and gen/M3/evidence.json;
   - holon derive --milestone M2: laws/M2/REGISTRY.json, in evidence_sha256 alone (laws/M2/DERIVATION.json reads none
     of I72's outputs and stays byte-identical);
   - holon derive --milestone M3: laws/M3/REGISTRY.json and DERIVATION.json, in evidence_sha256, derivation_sha256 and
     DERIVATION's input entry for gen/M3/evidence.json alone (no law file, statement hash or binding changes);
   - holon lossy --milestone M3: gen/M3/par_lossy/header_length.json, its evidence input entry alone, in a commit
     that touches nothing under laws/, gen/M0, gen/M1, gen/M2, results/M0-M2 or replay/ and not gen/M3/evidence.json
     (I25's test_i25_outcome_commits_touch_no_frozen_or_earlier_output);
   - holon metrics --milestone M3: results/M3/metrics.json, in evidenced_pair_coverage's evidence_sha256 alone, and
     metrics_timing.json (timings only);
   - holon run --milestone M1 and --milestone M2, then I40's filter stage (holon refute --milestone M3 --only filter),
     in one commit: every M1 and M2 record in generator_sha256 and keys named seconds alone, since holon/diagram/
     evidence.py is in the holon-ir/0.2 and 0.3 generator closures (results/M3/refute/ and every M3 record stay
     byte-identical); and holon profile --milestone T32: T32's five records likewise (I32's closure holds the file).
   No M0 file changes. I72 re-makes no M3 record: every M3 record's generator_sha256 trails I72's closures until the
   next M3 re-make, as after I66 (the full M3 gate's G1 fails on that staleness; CI's M3 jobs run no G1). I72's build
   is regenerated on the lead after I28's build lands, which writes gen/M3/evidence.json and this schema itself on a
   branch parallel to this prereg; so gen/M3/evidence.json is not one of the key's outcome_paths (audit rule 4 would
   count I28's commits against I72), and the M3 set is held to Z3 and Z4 by I72-P1 and R3 instead. A later branch that
   writes gen/M2/evidence.json (an outcome path) is created from, or merges, a lead that holds this prereg.
Z7 Earlier tests, amended in this prereg's pull request and logged, each narrowed to I72's outcomes:
   - I66, tests_m3/test_view_evidence.py (spec/M3/amendments.jsonl, in the prereg commit):
     TestBuild.test_the_set_gains_the_view_model_alone compares the atoms of every model but the view and the adopted
     transitions documents' models with the prereg's, and an adopted model's atoms with the prereg's but for its E2
     atoms, which I72 adds (checked exactly by I72-P1); TestConstruction.test_window_views_are_found_by_their_declaration
     compares the light copy's `holon evidence --milestone M2` set with I66's prereg set as JSON with the adopted
     transitions documents' models' E2 atoms and the evidence_sha256 left out on both sides, where it compared bytes;
   - I14, tests_m2/test_evidence.py (spec/M2/amendments.jsonl; a later commit of the pull request, since an M3 prereg
     commit may not touch tests_m2/): TestEvidenceFile.test_cli_writes_the_document_with_its_header admits E2 atoms
     on an adopted model (and no other level); test_atom_ids_endpoints_and_order matches an adopted model's atom ids
     with a local pattern whose model group admits a dot (tests_m2/_evidence.py's ID_RE is unchanged and still checks
     every other atom), and takes an adopted model's endpoints from its anchors' trans edges, since it has no diagram;
     TestSoundness.test_e2_atoms_use_terms_of_the_diagram
     checks the atoms of the models with a diagram, an adopted model's E2 atoms being checked against its document by
     I72-P1.
   At the prereg there is no adopted atom, so each amended test checks what it checked before. No other earlier test
   is amended: one that fails on I72's outcomes is a miss, reported.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import re
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KEY = "I72"
DOC = "spec/M2/facts/morph_rollup.extracted.json"
MODEL = "morph_rollup.extracted"
SETS = {"M2": "gen/M2/evidence.json", "M3": "gen/M3/evidence.json"}
PROBE = "tests_m3/fixtures/e2_transitions/L_probe_e2_challenge_pause.json"
INSTRUMENT = "tests_m3/_i72.py"
SCHEMA = "spec/schemas/evidence.schema.json"
MODEL_PATTERN = "^[A-Za-z0-9_][A-Za-z0-9_.]*$"
ID_PATTERN = "^[A-Za-z0-9_][A-Za-z0-9_.]*:E[1-6]:[^:]+:[^:]+:[0-9a-f]{8}$"


def load_json(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    return p.stdout


def key() -> dict:
    return load_json(ROOT / "spec" / "M3" / "predictions.json")["iterations"][KEY]


def item(kid: str) -> dict:
    k = key()
    for x in k["predictions"] + k["regressions"]:
        if x["id"] == kid:
            return x
    raise AssertionError(f"{kid} is not in the key")


def instrument():
    import tests_m3._i72 as I
    return I


def holon_module(name: str):
    return importlib.import_module(name)


def prereg_commit() -> str:
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and KEY in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I72")


def _is_ancestor(a: str, b: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", a, b], cwd=ROOT).returncode == 0


def _merge() -> str | None:
    """M: the oldest merge on R..HEAD's ancestry path (R the oldest commit adding docs/iterations/I72.md) whose second
    parent reaches R and whose first parent does not; None on I72's own branch before its merge."""
    added = git("log", "--full-history", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--",
                "docs/iterations/I72.md").split()
    if not added:
        return None
    r = added[0]
    for line in git("rev-list", "--ancestry-path", "--merges", "--reverse", "--parents", f"{r}..HEAD").splitlines():
        c, *parents = line.split()
        if len(parents) > 1 and _is_ancestor(r, parents[1]) and not _is_ancestor(r, parents[0]):
            return c
    return None


def end_commit() -> str:
    """The commit I72's own work ends at: M^2 once merged, else HEAD."""
    m = _merge()
    return git("rev-parse", f"{m}^2" if m else "HEAD").strip()


def own_commits() -> dict[str, list[str]]:
    """I72's own non-merge commits after its prereg, each with the paths it changes: along the first-parent line of
    M^2 back to the lead when I72 is merged, else prereg..HEAD. Another key's commits merged into I72's branch are
    never I72's."""
    pre, m = prereg_commit(), _merge()
    if m is not None:
        first, second = git("rev-parse", f"{m}^1", f"{m}^2").split()
        revs = [second, f"^{first}", f"^{pre}"]
    else:
        revs = [f"{pre}..HEAD"]
    out = {}
    for c in git("log", "--first-parent", "--no-merges", "--format=%H", *revs).split():
        out[c] = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", c).split()
    return out


def ls(commit: str, directory: str) -> list[str]:
    """The law or record files (L*.json) directly under directory at commit."""
    names = git("ls-tree", "--name-only", f"{commit}:{directory}").split()
    return sorted(f"{directory}/{n}" for n in names if n.startswith("L") and n.endswith(".json"))


def at(commit: str, rel: str):
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except AssertionError:
        return None


def at_text(commit: str, rel: str) -> str:
    """The text of rel at commit, "" when the commit holds no such file."""
    try:
        return git("show", f"{commit}:{rel}")
    except AssertionError:
        return ""


def target_names() -> set[str]:
    """The families and actions of every adopted transitions document of M2 and M3, and the probe's id."""
    I = instrument()
    out = {"L_probe_e2_challenge_pause"}
    for gm in SETS:
        for _rel, d in I.adopted(gm, ROOT):
            out |= {a["name"] for a in d.get("actions") or [] if isinstance(a, dict) and isinstance(a.get("name"), str)}
            out |= set(I.families(d)[0])
    return out


def adopted_models(doc: dict) -> set[str]:
    return {m for m, mo in doc["models"].items() if mo.get("facts_version") == "holon-facts/0.3"
            and mo.get("diagram") is None}


def built(doc: dict) -> bool:
    return any(a["model"] in adopted_models(doc) for a in doc["atoms"])


def need_built(test) -> None:
    for gm, rel in SETS.items():
        if not built(load_json(ROOT / rel)):
            test.fail(f"{rel} holds no atom of an adopted transitions document (no build)")


def _unseconded(x):
    if isinstance(x, dict):
        return {k: _unseconded(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_unseconded(v) for v in x]
    return x


def _unstamped(rec: dict) -> dict:
    return {k: v for k, v in _unseconded(rec).items() if k != "generator_sha256"}


# ------------------------------------------------------------------------------------------------ prereg
class TestPrereg(unittest.TestCase):
    """Construction checks, not counted: the key pins its instruments; the instrument maps the document."""

    def test_the_key_pins_the_instruments(self):
        th = key()["thresholds"]
        self.assertEqual(file_sha256(ROOT / INSTRUMENT), th["instrument_sha256"])
        self.assertEqual(file_sha256(ROOT / PROBE), th["fixture_sha256"][PROBE])
        doc = sys.modules[__name__].__doc__
        self.assertEqual(hashlib.sha256(doc.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])

    def test_r4_the_instrument_on_the_documents(self):
        """I72-R4 (construction): the instrument maps every adopted transitions document of M2 and M3 (the Rollup
        document alone) with no unmapped construct; the model's atoms are thresholds.atoms in number; every atom's p is
        a writer and q a reader of its carrier in the committed anchors (I20's rule, unchanged), and its writes and
        reads are non-empty and sorted."""
        I = instrument()
        th = key()["thresholds"]
        for gm, rel in SETS.items():
            with self.subTest(milestone=gm):
                docs = I.adopted(gm, ROOT)
                self.assertEqual([r for r, _ in docs], [DOC])
                atoms = I.e2_atoms(MODEL, docs[0][1])
                self.assertEqual(len(atoms), th["atoms"]["total"])
                self.assertEqual(sum(1 for a in atoms if a["p"] == a["q"]), th["atoms"]["self"])
                an = load_json(ROOT / rel)["models"][MODEL]["anchors"]
                for a in atoms:
                    c = an["carriers"][a["via"]["carrier"]]
                    self.assertIn(a["p"], c["writers"], a["id"])
                    self.assertIn(a["q"], c["readers"], a["id"])
                    for k in ("writes", "reads"):
                        self.assertTrue(a["via"][k])
                        self.assertEqual(a["via"][k], sorted(a["via"][k]))

    def test_r4_the_probe_at_the_prereg(self):
        """I72-R4 (construction): the probe is a valid holon-ir/0.3 law over the Rollup document with its sha256; over
        the prereg's sets it is covered, names TRANS.challengeState and TRANS.setPause, has all 33 TRANS edges as
        context, and has levels [] (no adopted atom yet)."""
        import tests_m3._i66 as I66
        from tests_m3._m3 import validate
        law = load_json(ROOT / PROBE)
        self.assertEqual(validate(law, ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"), [])
        self.assertEqual((law["facts"], law["facts_sha256"]), (DOC, file_sha256(ROOT / DOC)))
        pre = prereg_commit()
        for gm, rel in SETS.items():
            with self.subTest(milestone=gm):
                old = at(pre, rel)
                le = I66.law_atoms(law, old)
                self.assertTrue(le["covered"])
                self.assertEqual(le["named"], ["TRANS.challengeState", "TRANS.setPause"])
                self.assertEqual(len(le["context"]), 33)
                self.assertEqual(le["levels"], [])


# ------------------------------------------------------------------------------------------------ predictions
class TestPredictions(unittest.TestCase):
    def test_p1_the_e2_inventory(self):
        """I72-P1: in gen/M2/evidence.json and gen/M3/evidence.json, the Rollup document's model holds exactly the
        instrument's E2 atoms (ids, p, q, via and src as rule Z3 gives them): thresholds.atoms.total atoms, of which
        thresholds.atoms.self relate an action to itself, over thresholds.atoms.carriers families, with the pinned
        examples; it holds no atom of another level and no unresolved entry. Recorded, not counted: R3's function
        equality and R4's counts entail it (thresholds.counted_predictions is empty; the prereg review's M1)."""
        item("I72-P1")
        need_built(self)
        I = instrument()
        th = key()["thresholds"]
        for gm, rel in SETS.items():
            with self.subTest(milestone=gm):
                doc = load_json(ROOT / rel)
                mine = [a for a in doc["atoms"] if a["model"] == MODEL]
                want = I.e2_atoms(MODEL, load_json(ROOT / DOC))
                self.assertEqual(mine, want)
                self.assertEqual(len(mine), th["atoms"]["total"])
                self.assertEqual(sum(1 for a in mine if a["p"] == a["q"]), th["atoms"]["self"])
                self.assertEqual(len({a["via"]["carrier"] for a in mine}), th["atoms"]["carriers"])
                self.assertEqual([u for u in doc["unresolved"] if u["model"] == MODEL], [])
                got = {I.strip(a) for a in mine}
                for ex in th["atoms"]["examples"]:
                    self.assertIn((ex["p"], ex["q"], ex["carrier"], tuple(ex["writes"]), tuple(ex["reads"])), got)


# ------------------------------------------------------------------------------------------------ regressions
class TestRegressions(unittest.TestCase):
    def test_r5_the_probe_and_the_hand_abstraction(self):
        """I72-R5 (construction and a recorded observation, not counted): over each committed set the probe is
        covered, names TRANS.challengeState and TRANS.setPause, and has levels [E2] with max E2; its relevant atoms
        (L1-L4, by I66's instrument and by holon's law_evidence alike) are exactly the instrument's atoms with an endpoint
        at either action, thresholds.probe.relevant_atoms of them. Observed before the prereg, against the hand
        abstraction's model morph_rollup in gen/M2/evidence.json: every pair (TRANS.a, TRANS.b) of its E2 atoms whose
        two actions the Rollup document also has (thresholds.hand.common_actions) is the pair of an atom of the
        document's model (thresholds.hand.pairs of them), and the document's model relates exactly
        thresholds.hand.extracted_only among those actions besides."""
        item("I72-R5")
        need_built(self)
        import tests_m3._i66 as I66
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        th = key()["thresholds"]
        law = load_json(ROOT / PROBE)
        named = {"TRANS.challengeState", "TRANS.setPause"}
        for gm, rel in SETS.items():
            with self.subTest(milestone=gm):
                doc = load_json(ROOT / rel)
                ref, le = I66.law_atoms(law, doc), E.law_evidence(law, doc)
                for x in (ref, le):
                    self.assertTrue(x["covered"])
                    self.assertEqual(x["named"], sorted(named))
                    self.assertEqual(x["levels"], ["E2"])
                self.assertEqual(le["max"], "E2")
                self.assertEqual(le["atoms"], ref["atoms"])
                want = sorted(a["id"] for a in I.e2_atoms(MODEL, load_json(ROOT / DOC)) if {a["p"], a["q"]} & named)
                self.assertEqual(le["atoms"], want)
                self.assertEqual(len(want), th["probe"]["relevant_atoms"])
        doc = load_json(ROOT / SETS["M2"])
        common = set(th["hand"]["common_actions"])
        acts = {a["name"] for a in load_json(ROOT / DOC)["actions"]}
        hand_acts = {e[len("TRANS."):] for e in doc["models"][th["hand"]["model"]]["anchors"]["trans"]}
        self.assertEqual(sorted(acts & hand_acts), sorted(common))
        on = lambda a: a["p"].startswith("TRANS.") and a["q"].startswith("TRANS.") and a["p"][6:] in common \
            and a["q"][6:] in common
        hand = {(a["p"], a["q"]) for a in doc["atoms"] if a["model"] == th["hand"]["model"] and a["level"] == "E2"
                and on(a)}
        mine = {(a["p"], a["q"]) for a in doc["atoms"] if a["model"] == MODEL and on(a)}
        self.assertEqual(len(hand), th["hand"]["pairs"])
        self.assertEqual(sorted(hand - mine), [])
        self.assertEqual(sorted([p, q] for p, q in mine - hand), th["hand"]["extracted_only"])

    def test_r1_no_laws_evidence_moves(self):
        """I72-R1: for every law of laws/M0-M3 at the prereg, holon's law_evidence over the set at I72's end commit
        (end_commit) equals law_evidence over the prereg's set (levels, max, named, atoms), and no such law over an
        adopted document names an edge (the records I72's own commits change keep their evidence fields: R2's stamp-only
        check); on the tree under test GEVID (holon.diagram.evidence.gevid) passes on M0, M1, M2 and M3 with no problem
        and no uncovered law, and the prereg's laws' mismatches are the prereg's (thresholds.gevid_mismatches_at_prereg:
        M0's and M1's two each, report-only); each milestone's registry records its set's evidence_sha256."""
        item("I72-R1")
        need_built(self)
        E = holon_module("holon.diagram.evidence")
        pre, end = prereg_commit(), end_commit()
        prereg_laws = set()
        for M in ("M0", "M1", "M2", "M3"):
            gm = E.gen_milestone(M)
            new, old = at(end, f"gen/{gm}/evidence.json"), at(pre, f"gen/{gm}/evidence.json")
            for rel in ls(pre, f"laws/{M}"):
                law = at(pre, rel)
                if not isinstance(law, dict) or "statement" not in law:
                    continue
                prereg_laws.add(law.get("law_id"))
                with self.subTest(law=law.get("law_id")):
                    a, b = E.law_evidence(law, new), E.law_evidence(law, old)
                    self.assertEqual({k: a[k] for k in ("levels", "max", "named", "atoms")},
                                     {k: b[k] for k in ("levels", "max", "named", "atoms")})
                    if a["model"] in adopted_models(new):
                        self.assertEqual(a["named"], [])
        known = key()["thresholds"]["gevid_mismatches_at_prereg"]
        for M in ("M0", "M1", "M2", "M3"):
            with self.subTest(gevid=M):
                g = E.gevid(M, ROOT)
                self.assertTrue(g["passed"], g["detail"])
                self.assertEqual((g["problems"], g["uncovered"]), ([], []), M)
                self.assertEqual([x for x in g["mismatches"] if x["law"] in prereg_laws], known.get(M, []), M)
        for M in ("M2", "M3"):
            self.assertEqual(load_json(ROOT / f"laws/{M}/REGISTRY.json")["evidence_sha256"],
                             load_json(ROOT / SETS[M])["evidence_sha256"])

    def test_r2_own_commits_change_only_what_z6_allows(self):
        """I72-R2, judged commit by commit against each own commit's first parent (own_commits): I72's own commits
        change, outside holon/, docs/ (but the frozen docs/M0_SPEC.md and docs/BEND_PRIMER.md), tests_m2/test_evidence.py
        and the amendment files, only gen/M2/evidence.json, gen/M3/evidence.json, spec/schemas/evidence.schema.json (its
        atom "model" pattern and the model group of its atom "id" pattern, admitting a dot after the first character, and
        their descriptions, alone: rule Z4), laws/M2/REGISTRY.json (evidence_sha256 alone), laws/M3/REGISTRY.json and
        DERIVATION.json (evidence_sha256, derivation_sha256 and DERIVATION's gen/M3/evidence.json input entry alone),
        gen/M3/par_lossy/header_length.json (its gen/M3/evidence.json input entry alone, in a commit that changes nothing
        under laws/, gen/M0, gen/M1, gen/M2, results/M0-M2 or replay/ and not gen/M3/evidence.json), results/M3/metrics.json
        (evidenced_pair_coverage's evidence_sha256 alone), results/M3/metrics_timing.json, and the records directly under
        results/M1, results/M2 and results/T32, each such record keeping its status and differing from its parent's
        version only in generator_sha256 and keys named seconds. None adds or deletes a law or a record, and none changes
        a frozen root, a fact document, spec/ but the schema and the amendment files, replay/, audit/, laws/M0, laws/M1,
        laws/T32, a law file, results/M0, results/M3 but the two metrics files, results/T32/summary.json, gen/M0, gen/M1,
        gen/T32, or a gen/M2 or gen/M3 file but those named. The holon/ files they change name no family and no action of
        an adopted transitions document, and not the probe's id."""
        item("I72-R2")
        own = own_commits()
        self.assertTrue(own, "no commit of I72's after its prereg")
        fixed = {"gen/M2/evidence.json", "gen/M3/evidence.json", "laws/M2/REGISTRY.json", "laws/M3/REGISTRY.json",
                 "laws/M3/DERIVATION.json", "gen/M3/par_lossy/header_length.json", "results/M3/metrics.json",
                 "results/M3/metrics_timing.json", "spec/M2/amendments.jsonl", "spec/M3/amendments.jsonl",
                 "tests_m2/test_evidence.py", SCHEMA}
        frozen_docs = ("docs/M0_SPEC.md", "docs/BEND_PRIMER.md")
        record = re.compile(r"^results/(M1|M2|T32)/L[^/]*\.json$")
        names = target_names()
        for c, paths in sorted(own.items()):
            parent = git("rev-parse", f"{c}^1").strip()
            with self.subTest(commit=c[:12]):
                bad = [f for f in paths if f in frozen_docs
                       or not (f.startswith(("holon/", "docs/")) or f in fixed or record.match(f))]
                self.assertEqual(bad, [])
                if "gen/M3/par_lossy/header_length.json" in paths:
                    self.assertEqual([f for f in paths if f.startswith(("laws/", "gen/M0/", "gen/M1/", "gen/M2/", "replay/",
                                                                       "results/M0/", "results/M1/", "results/M2/"))
                                      or f == "gen/M3/evidence.json"], [], "holon lossy's output in a commit of its own")
                for f in paths:
                    if f.startswith("holon/") and f.endswith(".py"):
                        text = git("show", f"{c}:{f}") if at_text(c, f) else ""
                        found = sorted(n for n in names if re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])",
                                                                     text) and not re.search(
                            rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", at_text(parent, f)))
                        self.assertEqual(found, [], f)
                    if f == SCHEMA:
                        o, n = at(parent, f), at(c, f)
                        self.assertEqual(n["$defs"]["atom"]["properties"]["model"]["pattern"], MODEL_PATTERN)
                        self.assertEqual(n["$defs"]["atom"]["properties"]["id"]["pattern"], ID_PATTERN)
                        def strip(d):
                            d = json.loads(json.dumps(d))
                            for k in ("model", "id"):
                                d["$defs"]["atom"]["properties"][k] = {"type": "string"}
                            return d
                        self.assertEqual(strip(n), strip(o), f)
                for f in paths:
                    o = at(parent, f) if f.endswith(".json") else None
                    if record.match(f):
                        n = at(c, f)
                        self.assertIsNotNone(o, f"{f} added")
                        self.assertIsNotNone(n, f"{f} deleted")
                        self.assertEqual(_unstamped(n), _unstamped(o), f)
                    elif f == "laws/M2/REGISTRY.json":
                        n = at(c, f)
                        self.assertEqual({k: v for k, v in n.items() if k != "evidence_sha256"},
                                         {k: v for k, v in o.items() if k != "evidence_sha256"})
                    elif f in ("laws/M3/REGISTRY.json", "laws/M3/DERIVATION.json"):
                        n = at(c, f)
                        strip = lambda d: {k: ([i for i in v if i.get("path") != "gen/M3/evidence.json"]
                                               if k == "inputs" else v) for k, v in d.items()
                                           if k not in ("evidence_sha256", "derivation_sha256")}
                        self.assertEqual(strip(n), strip(o), f)
                    elif f == "gen/M3/par_lossy/header_length.json":
                        n = at(c, f)
                        strip = lambda d: {**d, "inputs": [i for i in d["inputs"] if i["path"] != "gen/M3/evidence.json"]}
                        self.assertEqual(strip(n), strip(o), f)
                    elif f == "results/M3/metrics.json":
                        n = at(c, f)
                        def strip(d):
                            d = json.loads(json.dumps(d))
                            d.get("evidenced_pair_coverage", {}).get("evidence", {}).pop("evidence_sha256", None)
                            return d
                        self.assertEqual(strip(n), strip(o), f)

    def test_r3_the_rule_where_and_not_elsewhere(self):
        """I72-R3 (rule Z4): holon.diagram.evidence.transitions_atoms equals the instrument on the Rollup document; a
        planted copy with a whole mapping family read as a value, one accessing a family two declarations share (a
        second scalar declaration of inChallenge), and one with a raw sload at a family's slot raise EvidenceError; the build for a test milestone (T24), with diagrams passed in, or with adopted off gives
        the Rollup model no atom; `holon evidence --milestone M2` and `--milestone M3` reproduce the committed sets byte
        for byte."""
        item("I72-R3")
        need_built(self)
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        D = holon_module("holon.diagram")
        d = load_json(ROOT / DOC)
        self.assertEqual(E.transitions_atoms(MODEL, d), I.e2_atoms(MODEL, d))
        bad = json.loads(json.dumps(d))
        act = next(a for a in bad["actions"] if a["name"] == "challengeState")
        act["guards"] = list(act["guards"]) + [{**act["guards"][0], "expr": ["==", ["storage", "challenges"], 0]}]
        with self.assertRaises(E.EvidenceError):
            E.transitions_atoms(MODEL, bad)
        dup = json.loads(json.dumps(d))
        owner = next(x for x in dup["inherited_storage"] if x["name"] == "_owner")
        dup["inherited_storage"].append({**owner, "name": "inChallenge", "declared_in": "Planted"})
        with self.assertRaises(E.EvidenceError):
            E.transitions_atoms(MODEL, dup)
        raw = json.loads(json.dumps(d))
        act = next(a for a in raw["actions"] if a["name"] == "challengeState")
        slot = next(x["slot"] for x in raw["storage"] if x["name"] == "inChallenge")
        act["guards"] = list(act["guards"]) + [{**act["guards"][0], "expr": ["==", ["sload", slot], 0]}]
        with self.assertRaises(E.EvidenceError):
            E.transitions_atoms(MODEL, raw)
        for doc in (E.build([], ROOT, milestone="T24"),
                    E.build(D.fact_documents("M2", ROOT), ROOT, milestone="M2", adopted=False),
                    E.build(D.fact_documents("M2", ROOT), ROOT, milestone="M2",
                            diagrams={p.stem: load_json(ROOT / "gen" / "M2" / "diagram" / f"{p.stem}.json")
                                      for p in D.fact_documents("M2", ROOT)})):
            self.assertEqual([a["id"] for a in doc["atoms"] if a["model"] == MODEL], [])
        for M, rel in SETS.items():
            with self.subTest(milestone=M):
                self.assertEqual(E.render(E.build_milestone(M, ROOT)), (ROOT / rel).read_text(encoding="utf-8"))

    def test_r3_every_other_model_and_the_header_as_at_the_parent(self):
        """I72-R3 (rule Z4), judged at each own commit that changes an evidence set, against its first parent (another
        key's models, merged into I72's branch, are never I72's): the set holds the parent's models with the parent's
        facts, sha256, versions, diagrams and anchors; every atom and unresolved entry of every other model is the
        parent's, and the adopted transitions documents' models gain E2 atoms alone; the header fields and inputs are the
        parent's; evidence_sha256 is the body's hash. At least one own commit changes each of the two sets."""
        item("I72-R3")
        need_built(self)
        E = holon_module("holon.diagram.evidence")
        own = own_commits()
        for M, rel in SETS.items():
            changes = [(git("rev-parse", f"{c}^1").strip(), c) for c, paths in sorted(own.items()) if rel in paths]
            self.assertTrue(changes, f"no own commit changes {rel}")
            for parent, c in changes:
                with self.subTest(milestone=M, commit=c[:12]):
                    new, old = at(c, rel), at(parent, rel)
                    self.assertEqual(new["models"], old["models"])
                    adopted = adopted_models(old)
                    self.assertEqual([a for a in new["atoms"] if a["model"] not in adopted],
                                     [a for a in old["atoms"] if a["model"] not in adopted])
                    self.assertEqual([a for a in old["atoms"] if a["model"] in adopted
                                      and a not in new["atoms"]], [])
                    self.assertEqual({a["level"] for a in new["atoms"] if a["model"] in adopted
                                      and a not in old["atoms"]} - {"E2"}, set())
                    self.assertEqual(new["unresolved"], old["unresolved"])
                    for k in ("document", "evidence_version", "milestone", "levels", "sorts_sha256", "inputs"):
                        self.assertEqual(new[k], old[k], k)
                    self.assertEqual(new["evidence_sha256"], E.body_sha256(new))


if __name__ == "__main__":
    unittest.main()
