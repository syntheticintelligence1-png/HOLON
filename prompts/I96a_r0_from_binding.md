# I96a (= I46c, first half): DISCH's R0 derived from the binding

**Goal.** Derive DISCH's initial state R0 from the code-derived deployment record (gen/M3/binding/<stem>.json) with a
target-agnostic step: `python -m holon disch-r0 --milestone M3 [--check]`. The step writes two members of the DISCH
sidecar (spec/M3/lib/disch.json) and nothing else:
- its r0;
- its model_sidecar, naming the milestone's typing sidecar explicitly.

holon/analysis/closure.py gets no default, and `expected` is never written. The lead's rulings for I96 (2026-11-04)
govern; the contract is the docstring of tests_m3/test_r0_i96a.py.

**The rule (ruling 3).**
- Paths come through the DISCH document's layout.
- A scalar path holds its exact deployed word.
- A non-zero address-typed word is `T`.
- A mapping family holds `{0}` plus its written keys' words. A struct family does this per member path, and lists
  its keys with the members made non-zero.
- Every other path is unlisted (`{0}`).
- proxy_slots are the written slots that no layout path holds.

**The lead.** It takes the same step.
- Disclose the field diff against its authored r0.
- Re-make its 41 DISCH laws locally, and disclose every moved decision (law, from → to, why).
- Commit no lead output that `holon land` regenerates.

**The session's typing (ruling 1).** The typing is still the session's own here. Re-decide I95's 11 DISCH
disagreements in a pack-like sandbox:
- I95's committed authored files;
- the step's r0 and model_sidecar;
- the session's own typed model.

Predict the outcome before measuring it, and do not assume the laws move.

**Not here.**
- Typing (I96b).
- writer_labels from write semantics (I96b; ruling 2).
- The one blind rerun (after I96b, with E2's predictions on I96b).
