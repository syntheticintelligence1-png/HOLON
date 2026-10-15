"""I43 part B: Lean for the promoted set (whitepaper §8.8, §8.9; BUILD_PLAN I43: "Lean emitters for the set Q8
promotes ... Records gain I2"; docs/HUMAN_ANSWERS.md Q8: "Every PROVED law. A law that Lean cannot check within budget
stays single-kernel (I1), with the reason recorded: timeout, recursion depth, or an unsupported form. Cross-kernel
coverage is reported as a metric. A cross-kernel disagreement is a blocking finding."). This docstring is the contract
that tests_m3/test_lean_promoted.py checks; part A (theory core II) is tests_m3/test_theory_core2.py.

Instruments fixed at the prereg: tests_m3/_i43.py (rules L0-L4, L7 and L9's canaries written out a second time,
independently of holon/: the scope, the model interfaces, the Lean statement of every in-scope law rendered from its
IR, the file rules, the differential samples with the values the compiled Bend models compute on them, the perturb
canaries with their Bend evidence, the site canaries of rule L11 (whose mutated Bend models holon's own Bend side builds
in a subprocess); and the readers the tests judge with, none taken from holon/lean.py, which I43 edits: the Lean
toolchain resolution (Lean 4.34.0 under ~/.elan and its fingerprint, frozen in the instrument), the banned words
LEAN_BANNED and the indented-command rule, the Lean check with a random sentinel and the axiom audit (lean_check), the
semantic-rejection and resource-limit readings with their probes, the Python import reader (import_closure), and the
independent review's cheat files as fixtures) and the frozen sidecar spec/M3/lib/lean_promoted.json
(tests_m3/_i43.py::promoted_doc; the tests compare parsed JSON, never the file's text). tests_m2/_i15.py, which rule R4
reads, is pinned by its sha256.

Disclosure. A read-only design survey run before this prereg (nothing of it is committed) wrote throwaway Lean models
and proofs and checked, in Lean 4.34.0: M1's 8 PROVED laws, the 7 PROVED laws of the window view (M2/extracted_m1), the
view's L_disch_delay_nofree counter-law at n = 1, and five M3 PAR laws (four round trips and one pinned cross-component
law, under informal names). The M1 and view laws are therefore regression I43-R11, not a prediction; the five M3 laws
cannot be matched to law ids reliably, so I43-P1 is scored on all 73 and says so. M2's six SORT-site laws were not
probed (no Lean reading of the site semantics existed), so I43-P2 is not; nor were the REFUTED counter-laws but the
one above (I43-P3), the frozen statement texts, interfaces, naming and differential, which differ from the survey's.
Since the second review (m8) the predictions are these three; part A's theory core II is construction (I43-R12),
every statement of it having been proved before this commit.
The independent review of the first draft ran the survey's models, renamed to the frozen interface, on the M1 and M3
differential samples (all proved by decide; nothing of it is committed).

What the plan asks and what the tree holds (computed at the prereg; spec/M3/lib/lean_promoted.json "counts")
  PROVED records: results/M1 8, results/M2 6, results/M2/extracted_m1 7 (I20's re-run of the M1 laws on the window view
  of the extracted model: PROVED records of M2, so Q8's "no hand-picked subset" covers them), results/M3 73 (the PAR
  laws over the linked codec component header_length): 94 laws. REFUTED records: 8, 2, 7 and 9; 21 of them are over
  model kinds the Lean emitters cover (L1) and are attempted as counter-laws at their recorded witnesses (counted for
  disagreement, never for coverage); the other 5 (M3: I30's typed laws L_sort_realize_rollup_363_4a64383b and
  L_sort_tag_rollup_279_e01ea84a, and I27's three REFUTED UNDO laws, over the typed and UNDO models) are not.
  Bend proof classes of the 94: evaluate, nat_split, noninterference, deadline, chain_revert (M1, the view),
  coercion_guard (M2), open_refl (M3). Stale statement hashes on the integration line be95d6d (this prereg's base): I31's holon-rules/1.4
  rebinding moved laws/M3/REGISTRY.json again, regenerating nothing. The 80 M3 PAR records and their 77 LAWS.bend files
  (the three PAR-weak laws have none) carry older statement hashes, as do I30's 3 typed and I27's 8 UNDO records and
  their LAWS.bend files. I43 regenerates the PAR records (they gain lean4) and brings their 80 hashes to the registry
  (regression R1). It leaves the typed, UNDO and DISCH records as they are (gap LP-G9).
  Generator closures: holon/lean.py is in the holon-ir/0.2 and 0.3 closures (holon.records.generator_files: mlaws ->
  sorts/sites -> mpipeline -> intake -> lean) and in run3's GEN3 closure (holon.sorts.run3.generator_sha256), which
  I27's UNDO closure (holon.undo.run.generator_sha256) contains. So I43's edit of holon/lean.py changes the generator
  hash of every M1-M3 record it regenerates (gap LP-G7: at be95d6d the M1 and M2 records carry the current closures'
  hashes, F36 having regenerated them), and moves run3's, the UNDO and the DISCH closures under I30's 3 typed, I27's
  8 UNDO and I31's 35 DISCH records (stale already at be95d6d: the typed ones carry 8c224786..., run3's closure is
  98c5af30...; the UNDO ones 03ffc198..., the UNDO closure 50f85e03...; the DISCH ones 5ceefbd0... and 2c9d9596...,
  the DISCH closure d3351397...), which I43 does not regenerate (gap LP-G9: regenerating them runs their models and
  replays, which need the full replay toolchain).

CLI (every JSON file: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; deterministic; no timings in committed files)
  python -m holon lean --milestone <M0|M1|M2|M3> [--root DIR] [--jobs N] [--json] [--check | --emit-only]
    M0 as I9 (unchanged, byte for byte). M1 writes gen/M1/lean/; M2 writes gen/M2/lean/ (results/M2) and
    gen/M2/extracted/m1/lean/ (results/M2/extracted_m1); M3 writes gen/M3/lean/ (results/M3, the linked kind). Each
    such directory holds <law id>.lean for every attempted law of its records (rule L0) that the emitters can express
    (a law they cannot has no file, and its record says unsupported_form), models/<model stem>.lean for every Bend
    model its laws use (rule L4) and report.json (rule L6), nothing else; `holon lean` owns these directories.
    --check re-emits every file in memory, runs no Lean, and exits 0 iff every committed .lean file equals its
    re-emission and no other .lean file is there (1 otherwise). --emit-only writes every Lean file of the milestone's
    Lean directories from the documents as they are, runs no Lean, writes no report and refuses nothing over a stale
    record, report or facts hash (rule L11 runs it on a copy whose facts document is mutated); exit 0 when written.
    The emission never reads the sidecars spec/M3/lib/lean_promoted.json or theory_core2.json, nor anything under
    tests_m3/ (TestCode runs --check in a copy without them). Regeneration order, as I9: holon run (Bend), holon
    lean, holon run again (the records read the report); for M2 also holon differential --milestone M2; for M3 holon
    run --milestone M3 --laws <the PAR law ids> (I30's typed and I27's UNDO records are not regenerated, gap LP-G9);
    then holon metrics.

Rules (holon/lean.py, holon/gen/lean_machine.py, lean_mlaws.py, lean_mproofs.py, lean_sites.py, lean_linked.py,
holon/records.py, holon/gate.py, holon/sorts/gate3.py, holon/metrics.py; tests_m3/_i43.py writes L0-L4, L7 and L9's
canaries again)
  L0 Scope (tests_m3/_i43.py::scope; sidecar "laws"). Every PROVED and REFUTED record of results/M1, results/M2,
     results/M2/extracted_m1 and results/M3, with its law file (laws/M1 for M1 and the view, laws/M2, laws/M3), its
     registry statement hash, rule, sub-form, the Bend proof class of its verdict (the generator of its successful
     proof or counter-law attempt), its facts document (the law's "facts"; for the view gen/M2/extracted/m1_view.json),
     its Bend model (the record's artifacts.model), its model kind (L1) and its Lean file <lean dir>/<law id>.lean. A
     PROVED law is attempted always, but I31's DISCH laws (rule DISCH, stated over a holon-facts/0.3 document,
     which no Lean emitter reads) are not attempted, PROVED or REFUTED (the human's answer at the move onto
     be95d6d; _i43.DISCH_NOT_ATTEMPTED). A REFUTED law is attempted when its model kind is covered and rule L3
     renders it.
  L1 Model kinds and emitters. machine: a holon-facts/0.2 machine document under holon-ir/0.2 (holon/gen/lean_machine.py
     for the model, holon/gen/lean_mlaws.py for statements, holon/gen/lean_mproofs.py for the classes evaluate,
     nat_split, noninterference, deadline, chain_revert and counter_decide); machine_oracle: the same document under
     holon-ir/0.3, with the modelled oracle parameters of spec/M2/lib/oracles.json as model parameters (also
     holon/gen/lean_sites.py: the SORT site and hit predicates per rules R8-R10 of holon.sorts.sites, read again, over
     the raw obligations, and the coercion_guard proofs); linked: a holon-linked codec document
     (holon/gen/lean_linked.py: model, statements, open_refl and counter proofs). These modules read the documents
     themselves. Independence (tests_m3/_i43.py::independence_violations over import_closure, review M3): no file of the
     transitive import closure of the five emitters and of holon/lean.py (every import statement at any depth; relative
     imports at any level; `from X import y` with y a submodule; helper modules followed) imports
     holon/gen/{machine,mlaws,mproofs,linked,coercion,core,refs,model,laws,proofs,oracles}.py or holon/sorts/*, nor
     tests, tests_m* or tests.reference, and none uses a dynamic import or reflection (importlib, __import__,
     import_module, exec, eval, runpy, sys.modules, getattr, vars, globals, __dict__, ...); an attribute chain from an
     imported name (`import holon.gen` then holon.gen.mlaws) counts as importing what it names (review 2, m2).
     Genericity: the emitters, holon/lean.py and every other holon/gen/lean_*.py module of that closure name no target
     (no compound name of the M1/M2 fact documents, libraries or M3 linked components, no quoted target name but the
     formats' own words Bool, Bytes, log, who, version and the reason timeout (and, in I9's M0 emitters lean_model.py,
     lean_laws.py and lean_proofs.py, M0's own Header and Fields), no law id, no target source file). No file under
     holon/ names spec/M3/lib/lean_promoted.json, theory_core2.json or the instrument (review M4); a name split across
     string pieces evades this textual check (a stated residual, review 2 m3: the emission is also checked in a copy
     without the sidecars and without tests_m3/). The target library's Lean twin is hand-written target input under
     spec/M1/lib/ in a file not matching *.lib.json (outside the generator closures' glob). An emitter that cannot
     express a form raises an unsupported-form error, which becomes reason unsupported_form (L8), never a silent
     fallback.
  L2 Interfaces (tests_m3/_i43.py::interface; sidecar models.<key>.interface). Per Bend model, the Lean names every
     emitted model of it provides, inside `namespace Model`: the frozen data types ("types": Obs, T_<record>, St, Act
     with deriving DecidableEq; or Cell, Bytes and R_<carrier>), the frozen statement-level declarations ("decls": the
     views V_<..> and view_<..> a noninterference statement names; Reach for machine_oracle), each verbatim, and the
     signatures ("signatures": name, type), each the type of the model's definition of that name. For every site
     predicate site_<x> the interface also has ro_<x> (review M1): the site's raw obligation, subtrahend <= minuend of
     the site's subtraction (laws/<M>/DERIVATION.json basis.expr) as a Bool function of its free variables in order of
     first occurrence (tests_m3/_i43.py::obligation_vars: Nat for an operand of + or -, the parameter's type for an
     argument of a facts definition call), the facts' Nat arithmetic (- truncated) and the model's own reading of each
     facts definition, with no path condition. Naming (sidecar "naming"): Model namespace; facts names under fixed
     prefixes (T_, f_, a_, i_, ob_, mig_, fn_, site_, hit_, ro_, R_, c_, c_ok_, V_, view_, v_, p_), so no generated
     identifier is a Lean keyword or a word of tests_m3/_i43.py::LEAN_BANNED; never an escaped identifier.
  L3 Statements (tests_m3/_i43.py::Render; sidecar laws[].statements). Rendered from the IR alone: binders in IR order
     with the oracle parameters first (Lean functions, the IR's reading of Fn<A,B>), a Reach binder as a state and the
     hypothesis Model.Reach <parameters> <state>, premises as hypotheses (as I9), claim eq/neq as =/≠, a conjunction
     as ∧; terms as the interface's functions, a view equation through view_<..>, a linked field as the list of its
     byte cells (some v.f_<F>_<k>) and a byte constant as a list of some 0x..; a PROVED law is `theorem <law id> :
     <statement>`; a REFUTED law is `theorem <law id>_counter : ∃ <binders>, <premises> ∧ <negated claim>` and
     `theorem <law id>_refuted : ¬ (<statement>)`. The texts are frozen; whitespace is not significant.
  L4 Files. Every .lean file under each Lean directory (gen/M1/lean, gen/M2/lean, gen/M2/extracted/m1/lean, gen/M3/lean;
     their models/ subdirectories included; review m6) is a law file <law id>.lean of an attempted law or a model file
     models/<model stem>.lean of one of its Bend models, and obeys tests_m3/_i43.py::file_violations, read comment-free
     by tests_m3/_i43.py::lean_code (an escaped identifier kept whole): no # anywhere in the code (no #eval, #exit or
     #print command, no array or BitVec literal: write (n : BitVec w)); no word of tests_m3/_i43.py::LEAN_BANNED
     (sorry, admit, sorryAx, native_decide, axiom, unsafe*, implemented_by, extern, opaque, partial, macro,
     macro_rules, syntax, elab, notation, infix*, prefix, postfix, attribute, instance, import, run_cmd, initialize,
     IO, Process, System, Lean, ...); no escaped identifier, attribute or string literal; none of the words instance,
     attribute, variable, include, omit, universe, open, export, section, local, scoped, private, protected, mutual,
     class, axiom, opaque, unsafe, partial, import, sorry, admit; first `set_option autoImplicit false`, then only
     set_option maxRecDepth|maxHeartbeats lines, then one `namespace Model` block (column-0 lines: def, noncomputable
     def, theorem, structure, inductive, abbrev, deriving, |, termination_by, decreasing_by, set_option
     maxRecDepth|maxHeartbeats <n> in) closed by one `end Model`; no indented line starts with a command keyword
     (tests_m3/_i43.py::INDENTED_COMMAND: theorem, lemma, def, abbrev, instance, axiom, example, opaque, structure,
     inductive, class, namespace, section, end, open, variable, universe, noncomputable, private, protected, mutual,
     attribute, macro, syntax, notation, initialize, export, import, and set_option unless followed by in on its line,
     its tactic form; review 2, m1); a model file ends there; a law file then has the
     marker line `-- holon:theorems` and only theorem, def, noncomputable def, example, |, termination_by,
     decreasing_by and set_option maxRecDepth|maxHeartbeats <n> [in] column-0 lines, without the words namespace, end,
     structure, inductive, abbrev, deriving. Every set_option is `autoImplicit false`, `maxRecDepth <n>` or
     `maxHeartbeats <n>`. The model section declares no name the frozen texts use from outside the interface
     (tests_m3/_i43.py::shadow_violations: a Model.Nat would change what a verbatim St means). Each frozen theorem of
     the law (L3) is declared exactly once with exactly its frozen statement. The model section contains, verbatim
     (comment-free, whitespace normalized), every frozen type and declaration the statements need
     (tests_m3/_i43.py::required_names), and any declaration named like a frozen one is that one. Every site_<x> it
     declares reaches ro_<x> through its declarations (tests_m3/_i43.py::site_reach_violations). Model consistency:
     every top-level declaration of a law file's model section is, verbatim, a declaration of its model file
     <lean dir>/models/<model stem>.lean (so the differential of the model file, L7, covers every law file).
  L5 Elaborated types. In the law file, each frozen theorem's type (`#check @<name>` under pp.all) equals its type
     elaborated from the frozen statement over the interface stub (tests_m3/_i43.py::stub_text: the frozen types and
     declarations, every signature as an axiom; test-only, never committed), and each required signature's definition
     has the frozen type (`example : <type> := @Model.<name>`).
  L6 Checking and the report. holon lean checks each law file and model file in a fresh lake project
     (holon.lean.check_text): result checked when Lean accepts it, every declared theorem audited by its bare name with
     axioms within {propext, Quot.sound}, within lean.budget_s_per_file (120 s). <lean dir>/report.json: {"dir",
     "milestone", "kernel": "lean4", "lean_version", "toolchain", "fingerprint", "allowed_axioms", "laws": {law id:
     {"result", "axioms", "verdict", "statement_hash", "source", "source_sha256", "theorems", "main", "generator",
     "reason"?, "detail"?}}, "models": {model stem: {"source", "source_sha256", "result"}}}; no timings.
     holon.lean.strip_comments lexes an escaped identifier «...» as one token, so «/-» opens no comment (I42
     Question 5): Lean G3 sees the code after it. holon.lean.applicable keeps its meaning for the intake (the
     holon-ir/0.1 header laws: tests_m3/test_intake.py's I41-R3 pins required_kernels(M1/M2) without lean4): the set
     I43 covers is a function of its own (review 2, m5), so a record the intake later decides PROVED in M1 or M2 has
     no lean4 entry until holon lean runs again (a human question). The tests judge every file with the instrument's
     own check (tests_m3/_i43.py::lean_check, review B1): the pinned lean, Lean 4.34.0 with its fingerprint frozen in
     the instrument (review 2, m4), runs the
     file (plus the test's probes) followed by a sentinel theorem with a fresh random name and `#print axioms` for every
     checked theorem and the sentinel; accepted when lean exits 0 with no error and no "declaration uses sorry", the
     audit lines end with exactly the checked theorems and the sentinel, and every printed axiom is propext or
     Quot.sound. The review's cheat files (tests_m3/_i43.py::CHEATS: a mid-line #eval that prints or exits early, a
     macro_rules that turns decide into sorryAx, forged audit lines, a wrong model that passes only with such a trick)
     are construction tests the instrument rejects.
  L7 Differential (tests_m3/_i43.py::machine_differential, linked_differential; sidecar models.<key>.differential).
     Sample inputs come from the laws and records (machine kinds: literal traces of the IR, witness and non-vacuity
     traces, actions and Reach runs, the REFUTED site laws' per-entry-point witnesses, of every attempted law over the
     same facts document (so M1's traces feed M2's instrumented model; review M1), the end states of those traces, each
     also perturbed by +1 on every top-level Nat field, one representative action per constructor, oracle tables from
     the non-vacuity witnesses; linked: zero, 0xff and seeded records, version variants of the tag field, seeded byte
     strings of lengths 0, 1, 248-250, 256-258 with first byte 0, 1, 2, 3, 255, strings with an undefined cell, and the
     witnesses), and their values are what the COMPILED BEND MODEL computes (bend evaluates a main that returns the
     list of values; no oracle). Functions: machine: run (and, with an oracle parameter, under the empty table too),
     obs, fn_runs_ok, fn_cost, fn_elapsed, fn_last_ok, every observer and migration at each sample trace's end state,
     fn_no_code on each log, step for every sample state and representative action, fn_perm, fn_is_<a> and the
     consumers on every sample action, every site and hit predicate at the representative and site-witness actions
     (at every sample state for an entry point of the site, at the first otherwise), and every raw obligation ro_<x>
     at the combinations of its free variables' values (a state field's value in each sample state; any other Nat
     variable 0, 1, 2, 3, 4 and 100); linked: every encoder on every record of its carrier, every decoder, predicate,
     loader and loader condition on every byte string. Counts per model in the sidecar (M1 morph_rollup 1290, M1
     morph_batchdata 28, M2 morph_rollup 4241, the view 1105, M3 header_length 711 samples). Every action constructor
     of a machine model succeeds in some sample (models.<key>.action_successes > 0: an ok in a sample trace's log, or
     a step sample whose log grows by ok); every hit and raw-obligation function takes both values (site_coverage).
     The Lean side: tests_m3/_i43.py::diff_lean appends the sample inputs and one theorem `Model.<fn> <args> = <value>`
     per sample to the model file; Lean must prove each by decide (the instrument's Lean check, L6). A Bend undefined
     byte 57005 is a Lean none.
  L8 Records. For every attempted law (L0), the record's kernels[] has exactly one lean4 entry {"name": "lean4",
     "version": "4.34.0", "role": "second-independent", "result": checked|not_run|failed, "source", "source_sha256",
     "theorem" (the law id, or <law id>_counter), "reading" (sidecar readings[kind]), "axioms" (checked), "reason" and
     "detail" (not_run)}; checked only when the committed report checked exactly the text emitted now;
     independence_class I2 exactly when lean4 is checked (holon.records); not_run carries a reason in {timeout,
     recursion_depth, heartbeats, unsupported_form, no_report, toolchain_unavailable} (over the budget: timeout;
     "maximum recursion depth": recursion_depth; "(deterministic) timeout ... heartbeats": heartbeats; an emitter's
     unsupported form: unsupported_form; no or stale report: no_report; no pinned toolchain: toolchain_unavailable);
     failed for every other Lean rejection, a forbidden word, bad axioms or a missing theorem. In the committed records
     (review M2) a REFUTED attempted law is checked or not_run with timeout, recursion_depth or heartbeats only (every
     counter-law is rendered, so never unsupported_form; no_report and toolchain_unavailable are transient states of a
     build, never committed), and each such resource claim reproduces (review 2, M3): the committed file, rerun by the
     instrument within the 120 s budget, reaches the claimed limit again (timeout: no verdict within 120 s;
     recursion_depth and heartbeats: Lean's own error for that limit, tests_m3/_i43.py::RESOURCE_LIMITS). UNKNOWN
     records and the 5 REFUTED records over uncovered kinds carry no lean4 entry.
     spec/schemas/result_record_v2.schema.json's kernel entries gain the optional properties reason (that enum), detail
     and reading (strings); every record of results/M1, results/M2 and results/M3 validates against it; the records of
     results/M2/extracted_m1 are exempt from the whole-record validation (review B2: their ledger_match is "derived" by
     design, as I20 built them, and tests_m2/test_ledger.py::TestDerivedFacts asserts that a derived record fails v2),
     so for their attempted records only kernels[] and independence_class are validated against the schema's definitions
     of those two properties (the UNKNOWN stub L_tag_BVH has neither). Lean entries only for target milestones
     (M<digits>), so test milestones keep their kernels (tests_m3/test_intake).
  L9 G7. For the holon-ir/0.2 and 0.3 milestones (holon/gate.py; M2's gate covers results/M2 and
     results/M2/extracted_m1) and for M3's PAR laws (holon/sorts/gate3.py): every PROVED record has exactly one lean4
     entry and I2 iff checked; every checked entry's file regenerates byte-identically and re-checks from scratch within
     the budget with allowed axioms; a not_run entry needs an allowed reason; a failed entry fails G7 (a blocking
     cross-kernel finding); without the pinned toolchain G7 fails, labelled single-kernel. The records G7 requires a
     lean4 entry of are those of I43's covered set (L6), not holon.lean.applicable's. Lean G3 scans every .lean file of
     every Lean directory of the milestone, models/ included (M2: gen/M2/lean and gen/M2/extracted/m1/lean; review
     m6), and its detail names each offending file by its repo-relative path. G7's detail reports, per lean dir,
     "cross-kernel coverage <dir key>: <checked>/<proved>" and every Lean canary as "<id> rejected (<first error>)".
     Canaries, per milestone gate (M1, M2, M3): flip:<law> (the counter-law of a checked REFUTED law with its claim's
     relation flipped) and perturb:<law>, where <law> is the sidecar's canaries.<gate>.law
     (tests_m3/_i43.py::perturb_canaries, review B3): among the gate's directories in order (M2: results/M2, then
     results/M2/extracted_m1), the PROVED laws in law-id order, the first that is of Bend class evaluate over a machine
     model without oracle parameters and whose claim has a Nat equation, or a PAR round trip without premise whose
     right side is some <field of width 2 or more>. Its perturbed statement (sidecar canaries.<gate>.text) changes,
     for an evaluate law, the right-hand constant k of the claim's first Nat equation (the claim's propositions in
     order: the claim itself, or the members of its "all" list in order; the first "eq" whose right side is a Nat
     literal and whose left side renders as a Nat term) to k + 1, and for a round trip swaps the first two cells of
     the claim's right side. The sidecar's evidence (review 2, m7): for an evaluate law, the compiled Bend model
     evaluates the left side to k at the record's witness, so the perturbed claim is false at that witness (not the
     perturbed existential false: the canary keeps the law's proof, which fixes the witness); for a round trip, the
     left side on a seeded record is the unswapped cells, which differ, so the swapped claim is false there. Each
     canary is rejected by Lean for a semantic reason. At the prereg the canaries are M1 and M2: L_disch_delay_pay
     (ob_lci_of ... = 2 becomes = 3; M2's from the view) and M3:
     L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BatchIndex_v2. The tests also build
     each canary themselves (review 2, B1): the committed law file, which must obey the law-file rules, with its frozen
     statement (from `theorem <law>` to its first `:=`, located in the comment-free reading) replaced in the raw source
     by the sidecar's perturbed statement, the proof and everything else kept (tests_m3/_i43.py::replace_statement);
     the instrument's Lean check must reject it after elaborating to the end (the sentinel's audit line present) with
     a first error the instrument reads as semantic (SEMANTIC_REJECTION: decide proved the proposition false, Not a
     definitional equality, the rfl tactic failed, a type mismatch in any case; and no NON_SEMANTIC error anywhere).
     So the law's proof must be one whose failure on the perturbed statement is semantic: decide, rfl (term or
     tactic), exact rfl, Eq.refl or fun _ => rfl, not a simp or omega that leaves goals. M0's G7 is unchanged.
  L10 Metrics. results/<M>/metrics.json (M1, M2, M3) gains cross_kernel_coverage {"proved", "lean4_checked", "rate",
     "not_run_by_reason", "failed"}; M2's also has "extracted_m1" with the same keys for results/M2/extracted_m1.
  L11 The site canary (review 2, M2; tests_m3/_i43.py::site_mutation, site_canaries, site_canary_lean; sidecar
     models.M2:morph_rollup.site_canaries). For each PROVED SORT site of M2, a mutation of the facts document strips
     the site of its protection, as spec/M1/mutations.json's MUT2 strips :363's: every condition on the way from a
     definition site's definition body to its subtraction, and every require of the action before each of the site's
     DERIVATION hits that names no caller (`who`) and is no hit itself, is kept under a constant guard (["||", true,
     e] where it must hold, ["&&", false, e] where it must fail), so the site keeps its id and hits. holon's own Bend
     side builds the mutated instrumented model (holon.sorts.sites.instrumented_model, in a subprocess, the derivation
     cut to that site); the instrument's sample is the first, over the mutated runs of the differential's traces and
     the site's entry-point actions (each of the differential's, and its one-input variants over NAT_PROBES), where
     the mutated site predicate is false; the hit predicate is true there. At the prereg all 6 sites have one. The
     test (I43-P2) applies each site's mutation to a copy of the tree, runs holon lean --milestone M2 --root <copy>
     --emit-only, and requires the re-emitted Lean model's site predicate to be false, and its hit predicate true, at
     the sample (the mutated Lean run of the trace from s0 under T1, the action), by decide, under the instrument's
     Lean check. A site predicate that ignores its obligations, or a vacuous one, fails it.

Gaps preregistered
  LP-G1 Readings (sidecar "readings", in every lean4 entry): Lean records are byte-valued where Bend's cells are U32
        (a narrower domain, I9 Surprise 5); a Fn oracle parameter is a Lean function where Bend ranges over finite
        tables (Lean's theorem implies Bend's); premises are hypotheses where Bend pins fields (equivalent).
  LP-G2 Common mode: both kernels read the same facts and IR; the Lean twin of the target library is hand-written
        target input, as the Bend library is (I9 Question 4). The second kernel is independent, the inputs are not.
  LP-G3 M2's site predicates: on every PROVED site both readings are constantly true (coercion_guard never uses
        Reach). Rule L7 pins where a site is hit (hit_<x>) and its raw obligation (ro_<x>), both taking both values
        on the samples, and rule L4 requires site_<x> to reach ro_<x>; rule L11's mutation canary shows, at one
        sample per site, that the emitted site predicate goes false when the site loses its protection (review 2,
        M2). Elsewhere how site_<x> combines hits, path conditions and obligations is pinned by the Lean proof and the
        two REFUTED sites' false values. I43-P2 scores the PROVED site laws whose hit and raw obligation take both
        values and that have a site canary (sidecar site_laws_scored: all 6).
  LP-G4 L7 is finite evidence: the Lean models agree with Bend on the samples; elsewhere agreement is not checked.
  LP-G5 The 5 REFUTED M3 records over the typed and UNDO models are not attempted (their records keep their kernels).
  LP-G6 Amended at this prereg (review m4): tests_m3/test_refute.py's I40-R2 pinned the M0-M2 and extracted_m1 records
        modulo filter_bin, concretization and generator_sha256; I43 changes their kernels and independence_class by
        design, so the prereg narrows the assertion (kernels may gain exactly one lean4 entry; independence_class may
        change only from I1-shared to I2, exactly when that entry is checked) and logs it in spec/M3/amendments.jsonl.
        Two more amendments are known at the move (the first build made them; the build makes them again): C1
        allows eta2 in holon/gen/theory2.py (tests_m2/test_target_agnostic_exhaustive.py) and C2 lets the view's
        decided records gain I41's prover field under I40-R2.
  LP-G7 Closure churn: holon/lean.py and holon/gen/lean_*.py are in the holon-ir/0.2 and 0.3 generator closures
        (mlaws -> sorts/sites -> mpipeline -> intake -> lean), so every regenerated M1-M3 record's generator_sha256
        changes (R1 tolerates it).
  LP-G8 The view's records state the M1 laws over the view's facts: their statement_hash differs from
        laws/M1/REGISTRY.json's in facts_sha256 only; the sidecar lists the registry's.
  LP-G9 Not regenerated (review 2, B3): I30's 3 typed, I27's 8 UNDO and I31's 35 DISCH M3 records, whose statement
        hashes (typed, UNDO) or generator hashes (all) are stale at be95d6d already; I43's edit of holon/lean.py moves
        their closures again. Regenerating them (holon run --milestone M3 --laws <their ids>) builds their models from
        the deployment and replays every REFUTED entry on the real contract: it needs the full replay toolchain (forge,
        solc, sol_deps, the morph checkout and the m3init deployment cache; CI installs it with
        .github/ci/install_toolchain.sh), which this environment lacks. R1 keeps all 46 records exactly as at the prereg
        (status, statement hash, generator hash, witnesses, kernels), and a human question asks the lead to regenerate
        them with that toolchain, last: any later edit of a closure leaves them stale again.
  LP-G10 Textual name checks (review 2, m3): rule L1's ban on naming the sidecars or the instrument is textual, so a
        name split across string pieces evades it; the emission is also re-checked in a copy without the sidecars and
        without tests_m3/ (R3), which an emitter reading them would fail.

Rules for the build
  - AGENTS.md is binding. The statements, interfaces and differential values are frozen; a law Lean cannot check
    stays I1 with its reason; a Lean rejection for any other reason is a failed entry, never relabelled.
  - Never edit facts/, spec/M1/facts/, laws/, frozen files; no change to any Bend file under gen/M0-M3 but the PAR
    law files' statement_hash header lines (R1); nothing under gen/M3/theory/ (part A's C5); I30's typed and I27's
    UNDO records stay as they are (LP-G9).
  - No skips: a test that needs bend, Lean or the replay toolchain fails, naming what is missing.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tests.reference import mini_schema
from tests_m2 import _i15 as I15
from tests_m3 import _i24x as X
from tests_m3 import _i43 as T
from tests_m3._m3 import ROOT, SCHEMAS, canonical_json, copy_repo, file_sha256, holon_module, load_json, run_holon

SIDECAR = ROOT / T.PROMOTED_SIDECAR
BUDGET_S = 120
ALLOWED_AXIOMS = set(T.ALLOWED_AXIOMS)
JOBS = 4
EMITTERS = ("holon/gen/lean_machine.py", "holon/gen/lean_mlaws.py", "holon/gen/lean_mproofs.py",
            "holon/gen/lean_sites.py", "holon/gen/lean_linked.py")
DIR_MILESTONE = {"M1": "M1", "M2": "M2", "M2/extracted_m1": "M2", "M3": "M3"}
# names the target vocabularies share with the formats themselves, which generic code may quote (the Bend emitters
# holon/gen/machine.py, mlaws.py and linked.py quote Bool, Bytes, log and who; holon/lean.py quotes version and the
# result timeout, rule L8's reason); I9's M0 emitters also quote M0's own Header and Fields (as at the prereg)
GENERIC_QUOTED = {"Bool", "Bytes", "log", "who", "version", "timeout"}
M0_EMITTER_QUOTED = {"holon/gen/lean_model.py": {"Header"}, "holon/gen/lean_laws.py": {"Fields", "Header"},
                     "holon/gen/lean_proofs.py": {"Header"}}
# tests_m2/_i15.py (rule R4 reads its target vocabularies) lies outside this package, so the prereg audit does not
# fingerprint it and FROZEN.sha256 does not list it: pinned here (review m5)
I15_SHA256 = "d6912d047d4ed6ad2a170e57c07bccd3d3bcac08296d6e19f0042a1fa00dbea4"
SIDECARS = ("spec/M3/lib/lean_promoted.json", "spec/M3/lib/theory_core2.json")
_SIDE: dict = {}


def side() -> dict:
    if not _SIDE:
        _SIDE.update(load_json(SIDECAR))
    return _SIDE


def entries(dkey: str | None = None, status: str | None = None) -> list[dict]:
    """The sidecar's attempted laws (L0), optionally of one directory and one status."""
    return [e for e in side()["laws"] if e["attempt"] == "lean" and (dkey is None or e["dir"] == dkey)
            and (status is None or e["status"] == status)]


def need(p: Path) -> Path:
    p = Path(p)
    if not p.exists():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing (I43 builds it)")
    return p


def lean_run(text: str, timeout: int = 900) -> tuple[str, float]:
    """Elaborate one Lean text with the pinned lean the instrument resolves (tests_m3/_i43.py::run_lean)."""
    r = T.run_lean(text, timeout)
    return r["out"], r["seconds"]


def pp_types(out: str, names: list[str]) -> dict[str, str | None]:
    """`#check @<name>` outputs under pp.all, whitespace normalized, by name (None when absent)."""
    got = {}
    for n in names:
        m = re.search(rf"(?ms)^@?{re.escape(n)} :(.*?)(?=^@?[\w.]+ :|^\S+:\d+:\d+: |^'|\Z)", out)
        got[n] = " ".join(m.group(1).split()) if m else None
    return got


_STUB: dict = {}


def stub_types(key: str) -> dict[str, str | None]:
    """Rule L5's reference: every frozen theorem of model `key`, elaborated over its interface stub, under pp.all."""
    if key not in _STUB:
        model = side()["models"][key]
        sts = [s for e in entries() if e["model_key"] == key for s in e["statements"]]
        names = [s["theorem"] for s in sts]
        out, _ = lean_run(T.stub_text(model, sts, names))
        if T.lean_errors(out):
            raise AssertionError(f"the interface stub of {key} does not elaborate: {T.lean_errors(out)[:5]}")
        _STUB[key] = pp_types(out, names)
    return _STUB[key]


def check_law_file(e: dict) -> list[str]:
    """Rules L3-L6 on one attempted law's committed file (and its record and report entries): the problems found."""
    bad = []
    model = side()["models"][e["model_key"]]
    p = ROOT / e["lean_source"]
    if not p.is_file():
        return [f"{e['lean_source']} is missing"]
    src = p.read_text(encoding="utf-8")
    bad += [f"L4: {v}" for v in T.file_check(src, "law", model) + T.site_reach_violations(src, model)]
    for s in e["statements"]:
        got = T.lean_statement(src, s["theorem"])
        if got != T.norm(s["text"]):
            bad.append(f"L3: theorem {s['theorem']} is not declared exactly once with its frozen statement")
    decls, sigs = T.required_names(model, [s["text"] for s in e["statements"]])
    frozen = {n: T.norm(t) for n, t in model["interface"]["types"] + model["interface"]["decls"]}
    mine = T.model_decls(src)
    for n in decls:
        if mine.get(n) != [frozen[n]]:
            bad.append(f"L4: the frozen declaration {n} is not in the model section exactly once, verbatim")
    for n, texts in mine.items():
        if n in frozen and texts != [frozen[n]]:
            bad.append(f"L4: a declaration named {n} is not the frozen one")
    mf = ROOT / e["lean_model"]
    if not mf.is_file():
        bad.append(f"L4: the model file {e['lean_model']} is missing")
    else:
        theirs = T.model_decls(mf.read_text(encoding="utf-8"))
        for n, texts in mine.items():
            if any(t not in theirs.get(n, []) for t in texts):
                bad.append(f"L4: model consistency: declaration {n} differs from the model file's")
    names = [s["theorem"] for s in e["statements"]]
    probe = (src.rstrip("\n") + "\n\nnamespace Model\n"
             + "".join(f"example : {dict(model['interface']['signatures'])[n]} := @{n}\n" for n in sigs)
             + "end Model\n")
    r = T.lean_check(probe, names, extra="\nset_option pp.all true\n" + "".join(f"#check @{n}\n" for n in names))
    bad += [f"L5/L6: {x}" for x in r["problems"]]
    if r["seconds"] > BUDGET_S:
        bad.append(f"L6: Lean took {r['seconds']:.1f} s, over the budget of {BUDGET_S} s")
    want, have = stub_types(e["model_key"]), pp_types(r["out"], names)
    for n in names:
        if have.get(n) is None or have.get(n) != want.get(n):
            bad.append(f"L5: the elaborated type of {n} is not the frozen statement's")
    return bad


def lean4_entry(rec: dict) -> list[dict]:
    return [k for k in rec.get("kernels", []) if k.get("name") == "lean4"]


def record_problems(e: dict, want_checked: bool) -> list[str]:
    """Rule L8 on one attempted law's record (and the report of its lean dir)."""
    bad = []
    rec = load_json(ROOT / e["record"])
    ks = lean4_entry(rec)
    if len(ks) != 1:
        return [f"L8: {len(ks)} lean4 entries"]
    k = ks[0]
    if (k.get("version"), k.get("role")) != ("4.34.0", "second-independent"):
        bad.append(f"L8: version/role {k.get('version')}/{k.get('role')}")
    if (rec.get("independence_class") == "I2") != (k.get("result") == "checked"):
        bad.append(f"L8: independence_class {rec.get('independence_class')} with lean4 {k.get('result')}")
    if k.get("reading") != side()["readings"][e["kind"]]:
        bad.append("L8: the reading is not the sidecar's for this kind")
    if k.get("result") == "not_run" and (k.get("reason") not in T.ALLOWED_REASONS or not k.get("detail")):
        bad.append(f"L8: not_run with reason {k.get('reason')!r}")
    if want_checked:
        if k.get("result") != "checked":
            return bad + [f"lean4 {k.get('result')} ({k.get('reason')}: {str(k.get('detail'))[:200]})"]
        if k.get("source") != e["lean_source"] or k.get("theorem") != e["theorem"]:
            bad.append(f"L8: source/theorem {k.get('source')}/{k.get('theorem')}")
        p = ROOT / e["lean_source"]
        if not p.is_file() or k.get("source_sha256") != file_sha256(p):
            bad.append("L8: source_sha256 is not the committed file's")
        if not set(k.get("axioms", ["?"])) <= ALLOWED_AXIOMS:
            bad.append(f"L8: axioms {k.get('axioms')}")
        rep = ROOT / e["lean_dir"] / "report.json"
        r = (load_json(rep).get("laws") or {}).get(e["law_id"]) if rep.is_file() else None
        if not r or r.get("result") != "checked" or r.get("source_sha256") != k.get("source_sha256"):
            bad.append("L6: the report does not say checked for this file")
    return bad


def check_laws(test: unittest.TestCase, es: list[dict], what: str) -> None:
    """Every law of es is checked in Lean (I2) with its frozen statement (L3-L8)."""
    for key in sorted({e["model_key"] for e in es}):   # the references first, once per model (not in the workers)
        stub_types(key)
    T.lean_toolchain()
    with ThreadPoolExecutor(max_workers=JOBS) as ex:
        files = list(ex.map(check_law_file, es))
    fails = {}
    for e, fb in zip(es, files):
        bad = record_problems(e, want_checked=True) + fb
        if bad:
            fails[e["law_id"]] = bad
    test.assertEqual(fails, {}, f"{len(fails)} of {len(es)} laws of {what} are not checked in Lean with their frozen "
                                f"statements")


def check_dir(test: unittest.TestCase, dkey: str, n: int) -> None:
    es = entries(dkey, "PROVED")
    test.assertEqual(len(es), n, f"the sidecar's PROVED laws of {dkey}")
    check_laws(test, es, dkey)


def canary_file(c: dict) -> str:
    """Rule L9's perturb canary as the tests build it: the committed law file, its frozen statement (from `theorem
    <law>` to its first `:=`, located in the comment-free reading) replaced in the raw source by the sidecar's perturbed
    statement, everything else kept (tests_m3/_i43.py::replace_statement; review 2, B1)."""
    src = need(ROOT / c["lean_source"]).read_text(encoding="utf-8")
    return T.replace_statement(src, c["theorem"], c["text"])


# ---------------------------------------------------------------------------------------------- the prereg's inputs
class TestPreregInstruments(unittest.TestCase):
    """Construction checks of the instruments fixed at the prereg (I43-R2; they hold before and after the build)."""

    def test_sidecar_is_the_computation(self):
        """Construction (I43-R2): spec/M3/lib/lean_promoted.json is tests_m3/_i43.py::promoted_doc over unchanged
        inputs: every input file's sha256 and every record's status and witnesses match, and recomputing the document
        (the differential values and the canaries' evidence by bend on the committed models) gives the same JSON."""
        s = side()
        for i in s["inputs"]:
            with self.subTest(input=i["path"]):
                if "sha256" in i:
                    self.assertEqual(file_sha256(ROOT / i["path"]), i["sha256"],
                                     f"{i['path']} changed since the prereg")
                else:
                    rec = load_json(ROOT / i["path"])
                    self.assertEqual(rec.get("status"), i["status"], i["path"])
                    self.assertEqual(T._sha_json(rec.get("witness")), i["witness_sha256"], i["path"])
                    self.assertEqual(T._sha_json((rec.get("non_vacuity") or {}).get("witness")),
                                     i["non_vacuity_witness_sha256"], i["path"])
                    self.assertEqual(T._sha_json(rec.get("witnesses")), i["witnesses_sha256"], i["path"])
        doc = T.promoted_doc(ROOT)
        moving = ("bend_files", "lean_m0", "statuses", "inputs", "unregenerated_records")   # R1/R7's baselines
        for k in moving:
            doc.pop(k)
        mine = {k: v for k, v in s.items() if k not in moving}
        self.assertEqual(canonical_json(doc), canonical_json(mine))

    def test_scope_counts(self):
        """Construction (L0; the counts the predictions name): attempted PROVED 8, 6, 7 and 73 (94), and REFUTED
        8, 2, 7 and 4 (21); not attempted, M3's typed and UNDO REFUTED laws (5) and I31's DISCH laws (13 PROVED and 7
        REFUTED: rule DISCH over a holon-facts/0.3 document, which no Lean emitter reads; carved out at the move onto
        be95d6d, the human's answer). Every other PROVED law is attempted. All PROVED: 8, 6, 7 and 86; all REFUTED:
        8, 2, 7 and 16."""
        c = side()["counts"]
        self.assertEqual(c["proved"], {"M1": 8, "M2": 6, "M2/extracted_m1": 7, "M3": 86})
        self.assertEqual(c["refuted"], {"M1": 8, "M2": 2, "M2/extracted_m1": 7, "M3": 16})
        self.assertEqual(c["refuted_attempted"], {"M1": 8, "M2": 2, "M2/extracted_m1": 7, "M3": 4})
        att = {d: len(entries(d, "PROVED")) for d, *_ in T.DIRS}
        self.assertEqual(att, {"M1": 8, "M2": 6, "M2/extracted_m1": 7, "M3": 73})
        out = [e for e in side()["laws"] if e["attempt"] != "lean"]
        self.assertEqual(sorted(e["law_id"] for e in out if not e["law_id"].startswith("L_disch_")),
                         ["L_sort_realize_rollup_363_4a64383b", "L_sort_tag_rollup_279_e01ea84a",
                          "L_undo_pair_Rollup_commitBatch_revertBatch",
                          "L_undo_res_Rollup_revertBatch_batchBlobVersionedHashes",
                          "L_undo_res_Rollup_revertBatch_batchDataStore"])
        disch = [e for e in out if e["law_id"].startswith("L_disch_")]
        self.assertEqual(sorted((e["status"], e["dir"], e["rule"], e["attempt"]) for e in disch),
                         sorted([("PROVED", "M3", "DISCH", T.DISCH_NOT_ATTEMPTED)] * 13
                                + [("REFUTED", "M3", "DISCH", T.DISCH_NOT_ATTEMPTED)] * 7))
        self.assertEqual({e["kind"] for e in out}, {"other"})
        self.assertEqual([e["law_id"] for e in out if e["status"] == "PROVED" and e["rule"] != "DISCH"], [])
        live = {(d, p.stem) for d, r, *_ in T.DIRS for p in (ROOT / r).glob("L*.json")
                if load_json(p).get("status") == "PROVED"}
        self.assertEqual(live, {(e["dir"], e["law_id"]) for e in side()["laws"] if e["status"] == "PROVED"})
        self.assertEqual([u["path"] for u in side()["unregenerated_records"] if "L_sort_" in u["path"]],
                         ["results/M3/L_sort_realize_rollup_363_4a64383b.json",
                          "results/M3/L_sort_tag_rollup_279_e01ea84a.json",
                          "results/M3/L_sort_tag_rollup_406_e01ea84a.json"])
        self.assertEqual(len([u for u in side()["unregenerated_records"] if "L_undo_" in u["path"]]), 8)

    def test_every_promoted_law_is_rendered(self):
        """Construction (L3): every PROVED law has exactly one frozen statement, named by its law id, but I31's DISCH
        laws, which have none (carved out at the move onto be95d6d); every attempted REFUTED law has its counter-law
        and refutation; no in-scope law falls back silently (rendering a PROVED law the rules do not cover raises); the
        IR forms the 94 statements use are the ones rule L3 lists."""
        forms = set()

        def walk(x):
            if isinstance(x, dict):
                if set(x) == {"act", "args"}:   # an action term: its argument map is keyed by the action's inputs
                    forms.add(("act", "args"))
                    for v in x["args"].values():
                        walk(v)
                    return
                forms.add(tuple(sorted(x)))
                if set(x) == {"s0"}:
                    return
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        for e in side()["laws"]:
            if e["attempt"] == T.DISCH_NOT_ATTEMPTED:   # I31's DISCH laws, carved out at the move: no statement at all
                self.assertEqual(e["statements"], [], e["law_id"])
                continue
            if e["status"] == "PROVED":
                self.assertEqual([s["theorem"] for s in e["statements"]], [e["law_id"]], e["law_id"])
                law = load_json(ROOT / e["law_file"])
                walk(law["statement"]["claim"])
                walk(law["statement"]["assume"])
            elif e["attempt"] == "lean":
                self.assertEqual([s["theorem"] for s in e["statements"]],
                                 [f"{e['law_id']}_counter", f"{e['law_id']}_refuted"])
            for s in e["statements"]:
                self.assertTrue(s["text"].startswith(f"theorem {s['theorem']} : "), s["theorem"])
                self.assertNotIn("«", s["text"])
                self.assertNotIn(":=", s["text"])
        known = {("eq",), ("all",), ("var",), ("nat",), ("bool",), ("nats",), ("s0",), ("from", "run"),
                 ("from", "step"), ("trace",), ("act", "args"), ("of", "proj"), ("obsv", "of"), ("args", "fn"),
                 ("from", "on", "site"), ("field", "of"), ("bytes",), ("some",), ("args", "call")}
        self.assertEqual(forms - known, set(), "IR forms of PROVED laws outside rule L3's list")

    def test_statements_elaborate_against_the_interfaces(self):
        """Construction (L2, L3): per model, its interface stub followed by every frozen statement of its laws, each
        proof a placeholder, passes the instrument's Lean check with placeholders allowed (exit 0, no error, the
        sentinel reached, every theorem audited by its bare name; the stub's axioms are its signatures) with one
        placeholder warning per theorem (94 + 42 in all)."""
        total = 0
        for key, model in side()["models"].items():
            with self.subTest(model=key):
                sts = [s for e in entries() if e["model_key"] == key for s in e["statements"]]
                names = [s["theorem"] for s in sts]
                total += len(names)
                r = T.lean_check(T.stub_text(model, sts), names, allow_sorry=True, allowed=None)
                self.assertEqual(r["problems"], [], r["out"][-3000:])
                self.assertEqual(len(T.LEAN_SORRY.findall(r["out"])), len(names), r["out"][-3000:])
        self.assertEqual(total, 94 + 2 * 21)

    def test_differential_samples_are_well_typed_and_not_trivial(self):
        """Construction (L7): per model, the interface stub followed by the sample inputs and one theorem per sample
        (each proof a placeholder) elaborates with no error; the samples cover every signature of the interface but s0
        and Reach; every action constructor is stepped from every sample state and succeeds in some sample; every hit
        predicate and every raw obligation takes both values and every REFUTED law's site predicate is false
        somewhere; an encoder with an unsupported tag gives an undefined cell; I43-P2 scores the 6 PROVED site laws."""
        counts = {}
        for key, model in side()["models"].items():
            with self.subTest(model=key):
                facts = load_json(ROOT / model["facts"])
                pre, thms = T.diff_lean(model, facts, proof="by sorry")
                counts[key] = len(thms)
                out, _ = lean_run(T.stub_text(model, []) + "\n" + pre + "\n" + "\n\n".join(thms) + "\n")
                self.assertEqual(T.lean_errors(out), [], out[-3000:])
                self.assertEqual(len(T.LEAN_SORRY.findall(out)), len(thms))
                d = model["differential"]
                fns = {s["fn"] for s in d["samples"]}
                sigs = {n for n, _ in model["interface"]["signatures"]} - {"s0"}
                self.assertEqual(sigs - fns, set(), "interface functions without a sample")
                if model["kind"] == "linked":
                    self.assertTrue(any(s["value"] == [T.UNDEF] for s in d["samples"] if s["fn"].startswith("c_enc")))
                    continue
                cons = {a["name"] for a in facts["actions"]}
                for j in range(len(d["states"])):
                    stepped = {d["actions"][a["act"]]["op"] for s in d["samples"] if s["fn"] == "step"
                               for a in s["args"] if "act" in a and {"state": j} in s["args"]}
                    self.assertEqual(stepped, cons, f"state {j}")
                self.assertEqual(model["action_successes"], T.action_successes(model, facts))
                self.assertEqual([a for a, n in model["action_successes"].items() if n == 0], [],
                                 "actions that succeed in no sample")
                for sname in model["sites"]:
                    x = sname[len("site_"):]
                    for f in ("hit", "ro"):
                        self.assertEqual({s["value"] for s in d["samples"] if s["fn"] == f"{f}_{x}"}, {True, False},
                                         f"{f}_{x}")
                for e in entries(status="REFUTED"):
                    if e["model_key"] == key and e["kind"] == "machine_oracle" and e["subform"] == "site":
                        sname = T.site_name(load_json(ROOT / e["law_file"])["statement"]["claim"]["eq"][0]["site"])
                        self.assertIn(False, {s["value"] for s in d["samples"] if s["fn"] == sname}, sname)
        self.assertEqual(counts, {"M1:morph_batchdata": 28, "M1:morph_rollup": 1290, "M2/extracted_m1:m1_view": 1105,
                                  "M2:morph_rollup": 4241, "M3:header_length": 711})
        self.assertEqual(side()["site_laws_scored"], {"laws": [e["law_id"] for e in entries("M2", "PROVED")],
                                                      "excluded": {}})

    def test_perturb_canaries_are_evidenced(self):
        """Construction (L9, review B3): the sidecar names one perturb canary per milestone gate, M1 and M2 an evaluate
        law (its first Nat equation's constant k becomes k + 1; the compiled Bend model evaluates the left side at the
        record's witness to k) and M3 a PAR round trip (the first two cells of its right side swapped; on the seeded
        record the left side is the unswapped cells, which differ); each canary text is its law's frozen statement
        with exactly that change."""
        c = side()["canaries"]
        self.assertEqual(sorted(c), ["M1", "M2", "M3"])
        laws = {(e["dir"], e["law_id"]): e for e in entries()}
        for g in ("M1", "M2"):
            with self.subTest(gate=g):
                x = c[g]
                self.assertEqual((x["kind"], x["law"], x["from"], x["to"]), ("nat_plus_one", "L_disch_delay_pay", 2, 3))
                self.assertEqual(x["dir"], {"M1": "M1", "M2": "M2/extracted_m1"}[g])
                self.assertEqual(x["evidence"]["value"], x["from"])
                frozen = laws[(x["dir"], x["law"])]["statements"][0]["text"]
                self.assertEqual(frozen.count(f" = {x['from']} ∧"), 1)
                self.assertEqual(x["text"], frozen.replace(f" = {x['from']} ∧", f" = {x['to']} ∧"))
        x = c["M3"]
        with self.subTest(gate="M3"):
            self.assertEqual(x["kind"], "swap_first_two_cells")
            ev = x["evidence"]
            self.assertNotEqual(ev["value"][0], ev["value"][1])
            self.assertEqual(ev["swapped"], [ev["value"][1], ev["value"][0]] + ev["value"][2:])
            frozen = laws[("M3", x["law"])]["statements"][0]["text"]
            self.assertNotEqual(x["text"], frozen)
            self.assertEqual(sorted(x["text"]), sorted(frozen))

    def test_the_instrument_rejects_the_review_cheats(self):
        """Construction (L4, L6, review B1): every cheat file of the independent review (tests_m3/_i43.py::CHEATS) is
        rejected by the instrument's file rules (a #, a banned word); those that cut elaboration short, forge audit
        lines or turn decide into sorry, and the wrong model without a trick, are rejected by the instrument's Lean
        check alone too (the models with the differential of M1's morph_batchdata appended); a clean law file passes
        both, and so does a model file made of each model's frozen declarations (the frozen texts and statements hold
        no # and no banned word: a compliant file exists)."""
        self.assertEqual(T.file_check(T.CLEAN_LAW, "law"), [])
        self.assertEqual(T.lean_check(T.CLEAN_LAW, ["t"])["problems"], [])
        for key, m in side()["models"].items():
            i = m["interface"]
            body = "\n\n".join(x for _, x in i["types"] + i["decls"])
            txt = "set_option autoImplicit false\n\nnamespace Model\n\n" + body + "\n\nend Model\n"
            self.assertEqual(T.file_check(txt, "model", m), [], key)
            for s in (s for e in entries() if e["model_key"] == key for s in e["statements"]):
                self.assertFalse("#" in s["text"] or T.LEAN_BANNED.search(s["text"]), s["theorem"])
        for name, ch in T.CHEATS.items():
            with self.subTest(cheat=name):
                if name != "fake_model_plain":
                    self.assertTrue([v for v in T.file_check(ch["text"], ch["file"])
                                     if v.startswith(("a # in the code", "the banned word"))], name)
                if ch["file"] == "model":
                    m = side()["models"][ch["model"]]
                    pre, thms = T.diff_lean(m, load_json(ROOT / m["facts"]))
                    text = ch["text"].rstrip("\n") + "\n\nset_option maxRecDepth 20000\n\n" + pre + "\n" + \
                        "\n\n".join(thms) + "\n"
                    names = [f"holon_diff_{k}" for k in range(len(thms))]
                else:
                    text, names = ch["text"], ch["names"]
                problems = T.lean_check(text, names)["problems"]
                if ch["lean_alone"]:
                    self.assertNotEqual(problems, [], f"{name} passes the Lean check alone")

    def test_the_instrument_reads_lean_rejections(self):
        """Construction (L6, L9; review 2, M1 and M3): tests_m3/_i43.py::semantic_rejection reads Lean 4.34.0's
        rejections of a false claim as semantic for every proof style the contract allows (decide, rfl on a closed
        term, the rfl tactic, fun _ => rfl, exact rfl, Eq.refl) and as not semantic for a simp or omega that leaves
        goals, an unknown identifier or tactic, and a parse error (SEMANTIC_PROBES); resource_limit_reproduces reads
        Lean's own heartbeat and recursion-depth errors, and not one for the other (RESOURCE_PROBES)."""
        for name, (text, want) in T.SEMANTIC_PROBES.items():
            with self.subTest(probe=name):
                r = T.run_lean("set_option autoImplicit false\n" + text + "\n")
                self.assertNotEqual(r["code"], 0, r["out"])
                self.assertEqual(T.semantic_rejection(r["out"]), want, r["out"][-1500:])
        for reason, text in T.RESOURCE_PROBES.items():
            with self.subTest(limit=reason):
                src = "set_option autoImplicit false\n" + text + "\n"
                self.assertTrue(T.resource_limit_reproduces(src, reason, BUDGET_S)[0])
                other = next(x for x in T.RESOURCE_PROBES if x != reason)
                self.assertFalse(T.resource_limit_reproduces(src, other, BUDGET_S)[0])

    def test_site_canaries_are_evidenced(self):
        """Construction (L11; review 2, M2): every PROVED SORT site of M2 has a mutation canary: a non-empty mutation
        whose every edit keeps the original expression under a constant guard (["||", true, e] for a require or a
        condition that must hold, ["&&", false, e] for one that must fail), touches no permission (a require naming
        the caller input who), and a sample where holon's mutated Bend model makes the site predicate false and the
        hit predicate true, whose Lean canary theorems (tests_m3/_i43.py::site_canary_lean) are well-typed over the
        interface stub; the 6 site laws are scored by I43-P2."""
        model = side()["models"]["M2:morph_rollup"]
        facts = load_json(ROOT / model["facts"])
        proved = {T.site_name(T.site_ids(load_json(ROOT / e["law_file"])["statement"], [])[0])
                  for e in entries("M2", "PROVED")}
        self.assertEqual(set(model["site_canaries"]), proved)
        for sname, c in sorted(model["site_canaries"].items()):
            with self.subTest(site=sname):
                self.assertNotIn("none", c, c.get("none"))
                self.assertEqual((c["site"], c["hit"]), (False, True))
                self.assertTrue(c["mutation"])
                for ed in c["mutation"]:
                    cur = T.apply_edits(facts, [{"pointer": ed["pointer"], "value": "x"}])   # the pointer exists
                    self.assertIsNotNone(cur)
                    orig = facts
                    for part in ed["pointer"].split("/")[1:]:
                        orig = orig[int(part)] if isinstance(orig, list) else orig[part]
                    self.assertIn(ed["value"], (["||", True, orig], ["&&", False, orig]), ed["pointer"])
                    self.assertFalse(ed["pointer"].endswith("/require") and T._mentions(orig, T.CALLER),
                                     f"{ed['pointer']} is a permission")
                pre, thms, names = T.site_canary_lean(model, facts, sname, c)
                text = (T.stub_text(model, []) + "\n" + pre + "\n"
                        + "\n\n".join(x.replace(":= by decide", ":= by sorry") for x in thms) + "\n")
                r = T.lean_check(text, names, allow_sorry=True, allowed=None)
                self.assertEqual(r["problems"], [], r["out"][-2000:])   # the canary theorems are well-typed
        self.assertEqual(sorted(side()["site_laws_scored"]["laws"]),
                         sorted(e["law_id"] for e in entries("M2", "PROVED")))

    def test_the_import_reader_sees_the_review_bypasses(self):
        """Construction (L1, review M3; review 2, m2): on a synthetic tree, tests_m3/_i43.py::independence_violations
        flags each bypass the reviews found (a level-2 relative import of holon.sorts, of a submodule of it, of a Bend
        emitter, a helper module that does the import, importlib.import_module, __import__, an attribute chain from an
        imported package into a Bend emitter, getattr, vars, __dict__) and passes a clean emitter."""
        tmp = Path(tempfile.mkdtemp(prefix="i43_imports_"))
        try:
            files = {"holon/__init__.py": "", "holon/gen/__init__.py": "", "holon/sorts/__init__.py": "",
                     "holon/sorts/sites.py": "X = 1\n", "holon/gen/mlaws.py": "class Emitter:\n    pass\n",
                     "holon/gen/lean_help.py": "from ..sorts import sites\n",
                     "holon/gen/lean_ok.py": "import json\nfrom . import lean_ok2\n", "holon/gen/lean_ok2.py": "",
                     "holon/gen/lean_a.py": "from ..sorts import sites\n",
                     "holon/gen/lean_b.py": "from ..sorts.sites import X\n",
                     "holon/gen/lean_c.py": "from ..gen.mlaws import Emitter\n",
                     "holon/gen/lean_d.py": "from . import lean_help\n",
                     "holon/gen/lean_e.py": "import importlib\nm = importlib.import_module('holon.sorts.sites')\n",
                     "holon/gen/lean_f.py": "m = __import__('holon.gen.mlaws')\n",
                     "holon/gen/lean_g.py": "import holon.sorts.sites\n",
                     "holon/gen/lean_h.py": "def f():\n    from tests_m3 import _i43\n",
                     "holon/gen/lean_i.py": "import holon.gen\nE = holon.gen.mlaws.Emitter\n",
                     "holon/gen/lean_j.py": "from holon import gen as g\nE = g.mlaws\n",
                     "holon/gen/lean_k.py": "from .. import gen\nm = getattr(gen, 'ml' + 'aws')\n",
                     "holon/gen/lean_l.py": "import holon\nm = vars(holon)['sor' + 'ts']\n",
                     "holon/gen/lean_m.py": "from .. import gen as g\nm = g.__dict__['mlaws']\n"}
            for rel, text in files.items():
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_text(text)
            self.assertEqual(T.independence_violations(tmp, ["holon/gen/lean_ok.py"]), [])
            for f in "abcdefghijklm":
                with self.subTest(module=f"lean_{f}"):
                    self.assertNotEqual(T.independence_violations(tmp, [f"holon/gen/lean_{f}.py"]), [])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- P1, P2: promotion
class TestPromoted(unittest.TestCase):
    def test_m3_promoted_laws_check_in_lean(self):
        """I43-P1: the 73 PROVED PAR laws of results/M3 are checked in Lean (I2): each record's lean4 entry is checked
        and the record is I2; each file obeys L4, states its frozen theorem (L3) with the frozen elaborated type (L5)
        and passes the instrument's Lean check here (allowed axioms, the sentinel, no sorry) within 120 s; the report
        says checked for that text."""
        check_dir(self, "M3", 73)

    def test_m2_site_laws_check_in_lean(self):
        """I43-P2: the PROVED SORT-site laws of results/M2 that the sidecar scores (site_laws_scored: the 6 whose hit
        predicate and raw obligation take both values on the samples and that have a site canary) are checked in Lean
        (I2), as for M3, each law file's site predicate reaching its raw obligation (L4); and each passes its mutation
        canary (rule L11): in a copy of the tree whose facts document carries the site's mutation
        (models.<key>.site_canaries.<site>.mutation), holon lean --milestone M2 --root <copy> --emit-only re-emits the
        Lean model, and that model's site predicate is false, and its hit predicate has the Bend value, at the
        canary's sample, under the instrument's Lean check."""
        scored = side()["site_laws_scored"]["laws"]
        es = [e for e in entries("M2", "PROVED") if e["law_id"] in scored]
        self.assertEqual(len(es), 6)
        check_laws(self, es, "M2 (the scored site laws)")
        model = side()["models"][es[0]["model_key"]]
        facts_rel = model["facts"]
        repo = copy_repo()
        try:
            original = (repo / facts_rel).read_text(encoding="utf-8")
            facts = load_json(repo / facts_rel)
            fails = {}
            for e in es:
                sname = T.site_name(T.site_ids(load_json(ROOT / e["law_file"])["statement"], [])[0])
                c = model["site_canaries"][sname]
                (repo / facts_rel).write_text(json.dumps(T.apply_edits(facts, c["mutation"]), indent=2) + "\n")
                p = run_holon(["lean", "--milestone", "M2", "--root", str(repo), "--emit-only"], cwd=repo,
                              timeout=3600)
                mf = repo / model["lean_model"]
                if p.returncode != 0 or not mf.is_file():
                    fails[sname] = [f"holon lean --emit-only exit {p.returncode}: {(p.stdout + p.stderr)[-500:]}"]
                    continue
                pre, thms, names = T.site_canary_lean(model, facts, sname, c)
                r = T.lean_check(mf.read_text(encoding="utf-8").rstrip("\n") + "\n\nset_option maxRecDepth 20000\n\n"
                                 + pre + "\n" + "\n\n".join(thms) + "\n", names)
                if r["problems"]:
                    fails[sname] = r["problems"]
                (repo / facts_rel).write_text(original, encoding="utf-8")
            self.assertEqual(fails, {}, "site predicates the mutation canary does not move")
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_m1_promoted_laws_check_in_lean(self):
        """I43-R11 (probed by the design survey): the 8 PROVED laws of results/M1 are checked in Lean (I2), as for
        M3."""
        check_dir(self, "M1", 8)

    def test_extracted_m1_promoted_laws_check_in_lean(self):
        """I43-R11 (probed by the design survey): the 7 PROVED laws of results/M2/extracted_m1 are checked in Lean
        (I2), as for M3."""
        check_dir(self, "M2/extracted_m1", 7)


# ---------------------------------------------------------------------------------------------- P3: no disagreement
class TestAgreement(unittest.TestCase):
    def test_no_cross_kernel_disagreement(self):
        """I43-P3: every attempted law (94 PROVED and 21 REFUTED records) has exactly one lean4 entry and none is
        failed (Lean rejected no Bend verdict for a non-resource reason, with no forbidden word, bad axiom or missing
        theorem); each of the 21 REFUTED is checked, or not_run with reason timeout, recursion_depth or heartbeats only
        (review M2), and each such resource claim reproduces: the committed file, rerun by the instrument within the
        120 s budget, reaches the claimed limit again (timeout: no verdict within 120 s; recursion_depth and
        heartbeats: Lean's own error for that limit; review 2, M3); every REFUTED record whose lean4 entry is checked
        has a file that states its frozen counter-law and refutation (L3-L5) and passes the instrument's Lean check
        here. The counts by status, result and reason are printed on every run (review 2, m9)."""
        att = entries()
        self.assertEqual(len(att), 115)
        failed, missing, checked_refuted, refuted_bad, limited, tally = [], [], [], [], [], {}
        for e in att:
            ks = lean4_entry(load_json(ROOT / e["record"]))
            if len(ks) != 1:
                missing.append(e["law_id"])
                continue
            k = ks[0]
            key = f"{e['status']} {k.get('result')}" + (f" {k.get('reason')}" if k.get("result") == "not_run" else "")
            tally[key] = tally.get(key, 0) + 1
            if k.get("result") == "failed":
                failed.append(f"{e['dir']}:{e['law_id']}: {k.get('note') or k.get('detail')}")
            elif e["status"] == "REFUTED" and k.get("result") == "checked":
                checked_refuted.append(e)
            elif e["status"] == "REFUTED" and k.get("result") == "not_run" and k.get("reason") in T.REFUTED_REASONS:
                limited.append((e, k["reason"]))
            elif e["status"] == "REFUTED":
                refuted_bad.append(f"{e['dir']}:{e['law_id']}: {k.get('result')} {k.get('reason')}")
        counts = f"counts: {dict(sorted(tally.items()))}"
        print(f"\nI43-P3 {counts}; missing {len(missing)}")
        self.assertEqual(missing, [], f"attempted laws without exactly one lean4 entry; {counts}")
        self.assertEqual(failed, [], f"cross-kernel disagreements (blocking findings); {counts}")
        self.assertEqual(refuted_bad, [], f"REFUTED laws neither checked nor resource-limited; {counts}")
        unproven = {}
        for e, reason in limited:
            p = ROOT / e["lean_source"]
            if not p.is_file():
                unproven[e["law_id"]] = f"{e['lean_source']} is missing"
                continue
            ok, tail = T.resource_limit_reproduces(p.read_text(encoding="utf-8"), reason, BUDGET_S)
            if not ok:
                unproven[e["law_id"]] = f"{reason} does not reproduce: {tail}"
        self.assertEqual(unproven, {}, f"resource claims that do not reproduce; {counts}")
        for key in sorted({e["model_key"] for e in checked_refuted}):
            stub_types(key)
        T.lean_toolchain()
        with ThreadPoolExecutor(max_workers=JOBS) as ex:
            probs = list(ex.map(check_law_file, checked_refuted))
        bad = {e["law_id"]: p for e, p in zip(checked_refuted, probs) if p}
        self.assertEqual(bad, {}, "a REFUTED record claims lean4 checked without its frozen counter-law")


# ---------------------------------------------------------------------------------------------- R1: nothing else moves
class TestRegressions(unittest.TestCase):
    def test_statuses_and_bend_files_are_unchanged(self):
        """I43-R1: every record of the four directories keeps its status; every .bend file under gen/M0-M3 at the
        prereg is byte-identical, except that a statement_hash value may change, and then only to the law's
        laws/<M>/REGISTRY.json entry; every M3 PAR record carries its registry statement hash (the integration line's
        80 stale PAR hashes are brought to holon-rules/1.3); I30's 3 typed and I27's 8 UNDO M3 records, which I43
        does not regenerate (gap LP-G9; review 2, B3), keep their status, statement hash, generator hash, witnesses
        and kernels as at the prereg (sidecar unregenerated_records); records outside the attempted laws gain no
        lean4 entry."""
        for path, st in side()["statuses"].items():
            with self.subTest(record=path):
                self.assertEqual(load_json(ROOT / path).get("status"), st)
        reg = {m: load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"] for m in ("M1", "M2", "M3")}
        for f in side()["bend_files"]:
            p = ROOT / f["path"]
            self.assertTrue(p.is_file(), f["path"])
            b = p.read_bytes()
            if file_sha256(p) == f["sha256"]:
                continue
            masked = re.sub(rb"statement_hash: sha256:[0-9a-f]{64}", b"statement_hash: sha256:<masked>", b)
            self.assertEqual(hashlib.sha256(masked).hexdigest(), f["masked_sha256"],
                             f"{f['path']} changed beyond its statement_hash")
            m = re.match(r"gen/(M[123])/laws/(L\w+)/LAWS\.bend$", f["path"])
            self.assertIsNotNone(m, f"{f['path']}: only a law file's statement_hash may change")
            for h in re.findall(r"statement_hash: (sha256:[0-9a-f]{64})", b.decode("utf-8")):
                self.assertEqual(h, reg[m.group(1)][m.group(2)], f["path"])
        par = sorted((ROOT / "results" / "M3").glob("L_par_*.json"))
        self.assertEqual(len(par), 80)
        stale = [p.stem for p in par if load_json(p).get("statement_hash") != reg["M3"][p.stem]]
        self.assertEqual(stale, [], "M3 PAR records with a statement hash other than the registry's")
        for u in side()["unregenerated_records"]:   # I30's typed and I27's UNDO records stay as they are (LP-G9)
            with self.subTest(record=u["path"]):
                r = load_json(ROOT / u["path"])
                have = {"path": u["path"], "status": r.get("status"), "statement_hash": r.get("statement_hash"),
                        "generator_sha256": r.get("generator_sha256"), "witness_sha256": T._sha_json(r.get("witness")),
                        "non_vacuity_witness_sha256": T._sha_json((r.get("non_vacuity") or {}).get("witness")),
                        "witnesses_sha256": T._sha_json(r.get("witnesses")),
                        "kernels_sha256": T._sha_json(r.get("kernels"))}
                self.assertEqual(have, u)
        attempted = {e["record"] for e in entries()}
        for d, r, *_ in T.DIRS:
            for p in sorted((ROOT / r).glob("L*.json")):
                rel = p.relative_to(ROOT).as_posix()
                if rel not in attempted:
                    self.assertEqual(lean4_entry(load_json(p)), [], f"{rel} gained a lean4 entry")

    def test_m0_lean_files_are_unchanged(self):
        """I43-R7: after the build (gen/M1/lean/report.json exists), gen/M0/lean/ (I9's files and report) is
        byte-identical to the prereg's."""
        need(ROOT / "gen" / "M1" / "lean" / "report.json")
        want = {f["path"]: f["sha256"] for f in side()["lean_m0"]}
        have = {p.relative_to(ROOT).as_posix(): file_sha256(p) for p in sorted((ROOT / "gen/M0/lean").iterdir())
                if p.is_file()}
        self.assertEqual(have, want)

    def test_records_are_honest_and_schema_valid(self):
        """I43-R5 (L8): every attempted law's record has exactly one lean4 entry with the frozen version, role and
        reading, I2 exactly when it is checked, an allowed reason and a detail when not_run; every record of results/M1,
        results/M2 and results/M3 validates against spec/schemas/result_record_v2.schema.json, whose kernel entries
        declare reason (the allowed enum), detail and reading; each attempted record of results/M2/extracted_m1 (exempt
        from the whole-record validation: its ledger_match is "derived" by design, review B2) has kernels[] and
        independence_class valid against the schema's definitions of those properties."""
        schema = load_json(SCHEMAS / "result_record_v2.schema.json")
        props = schema["properties"]["kernels"]["items"]["properties"]
        self.assertEqual(sorted(props.get("reason", {}).get("enum", [])), sorted(T.ALLOWED_REASONS))
        self.assertEqual((props.get("detail", {}).get("type"), props.get("reading", {}).get("type")),
                         ("string", "string"))
        bad = {}
        for e in entries():
            p = record_problems(e, want_checked=False)
            if p:
                bad[f"{e['dir']}:{e['law_id']}"] = p
        self.assertEqual(bad, {})
        for d, r, *_ in T.DIRS:
            for p in sorted((ROOT / r).glob("L*.json")):
                rec = load_json(p)
                with self.subTest(record=p.relative_to(ROOT).as_posix()):
                    if d != "M2/extracted_m1":
                        self.assertEqual(mini_schema.errors(rec, schema), [])
                    elif rec.get("status") in ("PROVED", "REFUTED"):
                        self.assertEqual(mini_schema.errors(rec.get("kernels"), schema["properties"]["kernels"]), [])
                        self.assertEqual(mini_schema.errors(rec.get("independence_class"),
                                                            schema["properties"]["independence_class"]), [])

    def test_strip_comments_reads_escaped_identifiers_whole(self):
        """Construction (L6, I42 Question 5): holon.lean.strip_comments keeps an escaped identifier whole, so «/-»
        hides nothing from Lean G3: a forbidden word after it is found."""
        lean = holon_module("holon.lean")
        self.assertIn("sorry", lean.forbidden("def «/-» : Nat := 1\ntheorem t : True := by sorry\n-- -/\n"))
        self.assertIn("«/-»", lean.strip_comments("def «/-» := 1\n"))


# ---------------------------------------------------------------------------------------------- R3, R4: CLI and code
class TestCode(unittest.TestCase):
    def test_lean_check_is_deterministic_on_the_committed_tree(self):
        """I43-R3 (the CLI): holon lean --milestone M --check exits 0 for M1, M2 and M3, twice (the committed
        Lean files and model files are their re-emission), and the Lean directories hold exactly the model files,
        report.json and the file of every attempted law whose record does not say unsupported_form."""
        for m in ("M1", "M2", "M3"):
            for n in (1, 2):
                with self.subTest(milestone=m, run=n):
                    p = run_holon(["lean", "--milestone", m, "--check"], timeout=3600)
                    self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        for d in side()["dirs"]:
            with self.subTest(dir=d["dir"]):
                want = {e["lean_model"] for e in entries(d["dir"])} | {f"{d['lean_dir']}/report.json"}
                for e in entries(d["dir"]):
                    ks = lean4_entry(load_json(ROOT / e["record"]))
                    if not (ks and ks[0].get("result") == "not_run" and ks[0].get("reason") == "unsupported_form"):
                        want.add(e["lean_source"])
                have = {p.relative_to(ROOT).as_posix() for p in (ROOT / d["lean_dir"]).rglob("*") if p.is_file()}
                self.assertEqual(have, want)

    def test_the_outputs_never_need_the_sidecars(self):
        """I43-R3 (review M4; review 2, m3): in a copy of the tree without spec/M3/lib/lean_promoted.json,
        theory_core2.json and tests_m3/ (the instrument and the contracts), holon lean --milestone M --check exits 0
        for M1, M2 and M3 and holon theory2 --milestone M3 --check exits 0: the committed outputs are their
        re-emission without the frozen sidecars or the instrument."""
        for rel in SIDECARS:
            need(ROOT / rel)
        repo = copy_repo()
        try:
            for rel in SIDECARS:
                (repo / rel).unlink()
            shutil.rmtree(repo / "tests_m3")   # the instrument and the contracts go too (review 2, m3)
            for args in (["lean", "--milestone", "M1"], ["lean", "--milestone", "M2"], ["lean", "--milestone", "M3"],
                         ["theory2", "--milestone", "M3"]):
                with self.subTest(command=" ".join(args)):
                    p = run_holon(args + ["--root", str(repo), "--check"], cwd=repo, timeout=3600)
                    self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_holon_never_names_the_sidecars(self):
        """I43-R4 (review M4): no file under holon/ names spec/M3/lib/lean_promoted.json, theory_core2.json or the
        instrument tests_m3/_i43.py (as a path, a file name or a module), so no emitter copies a frozen statement or
        builds a model function from the sample table."""
        hits = []
        for p in sorted((ROOT / "holon").rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                text = p.read_bytes().decode("utf-8", "replace")
                if re.search(r"lean_promoted|theory_core2|_i43\b", text):
                    hits.append(p.relative_to(ROOT).as_posix())
        self.assertEqual(hits, [])

    def test_emitters_are_independent_and_generic(self):
        """I43-R4 (L1): the Lean emitters exist; no file of the transitive import closure of the emitters and
        holon/lean.py imports a Bend emitter, the oracles, holon.sorts or an instrument, or uses a dynamic import
        (tests_m3/_i43.py::independence_violations, review M3); the emitters, holon/lean.py and every other
        holon/gen/lean_*.py module of that closure name no target: no compound target name of the M1/M2 fact documents
        and libraries (I15's vocabulary, tests_m2/_i15.py pinned by sha256, review m5) or of the M3 linked components,
        no quoted target name but the formats' own words (GENERIC_QUOTED; I9's M0 emitters also M0's Header and
        Fields), no law id, no target source file."""
        self.assertEqual(file_sha256(ROOT / "tests_m2" / "_i15.py"), I15_SHA256, "tests_m2/_i15.py changed")
        for rel in EMITTERS:
            self.assertTrue((ROOT / rel).is_file(), f"{rel} is missing (I43 builds it)")
        self.assertEqual(T.independence_violations(ROOT, list(EMITTERS) + ["holon/lean.py"]), [])
        closure = T.import_closure(ROOT, list(EMITTERS) + ["holon/lean.py"])
        named = sorted(set(EMITTERS) | {"holon/lean.py"}
                       | {f for f in closure if re.match(r"holon/gen/lean_\w+\.py$", f)})
        compound = I15.compound_target_names()
        quoted = I15.quoted_target_names()
        names3 = X.target_names(ROOT)
        compound3 = {n for n in names3 if len(n) >= 5 and ("_" in n or any(c.isupper() for c in n[1:]))}
        quoted3 = {n for n in names3 if len(n) >= 3} - X.GENERIC_WORDS
        for rel in named:
            with self.subTest(module=rel):
                text = (ROOT / rel).read_text(encoding="utf-8")
                for n in sorted(compound | compound3):
                    self.assertIsNone(re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", text),
                                      f"{rel} names {n}")
                for n in sorted((quoted | quoted3) - GENERIC_QUOTED - M0_EMITTER_QUOTED.get(rel, set())):
                    self.assertIsNone(re.search(rf"[\"']{re.escape(n)}[\"']", text), f"{rel} quotes {n!r}")
                self.assertNotRegex(text, r"\bL_(par|sort|disch|undo|fact|nat|sym|own|tag)_\w+")
                self.assertNotRegex(text, r"(?i)\bmorph\b|Rollup\.sol|header_length")


# ---------------------------------------------------------------------------------------------- R9: the models agree
class TestDifferential(unittest.TestCase):
    def test_lean_models_compute_the_bend_values(self):
        """I43-R9 (L4, L7): every model file obeys L4 (a model file: no #, no banned word, nothing after `end Model`,
        every site predicate reaching its raw obligation) and holds the frozen declarations; with the sidecar's sample
        inputs and one theorem per sample appended, it passes the instrument's Lean check (exit 0, no error, no sorry,
        the sentinel reached, every sample theorem audited with allowed axioms): every sample is proved by decide, so
        the Lean model computes what the compiled Bend model computes; every law file's model section is the model
        file's (checked per law in P1-P3 and R11)."""
        for key, model in side()["models"].items():
            with self.subTest(model=key):
                p = need(ROOT / model["lean_model"])
                src = p.read_text(encoding="utf-8")
                self.assertEqual(T.file_check(src, "model", model) + T.site_reach_violations(src, model), [])
                frozen = {n: T.norm(t) for n, t in model["interface"]["types"] + model["interface"]["decls"]}
                mine = T.model_decls(src)
                for n, t in frozen.items():
                    self.assertEqual(mine.get(n), [t], f"{key}: the frozen declaration {n}")
                for s in model["sites"]:
                    self.assertIn(s, mine, f"{key}: {s} is not declared")
                pre, thms = T.diff_lean(model, load_json(ROOT / model["facts"]))
                for i in range(0, len(thms), 400):
                    part = thms[i:i + 400]
                    names = [f"holon_diff_{k}" for k in range(i, i + len(part))]
                    r = T.lean_check(src.rstrip("\n") + "\n\nset_option maxRecDepth 20000\n\n" + pre + "\n"
                                     + "\n\n".join(part) + "\n", names, timeout=1800)
                    self.assertEqual(r["problems"], [], f"{key} samples {i}..{i + len(part) - 1}: {r['out'][-3000:]}")

    def test_every_emitted_lean_file_obeys_the_file_rules(self):
        """I43-R9 (L4, review m6): every .lean file under gen/M1/lean, gen/M2/lean, gen/M2/extracted/m1/lean and
        gen/M3/lean, models/ included, is the law file of an attempted law or the model file of one of its models, and
        obeys the file rules of its kind (tests_m3/_i43.py::file_check)."""
        bad = {}
        for d in side()["dirs"]:
            laws = {e["lean_source"]: e for e in entries(d["dir"])}
            models = {m["lean_model"]: m for m in side()["models"].values()
                      if m["lean_model"].startswith(d["lean_dir"] + "/")}
            files = sorted(p.relative_to(ROOT).as_posix() for p in need(ROOT / d["lean_dir"]).rglob("*.lean"))
            for f in files:
                src = (ROOT / f).read_text(encoding="utf-8")
                if f in laws:
                    v = T.file_check(src, "law", side()["models"][laws[f]["model_key"]])
                elif f in models:
                    v = T.file_check(src, "model", models[f])
                else:
                    v = ["neither an attempted law's file nor a model file"]
                if v:
                    bad[f] = v
        self.assertEqual(bad, {})


# ---------------------------------------------------------------------------------------------- R10: the canaries
class TestCanaries(unittest.TestCase):
    def test_perturb_canaries_are_rejected_by_lean(self):
        """I43-R10 (L9, review B3; review 2, B1): for M1, M2 and M3, the committed law file of the sidecar's perturb
        canary obeys the law-file rules, and the canary built by the test from it (the raw source with its frozen
        statement replaced by the sidecar's perturbed one, the proof kept) is rejected by the instrument's Lean check
        (exit code not 0) after elaborating to the end (the sentinel's audit line is there), for a semantic reason:
        the first error matches tests_m3/_i43.py::SEMANTIC_REJECTION and no error matches NON_SEMANTIC."""
        for g, c in sorted(side()["canaries"].items()):
            with self.subTest(gate=g, law=c.get("law")):
                self.assertIn("law", c, c)
                model = side()["models"][next(e["model_key"] for e in entries(c["dir"]) if e["law_id"] == c["law"])]
                committed = need(ROOT / c["lean_source"]).read_text(encoding="utf-8")
                self.assertEqual(T.file_check(committed, "law", model), [])
                r = T.lean_check(canary_file(c), [c["theorem"]])
                self.assertNotEqual(r["code"], 0, f"the canary {g}:{c['law']} is accepted")
                self.assertIn(r["sentinel"], r["out"], f"the canary did not elaborate to the end: {r['out'][-3000:]}")
                self.assertTrue(T.semantic_rejection(r["out"]), f"not a semantic rejection: {r['out'][-3000:]}")


# ---------------------------------------------------------------------------------------------- R6, R10: gates
class TestGates(unittest.TestCase):
    """I43-R6 and I43-R10. The partial gates run once, on a copy of the built tree."""
    reports: dict = {}
    logs: dict = {}

    @classmethod
    def setUpClass(cls):
        repo = copy_repo()
        cls.tmp = repo.parent
        plan = {"M0": "G3,G7", "M1": "G3,G7", "M2": "G3,G7", "M3": "G3,G5,G7,G11V,GEVID"}
        for m, checks in plan.items():
            rep = cls.tmp / f"gate_{m}.json"
            p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rep), "--checks", checks],
                          cwd=repo, timeout=7200)
            cls.logs[m] = p.stdout[-4000:] + p.stderr[-4000:]
            cls.reports[m] = load_json(rep) if rep.exists() else None

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_partial_gates_pass_with_lean(self):
        """I43-R6 (L9): on a copy of the built tree, holon gate --checks G3,G7 passes for M0, M1 and M2, and --checks
        G3,G5,G7,G11V,GEVID for M3 (84c185f's list, with the new Lean G7 for the PAR laws; not every check that passes
        at the prereg (see I43-R6); on be95d6d G11V fails on I31's rev_initializable_120 only, Q36); G7's detail
        reports the cross-kernel
        coverage of every Lean directory of M1, M2 (results and the view) and M3."""
        for m, rep in self.reports.items():
            with self.subTest(milestone=m):
                self.assertIsNotNone(rep, self.logs[m])
                for k, v in rep["checks"].items():
                    self.assertTrue(v["passed"], f"{m} {k}: {v['detail'][-2000:]}")
        for m, dkeys in (("M1", ["M1"]), ("M2", ["M2", "M2/extracted_m1"]), ("M3", ["M3"])):
            detail = self.reports[m]["checks"]["G7"]["detail"]
            for dk in dkeys:
                self.assertRegex(detail, rf"cross-kernel coverage {re.escape(dk)}: \d+/\d+", f"{m}: {detail[-1500:]}")

    def test_semantic_canaries_per_milestone(self):
        """I43-R10 (L9): for M1, M2 and M3, G7 reports a flip:<law> canary and the sidecar's perturb:<law> canary
        (canaries.<gate>.law), each rejected for a semantic reason."""
        for m in ("M1", "M2", "M3"):
            with self.subTest(milestone=m):
                rep = self.reports[m]
                self.assertIsNotNone(rep, self.logs[m])
                detail = rep["checks"]["G7"]["detail"]
                self.assertRegex(detail, r"flip:\w+ rejected \(", detail[-1500:])
                law = side()["canaries"][m]["law"]
                self.assertRegex(detail, rf"perturb:{re.escape(law)} rejected \(", detail[-1500:])

    def test_metrics_report_cross_kernel_coverage(self):
        """Construction (L10): results/<M>/metrics.json of M1, M2 and M3 carries cross_kernel_coverage with the PROVED
        count of its directory (and M2's an extracted_m1 entry), lean4_checked, rate, not_run_by_reason and failed."""
        for m, dkeys in (("M1", ["M1"]), ("M2", ["M2", "M2/extracted_m1"]), ("M3", ["M3"])):
            with self.subTest(milestone=m):
                cov = load_json(ROOT / "results" / m / "metrics.json").get("cross_kernel_coverage")
                self.assertIsNotNone(cov, f"results/{m}/metrics.json has no cross_kernel_coverage")
                for dk in dkeys:
                    c = cov if dk == m else cov.get("extracted_m1")
                    self.assertIsNotNone(c, dk)
                    self.assertEqual(c["proved"], side()["counts"]["proved"][dk])
                    self.assertLessEqual({"proved", "lean4_checked", "rate", "not_run_by_reason", "failed"}, set(c))

    def test_lean_g3_scans_every_lean_directory(self):
        """I43-R6 (L9, review m6): in a copy of the built tree with a theorem proved by sorry appended to one model
        file of every Lean directory, holon gate --checks G3 fails for M1, M2 and M3, its detail naming the planted
        file of each of the milestone's Lean directories (M2: gen/M2/lean and gen/M2/extracted/m1/lean)."""
        repo = copy_repo()
        try:
            planted = {}
            for d in side()["dirs"]:
                f = sorted(need(ROOT / d["lean_dir"] / "models").glob("*.lean"))[0].relative_to(ROOT).as_posix()
                with open(repo / f, "a", encoding="utf-8") as fh:
                    fh.write("\ntheorem holon_planted_g3 : True := by sorry\n")
                planted.setdefault(DIR_MILESTONE[d["dir"]], []).append(f)
            for m, files in sorted(planted.items()):
                with self.subTest(milestone=m):
                    rep = repo.parent / f"g3_{m}.json"
                    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rep), "--checks",
                                   "G3"], cwd=repo, timeout=7200)
                    self.assertTrue(rep.exists(), p.stdout[-2000:] + p.stderr[-2000:])
                    g3 = load_json(rep)["checks"]["G3"]
                    self.assertFalse(g3["passed"], g3["detail"][-2000:])
                    for f in files:
                        self.assertIn(f, g3["detail"])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)

    def test_full_gates_m0_m1_m2_pass(self):
        """I43-R6: the full gates of M0, M1 and M2 pass on a copy of the built tree. G1's re-extraction needs the
        replay toolchain at config/holon.json's paths (replay.solc, replay.forge; tools/setup_env.sh --replay): CI has
        it; where it is missing, as in the prereg's environment, this test fails naming it, never skips (review m7)."""
        repo = copy_repo()
        try:
            for m in ("M0", "M1", "M2"):
                with self.subTest(milestone=m):
                    rep = repo.parent / f"full_{m}.json"
                    p = run_holon(["gate", "--milestone", m, "--root", str(repo), "--report", str(rep)], cwd=repo,
                                  timeout=7200)
                    self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
