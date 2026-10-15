"""SORT-site predicates in Lean (I43 rules L1, L2, L4, L11; kind machine_oracle), the site laws' proofs.

Lean's own reading of rules R8-R10 of the SORT-site rule, written again from the facts document, the derivation
entry of each site (its site id, span, subtraction and entry points) and the realization-check reasons of the sort
sites sidecar; it imports neither holon.sorts nor any Bend emitter (rule L1).

  ro_<x>    the site's raw obligation: subtrahend <= minuend of its subtraction, a Bool function of the subtraction's
            free variables in order of first occurrence, with the model's own reading of each facts definition;
  site_<x>  per entry-point action, the guards walked as the decision chain walks them (a let binds; a failing
            require stops the action: true), and at each hit point the raw obligation under its path condition;
            true for every other action. It reaches ro_<x> (rule L4), so it goes false when the site loses its
            protection (rule L11's mutation canary);
  hit_<x>   true iff evaluating the action evaluates the subtraction at least once.

A site's name comes from its site id (rule R7: site_<where>_<x8>), never from a law id.

Classes: coercion_guard (a PROVED site law: at each hit, the earlier condition that implies the obligation; Reach is
never used) and counter_decide (a REFUTED site law: the record's witness, its oracle instance as a Lean function, its
state as a run from s0 with an explicit Reach proof).
"""
from __future__ import annotations

from .lean_common import Theorem, Unsupported
from .lean_machine import Ctx


def site_name(site_id: str) -> str:
    """Rule R7: site_<where>_<x8> of a site id "<model>:<span>:<x8>"."""
    raise Unsupported("not built")


def hit_points(facts: dict, entry: dict, real_reasons: list[str]) -> dict[str, list[dict]]:
    """Rules R8-R10: per action, where it evaluates the site's subtraction ({"action", "at", "kind", "via"}, as a
    derivation entry's "hits" lists them)."""
    raise Unsupported("not built")


def section(ctx: Ctx, entries: list[dict], sidecar: dict) -> list[str]:
    """The site declarations of ctx's model (inside namespace Model): ro_<x>, the per-action chains, site_<x> and
    hit_<x> for every derivation entry in entries."""
    raise Unsupported("not built")


def theorems(cls: str, law: dict, status: str, record: dict, ctx: Ctx, stmts: list[tuple[str, str]],
             entry: dict) -> tuple[Theorem, ...]:
    """The theorems of a site law file: cls is coercion_guard (PROVED) or counter_decide (REFUTED); entry: the law's
    derivation entry."""
    raise Unsupported("not built")
