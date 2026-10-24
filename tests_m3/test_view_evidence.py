"""I66: holon differential's window view in M2's evidence set (Question Q62, the route I65's prereg names:
prompts/I65_o12_view.md and rule O4 of tests_m3/test_o12.py; whitepaper Def 4.5; BUILD_PLAN I11, I14, I20 and row
I66). This docstring is the contract.

Scope. I65 (= I33b) adds a contract-derived M2 law, L_contract_C_o12, over holon.differential's window view
gen/M2/extracted/m1_view.json (the M1 abstraction spec/M1/facts/morph_rollup.json with the requires the extracted code
lacks removed). The law carries its contract's evidence claim E2, which GEVID (I14, enforcing from M2 on, with no
exemption) must check, but M2's evidence set gen/M2/evidence.json models no window view, so the law would be
uncovered. I65's prereg routes the fix to this separate key (Q62; no human answer is recorded for it), and I65's build
merges after it. I66 models the view in the set, as I20 covered the adopted transitions documents: a diagram built by
I11's adapters and atoms computed by I14's calculus, both as they stand. It changes no rule of the calculus (E1-E6,
L1-L4), no law, no fact document, no sorts assignment and no other model of the set. Reading I65's ghost term in rule
L2 is I65's build's (the term is not on this base).

Instruments fixed at the prereg (do not edit; a wrong instrument is a Question and an amendment line in
spec/M3/amendments.jsonl): tests_m3/_i66.py (V1, V2, V3's anchor rule, I14's anchors rule and rules L1-L4, and the
projections the checks compare, independently of holon/) and the fixture
tests_m3/fixtures/view_evidence/L_probe_view_challenge.json (a probe law over the view that ranges over traces and
names challengeState by an act term; never registered, run or proved).

V1 The view. gen/M2/extracted/m1_view.json is holon.differential's window view for the declaration
   spec/M2/lib/window_rollup.json: the abstraction without the guards its extraction block lists under "removed"
   (commitBatch [21], commitBatchWithProof [25, 30], commitState [11, 20], finalizeBatch [14], proveState [9], setPause
   [1, 2]; requires only), with that block as its own extraction block; every other section is the abstraction's. I66
   changes neither the view, nor the declaration, nor holon.differential.
V2 Window views. holon.diagram.window_views(milestone, root) -> [Path] (paths under root, sorted): every
   holon-facts/0.2 document directly under gen/<M>/extracted/ (holon.differential's output directory) whose window
   declaration (V3's window_declaration) is one of the milestone's, spec/<M>/lib/window_*.json. For M2 that is
   gen/M2/extracted/m1_view.json alone, for M3 nothing; a declaration whose view is absent gives nothing. A window view
   is never a fact document: holon.diagram.fact_documents, holon sorts, holon derive's inputs and I13's frozen
   assignment gen/M2/sorts/assignment.json do not change.
V3 Its libraries: the library half of I65's view anchor, as I65's build writes it (rule O4 of tests_m3/test_o12.py;
   holon/gen/targetlib.py at commit 85d91d70 of claude/brave-wright-2c5d0o-i65-build). holon.gen.targetlib gains
   WINDOW_VERSION, _repo_path, _named_declaration, window_declaration(facts_path, root) and anchor(facts_path, root),
   and lib_files reads <the anchor's dir>/../lib, their code verbatim as there (a docstring that mentions search hints
   says libraries only until I65 anchors hints_for), so that I65's rebase onto I66 is trivial: a .json document whose
   extraction block names, by a repository path, a declaration under root with window_version holon-window/0.1 and an
   existing "abstraction" is anchored to that abstraction (the view: spec/lib/ and spec/M1/lib/), every other document
   to itself, so lib_files changes for no document that names no declaration (no committed law's facts does).
   hints_for, holon.audit.regress.lib_docs_at, the ledger bundles (holon.records) and the generator closures'
   spec/*/lib/window_*.json entry stay as they are: they are I65's (85d91d70, e57fa11d), and none matters at I66 (no
   committed law names the view, and holon.differential's runs already take the abstraction as their anchor,
   holon.mpipeline.run_m1).
V4 Its diagram. `holon diagram --milestone M2` writes, besides one diagram per fact document, <out>/<stem>.json
   (default out gen/M2/diagram) for each window view of M2, stem the view file's (m1_view), built by
   holon.diagram.build with I11's adapters as they are (zero unmapped constructs); a window view whose stem is a fact
   document's is a DiagramError, exit 1, with nothing written. The diagram's inputs list the window declaration beside
   the libraries and the ledger it reads. G1 regenerates and compares it with the other diagrams
   (holon.gate.regenerate_m2_outputs, unchanged).
V5 Its evidence model. holon.diagram.evidence.build models window views only when it reads the committed diagrams
   (diagrams None) for a target milestone (milestone M<k>): it then adds one model per window view of gen_milestone(M)
   (window_views(gm, root): M2's view for M0-M2, nothing for M3), keyed by the view's stem, with facts its repo path,
   facts_sha256 its sha256, facts_version holon-facts/0.2, diagram gen/<gm>/diagram/<stem>.json (the committed file,
   never one passed in) and the anchors I14's rule gives that diagram (no site of the frozen assignment names the
   view). A build given its own diagrams, a build for a test milestone (T24, T25, ...: gen_milestone maps them to M2)
   and a build for no milestone add no view, whatever their adopted switch, so holon.rules._given_par_inputs,
   holon.codecrun.test_evidence_set, holon.rules.par_lossy.components with --codec and tests_m3/_i24.evidence_of build
   what they built before, byte for byte. The view's atoms and unresolved entries are I14's for a facts-0.2 document,
   over its diagram, the view and its libraries (V3), with one stated case: E5 reads the frozen assignment's model of
   the view's stem when there is one, and otherwise gives no operand a sort, so no E5 atom (where a fact document
   without a model is an EvidenceError, as before). E1 is a facts-0.1 level, so the view has E2, E3, E4 and E6 atoms
   and unresolved E2 entries. The calculus reads the view's diagram as it reads any diagram: never its ledger links or
   coverage debt. The inputs gain, per view, the view, its diagram and its window declaration, each with its sha256;
   files read only to find the views (the documents under gen/<gm>/extracted/ and the milestone's declarations) are
   not inputs. A view whose stem is another model's is an EvidenceError: `holon evidence` exits 1 and writes nothing.
   `holon evidence --milestone M2` still writes render(build(holon.diagram.fact_documents("M2"), root,
   milestone="M2")). Two consequences, for the human (prompt, Questions): over the view, a law whose only atoms
   stronger than E6 would be E5 atoms has max E6, so a REFUTED one is triaged intent_question where over the
   abstraction it is a finding; and the abstraction's sorts assignment is not simply the view's, since I13's
   constraints come partly from the removed requires.
V6 Laws. law_evidence (L1-L4) does not change. A law whose facts is a view's path, with that view's facts_sha256 or
   none, is covered by the view's model (L1). No committed law names the view's path, so no law's computed evidence, no
   record's evidence fields and no GEVID row changes; the M1 laws' records over the view (results/M2/extracted_m1: the
   abstraction's facts path with the view's facts_sha256) stay uncovered, and GEVID reads none of them. I65's derived
   law (facts the view) is covered by the view's model and names nothing until rule L2 reads its ghost term (I65's
   build); then it names TRANS.challengeState, and its relevant atoms are the probe's (I66-R5).
V7 Regenerated, never hand-written, by this recipe:
   - holon diagram --milestone M2: gen/M2/diagram/m1_view.json (the fact documents' diagrams byte-identical);
   - holon evidence --milestone M2: gen/M2/evidence.json;
   - holon derive --milestone M2: laws/M2/REGISTRY.json, its evidence_sha256 alone (laws/M2/DERIVATION.json reads
     none of I66's outputs and stays byte-identical);
   - holon run --milestone M1 and --milestone M2, then I40's filter stage, holon refute --milestone M3 --only filter:
     every M1 and M2 record, in generator_sha256 and seconds alone, since I66's code is in the holon-ir/0.2 and 0.3
     generator closures (the filter stage writes filter_bin and concretization back; results/M3/refute/filter.json and
     every M3 record stay byte-identical). holon lean need not run: holon run rebuilds each record's lean4 kernel entry
     (all 16 M1 records and 8 of the 12 M2 records have one) from the committed Lean reports gen/M1/lean/report.json
     and gen/M2/lean/report.json (holon.lean.kernel_entry_v2), which back it while the Lean text emitted now has the
     report's source_sha256 and the record the report's verdict, statement hash and main theorem. That text reads the
     law, its facts document, the Lean twin libraries (holon.gen.lean_machine.lib_twin, a path rule of its own), the
     oracle parameters and the SORT-site entries, none of which I66 changes, and the Lean emitters import none of
     I66's modules, so every lean4 entry is rebuilt as it is (R2);
   - holon profile --milestone T32 (I32): the five records of results/T32, in generator_sha256 and seconds alone,
     since I66's code is also in I32's generator closure (holon.profile.generator_files: 124 files at the base);
     laws/T32, gen/T32, results/T32/summary.json and gen/M3/disch/classification.json stay byte-identical. Without it
     I32's C1 (tests_m3/test_disch_profile.py::TestRun.test_c1_runs_and_regenerates_byte_identically, which compares a
     fresh run's records with the committed ones up to seconds) would fail on generator_sha256;
   - holon historical exit --milestone M2: results/M2/m2_exit.json and docs/M2_EXIT.md. I23's coverage lists every
     CODEC, CONS and TRANS edge of every diagram under gen/M2/diagram/, so coverage.not_replayed gains the view's 11.
     I23's wording is fixed for a generated view in holon/historical/exit_report.py (in no generator closure), by a
     rule, not by name: the why of a TRANS edge whose action the trans window replayed reads, for a diagram whose
     provenance.extraction names a window declaration, "the window view's <action> (<its facts>, <its extraction
     method>); its extracted counterpart ... was replayed ...", where a hand abstraction's still reads "the hand
     abstraction of <action> (...)"; every other why is unchanged.
   No M0 file, no record of results/M2/extracted_m1, no other gen/M2 or T32 file and no M3 file changes: I66 re-makes
   no M3 record. Its code is also in every M3 generator closure (holon.sorts.run3.GEN3 and, with it, holon.fact.run's
   GEN_FACT, holon.undo.run's GEN_UNDO and holon.disch.run's GEN_DISCH; holon-ir/0.3 for the PAR records), so after
   the build every M3 record's generator_sha256 trails the closures, as at I65's build head and as I43 let typed records
   trail (gap LP-G9), until the next M3 re-make (planned with I28's build, holon-rules/1.6, and the F40 and I67
   re-makes). Until then the full M3 gate's G1 (holon/fact/gate.py rerun_problems, holon/sorts/gate3.py G1) fails on
   that staleness; CI's M3 jobs run no G1 (I66-R3).
V8 Earlier tests, amended in this prereg's pull request and logged in their own key's amendments file, each narrowed to
   I66's outcomes but I32's, which is narrowed to I32's own commits (below):
   - I14, tests_m2/test_evidence.py (spec/M2/amendments.jsonl; a later commit of the pull request, since a prereg
     commit of an M3 key may not touch tests_m2/): TestEvidenceFile.test_cli_writes_the_document_with_its_header and
     test_inputs_are_hashed_and_the_only_vocabulary_is_the_lexical_sidecar admit a window view's model (its facts,
     sha256, facts_version and diagram) and its inputs (the view and its declaration);
     TestSoundness.test_e3_and_e5_atoms_point_at_their_nodes reads an atom's facts through the document's model, so it
     checks the view's atoms too; test_e6_atoms_equal_the_frozen_tokenizer recomputes E6 over the window views'
     diagrams too; TestPredictions.test_the_e3_inventory and test_the_e4_inventory count the fact documents' atoms, so
     the words of I14-P5 ("exactly 9 E3 atoms") and I14-P6 ("exactly 2 E4 atoms") describe the fact documents', not
     the whole set (17 and 4 after I66), and the view's are checked exactly by I66-P2;
   - I43, tests_m3/test_lean_promoted.py (spec/M3/amendments.jsonl, in the prereg commit):
     TestPreregInstruments.test_sidecar_is_the_computation accepts laws/M2/REGISTRY.json when it differs from its
     pinned bytes only in evidence_sha256, that value is the one the committed gen/M2/evidence.json of the tree under
     test holds and is that set's own body hash, and the registry with the value the I66 key records set back hashes to
     the pin (so it accepts the registry following any later rebuild of the set, which no claim of I43 reads);
   - I32, tests_m3/test_disch_profile.py (spec/M3/amendments.jsonl, in the prereg commit):
     TestRegressions.test_r2_no_closure_and_no_earlier_output_changes judges I32's own commits instead of the I32
     prereg against HEAD, which counted every later key's commits as I32's, I66's closure files and M1 records among
     them. It finds them by ancestry, whatever the topology: R the oldest commit that adds docs/iterations/I32.md, M the
     oldest merge on R..HEAD's ancestry path whose second parent reaches R and whose first parent does not (e215fbf5),
     and the non-merge commits of `git log --first-parent M^2 ^M^1 ^<prereg>` (seven). Its closure and earlier-output
     checks run over those commits, and M1's L_disch_delay_* records at M^2 must equal the prereg's but for
     generator_sha256 and keys named seconds. This narrows it beyond I66's outcomes: a later key's commits are judged
     by that key's own regressions (I66-R2 here).
   At the prereg there is no view model, so each amended I14 and I43 test checks what it checked before, and I32's finds
   I32's seven commits and passes, as the original does there. The I43 test already fails at the base (e215fbf5, as at
   fde1f819) on 103 laws/M3 inputs that I26's catalog bump moved (I26's Question 5) and on the baselines of two typed M3
   records; the amendment neither causes nor hides that. No other earlier test is amended: one that fails on I66's
   outcomes is a miss, reported.
V9 Rules. I66 writes no frozen root (AGENTS rule 1), changes no law file (laws/<M>/L*.json), no fact document and no
   M0 or M3 file, adds no law or record, names no id of its own in holon/ (L_probe_view_challenge), and holon/diagram/,
   holon/gen/targetlib.py and holon/historical/exit_report.py name neither the view's nor the declaration's file (they
   find both through the declarations and the documents' extraction blocks). Its outcome paths are narrow:
   gen/M2/diagram/m1_view.json, gen/M2/evidence.json and docs/iterations/I66.md. Its code (V2-V5, V7's wording) and
   the files of V7 are build commits; a commit that changes records carries them with the filter stage re-applied.
   I66's own commits are the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit that
   adds docs/iterations/I66.md (HEAD while none does). The pull request merges with a merge commit, so that its commits
   stay out of I65's own commits (I65-R2, whose registry rule allows that law's entries only); a lead merged into the
   branch is a merge commit too, so its changes are never counted as I66's.

Commands
  python -m holon diagram --milestone M2 [--out DIR] [--root DIR]      V4
  python -m holon evidence --milestone M2 [--out PATH] [--root DIR]    V5
  python -m holon derive --milestone M2                                V7 (the registry's evidence_sha256)
  python -m holon run --milestone M1|M2                                V7 (generator_sha256)
  python -m holon refute --milestone M3 --only filter                  V7 (filter_bin and concretization written back)
  python -m holon profile --milestone T32                              V7 (the T32 records' generator_sha256)
  python -m holon historical exit --milestone M2 [--check]             V7 (I23's coverage)
  python -m holon gate --milestone M0|M1|M2 [--checks GEVID]           R1, R3
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from tests_m3._m3 import ROOT, file_sha256, holon_module, item, load_json, predictions, run_holon, validate

FX = ROOT / "tests_m3" / "fixtures" / "view_evidence"
O12 = ROOT / "tests_m3" / "fixtures" / "o12"
TOY = "tests_m3/fixtures/par_weak.facts.json"   # I24's weak fixture: the test-milestone sets of V5
M = "M2"
CH = "TRANS.challengeState"
PROBE = "L_probe_view_challenge"
LAW_IR = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"
DIAGRAM_SCHEMA = ROOT / "spec" / "schemas" / "diagram.schema.json"
EVIDENCE_SCHEMA = ROOT / "spec" / "schemas" / "evidence.schema.json"
RECORD_FIELDS = ("evidence_levels", "evidence_triage", "evidence_override")
EXIT = "results/M2/m2_exit.json"
EXIT_MD = "docs/M2_EXIT.md"
I65_REPORT = "docs/iterations/I65.md"
# what holon diagram and holon evidence read, for the light copies of R4 and R5 (never spec/heldout/)
LIGHT = ("facts", "spec/lib", "spec/ledger", "spec/M1", "spec/M2", "gen/M2/diagram", "gen/M2/sorts")
_RUNS: dict = {}


def instrument():
    import tests_m3._i66 as I
    return I


def probe() -> dict:
    return load_json(FX / f"{PROBE}.json")


def git(*args, cwd=ROOT) -> str:
    p = subprocess.run(["git", "-C", str(cwd), "-c", "core.quotepath=false", *args], capture_output=True, text=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout


def prereg_commit() -> str:
    """The first commit, oldest first, whose spec/M3/predictions.json holds the key I66 (the audit's C_K)."""
    for c in git("log", "--format=%H", "--reverse", "HEAD", "--", "spec/M3/predictions.json").split():
        try:
            doc = json.loads(git("show", f"{c}:spec/M3/predictions.json"))
        except (ValueError, AssertionError):
            continue
        if isinstance(doc, dict) and "I66" in (doc.get("iterations") or {}):
            return c
    raise AssertionError("no commit holds the key I66")


def end_commit() -> str:
    """V9: the first commit that adds docs/iterations/I66.md, HEAD while none does."""
    added = git("log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", "docs/iterations/I66.md").split()
    return added[0] if added else git("rev-parse", "HEAD").strip()


def own_commits() -> list:
    """I66's own commits (V9): the non-merge commits of `git log --first-parent <prereg>..<end>`, oldest first, each
    with the (status, path) pairs it changes against its parent."""
    commits, cur = [], None
    for ln in git("log", "--first-parent", "--no-merges", "--no-renames", "--reverse", "--format=@%H", "--name-status",
                  f"{prereg_commit()}..{end_commit()}").splitlines():
        if ln.startswith("@"):
            cur = (ln[1:], [])
            commits.append(cur)
        elif ln.strip() and cur is not None:
            st, path = ln.split("\t", 1)
            cur[1].append((st[0], path.strip()))
    return commits


def show(commit: str, rel: str):
    """The JSON of a repository file at a commit, or None when it does not exist there."""
    try:
        return json.loads(git("show", f"{commit}:{rel}"))
    except AssertionError:
        return None


def show_bytes(commit: str, rel: str) -> bytes | None:
    p = subprocess.run(["git", "-C", str(ROOT), "show", f"{commit}:{rel}"], capture_output=True,
                       env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    return p.stdout if p.returncode == 0 else None


def at_prereg(rel: str):
    """The JSON of a repository file at the I66 prereg commit, or None when it did not exist there."""
    return show(prereg_commit(), rel)


def untimed(x):
    """A record without its wall-clock fields (every key named "seconds")."""
    if isinstance(x, dict):
        return {k: untimed(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [untimed(v) for v in x]
    return x


def scratch() -> Path:
    d = Path(tempfile.mkdtemp(prefix="i66-"))
    _RUNS.setdefault("dirs", []).append(d)
    return d


def light_copy(with_view: bool = True) -> Path:
    """A throwaway copy of what holon diagram and holon evidence read (LIGHT, and the view unless with_view is false),
    for runs with --root."""
    I = instrument()
    dst = scratch() / "repo"
    for rel in LIGHT:
        shutil.copytree(ROOT / rel, dst / rel, ignore=shutil.ignore_patterns("__pycache__"))
    if with_view:
        (dst / I.VIEW).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / I.VIEW, dst / I.VIEW)
    return dst


def holon_ok(test, args, cwd=ROOT):
    p = run_holon(args, cwd=cwd, timeout=3600)
    test.assertEqual(p.returncode, 0, f"holon {' '.join(args)}: {(p.stdout + p.stderr)[-3000:]}")
    return p


def evidence() -> dict:
    return load_json(ROOT / instrument().EVIDENCE)


def of_model(entries: list, model: str, level: str | None = None) -> list:
    return [x for x in entries if x["model"] == model and (level is None or x.get("level") == level)]


def need_built(test) -> None:
    """The construction checks read the built tree: the view's diagram is committed."""
    test.assertTrue((ROOT / instrument().DIAGRAM).is_file(), "gen/M2/diagram/m1_view.json is not committed (no build)")


def need_view_model(test, doc: dict) -> None:
    test.assertTrue(instrument().VIEW_MODEL in doc["models"], "gen/M2/evidence.json has no model of the view (no build)")


def on_abstraction(law: dict) -> dict:
    """The law with its facts set to the abstraction's (path and sha256), as the key's at-prereg values were taken."""
    I = instrument()
    return dict(law, facts=I.ABSTRACTION, facts_sha256=file_sha256(ROOT / I.ABSTRACTION))


def toy_sets(root: Path) -> dict:
    """{name: rendered text} of the evidence sets V5 says model no window view, built as their callers build them:
    I24's instrument tests_m3/_i24.evidence_of (test milestone T24, the fixture's diagram in memory, adopted left True);
    holon.rules._given_par_inputs and holon.codecrun.test_evidence_set (T24, in memory, adopted=False); I25's PAR-lossy
    start, holon.rules.par_lossy.components with --codec (T251, no fact document, diagrams {}, adopted=False); and an M2
    build given the committed fact diagrams in memory."""
    E = holon_module("holon.diagram.evidence")
    D = holon_module("holon.diagram")
    A = holon_module("holon.sorts.assign")
    import tests_m3._i24 as I24
    root = Path(root).resolve()
    fx = root / TOY
    asg = A.run_pass([fx], root, None)["assignment"]
    docs = D.fact_documents(M, root)
    out = {
        "i24_evidence_of_T24": I24.evidence_of([fx], asg, root, "T24"),
        "given_par_inputs_T24": E.build([fx], root, diagrams={fx.stem: I24.diagram_of(fx, root)}, assignment=asg,
                                        milestone="T24", components=[], adopted=False),
        "par_lossy_T251": E.build([], root, diagrams={}, assignment={"models": {}, "sites": [], "sorts_sha256": None},
                                  milestone="T251", components=[], adopted=False),
        "m2_in_memory": E.build(docs, root, diagrams={p.stem: load_json(root / "gen" / M / "diagram" / f"{p.stem}.json")
                                                      for p in docs}, milestone=M),
    }
    return {k: E.render(v) for k, v in out.items()}


def tearDownModule():
    for d in _RUNS.pop("dirs", []):
        shutil.rmtree(d, ignore_errors=True)


class TestInstrument(unittest.TestCase):
    """I66-R4 (construction, not counted): the instruments are what the key says, and they agree with I14's code on
    committed inputs."""

    def test_the_key_pins_the_instruments(self):
        th = predictions("I66")["thresholds"]
        self.assertEqual(file_sha256(ROOT / "tests_m3" / "_i66.py"), th["instrument_sha256"])
        self.assertEqual(hashlib.sha256(__doc__.encode("utf-8")).hexdigest(), th["contract_docstring_sha256"])
        got = {str(p.relative_to(ROOT)): file_sha256(p) for p in sorted(FX.glob("*.json"))}
        self.assertEqual(got, th["fixture_sha256"])
        for k in ("view", "declaration", "abstraction"):
            with self.subTest(input=k):
                self.assertEqual(file_sha256(ROOT / th[k]["path"]), th[k]["sha256"])

    def test_the_view_is_its_abstraction_without_the_removed_requires(self):
        """V1, read from the committed documents: the view is the abstraction without the guards its extraction block
        lists, every one a require, and the key records the same list; the instrument finds it as M2's one window view
        (V2) and anchors its libraries to the abstraction's (V3)."""
        I = instrument()
        ab, view = load_json(ROOT / I.ABSTRACTION), load_json(ROOT / I.VIEW)
        self.assertEqual(I.view_problems(ab, view), [])
        rem = I.removed(view)
        self.assertEqual(rem, predictions("I66")["thresholds"]["view"]["removed"])
        acts = {a["name"]: a for a in ab["actions"]}
        for a, ix in rem.items():
            for i in ix:
                with self.subTest(action=a, guard=i):
                    self.assertIn("require", acts[a]["guards"][i])
        self.assertEqual(view["extraction"]["declaration"], I.DECLARATION)
        self.assertEqual(load_json(ROOT / I.DECLARATION)["abstraction"], I.ABSTRACTION)
        self.assertEqual((I.window_views(M, ROOT), I.window_views("M3", ROOT)), ({I.VIEW_MODEL: I.VIEW}, {}))
        self.assertEqual(I.window_declaration(ROOT / I.VIEW, ROOT), I.DECLARATION)
        self.assertEqual(I.lib_paths(ROOT / I.VIEW, ROOT), I.lib_paths(ROOT / I.ABSTRACTION, ROOT))

    def test_the_probe_is_a_law_over_the_view(self):
        """The fixture is a valid holon-ir/0.3 law over the view as it is, ranging over traces (L3) and naming
        challengeState by one act term (L2; its other naming term, fn last_ok, names nothing), with metadata evidence
        E2; no law file or registry names it."""
        I = instrument()
        law = probe()
        self.assertEqual(validate(law, LAW_IR), [])
        self.assertEqual((law["law_id"], law["milestone"], law["facts"], law["facts_sha256"]),
                         (PROBE, M, I.VIEW, file_sha256(ROOT / I.VIEW)))
        self.assertEqual([b["type"] for b in law["statement"]["binders"]], ["Trace", "Nat"])
        self.assertEqual(I.naming_terms(law["statement"]), [("act", '"challengeState"'), ("fn", '"last_ok"')])
        self.assertEqual(law["evidence"], ["E2"])
        hits = [p for p in sorted((ROOT / "laws").rglob("*.json")) if PROBE in p.read_text(encoding="utf-8")]
        self.assertEqual(hits, [])

    def test_the_instrument_is_i14s_law_rules(self):
        """The instrument's rules L1-L4 (law_atoms) give what holon's law_evidence gives over the committed set, for
        every law of laws/M0, laws/M1 and laws/M2 at the prereg and for the probe with its facts set to the
        abstraction's; that probe is covered by morph_rollup, names [TRANS.challengeState] and has 35 relevant atoms,
        32 E2, 2 E6 and 1 E5 (levels [E2, E5, E6]), as the key records at the prereg."""
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        doc = evidence()
        c = prereg_commit()
        n = 0
        for m in ("M0", "M1", "M2"):
            for name in git("ls-tree", "--name-only", f"{c}:laws/{m}").split():
                if not (name.startswith("L") and name.endswith(".json")):
                    continue
                law = json.loads(git("show", f"{c}:laws/{m}/{name}"))
                n += 1
                with self.subTest(law=f"{m}/{name}"):
                    self.assertEqual(I.law_atoms(law, doc), E.law_evidence(law, doc))
        self.assertGreater(n, 0)
        pa = on_abstraction(probe())
        mine = I.law_atoms(pa, doc)
        self.assertEqual(mine, E.law_evidence(pa, doc))
        th = predictions("I66")["thresholds"]["probe"]
        by = {a["id"]: a for a in doc["atoms"]}
        self.assertEqual((mine["model"], mine["named"], mine["levels"]), (I.ABSTRACTION_MODEL, [CH],
                                                                          th["abstraction_levels_at_prereg"]))
        self.assertEqual(dict(Counter(by[i]["level"] for i in mine["atoms"])),
                         th["abstraction_relevant_atoms_at_prereg"])


class TestPredictions(unittest.TestCase):
    """The one counted prediction, I66-P2 (I66-P1, the probe over the view, is a construction check of I66-R5 since the
    verification of the prereg review's fold, finding N3; its id is not reused)."""

    def test_p2_the_views_e3_e4_e6_inventories(self):
        """I66-P2: the view's E6 atoms are the abstraction's 11 and its E4 atoms the abstraction's 2 (blob_hash between
        commitBatch and commitBatchWithProof), same p, q, via and src; its E3 atoms are 8: the abstraction's E3 atoms
        whose guard it keeps, each at that guard's index in the view with the same operands, reason and src
        (commitBatch guards[18] and [19], commitBatchWithProof [22] and [23], commitState [16] and [17], from [17] and
        [18], finalizeBatch [9] and [11]); finalizeBatch's guards[14] (qpend == btot - bn,
        L1MessageQueueWithGasPriceOracle.sol:325) goes with its removed require."""
        item("I66", "I66-P2")
        I = instrument()
        doc = evidence()
        need_view_model(self, doc)
        V, A = of_model(doc["atoms"], I.VIEW_MODEL), of_model(doc["atoms"], I.ABSTRACTION_MODEL)
        lv = lambda xs, level: sorted(I.strip(x) for x in xs if x["level"] == level)   # noqa: E731
        self.assertEqual(lv(V, "E6"), lv(A, "E6"))
        self.assertEqual(len(lv(V, "E6")), 11)
        self.assertEqual(lv(V, "E4"), lv(A, "E4"))
        self.assertEqual(len(lv(V, "E4")), 2)
        moved = I.e3_moved(A, I.removed(load_json(ROOT / I.VIEW)))
        self.assertEqual(lv(V, "E3"), moved)
        self.assertEqual(len(moved), 8)
        self.assertEqual(sorted([x["p"], x["via"]["where"]] for x in V if x["level"] == "E3"),
                         sorted(predictions("I66")["thresholds"]["view_e3_predicted"]))


class TestRegressions(unittest.TestCase):
    """What is already recorded must not change but as V7 and V8 allow."""

    def test_r1_no_laws_evidence_moves_and_gevid_passes(self):
        """I66-R1: for every law of laws/M0, laws/M1 and laws/M2 at the prereg, law_evidence over gen/M2/evidence.json
        equals law_evidence over the prereg's set, and its record's evidence fields are the prereg's; the M1 laws'
        records over the view (results/M2/extracted_m1) keep theirs and stay uncovered (their laws rebound to the view's
        facts_sha256, as holon.differential runs them); GEVID passes on M0 and M1 (report-only) and on M2 (enforcing)
        with no problem and no uncovered law; laws/M2/REGISTRY.json's evidence_sha256 is the set's."""
        item("I66", "I66-R1")
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        c = prereg_commit()
        old, new = at_prereg(I.EVIDENCE), evidence()
        for m in ("M0", "M1", "M2"):
            for n in git("ls-tree", "--name-only", f"{c}:laws/{m}").split():
                if not (n.startswith("L") and n.endswith(".json")):
                    continue
                law = json.loads(git("show", f"{c}:laws/{m}/{n}"))
                with self.subTest(law=f"{m}/{n}"):
                    self.assertEqual(E.law_evidence(law, new), E.law_evidence(law, old))
                    rold, rnew = show(c, f"results/{m}/{n}"), load_json(ROOT / "results" / m / n)
                    self.assertIsNotNone(rold)
                    self.assertEqual({k: rnew.get(k) for k in RECORD_FIELDS}, {k: rold.get(k) for k in RECORD_FIELDS})
        for n in git("ls-tree", "--name-only", f"{c}:results/M2/extracted_m1").split():
            if not (n.startswith("L") and n.endswith(".json")):
                continue
            rold, rnew = show(c, f"results/M2/extracted_m1/{n}"), load_json(ROOT / "results" / "M2" / "extracted_m1" / n)
            law = show(c, f"laws/M1/{n}")
            with self.subTest(view_record=n):
                self.assertEqual({k: rnew.get(k) for k in RECORD_FIELDS}, {k: rold.get(k) for k in RECORD_FIELDS})
                self.assertFalse(E.law_evidence(dict(law, facts_sha256=file_sha256(ROOT / I.VIEW)), new)["covered"])
        for m in ("M0", "M1", "M2"):
            with self.subTest(gevid=m):
                g = E.gevid(m, ROOT)
                self.assertEqual((g["passed"], g["problems"], g["uncovered"]), (True, [], []),
                                 json.dumps({k: g[k] for k in ("problems", "mismatches", "uncovered")})[:3000])
                self.assertEqual(g["mode"], "report-only" if m in ("M0", "M1") else "enforcing")
        self.assertEqual(load_json(ROOT / I.REGISTRY)["evidence_sha256"], new["evidence_sha256"])

    def test_r2_own_commits_change_only_what_v7_allows(self):
        """I66-R2: at least one of I66's own commits (V9) adds gen/M2/diagram/m1_view.json. None changes a frozen root,
        a fact document, the view or the declaration, a file of gen/M0, gen/M1, gen/M3 or gen/T32, a gen/M2 file but the
        view's diagram and gen/M2/evidence.json, a results/ file but the records directly under results/M1, results/M2
        and results/T32 and results/M2/m2_exit.json (so nothing of results/M0, results/M3, results/M2/extracted_m1 or
        results/T32/summary.json), replay/, audit/, spec/ledger/, spec/lib/, spec/M1/lib/, spec/schemas/, spec/M3/ but
        spec/M3/amendments.jsonl, or a law file but laws/M2/REGISTRY.json (and that only in evidence_sha256; so
        nothing of laws/T32). None adds or deletes a law or a record; each M1, M2 or T32 record such a commit changes
        keeps its status and differs from its parent's version only in generator_sha256 and keys named seconds (an M1
        or M2 record's lean4 kernel entry included, rebuilt from the committed Lean reports, which no own commit
        changes: V7). No M3 record is re-made, so after the build every M3 record's generator_sha256 trails I66's
        closures (V7). Each such commit that changes results/M2/m2_exit.json changes only the entries of
        exit_a.coverage.not_replayed keyed by the view ("gen/M2/extracted/m1_view.json#<edge id>"); at I66's end those
        are exactly the view diagram's CODEC, CONS and TRANS edges, and none of their whys says "the hand
        abstraction"."""
        item("I66", "I66-R2")
        I = instrument()
        commits = own_commits()
        self.assertTrue([c for c, ch in commits if ("A", I.DIAGRAM) in ch], "no own commit adds the view's diagram")
        frozen = ("facts/", "laws/M0/", "predictions/", "schemas/", "tests/", "bend/probes/", "AGENTS.md",
                  "tools/freeze.py", "docs/M0_SPEC.md", "docs/BEND_PRIMER.md", "FROZEN.sha256")
        never = frozen + ("spec/M1/facts/", "spec/M2/facts/", I.VIEW, I.DECLARATION, "gen/M0/", "gen/M1/", "gen/M3/",
                          "gen/T32/", "results/M0/", "results/M3/", "results/M2/extracted_m1/", "replay/", "audit/",
                          "spec/ledger/", "spec/lib/", "spec/M1/lib/", "spec/schemas/", "spec/M3/")
        allowed = ("spec/M3/amendments.jsonl",)
        record = re.compile(r"^results/(M[12]|T32)/L[^/]*\.json$")
        mine = lambda nr: {k: v for k, v in nr.items() if not k.startswith(f"{I.VIEW}#")}   # noqa: E731
        rest = lambda x: {**x, "exit_a": {**x["exit_a"], "coverage": {**x["exit_a"]["coverage"],   # noqa: E731
                                                                      "not_replayed": None}}}
        for c, ch in commits:
            for st, f in ch:
                with self.subTest(commit=c[:12], path=f):
                    self.assertFalse(f.startswith(never) and f not in allowed, f)
                    if f.startswith("gen/M2/"):
                        self.assertIn(f, (I.DIAGRAM, I.EVIDENCE))
                    if f.startswith("results/"):
                        self.assertTrue(record.match(f) or f == EXIT, f)
                    if f.startswith("laws/"):
                        self.assertEqual((st, f), ("M", I.REGISTRY))
                        new, old = show(c, f), show(f"{c}^", f)
                        self.assertEqual({k: v for k, v in new.items() if k != "evidence_sha256"},
                                         {k: v for k, v in old.items() if k != "evidence_sha256"})
                    if record.match(f):
                        self.assertEqual(st, "M")
                        new, old = untimed(show(c, f)), untimed(show(f"{c}^", f))
                        self.assertEqual(new.get("status"), old.get("status"))
                        self.assertLessEqual({k for k in set(new) | set(old) if new.get(k) != old.get(k)},
                                             {"generator_sha256"})
                    if f == EXIT:
                        self.assertEqual(st, "M")
                        new, old = show(c, f), show(f"{c}^", f)
                        self.assertEqual(rest(new), rest(old))
                        self.assertEqual(mine(new["exit_a"]["coverage"]["not_replayed"]),
                                         mine(old["exit_a"]["coverage"]["not_replayed"]))
        end = end_commit()
        nr = show(end, EXIT)["exit_a"]["coverage"]["not_replayed"]
        keys = sorted(k for k in nr if k.startswith(f"{I.VIEW}#"))
        self.assertEqual(keys, I.exit_keys(show(end, I.DIAGRAM)))
        self.assertEqual([k for k in keys if nr[k].startswith("the hand abstraction of ")], [])

    def test_r3_the_gates_and_the_exit_document(self):
        """I66-R3 (part): GEVID passes from the gate on M0, M1 and M2 (report-only, report-only, enforcing), and the
        M2 exit documents regenerate byte for byte (holon historical exit --check). The rest of R3 is checked by CI and
        the audits on the build head and named in the report: gates M0, M1 and M2 in full (G1 regenerating the view's
        diagram with the others); CI's three M3 jobs, gate-M3-partial (G3, G5, G8, G9, G10, G11, G11V, GEVID) and
        gate-M3-G2, which run no G1, failing only the base's items, and tests-m3-catalog
        (tests_m3.test_catalog_rederivation) passing, as at the base; the frozen suite, freeze-check and both prereg
        audits. The full M3 gate's G1 fails on the M3 records' staleness until the next M3 re-make (V7); R3 states
        that and does not check it."""
        item("I66", "I66-R3")
        for m in ("M0", "M1", "M2"):
            with self.subTest(milestone=m):
                out = scratch() / f"gate_{m}.json"
                run_holon(["gate", "--milestone", m, "--checks", "GEVID", "--report", str(out)], cwd=ROOT, timeout=7200)
                rep = load_json(out) if out.is_file() else {}
                g = (rep.get("checks") or {}).get("GEVID") or {}
                self.assertTrue(g.get("passed"), str(g.get("detail") or rep)[:3000])
                self.assertEqual(g.get("mode"), "report-only" if m in ("M0", "M1") else "enforcing")
        p = run_holon(["historical", "exit", "--milestone", M, "--check"], cwd=ROOT, timeout=1800)
        self.assertEqual(p.returncode, 0, (p.stdout + p.stderr)[-2000:])


class TestConstruction(unittest.TestCase):
    """I66-R4: construction checks, not predictions (V2, V3, V9 and the M3 inputs); each reads the built tree."""

    def test_window_views_are_found_by_their_declaration(self):
        """V2: holon.diagram.window_views gives the instrument's views (M2: the view alone; M3: none). In a light copy
        without the view (its declaration kept) it gives none, holon diagram writes the three fact documents' diagrams
        alone, and holon evidence writes the prereg's gen/M2/evidence.json byte for byte: nothing but the view's model
        moved the set."""
        need_built(self)
        I = instrument()
        D = holon_module("holon.diagram")
        for m in ("M2", "M3"):
            with self.subTest(milestone=m):
                got = [p.resolve().relative_to(ROOT.resolve()).as_posix() for p in D.window_views(m, ROOT)]
                self.assertEqual(got, sorted(I.window_views(m, ROOT).values()))
        self.assertEqual(I.window_views(M, ROOT), {I.VIEW_MODEL: I.VIEW})
        repo = light_copy(with_view=False)
        self.assertEqual(D.window_views(M, repo), [])
        out = scratch() / "d"
        holon_ok(self, ["diagram", "--milestone", M, "--root", str(repo), "--out", str(out)])
        self.assertEqual(sorted(q.name for q in out.glob("*.json")), sorted(Path(r).name for r in I.FACT_DIAGRAMS))
        (repo / I.DIAGRAM).unlink()
        f = scratch() / "evidence.json"
        holon_ok(self, ["evidence", "--milestone", M, "--root", str(repo), "--out", str(f)])
        self.assertEqual(f.read_bytes(), show_bytes(prereg_commit(), I.EVIDENCE))

    def test_the_view_takes_its_abstractions_libraries(self):
        """V3: holon.gen.targetlib's window_declaration, anchor and lib_files give what the instrument's anchor rule
        gives for the view (its declaration; the abstraction; spec/lib/ and spec/M1/lib/) and for every other document
        a library lookup can meet: every facts path a law of laws/ names, every JSON document directly under
        gen/M2/extracted/, and every document under facts/ and spec/M*/facts/ (no declaration; itself; the path rule,
        unchanged)."""
        need_built(self)
        I = instrument()
        T = holon_module("holon.gen.targetlib")
        rel = lambda ps: [Path(p).resolve().relative_to(ROOT.resolve()).as_posix() for p in ps]   # noqa: E731
        paths = {I.VIEW}
        for p in sorted((ROOT / "laws").glob("M*/L*.json")):
            f = load_json(p).get("facts")
            if isinstance(f, str):
                paths.add(f)
        for pat in ("gen/M2/extracted/*.json", "facts/*.json", "spec/M*/facts/*.json"):
            paths |= {p.relative_to(ROOT).as_posix() for p in ROOT.glob(pat)}
        self.assertIn("gen/M3/codec/header_length.json", paths)
        for f in sorted(paths):
            with self.subTest(document=f):
                p = ROOT / f
                self.assertEqual(rel(T.lib_files(p, ROOT)), I.lib_paths(p, ROOT))
                w = T.window_declaration(p, ROOT)
                self.assertEqual(w[0] if w else None, I.window_declaration(p, ROOT))
                want = ROOT / load_json(ROOT / w[0])["abstraction"] if w else p
                self.assertEqual(Path(T.anchor(p, ROOT)).resolve(), want.resolve())
        self.assertIn("spec/M1/lib/morph_rollup.lib.json", rel(T.lib_files(ROOT / I.VIEW, ROOT)))
        self.assertEqual([f for f in sorted(paths) if I.window_declaration(ROOT / f, ROOT)], [I.VIEW])

    def test_the_view_is_no_fact_document(self):
        """V2: the fact documents of M2 are the three hand documents; gen/M2/sorts is the prereg's byte for byte and the
        frozen assignment has no model of the view."""
        need_built(self)
        I = instrument()
        D = holon_module("holon.diagram")
        got = [p.resolve().relative_to(ROOT.resolve()).as_posix() for p in D.fact_documents(M, ROOT)]
        self.assertEqual(got, sorted(["facts/morph_header.json", "spec/M1/facts/morph_batchdata.json", I.ABSTRACTION]))
        c = prereg_commit()
        for p in sorted((ROOT / "gen" / M / "sorts").glob("*.json")):
            with self.subTest(file=p.name):
                self.assertEqual(p.read_bytes(), show_bytes(c, p.relative_to(ROOT).as_posix()))
        self.assertNotIn(I.VIEW_MODEL, load_json(ROOT / "gen" / M / "sorts" / "assignment.json")["models"])

    def test_no_m3_input_moves(self):
        """V7, V9: no own commit (V9) changes a file that laws/M3/DERIVATION.json or gen/M3/evidence.json lists as an
        input or that laws/M3/REGISTRY.json names among its facts files, at the prereg or at HEAD; and the committed
        gen/M3/evidence.json is what holon.diagram.evidence.build_milestone("M3") builds now (M3 has no window view). So
        nothing I66 changes reaches M3's derivation, through a file or through the evidence pass; M3's statement
        hashes read lib_files of M3's facts paths, which V3 leaves as they are (test_the_view_takes_its_abstractions_
        libraries)."""
        need_built(self)
        E = holon_module("holon.diagram.evidence")
        names = set()
        for c in (prereg_commit(), "HEAD"):
            der, ev, reg = (show(c, r) for r in ("laws/M3/DERIVATION.json", "gen/M3/evidence.json",
                                                 "laws/M3/REGISTRY.json"))
            names |= {i["path"] for i in der["inputs"]} | {i["path"] for i in ev["inputs"]}
            names |= set(reg.get("facts_files") or {})
        self.assertIn("gen/M3/evidence.json", names)
        touched = {f for _, ch in own_commits() for _, f in ch}
        self.assertEqual(sorted(touched & names), [])
        self.assertEqual(E.render(E.build_milestone("M3", ROOT)),
                         (ROOT / "gen" / "M3" / "evidence.json").read_text(encoding="utf-8"))

    def test_holon_names_no_i66_id(self):
        """V9: no file under holon/ names the probe; holon/diagram/, holon/gen/targetlib.py and
        holon/historical/exit_report.py name neither the view's file nor the declaration's."""
        need_built(self)
        strict = ("holon/diagram/", "holon/gen/targetlib.py", "holon/historical/exit_report.py")
        hits = []
        for p in sorted((ROOT / "holon").rglob("*")):
            if not (p.is_file() and p.suffix in (".py", ".mjs", ".js", ".json", ".bend", ".lean")):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            rel = p.relative_to(ROOT).as_posix()
            pat = r"L_probe_view|m1_view|window_rollup" if rel.startswith(strict) else r"L_probe_view"
            hits += [f"{rel}:{i}" for i, ln in enumerate(text.splitlines(), 1) if re.search(pat, ln)]
        self.assertEqual(hits, [])


class TestBuild(unittest.TestCase):
    """I66-R5: construction checks, not predictions (V4-V7: the view's diagram, its model, the sets that model no
    view, the CLI and the exit document); each reads the built tree."""

    def test_the_view_has_its_abstractions_diagram(self):
        """V4: holon diagram --milestone M2 writes the three fact documents' diagrams, byte-identical to the prereg's,
        and gen/M2/diagram/m1_view.json; the committed directory is that output. The view's diagram is valid, maps every
        top-level section of the view, names the view (model m1_view, facts and facts_sha256 the view's, facts_version
        holon-facts/0.2, provenance.extraction its extraction block), has the edges of the abstraction's diagram (ids
        and kinds: 10 TRANS, 2 MIG, 1 CONS, 22 STORE, 27 LOAD), every edge's access writes and every STORE edge's
        writers equal to the abstraction's, every edge's access reads and every LOAD edge's readers a subset of them,
        and equal for the TRANS edges of the actions the view keeps whole (challengeState, revertBatch, sendMessage,
        wait) and for every MIG, CONS and observer edge; each TRANS edge's guards are the abstraction's without the
        removed ones, in order; its principal classes are the abstraction's; its inputs include the window declaration
        and the libraries of the abstraction."""
        need_built(self)
        I = instrument()
        out = scratch() / "d"
        holon_ok(self, ["diagram", "--milestone", M, "--out", str(out)])
        names = sorted([Path(r).name for r in I.FACT_DIAGRAMS] + [Path(I.DIAGRAM).name])
        got = {q.name: q.read_bytes() for q in sorted(out.glob("*.json"))}
        self.assertEqual(sorted(got), names)
        self.assertEqual(got, {q.name: q.read_bytes() for q in sorted((ROOT / "gen" / M / "diagram").glob("*.json"))})
        c = prereg_commit()
        for rel in I.FACT_DIAGRAMS:
            with self.subTest(diagram=rel):
                self.assertEqual((ROOT / rel).read_bytes(), show_bytes(c, rel))
        d, a, view = load_json(ROOT / I.DIAGRAM), load_json(ROOT / I.ABSTRACTION_DIAGRAM), load_json(ROOT / I.VIEW)
        self.assertEqual(validate(d, DIAGRAM_SCHEMA), [])
        self.assertEqual((d["model"], d["facts"], d["facts_sha256"], d["facts_version"]),
                         (I.VIEW_MODEL, I.VIEW, file_sha256(ROOT / I.VIEW), I.FACTS02))
        self.assertEqual(set(d["mapped_sections"]), set(view) - {"facts_version"})
        self.assertEqual((d.get("provenance") or {}).get("extraction"), view["extraction"])
        kinds = lambda g: {e["id"]: e["kind"] for e in g["edges"]}   # noqa: E731
        self.assertEqual(kinds(d), kinds(a))
        self.assertEqual(Counter(kinds(d).values()), Counter({"TRANS": 10, "MIG": 2, "CONS": 1, "STORE": 22, "LOAD": 27}))
        rem = I.removed(view)
        same = I.unchanged_reads(a, I.kept_actions(load_json(ROOT / I.ABSTRACTION), rem))
        self.assertEqual(sorted(same), predictions("I66")["thresholds"]["unchanged_read_edges"])
        A, D = {e["id"]: e for e in a["edges"]}, {e["id"]: e for e in d["edges"]}
        acc = lambda e, k: {tuple(t) for t in e["access"][k]}   # noqa: E731
        for i in sorted(A):
            with self.subTest(edge=i):
                self.assertEqual(acc(D[i], "writes"), acc(A[i], "writes"))
                self.assertLessEqual(acc(D[i], "reads"), acc(A[i], "reads"))
                if i in same:
                    self.assertEqual(acc(D[i], "reads"), acc(A[i], "reads"))
                if A[i]["kind"] == "STORE":
                    self.assertEqual(D[i].get("writers"), A[i].get("writers"))
                if A[i]["kind"] == "LOAD" and "readers" in A[i]:
                    self.assertLessEqual(set(D[i].get("readers") or []), set(A[i]["readers"]))
                if A[i]["kind"] == "TRANS":
                    gone = set(rem.get(A[i]["component"], []))
                    self.assertEqual(D[i].get("guards"), [g for k, g in enumerate(A[i]["guards"]) if k not in gone])
        self.assertEqual(d["principal_classes"], a["principal_classes"])
        libs = {x["path"] for x in a["inputs"] if x["path"].endswith(".lib.json")}
        self.assertLessEqual(libs | {I.DECLARATION}, {x["path"] for x in d["inputs"]})

    def test_the_set_gains_the_view_model_alone(self):
        """V5: gen/M2/evidence.json holds the prereg's four models unchanged, their atoms and unresolved entries as at
        the prereg (ids included), its header fields (document, versions, milestone, levels, sorts_sha256) as at the
        prereg, and one more model, m1_view: facts gen/M2/extracted/m1_view.json, its sha256, holon-facts/0.2, diagram
        gen/M2/diagram/m1_view.json and the anchors I14's rule gives that diagram (sites {}), with no E1 and no E5 atom.
        Its inputs are the prereg's, each with its sha256 unchanged, plus exactly the view, its diagram and its window
        declaration. The document is valid, its evidence_sha256 is its body's hash, differs from the prereg's, and is
        the one laws/M2/REGISTRY.json records."""
        need_built(self)
        I = instrument()
        doc, old = evidence(), at_prereg(I.EVIDENCE)
        self.assertIsNotNone(old)
        self.assertEqual(sorted(doc["models"]), sorted([*old["models"], I.VIEW_MODEL]))
        for m in old["models"]:
            with self.subTest(model=m):
                self.assertEqual(doc["models"][m], old["models"][m])
        self.assertEqual([x for x in doc["atoms"] if x["model"] != I.VIEW_MODEL], old["atoms"])
        self.assertEqual([x for x in doc["unresolved"] if x["model"] != I.VIEW_MODEL], old["unresolved"])
        for k in ("document", "evidence_version", "milestone", "levels", "sorts_sha256"):
            self.assertEqual(doc[k], old[k], k)
        new_in = {x["path"]: x["sha256"] for x in doc["inputs"]}
        old_in = {x["path"]: x["sha256"] for x in old["inputs"]}
        self.assertEqual(sorted(set(new_in) - set(old_in)), sorted([I.VIEW, I.DIAGRAM, I.DECLARATION]))
        self.assertEqual({k: new_in.get(k) for k in old_in}, old_in)
        for rel in (I.VIEW, I.DIAGRAM, I.DECLARATION):
            self.assertEqual(new_in[rel], file_sha256(ROOT / rel), rel)
        mo = doc["models"][I.VIEW_MODEL]
        self.assertEqual({k: v for k, v in mo.items() if k != "anchors"},
                         {"facts": I.VIEW, "facts_sha256": file_sha256(ROOT / I.VIEW), "facts_version": I.FACTS02,
                          "diagram": I.DIAGRAM})
        sites = load_json(ROOT / "gen" / M / "sorts" / "assignment.json").get("sites") or []
        self.assertEqual(mo["anchors"], I.anchors(load_json(ROOT / I.DIAGRAM), sites, I.VIEW_MODEL))
        self.assertEqual(mo["anchors"]["sites"], {})
        self.assertEqual([x["id"] for x in of_model(doc["atoms"], I.VIEW_MODEL) if x["level"] in ("E1", "E5")], [])
        self.assertEqual(validate(doc, EVIDENCE_SCHEMA), [])
        body = {k: v for k, v in doc.items() if k not in ("evidence_sha256", "inputs")}
        self.assertEqual(doc["evidence_sha256"], I.canonical_sha256(body))
        self.assertNotEqual(doc["evidence_sha256"], old["evidence_sha256"])
        self.assertEqual(load_json(ROOT / I.REGISTRY)["evidence_sha256"], doc["evidence_sha256"])

    def test_e2_moves_only_where_a_removed_require_can(self):
        """V5, read through the calculus: the view's E2 atoms with an endpoint TRANS.challengeState are the
        abstraction's 35 (same p, q and via; 32 between two TRANS edges), since challengeState keeps every guard and no
        removed require reads bc, chs, inch or win; the view's E2 atoms and unresolved entries ending at an edge whose
        reads no removed require can change (the twelve of thresholds.unchanged_read_edges) are the abstraction's; and
        every other one relates a (p, q, carrier) the abstraction relates by an atom or an unresolved entry."""
        need_built(self)
        I = instrument()
        doc = evidence()
        V, A = of_model(doc["atoms"], I.VIEW_MODEL), of_model(doc["atoms"], I.ABSTRACTION_MODEL)
        VU, AU = of_model(doc["unresolved"], I.VIEW_MODEL), of_model(doc["unresolved"], I.ABSTRACTION_MODEL)
        self.assertTrue(V, "the view has no atom")
        at = lambda xs: sorted(I.strip(x) for x in xs if x["level"] == "E2" and CH in (x["p"], x["q"]))   # noqa: E731
        self.assertEqual(at(V), at(A))
        self.assertEqual(len(at(V)), predictions("I66")["thresholds"]["challenge_state_e2_at_prereg"]["atoms"])
        self.assertEqual(sum(1 for x in V if x["level"] == "E2" and CH in (x["p"], x["q"])
                             and x["p"].startswith("TRANS.") and x["q"].startswith("TRANS.")), 32)
        same = set(predictions("I66")["thresholds"]["unchanged_read_edges"])
        e2 = lambda xs: sorted(I.strip(x) for x in xs if x["level"] == "E2" and x["q"] in same)   # noqa: E731
        self.assertEqual(e2(V), e2(A))
        un = lambda xs: sorted(I.strip(x) for x in xs if x["q"] in same)   # noqa: E731
        self.assertEqual(un(VU), un(AU))
        self.assertLessEqual(I.relation(V, VU), I.relation(A, AU))

    def test_the_probe_over_the_view(self):
        """V5, V6 (construction: it follows from test_e2_moves_only_where_a_removed_require_can, I66-P2 and V6, and was
        I66-P1 until the verification of the prereg review's fold, finding N3): the probe law (over the view; binders
        p: Trace and j: Nat; challengeState named by one act term; metadata E2) is covered by m1_view, names
        [TRANS.challengeState], has the view's 10 TRANS edges as context and computes levels [E2, E6] (max E2), by
        holon's law_evidence and by the instrument's rules L1-L4 alike, so its metadata E2 is computed. Its relevant
        atoms are 34, 32 E2 (between TRANS.challengeState and a TRANS edge) and 2 E6 (challengeState with commitState
        and with proveState, token "state"), and they are the relevant atoms of the same probe over the abstraction's
        model (same level, p, q, via and src) but its E5 atom at challengeState guards[9] (sort Time): no sorts
        assignment names the view, so it has no E5 atom (V5)."""
        need_built(self)
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        doc = evidence()
        need_view_model(self, doc)
        law = probe()
        mine = I.law_atoms(law, doc)
        self.assertEqual(E.law_evidence(law, doc), mine)
        trans = doc["models"][I.VIEW_MODEL]["anchors"]["trans"]
        self.assertEqual(len(trans), 10)
        self.assertEqual((mine["model"], mine["covered"], mine["named"], mine["context"], mine["levels"], mine["max"]),
                         (I.VIEW_MODEL, True, [CH], trans, ["E2", "E6"], "E2"))
        self.assertLessEqual(set(law["evidence"]), set(mine["levels"]))
        by = {a["id"]: a for a in doc["atoms"]}
        self.assertEqual(Counter(by[i]["level"] for i in mine["atoms"]), Counter({"E2": 32, "E6": 2}))
        ref = I.law_atoms(on_abstraction(law), doc)
        self.assertEqual(sorted(I.strip(by[i]) for i in mine["atoms"]),
                         sorted(I.strip(by[i]) for i in ref["atoms"] if by[i]["level"] != "E5"))
        self.assertEqual([by[i]["via"]["where"] for i in ref["atoms"] if by[i]["level"] == "E5"], ["guards[9].require"])

    def test_the_derived_law_names_nothing_until_i65(self):
        """V6: I65's derived law (tests_m3/_i64.derived_law of tests_m3/fixtures/o12/C_o12.json) is covered by m1_view
        with the view's 10 TRANS edges as context. While docs/iterations/I65.md does not exist (rule L2 reads no ghost
        term), holon's law_evidence and the instrument's rules both give it named [] and levels []; once it exists
        (I65's build), law_evidence names [TRANS.challengeState] and gives the probe's levels [E2, E6] and its
        relevant atoms."""
        need_built(self)
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        import tests_m3._i64 as I64
        doc = evidence()
        trans = doc["models"][I.VIEW_MODEL]["anchors"]["trans"]
        law = I64.derived_law(load_json(O12 / "C_o12.json"), ROOT)
        self.assertEqual((law["facts"], law["facts_sha256"]), (I.VIEW, file_sha256(ROOT / I.VIEW)))
        le = E.law_evidence(law, doc)
        self.assertEqual((le["model"], le["covered"], le["context"]), (I.VIEW_MODEL, True, trans))
        if not (ROOT / I65_REPORT).is_file():
            self.assertEqual((le["named"], le["levels"], le["atoms"]), ([], [], []))
            self.assertEqual(I.law_atoms(law, doc), le)
        else:
            pr = E.law_evidence(probe(), doc)
            self.assertEqual((le["named"], le["levels"], le["atoms"]), ([CH], ["E2", "E6"], pr["atoms"]))

    def test_test_milestone_and_in_memory_sets_model_no_view(self):
        """V5: the sets built for a test milestone or from diagrams passed in model no window view: I24's
        evidence_of (T24), the _given_par_inputs and test_evidence_set shape (T24, adopted=False), I25's PAR-lossy
        start (T251) and an M2 build given the committed fact diagrams in memory. None has a model m1_view or names
        the view, its diagram or its declaration among its inputs; each renders to the bytes it rendered to at the
        prereg (thresholds.toy_sets_at_prereg), and the same in a light copy, with the view, its diagram and its
        declaration and without them."""
        need_built(self)
        I = instrument()
        th = predictions("I66")["thresholds"]["toy_sets_at_prereg"]
        got = toy_sets(ROOT)
        self.assertEqual(sorted(got), sorted(th))
        for k, text in got.items():
            with self.subTest(set=k):
                d = json.loads(text)
                self.assertNotIn(I.VIEW_MODEL, d["models"])
                self.assertEqual(sorted(d["models"]), th[k]["models"])
                self.assertEqual(sorted({I.VIEW, I.DIAGRAM, I.DECLARATION} & {x["path"] for x in d["inputs"]}), [])
                self.assertEqual(hashlib.sha256(text.encode("utf-8")).hexdigest(), th[k]["sha256"])
        repo = light_copy()
        (repo / TOY).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / TOY, repo / TOY)
        self.assertTrue((repo / I.DIAGRAM).is_file())
        self.assertEqual(toy_sets(repo), got)
        for rel in (I.VIEW, I.DIAGRAM, I.DECLARATION):
            (repo / rel).unlink()
        self.assertEqual(toy_sets(repo), got)

    def test_a_stem_collision_is_refused(self):
        """V4, V5: in a light copy where a second window view has a fact document's stem (the view copied to
        gen/M2/extracted/morph_rollup.json), holon diagram --milestone M2 and holon evidence --milestone M2 exit 1 and
        write nothing."""
        need_built(self)
        I = instrument()
        repo = light_copy()
        shutil.copy2(ROOT / I.VIEW, repo / "gen" / M / "extracted" / "morph_rollup.json")
        self.assertEqual(sorted(I.window_views(M, repo)), sorted([I.ABSTRACTION_MODEL, I.VIEW_MODEL]))
        out = scratch() / "d"
        p = run_holon(["diagram", "--milestone", M, "--root", str(repo), "--out", str(out)], cwd=ROOT, timeout=1800)
        self.assertEqual(p.returncode, 1, (p.stdout + p.stderr)[-2000:])
        self.assertEqual(sorted(out.glob("*")) if out.exists() else [], [])
        f = scratch() / "evidence.json"
        p = run_holon(["evidence", "--milestone", M, "--root", str(repo), "--out", str(f)], cwd=ROOT, timeout=1800)
        self.assertEqual(p.returncode, 1, (p.stdout + p.stderr)[-2000:])
        self.assertFalse(f.exists())

    def test_the_cli_is_the_build_and_deterministic(self):
        """V5: two runs of holon evidence --milestone M2 write the committed file; it is render(build(<the fact
        documents>, root, milestone="M2")); a build for no milestone has no view model."""
        need_built(self)
        I = instrument()
        E = holon_module("holon.diagram.evidence")
        D = holon_module("holon.diagram")
        texts = []
        for i in range(2):
            f = scratch() / f"e{i}.json"
            holon_ok(self, ["evidence", "--milestone", M, "--out", str(f)])
            texts.append(f.read_bytes())
        self.assertEqual(texts[0], texts[1])
        self.assertEqual(texts[0], (ROOT / I.EVIDENCE).read_bytes())
        paths = D.fact_documents(M, ROOT)
        self.assertEqual(E.render(E.build(paths, ROOT, milestone=M)).encode("utf-8"), texts[0])
        self.assertNotIn(I.VIEW_MODEL, E.build(paths, ROOT)["models"])

    def test_the_view_model_ignores_ledger_links(self):
        """V5: with every ledger link and LEDGER or HASH debt emptied in the view's diagram (which has LEDGER debt
        and no links here) and in the abstraction's (which has ledger links and HASH debt: what I65's ledger anchor will
        give the view), holon evidence gives both models the same model entry, atoms and unresolved entries."""
        need_built(self)
        I = instrument()
        repo = light_copy()
        for rel in (I.DIAGRAM, I.ABSTRACTION_DIAGRAM):
            dg = load_json(ROOT / rel)
            (repo / rel).write_text(json.dumps(I.ledger_free(dg), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        ab = load_json(ROOT / I.ABSTRACTION_DIAGRAM)
        self.assertNotEqual(I.ledger_free(ab), ab)
        f = scratch() / "evidence.json"
        holon_ok(self, ["evidence", "--milestone", M, "--root", str(repo), "--out", str(f)])
        got, doc = load_json(f), evidence()
        for m in (I.VIEW_MODEL, I.ABSTRACTION_MODEL):
            with self.subTest(model=m):
                self.assertEqual(got["models"][m], doc["models"][m])
                for k in ("atoms", "unresolved"):
                    self.assertEqual(of_model(got[k], m), of_model(doc[k], m), k)

    def test_the_re_make_reached_every_m1_m2_and_t32_record(self):
        """V7: at I66's end every record directly under results/M1, results/M2 and results/T32 carries a
        generator_sha256 that differs from its version at the prereg, one value per milestone (holon run re-made the M1
        and M2 records and holon profile the T32 records with I66's code), and laws/T32, gen/T32 and
        results/T32/summary.json are the prereg's."""
        need_built(self)
        c, end = prereg_commit(), end_commit()
        for m in ("M1", "M2", "T32"):
            names = [n for n in git("ls-tree", "--name-only", f"{end}:results/{m}").split()
                     if n.startswith("L") and n.endswith(".json")]
            new = {n: (show(end, f"results/{m}/{n}") or {}).get("generator_sha256") for n in names}
            old = {n: (show(c, f"results/{m}/{n}") or {}).get("generator_sha256") for n in names}
            with self.subTest(milestone=m):
                self.assertTrue(names)
                self.assertEqual(len(set(new.values())), 1, sorted(set(new.values())))
                self.assertEqual([n for n in names if new[n] == old[n]], [])
        for rel in ("laws/T32", "gen/T32", "results/T32/summary.json"):
            with self.subTest(unchanged=rel):
                self.assertEqual(git("rev-parse", f"{end}:{rel}"), git("rev-parse", f"{c}:{rel}"))

    def test_the_exit_document_names_the_window_view(self):
        """V7: results/M2/m2_exit.json's exit_a.coverage.not_replayed holds one entry per CODEC, CONS and TRANS edge of
        the view's diagram ("gen/M2/extracted/m1_view.json#<edge id>"), each with the why of the abstraction's entry for
        the same edge, except for the actions the trans window replayed (the abstraction's why reads "the hand
        abstraction of ..."): there it reads "the window view's <action> (gen/M2/extracted/m1_view.json, <the view's
        extraction method>); its extracted counterpart ..." with the abstraction's rest (instrument view_why);
        docs/M2_EXIT.md names each entry with its why."""
        need_built(self)
        I = instrument()
        nr = load_json(ROOT / EXIT)["exit_a"]["coverage"]["not_replayed"]
        dg, view = load_json(ROOT / I.DIAGRAM), load_json(ROOT / I.VIEW)
        md = (ROOT / EXIT_MD).read_text(encoding="utf-8")
        edges = {e["id"]: e for e in dg["edges"]}
        changed = []
        for k in I.exit_keys(dg):
            eid = k.split("#", 1)[1]
            comp = edges[eid].get("component") or eid.split(".", 1)[-1]
            hand = nr[f"{I.ABSTRACTION}#{eid}"]
            with self.subTest(edge=eid):
                self.assertEqual(nr[k], I.view_why(hand, comp, view))
                self.assertIn(f"- `{k}`: {nr[k]}", md)
            if nr[k] != hand:
                changed.append(eid)
        self.assertTrue(changed, "no replayed action among the view's edges")
        self.assertEqual(changed, sorted(e for e in changed if nr[f"{I.ABSTRACTION}#{e}"].startswith(I.HAND)))


if __name__ == "__main__":
    unittest.main()
