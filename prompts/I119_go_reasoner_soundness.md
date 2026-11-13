# I119 (M6, generality): Go reasoner soundness

Branch `claude/i119-go-reasoner-soundness`, based on I117's branch `claude/i117-go-op-semantics` (93d12670; it holds
the opaque-arithmetic rule). When the lead moves, merge it with a merge commit; never rebase. Branch only (Q88): the
lead lands this key, after I118. Read AGENTS.md, docs/M0_SPEC.md, docs/BEND_PRIMER.md, BUILD_PLAN §4 "M6: generality"
and docs/iterations/I117.md (Surprise 1) first.

## The defect (I117's report, Surprise 1; HUMAN_ANSWERS Q93 (1), the lead's ruling)

Before I117 the Go frontend's path reasoner read Go integers as unbounded: it pruned branches reachable only through
wraparound (`x+1 < x`), and an index bound implied only by unbounded arithmetic made a site "safe". A committed PROVED
law over a Go document could rest on an incomplete path set: a possible soundness defect of HOLON's own extraction.

## (a) The audit, read-only, first

`tools/i119_audit.py` re-extracts every committed Go document (Morph's M0-M3: spec/M2/facts, spec/M3/facts; every
corpus entry's committed Go documents, codec and machine, deduplicated by config) in scratch copies of holon/: the old
reading at the audited commit, and the same with only the rule (paths.py's Reasoner opaque). It lists the documents
whose paths change and the committed decided laws that read them. The list stays in the vault; committed are
per-milestone counts and a sha256 bundle commitment only (results/M6/I119/audit.json). One line goes to the
coordinator: `I119 soundness audit: <milestone>, <count> committed decided laws affected`. The defect enters the
findings ledger (audit/M6_findings.jsonl) as a defect of HOLON's own extraction. Nothing committed moves in (a).

Extension A2, measured apart: the same rule in the site reasoner of functions with no path set
(analyses.py's dominator-atom Reasoner). (b) does not flip it without a ruling.

## (b) The default flip

The rule becomes the default for every Go document (extract go and extract go_machines, every config version). The
narrow-arithmetic loop mode stays. Changed documents are re-extracted; affected laws re-derived and re-decided through
the statement-diff log, never edited. A newly REFUTED law on deployed code follows Q56.

## Planted fixtures (Go semantics only)

tests_m6/fixtures/i119: Inc64 (a branch reachable only through 64-bit wraparound) and Idx (an index the unbounded
reading calls in bounds, false under wraparound), confirmed against the pinned go 1.24.7 (Q90's differential method).

Predictions: spec/M6/predictions/I119.json. Tests: tests_m6/test_i119_go_reasoner_soundness.py.
