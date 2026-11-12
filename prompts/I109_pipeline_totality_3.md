# I109 (M6, generality): pipeline totality, pass 3

Branch `claude/i109-pipeline-totality-3`, based on I108's branch `claude/i108-pipeline-totality` (cf1a536c; #178 had
not landed when this key started), which holds the lead's M6 tools landing (55c679df). The lead is merged whenever it
moves. Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality" and
docs/iterations/I108.md first. This key lands only after I107 (HUMAN_ANSWERS Q65).

## The gap

I108 moved the frontier one stage deeper: no Go machine stops at sorts, but every Go entry meets a types refusal, and
Solidity entries hit the term-size budget. Fix each generically, justified by the language's semantics or the IR,
never by a corpus entry. A write that cannot be modelled soundly stays a havoc (over-approximation) or a refusal,
never a guess:

- (a) Types gaps of the Go machine rendering: a static method call's arity (the receiver is an argument), `len` of a
  word, whole-string and whole-map writes.
- (b) The Go machine frontend's toolchain rule: I103's go set and rule (the lowest pinned release at or above the go
  directive).
- (c) DISCH's sign analysis (D9) for signed comparisons: rules sound under two's-complement order, proved on planted
  fixtures.
- (d) SP_b, string- and bytes-keyed mappings, through Q61's opaque-key fallback: opaque keys are never equated or
  ordered to prove anything; a read after a write to a syntactically different key is unconstrained.
- (e) The Solidity term-size budget as a recorded, preregistered parameter with a higher M6 tier. Never drop terms.
- (f) Pragma selection through remapped imports (I108's Not done).
- (g) Q60's constructor rule for R0 and Q64's default flip (nil maps UNKNOWN by default; the only opt-out an explicit
  key recorded in the document); I105's demo law re-decided (expected UNKNOWN), disclosed.
- (h) Q62: a missing link sidecar means no codec components.
- (i) Q63: go_ops and go_laws over several documents, if it fits.

(f) and (i) are stretch items: they carry no prediction, and are reported built or under Not done.

## Invariants

AGENTS.md's hard rules; prereg first; Morph's M0-M3 outputs move by re-stamp only (every new rule applies to Go
machine documents, to sidecars that name the new key, or where no hand sidecar exists); holon/ names no target;
soundness over coverage; Q56 disclosure (the smoke run stops at derive and records no verdict); no tuning to the
corpus; never read `spec/heldout/`, `spec/heldout2/` beyond `commitment.json`, `scroll-tech/`, any repository on
I106's candidate list, or any I107 output on the sealed targets.

## Predictions

spec/M6/predictions/I109.json (P1-P13, R1-R4), checked by tests_m6/test_i109_pipeline_totality_3.py; the run protocol
is spec/M6/lib/i109_run.json. The corpus measures are smoke measures (I107 scores).

## Exit

(a)-(i) built or reported with reasons; the corpus smoke counts; M0-M3 byte-identical (re-stamp only); tests_m6 green
except the records of missed predictions; the report docs/iterations/I109.md; a draft PR whose body starts
`I109 ready: <outcome>`.
