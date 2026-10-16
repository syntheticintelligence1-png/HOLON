"""I61: A1 mutation adequacy on real code, second replacement catalog (whitepaper §9.5 auditor A1, §9.6, §12.1 L1
"Sensitivity", §13 metric "mutation adequacy", §15.2 M2 exit (b); BUILD_PLAN §3 row I61 and §4 I22, whose kill
criterion, threshold and exit I61 inherits). This docstring is the contract.

Plant misimplementations in the real Solidity and Go of the pinned Morph checkout, re-extract them with the M2
frontends, decide the laws on what was extracted, replay every witness on the real code, and measure the kill rate of
stratum A against the threshold the human fixed in advance (0.80 of non-equivalent mutants, docs/HUMAN_ANSWERS.md Q6).
The threshold never moves.

Why a second replacement. I60's catalog (prereg 7b211e0) was not signed off before any mutant ran
(docs/iterations/I60.md, docs/iterations/I60_catalog_review.json): the soundness lens found that the enc_sol replay
harness, through which every K1 witness and every K2 (c) falsification of a PROVED M0 law passes, was specified so
that its inputs did not overlap the refuter's candidates, leaving the outcome to an unpreregistered build choice; the
fairness lens signed off with advisories. I60's own contract: "If either lens finds a blocking problem, nothing runs
and a replacement is preregistered under a new key." I61 is that key. It keeps I60's 242 mutants byte for byte
(mutants_sha256 equal) and every value computed from the pinned checkout, and changes what the review found
(instrument replaces.findings): the replay harness is pinned to I16's store-level binding (instrument replay), a
harness gate runs before any mutant (instrument harness_gate), and the kill criterion, survivor classes, duplicates,
contradictions, reporting and adjudication are corrected; every remaining limitation is stated (instrument
limitations). I60's predictions stay in spec/M2/predictions.json, unscored; its run tests are retired through
spec/M2/amendments.jsonl (TestI60Retirement), never skipped.

Dependencies and order (instrument preconditions). Catalog mutants run only after (1) this prereg, (2) a signed-off
two-lens catalog review committed at docs/iterations/I61_catalog_review.json, (3) the delegated blind equivalence
panel's adjudication committed alone at spec/M2/equivalent_mutants_i61.json, (4) a passed harness gate,
results/M2/mutation_i61/gate.json, first committed before any catalog mutant's record, (5) a baseline that reproduces
the pinned statuses, documents and projection, and (6) I21's exit (zero open high-severity findings): the tree of the
records' pipeline_commit holds audit/rounds/M2/round2.json and an audit/M2_findings.jsonl with no line of severity
"high" and status "open". The gate needs neither the review nor the adjudication; each step descends from this prereg. It uses I17, I19 (with A19), I18 and I20 as merged at the instrument's pins.holon_commit,
unchanged.

Frozen inputs (this prereg commit; the instrument's sha256 is pinned below as INSTRUMENT_SHA256)
  spec/M2/lib/mutation_catalog_i61.json  the instrument. Its fields hold the rules this contract names: replaces (I60,
        each of its review's findings and what I61 does with it), limitations, preconditions, pins, computation,
        threshold (with its consequence), seed, target, strata, in_scope, stillborn, operators, counts,
        structural_counts, roles, law_sets, predicted (with recomputed), baseline, structural (with premise_limited),
        kill_criterion, replay (m0, hits, semantics, partiality, model_tied, both), harness_gate (checks, controls),
        projection, equivalence, duplicates, tce, channels, survivor_classes, reporting, adjudication, mutants_sha256,
        diff_sheet and the 242 mutants (A001-A192 stratum A, B001-B050 stratum B), each {id, stratum, operator,
        variant, file, root, offset, length, line, col, function, original, replacement, mutant_sha256, tce, edges,
        actions, predicted: {M0, M1x, M2}, structural: {class, M0, M0_reading_laws, M1x, M2}}, I60's list unchanged.
  spec/M2/lib/mutation_diff_sheet_i61.md  render_sheet() below applied to the instrument and the pinned files: what the
        panel adjudicates. No prediction, no structural class, no outcome. Every mutant section is I60's.
  The pinned checkout (config/holon.json replay.morph at target.commit) and the OpenZeppelin units (replay.sol_deps
  /node_modules), read only. Every mutant lives in a scratch copy.

Delegated steps, before any catalog mutant runs (instrument "adjudication"; docs/HUMAN_ANSWERS.md delegated answers)
  docs/iterations/I61_catalog_review.json  two fresh agents, a fairness lens and a soundness lens, each read the
        instrument in full and recompute the sites: {"what", "who", "delegation", "instrument": {"path", "sha256"},
        "verdict", "reviews": {"fairness" | "soundness": {"sign_off", "blocking", "advisory", "checked",
        "forbidden_files_touched"}}}. Signed off iff both sign off with no blocking finding; if not, nothing runs and a
        replacement is preregistered under a new key. Its first commit descends from this prereg commit.
  spec/M2/equivalent_mutants_i61.json  the blind panel (two judges per file group plus a refuter; equivalent iff the
        refuter confirms; a tce mutant is equivalent): {"adjudication_version": "holon-equivalent-mutants/0.2",
        "instrument": {"path", "sha256"}, "mutants_sha256", "diff_sheet_sha256", "review": {"path", "sha256"},
        "adjudicator": "delegated_panel", "delegation": {"decision", "panel", "procedure", "blindness_audit"},
        "verdicts": {"<id>": {"equivalent": bool, "reason": str, "duplicate_of": null | "<id>",
                              "panel": {"judges": [bool, bool], "refuter_confirmed": bool | null}}}}
        Every mutant id exactly once; a reason is non-empty when equivalent; a non-tce mutant is equivalent only when
        some judge called it equivalent and the refuter confirmed it; duplicate_of names the lowest id of the
        mutant's duplicate candidate group (instrument duplicates.candidates) or is null. Committed alone, its first
        commit descends from the review's and is a proper ancestor of the first commit of any catalog mutant's record.
  docs/iterations/I61_equivalence_panel.json  (optional) the panel's full record (each judge's and the refuter's
        output, the blindness audit), first committed after the adjudication, never in its commit.
  Neither step's agents read the files instrument adjudication.forbidden names (the I60 and I61 forecasts and
  outcomes, and docs/iterations/I60_catalog_review.json, which records I60's headline forecast in two disclosures;
  the reviewers get I60's findings from replaces.findings or a redacted copy, adjudication.redacted_i60_review); each
  lists the forbidden files it touched. The instrument's own statements that border on outcomes are stated
  (adjudication.known_exposure).

The harness gate (instrument harness_gate), after the build and before any catalog mutant
  `python -m holon mutate gate` runs its four checks on the original code and the four planted controls and writes
  results/M2/mutation_i61/gate.json: {"instrument": {"path", "sha256"}, "pipeline_commit", "attempts":
  [{"pipeline_commit", "checks": {"i16" | "model" | "null" | "controls": {"passed": bool, "detail": str}}, "passed":
  bool, "fix": null | str}], "passed": bool}; the top-level pipeline_commit is the last attempt's. Every attempt is
  kept; a fix of holon/mutate after a failed attempt names it ("fix") and is reported (no catalog mutant has run by
  then); a failure caused by a tool the rules keep unchanged stops the run for the human's decision. The controls'
  records are results/M2/mutation_i61/controls/<C1..C4>.json, in the record format below (id "C1".."C4", stratum,
  operator and structural null), and each must be killed through every law its instrument entry's "expected" names,
  by the "how" it names (K1, or K2 with the named falsifier kind): C1 and C2 in the codec library and the Go encoder,
  C3 inside the copied build block of the entry function, C4 at the copied require through a partiality witness. The
  gate needs neither the review nor the adjudication.

Deliverables
  holon/mutate/ (operators.py, project.py, replay.py, run.py; helpers may be added), harness sources under
  replay/M2/mutation_i61/, the dispatch `python -m holon mutate ...` in holon/__main__.py. holon/mutate names no file,
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
        False iff a step panics at the law's site (its basis span); a reverted step is a no-op, never a violation.
  CLI (exit 0 ok; 1 --check found a difference; 2 refused, nothing written)
    python -m holon mutate list                         the catalog recomputed from the pinned checkout, as JSON
    python -m holon mutate sheet [--out PATH] [--check]  the diff sheet (default spec/M2/lib/mutation_diff_sheet_i61.md)
    python -m holon mutate project [--documents DIR] [--out PATH] [--check]
                                                         the projected header document (default
                                                         gen/M2/mutation_i61/header.projected.json, from spec/M2/facts)
    python -m holon mutate replay --i16 [--tree DIR]     every role of I16's binding (replay/M2/implementations.json)
                                                         run through holon.mutate.replay on I16's per-edge corpus
                                                         (holon.corpus, I16's seeds): prints {edge: {"compared": n,
                                                         "outputs_sha256": "<hex>"}} with outputs digested as I16's
                                                         records digest the real side
    python -m holon mutate gate [--check]                the harness gate (above)
    python -m holon mutate run --milestone M2 [--only A001,...] [--control C1,...] [--baseline-only] [--work DIR]
                               [--jobs N] [--no-carry] [--dry-run] [--check]
    python -m holon mutate rate [--check]                results/M2/mutation_i61/summary.json from the records
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
facts/morph_header.json compiles to the same bytes as before; gen/M2/mutation_i61/header.projected.json is the
projection of the committed documents and `holon mutate project --check` reproduces it.

Outputs (canonical JSON: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; no timestamps, scratch paths or process
ids; timings stay in scratch)
  results/M2/mutation_i61/baseline.json, results/M2/mutation_i61/<id>.json, one per mutant, and
  results/M2/mutation_i61/controls/<C1|C2>.json:
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
  results/M2/mutation_i61/summary.json:
    {"version": "holon-mutation/0.3", "iteration": "I61", "milestone": "M2", "pipeline_commit",
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
  results/M2/mutation_i61/gate.json (the harness gate, above).
  gen/M2/mutation_i61/header.projected.json (Projection).
  results/M2/metrics.json "mutation_adequacy" (whitepaper §13; §12.1: certificates report Sensitivity), read by
    holon/metrics.py from the summary: {"source": "results/M2/mutation_i61/summary.json", "threshold": 0.8,
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
  - Survivors are filed mechanically (instrument survivor_classes), never explained away; each record keeps its
    instrument structural class beside the class it received.
  - No skips. The catalog never changes after the sign-off, the threshold never moves, predictions are never tuned.
"""
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
INSTRUMENT = SPEC2 / "lib" / "mutation_catalog_i61.json"
INSTRUMENT_SHA256 = "b9f04fc2f7e39b47e8d1d6b700d46db12f073b1c10d84bc6ca5992822afa4cf6"
SHEET = SPEC2 / "lib" / "mutation_diff_sheet_i61.md"
ADJ = SPEC2 / "equivalent_mutants_i61.json"
REVIEW = ROOT / "docs" / "iterations" / "I61_catalog_review.json"
RESULTS = ROOT / "results" / "M2" / "mutation_i61"
SUMMARY = RESULTS / "summary.json"
GATE = RESULTS / "gate.json"
CONTROLS = RESULTS / "controls"
PROJECTED = ROOT / "gen" / "M2" / "mutation_i61" / "header.projected.json"
PIN = "e20648e05052ad37db3f874c66b7a71af1381752"
I60_PREREG = "7b211e081ec7a0214c4034c161e6cb06fd572f53"
I60_INSTRUMENT = SPEC2 / "lib" / "mutation_catalog_i60.json"
I60_SHEET = SPEC2 / "lib" / "mutation_diff_sheet_i60.md"
STATUSES = ("PROVED", "REFUTED", "UNKNOWN")
LAYOUT_OPS = ("mstore_offset", "shl_width")
CMP_OPS = ("cmp_boundary", "cmp_boundary_mirror")
EDGE_ROLE = {"enc_sol": "enc_sol", "ok_sol": "load_sol"}
ROLLUP = "contracts/contracts/l1/rollup/Rollup.sol"
PREMISE_LIMITED = ["A148", "A162", "A165", "A166", "A167", "A168"]

# ---------------------------------------------------------------------------------------------- the forecast (I61-P*)
# I60's forecast (made before any run; consistent with the working reading of its harness, I16's store-level binding,
# which I61 preregisters), re-derived under I61's rules: only A081 changes, killed by K2 through a partiality witness
# (replay.partiality) where I60 forecast proof_lost_unwitnessed.
M0_BASELINE = {"L_par_hdr_v0": "PROVED", "L_par_hdr_v1": "PROVED", "L_rt_go_v0": "PROVED", "L_rt_go_v1": "PROVED",
               "L_rt_go_v2": "PROVED", "L_par_hdr_v2": "REFUTED", "L_par_hdr_ssvh": "REFUTED", "L_dom_hdr": "REFUTED"}
ALL5 = ["L_par_hdr_v0", "L_par_hdr_v1", "L_rt_go_v0", "L_rt_go_v1", "L_rt_go_v2"]
V1_3 = ["L_par_hdr_v1", "L_rt_go_v1", "L_rt_go_v2"]
RT3 = ["L_rt_go_v0", "L_rt_go_v1", "L_rt_go_v2"]


def ids(prefix: str, a: int, b: int) -> list:
    return [f"{prefix}{i:03d}" for i in range(a, b + 1)]


# mutant -> (how: "K1" if some killing law is K1, else "K2"; the killing laws)
KILLS = {}
for _i in ("A001", "A003", "A004", "A005", "A006", "A008"):
    KILLS[_i] = ("K1", ALL5)
for _i in ["A002", "A007"] + ids("A", 9, 17) + ["A019", "A020"]:
    KILLS[_i] = ("K2", ALL5)
KILLS["A021"] = ("K1", V1_3)
KILLS["A022"] = ("K2", V1_3)
for _i in ids("A", 27, 32):
    KILLS[_i] = ("K1", ALL5)
for _i in ("A033", "A034"):
    KILLS[_i] = ("K1", V1_3)
KILLS["A058"] = ("K1", ["L_par_hdr_v1", "L_rt_go_v1"])
KILLS["A059"] = ("K2", ["L_par_hdr_v1", "L_rt_go_v1"])
KILLS["A081"] = ("K2", ["L_rt_go_v2"])
for _i in ids("A", 123, 128):
    KILLS[_i] = ("K1", ["L_par_hdr_v0"])
for _i in ids("A", 129, 135):
    KILLS[_i] = ("K1", ["L_par_hdr_v1"])
KILLS["A136"] = ("K2", ["L_par_hdr_v1"])
for _i in ids("A", 137, 150):
    if _i != "A148":
        KILLS[_i] = ("K1", ["L_par_hdr_v0"])
for _i in ids("A", 151, 164):
    if _i != "A162":
        KILLS[_i] = ("K1", ["L_par_hdr_v1"])
_GETTER_LAWS = {"BatchIndex": RT3, "L1MessagePopped": RT3, "TotalL1MessagePopped": RT3, "DataHash": RT3,
                "BlobVersionedHash": ["L_rt_go_v0", "L_rt_go_v1"], "BlobHashesHash": ["L_rt_go_v2"],
                "PrevStateRoot": RT3, "PostStateRoot": RT3, "WithdrawalRoot": RT3, "SequencerSetVerifyHash": RT3,
                "ParentBatchHash": RT3, "LastBlockNumber": ["L_rt_go_v1", "L_rt_go_v2"]}
_GETTERS = ["BatchIndex", "L1MessagePopped", "TotalL1MessagePopped", "DataHash", "BlobVersionedHash", "BlobHashesHash",
            "PrevStateRoot", "PostStateRoot", "WithdrawalRoot", "SequencerSetVerifyHash", "ParentBatchHash",
            "LastBlockNumber"]
for _k, _g in enumerate(_GETTERS):
    for _d in (0, 1):
        KILLS[f"A{169 + 2 * _k + _d:03d}"] = ("K1", _GETTER_LAWS[_g])
PARTIALITY = {"A081": ["L_rt_go_v2"]}
PROOF_LOST = {"A018": ALL5}
MASKED = {i: ["L_par_hdr_ssvh"] for i in ["A001", "A003", "A004", "A005", "A006", "A008", "A021"] + ids("A", 27, 34)
          + ["A058"] + ids("A", 129, 135) + [x for x in ids("A", 151, 164) if x != "A162"]}
MASKED.update({i: ["L_dom_hdr"] for i in ("A076", "A165", "A166", "A167")})
TCE = ["A110", "A111", "A112", "A113", "A121", "A122"]
CORPUS_SWAPS = ["A045", "A047", "A048", "A049", "A050", "A051", "A052"]
A_BY_OPERATOR = {"mstore_offset": (22, 21), "shl_width": (12, 8), "drop_delete": (7, 0), "swap_cursor": (12, 0),
                 "cmp_boundary": (23, 2), "cmp_boundary_mirror": (15, 1), "mload_offset": (22, 0), "shr_width": (9, 0),
                 "putuint64_offset": (14, 14), "copy_offset": (28, 26), "drop_len_check": (4, 0),
                 "go_slice_offset": (24, 24)}
B_DOC_CHANGED = ids("B", 1, 8) + ids("B", 11, 16) + ids("B", 23, 50)


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
    """The first commit whose spec/M2/predictions.json holds key I61."""
    for c in git("log", "--reverse", "--format=%H", "--", "spec/M2/predictions.json").splitlines():
        p = subprocess.run(["git", "-C", str(ROOT), "show", f"{c}:spec/M2/predictions.json"], capture_output=True)
        if p.returncode == 0 and "I61" in json.loads(p.stdout).get("iterations", {}):
            return c
    raise AssertionError("no commit introduces key I61")


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
    # amended (spec/M2/amendments.jsonl, I61, superseded_by_rerun): holon/mutate serves I62 by default; I61's tests
    # read I61's files
    return subprocess.run([sys.executable, "-m", "holon", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=timeout, env={**os.environ, "HOLON_MUTATE_KEY": "I61"})


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
    d = Path(tempfile.mkdtemp(prefix="i61-repo-"))
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
    d = Path(tempfile.mkdtemp(prefix="i61-go-sites-"))
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
        self.assertEqual((inst["iteration"], inst["milestone"]), ("I61", "M2"))
        self.assertEqual(inst["mutants_sha256"], sha256(canon(inst["mutants"]).encode()))
        self.assertEqual(inst["diff_sheet"]["sha256"], sha256(SHEET.read_bytes()))
        rep = inst["replaces"]
        self.assertEqual(rep["key"], "I60")
        for k in ("instrument", "rejection"):
            self.assertEqual(sha256((ROOT / rep[k]["path"]).read_bytes()), rep[k]["sha256"], k)
        review = load_json(ROOT / rep["rejection"]["path"])
        self.assertIs(review["reviews"]["soundness"]["sign_off"], False)
        self.assertTrue(review["reviews"]["soundness"]["blocking"])
        # every finding of the I60 review is answered (21: soundness 1 blocking and 10 advisory, fairness 10
        # advisory), each blocking one fixed
        n = {lens: (len(r["blocking"]), len(r["advisory"])) for lens, r in review["reviews"].items()}
        self.assertEqual(n, {"soundness": (1, 10), "fairness": (0, 10)})
        labels = set()
        for k, v in rep["findings"].items():
            self.assertTrue(v.startswith(("Fixed", "Stated")), k)
            labels |= set(re.findall(r"\b([SF]-[AB][0-9]+)\b", k.split(":")[0]))
        self.assertEqual(labels, {"S-B1"} | {f"S-A{i}" for i in range(1, 11)} | {f"F-A{i}" for i in range(1, 11)})
        blocking = [k for k in rep["findings"] if "blocking" in k.split(":")[0]]
        self.assertEqual(len(blocking), 1)
        self.assertTrue(rep["findings"][blocking[0]].startswith("Fixed"))

    def test_the_mutants_and_their_diffs_are_i60s(self):
        """I61 keeps I60's 242 mutants byte for byte (mutants_sha256 equal) and every value computed from the pinned
        checkout; every mutant section of the I61 sheet is I60's."""
        inst, old = instrument(), load_json(I60_INSTRUMENT)
        self.assertEqual(inst["mutants"], old["mutants"])
        self.assertEqual(inst["mutants_sha256"], old["mutants_sha256"])
        for k in ("target", "in_scope", "stillborn", "operators", "operator_order", "variant_order", "cursor_pairs",
                  "counts", "structural_counts", "roles", "baseline", "tce", "channels"):
            self.assertEqual(inst[k], old[k], k)
        cut = lambda t: t[t.index("\n## A001 "):]
        self.assertEqual(cut(SHEET.read_text()), cut(I60_SHEET.read_text()))

    def test_threshold_seed_strata_and_counts(self):
        inst = instrument()
        self.assertEqual((inst["threshold"]["kill_rate_non_equivalent"], inst["threshold"]["stratum"]), (0.8, "A"))
        t = predictions("I61")["thresholds"]
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
        """I61-R2: holon.mutate.operators finds exactly the 242 mutants, keys, values and order (stillborn excluded)."""
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
               "review": {"path": "docs/iterations/I61_catalog_review.json", "sha256": None},
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
            names = ("I61_catalog_review.json", "equivalent_mutants_i61.json", "gate.json", "baseline.json",
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
    d = Path(tempfile.mkdtemp(prefix="i61-tree-"))
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
        self.assertEqual(g["instrument"], {"path": "spec/M2/lib/mutation_catalog_i61.json", "sha256": INSTRUMENT_SHA256})
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", g["pipeline_commit"]) and is_ancestor(g["pipeline_commit"], "HEAD"))
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

    def test_the_gate_came_before_any_catalog_record(self):
        c_gate = first_add("results/M2/mutation_i61/gate.json")
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
    """Construction (MAJOR-1 of the I61 prereg review): K2 (b) counts a rejection only over a generated model that
    checks alone, because the pinned Bend prints 'SOME PROOFS FAIL' for a parse or type error of a generated file too."""

    def test_a_model_that_does_not_check_alone_is_told_apart(self):
        Rn = holon_module("holon.mutate.run")
        G = holon_module("holon.gen.model")
        facts = load_json(ROOT / "facts" / "morph_header.json")
        text = G.generate(facts, sha256((ROOT / "facts" / "morph_header.json").read_bytes()))
        d = Path(tempfile.mkdtemp(prefix="i61-model-"))
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
        """I61-R4: on the committed documents the projection equals the frozen header facts where I17 and I18 compared
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
        """I61-R6: both lenses, fresh agents, delegated, signed off with no blocking finding, on this instrument."""
        r = need(REVIEW)
        self.assertEqual(r["instrument"], {"path": "spec/M2/lib/mutation_catalog_i61.json", "sha256": INSTRUMENT_SHA256})
        self.assertTrue(isinstance(r["delegation"], str) and r["delegation"].strip())
        self.assertEqual(sorted(r["reviews"]), ["fairness", "soundness"])
        for lens, v in r["reviews"].items():
            with self.subTest(lens=lens):
                self.assertIs(v["sign_off"], True)
                self.assertEqual(v["blocking"], [])
                self.assertIsInstance(v["advisory"], list)
                self.assertTrue(isinstance(v["checked"], str) and v["checked"].strip())
                self.assertIsInstance(v["forbidden_files_touched"], list)

    def test_every_mutant_is_adjudicated_once_by_the_delegated_panel(self):
        inst = instrument()
        a = need(ADJ)
        self.assertEqual(a["adjudication_version"], "holon-equivalent-mutants/0.2")
        self.assertEqual(a["instrument"], {"path": "spec/M2/lib/mutation_catalog_i61.json", "sha256": INSTRUMENT_SHA256})
        self.assertEqual((a["mutants_sha256"], a["diff_sheet_sha256"]),
                         (inst["mutants_sha256"], inst["diff_sheet"]["sha256"]))
        self.assertEqual(a["review"], {"path": "docs/iterations/I61_catalog_review.json", "sha256": sha256(REVIEW.read_bytes())})
        self.assertEqual(a["adjudicator"], "delegated_panel")
        for k in ("decision", "panel", "procedure", "blindness_audit"):
            self.assertTrue(isinstance(a["delegation"][k], str) and a["delegation"][k].strip(), k)
        self.assertEqual(sorted(a["verdicts"]), sorted(m["id"] for m in inst["mutants"]))
        lowest = {i: g[0] for g in inst["duplicates"]["candidates"] for i in g}
        for m in inst["mutants"]:
            v = a["verdicts"][m["id"]]
            with self.subTest(mutant=m["id"]):
                self.assertIsInstance(v["equivalent"], bool)
                if v["equivalent"]:
                    self.assertTrue(v["reason"].strip())
                    self.assertTrue(m["tce"] or (v["panel"]["refuter_confirmed"] is True and any(v["panel"]["judges"])))
                else:
                    self.assertIsNot(v["panel"]["refuter_confirmed"], True)
                if m["tce"]:
                    self.assertIs(v["equivalent"], True)
                self.assertIn(v["duplicate_of"], (None, lowest.get(m["id"])))
                self.assertNotEqual(v["duplicate_of"], m["id"])
                self.assertEqual(len(v["panel"]["judges"]), 2)

    def test_the_review_and_the_adjudication_came_in_order(self):
        """prereg -> review -> adjudication (committed alone) -> catalog results; the gate descends from the prereg and
        precedes every catalog record (TestHarnessGate); the run started after the adjudication."""
        c_pre = prereg_commit()
        c_rev = first_add("docs/iterations/I61_catalog_review.json")
        c_adj = first_add("spec/M2/equivalent_mutants_i61.json")
        c_res = first_add("results/M2/mutation_i61/summary.json")
        self.assertTrue(is_ancestor(c_pre, c_rev) and c_pre != c_rev)
        self.assertTrue(is_ancestor(c_rev, c_adj) and c_rev != c_adj)
        self.assertTrue(is_ancestor(c_adj, c_res) and c_adj != c_res)
        self.assertEqual(git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", c_adj).splitlines(),
                         ["spec/M2/equivalent_mutants_i61.json"])
        for m in instrument()["mutants"]:
            p = RESULTS / f"{m['id']}.json"
            self.assertTrue(is_ancestor(c_adj, first_add(p.relative_to(ROOT).as_posix())), p.name)
        self.assertTrue(is_ancestor(c_adj, need(SUMMARY)["pipeline_commit"]))
        panel = ROOT / "docs" / "iterations" / "I61_equivalence_panel.json"
        if panel.is_file():
            c_pan = first_add("docs/iterations/I61_equivalence_panel.json")
            self.assertTrue(is_ancestor(c_adj, c_pan) and c_adj != c_pan)

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
        self.assertEqual((s["version"], s["iteration"], s["milestone"]), ("holon-mutation/0.3", "I61", "M2"))
        self.assertEqual(s["instrument"], {"path": "spec/M2/lib/mutation_catalog_i61.json", "sha256": INSTRUMENT_SHA256})
        self.assertEqual(s["mutants_sha256"], self.inst["mutants_sha256"])
        self.assertEqual(s["review"], {"path": "docs/iterations/I61_catalog_review.json", "sha256": sha256(REVIEW.read_bytes())})
        self.assertEqual(s["adjudication"], {"path": "spec/M2/equivalent_mutants_i61.json", "sha256": sha256(ADJ.read_bytes())})
        self.assertEqual(s["gate"], {"path": "results/M2/mutation_i61/gate.json", "sha256": sha256(GATE.read_bytes())})
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
                        self.assertGreaterEqual(r["steps"], 2432)
                        self.assertIsInstance(r["corpus_differences"], list)
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
        """I61-R9: I22-R6's metric name and shape, from stratum A (I23 reads it); it leaves not_applicable. Amended
        (spec/M2/amendments.jsonl, I61, superseded_by_rerun): once I62's summary exists it is the metric's source."""
        m = need(ROOT / "results" / "M2" / "metrics.json")
        rel = "results/M2/mutation_i61/summary.json"
        if (ROOT / "results" / "M2" / "mutation_i62" / "summary.json").is_file():
            rel = "results/M2/mutation_i62/summary.json"
        a = load_json(ROOT / rel)["strata"]["A"]
        self.assertEqual(m["mutation_adequacy"], {"source": rel, "threshold": 0.8,
                                                  "rate_all": a["rate_all"],
                                                  "rate_non_equivalent": a["rate_non_equivalent"],
                                                  "meets_threshold": a["meets_threshold"]})
        self.assertNotIn("mutation_adequacy", m.get("not_applicable") or {})

    def test_m2_exit_b_the_rate_meets_the_threshold(self):
        """BUILD_PLAN I22 Exit and §15.2 M2 exit (b): stratum A's rate_non_equivalent >= 0.80 (Q6). The drafter
        forecasts that this fails (I61-P2; instrument threshold.consequence); it stays, unchanged, as the exit check."""
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
        modifier, a Go encoder, a Go check, a Go getter, a stratum-B file) rerun with --no-carry at the records'
        pipeline_commit and reproduce their records byte for byte, each law's "decided" field aside."""
        need(SUMMARY)
        p = run_holon(["mutate", "run", "--milestone", "M2", "--only", "A001,A035,A077,A123,A165,A169,B001", "--check"],
                      timeout=7200)
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])


# ============================================================================================ predictions
class TestPredictions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inst = instrument()
        cls.ms = by_id(cls.inst)
        cls.base = need(RESULTS / "baseline.json")
        cls.r = records()
        cls.s = need(SUMMARY)

    def _killed(self, i, how, laws):
        rec = self.r[i]
        self.assertEqual(rec["outcome"], "killed", (i, rec["kill"]))
        self.assertEqual(sorted(x["law"] for x in rec["kill"]["by"]), sorted(laws), i)
        self.assertEqual(any(x["how"] == "K1" for x in rec["kill"]["by"]), how == "K1", (i, rec["kill"]))

    def _survived(self, i):
        self.assertEqual(self.r[i]["outcome"], "survived", (i, self.r[i]["kill"]))

    def test_the_baseline_reproduces_every_committed_status(self):
        """I61-P1: the null mutant, re-extracted from scratch and projected, decides M0 as results/M0 (5 PROVED, 3
        REFUTED), M1x as results/M2/differential.json 'extracted' (7 PROVED, 7 REFUTED, L_tag_BVH UNKNOWN) and M2 as
        results/M2 (6 PROVED, 4 UNKNOWN, 2 REFUTED), and its documents and projection are the committed ones."""
        st = {k: e["mutant"] for k, e in self.base["laws"].items()}
        self.assertEqual({k: v for k, v in st.items() if self.base["laws"][k]["set"] == "M0"}, M0_BASELINE)
        for s_, want in (("M1x", {"PROVED": 7, "REFUTED": 7, "UNKNOWN": 1}), ("M2", {"PROVED": 6, "UNKNOWN": 4,
                                                                                    "REFUTED": 2})):
            self.assertEqual(dict(Counter(v for k, v in st.items() if self.base["laws"][k]["set"] == s_)), want)
        self.assertEqual(self.base["extraction"]["status"], "ok")
        self.assertIs(self.base["projection"]["error"], None)

    def test_stratum_a_totals_and_exit_b(self):
        """I61-P2: 96 of the 192 stratum-A mutants are killed (rate_all 96/192 = 0.5), none ends in error, no law
        outside a predicted set satisfies K1 or K2, no law is a replay disagreement or a baseline finding, and
        rate_non_equivalent_A < 0.80: M2 exit (b) is not met (with no killed mutant equivalent it would need at least 72
        of the 96 survivors equivalent: 5 * 96 >= 4 * (192 - 72); the drafter expects far fewer)."""
        a = self.s["strata"]["A"]
        self.assertEqual((a["killed"], a["rate_all"]["num"], a["rate_all"]["den"]), (96, 96, 192))
        self.assertEqual(a["errors"], 0)
        self.assertEqual([x for x in self.s["unpredicted"] if x["id"][0] == "A"], [])
        for i in ids("A", 1, 192):
            self.assertEqual((self.r[i]["replay_disagreements"], self.r[i]["baseline_findings"]), ([], []), i)
        self.assertLess(5 * a["rate_non_equivalent"]["num"], 4 * a["rate_non_equivalent"]["den"])
        self.assertIs(a["meets_threshold"], False)

    def test_kills_by_operator_in_stratum_a(self):
        """I61-P3: kills per operator in stratum A: mstore_offset 21/22, shl_width 8/12, drop_delete 0/7, swap_cursor
        0/12, cmp_boundary 2/23, cmp_boundary_mirror 1/15, mload_offset 0/22, shr_width 0/9, putuint64_offset 14/14,
        copy_offset 26/28, drop_len_check 0/4, go_slice_offset 24/24."""
        got = {o: (v["mutants"], v["killed"]) for o, v in self.s["by_operator"]["A"].items()}
        self.assertEqual(got, A_BY_OPERATOR)

    def test_codec_store_offsets_kill_by_k1_where_every_byte_is_written(self):
        """I61-P4: mstore_offset: 21 of 22 killed. Where the shifted store leaves no byte unwritten (A001, A003-A006,
        A008, A021) the kill is K1; where it leaves one (A002, A007, A009-A017, A019, A020, A022) the model has no
        witness and the kill is K2 alone, the code's fresh memory reading 0 at the unwritten byte. A001-A020 are killed
        by all five non-REFUTED codec laws, A021-A022 by L_par_hdr_v1, L_rt_go_v1 and L_rt_go_v2. A018 (the
        sequencer-set store at 186) survives as proof_lost_unwitnessed on those five laws: its only unwritten byte, 185,
        is 0 in the code as the ssvh = 0 premise wants, so no candidate falsifies a law."""
        for i in ids("A", 1, 22):
            with self.subTest(mutant=i):
                if i == "A018":
                    self._survived(i)
                    self.assertEqual(self.r[i]["proof_lost_unwitnessed"], PROOF_LOST[i])
                    self.assertEqual(self.r[i]["class"], "proof_lost_unwitnessed")
                else:
                    self._killed(i, *KILLS[i])

    def test_shl_width_kills_the_codec_stores_and_not_the_preimage(self):
        """I61-P5: the 8 codec-store shl_width mutants (A027-A034) are killed by K1 (A027-A032 by the five codec laws,
        A033-A034 by L_par_hdr_v1, L_rt_go_v1, L_rt_go_v2); the 4 in Rollup._commitBatch (A023-A026, the data-hash
        preimage) survive with the projected header document unchanged."""
        for i in ids("A", 27, 34):
            with self.subTest(mutant=i):
                self._killed(i, *KILLS[i])
        for i in ids("A", 23, 26):
            with self.subTest(mutant=i):
                self._survived(i)
                self.assertIs(self.r[i]["projection"]["changed"], False)

    def test_cmp_boundary_kills_exactly_the_two_header_build_sites(self):
        """I61-P6: of the 23 cmp_boundary mutants exactly A058 (Rollup.sol:333, version 1 gets the 249-byte length:
        K1) and A059 (:353, version 1 skips the lastBlockNumber store: K2) are killed, each by L_par_hdr_v1 and
        L_rt_go_v1 and no other law; the other 21 survive. Both lines run in the generated harness from the tree's own
        text (replay.m0)."""
        self._killed("A058", *KILLS["A058"])
        self._killed("A059", *KILLS["A059"])
        for i in ids("A", 54, 76):
            if i not in ("A058", "A059"):
                with self.subTest(mutant=i):
                    self._survived(i)

    def test_one_mirrored_flip_is_killed_by_a_partiality_witness(self):
        """I61-P7: of the 15 cmp_boundary_mirror mutants exactly A081 (Rollup.sol:293, `version <= 2` to `< 2`: every
        version-2 commit now reverts) is killed, by K2 on L_rt_go_v2 alone: its baseline generator's proof is rejected
        on the mutant's projection (the version bound falls to 1) and K2 (c) holds through a partiality witness
        (replay.partiality): a version-2 candidate at which the original code executes and the mutant's enc_sol reverts
        at :293. I60 forecast proof_lost_unwitnessed here; the partiality witness is I61's (S-A3). The other 14
        survive."""
        self._killed("A081", *KILLS["A081"])
        e = self.r["A081"]["laws"]["L_rt_go_v2"]
        self.assertEqual((e["how"], e["falsifier"]["kind"]), ("K2", "partiality"))
        for i in ids("A", 77, 91):
            if i != "A081":
                with self.subTest(mutant=i):
                    self._survived(i)

    def test_solidity_decoders_never_reach_a_law(self):
        """I61-P8: none of the 31 Solidity getter mutants (mload_offset A092-A113, shr_width A114-A122) is killed and
        none changes the projected header document; the 6 tce mutants change no extracted document."""
        for i in ids("A", 92, 122):
            with self.subTest(mutant=i):
                self._survived(i)
                self.assertIs(self.r[i]["projection"]["changed"], False)
        for i in TCE:
            self.assertFalse(any(d["changed"] for d in self.r[i]["documents"].values()), i)

    def test_the_window_view_never_changes(self):
        """I61-P9: for all 242 mutants the window view m1_view is byte-identical to the baseline's, so every one of the
        15 M1x laws is carried with its baseline status in every record; none of the 7 drop_delete and 12 swap_cursor
        mutants is killed."""
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                for law, e in rec["laws"].items():
                    if e["set"] == "M1x":
                        self.assertEqual((e["decided"], e["mutant"]), ("carried", e["baseline"]), law)
        for i in ids("A", 35, 53):
            self._survived(i)

    def test_every_putuint64_offset_mutant_is_killed(self):
        """I61-P10: all 14 putuint64_offset mutants are killed: A123-A128 by L_par_hdr_v0 and A129-A135 by
        L_par_hdr_v1 through K1, A136 (PutUint64 on the 7-byte batchBytes[250:], a panic for every header) by
        L_par_hdr_v1 through K2 alone (the encoder has no ok path, the code's panic falsifies)."""
        for i in ids("A", 123, 136):
            with self.subTest(mutant=i):
                self._killed(i, *KILLS[i])

    def test_copy_offset_kills_all_but_the_two_shifted_sequencer_set_hashes(self):
        """I61-P11: 26 of 28 copy_offset mutants are killed by K1 (V0 by L_par_hdr_v0, V1 by L_par_hdr_v1); A148 and
        A162 (the sequencerSetVerifyHash copy moved to 186; structural.premise_limited) survive: under every codec law's
        ssvh = 0 premise the shifted zeros equal the original bytes, and L_par_hdr_ssvh is REFUTED at baseline."""
        for i in ids("A", 137, 164):
            with self.subTest(mutant=i):
                if i in ("A148", "A162"):
                    self._survived(i)
                else:
                    self._killed(i, *KILLS[i])

    def test_every_go_getter_shift_is_killed_by_the_round_trip_laws(self):
        """I61-P12: all 24 go_slice_offset mutants are killed by K1, by the round-trip laws whose version reads the
        getter: BlobVersionedHash (A177, A178) by L_rt_go_v0 and v1, BlobHashesHash (A179, A180) by L_rt_go_v2,
        LastBlockNumber (A191, A192) by L_rt_go_v1 and v2, every other getter by all three."""
        for i in ids("A", 169, 192):
            with self.subTest(mutant=i):
                self._killed(i, *KILLS[i])

    def test_dropped_go_length_checks_survive(self):
        """I61-P13: none of the 4 drop_len_check mutants of stratum A is killed (the round-trip laws only decode the
        exact-length headers enc_sol makes; structural.premise_limited). The three validate drops (A165-A167) show a
        masked obstruction on L_dom_hdr (a 1-byte header [v]: Go now accepts, Solidity rejects) and are filed rule_gap
        (law_unmoved): ok_go changes, so the three round-trip laws are re-decided on a changed own input and stay
        PROVED. The Version drop (A168) shows none and is filed extraction_gap (model): its panicking path is not an ok
        path, so the projection, and with it every predicted law's own input, does not change."""
        for i in ids("A", 165, 168):
            with self.subTest(mutant=i):
                rec = self.r[i]
                self._survived(i)
                self.assertEqual(rec["masked_obstructions"], MASKED.get(i, []))
                self.assertEqual((rec["class"], rec["gap_stage"], rec["rule_gap_kind"]),
                                 ("extraction_gap", "model", None) if i == "A168" else ("rule_gap", None, "law_unmoved"))
                self.assertIs(rec["projection"]["changed"], i != "A168")

    def test_masked_obstructions(self):
        """I61-P14: exactly 40 stratum-A mutants show a masked obstruction: L_par_hdr_ssvh for the 36 K1-killed codec
        mutants whose version-1 output differs at ssvh = 0 (A001, A003-A006, A008, A021, A027-A034, A058, A129-A135,
        A151-A161, A163, A164), and L_dom_hdr for A076 (BatchHeaderCodecV0.sol:32, a 249-byte version-0 header now
        rejected by Solidity) and A165-A167."""
        self.assertEqual(len(MASKED), 40)
        got = {x["id"]: [] for x in self.s["masked_obstructions"]}
        for x in self.s["masked_obstructions"]:
            got[x["id"]].append(x["law"])
        self.assertEqual({i: sorted(v) for i, v in got.items() if i[0] == "A"}, MASKED)

    def test_k1_only_rate(self):
        """I61-P15: 79 stratum-A mutants are killed by K1 (the 96 kills less the 17 K2-only ones: A002, A007,
        A009-A017, A019, A020, A022, A059, A081, A136)."""
        self.assertEqual(sorted(i for i, (h, _) in KILLS.items() if h == "K2"),
                         sorted(["A002", "A007", "A019", "A020", "A022", "A059", "A081", "A136"] + ids("A", 9, 17)))
        k1 = sorted(i for i in ids("A", 1, 192) if any(x["how"] == "K1" for x in self.r[i]["kill"]["by"]))
        self.assertEqual(k1, sorted(i for i, (h, _) in KILLS.items() if h == "K1"))
        self.assertEqual(len(k1), 79)
        self.assertEqual(self.s["strata"]["A"]["killed_k1"], 79)
        eq = {i for i, v in need(ADJ)["verdicts"].items() if v["equivalent"]}
        self.assertEqual(self.s["k1_only"]["A"]["num"], len(set(k1) - eq))

    def test_stratum_b_has_no_decision_path(self):
        """I61-P16: none of the 50 stratum-B mutants is killed; each has an empty predicted set and is filed rule_gap
        (no_law) or extraction_gap (frontend). The 14 genesis encoder mutants (B001-B008, B011-B016) and the 28
        node/types mutants (B023-B050) change their extracted document. Over the 42 mutants in a codec function
        (reporting.B_codec_functions), none is killed."""
        b = self.s["strata"]["B"]
        self.assertEqual((b["mutants"], b["killed"]), (50, 0))
        self.assertEqual((self.s["B_codec_functions"]["mutants"], self.s["B_codec_functions"]["killed"]), (42, 0))
        for i in ids("B", 1, 50):
            rec = self.r[i]
            with self.subTest(mutant=i):
                self._survived(i)
                self.assertFalse(any(e["predicted"] for e in rec["laws"].values()))
                self.assertIn((rec["class"], rec["gap_stage"], rec["rule_gap_kind"]),
                              [("rule_gap", None, "no_law"), ("extraction_gap", "frontend", None)])
        for i in B_DOC_CHANGED:
            self.assertTrue(any(d["changed"] for d in self.r[i]["documents"].values()), i)

    def test_law_families(self):
        """I61-P17: in stratum A, PAR-codec laws are predicted for 91 mutants and kill 71; PAR-round-trip for 77 and
        kill 56 (I60's 55 and A081); PAR-domain for 6 and kill 0; M1x:DISCH, M1x:FACT, M1x:NAT, M1x:SORT, M1x:SYM and
        M1x:UNDO are each predicted for 100 and kill 0; M2:SORT/site is predicted for 99 and M2:SORT/width for 73, and
        both kill 0. No other family appears."""
        self.assertEqual(self.s["by_family"]["A"], {
            "PAR-codec": {"predicted": 91, "killed": 71}, "PAR-round-trip": {"predicted": 77, "killed": 56},
            "PAR-domain": {"predicted": 6, "killed": 0},
            **{f"M1x:{r}": {"predicted": 100, "killed": 0} for r in ("DISCH", "FACT", "NAT", "SORT", "SYM", "UNDO")},
            "M2:SORT/site": {"predicted": 99, "killed": 0}, "M2:SORT/width": {"predicted": 73, "killed": 0}})

    def test_the_corpus_sees_seven_swapped_cursors(self):
        """I61-P18: the i20_step corpus detects the 7 swapped cursors on modelled paths that its m1 traces exercise
        (A045 :312, A047 :417, A048 :441, A049 :476, A050 and A051 :489, A052 :643). Nothing is predicted for A046's
        corpus."""
        for i in CORPUS_SWAPS:
            with self.subTest(mutant=i):
                self.assertIs(self.r[i]["corpus_detected"], True)

    def test_the_frontends_see_every_stratum_a_mutant_but_the_tce_ones(self):
        """I61-P19: each stratum-A mutant except the 6 tce ones changes at least one extracted document (normalized),
        so no stratum-A survivor but those is an extraction gap at the frontend stage."""
        for i in ids("A", 1, 192):
            with self.subTest(mutant=i):
                self.assertIs(any(d["changed"] for d in self.r[i]["documents"].values()), i not in TCE)

    def test_no_m2_law_moves(self):
        """I61-P20: in every record no M2 law, baseline or derived only on the mutant, is REFUTED unless it is REFUTED
        at baseline, and no PROVED M2 law loses its proof (SORT-site laws decide on the hand model; SORT-width laws
        have no Reach predicate on the extracted model)."""
        for i, rec in self.r.items():
            with self.subTest(mutant=i):
                for law, e in rec["laws"].items():
                    if e["set"] == "M2" and e["mutant"] != "error":
                        if e["baseline"] in ("PROVED", "UNKNOWN", "absent"):
                            self.assertNotEqual(e["mutant"], "REFUTED", law)
                        if e["baseline"] == "PROVED":
                            self.assertEqual(e["mutant"], "PROVED", law)

    def test_the_gate_passes_at_its_first_attempt(self):
        """I61-P21: the harness gate passes at its first attempt: on the original code the harness reproduces I16's
        outputs of all six edges, agrees with the baseline model wherever the model is defined, falsifies no PROVED M0
        law and replays every REFUTED M0 law's witness; C1 and C2 are killed by K1 through L_par_hdr_v0, C3 by K1
        through L_par_hdr_v1, and C4 by K2 with partiality witnesses through L_rt_go_v1 and L_rt_go_v2."""
        g = need(GATE)
        self.assertEqual(len(g["attempts"]), 1, [a["checks"] for a in g["attempts"]])
        self.assertIs(g["attempts"][0]["passed"], True)
        for c, law, how in (("C1", "L_par_hdr_v0", "K1"), ("C2", "L_par_hdr_v0", "K1"), ("C3", "L_par_hdr_v1", "K1"),
                            ("C4", "L_rt_go_v1", "K2"), ("C4", "L_rt_go_v2", "K2")):
            rec = need(CONTROLS / f"{c}.json")
            self.assertIn({"law": law, "how": how}, rec["kill"]["by"], c)
            if how == "K2":
                self.assertEqual(rec["laws"][law]["falsifier"]["kind"], "partiality", c)

    def test_kills_by_language_and_site(self):
        """I61-P22: by language in stratum A, Solidity 32 of 122 killed and Go 64 of 70; stratum B (Go only) 0 of 50.
        Per site (reporting.per_site), 51 of stratum A's 127 sites are killed."""
        bl = self.s["by_language"]
        self.assertEqual({k: (v["mutants"], v["killed"]) for k, v in bl["A"].items()},
                         {"solidity": (122, 32), "go": (70, 64)})
        self.assertEqual({k: (v["mutants"], v["killed"]) for k, v in bl["B"].items()}, {"go": (50, 0)})
        self.assertEqual((self.s["per_site"]["A"]["sites"], self.s["per_site"]["A"]["killed"]), (127, 51))

    def test_k2_kills_are_model_tied_and_no_new_class_appears(self):
        """I61-P23: every killed stratum-A mutant with a K2 law has a model-tied one (k2_model_tied.A.untied = 0: at the
        (c) candidate the mutant model is undefined or false where the baseline model holds); no mutant is filed
        baseline_finding or extraction_gap (replay); no obstruction is recomputed_only."""
        self.assertEqual(self.s["k2_model_tied"]["A"]["untied"], 0)
        self.assertGreater(self.s["k2_model_tied"]["A"]["tied"], 0)
        for i, rec in self.r.items():
            self.assertNotIn(rec["class"], ("baseline_finding",), i)
            self.assertNotEqual((rec["class"], rec["gap_stage"]), ("extraction_gap", "replay"), i)
        self.assertEqual(self.s["recomputed_only"], [])

    def test_the_plan_literal_count(self):
        """I61-P24: the plan-literal count of stratum A (reporting.plan_literal) is 97 of 192: the 96 kills and A018,
        whose proof loss the plan's words count and K2 (c) does not."""
        self.assertEqual((self.s["plan_literal"]["A"]["num"], self.s["plan_literal"]["A"]["den"]), (97, 192))
        self.assertTrue(plan_literal(self.r["A018"]))


# ============================================================================================ I60's retirement
class TestI60Retirement(unittest.TestCase):
    """Construction (green from the prereg on): I60 is retired honestly. Its key stays in spec/M2/predictions.json,
    unchanged and unscored (none of its run's outcome paths is ever written: only its catalog review and its report
    were); the tests of its run are removed through spec/M2/amendments.jsonl lines (kind retired_by_rejection) that
    holon audit prereg reports as amended, never skipped; its instrument, scope and I22-retirement tests stay."""

    I60_TEST = "tests_m2/test_mutation_adequacy_i60.py"
    RUN_CLASSES = ["TestDeterminism", "TestOperators", "TestPredictions", "TestProjection", "TestReplayHarness",
                   "TestResults", "TestReviewAndAdjudication"]
    KEPT_CLASSES = ["TestI22Retirement", "TestInstrument", "TestScope"]

    def test_the_i60_key_stays_and_is_never_scored(self):
        now = predictions("I60")
        then = json.loads(subprocess.run(["git", "-C", str(ROOT), "show", f"{I60_PREREG}:spec/M2/predictions.json"],
                                         capture_output=True, check=True).stdout)["iterations"]["I60"]
        self.assertEqual(canon(now), canon(then))
        run_paths = [p for p in now["outcome_paths"]
                     if p not in ("docs/iterations/I60_catalog_review.json", "docs/iterations/I60.md")]
        self.assertEqual(len(run_paths), 5)
        for p in run_paths:
            self.assertFalse((ROOT / p).exists(), p)
            self.assertEqual(git("log", "--format=%H", "--", p), "", p)
        self.assertIs(load_json(REVIEW.parent / "I60_catalog_review.json")["reviews"]["soundness"]["sign_off"], False)

    def test_the_run_tests_are_retired_by_amendment(self):
        sys.path.insert(0, str(ROOT))
        from holon.audit import prereg as P
        old = P.analyse(subprocess.run(["git", "-C", str(ROOT), "show", f"{I60_PREREG}:{self.I60_TEST}"],
                                       capture_output=True, check=True).stdout.decode(), True)
        new = P.analyse((ROOT / self.I60_TEST).read_text(), True)
        removed = sorted(k for k in old.fps if k not in new.fps)
        changed = sorted(k for k in old.fps if k in new.fps and old.fps[k] != new.fps[k])
        self.assertEqual(changed, [])
        self.assertEqual(sorted({k.split(".")[0] for k in removed}), self.RUN_CLASSES)
        self.assertEqual(sorted({k.split(".")[0] for k in new.fps if "." in k}), self.KEPT_CLASSES)
        for c in self.KEPT_CLASSES:
            self.assertEqual(sorted(k for k in new.fps if k.startswith(c + ".")),
                             sorted(k for k in old.fps if k.startswith(c + ".")), c)
        lines = [json.loads(l) for l in (ROOT / "spec" / "M2" / "amendments.jsonl").read_text().splitlines() if l.strip()]
        amended = {l["test"].split("::", 1)[1] for l in lines if l["iteration"] == "I60"
                   and l.get("kind") == "retired_by_rejection" and l["test"].startswith(self.I60_TEST + "::")}
        self.assertEqual(sorted(amended), removed)
        body = (ROOT / self.I60_TEST).read_text().split('"""', 2)[2]
        self.assertIsNone(re.search(r"@\s*(unittest\.)?skip|skipTest\(|SkipTest|skipIf|skipUnless", body))


if __name__ == "__main__":
    unittest.main()
