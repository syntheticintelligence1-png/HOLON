"""I62: A1 mutation adequacy on real code, the rerun of I61's catalog with I61's defects fixed (whitepaper §9.5 auditor
A1, §9.6, §12.1 L1 "Sensitivity", §13 metric "mutation adequacy", §15.2 M2 exit (b); BUILD_PLAN §4 I22, whose kill
criterion, threshold and exit I62 inherits, as I61 did). This docstring is the contract.

Plant misimplementations in the real Solidity and Go of the pinned Morph checkout, re-extract them with the M2
frontends, decide the laws on what was extracted, replay every witness on the real code, and measure the kill rate of
stratum A against the threshold the human fixed in advance (0.80 of non-equivalent mutants, docs/HUMAN_ANSWERS.md Q6).
The threshold never moves.

Why a rerun. I61 ran its 242 mutants once (docs/iterations/I61.md, results/M2/mutation_i61/, pipeline commit
a233867). Its run showed five defects of the pipeline and one of the gate's rules, each named in the instrument's
replaces.defects with what it did in I61's run and its fix:
  D1 the replay read dec_go's none value as a call not yet run (six law entries: A001 x3, A058, C3 x2);
  D2 a deployment that reverts failed every trace of I20's step harness and I15's trace harness (A076, A098, A100,
     A101, A104: 5 error outcomes);
  D3 a SORT-width law over the header document could not be recorded: no ledger bundle, no coverage entry (A116,
     A120: 2 error outcomes; A027, A031 killed anyway);
  D4 one failing law failed its whole set's run;
  D5 channel runs were never retried;
  D6 9 records held timings or scratch paths in their messages (AGENTS.md rule 7);
  D7 a control's replay disagreement passed the gate (C3, the D1 defect, before any catalog mutant ran);
  D8 the gate's first attempt came after a component-level rehearsal of its checks.
I61's rule: "A defect found in them is a Surprise; a fix needs a rerun of every mutant from scratch, and the first
run's records are reported." Its gate stops at the first passing attempt, so the rerun is a new key: I62. It keeps
I61's 242 mutants, its diff sheet and every value computed from the pinned checkout byte for byte (the instrument's
replaces.carried), carries I61's panel verdicts (adjudication.panel), and changes only what D1-D8 touch. I61's records
stay as its run wrote them, reported as the first run (TestI61FirstRun); I61's tests keep reading I61's files
(HOLON_MUTATE_KEY=I61, an amendment of their run_holon). I62's predictions are I61's measured outcomes with the
fixes' expected effects (TestPredictions): the rerun tests whether the fixes do what they claim and nothing else.

Dependencies and order (instrument preconditions). Catalog mutants run only after (1) this prereg, (2) the build: the
fixes of holon/mutate, the mutation copies of the two harnesses (replay/M2/mutation_i62/), the header document's ledger
bundle (spec/M2/ledger.json) and holon.records' coverage rule, the M1 and M2 records regenerated for the changed
generator closure (generator_sha256 only), (3) a signed-off delta review committed at
docs/iterations/I62_catalog_review.json, (4) the carried adjudication committed alone at
spec/M2/equivalent_mutants_i62.json, (5) a passed harness gate, results/M2/mutation_i62/gate.json, first committed
before any catalog mutant's record, its first attempt not preceded by any run of its checks on the build
(harness_gate.rehearsal), (6) a baseline that reproduces the pinned statuses, documents and projection, and (7) I21's
exit at the records' pipeline_commit. Each step descends from this prereg.

Frozen inputs (this prereg commit; the instrument's sha256 is pinned below as INSTRUMENT_SHA256)
  spec/M2/lib/mutation_catalog_i62.json  the instrument: I61's (spec/M2/lib/mutation_catalog_i61.json) with
        iteration I62 and these fields changed: preregistration_version, doc, replaces (key I61, first_run, rule,
        carried, defects D1-D8), limitations (four sentences added), preconditions (I62's paths), pins (the
        i61_pipeline_commit added), kill_criterion.errors, replay (doc, semantics, trace), harness_gate (doc,
        checks.model, checks.controls, record, rehearsal, before_prereg), projection.output, channels (i20_step,
        retry), reporting (metric, determinism, first_run) and adjudication; every other field, the 242 mutants
        among them, is I61's (TestInstrument).
  spec/M2/lib/mutation_diff_sheet_i61.md  I61's diff sheet, unchanged: the instrument's diff_sheet is I61's.
  The pinned checkout (config/holon.json replay.morph at target.commit) and the OpenZeppelin units (replay.sol_deps
  /node_modules), read only. Every mutant lives in a scratch copy.

Delegated steps, before any catalog mutant runs (instrument "adjudication"; docs/HUMAN_ANSWERS.md delegated answers)
  docs/iterations/I62_catalog_review.json  one fresh agent, both lenses, reads this instrument in full against I61's,
        I61's signed-off review and the fixes' diff (instrument adjudication.review): {"what", "who", "delegation",
        "instrument": {"path", "sha256"}, "base_review": {"path", "sha256"}, "verdict", "reviews": {"fairness" |
        "soundness": {"sign_off", "blocking", "advisory", "checked", "forbidden_files_touched"}}}. Signed off iff
        both lenses sign off with no blocking finding; if not, nothing runs and a replacement is preregistered under a
        new key. Its first commit descends from this prereg commit.
  spec/M2/equivalent_mutants_i62.json  I61's adjudication with instrument and review naming I62's and the delegation
        stating the carry; every verdict I61's: {"adjudication_version": "holon-equivalent-mutants/0.2",
        "instrument": {"path", "sha256"}, "mutants_sha256", "diff_sheet_sha256", "review": {"path", "sha256"},
        "adjudicator": "delegated_panel", "delegation": {"decision", "panel", "procedure", "blindness_audit"},
        "verdicts": {"<id>": I61's verdict}}. Committed alone, its first commit descends from the review's and is a
        proper ancestor of the first commit of any catalog mutant's record.
  The reviewer does not read the files instrument adjudication.forbidden names (the I62 forecasts, prompt, tests and
  report, I62's results, and I61's outcomes beyond what the instrument states) and lists the forbidden files it
  touched. The instrument's own statements that border on outcomes are stated (adjudication.known_exposure).

The harness gate (instrument harness_gate), after the build and before any catalog mutant
  `python -m holon mutate gate` runs its four checks on the original code and the four planted controls and writes
  results/M2/mutation_i62/gate.json: {"instrument": {"path", "sha256"}, "pipeline_commit", "attempts":
  [{"pipeline_commit", "checks": {"i16" | "model" | "null" | "controls": {"passed": bool, "detail": str}}, "passed":
  bool, "fix": null | str}], "passed": bool}; the top-level pipeline_commit is the last attempt's. Every attempt is
  kept; a fix of holon/mutate after a failed attempt names it ("fix") and is reported (no catalog mutant has run by
  then); a failure caused by a tool the rules keep unchanged stops the run for the human's decision. No check of the
  gate runs on the build before its first attempt (harness_gate.rehearsal). The controls' records are
  results/M2/mutation_i62/controls/<C1..C4>.json, in the record format below (id "C1".."C4", stratum, operator and
  structural null), and each must be killed through every law its instrument entry's "expected" names, by the "how"
  it names (K1, or K2 with the named falsifier kind), with no replay disagreement and no error of step "replay" in its
  record (D7): C1 and C2 in the codec library and the Go encoder, C3 inside the copied build block of the entry
  function, C4 at the copied require through a partiality witness. The gate needs neither the review nor the
  adjudication.

What I62 changes, beside its paths (the instrument's replaces.defects; holon/mutate serves the key
HOLON_MUTATE_KEY, I62 unless it names I61)
  D1  holon.mutate.replay: a role whose value is none (dec_go's None) is a value, unequal to every some(...) value; a
      field of none, or a role called with none as its argument, is no execution (replay.semantics).
  D2  channels.i20_step runs replay/M2/mutation_i62/HolonStepBase.sol in place of I20's
      replay/M2/solidity/HolonStepBase.sol, and the replay of trace laws runs
      replay/M2/mutation_i62/HolonTraceReplay.t.sol in place of replay/M1/solidity/HolonTraceReplay.t.sol: each is
      the original file plus a deployment probe per trace (TestFixes reads the difference). A trace whose deployment
      reverts writes F <tid> <revert data> (step harness) or logs every step "rev deploy: <reason>" (trace harness)
      and runs no step. On a mutant, the i20_step run then compares only the deployed traces: a run whose every
      deployment reverts has steps 0, no disagreement, no width observation, and every baseline corpus step as a
      corpus difference. The baseline's deployments must all succeed. I20's and I15's own files are unchanged.
  D3  spec/M2/ledger.json registers spec/M2/facts/morph_header.extracted.json's bundle: one entry per assumption the
      document declares (its id, text and source "<document>#/assumptions/<i>"), each introduced by "*", and no
      no_assumption group; holon.records.coverage_field returns null for a law over a document whose extraction is
      not "transitions" (holon coverage reports transitions documents only).
  D4  a set's `holon run --milestone M2` that fails twice is retried law by law (each law alone, twice at most); only
      the laws that fail alone are error, the others are decided by one run of their own set
      (kill_criterion.errors).
  D5  a channel run that does not complete is retried once; the record keeps the second attempt's entry
      (channels.retry).
  D6  every message a step writes is scrubbed before it is cut to length (holon.mutate.common.scrub): Python
      traceback frames dropped, every path of the run (work directory, HOLON root, pinned checkout, sol_deps, Python
      prefixes, home) replaced by <name>, every duration by <t> (reporting.determinism).
  D7, D8  the gate (above).
  results/M2/metrics.json "mutation_adequacy" reads I62's summary once it exists (reporting.metric).

Deliverables
  holon/mutate/ (operators.py, project.py, replay.py, run.py; helpers may be added), harness sources under
  replay/M2/mutation_i61/ and replay/M2/mutation_i62/ (D2), the dispatch `python -m holon mutate ...` in holon/__main__.py. holon/mutate names no file,
  function, variable, type or field of the target: everything target-facing comes from the instrument and the null
  mutant's documents.
    holon.mutate.operators.catalog(instrument: dict, checkout: Path, sol_deps: Path) -> list[dict]
        Matches every operator's pattern on the in-scope files (Solidity through solc's compact AST, Go through go/ast)
        and returns the mutants with exactly the instrument's keys and values, in its order, stillborn ones excluded.
    holon.mutate.operators.apply(mutant: dict, data: bytes) -> bytes
        data[:offset] + replacement + data[offset + length:], after checking data[offset:offset + length] is the
        mutant's original text (ValueError otherwise). The planted controls (harness_gate.controls) apply the same way.
    holon.mutate.replay.call(tree: Path, role: str, arg, sol_deps: Path | None = None) -> dict
        Runs one M0 role on the code of a source tree laid out as the checkout (contracts/, common/, the go.work
        modules), OpenZeppelin units from sol_deps (default config's; a mutant of an OpenZeppelin unit passes its
        scratch sol_deps): {"kind": "value" | "revert" | "panic", "value":
        "0x.." (encoders) | bool (predicates) | null or ["0x..", ...] (dec_go) | null, "detail": str,
        "revert_line": null | "<unit>:<line>" (a Solidity revert: the line of the reverting statement in the tree's
        text, mapped back from the generated harness)}. arg is a Header
        ({field: "0x.."}) for enc_sol, enc_go_v0, enc_go_v1, or "0x.." bytes for ok_sol, ok_go, dec_go. enc_sol follows
        instrument replay.m0: generated from the tree's own Rollup text with the statement locations and field map of
        the null mutant's document; every store call whose op maps a Header field takes the witness value at the
        Header field's width; only the version's require is copied; the sink becomes the return of the hashed bytes.
        The Go roles run through a Go test in the tree's own package that makes I16's harness's calls with a recover
        per call (I16's replay/M2/go/holon_codec_test.go does not recover: one panic would fail every Go edge).
    holon.mutate.replay.claim(tree: Path, law: dict, env: dict, sol_deps: Path | None = None) -> True | False | None
        The law's claim at one assignment ({binder: value}) on that code (instrument replay.m0, replay.semantics):
        True holds, False falsified, None not an execution (some role call, at the top level or inside another call,
        has no value).
    holon.mutate.replay.trace_claim(tree: Path, law: dict, trace: list, sol_deps: Path | None = None) -> bool
        A trace law's claim (an M2 law of laws/M2, or an M1x law) on one witness trace (the step format of
        replay/M2/report.json traces, holon.mreplay's) replayed on the tree's own Rollup (instrument replay.semantics):
        False iff a step panics at the law's site (its basis span); a reverted step is a no-op, never a violation;
        a trace whose deployment reverts runs no step and holds (D2).
  CLI (exit 0 ok; 1 --check found a difference; 2 refused, nothing written)
    python -m holon mutate list                         the catalog recomputed from the pinned checkout, as JSON
    python -m holon mutate sheet [--out PATH] [--check]  the diff sheet (default spec/M2/lib/mutation_diff_sheet_i61.md)
    python -m holon mutate project [--documents DIR] [--out PATH] [--check]
                                                         the projected header document (default
                                                         gen/M2/mutation_i62/header.projected.json, from spec/M2/facts)
    python -m holon mutate replay --i16 [--tree DIR]     every role of I16's binding (replay/M2/implementations.json)
                                                         run through holon.mutate.replay on I16's per-edge corpus
                                                         (holon.corpus, I16's seeds): prints {edge: {"compared": n,
                                                         "outputs_sha256": "<hex>"}} with outputs digested as I16's
                                                         records digest the real side
    python -m holon mutate gate [--check]                the harness gate (above)
    python -m holon mutate run --milestone M2 [--only A001,...] [--control C1,...] [--baseline-only] [--work DIR]
                               [--jobs N] [--no-carry] [--dry-run] [--check]
    python -m holon mutate rate [--check]                results/M2/mutation_i62/summary.json from the records
    holon.mutate.run.model_verdict(model_bend: Path) -> str | None
        Checks a generated model module alone (its definitions, no law) with the pinned Bend: the first line of the
        checker's output when it is "ALL PROOFS CHECK" or "SOME PROOFS FAIL", else None (K2 (b)'s model check).
  run refuses when the pinned checkout is dirty or not at target.commit, when an in-scope file's sha256 differs from
  the instrument's, and, for catalog mutants, while a precondition is missing (instrument preconditions.refusal): the
  review or the adjudication is missing, does not parse, names another instrument, catalog or sheet, misses an id, or
  the review is not signed off; gate.json is missing, names another instrument or has not passed at the run's pipeline
  commit; the baseline record is missing or does not reproduce (statuses, documents' normalized sha256, projection);
  I21's exit does not hold at the run's pipeline commit. --baseline-only and --control need none of these. --dry-run checks every input and
  exits. --check of run materializes the tree of the records' pipeline_commit (git archive into scratch), reruns there
  the baseline and the listed mutants with --no-carry, and exits 0 iff the rerun's records equal the committed ones
  byte for byte except each law's "decided" field; a difference is an error of the affected laws, reported.

The pipeline, per mutant, per control and for the baseline (the null mutant: the unmutated pinned files)
  1. Source: a scratch copy of the pinned checkout and of sol_deps with the mutant applied (operators.apply); its
     sha256 is the mutant's mutant_sha256.
  2. Re-extraction with the M2 frontends, unchanged: `holon extract solidity` with copies of
     spec/M2/lib/extract_solidity.json and extract_rollup.json (target.commit null) on the scratch tree (include path
     the scratch sol_deps), `holon extract go` with a copy of spec/M2/lib/go_frontend.json. Documents go to scratch.
  3. A scratch copy of the HOLON tree at pipeline_commit whose spec/M2/facts/*.extracted.json are the step-2 documents
     and whose config/holon.json names the scratch source tree and sol_deps (extract.sources, replay.morph,
     replay.sol_deps, and for a mutant of an OpenZeppelin unit the scratch sol_deps' tree hash; forge, solc and go stay
     pinned); the three law sets of instrument law_sets are decided there (M0 on the projected header document, M1x
     through holon differential on m1_view, M2 through holon derive, holon model and holon run, the SORT-width laws
     reading the mutant's own gen/M2/extracted/model.bend and the width values of its own i20_step run whenever its
     rollup document changed). Each law's own decided input
     (law_sets.own_input) is hashed; a law whose own input equals the baseline's is carried (law_sets.carrying);
     mutant laws are matched to baseline laws (law_sets.matching). The edges, actions and predicted sets are also
     recomputed on the step-2 documents (predicted.recomputed).
  4. For every law: the proof attempt of the generator that proved it at baseline (when PROVED at baseline and
     decided), with the first line of the checker's output and the verdict of the mutant's generated model checked
     alone; the model hits (replay.hits: holon.refute's candidates in order, at
     most 16 hits); the replay of each hit on the mutant and on the original tree; the recorded witness and its
     Bend-checked counter-law; and for a law PROVED at baseline and UNKNOWN on the mutant the K2 (c) search over the
     first 16 candidates, for a falsification and, failing that, a partiality witness (replay.partiality), with the
     model tie of the candidate found (replay.model_tied).
  5. Detection channels (instrument channels; never a kill): i20_step for the baseline and every stratum-A Solidity
     mutant, i16_edge for the baseline, every stratum-A Go mutant and every stratum-A Solidity mutant with edges.
  6. The kill decision and the outcome (instrument kill_criterion; errors are scoped to laws).
  No step writes a committed file outside the outcome paths (spec/M2/disagreements.json included).

Kill criterion (BUILD_PLAN I22, verbatim, read as the instrument's kill_criterion says; recomputed by TestResults)
  "A mutant is killed iff the obstruction predicted for its operator appears, localized to the mutated edge: a law
  moves to REFUTED, with a witness that replays on the mutant code, or a PROVED law loses its proof. A replay
  disagreement alone is recorded as 'extraction defect detected', not as a kill."
  decided     REFUTED with a Bend-checked counter-law is REFUTED whatever happened to the proof attempt; PROVED is PROVED
  predicted   the record's laws with "predicted": true (the instrument's predicted sets, plus new laws whose mutant
              DERIVATION entry points meet the mutant's actions)
  K1          baseline PROVED or UNKNOWN (or absent, with site_in_mutated_function true), mutant REFUTED, counter_law
              marker "ALL PROOFS CHECK", and witness = the first replay entry with mutant true and original false
  K2          baseline PROVED, mutant UNKNOWN, own_input.changed, proof.generator the baseline record's proof
              generator, proof.exit_code not null, proof.verdict "SOME PROOFS FAIL" (the first line of the checker's
              output; holon.bend's marker alone falls back to "SOME PROOFS FAIL" on any non-zero exit) and
              proof.model_verdict "ALL PROOFS CHECK" (the mutant's generated model checked alone: the pinned Bend
              prints "SOME PROOFS FAIL" for a parse or type error of a generated file too),
              falsifier not null (kind "falsification" or "partiality", tried 1..16); without falsifier:
              proof_lost_unwitnessed (never a kill). A law PROVED at baseline, decided (run) on the mutant, neither
              REFUTED with a checked counter-law nor PROVED there, with no such completed, rejected attempt (a timeout,
              a checker exit with no verdict line, a model that does not check alone, Unsupported, None) is "error",
              never UNKNOWN
  masked      a predicted law, baseline REFUTED, and some replay entry with mutant true and original false
              (masked_obstruction)
  replay_disagreement / baseline_finding  a move to REFUTED (baseline PROVED, UNKNOWN or absent, whether or not the
              law is K1-eligible) with no replay entry true on the mutant / with every such entry also true on the
              original
  killed      some predicted law has how K1 or K2; outcome error iff not killed and some predicted law is "error"
  unpredicted / recomputed_only  K1 or K2 on a law outside the frozen predicted set / on such a law that the record's
              recomputed predicted set holds: listed, never counted

Projection (holon/mutate/project.py; instrument projection): holon-facts/0.1 with additive extensions only, so that
facts/morph_header.json compiles to the same bytes as before; gen/M2/mutation_i62/header.projected.json is the
projection of the committed documents and `holon mutate project --check` reproduces it.

Outputs (canonical JSON: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; no timestamps, scratch paths or process
ids; timings stay in scratch; every message scrubbed before it is cut, D6)
  results/M2/mutation_i62/baseline.json, results/M2/mutation_i62/<id>.json, one per mutant, and
  results/M2/mutation_i62/controls/<C1..C4>.json:
    {"id": "baseline" | "<id>" | "C1" | "C2", "stratum": null | "A" | "B", "operator": null | op,
     "pipeline_commit": "<40 hex>",
     "documents": {"<spec/M2/facts/...>": {"sha256", "normalized_sha256", "changed": bool}},  every step-2 document
     "extraction": {"status": "ok" | "error", "errors": {"<document>": "<message>"}},
     "projection": {"normalized_sha256": hex | null, "changed": bool | null, "error": null | str},
     "recomputed": null (baseline) | {"edges": [role], "actions": [action], "predicted": {"M0", "M1x", "M2": [law]}},
     "laws": {"<law id>": {"set": "M0" | "M1x" | "M2", "matched_from": null | "<mutant law id>",
                           "family": "PAR-codec" | "PAR-round-trip" | "PAR-domain" | "M1x:<rule>" | "M2:<rule>/<subform>",
                           "entry_points": null (M0, M1x) | [action] (M2: the run's DERIVATION entry_points),
                           "baseline": status | "absent", "mutant": status | "absent" | "error",
                           "decided": "run" | "carried" | null, "own_input": {"sha256": hex | null, "changed": bool | null},
                           "predicted": bool, "basis_span": null | "<unit>:<lo>[-<hi>]", "site_in_mutated_function": bool,
                           "proof": null | {"generator", "exit_code": int | null, "marker",
                                            "verdict": null | "ALL PROOFS CHECK" | "SOME PROOFS FAIL",
                                            "model_verdict": null | "ALL PROOFS CHECK" | "SOME PROOFS FAIL"},
                                     (verdict: the first line of the checker's output when it is one of the two
                                      markers, else null),
                           "hits": null | [label], "replay": null | [{"label", "mutant": bool, "original": bool}],
                           "witness": null | label, "counter_law": null | {"exit_code", "marker"},
                           "falsifier": null | {"label", "tried": n, "kind": "falsification" | "partiality",
                                                "model_tied": bool, "role": null | role,
                                                "revert_line": null | "<unit>:<line>"},
                           "witness_fits_entry": null | bool,
                           "how": null | "K1" | "K2" | "proof_lost_unwitnessed" | "masked_obstruction"
                                  | "replay_disagreement" | "baseline_finding",
                           "error": null | str}},
     "kill": {"killed": bool, "by": [{"law", "how"}], "unpredicted": [{"law", "how"}]},
     "recomputed_only": [{"law", "how"}],
     "masked_obstructions": [law], "proof_lost_unwitnessed": [law], "replay_disagreements": [law],
     "baseline_findings": [law], "errors": [{"step", "laws": [law], "message"}],
     "refinement": {"channels": [{"harness": "i20_step" | "i16_edge", "steps": n, "new_disagreements": [id],
                                  "corpus_differences": [step id] | null, "error": null | str}]},
     "extraction_defect_detected": bool | null, "corpus_detected": bool | null,
     "outcome": "killed" | "survived" | "error",
     "class": null | "equivalent" | "error" | "extraction_gap" | "masked" | "baseline_finding"
              | "proof_lost_unwitnessed" | "rule_gap",
     "gap_stage": null | "frontend" | "model" | "replay", "rule_gap_kind": null | "no_law" | "law_unmoved",
     "structural": the instrument's structural class (null for the baseline and the controls)}
    The baseline's statuses fill every record's "baseline"; the baseline decides every law ("decided": "run") and
    reproduces the pinned statuses, the committed documents (every spec/M2/facts/*.extracted.json) and the committed
    projection. Every law that is decided (status, not "absent" or "error") has a 64-hex own_input.sha256 and a bool
    changed; projection.changed is a hash comparison with the baseline's. family comes from the law's set (M0 by
    prefix: L_par_hdr_*, L_rt_go_*, L_dom_hdr), from laws/M1/<id>.json "rule" (M1x) or from the DERIVATION entry's
    rule and subform (M2). site_in_mutated_function is true iff basis_span is "<unit>:<lo>[-<hi>]" with unit the
    mutant's file and lo..hi inside the line range of the Solidity function the mutant mutates; a law absent at
    baseline is predicted iff its entry_points meet the mutant's actions. witness_fits_entry, for a law with a
    recorded witness, a falsifier or a masked obstruction, says whether that witness fits an entry point as
    equivalence.contradictions defines it (a Go mutant's always does; a Solidity mutant's when every enc_sol call it
    executes satisfies enc_sol's unprojected revert conditions and the extracted Header's value types, or when it
    executes only the loader), null for other laws. A partiality falsifier names the role whose call reverted and the
    revert's line, one of that role's revert_lines; a falsification has both null. hits holds at most 16 labels. Lists are
    sorted. A killed mutant has class, gap_stage and rule_gap_kind null; a survivor's class follows instrument
    survivor_classes, the first rule that holds in its listed order.
  results/M2/mutation_i62/summary.json:
    {"version": "holon-mutation/0.3", "iteration": "I62", "milestone": "M2", "pipeline_commit",
     "instrument": {"path", "sha256"}, "mutants_sha256", "review": {"path", "sha256"}, "adjudication": {"path", "sha256"},
     "gate": {"path", "sha256"}, "threshold": 0.8, "threshold_stratum": "A", "seed": 20261061,
     "strata": {"A" | "B" | "all": {"mutants", "killed", "killed_k1", "equivalent", "killed_equivalent", "errors",
                                  "rate_all": {"num", "den", "value"}, "rate_non_equivalent": {"num", "den", "value"},
                                  "meets_threshold": bool (A) | null (B, all)}},
     "non_error": {"A" | "B": {"rate_all": {...}, "rate_non_equivalent": {...}}},
     "by_language": {"A" | "B": {"solidity" | "go": {"mutants", "killed", "errors", "equivalent", "rate_all",
                                                    "rate_non_equivalent"}}},
     "per_site": {"A" | "B": {"sites", "killed", "equivalent", "rate_non_equivalent": {...}}},
     "B_codec_functions": {"mutants", "killed", "equivalent", "rate_all": {...}, "rate_non_equivalent": {...}},
     "k1_only": {"A" | "B": {"num", "den", "value"}},
     "plan_literal": {"A" | "B": {"num", "den", "value"}}, "new_law_kills": {"A" | "B": n},
     "k2_model_tied": {"A" | "B": {"tied": n, "untied": n}},
     "detection": {"A" | "B": {"num", "den", "value"}},
     "unpredicted_rate": {"A" | "B": {"num", "den", "value"}}, "masked_rate": {"A" | "B": {"num", "den", "value"}},
     "dedup": {"A" | "B": {"rate_all": {...}, "rate_non_equivalent": {...}}},
     "by_operator": {"A" | "B": {op: {"mutants", "killed", "killed_k1", "equivalent", "errors", "unpredicted", "masked",
                                     "proof_lost_unwitnessed"}}},
     "by_family": {"A" | "B": {family: {"predicted", "killed"}}},
     "contradicted": {"function_level": [{"id", "why"}], "reachable": [{"id", "why"}]},   (reachable: entry-fit)
     "rate_non_equivalent_reversed": {"function_level": {...}, "reachable": {...}},
     "structural_agreement": {class: {survivor class (with "/<gap_stage>" or "/<rule_gap_kind>"): n}},
     "survivors": [{"id", "class", "gap_stage", "rule_gap_kind", "structural", "why"}],
     "unpredicted": [{"id", "law", "how"}], "recomputed_only": [{"id", "law", "how"}],
     "masked_obstructions": [{"id", "law"}], "proof_lost_unwitnessed": [{"id", "law"}], "errors": [id],
     "extraction_defects": [id], "corpus_detected": [id]}
    value = num / den; meets_threshold = 5 * num >= 4 * den of strata.A.rate_non_equivalent (exact integers).
    unpredicted_rate and masked_rate: mutants of the stratum with some unpredicted obstruction (kill.unpredicted) or
    some masked obstruction, over the stratum's mutants. by_family covers every family some record's law carries.
    The lists unpredicted, recomputed_only, masked_obstructions, proof_lost_unwitnessed (sorted by id, then law),
    errors, extraction_defects and corpus_detected (sorted ids) are exactly the records'.
  results/M2/mutation_i62/gate.json (the harness gate, above).
  gen/M2/mutation_i62/header.projected.json (Projection).
  gen/M2/mutation_i62/baseline_inputs.json and gen/M2/mutation_i62/i20_corpus.json (the baseline's inputs of the
    later units, as I61's).
  results/M2/metrics.json "mutation_adequacy" (whitepaper §13; §12.1: certificates report Sensitivity), read by
    holon/metrics.py from the summary: {"source": "results/M2/mutation_i62/summary.json", "threshold": 0.8,
    "rate_all": strata.A.rate_all, "rate_non_equivalent": strata.A.rate_non_equivalent, "meets_threshold":
    strata.A.meets_threshold}, I22-R6's name and shape (I23's prereg 60d9c42 reads it); it leaves not_applicable. The
    gate regenerates the file; it is shared, not an outcome path.

Rules
  - AGENTS.md is binding. Never edit facts/, spec/M1/facts/, laws/M0/ or laws/M1/; never write to the pinned checkout
    or to sol_deps.
  - The extractors, the M0 pipeline (but the projection's additive extensions of the M0 generator and refuter,
    instrument projection.extensions, under which facts/morph_header.json compiles and decides exactly as before),
    holon differential, holon derive, holon fragments and the I16 and I20 harnesses run unchanged, through their library
    entry points on the scratch trees (their CLIs refuse any tree but the pinned checkout). A defect found in them is a
    Surprise; a fix needs a rerun of every mutant from scratch, and the first run's records are reported.
  - I62's exceptions to the rule above are the instrument's replaces.defects: the mutation copies of the step and
    trace harnesses' Solidity (D2), the header document's ledger bundle and holon.records' coverage rule (D3),
    which change no committed law, record status or output (gate M2 G1; M1 and M2 records regenerated for the
    generator closure, generator_sha256 only).
  - I61's records, summary, gate and report are never edited; the report compares every I62 record with I61's
    (reporting.first_run) and files every change no defect explains as a Surprise.
  - Survivors are filed mechanically (instrument survivor_classes), never explained away; each record keeps its
    instrument structural class beside the class it received.
  - No skips. The catalog never changes after the sign-off, the threshold never moves, predictions are never tuned.
"""
import ast
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

from tests_m2._m2 import ROOT, holon_module, load_json, predictions

SPEC2 = ROOT / "spec" / "M2"
INSTRUMENT = SPEC2 / "lib" / "mutation_catalog_i62.json"
INSTRUMENT_SHA256 = "2328e970f039885eff874d9bb55f0f9935edd081cf3c593b5f05bc5bd9790a4b"
SHEET = SPEC2 / "lib" / "mutation_diff_sheet_i61.md"
ADJ = SPEC2 / "equivalent_mutants_i62.json"
REVIEW = ROOT / "docs" / "iterations" / "I62_catalog_review.json"
RESULTS = ROOT / "results" / "M2" / "mutation_i62"
SUMMARY = RESULTS / "summary.json"
GATE = RESULTS / "gate.json"
CONTROLS = RESULTS / "controls"
PROJECTED = ROOT / "gen" / "M2" / "mutation_i62" / "header.projected.json"
PIN = "e20648e05052ad37db3f874c66b7a71af1381752"
I61_PREREG = "e18d2ea2c854f817d653d5c05c6440db72d20b92"
I61_PIPELINE = "a233867f989a97a4b0cbed2799863abe0a74a915"
I61_INSTRUMENT = SPEC2 / "lib" / "mutation_catalog_i61.json"
I61_ADJ = SPEC2 / "equivalent_mutants_i61.json"
I61_REVIEW = ROOT / "docs" / "iterations" / "I61_catalog_review.json"
I61_RESULTS = ROOT / "results" / "M2" / "mutation_i61"
STATUSES = ("PROVED", "REFUTED", "UNKNOWN")
LAYOUT_OPS = ("mstore_offset", "shl_width")
CMP_OPS = ("cmp_boundary", "cmp_boundary_mirror")
EDGE_ROLE = {"enc_sol": "enc_sol", "ok_sol": "load_sol"}
ROLLUP = "contracts/contracts/l1/rollup/Rollup.sol"
PREMISE_LIMITED = ["A148", "A162", "A165", "A166", "A167", "A168"]
# the fields the I62 instrument changes (replaces.defects; every other field is I61's)
CHANGED_FIELDS = ["adjudication", "channels", "doc", "harness_gate", "iteration", "kill_criterion", "limitations", "pins",
                  "preconditions", "preregistration_version", "projection", "replaces", "replay", "reporting"]

# ---------------------------------------------------------------------------------------------- the forecast (I62-P*)
# I61's measured outcomes (results/M2/mutation_i61/, pipeline commit a233867) with the fixes' expected effects
# (instrument replaces.defects): first_run_view and expected_view below.
M0_BASELINE = {"L_par_hdr_v0": "PROVED", "L_par_hdr_v1": "PROVED", "L_rt_go_v0": "PROVED", "L_rt_go_v1": "PROVED",
               "L_rt_go_v2": "PROVED", "L_par_hdr_v2": "REFUTED", "L_par_hdr_ssvh": "REFUTED", "L_dom_hdr": "REFUTED"}


def ids(prefix: str, a: int, b: int) -> list:
    return [f"{prefix}{i:03d}" for i in range(a, b + 1)]


TCE = ["A110", "A111", "A112", "A113", "A121", "A122"]
A_BY_OPERATOR = {"mstore_offset": (22, 21), "shl_width": (12, 8), "drop_delete": (7, 0), "swap_cursor": (12, 0),
                 "cmp_boundary": (23, 2), "cmp_boundary_mirror": (15, 1), "mload_offset": (22, 0), "shr_width": (9, 0),
                 "putuint64_offset": (14, 14), "copy_offset": (28, 26), "drop_len_check": (4, 0),
                 "go_slice_offset": (24, 24)}
NONE_VALUE = {"A001": ["L_rt_go_v0", "L_rt_go_v1", "L_rt_go_v2"], "A058": ["L_rt_go_v1"]}   # D1
NONE_VALUE_STILL_DEFECT = ["A058"]         # its i16_edge run has new disagreements of its own
GENESIS = ["A076", "A098", "A100", "A101", "A104"]                                       # D2
HEADER_WIDTH = ["A027", "A031", "A116", "A120"]                                          # D3, D4
FORMER_ERRORS = GENESIS + ["A116", "A120"]
WIDTH_LAWS = ["L_sort_width_batchheadercodecv0_144_1abeb29c", "L_sort_width_batchheadercodecv0_166_8ad80b42"]

# ---------------------------------------------------------------------------------------------- helpers
def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canon(x) -> str:
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def instrument() -> dict:
    return load_json(INSTRUMENT)


def need(p: Path):
    if not p.is_file():
        raise AssertionError(f"{p.relative_to(ROOT)} is missing")
    return load_json(p)


def config() -> dict:
    return load_json(ROOT / "config" / "holon.json")


def morph() -> Path:
    return Path(config()["replay"]["morph"])


def sol_deps() -> Path:
    return Path(config()["replay"]["sol_deps"]) / "node_modules"


def pinned(path: str, commit: str) -> bytes:
    """A file of the pinned checkout at the target commit (git show, read only). Missing: a failure."""
    p = subprocess.run(["git", "-C", str(morph()), "show", f"{commit}:{path}"], capture_output=True)
    if p.returncode != 0:
        raise AssertionError(f"cannot read {path} at {commit} from {morph()}: {p.stderr.decode()[-300:]}")
    return p.stdout


def source(inst: dict, path: str) -> bytes:
    f = inst["in_scope"]["files"][path]
    if f["root"] == "checkout":
        return pinned(path, inst["target"]["commit"])
    data = (sol_deps() / path).read_bytes()
    if sha256(data) != f["sha256"]:
        raise AssertionError(f"{path} in sol_deps is not the pinned bytes")
    return data


def sources(inst: dict) -> dict:
    return {f: source(inst, f) for f in inst["in_scope"]["files"]}


def at_pin(path: str) -> bytes:
    p = subprocess.run(["git", "-C", str(ROOT), "show", f"{PIN}:{path}"], capture_output=True)
    if p.returncode != 0:
        raise AssertionError(f"cannot read {path} at {PIN} (this check needs the real checkout's history)")
    return p.stdout


def pin_json(path: str):
    return json.loads(at_pin(path))


def git(*args: str) -> str:
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed (this check needs the real checkout's history): "
                             f"{p.stderr[-300:]}")
    return p.stdout.strip()


def is_ancestor(a: str, b: str) -> bool:
    p = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", a, b], capture_output=True)
    if p.returncode not in (0, 1):
        raise AssertionError(f"git merge-base failed: {p.stderr.decode()[-300:]}")
    return p.returncode == 0


def first_add(path: str) -> str:
    out = git("log", "--diff-filter=A", "--format=%H", "--", path).splitlines()
    if not out:
        raise AssertionError(f"{path} was never committed")
    return out[-1]


def prereg_commit() -> str:
    """The first commit whose spec/M2/predictions.json holds key I62."""
    for c in git("log", "--reverse", "--format=%H", "--", "spec/M2/predictions.json").splitlines():
        p = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:spec/M2/predictions.json"], capture_output=True)
        if p.returncode == 0 and "I62" in json.loads(p.stdout).get("iterations", {}):
            return c
    raise AssertionError("no commit introduces key I62")


def apply(m: dict, data: bytes) -> bytes:
    return data[:m["offset"]] + m["replacement"].encode() + data[m["offset"] + m["length"]:]


def render_sheet(inst: dict, srcs: dict) -> str:
    """The reference rendering of the diff sheet (computation item 10)."""
    out = "\n".join(inst["diff_sheet"]["header"]) + "\n"
    for m in inst["mutants"]:
        b = srcs[m["file"]]
        diff = list(difflib.unified_diff(b.decode().splitlines(), apply(m, b).decode().splitlines(),
                                         "a/" + m["file"], "b/" + m["file"], n=3, lineterm=""))
        out += (f"\n## {m['id']} {m['operator']} {m['variant']} {m['file']}:{m['line']}:{m['col']} {m['function']}\n\n"
                "```diff\n" + "\n".join(diff) + "\n```\n")
    return out


def run_holon(args, cwd=ROOT, timeout=3600):
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, "HOLON_MUTATE_KEY": "I62"})


def records() -> dict:
    return {m["id"]: need(RECORDS_DIR / f"{m['id']}.json") for m in instrument()["mutants"]}


RECORDS_DIR = RESULTS


def by_id(inst: dict) -> dict:
    return {m["id"]: m for m in inst["mutants"]}


def normalized_sha256(doc: dict) -> str:
    """instrument law_sets.own_input: the document without its provenance, the top-level 'extraction' block and its
    target's 'commit' (a scratch extraction records null there)."""
    d = {k: v for k, v in doc.items() if k != "extraction"}
    if isinstance(d.get("target"), dict):
        d["target"] = {k: v for k, v in d["target"].items() if k != "commit"}
    return sha256(canon(d).encode())


def statement_calls(law: dict) -> set:
    out, stack = set(), [law["statement"]]
    while stack:
        t = stack.pop()
        if isinstance(t, dict):
            if isinstance(t.get("call"), str):
                out.add(t["call"])
            stack.extend(t.values())
        elif isinstance(t, list):
            stack.extend(t)
    if "dec_go" in out:
        out.add("ok_go")
    return out


# ---- the kill criterion, recomputed from a record's law entry
def law_how(e: dict):
    b, m = e["baseline"], e["mutant"]
    rep = e.get("replay") or []
    first_local = next((r["label"] for r in rep if r["mutant"] is True and r["original"] is False), None)
    if b == "REFUTED":
        # instrument kill_criterion.masked_obstruction: a *predicted* law REFUTED at baseline
        return "masked_obstruction" if first_local is not None and e["predicted"] is True else None
    if m == "REFUTED" and b in ("PROVED", "UNKNOWN", "absent"):
        cl = e.get("counter_law") or {}
        eligible = b in ("PROVED", "UNKNOWN") or e.get("site_in_mutated_function") is True
        if eligible and first_local is not None and e.get("witness") == first_local \
                and cl.get("marker") == "ALL PROOFS CHECK":
            return "K1"
        # a move to REFUTED is classified whether or not the law is K1-eligible (kill_criterion)
        if not any(r["mutant"] is True for r in rep):
            return "replay_disagreement"
        if all(r["original"] is True for r in rep if r["mutant"] is True):
            return "baseline_finding"
        return None
    if b == "PROVED" and m == "UNKNOWN":
        pr = e.get("proof") or {}
        a = (e.get("own_input") or {}).get("changed") is True
        # K2 (b): a completed attempt whose checker printed 'SOME PROOFS FAIL' first, over a generated model that
        # checks alone (the pinned Bend prints that line for a parse or type error of a generated file too; S-A2)
        rejected = pr.get("exit_code") is not None and pr.get("verdict") == "SOME PROOFS FAIL" \
            and pr.get("model_verdict") == "ALL PROOFS CHECK"
        if a and rejected:
            f = e.get("falsifier")
            return "K2" if f and f.get("kind") in ("falsification", "partiality") else "proof_lost_unwitnessed"
    return None


def recompute_kill(rec: dict) -> dict:
    by, un = [], []
    for law in sorted(rec["laws"]):
        e = rec["laws"][law]
        h = law_how(e)
        if h in ("K1", "K2"):
            (by if e["predicted"] else un).append({"law": law, "how": h})
    return {"killed": bool(by), "by": by, "unpredicted": un}


def recompute_recomputed_only(rec: dict) -> list:
    """kill_criterion.recomputed_only: the unpredicted obstructions on laws the record's recomputed predicted set holds."""
    rp = rec.get("recomputed") or {}
    inside = set().union(*[set(v) for v in (rp.get("predicted") or {}).values()]) if rp.get("predicted") else set()
    return [x for x in recompute_kill(rec)["unpredicted"] if x["law"] in inside]


def outcome_of(rec: dict) -> str:
    k = recompute_kill(rec)
    if k["killed"]:
        return "killed"
    if any(e["predicted"] and e["mutant"] == "error" for e in rec["laws"].values()):
        return "error"
    return "survived"


def survivor_class(rec: dict, equivalent: bool):
    """(class, gap_stage, rule_gap_kind) of instrument survivor_classes (the first rule that holds, in its listed
    order), from the record alone."""
    if rec["outcome"] == "killed":
        return None, None, None
    if equivalent:
        return "equivalent", None, None
    if rec["outcome"] == "error":
        return "error", None, None
    if not any(d["changed"] for d in rec["documents"].values()):
        return "extraction_gap", "frontend", None
    pred = {k: e for k, e in rec["laws"].items() if e["predicted"]}
    if not pred:
        return "rule_gap", None, "no_law"
    if any(law_how(e) == "replay_disagreement" for e in pred.values()):
        return "extraction_gap", "replay", None
    changed = {k: e for k, e in pred.items() if (e.get("own_input") or {}).get("changed") is True
               or e["baseline"] == "absent"}
    if not changed:
        return "extraction_gap", "model", None
    if all(e["baseline"] == "REFUTED" for e in changed.values()):
        return "masked", None, None
    if any(law_how(e) == "baseline_finding" for e in pred.values()):
        return "baseline_finding", None, None
    if any(law_how(e) == "proof_lost_unwitnessed" for e in pred.values()):
        return "proof_lost_unwitnessed", None, None
    return "rule_gap", None, "law_unmoved"


def plan_literal(rec: dict) -> bool:
    """reporting.plan_literal (F-A9): some predicted law moves to REFUTED with a checked counter-law and a hit that
    replays on the mutant (no two-sided test), or satisfies K2 (a) and (b) (no (c))."""
    for e in rec["laws"].values():
        if not e["predicted"]:
            continue
        b, m = e["baseline"], e["mutant"]
        rep = e.get("replay") or []
        if m == "REFUTED" and (b in ("PROVED", "UNKNOWN") or (b == "absent" and e.get("site_in_mutated_function"))) \
                and (e.get("counter_law") or {}).get("marker") == "ALL PROOFS CHECK" \
                and any(r["mutant"] is True for r in rep):
            return True
        if law_how(e) in ("K2", "proof_lost_unwitnessed"):
            return True
    return False


def language(m: dict) -> str:
    return "solidity" if m["file"].endswith(".sol") else "go"


def copy_repo() -> Path:
    """A scratch clone of the committed repository at HEAD (its parent directory is removed by the caller)."""
    d = Path(tempfile.mkdtemp(prefix="i62-repo-"))
    p = subprocess.run(["git", "clone", "-q", "--no-hardlinks", str(ROOT), str(d / "repo")], capture_output=True,
                       text=True)
    if p.returncode != 0:
        shutil.rmtree(d, ignore_errors=True)
        raise AssertionError(f"git clone failed: {p.stderr[-500:]}")
    return d / "repo"


def channel_runs(rec: dict) -> list:
    ref = rec.get("refinement")
    if not isinstance(ref, dict) or not isinstance(ref.get("channels"), list):
        raise AssertionError(f"{rec.get('id')}: no refinement channel runs recorded")
    return ref["channels"]


def defect_flag(rec: dict):
    runs = channel_runs(rec)
    if rec["replay_disagreements"] or any(r["new_disagreements"] for r in runs):
        return True
    if any(r["error"] for r in runs):
        return None
    return False


def rate(num: int, den: int) -> dict:
    return {"num": num, "den": den, "value": num / den if den else None}


def m0_family(law: str) -> str:
    for pre, fam in (("L_par_hdr_", "PAR-codec"), ("L_rt_go_", "PAR-round-trip"), ("L_dom_hdr", "PAR-domain")):
        if law.startswith(pre):
            return fam
    raise AssertionError(f"{law}: no M0 family")


def baseline_families() -> dict:
    """The family of every pinned baseline law (instrument reporting.by_family)."""
    out = {p.stem: m0_family(p.stem) for p in sorted((ROOT / "laws" / "M0").glob("L_*.json"))}
    for law in instrument()["baseline"]["M1x"]:
        out[law] = "M1x:" + pin_json(f"laws/M1/{law}.json")["rule"]
    for e in pin_json("laws/M2/DERIVATION.json")["laws"]:
        out[e["law_id"]] = f"M2:{e['rule']}/{e['subform']}"
    return out


_FN_LINES = {}


def mutated_function_lines() -> dict:
    """{mutant id: (unit, first line, last line)} of the Solidity function or modifier each Solidity mutant mutates,
    from the pinned checkout's compact AST (the I19 walker's index; computation item 2)."""
    if not _FN_LINES:
        inst = instrument()
        _, compiled, index, _, _, coll = compile_rollup(inst)
        fns = list(coll.reached.values())
        for u in {m["file"] for m in inst["mutants"] if m["file"].endswith(".sol")}:
            for n in compiled.asts[u]["nodes"]:
                if n.get("nodeType") == "ContractDefinition":
                    fns += [f for f in n["nodes"] if f.get("nodeType") in ("FunctionDefinition", "ModifierDefinition")
                            and f.get("body")]
        spans = defaultdict(list)
        for f in fns:
            unit, lines = index.span(f["src"]).rsplit(":", 1)
            lo, _, hi = lines.partition("-")
            spans[(unit, index.fn_name(f))].append((int(lo), int(hi or lo)))
        for m in inst["mutants"]:
            if m["file"].endswith(".sol"):
                hit = sorted({s for s in spans[(m["file"], m["function"])] if s[0] <= m["line"] <= s[1]})
                if len(hit) != 1:
                    raise AssertionError(f"{m['id']}: {len(hit)} enclosing functions named {m['function']}")
                _FN_LINES[m["id"]] = (m["file"], *hit[0])
    return _FN_LINES


def basis_inside(span, where) -> bool:
    """Whether a basis span "<unit>:<lo>[-<hi>]" lies inside (unit, first, last)."""
    if where is None or not isinstance(span, str) or ":" not in span:
        return False
    unit, lines = span.rsplit(":", 1)
    mt = re.fullmatch(r"([0-9]+)(?:-([0-9]+))?", lines)
    if mt is None or unit != where[0]:
        return False
    lo, hi = int(mt.group(1)), int(mt.group(2) or mt.group(1))
    return where[1] <= lo and hi <= where[2]


# ---------------------------------------------------------------------------------------------- the Solidity scope
def compile_rollup(inst: dict):
    """The pinned Rollup compiled by the I19 frontend's own compile step, and its walk (computation item 2)."""
    sys.path.insert(0, str(ROOT))
    from holon.frontends.solidity import compile as comp
    from holon.frontends.solidity import transitions as T
    side = load_json(ROOT / "spec" / "M2" / "lib" / "extract_rollup.json")
    compiled = comp.compile_sources(config(), side, morph(), storage_layout=True)
    index, contract, acts, coll = T.walk_contract(compiled, side)
    return T, compiled, index, contract, acts, coll


def refs_of(node) -> set:
    out, stack = set(), [node]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            if x.get("nodeType") in ("Identifier", "MemberAccess", "IdentifierPath") \
                    and isinstance(x.get("referencedDeclaration"), int):
                out.add(x["referencedDeclaration"])
            if x.get("nodeType") == "ModifierInvocation":
                r = (x.get("modifierName") or {}).get("referencedDeclaration")
                if isinstance(r, int):
                    out.add(r)
            stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
        elif isinstance(x, list):
            stack.extend(x)
    return out


GO_SITES_PROGRAM = r'''
package main

import (
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

type Site struct {
	Op     string `json:"op"`
	File   string `json:"file"`
	Offset int    `json:"offset"`
	Length int    `json:"length"`
}

var dec = regexp.MustCompile(`^[0-9]+$`)

func lit(e ast.Expr) (*ast.BasicLit, bool) {
	b, ok := e.(*ast.BasicLit)
	return b, ok && b.Kind == token.INT && dec.MatchString(b.Value)
}

func errValue(e ast.Expr) bool {
	switch x := e.(type) {
	case *ast.Ident:
		return strings.HasPrefix(x.Name, "Err")
	case *ast.SelectorExpr:
		return strings.HasPrefix(x.Sel.Name, "Err")
	case *ast.CallExpr:
		if s, ok := x.Fun.(*ast.SelectorExpr); ok {
			if p, ok := s.X.(*ast.Ident); ok {
				return (p.Name == "errors" && s.Sel.Name == "New") || (p.Name == "fmt" && s.Sel.Name == "Errorf")
			}
		}
	}
	return false
}

func main() {
	root := os.Args[1]
	enc := json.NewEncoder(os.Stdout)
	for _, rel := range os.Args[2:] {
		src, err := os.ReadFile(filepath.Join(root, rel))
		if err != nil {
			panic(err)
		}
		fset := token.NewFileSet()
		f, err := parser.ParseFile(fset, rel, src, 0)
		if err != nil {
			panic(err)
		}
		consts := map[string]bool{}
		for _, d := range f.Decls {
			if g, ok := d.(*ast.GenDecl); ok && g.Tok == token.CONST {
				for _, s := range g.Specs {
					for _, n := range s.(*ast.ValueSpec).Names {
						consts[n.Name] = true
					}
				}
			}
		}
		emit := func(op string, a, b token.Pos) {
			enc.Encode(Site{op, rel, fset.Position(a).Offset, fset.Position(b).Offset - fset.Position(a).Offset})
		}
		for _, d := range f.Decls {
			fd, ok := d.(*ast.FuncDecl)
			if !ok || fd.Body == nil {
				continue
			}
			dst := map[ast.Expr]bool{}
			ast.Inspect(fd.Body, func(n ast.Node) bool {
				switch x := n.(type) {
				case *ast.CallExpr:
					if s, ok := x.Fun.(*ast.SelectorExpr); ok && strings.HasPrefix(s.Sel.Name, "Put") && len(x.Args) >= 1 {
						if s2, ok := s.X.(*ast.SelectorExpr); ok && s2.Sel.Name == "BigEndian" {
							dst[x.Args[0]] = true
							if p, ok := s2.X.(*ast.Ident); ok && p.Name == "binary" && s.Sel.Name == "PutUint64" && len(x.Args) == 2 {
								if sl, ok := x.Args[0].(*ast.SliceExpr); ok && sl.Low != nil && sl.High == nil && sl.Max == nil {
									if b, ok := lit(sl.Low); ok {
										emit("putuint64_offset", b.Pos(), b.End())
									}
								}
							}
						}
					}
					if id, ok := x.Fun.(*ast.Ident); ok && id.Name == "copy" && len(x.Args) == 2 {
						dst[x.Args[0]] = true
						if sl, ok := x.Args[0].(*ast.SliceExpr); ok && sl.Low != nil && sl.High == nil && sl.Max == nil {
							if b, ok := lit(sl.Low); ok {
								emit("copy_offset", b.Pos(), b.End())
							}
						}
					}
				case *ast.IfStmt:
					be, ok := x.Cond.(*ast.BinaryExpr)
					if x.Init != nil || x.Else != nil || !ok {
						return true
					}
					switch be.Op {
					case token.EQL, token.NEQ, token.LSS, token.LEQ, token.GTR, token.GEQ:
					default:
						return true
					}
					isLen := func(e ast.Expr) bool {
						c, ok := e.(*ast.CallExpr)
						if !ok || len(c.Args) != 1 {
							return false
						}
						id, ok := c.Fun.(*ast.Ident)
						return ok && id.Name == "len"
					}
					isConst := func(e ast.Expr) bool {
						if _, ok := lit(e); ok {
							return true
						}
						id, ok := e.(*ast.Ident)
						return ok && consts[id.Name]
					}
					if (isLen(be.X) && isConst(be.Y)) || (isLen(be.Y) && isConst(be.X)) {
						if len(x.Body.List) == 1 {
							if r, ok := x.Body.List[0].(*ast.ReturnStmt); ok && len(r.Results) > 0 && errValue(r.Results[len(r.Results)-1]) {
								emit("drop_len_check", x.Pos(), x.End())
							}
						}
					}
				}
				return true
			})
			ast.Inspect(fd.Body, func(n ast.Node) bool {
				if sl, ok := n.(*ast.SliceExpr); ok && !sl.Slice3 && sl.Low != nil && sl.High != nil && !dst[sl] {
					lo, ok1 := lit(sl.Low)
					hi, ok2 := lit(sl.High)
					if ok1 && ok2 {
						emit("go_slice_offset", lo.Pos(), hi.End())
					}
				}
				return true
			})
		}
	}
}
'''


def go_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("GOWORK", "GOFLAGS", "GOTOOLCHAIN")}
    env.update(GOWORK="off", GOFLAGS="-mod=mod", GOTOOLCHAIN="local", GOPROXY="off")
    return env


def go_sites(files: list) -> set:
    """Go sites of the instrument's patterns, found with go/ast on the pinned checkout (computation item 4)."""
    d = Path(tempfile.mkdtemp(prefix="i62-go-sites-"))
    try:
        (d / "go.mod").write_text("module i61sites\n\ngo 1.24\n")
        (d / "main.go").write_text(GO_SITES_PROGRAM)
        p = subprocess.run(["go", "run", ".", str(morph()), *files], cwd=d, env=go_env(), capture_output=True,
                           text=True, timeout=900)
        if p.returncode != 0:
            raise AssertionError(f"go run failed: {p.stderr[-1500:]}")
        return {(s["op"], s["file"], s["offset"], s["length"]) for s in map(json.loads, p.stdout.splitlines())}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def solidity_sites(compiled, index, scope: dict) -> set:
    """Solidity sites of the instrument's patterns on the compact AST (computation item 4)."""
    cursor = {nid for nid, n in index.nodes.items() if n.get("nodeType") == "VariableDeclaration"
              and n.get("stateVariable") and n.get("name") in {c for p in instrument()["cursor_pairs"] for c in p}}
    out = set()

    def unit(fid):
        return compiled.file_ids[fid]

    def src(s):
        a, b, f = (int(x) for x in s.split(":"))
        return a, b, unit(f)

    def text(s):
        a, b, u = src(s)
        return compiled.units[u][a:a + b].decode()

    for fn in scope.values():
        stack = [(fn["body"], None, None)]
        while stack:
            x, par, key = stack.pop()
            if isinstance(x, list):
                stack.extend((v, par, key) for v in x)
                continue
            if not isinstance(x, dict):
                continue
            nt = x.get("nodeType")
            if nt == "InlineAssembly":
                ys = [x["AST"]]
                while ys:
                    y = ys.pop()
                    if isinstance(y, list):
                        ys.extend(y)
                        continue
                    if not isinstance(y, dict):
                        continue
                    if y.get("nodeType") == "YulFunctionCall":
                        name, args = y["functionName"]["name"], y.get("arguments") or []
                        if name in ("mstore", "mstore8", "mload") and args and args[0].get("nodeType") == "YulFunctionCall" \
                                and args[0]["functionName"]["name"] == "add" and len(args[0]["arguments"]) == 2:
                            k = args[0]["arguments"][1]
                            if k.get("nodeType") == "YulLiteral" and re.fullmatch(r"[0-9]+", text(k["src"])):
                                a, b, u = src(k["src"])
                                out.add(("mload_offset" if name == "mload" else "mstore_offset", u, a, b))
                        if name in ("shl", "shr") and args and args[0].get("nodeType") == "YulLiteral" \
                                and re.fullmatch(r"[0-9]+", text(args[0]["src"])):
                            a, b, u = src(args[0]["src"])
                            out.add((name + "_width", u, a, b))
                    ys.extend(v for v in y.values() if isinstance(v, (dict, list)))
                continue
            if nt == "ExpressionStatement" and x["expression"].get("nodeType") == "UnaryOperation" \
                    and x["expression"].get("operator") == "delete":
                a, b, u = src(x["src"])
                data = compiled.units[u]
                j = a + b
                while data[j:j + 1] in (b" ", b"\t"):
                    j += 1
                if data[j:j + 1] != b";":
                    raise AssertionError(f"{u}:{a}: a delete statement without its semicolon")
                out.add(("drop_delete", u, a, j + 1 - a))
            if nt == "BinaryOperation" and x.get("operator") in (">=", ">", "<=", "<"):
                la, lb, u = src(x["leftExpression"]["src"])
                ra, _, _ = src(x["rightExpression"]["src"])
                between = compiled.units[u][la + lb:ra].decode()
                op = "cmp_boundary" if x["operator"] in (">=", ">") else "cmp_boundary_mirror"
                out.add((op, u, la + lb + between.index(x["operator"]), len(x["operator"])))
            if nt == "Identifier" and x.get("referencedDeclaration") in cursor:
                lhs = par is not None and par.get("nodeType") == "Assignment" and key == "leftHandSide"
                unary = par is not None and par.get("nodeType") == "UnaryOperation" \
                    and par.get("operator") in ("++", "--", "delete")
                if not (lhs or unary):
                    a, b, u = src(x["src"])
                    out.add(("swap_cursor", u, a, b))
            for k, v in x.items():
                if isinstance(v, (dict, list)):
                    stack.append((v, x, k))
    return out


# ============================================================================================ the frozen instrument
class TestInstrument(unittest.TestCase):
    """Integrity of the frozen instrument and diff sheet (green from the prereg on: they read only frozen inputs, the
    pinned checkout and sol_deps)."""

    def test_the_instrument_is_the_frozen_one(self):
        self.assertEqual(sha256(INSTRUMENT.read_bytes()), INSTRUMENT_SHA256)
        inst = instrument()
        self.assertEqual((inst["iteration"], inst["milestone"]), ("I62", "M2"))
        self.assertEqual(inst["mutants_sha256"], sha256(canon(inst["mutants"]).encode()))
        self.assertEqual(inst["diff_sheet"]["sha256"], sha256(SHEET.read_bytes()))
        rep = inst["replaces"]
        self.assertEqual(rep["key"], "I61")
        self.assertEqual(sha256(I61_INSTRUMENT.read_bytes()), rep["instrument"]["sha256"])
        self.assertEqual(rep["instrument"]["path"], "spec/M2/lib/mutation_catalog_i61.json")
        self.assertEqual(rep["first_run"]["pipeline_commit"], I61_PIPELINE)
        # every defect of I61's run is named with its fix, D1-D8
        self.assertEqual(sorted(k.split(" ")[0] for k in rep["defects"]), [f"D{i}" for i in range(1, 9)])
        for k, v in rep["defects"].items():
            self.assertIn("Fix", v, k)

    def test_the_catalog_and_sheet_are_i61s(self):
        """I62 keeps I61's instrument but for the fields the defects touch (CHANGED_FIELDS): the 242 mutants, the
        controls, the scope, the predicted sets, the structural classes and the diff sheet are I61's byte for byte."""
        inst, old = instrument(), load_json(I61_INSTRUMENT)
        self.assertEqual(list(inst), list(old))
        self.assertEqual(sorted(k for k in inst if inst[k] != old[k]), CHANGED_FIELDS)
        self.assertEqual(inst["harness_gate"]["controls"], old["harness_gate"]["controls"])
        self.assertEqual(inst["harness_gate"]["checks"]["i16"], old["harness_gate"]["checks"]["i16"])
        self.assertEqual(inst["harness_gate"]["checks"]["null"], old["harness_gate"]["checks"]["null"])
        self.assertEqual(inst["diff_sheet"], old["diff_sheet"])
        for k in ("doc", "kill_criterion", "replay", "channels", "reporting", "projection", "pins", "preconditions",
                  "adjudication", "harness_gate"):
            for f, v in old[k].items() if isinstance(old[k], dict) else ():
                if f in ("doc", "semantics", "errors", "i20_step", "metric", "controls", "checks", "record",
                         "output", "why", "review", "adjudication", "gate", "baseline", "order", "forbidden",
                         "known_exposure", "file", "panel", "panel_record", "redacted_i60_review"):
                    continue
                self.assertEqual(inst[k].get(f), v, (k, f))
        # the changed rules extend I61's text: I61's sentence stays, I62's follows
        for k, f in (("kill_criterion", "errors"), ("replay", "semantics"), ("channels", "i20_step"),
                     ("reporting", "metric")):
            self.assertTrue(inst[k][f].startswith(old[k][f]), (k, f))
            self.assertIn("I62", inst[k][f][len(old[k][f]):], (k, f))
        self.assertTrue(inst["harness_gate"]["checks"]["controls"].startswith(old["harness_gate"]["checks"]["controls"]))
        self.assertEqual(inst["limitations"][:len(old["limitations"])], old["limitations"])
        self.assertEqual(SHEET, SPEC2 / "lib" / "mutation_diff_sheet_i61.md")

    def test_threshold_seed_strata_and_counts(self):
        inst = instrument()
        self.assertEqual((inst["threshold"]["kill_rate_non_equivalent"], inst["threshold"]["stratum"]), (0.8, "A"))
        t = predictions("I62")["thresholds"]
        self.assertEqual((t["kill_rate_non_equivalent"], t["stratum"], t["seed"]), (0.8, "A", inst["seed"]))
        self.assertEqual(inst["seed"], 20261061)
        got = {s: Counter(m["operator"] for m in inst["mutants"] if m["stratum"] == s) for s in "AB"}
        self.assertEqual(dict(got["A"]), {op: n for op, (n, _) in A_BY_OPERATOR.items()})
        self.assertEqual(dict(got["B"]), {"putuint64_offset": 8, "copy_offset": 8, "drop_len_check": 10,
                                          "go_slice_offset": 24})
        self.assertEqual([m["id"] for m in inst["mutants"]], ids("A", 1, 192) + ids("B", 1, 50))
        self.assertEqual({s: {k: v for k, v in inst["counts"][s].items() if k != "total"} for s in "AB"},
                         {s: dict(got[s]) for s in "AB"})
        self.assertEqual((inst["counts"]["A"]["total"], inst["counts"]["B"]["total"], inst["counts"]["total"]),
                         (192, 50, 242))
        self.assertEqual(len(inst["stillborn"]), 1)
        self.assertEqual(t["mutants"], {"A": 192, "B": 50})

    def test_the_threshold_consequence_is_the_arithmetic(self):
        """S-A10/F-A2: the stated consequence is the arithmetic of the catalog: the reachable count less the
        premise-limited mutants is the ceiling, and meets needs at least the stated number of equivalent verdicts."""
        inst = instrument()
        reach = Counter(m["structural"]["class"] for m in inst["mutants"] if m["stratum"] == "A")["reachable"]
        lim = inst["structural"]["premise_limited"]
        self.assertEqual(lim["ids"], PREMISE_LIMITED)
        ceiling = reach - len(lim["ids"])
        self.assertEqual(lim["ceiling"], ceiling)
        n = inst["counts"]["A"]["total"]
        need_e = next(e for e in range(n + 1) if 5 * ceiling >= 4 * (n - e))
        text = inst["threshold"]["consequence"]
        for x in (f"{reach} reachable", f"at most {ceiling}", f"e >= {need_e}", f"{len(TCE)} by tce"):
            self.assertIn(x, text)

    def test_the_planted_controls_are_outside_the_catalog(self):
        """harness_gate.controls: each control is a single-site edit of the pinned bytes, keeps the line count, is no
        catalog mutant, and its mutant_sha256 is the mutated file's."""
        inst = instrument()
        cs = inst["harness_gate"]["controls"]
        self.assertEqual([c["id"] for c in cs], ["C1", "C2", "C3", "C4"])
        catalog = {(m["file"], m["offset"], m["replacement"]) for m in inst["mutants"]}
        for c in cs:
            with self.subTest(control=c["id"]):
                b = source(inst, c["file"])
                self.assertEqual(b[c["offset"]:c["offset"] + c["length"]].decode(), c["original"])
                nb = apply(c, b)
                self.assertEqual(sha256(nb), c["mutant_sha256"])
                self.assertEqual(nb.count(b"\n"), b.count(b"\n"))
                self.assertNotIn((c["file"], c["offset"], c["replacement"]), catalog)
                self.assertEqual(c["expected"]["outcome"], "killed")
                self.assertIn(c["expected"]["how"], ("K1", "K2"))
                self.assertEqual("falsifier" in c["expected"], c["expected"]["how"] == "K2")
                self.assertTrue(set(c["expected"]["laws"]) <= {k for k, v in M0_BASELINE.items() if v == "PROVED"})
        # C3 and C4 sit inside the entry function's copied text, C1 and C2 in a codec library and the Go encoder
        entry = instrument()["roles"]["solidity"]["enc_sol"]["entry"]
        self.assertEqual([c["function"] == entry for c in cs], [False, False, True, True])

    def test_in_scope_files_are_the_pinned_bytes_the_extractions_read(self):
        inst = instrument()
        recorded = {}
        for doc in sorted((SPEC2 / "facts").glob("*.extracted.json")):
            for x in pin_json(f"spec/M2/facts/{doc.name}")["extraction"]["inputs"]:
                recorded[x.get("unit") or x.get("path")] = x["sha256"]
        for f, v in inst["in_scope"]["files"].items():
            with self.subTest(file=f):
                self.assertEqual(sha256(source(inst, f)), v["sha256"])
                self.assertEqual(recorded.get(f), v["sha256"])
        self.assertEqual(sorted(inst["in_scope"]["order"]), sorted(inst["in_scope"]["files"]))

    def test_each_mutant_is_its_operators_rewrite(self):
        inst = instrument()
        srcs = sources(inst)
        pair = {}
        for a, b in inst["cursor_pairs"]:
            pair[a], pair[b] = b, a
        order = inst["in_scope"]["order"]
        keys = []
        for m in inst["mutants"] + [dict(s, id=None) for s in inst["stillborn"]]:
            with self.subTest(mutant=m["id"] or "stillborn"):
                b = srcs[m["file"]]
                self.assertEqual(b[m["offset"]:m["offset"] + m["length"]].decode(), m["original"])
                nb = apply(m, b)
                self.assertEqual(nb.count(b"\n"), b.count(b"\n"))
                if m["id"]:
                    self.assertEqual(sha256(nb), m["mutant_sha256"])
                self.assertEqual(b.count(b"\n", 0, m["offset"]) + 1, m["line"])
                self.assertEqual(m["offset"] - (b.rfind(b"\n", 0, m["offset"]) + 1) + 1, m["col"])
                op, o, r, v = m["operator"], m["original"], m["replacement"], m["variant"]
                if op in ("mstore_offset", "mload_offset", "putuint64_offset", "copy_offset"):
                    self.assertEqual(int(r) - int(o), int(v))
                elif op in ("shl_width", "shr_width"):
                    self.assertEqual(int(r) - int(o), int(v))
                    self.assertTrue(0 < int(r) < 256)
                elif op == "go_slice_offset":
                    lo, hi = map(int, o.split(":"))
                    self.assertEqual(r, f"{lo + int(v)}:{hi + int(v)}")
                elif op == "cmp_boundary":
                    self.assertEqual(r, {">=": ">", ">": ">="}[o])
                elif op == "cmp_boundary_mirror":
                    self.assertEqual(r, {"<=": "<", "<": "<="}[o])
                elif op == "swap_cursor":
                    self.assertEqual(pair[o], r)
                elif op == "drop_delete":
                    self.assertTrue(o.startswith("delete ") and o.endswith(";") and r == "{}" + "\n" * o.count("\n"))
                else:
                    self.assertTrue(o.startswith("if len(") and o.endswith("}") and r == "{}" + "\n" * o.count("\n"))
                if m["id"]:
                    keys.append((m["stratum"], inst["operator_order"].index(op), order.index(m["file"]), m["offset"],
                                 inst["variant_order"].index(v)))
        self.assertEqual(keys, sorted(keys))

    def test_the_diff_sheet_is_the_rendering_of_the_catalog(self):
        """The sheet is render_sheet() of the catalog, and it is blind: no law id (laws/M0, laws/M1, laws/M2), no
        status, no structural or survivor class and no kill vocabulary appears anywhere in it."""
        inst = instrument()
        text = SHEET.read_text()
        self.assertEqual(render_sheet(inst, sources(inst)), text)
        laws = sorted({p.stem for d in ("M0", "M1", "M2") for p in (ROOT / "laws" / d).glob("L_*.json")})
        self.assertGreater(len(laws), 30)
        words = ["predicted", "structural", "forecast", "killed", "survive", "masked", "proof_lost", "rule_gap",
                 "extraction_gap", "projection_carried", "abstraction_carried", "PROVED", "REFUTED", "UNKNOWN"]
        self.assertEqual([w for w in laws + words if w in text], [])

    def test_the_pins_hold_at_the_pinned_commit(self):
        """S-A8: every committed artifact the computation read has its pinned sha256 at pins.holon_commit, an ancestor
        of HEAD."""
        inst = instrument()
        self.assertEqual(inst["pins"]["holon_commit"], PIN)
        self.assertTrue(is_ancestor(PIN, "HEAD"))
        for path, h in inst["pins"]["files"].items():
            with self.subTest(path=path):
                self.assertEqual(sha256(at_pin(path)), h)

    def test_the_tce_mutants_leave_rollup_bytecode_unchanged(self):
        """Computation item 6: of the 122 Solidity mutants exactly the six tce ones compile to Rollup's original
        deployed bytecode; every other one (A108 and A109, the neighbouring getSequencerSetVerifyHash mutants that
        Rollup calls, among them) changes it and compiles."""
        inst = instrument()
        self.assertEqual(inst["tce"]["mutants"], TCE)
        self.assertEqual(sorted(m["id"] for m in inst["mutants"] if m["tce"]), TCE)
        cfg = config()

        def bytecode(override=None):
            sources_ = {ROLLUP: {"content": source(inst, ROLLUP).decode()}}
            if override:
                sources_[override[0]] = {"content": override[1].decode()}
            inp = {"language": "Solidity", "sources": sources_,
                   "settings": {"optimizer": {"enabled": False}, "evmVersion": "cancun",
                                "metadata": {"bytecodeHash": "none", "appendCBOR": False},
                                "outputSelection": {ROLLUP: {"Rollup": ["evm.deployedBytecode.object"]}}}}
            p = subprocess.run([cfg["replay"]["solc"], "--standard-json", "--base-path", ".", "--include-path",
                                str(sol_deps())], input=json.dumps(inp), capture_output=True, text=True,
                               cwd=str(morph()), timeout=900)
            out = json.loads(p.stdout)
            errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
            self.assertEqual(errs, [])
            return out["contracts"][ROLLUP]["Rollup"]["evm"]["deployedBytecode"]["object"]

        base = bytecode()
        sol = [m for m in inst["mutants"] if m["file"].endswith(".sol")]
        self.assertEqual(len(sol), 122)
        self.assertTrue({"A108", "A109"} <= {m["id"] for m in sol})
        for m in sol:
            with self.subTest(mutant=m["id"]):
                same = bytecode((m["file"], apply(m, source(inst, m["file"])))) == base
                self.assertIs(same, m["id"] in TCE)


class TestScope(unittest.TestCase):
    """Construction (green from the prereg on): the scope, sites, edges, actions, predicted sets and structural classes
    are recomputed from the pinned checkout and the pinned artifacts by the instrument's own rules."""

    @classmethod
    def setUpClass(cls):
        cls.inst = instrument()
        cls.T, cls.compiled, cls.index, cls.contract, cls.acts, cls.coll = compile_rollup(cls.inst)
        cls.scope = dict(cls.coll.reached)
        for u in ("contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol",
                  "contracts/contracts/libraries/codec/BatchHeaderCodecV1.sol"):
            for n in cls.compiled.asts[u]["nodes"]:
                if n.get("nodeType") == "ContractDefinition":
                    for f in n["nodes"]:
                        if f.get("nodeType") in ("FunctionDefinition", "ModifierDefinition") and f.get("body"):
                            cls.scope.setdefault(f["id"], f)

    def test_the_solidity_scope_is_the_walkers_reached_set(self):
        """F-B1: stratum A's Solidity functions are the walker's reached set of the adopted document (the coverage
        scope) plus the codec libraries; coverage_document over the same walk is gen/M2/coverage.json's."""
        self.assertEqual(load_json(ROOT / "spec" / "M2" / "lib" / "derive_extracted.json")["documents"],
                         ["spec/M2/facts/morph_header.extracted.json", "spec/M2/facts/morph_rollup.extracted.json"])
        self.assertEqual(len(self.coll.reached), 92)
        self.assertEqual(len(self.scope), 94)
        names = {(self.index.span(f["src"]).rsplit(":", 1)[0], self.index.fn_name(f)) for f in self.scope.values()}
        listed = {(u, fn["function"]) for u, v in self.inst["in_scope"]["files"].items() if u.endswith(".sol")
                  for fn in v["functions"]}
        self.assertEqual(listed, names)
        side = load_json(ROOT / "spec" / "M2" / "lib" / "extract_rollup.json")
        cov = self.T.coverage_document(self.compiled, side)
        doc = pin_json("gen/M2/coverage.json")["documents"][0]
        self.assertEqual((cov["statements"], cov["extracted"], len(cov["debt"]), len(cov["unaccounted"])),
                         (doc["statements"], doc["extracted"], len(doc["debt"]), len(doc["unaccounted"])))

    def test_actions_are_the_per_action_closures(self):
        nodes = self.index.nodes
        fns = list(self.T.actions_of(self.index, self.contract))
        self.assertEqual(len(fns), 33)
        reach = defaultdict(set)
        union = set()
        for fn, a in zip(fns, self.acts):
            seen, todo = {fn["id"]}, [fn["id"]]
            while todo:
                x = todo.pop()
                for y in refs_of(nodes[x]):
                    if y in nodes and nodes[y].get("nodeType") in ("FunctionDefinition", "ModifierDefinition") \
                            and y not in seen:
                        seen.add(y)
                        todo.append(y)
            for i in seen & set(self.scope):
                reach[self.index.fn_name(nodes[i])].add(a["name"])
                union.add(i)
        self.assertEqual(union, set(self.coll.reached))
        for m in self.inst["mutants"]:
            if m["file"].endswith(".sol"):
                with self.subTest(mutant=m["id"]):
                    self.assertEqual(m["actions"], sorted(reach.get(m["function"], ())))
            else:
                self.assertEqual(m["actions"], [])

    def test_the_go_strata_follow_the_diagram_and_the_codecs(self):
        """F-A9: stratum A's Go file is the codec file the M2 diagram adopts; stratum B every other file holding an
        I18 codec of a committed Go document."""
        diagram = pin_json("gen/M2/diagram/morph_header.json")
        facts = pin_json(diagram["facts"])
        codec_fns = {e["component"] for e in diagram["edges"] if e["kind"] == "CODEC"} | set(diagram["predicates"])
        go_a = {s["file"] for fn in codec_fns for s in facts["functions"][fn]["source"]
                if facts["functions"][fn]["lang"].startswith("go")}
        self.assertEqual(go_a, {"common/batch/batch_header.go"})
        files = set()
        for p in sorted((SPEC2 / "facts").glob("*.go.extracted.json")):
            d = pin_json(f"spec/M2/facts/{p.name}")
            for k in ("encoders", "decoders", "predicates"):
                for c in d["go"]["codecs"][k]:
                    files.add(d["go"]["functions"][c["function"]]["span"].rsplit(":", 1)[0])
        stratum = {f: v["stratum"] for f, v in self.inst["in_scope"]["files"].items() if f.endswith(".go")}
        self.assertEqual({f for f, s in stratum.items() if s == "A"}, go_a)
        self.assertEqual({f for f, s in stratum.items() if s == "B"}, files - go_a)
        self.assertEqual(len(files - go_a), 11)

    def test_the_sites_are_recomputed_from_the_pinned_checkout(self):
        """Computation item 4: the operator patterns, matched again (solc's AST; go/ast), give exactly the catalog's
        sites (each mutant's (operator, file, offset, length), the stillborn included)."""
        want = {(m["operator"], m["file"], m["offset"], m["length"]) for m in self.inst["mutants"] + self.inst["stillborn"]}
        sol = solidity_sites(self.compiled, self.index, self.scope)
        gofiles = [f for f in self.inst["in_scope"]["order"] if f.endswith(".go")]
        got = sol | go_sites(gofiles)
        self.assertEqual(sorted(got - want), [])
        self.assertEqual(sorted(want - got), [])

    def test_edges_and_predicted_sets_follow_the_rules(self):
        """F-A2: one rule for every operator, from the pinned artifacts (instrument predicted, roles)."""
        hdr = pin_json("spec/M2/facts/morph_header.extracted.json")
        walk = {r: set(hdr["functions"][e]["walk"]["functions"]) for r, e in EDGE_ROLE.items()}
        gob = pin_json("spec/M2/facts/morph_batch.go.extracted.json")
        calls = defaultdict(set)
        for e in gob["go"]["calls"]["edges"]:
            if e["callee_kind"] == "analyzed":
                calls[e["caller"]].add(e["callee"])
        gofns = {}
        for r, named in self.inst["roles"]["go"].items():
            seen, todo = set(named["named"]), list(named["named"])
            while todo:
                for y in calls[todo.pop()]:
                    if y not in seen:
                        seen.add(y)
                        todo.append(y)
            gofns[r] = seen
            self.assertEqual(sorted(seen), named["functions"])
        roles = {p.stem: statement_calls(json.loads(at_pin(f"laws/M0/{p.name}")))
                 for p in sorted((ROOT / "laws" / "M0").glob("L_*.json"))}
        cones = {}
        for p in sorted((ROOT / "results" / "M2" / "extracted_m1").glob("L_*.json")):
            r = pin_json(f"results/M2/extracted_m1/{p.name}")
            cones[r["law_id"]] = {c[len("step_"):] for c in r.get("cone") or [] if c.startswith("step_") and c != "step_"}
        self.assertEqual(len(cones), 15)
        entry = {e["law_id"]: set(e["entry_points"]) for e in pin_json("laws/M2/DERIVATION.json")["laws"]}
        for m in self.inst["mutants"]:
            with self.subTest(mutant=m["id"]):
                if m["file"].endswith(".sol"):
                    edges = sorted(r for r, fs in walk.items() if m["function"] in fs)
                elif m["stratum"] == "A":
                    edges = sorted(r for r, fs in gofns.items() if m["function"] in fs)
                else:
                    edges = []
                self.assertEqual(m["edges"], edges)
                acts = set(m["actions"])
                self.assertEqual(m["predicted"], {
                    "M0": sorted(l for l, rs in roles.items() if rs & set(edges)),
                    "M1x": sorted(l for l, c in cones.items() if c & acts),
                    "M2": sorted(l for l, e in entry.items() if e & acts)})

    def test_structural_classes_follow_the_rule(self):
        """F-A1/S-A1: the structural class of every mutant follows instrument structural from the pinned artifacts."""
        hdr = pin_json("spec/M2/facts/morph_header.extracted.json")
        origin, entry, revert = {}, {}, {}
        for r, e in EDGE_ROLE.items():
            f = hdr["functions"][e]
            origin[r] = {op["origin"]["fn"] for p in f["paths"] if p["outcome"] == "ok" for op in p.get("ops", [])}
            entry[r] = f["entry"]["fn"]
            revert[r] = {p["src"] for p in f["paths"] if p["outcome"] == "revert" and p.get("src")}
        roles = self.inst["roles"]["m0_law_roles"]
        base = {law: pin_json(f"results/M0/{law}.json")["status"] for law in roles}
        counts = Counter()
        for m in self.inst["mutants"]:
            with self.subTest(mutant=m["id"]):
                pr = set()
                for r in m["edges"]:
                    if r in EDGE_ROLE:
                        if (m["operator"] in LAYOUT_OPS and m["function"] in origin[r]) or (
                                m["operator"] in CMP_OPS and (m["function"] == entry[r]
                                                              or f"{m['file']}:{m['line']}" in revert[r])):
                            pr.add(r)
                    else:
                        pr.add(r)
                reads = sorted(l for l in m["predicted"]["M0"] if set(roles[l]) & pr)
                live = [l for l in reads if base[l] in ("PROVED", "UNKNOWN")]
                p0, p1, p2 = (m["predicted"][k] for k in ("M0", "M1x", "M2"))
                cls = ("reachable" if live else "masked" if reads else "projection_carried" if p0
                       else "abstraction_carried" if (p1 or p2) else "no_predicted_law")
                self.assertEqual(m["structural"], {
                    "class": cls, "M0": "reads" if live else "masked" if reads else "carried" if p0 else "none",
                    "M0_reading_laws": reads, "M1x": "carried" if p1 else "none", "M2": "carried" if p2 else "none"})
                counts[(m["stratum"], cls)] += 1
        self.assertEqual(dict(counts), {("A", "reachable"): 103, ("A", "masked"): 2, ("A", "projection_carried"): 14,
                                        ("A", "abstraction_carried"): 51, ("A", "no_predicted_law"): 22,
                                        ("B", "no_predicted_law"): 50})

    def test_duplicate_candidates_follow_the_widened_rule(self):
        """F-A4: the candidate groups are the mutants of one line that come from two or more sites (any operators) or
        from one statement-level operator."""
        stmt = {"drop_delete", "swap_cursor", "cmp_boundary", "cmp_boundary_mirror", "drop_len_check"}
        by_line = defaultdict(list)
        for m in self.inst["mutants"]:
            by_line[(m["file"], m["line"])].append(m)
        want = sorted(sorted(m["id"] for m in ms) for ms in by_line.values()
                      if len({m["offset"] for m in ms}) >= 2 or len([m for m in ms if m["operator"] in stmt]) >= 2)
        self.assertEqual(self.inst["duplicates"]["candidates"], want)
        for g in ([["A001", "A002", "A027", "A028"], ["A003", "A004", "A029", "A030"],
                   ["A005", "A006", "A031", "A032"], ["A021", "A022", "A033", "A034"], ["A050", "A051", "A085"]]):
            self.assertIn(g, want)

    def test_premise_limited_mutants_are_reachable_and_read_only_by_masked_laws(self):
        """F-A1 (structural.premise_limited): each keeps the mechanical class 'reachable'; A148 and A162 are the +1
        sequencer-set copy of the two Go encoders, whose only premise-free reader, L_par_hdr_ssvh, is REFUTED at
        baseline; A165-A168 drop a length check, which only L_dom_hdr (REFUTED at baseline) sees beyond enc_sol's
        exact-length outputs."""
        ms = by_id(self.inst)
        for i in PREMISE_LIMITED:
            self.assertEqual(ms[i]["structural"]["class"], "reachable", i)
        for i in ("A148", "A162"):
            self.assertEqual((ms[i]["operator"], ms[i]["variant"], ms[i]["file"]),
                             ("copy_offset", "+1", "common/batch/batch_header.go"))
            self.assertIn("SequencerSetVerifyHash", source(self.inst, ms[i]["file"]).decode().splitlines()[ms[i]["line"] - 1])
        for i in ("A165", "A166", "A167", "A168"):
            self.assertEqual(ms[i]["operator"], "drop_len_check")
        self.assertEqual(self.inst["baseline"]["M0"]["L_par_hdr_ssvh"], "REFUTED")
        self.assertEqual(self.inst["baseline"]["M0"]["L_dom_hdr"], "REFUTED")


# ============================================================================================ construction (the build)
class TestOperators(unittest.TestCase):
    def test_operators_enumerate_exactly_the_catalog(self):
        """I62-R2: holon.mutate.operators finds exactly the 242 mutants, keys, values and order (stillborn excluded)."""
        ops = holon_module("holon.mutate.operators")
        inst = instrument()
        self.assertEqual(ops.catalog(inst, morph(), sol_deps()), inst["mutants"])

    def test_apply_checks_the_original_text(self):
        ops = holon_module("holon.mutate.operators")
        inst = instrument()
        for m in (inst["mutants"][0], by_id(inst)["A165"], by_id(inst)["B001"], *inst["harness_gate"]["controls"]):
            data = source(inst, m["file"])
            self.assertEqual(ops.apply(m, data), apply(m, data))
            with self.assertRaises(ValueError):
                ops.apply(dict(m, original="#" * m["length"]), data)

    def test_the_sheet_cli_reproduces_the_frozen_sheet(self):
        p = run_holon(["mutate", "sheet", "--check"], timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_mutate_code_holds_no_target_vocabulary(self):
        """holon/mutate names nothing of the target: no in-scope file, function, cursor, role function or Go field."""
        import io
        import tokenize
        inst = instrument()
        words = set()
        for f, v in inst["in_scope"]["files"].items():
            words.add(Path(f).name)
            for fn in v.get("functions", []):
                words.add(re.split(r"[.)]", fn["function"])[-1])
            for fn in v.get("site_functions", []) + v.get("codec_functions", []):
                words.add(fn.split(".")[-1])
        words |= {c for p in inst["cursor_pairs"] for c in p}
        for r in inst["roles"]["go"].values():
            words |= {n.split(".")[-1] for n in r["functions"]}
            words |= {t.split(".")[-1] for n in r["functions"] for t in re.findall(r"\(\*?([^)]*)\)", n)}
        words -= {"Bytes", "Hash", "Version", "validate", "initialize", "owner", "paused", "receive"}
        files = sorted((ROOT / "holon" / "mutate").glob("*.py"))
        self.assertTrue(files, "holon/mutate/ has no module")
        for f in files:
            toks = []
            for t in tokenize.generate_tokens(io.StringIO(f.read_text()).readline):
                if t.type == tokenize.NAME:
                    toks.append(t.string)
                elif t.type == tokenize.STRING and not t.string.startswith(('"""', "'''", 'r"""')):
                    toks += re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", t.string)
            hits = sorted({w for w in words if any(w == x or x.endswith("." + w) or x.startswith(w + ".") for x in toks)})
            with self.subTest(module=f.name):
                self.assertEqual(hits, [])

    def test_run_refuses_without_the_preconditions(self):
        """instrument preconditions.refusal, mechanically: a missing, unparsable, foreign or incomplete review or
        adjudication, a review that is not signed off, a gate.json that is missing, foreign, not passed or at another
        pipeline commit, a baseline record that is missing or does not reproduce, or an open high-severity I21 finding
        at the run's pipeline commit make run --dry-run exit 2 naming the file and write nothing; a complete set
        (synthetic, in a scratch clone: the control that the refusal is not unconditional) exits 0. --baseline-only
        needs none of them."""
        holon_module("holon.mutate.run")
        inst = instrument()
        lens = {"sign_off": True, "blocking": [], "advisory": [], "checked": "x", "forbidden_files_touched": []}
        ipath = str(INSTRUMENT.relative_to(ROOT))
        review = {"what": "x", "who": "x", "delegation": "x", "instrument": {"path": ipath, "sha256": INSTRUMENT_SHA256},
                  "verdict": "signed off", "reviews": {"fairness": lens, "soundness": lens}}
        adj = {"adjudication_version": "holon-equivalent-mutants/0.2",
               "instrument": {"path": ipath, "sha256": INSTRUMENT_SHA256},
               "mutants_sha256": inst["mutants_sha256"], "diff_sheet_sha256": inst["diff_sheet"]["sha256"],
               "review": {"path": "docs/iterations/I62_catalog_review.json", "sha256": None},
               "adjudicator": "delegated_panel", "delegation": {"decision": "x", "panel": "x", "procedure": "x",
                                                                "blindness_audit": "x"},
               "verdicts": {m["id"]: {"equivalent": bool(m["tce"]), "reason": "tce" if m["tce"] else "",
                                      "duplicate_of": None, "panel": {"judges": [bool(m["tce"])] * 2,
                                                                      "refuter_confirmed": True if m["tce"] else None}}
                            for m in inst["mutants"]}}
        rtext = json.dumps(review)
        adj["review"]["sha256"] = sha256(rtext.encode())
        bad_review = json.loads(rtext)
        bad_review["reviews"]["soundness"] = dict(lens, sign_off=False, blocking=["x"])
        incomplete = json.loads(json.dumps(adj))
        del incomplete["verdicts"]["B050"]
        repo = copy_repo()
        try:
            def head():
                return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                                      check=True).stdout.strip()

            def gate_for(commit, passed=True):
                ok = {"passed": True, "detail": "x"}
                checks = {k: ok for k in ("i16", "model", "null", "controls")}
                if not passed:
                    checks = dict(checks, controls={"passed": False, "detail": "x"})
                return {"instrument": {"path": ipath, "sha256": INSTRUMENT_SHA256}, "pipeline_commit": commit,
                        "attempts": [{"pipeline_commit": commit, "checks": checks, "passed": passed, "fix": None}],
                        "passed": passed}

            def baseline_for(commit, flip=None):
                docs = {}
                for p in sorted((repo / "spec" / "M2" / "facts").glob("*.extracted.json")):
                    docs[f"spec/M2/facts/{p.name}"] = {"sha256": sha256(p.read_bytes()),
                                                       "normalized_sha256": normalized_sha256(load_json(p)),
                                                       "changed": False}
                laws = {}
                for set_ in ("M0", "M1x", "M2"):
                    for law, st in inst["baseline"][set_].items():
                        laws[law] = {"set": set_, "baseline": st, "mutant": st, "decided": "run"}
                if flip:
                    laws[flip]["mutant"] = "UNKNOWN" if laws[flip]["mutant"] != "UNKNOWN" else "PROVED"
                proj = load_json(repo / PROJECTED.relative_to(ROOT))
                return {"id": "baseline", "stratum": None, "operator": None, "structural": None,
                        "pipeline_commit": commit, "documents": docs, "extraction": {"status": "ok", "errors": {}},
                        "projection": {"normalized_sha256": normalized_sha256(proj), "changed": None, "error": None},
                        "laws": laws}

            h0 = head()
            gtext = json.dumps(gate_for(h0))
            btext = json.dumps(baseline_for(h0))
            variants = [
                ("no review", None, json.dumps(adj), gtext, btext, 2),
                ("no adjudication", rtext, None, gtext, btext, 2),
                ("unparsable", rtext, "{", gtext, btext, 2),
                ("incomplete", rtext, json.dumps(incomplete), gtext, btext, 2),
                ("review not signed off", json.dumps(bad_review), json.dumps(adj), gtext, btext, 2),
                ("other catalog", rtext, json.dumps(dict(adj, mutants_sha256="0" * 64)), gtext, btext, 2),
                ("other sheet", rtext, json.dumps(dict(adj, diff_sheet_sha256="0" * 64)), gtext, btext, 2),
                ("no gate", rtext, json.dumps(adj), None, btext, 2),
                ("gate failed", rtext, json.dumps(adj), json.dumps(gate_for(h0, passed=False)), btext, 2),
                ("gate at another commit", rtext, json.dumps(adj), json.dumps(gate_for("0" * 40)), btext, 2),
                ("foreign gate", rtext, json.dumps(adj),
                 json.dumps(dict(gate_for(h0), instrument={"path": ipath, "sha256": "0" * 64})), btext, 2),
                ("no baseline", rtext, json.dumps(adj), gtext, None, 2),
                ("baseline does not reproduce", rtext, json.dumps(adj), gtext,
                 json.dumps(baseline_for(h0, flip="L_par_hdr_v0")), 2),
                ("complete", rtext, json.dumps(adj), gtext, btext, 0)]
            rp, ap, gp = (repo / REVIEW.relative_to(ROOT), repo / ADJ.relative_to(ROOT), repo / GATE.relative_to(ROOT))
            bp = repo / (RESULTS / "baseline.json").relative_to(ROOT)
            names = ("I62_catalog_review.json", "equivalent_mutants_i62.json", "gate.json", "baseline.json",
                     "M2_findings.jsonl")

            def attempt(name, r, a, g, b, code):
                with self.subTest(case=name):
                    for p, v in ((rp, r), (ap, a), (gp, g), (bp, b)):
                        if v is None:
                            p.unlink(missing_ok=True)
                        else:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_text(v)
                    before = sorted((x.relative_to(repo).as_posix(), x.stat().st_size)
                                    for x in (repo / "results" / "M2").rglob("*") if x.is_file())
                    p = run_holon(["mutate", "run", "--milestone", "M2", "--dry-run"], cwd=repo, timeout=900)
                    self.assertEqual(p.returncode, code, p.stdout[-800:] + p.stderr[-800:])
                    if code == 2:
                        self.assertTrue(any(x in p.stderr for x in names), p.stderr[-800:])
                    after = sorted((x.relative_to(repo).as_posix(), x.stat().st_size)
                                   for x in (repo / "results" / "M2").rglob("*") if x.is_file())
                    self.assertEqual(before, after)

            for v in variants:
                attempt(*v)
            # I21's exit at the run's pipeline commit: an open high finding committed in the clone refuses
            fp = repo / "audit" / "M2_findings.jsonl"
            fp.write_text(fp.read_text() + json.dumps({"id": "F-M2-X", "severity": "high", "status": "open"}) + "\n")
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am",
                            "open high"], check=True)
            h1 = head()
            attempt("open high finding", rtext, json.dumps(adj), json.dumps(gate_for(h1)), json.dumps(baseline_for(h1)),
                    2)
            for p in (rp, ap, gp, bp):
                p.unlink(missing_ok=True)
            p = run_holon(["mutate", "run", "--milestone", "M2", "--baseline-only", "--dry-run"], cwd=repo, timeout=900)
            self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        finally:
            shutil.rmtree(repo.parent, ignore_errors=True)


def scratch_tree() -> Path:
    """A scratch copy of the checkout parts the replay harness builds (contracts/ and the go.work modules)."""
    d = Path(tempfile.mkdtemp(prefix="i62-tree-"))
    src = morph()
    for x in ["contracts", "bindings", "common", "node", "ops/l2-genesis", "ops/tools", "token-price-oracle",
              "tx-submitter"]:
        (d / x).parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src / x, d / x, symlinks=True, ignore=shutil.ignore_patterns(".git", "node_modules"))
    for f in ("go.work", "go.work.sum"):
        if (src / f).exists():
            shutil.copy2(src / f, d / f)
    return d


def plant(tree: Path, rel: str, old: str, new: str) -> None:
    p = tree / rel
    t = p.read_text()
    if t.count(old) != 1:
        raise AssertionError(f"{rel}: the planted anchor {old!r} occurs {t.count(old)} times")
    p.write_text(t.replace(old, new))


def header(version: int, fill: int = 0xFF, ssvh_zero: bool = True) -> dict:
    facts = load_json(ROOT / "facts" / "morph_header.json")
    h = {f["name"]: "0x" + (bytes([fill]) * f["width"]).hex() for f in facts["types"]["Header"]["fields"]}
    h["version"] = "0x%02x" % version
    if ssvh_zero:
        h["sequencerSetVerifyHash"] = "0x" + "00" * 32
    return h


def header_field(name: str) -> dict:
    return next(f for f in load_json(ROOT / "facts" / "morph_header.json")["types"]["Header"]["fields"]
                if f["name"] == name)


class TestReplayHarness(unittest.TestCase):
    """Construction (S-B1, S-A3, S-A4): the replay harness runs the given tree's own code, by claim, at exact field
    values, with the declared meanings; enc_sol is I16's store-level binding generated from the tree's own text."""

    def test_the_harness_reproduces_i16s_real_outputs_on_the_original_code(self):
        """On the unmutated checkout every role through holon.mutate.replay reproduces the real-side outputs I16
        recorded on its per-edge corpus (results/M2/refinement/<edge>.json outputs_sha256.real, pinned)."""
        holon_module("holon.mutate.replay")
        p = run_holon(["mutate", "replay", "--i16"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        got = json.loads(p.stdout)
        for edge in ("enc_sol", "ok_sol", "enc_go_v0", "enc_go_v1", "ok_go", "dec_go"):
            rec = pin_json(f"results/M2/refinement/{edge}.json")
            with self.subTest(edge=edge):
                self.assertEqual((got[edge]["compared"], got[edge]["outputs_sha256"]),
                                 (rec["compared"], rec["outputs_sha256"]["real"]))

    def test_enc_sol_binds_store_values_at_the_header_widths(self):
        """replay.m0 (1)-(2): every Header field a store call maps is bound from the witness at the Header field's
        width (l1MessagePopped is 8 bytes wide, so 0xff..ff is stored whole), the requires on the unprojected state
        roots are not copied (zero roots execute and are stored as zeros), and the version's require is copied
        (version 3 reverts)."""
        R = holon_module("holon.mutate.replay")
        tree = scratch_tree()
        try:
            self.assertEqual(header_field("l1MessagePopped")["width"], 8)
            out = R.call(tree, "enc_sol", header(0))
            self.assertEqual(out["kind"], "value")
            b = bytes.fromhex(out["value"][2:])
            self.assertEqual(len(b), 249)
            self.assertEqual(b[9:17], b"\xff" * 8)
            zero = dict(header(1), prevStateHash="0x" + "00" * 32, postStateHash="0x" + "00" * 32)
            out = R.call(tree, "enc_sol", zero)
            self.assertEqual(out["kind"], "value", out)
            b = bytes.fromhex(out["value"][2:])
            self.assertEqual(len(b), 257)
            self.assertEqual(b[89:153], b"\x00" * 64)
            self.assertEqual(R.call(tree, "enc_sol", header(3))["kind"], "revert")
        finally:
            shutil.rmtree(tree, ignore_errors=True)

    def test_planted_changes_are_executed(self):
        """Planted edits outside the catalog (a scratch tree) are seen exactly where the code changed: the header
        length of version 1 in Rollup's build block (the harness runs the tree's own block, not a copy of the pinned
        one), a constant store in that block (a store call that writes no Header field keeps the tree's text), the
        version byte of the Go v0 encoder, and a Go getter that panics (recovered per call, falsifying)."""
        R = holon_module("holon.mutate.replay")
        laws = {p.stem: load_json(p) for p in (ROOT / "laws" / "M0").glob("L_*.json")}
        orig = scratch_tree()
        tree = scratch_tree()
        try:
            plant(tree, ROLLUP, "_headerLength = BatchHeaderCodecV1.BATCH_HEADER_LENGTH;",
                  "_headerLength = BatchHeaderCodecV0.BATCH_HEADER_LENGTH;")
            plant(tree, ROLLUP, "storeSequencerSetVerifyHash(_batchPtr, bytes32(0));",
                  "storeSequencerSetVerifyHash(_batchPtr, bytes32(uint256(1)));")
            plant(tree, "common/batch/batch_header.go", "batchBytes[0] = BatchHeaderVersion0",
                  "batchBytes[0] = BatchHeaderVersion1")
            plant(tree, "common/batch/batch_header.go", "return common.BytesToHash(b[25:57]), nil",
                  "return common.BytesToHash(b[25:300]), nil")
            h1, h0 = header(1), header(0)
            self.assertEqual(R.call(orig, "enc_sol", h1)["kind"], "value")
            self.assertEqual(len(bytes.fromhex(R.call(orig, "enc_sol", h1)["value"][2:])), 257)
            self.assertEqual(len(bytes.fromhex(R.call(tree, "enc_sol", h1)["value"][2:])), 249)
            self.assertEqual(bytes.fromhex(R.call(orig, "enc_sol", h0)["value"][2:])[185:217], b"\x00" * 32)
            self.assertEqual(bytes.fromhex(R.call(tree, "enc_sol", h0)["value"][2:])[185:217], b"\x00" * 31 + b"\x01")
            self.assertIs(R.claim(orig, laws["L_par_hdr_v1"], {"h": h1}), True)
            self.assertIs(R.claim(tree, laws["L_par_hdr_v1"], {"h": h1}), False)
            self.assertIs(R.claim(orig, laws["L_par_hdr_v0"], {"h": h0}), True)
            self.assertIs(R.claim(tree, laws["L_par_hdr_v0"], {"h": h0}), False)
            enc = R.call(orig, "enc_sol", h0)["value"]
            self.assertEqual(R.call(tree, "dec_go", enc)["kind"], "panic")
            self.assertIs(R.claim(tree, laws["L_rt_go_v0"], {"h": h0}), False)
            self.assertIs(R.claim(orig, laws["L_rt_go_v0"], {"h": h0}), True)
        finally:
            shutil.rmtree(orig, ignore_errors=True)
            shutil.rmtree(tree, ignore_errors=True)

    def test_values_follow_the_declared_meanings(self):
        """replay.semantics on the original code: a revert or error that is the function's value is not a violation;
        an inner role with no value makes no execution; and (S-B1 (3)) a top-level role call with no value makes no
        execution: a planted version bound of 1 (outside the catalog) makes enc_sol revert at version 2, so
        L_rt_go_v2 is neither falsified nor confirmed there, while it holds on the original code."""
        R = holon_module("holon.mutate.replay")
        laws = {p.stem: load_json(p) for p in (ROOT / "laws" / "M0").glob("L_*.json")}
        tree = scratch_tree()
        low = scratch_tree()
        try:
            r = R.call(tree, "ok_sol", "0x")
            self.assertEqual((sorted(r), r["kind"], r["value"]), (["detail", "kind", "revert_line", "value"], "value",
                                                                  False))
            self.assertIs(R.call(tree, "ok_go", "0x")["value"], False)
            self.assertIs(R.call(tree, "ok_go", "0x00" + "00" * 249)["value"], False)
            self.assertIsNone(R.call(tree, "dec_go", "0x00" + "00" * 249)["value"])
            self.assertEqual(R.call(tree, "enc_sol", header(3))["kind"], "revert")
            self.assertIsNone(R.claim(tree, laws["L_rt_go_v2"], {"h": dict(header(2), version="0x03")}))
            self.assertIs(R.claim(tree, laws["L_dom_hdr"], {"b": "0x00" + "00" * 249}), False)
            self.assertIs(R.claim(tree, laws["L_dom_hdr"], {"b": "0x"}), True)
            plant(low, ROLLUP, "require(batchDataInput.version <= 2,", "require(batchDataInput.version <= 1,")
            r = R.call(low, "enc_sol", header(2))
            self.assertEqual((r["kind"], r["revert_line"]), ("revert", ROLLUP + ":293"))
            self.assertIn(r["revert_line"], instrument()["roles"]["solidity"]["enc_sol"]["revert_lines"])
            self.assertIsNone(R.call(tree, "enc_sol", header(2))["revert_line"])
            self.assertIsNone(R.claim(low, laws["L_rt_go_v2"], {"h": header(2)}))
            self.assertIs(R.claim(tree, laws["L_rt_go_v2"], {"h": header(2)}), True)
        finally:
            shutil.rmtree(tree, ignore_errors=True)
            shutil.rmtree(low, ignore_errors=True)

    def test_trace_witnesses_follow_the_declared_meanings(self):
        """replay.semantics for trace laws (the K1 path of an M2 law): on the unmutated tree every witness trace I15
        replayed for the two baseline-REFUTED M2 laws (replay/M2/report.json at the pin) falsifies its law (a Panic at
        the law's site); a step that reverts (commitBatch by principal 5, 'anyone') is a no-op: alone it falsifies
        nothing, and put before the :636 witness it does not stop the replay; a planted edit that removes the :363
        underflow (a scratch tree) makes the :363 witnesses hold, while the :636 witness still falsifies there."""
        R = holon_module("holon.mutate.replay")
        rep = pin_json("replay/M2/report.json")
        self.assertEqual(sorted(rep["laws"]), ["L_sort_site_rollup_363_1fc7f88a", "L_sort_site_rollup_636_e68daf06"])
        laws = {k: json.loads(at_pin(f"laws/M2/{k}.json")) for k in rep["laws"]}
        traces = {k: [e["trace"] for _, e in sorted(v["entries"].items())] for k, v in rep["laws"].items()}
        self.assertEqual({k: len(v) for k, v in traces.items()},
                         {"L_sort_site_rollup_363_1fc7f88a": 3, "L_sort_site_rollup_636_e68daf06": 1})
        l363, l636 = laws["L_sort_site_rollup_363_1fc7f88a"], laws["L_sort_site_rollup_636_e68daf06"]
        reverting = dict(traces["L_sort_site_rollup_363_1fc7f88a"][0][0], who=5)
        self.assertEqual(reverting["op"], "commitBatch")
        orig = scratch_tree()
        tree = scratch_tree()
        try:
            plant(tree, ROLLUP, "challenges[batchChallenged].startTime - block.timestamp",
                  "challenges[batchChallenged].startTime + block.timestamp")
            for k, ts in traces.items():
                for t in ts:
                    with self.subTest(law=k, trace=t[0]["op"]):
                        self.assertIs(R.trace_claim(orig, laws[k], t), False)
            self.assertIs(R.trace_claim(orig, l636, [reverting]), True)
            self.assertIs(R.trace_claim(orig, l636, [reverting] + traces["L_sort_site_rollup_636_e68daf06"][0]), False)
            for t in traces["L_sort_site_rollup_363_1fc7f88a"]:
                self.assertIs(R.trace_claim(tree, l363, t), True)
            self.assertIs(R.trace_claim(tree, l636, traces["L_sort_site_rollup_636_e68daf06"][0]), False)
        finally:
            shutil.rmtree(orig, ignore_errors=True)
            shutil.rmtree(tree, ignore_errors=True)


class TestHarnessGate(unittest.TestCase):
    """Construction (S-B1 (5), instrument harness_gate): the gate passed before any catalog mutant ran, its controls
    were killed as preregistered, and it reproduces."""

    def test_the_gate_passed_on_the_pinned_code(self):
        g = need(GATE)
        self.assertEqual(g["instrument"], {"path": "spec/M2/lib/mutation_catalog_i62.json", "sha256": INSTRUMENT_SHA256})
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", g["pipeline_commit"]) and is_ancestor(g["pipeline_commit"], "HEAD"))
        self.assertTrue(is_ancestor(prereg_commit(), g["attempts"][0]["pipeline_commit"]))
        self.assertTrue(g["attempts"])
        self.assertEqual(g["pipeline_commit"], g["attempts"][-1]["pipeline_commit"])
        for k, a in enumerate(g["attempts"]):
            with self.subTest(attempt=k):
                self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", a["pipeline_commit"])
                                and is_ancestor(a["pipeline_commit"], "HEAD"))
                self.assertEqual(sorted(a["checks"]), ["controls", "i16", "model", "null"])
                self.assertIs(a["passed"], all(c["passed"] is True for c in a["checks"].values()))
                for c in a["checks"].values():
                    self.assertTrue(isinstance(c["detail"], str) and c["detail"].strip())
                if k > 0:
                    self.assertTrue(isinstance(a["fix"], str) and a["fix"].strip(), "a re-run names the fix")
                if k < len(g["attempts"]) - 1:
                    self.assertIs(a["passed"], False, "attempts stop at the first that passes")
        self.assertIs(g["attempts"][-1]["passed"], True)
        self.assertIs(g["passed"], True)
        if SUMMARY.is_file():
            self.assertEqual(g["pipeline_commit"], need(SUMMARY)["pipeline_commit"])

    def test_the_controls_are_killed_as_preregistered(self):
        """Each planted control's record is killed by K1 through every law its 'expected' names, recomputed by the
        kill criterion from the record; the controls are not catalog mutants and carry no structural class."""
        for c in instrument()["harness_gate"]["controls"]:
            rec = need(CONTROLS / f"{c['id']}.json")
            with self.subTest(control=c["id"]):
                self.assertEqual((rec["id"], rec["stratum"], rec["operator"], rec["structural"]),
                                 (c["id"], None, None, None))
                self.assertEqual(rec["kill"], recompute_kill(rec))
                self.assertEqual(rec["outcome"], c["expected"]["outcome"])
                how = {x["law"]: x["how"] for x in rec["kill"]["by"]}
                for law in c["expected"]["laws"]:
                    self.assertEqual(how.get(law), c["expected"]["how"], (law, rec["kill"]))
                    if "falsifier" in c["expected"]:
                        self.assertEqual(rec["laws"][law]["falsifier"]["kind"], c["expected"]["falsifier"], law)
                # D7: the replay harness the gate certifies disagrees with no control and fails on none
                self.assertEqual(rec["replay_disagreements"], [])
                self.assertEqual([e for e in rec["errors"] if e["step"] == "replay"], [])

    def test_the_gate_came_before_any_catalog_record(self):
        c_gate = first_add("results/M2/mutation_i62/gate.json")
        self.assertTrue(is_ancestor(prereg_commit(), c_gate))
        for m in instrument()["mutants"]:
            p = RESULTS / f"{m['id']}.json"
            if p.is_file():
                c = first_add(p.relative_to(ROOT).as_posix())
                self.assertTrue(is_ancestor(c_gate, c) and c_gate != c, m["id"])

    def test_the_gate_reproduces(self):
        need(GATE)
        p = run_holon(["mutate", "gate", "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


class TestProofChecks(unittest.TestCase):
    """Construction (MAJOR-1 of the I61 prereg review, kept): K2 (b) counts a rejection only over a generated model that
    checks alone, because the pinned Bend prints 'SOME PROOFS FAIL' for a parse or type error of a generated file too."""

    def test_a_model_that_does_not_check_alone_is_told_apart(self):
        Rn = holon_module("holon.mutate.run")
        G = holon_module("holon.gen.model")
        facts = load_json(ROOT / "facts" / "morph_header.json")
        text = G.generate(facts, sha256((ROOT / "facts" / "morph_header.json").read_bytes()))
        d = Path(tempfile.mkdtemp(prefix="i62-model-"))
        try:
            good, bad = d / "good" / "morph_header.bend", d / "bad" / "morph_header.bend"
            for p in (good, bad):
                p.parent.mkdir(parents=True)
            good.write_text(text)
            bad.write_text(text + "\ndef holon_ill_typed(x: Nat) -> Nat:\n  True{}\n")
            self.assertEqual(Rn.model_verdict(good), "ALL PROOFS CHECK")
            self.assertEqual(Rn.model_verdict(bad), "SOME PROOFS FAIL")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestProjection(unittest.TestCase):
    def test_the_committed_projection_is_reproduced(self):
        need(PROJECTED)
        p = run_holon(["mutate", "project", "--check"], timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_the_projection_of_the_pinned_code_equals_the_frozen_facts(self):
        """I62-R4: on the committed documents the projection equals the frozen header facts where I17 and I18 compared
        them: enc_sol (versions 0, 1, 2), enc_go_v0 (0) and enc_go_v1 (1) cell for cell, the dec_go getters, view, and
        ok_sol, ok_go on I17's loader grid; and facts/morph_header.json still compiles to its committed model."""
        L = holon_module("holon.layout")
        proj = need(PROJECTED)
        frozen = load_json(ROOT / "facts" / "morph_header.json")
        self.assertEqual(proj["facts_version"], "holon-facts/0.1")
        self.assertEqual(proj["types"]["Header"], frozen["types"]["Header"])
        for fn, versions in (("enc_sol", (0, 1, 2)), ("enc_go_v0", (0,)), ("enc_go_v1", (1,))):
            for v in versions:
                with self.subTest(fn=fn, version=v):
                    self.assertEqual(L.layout(proj, fn, v), L.layout(frozen, fn, v))
        strip = lambda gs: [{k: g[k] for k in ("name", "offset", "width", "when") if k in g} for g in gs]
        self.assertEqual(strip(proj["functions"]["dec_go"]["getters"]), strip(frozen["functions"]["dec_go"]["getters"]))
        self.assertEqual(proj["functions"]["view"], frozen["functions"]["view"])
        M = holon_module("holon.model_eval")
        for fn in ("ok_sol", "ok_go"):
            grid = ["0x"] + ["0x" + bytes([b0]).hex() + "00" * (n - 1) for b0 in (0, 1, 2, 3, 255)
                             for n in (1, 2, 248, 249, 250, 256, 257, 258)]
            with self.subTest(fn=fn):
                self.assertEqual(M.eval_batch(fn, grid, str(PROJECTED))["outputs"],
                                 M.eval_batch(fn, grid, str(ROOT / "facts" / "morph_header.json"))["outputs"])


# ============================================================================================ delegated steps and order
class TestReviewAndAdjudication(unittest.TestCase):
    def test_the_catalog_review_signed_off_this_instrument(self):
        """I62-R6: the delta review (one fresh agent, both lenses), delegated, signed off with no blocking finding, on
        this instrument, against I61's signed-off review."""
        r = need(REVIEW)
        self.assertEqual(r["instrument"], {"path": "spec/M2/lib/mutation_catalog_i62.json", "sha256": INSTRUMENT_SHA256})
        self.assertEqual(r["base_review"], {"path": "docs/iterations/I61_catalog_review.json",
                                            "sha256": sha256(I61_REVIEW.read_bytes())})
        self.assertEqual(r["verdict"], "signed off")
        self.assertTrue(isinstance(r["delegation"], str) and r["delegation"].strip())
        self.assertEqual(sorted(r["reviews"]), ["fairness", "soundness"])
        for lens, v in r["reviews"].items():
            with self.subTest(lens=lens):
                self.assertIs(v["sign_off"], True)
                self.assertEqual(v["blocking"], [])
                self.assertIsInstance(v["advisory"], list)
                self.assertTrue(isinstance(v["checked"], str) and v["checked"].strip())
                self.assertIsInstance(v["forbidden_files_touched"], list)

    def test_every_mutant_keeps_its_panel_verdict(self):
        """adjudication.panel: I61's verdicts, carried verdict for verdict, naming this instrument and review."""
        inst = instrument()
        a, old = need(ADJ), load_json(I61_ADJ)
        self.assertEqual(a["adjudication_version"], "holon-equivalent-mutants/0.2")
        self.assertEqual(a["instrument"], {"path": "spec/M2/lib/mutation_catalog_i62.json", "sha256": INSTRUMENT_SHA256})
        self.assertEqual((a["mutants_sha256"], a["diff_sheet_sha256"]),
                         (inst["mutants_sha256"], inst["diff_sheet"]["sha256"]))
        self.assertEqual((a["mutants_sha256"], a["diff_sheet_sha256"]), (old["mutants_sha256"], old["diff_sheet_sha256"]))
        self.assertEqual(a["review"], {"path": "docs/iterations/I62_catalog_review.json", "sha256": sha256(REVIEW.read_bytes())})
        self.assertEqual(a["adjudicator"], "delegated_panel")
        for k in ("decision", "panel", "procedure", "blindness_audit"):
            self.assertTrue(isinstance(a["delegation"][k], str) and "I61" in a["delegation"][k], k)
        self.assertEqual(a["verdicts"], old["verdicts"])
        self.assertEqual(sorted(a["verdicts"]), sorted(m["id"] for m in inst["mutants"]))

    def test_the_review_and_the_adjudication_came_in_order(self):
        """prereg -> review -> adjudication (committed alone) -> catalog results; the gate descends from the prereg and
        precedes every catalog record (TestHarnessGate); the run started after the adjudication."""
        c_pre = prereg_commit()
        c_rev = first_add("docs/iterations/I62_catalog_review.json")
        c_adj = first_add("spec/M2/equivalent_mutants_i62.json")
        c_res = first_add("results/M2/mutation_i62/summary.json")
        self.assertTrue(is_ancestor(c_pre, c_rev) and c_pre != c_rev)
        self.assertTrue(is_ancestor(c_rev, c_adj) and c_rev != c_adj)
        self.assertTrue(is_ancestor(c_adj, c_res) and c_adj != c_res)
        self.assertEqual(git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c_adj).splitlines(),
                         ["spec/M2/equivalent_mutants_i62.json"])
        for m in instrument()["mutants"]:
            p = RESULTS / f"{m['id']}.json"
            self.assertTrue(is_ancestor(c_adj, first_add(p.relative_to(ROOT).as_posix())), p.name)
        self.assertTrue(is_ancestor(c_adj, need(SUMMARY)["pipeline_commit"]))

    def test_the_run_started_after_i21s_exit(self):
        """instrument preconditions.i21_exit: the tree of the records' pipeline_commit holds I21's round
        (audit/rounds/M2/round2.json) and no open high finding in audit/M2_findings.jsonl."""
        pc = need(SUMMARY)["pipeline_commit"]
        self.assertTrue(json.loads(git("show", f"{pc}:audit/rounds/M2/round2.json")))
        lines = [json.loads(l) for l in git("show", f"{pc}:audit/M2_findings.jsonl").splitlines() if l.strip()]
        self.assertTrue(lines)
        self.assertEqual([f["id"] for f in lines if f.get("severity") == "high" and f.get("status") == "open"], [])


# ============================================================================================ results (construction)
class TestResults(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inst = instrument()
        cls.s = need(SUMMARY)
        cls.base = need(RESULTS / "baseline.json")
        cls.r = records()
        cls.adj = need(ADJ)
        cls.eq = {i for i, v in cls.adj["verdicts"].items() if v["equivalent"]}
        cls.ms = by_id(cls.inst)

    def test_summary_names_its_inputs(self):
        s = self.s
        self.assertEqual((s["version"], s["iteration"], s["milestone"]), ("holon-mutation/0.3", "I62", "M2"))
        self.assertEqual(s["instrument"], {"path": "spec/M2/lib/mutation_catalog_i62.json", "sha256": INSTRUMENT_SHA256})
        self.assertEqual(s["mutants_sha256"], self.inst["mutants_sha256"])
        self.assertEqual(s["review"], {"path": "docs/iterations/I62_catalog_review.json", "sha256": sha256(REVIEW.read_bytes())})
        self.assertEqual(s["adjudication"], {"path": "spec/M2/equivalent_mutants_i62.json", "sha256": sha256(ADJ.read_bytes())})
        self.assertEqual(s["gate"], {"path": "results/M2/mutation_i62/gate.json", "sha256": sha256(GATE.read_bytes())})
        self.assertEqual((s["threshold"], s["threshold_stratum"], s["seed"]), (0.8, "A", 20261061))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", s["pipeline_commit"]) and is_ancestor(s["pipeline_commit"], "HEAD"))
        for rec in [self.base, *self.r.values()]:
            self.assertEqual(rec["pipeline_commit"], s["pipeline_commit"])

    def test_the_baseline_reproduces_the_pinned_statuses_and_documents(self):
        """instrument preconditions.baseline (S-A7)."""
        b = self.base
        self.assertEqual((b["id"], b["stratum"], b["operator"], b["structural"]), ("baseline", None, None, None))
        self.assertEqual(b["extraction"], {"status": "ok", "errors": {}})
        st = {k: e["mutant"] for k, e in b["laws"].items()}
        for law, e in b["laws"].items():
            self.assertEqual(e["decided"], "run", law)
        base = self.inst["baseline"]
        self.assertEqual({k: v for k, v in st.items() if b["laws"][k]["set"] == "M0"}, base["M0"])
        self.assertEqual({k: v for k, v in st.items() if b["laws"][k]["set"] == "M1x"}, base["M1x"])
        self.assertEqual({k: v for k, v in st.items() if b["laws"][k]["set"] == "M2"}, base["M2"])
        self.assertEqual(sorted(b["documents"]),
                         sorted(f"spec/M2/facts/{p.name}" for p in (SPEC2 / "facts").glob("*.extracted.json")))
        self.assertGreaterEqual(len(b["documents"]), 7)
        for path, d in b["documents"].items():
            with self.subTest(document=path):
                self.assertIs(d["changed"], False)
                self.assertEqual(d["normalized_sha256"], normalized_sha256(pin_json(path)))
        self.assertEqual(b["projection"]["normalized_sha256"], normalized_sha256(need(PROJECTED)))
        fam = baseline_families()
        der = {e["law_id"]: sorted(e["entry_points"]) for e in pin_json("laws/M2/DERIVATION.json")["laws"]}
        for law, e in b["laws"].items():
            with self.subTest(law=law):
                self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", e["own_input"]["sha256"] or ""))
                self.assertEqual(e["family"], fam[law])
                self.assertEqual(e["entry_points"], der.get(law) if e["set"] == "M2" else None)
                if e["mutant"] == "PROVED":
                    # the generator K2 (b) re-runs is the pinned record's accepted proof attempt
                    pinned_rec = pin_json({"M0": f"results/M0/{law}.json", "M1x": f"results/M2/extracted_m1/{law}.json",
                                           "M2": f"results/M2/{law}.json"}[e["set"]])
                    acc = [a["generator"] for a in pinned_rec["attempts"]
                           if a.get("kind") == "proof" and a.get("marker") == "ALL PROOFS CHECK"]
                    self.assertTrue(acc)
                    self.assertEqual((e["proof"] or {}).get("marker"), "ALL PROOFS CHECK")
                    self.assertEqual((e["proof"] or {}).get("verdict"), "ALL PROOFS CHECK")
                    self.assertEqual(e["proof"]["generator"], acc[-1])

    def test_every_record_covers_the_baseline_law_set(self):
        base = set(self.base["laws"])
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                self.assertEqual((rec["id"], rec["stratum"], rec["operator"], rec["structural"]),
                                 (i, self.ms[i]["stratum"], self.ms[i]["operator"], self.ms[i]["structural"]["class"]))
                self.assertTrue(base <= set(rec["laws"]))
                for law, e in rec["laws"].items():
                    if law in base:
                        self.assertEqual(e["baseline"], self.base["laws"][law]["mutant"])
                    else:
                        self.assertEqual(e["baseline"], "absent")
                    self.assertIn(e["mutant"], STATUSES + ("absent", "error"))
                    if e["decided"] == "carried":
                        self.assertIs(e["own_input"]["changed"], False)
                        self.assertEqual(e["mutant"], e["baseline"])

    def test_own_inputs_and_documents_are_compared_with_the_baseline(self):
        b = self.base
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                if rec["extraction"]["status"] == "ok":
                    self.assertEqual(set(rec["documents"]), set(b["documents"]))
                for path, d in rec["documents"].items():
                    self.assertIs(d["changed"], d["normalized_sha256"] != b["documents"][path]["normalized_sha256"])
                pj = rec["projection"]
                if pj["error"] is None and pj["normalized_sha256"] is not None:
                    self.assertIs(pj["changed"], pj["normalized_sha256"] != b["projection"]["normalized_sha256"])
                else:
                    self.assertIsNone(pj["changed"])
                for law, e in rec["laws"].items():
                    if e["mutant"] in STATUSES:
                        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", e["own_input"]["sha256"] or ""), law)
                        self.assertIsInstance(e["own_input"]["changed"], bool, law)
                    if law in b["laws"]:
                        self.assertEqual(e["family"], b["laws"][law]["family"], law)
                        if e["own_input"]["sha256"] is not None:
                            self.assertIs(e["own_input"]["changed"],
                                          e["own_input"]["sha256"] != b["laws"][law]["own_input"]["sha256"])
                    else:
                        self.assertEqual(e["set"], "M2", law)
                        self.assertTrue(re.fullmatch(r"M2:[A-Z]+/[a-z_]+", e["family"]), law)

    def test_predicted_sets_follow_the_rule(self):
        """instrument predicted: the frozen sets for baseline laws; a law absent at baseline is predicted iff its
        mutant DERIVATION entry points meet the mutant's actions; every record carries its sets recomputed on its own
        documents (predicted.recomputed)."""
        for i, rec in self.r.items():
            m = self.ms[i]
            want = set(m["predicted"]["M0"] + m["predicted"]["M1x"] + m["predicted"]["M2"])
            with self.subTest(mutant=i):
                got = {k for k, e in rec["laws"].items() if e["predicted"]}
                self.assertEqual({k for k in got if rec["laws"][k]["baseline"] != "absent"}, want)
                for law, e in rec["laws"].items():
                    self.assertIsInstance(e["predicted"], bool, law)
                    if e["baseline"] == "absent":
                        self.assertEqual(e["set"], "M2", law)
                        self.assertIsInstance(e["entry_points"], list, law)
                        self.assertIs(e["predicted"], bool(set(e["entry_points"]) & set(m["actions"])), law)
                rp = rec["recomputed"]
                self.assertEqual(sorted(rp), ["actions", "edges", "predicted"])
                self.assertEqual(sorted(rp["predicted"]), ["M0", "M1x", "M2"])
                for v in (rp["edges"], rp["actions"], *rp["predicted"].values()):
                    self.assertEqual(v, sorted(v))
                if not any(d["changed"] for d in rec["documents"].values()):
                    self.assertEqual((rp["edges"], rp["actions"], rp["predicted"]),
                                     (m["edges"], m["actions"], m["predicted"]))

    def test_new_laws_are_localized_to_the_mutated_function(self):
        """K1 for a law absent at baseline needs its basis span inside the function the mutant mutates
        (site_in_mutated_function), recomputed from the record's basis_span and the pinned AST."""
        where = mutated_function_lines()
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                for law, e in rec["laws"].items():
                    if e["baseline"] == "absent":
                        self.assertIs(e["site_in_mutated_function"], basis_inside(e["basis_span"], where.get(i)), law)

    def test_proof_losses_are_completed_rejections_of_the_baseline_generator(self):
        """K2 (b) and not_K2 (S-A1, S-A2): a law PROVED at baseline and decided (run) UNKNOWN on the mutant carries the
        baseline record's generator, an exit code and the checker's own verdict line 'SOME PROOFS FAIL' (anything else,
        a timeout, a checker exit with no verdict line, Unsupported or None, is 'error', and only for a law that would
        otherwise end UNKNOWN); a falsifier, of kind falsification or partiality with its model tie, was found among the
        first 16 candidates; at most 16 hits."""
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                for law, e in rec["laws"].items():
                    if e["hits"] is not None:
                        self.assertLessEqual(len(e["hits"]), 16, law)
                    f = e["falsifier"]
                    if f is not None:
                        self.assertTrue(isinstance(f["tried"], int) and 1 <= f["tried"] <= 16)
                        self.assertIn(f["kind"], ("falsification", "partiality"))
                        self.assertIsInstance(f["model_tied"], bool)
                        if f["kind"] == "partiality":
                            sol = self.inst["roles"]["solidity"]
                            self.assertIn(f["role"], sol, law)
                            self.assertIn(f["revert_line"], sol[f["role"]]["revert_lines"], law)
                        else:
                            self.assertEqual((f["role"], f["revert_line"]), (None, None), law)
                    if e["proof"] is not None:
                        self.assertIn(e["proof"]["verdict"], (None, "ALL PROOFS CHECK", "SOME PROOFS FAIL"), law)
                    if law in self.base["laws"] and e["baseline"] == "PROVED" and e["mutant"] == "UNKNOWN":
                        self.assertEqual(e["decided"], "run", law)
                        pr = e["proof"] or {}
                        self.assertEqual(pr.get("generator"), self.base["laws"][law]["proof"]["generator"], law)
                        self.assertIsNotNone(pr.get("exit_code"), law)
                        self.assertEqual(pr.get("verdict"), "SOME PROOFS FAIL", law)
                        self.assertEqual(pr.get("model_verdict"), "ALL PROOFS CHECK", law)
                    if e["mutant"] == "error":
                        # kill_criterion.decided: a checked counter-law or a proof decides the law
                        self.assertNotEqual((e["counter_law"] or {}).get("marker"), "ALL PROOFS CHECK", law)
                    if e["witness"] is not None or e["falsifier"] is not None or law_how(e) == "masked_obstruction":
                        self.assertIsInstance(e["witness_fits_entry"], bool, law)
                        if language(self.ms[i]) == "go":
                            self.assertIs(e["witness_fits_entry"], True, law)
                    else:
                        self.assertIsNone(e["witness_fits_entry"], law)

    def test_kill_decisions_follow_the_criterion(self):
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                self.assertEqual(rec["kill"], recompute_kill(rec))
                self.assertEqual(rec["recomputed_only"], recompute_recomputed_only(rec))
                for law, e in rec["laws"].items():
                    self.assertEqual(e["how"], law_how(e), law)
                    if e["replay"] is not None:
                        self.assertEqual([x["label"] for x in e["replay"]], e["hits"][:16])
                self.assertEqual(rec["masked_obstructions"],
                                 sorted(l for l, e in rec["laws"].items() if law_how(e) == "masked_obstruction"))
                self.assertEqual(rec["proof_lost_unwitnessed"],
                                 sorted(l for l, e in rec["laws"].items() if law_how(e) == "proof_lost_unwitnessed"))
                self.assertEqual(rec["replay_disagreements"],
                                 sorted(l for l, e in rec["laws"].items() if law_how(e) == "replay_disagreement"))
                self.assertEqual(rec["baseline_findings"],
                                 sorted(l for l, e in rec["laws"].items() if law_how(e) == "baseline_finding"))
                self.assertEqual(rec["outcome"], outcome_of(rec))

    def test_errors_are_scoped_to_laws(self):
        """S-B2 (I22) and S-A1: an error marks laws, never a whole mutant that a completed path killed."""
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                errs = {l for e in rec["errors"] for l in e["laws"]}
                self.assertEqual(errs, {l for l, e in rec["laws"].items() if e["mutant"] == "error"})
                for e in rec["errors"]:
                    self.assertTrue(e["step"] and e["message"])
                if recompute_kill(rec)["killed"]:
                    self.assertEqual(rec["outcome"], "killed")

    def test_every_record_holds_exactly_its_channel_runs(self):
        for i, rec in [("baseline", self.base), *self.r.items()]:
            if rec["extraction"]["status"] != "ok":
                continue
            with self.subTest(record=i):
                if i == "baseline":
                    want = ["i16_edge", "i20_step"]
                else:
                    m = self.ms[i]
                    sol = m["file"].endswith(".sol")
                    want = [] if m["stratum"] == "B" else sorted(
                        (["i20_step"] if sol else []) + (["i16_edge"] if (not sol or m["edges"]) else []))
                runs = channel_runs(rec)
                self.assertEqual(sorted(r["harness"] for r in runs), want)
                for r in runs:
                    if i == "baseline":
                        self.assertIsNone(r["error"])
                        self.assertEqual(r["new_disagreements"], [])
                    if r["harness"] == "i20_step" and r["error"] is None:
                        self.assertIsInstance(r["corpus_differences"], list)
                        if r["steps"] < 2432:
                            # D2: only a mutant whose every trace's deployment reverts compares fewer steps: none,
                            # and every step of the baseline's corpus differs
                            self.assertNotEqual(i, "baseline")
                            self.assertEqual((r["steps"], r["new_disagreements"]), (0, []))
                            self.assertEqual(r["corpus_differences"], sorted(need(
                                ROOT / "gen" / "M2" / "mutation_i62" / "i20_corpus.json")["observables"]))
                    if r["harness"] == "i16_edge":
                        self.assertIsNone(r["corpus_differences"])
                if i != "baseline":
                    self.assertIs(rec["extraction_defect_detected"], defect_flag(rec))
                    i20 = [r for r in runs if r["harness"] == "i20_step"]
                    want_c = (bool(i20[0]["corpus_differences"]) if i20 and i20[0]["error"] is None else None)
                    self.assertIs(rec["corpus_detected"], want_c)

    def test_survivors_are_classified_mechanically(self):
        listed = {x["id"]: x for x in self.s["survivors"]}
        self.assertEqual(sorted(listed), sorted(i for i, rec in self.r.items() if rec["outcome"] != "killed"))
        agree = defaultdict(Counter)
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                want = survivor_class(rec, i in self.eq)
                self.assertEqual((rec["class"], rec["gap_stage"], rec["rule_gap_kind"]), want)
                if rec["outcome"] != "killed":
                    x = listed[i]
                    self.assertEqual((x["class"], x["gap_stage"], x["rule_gap_kind"], x["structural"]),
                                     want + (self.ms[i]["structural"]["class"],))
                    self.assertTrue(x["why"].strip())
                    agree[self.ms[i]["structural"]["class"]]["/".join(v for v in want if v)] += 1
        self.assertEqual(self.s["structural_agreement"], {k: dict(v) for k, v in agree.items()})

    def test_the_rates_are_recomputed(self):
        """BUILD_PLAN I22 Exit: the rates, recomputed by test, per stratum, operator, family, language and site, with
        the non-error, K1-only, plan-literal, detection, deduplicated, B-codec and contradiction-reversed variants."""
        s, r, eq = self.s, self.r, self.eq
        killed = {i for i, rec in r.items() if rec["outcome"] == "killed"}
        err = {i for i, rec in r.items() if rec["outcome"] == "error"}
        k1 = {i for i, rec in r.items() if any(x["how"] == "K1" for x in rec["kill"]["by"])}
        dup = {i for i, v in self.adj["verdicts"].items() if v["duplicate_of"]}
        for st, members in (("A", [i for i in r if i[0] == "A"]), ("B", [i for i in r if i[0] == "B"]), ("all", list(r))):
            ms = set(members)
            ne = ms - eq
            e = s["strata"][st]
            with self.subTest(stratum=st):
                self.assertEqual((e["mutants"], e["killed"], e["killed_k1"], e["equivalent"], e["killed_equivalent"],
                                  e["errors"]),
                                 (len(ms), len(killed & ms), len(k1 & ms), len(eq & ms), len(killed & eq & ms),
                                  len(err & ms)))
                self.assertEqual(e["rate_all"], rate(len(killed & ms), len(ms)))
                self.assertEqual(e["rate_non_equivalent"], rate(len(killed & ne), len(ne)))
                self.assertEqual(e["meets_threshold"], 5 * len(killed & ne) >= 4 * len(ne) if st == "A" else None)
                if st == "all":
                    continue
                self.assertEqual(s["non_error"][st], {"rate_all": rate(len(killed & (ms - err)), len(ms - err)),
                                                      "rate_non_equivalent": rate(len(killed & (ne - err)),
                                                                                  len(ne - err))})
                langs = {}
                for lang in ("solidity", "go"):
                    lm = {i for i in ms if language(self.ms[i]) == lang}
                    if not lm:
                        continue
                    lne = lm - eq
                    langs[lang] = {"mutants": len(lm), "killed": len(killed & lm), "errors": len(err & lm),
                                   "equivalent": len(eq & lm), "rate_all": rate(len(killed & lm), len(lm)),
                                   "rate_non_equivalent": rate(len(killed & lne), len(lne))}
                self.assertEqual(s["by_language"][st], langs)
                sites = defaultdict(set)
                for i in ms:
                    m = self.ms[i]
                    sites[(m["file"], m["offset"], m["operator"])].add(i)
                ks = {k for k, v in sites.items() if v & killed}
                es = {k for k, v in sites.items() if v <= eq}
                nes = set(sites) - es
                self.assertEqual(s["per_site"][st], {"sites": len(sites), "killed": len(ks), "equivalent": len(es),
                                                     "rate_non_equivalent": rate(len(ks & nes), len(nes))})
                self.assertEqual(s["k1_only"][st], rate(len(k1 & ne), len(ne)))
                self.assertEqual(s["plan_literal"][st], rate(sum(1 for i in ms if plan_literal(r[i])), len(ms)))
                self.assertEqual(s["new_law_kills"][st],
                                 sum(1 for i in ms if r[i]["kill"]["by"]
                                     and all(r[i]["laws"][x["law"]]["baseline"] == "absent" for x in r[i]["kill"]["by"])))
                tied = untied = 0
                for i in ms & killed:
                    k2 = [r[i]["laws"][x["law"]] for x in r[i]["kill"]["by"] if x["how"] == "K2"]
                    if any(e_["falsifier"]["model_tied"] for e_ in k2):
                        tied += 1
                    elif k2:
                        untied += 1
                self.assertEqual(s["k2_model_tied"][st], {"tied": tied, "untied": untied})
                det = {i for i in ms if r[i]["outcome"] == "killed" or r[i]["kill"]["unpredicted"]
                       or r[i]["masked_obstructions"]}
                self.assertEqual(s["detection"][st], rate(len(det), len(ms)))
                dd, dne = ms - dup, ne - dup
                self.assertEqual(s["dedup"][st], {"rate_all": rate(len(killed & dd), len(dd)),
                                                  "rate_non_equivalent": rate(len(killed & dne), len(dne))})
                ops = defaultdict(lambda: Counter())
                for i in ms:
                    o = self.ms[i]["operator"]
                    ops[o]["mutants"] += 1
                    ops[o]["killed"] += i in killed
                    ops[o]["killed_k1"] += i in k1
                    ops[o]["equivalent"] += i in eq
                    ops[o]["errors"] += i in err
                    ops[o]["unpredicted"] += bool(r[i]["kill"]["unpredicted"])
                    ops[o]["masked"] += bool(r[i]["masked_obstructions"])
                    ops[o]["proof_lost_unwitnessed"] += bool(r[i]["proof_lost_unwitnessed"])
                self.assertEqual(s["by_operator"][st], {o: {k: c[k] for k in ("mutants", "killed", "killed_k1",
                                                                              "equivalent", "errors", "unpredicted",
                                                                              "masked", "proof_lost_unwitnessed")}
                                                        for o, c in ops.items()})
                fams = defaultdict(lambda: {"predicted": 0, "killed": 0})
                for i in ms:
                    laws_ = r[i]["laws"]
                    for f in {e_["family"] for e_ in laws_.values() if e_["predicted"]}:
                        fams[f]["predicted"] += 1
                    for f in {laws_[x["law"]]["family"] for x in r[i]["kill"]["by"]}:
                        fams[f]["killed"] += 1
                self.assertEqual(s["by_family"][st], dict(fams))
                self.assertEqual(s["unpredicted_rate"][st],
                                 rate(sum(1 for i in ms if r[i]["kill"]["unpredicted"]), len(ms)))
                self.assertEqual(s["masked_rate"][st],
                                 rate(sum(1 for i in ms if r[i]["masked_obstructions"]), len(ms)))
        codec = {i for i in r if i[0] == "B"
                 and self.ms[i]["function"] in self.inst["in_scope"]["files"][self.ms[i]["file"]]["codec_functions"]}
        cne = codec - eq
        self.assertEqual(s["B_codec_functions"], {"mutants": len(codec), "killed": len(killed & codec),
                                                  "equivalent": len(eq & codec),
                                                  "rate_all": rate(len(killed & codec), len(codec)),
                                                  "rate_non_equivalent": rate(len(killed & cne), len(cne))})
        # equivalence.contradictions: function-level, and reachable when corpus_detected or the record says the
        # contradicting witness fits the entry function (the law entry's 'witness_fits_entry')
        fl, rc = [], []
        for i in sorted(eq):
            rec = r[i]
            why, laws_c = [], set()
            k1 = {x["law"] for x in rec["kill"]["by"] + rec["kill"]["unpredicted"] if x["how"] == "K1"}
            if k1:
                why.append("K1")
                laws_c |= k1
            fal = {l for l, e_ in rec["laws"].items() if e_.get("falsifier")}
            if fal:
                why.append("K2 (c)")
                laws_c |= fal
            if rec["masked_obstructions"]:
                why.append("masked")
                laws_c |= set(rec["masked_obstructions"])
            if rec["corpus_detected"]:
                why.append("corpus")
            if why:
                fl.append(i)
                fits = any(rec["laws"][l].get("witness_fits_entry") is True for l in laws_c)
                if rec["corpus_detected"] or fits:
                    rc.append(i)
        self.assertEqual([x["id"] for x in s["contradicted"]["function_level"]], fl)
        self.assertEqual([x["id"] for x in s["contradicted"]["reachable"]], rc)
        for key, lst in (("function_level", fl), ("reachable", rc)):
            ne_rev = {i for i in (set(r) - eq) | set(lst) if i[0] == "A"}
            self.assertEqual(s["rate_non_equivalent_reversed"][key], rate(len(killed & ne_rev), len(ne_rev)))
        p = run_holon(["mutate", "rate", "--check"], timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])

    def test_the_summary_lists_are_the_records(self):
        """The summary's lists, which several predictions read, are exactly the records'."""
        s, r = self.s, self.r
        self.assertEqual(s["unpredicted"], [{"id": i, "law": x["law"], "how": x["how"]}
                                            for i in sorted(r) for x in r[i]["kill"]["unpredicted"]])
        self.assertEqual(s["recomputed_only"], [{"id": i, "law": x["law"], "how": x["how"]}
                                                for i in sorted(r) for x in r[i]["recomputed_only"]])
        for key in ("masked_obstructions", "proof_lost_unwitnessed"):
            self.assertEqual(s[key], [{"id": i, "law": law} for i in sorted(r) for law in r[i][key]], key)
        self.assertEqual(s["errors"], sorted(i for i in r if r[i]["outcome"] == "error"))
        self.assertEqual(s["extraction_defects"], sorted(i for i in r if r[i]["extraction_defect_detected"] is True))
        self.assertEqual(s["corpus_detected"], sorted(i for i in r if r[i]["corpus_detected"] is True))

    def test_metrics_report_mutation_adequacy(self):
        """I62-R9: I22-R6's metric name and shape, from stratum A of I62's summary, which supersedes I61's (I23 reads
        it); it leaves not_applicable."""
        m = need(ROOT / "results" / "M2" / "metrics.json")
        a = self.s["strata"]["A"]
        self.assertEqual(m["mutation_adequacy"], {"source": "results/M2/mutation_i62/summary.json", "threshold": 0.8,
                                                  "rate_all": a["rate_all"],
                                                  "rate_non_equivalent": a["rate_non_equivalent"],
                                                  "meets_threshold": a["meets_threshold"]})
        self.assertNotIn("mutation_adequacy", m.get("not_applicable") or {})

    def test_m2_exit_b_the_rate_meets_the_threshold(self):
        """BUILD_PLAN I22 Exit and §15.2 M2 exit (b): stratum A's rate_non_equivalent >= 0.80 (Q6). The drafter
        forecasts that this fails (I62-P2; instrument threshold.consequence); it stays, unchanged, as the exit check."""
        self.assertTrue(self.s["strata"]["A"]["meets_threshold"], self.s["strata"]["A"]["rate_non_equivalent"])

    def test_the_pinned_checkout_and_sol_deps_are_untouched(self):
        inst = self.inst
        p = subprocess.run(["git", "-C", str(morph()), "status", "--porcelain"], capture_output=True, text=True)
        self.assertEqual((p.returncode, p.stdout), (0, ""))
        p = subprocess.run(["git", "-C", str(morph()), "rev-parse", "HEAD"], capture_output=True, text=True)
        self.assertEqual(p.stdout.strip(), inst["target"]["commit"])
        for f, v in inst["in_scope"]["files"].items():
            if v["root"] == "sol_deps":
                self.assertEqual(sha256((sol_deps() / f).read_bytes()), v["sha256"], f)


class TestDeterminism(unittest.TestCase):
    def test_a_sample_reruns_identically_at_the_pipeline_commit(self):
        """run --check: the baseline and one mutant per shape (a codec store, a Rollup statement, an OpenZeppelin
        modifier, a Go encoder, a Go check, a Go getter, a stratum-B file) and two of I61's error mutants (A076, whose
        deployment reverts, D2; A116, with a width law over the header document, D3) rerun with --no-carry at the
        records' pipeline_commit and reproduce their records byte for byte, each law's "decided" field aside."""
        need(SUMMARY)
        p = run_holon(["mutate", "run", "--milestone", "M2", "--only", "A001,A035,A076,A077,A116,A123,A165,A169,B001",
                       "--check"], timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


# ============================================================================================ predictions
def first_run_view(rec: dict) -> dict:
    """What I62's predictions compare between a record and I61's: the outcome and class, the kill, the obstruction
    lists, the flags, and per law its statuses, how, witness and prediction (messages, own-input hashes, timings and
    pipeline_commit aside)."""
    keys = ("outcome", "class", "gap_stage", "rule_gap_kind", "kill", "recomputed_only", "masked_obstructions",
            "proof_lost_unwitnessed", "replay_disagreements", "baseline_findings", "extraction_defect_detected",
            "corpus_detected")
    v = {k: rec[k] for k in keys}
    v["laws"] = {law: {k: e[k] for k in ("baseline", "mutant", "how", "witness", "predicted")}
                 for law, e in rec["laws"].items()}
    return v


def expected_view(i: str, corpus_steps: list) -> dict:
    """I61's record of mutant i with the fixes' effects (instrument replaces.defects), as I62 predicts it."""
    v = first_run_view(load_json(I61_RESULTS / f"{i}.json"))
    if i in NONE_VALUE:                                   # D1: the round-trip laws are decided by their replay
        for law in NONE_VALUE[i]:
            v["laws"][law]["how"] = "K1"
            v["kill"]["by"] = sorted(v["kill"]["by"] + [{"law": law, "how": "K1"}],
                                     key=lambda x: (x["law"], x["how"]))
        v["replay_disagreements"] = []
        v["extraction_defect_detected"] = i in NONE_VALUE_STILL_DEFECT
    if i in GENESIS + HEADER_WIDTH:                       # D2, D3, D4: the width laws are decided
        for law in WIDTH_LAWS:
            v["laws"][law]["mutant"] = "UNKNOWN"
    if i in FORMER_ERRORS:
        v["outcome"], v["class"], v["gap_stage"], v["rule_gap_kind"] = "survived", "rule_gap", None, "law_unmoved"
    if i in GENESIS:                                      # D2: every trace's deployment reverts: every step differs
        v["corpus_detected"] = True
        v["extraction_defect_detected"] = False
    return v


class TestPredictions(unittest.TestCase):
    """I62's forecast: I61's measured outcomes with the fixes' expected effects (instrument limitations: made after
    I61's run and the test units of harness_gate.before_prereg)."""

    @classmethod
    def setUpClass(cls):
        cls.inst = instrument()
        cls.ms = by_id(cls.inst)
        cls.base = need(RESULTS / "baseline.json")
        cls.r = records()
        cls.s = need(SUMMARY)
        cls.s61 = load_json(I61_RESULTS / "summary.json")
        cls.corpus = sorted(need(ROOT / "gen" / "M2" / "mutation_i62" / "i20_corpus.json")["observables"])

    def test_the_baseline_reproduces_every_committed_status(self):
        """I62-P1: the null mutant, re-extracted from scratch and projected, decides M0 as results/M0 (5 PROVED, 3
        REFUTED), M1x as results/M2/differential.json 'extracted' (7 PROVED, 7 REFUTED, L_tag_BVH UNKNOWN) and M2 as
        results/M2 (6 PROVED, 4 UNKNOWN, 2 REFUTED), its documents and projection are the committed ones, and its laws,
        documents and corpus are I61's baseline's."""
        st = {k: e["mutant"] for k, e in self.base["laws"].items()}
        self.assertEqual({k: v for k, v in st.items() if self.base["laws"][k]["set"] == "M0"}, M0_BASELINE)
        for s_, want in (("M1x", {"PROVED": 7, "REFUTED": 7, "UNKNOWN": 1}), ("M2", {"PROVED": 6, "UNKNOWN": 4,
                                                                                    "REFUTED": 2})):
            self.assertEqual(dict(Counter(v for k, v in st.items() if self.base["laws"][k]["set"] == s_)), want)
        self.assertEqual(self.base["extraction"]["status"], "ok")
        self.assertIs(self.base["projection"]["error"], None)
        old = load_json(I61_RESULTS / "baseline.json")
        self.assertEqual(first_run_view(self.base), first_run_view(old))
        self.assertEqual(self.base["documents"], old["documents"])
        self.assertEqual(self.base["projection"], old["projection"])
        self.assertEqual({k: e["own_input"] for k, e in self.base["laws"].items()},
                         {k: e["own_input"] for k, e in old["laws"].items()})
        self.assertEqual(need(ROOT / "gen" / "M2" / "mutation_i62" / "i20_corpus.json"),
                         load_json(ROOT / "gen" / "M2" / "mutation_i61" / "i20_corpus.json"))

    def test_stratum_totals_and_exit_b(self):
        """I62-P2: stratum A: 96 of 192 killed (79 with a K1 law), 12 equivalent, none in error, rate_non_equivalent
        96/180 < 0.80 (M2 exit (b) not met), the non-error rates equal to the plain ones; stratum B: 0 of 50 killed, 5
        equivalent, none in error."""
        a, b = self.s["strata"]["A"], self.s["strata"]["B"]
        self.assertEqual((a["mutants"], a["killed"], a["killed_k1"], a["equivalent"], a["errors"]), (192, 96, 79, 12, 0))
        self.assertEqual((a["rate_non_equivalent"]["num"], a["rate_non_equivalent"]["den"]), (96, 180))
        self.assertIs(a["meets_threshold"], False)
        self.assertEqual(self.s["non_error"]["A"], {"rate_all": a["rate_all"],
                                                   "rate_non_equivalent": a["rate_non_equivalent"]})
        self.assertEqual((b["mutants"], b["killed"], b["equivalent"], b["errors"]), (50, 0, 5, 0))
        self.assertEqual(self.s["errors"], [])

    def test_every_record_is_the_first_runs_but_for_the_fixes(self):
        """I62-P3: every catalog record equals I61's (first_run_view) except the fixes' effects (expected_view): D1 on
        A001 and A058, D2 on A076, A098, A100, A101 and A104, D3 and D4 on A027, A031, A116 and A120. Nothing else
        moves."""
        for i in sorted(self.r):
            with self.subTest(mutant=i):
                self.assertEqual(first_run_view(self.r[i]), expected_view(i, self.corpus))

    def test_none_values_are_decided_by_their_replay(self):
        """I62-P4 (D1): A001's three round-trip laws and A058's L_rt_go_v1 satisfy K1: their recorded witness is I61's
        (its first hit), every hit replays on the mutant and none on the original; no record holds a replay
        disagreement; the extraction defects are I61's but A001 (whose flag only the replay disagreements set)."""
        for i, laws in NONE_VALUE.items():
            old = load_json(I61_RESULTS / f"{i}.json")
            for law in laws:
                with self.subTest(mutant=i, law=law):
                    e = self.r[i]["laws"][law]
                    self.assertIn({"law": law, "how": "K1"}, self.r[i]["kill"]["by"])
                    self.assertEqual(e["witness"], old["laws"][law]["witness"])
                    self.assertTrue(e["replay"])
                    self.assertTrue(all(x["mutant"] is True and x["original"] is False for x in e["replay"]),
                                    e["replay"])
        for i, rec in self.r.items():
            self.assertEqual(rec["replay_disagreements"], [], i)
        self.assertEqual(self.s["extraction_defects"], [x for x in self.s61["extraction_defects"] if x != "A001"])

    def test_undeployable_mutants_complete_their_channel(self):
        """I62-P5 (D2): the five mutants that break Rollup's genesis import complete their i20_step run with every
        trace's deployment reverted (steps 0, no new disagreement, every baseline corpus step a difference), so they
        are corpus_detected and no extraction defect; they survive, filed rule_gap (law_unmoved); A076 keeps its
        masked obstruction on L_dom_hdr. The corpus_detected list is I61's plus the five."""
        for i in GENESIS:
            with self.subTest(mutant=i):
                rec = self.r[i]
                i20 = [x for x in rec["refinement"]["channels"] if x["harness"] == "i20_step"]
                self.assertEqual(len(i20), 1)
                self.assertEqual((i20[0]["error"], i20[0]["steps"], i20[0]["new_disagreements"]), (None, 0, []))
                self.assertEqual(i20[0]["corpus_differences"], self.corpus)
                self.assertEqual((rec["corpus_detected"], rec["extraction_defect_detected"]), (True, False))
                self.assertEqual((rec["outcome"], rec["class"], rec["rule_gap_kind"]),
                                 ("survived", "rule_gap", "law_unmoved"))
                self.assertEqual(rec["errors"], [])
        self.assertEqual(self.r["A076"]["masked_obstructions"], ["L_dom_hdr"])
        self.assertEqual(self.s["corpus_detected"], sorted(set(self.s61["corpus_detected"]) | set(GENESIS)))

    def test_the_header_width_laws_are_decided(self):
        """I62-P6 (D3, D4): the two SORT-width laws of A027, A031, A116 and A120 are decided UNKNOWN by a run (no
        error), A116 and A120 survive (rule_gap, law_unmoved) and A027 and A031 stay killed as in I61; no record holds
        an error."""
        for i in HEADER_WIDTH:
            with self.subTest(mutant=i):
                rec = self.r[i]
                for law in WIDTH_LAWS:
                    self.assertEqual((rec["laws"][law]["mutant"], rec["laws"][law]["decided"],
                                      rec["laws"][law]["error"]), ("UNKNOWN", "run", None), law)
                self.assertEqual(rec["errors"], [])
        for i in ("A116", "A120"):
            self.assertEqual((self.r[i]["outcome"], self.r[i]["class"]), ("survived", "rule_gap"))
        for i in ("A027", "A031"):
            self.assertEqual(self.r[i]["outcome"], "killed")
        self.assertEqual([i for i, rec in self.r.items() if rec["errors"]], [])

    def test_the_gate_passes_at_its_first_attempt(self):
        """I62-P7 (D7): the harness gate passes at its first attempt: on the original code the harness reproduces I16's
        outputs of all six edges, agrees with the baseline model wherever the model is defined, falsifies no PROVED M0
        law and replays every REFUTED M0 law's witness; C1 and C2 are killed by K1 through L_par_hdr_v0, C3 by K1
        through L_par_hdr_v1, L_rt_go_v1 and L_rt_go_v2 (its round-trip laws now decided by their replay, D1), C4 by
        K2 with partiality witnesses through L_rt_go_v1 and L_rt_go_v2; no control holds a replay disagreement or an
        error of step 'replay'."""
        g = need(GATE)
        self.assertEqual(len(g["attempts"]), 1, [a["checks"] for a in g["attempts"]])
        self.assertIs(g["attempts"][0]["passed"], True)
        for c, law, how in (("C1", "L_par_hdr_v0", "K1"), ("C2", "L_par_hdr_v0", "K1"), ("C3", "L_par_hdr_v1", "K1"),
                            ("C3", "L_rt_go_v1", "K1"), ("C3", "L_rt_go_v2", "K1"), ("C4", "L_rt_go_v1", "K2"),
                            ("C4", "L_rt_go_v2", "K2")):
            rec = need(CONTROLS / f"{c}.json")
            self.assertIn({"law": law, "how": how}, rec["kill"]["by"], c)
            if how == "K2":
                self.assertEqual(rec["laws"][law]["falsifier"]["kind"], "partiality", c)
        for c in ("C1", "C2", "C3", "C4"):
            rec = need(CONTROLS / f"{c}.json")
            self.assertEqual(rec["replay_disagreements"], [], c)
            self.assertEqual([e for e in rec["errors"] if e["step"] == "replay"], [], c)

    def test_the_rates_are_the_first_runs_but_for_the_fixes(self):
        """I62-P8: by operator, family, language and site, stratum A's counts are I61's but every error count is 0 and
        PAR-round-trip kills 56 mutants (I61: 54; A001 and A058 join it, D1); the structural agreement is I61's with
        the 7 former errors filed rule_gap/law_unmoved (abstraction_carried +4, masked +1, projection_carried +2); the
        unpredicted, recomputed-only, masked and proof-lost lists are I61's."""
        s, o = self.s, self.s61
        self.assertEqual({k: dict(v, errors=0) for k, v in o["by_operator"]["A"].items()}, s["by_operator"]["A"])
        fam = json.loads(json.dumps(o["by_family"]))
        fam["A"]["PAR-round-trip"]["killed"] += 2
        self.assertEqual(o["by_family"]["A"]["PAR-round-trip"]["killed"], 54)
        self.assertEqual(s["by_family"], fam)
        self.assertEqual({k: dict(v, errors=0) for k, v in o["by_language"]["A"].items()}, s["by_language"]["A"])
        self.assertEqual(s["per_site"], o["per_site"])
        agree = json.loads(json.dumps(o["structural_agreement"]))
        for cls, n in (("abstraction_carried", 4), ("masked", 1), ("projection_carried", 2)):
            self.assertEqual(agree[cls].pop("error"), n, cls)
            agree[cls]["rule_gap/law_unmoved"] = agree[cls].get("rule_gap/law_unmoved", 0) + n
        self.assertEqual(s["structural_agreement"], agree)
        for k in ("unpredicted", "recomputed_only", "masked_obstructions", "proof_lost_unwitnessed", "k1_only",
                  "plan_literal", "new_law_kills", "k2_model_tied", "detection", "unpredicted_rate", "masked_rate",
                  "dedup", "B_codec_functions", "contradicted", "rate_non_equivalent_reversed"):
            self.assertEqual(s[k], o[k], k)

    def test_no_message_holds_a_timing_a_path_or_a_frame(self):
        """I62-P9 (D6): no record, control record or gate detail holds a duration, an absolute path of the run's
        machine or a Python traceback frame; the determinism sample (TestDeterminism) includes two of I61's error
        mutants."""
        pats = (re.compile(r"(?<![\w.<])\d+(?:\.\d+)?\s?(?:ns|µs|us|ms|s)\b"), re.compile(r"/(?:home|tmp|root|usr)/"),
                re.compile(r'^\s+File "', re.M))
        texts = []
        for p in sorted(RESULTS.rglob("*.json")):
            d = load_json(p)
            for e in d.get("errors") or []:
                texts.append((p.name, e["message"]))
            for law, e in (d.get("laws") or {}).items():
                if isinstance(e.get("error"), str):
                    texts.append((p.name, e["error"]))
            for c in ((d.get("refinement") or {}).get("channels") or []):
                if isinstance(c.get("error"), str):
                    texts.append((p.name, c["error"]))
            for a in d.get("attempts") or []:
                for c in a["checks"].values():
                    texts.append((p.name, c["detail"]))
        for name, t in texts:
            for pat in pats:
                self.assertIsNone(pat.search(t), (name, t[:300]))


# ============================================================================================ the fixes (I62)
class TestFixes(unittest.TestCase):
    """Construction (instrument replaces.defects D1-D6): what each fix is, read from the code and the committed files;
    their effect on the run is TestPredictions'."""

    def test_the_harness_copies_are_the_originals_plus_a_deployment_probe(self):
        """D2: replay/M2/mutation_i62/HolonStepBase.sol is I20's step harness base and
        replay/M2/mutation_i62/HolonTraceReplay.t.sol is I15's trace harness, each with one change: lines added (a
        header note, the probe and its use) around the deployment's call site, compared line by line with indentation
        aside: at most two original lines are not kept in place."""
        for copy, orig in (("replay/M2/mutation_i62/HolonStepBase.sol", "replay/M2/solidity/HolonStepBase.sol"),
                           ("replay/M2/mutation_i62/HolonTraceReplay.t.sol", "replay/M1/solidity/HolonTraceReplay.t.sol")):
            with self.subTest(copy=copy):
                a = [l.strip() for l in (ROOT / orig).read_text().splitlines()]
                b = [l.strip() for l in (ROOT / copy).read_text().splitlines()]
                sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
                removed = [a[i1:i2] for tag, i1, i2, _, _ in sm.get_opcodes() if tag in ("replace", "delete")]
                self.assertLessEqual(sum(len(x) for x in removed), 2, removed)
                added = "\n".join(l for tag, _, _, j1, j2 in sm.get_opcodes() if tag in ("replace", "insert")
                                  for l in b[j1:j2])
                self.assertIn("I62", added)
                self.assertRegex(added, r"snapshotState\(\)")
                self.assertRegex(added, r"revertToState\(")
                self.assertRegex(added, r"try this\.\w+\(")
        step = (ROOT / "replay/M2/mutation_i62/HolonStepBase.sol").read_text()
        self.assertIn('holonLine(string.concat("F ", dec(tid), " ", hx(why)));', step)
        trace = (ROOT / "replay/M2/mutation_i62/HolonTraceReplay.t.sol").read_text()
        self.assertIn('" rev deploy: "', trace)

    def test_the_channel_and_the_trace_replay_run_the_copies(self):
        CH = holon_module("holon.mutate.channels")
        R = holon_module("holon.mutate.replay")
        self.assertEqual(CH.STEP_BASE.as_posix(), "replay/M2/mutation_i62/HolonStepBase.sol")
        self.assertIn("replay/M2/mutation_i62/HolonTraceReplay.t.sol", [p.as_posix() for p in R.TRACE_HARNESSES])
        binding = load_json(ROOT / "replay" / "M2" / "fragments.json")
        self.assertIn("replay/M2/solidity/HolonStepBase.sol", binding["harness"]["files"])

    def test_the_header_document_has_its_ledger_bundle(self):
        """D3: spec/M2/ledger.json registers the header document with one entry per declared assumption, each
        introduced by '*', and no assumption-free group; the rollup document's bundle is unchanged."""
        rel = "spec/M2/facts/morph_header.extracted.json"
        led = load_json(SPEC2 / "ledger.json")
        hb = [b for b in led["bundles"] if b["facts"] == rel]
        self.assertEqual(len(hb), 1)
        b = hb[0]
        self.assertEqual(b["facts_sha256"], sha256((ROOT / rel).read_bytes()))
        doc = load_json(ROOT / rel)
        self.assertEqual([(e["id"], e["text"], e["source"], e["introduced_by"]) for e in b["entries"]],
                         [(a["id"], a["text"], f"{rel}#/assumptions/{k}", ["*"]) for k, a in
                          enumerate(doc["assumptions"])])
        self.assertEqual(b["no_assumption"], [])
        roll = [x for x in led["bundles"] if x["facts"] == "spec/M2/facts/morph_rollup.extracted.json"]
        old = json.loads(git("show", f"{I61_PIPELINE}:spec/M2/ledger.json"))
        self.assertEqual(roll, [x for x in old["bundles"] if x["facts"] == "spec/M2/facts/morph_rollup.extracted.json"])
        self.assertEqual(led["extends"], old["extends"])

    def test_a_layout_document_has_no_coverage_entry(self):
        """D3: holon.records.coverage_field gives null for a law over a document that is not a transitions document,
        and still refuses an unlisted transitions document."""
        Rr = holon_module("holon.records")
        law = {"law_id": "L_x", "milestone": "M2", "facts": "spec/M2/facts/morph_header.extracted.json"}
        self.assertIsNone(Rr.coverage_field(law, ROOT))
        cov = load_json(ROOT / "gen" / "M2" / "coverage.json")
        self.assertNotIn(law["facts"], [d["document"] for d in cov["documents"]])
        roll = dict(law, facts="spec/M2/facts/morph_rollup.extracted.json")
        self.assertEqual(Rr.coverage_field(roll, ROOT)["document"], roll["facts"])
        d = Path(tempfile.mkdtemp(prefix="i62-cov-"))
        try:
            (d / "gen" / "M2").mkdir(parents=True)
            (d / "gen" / "M2" / "coverage.json").write_text(json.dumps({"documents": []}))
            (d / "spec" / "M2" / "facts").mkdir(parents=True)
            shutil.copy(SPEC2 / "facts" / "morph_rollup.extracted.json", d / "spec" / "M2" / "facts")
            with self.assertRaises(ValueError):
                Rr.coverage_field(roll, d)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_messages_are_scrubbed_before_they_are_cut(self):
        """D6: holon.mutate.common.scrub drops traceback frames, replaces the run's paths and durations, and is
        idempotent; the run's cut points scrub first (stage._tail, Unit.error)."""
        Cm = holon_module("holon.mutate.common")
        raw = ("holon run (exit 1): Traceback (most recent call last):\n"
               '  File "/w/x/A027/holon/holon/records.py", line 270, in resolve_bundle\n'
               '    raise LedgerError("no bundle")\n'
               "             ~~~~^^\n"
               "holon.records.LedgerError: no bundle\n"
               "Suite result: FAILED. 0 passed; 1 failed; finished in 1.43ms (894.43µs CPU time)\n"
               "see /w/x/A027/holon/out and /home/me/.holon/tools")
        got = Cm.scrub(raw, {"work": "/w/x", "home": "/home/me"})
        self.assertEqual(got, "holon run (exit 1): Traceback (most recent call last):\n"
                              "holon.records.LedgerError: no bundle\n"
                              "Suite result: FAILED. 0 passed; 1 failed; finished in <t> (<t> CPU time)\n"
                              "see <work>/A027/holon/out and <home>/.holon/tools")
        self.assertEqual(Cm.scrub(got, {"work": "/w/x", "home": "/home/me"}), got)
        S = holon_module("holon.mutate.stage")
        p = subprocess.CompletedProcess([], 1, "x" * 2000 + " took 12.5s", "")
        self.assertTrue(S._tail(p).endswith("took <t>"))

    def test_channel_runs_are_retried_once(self):
        """D5: a channel run that does not complete is run once more, and the second entry is kept."""
        Rn = holon_module("holon.mutate.run")
        calls = []

        def flaky(*a):
            calls.append(a)
            return {"harness": "i20_step", "steps": 0 if len(calls) == 1 else 5, "new_disagreements": [],
                    "corpus_differences": [] if len(calls) > 1 else None,
                    "error": "first attempt failed" if len(calls) == 1 else None}

        self.assertEqual(Rn._channel_retry(flaky, 1)["steps"], 5)
        self.assertEqual(len(calls), 2)
        calls.clear()

        def broken(*a):
            calls.append(a)
            return {"harness": "i16_edge", "steps": 0, "new_disagreements": [], "corpus_differences": None,
                    "error": f"attempt {len(calls)}"}, []

        res, ids_ = Rn._channel_retry(broken, 1)
        self.assertEqual((res["error"], len(calls)), ("attempt 2", 2))

    def test_the_replay_keeps_none_as_a_value(self):
        """D1, in the evaluator: dec_go's none against some(...) is false, a field of none or a role called on none is
        no execution, and a call not yet run still stops the evaluation."""
        R = holon_module("holon.mutate.replay")
        claim = {"eq": [{"call": "dec_go", "args": [{"var": "b"}]}, {"some": {"call": "view", "args": [{"var": "h"}]}}]}
        ev = R._Eval(claim["eq"], {"b": "0x00", "h": {"version": "0x00"}})
        ev.results = {("eq", 0): {"kind": "value", "value": None}, ("eq", 1, "some"): {"kind": "value", "value": ["0x00"]}}
        self.assertIs(ev.verdict(), False)
        ev.results[("eq", 0)] = {"kind": "value", "value": ["0x00"]}
        self.assertIs(ev.verdict(), True)
        nested = [{"call": "enc_go_v0", "args": [{"call": "dec_go", "args": [{"var": "b"}]}]}, {"var": "b"}]
        ev = R._Eval(nested, {"b": "0x00"})
        ev.results = {("eq", 0, "args", 0): {"kind": "value", "value": None}}
        self.assertIsNone(ev.verdict())
        ev = R._Eval(claim["eq"], {"b": "0x00", "h": {"version": "0x00"}})
        with self.assertRaises(Exception):
            ev.verdict()


# ============================================================================================ I61's first run
class TestI61FirstRun(unittest.TestCase):
    """Construction (green from the prereg on): I61's run stays as it was written and is reported as the first run.
    Its key stays in spec/M2/predictions.json unchanged and is scored on its own records; its records, summary, gate
    and report are never edited after this prereg; its tests read I61's files through HOLON_MUTATE_KEY=I61 (one
    spec/M2/amendments.jsonl line for its run_holon, one for its metrics test, which now accepts the superseding
    summary); nothing is skipped."""

    I61_TEST = "tests_m2/test_mutation_adequacy_i61.py"

    def test_the_i61_key_and_its_outputs_stay(self):
        now = predictions("I61")
        then = json.loads(git("show", f"{I61_PREREG}:spec/M2/predictions.json"))["iterations"]["I61"]
        self.assertEqual(canon(now), canon(then))
        c_pre = prereg_commit()
        for p in ("results/M2/mutation_i61", "gen/M2/mutation_i61", "replay/M2/mutation_i61",
                  "spec/M2/equivalent_mutants_i61.json", "docs/iterations/I61_catalog_review.json",
                  "docs/iterations/I61_equivalence_panel.json", "docs/iterations/I61.md",
                  "spec/M2/lib/mutation_catalog_i61.json", "spec/M2/lib/mutation_diff_sheet_i61.md"):
            with self.subTest(path=p):
                self.assertEqual(git("diff", "--name-only", c_pre, "HEAD", "--", p), "")
        inst = instrument()
        fr = inst["replaces"]["first_run"]
        for k in ("summary", "gate", "report"):
            self.assertEqual(sha256((ROOT / fr[k]["path"]).read_bytes()), fr[k]["sha256"], k)
        self.assertEqual(fr["pipeline_commit"], I61_PIPELINE)
        self.assertEqual(load_json(I61_RESULTS / "summary.json")["pipeline_commit"], I61_PIPELINE)

    def test_i61s_tests_read_i61s_files_by_amendment(self):
        sys.path.insert(0, str(ROOT))
        from holon.audit import prereg as P
        old = P.analyse(git("show", f"{I61_PREREG}:{self.I61_TEST}"), True)
        new = P.analyse((ROOT / self.I61_TEST).read_text(), True)
        self.assertEqual(sorted(k for k in old.fps if k not in new.fps), [])
        changed = sorted(k for k in old.fps if old.fps[k] != new.fps[k])
        self.assertEqual(changed, ["TestResults.test_metrics_report_mutation_adequacy", "run_holon"])
        lines = [json.loads(l) for l in (SPEC2 / "amendments.jsonl").read_text().splitlines() if l.strip()]
        amended = sorted(l["test"].split("::", 1)[1] for l in lines if l["iteration"] == "I61"
                         and l["test"].startswith(self.I61_TEST + "::"))
        self.assertEqual(amended, changed)
        src = (ROOT / self.I61_TEST).read_text()
        self.assertIn('"HOLON_MUTATE_KEY": "I61"', src)
        # nothing is skipped: no skip decorator, no skipTest call, no SkipTest raised (read from the syntax tree: the
        # file holds I60's anti-skip pattern as a string)
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    self.assertNotIn("skip", ast.unparse(dec).lower(), node.name)
            if isinstance(node, ast.Call):
                self.assertFalse(ast.unparse(node.func).endswith(("skipTest", "SkipTest")), ast.unparse(node))
            if isinstance(node, ast.Raise) and node.exc is not None:
                self.assertNotIn("SkipTest", ast.unparse(node.exc))

    def test_the_package_serves_both_keys(self):
        """holon/mutate reads HOLON_MUTATE_KEY: I62 (the default) writes only I62's paths, I61 reads only I61's."""
        code = ("import json; from holon.mutate import common as C; print(json.dumps([C.KEY, str(C.INSTRUMENT), "
                "str(C.RESULTS), str(C.GEN), str(C.REVIEW), str(C.ADJUDICATION), str(C.SHEET)]))")
        got = {}
        for key in ("", "I61", "I62"):
            env = {k: v for k, v in os.environ.items() if k != "HOLON_MUTATE_KEY"}
            if key:
                env["HOLON_MUTATE_KEY"] = key
            p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr[-500:])
            got[key] = json.loads(p.stdout)
        sheet = "spec/M2/lib/mutation_diff_sheet_i61.md"
        self.assertEqual(got[""], got["I62"])
        self.assertEqual(got["I62"], ["I62", "spec/M2/lib/mutation_catalog_i62.json", "results/M2/mutation_i62",
                                      "gen/M2/mutation_i62", "docs/iterations/I62_catalog_review.json",
                                      "spec/M2/equivalent_mutants_i62.json", sheet])
        self.assertEqual(got["I61"], ["I61", "spec/M2/lib/mutation_catalog_i61.json", "results/M2/mutation_i61",
                                      "gen/M2/mutation_i61", "docs/iterations/I61_catalog_review.json",
                                      "spec/M2/equivalent_mutants_i61.json", sheet])
        env = dict(os.environ, HOLON_MUTATE_KEY="I60")
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)


if __name__ == "__main__":
    unittest.main()
