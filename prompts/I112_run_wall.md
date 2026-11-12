# I112 (M6, generality): the run wall

Branch `claude/i112-run-wall`, based on I111's branch `claude/i111-types-totality` (3b36f18a; it holds the types
fallback). When the lead lands I111 (re-stamp branch `claude/ci-i111-restamp`), merge the lead
`claude/holon-v2-bend2-c6z3cd` with a merge commit before the first measured run, and record the merged head's sha.
Never rebase. Branch only: this key lands after I111 (Q85). Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md,
BUILD_PLAN §4 "M6: generality" and docs/iterations/I111.md first.

## The gap (I111, the types totality)

I111 took down the types wall: 9 corpus entries reach derive and 107 laws are derived. None is decided, because of
the run step:
- the composed driver's run call sends route C's laws (PAR) to `holon.pipeline` with typed-only arguments
  (`--sidecar`, `--disch`, `--fact-sidecar`), and the milestone runner refuses the arguments;
- one DISCH section error (`holon.disch.section.SectionError`) stops the whole DISCH runner.

On the spent targets, Aave V3 passes types and DISCH then refuses; EigenLayer stops at types on a member-layout
refusal that I111's O1 does not cover.

## Build (HUMAN_ANSWERS Q80-Q85), generically, justified by semantics, never by a corpus entry

1. **Per-runner routing and section-level errors (Q82).** The composed driver's run call sends every law to the runner
   its rule family belongs to, with that runner's own arguments. A DISCH section error makes that section's laws
   UNKNOWN, each recorded with the error; every other section still runs. An error never yields PROVED. Every REFUTED
   needs its replay and, on a deployed system, follows Q56.
2. **O1 widened (Q81).** `extracted_eval.Unsupported` and the member-layout refusal also make a document opaque,
   under I111's O2-O7, unchanged. Each new refusal class gets its own planted fixture in three shapes (alone,
   cross-document, constrained-state: UNKNOWN). A milestone-wide input error stays a refusal of the milestone; only a
   per-document refusal becomes opaque.
3. **`withhold()` inside the driver:** it covers `gen/` and the run details itself. No per-law id or verdict on a
   deployed system's code reaches a commit.
4. **Q80's preflight:** a counted run checks every toolchain-set binary its protocol can select against
   `config/toolchains.json`, refuses to start if any is missing, and records the check in the run's snapshot.

Not in this key: a per-document DISCH fallback (Q83), a per-component search cutoff (Q84).

## Measures

Through `holon eval holon --compose` with I111's protocol as the base (`spec/M6/lib/i112_run.json`): entries reaching
each stage; laws derived, decided and UNKNOWN as aggregates; section errors per runner; documents opaque per refusal
class; Morph byte-identical (re-stamp only). Smoke measures on contaminated data. Runs on EigenLayer and Aave V3
(spec/heldout2/target.json) are labelled `contaminated: post-I107` and follow Q56 and Q72.

The counted run is the first measured run that finishes (Q80, Q76, Q69); every prediction is scored on it.

## Invariants

AGENTS.md's hard rules; prereg first (this prompt, spec/M6/predictions/I112.json and its aggregate entry, the contract
tests_m6/test_i112_run_wall.py; PREREG OK before any build commit or measured run); Morph's M0-M3 outputs
byte-identical (re-stamp only); holon/ names no target; soundness over coverage; never read spec/heldout/ or
scroll-tech/; rulings read before the prereg and before each measured run (Q76).

## Report

docs/iterations/I112.md and a draft PR against the lead whose body starts `I112 ready: <one-line outcome>`, with Done
(the frozen suite's summary line), Surprises, Questions for the human and Not done.
