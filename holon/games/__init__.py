"""Bounded games over a target's REFUTED findings (I56; key I56's definitions, L6 by I54's definition).

  holon.games.flows    the value-flow document (VM1-VM4) generated from the deployment's extracted documents, and V9
  holon.games.run      a schedule run on the run member's extracted model, and its flows to a set of deviators
  holon.games.engine   the complete solver of a game document (every schedule of distinct actions)
  holon.games.target   a finding's witness game (the witness-form table, single-deviator legality)
  holon.games.bendgen  one Bend module per game, its laws and proofs (class verdicts computed inside Bend)
  holon.games.econ     the DISCH-econ readings (N3 over attribution witnesses, O35 over a self-controlled law's loop)
  holon.games.metric   L6 (holon.m5.metrics.l6, unchanged) after V9
  holon.games.cli      python -m holon games flows|run [--check]

Target-agnostic: every target fact comes from the documents and the game sidecar the CLI is given. Nothing here is
imported by a generator closure.
"""
