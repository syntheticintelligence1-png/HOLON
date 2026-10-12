"""Lean 4 law emitter: law IR (holon-ir/0.1) -> Lean propositions over the Lean model (I9).

Independent of the Bend law emitter (holon/gen/laws.py): it does not import it, has its own type
checker for IR terms, and states premises as hypotheses (Bend pins them). Never weakens a statement:
every `assume` clause becomes a hypothesis, the claim is the IR's equality, and a form it cannot
express raises LeanUnsupported (the Lean result is then UNKNOWN, never a weaker theorem).

Two statement forms share the term translation:
  law      ∀ (x : T) .., P1 → .. → Pn → lhs = rhs                 (the frozen claim)
  counter  ∃ (x : T) .., P1 ∧ .. ∧ Pn ∧ lhs ≠ rhs                 (its refutation, at a witness)

The claim line ends with CLAIM_MARK so holon.lean.flip_canary can find the main equality.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lean_model import NS, LeanUnsupported, header_layout

CLAIM_MARK = "-- holon:claim"
LEAN_TYPE = {"Header": f"{NS}.Hdr", "Bytes": f"{NS}.Bytes", "Bool": "Bool", "Fields": f"{NS}.Fields",
             "MaybeFields": f"Option {NS}.Fields"}
KIND_SIG = {"encoder": ("Header", "Bytes"), "predicate": ("Bytes", "Bool"), "decoder": ("Bytes", "MaybeFields"),
            "projection": ("Header", "Fields")}
_KEYWORDS = {"fun", "let", "in", "if", "then", "else", "match", "with", "do", "by", "at", "have", "show", "from",
             "theorem", "def", "structure", "where", "end", "namespace", "open", "Type", "Prop", "Sort"}


@dataclass
class LeanLaw:
    law_id: str
    statement_hash: str
    binders: list[tuple[str, str]]          # [(name, IR type)]
    premises: list[str]                     # Lean propositions over the binders
    premise_pins: list[tuple[str, str, list[int]] | None] = field(default_factory=list)  # (var, field, bytes)
    lhs: str = ""
    rhs: str = ""
    claim_type: str = ""

    @property
    def name(self) -> str:
        return self.law_id

    @property
    def counter_name(self) -> str:
        return f"{self.law_id}_counter"

    @property
    def refuted_name(self) -> str:
        return f"{self.law_id}_refuted"


def hexbytes(s: str) -> list[int]:
    if not isinstance(s, str) or not re.fullmatch(r"0x([0-9a-fA-F]{2})*", s):
        raise LeanUnsupported(f"bytes literal {s!r}")
    return list(bytes.fromhex(s[2:]))


def cells_literal(bs: list[int]) -> str:
    return "([" + ", ".join(f"some 0x{b:02x}" for b in bs) + f"] : {NS}.Bytes)"


def _binders(law: dict) -> list[tuple[str, str]]:
    out = []
    for b in law["statement"]["forall"]:
        n, t = b["name"], b["type"]
        if not n.isidentifier() or n in _KEYWORDS or t not in ("Header", "Bytes"):
            raise LeanUnsupported(f"binder {n}: {t}")
        out.append((n, t))
    if len({n for n, _ in out}) != len(out):
        raise LeanUnsupported("repeated binder name")
    return out


def type_of(t: dict, env: dict[str, str], facts: dict) -> str:
    if set(t) == {"var"}:
        if t["var"] not in env:
            raise LeanUnsupported(f"unbound variable {t['var']!r}")
        return env[t["var"]]
    if set(t) == {"bytes"}:
        hexbytes(t["bytes"])
        return "Bytes"
    if set(t) == {"field", "of"}:
        if type_of(t["of"], env, facts) != "Header" or t["field"] not in dict(header_layout(facts)):
            raise LeanUnsupported(f"field access {t!r}")
        return "Bytes"
    if set(t) == {"call", "args"}:
        f = facts["functions"].get(t["call"])
        if f is None or f["kind"] not in KIND_SIG:
            raise LeanUnsupported(f"unknown function {t['call']!r}")
        arg, res = KIND_SIG[f["kind"]]
        if len(t["args"]) != 1 or type_of(t["args"][0], env, facts) != arg:
            raise LeanUnsupported(f"ill-typed call {t!r}")
        return res
    if set(t) == {"some"}:
        if type_of(t["some"], env, facts) != "Fields":
            raise LeanUnsupported(f"`some` over a non-Fields term {t!r}")
        return "MaybeFields"
    raise LeanUnsupported(f"term {t!r}")


def term(t: dict, env: dict[str, str], facts: dict) -> str:
    type_of(t, env, facts)
    if "var" in t:
        return t["var"]
    if "bytes" in t:
        return cells_literal(hexbytes(t["bytes"]))
    if "field" in t:
        return f"{NS}.Hdr.get_{t['field']} {_atom(term(t['of'], env, facts))}"
    if "call" in t:
        return f"{NS}.{t['call']} {_atom(term(t['args'][0], env, facts))}"
    if "some" in t:
        return f"(some {_atom(term(t['some'], env, facts))} : Option {NS}.Fields)"
    raise LeanUnsupported(f"term {t!r}")


def _atom(s: str) -> str:
    return s if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", s) or (s.startswith("(") and s.endswith(")")) else f"({s})"


def _eq(p: dict, env: dict, facts: dict) -> tuple[str, str, str]:
    if set(p) != {"eq"} or len(p["eq"]) != 2:
        raise LeanUnsupported(f"proposition {p!r}: only equalities exist in holon-ir/0.1")
    a, b = p["eq"]
    ta, tb = type_of(a, env, facts), type_of(b, env, facts)
    if ta != tb:
        raise LeanUnsupported(f"sides of different types {ta} / {tb}")
    return term(a, env, facts), term(b, env, facts), ta


def _pin(p: dict, env: dict, facts: dict):
    """(var, field, bytes) when the premise is `var.field == bytes` (either order), else None."""
    a, b = p["eq"]
    if "bytes" in a and "field" in b:
        a, b = b, a
    if set(a) == {"field", "of"} and set(a["of"]) == {"var"} and set(b) == {"bytes"}:
        w = dict(header_layout(facts))[a["field"]]
        bs = hexbytes(b["bytes"])
        if env.get(a["of"]["var"]) == "Header" and len(bs) == w:
            return a["of"]["var"], a["field"], bs
    return None


def emit(law: dict, facts: dict, statement_hash: str) -> LeanLaw:
    if law.get("ir_version") != "holon-ir/0.1":
        raise LeanUnsupported(f"IR version {law.get('ir_version')!r}")
    if not re.fullmatch(r"L_[A-Za-z0-9_]+", law["law_id"]):
        raise LeanUnsupported(f"law id {law['law_id']!r}")
    st = law["statement"]
    binders = _binders(law)
    env = dict(binders)
    prem, pins = [], []
    for p in st.get("assume", []):
        l, r, _ = _eq(p, env, facts)
        prem.append(f"{l} = {r}")
        pins.append(_pin(p, env, facts))
    lhs, rhs, ty = _eq(st["claim"], env, facts)
    return LeanLaw(law["law_id"], statement_hash, binders, prem, pins, lhs, rhs, ty)


# ---------------------------------------------------------------- statement text
def _quant(binders: list[tuple[str, str]], q: str) -> str:
    return f"{q} " + " ".join(f"({n} : {LEAN_TYPE[t]})" for n, t in binders) + ","


def law_prop(ll: LeanLaw, indent: str = "    ", mark: bool = True) -> list[str]:
    """`∀ binders, P1 → .. → lhs = rhs`, one item per line; the claim line carries CLAIM_MARK."""
    out = [indent + _quant(ll.binders, "∀")]
    out += [f"{indent}  {p} →" for p in ll.premises]
    out.append(f"{indent}  {ll.lhs} = {ll.rhs}" + (f" {CLAIM_MARK}" if mark else ""))
    return out


def counter_prop(ll: LeanLaw, indent: str = "    ") -> list[str]:
    """`∃ binders, P1 ∧ .. ∧ lhs ≠ rhs`; the claim line carries CLAIM_MARK."""
    out = [indent + _quant(ll.binders, "∃")]
    out += [f"{indent}  {p} ∧" for p in ll.premises]
    out.append(f"{indent}  {ll.lhs} ≠ {ll.rhs} {CLAIM_MARK}")
    return out


def doc(ll: LeanLaw, law: dict, rendered: str) -> str:
    return (f"/-- {ll.law_id} ({law.get('rule')}/{law.get('subform')}), law IR {law['ir_version']}.\n"
            f"statement_hash: {ll.statement_hash}\n{rendered} -/")


# ---------------------------------------------------------------- witnesses (from the record)
def witness_term(ll: LeanLaw, var: str, value, facts: dict) -> str:
    """Lean value of a recorded witness: a Header as a structure literal, Bytes as a cell list."""
    ty = dict(ll.binders)[var]
    if ty == "Bytes":
        return cells_literal(hexbytes(value))
    lay = header_layout(facts)
    if not isinstance(value, dict) or set(value) != {n for n, _ in lay}:
        raise LeanUnsupported(f"witness for {var} does not list exactly the header fields")
    parts = []
    for n, w in lay:
        bs = hexbytes(value[n])
        if len(bs) != w:
            raise LeanUnsupported(f"witness {var}.{n} has {len(bs)} bytes, expected {w}")
        parts += [f"{n}_{k} := 0x{b:02x}" for k, b in enumerate(bs)]
    return "{ " + ", ".join(parts) + " }"


def witness_name(ll: LeanLaw, var: str) -> str:
    return f"{ll.law_id}_witness_{var}"
