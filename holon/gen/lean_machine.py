"""The Lean model of a holon-facts/0.2 machine document (I43 rule L1, kinds machine and machine_oracle; rules L2, L4).

The model reads the facts document itself, never holon.gen.machine (the Bend emitter), and the target library
through its Lean twin: hand-written target input next to the Bend library, in files <lib dir>/*.lean.json (outside
the *.lib.json glob of the generator closures). Inside `namespace Model`, in order:

  - the frozen data types, verbatim: Obs, T_<record>, St, Act (deriving DecidableEq);
  - the twin's declarations and the facts definitions, in dependency order;
  - per action the decision over the fields its guards read, its execution, its step; then step, run (a left
    fold), s0, obs, fn_runs_ok, fn_last_ok, fn_no_code, fn_perm, fn_cost, fn_elapsed, fn_is_<a>, the consumers, the
    observers ob_<o> and the migrations mig_<m>;
  - for machine_oracle the oracle parameters p_<name> first in every function whose evaluation reaches them, and the
    site declarations holon.gen.lean_sites writes;
  - the frozen statement-level declarations, verbatim: the views V_<..> and view_<..>, and Reach (after step, s0).

Every function is structurally recursive and every condition a Bool (Nat.ble, Nat.blt, Nat.beq, &&, ||, !), so the
differential samples reduce by decide. Names: the interface's fixed prefixes (rule L2); internal helpers use
prefixes that collide with no name of the frozen texts.

Ctx is the compiled document (names, types, the expression compiler), which lean_mlaws, lean_mproofs and lean_sites
build on.
"""
from __future__ import annotations

from pathlib import Path

from .lean_common import Model, Unsupported


class Ctx:
    """One facts document compiled for Lean: kind (machine | machine_oracle), the oracle parameters {name: Fn type}
    in sidecar order, the library twin and the Bend model's stem."""

    def __init__(self, facts: dict, kind: str, params: dict[str, str], lib: dict, stem: str):
        raise Unsupported("not built")

    def ty(self, facts_type: str) -> str:
        """A facts type as a Lean type, unqualified (inside namespace Model): Nat, Bool, List .., T_<record>, St."""
        raise Unsupported("not built")

    def expr(self, e, env: dict[str, tuple[str, str]]) -> tuple[str, str]:
        """A facts expression as (Lean term, facts type); env maps a facts variable to (Lean term, facts type).
        Conditions compile to Bool terms, never to Prop."""
        raise Unsupported("not built")

    def def_name(self, d: str) -> str:
        """The Lean name of facts definition d."""
        raise Unsupported("not built")

    def def_params(self, d: str) -> list[tuple[str, str]]:
        """Facts definition d's parameters: [(name, facts type)]."""
        raise Unsupported("not built")

    def ctor(self, a: str) -> str:
        """The Act constructor of action a: Act.a_<a>."""
        raise Unsupported("not built")

    def inp(self, n: str) -> str:
        """The binder of action input n: i_<n>."""
        raise Unsupported("not built")

    def field(self, s_term: str, f: str) -> str:
        """State field f of the state term s_term: <s_term>.f_<f>."""
        raise Unsupported("not built")

    def pbinders(self) -> str:
        """The oracle-parameter binders "(p_<name> : A → B) ..", or "" without parameters."""
        raise Unsupported("not built")

    def pargs(self) -> str:
        """The oracle-parameter arguments " p_<name> ..", or "" without parameters."""
        raise Unsupported("not built")

    def guard_walk(self, a: str, upto: int, s_term: str) -> list[tuple[str, str, str]]:
        """Action a's guards before index upto, in source order, over the state term s_term: ("let", name, term) or
        ("require", Bool term, revert code)."""
        raise Unsupported("not built")


def lib_twin(anchor_facts: Path, root: Path) -> dict:
    """The Lean twin of the target libraries that apply to a facts document: <anchor's dir>/../lib/*.lean.json and
    spec/lib/*.lean.json, merged in that order. anchor_facts: the document the libraries are found from (a law's
    facts; for an extracted view, the law's own facts document, not the view)."""
    raise Unsupported("not built")


def model(ctx: Ctx, views: list[str], site_decls: list[str]) -> Model:
    """The Lean model of ctx's document: views (V-keys: erased field names, sorted, joined by "__"), and the site
    declarations of holon.gen.lean_sites (machine_oracle only), placed before the views and Reach."""
    raise Unsupported("not built")
