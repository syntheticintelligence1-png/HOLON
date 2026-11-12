# I105 (M6, generality): Go state machines

Branch `claude/i105-go-machines`, based on the lead `claude/holon-v2-bend2-c6z3cd`, with the M6 skeleton
(`claude/ci-m6-skeleton`) merged. Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md and BUILD_PLAN §4 "M6:
generality" first.

## The gap

Only the Solidity frontend (`holon/frontends/solidity/transitions.py`) yields transitions documents (state, actions,
guards, writes), which the typed rule families (DISCH, UNDO, SORT, FACT, SYM, OWN) read. The Go frontend
(`holon/frontends/go/`, config 0.3) extracts functions and codecs, but no state machine, so a Go-only system gives those
rules nothing: I51 recorded `no_producer` on 8 Go entries (c03, c04, c08, c09, c13, c14, c18, c19).

## Build

- The Go frontend emits transitions documents in the same IR as Solidity's: the same schema (holon-facts/0.3,
  extraction.kind "transitions") and term language, so `holon sorts`, `types`, `model`, `disch` and `derive` run on
  them unchanged. Extend the schema only where Go needs it, leaving every Solidity document byte-identical.
- Scope, in order (the lead's ruling): struct-field state first, KV stores second; if the night runs out, KV is Not done.
  - struct-field machines: a named receiver type whose fields are the state, its exported methods the actions. Guards
    from early `return ..., err` and `panic` paths; writes from field assignments, including through pointers to the
    receiver.
  - KV-store machines (the keeper pattern): state is a store accessed through Get/Set/Has/Delete with keys built from
    constant prefixes plus arguments, modelled as maps keyed structurally (as Q21's structural storage keys).
  - out of scope, reported as coverage debt: goroutines and channels, reflection, unbounded loops. A loop the frontend
    cannot bound becomes an opaque write set, never a guess.
- Soundness: a write the frontend cannot model makes the action's write set over-approximate (havoc); it never drops a
  write silently. Argue it, and test it with planted cases (a write through an alias, a write inside an unbounded loop).

## Predictions

Preregister, before any run on a corpus repository: machines and actions per I51 Go entry; whether the typed pipeline
completes on them; laws derived per entry. These are smoke measures; I107 scores.

## Exit

- Go transitions documents for the struct-field and KV-store patterns;
- the typed pipeline runs end to end on at least one Go-only machine, or the exact refusing stage is named;
- every Solidity document and M0-M3 output byte-identical (re-stamp only);
- tests_m6 green.

## Invariants

AGENTS.md's hard rules; prereg first (`python -m holon audit prereg --milestone M6` prints PREREG OK before any build
commit); Morph's M0-M3 outputs re-stamp only; holon/ names no target; soundness over coverage (a fallback only makes a
law weaker or UNKNOWN); never read spec/heldout/, spec/heldout2/ or scroll-tech/; justify every change by the language's
semantics, never by a corpus entry; no model identifiers in any file; merge commits only.

## Report

docs/iterations/I105.md: each prediction's outcome, the soundness argument, surprises and what is left. A draft PR
against the lead whose body starts `I105 ready: <one-line outcome>`, then Done (with the frozen suite's summary line),
Surprises, Questions for the human, Not done.
