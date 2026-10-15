# I48: evaluation corpus and unsolved controls

Rendered from `docs/BUILD_PLAN.md` §4 I48 (whitepaper §13 "Corpus", "Threats to validity", and L15 "UNKNOWN calibration"), with the human answers Q20 (N = 20 defects across at least 3 systems), Q9 (same-family labellers are labelled), Q7 (the sealed held-out target) and the end-goal guidance in `docs/HUMAN_ANSWERS.md` (the corpus tests generality beyond rollups wherever the frontends reach). Read `AGENTS.md` first.

The exact outputs, formats and rules are in the docstring of `tests_m4/test_eval_corpus.py`: rules C0–C7 (the corpus), N0–N3 (the renaming) and K0–K4 (the controls), plus gaps E-G1–E-G7. The instruments are fixed at this prereg, and each file below is pinned by its sha256 in the test file's `PINNED` (a later edit needs an amendment):
- `tests_m4/_i48.py`: the selection, the agreement statistic, the prompt renderer with its diff cap, the retry rule's attempt outcome, the index enumerators and their pre-filter, the controls' exact documents and an explicit-state interpreter for their ground truth, git verification, the exact renaming rule and the isomorphism checks. It holds the pins of the parsers it runs as constants, `SOLC_SHA256` (solc 0.8.24) and `GO_VERSION` (`go version go1.24.7 linux/amd64`); `config/holon.json` may only name a candidate path of solc;
- `tests_m4/_m4.py`: the shared readers, and `tests_m4/__init__.py` (empty);
- `tests_m4/fixtures/goast/main.go`: a `go/parser` AST printer (depth, operators, literal values, nil children, declaring identifiers, kept comments);
- the frozen sidecars in `spec/M4/lib/`: `corpus_protocol.json`, `rule_sheet.json`, `labeller_prompt.md`, `adjudicator_prompt.md`, `rename_reserved.json`, `controls_plan.json`, and the five schemas beside them;
- this prompt.

`setUpModule`, `tearDownModule` and `test_instruments_are_the_preregistered_ones` import a fresh copy of `tests_m4/_i48.py`, `tests_m4/_m4.py` and the test module itself under other names and check that the loaded modules have the same functions and test methods (code, constants, names, defaults, their own globals), module bindings and constants. The test process never imports a holon module: holon's functions run in child processes. What holds exactly (gap E-G7): the authoritative run is the named module in a fresh process, `python -m unittest tests_m4.test_eval_corpus`, which imports no other test module and no holon module. A discovery run that imports other `tests_m4` modules can be patched by them, so a new `tests_m4` module needs the lead's diff review, and I48's eval commits may not add one (R3).

**Order.** `docs/BUILD_PLAN.md` lists I47 before I48; I48 runs first. I47's performance loop may change the explorer's and houdini's defaults, so the controls' run budgets are pinned in `controls_plan.json` (`budgets.run`) and I53 passes them explicitly. The sizing also rests on the generic policy, houdini and the explorer as they are at this base: `controls_plan.json` records their sha256 (`sizing_sources`), and I53 asserts them or re-derives the sizing (gap E-G6, Question 4).

## Goal

Build the inputs of M4's measurements, so that I51 (HOLON on the corpus), I52 (baselines) and I53 (ablations and UNKNOWN calibration) measure against fixed ground truth:
- **a corpus of 20 public defects.**
  - Each has a public write-up, a fix commit reachable by `git clone` from a branch or tag, and its pre-fix parent.
  - The defects come from six fixed systems, two of them rollups and four beyond.
  - Fresh collector agents examine fixed public indexes in a fixed order, record every candidate examined, and a mechanical round-robin selection picks the entries.
  - Each entry is labelled with the minimal rule that exposes it by two different models of one family, each prompt read by a fresh tool-less process from a frozen template, with an adjudicator for the disagreements, and the agreement is reported;
- **an isomorphic renaming tool**, which mitigates contamination (§13): agents that recognise a public defect by its names see renamed code.
  - Which identifiers it renames is fixed exactly by rule N1, and its round trip is checked byte for byte.
  - Its isomorphism is checked by parsers it does not share code with;
- **14 controls.** These are planted true and false obligations whose documents and ground truth are fixed by construction and recomputed independently, sized against pinned budgets, so that I53 can calibrate UNKNOWN (L15).

## The protocol (frozen; read `spec/M4/lib/corpus_protocol.json`)

**Systems and indexes.**

| system | kind | repositories | indexes, in order (enumeration) |
|---|---|---|---|
| arbitrum | rollup | `OffchainLabs/nitro`, `OffchainLabs/nitro-contracts` | GitHub Advisory Database (ghsa); docs.arbitrum.io/audit-reports (page) |
| compound | defi | `compound-finance/compound-protocol` | GitHub Advisory Database (ghsa); docs.compound.finance/v2/security (page) |
| cosmos | appchain | `cosmos/cosmos-sdk`, `cosmos/ibc-go` | GitHub Advisory Database (ghsa); both repos' `docs/audits` (folder) |
| go-ethereum | client | `ethereum/go-ethereum` | geth's `vulnerabilities.json` (geth; served from branch `website` of `ethereum/go-ethereum`); GitHub Advisory Database (ghsa) |
| optimism | rollup | `ethereum-optimism/optimism` | GitHub Advisory Database (ghsa); `docs/security-reviews` (folder) |
| wormhole | bridge | `wormhole-foundation/wormhole` | GitHub Advisory Database (ghsa); the repo's `audits` (folder) |

`scroll-tech/*` (the sealed held-out target) and `morph-l2/*` (the development target) are excluded by repository and by subject (Scroll, scroll-tech, ScrollChain, scroll.io, Morph, morph-l2, whole words). On the mechanical indexes a pre-filter runs before any agent sees an item: an item any of whose JSON string values holds an excluded repository pattern or names an excluded subject is never opened and is recorded as `excluded_repo` with `excluded_by`, without a title. On the other indexes a candidate whose item, repository or source URLs hold a pattern, or whose title or description names a subject, is `excluded_repo` and is not read further. Every index URL was checked to exist at the prereg.

**Reading the sources.** github.com's web pages and API are not reachable from this environment. GHSA records are read from the advisory database's git repository; in-repo folders and the geth list's source (branch `website` of `ethereum/go-ethereum`) through `git clone`; a relative page link resolves against the page's final URL; a repository file linked as `github.com/<o>/<r>/blob/<ref>/<path>` from `raw.githubusercontent.com/<o>/<r>/<ref>/<path>` (compound's audit page links some of its reports so; its URL redirects to `docs.compound.xyz/v2/security/`); a repository advisory link (`github.com/<o>/<r>/security/advisories/GHSA-...`) through the advisory database's record of the same id. For sizing the clones: a blobless bare clone of optimism with all heads and tags was measured at 61 MB in 6 s; the advisory database's commit graph (`--filter=tree:0`) at 54 MB in 3 s, a depth-1 fetch of one of its commits at 231 MB in 33 s, and a full scan of its advisory files at about 51 s.

**Snapshots, pinned now** (`corpus_protocol.json` `snapshots`). Each git index is read at the newest first-parent commit of its branch whose committer date is before the cutoff, computed by the lead from commit graphs only:

| source | repository | branch | commit | committer date |
|---|---|---|---|---|
| advisory database | `github/advisory-database` | `main` | `b950a40c9ce07b70b943775709034132dd9614cb` | 2026-10-14T21:37:11Z |
| geth list | `ethereum/go-ethereum` | `website` | `17538c7bbb135c95244a60c625917cc1975cdc85` | 2026-10-07T09:48:23Z |
| cosmos-sdk audits | `cosmos/cosmos-sdk` | `main` | `2ad20ad7ca843fbde95c1472ab69f1d3f04e46d4` | 2026-10-06T07:19:38Z |
| ibc-go audits | `cosmos/ibc-go` | `main` | `35cf291f836ecd324d5921150c417f79b6ebfc77` | 2026-10-14T13:35:11Z |
| optimism security reviews | `ethereum-optimism/optimism` | `develop` | `7c2e64f60028baca88367c35e1007e568036648b` | 2026-10-14T21:43:33Z |
| wormhole audits | `wormhole-foundation/wormhole` | `main` | `bb5957f321b0a9d168f52e906699ee77baa82a28` | 2026-10-13T17:04:00Z |

A correction to the second fold: the geth list is not served from `ethereum/geth-website`, which stopped in 2023-01 and whose copy holds 10 entries while the URL serves 12. The served file is `public/docs/vulnerabilities/vulnerabilities.json` on branch `website` of `ethereum/go-ethereum`. Verified at the prereg: at the pinned commit its sha256 is `c0d3311d521e0b619129e8318b754474511ce104ca57f90faa9f7c92fa5a7346`, equal to the bytes the URL served. To settle the geth item rule, the lead read only the list's entry count and uids. The fold also checked that every pin is reachable from its branch (commit graphs only). Page snapshots (arbitrum, compound) are fetched at collection and recorded with their final URL and the sha256 of their bytes; they cannot be fetched again here (gap E-G1).

**Item lists.** Each index record holds the whole item list and how far it was examined.
- **Mechanical indexes (ghsa, geth).** They are enumerated by an exact rule (`tests_m4/_i48.py::ghsa_items_from`, `geth_items_from`; an entry without a parsable published date is not an item). Their collectors work from the item list of `python -m holon eval index`, and the test recomputes it at the pin.
  - A geth item is `<list URL>#<uid>` (or `#<position>` when the uids are not distinct): the list entry itself, its links following as supplementary sources.
  - When an item names a commit of the system's repositories that is reachable, the fix commit is the earliest named one (`named_fix`), and the description must be a verbatim excerpt of the item (`description_ok`).
- **Folders.** A folder's items are exactly its `.pdf` and `.md` reports other than a README at the pin, which is the folder's cutoff.
- **Audit items (folder, page).** Each records `findings`, the number of findings the report holds (every numbered or headed finding, whatever its severity or status), and yields exactly that many candidates, one per finding (the stopping item up to the system's 8th eligible candidate); a report with no finding records 0 and a note.
- **Dates of audit items.** The report's own date (a month, quarter or year alone means its first day); for a folder report without a date, or with one after its pin, the committer date of the earliest first-parent commit adding the path; for a page report without a date, the page's, else 1970-01-01.

**Collection.** Fresh agents, one per system, given only the protocol, examine the system's indexes in order, each in its enumeration's order (newest published first), and record every candidate examined with its rank (ids `<system>:<rank>`, at least three digits). A mechanical index's item yields exactly one candidate; an audit report one per finding. No supplementary source holds an excluded pattern; an excluded candidate that was not opened may have no title or description. A system stops at its 8th eligible candidate or when its indexes run out. Issues and other pages are supplementary sources only. The fix commit, the duplicate rule and the verbatim title and description are defined in the protocol; a judged exclusion carries a note.

**Criteria**, in order (the first failing one is the reason): excluded repository, other repository (a fork or dependency such as op-geth, recorded with its fix commit, which must be reachable in that GitHub repository, or with a null fix commit and a note when it cannot be named), commit not found (not reachable from a branch or tag; without a fix commit, a note says what was searched), not in frontend reach (no non-test, non-generated `.go`/`.sol` file changed, or such files hold under half of the changed source lines), no public write-up, not a functional defect, duplicate.

**Selection** (mechanical, rule C4): round robin over the systems in the protocol's order, each system's eligible candidates newest fix first, at most 8 per system, 20 in total. No candidate is chosen by hand, and the selection is never re-run after labelling.

**Labelling** (rules C5–C6):
- Labeller a and the adjudicator run model A, the family's most capable model available to the build; labeller b runs model B, a smaller, different model of the same family. The repository records only the tags A and B, never model names, together with the tool's run-time checks (one model per role, a differs from b, the adjudicator is a's model), which the tool reads from each call's own report of the model it used.
- Each prompt (one entry, one role) is read by a fresh process run exactly as `corpus_protocol.json` `labelling_invocation` says: `claude -p --tools "" --strict-mcp-config --disable-slash-commands --no-session-persistence --setting-sources "" --system-prompt <system_prompt> --model <model> --output-format json`, the prompt on stdin, a fresh empty working directory, no additional CLAUDE.md directories, 600 s. Verified at the prereg: this invocation answers with `is_error` false and `num_turns` 1, reports one model per call, and the process sees no tools and no project instructions (it does see the date and its working directory).
- The prompt is rendered from `spec/M4/lib/labeller_prompt.md`: the rule sheet, the entry's title, the verbatim excerpt of its first source, its source URLs and the fix diff, capped at 60000 characters of whole lines (a final line says how many were kept). The adjudicator labels exactly the disagreements from `adjudicator_prompt.md`, which adds both labels.
- Each label records the prompt's sha256, every attempt (the CLI's JSON reduced to `is_error`, `num_turns`, `result`, `session_id`, `subtype`, and its outcome) and the last response. Retry rule: an attempt is ok when the CLI reports no error and one turn and its result parses to a valid label. A failed attempt with model output is followed by exactly one more such attempt. A `cli_error` attempt does not count: the prompt is run again after a 60 s wait, at most 5 `cli_error` attempts per prompt. The label is null only when both counted attempts fail or the 5 `cli_error` attempts are spent.
- Cohen's kappa is reported over the nine categories (the eight rules and none), with its standard error. Every agent is same-family, and recorded as such (Q9).

## Deliverables (summary; the contract has the details)

- **`holon/eval/`** and **`python -m holon eval {index,verify,select,agree,rename,unrename,renaming,controls}`**. Nothing in `holon/eval/` imports a test module. `holon eval index` writes a mechanical index's item list outside the repository for its collector; `holon eval rename` refuses a set with `.sol` files when the pinned solc is missing.
- **Corpus outputs:**
  - `spec/eval/candidates.json` and `spec/eval/corpus.json`;
  - `spec/eval/labels/{a,b,adjudicator}.json`: the invocation, the model tag, the run-time checks, and per entry the prompt's sha256, every attempt and the raw response, recorded verbatim;
  - `gen/eval/renaming/<entry>.json`.

  The maps themselves are not committed: they would pair each original name with its renamed one.
- **Control outputs:** `spec/eval/controls.json`, `spec/eval/controls/<id>.{facts,law}.json` (exactly the instrument's documents) and `spec/eval/controls/ledger.json`. Never `spec/eval/policy_hints.mjs` or `spec/eval/lib/`.
- **Solidity parser:** `tools/setup_env.sh --solc` installs the pinned solc 0.8.24 into `~/.holon`, for the Solidity isomorphism check and rule N1 (e). Its sha256 is pinned in `tests_m4/_i48.py` (`SOLC_SHA256`, equal to `config/holon.json`'s).
- **Report:** `docs/iterations/I48.md`, with the prediction table, the per-entry renamed/candidates counts, the files compared by AST and by tokens, kappa's interval, the attempts that needed a retry, and how often the adjudicator chose a's rule, b's or a third.

## Predictions (key I48 of `spec/M4/predictions.json`)

| id | claim |
|---|---|
| P1 | At least 4 of the 6 systems contribute at least 3 entries each, at least 2 of these not rollups (the exit asks 3 systems; round robin alone would make one entry per system near certain). |
| P2 | Cohen's kappa ≥ 0.40 between two different models of the same family, each prompt read by a fresh tool-less process. This is reported, not an exit condition; an undefined kappa is a miss. |
| P3 | The final labels use ≥ 5 of the 9 categories, and at most 5 entries are labelled none. |
| P4 | In at least 6 of the 20 entries, an identifier the renaming renames occurs on a pre-fix line the fix deletes or changes. |

**Regressions and construction checks (not counted).**
- **R1:** the candidates follow the protocol (pinned snapshots, whole item lists, examined prefixes, one candidate per mechanical item and per audit finding, exclusions with what excluded them), the mechanical item lists are the instrument's recomputed at the pins, a mechanical candidate's fix commit and description are its item's, every commit is reachable by `git clone` with the instrument's git facts, the selection is rule C4's, and the plan's exit holds (20 doubly labelled entries from at least 3 systems, at least 2 not rollups, no null label).
- **R2:** the pinned instruments are unchanged and the loaded instrument, its readers and the test module are the files on disk, the sidecars are well formed, and the instrument behaves on synthetic cases (including the reviews' renaming cases, the enumerators, the snapshot rule, the diff cap and the retry rule).
- **R3:** nothing of M0–M3 and no prereg input changes (the eval commits touch no file under `holon/` but `holon/eval/` and the CLI entry, under `tools/` but `setup_env.sh`, under `config/`, `tests_m4/`, `spec/M4/` but its amendments, `spec/schemas/`, `spec/heldout/` or `prompts/`), no `holon/eval/` module enters a generator closure, and none imports a test module.
- **R4:** the 14 controls are the plan's:
  - within the budget: depth 1 and 2, value 1, and constant 1 and 3;
  - expected outcomes: REFUTED 3, PROVED 2, UNKNOWN 9;
  - the documents are exactly the instrument's, and the ledger classifies their models;
  - the ground truth and the sizing are confirmed by the independent interpreter, and the plan records the sha256 of the files the sizing rests on.
- **R5:** the labels are complete, from three different labellers run exactly as the frozen invocation says (tags A, B, A; run-time checks true), the retry rule is followed (`cli_error` attempts not counted), the prompts are the templates', and every label is what its verbatim response says.
- **R6:** the renaming round-trips, is isomorphic, and renames exactly rule N1's identifiers.

## Outcome paths, narrowly

`spec/eval/` and `gen/eval/`. `docs/iterations/I48.md` is written in the report commit, as usual.

## Rules

- **AGENTS.md is binding.** I48 changes no law, record, model or generator of M0–M3.
- **Candidates and labels are data from fresh agents and processes, recorded verbatim.**
  - Nobody edits a label after it is recorded.
  - No label is chosen to reach an agreement level.
  - A missed prediction (spread, kappa, labels, renaming strength) is a Surprise.
- **The sealed target stays sealed.** No agent searches, clones or reads `scroll-tech/*`, or opens an item about it. Morph is not a corpus system.
- **No skips.** A test that needs the network, `go` or solc fails when it is missing, naming it.

## Adversarial review folded into this prereg

An independent reviewer attacked the first draft of this prereg; every finding was fixed before any candidate was collected. The Solidity check now drops every location field, maps every name field, neutralises version pragmas and compares token streams. The renaming rule renames only declared names and keeps directives. The Go printer distinguishes structure. The instruments are pinned. The collection runs from fixed indexes in a fixed order. Construction checks moved out of the predictions. The labeller prompts are frozen, the minimality measure is defined, the control documents and run budgets are pinned, and git verification is independent and reachability-checked. The control law ids were also fixed: the first draft's `L48_*` failed the IR 0.3 schema.

A second independent review of the folded prereg found no blocking problem but five major and nine minor findings, all fixed before any candidate was collected. Rule N1 renamed names that compilers reject (a call option `salt`, cgo `C.free`, a non-ASCII constant used in a sibling file) and refused a valid one (a local named `error`): the reserved names, a cgo rule, Unicode words and an exact rule for unparsable `.sol` files fix it, with the four cases as tests. The instrument modules are now pinned and checked against a fresh import; P1 now counts systems with three entries; the labellers are two different models in fresh tool-less processes under a frozen invocation and a retry rule; and every index is read at a recorded snapshot, with the mechanical item lists recomputed by the instrument, so that an omitted or quietly excluded candidate is detectable.

A third independent review found two blocking problems: an audit report without findings could not be recorded, and geth items were not unique by construction. It also found three major ones: snapshot commits were unconstrained in time, the instrument's integrity check could be bypassed by a sibling module, and a mechanical item's fix commit and description were left to judgment. The fold fixes them as follows. Audit items record their number of findings, geth items are `<list>#<uid>`, the git snapshots are pinned here (correcting the geth list's source to branch `website` of `ethereum/go-ethereum`), the integrity check covers the instrument, its readers and the test module before and after the tests (with holon run in child processes), and a mechanical candidate's fix commit and description are checked against its item; the twelve minor findings (cli_error retries, other_repo without a commit, `names_repo` boundaries, dotted Yul names, the cgo preamble, ids above 999, page links and dates, unopened exclusions, R3's scope, clone redirects, undated entries, unrecorded model choice) are fixed too.

## Questions for the human (raised by the prereg)

1. **Labeller family and models.** Every collector, labeller and adjudicator is same-family (Q9 default). Labeller a and the adjudicator run model A, the family's most capable model available to the build; labeller b runs model B, a smaller model of the same family; the repository records only the tags. If another family becomes available, should I48's labels be re-done by it before I51 (for example as labeller b)? If so, the agreement would be re-reported.
2. **Advisories through a mirror.** github.com's advisory pages and the REST API are refused in this environment, so GHSA records are read from the GitHub Advisory Database's git repository (the same records) and cited by their canonical `https://github.com/advisories/<id>` URL. Is that acceptable as "public"?
3. **Renaming depth and behaviour.** File names, string literals and kept comments stay (gap E-G3). The isomorphism is checked by parsers, not by building: no `go build`, `go vet` or Solidity compilation runs, because a package needs its whole module and dependency graph, and Solidity sources need dependencies the checkout does not hold. Should a later iteration add a behaviour-checked renaming that builds the full checkout and runs the project's tests before and after?
4. **Order.** I48 runs before I47, although the plan lists I47 as its dependency. The controls' run budgets are pinned so that I47 cannot change what "within budget" means, and the sha256 of the files the sizing rests on are recorded for I53 to assert. Is the reordering acceptable, or should I48's controls wait for I47?
5. **Forks and dependencies.** Fixes in op-geth, OffchainLabs/go-ethereum, OffchainLabs/bold or cometbft/cometbft are recorded as `other_repo` and are not eligible. Should a later corpus version add such repositories to their systems?
