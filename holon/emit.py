"""Law IR -> LAWS.bend + PROOF.bend (M0_SPEC section 6, BEND_PRIMER 5.2-5.4).

Premises `field == const` are applied through a generated `pin_<law>` def in
LAWS.bend. Proof class "refl_after_open": open every Header binder, then {==}.
Counter-laws use the `exs` form with a concrete witness and a motive rewrite.
"""
from __future__ import annotations

import re

from .facts import widths
from .gen_model import field_names

MODEL_IMPORT = "../model/morph_header.bend"

_BINDER_TYPE = {"Header": "M.Hdr", "Bytes": "List<&2, U32>"}
_EQ_FN = {"Bytes": "bytes_eq", "Bool": "bool_eq", "Fields": "fields_eq",
          "Maybe<Fields>": "maybe_fields_eq"}


def pins_of(law: dict) -> dict:
    """{binder var: {field: bytes}} from eq(field of var, bytes) premises."""
    pins: dict = {}
    for prem in law["statement"].get("assume", []):
        a, b = prem["eq"]
        if "field" in a and "of" in a and "var" in a["of"] and "bytes" in b:
            pins.setdefault(a["of"]["var"], {})[a["field"]] = b["bytes"]
        else:
            raise ValueError(f"unsupported premise {prem}")
    return pins


def premise_strings(law: dict) -> list:
    out = []
    for prem in law["statement"].get("assume", []):
        a, b = prem["eq"]
        out.append(f"{a.get('field', '?')} of {a.get('of', {}).get('var', '?')} == {b.get('bytes', '?')}")
    return out


def _pin_name(law_id: str, var: str) -> str:
    return f"pin_{law_id.lower()}_{var}"


def _claim_type(law: dict, facts: dict) -> str:
    a, _ = law["statement"]["claim"]["eq"]
    return _term_type(a, law, facts)


def _term_type(t: dict, law: dict, facts: dict) -> str:
    if "call" in t:
        return facts["functions"][t["call"]]["to"]
    if "some" in t:
        return f"Maybe<Fields>" if True else ""
    if "var" in t:
        return {b["name"]: b["type"] for b in law["statement"]["forall"]}[t["var"]]
    if "bytes" in t or "field" in t:
        return "Bytes"
    raise ValueError(t)


def _term_bend(t: dict, pins: dict, law_id: str, at_witness=None, pin_mod="") -> str:
    """Render an IR term as a Bend expression.

    pins: {var: pin_def_name} (local def inside LAWS.bend). at_witness:
    {var: bend literal} replaces bound variables by literals (used in
    counter-law motives); pin_mod qualifies the pin def there ("Laws.").
    """
    if "var" in t:
        v = t["var"]
        if at_witness and v in at_witness:
            return f"{pin_mod}{pins[v]}({at_witness[v]})" if v in pins else at_witness[v]
        return f"{pins[v]}({v})" if v in pins else v
    if "bytes" in t:
        bs = bytes.fromhex(t["bytes"][2:])
        return "[" + ", ".join(str(b) for b in bs) + "]"
    if "call" in t:
        args = ", ".join(_term_bend(x, pins, law_id, at_witness, pin_mod) for x in t["args"])
        return f"M.{t['call']}({args})"
    if "some" in t:
        return "Some{" + _term_bend(t["some"], pins, law_id, at_witness, pin_mod) + "}"
    if "field" in t:
        raise ValueError("field terms are only supported inside assume clauses")
    raise ValueError(t)


def _pin_defs(law: dict, facts: dict, pins: dict) -> list:
    """Bend source of one pin def per pinned binder."""
    out = []
    names = field_names(facts)
    w = widths(facts)
    btypes = {b["name"]: b["type"] for b in law["statement"]["forall"]}
    for var in sorted(pins):
        if btypes[var] != "Header":
            raise ValueError("pinning is only defined for Header binders")
        pinned = {}
        for fname, hexs in pins[var].items():
            bs = bytes.fromhex(hexs[2:])
            if len(bs) != w[fname]:
                raise ValueError(f"premise width mismatch on {fname}")
            for k, v in enumerate(bs):
                pinned[f"{fname}_{k}"] = str(v)
        pn = _pin_name(law["law_id"], var)
        out.append(f"def {pn}(h: M.Hdr) -> M.Hdr:")
        out.append("  match h:")
        out.append("    case M." + "Hdr{" + ", ".join(names) + "}:")
        out.append("      M.Hdr{" + ", ".join(pinned.get(n, n) for n in names) + "}")
        out.append("")
    return out


def law_names(laws_file) -> list:
    return re.findall(r"^law\s+([A-Za-z0-9_.]+)\s*:", laws_file.read_text(), re.M)


def emit_laws(law: dict, facts: dict) -> str:
    """LAWS.bend for the direct (for-all) form of a law."""
    pins = {v: _pin_name(law["law_id"], v) for v in pins_of(law)}
    lines = ["import Base", f"import {MODEL_IMPORT} as M", ""]
    lines += _pin_defs(law, facts, pins_of(law))
    a, b = law["statement"]["claim"]["eq"]
    ct = _BEND_TYPE[_claim_type(law, facts)]
    lines.append(f"law {law['law_id'].lower()}:")
    for bd in law["statement"]["forall"]:
        lines.append(f"  for {bd['name']}: {_BINDER_TYPE[bd['type']]}")
    lhs = _term_bend(a, pins, law["law_id"])
    rhs = _term_bend(b, pins, law["law_id"])
    lines.append(f"  {{{lhs} == {rhs} : {ct}}}")
    lines.append("")
    return "\n".join(lines)


def emit_proof(law: dict, facts: dict) -> str:
    """PROOF.bend, proof class refl_after_open."""
    names = field_names(facts)
    binders = law["statement"]["forall"]
    args = ", ".join(b["name"] for b in binders)
    lines = ["import Base", f"import {MODEL_IMPORT} as M", "import ./LAWS.bend as Laws", ""]
    lines.append(f"def Laws.{law['law_id'].lower()}({args}):")
    hdrs = [b["name"] for b in binders if b["type"] == "Header"]
    if hdrs:
        lines.append(f"  match {hdrs[0]}:")
        lines.append(f"    case M.Hdr{{{', '.join(names)}}}:")
        lines.append("      {==}")
    else:
        lines.append("  {==}")
    lines.append("")
    return "\n".join(lines)


def emit_counter_laws(law: dict, facts: dict, witness: dict) -> str:
    """LAWS.bend for the exs counter-law cl_<law_id> (BEND_PRIMER 5.4)."""
    pins = {v: _pin_name(law["law_id"], v) for v in pins_of(law)}
    lines = ["import Base", f"import {MODEL_IMPORT} as M", ""]
    lines += _pin_defs(law, facts, pins_of(law))
    a, b = law["statement"]["claim"]["eq"]
    ct = _BEND_TYPE[_claim_type(law, facts)]
    lines.append(f"law cl_{law['law_id'].lower()}:")
    for bd in law["statement"]["forall"]:
        lines.append(f"  exs {bd['name']}: {_BINDER_TYPE[bd['type']]}")
    lhs = _term_bend(a, pins, law["law_id"])
    rhs = _term_bend(b, pins, law["law_id"])
    lines.append(f"  {{{lhs} != {rhs} : {ct}}}")
    lines.append("")
    return "\n".join(lines)


def _witness_literal(btype: str, value, facts: dict) -> str:
    if btype == "Header":
        names = field_names(facts)
        w = widths(facts)
        vals = []
        for f, wd in w.items():
            bs = bytes.fromhex(value[f][2:])
            vals.extend(str(b) for b in bs)
        return "M.Hdr{" + ", ".join(vals) + "}"
    if btype == "Bytes":
        bs = bytes.fromhex(value[2:])
        return "[" + ", ".join(str(b) for b in bs) + "]"
    raise ValueError(btype)


def emit_counter_proof(law: dict, facts: dict, witness: dict) -> str:
    """PROOF.bend for the exs counter-law: (W, e => (%e : is_true(eq(_, L(W))); Unit{}))."""
    pins = {v: _pin_name(law["law_id"], v) for v in pins_of(law)}
    btypes = {b["name"]: b["type"] for b in law["statement"]["forall"]}
    wlit = {b["name"]: _witness_literal(btypes[b["name"]], witness[b["name"]], facts)
            for b in law["statement"]["forall"]}
    a, _ = law["statement"]["claim"]["eq"]
    ct = _claim_type(law, facts)
    eqfn = _EQ_FN[ct]
    lhs_w = _term_bend(a, pins, law["law_id"], at_witness=wlit, pin_mod="Laws.")
    wlit_str = ", ".join(wlit[b["name"]] for b in law["statement"]["forall"])
    lines = ["import Base", f"import {MODEL_IMPORT} as M", "import ./LAWS.bend as Laws", ""]
    lines.append(f"def Laws.cl_{law['law_id'].lower()}():")
    lines.append(f"  ({wlit_str}, e => (%e : M.is_true(M.{eqfn}(_, {lhs_w}))")
    lines.append("  Unit{}))")
    lines.append("")
    return "\n".join(lines)


_BEND_TYPE = {"Bytes": "List<&2, U32>", "Bool": "Bool",
              "Fields": "List<&2, List<&2, U32>>",
              "Maybe<Fields>": "Maybe<&2, List<&2, List<&2, U32>>>",
              "Header": "M.Hdr"}
