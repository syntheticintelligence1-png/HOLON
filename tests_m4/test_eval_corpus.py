"""I48: evaluation corpus and unsolved controls (whitepaper §13 "Corpus", "Threats to validity" and L15; BUILD_PLAN I48;
docs/HUMAN_ANSWERS.md: Q20 (N = 20 defects across at least 3 systems), Q9 (same-family labellers are labelled), Q7 (the
sealed held-out target), and the end-goal guidance (the corpus tests generality beyond rollups wherever the frontends
reach)). This docstring is the contract that tests_m4/test_eval_corpus.py checks.

Instruments fixed at the prereg, each pinned by its sha256 in PINNED below (a later edit is a change of this test file,
so it needs an amendment): tests_m4/_i48.py (rules C2-C6, N1-N3 and K1-K4 written out a second time, independently of
holon/, with the pins of the parsers it runs, SOLC_SHA256 and GO_VERSION; fingerprinted by the prereg audit),
tests_m4/_m4.py (the shared readers), tests_m4/__init__.py (empty), tests_m4/fixtures/goast/main.go (a go/parser AST
printer), the frozen sidecars spec/M4/lib/corpus_protocol.json (systems, indexes and their enumerations, the pinned
snapshots, collection, criteria, selection, N, the labelling invocation), rule_sheet.json (the rules a labeller
applies), labeller_prompt.md and adjudicator_prompt.md (the exact prompts), rename_reserved.json (names never renamed),
controls_plan.json (control families, sizes, budgets and sizing sources) and the schemas
spec/M4/lib/{candidates,corpus,labels,controls,renaming}.schema.json, and the prompt prompts/I48_eval_corpus.md.
setUpModule, tearDownModule and test_instruments_are_the_preregistered_ones also check that the loaded
tests_m4/_i48.py, tests_m4/_m4.py and this module are the files on disk (integrity_problems: a fresh copy of each,
imported under another name, has the same functions and test methods, globals, module bindings and constants). The
test process never imports a holon module: holon's functions run in child processes (holon_call).

What the plan asks
  BUILD_PLAN I48: spec/eval/corpus.json, public defects with pre-fix and fix commits obtained through git clone, minimal
  rule labels from two labellers, and isomorphic renaming; spec/eval/controls.json, planted true and false obligations
  with known ground truth, sized beyond the budgets, for UNKNOWN calibration (L15). Thresholds: N (20 across at least 3
  systems, Q20); the inter-rater agreement target (reported, not asserted); the size of the control set. Exit: the
  manifests validate with at least N doubly labelled entries, and the renaming tool round-trips. I51 runs HOLON on the
  corpus's pre-fix commits, I52 the baselines, I53 the UNKNOWN calibration on the controls; I48 runs none of them.

Predictions and construction checks (spec/M4/predictions.json, key I48)
  Predictions (outcomes recorded nowhere before the build): I48-P1 at least 4 of the 6 systems contribute at least 3
  entries each, at least 2 of these not rollups (test_system_spread_prediction); I48-P2 Cohen's kappa >= 0.40 between
  two different models of the same family, each prompt read by a fresh tool-less process (test_agreement_prediction);
  I48-P3 the final labels use at least 5 of the 9 categories and at most 5 entries are none (test_label_spread_
  prediction); I48-P4 in at least 6 of the 20 entries the renaming renames an identifier on a pre-fix line the fix
  deletes or changes (test_renaming_strength_prediction). A miss is a Surprise, never a reason to edit anything.
  Everything else here is a regression or a construction check (properties of the tools and the process, I48-R1..R6):
  the files validate, the item lists are the snapshots', the selection is rule C4's, 20 entries exist and are doubly
  labelled, the labelling runs are the protocol's, the prompts are the templates', the renaming round-trips and is
  isomorphic, the controls are the plan's.

Gaps preregistered
  E-G1 Selection bias. The population is what the fixed indexes list (advisories and audit reports, chosen by the
       projects), examined newest first by fresh collectors and recorded in full in spec/eval/candidates.json: every
       index's snapshot and whole item list, how far it was examined, and every candidate with its exclusion, its
       reason and, for the judged reasons, a note. Every git snapshot is pinned at the prereg (the protocol's
       snapshots): the mechanical indexes (GHSA and the geth list) are recomputed by the instrument at their pins, an
       in-repo folder's reports are listed again at its pin, and a mechanical item's fix commit (when it names a
       reachable commit) and description are checked against the item; the rule picks the earliest named reachable
       commit even when a source names a commit that is not the fix. A page snapshot (arbitrum's and compound's audit
       pages) records the final URL and the sha256 of the fetched bytes but cannot be fetched again here. Judgment
       channels that remain, stated: the fix commit where no reachable commit is named, a null fix, other_repo, the
       findings an audit report holds (its count), the dates of page and folder items (they set the examination
       order), the item list of a page, and the criteria write-up, functional and duplicate. Security-relevant defects
       are over-represented. Titles and descriptions are verbatim; no test re-reads an audit report or a page (they
       are public, so anyone can). The selection among eligible candidates is mechanical (rule C4).
  E-G2 Same family (Q9). The collectors, both labellers and the adjudicator are of the build agent's family. Labeller a
       and the adjudicator run model A (the family's most capable model available to the build), labeller b model B
       (a smaller, different model of the same family), each prompt in a fresh tool-less process (the protocol's
       labelling_invocation). The adjudicator shares a's model, a possible bias toward a: the report gives how often
       it chose a's rule, b's or a third. The repository cannot re-verify which models ran: their names are not
       recorded (a repository rule), only the tags A and B and the tool's recorded run-time checks; neither the choice
       of model B nor any re-run of the labelling is checkable from the repository. The agreement is reported with
       that label and is not evidence of independence across families.
  E-G3 Renaming depth and semantics (rule N1). Conservative: only names declared in the set and used nowhere else that
       the checkout shows are renamed; file names, string literals and kept comments stay, so they can still identify a
       defect; a .sol file of the set that solc cannot parse is renamed in no word (N1 (e)). Semantics are checked by
       parsers (N3), not by building: no go build, go vet or solc compilation runs (a package needs its whole module
       and dependency graph, and Solidity sources need lib/ and node_modules/ dependencies the checkout does not
       hold). The construction tests cover the cases the second review compiled: a call option (salt), a contextual
       keyword (error), cgo selectors (C.free) and a non-ASCII name used in a sibling file. Residual risks, stated: a
       Solidity name declared in the set that also names a member of an absent dependency and is used in the set as
       that member is renamed and breaks the binding; a name read by tooling outside the checked files (a deployment
       script naming a contract) is not checked; Go's %+v output of a struct prints its field names.
  E-G4 The controls' factory outcomes are predicted by the plan's budget rule, recomputed by the interpreter (K4), but
       not run here (I53 measures them, with the run budgets of controls_plan.json passed explicitly).
  E-G5 No HOLON run on the corpus: a label says which rule's obligation the defect falsifies, not whether today's
       extractors reach the code (I51 measures that).
  E-G6 Order. BUILD_PLAN lists I47 before I48; I48 runs first. I47's performance loop may change the explorer's and
       houdini's defaults, so the controls' run budgets are pinned (controls_plan.json budgets.run) and within_budget
       is true of those budgets, not of later defaults. The sizing also rests on the generic policy's Nat inputs
       {0, 1}, houdini's field-constant proposals and the explorer's prefix search as they are at this base:
       controls_plan.json sizing_sources records the sha256 of those files, and I53 asserts them or re-derives the
       sizing when they changed (I48 checks only that the record is well formed).
  E-G7 Instrument integrity. The pins cover the files; integrity_problems (run by setUpModule, tearDownModule and
       test_instruments_are_the_preregistered_ones) checks that the loaded tests_m4/_i48.py, tests_m4/_m4.py and this
       module are those files. What holds exactly: the authoritative run is this module named in a fresh process
       (python -m unittest tests_m4.test_eval_corpus), which imports no other test module and no holon module (holon
       runs in child processes). A discovery run that imports other tests_m4 modules can be patched by them (a module
       loaded in the same process can replace setUpModule itself, the standard library, the frozen tests/ helpers or
       the per-process caches, RUNTIME_STATE), so a new tests_m4 module needs the lead's diff review; I48's eval
       commits may not add one (I48-R3).

CLI (every JSON file: json.dumps(obj, indent=2, sort_keys=True) + "\\n"; deterministic, no timestamps)
  python -m holon eval index --system ID --out FILE
      Rule C2: writes the system's mechanical index items (its ghsa index, and for go-ethereum also the geth list) at
      the protocol's pinned snapshots to FILE: {"system", "indexes": [{"index", "snapshot", "items"}]}, items exactly
      tests_m4/_i48.py's lists (a pre-filtered item with its excluded_by and title null). FILE must lie outside the
      repository; exit 0 written, 2 refused. A collector of a mechanical index works from this list.
  python -m holon eval verify [--root DIR] [--cache DIR]
      Re-derives every candidate's git facts (rule C3) from partial clones and checks them against
      spec/eval/candidates.json; exit 0 all agree, 1 a mismatch (named).
  python -m holon eval select [--root DIR] [--check]
      Rule C4: writes the selection into spec/eval/candidates.json (reason, entry) and the entries' git and source fields
      into spec/eval/corpus.json; with --check, exit 1 when either differs from a fresh selection.
  python -m holon eval agree [--root DIR] [--check]
      Rules C5-C6: reads spec/eval/labels/{a,b,adjudicator}.json, writes each entry's labels and label and the
      agreement into spec/eval/corpus.json.
  python -m holon eval rename --root DIR --files F [F ...] --seed S --out DIR2 --map MAP
  python -m holon eval unrename --root DIR2 --map MAP --out DIR3
      Rules N0-N3. rename writes the renamed copies of the files (same relative paths) under DIR2 and the map; unrename
      restores them under DIR3. Exit 0 written, 2 refused (a file missing, a language outside go and solidity, or a
      set holding .sol files without the pinned solc, which rule N1 (e) needs).
  python -m holon eval controls [--root DIR] [--check]
      Rules K1-K2: writes spec/eval/controls/<id>.facts.json and <id>.law.json for every control of the plan,
      spec/eval/controls/ledger.json and spec/eval/controls.json; with --check, exit 1 when a file differs.
  python -m holon eval renaming [--root DIR] [--cache DIR] [--check]
      Rule N3: renames every corpus entry's files at its pre-fix commit (seed: the entry id) and writes
      gen/eval/renaming/<entry>.json; with --check, exit 1 when a file differs.

Rules (holon/eval/*.py; tests_m4/_i48.py writes each one out again)
  C0 Inputs. The pinned sidecars; public git repositories (holon's clones under ~/.holon/eval/repos, the instrument's
     own under ~/.holon/eval/instrument-repos, never inside the repository); the indexes' snapshots (C2), every git one
     pinned in the protocol (snapshots: the newest first-parent commit of the branch whose committer date is before
     the cutoff, tests_m4/_i48.py::snapshot_rule). A commit is accepted only as reachable from a branch or tag (or from
     the pinned branch, where C2 says so), decided from git rev-list over the clone's refs alone. Fetching by sha
     happens only after that reachability check and only for the advisory-database snapshot: a commit-graph clone
     (--filter=tree:0) proves the pin reachable from the database's branch, and only then is it fetched by sha, depth
     1, into a separate bare repository. The sealed target and the development target are excluded by repository
     (protocol excluded_repos) and by subject (excluded_subjects): a mechanical index item naming one is pre-filtered
     and never opened, any other item naming one is not read further, and no tool clones or reads them; a clone or
     fetch that git redirects ("redirecting to <url>", which git does not print under --quiet) to a URL under an
     excluded pattern fails, in the instrument and in the tool. A rename GitHub serves without an HTTP redirect (as
     observed at the prereg for a renamed public repository) is not detectable this way.
  C1 Systems. The six systems of the protocol (arbitrum, compound, cosmos, go-ethereum, optimism, wormhole: two rollups,
     a DeFi protocol, an application-chain framework, an execution client and a bridge), each with its repositories and
     its ordered indexes. No other system enters; a fix in another repository is recorded as other_repo.
  C2 Candidates. spec/eval/candidates.json (schema candidates.schema.json) records what the collectors examined
     (protocol "collection": fresh agents, one per system, given only the protocol; the system's indexes in order, each
     in its enumeration's order; stop at the system's 8th eligible candidate or when its indexes run out).
     - indexes: one record per index of every system, in the protocol's order (protocol index_record): {system, index,
       snapshot, items, examined}. snapshot: a git index {kind git, repo, commit, path}, exactly its pin's repo, commit
       and path (snapshots.pins; the GHSA pin has no path), reachable from the pin's branch (the geth list's file with
       the pinned sha256); page {kind page, url the final URL after redirects, sha256 of the fetched bytes}. items: the
       whole list of the index's items in examination order. ghsa and geth: exactly tests_m4/_i48.py::index_items at
       the pin ({item, published, title, excluded_by}: ghsa_items_from, geth_items_from, with the pre-filter prefilter;
       a pre-filtered item's title is null; an entry without a parsable published date is no item; a geth item is
       <list URL>#<uid> when the list's uids are distinct, else #<1-based position>); published before the cutoff.
       folder: exactly folder_items at the pin (every .pdf or .md file under the folder other than a README.md, as
       <repo>/blob/<commit>/<path>), the pin being the folder's cutoff, published at most the pin's committer date.
       page: published before the cutoff. folder and page items are {item, published, title, findings, note}, in the
       order published newest first, then item (items_order), dated as the protocol says (the report's own date; a
       month, quarter or year means its first day; else, for a folder, the committer date of the earliest commit of
       the pin's first-parent history adding the path; for a page, the page's date, else 1970-01-01); findings is the
       number of findings the report holds when the item was examined (else null) and note says why exactly when it is
       0. examined: indexes before the stopping index fully, the stopping index up to the item holding the 8th
       eligible candidate, later ones 0; an exhausted system examines all fully.
     - candidates, per system in examination order: id <system>:<rank, zero-padded to at least three digits> (rank 1,
       2, ... without gaps), index, item (an item of items[:examined] of its index, also its first source's URL),
       published (the item's), repo, title (verbatim), description (a verbatim excerpt of the first source, whitespace
       collapsed, at most 2000 characters), sources (no source but the first holds an excluded pattern), fix_commit
       (the protocol's fix-commit rule) and, from git, prefix_commit, fix_date (committer date, UTC), files,
       source_lines and frontend_lines; excluded_by; eligible iff every criterion holds, else the reason of the first
       failing one in the protocol's order (excluded_repo, other_repo, commit_not_found, not_in_frontend_reach,
       no_public_writeup, not_functional, duplicate). Candidates appear in items order (index order, then item order);
       an examined item of a mechanical index yields exactly one candidate, whose item, published and title are the
       item's; an examined audit item yields exactly findings candidates, one per finding in the report's order, except
       the stopping item, which yields 1 to findings, its last the system's 8th eligible candidate.
     - mechanical items (M3): an opened candidate's description is a verbatim excerpt of the advisory's details or the
       geth entry's description (each its summary when blank; tests_m4/_i48.py::description_ok); when the item names
       a commit of the system's repositories (named_commits) reachable from a branch or tag, the fix commit is the
       earliest such commit by committer date (ties: the sha) and repo its repository (named_fix).
     - excluded_repo: excluded_by is the pre-filter's {pattern} or {subject} for a pre-filtered item (title,
       description and repo null, never read); an opened mechanical item is excluded only by {pattern: P} with P found
       (case-insensitive) in its repo; another item by {pattern: P} with P found in its repo or item, or {subject: S}
       with S a whole word of its title or description. Conversely, a candidate whose repo or item holds an
       excluded_repos pattern, or whose (opened) title or description names an excluded subject, is excluded_repo. A
       candidate may lack a title and a description only when it is excluded_repo and was not opened (pre-filtered,
       or excluded by a pattern in its item or repo). excluded_by is null for every other reason.
     - other_repo: repo none of the system's and not excluded; fix_commit a commit reachable from a branch or tag of
       that GitHub repository, or null with an exclusion_note (a commit that cannot be named, or a repository outside
       GitHub); no other git facts. commit_not_found: repo one of the system's; a null fix_commit carries an
       exclusion_note saying what was searched. exclusion_note for no_public_writeup, not_functional and duplicate;
       duplicate_of for duplicate (the kept candidate has the earlier fix_date).
     - systems[] counts each system's candidates and says why it stopped (eighth_eligible, exhausted); collectors[]
       names one fresh agent per system.
  C3 Verification. For every candidate whose fix commit is given in one of its system's repositories, holon eval verify
     and the instrument (tests_m4/_i48.py::commit_info) derive the same facts as the file holds: the commit is reachable
     from a branch or a tag of the public repository (else commit_not_found; never fetched by sha); prefix_commit,
     fix_date, files (non-test, non-generated .go and .sol files changed and present in the pre-fix tree),
     source_lines and frontend_lines (git numstat); and among these candidates reason not_in_frontend_reach holds
     exactly when commit_info's reach is false (files empty, or .go and .sol files hold under half of the changed
     source lines). An other_repo candidate's given fix commit is reachable from a branch or tag of its GitHub
     repository (commit_info's found; never fetched by sha). excluded_repo and other_repo candidates carry no other git
     facts. A mechanical candidate's fix commit and description are checked against its item (C2, M3). The index
     snapshots are checked as C2 says (the advisory-database pin is the only commit fetched by sha).
  C4 Selection: tests_m4/_i48.py::select (round robin): each system's eligible candidates newest fix first; rounds visit
     the systems in the protocol's order, each system below max_per_system taking its next candidate, until n entries.
     Included candidates get entry ids c01.. in inclusion order and reason null; the other eligible ones cap_reached
     (their system is full) or past_n. spec/eval/corpus.json's entries are exactly the included candidates, in that
     order, with the candidate's fields (system, repo, title, description, sources, fix_commit, prefix_commit,
     fix_date, files), the system's kind, and languages (from the files' extensions, sorted).
  C5 Labels. spec/eval/labels/a.json, b.json and adjudicator.json (schema labels.schema.json). Each prompt (one entry,
     one role) is read by a fresh, tool-less process run exactly as the protocol's labelling_invocation says (argv with
     <model> the model of the role's tag; the frozen system prompt; the prompt on stdin; a fresh empty working
     directory; a 600 s timeout): labeller a and the adjudicator run model A, labeller b model B, a different model of
     the same family; only the tags are recorded (model_tag; corpus.json's labellers.model_tags), with the tool's
     run-time checks (checks: one_model_per_role, a_differs_from_b, adjudicator_is_a, each true). The prompt is exactly
     tests_m4/_i48.py::render_prompt(role, entry, fix_diff(entry's diff_files)): the frozen template filled with the
     rule sheet, the entry's title, description, source URLs and fix diff (capped: cap_diff keeps the longest prefix of
     whole lines of at most 60000 characters and then says how many lines it kept), the adjudicator's also with both
     labels. Each label records the prompt's sha256, its attempts (each: the CLI's JSON reduced to is_error,
     num_turns, result, session_id and subtype, verbatim, and its outcome attempt_outcome), the response (the last
     attempt's result) and the label: parse_response(response) when the last attempt is ok, else null. Retry rule
     (tests_m4/_i48.py::retry_follows): a cli_error attempt does not count toward the two model-output attempts and is
     run again after a 60 s wait, at most 5 cli_error attempts per prompt; a failed counted attempt is followed by one
     more counted attempt; the attempts stop at the first ok one, the second counted one or the fifth cli_error one,
     every attempt recorded. The label is null only when both counted attempts fail or the 5 cli_error attempts are
     spent. a and b label every
     entry in corpus order; the adjudicator labels exactly the entries whose a and b labels are both non-null with
     different primaries. a, b and the adjudicator are three different labellers; nobody edits a label after it is
     recorded, and no label is chosen to reach an agreement level. An entry's labels hold a, b and adjudicated (null
     when a and b agree); its label is tests_m4/_i48.py::final_label.
  C6 Agreement: corpus.json's agreement is tests_m4/_i48.py::kappa over the a and b primary labels and the nine
     categories (n, p_o, p_e, kappa, se, ci95, confusion). No exit test asserts kappa; test_agreement_prediction checks
     I48-P2's level, and a miss is a Surprise.
  C7 Exit (the plan's; a construction check): corpus.json validates, names the sha256 of the protocol, the rule sheet
     and candidates.json, and holds n = 20 entries from at least min_systems = 3 systems of which at least 2 are not
     rollups; every a and b label is non-null and every disagreement is adjudicated with a non-null label;
     candidates.json validates and its selection is rule C4's.
  N0 Renaming (contamination mitigation, §13). A map is {"map_version": "holon-rename/0.1", "seed", "files": [{"path",
     "language", "sha256": the original's, "renamed_sha256"}], "identifiers": {old: new} (keys sorted), "comments":
     [{"path", "offset": the comment's byte offset in the original, "text": the comment's original bytes,
     "replaced_by": "" | " " | "\\n"}]}; rename and unrename are deterministic functions of (the files, the root's other
     files, the seed), and the map with the renamed files gives back the originals.
  N1 What is renamed. One map per entry, applied to every file of the set: an identifier token (never inside a string,
     character literal or comment) is renamed in every file of the set or in none. It is renamed iff
     (a) it is declared in a file of the set. Go: the name of a func, method, var, const, type, struct field, interface
         method, parameter, result, label or import alias, or a := or range := name. Solidity: the name of a contract,
         interface, library, function, modifier, variable, struct or member, enum or value, user-defined value type,
         event, error, parameter or import alias, or a Yul variable or function; a declared name holding a dot (a
         pre-0.7 dotted Yul name) is never renamed;
     (b) it is reserved for no language of the set's files (spec/M4/lib/rename_reserved.json, names and patterns: for
         Go the keywords, predeclared names, _, init, main and C, the package-clause name of every Go file of the set,
         and, in every Go file of the set that imports "C", every name X of a selector expression C.X; for Solidity
         the keywords, units, every global name and member, _, Error, Panic, the call options value, gas and salt,
         the contextual keywords error, from, revert, global, transient, layout and at, the EVM-Cancun Yul builtins and
         the pragma words);
     (c) when the set holds Go files, it is not exported (its first character is not an upper-case letter, Unicode
         category Lu) and occurs in no file of any extension outside the set in a directory holding a .go file of the
         set (the package's other files, test, assembly, C and header files included); when the set holds Solidity
         files, it is not ABI-visible (the name of a public or external function, a public state variable, an event or
         an error), it names no function or modifier declared override (its base may lie outside the checkout), and it
         occurs in no .sol file outside the set anywhere under --root;
     (d) it occurs in no string or character literal's value in the set and in no kept comment;
     (e) it occurs in no .sol file of the set that the pinned solc cannot parse (from the copy with neutralised
         version pragmas, as N3), so N1's set is exact for every set.
     "Occurs" means as a word: a maximal run of [A-Za-z0-9_$] in the bytes, or a maximal run of characters that are _,
     $, a Unicode letter (category L*) or a decimal digit (Nd) in the UTF-8 decoding (errors replaced); a file's words
     are both kinds (tests_m4/_i48.py::words). New names: tests_m4/_i48.py::new_names(seed, renamed, words of every
     file under --root): v (V when the first character is category Lu) and the first 10 hex digits of
     sha256(seed + ":" + old), lengthened one digit at a time until it is no word of the tree and no other new name.
     Comments: every comment is removed and recorded in the map, except the kept ones, which stay verbatim: Go
     directives (//go:, // +build, //export , //line , /*line ) and the cgo preamble (the comment group documenting
     import "C"); Solidity comments holding @solidity or @custom:. A removed line comment becomes nothing, a block
     comment holding a newline one newline, any other block comment one space (tests_m4/_i48.py::replaced_by).
  N2 Round trip: unrename(rename(files)) is byte for byte the original files.
  N3 Isomorphism, decided by parsers the tool does not share code with (tests_m4/_i48.py::check_renaming).
     - Go: each renamed .go file parses, and its tests_m4/fixtures/goast/main.go printout (depth, operators and
       tokens, literal values, nil children, declaring identifiers, kept comments in place) equals the original's with
       every identifier renamed through the map.
     - Solidity: each renamed .sol file's token stream (tests_m4/_i48.py::sol_tokens, an independent lexer: comments
       skipped except the kept ones, string, hex and unicode literals one token each) equals the original's under the
       map; and, parsed by the pinned solc 0.8.24 (--stop-after parsing) from a copy whose `pragma solidity <expr>;`
       is rewritten to `pragma solidity >=0.0.0;`, it parses exactly when the original does, and when both parse
       their ASTs are equal under the map (locations, ids, documentation and references aside). How many files were
       compared by AST and how many by tokens alone is recorded.
     - Each renamed file's comments are exactly the original's kept ones; the map's comments are exactly the
       original's removed ones with their replaced_by, each map text the original's bytes at its offset (a Go
       comment is compared with the printer's text with "\\r" removed on both sides: go/scanner strips it); the map's
       identifiers are exactly N1's set with new_names' names.
     gen/eval/renaming/<entry>.json (schema renaming.schema.json): {"entry", "seed": the entry id, "files" (as in the
     map), "renamed": the number of identifiers renamed, "candidates": the number of distinct identifier tokens of the
     set's files that are not reserved, "on_changed_lines": the number of renamed identifiers that occur on a pre-fix
     line the fix deletes or changes (tests_m4/_i48.py::changed_old_lines: the old lines of the -U0 hunks; a pure
     insertion contributes none), "files_by_ast", "files_by_tokens", "roundtrip": true, "isomorphic": true,
     "map_sha256": the map file's sha256}; the map itself is not committed (it would pair each original identifier with
     its renamed one).
  K0 Controls inputs: spec/M4/lib/controls_plan.json alone.
  K1 The controls: tests_m4/_i48.py::controls(plan): 14 controls (depth 1, 2, 4, 8, 16; value 1, 2, 7, 1000; relational
     1, 2, 4; constant 1, 3), each with truth, witness, within_budget and expected from the plan's rules.
  K2 Documents: spec/eval/controls/<id>.facts.json and <id>.law.json are byte for byte dumps(tests_m4/_i48.py::
     expected_documents(control, plan)) (holon-facts/0.2, target holon/eval-controls, the generic policy, no search
     key; holon-ir/0.3, milestone T48, law_id L_i48_<family>_<size>, rule SORT with no subform, one binder s: Reach,
     claim <observer>(s) == true, scope unbounded, facts_sha256 the facts file's); each law validates against
     spec/schemas/law_ir_0_3.schema.json and passes holon.ir's premise checks; spec/eval/policy_hints.mjs and
     spec/eval/lib/ do not exist; spec/eval/controls/ledger.json gives each control an exact holon.records bundle that
     classifies every definition of the model holon.gen.machine generates from its facts; spec/eval/controls.json
     (schema controls.schema.json) lists the controls with the plan's budgets, run budgets included.
  K3 Ground truth, independent of HOLON (the instrument's interpreter): each false control's witness reaches a state
     where the observer is false, and no shorter trace does; each true control's reachable states are finite and the
     observer holds on all of them, and its claim alone is not inductive (a counterexample to induction exists in the
     box where every Nat register is 0..3).
  K4 Sizing, recomputed by the interpreter: a false control is within the budget iff a breadth-first search over the
     generic policy's inputs finds a violating trace of at most prefixDepth actions; a true control iff no
     counterexample to induction exists in the box for the claim together with houdini's constants
     (tests_m4/_i48.py::houdini_constants at prefixDepth and maxPrefixes); within_budget and expected equal the
     plan's rule. The files this sizing rests on are recorded with their sha256 (controls_plan.json sizing_sources).

Rules for the build
  - AGENTS.md is binding. I48 writes only spec/eval/, gen/eval/ and holon/eval/ (plus the CLI entry holon/__main__.py
    and tools/setup_env.sh's solc install); it changes no law, record, model, generator, tool or configuration of
    M0-M3, no test module (tests_m4/ included), no prereg file (spec/M4/ but its amendments, spec/schemas/,
    spec/heldout/, prompts/); holon/eval/ imports no test module. test_i48_outcome_commits_touch_nothing_else checks
    the commits that write the eval paths; a commit that touches none of them is not scoped by that test.
  - Candidates come from fresh collector agents, labels from fresh labelling processes, recorded verbatim; nobody edits
    a label after it is recorded, and no label is chosen to reach an agreement target. A selection is never re-run
    after labelling.
  - No skips: a test that needs the network, go or solc fails when it is missing, naming it.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path, PurePath

from tests_m4 import _i48 as I
from tests_m4 import _m4 as M4
from tests_m4._m4 import ROOT, canonical_json, file_sha256, load_json, run_holon, validate

LIB = ROOT / "spec" / "M4" / "lib"
EVAL = ROOT / "spec" / "eval"
GEN = ROOT / "gen" / "eval"
CATS = ["PAR", "UNDO", "NAT", "SYM", "FACT", "SORT", "DISCH", "OWN", "none"]
# M1: the snapshot pins the lead fixed at the prereg (the newest first-parent commit of each branch whose committer date
# is before the cutoff, computed from commit graphs only).
SNAPSHOT_PINS = {
    "advisory-database": {"repo": "https://github.com/github/advisory-database", "branch": "main",
                          "commit": "b950a40c9ce07b70b943775709034132dd9614cb",
                          "committer_date": "2026-10-14T21:37:11Z"},
    "geth-list": {"repo": "https://github.com/ethereum/go-ethereum", "branch": "website",
                  "commit": "17538c7bbb135c95244a60c625917cc1975cdc85", "committer_date": "2026-10-07T09:48:23Z",
                  "path": "public/docs/vulnerabilities/vulnerabilities.json",
                  "sha256": "c0d3311d521e0b619129e8318b754474511ce104ca57f90faa9f7c92fa5a7346"},
    "cosmos-sdk-audits": {"repo": "https://github.com/cosmos/cosmos-sdk", "branch": "main",
                          "commit": "2ad20ad7ca843fbde95c1472ab69f1d3f04e46d4",
                          "committer_date": "2026-10-06T07:19:38Z", "path": "docs/audits"},
    "ibc-go-audits": {"repo": "https://github.com/cosmos/ibc-go", "branch": "main",
                      "commit": "35cf291f836ecd324d5921150c417f79b6ebfc77", "committer_date": "2026-10-14T13:35:11Z",
                      "path": "docs/audits"},
    "optimism-security-reviews": {"repo": "https://github.com/ethereum-optimism/optimism", "branch": "develop",
                                  "commit": "7c2e64f60028baca88367c35e1007e568036648b",
                                  "committer_date": "2026-10-14T21:43:33Z", "path": "docs/security-reviews"},
    "wormhole-audits": {"repo": "https://github.com/wormhole-foundation/wormhole", "branch": "main",
                        "commit": "bb5957f321b0a9d168f52e906699ee77baa82a28", "committer_date": "2026-10-13T17:04:00Z",
                        "path": "audits"},
}
LAW_SCHEMA = ROOT / "spec" / "schemas" / "law_ir_0_3.schema.json"

# The instruments as preregistered (B4, MJ2): a later edit of any of them fails test_instruments_are_the_preregistered_ones
# and so needs an amendment of this test file (spec/M4/amendments.jsonl).
PINNED = {
    "prompts/I48_eval_corpus.md": "9c00c7113e1cb40b1452eeca4ad292c154604ea327265fa15550ef7a7e3783a0",
    "spec/M4/lib/adjudicator_prompt.md": "507ab305557c7b506af607a11b961ae2bde0d428591f3f7585a75d9474f8f395",
    "spec/M4/lib/candidates.schema.json": "b17ac5a3d5df718a02aeba42823cdac61bb625cd0394ab211968fbc315f7c634",
    "spec/M4/lib/controls.schema.json": "96971dd1f5d66f0da17934c76df1defb70d7574fc1bcac92bfdceda3c5017a04",
    "spec/M4/lib/controls_plan.json": "54d398aa233402c1a7e9b1451ba3a38da670b11fb7e711886b5019c654b71b92",
    "spec/M4/lib/corpus.schema.json": "37646d418e864b148ad3e2288119ff7f4f08d4ea64af5407a7a94b8a65a6daa5",
    "spec/M4/lib/corpus_protocol.json": "600be4809044ae9a13b727a042aeb95960b038d0e74c0511f8910cfdd3148f05",
    "spec/M4/lib/labeller_prompt.md": "9657b5ce15866b5e04ac1aa4816dba01b0cdeacdcdd38adf8f33e9b29a1a8225",
    "spec/M4/lib/labels.schema.json": "449a370db351e3902e2a1a49751c61ed775e59caac33800dbbe0df91cca68abf",
    "spec/M4/lib/rename_reserved.json": "4482c268f180c18089c8623fffb2cae551924835f92173270b450e922404b951",
    "spec/M4/lib/renaming.schema.json": "d82eec7392b474baac5ec2e0429d5872f40347f63f4ee8a46d3a62676ef9a650",
    "spec/M4/lib/rule_sheet.json": "07cf70eda559bbc2d559ce920ce2a278db0efb1ad59203d691256ef6c587d253",
    "tests_m4/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "tests_m4/_i48.py": "b02e6ba8bc25854c4fee4f499d5e625e649f67f2b812e144f15a4c9241b51f22",
    "tests_m4/_m4.py": "37465d13f824fb37ecad2ff6c8943110a60de71502a89c18a9322e5fee0d8aa0",
    "tests_m4/fixtures/goast/main.go": "3c8f6beff249ba5ad59c5f44abc5486ba50520f05c929f4a5f3c43a1ddac084b",
}

_RUNS: dict = {}   # entry id -> the instrument's renaming check of that entry (one run per process)
RUNTIME_STATE = ("_RUNS",)   # this module's per-process caches (integrity_problems compares every other binding)
_CONST_KINDS = (str, int, float, bool, tuple, list, dict, set, frozenset, PurePath, re.Pattern)
_UNITTEST_STATE = {"_classSetupFailed", "tearDown_exceptions"}   # what unittest itself sets on a TestCase class


def _code(f) -> tuple:
    c = f.__code__
    return c.co_code, c.co_consts, c.co_names, f.__defaults__, f.__kwdefaults__


def _same_function(a, b, mod) -> bool:
    """a, a binding of the loaded module mod, is the file's function b: defined in mod, with b's code, constants,
    names and defaults, and mod's own globals."""
    return (inspect.isfunction(a) and a.__module__ == mod.__name__ and a.__globals__ is vars(mod)
            and _code(a) == _code(b))


def _compare(mod, fresh, where: str) -> list[str]:
    out, mine, theirs, _MISSING = [], vars(mod), vars(fresh), object()
    skip = set(getattr(fresh, "RUNTIME_STATE", ()))
    for k in sorted((set(mine) | set(theirs)) - skip):
        if k.startswith("__"):
            continue
        a, b = mine.get(k, _MISSING), theirs.get(k, _MISSING)
        if a is _MISSING or b is _MISSING:
            out.append(f"{where}: {k} is bound in only one of the loaded module and the file")
        elif inspect.isfunction(b) and b.__module__ == fresh.__name__:
            if not _same_function(a, b, mod):
                out.append(f"{where}: function {k} is not the file's")
        elif inspect.isclass(b) and b.__module__ == fresh.__name__:
            if not inspect.isclass(a) or a.__module__ != mod.__name__ or a.__bases__ != b.__bases__:
                out.append(f"{where}: class {k} is not the file's")
                continue
            ma, mb = vars(a), vars(b)
            for m in sorted((set(ma) | set(mb)) - (_UNITTEST_STATE - set(mb))):
                x, y = ma.get(m, _MISSING), mb.get(m, _MISSING)
                if inspect.isfunction(x) or inspect.isfunction(y):
                    if not (inspect.isfunction(y) and _same_function(x, y, mod)):
                        out.append(f"{where}: method {k}.{m} is not the file's")
                elif not m.startswith("__") and (x is _MISSING or y is _MISSING or type(x) is not type(y)
                                                 or (isinstance(y, _CONST_KINDS) and x != y)):
                    out.append(f"{where}: class attribute {k}.{m} is not the file's")
        elif inspect.ismodule(b):
            if not inspect.ismodule(a) or a.__name__ != b.__name__ or a is not sys.modules.get(b.__name__):
                out.append(f"{where}: module binding {k} is not sys.modules[{b.__name__!r}]")
        elif isinstance(b, _CONST_KINDS) and not inspect.isclass(b):
            if type(a) is not type(b) or a != b:
                out.append(f"{where}: constant {k} is not the file's")
        elif a is not b:   # an imported function, class or object: the very object the file's import binds
            out.append(f"{where}: {k} is not the object the file's import binds")
    return out


def integrity_problems() -> list[str]:
    """M2 (gap E-G7): the loaded tests_m4/_i48.py, tests_m4/_m4.py and this module are the files on disk. A fresh copy
    of each file, imported under another name, has the same bindings: every function and every method of a class
    defined in the file has the file's code, constants, names and defaults and the loaded module's own globals; every
    module binding is sys.modules of its name; every constant is equal; every other binding (an imported function or
    class) is the very object the file's import binds. RUNTIME_STATE, the per-process caches, aside."""
    out = []
    me = sys.modules[__name__]
    for mod, rel in ((I, "tests_m4/_i48.py"), (M4, "tests_m4/_m4.py"), (me, "tests_m4/test_eval_corpus.py")):
        spec = importlib.util.spec_from_file_location(f"{mod.__name__}__integrity_copy", ROOT / rel)
        fresh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fresh)
        out += _compare(mod, fresh, rel)
    return out


def setUpModule():
    """M2: the integrity check runs before any test of this module (and again after the last one)."""
    problems = integrity_problems()
    if problems:
        raise AssertionError("instrument integrity (gap E-G7): " + "; ".join(problems[:20]))


def tearDownModule():
    problems = integrity_problems()
    if problems:
        raise AssertionError("instrument integrity after the tests (gap E-G7): " + "; ".join(problems[:20]))


_CHILD = """import json, sys, traceback
from pathlib import Path
req = json.loads(sys.stdin.read())
sys.path.insert(0, req["root"])
def dec(x):
    if isinstance(x, dict):
        return Path(x["$path"]) if set(x) == {"$path"} else {k: dec(v) for k, v in x.items()}
    return [dec(v) for v in x] if isinstance(x, list) else x
def enc(x):
    return sorted(x) if isinstance(x, (set, frozenset)) else str(x)
try:
    import importlib
    f = getattr(importlib.import_module(req["module"]), req["func"])
    out = {"ok": f(*dec(req["args"]), **dec(req["kwargs"]))}
except BaseException:
    out = {"error": traceback.format_exc()[-4000:]}
with open(req["out"], "w", encoding="utf-8") as fh:
    json.dump(out, fh, default=enc)
"""


def holon_call(module: str, func: str, *args, **kwargs):
    """M2: holon's module.func(*args, **kwargs) run in a child process (python -I, ROOT on sys.path; JSON in and out:
    paths as {"$path": ...}, sets as sorted lists), so that the test process never imports a holon module. An
    exception in the child is a failure carrying its traceback."""
    def enc(x):
        if isinstance(x, PurePath):
            return {"$path": str(x)}
        if isinstance(x, dict):
            return {k: enc(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [enc(v) for v in x]
        return x
    with tempfile.TemporaryDirectory(prefix="i48_holon_") as tmp:
        res_path = Path(tmp) / "result.json"
        req = {"root": str(ROOT), "module": module, "func": func, "args": enc(list(args)), "kwargs": enc(kwargs),
               "out": str(res_path)}
        p = subprocess.run([sys.executable, "-I", "-c", _CHILD], input=json.dumps(req), capture_output=True, text=True,
                           cwd=ROOT, timeout=3600)
        if not res_path.exists():
            raise AssertionError(f"{module}.{func}: the child process wrote no result (exit {p.returncode}): "
                                 f"{p.stderr[-2000:]}")
        res = json.loads(res_path.read_text(encoding="utf-8"))
    if "error" in res:
        raise AssertionError(f"{module}.{func} raised in the child process:\n{res['error']}")
    return res["ok"]


def protocol() -> dict:
    return load_json(I.PROTOCOL)


def plan() -> dict:
    return load_json(I.CONTROLS_PLAN)


def need(p: Path):
    p = Path(p)
    if not p.exists():
        raise AssertionError(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p} is missing (I48 builds it)")
    return load_json(p)


def corpus() -> dict:
    return need(EVAL / "corpus.json")


def candidates() -> dict:
    return need(EVAL / "candidates.json")


def ev(args: list, timeout: int = 7200):
    return run_holon(["eval", *[str(a) for a in args]], timeout=timeout)


def diff_files(e: dict) -> list[str]:
    info = I.commit_info(e["repo"], e["fix_commit"], protocol())
    if not info["found"]:
        raise AssertionError(f"{e['id']}: {e['repo']}@{e['fix_commit']} is not reachable")
    return info["diff_files"]


def control_truth(tc: unittest.TestCase, c: dict, facts: dict, law: dict) -> None:
    """Rule K3 on one control's documents (the instrument's interpreter)."""
    obs = law["statement"]["claim"]["eq"][0]["obsv"]
    if c["truth"]:
        states = I.enumerate_machine(facts, {}, max_states=20000)
        tc.assertTrue(all(I.observer(facts, obs, s) for s in states), c["id"])
        tc.assertIsNotNone(I.cti(facts, obs, {}), f"{c['id']}: the claim alone is inductive")
    else:
        end = I.run_trace(facts, c["witness"])
        tc.assertIsNotNone(end, f"{c['id']}: the witness reverts")
        tc.assertFalse(I.observer(facts, obs, end))
        inputs = {}
        for a in c["witness"]:
            for k, v in a.items():
                if k != "op":
                    inputs.setdefault(a["op"], {}).setdefault(k, sorted({0, 1, v}))
        tc.assertEqual(I.shortest(facts, obs, inputs, len(c["witness"])), len(c["witness"]), c["id"])


def control_within(c: dict, facts: dict, law: dict, b: dict) -> bool:
    """Rule K4 on one control's documents: what the interpreter says within_budget is."""
    obs = law["statement"]["claim"]["eq"][0]["obsv"]
    if c["truth"]:
        return I.cti(facts, obs, I.houdini_constants(facts, b["prefixDepth"], b["maxPrefixes"])) is None
    return I.shortest(facts, obs, {}, b["prefixDepth"]) is not None


# ---------------------------------------------------------------------------------------------- the prereg's inputs
class TestPreregInstruments(unittest.TestCase):
    """Construction checks of the instruments fixed at the prereg (I48-R2; they hold before and after the build)."""

    def test_instruments_are_the_preregistered_ones(self):
        """I48-R2 (B4, MJ2, M2): every pinned instrument has the sha256 it had at the prereg (tests_m4/__init__.py,
        tests_m4/_i48.py and tests_m4/_m4.py included), and the loaded instrument, its readers and this module are the
        files on disk (integrity_problems, which setUpModule and tearDownModule also run; gap E-G7)."""
        for path, sha in sorted(PINNED.items()):
            with self.subTest(path=path):
                self.assertEqual(file_sha256(ROOT / path), sha, f"{path} changed since the prereg")
        self.assertEqual(integrity_problems(), [])
        self.assertEqual((I.SOLC_SHA256, I.GO_VERSION, I.DIFF_CAP),
                         ("fb03a29a517452b9f12bcf459ef37d0a543765bb3bbc911e70a87d6a37c30d5f",
                          "go version go1.24.7 linux/amd64", 60000))

    def test_protocol_is_well_formed(self):
        """I48-R2: n = 20, at least 3 systems and 2 non-rollup ones, caps of 8, six systems (two rollups) each with
        ordered indexes, the cutoff, the sealed and development targets excluded by repository and by subject, the
        criteria in their order (mechanical before judged), and issue only as a supplementary source."""
        p = protocol()
        self.assertEqual((p["n"], p["min_systems"], p["min_non_rollup_systems"], p["max_per_system"]), (20, 3, 2, 8))
        self.assertEqual([s["id"] for s in p["systems"]],
                         ["arbitrum", "compound", "cosmos", "go-ethereum", "optimism", "wormhole"])
        self.assertEqual(sum(s["kind"] == "rollup" for s in p["systems"]), 2)
        self.assertEqual(p["cutoff"], "2026-10-15T00:00:00Z")
        pats = [x["pattern"] for x in p["excluded_repos"]]
        self.assertEqual(pats, ["github.com/scroll-tech/", "github.com/morph-l2/"])
        self.assertEqual(p["excluded_subjects"]["subjects"],
                         ["Scroll", "scroll-tech", "ScrollChain", "scroll.io", "Morph", "morph-l2"])
        ids = [x["id"] for s in p["systems"] for x in s["indexes"]]
        self.assertEqual(len(ids), len(set(ids)))
        for s in p["systems"]:
            self.assertTrue(s["indexes"], s["id"])
            for r in s["repos"]:
                self.assertFalse(I.excluded(r, p), r)
            for x in s["indexes"]:
                self.assertTrue(x["url"].startswith("https://"), x["id"])
                self.assertIn(x["kind"], ("advisory", "audit", "postmortem", "bounty"), x["id"])
                self.assertFalse(re.search(r"scroll|morph", x["url"], re.I), x["url"])
        self.assertEqual([c["reason"] for c in p["criteria"]],
                         ["excluded_repo", "other_repo", "commit_not_found", "not_in_frontend_reach",
                          "no_public_writeup", "not_functional", "duplicate"])
        self.assertEqual(p["exclusion_reasons"], [c["reason"] for c in p["criteria"]] + ["cap_reached", "past_n"])
        self.assertIn("round robin", p["selection"].lower())
        self.assertIn("index_record", p)
        self.assertEqual(p["snapshots"]["pins"], SNAPSHOT_PINS, "M1: the snapshot pins of the prereg")
        for s in p["systems"]:
            for x in s["indexes"]:
                with self.subTest(index=x["id"]):
                    self.assertIn(x["enumeration"], ("ghsa", "geth", "folder", "page"))
                    self.assertNotIn("source", x)
                    if x["enumeration"] == "ghsa":
                        self.assertEqual(x["snapshot"], "advisory-database")
                        self.assertEqual(x["url"], I.ADVISORY_DB)
                    elif x["enumeration"] == "geth":
                        self.assertEqual(x["snapshot"], "geth-list")
                        self.assertEqual(x["url"], "https://geth.ethereum.org/docs/vulnerabilities/"
                                                   "vulnerabilities.json")
                    elif x["enumeration"] == "folder":
                        pin = I.pin_of(p, x)
                        self.assertEqual(x["snapshot"], x["id"])
                        self.assertIn(pin["repo"], s["repos"])
                        self.assertEqual(x["url"], f"{pin['repo']}/tree/{pin['branch']}/{pin['path']}")
                    else:
                        self.assertNotIn("snapshot", x)
        self.assertEqual(sorted(x["enumeration"] for s in p["systems"] for x in s["indexes"]),
                         sorted(["ghsa"] * 6 + ["geth"] + ["folder"] * 4 + ["page"] * 2))
        inv = p["labelling_invocation"]
        self.assertEqual(inv["argv"], ["claude", "-p", "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
                                       "--no-session-persistence", "--setting-sources", "", "--system-prompt",
                                       "<system_prompt>", "--model", "<model>", "--output-format", "json"])
        self.assertEqual(inv["system_prompt"], "You label software defects for an evaluation corpus. You have no "
                                               "tools. Answer only with what the prompt asks for.")
        self.assertEqual(inv["roles"], {"a": "A", "b": "B", "adjudicator": "A"})
        self.assertEqual(sorted(inv["models"]), ["A", "B"])
        self.assertEqual(inv["env_removed"], ["CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD",
                                              "CLAUDE_ADDITIONAL_DIRECTORIES"])
        self.assertEqual(inv["timeout_seconds"], 600)
        self.assertIn('tempfile.mkdtemp(prefix="label-", dir="/tmp")', inv["cwd"])
        self.assertIn("at most 5 cli_error attempts", inv["retry"])

    def test_rule_sheet_is_well_formed(self):
        """I48-R2 (M3): the nine categories, one rule each, the minimality measure and tie order, NAT's order clause,
        the output form, and what a labeller reads (title included)."""
        s = load_json(I.RULE_SHEET)
        self.assertEqual(s["categories"], CATS)
        self.assertEqual([r["id"] for r in s["rules"]], CATS)
        self.assertEqual(s["tie_order"], ["SORT", "PAR", "OWN", "FACT", "UNDO", "SYM", "NAT", "DISCH"])
        self.assertIn("count the components, carriers (registers, slots, messages, encodings) and edges", s["minimal"])
        self.assertIn("SORT (a site), PAR (a cycle), OWN (a view), FACT (a commitment), UNDO (a pair), SYM (a generator), "
                      "NAT (a migration), DISCH (a guard closure)", s["minimal"])
        nat = next(r for r in s["rules"] if r["id"] == "NAT")
        self.assertIn("every reachable order of migrations gives the same state", nat["obligation"])
        self.assertEqual(sorted(s["output"]), ["justification", "primary", "secondary", "subform"])
        self.assertIn("title", s["doc"])

    def test_schemas_parse(self):
        """Construction: the five schemas are JSON objects with a title and a type (they validate the outcome files)."""
        for n in ("candidates", "corpus", "labels", "controls", "renaming"):
            s = load_json(LIB / f"{n}.schema.json")
            self.assertEqual(s["type"], "object", n)
            self.assertTrue(s["title"], n)

    def test_reserved_names_are_well_formed(self):
        """I48-R2 (B2): the rename-reserved list holds what rule N1 (b) names, and its patterns compile."""
        r = load_json(I.RESERVED)
        go, sol = set(r["go"]["names"]), set(r["solidity"]["names"])
        self.assertTrue(r["go"]["package_clause_names"])
        self.assertLessEqual({"_", "init", "main", "C", "func", "len", "append", "nil", "iota", "error", "any"}, go)
        self.assertTrue(r["go"]["cgo_selector_names"])
        self.assertLessEqual({"_", "Error", "Panic", "length", "push", "pop", "slot", "offset", "selector", "interfaceId",
                              "wrap", "unwrap", "codehash", "encodeCall", "mload", "tload", "tstore", "mcopy",
                              "returndatacopy", "blobhash", "solidity", "abicoder", "experimental", "msg", "sender",
                              "this", "super", "keccak256", "let", "leave", "function"}, sol)
        self.assertLessEqual({"value", "gas", "salt", "error", "from", "revert", "global", "transient", "layout", "at"},
                             sol, "MJ1: call options and contextual keywords")
        names, pats = I.reserved(["solidity"])
        for x in ("uint256", "int8", "bytes32", "fixed128x18", "verbatim_1i_2o"):
            self.assertTrue(I.is_reserved(x, names, pats), x)
        self.assertFalse(I.is_reserved("reserveTotal", names, pats))

    def test_prompt_templates_render(self):
        """I48-R2 (M2): the labeller and adjudicator templates hold exactly their slots; render_prompt fills each once
        (a value is never scanned again) and parse_response reads a bare or fenced JSON answer."""
        lab = I.LABELLER_PROMPT.read_text(encoding="utf-8")
        adj = I.ADJUDICATOR_PROMPT.read_text(encoding="utf-8")
        slots = ["DESCRIPTION", "DIFF", "ENTRY", "RULE_SHEET", "SOURCES", "TITLE"]
        self.assertEqual(sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", lab))), slots)
        self.assertEqual(sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", adj))), sorted(slots + ["LABEL_A", "LABEL_B"]))
        e = {"id": "c07", "title": "T {{DIFF}}", "description": "D", "sources": [{"kind": "advisory", "url": "https://u"}]}
        p = I.render_prompt("a", e, "@@ -1 +1 @@")
        self.assertIn("Title (verbatim from its first source): T {{DIFF}}", p)
        self.assertIn("- advisory: https://u", p)
        self.assertIn(I.RULE_SHEET.read_text(encoding="utf-8"), p)
        self.assertEqual(p.count("@@ -1 +1 @@"), 1)
        lab_a = {"primary": "PAR", "secondary": None, "subform": "x", "justification": "y"}
        q = I.render_prompt("adjudicator", e, "d", {"a": lab_a, "b": dict(lab_a, primary="SORT")})
        self.assertIn('"primary": "SORT"', q)
        self.assertEqual(I.parse_response(json.dumps(lab_a)), lab_a)
        self.assertEqual(I.parse_response("```json\n" + json.dumps(lab_a) + "\n```\n"), lab_a)

    def test_prompt_diff_cap(self):
        """I48-R2 (MINOR 8): the DIFF slot holds the diff when it has at most 60000 characters; else its longest prefix
        of whole lines of at most 60000 characters and the line saying how many lines it kept."""
        self.assertEqual(I.DIFF_CAP, 60000)
        small = "@@ -1 +1 @@\n-a\n+b\n"
        self.assertEqual(I.cap_diff(small), small)
        exact = "y" * (I.DIFF_CAP - 1) + "\n"
        self.assertEqual(I.cap_diff(exact), exact)
        line = "+" + "x" * 99 + "\n"
        k = I.DIFF_CAP // len(line)
        want = line * k + f"[diff truncated by the protocol: {k} of 700 lines shown]\n"
        self.assertEqual(I.cap_diff(line * 700), want)
        self.assertEqual(I.cap_diff(line * 700 + "tail"),
                         line * k + f"[diff truncated by the protocol: {k} of 701 lines shown]\n")
        self.assertEqual(I.cap_diff("z" * (I.DIFF_CAP + 1)), "[diff truncated by the protocol: 0 of 1 lines shown]\n")
        e = {"id": "c01", "title": "T", "description": "D", "sources": [{"kind": "advisory", "url": "https://u"}]}
        prompt = I.render_prompt("b", e, line * 700)
        self.assertIn("```diff\n" + want + "\n```", prompt)
        self.assertNotIn(line * (k + 1), prompt)

    def test_attempt_outcome_on_synthetic_outputs(self):
        """I48-R2 (MJ3): the retry rule's outcome of one attempt on synthetic CLI outputs: ok, else the first failing of
        cli_error, turns, unparsable and invalid (the labels schema's label object)."""
        lab = {"primary": "PAR", "secondary": None, "subform": "x", "justification": "y z"}
        ok = {"is_error": False, "num_turns": 1, "result": json.dumps(lab), "session_id": "s", "subtype": "success"}
        nothing = {k: None for k in ok}
        cases = [(ok, "ok"), (dict(ok, result="```json\n" + json.dumps(lab) + "\n```"), "ok"),
                 (dict(ok, result=json.dumps(dict(lab, secondary="none"))), "ok"),
                 (dict(ok, is_error=True), "cli_error"), (nothing, "cli_error"), ({}, "cli_error"),
                 (dict(ok, is_error=0), "cli_error"), (dict(ok, is_error=True, num_turns=2, result="no"), "cli_error"),
                 (dict(ok, num_turns=2), "turns"), (dict(ok, num_turns=True), "turns"), (dict(ok, num_turns=None), "turns"),
                 (dict(ok, num_turns=2, result="no"), "turns"),
                 (dict(ok, result="not json"), "unparsable"), (dict(ok, result="[1]"), "unparsable"),
                 (dict(ok, result=None), "unparsable"), (dict(ok, result=""), "unparsable"),
                 (dict(ok, result=json.dumps(dict(lab, primary="XYZ"))), "invalid"),
                 (dict(ok, result=json.dumps(dict(lab, extra=1))), "invalid"),
                 (dict(ok, result=json.dumps({k: v for k, v in lab.items() if k != "subform"})), "invalid"),
                 (dict(ok, result=json.dumps(dict(lab, justification=" "))), "invalid"),
                 (dict(ok, result=json.dumps(dict(lab, secondary="NOPE"))), "invalid"),
                 (dict(ok, result=json.dumps(dict(lab, subform=None))), "invalid")]
        for cli, want in cases:
            with self.subTest(cli=cli, want=want):
                self.assertEqual(I.attempt_outcome(cli), want)

    def test_retry_rule_on_synthetic_sequences(self):
        """I48-R2 (MINOR 1): the retry rule over a prompt's attempts: a cli_error attempt is not counted (at most 5 of
        them); the attempts stop at the first ok one, the second counted one or the fifth cli_error one, and only
        there."""
        c, iv = "cli_error", "invalid"
        good = [["ok"], [iv, "ok"], ["turns", "unparsable"], [c, "ok"], [c] * 5, [iv, c, c, iv], [c] * 4 + [iv, "ok"],
                [iv] + [c] * 5, [c, iv, c, "ok"]]
        bad = [[], [iv], [c], ["ok", "ok"], [iv, iv, "ok"], [c] * 6, [c] * 4, [c] * 5 + ["ok"], ["bogus"],
               ["turns", "turns", "turns"], [iv, c] + [c] * 4 + ["ok"]]
        for seq in good:
            with self.subTest(seq=seq):
                self.assertTrue(I.retry_follows(seq))
        for seq in bad:
            with self.subTest(seq=seq):
                self.assertFalse(I.retry_follows(seq))

    def test_snapshot_rule_on_a_synthetic_graph(self):
        """I48-R2 (M1): the snapshot rule on a synthetic commit graph: walking first parents from the branch head, the
        first commit whose committer date (UTC) is before the cutoff; a commit at the cutoff is not before it, a second
        parent is never walked, and an older-dated commit further down the chain does not win; None when none is."""
        cut = protocol()["cutoff"]
        graph = {"h": {"date": "2026-10-15T08:00:00Z", "parents": ["p1", "x1"]},
                 "x1": {"date": "2026-10-14T23:59:00Z", "parents": ["p1"]},
                 "p1": {"date": "2026-10-15T00:00:00Z", "parents": ["p2"]},
                 "p2": {"date": "2026-10-15T01:30:00+02:00", "parents": ["p3"]},
                 "p3": {"date": "2026-10-14T23:45:00Z", "parents": []}}
        self.assertEqual(I.snapshot_rule(graph, "h", cut), "p2")
        self.assertEqual(I.snapshot_rule(graph, "p3", cut), "p3")
        self.assertIsNone(I.snapshot_rule({"a": {"date": "2027-01-01", "parents": []}}, "a", cut))

    def test_index_enumerators_on_synthetic_data(self):
        """I48-R2 (MJ5, MINOR 1, B2, M3, MINOR 3, MINOR 11): the mechanical index enumerators and the pre-filter on
        synthetic advisories and synthetic geth lists: owner/repo matched exactly (nitro is not nitro-contracts,
        nitrogen, nitro.github.io or nitro.gitbook; gist.github.com and notgithub.com are not github.com;
        case-insensitive, followed by the end, one of / ? # @ or .git and then one of those), withdrawn advisories,
        other folders and entries without a parsable published date left out, published in UTC before the cutoff,
        newest first with ties by GHSA id (geth: by list order), an empty summary titled by the id; geth items
        <list>#<uid> when the uids are distinct, else <list>#<position>; pre-filtered items (a Scroll subject in
        details, a morph-l2 URL in a reference) keep no title; patterns before subjects, each in protocol order; named
        commits and verbatim descriptions; the folder and page orders."""
        p = protocol()
        rev, unr = "advisories/github-reviewed/2024/01/", "advisories/unreviewed/2023/05/"

        def adv(gid, published, refs=(), pkgs=(), summary="S", **extra):
            return {"id": gid, "published": published, "summary": summary,
                    "affected": [{"package": {"ecosystem": "Go", "name": n}} for n in pkgs],
                    "references": [{"type": "WEB", "url": u} for u in refs], **extra}
        advs = [
            (rev + "GHSA-0001/GHSA-0001.json",
             adv("GHSA-0001", "2024-01-02T00:00:00Z", refs=["https://github.com/OffchainLabs/nitro-contracts/pull/1"])),
            (rev + "GHSA-0003/GHSA-0003.json",
             adv("GHSA-0003", "2024-03-01T10:00:00Z", refs=["https://github.com/OffchainLabs/nitro.git"])),
            (rev + "GHSA-0002/GHSA-0002.json", adv("GHSA-0002", "2024-03-01T10:00:00Z", pkgs=["github.com/offchainlabs/NITRO"])),
            (rev + "GHSA-0004/GHSA-0004.json",
             adv("GHSA-0004", "2024-02-01T00:00:00Z", refs=["https://github.com/OffchainLabs/nitro/commit/ab"],
                 withdrawn="2024-02-02T00:00:00Z")),
            (unr + "GHSA-0005/GHSA-0005.json",
             adv("GHSA-0005", "2023-05-01T00:00:00+02:00", summary="",
                 refs=["https://github.com/OffchainLabs/nitro/security/advisories/GHSA-0005"],
                 details="The same bug also hits Scroll's sequencer.")),
            (unr + "GHSA-0006/GHSA-0006.json",
             adv("GHSA-0006", "2023-04-01T00:00:00Z",
                 refs=["https://github.com/OffchainLabs/nitro?tab=x", "https://github.com/morph-l2/go-ethereum/pull/2"])),
            (unr + "GHSA-0007/GHSA-0007.json",
             adv("GHSA-0007", "2023-03-01T00:00:00Z", refs=["https://github.com/OffchainLabs/nitro#readme"], summary=" ")),
            (rev + "GHSA-0008/GHSA-0008.json", adv("GHSA-0008", "2026-10-15T00:00:00Z", refs=["https://github.com/OffchainLabs/nitro"])),
            (rev + "GHSA-0009/GHSA-0009.json",
             adv("GHSA-0009", "2026-10-14T23:59:59Z", refs=["https://github.com/OffchainLabs/nitro@v1"])),
            (rev + "GHSA-0010/GHSA-0010.json", adv("GHSA-0010", "2024-01-01T00:00:00Z", refs=["https://github.com/OffchainLabs/nitrogen"])),
            ("advisories/other/GHSA-0011.json", adv("GHSA-0011", "2024-01-01T00:00:00Z", refs=["https://github.com/OffchainLabs/nitro"])),
        ]
        url = "https://github.com/advisories/"
        got = I.ghsa_items_from(advs, ["https://github.com/OffchainLabs/nitro"], p)
        self.assertEqual(got, [
            {"item": url + "GHSA-0009", "published": "2026-10-14", "title": "S", "excluded_by": None},
            {"item": url + "GHSA-0002", "published": "2024-03-01", "title": "S", "excluded_by": None},
            {"item": url + "GHSA-0003", "published": "2024-03-01", "title": "S", "excluded_by": None},
            {"item": url + "GHSA-0005", "published": "2023-04-30", "title": None, "excluded_by": {"subject": "Scroll"}},
            {"item": url + "GHSA-0006", "published": "2023-04-01", "title": None,
             "excluded_by": {"pattern": "github.com/morph-l2/"}},
            {"item": url + "GHSA-0007", "published": "2023-03-01", "title": "GHSA-0007", "excluded_by": None}])
        got = I.ghsa_items_from(advs, ["https://github.com/OffchainLabs/nitro-contracts"], p)
        self.assertEqual([x["item"] for x in got], [url + "GHSA-0001"])
        self.assertEqual(I.prefilter({"a": "a scroll-tech fork", "b": ["https://github.com/Scroll-Tech/x"]}, p),
                         {"pattern": "github.com/scroll-tech/"})
        self.assertEqual(I.prefilter({"a": ["Morph and the ScrollChain contract"]}, p), {"subject": "ScrollChain"})
        self.assertEqual(I.prefilter({"a": "see scroll.io"}, p), {"subject": "Scroll"})   # Scroll comes first
        for clean in ({"a": "scrolling down"}, {"a": "scrollXio"}, {"a": "metamorphosis"}, {"Scroll": 1}):
            self.assertIsNone(I.prefilter(clean, p), clean)
        geth = json.dumps([
            {"name": "A", "published": "2021-01-01", "links": ["https://x.example/a"]},
            {"name": "B", "published": "2022-05-05", "links": []},
            {"name": "C", "published": "2021-01-01", "links": ["https://x.example/c"], "description": "also morph-l2"},
            {"name": "D", "published": "2026-10-15", "links": ["https://x.example/d"]}]).encode()
        lst = "https://geth.ethereum.org/docs/vulnerabilities/vulnerabilities.json"
        self.assertEqual(I.geth_items_from(geth, p, lst), [
            {"item": lst + "#2", "published": "2022-05-05", "title": "B", "excluded_by": None},
            {"item": lst + "#1", "published": "2021-01-01", "title": "A", "excluded_by": None},
            {"item": lst + "#3", "published": "2021-01-01", "title": None, "excluded_by": {"subject": "Morph"}}])
        uid = [{"uid": "GETH-1", "name": "A", "published": "2021-01-01", "links": ["https://x.example/a"]},
               {"uid": "GETH 2", "name": "B", "published": "2022-01-01", "links": ["https://x.example/a"]},
               {"uid": "GETH-3", "name": "C", "published": "soon"}]
        self.assertEqual([x["item"] for x in I.geth_items_from(json.dumps(uid).encode(), p, lst)],
                         [lst + "#GETH%202", lst + "#GETH-1"])
        dup = [dict(uid[0]), dict(uid[1], uid="GETH-1")]
        self.assertEqual([x["item"] for x in I.geth_items_from(json.dumps(dup).encode(), p, lst)],
                         [lst + "#2", lst + "#1"])
        nameless = [{"uid": "GETH-1", "published": "2021-01-01", "links": []}]
        with self.assertRaises(AssertionError):
            I.geth_items_from(json.dumps(nameless).encode(), p, lst)
        nitro = "https://github.com/OffchainLabs/nitro"
        undated = [(rev + "GHSA-0012/GHSA-0012.json",
                    {"id": "GHSA-0012", "summary": "S", "references": [{"url": nitro}]}),
                   (rev + "GHSA-0013/GHSA-0013.json", adv("GHSA-0013", "yesterday", refs=[nitro]))]
        self.assertEqual(I.ghsa_items_from(undated, [nitro], p), [])
        slug, gh = "github.com/offchainlabs/nitro", "github.com/OffchainLabs/nitro"
        for text, want in [(gh, True), (f"https://{gh}.git", True), (f"git+https://{gh}.git#v1", True),
                           (f"https://{gh}@v1", True), (f"https://{gh}.github.io", False),
                           (f"https://{gh}.gitbook", False), (f"https://gist.{gh}", False), (f"https://not{gh}", False),
                           (f"https://{gh}-contracts", False), (f"https://gist.{gh} and https://{gh}/pull/1", True)]:
            with self.subTest(text=text):
                self.assertEqual(I.names_repo(text, slug), want)
        doc = {"references": [{"url": nitro + "/commit/" + "A" * 40},
                              {"url": f"https://{slug}/commit/" + "b" * 40 + "#diff-1"},
                              {"url": nitro + "-contracts/commit/" + "c" * 40}, {"url": nitro + "/commit/" + "d" * 41},
                              {"url": f"https://gist.{gh}/commit/" + "e" * 40},
                              {"url": nitro + "/pull/1/commits/" + "f" * 40}, {"url": nitro + "/commit/" + "a" * 40}]}
        self.assertEqual(I.named_commits(doc, [nitro]), [(nitro, "a" * 40), (nitro, "b" * 40)])
        geth_repo = "https://github.com/ethereum/go-ethereum"
        links = {"links": [geth_repo + "/commit/" + "1" * 40, "https://x.example"]}
        self.assertEqual(I.named_commits(links, [geth_repo]), [(geth_repo, "1" * 40)])
        g = {"details": "A  bug\n in the   thing.", "summary": "Sum"}
        self.assertTrue(I.description_ok("bug in the", g, "ghsa"))
        for bad in ("bug  in", "", " bug", "Sum", "x" * 2001):
            self.assertFalse(I.description_ok(bad, g, "ghsa"), bad)
        self.assertTrue(I.description_ok("Sum", dict(g, details=" \n"), "ghsa"))
        self.assertTrue(I.description_ok("text", {"description": "", "summary": "Sum text"}, "geth"))
        self.assertFalse(I.description_ok("text", {"description": "other", "summary": "Sum text"}, "geth"))
        paths = ["docs/audits/README.md", "docs/audits/2023 ToB.pdf", "docs/audits/sub/x.MD", "docs/audits/sub/ReadMe.md",
                 "docs/auditsX/y.pdf", "docs/audits/notes.txt", "other/z.pdf"]
        sha = "a" * 40
        self.assertEqual(I.folder_items_from(paths, "https://github.com/o/r", sha, "docs/audits"),
                         [f"https://github.com/o/r/blob/{sha}/docs/audits/2023%20ToB.pdf",
                          f"https://github.com/o/r/blob/{sha}/docs/audits/sub/x.MD"])
        its = [{"item": "https://b", "published": "2024-01-01"}, {"item": "https://a", "published": "2024-01-01"},
               {"item": "https://c", "published": "2025-01-01"}]
        self.assertEqual([x["item"] for x in I.items_order(its)], ["https://c", "https://a", "https://b"])

    def test_old_lines_from_a_synthetic_diff(self):
        """I48-R2 (MINOR 2): the pre-fix lines a -U0 diff deletes or changes; a pure insertion contributes nothing."""
        diff = ("diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -3 +3 @@\n-x\n+y\n@@ -10,2 +9,0 @@\n-a\n-b\n"
                "@@ -20,0 +19,3 @@\n+c\n+d\n+e\n@@ -0,0 +1 @@\n+top\n@@ -30,2 +32 @@\n-p\n-q\n+r\n")
        self.assertEqual(I.old_lines_from_diff(diff), [3, 10, 11, 30, 31])

    def test_kappa_instrument(self):
        """Construction: the instrument's kappa on textbook cases: perfect agreement over two used categories gives 1;
        agreement equal to chance gives 0; kappa is None (undefined) with no item or with chance agreement 1."""
        k = I.kappa(["PAR", "PAR", "SORT", "SORT"], ["PAR", "PAR", "SORT", "SORT"], CATS)
        self.assertAlmostEqual(k["kappa"], 1.0)
        k = I.kappa(["PAR", "PAR", "SORT", "SORT"], ["PAR", "SORT", "PAR", "SORT"], CATS)
        self.assertAlmostEqual(k["kappa"], 0.0)
        self.assertAlmostEqual(k["se"], 0.5)
        self.assertIsNone(I.kappa([], [], CATS)["kappa"])
        self.assertIsNone(I.kappa(["PAR", "PAR"], ["PAR", "PAR"], CATS)["kappa"])

    def test_selection_instrument_on_a_synthetic_list(self):
        """Construction: rule C4 on a synthetic candidate list: round robin over the systems in the protocol's order,
        newest fix first within a system, caps per system, n in total, ineligible candidates after the eligible ones
        with their own reason."""
        p = dict(protocol(), n=3, max_per_system=2, systems=[{"id": "a"}, {"id": "b"}, {"id": "c"}])
        mk = lambda sid, i, d, el=True, why=None: {"id": f"{sid}:{i:03d}", "system": sid, "eligible": el,
                                                    "reason": why, "fix_date": d, "fix_commit": f"{i:040x}"}
        cs = [mk("a", 1, "2024-01-01T00:00:00Z"), mk("a", 2, "2024-03-01T00:00:00Z"), mk("a", 3, "2024-02-01T00:00:00Z"),
              mk("b", 1, "2023-01-01T00:00:00Z"), mk("b", 2, "2022-01-01T00:00:00Z"),
              mk("c", 1, None, False, "commit_not_found")]
        self.assertEqual(I.select(cs, p), [("a:002", "c01", None), ("b:001", "c02", None), ("a:003", "c03", None),
                                           ("a:001", None, "cap_reached"), ("b:002", None, "past_n"),
                                           ("c:001", None, "commit_not_found")])
        p = dict(p, n=4, max_per_system=8)
        self.assertEqual([x for x in I.select(cs, p) if x[1]],
                         [("a:002", "c01", None), ("b:001", "c02", None), ("a:003", "c03", None), ("b:002", "c04", None)])

    def test_controls_plan_expands_to_fourteen(self):
        """Construction (I48-R4's values): the plan expands to 14 controls; within the budget: depth 1 and 2 (witnesses
        of 2 and 3 actions, prefixDepth 3), value 1 (input domain [0, 1]) and both constant controls; expected outcomes
        REFUTED 3, PROVED 2, UNKNOWN 9; law ids match holon-ir/0.3's pattern; the run budgets I53 passes."""
        pl = plan()
        cs = I.controls(pl)
        self.assertEqual([c["id"] for c in cs],
                         ["depth_1", "depth_2", "depth_4", "depth_8", "depth_16", "value_1", "value_2", "value_7",
                          "value_1000", "relational_1", "relational_2", "relational_4", "constant_1", "constant_3"])
        self.assertEqual(sorted(c["id"] for c in cs if c["within_budget"]),
                         ["constant_1", "constant_3", "depth_1", "depth_2", "value_1"])
        self.assertEqual(Counter(c["expected"] for c in cs), Counter({"UNKNOWN": 9, "REFUTED": 3, "PROVED": 2}))
        pat = load_json(LAW_SCHEMA)["properties"]["law_id"]["pattern"]
        for c in cs:
            self.assertRegex(c["law_id"], pat)
        self.assertEqual(pl["budgets"]["run"], {"prefixDepth": 3, "suffixDepth": 4, "natMax": 5, "maxPrefixes": 3000,
                                                "maxNodes": 400000, "reach_max_tries": 120})

    def test_controls_plan_names_its_sizing_sources(self):
        """I48-R4 (MINOR 4): the plan records the sha256 at this base of the files the sizing rests on and the rule I53
        applies to them; I48 checks only that the files exist and the values are sha256 (I47 may change the files)."""
        pl = plan()
        self.assertEqual(sorted(pl["sizing_sources"]), ["holon/gen/mproofs.py", "holon/js/explore.mjs",
                                                        "holon/js/houdini.mjs", "holon/js/policy_gen.mjs",
                                                        "holon/mpipeline.py"])
        for f, h in sorted(pl["sizing_sources"].items()):
            with self.subTest(path=f):
                self.assertTrue((ROOT / f).is_file(), f)
                self.assertRegex(h, r"^[0-9a-f]{64}$")
        self.assertIn("I53 asserts these sha256", pl["sizing_sources_rule"])

    def test_controls_plan_agrees_with_the_interpreter(self):
        """Construction (K2-K4 on the instrument's own documents): every law validates against the IR 0.3 schema; each
        false control's witness is a shortest violating trace; each true control holds on its finite reachable set and
        is not inductive alone; within_budget is the interpreter's (shortest within prefixDepth; no counterexample to
        induction with houdini's constants)."""
        pl = plan()
        b = pl["budgets"]
        for c in I.controls(pl):
            with self.subTest(control=c["id"]):
                facts, law = I.expected_documents(c, pl)
                self.assertEqual(validate(law, LAW_SCHEMA), [])
                self.assertNotIn("search", facts)
                control_truth(self, c, facts, law)
                self.assertEqual(control_within(c, facts, law, b), c["within_budget"])

    def test_go_printer_flags_injected_changes(self):
        """Construction (B3, MINOR 5): the Go printer accepts a correct renaming of a file and flags each injected
        change: call nesting, operator, assignment token, slice bounds, channel direction, a moved or dropped directive,
        a changed cgo preamble, a struct tag; its comment listing marks the kept comments; the cgo preamble is read as
        cmd/cgo reads it (the declaration's doc comment when it holds exactly one spec, parenthesised or not)."""
        tmp = Path(tempfile.mkdtemp(prefix="i48_go_"))
        try:
            ren = {"helper": "vaaaaaaaaaa", "total": "vbbbbbbbbbb", "dx": "vcccccccccc"}
            renamed = _GO_SRC
            for old, new in ren.items():
                renamed = re.sub(rf"\b{old}\b", new, renamed)
            renamed = renamed.replace("// Package p is a test.\n", "").replace(" // coords", "") \
                .replace("/* two\n\t   lines */", "\n")
            (tmp / "a.go").write_text(_GO_SRC)
            (tmp / "b.go").write_text(renamed)
            a, b = I.go_ast(tmp / "a.go"), I.go_ast(tmp / "b.go")
            self.assertEqual(I.map_go_ast(a, ren), b)
            kept = [t for _, t, k in I.go_comments(tmp / "a.go") if k]
            self.assertEqual(kept, ["//go:build linux", "/*\n#include <stdlib.h>\n*/", "//go:embed data.txt"])
            self.assertEqual(I.go_facts(a)["package"], "p")
            for name, imp, kept in [("one spec in parentheses", 'import (\n\t"C"\n)', True),
                                    ("two specs", 'import (\n\t"C"\n\t"fmt"\n)', False)]:
                with self.subTest(preamble=name):
                    (tmp / "d.go").write_text("package d\n\n/*\n#include <stdio.h>\n*/\n" + imp + "\n")
                    self.assertEqual([k for _, _, k in I.go_comments(tmp / "d.go")], [kept])
                    self.assertEqual(any(x.startswith("CgoPreamble ") for x in I.go_ast(tmp / "d.go")), kept)
            for old, new in [("f(g(1), 2)", "f(g(1, 2))"), ("vbbbbbbbbbb = a + b", "vbbbbbbbbbb = a - b"),
                             ("x := []int{1, 2}", "x = []int{1, 2}"), ("x[1:]", "x[:1]"),
                             ("chan<- int", "<-chan int"), ("//go:embed data.txt\n", ""),
                             ("#include <stdlib.h>", "#include <stdio.h>"), ('`json:"y"`', '`json:"z"`')]:
                with self.subTest(change=old):
                    self.assertIn(old, renamed)
                    (tmp / "c.go").write_text(renamed.replace(old, new, 1))
                    self.assertNotEqual(I.map_go_ast(a, ren), I.go_ast(tmp / "c.go"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_n1_go_cases(self):
        """I48-R2 (MJ1): rule N1 on Go: in a file importing "C", a declared name that is also a C.X selector is
        reserved (free) while plain names are renamed (release, p); a name declared in the set and used in a sibling
        file outside it is blocked although it is not ASCII (pi, a Unicode word); a name whose first character is an
        upper-case non-ASCII letter is exported; words and new_names are Unicode-aware."""
        self.assertLessEqual({"x", "π", "naïve", "na", "ve", "x$y"}, I.words("x := π + naïve // x$y".encode()))
        self.assertEqual(I.words(b"\xff\xfeab"), {"ab"})
        self.assertEqual(I.words("3² Ω".encode()), {"3", "Ω"})
        self.assertTrue(I.upper_initial("Ωmega") and not I.upper_initial("πx") and not I.upper_initial("_X"))
        self.assertTrue(I.new_names("s", ["Ωmega"], set())["Ωmega"].startswith("V"))
        self.assertTrue(I.new_names("s", ["πx"], set())["πx"].startswith("v"))
        p = protocol()
        tmp = Path(tempfile.mkdtemp(prefix="i48_n1go_"))
        try:
            (tmp / "cg").mkdir()
            (tmp / "cg" / "a.go").write_text('package cg\n\n/*\n#include <stdlib.h>\n*/\nimport "C"\n\nimport "unsafe"\n\n'
                                             'func release(p unsafe.Pointer) {\n\tfree := 1\n\t_ = free\n\tC.free(p)\n}\n')
            nf = I.n1_facts(tmp, ["cg/a.go"], p)
            self.assertEqual(nf["expected"], {"p", "release"})
            self.assertIn("free", nf["reserved"][0])
            (tmp / "pk").mkdir()
            (tmp / "pk" / "a.go").write_text("package pk\n\nconst π = 3\n\nconst Ωmega = 4\n\n"
                                             "func twice() int { return 2 * π * Ωmega }\n")
            (tmp / "pk" / "b.go").write_text("package pk\n\nfunc three() int { return π }\n")
            self.assertEqual(I.n1_facts(tmp, ["pk/a.go"], p)["expected"], {"twice"})
            (tmp / "pk" / "b.go").write_text("package pk\n")
            self.assertEqual(I.n1_facts(tmp, ["pk/a.go"], p)["expected"], {"twice", "π"})
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


_GO_SRC = """//go:build linux

// Package p is a test.
package p

/*
#include <stdlib.h>
*/
import "C"

//go:embed data.txt
var blob string

type pt struct {
	x, y int // coords
	z    int `json:"y"`
}

func f(a, b int) int { return a }
func g(a ...int) int  { return 0 }

func helper(a, b int, dx int) (total int) {
	/* two
	   lines */
	total = a + b
	x := []int{1, 2}
	_ = x[1:]
	_ = f(g(1), 2)
	_ = make(chan<- int)
	return total + dx
}
"""


class TestSolidityInstrument(unittest.TestCase):
    """Construction checks of the Solidity half of rule N3's instrument (I48-R2); they need the pinned solc
    (tools/setup_env.sh --solc, or HOLON_SOLC), which the build installs: until then they fail naming it."""

    def test_solidity_checks_flag_injected_changes(self):
        """Construction (B1): a correct renaming passes the token and AST checks; each injected change is flagged by
        one of them (operator, hex literal, a dropped @solidity or @custom: comment, the version pragma, visibility, a
        member name, Yul arguments); old pragmas are neutralised; the AST reader finds the ABI-visible, override and
        declared names."""
        tmp = Path(tempfile.mkdtemp(prefix="i48_sol_"))
        try:
            ren = {"reserveTotal": "v1111111111", "delta": "v2222222222", "ptr": "v3333333333", "Pos": "V4444444444",
                   "amt": "v5555555555", "credits": "v6666666666"}
            src = _SOL_SRC
            toks = I.sol_lex(src)
            out, last = [], 0
            for k, t, s, e in toks:
                if (k == "id" and t in ren) or (k == "comment" and not I.sol_kept(t)):
                    out += [src[last:s], ren[t] if k == "id" else I.replaced_by(t)]
                    last = e
            renamed = "".join(out) + src[last:]
            (tmp / "A.sol").write_text(src)
            (tmp / "B.sol").write_text(renamed)
            a, b = I.sol_ast(tmp / "A.sol"), I.sol_ast(tmp / "B.sol")
            self.assertIsNotNone(a)
            self.assertEqual(I.map_sol_ast(a, ren), b)
            self.assertEqual(I.sol_tokens(src, ren), I.sol_tokens(renamed))
            f = I.sol_facts(a)
            self.assertEqual(f["abi"], {"credit", "Credited", "Bad", "pub"})
            self.assertEqual(f["override"], {"_hook"})
            self.assertLessEqual({"reserveTotal", "credits", "Pos", "amt", "ptr", "dbl", "Phase", "Open"}, f["decls"])
            for old, new in [("+= ", "-= "), ('hex"00ff"', 'hex"00fe"'), ("/// @solidity memory-safe-assembly\n", ""),
                             ("/// @custom:security-contact x@example.org\n", ""), ("^0.8.20", "^0.8.21"),
                             ("external {", "public {"), ("xs.length", "xs.lngth"), ("tstore(0, 1)", "tstore(1, 0)")]:
                with self.subTest(change=old):
                    self.assertIn(old, renamed)
                    m = renamed.replace(old, new, 1)
                    (tmp / "C.sol").write_text(m)
                    c = I.sol_ast(tmp / "C.sol")
                    self.assertTrue(I.sol_tokens(src, ren) != I.sol_tokens(m) or I.map_sol_ast(a, ren) != c)
            old_src = "pragma solidity ^0.5.16;\ncontract O { uint public x; function f() external { x = now; } }\n"
            (tmp / "O.sol").write_text(old_src)
            self.assertIsNotNone(I.sol_ast(tmp / "O.sol"))
            self.assertTrue(I.sol_neutralise(old_src).startswith("pragma solidity >=0.0.0;\n"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_n1_solidity_cases(self):
        """I48-R2 (MJ1, MINOR 2, MINOR 4): rule N1 on Solidity: a local named salt used as the call option {salt: salt}
        is not renamed; a local named error beside an error definition is not renamed; a dotted (pre-0.7) Yul name is
        never renamed; a .sol file of the set that the pinned solc cannot parse blocks every word it holds (N1 (e)), so
        the renamed set stays exact."""
        p = protocol()
        head = "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.24;\n"
        cases = {
            "salt": ({"S.sol": head + "contract Child { constructor(uint256 n) {} }\ncontract F {\n"
                               "    function make(uint256 n) internal returns (address) {\n"
                               "        bytes32 salt = bytes32(n);\n        return address(new Child{salt: salt}(n));\n"
                               "    }\n}\n"}, ["S.sol"], {"Child", "F", "make", "n"}),
            "error": ({"E.sol": head + "contract G {\n    error Bad(uint256 code);\n"
                                "    function f(uint256 x) internal pure returns (uint256) {\n"
                                "        uint256 error = x + 1;\n        return error;\n    }\n}\n"},
                      ["E.sol"], {"G", "f", "x"}),
            "dotted": ({"D.sol": "pragma solidity ^0.5.16;\ncontract D { function f() internal pure { uint256 keep; "
                                 "assembly { let a.b := 1 } keep = 2; } }\n"}, ["D.sol"], {"D", "f", "keep"}),
            "unparsed": ({"P.sol": head + "contract P { uint256 internal total; uint256 internal other; }\n",
                          "U.sol": "pragma solidity ^0.5.16;\ncontract U { uint total; function () external payable "
                                   "{ total = 1; } }\n"}, ["P.sol", "U.sol"], {"P", "other"}),
        }
        for name, (files, sset, want) in cases.items():
            tmp = Path(tempfile.mkdtemp(prefix="i48_n1sol_"))
            try:
                for f, text in files.items():
                    (tmp / f).write_text(text)
                with self.subTest(case=name):
                    nf = I.n1_facts(tmp, sset, p)
                    self.assertEqual(nf["expected"], want)
                    self.assertEqual(nf["unparsed"], ["U.sol"] if name == "unparsed" else [])
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


_SOL_SRC = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title Vault
/// @custom:security-contact x@example.org
contract Vault {
    struct Pos { uint256 amt; address who; }
    enum Phase { Open, Closed }
    mapping(address => Pos) internal credits;
    uint256 internal reserveTotal;
    uint256 public pub;
    event Credited(address who, uint256 delta);
    error Bad(uint256 code);
    function _hook() internal virtual {}
    function credit(uint256 delta) external {
        /* add */ credits[msg.sender].amt += delta;
        reserveTotal = reserveTotal + delta * 2 ** 3;
        uint256[] memory xs = new uint256[](2);
        xs[0] = xs.length;
        bytes memory h = hex"00ff";
        /// @solidity memory-safe-assembly
        assembly {
            let ptr := mload(0x40)
            function dbl(v) -> r { r := add(v, v) }
            mstore(ptr, dbl(sload(reserveTotal.slot)))
            tstore(0, 1)
        }
        emit Credited(msg.sender, delta);
    }
}
contract Child is Vault { function _hook() internal override {} }
"""


# ---------------------------------------------------------------------------------------------- the candidates
class TestCandidates(unittest.TestCase):
    def test_candidates_validate_and_follow_the_protocol(self):
        """I48-R1 (C1, C2; B1, M1, M3, MINOR 6, MINOR 8): spec/eval/candidates.json validates and names the protocol's
        sha256; one fresh collector per system; one index record per index in the protocol's order, a git snapshot
        exactly its pin; its items without duplicates (ghsa, geth and page items before the cutoff, folder items at
        most the snapshot's committer date; folder and page items in items_order; a pre-filtered item without a title;
        an audit item's findings recorded exactly when it was examined, with a note exactly when 0), examined within
        the list and following the stop rule; ids <system>:<rank, at least three digits> with ranks 1.. without gaps,
        candidates in items order from items[:examined] only: a mechanical item yields exactly one candidate (the
        item's published and title), an audit item exactly findings candidates (the stopping item 1 to findings);
        the first source is the item and no other source holds an excluded pattern; excluded_repo exactly when the repo
        or the item holds a pattern or an opened item's title or description names a subject, an opened mechanical
        item only by its repo, and a candidate without title or description only when unopened and excluded by a
        pattern; repositories, other_repo and duplicates as the protocol says."""
        c, p = candidates(), protocol()
        self.assertEqual(validate(c, LIB / "candidates.schema.json"), [])
        self.assertEqual(c["protocol_sha256"], file_sha256(I.PROTOCOL))
        sids = [s["id"] for s in p["systems"]]
        self.assertEqual(sorted(x["system"] for x in c["collectors"]), sorted(sids))
        self.assertEqual(len({x["agent"] for x in c["collectors"]}), len(sids))
        self.assertEqual(sorted(s["id"] for s in c["systems"]), sorted(sids))
        self.assertEqual([(r["system"], r["index"]) for r in c["indexes"]],
                         [(s["id"], x["id"]) for s in p["systems"] for x in s["indexes"]])
        recs = {(r["system"], r["index"]): r for r in c["indexes"]}
        cut = p["cutoff"][:10]
        for s in p["systems"]:
            for x in s["indexes"]:
                r = recs[(s["id"], x["id"])]
                snap, items, kind = r["snapshot"], r["items"], x["enumeration"]
                with self.subTest(index=x["id"]):
                    if kind == "page":
                        self.assertEqual(snap["kind"], "page")
                    else:
                        pin = I.pin_of(p, x)
                        want = {"kind": "git", "repo": pin["repo"], "commit": pin["commit"]}
                        self.assertEqual(snap, dict(want, path=pin["path"]) if "path" in pin else want, "M1: the pin")
                    self.assertLessEqual(r["examined"], len(items))
                    self.assertEqual(len({it["item"] for it in items}), len(items), "an item listed twice")
                    for k, it in enumerate(items):
                        if kind == "folder":
                            self.assertLessEqual(it["published"], I.pin_of(p, x)["committer_date"][:10], it["item"])
                        else:
                            self.assertLess(it["published"], cut, it["item"])
                        if kind in ("ghsa", "geth"):
                            self.assertIn("excluded_by", it)
                            self.assertEqual(it["title"] is None, it["excluded_by"] is not None, it["item"])
                        else:
                            self.assertIn("findings", it)
                            if k < r["examined"]:
                                self.assertIsInstance(it["findings"], int, f"{it['item']}: examined, so findings")
                                self.assertEqual(it["note"] is not None, it["findings"] == 0,
                                                 f"{it['item']}: a note exactly when findings is 0")
                            else:
                                self.assertEqual((it["findings"], it["note"]), (None, None), it["item"])
                    if kind in ("folder", "page"):
                        self.assertEqual(items, I.items_order(items), "items order: published newest first, then item")
        stopped = {s["id"]: (s["examined"], s["stopped"]) for s in c["systems"]}
        by = {x["id"]: x for x in c["candidates"]}
        for sid in sids:
            sysd = I.system_of(p, sid)
            idx = [x["id"] for x in sysd["indexes"]]
            kinds = {x["id"]: x["enumeration"] for x in sysd["indexes"]}
            mine = sorted((x for x in c["candidates"] if x["system"] == sid), key=lambda x: x["rank"])
            with self.subTest(system=sid):
                self.assertEqual([x["rank"] for x in mine], list(range(1, len(mine) + 1)))
                self.assertEqual(stopped[sid][0], len(mine))
                pos, per = [], {i: [] for i in idx}
                for x in mine:
                    self.assertEqual(x["id"], f"{sid}:{x['rank']:03d}")
                    self.assertIn(x["index"], idx, x["id"])
                    r = recs[(sid, x["index"])]
                    urls = [it["item"] for it in r["items"]]
                    self.assertIn(x["item"], urls[:r["examined"]], f"{x['id']}: not an examined item of its index")
                    k = urls.index(x["item"])
                    it = r["items"][k]
                    pos.append((idx.index(x["index"]), k))
                    per[x["index"]].append(x)
                    self.assertEqual(x["published"], it["published"], x["id"])
                    self.assertTrue(x["sources"] and x["sources"][0]["url"] == x["item"], x["id"])
                    self.assertIsNone(I.pattern_in([y["url"] for y in x["sources"][1:]], p),
                                      f"{x['id']}: a source holds an excluded pattern")
                    mech = kinds[x["index"]] in ("ghsa", "geth")
                    pre = mech and it["excluded_by"] is not None
                    texts = [t for t in (x["title"], x["description"]) if t is not None]
                    if pre:
                        self.assertEqual((x["reason"], x["excluded_by"], x["title"], x["description"], x["repo"]),
                                         ("excluded_repo", it["excluded_by"], None, None, None), x["id"])
                    else:
                        if x["title"] is None or x["description"] is None:
                            self.assertEqual(x["reason"], "excluded_repo", f"{x['id']}: no title or description")
                            self.assertIn("pattern", x["excluded_by"], f"{x['id']}: unopened, so excluded by a pattern")
                        if mech and x["title"] is not None:
                            self.assertEqual(x["title"], it["title"], x["id"])
                        if x["description"] is not None:
                            self.assertEqual(x["description"], I.collapse(x["description"]), x["id"])
                            self.assertTrue(0 < len(x["description"]) <= 2000, x["id"])
                    locs = [u for u in (x["repo"], x["item"]) if u]
                    if I.pattern_in(locs, p) or (not pre and I.subject_in(texts, p)):
                        self.assertEqual(x["reason"], "excluded_repo", f"{x['id']}: names an excluded repo or subject")
                    if x["reason"] == "excluded_repo" and not pre:
                        eb = x["excluded_by"]
                        if mech:
                            self.assertIn("pattern", eb, f"{x['id']}: an opened mechanical item, excluded by its repo")
                            self.assertIn(eb["pattern"].lower(), (x["repo"] or "").lower(), x["id"])
                        elif "pattern" in eb:
                            self.assertTrue(any(eb["pattern"].lower() in u.lower() for u in locs), x["id"])
                        else:
                            one = dict(p, excluded_subjects={"subjects": [eb["subject"]]})
                            self.assertEqual(I.subject_in(texts, one), eb["subject"], x["id"])
                    if x["reason"] not in ("excluded_repo", "other_repo"):
                        self.assertIn(x["repo"], sysd["repos"], x["id"])
                    if x["reason"] == "other_repo":
                        self.assertIsInstance(x["repo"], str, x["id"])
                        self.assertNotIn(x["repo"], sysd["repos"], x["id"])
                        self.assertFalse(I.excluded(x["repo"], p), x["id"])
                    if x["reason"] == "duplicate":
                        k = by.get(x["duplicate_of"])
                        self.assertTrue(k and k["system"] == sid and k["reason"] != "duplicate", x["id"])
                        if k["fix_date"] and x["fix_date"]:
                            self.assertLessEqual((k["fix_date"], k["rank"]), (x["fix_date"], x["rank"]), x["id"])
                self.assertEqual(pos, sorted(pos), "examination order: index order, then items order")
                elig = sum(x["eligible"] for x in mine)
                self.assertLessEqual(elig, p["max_per_system"])
                last = mine[-1] if mine and stopped[sid][1] == "eighth_eligible" else None
                for i in idx:
                    r = recs[(sid, i)]
                    seen = [x["item"] for x in per[i]]
                    head = r["items"][:r["examined"]]
                    if kinds[i] in ("ghsa", "geth"):
                        self.assertEqual(seen, [it["item"] for it in head], f"{i}: one candidate per examined item")
                        continue
                    for it in head:
                        n = seen.count(it["item"])
                        if last is not None and (last["index"], last["item"]) == (i, it["item"]):
                            self.assertTrue(1 <= n <= it["findings"], f"{it['item']}: the stopping item yields "
                                                                       f"1 to findings candidates")
                        else:
                            self.assertEqual(n, it["findings"], f"{it['item']}: one candidate per finding")
                lens = [len(recs[(sid, i)]["items"]) for i in idx]
                got = [recs[(sid, i)]["examined"] for i in idx]
                if last is not None:
                    self.assertTrue(elig == p["max_per_system"] and last["eligible"], "stopped at the 8th eligible")
                    k, j = pos[-1]
                    self.assertEqual(got, lens[:k] + [j + 1] + [0] * (len(idx) - k - 1), "examined: the stop rule")
                else:
                    self.assertLess(elig, p["max_per_system"], "exhausted with 8 eligible: the stop rule was missed")
                    self.assertEqual(got, lens, "an exhausted system examines every item")

    def test_indexes_are_the_snapshots(self):
        """I48-R1 (C2, MJ5, M1): every git index is read at its pin, reachable from the pinned branch (the geth list's
        file with the pinned sha256), and its items are what the pin holds: ghsa and geth exactly the instrument's list
        recomputed at the pin (tests_m4/_i48.py::index_items), folder exactly the folder's reports there
        (folder_items). Page snapshots cannot be fetched again (gap E-G1)."""
        c, p = candidates(), protocol()
        recs = {(r["system"], r["index"]): r for r in c["indexes"]}
        for s in p["systems"]:
            for x in s["indexes"]:
                with self.subTest(index=x["id"]):
                    r = recs.get((s["id"], x["id"]))
                    self.assertIsNotNone(r, f"no index record for {x['id']}")
                    if x["enumeration"] == "page":
                        continue
                    pin = I.pin_of(p, x)
                    self.assertEqual((r["snapshot"]["repo"], r["snapshot"]["commit"]), (pin["repo"], pin["commit"]))
                    if x["enumeration"] in ("ghsa", "geth"):
                        self.assertEqual(r["items"], I.index_items(s, x, p))
                    else:
                        self.assertEqual(sorted(it["item"] for it in r["items"]), I.folder_items(pin))

    def test_mechanical_candidates_are_their_items(self):
        """I48-R1 (M3): every opened candidate of a mechanical index has its item's verbatim description
        (tests_m4/_i48.py::description_ok: the advisory's details or the geth entry's description, each its summary
        when blank) and, when its item names a commit of the system's repositories reachable from a branch or tag, the
        fix commit of the exact rule (named_fix: the earliest such commit by committer date) in that repository."""
        c, p = candidates(), protocol()
        for s in p["systems"]:
            for x in s["indexes"]:
                if x["enumeration"] not in ("ghsa", "geth"):
                    continue
                docs = None
                for y in (y for y in c["candidates"] if (y["system"], y["index"]) == (s["id"], x["id"])):
                    with self.subTest(candidate=y["id"]):
                        docs = I.index_docs(s, x, p) if docs is None else docs
                        doc = docs.get(y["item"])
                        self.assertIsNotNone(doc, f"{y['item']} is not an item of {x['id']}")
                        if I.prefilter(doc, p) is not None:
                            continue   # pre-filtered: never read
                        if y["description"] is not None:
                            self.assertTrue(I.description_ok(y["description"], doc, x["enumeration"]),
                                            f"{y['id']}: the description is not a verbatim excerpt of its item")
                        fix = I.named_fix(doc, s["repos"])
                        if fix is not None:
                            self.assertEqual((y["repo"], y["fix_commit"]), fix,
                                             f"{y['id']}: not the earliest reachable commit its item names")

    def test_git_facts_are_the_instruments(self):
        """I48-R1 (C3, MINOR 2): for every candidate whose fix commit is given in its system's repository, the
        instrument's partial clone finds it reachable from a branch or tag (else commit_not_found) and derives the same
        prefix_commit, fix_date, files, source_lines and frontend_lines; reason not_in_frontend_reach holds exactly when
        reach fails; a candidate without a fix commit is excluded_repo, other_repo or commit_not_found; an other_repo
        candidate's given fix commit is reachable from a branch or tag of its GitHub repository."""
        p = protocol()
        for x in candidates()["candidates"]:
            with self.subTest(candidate=x["id"]):
                if x["reason"] == "excluded_repo":
                    continue
                if x["reason"] == "other_repo":
                    self.assertIsInstance(x["repo"], str)
                    self.assertNotIn(x["repo"], I.system_of(p, x["system"])["repos"])
                    self.assertFalse(I.excluded(x["repo"], p))
                    if x["fix_commit"] is not None:
                        self.assertRegex(x["repo"], r"^https://github\.com/", "a given fix commit needs a GitHub repo")
                        self.assertTrue(I.commit_info(x["repo"], x["fix_commit"], p)["found"],
                                        f"{x['repo']}@{x['fix_commit']} is not reachable from a branch or tag")
                    continue
                self.assertIn(x["repo"], I.system_of(p, x["system"])["repos"])
                if x["fix_commit"] is None:
                    self.assertEqual(x["reason"], "commit_not_found")
                    continue
                info = I.commit_info(x["repo"], x["fix_commit"], p)
                if not info["found"]:
                    self.assertEqual(x["reason"], "commit_not_found")
                    continue
                self.assertNotEqual(x["reason"], "commit_not_found")
                self.assertEqual({k: x[k] for k in ("prefix_commit", "fix_date", "files", "source_lines",
                                                    "frontend_lines")},
                                 {k: info[k] for k in ("prefix_commit", "fix_date", "files", "source_lines",
                                                       "frontend_lines")})
                self.assertEqual(x["reason"] == "not_in_frontend_reach", not info["reach"])

    def test_holon_verify_agrees(self):
        """I48-R1 (C3): python -m holon eval verify exits 0 on the committed candidates."""
        candidates()
        p = ev(["verify"])
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])


# ---------------------------------------------------------------------------------------------- the corpus
class TestCorpus(unittest.TestCase):
    def test_selection_is_rule_c4(self):
        """I48-R1 (C4): the candidates' reasons and entry ids are tests_m4/_i48.py::select over their eligibility, and the
        corpus's entries are exactly the included candidates in selection order with the candidates' fields."""
        c = candidates()
        sel = I.select(c["candidates"], protocol())
        by = {x["id"]: x for x in c["candidates"]}
        self.assertEqual(sorted(cid for cid, _, _ in sel), sorted(by))
        for cid, entry, reason in sel:
            with self.subTest(candidate=cid):
                self.assertEqual((by[cid]["entry"], by[cid]["reason"]), (entry, reason))
        inc = [(cid, e) for cid, e, _ in sel if e]
        ents = corpus()["entries"]
        self.assertEqual([(e["candidate"], e["id"]) for e in ents], inc)
        for e in ents:
            x = by[e["candidate"]]
            for k in ("system", "repo", "title", "description", "sources", "fix_commit", "prefix_commit", "fix_date",
                      "files"):
                self.assertEqual(e[k], x[k], (e["id"], k))
            self.assertEqual(e["kind"], I.system_of(protocol(), e["system"])["kind"])
            self.assertEqual(e["languages"], sorted({I.language_of(f, protocol()) for f in e["files"]}))

    def test_corpus_names_its_inputs(self):
        """I48-R1 (C7): corpus.json names the sha256 of the protocol, the rule sheet and candidates.json."""
        cp = corpus()
        self.assertEqual((cp["protocol_sha256"], cp["rule_sheet_sha256"], cp["candidates_sha256"]),
                         (file_sha256(I.PROTOCOL), file_sha256(I.RULE_SHEET), file_sha256(EVAL / "candidates.json")))

    def test_exit_criterion(self):
        """I48-R1 (C7, the plan's exit; a construction check): corpus.json validates and holds 20 entries from at least
        3 systems (Q20), at least 2 of them not rollups, every entry doubly labelled: every a and b label non-null and
        every disagreement adjudicated with a non-null label."""
        cp, p = corpus(), protocol()
        raw = {w: need(EVAL / "labels" / f"{w}.json")["labels"] for w in ("a", "b", "adjudicator")}
        for w in ("a", "b", "adjudicator"):
            self.assertEqual([x["entry"] for x in raw[w] if x["label"] is None], [], f"{w}: labels without a label")
        self.assertEqual(validate(cp, LIB / "corpus.schema.json"), [])
        ents = cp["entries"]
        self.assertEqual(len(ents), p["n"])
        self.assertGreaterEqual(len({e["system"] for e in ents}), p["min_systems"])
        self.assertGreaterEqual(len({e["system"] for e in ents if e["kind"] not in p["rollup_kinds"]}),
                                p["min_non_rollup_systems"])
        for e in ents:
            self.assertIsNotNone(e["labels"]["a"])
            self.assertIsNotNone(e["labels"]["b"])

    def test_system_spread_prediction(self):
        """I48-P1: at least 4 of the 6 systems contribute at least 3 entries each, at least 2 of these not rollups (a
        prediction about the candidate pool under the frozen protocol; Q20 and the exit ask 3 systems)."""
        ents, p = corpus()["entries"], protocol()
        n = Counter(e["system"] for e in ents)
        kind = {e["system"]: e["kind"] for e in ents}
        big = sorted(s for s, k in n.items() if k >= 3)
        self.assertGreaterEqual(len(big), 4, dict(n))
        self.assertGreaterEqual(sum(kind[s] not in p["rollup_kinds"] for s in big), 2, dict(n))

    def test_cli_selection_is_reproducible(self):
        """I48-R1 (C4): python -m holon eval select --check exits 0 on the committed files."""
        corpus()
        p = ev(["select", "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])


# ---------------------------------------------------------------------------------------------- the labels
class TestLabels(unittest.TestCase):
    def test_raw_labels_are_complete_and_blind_to_each_other(self):
        """I48-R5 (C5): labels/a.json and labels/b.json validate, name the rule sheet and the template, label every
        entry exactly once in corpus order; the adjudicator labels exactly the entries whose a and b labels are both
        non-null and disagree; three different labellers, family "same" (Q9), no tools; every prompt_sha256 is the
        sha256 of the prompt re-rendered from the frozen template (diff capped), and every non-null label is what its
        verbatim response says."""
        cp = corpus()
        ents = {e["id"]: e for e in cp["entries"]}
        ids = list(ents)
        raw = {}
        for who in ("a", "b", "adjudicator"):
            raw[who] = need(EVAL / "labels" / f"{who}.json")
            self.assertEqual(validate(raw[who], LIB / "labels.schema.json"), [], who)
            self.assertEqual(raw[who]["role"], who)
            self.assertEqual(raw[who]["rule_sheet_sha256"], file_sha256(I.RULE_SHEET), who)
            tpl = I.ADJUDICATOR_PROMPT if who == "adjudicator" else I.LABELLER_PROMPT
            self.assertEqual(raw[who]["prompt_template_sha256"], file_sha256(tpl), who)
            self.assertEqual((raw[who]["family"], raw[who]["tools"]), ("same", "none"), who)
        self.assertEqual(len({raw[w]["labeller"] for w in raw}), 3, "a, b and the adjudicator are three agents")
        for who in ("a", "b"):
            self.assertEqual([x["entry"] for x in raw[who]["labels"]], ids, who)
        a = {x["entry"]: x["label"] for x in raw["a"]["labels"]}
        b = {x["entry"]: x["label"] for x in raw["b"]["labels"]}
        dis = [i for i in ids if a[i] and b[i] and a[i]["primary"] != b[i]["primary"]]
        self.assertEqual([x["entry"] for x in raw["adjudicator"]["labels"]], dis)
        self.assertEqual(cp["labellers"], {"a": raw["a"]["labeller"], "b": raw["b"]["labeller"],
                                           "adjudicator": raw["adjudicator"]["labeller"], "family": "same",
                                           "model_tags": protocol()["labelling_invocation"]["roles"]})
        diffs = {}
        for who in ("a", "b", "adjudicator"):
            for x in raw[who]["labels"]:
                with self.subTest(labeller=who, entry=x["entry"]):
                    e = ents[x["entry"]]
                    if e["id"] not in diffs:
                        diffs[e["id"]] = I.fix_diff(e["repo"], e["prefix_commit"], e["fix_commit"], diff_files(e))
                    both = {"a": a[e["id"]], "b": b[e["id"]]} if who == "adjudicator" else None
                    self.assertEqual(x["prompt_sha256"],
                                     I.prompt_sha256(I.render_prompt(who, e, diffs[e["id"]], both)))
                    if x["label"] is not None:
                        self.assertEqual(I.parse_response(x["response"]), x["label"])

    def test_labelling_runs_are_the_protocols(self):
        """I48-R5 (C5, MJ3, MINOR 1): every label file names the protocol's invocation and the sha256 of its system
        prompt, its role's model tag (a: A, b: B, adjudicator: A) and the tool's run-time checks, all true; every
        label's attempts follow the retry rule (each outcome is attempt_outcome of its CLI output; retry_follows: a
        cli_error attempt not counted, at most 5 of them, a second counted attempt after a failed one, no more; ok
        attempts have num_turns 1); its response is the last attempt's result, and its label is
        parse_response(response) when the last attempt is ok, else null."""
        inv = protocol()["labelling_invocation"]
        for who in ("a", "b", "adjudicator"):
            raw = need(EVAL / "labels" / f"{who}.json")
            with self.subTest(labeller=who):
                self.assertEqual(validate(raw, LIB / "labels.schema.json"), [])
                self.assertEqual(raw["invocation"], inv["argv"])
                self.assertEqual(raw["system_prompt_sha256"],
                                 hashlib.sha256(inv["system_prompt"].encode("utf-8")).hexdigest())
                self.assertEqual(raw["model_tag"], inv["roles"][who])
                self.assertEqual(raw["checks"], {"one_model_per_role": True, "a_differs_from_b": True,
                                                 "adjudicator_is_a": True})
            for x in raw["labels"]:
                with self.subTest(labeller=who, entry=x["entry"]):
                    outs = [I.attempt_outcome(t["cli"]) for t in x["attempts"]]
                    self.assertEqual([t["outcome"] for t in x["attempts"]], outs)
                    self.assertTrue(I.retry_follows(outs), f"the attempts {outs} do not follow the retry rule")
                    for t in x["attempts"]:
                        if t["outcome"] == "ok":
                            self.assertEqual(t["cli"]["num_turns"], 1)
                    self.assertEqual(x["response"], x["attempts"][-1]["cli"]["result"])
                    self.assertEqual(x["label"], I.parse_response(x["response"]) if outs[-1] == "ok" else None)

    def test_entries_carry_the_raw_labels_and_the_final_label(self):
        """I48-R5 (C5): each entry's labels are the raw ones and its label is final_label(a, b, adjudicated)."""
        cp = corpus()
        raw = {w: {x["entry"]: x["label"] for x in need(EVAL / "labels" / f"{w}.json")["labels"]}
               for w in ("a", "b", "adjudicator")}
        for e in cp["entries"]:
            with self.subTest(entry=e["id"]):
                self.assertIsNotNone(e["labels"]["a"], f"{e['id']}: no label a (the exit needs it)")
                self.assertIsNotNone(e["labels"]["b"], f"{e['id']}: no label b (the exit needs it)")
                self.assertEqual(e["labels"]["a"], raw["a"][e["id"]])
                self.assertEqual(e["labels"]["b"], raw["b"][e["id"]])
                self.assertEqual(e["labels"]["adjudicated"], raw["adjudicator"].get(e["id"]))
                adj = e["labels"]["adjudicated"]["primary"] if e["labels"]["adjudicated"] else None
                self.assertEqual(e["label"], I.final_label(e["labels"]["a"]["primary"], e["labels"]["b"]["primary"], adj))

    def test_agreement_is_the_instruments(self):
        """I48-R5 (C6): corpus.json's agreement is the instrument's kappa over the a and b primary labels."""
        cp = corpus()
        missing = [e["id"] for e in cp["entries"] if e["labels"]["a"] is None or e["labels"]["b"] is None]
        self.assertEqual(missing, [], "entries without both labels: kappa is not defined over them")
        want = I.kappa([e["labels"]["a"]["primary"] for e in cp["entries"]],
                       [e["labels"]["b"]["primary"] for e in cp["entries"]], CATS)
        got = cp["agreement"]
        self.assertEqual((got["n"], got["confusion"]), (want["n"], want["confusion"]))
        for k in ("p_o", "p_e", "kappa", "se"):
            if want[k] is None:
                self.assertIsNone(got[k], k)
            else:
                self.assertAlmostEqual(got[k], want[k], places=12)
        if want["ci95"] is None:
            self.assertIsNone(got["ci95"])
        else:
            for g, w in zip(got["ci95"], want["ci95"]):
                self.assertAlmostEqual(g, w, places=12)

    def test_agreement_prediction(self):
        """I48-P2: Cohen's kappa between the two labellers is at least 0.40 (a prediction, reported; never an exit
        condition). An undefined kappa is a miss."""
        k = corpus()["agreement"]["kappa"]
        self.assertIsNotNone(k, "kappa undefined: a miss")
        self.assertGreaterEqual(k, 0.40)

    def test_label_spread_prediction(self):
        """I48-P3: the final labels use at least 5 of the 9 categories, and at most 5 of the 20 entries are labelled
        none."""
        labels = [e["label"] for e in corpus()["entries"]]
        self.assertGreaterEqual(len(set(labels)), 5, labels)
        self.assertLessEqual(labels.count("none"), 5, labels)


# ---------------------------------------------------------------------------------------------- the renaming
def _entry(e: dict) -> dict:
    """Rename and unrename one entry's files in a sparse worktree at its pre-fix commit (tests_m4/_i48.py::
    sparse_checkout) with the CLI, and check them with the instrument; cached per process, nothing written into the
    repository."""
    if e["id"] in _RUNS:
        return _RUNS[e["id"]]
    tmp = Path(tempfile.mkdtemp(prefix="i48_rename_"))
    src = tmp / "src"
    try:
        I.sparse_checkout(e["repo"], e["prefix_commit"], e["files"], src)
        try:
            out, mp, back = tmp / "renamed", tmp / "map.json", tmp / "back"
            p = ev(["rename", "--root", src, "--files", *e["files"], "--seed", e["id"], "--out", out, "--map", mp])
            if p.returncode != 0:
                raise AssertionError(f"{e['id']}: holon eval rename: {p.stdout[-2000:]}{p.stderr[-2000:]}")
            p = ev(["unrename", "--root", out, "--map", mp, "--out", back])
            if p.returncode != 0:
                raise AssertionError(f"{e['id']}: holon eval unrename: {p.stdout[-2000:]}{p.stderr[-2000:]}")
            m = load_json(mp)
            old = {f: I.changed_old_lines(e["repo"], e["prefix_commit"], e["fix_commit"], f) for f in e["files"]}
            res = I.check_renaming(src, out, back, e["files"], e["id"], m, protocol(), old)
            res["map_sha256"] = file_sha256(mp)
            res["files"] = sorted(m["files"], key=lambda x: x["path"])
        finally:
            I.drop_worktree(e["repo"], src)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    _RUNS[e["id"]] = res
    return res


class TestRenaming(unittest.TestCase):
    def test_round_trip_and_isomorphism_on_every_entry(self):
        """I48-R6 (N0-N3): for every corpus entry, rename then unrename gives back its files at the pre-fix commit byte
        for byte; every renamed file is isomorphic to the original under the map (Go: the goast printout; Solidity: the
        independent token stream always, and solc's AST when both parse); the map's identifiers are N1's set with
        new_names' names (none reserved), its comments the removed ones, and the renamed files keep exactly the kept
        comments."""
        for e in corpus()["entries"]:
            with self.subTest(entry=e["id"]):
                r = _entry(e)
                self.assertTrue(all(r["roundtrip"]), (e["id"], r["roundtrip"]))
                self.assertTrue(all(r["iso"]), (e["id"], r["iso"]))
                self.assertEqual(r["problems"], [], e["id"])

    def test_renaming_documents(self):
        """I48-R6 (N3): gen/eval/renaming/<entry>.json validates for every entry and records what the instrument's run
        of the CLI found (files, renamed, candidates, on_changed_lines, files_by_ast, files_by_tokens, the map's
        sha256), and python -m holon eval renaming --check exits 0."""
        for e in corpus()["entries"]:
            with self.subTest(entry=e["id"]):
                d = need(GEN / "renaming" / f"{e['id']}.json")
                self.assertEqual(validate(d, LIB / "renaming.schema.json"), [])
                r = _entry(e)
                self.assertEqual((d["entry"], d["seed"]), (e["id"], e["id"]))
                self.assertEqual(sorted(d["files"], key=lambda x: x["path"]), r["files"])
                for k in ("renamed", "candidates", "on_changed_lines", "files_by_ast", "files_by_tokens", "map_sha256"):
                    self.assertEqual(d[k], r[k], k)
        p = ev(["renaming", "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])

    def test_renaming_strength_prediction(self):
        """I48-P4: in at least 6 of the 20 entries, at least one renamed identifier occurs on a pre-fix line that the fix
        deletes or changes (the renaming reaches the defect's own lines; N1 fixes which identifiers are renamed, so the
        count is a property of the corpus and the rule, not of the tool)."""
        hits = {e["id"]: _entry(e)["on_changed_lines"] for e in corpus()["entries"]}
        self.assertGreaterEqual(sum(v >= 1 for v in hits.values()), 6, hits)


# ---------------------------------------------------------------------------------------------- the controls
class TestControls(unittest.TestCase):
    def test_manifest_is_the_plans(self):
        """I48-R4 (K1, K2): spec/eval/controls.json validates and lists exactly the plan's 14 controls with their truth,
        witness, within_budget and expected; its budgets are the plan's, run budgets included; it names the ledger."""
        doc = need(EVAL / "controls.json")
        self.assertEqual(validate(doc, LIB / "controls.schema.json"), [])
        pl = plan()
        self.assertEqual(doc["milestone"], pl["milestone"])
        self.assertEqual(canonical_json(doc["controls"]), canonical_json(I.controls(pl)))
        b = pl["budgets"]
        for k in ("prefixDepth", "suffixDepth", "natMax", "maxPrefixes", "strengthening", "source", "run", "run_rule"):
            self.assertEqual(doc["budgets"][k], b[k], k)
        self.assertEqual(doc["ledger"], "spec/eval/controls/ledger.json")

    def test_documents_are_the_plans(self):
        """I48-R4 (K2): each control's facts and law files are byte for byte dumps(expected_documents(control, plan));
        each law validates against the IR 0.3 schema and passes holon.ir's premise checks; no search key, no hints
        module and no library directory can steer the factory."""
        pl = plan()
        self.assertFalse((EVAL / "policy_hints.mjs").exists(), "spec/eval/policy_hints.mjs steers the explorer")
        self.assertFalse((EVAL / "lib").exists(), "spec/eval/lib/ adds target libraries")
        for c in I.controls(pl):
            with self.subTest(control=c["id"]):
                facts, law = I.expected_documents(c, pl)
                got_facts, got = need(ROOT / c["facts"]), need(ROOT / c["law"])
                self.assertNotIn("search", got_facts)
                self.assertEqual((ROOT / c["facts"]).read_bytes(), I.dumps(facts).encode(), c["facts"])
                self.assertEqual((ROOT / c["law"]).read_bytes(), I.dumps(law).encode(), c["law"])
                self.assertEqual(validate(got, LAW_SCHEMA), [])
                holon_call("holon.ir", "check_premises", got)

    def test_ground_truth_is_independent(self):
        """I48-R4 (K3): the instrument's interpreter confirms every committed control's truth: each false control's
        witness reaches a state where the observer is false and no shorter trace does; each true control's reachable
        states are finite, the observer holds on all of them, and the claim alone is not inductive."""
        for c in I.controls(plan()):
            with self.subTest(control=c["id"]):
                control_truth(self, c, need(ROOT / c["facts"]), need(ROOT / c["law"]))

    def test_sizing_is_the_interpreters(self):
        """I48-R4 (K4): within_budget of every committed control is the interpreter's (false: a violating trace within
        prefixDepth over the generic inputs; true: no counterexample to induction in the box with houdini's
        constants)."""
        b = plan()["budgets"]
        for c in I.controls(plan()):
            with self.subTest(control=c["id"]):
                within = control_within(c, need(ROOT / c["facts"]), need(ROOT / c["law"]), b)
                self.assertEqual(within, c["within_budget"])

    def test_ledger_bundles_classify_the_models(self):
        """I48-R4 (K2): spec/eval/controls/ledger.json gives each control's facts an exact holon.records bundle, and
        that bundle classifies every definition of the model holon.gen.machine generates from them (so I53's runs
        build records without writing into I48's outcome paths)."""
        need(EVAL / "controls" / "ledger.json")
        for c in I.controls(plan()):
            with self.subTest(control=c["id"]):
                sha = file_sha256(ROOT / c["facts"])
                b = holon_call("holon.records", "bundle", sha, ROOT, c["facts"])
                self.assertEqual(b["facts"], c["facts"])
                text = holon_call("holon.gen.machine", "generate", need(ROOT / c["facts"]), sha, ROOT / c["facts"],
                                  reach=True)
                self.assertEqual(holon_call("holon.records", "unclassified", sha, text, ROOT, c["facts"],
                                            plan()["milestone"]), [])

    def test_cli_controls_are_reproducible(self):
        """I48-R4 (K2): python -m holon eval controls --check exits 0 on the committed files."""
        need(EVAL / "controls.json")
        p = ev(["controls", "--check"])
        self.assertEqual(p.returncode, 0, p.stdout[-3000:] + p.stderr[-3000:])


# ---------------------------------------------------------------------------------------------- regressions
class TestRegressions(unittest.TestCase):
    def test_i48_outcome_commits_touch_nothing_else(self):
        """I48-R3: every commit that changes spec/eval/, gen/eval/ or holon/eval/ changes no file under laws/, results/,
        facts/, replay/, spec/M1-M3/, gen/M0-M3/, tests/, tests_m1/-tests_m4/, holon/ (holon/eval/ and the CLI entry
        holon/__main__.py aside), tools/ (tools/setup_env.sh aside), config/, spec/M4/ (spec/M4/amendments.jsonl
        aside), spec/schemas/, spec/heldout/ or prompts/. Commits that change none of the eval paths are not scoped by
        this test. Needs the real checkout's history: a missing .git is a failure, never a skip."""
        import subprocess

        def git(*args):
            p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                               env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if p.returncode != 0:
                raise AssertionError(f"git {' '.join(args)}: {p.stderr.strip()}")
            return p.stdout
        commits = git("log", "--format=%H", "--", "spec/eval", "gen/eval", "holon/eval").split()
        self.assertTrue(commits, "no commit writes spec/eval/, gen/eval/ or holon/eval/")
        never = ("laws/", "results/", "facts/", "replay/", "spec/M1/", "spec/M2/", "spec/M3/", "gen/M0/", "gen/M1/",
                 "gen/M2/", "gen/M3/", "tests/", "tests_m1/", "tests_m2/", "tests_m3/", "tests_m4/", "holon/", "tools/",
                 "config/", "spec/M4/", "spec/schemas/", "spec/heldout/", "prompts/")
        allowed = ("holon/__main__.py", "tools/setup_env.sh", "spec/M4/amendments.jsonl")
        for c in commits:
            touched = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--root", "-z", c).split("\0")
            self.assertEqual([f for f in touched if f.startswith(never) and not f.startswith("holon/eval/")
                              and f not in allowed], [], c)

    def test_eval_code_enters_no_generator_closure(self):
        """I48-R3: no holon/eval/ module is in the holon-ir/0.1-0.3 generator closures (M0-M3 records keep their
        generator_sha256; holon.records runs in a child process)."""
        mods = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "holon" / "eval").glob("*.py"))
        self.assertTrue(mods, "holon/eval/ is missing")
        for v in ("holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"):
            closure = holon_call("holon.records", "generator_files", v, ROOT)
            self.assertEqual([m for m in mods if m in closure], [], v)

    def test_eval_code_imports_no_instrument(self):
        """I48-R3 (AGENTS rule 5): no holon/eval/ module imports or names a test module (tests_m4, tests.reference or
        any other tests package): the tool and the instrument stay independent."""
        mods = sorted((ROOT / "holon" / "eval").glob("*.py"))
        self.assertTrue(mods, "holon/eval/ is missing")
        bad = re.compile(r"^tests(_m[0-9]+)?(\.|$)")
        for p in mods:
            with self.subTest(module=p.name):
                text = p.read_text(encoding="utf-8")
                for node in ast.walk(ast.parse(text)):
                    if isinstance(node, ast.Import):
                        self.assertFalse([a.name for a in node.names if bad.match(a.name)])
                    elif isinstance(node, ast.ImportFrom):
                        self.assertFalse(node.level == 0 and bad.match(node.module or ""), node.module)
                self.assertNotRegex(text, r"tests_m[0-9]|tests[./]reference|tests/_util|tests\._util")


if __name__ == "__main__":
    unittest.main()
