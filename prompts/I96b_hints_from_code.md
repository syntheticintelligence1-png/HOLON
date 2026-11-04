# I96b (= I46c, second half): the refinement hints derived inside the pack, then the one blind rerun

**Goal.** I96a's sandbox and its control locate the cause of I95's 11 DISCH disagreements: the blind tree had no
refinement hints (`results/M3/sorts/refinement/hints.json`). The hints are the real target's external-call answers,
and the DISCH and I30 searches read them. I96b derives them inside the pack. The lead's rulings for I96 (2026-11-04,
11:17 and 11:55) govern, and the contract is the docstring of tests_m3/test_hints_i96b.py.

**The principle.** Declare inputs, derive generated artifacts, never pack outcomes.

**The build.**
- **The fragments binding.** `python -m holon binding --fragments-out --milestone M3 [--check]` derives
  `replay/M2/fragments.json`, byte-equal, from:
  - the declared `spec/M3/lib/fragments.json` (abstract, window, the binding's doc and document);
  - `spec/M3/lib/binding.json`.
  It gets a REGEN entry right after binding.
- **The refinement.** `python -m holon refinement --milestone M3 [--check]` runs I30's R5:
  - `holon fragments --sources m1,boundary,target`, with the results/M2 witness source dropped on both sides;
  - the typed model it generates as the evaluator;
  - it writes `hints.json` and `keys.json`.
  A CI test runs `--check`, with sha256 rows.
- **The declared inputs**, each with its sha256 in the protocol:
  - the M1 facts;
  - the M1 model definitions (`.lib.json`, `.lean.json`);
  - `spec/M1/policy_hints.mjs`, as search configuration, after the H1 check with a plant.
  `go_slices.lib.json` stays out.
- **`statement_diff.derived_under`** caches refusals, with a regression test.

**The rerun.** One fresh blind session on the pack of the commit that lands I96b, on the session's own typing, then
the comparison. The predictions (hints, keys, the 11 DISCH, the 17 SYM/UNDO/FACT laws, and E2) are in the key.
