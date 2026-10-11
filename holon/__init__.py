"""HOLON: violations as obstructions to commutation, with proof-carrying obligations in Bend 2.

Package map (whitepaper Appendix H):
  ir          law IR (holon-ir/0.1): canonical JSON, statement hashes, loading
  facts       fact sets: loading, hashing, typing of fact functions
  layout      layout algebra (whitepaper §10.2)
  bend        the pinned Bend 2 checker: invocation, environment safety
  gen/        generators: model (facts -> Bend), laws (IR -> Bend), proofs (per class)
  model_eval  compiled-model evaluation (Bend -> ES module -> node)
  refute      deterministic witness search on the compiled model
  pipeline    `holon run`: proof attempt, refutation, result records
  gate        `holon gate`: G1-G5, G7, G11, GENV, canaries
"""

__version__ = "0.1.0"
