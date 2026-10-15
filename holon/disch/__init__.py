"""DISCH I over the typed M3 model (BUILD_PLAN I31; the contract is the docstring of tests_m3/test_disch.py).

  section.py   the generated DISCH section gen/<M>/disch/models/<model>.disch.bend: B, c, perm_X, the closures and the
               claim of every DISCH law (disch_<x>), over I30's typed model, which it imports (never copies)
  lemmas.py    the core lemmas the proofs use (words, storage, booleans), emitted as fixed generic text and proved in
               every proof file that uses them (never assumed)
  proofs.py    the proof generators: frame and chain_revert per action of a closure, time monotonicity, and the
               witness-evaluation counter-laws, existential proofs and inhabitants (the A30 shape)
  search.py    the refutation and witness search: I30's stages S1-S3 (holon.sorts.search3) with the sidecar's budget
  run.py       `holon run` / `holon replay` for the DISCH laws: law files, decisions, records, the replay report

Nothing here names a target: every name, span and term comes from the document, the analysis and the model.
"""
