"""The proof class residue_bound (BUILD_PLAN I33; tests_m3/test_o12_m3.py rule B6): the residue of two steps of a typed
contract law, bounded over I68's structural store.

It applies to a law with binders s: Reach, x: Act, y: Act and Word binders, the premises is[A](x), ok(x, s), is[B](y),
ok(y, step(x, s)) for two actions of the facts, and a claim that is a conjunction of props {eq: [{cmp: C, args: [A,
B]}, true]} and {eq: [A, B]} over linear Nat sums of N(sread ..) and N(env ..) at s, step(x, s) or step(y, step(x, s))
and Nat literals. prove() writes the law's PROOF.bend or raises NoProof naming what it lacks.
"""
from __future__ import annotations

CLASS = "residue_bound"


class NoProof(ValueError):
    """The class does not apply, or cannot prove a conjunct (named)."""


def prove(law: dict, facts: dict, model_text: str, tables: list, model_import: str, laws_import: str):
    """(PROOF.bend text, a note) of the law, or NoProof."""
    raise NoProof("residue_bound is not built yet: the store, word and loop lemmas it needs are not generated")
