# I124 (M6, generality): the post-derive crashes

Branch `claude/i124-post-derive-crashes`, based on the lead `claude/holon-v2-bend2-c6z3cd` at e3be9798 (I118's
landing). Merge the lead with a merge commit whenever it moves; never rebase. Branch only (Q88): the lead lands this
key. A crash fix changes the default path (Q106 (4)), so this key measures on the base after I122 and I123 land (and
I121, if it lands in between), with Q104's combined base protocol `spec/M6/lib/base_run.json` as the lead regenerates
it there, merged into this branch when the coordinator names it. Two runs on that one protocol (Q104 (2)): the base
code (the baseline) and this key's code (the counted run); their difference is this key's one change.

## The walls (I120, Q106)

With every stage reading the whole extracted document, the corpus derives 268 laws and decides 0: the full documents
reach post-derive stages that crash. The lead filed three fail-closed instrument defects for this key. Their
mechanisms, found by reproducing c04 and c19 in this key's sandbox (I120's code and protocol, not counted, nothing
committed) before this prereg:

- **F-M6-06.** `holon.gen.goloop.cells_literal` takes `parts[-1]` of an empty list. A Go-op component whose ops read
  no field of the carrier (I117's straight-line class) has a carrier of zero cells. Its one value is the empty
  sequence, every candidate witness is that sequence, and `counter_proof` raises IndexError. The milestone runner
  exits 1 and every law of its group is left without a record.
- **F-M6-07.** The DISCH runner builds each document's typed model (`holon.sorts.evaluate3.Evaluator.build`, which
  compiles it with Bend). On c19 the compile failed, and the resulting `EvalError` stopped the runner, so none of the
  milestone's DISCH laws got a record. The ledger calls it a generator emitting code its checker rejects. It does
  not reproduce as that: the same model bytes (22 MB) compile in Bend with exit 0 here, and the compile peaks at
  about 11.7 GB of memory on a 15 GB container. I120's run stage took 120 s in total, so it was not the checker's
  180 s time-out. The checker run left no module, and the error recorded only the checker's output, not why.
- **F-M6-08.** `holon bind --unbound skip` reads `gen/<M>/model/<component>.bend`, which the milestone runner writes
  only when it first decides a law of the component. When a runner never reaches a component (F-M6-06's crash, or
  I118's per-document re-run of another document), the model does not exist. bind_law then raises FileNotFoundError,
  which is not a BindingError, so bind refuses the whole milestone and binds nothing.

The lead approved this reading and the plan below as HUMAN_ANSWERS Q108: F-M6-07 is a resource limit, not a generator
defect. A resource kill depends on the environment, so the record always names its cause. The preflight memory record
(Q108 (4)) is not added here: it stays the ledger entry F-M6-11.

## Build (from the semantics; nothing more permissive)

1. **F-M6-06:** the empty sequence is Bend's empty list `[]`. It is the only `List<&2, U32>` of length 0, so this is
   exact. Every non-empty sequence is written byte for byte as before. Every decision stays Bend's: a counter-law at
   `[]` that Bend rejects leaves the law UNKNOWN.
2. **F-M6-07:** a compile that fails for any recorded cause confines its failure to its document under the opt-in.
   (a) The compile error names its cause: the exit code, the signal that ended the checker, the
   time-out, or exit 0 with no module written. (b) Under the DISCH runner's `--section-errors unknown` (I112's
   opt-in, in the base protocol), a document whose model cannot be built is refused the way a document whose section
   is refused already is. Its laws are UNKNOWN with the error and nothing is attempted, and every other document is
   decided as before. Without the opt-in the error stops the runner, as before. The generator is not changed:
   it emits code Bend accepts.
3. **F-M6-08:** a law whose model the run never generated is unbound with that reason (a BindingError), and every
   other law is bound exactly as before. Anything else that fails still refuses as before. The binding check still
   refuses every decided record of an unbound law. A bind failure confined to one document stays I118's per-document
   fallback where the protocol opts in.

## Fixtures and controls (prereg; written from Go's and Bend's semantics, never corpus code)

- `tests_m6/fixtures/i124/src` (package latch):
  - Latch: no op reads a field. Trip always panics (its totality law is false), and Rest never panics (true).
  - Valve: a second component, guarded on one bool field.
  - Stale: loads a field after storing it, outside the model class, so it is the just-outside case.
- `tests_m6/fixtures/i124/machines` (package till): Till and Drawer, two well-typed Go machines. The planted fault
  runs the compile of Drawer's typed model on the real checker under a time-out it cannot meet, a deterministic
  recorded cause (Q108). The fault is written into the scratch root only.
- For each defect: the crash on the base, a clean run under the fix, the soundness control, and the case just outside
  the handled shape. The soundness controls:
  - every REFUTED is replayed on the real Go code;
  - the true law is never REFUTED;
  - the faulted document's laws are never decided;
  - a planted decided record of an unbound law is refused.
- Morph: every committed M0-M3 output byte-identical (re-stamp only), by the CI gates and `holon land dirty`.

## The usual rules

- Prereg first: PREREG OK, committed and pushed before any build commit or measured run.
- Q56, Q72, Q89 (decided counts never split) and Q101.
- The no-read rule (Q86 (3)), with a read-receipt.
- The key's own CI job, `tests-m6-i124`.
- The target-agnostic test locally.
- Every earlier `tests-m6-*` job locally after each lead merge.
- The counted run is the first that finishes (Q80, Q76, Q69).
- Corpus measurements are smoke on contaminated data. This key runs no spent target.
- Any REFUTED on corpus code outside Q56 (4)'s exemption stays in the vault. It is replayed, classified, and reported
  to the coordinator as a potential vulnerability unless shown to be a model defect or an intended asymmetry.

## Report

docs/iterations/I124.md (each prediction's outcome, the soundness argument, surprises, what is left) and a draft PR
against the lead whose body starts `I124 ready: <one-line outcome>`.
