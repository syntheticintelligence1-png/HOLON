"""Role inference (I104, M6 generality; the contract is the docstring of tests_m6/test_i104_roles.py, rules R1-R6).

    python -m holon roles --milestone M --root R --documents P[,P...] --out-dir D
                          [--mode static|static+ai] [--proposed PATH] [--install] [--roles hand|auto]

The rule producers read per-target role sidecars: which extracted fact plays which role. A role sidecar states no
value; it names facts. This package writes those sidecars for any target from its extracted documents:

  holon.roles.infer    the deterministic static inferencer (the primary channel). Every role carries its evidence: the
                       rule of inference and the facts it rests on. Names are tie-breakers, never the evidence.
  holon.roles.propose  the AI proposal channel: a proposal file (holon-roles-proposed/0.1, proposer "agent", no model
                       identifier) is data, read with its sha256 and merged deterministically; static wins on conflict.
  holon.roles.cli      the command: the manifest roles.json (holon-roles/0.1) and the sidecars in the readers' own
                       formats; --install places them under R/spec/<M>/lib/ only where no hand sidecar exists, or
                       replaces them under --roles auto (a scratch root).
  holon.roles.provenance  roles_source of a law: hand where the milestone's sidecar is a hand one, else the source of
                       the generated role the law was derived through.

Soundness. A role only selects which facts a rule producer compares; the producer's law is a claim about those facts,
and the checker decides it. A wrong role therefore gives a law about the wrong facts: it is UNKNOWN, PROVED (a true
claim about facts nobody meant), or REFUTED with a witness that the replay on the real code does not confirm. None of
these is a finding: holon.roles.provenance.classify labels them role or model defects. A role never adds a premise:
where a hand sidecar supplies a hypothesis (a premise), the generated one supplies none, so the law is at most
stronger, its PROVED still means what it says, and its REFUTED still needs the replay.

Nothing here names a target: every name comes from the documents and the proposal.
"""
