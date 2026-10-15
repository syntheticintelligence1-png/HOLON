"""Lean proofs of machine laws (I43 rule L1): one generator per Bend proof class of the verdict re-checked.

  evaluate         an existential law at the record's witness, each conjunct by decide (a perturbed constant then
                   fails for a semantic reason: rule L9's canary keeps the proof)
  nat_split        a lemma for the fixed prefix's end state, then a case split on the Nat binder
  noninterference  a step lemma for the view (the decision reads only the fields its guards read), then induction on
                   the trace
  deadline         per permissionless action, the deadline observer kept
  chain_revert     the require the premise falsifies, by its index in the decision chain
  counter_decide   a REFUTED law: the counter-law at the record's witness by decide, and the refutation from it

Imports no Bend-side module (rule L1). A form a generator cannot prove raises Unsupported.
"""
from __future__ import annotations

from .lean_common import Theorem, Unsupported
from .lean_machine import Ctx

CLASSES = ("evaluate", "nat_split", "noninterference", "deadline", "chain_revert", "counter_decide")


def theorems(cls: str, law: dict, status: str, record: dict, ctx: Ctx,
             stmts: list[tuple[str, str]]) -> tuple[Theorem, ...]:
    """The theorems of a machine law file, after the marker: its frozen statements (stmts, from lean_mlaws) with
    their proofs by class cls, and any helper declarations before them. record: the law's record (its status,
    witness and attempts)."""
    raise Unsupported("not built")
