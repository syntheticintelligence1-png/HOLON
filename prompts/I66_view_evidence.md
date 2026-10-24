# I66: holon differential's window view in M2's evidence set (Q62)

Rendered from Question Q62, the route I65's prereg names (`prompts/I65_o12_view.md`, "GEVID" under the integration and the risk "GEVID and the build's merge"; rule O4 of `tests_m3/test_o12.py`): a small separate key, preregistered and reviewed, that models holon differential's window views in M2's evidence set, as I20 covered its adopted documents (`docs/iterations/I20.md`, "GEVID: the evidence set covers the adopted transitions document"). No human answer to Q62 is recorded (`docs/HUMAN_ANSWERS.md`). The plan is row I66 of `docs/BUILD_PLAN.md`, section 3. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (V1-V9), commands and exit codes are in the docstring of `tests_m3/test_view_evidence.py`; I14's calculus is the docstring of `tests_m2/test_evidence.py`.

## Why a separate key, and why before I65's build

- I65 adds `L_contract_C_o12`, an ordinary M2 law over the window view `gen/M2/extracted/m1_view.json` (holon.differential's view: the M1 abstraction `spec/M1/facts/morph_rollup.json` with the requires the extracted code lacks removed). The law carries its contract's evidence claim `E2`.
- GEVID (I14) enforces from M2 on, with no exemption: a law the evidence set does not cover, or metadata evidence its computed levels lack, fails. `gen/M2/evidence.json` models the three fact documents and the adopted transitions document, and no window view, so the law is uncovered.
- I65's prereg therefore routes the fix to a separately preregistered key, Q62, and its build merges only after that key. Modelling the view is a change to M2's evidence set, which every M0-M2 GEVID run rebuilds byte for byte and `laws/M2/REGISTRY.json` hashes, so it has its own predictions, as I20's integrator fix had.
- The key is filed in `spec/M3/predictions.json`, beside I65. Keys are filed by the phase in which they are preregistered and audited, not by the directories their outcomes touch: I65 (milestone column M2 in the BUILD_PLAN table) and I43 are M3 keys with M2 outcomes, while I59-I62 are M2 keys because they are M2 exit deliverables. I66 is no M2 exit item; it is I65's prerequisite. The cost is the one I65 paid for I15: an M3 prereg commit may touch `tests_m3/` (I43's amendment is in it) but not `tests_m2/`, so I14's amendments are a later commit of this pull request.

## What I66 does

- **The view (V1).** Nothing changes in it. It is the abstraction without the requires its extraction block lists under `removed`: commitBatch [21], commitBatchWithProof [25, 30], commitState [11, 20], finalizeBatch [14], proveState [9], setPause [1, 2]. The tests check that from the committed files.
- **Window views (V2).** `holon.diagram.window_views(milestone, root)`: the holon-facts/0.2 documents directly under `gen/<M>/extracted/` whose window declaration (V3) is one of the milestone's, `spec/<M>/lib/window_*.json` (for M2, the view alone; for M3, none). A view never becomes a fact document: `fact_documents`, `holon sorts`, `holon derive` and I13's frozen assignment do not change.
- **Its libraries (V3), as I65's code.** The view calls the abstraction's target-library builtins (`w`, `bump_f`, `nth_default`, ...). `holon.gen.targetlib.lib_files` finds libraries next to a document's milestone directory, which for `gen/M2/extracted/` is none, and I11's walker refuses an unknown builtin ("unknown function agg" at the base), so the view's diagram cannot be built without an anchor.
  - I66 takes I65's anchor from its build, its code verbatim (`holon/gen/targetlib.py` at 85d91d70 on `claude/brave-wright-2c5d0o-i65-build`): `WINDOW_VERSION`, `_repo_path`, `_named_declaration`, `window_declaration`, `anchor`, and `lib_files` reading the anchor's libraries. A docstring that mentions search hints says libraries only until I65 anchors `hints_for`. A document whose extraction block names a window declaration (holon-window/0.1, with an existing abstraction) is anchored to the abstraction; every other document to itself. So I65's rebase onto I66 is trivial.
  - `hints_for` keeps its current code (I65 anchors it). This is the library half of I65's view anchor (O4).
- **Its diagram (V4).** `holon diagram --milestone M2` also writes `gen/M2/diagram/m1_view.json`, by I11's adapters as they are. Its inputs list the window declaration. A view whose stem is a fact document's is a DiagramError, with nothing written. G1 regenerates the view's diagram with the other diagrams, unchanged.
- **Its evidence model (V5).** `holon.diagram.evidence.build` models window views only when it reads the committed diagrams for a target milestone (M<k>): one model per view of `gen_milestone(M)`, key `m1_view`, with its facts, sha256, `holon-facts/0.2`, its committed diagram and the anchors I14's rule gives. Its atoms are I14's E2, E3, E4 and E6 (E1 is a facts-0.1 level).
  - A build given its own diagrams, for a test milestone (T24, T25, ...: `gen_milestone` maps them to M2) or for no milestone adds no view, whatever its adopted switch. So PAR's `_given_par_inputs`, `codecrun.test_evidence_set`, `par_lossy.components` with `--codec` and I24's `evidence_of` build what they built before, byte for byte.
  - One stated case: E5 reads the frozen assignment's model of the view's stem when there is one, and otherwise gives no operand a sort. A fact document without a model stays an EvidenceError. I13's pass assigns sorts to fact documents only, so the view has no E5 atom.
  - The inputs gain the view, its diagram and its declaration. Files read only to find the views are not inputs. A view whose stem is another model's is an EvidenceError.
- **Laws (V6).** law_evidence (L1-L4) does not change. No committed law names the view's path, so no computed evidence, record field or GEVID row moves. The M1 laws' records over the view (`results/M2/extracted_m1`) keep the abstraction's path with the view's sha256, and stay uncovered, as now.
- **Regenerated (V7), by this recipe:**
  1. `holon diagram --milestone M2`: `gen/M2/diagram/m1_view.json`;
  2. `holon evidence --milestone M2`: `gen/M2/evidence.json`;
  3. `holon derive --milestone M2`: `laws/M2/REGISTRY.json`, its evidence_sha256 alone;
  4. `holon run --milestone M1` and `--milestone M2`, then I40's filter stage, `holon refute --milestone M3 --only filter`: every M1 and M2 record, generator_sha256 and seconds alone (I66's code is in the holon-ir/0.2 and 0.3 generator closures). `results/M3/refute/filter.json` stays unchanged. A commit that changes records carries them with the filter stage re-applied.
     - `holon lean` need not run. All 16 M1 records and 8 of the 12 M2 records carry a lean4 kernel entry, and `holon run` rebuilds each from the committed Lean report (`gen/M1/lean/report.json`, `gen/M2/lean/report.json`; `holon.lean.kernel_entry_v2`). The report backs the entry while the Lean text emitted now has the report's source_sha256 and the record has the report's verdict, statement hash and main theorem.
     - That text reads the law, its facts document, the Lean twin libraries (`holon.gen.lean_machine.lib_twin`, a path rule of its own, not `targetlib`), the oracle parameters and the SORT-site entries. I66 changes none of these, and the Lean emitters import none of I66's modules. So every lean4 entry is rebuilt as it is, which R2 requires.
  5. `holon profile --milestone T32` (I32): the five records of `results/T32`, generator_sha256 and seconds alone. I66's code is also in I32's generator closure (`holon.profile.generator_files`: 124 files at the base). `laws/T32`, `gen/T32`, `results/T32/summary.json` and `gen/M3/disch/classification.json` stay byte-identical. Without this step, I32's C1 (`tests_m3/test_disch_profile.py::TestRun.test_c1_runs_and_regenerates_byte_identically`) would fail: it compares a fresh run's records with the committed ones up to seconds.
  6. `holon historical exit --milestone M2`: `results/M2/m2_exit.json` and `docs/M2_EXIT.md`. I23's coverage lists every CODEC, CONS and TRANS edge of every diagram under `gen/M2/diagram/`, so the view's 11 edges join `not_replayed`.
- **I23's wording for a generated view (V7).** For the two replayed actions (commitBatch, finalizeBatch), I23's generic text would call the view "the hand abstraction of X", which is false. The build fixes `holon/historical/exit_report.py` (in no generator closure) by a rule: for a diagram whose `provenance.extraction` names a window declaration, the why reads "the window view's X (gen/M2/extracted/m1_view.json, <its extraction method>); its extracted counterpart ... was replayed ...". A hand abstraction's why does not change, and neither does any other why.
- **M3 records (V7).** I66 re-makes no M3 record. Its code is also in every M3 generator closure (GEN3 and, with it, GEN_FACT, GEN_UNDO and GEN_DISCH; holon-ir/0.3 for the PAR records). So after the build every M3 record's generator_sha256 trails the closures. That is accepted practice: I65's build head already leaves all M3 records trailing, and I43 let typed records trail (gap LP-G9). The next M3 re-make refreshes them: it is planned with I28's build (holon-rules/1.6) and the F40 and I67 re-makes. Until then the full M3 gate's G1 (`holon/fact/gate.py` rerun_problems, `holon/sorts/gate3.py` G1) fails on that staleness. CI's M3 jobs (gate-M3-partial, gate-M3-G2 and tests-m3-catalog) run no G1.

## What was known before this prereg (disclosed)

- **Nothing was run on the subject.** No generator, `holon diagram`, `holon evidence`, `holon derive`, `holon run`, gate or Bend run built the view's diagram or its evidence model, and no code for either exists yet. What was run:
  - the prereg audits and the freeze check;
  - `tests_m2/test_evidence.py` with I14's amendments: 23 OK. It builds the existing set, which has no view;
  - `holon.diagram.evidence.law_evidence` and the instrument's `law_atoms` on the committed set (not the view's model): equal for every law of laws/M0-M2 and for the probe with its facts set to the abstraction's (covered, named `[TRANS.challengeState]`, 35 relevant atoms: 32 E2, 2 E6, 1 E5; levels `[E2, E5, E6]`). I65's derived law, facts likewise: named `[]`, levels `[]`;
  - the instrument on committed inputs: its anchors rule reproduces the committed anchors of the three fact-document models; the view equals its abstraction without the recorded guards; its E3 re-indexing gives the 8 of P2; its library rule gives today's `lib_files` for every document but the view;
  - at the base, outside the view: the four toy and in-memory evidence sets of V5 (their render hashes are pinned in the key), `holon diagram` over the fact documents in a light copy (byte-identical diagrams), `holon evidence` in a light copy with the abstraction's diagram stripped of its ledger links and HASH debt (same model, atoms and unresolved entries), M3's evidence set rebuilt (byte-identical), and the generator closures and M3 record digests;
  - the I43 amendment's helper on simulated registry variants;
  - after the base moved to e215fbf5 (I32's build), every pin and computed number of the key again: the view, its declaration, the abstraction and its diagram, `gen/M2/evidence.json` (sha256, evidence_sha256, 230 atoms, 74 unresolved entries, 13 inputs), the registry, the four toy-set renders, M3's derivation inputs (55, all current) and evidence set (rebuilt byte for byte), the closures and record digests, the Lean entries and I43's known red; and I32's own tests where I66 meets them: I32-R2's test, original and amended, and the T32 generator closure (124 files, holding I66's code; the five T32 records current).
- **How the predictions were made.** I read:
  - the abstraction's committed evidence model (`gen/M2/evidence.json`, morph_rollup: 174 E2, 9 E3, 2 E4, 14 E5 and 11 E6 atoms, 68 unresolved entries) and its diagram;
  - the removed requires: their state reads are qlen, D, t, qpend and paused, besides the lets the actions keep;
  - the calculus' code (`holon/diagram/evidence.py`, `access.py`, `build.py`).

  A removed require changes only its own TRANS edge's reads. Writes, lets, effects, observers, migrations and consumers are untouched. So E2 can only lose relations, an endpoint whose reads cannot change keeps its atoms exactly, E6 reads names only, E4's recomputations sit in kept guards, and E3 atoms move to their guards' new indices. The probe's 32 E2 atoms at `TRANS.challengeState` carry over because challengeState keeps all its guards and no removed require reads bc, chs, inch or win.
- **What counts as a prediction.** Only claims that could fail other than by implementing V2-V5 as written, and that no construction check entails, are predictions. One is left: P2, the view's E3, E4 and E6 inventories, counts and positions that the instrument computes and that the build's unchanged I14 code computes independently, as I14 counted its own P5 and P6.
  - What follows from V2-V7 by construction is checked as construction, R4 and R5, not counted: the view's diagram, the set's shape, E2 at challengeState and at the unchanged endpoints, the derived law, the toy sets and the exit wording.
  - The probe's levels and relevant atoms over the view were P1 in the first fold. They follow from R5's E2 check at challengeState, P2 and V6, so the probe check is now part of R5 (the verification's finding N3). The id I66-P1 is not reused.
  - What P2 risks: the calculus attributes or indexes the view's guards differently from the instrument (E3), attributes a recomputation or a stored value differently (E4), or tokenizes the view's edges differently (E6).
- **The probe** (`tests_m3/fixtures/view_evidence/L_probe_view_challenge.json`) is a law IR fixture, never registered, run or proved, read only by law_evidence and the instrument. It names challengeState by an act term, as I65's ghost term will once I65's build reads it in L2.
- **Code and documents read:**
  - `holon/diagram/` (`__init__`, `build`, `access`, `evidence`, `linked`), `holon/gen/targetlib.py`, `holon/window.py`, `holon/differential.py`;
  - `holon/mpipeline.py` (run_m1's anchor), `holon/records.py` (generator closures, bundles), `holon/gate.py` (G1's M2 outputs, GEVID), `holon/rules/__init__.py` (the registry's evidence_sha256, `_given_par_inputs`), `holon/codecrun.py`, `holon/rules/par_lossy.py`, `holon/historical/exit_report.py`, `holon/lean.py`, `holon/fact/gate.py` and `holon/sorts/gate3.py` (the M3 G1), `.github/workflows/holon-ci.yml` (the M3 jobs);
  - `holon/audit/prereg.py`;
  - the tests of I11, I13, I14, I15, I20, I21, I23, I24, I25, I40, I43, I62, I64 and I65 that read diagrams, the evidence set or the registry;
  - `docs/iterations/I20.md` and `I26.md`, and I65's build (85d91d70, e57fa11d) for the anchor.

## Risks

- **The view's ledger.** No ledger bundle has the view's sha256, so its diagram carries LEDGER coverage debt instead of links, and no HASH debt. That is honest for this base. I65's ledger anchor will rewrite the view's diagram, and so `gen/M2/evidence.json`'s input entry for it. R5 checks, on the view's diagram and on the abstraction's (which has ledger links and HASH debt), that a model's anchors and atoms do not depend on them, so I65 moves neither evidence_sha256 nor the registry.
- **Closure churn.** Every M1, M2 and T32 record is re-made for generator_sha256, as I26 did for M1 and M2 and I65 will do; whichever lands second re-makes them again. The M3 records trail until the next M3 re-make (V7).
- **I32's tests.** I32 merged into the base with T32's records and a regression, I32-R2, whose test diffed the I32 prereg against HEAD. I66's closure files and re-made M1 records would count against I32 there, so the test is amended to I32's own commits (V8). I32's C1 regenerates T32 and compares records with the committed ones, so V7 re-makes the T32 records.
- **The I43 sidecar test** already fails at the base (e215fbf5, as at fde1f819): 103 laws/M3 inputs moved by I26's catalog bump (I26's Question 5) and two typed M3 records' baselines. I66's amendment covers only the M2 registry's evidence_sha256.
- **The merge.** If this pull request's commits landed on the first-parent line between I65's prereg and I65's end, I65's own-commit regressions would count them (I65-R2 allows only the derived law's registry entries). It merges with a merge commit, which the coordinator guarantees.

## Predictions (key I66 in `spec/M3/predictions.json`)

One counted prediction (I66-P1 moved to R5; its id is not reused):
- **P2.** The view's E6 (11) and E4 (2) atoms are the abstraction's. Its E3 atoms are 8, re-indexed: finalizeBatch's guards[14] goes with its removed require, and commitState's move to [16] and [17].

**Regressions:**
- **R1.** No law's computed evidence or record evidence field moves, and the view records stay uncovered. GEVID passes on M0 and M1 (report-only) and on M2 (enforcing). The registry's evidence_sha256 is the set's.
- **R2.** I66's own commits change only what V7 allows: the M1, M2 and T32 records in generator_sha256 alone, the registry in evidence_sha256 alone, `gen/M2` in the view's diagram and the evidence set, and nothing under `spec/M3/` (but its amendments file), `spec/schemas/`, `audit/`, `replay/`, `results/M3/`, `laws/T32/`, `gen/T32/` or `results/T32/summary.json`. No M3 record is re-made, so every M3 record's generator_sha256 trails I66's closures after the build (V7). Each commit that changes `results/M2/m2_exit.json` changes only the view's not-replayed entries, judged against its parent. At I66's end those entries are the view's 11 edges, and none says "the hand abstraction".
- **R3.**
  - The gates' GEVID passes on M0, M1 and M2, and `holon historical exit --check` passes.
  - Gates M0, M1 and M2 pass in full on the build head.
  - CI's three M3 jobs, as at the base, I66 adding no failure:
    - gate-M3-partial and gate-M3-G2 run no G1. gate-M3-partial fails only G11V on Q36's law, and gate-M3-G2 passes.
    - tests-m3-catalog (`tests_m3.test_catalog_rederivation`: M3's registry tie to `laws/STATEMENT_DIFF.jsonl`, the lines the tool generates, the typed bindings, and gate3's G2 on a clone) passes, as in I26's final CI run. It reads only M3's laws, registry, bindings, records and generated files, the statement-diff log and the history, none of which I66 changes, and it derives through no library lookup that I66 changes (no M3 law's facts is a window view; R4).
  - The frozen suite, freeze-check and both prereg audits pass.
  - The full M3 gate is not claimed. It was never run on the base (I26's Question 1), and after I66 its G1 fails on the M3 records' staleness until the next M3 re-make.
- **R4.** Construction checks:
  - the instruments' pins; the view against its abstraction; the probe's validity; the instrument's L1-L4 equal to holon's on every committed M0-M2 law;
  - window_views by declaration, and a copy without the view gives the prereg's evidence set byte for byte;
  - I65's anchor for the view, and lib_files unchanged for every facts path a law names and every document under `gen/M2/extracted/`, `facts/` and `spec/M*/facts/`;
  - the view is no fact document, and gen/M2/sorts is unchanged;
  - no own commit changes an input of M3's derivation or evidence set, and M3's set rebuilds byte for byte;
  - holon/ names no I66 id, the view's file or the declaration's file.
- **R5.** Construction checks:
  - the view's diagram against the abstraction's (edges, writes, reads, guards, principal classes, inputs);
  - the set gains the model `m1_view` alone, with no E1 or E5 atom;
  - E2 at challengeState and at the 12 unchanged endpoints is the abstraction's, and elsewhere only loses relations;
  - the probe over the view is covered by `m1_view`, names `[TRANS.challengeState]`, has the view's 10 TRANS edges as context and computes `[E2, E6]`, by holon and by the instrument alike; its 34 relevant atoms (32 E2, 2 E6) are the abstraction's for the same probe, without the E5 atom (I66-P1 until the verification);
  - I65's derived law names nothing while `docs/iterations/I65.md` is absent, and the probe's edge and levels once it exists;
  - the test-milestone and in-memory sets model no view and render as at the prereg;
  - a stem collision is refused by both CLIs;
  - the CLI is the build API, and it is deterministic;
  - neither model depends on ledger links or LEDGER and HASH debt;
  - the exit document's wording for the view;
  - the re-make reached every M1, M2 and T32 record (one new generator_sha256 per milestone at I66's end), and T32's other outputs are the prereg's.

## Earlier tests, amended in this prereg's pull request (V8)

Each amended test is narrowed to I66's outcomes, with its line in its own key's amendments file. At the prereg there is no view model, so each checks what it checked before.

- **I14** (`spec/M2/amendments.jsonl`), in a later commit of this pull request, because an M3 prereg commit may not touch `tests_m2/`:
  - the header test and the inputs test admit a window view's model and inputs;
  - the E3/E5 node test reads facts through the document's model;
  - the E6 tokenizer test covers the views' diagrams;
  - the E3 and E4 inventories count the fact documents' atoms. The words of I14-P5 ("exactly 9 E3 atoms") and I14-P6 ("exactly 2 E4 atoms") then describe the fact documents' atoms, not the whole set, which holds 17 and 4 after I66. The view's are checked exactly by I66-P2, so nothing goes unchecked.
- **I43** (`spec/M3/amendments.jsonl`, in the prereg commit): the sidecar test accepts the M2 registry when only its evidence_sha256 moved, to the evidence_sha256 of the committed set at the commit under test, which must be that set's own body hash. So it accepts the registry following any rebuild of the set; no claim of I43 reads that field.
- **I32** (`spec/M3/amendments.jsonl`, in the prereg commit): I32-R2's test (`tests_m3/test_disch_profile.py::TestRegressions.test_r2_no_closure_and_no_earlier_output_changes`) diffed the I32 prereg against HEAD, so it would count I66's closure files and re-made M1 records as I32's.
  - It now finds I32's own commits by ancestry, whatever the topology. R is the oldest commit that adds `docs/iterations/I32.md` (27d08ab8). M is the oldest merge on R..HEAD's ancestry path whose second parent reaches R and whose first parent does not (e215fbf5). The own commits are the non-merge commits of `git log --first-parent M^2 ^M^1 ^<prereg>`: the seven, 6f1e076e to c164ba51.
  - Its closure and earlier-output checks run over those commits. M1's `L_disch_delay_*` records at M^2 must equal the prereg's, but for generator_sha256 and keys named seconds.
  - This narrows it beyond I66's outcomes: later keys' commits are judged by their own regressions (I66-R2 here). Both forms pass at the base, and the selection gives the same seven commits on the lead, on branches based before e215fbf5 that merge it, and on branches based after it.

No other earlier test is amended. One that fails on I66's outcomes is a miss, reported.

## Deliverables

- **Code:**
  - `holon/gen/targetlib.py` (V3: I65's code, verbatim; its docstrings, the module's window paragraph included, say "libraries" only where I65's say "libraries and hints", since `hints_for` is I65's);
  - `holon/diagram/__init__.py` (`window_views`, `run`), and `holon/diagram/build.py` where the declaration must be listed as an input (V4);
  - `holon/diagram/evidence.py` (V5, and its module docstring's "Window views (I66)" paragraph, as I20 added "Adopted transitions documents");
  - `holon/historical/exit_report.py` (V7's wording, and its module docstring).
  - `spec/schemas/evidence.schema.json` needs no constraint change: its diagram pattern and facts_version enum already admit the view.
- **Outcomes:** `gen/M2/diagram/m1_view.json`, `gen/M2/evidence.json`, `laws/M2/REGISTRY.json`, the M1, M2 and T32 records, `results/M2/m2_exit.json`, `docs/M2_EXIT.md`, `docs/iterations/I66.md`.
- **One fresh build review.**

## Not in I66

- **The ghost term's reading in rule L2**, which is I65's build. It names its action's TRANS edge, as an act term does. It also changes I14's contract text: L2 says "every other term names nothing".
- **The rest of I65's anchor** (85d91d70, e57fa11d): `hints_for`, `holon.audit.regress.lib_docs_at` (until I65 lands, it applies the path rule to the view, while `lib_files` anchors it), the ledger bundle, the generator closures' `spec/*/lib/window_*.json` entry (the declaration now decides the view's libraries but is in no closure) and the Lean twin library. None matters at I66: no committed law names the view, and holon.differential's runs already take the abstraction as their anchor (`holon.mpipeline.run_m1`).
- **E5 for window views.** That needs a sorts assignment of the view: either I13's pass run over it, or a rule that it inherits its abstraction's. Either is a calculus change for the human (Questions).
- **Covering the M1 laws' records over the view.** That would change L1 (a lookup by sha256).
- **Atoms for I20's adopted 0.3 documents.** That needs a 0.3 diagram adapter, I20's Question 5.
- **Refreshing the M3 records' generator_sha256**, the next M3 re-make's (V7).

## Coordination

- **I65's build** rebases onto I66's merge. `holon/gen/targetlib.py` then differs from I65's only in `hints_for`. I65 adds the rest of its anchor and the ghost L2 rule. With that rule, the derived law names `TRANS.challengeState` and computes `[E2, E6]`, the probe's levels (R5), so its metadata `E2` holds under GEVID. Its code is in the same closures, so it re-makes the M1, M2 and T32 records again.
- **I26** (merged at 9bb2eac7), **I32** (prereg at 476b02bc; build merged at e215fbf5, the base) and PR #44 (an I43 follow-up at fde1f819: docs/iterations/I43.md and I43's sidecar) touch no input of M2's evidence set. Between 25303315 and e215fbf5, `gen/M2`, `laws/M2`, the view and `holon/diagram` are unchanged, and the M1 and M2 records moved only in generator_sha256 and seconds (not at all after fde1f819). Every pin of the key holds at e215fbf5.
- **The M3 re-make** that refreshes the M3 records' generator_sha256 is planned with I28's build (holon-rules/1.6) and the F40 and I67 re-makes.

## Questions for the human

1. **E5 for window views.** V5 gives a view no E5 atom, because no sorts assignment names it. Two consequences follow. Over the view, a law whose only atoms stronger than E6 would be E5 atoms has max E6, so a REFUTED one is triaged intent_question where over the abstraction it is a finding. And inheriting the abstraction's assignment is not obviously sound: I13's constraints come partly from the removed requires (`tot + n <= qlen`, `ef + D < t`, `qpend == btot - bn`), so a fresh pass over the view could assign different sorts. Should a later key give views E5, and how?
2. **The M1 laws' records over the view stay uncovered.** They name the abstraction's path with the view's sha256, so L1 finds no model for them. Covering them needs L1 to match by sha256, a calculus change. GEVID reads none of them, so nothing fails. Leave them uncovered?

## Rules

- AGENTS.md throughout. Never write under `schemas/` or another frozen root, and never run `tools/freeze.py write`.
- The instrument `tests_m3/_i66.py` and the fixture are fixed at this commit. A wrong instrument is a Question plus an amendment line, never a silent edit.
- Earlier keys' tests change only as V8 says.
- A missed prediction is a result.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
