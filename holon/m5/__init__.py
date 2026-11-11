"""M5's metric definitions and their computation (I54): L6 (bounded games), L9 (environment modules) and L10 (the
intent lane), as preregistered in spec/M5/preregistration.json (rendered from the key I54's thresholds.definitions).

  holon.m5.definitions  the preregistration file and the base populations, read from the base commit through git
  holon.m5.controls     the constructed controls (game and intent) and a solver for a game control's truth
  holon.m5.census       L10's mechanical census of normative doc-comment clauses
  holon.m5.metrics      L6, L9 and L10 from records
  holon.m5.cli          python -m holon m5 prereg|controls|census|metrics

Nothing here is imported by a generator closure; it reads records and truth files and runs no checker.
"""
