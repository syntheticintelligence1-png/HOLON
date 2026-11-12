# I51 (M4): HOLON on the corpus pre-fix commits

Rendered from docs/BUILD_PLAN.md §4 I51 and the coordinator's brief for this session. Read AGENTS.md, docs/M0_SPEC.md,
docs/BEND_PRIMER.md, BUILD_PLAN §0.1, §0.2, §2, §3, the M4 header and §4 I51 (it depends on I47 and I48), whitepaper
§13, the corpus spec/eval/corpus.json with its labels and docs/iterations/I48.md, I47's code (targets/, holon/target_run.py)
and docs/HUMAN_ANSWERS.md (Q19; the lead's delegated answers: the corpus tests generality beyond rollups).

Base: I47's branch `claude/i47-target-factory` at 7dc50894 (draft, not landed); the draft PR goes against
`claude/holon-v2-bend2-c6z3cd` and says it is stacked on I47's PR. Landing waits for M3's exit. Merge commits only.

## Goal

Run extraction, the rules, replay and filtering on every corpus pre-fix commit, then compute per-rule recall and
precision (true defects, intended asymmetries, model defects). Exit: `results/eval/holon/corpus.json` has a row for every
entry, "not run" only for an extraction failure that carries a reason. Extraction gaps on foreign codebases are misses,
never exclusions; a frontend HOLON lacks is a reasoned miss, never a hand-written fact.

The contract is the docstring of `tests_m4/test_i51_corpus_run.py` (H0-H9, S1-S6). The key is `I51` in
`spec/M4/predictions.json` (source `spec/M4/predictions/I51.json`). The run protocol is `spec/M4/lib/i51_run.json`; the
independent scorer is `tests_m4/_i51.py`.

## What I51 must not change

Nothing in M0-M3: no law, record, result, generated file or record-pinned holon/ file. New code goes into
`holon/eval/holon_run.py` (and the command table of `holon/eval/cli.py`), which no generator closure imports. I48's own
rule R3 (tests_m4/test_eval_corpus.py) requires that a commit touching holon/eval/ touch nothing outside holon/eval/
(and a few allowed files): the code commits and the outcome commits (results/eval/holon/) are separate.

## How HOLON is run on a foreign commit (fixed by the protocol)

HOLON is run as it is: no frontend, rule or runner of M0-M3 is changed for I51. For each entry the tool generates,
from the entry alone, the inputs a blind session would author: a transitions sidecar per declared Solidity contract
(pinned solc 0.8.24, no dependency tree), a Go frontend config per package (no primitives), and generic typed-sorts,
DISCH, UNDO and FACT sidecars whose target-facing values are empty (no binding, zero storage, no hypotheses) and whose
EVM and budget values are M3's. It then runs `holon sorts`, `types`, `model`, `disch`, `derive --catalog
holon-rules/1.15` and `run` in a scratch test milestone T510. No rule producer takes a Go-only document without a target
sidecar (go_laws, link roles) that no generator writes, so a Go entry is extracted and derives nothing: a reasoned miss.

## What ran before the prereg

For sizing and feasibility only, never on a corpus commit: the CI toolchain install (PINS ALL PASS 13/13), and the I31
toy fixture (tests_m3/fixtures/disch/a, a contract written for a test) through sorts, types, model, disch, derive with
catalog holon-rules/1.15 and generated UNDO, FACT and DISCH sidecars, and run (10 laws derived: 2 DISCH, 8 SYM; one
DISCH law REFUTED with replay not_applicable). No corpus repository was cloned or read before this commit.

## Predictions and regressions

See the key. P1 no entry is detected (the per-entry table); P2 extraction reach (Solidity: only c17 extracts; the
nitro-family Go entries fail; at least 7 of the other 11 Go entries extract); P3 no entry derives a law of its label
rule; P4 every finding, if any, is unreplayed. R1 the exit; R2 the rows are the corpus's; R3 the scoring is the
instrument's and can fail; R4 the evidence re-checks; R5 determinism; R6 nothing in M0-M3 changes and the runner is
target-agnostic.

## The adversarial phase (run by the builder after the build, before scoring is reported)

Try to inflate recall and precision (looser localization, any-rule detection, counting unreplayed findings as true),
show what each inflation would read and that the preregistered scoring rejects it, and check that the scoring can fail
(planted rows). Fold in the fixes; disclose every change after this commit as an amendment.

## Hard constraints

AGENTS.md's rules, all of them; never clone, fetch or read anything under scroll-tech/ or spec/heldout/; nothing under
holon/ names a target or a corpus system; no model identifiers in any file, commit or PR text; author commits as
Claude <noreply@anthropic.com>; never force-push, rebase or amend.
