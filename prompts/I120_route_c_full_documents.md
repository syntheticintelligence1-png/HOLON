# I120 (M6, generality): route C reads beyond the store limit

Branch `claude/i120-route-c-full-documents`, based on the lead `claude/holon-v2-bend2-c6z3cd` at 40da439d (I117's
landing dda3319a, then Q94). Merge the lead with a merge commit whenever it moves; never rebase. Branch only (Q88): the
lead lands this key. One change per measurement (Q92 (4)): the prereg, the build, the planted fixtures and Morph's
byte-identity check come first; the measured runs wait for the coordinator's word on their base (the landing before
this key's: I118's, then I119's), merged into this branch, and the base sha is recorded in the report. Read AGENTS.md,
BUILD_PLAN §4 "M6: generality" and docs/iterations/I117.md ("Why the PAR laws fell from 93 to 29", Surprise 2,
Question 1) first.

## The wall (I117)

Under `go.ops "typed"` every enumerated function carries its paths and typed terms, and the Go documents of c08, c09,
c14 and c18 (second package) grew past the protocol's `go.store_max_bytes` (1,000,000). `holon eval holon` removed a
Go document over the limit from the run's working tree right after extraction (`d["stored"] = ... <=
store_max_bytes`, then `unlink()`), before any later stage ran. Route C then had no Go-op document for those entries
and derived none of their PAR laws: 64 of I116's 93. Under `--compose`, `store_large` already applies the limit again
when the outputs are copied. The early removal is what made the limit an input of evaluation.

## The ruling (HUMAN_ANSWERS Q93 (2), the lead's)

A storage limit must not decide what is evaluated. The composed driver hands route C the full document from the run's
working tree or vault. The store limit then governs only what is committed: the sha256 and size, as now.

## Build

1. **The opt-in `go.store_scope "commit"`** (spec/M6/lib/i120_run.json: I117's protocol plus this key alone; default
   `"evaluate"`, every earlier protocol; any other value refused). Under it `store_documents` records each extracted
   document's sha256, bytes and stored, and removes nothing; every stage (roles, route C's Go-op documents, diagram,
   evidence, machines, derive, run, bind) reads the whole document from the working tree.
2. **What is committed is unchanged.** After the outputs are copied, `commit_documents` removes each document not
   stored from `<id>/facts/` (with `--vault`, it first keeps the whole document at `<vault>/<id>/facts/`, outside the
   repository); `store_large` then records every other file over the limit, as before.
3. **The record.** Under the opt-in each extracted document's row carries `evaluated: "full"` beside `stored`:
   `stored: false` with `evaluated: "full"` means evaluated in full, stored by hash.
4. **Out of scope, reported only:** c18's first document (3.9 GB under I116, killed during extraction under I117,
   exit -9). That is an extraction memory limit, not the store limit.

## Fixtures and controls (prereg)

The planted entry (tests_m6/fixtures/i120/planted.json) is a git repository built in a scratch directory from I117's
planted Go package (written from the Go specification, never from corpus code), run end to end through
`holon_run.run_entry --compose`:

- over the limit (a planted `store_max_bytes` of 8192, below its typed document's size): the route C laws are derived,
  and the committed output holds only the document's sha256 and size;
- under the limit (the protocol's own): the derived laws, and every committed byte apart from the storage fields, are
  identical either side of the limit;
- the control: the same small limit without the opt-in reproduces the wall (no Go-op stage, no PAR law);
- Morph: every committed M0-M3 output byte-identical (re-stamp only), by the CI gates and `holon land dirty`.

## The usual rules

Prereg first (PREREG OK, committed and pushed before any build commit or measured run); Q56, Q72 and Q89 (decided
counts never split); the no-read rule (Q86 (3)) with a read-receipt; the key's own CI job `tests-m6-i120`; the
target-agnostic test locally; every earlier `tests-m6-*` job locally after each lead merge; the counted run is the
first that finishes (Q80, Q76, Q69). EigenLayer and Aave V3 (spent, both Solidity): measurements only, labelled
`contaminated: post-I107`, aggregates and one bundle commitment per target. Any REFUTED on corpus or spent-target code
outside Q56 (4)'s exemption stays in the vault, is replayed and classified, and is reported to the coordinator as a
potential vulnerability unless shown to be a model defect.

## Report

docs/iterations/I120.md (each prediction's outcome, the soundness argument, surprises, what is left) and a draft PR
against the lead whose body starts `I120 ready: <one-line outcome>`.
