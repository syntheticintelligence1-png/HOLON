"""M2 A1 mutation-adequacy harness (docs/M2_SPEC.md §1).

Applies each spec/M2 mutant to a fresh worktree of the pinned morph checkout,
re-extracts header facts (S2 + S3 via holon.assemble), runs the M0 law
pipeline, and scores mutants as detected iff at least one law's status
differs from the unmutated baseline. The contract (apply rule, detection,
miss labels, equivalence, score) is spec/M2/mutants.json — read, never edited.
"""
