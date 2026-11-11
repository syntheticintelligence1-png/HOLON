# I56b: L6's corpus accuracy against the corpus-truth key (I54b)

The lead's condition 5 on PR #134: no corpus item is scored until a separate corpus-truth key exists. I54b (`claude/i54b-m5-truth-key`, PR #136) committed it at `29526bea` (`spec/M5/truth/corpus.json` and its run sidecar), and the lead released it to I56, which merged it as a merge commit. I56's key is immutable and does not pin that truth, so this key does, before any record it scores (I54's truth_pinning). Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, I54's and I56's keys first.

## Goal

Score L6's corpus accuracy by I54's definitions, unchanged:
- truth: each entry's `l6` in the pinned truth file, read as given. An undocumented or disagreed answer is never resolved; c13 is excluded.
- items: I54's `corpus_mapping`. A finding is an item only if it comes from I51's run on the entry's pre-fix commit and its law's spans meet a line the fix changes. I51's runs are the rows of `results/eval/holon/corpus.json`.
- score: `holon.games.metric.l6_v9` with the mapped items.

## Build (after the prereg is pushed)

- `python -m holon games corpus [--check]`: `results/M5/corpus/mapping.json` (per entry: truth, pre-fix commit, mapped findings or the reason there are none) and `results/M5/corpus/l6_corpus.json`.
- No file of I56's outputs (`results/M5/games/`, `gen/M5/games/`, `laws/M5/games/`) changes.

## Rules

AGENTS.md's hard rules. The truth file is never edited and never re-labelled. A missed prediction is a Surprise; the key is never edited.
