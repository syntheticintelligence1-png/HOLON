"""M2 S10: refutation engines for the codec fragment (whitepaper §10.5, docs/M2_SPEC.md §3).

Two engines over the *compiled* model, both ending in the same acceptance path:

  qf_ufbv   a z3 encoding of the law's negation over the generated model's
            bit-vector semantics. SAT yields a concrete witness; UNSAT is
            recorded as evidence only (PROVED still requires the kernel).
  fuzz      seeded, deterministic grammar- and sort-boundary fuzzing, evaluated
            on the compiled Bend model, respecting the same input domain as
            holon.refute.in_domain (the restored M0 _in_domain).

A solver answer alone is never a REFUTED: every candidate witness is replayed
through the compiled model and then re-encoded as a counter-law, which only
counts if the existing check (`bend`, plus `--verdict` when available) accepts
it (Thm 6.17). Timeouts and unsupported constructs give UNKNOWN or coverage
debt in spec/M2/coverage/refuter.json, never an approximation.
"""
