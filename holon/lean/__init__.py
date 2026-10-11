"""holon.lean: law IR + generated model -> Lean 4.34 (Lean core only) theorems (whitepaper 8.8-8.9).

For every PROVED and REFUTED law of a milestone, the emitter produces one
self-contained ``gen/lean/<milestone>/<law_id>.lean`` file: the generated model
(a term-for-term mirror of the Bend model) plus a theorem carrying the frozen
statement -- the statement itself for PROVED laws, its negation instantiated at
the model witness for REFUTED laws -- and checks it with the pinned Lean.

Hard rules (M2 spec S8):
  * no ``sorry``, ``axiom``, ``admit``, ``native_decide``, ``implemented_by``,
    ``unsafe`` or ``decide`` on unbounded domains; ``decide`` appears only in
    proofs of fully instantiated (closed) goals;
  * statements are generated from the law IR; no law-ID special cases;
  * a law that cannot be expressed faithfully is recorded ``UNSUPPORTED`` with
    the reason -- never approximated.
"""
