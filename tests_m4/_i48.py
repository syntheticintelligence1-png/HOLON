"""Helpers and invariants for Iteration I48 (Evaluation corpus and unsolved controls)."""
from __future__ import annotations

import re

EXPECTED_SYSTEMS = ("morph", "arbitrum-nitro", "optimism", "taiko")
EXPECTED_RULES = ("PAR", "SORT", "NAT", "OWN", "DISCH", "FACT", "UNDO", "SYM")
EXPECTED_LANGUAGES = ("solidity", "go")

HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

FORBIDDEN_PROOF_TOKENS = ("?", "sorry", "admit", "@unsafe")
EXPECTED_GENERATORS = ("refl", "case_split_guard", "nat_ind", "list_ind", "eq_chain", "evaluate")


def witness_exceeds_budget(law: dict, witness: dict, budget: dict) -> bool:
    """True iff `witness` requires a Nat binder > natMax or a Reach/State prefix longer than prefixDepth.

    Note: `explore.mjs` enumerates prefixes `s` up to `prefixDepth` and evaluates all `step` terms in the
    claim at each prefix, so `step` terms inside `law["statement"]["claim"]` do NOT consume `prefixDepth`.
    """
    _ = law
    prefix_depth = int(budget["prefixDepth"])
    nat_max = int(budget["natMax"])
    for val in witness.values():
        if isinstance(val, int) and not isinstance(val, bool) and val > nat_max:
            return True
        if isinstance(val, dict) and "nat" in val and int(val["nat"]) > nat_max:
            return True
    s_val = witness.get("s")
    if isinstance(s_val, dict) and isinstance(s_val.get("run"), list):
        if len(s_val["run"]) > prefix_depth:
            return True
    return False
