# I50b (M4): a contaminated rerun of the held-out target

Rendered from the coordinator's brief for I50b and the lead's terms (a)-(e). Read I49's and I50's prompts and reports
(docs/iterations/I49.md, I50.md) first. I50b adds a rerun **beside** the sealed I49/I50 result; it never replaces it.

Base: `claude/i50-heldout` (#145, stacked on #144 and I47's #141). One draft PR against
`claude/holon-v2-bend2-c6z3cd`, stacked on #145. Merge commits only; landing waits for M3's exit.

## The situation

- I49 (#144) held 4 of 6 predictions: G8 is red because the pinned frontend counts two statically dead statements
  (`ScrollChain.sol:748-750`, `:749`) as unaccounted.
- I50 (#145) held 0 of 5: the pinned sort pass has no rule for the frontend's `update` term, so `holon sorts` refuses
  the document and no law is derived (results/targets/scroll/derive_refusal.json).
- The lead ruled that these stand as the result of record. The seal on readers has lifted.

## The lead's terms

- **(a) Prereg first.** This prompt, the key `spec/M4/predictions/I50b.json`, the contract
  `tests_m4/test_i50b_rerun.py` (K1-K4) and its instruments (`spec/M4/lib/heldout_rerun.json`, `tests_m4/_i50b.py`,
  the fixture `tests_m4/fixtures/i50b/`) are committed and pushed, with PREREG OK, before any change to holon/ or any
  rerun. The sealed I49/I50 files stay byte-identical (I50b-R1).
- **(b) Generic producer changes only**, each justified by what the construct means in Solidity, never by the target's
  code, and each a new version of an existing contract so that the old version (the sealed route, every M0-M3
  sidecar) is unchanged:
  - `holon-sort-types/0.2`: rules U1-U3, the sort pass's reading of `["update", B, T, v]` (B with one member
    replaced: a memory value, stored only when assigned back to storage);
  - extraction `sidecar_version 2`: rule D1, a branch that no reach of its if statement selects (the condition a
    constant at every reach) is `dead_code` debt with a reason, never unaccounted. G8 itself is unchanged.
  - Neither holon/rules/ nor the catalog changes. Every changed holon/ file is disclosed in
    spec/M4/lib/heldout_disclosures.jsonl.
- **(c) Morph is unaffected.** No M0-M3 output changes. The modules sit in generator closures, so their digests move;
  the re-stamp is planned with `holon land plan` and waits for M3's exit. The plan goes in the PR.
- **(d) The contamination label** `contaminated (post-seal change)` is on every rerun record and metric, and
  `holon target compare` puts each rerun number beside its sealed counterpart (rule C1).
- **(e) Fresh predictions.** No I49/I50 threshold or prediction is reused. I50b's are stage by stage (I50's Surprise
  2): P1 the sort pass accepts; P2 derive completes in a predicted range; P3 the run stops at the unchanged model
  generator; P4 G8 under D1; P5 the rerun gate's I49 checks and L2.

## The rerun

A sibling target `targets/scroll_i50b/` (rule T1b): the sealed description with its paths moved, no `checkout.sealed`
(so the sealed target stays the one target that names the seal), `rerun_of: scroll` and the label. Its scope sidecar is
the sealed one at sidecar_version 2. Route R1b-R6b of heldout_run's R1-R3 with sidecars Q1b-Q4b (Q1b at
holon-sort-types/0.2): extract, coverage, diagram, derive, run, replay (binding null: not_run), gate, compare.

## Process

1. Prereg, push, PREREG OK.
2. The adversarial phase (this session's own, no subagent): try to make each rule target-specific by accident, and
   check it is not: the fixture contract, the synthetic document, the development target under the new versions,
   the target-agnostic scan.
3. Build, then rerun, all labelled contaminated.
4. Validate: the new tests; the sealed suites (I50b-R2); `python tools/freeze.py check`; the gates CI runs; the
   target-agnostic scan; the frozen suite if feasible.
5. docs/iterations/I50b.md and the draft PR (`I50b ready: <one-line outcome>`; Done, Surprises, Questions for the
   human, Not done).

## Hard constraints

AGENTS.md's rules, all of them; nothing under holon/ names a target; no model identifiers in any file, commit or PR
text; author commits as Claude <noreply@anthropic.com>; merge commits only.
