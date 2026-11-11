# I54b (M5): the corpus-truth key

Rendered from the coordinator's brief for I54b, the lead's review of I54 (PR #134, condition 5), `docs/BUILD_PLAN.md` §0.1 and the M5 section, and `docs/HUMAN_ANSWERS.md` Q9, Q9a, Q9b and Q11. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first.

## Goal

Preregister how the ground truth of I48's corpus (`spec/eval/corpus.json`, 20 entries) is labelled for L6 and L10, before I55 or I56 scores any corpus item. The procedure is I54's frozen `spec/M5/lib/truth_protocol.json` with its prompt `spec/M5/lib/truth_prompt.md`. Implement both exactly, and never edit them.

## Base

- Branch from `claude/i54-m5-definitions` (I54, PR #134). Open the draft PR against `claude/holon-v2-bend2-c6z3cd`, stacked on #134. Do not merge it.
- Nothing in M0-M3 changes.

## What the key pins, before any labeller runs

- The texts: each entry's verbatim text (title, a newline, the description), by sha256, exactly as each labeller receives it.
- The prompt, by sha256.
- The agreement rule: two labellers per entry; quotes are exact substrings of the entry's text (Q2's whitespace rule); an answer stands only when both labellers agree (Q3). A disagreement is recorded, never resolved by the builder.
- The output path (`spec/M5/truth/corpus.json`, the protocol's), and a schema for the labels.
- The labeller family. The default is same-family fresh labellers, disclosed as a limitation (the Q9b precedent). If the human runs a different-family labeller (Q9a), its truth is compared against the same-family truth, never pooled. Both paths are in the key.

## Make the labelling mechanical for the coordinator

- The coordinator launches the labellers. Each is fresh, with no repository and no context beyond its message.
- One packet per (entry, labeller), under `spec/M5/truth/packets/`: the exact message, the pinned prompt with the entry's verbatim text. Nothing else: no repository names, no fix write-ups, no labels.
- The labeller returns one JSON object (optionally in one fenced block) as its final message, in the schema.
- A collector takes the answers (one JSON file per entry and labeller), validates them against the schema and the pins (quotes are exact substrings; the packet hashes match), applies the agreement rule and writes the outputs. It is deterministic.
- Use as few labeller sessions as the frozen protocol's independence rule allows, and say how many that is.

## Process

1. Prereg first (§0.1): this prompt, the key `spec/M5/predictions/I54b.json`, contract tests in `tests_m5/`, and the packet generator and the collector as instruments. `python -m holon audit prereg --milestone M5` prints PREREG OK. Commit and push the prereg alone.
2. The adversarial phase, by the builder, with no subagent: try to leak repository context or labels through a packet, and fix it; check that every quote rule can fail.
3. Generate the packets, commit them, and stop. Run no labeller and launch no session. The draft PR's first line is `I54b ready: <n> packets pinned, collector at <path>; awaiting labellers`. Its body has Done, Surprises, Questions for the human and Not done; Not done lists the labelling run.

## Rules

- AGENTS.md's hard rules, all of them. No edit to a frozen file; never run `tools/freeze.py write`; never weaken a claim; generate, don't hand-write; determinism; no `bunfig.toml` or `.env`.
- The sealed held-out target is never read: nothing under `scroll-tech/` or `spec/heldout/`.
- No model identifier in any file, commit or PR text.
- Commits authored as Claude <noreply@anthropic.com>. Never force-push, rebase or amend; merge commits only.
