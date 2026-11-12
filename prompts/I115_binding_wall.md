# I115 (M6, generality): the binding wall

Branch `claude/i115-binding-wall`, based on I112's branch `claude/i112-run-wall` (a5db40d6; it holds the per-runner
routing). When the lead lands I112, merge the lead `claude/holon-v2-bend2-c6z3cd` with a merge commit before the first
measured run, and record the merged head's sha. Never rebase. Branch only (Q88): the lead lands this key. Read
AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality" and docs/iterations/I112.md first.

## The gap (I112, the run wall)

I112 routed each derived law to the runner of its rule family. On the corpus 14 entries reach derive and 107 laws are
derived, 1 decided (PROVED and REFUTED together, Q56). The milestone runner writes no record for any of its 93 PAR laws:
it stops at `holon.bindings.kernel_cone` ("M.<name> in the statement resolves to no kernel entry"). The composed route
runs no `holon bind`, so no law of it is bound as route A's milestones are (spec/bindings, G2).

Reproduced on a planted fixture before the prereg (tests_m6/fixtures/i115): the Go-op model (`holon.gen.goloop`) models
an op only in its loop class; any other op is Unsupported and its definitions are not generated, so the law naming it
is UNKNOWN by its decider, and then `holon.codecrun.decide` computes that law's kernel cone, which raises and stops the
whole runner. The decidable laws of the same run get no record.

## Build (HUMAN_ANSWERS Q88 (2), Q87), generically, justified by semantics, never by a corpus entry

1. **The binding (Q88 (2)).** A law is bound by the kernel cone of its statement over the model it is decided on. A law
   whose statement names a definition its model does not define cannot be bound, so it cannot be decided: under
   `holon run --unbound unknown` the milestone runner computes the binding first and records such a law UNKNOWN with
   the error, nothing attempted; every other law is decided as before. The composed route then binds its own
   milestone with `holon bind` over the derived statements and the models the run generated (`--unbound skip` lists
   the laws it cannot bind), in its scratch root, and a binding check admits a decided record only when its law is
   bound with the record's statement hash and model. No family is routed around it: G2 binds every law of a
   milestone. A planted control shows that a mis-bound law is refused.
2. **Q87, the go pins.** Each go release in `config/toolchains.json` gains its installed `bin/go` sha256; the preflight
   checks it under the new protocol key; a mismatching environment refuses a counted run, and the refusal is recorded.
   I112's basis (solc by sha256, go by version line) stands for I112's run.

Not in this key: the per-document DISCH, evidence and derive fallbacks (I116).

## Measures

Through `holon eval holon --compose` with I112's protocol as the base (`spec/M6/lib/i115_run.json`): PAR laws bound,
run and decided; laws derived and decided as aggregates (Q89's wording); entries reaching each stage; whether Q88 (1)'s
gate is met (at least 1 law decided on the corpus and at least 1 on a spent target); Morph byte-identical (re-stamp
only). Smoke measures on contaminated data. Runs on EigenLayer and Aave V3 (spec/heldout2/target.json) are labelled
`contaminated: post-I107` and follow Q56 and Q72; any REFUTED on them, or on corpus code other than a match to an
entry's known, fixed defect, is a potential vulnerability: vault only, replayed and classified, reported to the
coordinator by commitment.

The counted run is the first measured run that finishes (Q80, Q76, Q69); every prediction is scored on it.

## Invariants

AGENTS.md's hard rules; prereg first (this prompt, spec/M6/predictions/I115.json and its aggregate entry, the contract
tests_m6/test_i115_binding_wall.py; PREREG OK before any build commit or measured run); Morph's M0-M3 outputs
byte-identical (re-stamp only); holon/ names no target; soundness over coverage; never read spec/heldout/ or
scroll-tech/, I113's candidates or spec/heldout3/ beyond commitment.json (Q86 (3)); rulings read before the prereg and
before each measured run (Q76); decided counts never split (Q89).

## Report

docs/iterations/I115.md and a draft PR against the lead whose body starts `I115 ready: <one-line outcome>`, with Done
(the frozen suite's summary line), Surprises, Questions for the human and Not done.
