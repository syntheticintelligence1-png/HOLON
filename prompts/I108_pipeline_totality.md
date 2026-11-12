# I108 (M6, generality): pipeline totality, pass 2

Branch `claude/i108-pipeline-totality`, based on the lead `claude/holon-v2-bend2-c6z3cd` (c2cd112c), with I103's
branch `claude/i103-frontend-reach` (#172) and I105's `claude/i105-go-machines` (#170) merged. Read AGENTS.md,
docs/M0_SPEC.md, docs/BEND_PRIMER.md and BUILD_PLAN §4 "M6: generality" first.

## The gap

I103 and I105 made the frontends reach new code. Their counted runs on I51's corpus still end before any law, at
concrete stages. Fix each generically, justified by semantics, never by a corpus entry:

- (a) **Signed operators in the sort pass.** `holon sorts` has no rule for `s<`, `s>`, `sext` and the rest of the signed
  family the IR defines for intN (I105 run 2: 7 of 8 Go entries stop there). Add real sort rules, consistent with the
  IR's two's-complement semantics, and compile them in the typed model. Morph's documents hold none of these heads.
- (b) **String- and bytes-keyed mappings (SP_b)** in the structural model: compile them structurally, or a sound
  opaque-key fallback whose keys are never equated or ordered to prove anything (Q61). Whole-map havoc may stay refused.
- (c) **Project layout.** foundry.toml / remappings.txt remappings into the solc import mapping, read at the pinned
  commit only and never invented; git submodules initialized only at their gitlinked commits, refusing URLs the clone
  rule excludes (Q51, Q59); every submodule's URL and commit recorded.
- (d) **SYM in multi-model milestones (Q58):** derive per model inside the milestone; do not split it.
- (e) **Go machines: the initial state and nil maps (Q60).** R0 is what the constructors return (the zero state only
  without one); a write to a nil map is a panic. If full semantics does not fit, every law over a step that writes a
  possibly nil map is UNKNOWN, disclosed.

## Invariants

AGENTS.md's hard rules; prereg first; Morph's M0-M3 outputs move by re-stamp only (every new rule applies only where no
hand sidecar exists or under an explicit opt-in); holon/ names no target; soundness over coverage (a fallback may only
make a law weaker or UNKNOWN); responsible disclosure (Q56: the smoke run stops at derive and records no verdict);
no tuning to the corpus; no reading `spec/heldout2/` beyond `commitment.json` nor any repository on I106's candidate
list (a submodule URL named there is refused).

## Predictions

spec/M6/predictions/I108.json (P1-P10, R1-R2), checked by tests_m6/test_i108_pipeline_totality.py; the run protocol is
spec/M6/lib/i108_run.json. The corpus measures are smoke measures (I107 scores).

## Exit

(a)-(e) built or reported with reasons; the corpus smoke counts; M0-M3 byte-identical (re-stamp only); the report
docs/iterations/I108.md; a draft PR whose body starts `I108 ready: <outcome>`.
