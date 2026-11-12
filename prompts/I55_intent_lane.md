# I55: the intent lane (M5)

Rendered from `docs/BUILD_PLAN.md` §4 I55 (milestone M5) and the session brief, with the whitepaper's §5.10 (the intent lane), §5.4 (SYM route (i)), §11.3 O10 (documentation–code disagreements, F12.8) and §12 row L10. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/BUILD_PLAN.md` §0.1, §0.2, §2, §3 and the M5 header with §4 I54–I58.

Base: I54's branch `claude/i54-m5-definitions` (PR #134, not landed), which holds the L6, L9 and L10 definitions I55 is measured by. The draft PR goes against `claude/holon-v2-bend2-c6z3cd`, stacked on #134, and waits for the lead (M4 and M5 code lands only after M3's exit). I55 changes no M0–M3 result, law, record or generated file.

## Goal (BUILD_PLAN §4 I55)

- `holon/intent/atomize.py` turns NatSpec and doc comments into clause records with exact source spans.
- Reviewed clauses compile to `laws/INTENT/`.
- A refuted intent law is an intent obstruction.
- Intent feeds SYM route (i).
- **Preregister:** the clause count and the expected intent obstructions, O10's doc-drift items included.
- **Exit:** L10 is computed by I54's definition (`spec/M5/preregistration.json` `definitions.L10`).
- **Risk:** unreviewed clauses cannot produce findings.

## The lead's conditions (review of I54 on PR #134), in the measuring key before any record it scores

1. **The atomizer never reads I54's census.** Checked mechanically: nothing in the atomizer's import and file-access closure reads `results/M5/l10_census*` or `holon.m5.census`, and its output is byte-identical with the census file absent.
2. **The trivially-true share** of the laws is reported beside coverage, defined in the key before the build.
3. **The overall verdict** still needs control_recall.
4. **A second census** resolving `@inheritdoc` is allowed only under a later key, preregistered before the atomizer runs. The 82-clause base census is never replaced. (I55 adds none.)
5. **Corpus truth.** No corpus item is scored until a separate corpus-truth key exists (fresh labellers with no repository context, given only the verbatim text). Build everything up to it and list the scoring as pending.

## Process

1. Prereg first (§0.1): this prompt, the key `spec/M5/predictions/I55.json`, the contract tests in `tests_m5/`, and the instruments they pin. `python -m holon audit prereg --milestone M5` prints PREREG OK before any build commit.
2. The adversarial phase, run by the builder (no separate agent): try to break the prereg, then the build, and try to game L10; fold in the fixes. I54's W2 needs a review by someone other than the compiler: exactly one fresh reviewer with no context beyond its input, disclosed.
3. Build: generate, don't hand-write; deterministic; laws from generators, proofs from proof generators.
4. Validate: the new tests, `python tools/freeze.py check`, the gates CI runs with M0–M3 unchanged, and the frozen suite if feasible.
5. Report: `docs/iterations/I55.md` and a draft PR whose body starts `I55 ready: <one-line outcome>` and has Done, Surprises, Questions for the human and Not done.

## Hard constraints

AGENTS.md's hard rules, all of them. Never clone, fetch or read anything under scroll-tech/ or spec/heldout/. No model identifiers in any file, commit or PR text. Commits as Claude <noreply@anthropic.com>; never force-push, rebase or amend; merge commits only (merge #134's branch in if it moves).
