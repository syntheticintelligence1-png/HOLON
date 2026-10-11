"""holon-ir/0.1 (codec laws) -> Lean theorem text.

Mirrors holon.gen.laws: premises become `pin_<v>` functions applied to the
binder (`{h with pcJ := {h.pcJ with f := c, ..}}`, one `with` per chunk), the
claim is translated term-for-term, and the theorem carries `forall` for PROVED
laws and `exists .. /\\ lhs != rhs` for REFUTED laws instantiated at the model
witness. Proofs: `intro; rfl` for proved codec laws (every binder is Header and
pinning reduces cell reads without a match), `by decide` for refuted laws
(fully instantiated, closed goals).
"""
from __future__ import annotations

from .. import facts as F
from . import codec as C

REC_DEPTH = 8192


class Unsupported(Exception):
    """The statement uses a form this emitter cannot express faithfully."""


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
            raise Unsupported(f"contradictory premises on {var}.{field}")
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


LEAN_TYPE = {"Bytes": "List Nat", "Bool": "Bool", "Fields": "List (List Nat)",
             "MaybeFields": "Option (List (List Nat))", "Header": "Hdr"}


def term(t: dict, env: dict[str, str], facts: dict) -> str:
    if "var" in t:
        return env[t["var"]]
    if "bytes" in t:
        return "[" + ", ".join(str(x) for x in hexbytes(t["bytes"])) + "]"
    if "field" in t:
        return f"get_{t['field']} ({term(t['of'], env, facts)})"
    if "call" in t:
        return f"{t['call']} ({', '.join(term(a, env, facts) for a in t['args'])})"
    if "some" in t:
        return f"(some ({term(t['some'], env, facts)}))"
    raise Unsupported(f"term {t}")


def pin_def(facts: dict, var: str, fields: dict[str, list[int]]) -> str:
    """pin_<v> via record update, one nested `with` per header chunk."""
    w = F.widths(facts)
    cells = C.cell_names(facts)
    by_chunk: dict[int, list[str]] = {}
    for f in F.header_fields(facts):
        if f["name"] not in fields:
            continue
        for k in range(w[f["name"]]):
            i = cells.index(f"{f['name']}_{k}")
            by_chunk.setdefault(i // C.CHUNK, []).append(f"{f['name']}_{k} := {fields[f['name']][k]}")
    inner = ", ".join(f"pc{j} := {{ h.pc{j} with {', '.join(up)} }}" for j, up in sorted(by_chunk.items()))
    doc = ", ".join(f"{k} = 0x{bytes(v).hex()}" for k, v in sorted(fields.items()))
    return (f"-- premises on {var}, by pinning: {doc}\n"
            f"def pin_{var} (h : Hdr) : Hdr := {{ h with {inner} }}\n")


def header_literal(facts: dict, fields: dict[str, str]) -> str:
    """Lean literal of a header witness {"field": "0x.."}."""
    w = F.widths(facts)
    chs = C.chunks(facts)
    flat = []
    for f in F.header_fields(facts):
        if f["name"] not in fields:
            raise Unsupported(f"header witness missing field {f['name']}")
        flat += hexbytes(fields[f["name"]])
    parts = []
    for j, ch in enumerate(chs):
        vals = " ".join(str(flat[C.cell_names(facts).index(c)]) for c in ch)
        parts.append(f"(HC{j}.mk {vals})")
    return "Hdr.mk " + " ".join(parts)


def emit(law: dict, facts: dict, counter: bool = False, witness=None,
         note: str = "") -> tuple[str, list[str]]:
    """(theorem block text, emitted def lines before it)."""
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
    env = {v: (f"(pin_{v} {v})" if v in pins else v) for v in types}
    lhs, rhs = term(a, env, facts), term(b, env, facts)
    name = law_name(law["law_id"], counter)
    defs = [pin_def(facts, v, pins[v]) for v in sorted(pins)]
    if not counter:
        for v, t in types.items():
            if t != "Header":
                raise Unsupported(f"forall over {t} needs induction (not in M0)")
        bnd = " ".join(f"({v} : Hdr)" for v in types)
        stmt = f"forall {bnd}, {lhs} = {rhs}"
        proof = "by\n  intro " + " ".join(types) + "\n  rfl"
    else:
        if witness is None:
            raise Unsupported("refuted law without a witness")
        wargs = []
        for v, t in types.items():
            if v not in witness:
                raise Unsupported(f"witness has no value for binder {v}")
            if t == "Header":
                wargs.append(header_literal(facts, witness[v]))
            elif t == "Bytes":
                wargs.append("[" + ", ".join(str(x) for x in hexbytes(witness[v])) + "]")
            else:
                raise Unsupported(f"binder type {t}")
        bnd = " ".join(f"({v} : {LEAN_TYPE[t]})" for v, t in types.items())
        stmt = f"exists {bnd}, ({lhs} != {rhs})"
        proof = "by exact ⟨" + ", ".join(wargs + ["by decide"]) + "⟩"
    block = f"set_option maxRecDepth {REC_DEPTH} in\nset_option maxHeartbeats 16000000 in\ntheorem {name} : {stmt} := {proof}\n"
    return block, defs
