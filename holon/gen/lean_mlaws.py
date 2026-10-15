"""Lean statements of machine laws (I43 rule L3, kinds machine and machine_oracle), rendered from the IR alone.

Binders in IR order with the oracle parameters first (Lean functions, the IR's reading of Fn<A,B>); a Reach binder
as a state and the hypothesis Model.Reach <parameters> <state>, the quantifier group closed at each such hypothesis;
premises as hypotheses (as I9); claim eq/neq as =/≠ and a conjunction as ∧; terms as the interface's functions
(Model.<name>), a view equation through view_<..>. A PROVED law is `theorem <law id> : <statement>`; a REFUTED law is
`theorem <law id>_counter : ∃ <binders>, <premises> ∧ <negated claim>` and `theorem <law id>_refuted : ¬
(<statement>)`. Whitespace aside, every text equals the frozen one.

Imports neither holon.gen.mlaws nor holon.gen.machine (rule L1).
"""
from __future__ import annotations

from .lean_common import Unsupported
from .lean_machine import Ctx


def statements(law: dict, status: str, ctx: Ctx, flip: bool = False) -> list[tuple[str, str]]:
    """[(theorem name, statement text)]: the law's theorem (PROVED), or its counter-law and refutation (REFUTED).
    flip=True renders a REFUTED law's counter-law with its claim's relation flipped (G7's flip canary)."""
    raise Unsupported("not built")


def perturbed_nat(law: dict) -> tuple[dict, int, int] | None:
    """G7's perturb rule for a machine law: a copy of the law whose claim's first Nat equation (the claim, or the
    members of its "all" list in order; the first eq whose right side is a Nat literal) has its constant k replaced
    by k + 1, with k and k + 1; None when the claim has no such equation."""
    raise Unsupported("not built")


def views(law: dict) -> list[str]:
    """The views a law's statement names: every proj term's field set, sorted and joined by "__"."""
    raise Unsupported("not built")


def site_ids(law: dict) -> list[str]:
    """Every site id of a law's statement (its {"site": id, ...} terms), in pre-order."""
    raise Unsupported("not built")
