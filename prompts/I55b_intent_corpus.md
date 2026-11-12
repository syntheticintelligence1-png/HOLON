# I55b: the intent lane on the corpus (M5, L10 corpus_recall)

A follow-up key of I55, made when the corpus-truth key I54b (PR #136, `claude/i54b-m5-truth-key` at `29526bea`) committed `spec/M5/truth/corpus.json`. The lead's condition 5 (review of I54 on PR #134): no corpus item is scored until that key exists; the coordinator's message of 2026-11-11 then allowed merging the truth commit and scoring corpus items, the measuring key pinning the truth file's sha256 before any record it scores, and every undocumented or disagreed answer treated exactly as I54's definitions say (never resolved by the builder).

## Goal

Compute L10's corpus_recall (spec/M5/preregistration.json definitions.L10.measures.corpus_recall): corpus entries with l10 truth yes and an intent obstruction on their pre-fix commit, over such entries, min_n applying.

- The scored entries are those whose truth `l10` is yes or no, less truth_protocol.json's known_exclusions (c13). At the truth commit that is c17 alone (yes). The builder read the truth's `l10` field before this prereg to list them; nothing else in the truth file drives the lane.
- The lane is I55's, unchanged: the atomizer, the compiler, the model and the runner run on each scored entry's files at its prefix_commit. Only the score stage reads the truth.
- A law that compiles needs a review under I55's design V before it can be an obstruction; an unreviewed law produces no finding.

Read AGENTS.md, docs/M0_SPEC.md and docs/BEND_PRIMER.md first. Hard constraints as in prompts/I55_intent_lane.md.
