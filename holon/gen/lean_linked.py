"""Lean model, statements and proofs of a holon-linked codec document (I43 rule L1, kind linked; rules L2-L4).

The model: the frozen abbrev Cell := Option (BitVec 8) and Bytes := List Cell, and a structure R_<carrier> per record
carrier (one BitVec 8 per byte, f_<field with . written __>_<k>), verbatim; c_<f> per encoder (a layout: a list
literal over the record's bytes, a tag-dispatched encoder by its tag cell, none for a version without a layout),
decoder (the slice under its ok condition), predicate and loader, and c_ok_<loader>. Reading a byte past the end or
an undefined cell gives 57005, so the decoders' orderings agree with Bend's U32 cells (reading LP-G1). It reads the
document itself, never holon.gen.linked (rule L1).

Statements: rule L3 for the linked kind (a field as the list of its cells, a byte constant as a list of some 0x..).
Classes: open_refl (a round trip, with or without the version premise; a pinned cross-component law: the premises
substituted, then rfl) and counter_decide (a REFUTED law at the record's witness, by decide; witness records and byte
strings as noncomputable definitions).
"""
from __future__ import annotations

from .lean_common import Model, Theorem, Unsupported


def model(codec: dict, stem: str) -> Model:
    """The Lean model of a linked codec document (models/<stem>.lean)."""
    raise Unsupported("not built")


def statements(law: dict, status: str, codec: dict, flip: bool = False) -> list[tuple[str, str]]:
    """[(theorem name, statement text)], as lean_mlaws.statements for the linked kind (flip: G7's flip canary)."""
    raise Unsupported("not built")


def swap_canary(law: dict, codec: dict) -> str | None:
    """G7's perturb text for a round trip without premise whose right side is some <field of width 2 or more>: the
    law's statement with the first two cells of the right side swapped; None for any other law."""
    raise Unsupported("not built")


def theorems(cls: str, law: dict, status: str, record: dict, codec: dict,
             stmts: list[tuple[str, str]]) -> tuple[Theorem, ...]:
    """The theorems of a linked law file: cls is open_refl (PROVED) or counter_decide (REFUTED)."""
    raise Unsupported("not built")
