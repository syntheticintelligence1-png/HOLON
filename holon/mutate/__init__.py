"""holon.mutate: A1 mutation adequacy on real code (I61; whitepaper §9.5 auditor A1, §13 "mutation adequacy").

The contract is the docstring of tests_m2/test_mutation_adequacy_i61.py; the rules are the frozen instrument
spec/M2/lib/mutation_catalog_i61.json. Modules:

  common     the instrument, the pinned target, canonical JSON, scratch trees (shared helpers)
  operators  the catalog recomputed from the pinned checkout (catalog, apply) and the diff sheet
  project    the projected header document the laws/M0 statements are decided on
  replay     the replay harness: one role call, a law's claim, a trace law's claim, on a given source tree
  run        the per-mutant pipeline, the harness gate, the rates (run, gate, rate)
  cli        `python -m holon mutate list | sheet | project | replay | gate | run | rate`

This package names no file, function, variable, type or field of the target: everything target-facing comes from the
instrument and the null mutant's documents.
"""
