# I52 (M4): baselines on Morph, the corpus and the held-out target

Rendered by the coordinator from docs/BUILD_PLAN.md §4 I52 for this session, which covers Morph and the corpus. The
builder works alone, all the way to a draft PR; the coordinator reads the PR.

## Read first
- AGENTS.md (the hard rules), docs/M0_SPEC.md, docs/BEND_PRIMER.md.
- docs/BUILD_PLAN.md §0.1 (preregistration), §0.2 (session protocol), §2 (invariants), §3 (iteration map), the M4
  header and §4 I52.
- whitepaper.md §13, the evaluation protocol: equal budgets, baselines, the common findings schema.
- docs/HUMAN_ANSWERS.md: Q16 is yes (baselines); Q20 is N = 20.
- docs/iterations/I48.md and spec/eval/: the corpus (spec/eval/corpus.json), the controls and the labels. tests_m4/ and
  spec/M4/ show M4's prereg layout. For conventions: docs/iterations/I97.md, I98.md and I99.md.

## Toolchain
- Install HOLON's pinned toolchain as CI does (.github/ci/install_toolchain.sh; link_paths.sh when $HOME is not
  /root). `python .github/ci/verify_toolchain.py` must print PINS ALL PASS (13/13). Always export BEND_NO_TELEMETRY=1.
- Baseline tools: install slither, echidna, medusa, hevm and halmos pinned under ~/.holon/tools, plus Go's native
  fuzzing. Add their pins the way config/holon.json pins tools, as a separate set that CI's toolchain job does not
  require (unless the design calls for it, with the reason). Keep the 13 existing pins unchanged. A baseline that
  cannot be installed is recorded as missing, never substituted silently.

## Base and landing
- Base: claude/holon-v2-bend2-c6z3cd at 4fd64a52 or newer; merge the lead in if it moves (merge commits only).
- The lead lands M4 code only after M3's exit commit is fixed, so the PR waits. I52 changes no M0-M3 result, law,
  record or generated file. One draft PR against claude/holon-v2-bend2-c6z3cd; do not merge it.

## The iteration
- Goal: the pinned baselines slither, echidna, medusa, hevm and halmos; Go fuzzing, 2-cycle round-trip testing,
  frequency-based spec mining and agent-only review; all at equal budget, reported in a common findings schema, run on
  Morph and the corpus pre-fix commits.
- Scope: Morph and the corpus only. The held-out target waits for I49 and I50: never read spec/heldout/. Build the
  runner so the held-out run is a single command once I50 lands, and list it as pending under Not done.
- Preregister, before any baseline runs: each baseline's expected detections per system and per corpus entry (for
  example, 2-cycle testing finds the O1/O2 class and single-component analyzers find no relational obstruction); the
  equal budget (wall clock and CPU per system, the same for every baseline); the common findings schema; how a
  baseline finding is matched to a corpus label.
- Agent-only review: fresh subagents, given only the code under review and the same budget, never HOLON's outputs or
  the corpus labels; same-family reviewers are labelled as such.
- Exit: results/eval/morph/<baseline>.json and the corpus results, in the schema, for every baseline, each run or
  recorded as missing with a reason.

## Process
1. Prereg first (§0.1): this prompt, the key spec/M4/predictions/I52.json, the contract tests in tests_m4/ and the
   instruments they pin; `python -m holon audit prereg --milestone M4` prints PREREG OK before any baseline runs or any
   build commit. Before building, one fresh subagent reviews the prereg adversarially; its blocking findings are folded.
2. Build the runners, then run the baselines; deterministic where the tools allow; seeds and versions recorded.
3. Validate: the new tests, `python tools/freeze.py check`, CI's gates with M0-M3 outputs unchanged, and the frozen
   suite if feasible.
4. Report docs/iterations/I52.md (each prediction's outcome, surprises, missing baselines) and open the draft PR, whose
   body starts `I52 ready: <one-line outcome>` and has Done, Surprises, Questions for the human and Not done.

## Hard constraints
- AGENTS.md's rules, all of them. Never clone, fetch or read anything under scroll-tech/ or spec/heldout/. Clone corpus
  repositories only as I48's manifest names them, at the pinned commits. No model identifiers in any file, commit or PR
  text. Commits authored as Claude <noreply@anthropic.com>; never force-push, rebase or amend.
