"""Law emitter: law IR -> LAWS.bend (whitepaper §8.4, §8.9).

The emitter is deterministic and never weakens a statement (AGENTS.md rule 2):
  * every `assume` clause is applied, by pinning (BEND_PRIMER §5.2): a premise
    `h.f == c` becomes `pin_h(h)`, which rebuilds h with field f replaced by c. A law
    over `pin_h(h)` for all h is equivalent to the law over all h satisfying the premises,
    because pin_h is onto the premise set and the identity on it;
  * a premise the emitter cannot express raises `Unsupported`; the law then ends UNKNOWN
    rather than being emitted without it.

Two emission modes share the same term translation:
  law     `for h: T ... {lhs == rhs : T}`             (the frozen claim)
  counter `exs h: T ... {lhs != rhs : T}`             (its refutation, BEND_PRIMER §5.4)
"""
from __future__ import annotations

from dataclasses import dataclass

from .. import facts as F
from . import model as G

MODEL_ALIAS = "M"


class Unsupported(Exception):
    """The statement uses a form this emitter cannot express faithfully."""


@dataclass
class Emitted:
    name: str            # Bend law name
    text: str            # LAWS.bend contents
    claim_type: str      # IR type of the claim sides (Bytes, Bool, Fields, MaybeFields)
    lhs: str             # Bend term of each side, over the binder names
    rhs: str
    binders: list        # [(name, IR type)]
    pins: dict           # binder -> {field: [byte, ..]}


def law_name(law_id: str, counter: bool = False) -> str:
    return ("cl_" if counter else "") + law_id.lower()


def hexbytes(s: str) -> list[int]:
    if not s.startswith("0x"):
        raise Unsupported(f"bytes literal {s!r}")
    return list(bytes.fromhex(s[2:]))


def binder_types(law: dict) -> dict[str, str]:
    out = {}
    for b in law["statement"]["forall"]:
        if b["type"] not in ("Header", "Bytes"):
            raise Unsupported(f"binder type {b['type']}")
        out[b["name"]] = b["type"]
    return out


def collect_pins(law: dict, facts: dict) -> dict[str, dict[str, list[int]]]:
    """Premises of the form `var.field == bytes` (the only premise form in holon-ir/0.1 M0)."""
    types = binder_types(law)
    w = F.widths(facts)
    pins: dict[str, dict[str, list[int]]] = {}
    for p in law["statement"].get("assume", []):
        a, b = p["eq"]
        if "field" in b and "bytes" in a:
            a, b = b, a
        if not ("field" in a and "var" in a["of"] and "bytes" in b):
            raise Unsupported(f"premise form {p}")
        var, field, val = a["of"]["var"], a["field"], hexbytes(b["bytes"])
        if types.get(var) != "Header" or field not in w or len(val) != w[field]:
            raise Unsupported(f"premise {p}")
        prev = pins.setdefault(var, {}).get(field)
        if prev is not None and prev != val:
            raise Unsupported(f"contradictory premises on {var}.{field}")  # vacuous: refuse (G11)
        pins[var][field] = val
    return pins


def type_of(t: dict, types: dict, facts: dict) -> str:
    if "var" in t:
        return types[t["var"]]
    if "bytes" in t or "field" in t:
        return "Bytes"
    if "call" in t:
        fn = t["call"]
        if fn not in facts["functions"]:
            raise Unsupported(f"unknown function {fn}")
        arg_t, res_t = F.fn_types(facts, fn)
        if len(t["args"]) != 1 or type_of(t["args"][0], types, facts) != arg_t:
            raise Unsupported(f"ill-typed call {t}")
        return res_t
    if "some" in t:
        if type_of(t["some"], types, facts) != "Fields":
            raise Unsupported(f"Some over a non-Fields term {t}")
        return "MaybeFields"
    raise Unsupported(f"term {t}")


def term(t: dict, env: dict[str, str]) -> str:
    """Bend text of an IR term; env maps a binder name to the Bend term it stands for."""
    if "var" in t:
        return env[t["var"]]
    if "bytes" in t:
        return G._list([str(x) for x in hexbytes(t["bytes"])])
    if "field" in t:
        return f"{MODEL_ALIAS}.get_{t['field']}({term(t['of'], env)})"
    if "call" in t:
        return f"{MODEL_ALIAS}.{t['call']}({', '.join(term(a, env) for a in t['args'])})"
    if "some" in t:
        return f"{{Some{{{term(t['some'], env)}}} : {G.MAYBE_FIELDS}}}"
    raise Unsupported(f"term {t}")


def bend_type(ir_type: str) -> str:
    return (f"{MODEL_ALIAS}.Hdr" if ir_type == "Header" else G.BEND_TYPE[ir_type])


def pin_def(facts: dict, var: str, fields: dict[str, list[int]]) -> list[str]:
    w = F.widths(facts)
    vals = []
    for f in F.header_fields(facts):
        n = f["name"]
        vals += [str(fields[n][k]) if n in fields else f"{n}_{k}" for k in range(w[n])]
    pat = "M.Hdr{" + ", ".join(G.cell_names(facts)) + "}"
    doc = ", ".join(f"{k} = 0x{bytes(v).hex()}" for k, v in sorted(fields.items()))
    return [f"# premises on {var}, by pinning: {doc}",
            f"def pin_{var}(h: {MODEL_ALIAS}.Hdr) -> {MODEL_ALIAS}.Hdr:", "  match h:", f"    case {pat}:",
            f"      {MODEL_ALIAS}.Hdr{{" + ", ".join(vals) + "}"]


def emit(law: dict, facts: dict, model_import: str, counter: bool = False,
         header_note: str = "") -> Emitted:
    st = law["statement"]
    types = binder_types(law)
    pins = collect_pins(law, facts)
    claim = st["claim"]
    if set(claim) != {"eq"}:
        raise Unsupported("only eq claims exist in holon-ir/0.1")
    a, b = claim["eq"]
    ta, tb = type_of(a, types, facts), type_of(b, types, facts)
    if ta != tb:
        raise Unsupported(f"claim sides have different types {ta} / {tb}")
    env = {v: (f"pin_{v}({v})" if v in pins else v) for v in types}
    lhs, rhs = term(a, env), term(b, env)
    name = law_name(law["law_id"], counter)
    q = "exs" if counter else "for"
    rel = "!=" if counter else "=="
    lines = ["# GENERATED by holon.gen.laws from the frozen law IR; do not edit.",
             f"# law_id: {law['law_id']}   statement_hash: {header_note}",
             "import Base", f"import {model_import} as {MODEL_ALIAS}", ""]
    for v in sorted(pins):
        lines += pin_def(facts, v, pins[v]) + [""]
    lines += [f"law {name}:"] + [f"  {q} {v}: {bend_type(t)}" for v, t in types.items()]
    lines += [f"  {{{lhs} {rel} {rhs} : {G.BEND_TYPE[ta]}}}"]
    return Emitted(name, "\n".join(lines) + "\n", ta, lhs, rhs, list(types.items()), pins)
